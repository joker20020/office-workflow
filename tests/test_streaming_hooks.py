# -*- coding: utf-8 -*-
"""AgentScope 2.0 event-stream reconstruction contracts."""

import asyncio
import threading
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
from src.agent.async_runtime import AgentAsyncRuntime


_CREATED_INTEGRATIONS: list[AgentIntegration] = []


async def _current_loop():
    return asyncio.get_running_loop()


@pytest.fixture(autouse=True)
def _stop_created_runtimes():
    yield
    while _CREATED_INTEGRATIONS:
        integration = _CREATED_INTEGRATIONS.pop()
        integration.shutdown()


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
    integration._parked_reply_id = None
    integration._parked_cleanup_future = None
    integration._async_runtime = AgentAsyncRuntime()
    integration._mcp_clients = []
    integration._toolkit = None
    integration._initialized = False
    integration._history = SimpleNamespace(clear=Mock())
    _CREATED_INTEGRATIONS.append(integration)
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
async def test_park_event_stores_only_reply_id(park_event_type: type[AgentEvent]) -> None:
    integration = _integration_with(
        [park_event_type(reply_id="parked-reply", tool_calls=[])],
    )

    await integration._consume_reply_stream(UserMsg(name="User", content="pause"))

    assert integration._parked_reply_id == "parked-reply"
    assert not hasattr(integration, "_parked_reply_loop")
    assert not hasattr(integration, "_parked_reply_loop_thread")


@pytest.mark.asyncio
async def test_parked_cleanup_sends_exact_user_interrupt_event_and_clears_state() -> None:
    integration = _integration_with([])
    integration._parked_reply_id = "parked-reply"
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
        self.reply_count = 0
        self.reply_loops: list[asyncio.AbstractEventLoop] = []

    async def reply(self, *, inputs: UserInterruptEvent) -> AssistantMsg:
        self.reply_count += 1
        self.reply_loops.append(asyncio.get_running_loop())
        self.interrupt_input = inputs
        return AssistantMsg(name="Assistant", content=[], id=inputs.reply_id)


def _wait_until(predicate: Any, timeout: float = 2.0) -> bool:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_sync_parked_interrupt_uses_shared_runtime_and_schedules_once() -> None:
    integration = _chat_integration([])
    integration._agent = _ParkedSyncAgent()

    assert integration.chat("question") == ""
    runtime_loop = integration._async_runtime.run(_current_loop())

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
    assert _wait_until(lambda: integration._parked_cleanup_future is None)
    assert integration._agent.reply_count == 1
    assert integration._agent.reply_loops == [runtime_loop]
    assert integration._parked_reply_id is None


class _FailThenSucceedParkedAgent(_ParkedSyncAgent):
    async def reply(self, *, inputs: UserInterruptEvent) -> AssistantMsg:
        self.reply_count += 1
        self.reply_loops.append(asyncio.get_running_loop())
        if self.reply_count == 1:
            raise RuntimeError("cleanup failed")
        self.interrupt_input = inputs
        return AssistantMsg(name="Assistant", content=[], id=inputs.reply_id)


def test_failed_parked_cleanup_releases_reservation_and_allows_retry() -> None:
    integration = _chat_integration([])
    integration._agent = _FailThenSucceedParkedAgent()
    integration.chat("question")

    assert integration.interrupt("first") is True
    assert _wait_until(lambda: integration._parked_cleanup_future is None)
    assert integration._parked_reply_id == "sync-parked"

    assert integration.interrupt("retry") is True
    assert _wait_until(lambda: integration._parked_cleanup_future is None)
    assert integration._agent.reply_count == 2
    assert integration._parked_reply_id is None


class _CancelThenSucceedParkedAgent(_ParkedSyncAgent):
    def __init__(self) -> None:
        super().__init__()
        self.first_cleanup_started = threading.Event()

    async def reply(self, *, inputs: UserInterruptEvent) -> AssistantMsg:
        self.reply_count += 1
        self.reply_loops.append(asyncio.get_running_loop())
        if self.reply_count == 1:
            self.first_cleanup_started.set()
            await asyncio.Event().wait()
        self.interrupt_input = inputs
        return AssistantMsg(name="Assistant", content=[], id=inputs.reply_id)


def test_independently_cancelled_parked_cleanup_releases_and_allows_retry() -> None:
    integration = _chat_integration([])
    integration._agent = _CancelThenSucceedParkedAgent()
    integration.chat("question")
    assert integration.interrupt("first") is True
    assert integration._agent.first_cleanup_started.wait(timeout=1)
    with integration._reply_ownership_lock:
        first_cleanup = integration._parked_cleanup_future
    assert first_cleanup is not None

    assert first_cleanup.cancel() is True
    assert _wait_until(lambda: integration._parked_cleanup_future is None)
    assert integration._parked_reply_id == "sync-parked"

    assert integration.interrupt("retry") is True
    assert _wait_until(lambda: integration._parked_cleanup_future is None)
    assert integration._agent.reply_count == 2
    assert integration._parked_reply_id is None


class _BlockingParkedAgent(_ParkedSyncAgent):
    def __init__(self) -> None:
        super().__init__()
        self.cleanup_started = threading.Event()

    async def reply(self, *, inputs: UserInterruptEvent) -> AssistantMsg:
        self.reply_count += 1
        self.cleanup_started.set()
        await asyncio.Event().wait()
        return AssistantMsg(name="Assistant", content=[], id=inputs.reply_id)


@pytest.mark.parametrize("lifecycle_method", ["reset", "shutdown"])
def test_lifecycle_racing_parked_cleanup_clears_reservation(
    lifecycle_method: str,
) -> None:
    integration = _chat_integration([])
    integration._agent = _BlockingParkedAgent()
    integration.chat("question")
    assert integration.interrupt("cleanup") is True
    assert integration._agent.cleanup_started.wait(timeout=1)

    getattr(integration, lifecycle_method)()

    assert integration._parked_cleanup_future is None
    assert integration._parked_reply_id is None
    if lifecycle_method == "reset":
        assert integration._async_runtime.is_running is True
    else:
        assert integration._async_runtime.is_running is False


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


@pytest.mark.parametrize("lifecycle_method", ["reset", "shutdown"])
def test_runtime_callback_rejects_sync_lifecycle_without_losing_state(
    lifecycle_method: str,
) -> None:
    integration = _chat_integration(_reply_events())
    original_agent = integration._agent
    original_toolkit = object()
    integration._toolkit = original_toolkit

    class StatefulClient:
        name = "owned"
        is_stateful = True

        def __init__(self):
            self.close_calls = 0

        async def close(self):
            self.close_calls += 1

    client = StatefulClient()
    integration._mcp_clients = [client]
    errors: list[RuntimeError] = []

    def reenter_lifecycle(agent: Any, kwargs: dict, event: Any) -> None:
        if errors:
            return
        try:
            getattr(integration, lifecycle_method)()
        except RuntimeError as error:
            errors.append(error)

    integration.register_streaming_callback(reenter_lifecycle)

    assert integration.chat("question") == "Hello world"
    assert len(errors) == 1
    assert "runtime thread" in str(errors[0]).lower()
    assert integration._initialized is True
    assert integration._agent is original_agent
    assert integration._toolkit is original_toolkit
    assert integration._mcp_clients == [client]
    assert client.close_calls == 0
    assert integration._async_runtime.is_running is True


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


class _CallerCancellationAgent:
    def __init__(self) -> None:
        self.state = SimpleNamespace(reply_id="caller-cancel")
        self.started = threading.Event()

    async def reply_stream(self, *, inputs: Msg) -> AsyncGenerator[AgentEvent, None]:
        yield ReplyStartEvent(
            session_id="session-1",
            reply_id="caller-cancel",
            name="Assistant",
        )
        self.started.set()
        await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_chat_async_propagates_caller_cancellation() -> None:
    integration = _chat_integration([])
    integration._agent = _CallerCancellationAgent()
    chat_task = asyncio.create_task(integration.chat_async("question"))
    assert await asyncio.to_thread(integration._agent.started.wait, 1)

    chat_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await chat_task


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
        self.started = {label: threading.Event() for label in ("A", "B")}
        self.release = {label: threading.Event() for label in ("A", "B")}

    async def reply_stream(self, *, inputs: Msg) -> AsyncGenerator[AgentEvent, None]:
        label = inputs.get_text_content()
        yield ReplyStartEvent(
            session_id="session-1",
            reply_id=f"reply-{label}",
            name="Assistant",
        )
        self.started[label].set()
        while not self.release[label].is_set():
            await asyncio.sleep(0.001)
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
    assert await asyncio.to_thread(streaming_agent.started["A"].wait, 1)
    owner_a = integration._active_reply_task
    task_b = asyncio.create_task(integration.chat_async("B"))
    assert await asyncio.to_thread(streaming_agent.started["B"].wait, 1)

    streaming_agent.release["B"].set()
    await task_b

    assert integration._active_reply_task is owner_a
    assert integration._current_loop is integration._async_runtime.run(_current_loop())
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
    assert await asyncio.to_thread(streaming_agent.started["A"].wait, 1)
    task_b = asyncio.create_task(integration.chat_async("B"))
    assert await asyncio.to_thread(streaming_agent.started["B"].wait, 1)
    owner_b = integration._active_reply_task

    streaming_agent.release["A"].set()
    await task_a

    assert integration._active_reply_task is owner_b
    assert integration._current_loop is integration._async_runtime.run(_current_loop())
    assert integration.is_running is True

    streaming_agent.release["B"].set()
    await task_b
    assert integration.is_running is False


class _CancellationCleanupStreamingAgent:
    def __init__(self) -> None:
        self.state = SimpleNamespace(reply_id="cancel-reply")
        self.started = threading.Event()
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
    assert await asyncio.to_thread(streaming_agent.started.wait, 1)

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
