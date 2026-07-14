"""A single-threaded, one-shot asyncio runtime for agent resources."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
from collections.abc import Awaitable, Coroutine
from typing import Any, TypeVar, cast


T = TypeVar("T")


class AgentAsyncRuntime:
    """Own one long-lived event loop running in one daemon thread."""

    def __init__(self, thread_name: str = "AgentAsyncRuntime") -> None:
        self._thread_name = thread_name
        self._condition = threading.Condition()
        self._state = "new"
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._startup_error: BaseException | None = None

    def start(self) -> None:
        """Start the owned thread and loop, or wait for another caller to do so."""
        with self._condition:
            while True:
                if self._state == "running":
                    return
                if self._state == "new":
                    self._state = "starting"
                    self._thread = threading.Thread(
                        target=self._thread_main,
                        name=self._thread_name,
                        daemon=True,
                    )
                    self._thread.start()
                elif self._state in {"starting", "stopping"}:
                    self._condition.wait()
                    continue
                elif self._state == "failed":
                    error = self._startup_error
                    raise RuntimeError("Agent async runtime failed to start") from error
                else:
                    raise RuntimeError("Agent async runtime has been stopped")

                while self._state == "starting":
                    self._condition.wait()

    def submit(self, awaitable: Awaitable[T]) -> concurrent.futures.Future[T]:
        """Submit an awaitable to the runtime loop."""
        if self.in_runtime_thread():
            self._close_rejected(awaitable)
            raise RuntimeError("Synchronous submission is not allowed from the runtime thread")

        try:
            self.start()
        except BaseException:
            self._close_rejected(awaitable)
            raise

        with self._condition:
            if self._state != "running" or self._loop is None or self._loop.is_closed():
                self._close_rejected(awaitable)
                raise RuntimeError("Agent async runtime has been stopped")

            coroutine = self._as_coroutine(awaitable)
            try:
                future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
            except BaseException:
                coroutine.close()
                if coroutine is not awaitable:
                    self._close_rejected(awaitable)
                raise
            return cast(concurrent.futures.Future[T], future)

    def run(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        """Submit an awaitable and synchronously return its result."""
        if self.in_runtime_thread():
            self._close_rejected(awaitable)
            raise RuntimeError("Synchronous wait is not allowed from the runtime thread")

        future = self.submit(awaitable)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise

    async def run_async(self, awaitable: Awaitable[T]) -> T:
        """Await work on the runtime without blocking the caller's event loop."""
        if self.in_runtime_thread():
            return await awaitable

        try:
            future = self.submit(awaitable)
        except BaseException:
            # submit() owns rejection cleanup, including closing coroutine inputs.
            raise
        return await asyncio.wrap_future(future)

    def in_runtime_thread(self) -> bool:
        """Return whether the caller is the owned runtime thread."""
        thread = self._thread
        return thread is not None and thread.ident == threading.get_ident()

    @property
    def is_running(self) -> bool:
        """Return whether the runtime can currently accept submissions."""
        with self._condition:
            return (
                self._state == "running"
                and self._thread is not None
                and self._thread.is_alive()
                and self._loop is not None
                and not self._loop.is_closed()
            )

    def stop(
        self,
        cleanup_awaitable: Awaitable[Any] | None = None,
        timeout: float | None = 30.0,
    ) -> None:
        """Run optional cleanup, then drain and close the owned runtime."""
        if self.in_runtime_thread():
            if cleanup_awaitable is not None:
                self._close_rejected(cleanup_awaitable)
            raise RuntimeError("Stopping from the runtime thread is not allowed")

        if cleanup_awaitable is not None:
            with self._condition:
                should_start = self._state == "new"
            if should_start:
                try:
                    self.start()
                except BaseException:
                    self._close_rejected(cleanup_awaitable)
                    raise

        cleanup_future: concurrent.futures.Future[Any] | None = None
        cleanup_error: BaseException | None = None
        thread: threading.Thread | None
        loop: asyncio.AbstractEventLoop | None

        with self._condition:
            while self._state == "starting":
                self._condition.wait()

            if self._state == "stopping":
                if cleanup_awaitable is not None:
                    self._close_rejected(cleanup_awaitable)
                while self._state == "stopping":
                    self._condition.wait()
                return

            if self._state in {"stopped", "failed"}:
                if cleanup_awaitable is not None:
                    self._close_rejected(cleanup_awaitable)
                return

            if self._state == "new":
                self._state = "stopped"
                self._condition.notify_all()
                return

            self._state = "stopping"
            thread = self._thread
            loop = self._loop
            if cleanup_awaitable is not None and loop is not None:
                coroutine = self._as_coroutine(cleanup_awaitable)
                try:
                    cleanup_future = asyncio.run_coroutine_threadsafe(coroutine, loop)
                except BaseException as exc:
                    coroutine.close()
                    if coroutine is not cleanup_awaitable:
                        self._close_rejected(cleanup_awaitable)
                    cleanup_error = exc

        if cleanup_future is not None:
            try:
                cleanup_future.result(timeout=timeout)
            except BaseException as exc:
                cleanup_future.cancel()
                cleanup_error = exc

        if loop is not None:
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass
        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive() and cleanup_error is None:
                cleanup_error = concurrent.futures.TimeoutError(
                    "Timed out waiting for the agent async runtime thread to stop"
                )

        if cleanup_error is not None:
            raise cleanup_error

    @staticmethod
    def _close_rejected(awaitable: Awaitable[Any]) -> None:
        if inspect.iscoroutine(awaitable):
            awaitable.close()

    @staticmethod
    def _as_coroutine(awaitable: Awaitable[T]) -> Coroutine[Any, Any, T]:
        if inspect.iscoroutine(awaitable):
            return cast(Coroutine[Any, Any, T], awaitable)

        async def await_input() -> T:
            return await awaitable

        return await_input()

    def _thread_main(self) -> None:
        loop: asyncio.AbstractEventLoop | None = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with self._condition:
                self._loop = loop
                self._state = "running"
                self._condition.notify_all()
            loop.run_forever()
        except BaseException as exc:
            with self._condition:
                if self._state == "starting":
                    self._startup_error = exc
                    self._state = "failed"
                    self._condition.notify_all()
        finally:
            if loop is not None:
                self._drain_and_close(loop)
            with self._condition:
                if self._state != "failed":
                    self._state = "stopped"
                self._condition.notify_all()

    @staticmethod
    def _drain_and_close(loop: asyncio.AbstractEventLoop) -> None:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        asyncio.set_event_loop(None)
        loop.close()
