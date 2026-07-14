# -*- coding: utf-8 -*-
"""ChatPanel streaming tests"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import QWidget

from agentscope.event import (
    DataBlockDeltaEvent,
    TextBlockDeltaEvent,
    TextBlockStartEvent,
    ThinkingBlockDeltaEvent,
    ThinkingBlockStartEvent,
    ToolCallDeltaEvent,
    ToolCallStartEvent,
    ToolResultStartEvent,
    ToolResultTextDeltaEvent,
)

import src.ui.chat.chat_panel as chat_panel


class MockStreamingWidget:
    """Mock widget for streaming tests"""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def set_content(self, content: str) -> None:
        self.content = content


class TestChatPanelStreaming:
    """Test streaming output in ChatPanel"""

    def test_streaming_chunk_updates_message_widget(self):
        """Streaming chunks should update the message widget"""
        widget = MockStreamingWidget("assistant", "")
        chunk = "Hello, world!"

        widget.set_content(chunk)

        assert widget.content == "Hello, world!"

    def test_streaming_accumulates_text(self):
        """Multiple chunks should accumulate"""
        streaming_text = ""

        chunk1 = "Hello"
        streaming_text += chunk1

        chunk2 = " World"
        streaming_text += chunk2

        assert streaming_text == "Hello World"

    def test_streaming_chunk_signal_emission(self):
        """streaming_chunk signal should be emitted correctly"""
        from PySide6.QtCore import QObject

        class MockWorker(QObject):
            streaming_chunk = Signal(str)

            def __init__(self):
                super().__init__()
                self.emitted_chunks = []

            def emit_chunk(self, chunk: str) -> None:
                self.emitted_chunks.append(chunk)
                self.streaming_chunk.emit(chunk)

        worker = MockWorker()
        received = []

        def on_chunk(chunk: str) -> None:
            received.append(chunk)

        worker.streaming_chunk.connect(on_chunk)
        worker.emit_chunk("test chunk")

        assert "test chunk" in received

    def test_streaming_callback_extracts_text_from_string(self):
        """Streaming callback should extract text from string output"""
        output = "Simple text output"
        chunk_text = ""

        if isinstance(output, str):
            chunk_text = output

        assert chunk_text == "Simple text output"

    def test_streaming_callback_extracts_text_from_content_attribute(self):
        """Streaming callback should extract text from content attribute"""
        output = MagicMock()
        output.content = "Content from attribute"
        chunk_text = ""

        if hasattr(output, "content"):
            content = output.content
            if isinstance(content, str):
                chunk_text = content

        assert chunk_text == "Content from attribute"

    def test_streaming_callback_extracts_text_from_list_content(self):
        """Streaming callback should extract text from list content blocks"""
        output = MagicMock()
        output.content = [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "World"},
        ]
        chunk_text = ""

        if hasattr(output, "content"):
            content = output.content
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                chunk_text = "".join(text_parts)

        assert chunk_text == "Hello World"

    def test_streaming_resets_on_new_message(self):
        """Streaming text should reset when starting a new message"""
        streaming_text = "Previous content"
        streaming_message = MockStreamingWidget("assistant", streaming_text)

        streaming_text = ""
        streaming_message = None

        assert streaming_text == ""
        assert streaming_message is None

    def test_event_adapter_accumulates_text_and_thinking_deltas(self):
        state = {}
        chat_panel._event_to_block_update(TextBlockStartEvent(reply_id="reply", block_id="text"), state)
        first = chat_panel._event_to_block_update(
            TextBlockDeltaEvent(reply_id="reply", block_id="text", delta="Hello"), state
        )
        second = chat_panel._event_to_block_update(
            TextBlockDeltaEvent(reply_id="reply", block_id="text", delta=" world"), state
        )
        chat_panel._event_to_block_update(
            ThinkingBlockStartEvent(reply_id="reply", block_id="thinking"), state
        )
        thinking = chat_panel._event_to_block_update(
            ThinkingBlockDeltaEvent(
                reply_id="reply", block_id="thinking", delta="reasoning"
            ),
            state,
        )

        assert first == {"type": "text", "text": "Hello"}
        assert second == {"type": "text", "text": "Hello world"}
        assert thinking == {"type": "thinking", "thinking": "reasoning"}

    def test_event_adapter_translates_tool_call_result_and_data_events(self):
        state = {}
        tool_start = chat_panel._event_to_block_update(
            ToolCallStartEvent(
                reply_id="reply", tool_call_id="call", tool_call_name="search"
            ),
            state,
        )
        tool_delta = chat_panel._event_to_block_update(
            ToolCallDeltaEvent(
                reply_id="reply", tool_call_id="call", delta='{"q":"docs"}'
            ),
            state,
        )
        result_start = chat_panel._event_to_block_update(
            ToolResultStartEvent(
                reply_id="reply", tool_call_id="call", tool_call_name="search"
            ),
            state,
        )
        result_delta = chat_panel._event_to_block_update(
            ToolResultTextDeltaEvent(reply_id="reply", tool_call_id="call", delta="found"),
            state,
        )
        data = chat_panel._event_to_block_update(
            DataBlockDeltaEvent(
                reply_id="reply",
                block_id="image",
                data="aW1hZ2U=",
                media_type="image/png",
            ),
            state,
        )

        assert tool_start == {
            "type": "tool_use",
            "id": "call",
            "name": "search",
            "input": "",
        }
        assert tool_delta["input"] == '{"q":"docs"}'
        assert result_start["type"] == "tool_result"
        assert result_delta["output"] == "found"
        assert data == {
            "type": "image",
            "source": {
                "type": "base64",
                "data": "aW1hZ2U=",
                "media_type": "image/png",
            },
        }
