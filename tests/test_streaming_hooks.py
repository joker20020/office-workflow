# -*- coding: utf-8 -*-
"""AgentScope 2.0 event-stream reconstruction contracts."""

from types import SimpleNamespace
from typing import Any, AsyncGenerator, get_args
from unittest.mock import Mock

import pytest

from agentscope.agent import Agent
from agentscope.event import (
    AgentEvent,
    ReplyEndEvent,
    ReplyEndReason,
    ReplyStartEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
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


def _chat_integration(events: list[AgentEvent]) -> AgentIntegration:
    integration = _integration_with(events)
    integration._initialized = True
    integration._history = SimpleNamespace(add_message=Mock())
    integration._provider = "test"
    integration._model_name = "test-model"
    integration._base_url = "https://example.test"
    integration._current_loop = None
    return integration


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
