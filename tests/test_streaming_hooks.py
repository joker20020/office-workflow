# -*- coding: utf-8 -*-
"""AgentScope 2.0 event-stream reconstruction contracts."""

import asyncio
import threading
from concurrent.futures import Future
from types import SimpleNamespace
from typing import Any, AsyncGenerator, get_args
from unittest.mock import AsyncMock, Mock

import pytest

from agentscope.agent import Agent
from agentscope.event import (
    AgentEvent,
    RequireExternalExecutionEvent,
    RequireUserConfirmEvent,
    ReplyEndEvent,
    ReplyEndReason,
    ReplyStartEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
    UserInterruptEvent,
)
from agentscope.message import AssistantMsg, Msg, UserMsg
from agentscope.middleware import MiddlewareBase

from src.agent.agent_integration import AgentIntegration


def _reply_events(
    *,
    reply_id: str = "reply-1",
    finished_reason: ReplyEndReason = ReplyEndReason.COMPLETED,
) -> list[AgentEvent]:
    return [
        ReplyStartEvent(
            session_id="session-1",
            reply_id=reply_id,
            name="Assistant",
        ),
        TextBlockStartEvent(reply_id=reply_id, block_id="text-1"),
        TextBlockDeltaEvent(
            reply_id=reply_id,
            block_id="text-1",
            delta="Hello",
        ),
        TextBlockDeltaEvent(
            reply_id=reply_id,
            block_id="text-1",
            delta=" world",
        ),
        TextBlockEndEvent(reply_id=reply_id, block_id="text-1"),
        ReplyEndEvent(
            session_id="session-1",
            reply_id=reply_id,
            finished_reason=finished_reason,
        ),
    ]


def test_assistant_msg_append_event_reconstructs_complete_reply() -> None:
    events = _reply_events()
    reply = AssistantMsg(name="Assistant", content=[], id="reply-1")

    for event in events:
        reply.append_event(event)

    assert reply.id == "reply-1"
    assert reply.get_text_content() == "Hello world"
    assert len(reply.content) == 1
    assert reply.content[0].id == "text-1"
    assert reply.content[0].type == "text"
    assert reply.finished_at == events[-1].created_at


class _FakeStreamingAgent:
    def __init__(self, events: list[AgentEvent]) -> None:
        self.events = events
        self.state = SimpleNamespace(reply_id="provisional-reply")
        self.received_inputs: Msg | None = None

    async def reply_stream(self, *, inputs: Msg) -> AsyncGenerator[AgentEvent, None]:
        self.received_inputs = inputs
        for event in self.events:
            yield event


def _integration_with(events: list[AgentEvent]) -> AgentIntegration:
    integration = AgentIntegration.__new__(AgentIntegration)
    integration._agent = _FakeStreamingAgent(events)
    integration._streaming_callbacks = []
    integration._last_response_interrupted = False
    integration._active_reply_task = None
    integration._active_reply_cancel_requests = set()
    integration._reply_ownership_lock = threading.Lock()
    integration._active_reply_owners = []
    integration._current_loop = None
    integration._parked_reply_id = None
    integration._parked_reply_loop = None
    integration._parked_reply_loop_thread = None
    integration._parked_cleanup_future = None
    return integration


@pytest.mark.asyncio
async def test_consume_reply_stream_rebuilds_reply_and_uses_reply_start_id() -> None:
    events = _reply_events(reply_id="server-reply")
    integration = _integration_with(events)
    inputs = UserMsg(name="User", content="Please stream")

    reply = await integration._consume_reply_stream(inputs)

    assert integration._agent.received_inputs is inputs
    assert reply.id == "server-reply"
    assert reply.id != integration._agent.state.reply_id
    assert reply.get_text_content() == "Hello world"
    assert reply.content[0].id == "text-1"
    assert reply.finished_at == events[-1].created_at


def test_notify_stream_event_preserves_events_order_and_callback_shape() -> None:
    events = _reply_events()
    integration = _integration_with(events)
    failing_deliveries: list[AgentEvent] = []
    delivered: list[tuple[Any, dict[str, AgentEvent], AgentEvent]] = []

    def failing_callback(agent: Any, kwargs: dict, output: Any) -> None:
        failing_deliveries.append(output)
        raise RuntimeError("one callback must not stop delivery")

    def recording_callback(
        agent: Any,
        kwargs: dict[str, AgentEvent],
        output: AgentEvent,
    ) -> None:
        delivered.append((agent, kwargs, output))

    integration.register_streaming_callback(failing_callback)
    integration.register_streaming_callback(recording_callback)

    for event in events:
        integration._notify_stream_event(event)

    assert len(failing_deliveries) == len(events)
    assert all(
        received is original
        for received, original in zip(failing_deliveries, events)
    )
    assert len(delivered) == len(events)
    for delivery, original_event in zip(delivered, events):
        agent, kwargs, output = delivery
        assert agent is integration._agent
        assert kwargs == {"event": original_event}
        assert kwargs["event"] is original_event
        assert output is original_event


def test_streaming_callback_annotation_matches_three_argument_protocol() -> None:
    callback_annotation = AgentIntegration.register_streaming_callback.__annotations__[
        "callback"
    ]
    callback_args, return_type = get_args(callback_annotation)

    assert callback_args == [Any, dict[str, Any], Any]
    assert return_type is type(None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("finished_reason", "expected_interrupted"),
    [
        (ReplyEndReason.COMPLETED, False),
        (ReplyEndReason.INTERRUPTED, True),
    ],
)
async def test_reply_end_reason_controls_interrupted_state_and_keeps_partial_text(
    finished_reason: ReplyEndReason,
    expected_interrupted: bool,
) -> None:
    events = _reply_events(finished_reason=finished_reason)
    integration = _integration_with(events)

    reply = await integration._consume_reply_stream(
        UserMsg(name="User", content="Continue"),
    )

    assert integration._last_response_interrupted is expected_interrupted
    assert reply.get_text_content() == "Hello world"
    assert reply.finished_at == events[-1].created_at


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "park_event_type",
    [RequireUserConfirmEvent, RequireExternalExecutionEvent],
)
async def test_park_event_stores_reply_id(park_event_type: type[AgentEvent]) -> None:
    integration = _integration_with(
        [park_event_type(reply_id="parked-reply", tool_calls=[])],
    )

    await integration._consume_reply_stream(UserMsg(name="User", content="pause"))

    assert integration._parked_reply_id == "parked-reply"
    assert integration._parked_reply_loop is asyncio.get_running_loop()


@pytest.mark.asyncio
async def test_parked_cleanup_sends_exact_user_interrupt_event_and_clears_state() -> None:
    integration = _integration_with([])
    integration._parked_reply_id = "parked-reply"
    integration._parked_reply_loop = asyncio.get_running_loop()
    integration._agent = SimpleNamespace(
        reply=AsyncMock(return_value=AssistantMsg(name="Assistant", content=[])),
    )

    await integration._cleanup_parked_reply("parked-reply")

    integration._agent.reply.assert_awaited_once()
    event = integration._agent.reply.await_args.kwargs["inputs"]
    assert isinstance(event, UserInterruptEvent)
    assert event.reply_id == "parked-reply"
    assert not hasattr(event, "reason")
    assert integration._last_response_interrupted is True
    assert integration._parked_reply_id is None
    assert integration._parked_reply_loop is None


class _ParkedSyncAgent(_FakeStreamingAgent):
    def __init__(self) -> None:
        super().__init__(
            [
                ReplyStartEvent(
                    session_id="session-1",
                    reply_id="sync-parked",
                    name="Assistant",
                ),
                RequireUserConfirmEvent(reply_id="sync-parked", tool_calls=[]),
            ],
        )
        self.interrupt_input: UserInterruptEvent | None = None

    async def reply(self, *, inputs: UserInterruptEvent) -> AssistantMsg:
        self.interrupt_input = inputs
        return AssistantMsg(name="Assistant", content=[], id=inputs.reply_id)


def test_interrupt_cleans_up_sync_parked_reply_on_retained_loop() -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()

    assert integration.chat("question") == ""
    parked_loop = integration._parked_reply_loop
    parked_thread = integration._parked_reply_loop_thread
    assert parked_loop is not None
    assert parked_thread is not None
    assert parked_loop.is_running()

    assert integration.interrupt("stop parked") is True
    parked_thread.join(timeout=2)

    assert isinstance(integration._agent.interrupt_input, UserInterruptEvent)
    assert integration._agent.interrupt_input.reply_id == "sync-parked"
    assert integration._parked_reply_id is None
    assert not parked_thread.is_alive()
    assert parked_loop.is_closed()


def test_reset_stops_retained_sync_parked_loop() -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()
    integration.chat("question")
    parked_loop = integration._parked_reply_loop
    parked_thread = integration._parked_reply_loop_thread
    assert parked_loop is not None
    assert parked_thread is not None

    integration.reset()

    parked_thread.join(timeout=2)
    assert not parked_thread.is_alive()
    assert parked_loop.is_closed()
    assert integration._parked_reply_id is None
    assert integration._parked_reply_loop is None


def test_concurrent_parked_interrupt_schedules_exactly_one_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()
    integration.chat("question")
    release = threading.Event()
    schedule_calls: list[Any] = []
    schedule_lock = threading.Lock()

    def fake_schedule(coroutine: Any, loop: Any) -> Mock:
        coroutine.close()
        with schedule_lock:
            schedule_calls.append(loop)
            if len(schedule_calls) == 2:
                release.set()
        release.wait(timeout=0.5)
        future = Mock()
        future.done.return_value = False
        return future

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", fake_schedule)
    results: list[bool] = []
    threads = [
        threading.Thread(target=lambda: results.append(integration.interrupt()))
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert sorted(results) == [False, True]
    assert len(schedule_calls) == 1
    integration.reset()


def test_shutdown_stops_retained_sync_parked_loop() -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()
    integration._mcp_clients = []
    integration.chat("question")
    parked_loop = integration._parked_reply_loop
    parked_thread = integration._parked_reply_loop_thread
    assert parked_loop is not None
    assert parked_thread is not None

    integration.shutdown()

    parked_thread.join(timeout=2)
    assert not parked_thread.is_alive()
    assert parked_loop.is_closed()
    assert integration._parked_reply_id is None
    assert integration._parked_reply_loop is None
    assert integration._parked_cleanup_future is None


def test_reset_cancels_and_clears_pending_parked_cleanup() -> None:
    integration = _chat_integration([])
    cleanup = Mock()
    cleanup.done.return_value = False
    integration._parked_cleanup_future = cleanup

    integration.reset()

    cleanup.cancel.assert_called_once_with()
    assert integration._parked_cleanup_future is None


def test_cancelled_cleanup_callback_does_not_touch_retained_loop() -> None:
    integration = _chat_integration([])
    cleanup: Future[None] = Future()
    cleanup.cancel()
    loop = Mock()
    thread = Mock()

    integration._finish_parked_cleanup(cleanup, loop, thread)

    loop.call_soon_threadsafe.assert_not_called()


def test_completed_cleanup_future_callback_runs_without_ownership_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = _chat_integration([])
    loop = Mock()
    loop.is_running.return_value = True
    retained_thread = Mock()
    integration._parked_reply_id = "parked-reply"
    integration._parked_reply_loop = loop
    integration._parked_reply_loop_thread = retained_thread

    def completed_schedule(coroutine: Any, scheduled_loop: Any) -> Future[None]:
        coroutine.close()
        future: Future[None] = Future()
        future.set_result(None)
        return future

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", completed_schedule)
    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(integration.interrupt()),
        daemon=True,
    )

    worker.start()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert result == [True]
    loop.call_soon_threadsafe.assert_called_once_with(loop.stop)


def test_cleanup_callback_registration_does_not_block_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()
    integration.chat("question")
    callback_entered = threading.Event()
    release_callback = threading.Event()

    class BlockingCallbackFuture(Future[None]):
        def add_done_callback(self, fn: Any) -> None:
            callback_entered.set()
            release_callback.wait(timeout=1)
            super().add_done_callback(fn)

    cleanup: Future[None] = BlockingCallbackFuture()

    def pending_schedule(coroutine: Any, loop: Any) -> Future[None]:
        coroutine.close()
        return cleanup

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", pending_schedule)
    interrupt_thread = threading.Thread(target=integration.interrupt, daemon=True)
    reset_done = threading.Event()
    reset_thread = threading.Thread(
        target=lambda: (integration.reset(), reset_done.set()),
        daemon=True,
    )

    interrupt_thread.start()
    assert callback_entered.wait(timeout=1)
    reset_thread.start()
    reset_completed_before_callback_release = reset_done.wait(timeout=0.3)
    release_callback.set()
    interrupt_thread.join(timeout=2)
    reset_thread.join(timeout=2)

    assert reset_completed_before_callback_release is True
    assert not interrupt_thread.is_alive()
    assert not reset_thread.is_alive()
    assert integration._parked_cleanup_future is None


@pytest.mark.parametrize("lifecycle_method", ["reset", "shutdown"])
def test_lifecycle_disposal_owns_retained_loop_when_cleanup_callback_is_pending(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_method: str,
) -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()
    integration._mcp_clients = []
    integration.chat("question")
    parked_loop = integration._parked_reply_loop
    parked_thread = integration._parked_reply_loop_thread
    assert parked_loop is not None
    assert parked_thread is not None
    callback_entered = threading.Event()
    release_callback = threading.Event()
    original_stop = integration._finish_parked_cleanup

    def gated_stop(cleanup: Any, loop: Any, thread: Any) -> None:
        callback_entered.set()
        release_callback.wait(timeout=2)
        original_stop(cleanup, loop, thread)

    monkeypatch.setattr(integration, "_finish_parked_cleanup", gated_stop)
    assert integration.interrupt("cleanup") is True
    assert callback_entered.wait(timeout=1)

    getattr(integration, lifecycle_method)()
    release_callback.set()
    parked_thread.join(timeout=0.5)
    thread_still_alive = parked_thread.is_alive()
    loop_still_open = not parked_loop.is_closed()
    state_cleared = (
        integration._parked_reply_id is None
        and integration._parked_reply_loop is None
        and integration._parked_reply_loop_thread is None
        and integration._parked_cleanup_future is None
    )
    if thread_still_alive:
        parked_loop.call_soon_threadsafe(parked_loop.stop)
        parked_thread.join(timeout=2)

    assert state_cleared is True
    assert thread_still_alive is False
    assert loop_still_open is False


@pytest.mark.parametrize("lifecycle_method", ["reset", "shutdown"])
def test_sync_parked_retain_handoff_is_atomic_with_lifecycle_disposal(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_method: str,
) -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()
    integration._mcp_clients = []
    retain_entered = threading.Event()
    release_retain = threading.Event()
    original_retain = integration._retain_sync_parked_loop

    def gated_retain(loop: Any) -> Any:
        retain_entered.set()
        release_retain.wait(timeout=1)
        return original_retain(loop)

    monkeypatch.setattr(integration, "_retain_sync_parked_loop", gated_retain)
    chat_thread = threading.Thread(target=lambda: integration.chat("question"))
    chat_thread.start()
    assert retain_entered.wait(timeout=1)

    getattr(integration, lifecycle_method)()
    release_retain.set()
    chat_thread.join(timeout=2)

    leaked_thread = integration._parked_reply_loop_thread
    leaked_loop = integration._parked_reply_loop
    leaked_thread_alive = leaked_thread is not None and leaked_thread.is_alive()
    leaked_loop_open = leaked_loop is not None and not leaked_loop.is_closed()
    integration._dispose_parked_reply_runtime()

    assert not chat_thread.is_alive()
    assert leaked_thread_alive is False
    assert leaked_loop_open is False


def _chat_integration(events: list[AgentEvent]) -> AgentIntegration:
    integration = _integration_with(events)
    integration._initialized = True
    integration._history = SimpleNamespace(add_message=Mock(), clear=Mock())
    integration._provider = "test"
    integration._model_name = "test-model"
    integration._base_url = "https://example.test"
    integration._current_loop = None
    return integration


def test_interrupt_cancels_owned_active_task_thread_safely_without_legacy_call() -> None:
    integration = _chat_integration([])
    integration._agent = SimpleNamespace(interrupt=Mock())
    task = Mock()
    task.done.return_value = False
    loop = Mock()
    loop.is_running.return_value = True
    integration._active_reply_task = task
    integration._current_loop = loop

    assert integration.interrupt("stop now") is True

    loop.call_soon_threadsafe.assert_called_once_with(task.cancel)
    integration._agent.interrupt.assert_not_called()


def test_repeated_active_interrupt_schedules_cancel_only_once() -> None:
    integration = _chat_integration([])
    task = Mock()
    task.done.return_value = False
    loop = Mock()
    loop.is_running.return_value = True
    integration._active_reply_task = task
    integration._current_loop = loop

    assert integration.interrupt("first") is True
    assert integration.interrupt("second") is False

    loop.call_soon_threadsafe.assert_called_once_with(task.cancel)


def test_concurrent_active_interrupt_schedules_cancel_only_once() -> None:
    integration = _chat_integration([])
    task = Mock()
    task.done.return_value = False
    loop = Mock()
    loop.is_running.return_value = True
    entered = threading.Event()
    release = threading.Event()

    def blocking_schedule(callback: Any) -> None:
        entered.set()
        release.wait(timeout=1)

    loop.call_soon_threadsafe.side_effect = blocking_schedule
    integration._active_reply_task = task
    integration._current_loop = loop
    results: list[bool] = []
    first = threading.Thread(target=lambda: results.append(integration.interrupt()))
    second = threading.Thread(target=lambda: results.append(integration.interrupt()))

    first.start()
    assert entered.wait(timeout=1)
    second.start()
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert sorted(results) == [False, True]
    loop.call_soon_threadsafe.assert_called_once_with(task.cancel)


def test_interrupt_without_active_or_parked_work_returns_false() -> None:
    integration = _chat_integration([])

    assert integration.interrupt() is False


def test_chat_persists_one_user_and_one_reconstructed_assistant_message() -> None:
    integration = _chat_integration(_reply_events())

    result = integration.chat("  question  ")

    assert result == "Hello world"
    assert integration._history.add_message.call_count == 2
    user_call, assistant_call = integration._history.add_message.call_args_list
    user_msg = user_call.kwargs["msg"]
    assistant_msg = assistant_call.kwargs["msg"]
    assert user_msg.role == "user"
    assert user_msg.get_text_content() == "  question  "
    assert integration._agent.received_inputs is user_msg
    assert assistant_msg.role == "assistant"
    assert assistant_msg.id == "reply-1"
    assert assistant_msg.get_text_content() == "Hello world"


@pytest.mark.asyncio
async def test_chat_async_persists_one_user_and_one_reconstructed_assistant_message() -> None:
    integration = _chat_integration(_reply_events())

    result = await integration.chat_async("question")

    assert result == "Hello world"
    assert integration._history.add_message.call_count == 2
    user_call, assistant_call = integration._history.add_message.call_args_list
    user_msg = user_call.kwargs["msg"]
    assistant_msg = assistant_call.kwargs["msg"]
    assert integration._agent.received_inputs is user_msg
    assert assistant_msg.role == "assistant"
    assert assistant_msg.id == "reply-1"


@pytest.mark.asyncio
async def test_interrupted_chat_async_persists_partial_text_without_generic_error() -> None:
    integration = _chat_integration(
        _reply_events(finished_reason=ReplyEndReason.INTERRUPTED),
    )

    result = await integration.chat_async("question")

    assert result == "Hello world"
    assert not result.startswith("\u9519\u8bef:")
    assert integration._last_response_interrupted is True
    assert integration._history.add_message.call_count == 2
    partial_reply = integration._history.add_message.call_args_list[1].kwargs["msg"]
    assert partial_reply.get_text_content() == "Hello world"


class _OwnershipStreamingAgent(_FakeStreamingAgent):
    def __init__(
        self,
        integration: AgentIntegration,
        events: list[AgentEvent],
        *,
        fail: bool = False,
    ) -> None:
        super().__init__(events)
        self.integration = integration
        self.fail = fail

    async def reply_stream(self, *, inputs: Msg) -> AsyncGenerator[AgentEvent, None]:
        self.received_inputs = inputs
        assert self.integration._active_reply_task is asyncio.current_task()
        assert self.integration._current_loop is asyncio.get_running_loop()
        for event in self.events:
            yield event
        if self.fail:
            raise RuntimeError("owned stream exploded")


class _GatedStreamingAgent:
    def __init__(self) -> None:
        self.state = SimpleNamespace(reply_id="provisional-reply")
        self.started = {label: asyncio.Event() for label in ("A", "B")}
        self.release = {label: asyncio.Event() for label in ("A", "B")}

    async def reply_stream(self, *, inputs: Msg) -> AsyncGenerator[AgentEvent, None]:
        label = inputs.get_text_content()
        yield ReplyStartEvent(
            session_id="session-1",
            reply_id=f"reply-{label}",
            name="Assistant",
        )
        self.started[label].set()
        await self.release[label].wait()
        yield ReplyEndEvent(
            session_id="session-1",
            reply_id=f"reply-{label}",
        )


@pytest.mark.asyncio
async def test_overlapping_reply_promotes_older_owner_when_newer_finishes_first() -> None:
    integration = _chat_integration([])
    streaming_agent = _GatedStreamingAgent()
    integration._agent = streaming_agent

    task_a = asyncio.create_task(integration.chat_async("A"))
    await streaming_agent.started["A"].wait()
    task_b = asyncio.create_task(integration.chat_async("B"))
    await streaming_agent.started["B"].wait()

    streaming_agent.release["B"].set()
    await task_b

    assert integration._active_reply_task is task_a
    assert integration._current_loop is asyncio.get_running_loop()
    assert integration.is_running is True

    streaming_agent.release["A"].set()
    await task_a
    assert integration.is_running is False


@pytest.mark.asyncio
async def test_overlapping_reply_keeps_newer_owner_when_older_finishes_first() -> None:
    integration = _chat_integration([])
    streaming_agent = _GatedStreamingAgent()
    integration._agent = streaming_agent

    task_a = asyncio.create_task(integration.chat_async("A"))
    await streaming_agent.started["A"].wait()
    task_b = asyncio.create_task(integration.chat_async("B"))
    await streaming_agent.started["B"].wait()

    streaming_agent.release["A"].set()
    await task_a

    assert integration._active_reply_task is task_b
    assert integration._current_loop is asyncio.get_running_loop()
    assert integration.is_running is True

    streaming_agent.release["B"].set()
    await task_b
    assert integration.is_running is False


class _CancellationCleanupStreamingAgent:
    def __init__(self) -> None:
        self.state = SimpleNamespace(reply_id="cancel-reply")
        self.started = asyncio.Event()
        self.cancelled_count = 0

    async def reply_stream(self, *, inputs: Msg) -> AsyncGenerator[AgentEvent, None]:
        yield ReplyStartEvent(
            session_id="session-1",
            reply_id="cancel-reply",
            name="Assistant",
        )
        yield TextBlockStartEvent(reply_id="cancel-reply", block_id="text-1")
        yield TextBlockDeltaEvent(
            reply_id="cancel-reply",
            block_id="text-1",
            delta="partial",
        )
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled_count += 1
            yield TextBlockEndEvent(reply_id="cancel-reply", block_id="text-1")
            yield ReplyEndEvent(
                session_id="session-1",
                reply_id="cancel-reply",
                finished_reason=ReplyEndReason.INTERRUPTED,
            )


@pytest.mark.asyncio
async def test_real_task_cancel_persists_partial_interrupted_reply_once() -> None:
    integration = _chat_integration([])
    streaming_agent = _CancellationCleanupStreamingAgent()
    integration._agent = streaming_agent
    chat_task = asyncio.create_task(integration.chat_async("question"))
    await streaming_agent.started.wait()

    assert integration.interrupt("first") is True
    assert integration.interrupt("duplicate") is False
    result = await chat_task

    assert result == "partial"
    assert streaming_agent.cancelled_count == 1
    assert integration._last_response_interrupted is True
    assert integration._history.add_message.call_count == 2
    persisted_reply = integration._history.add_message.call_args_list[1].kwargs["msg"]
    assert persisted_reply.get_text_content() == "partial"
    assert integration._active_reply_cancel_requests == set()


def test_chat_clears_sync_reply_ownership_after_completion() -> None:
    integration = _chat_integration([])
    integration._agent = _OwnershipStreamingAgent(integration, _reply_events())

    assert integration.chat("question") == "Hello world"
    assert integration._active_reply_task is None
    assert integration._current_loop is None


@pytest.mark.asyncio
async def test_chat_async_clears_reply_ownership_after_stream_error() -> None:
    integration = _chat_integration([])
    integration._agent = _OwnershipStreamingAgent(integration, [], fail=True)

    assert await integration.chat_async("question") == "\u9519\u8bef: owned stream exploded"
    assert integration._active_reply_task is None
    assert integration._current_loop is None


class _FailingStreamingAgent(_FakeStreamingAgent):
    async def reply_stream(self, *, inputs: Msg) -> AsyncGenerator[AgentEvent, None]:
        self.received_inputs = inputs
        for event in self.events:
            yield event
        raise RuntimeError("stream exploded")


@pytest.mark.asyncio
async def test_chat_async_resets_interrupted_and_persists_partial_reply_on_stream_error() -> None:
    partial_events = _reply_events()[:3]
    integration = _chat_integration([])
    integration._agent = _FailingStreamingAgent(partial_events)
    integration._last_response_interrupted = True

    result = await integration.chat_async("question")

    assert result == "错误: stream exploded"
    assert integration._last_response_interrupted is False
    assert integration._history.add_message.call_count == 2
    partial_reply = integration._history.add_message.call_args_list[1].kwargs["msg"]
    assert partial_reply.get_text_content() == "Hello"
    assert integration._agent.received_inputs is integration._history.add_message.call_args_list[0].kwargs["msg"]


def test_chat_persists_partial_reply_once_on_stream_error() -> None:
    partial_events = _reply_events()[:3]
    integration = _chat_integration([])
    integration._agent = _FailingStreamingAgent(partial_events)

    result = integration.chat("question")

    assert result == "错误: stream exploded"
    assert integration._history.add_message.call_count == 2
    partial_reply = integration._history.add_message.call_args_list[1].kwargs["msg"]
    assert partial_reply.get_text_content() == "Hello"


class _OrderMiddleware(MiddlewareBase):
    def __init__(self, label: str, order: list[str]) -> None:
        self.label = label
        self.order = order

    async def on_reply(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Any,
    ) -> AsyncGenerator[Any, None]:
        self.order.append(f"before-{self.label}")
        async for item in next_handler():
            yield item
        self.order.append(f"after-{self.label}")


class _MinimalAgent(Agent):
    def __init__(self, middlewares: list[MiddlewareBase], yielded: list[Any]) -> None:
        self.name = "MinimalAgent"
        self._reply_middlewares = middlewares
        self._yielded = yielded

    async def _reply_impl(self, inputs: Msg | None = None) -> AsyncGenerator[Any, None]:
        for item in self._yielded:
            yield item


@pytest.mark.asyncio
async def test_agent_reply_middleware_chain_has_onion_order_and_preserves_items() -> None:
    order: list[str] = []
    expected_items = [object(), object()]
    agent = _MinimalAgent(
        [
            _OrderMiddleware("1", order),
            _OrderMiddleware("2", order),
        ],
        expected_items,
    )

    actual_items = [
        item
        async for item in agent._reply(
            inputs=UserMsg(name="User", content="middleware"),
        )
    ]

    assert actual_items == expected_items
    assert order == ["before-1", "before-2", "after-2", "after-1"]
