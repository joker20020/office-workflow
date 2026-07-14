from __future__ import annotations

import asyncio
import concurrent.futures
import gc
import threading
import time
import warnings
from collections.abc import Coroutine
from typing import Any

import pytest

from src.agent.async_runtime import AgentAsyncRuntime


@pytest.fixture
def runtime() -> AgentAsyncRuntime:
    instance = AgentAsyncRuntime()
    yield instance
    if instance.is_running:
        instance.stop()


async def _execution_context() -> tuple[asyncio.AbstractEventLoop, str, int]:
    return asyncio.get_running_loop(), threading.current_thread().name, threading.get_ident()


def test_sequential_submissions_share_open_loop_and_named_thread() -> None:
    runtime = AgentAsyncRuntime(thread_name="agent-runtime-test")
    try:
        first_loop, first_name, first_ident = runtime.run(_execution_context())
        second_loop, second_name, second_ident = runtime.run(_execution_context())

        assert first_loop is second_loop
        assert not first_loop.is_closed()
        assert first_name == second_name == "agent-runtime-test"
        assert first_ident == second_ident
    finally:
        runtime.stop()

    assert first_loop.is_closed()
    assert not any(thread.name == "agent-runtime-test" for thread in threading.enumerate())


def test_concurrent_start_callers_create_one_runtime_thread_and_loop() -> None:
    runtime = AgentAsyncRuntime(thread_name="concurrent-start-runtime")
    barrier = threading.Barrier(9)
    errors: list[BaseException] = []

    def start() -> None:
        barrier.wait()
        try:
            runtime.start()
        except BaseException as exc:
            errors.append(exc)

    workers = [threading.Thread(target=start) for _ in range(8)]
    for worker in workers:
        worker.start()
    barrier.wait()
    for worker in workers:
        worker.join(timeout=5)

    try:
        loop, name, ident = runtime.run(_execution_context())
        contexts = [runtime.run(_execution_context()) for _ in range(4)]
        assert errors == []
        assert all(not worker.is_alive() for worker in workers)
        assert all(item == (loop, name, ident) for item in contexts)
        assert sum(thread.name == "concurrent-start-runtime" for thread in threading.enumerate()) == 1
    finally:
        runtime.stop()


def test_startup_failure_unblocks_concurrent_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = AgentAsyncRuntime()
    barrier = threading.Barrier(3)
    errors: list[BaseException] = []

    def fail_to_create_loop() -> asyncio.AbstractEventLoop:
        raise OSError("loop creation failed")

    monkeypatch.setattr(asyncio, "new_event_loop", fail_to_create_loop)

    def start() -> None:
        barrier.wait()
        try:
            runtime.start()
        except BaseException as exc:
            errors.append(exc)

    workers = [threading.Thread(target=start) for _ in range(2)]
    for worker in workers:
        worker.start()
    barrier.wait()
    for worker in workers:
        worker.join(timeout=5)

    assert all(not worker.is_alive() for worker in workers)
    assert len(errors) == 2
    assert all(isinstance(exc, RuntimeError) for exc in errors)
    assert all("start" in str(exc).lower() for exc in errors)
    assert all(isinstance(exc.__cause__, OSError) for exc in errors)
    assert not runtime.is_running


def test_start_is_idempotent_while_running(runtime: AgentAsyncRuntime) -> None:
    runtime.start()
    first = runtime.run(_execution_context())
    runtime.start()
    second = runtime.run(_execution_context())
    assert first == second


def test_submit_and_run_propagate_results_and_exceptions(runtime: AgentAsyncRuntime) -> None:
    async def result() -> int:
        return 42

    async def failure() -> None:
        raise ValueError("boom")

    submitted = runtime.submit(result())
    assert isinstance(submitted, concurrent.futures.Future)
    assert submitted.result(timeout=5) == 42
    with pytest.raises(ValueError, match="boom"):
        runtime.run(failure())


@pytest.mark.asyncio
async def test_run_async_bridges_from_caller_loop_to_runtime_loop(
    runtime: AgentAsyncRuntime,
) -> None:
    caller_loop = asyncio.get_running_loop()
    execution_loop, _, _ = await runtime.run_async(_execution_context())
    assert execution_loop is not caller_loop


def test_run_async_directly_awaits_when_called_on_runtime_thread(
    runtime: AgentAsyncRuntime,
) -> None:
    async def nested() -> tuple[asyncio.AbstractEventLoop, asyncio.AbstractEventLoop]:
        outer_loop = asyncio.get_running_loop()
        inner_loop, _, _ = await runtime.run_async(_execution_context())
        return outer_loop, inner_loop

    outer_loop, inner_loop = runtime.run(nested())
    assert inner_loop is outer_loop


def test_runtime_thread_rejects_sync_submit_and_run_without_warnings(
    runtime: AgentAsyncRuntime,
) -> None:
    async def rejected_calls() -> list[str]:
        messages: list[str] = []
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for call in (runtime.submit, runtime.run):
                coroutine = asyncio.sleep(0)
                with pytest.raises(RuntimeError, match="runtime thread") as exc_info:
                    call(coroutine)
                messages.append(str(exc_info.value))
            await asyncio.sleep(0)
            assert not [item for item in caught if "was never awaited" in str(item.message)]
        return messages

    messages = runtime.run(rejected_calls())
    assert len(messages) == 2


def test_run_timeout_cancels_submitted_coroutine(runtime: AgentAsyncRuntime) -> None:
    cancelled = threading.Event()

    async def wait_forever() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with pytest.raises(concurrent.futures.TimeoutError):
        runtime.run(wait_forever(), timeout=0.01)
    assert cancelled.wait(timeout=5)


def test_stop_cleanup_runs_on_runtime_loop() -> None:
    runtime = AgentAsyncRuntime()
    loop, _, _ = runtime.run(_execution_context())
    observed: list[asyncio.AbstractEventLoop] = []

    async def cleanup() -> None:
        observed.append(asyncio.get_running_loop())

    runtime.stop(cleanup())
    assert observed == [loop]
    assert loop.is_closed()


def test_cleanup_exception_still_fully_stops_runtime() -> None:
    runtime = AgentAsyncRuntime(thread_name="cleanup-error-runtime")
    loop, _, _ = runtime.run(_execution_context())

    async def cleanup() -> None:
        raise LookupError("cleanup failed")

    with pytest.raises(LookupError, match="cleanup failed"):
        runtime.stop(cleanup())

    assert not runtime.is_running
    assert loop.is_closed()
    assert not any(thread.name == "cleanup-error-runtime" for thread in threading.enumerate())


def test_cleanup_error_is_raised_only_after_delayed_drain_and_loop_close() -> None:
    runtime = AgentAsyncRuntime(thread_name="delayed-cleanup-error-runtime")
    loop, _, _ = runtime.run(_execution_context())
    task_started = threading.Event()
    cancellation_started = threading.Event()
    allow_drain = threading.Event()
    drain_finished = threading.Event()

    async def slow_to_cancel() -> None:
        task_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellation_started.set()
            while not allow_drain.is_set():
                await asyncio.sleep(0.005)
            drain_finished.set()

    async def spawn() -> None:
        asyncio.create_task(slow_to_cancel())

    async def cleanup() -> None:
        raise LookupError("cleanup failed before delayed drain")

    runtime.run(spawn())
    assert task_started.wait(timeout=5)
    release = threading.Timer(0.15, allow_drain.set)
    release.start()
    try:
        with pytest.raises(LookupError, match="cleanup failed before delayed drain"):
            runtime.stop(cleanup(), timeout=0.01)

        assert cancellation_started.is_set()
        assert drain_finished.is_set()
        assert loop.is_closed()
        assert not runtime.is_running
        assert not any(
            thread.name == "delayed-cleanup-error-runtime"
            for thread in threading.enumerate()
        )
    finally:
        allow_drain.set()
        release.cancel()
        deadline = time.monotonic() + 5
        while not loop.is_closed() and time.monotonic() < deadline:
            time.sleep(0.01)


def test_cleanup_scheduling_error_still_fully_stops_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = AgentAsyncRuntime(thread_name="cleanup-scheduling-error-runtime")
    loop, _, _ = runtime.run(_execution_context())

    def reject_scheduling(
        coroutine: Coroutine[Any, Any, Any],
        target_loop: asyncio.AbstractEventLoop,
    ) -> concurrent.futures.Future[Any]:
        raise RuntimeError("cleanup scheduling failed")

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", reject_scheduling)
    try:
        with pytest.raises(RuntimeError, match="cleanup scheduling failed"):
            runtime.stop(asyncio.sleep(0))

        assert not runtime.is_running
        assert loop.is_closed()
        assert not any(
            thread.name == "cleanup-scheduling-error-runtime"
            for thread in threading.enumerate()
        )
    finally:
        if not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)
            deadline = time.monotonic() + 5
            while not loop.is_closed() and time.monotonic() < deadline:
                time.sleep(0.01)


def test_stop_cancels_and_drains_pending_tasks() -> None:
    runtime = AgentAsyncRuntime()
    started = threading.Event()
    cancelled = threading.Event()

    async def background() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def spawn() -> asyncio.Task[None]:
        return asyncio.create_task(background())

    task = runtime.run(spawn())
    assert started.wait(timeout=5)
    runtime.stop()
    assert task.cancelled()
    assert cancelled.is_set()


def test_repeated_stop_is_safe() -> None:
    runtime = AgentAsyncRuntime()
    runtime.start()
    runtime.stop()
    runtime.stop()


def test_stop_from_runtime_thread_is_rejected_without_stopping(
    runtime: AgentAsyncRuntime,
) -> None:
    async def attempt_stop() -> str:
        with pytest.raises(RuntimeError, match="runtime thread") as exc_info:
            runtime.stop()
        return str(exc_info.value)

    assert "runtime thread" in runtime.run(attempt_stop())
    assert runtime.is_running


def test_start_submit_run_and_external_run_async_fail_after_stop() -> None:
    runtime = AgentAsyncRuntime()
    runtime.start()
    runtime.stop()

    with pytest.raises(RuntimeError, match="stopped"):
        runtime.start()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeError, match="stopped"):
            runtime.submit(asyncio.sleep(0))
        with pytest.raises(RuntimeError, match="stopped"):
            runtime.run(asyncio.sleep(0))

        async def external_attempt() -> None:
            with pytest.raises(RuntimeError, match="stopped"):
                await runtime.run_async(asyncio.sleep(0))

        asyncio.run(external_attempt())
        assert not [item for item in caught if "was never awaited" in str(item.message)]


def test_stale_runtime_thread_ident_does_not_bypass_one_shot_rejection() -> None:
    runtime = AgentAsyncRuntime()
    _, _, stopped_ident = runtime.run(_execution_context())
    runtime.stop()
    owned_thread = runtime._thread
    assert owned_thread is not None

    ready = threading.Event()
    proceed = threading.Event()
    child_ident: list[int] = []
    outcomes: list[tuple[str, Any]] = []

    def use_stopped_runtime() -> None:
        child_ident.append(threading.get_ident())
        ready.set()
        proceed.wait(timeout=5)
        try:
            runtime.stop()
            outcomes.append(("stop", "returned"))
        except BaseException as exc:
            outcomes.append(("stop", exc))

        async def run_after_stop() -> None:
            with pytest.raises(RuntimeError, match="stopped"):
                await runtime.run_async(asyncio.sleep(0))

        try:
            asyncio.run(run_after_stop())
            outcomes.append(("run_async", "rejected"))
        except BaseException as exc:
            outcomes.append(("run_async", exc))

    worker = threading.Thread(target=use_stopped_runtime)
    worker.start()
    assert ready.wait(timeout=5)
    original_ident = owned_thread._ident
    assert original_ident == stopped_ident
    owned_thread._ident = child_ident[0]
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            proceed.set()
            worker.join(timeout=10)
            assert not worker.is_alive()
            assert outcomes == [("stop", "returned"), ("run_async", "rejected")]
            assert not [item for item in caught if "was never awaited" in str(item.message)]
    finally:
        owned_thread._ident = original_ident


def test_submit_stop_race_has_explicit_outcomes_and_no_coroutine_warnings() -> None:
    runtime = AgentAsyncRuntime(thread_name="submit-stop-race-runtime")
    task_started = threading.Event()
    cancellation_started = threading.Event()
    allow_drain = threading.Event()
    submission_started = threading.Event()
    outcomes: list[tuple[str, Any]] = []
    stop_errors: list[BaseException] = []

    async def hold_shutdown_open() -> None:
        task_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellation_started.set()
            while not allow_drain.is_set():
                await asyncio.sleep(0.005)

    async def spawn_pending_task() -> None:
        asyncio.create_task(hold_shutdown_open())

    runtime.run(spawn_pending_task())
    assert task_started.wait(timeout=5)

    async def value() -> int:
        return 7

    def stop_runtime() -> None:
        try:
            runtime.stop()
        except BaseException as exc:
            stop_errors.append(exc)

    def submit_during_stop() -> None:
        coroutine: Coroutine[Any, Any, int] = value()
        submission_started.set()
        try:
            runtime.submit(coroutine)
            outcomes.append(("unexpected", "accepted"))
        except BaseException as exc:
            outcomes.append(("rejected", exc))

    stopper = threading.Thread(target=stop_runtime)
    submitter = threading.Thread(target=submit_during_stop)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stopper.start()
        cancellation_observed = cancellation_started.wait(timeout=5)
        if not cancellation_observed:
            allow_drain.set()
            stopper.join(timeout=5)
            pytest.fail(
                "pending task cancellation was not observed; "
                f"stop_errors={stop_errors!r}, loop_closed={runtime.is_running is False}"
            )
        submitter.start()
        assert submission_started.wait(timeout=5)
        allow_drain.set()
        stopper.join(timeout=10)
        submitter.join(timeout=10)
        gc.collect()

        assert not stopper.is_alive()
        assert not submitter.is_alive()
        assert stop_errors == []
        assert len(outcomes) == 1
        assert outcomes[0][0] == "rejected"
        assert isinstance(outcomes[0][1], RuntimeError)
        assert "stopped" in str(outcomes[0][1])
        assert not [item for item in caught if "was never awaited" in str(item.message)]


def test_is_running_tracks_acceptance_state() -> None:
    runtime = AgentAsyncRuntime()
    assert not runtime.is_running
    runtime.start()
    assert runtime.is_running
    runtime.stop()
    assert not runtime.is_running
