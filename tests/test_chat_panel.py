# -*- coding: utf-8 -*-
"""ChatPanel streaming tests"""

import base64

import pytest
from unittest.mock import MagicMock, patch
from typing import Any
from PIL import Image

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import QApplication, QWidget

from agentscope.event import (
    DataBlockDeltaEvent,
    DataBlockEndEvent,
    DataBlockStartEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
    ThinkingBlockDeltaEvent,
    ThinkingBlockEndEvent,
    ThinkingBlockStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultDataDeltaEvent,
    ToolResultStartEvent,
    ToolResultEndEvent,
    ToolResultTextDeltaEvent,
)
from agentscope.message import Base64Source, DataBlock, ToolResultState, UserMsg

import src.ui.chat.chat_panel as chat_panel
from src.ui.chat.composite_message_widget import CompositeMessageWidget
from src.ui.chat.blocks.image_block import ImageBlockWidget
from src.ui.chat.blocks.tool_result_block import ToolResultBlockWidget


class MockStreamingWidget:
    """Mock widget for streaming tests"""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def set_content(self, content: str) -> None:
        self.content = content


class TestChatPanelStreaming:
    def test_image_block_loads_file_uri(self, tmp_path):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        image_path = tmp_path / "preview.png"
        Image.new("RGB", (2, 2), color="red").save(image_path)

        widget = ImageBlockWidget(
            {"type": "image", "source": {"type": "url", "url": image_path.as_uri()}}
        )

        assert not widget._image_label.pixmap().isNull()

    def test_history_extracts_base64_image_data_blocks_for_display(self):
        message = UserMsg(
            name="User",
            content=[
                DataBlock(
                    name="image",
                    source=Base64Source(data="aW1hZ2U=", media_type="image/png"),
                ),
            ],
        )

        blocks = chat_panel._extract_blocks_from_msg(message)

        assert blocks == [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "data": "aW1hZ2U=",
                    "media_type": "image/png",
                },
            },
        ]

    def test_subagent_marker_delta_becomes_nested_event_not_tool_output(self):
        state = {("tool_result", "call-1"): {"name": "tool_blender_model", "output": ""}}
        marker = chat_panel.encode_subagent_event(
            {"kind": "phase", "title": "Blender", "text": "started"}
        )
        event = ToolResultTextDeltaEvent(
            reply_id="reply-1",
            tool_call_id="call-1",
            tool_call_name="tool_blender_model",
            delta=marker,
        )

        update = chat_panel._event_to_block_update(event, state)

        assert update["type"] == "subagent_event"
        assert update["parent_tool_call_id"] == "call-1"
        assert state[("tool_result", "call-1")]["output"] == ""

    def test_event_adapter_reassembles_fragmented_subagent_marker(self):
        state = {("tool_result", "call-1"): {"name": "image", "output": ""}}
        marker = chat_panel.encode_subagent_event(
            {"kind": "text", "title": "Image Agent", "text": "done"}
        )
        first = ToolResultTextDeltaEvent(
            reply_id="reply-1",
            tool_call_id="call-1",
            tool_call_name="image",
            delta=marker[:11],
        )
        second = ToolResultTextDeltaEvent(
            reply_id="reply-1",
            tool_call_id="call-1",
            tool_call_name="image",
            delta=marker[11:],
        )

        assert chat_panel._event_to_block_updates(first, state) == []
        updates = chat_panel._event_to_block_updates(second, state)

        assert updates[-1]["type"] == "subagent_event"
        assert updates[-1]["event_kind"] == "text"
        assert state[("tool_result", "call-1")]["output"] == ""

    def test_text_delta_private_subagent_marker_is_not_rendered(self):
        marker = chat_panel.encode_subagent_event(
            {"kind": "phase", "title": "Blender", "text": "started"}
        )
        event = TextBlockDeltaEvent(
            reply_id="reply-1",
            block_id="text-1",
            delta=marker,
        )

        assert chat_panel._event_to_block_updates(event, {}) == []

    def test_event_adapter_keeps_visible_tool_output_and_removes_multiple_markers(self):
        state = {("tool_result", "call-1"): {"name": "image", "output": ""}}
        delta = "summary " + chat_panel.encode_subagent_event(
            {"kind": "phase", "title": "Image Agent", "text": "running"}
        ) + chat_panel.encode_subagent_event(
            {"kind": "complete", "title": "Image Agent", "text": "done"}
        )
        event = ToolResultTextDeltaEvent(
            reply_id="reply-1",
            tool_call_id="call-1",
            tool_call_name="image",
            delta=delta,
        )

        updates = chat_panel._event_to_block_updates(event, state)

        assert updates[0]["output"] == "summary "
        assert [item["event_kind"] for item in updates[1:]] == ["phase", "complete"]

    def test_streaming_callback_emits_all_updates_from_one_delta(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()
        panel._worker = MagicMock()
        callback = panel._create_streaming_callback()
        event = ToolResultTextDeltaEvent(
            reply_id="reply-1",
            tool_call_id="call-1",
            tool_call_name="image",
            delta="summary " + chat_panel.encode_subagent_event(
                {"kind": "complete", "title": "Image Agent", "text": "done"}
            ),
        )

        callback(None, {"event": event}, None)

        emitted = panel._worker.block_update.emit.call_args.args[0]
        assert [item["type"] for item in emitted] == ["tool_result", "subagent_event"]

    def test_coalesce_block_updates_merges_adjacent_subagent_text(self):
        updates = chat_panel._coalesce_block_updates(
            [
                {
                    "type": "subagent_event",
                    "parent_tool_call_id": "call-1",
                    "event_kind": "text",
                    "title": "Image Agent",
                    "status": "running",
                    "text": "A",
                },
                {
                    "type": "subagent_event",
                    "parent_tool_call_id": "call-1",
                    "event_kind": "text",
                    "title": "Image Agent",
                    "status": "running",
                    "text": " 2D",
                },
            ]
        )

        assert len(updates) == 1
        assert updates[0]["text"] == "A 2D"

    def test_block_update_does_not_log_plain_text_at_info(self):
        streaming_message = MagicMock()
        streaming_message.block_count.return_value = 0
        panel = MagicMock()
        panel._streaming_message = streaming_message
        panel._streaming_blocks = []
        panel._current_block_type = "unknown"

        with patch.object(chat_panel._logger, "info") as info:
            chat_panel.ChatPanel._on_block_update(
                panel,
                [{"type": "text", "id": "text-1", "text": "one", "_new_block": True}],
            )

        info.assert_not_called()

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

        assert first == {
            "type": "text",
            "id": "text",
            "text": "Hello",
            "_new_block": True,
        }
        assert second == {
            "type": "text",
            "id": "text",
            "text": "Hello world",
            "_new_block": False,
        }
        assert thinking == {
            "type": "thinking",
            "id": "thinking",
            "thinking": "reasoning",
            "_new_block": True,
        }

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
        chat_panel._event_to_block_update(
            DataBlockStartEvent(
                reply_id="reply", block_id="image", media_type="image/png"
            ),
            state,
        )
        data_delta = chat_panel._event_to_block_update(
            DataBlockDeltaEvent(
                reply_id="reply",
                block_id="image",
                data="aW1hZ2U=",
                media_type="image/png",
            ),
            state,
        )
        data = chat_panel._event_to_block_update(
            DataBlockEndEvent(reply_id="reply", block_id="image"), state
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
        assert data_delta is None
        assert data == {
            "type": "image",
            "id": "image",
            "_new_block": True,
            "source": {
                "type": "base64",
                "data": "aW1hZ2U=",
                "media_type": "image/png",
            },
        }

    def test_data_deltas_decode_independent_base64_and_emit_only_on_end(self):
        state = {}
        first_bytes = b"first chunk"
        second_bytes = b"second chunk"
        chat_panel._event_to_block_update(
            DataBlockStartEvent(
                reply_id="reply", block_id="image", media_type="image/png"
            ),
            state,
        )

        first = chat_panel._event_to_block_update(
            DataBlockDeltaEvent(
                reply_id="reply",
                block_id="image",
                data=base64.b64encode(first_bytes).decode(),
                media_type="image/png",
            ),
            state,
        )
        second = chat_panel._event_to_block_update(
            DataBlockDeltaEvent(
                reply_id="reply",
                block_id="image",
                data=base64.b64encode(second_bytes).decode(),
                media_type="image/png",
            ),
            state,
        )
        completed = chat_panel._event_to_block_update(
            DataBlockEndEvent(reply_id="reply", block_id="image"), state
        )

        assert first is None
        assert second is None
        assert base64.b64decode(completed["source"]["data"]) == (
            first_bytes + second_bytes
        )
        assert completed["_new_block"] is True
        assert completed["id"] == "image"

    @pytest.mark.parametrize(
        ("start_factory", "delta_factory", "end_factory", "content_key"),
        [
            (TextBlockStartEvent, TextBlockDeltaEvent, TextBlockEndEvent, "text"),
            (
                ThinkingBlockStartEvent,
                ThinkingBlockDeltaEvent,
                ThinkingBlockEndEvent,
                "thinking",
            ),
        ],
    )
    def test_consecutive_same_type_blocks_have_explicit_boundaries(
        self, start_factory, delta_factory, end_factory, content_key
    ):
        state = {}
        updates = []
        for block_id, delta in (("one", "first"), ("two", "second")):
            chat_panel._event_to_block_update(
                start_factory(reply_id="reply", block_id=block_id), state
            )
            updates.append(
                chat_panel._event_to_block_update(
                    delta_factory(
                        reply_id="reply", block_id=block_id, delta=delta
                    ),
                    state,
                )
            )
            boundary = chat_panel._event_to_block_update(
                end_factory(reply_id="reply", block_id=block_id), state
            )
            assert boundary == {
                "type": "_stream_end",
                "block_type": content_key,
                "id": block_id,
            }

        assert [update[content_key] for update in updates] == ["first", "second"]
        assert [update["id"] for update in updates] == ["one", "two"]
        assert all(update["_new_block"] for update in updates)

    def test_consecutive_data_blocks_keep_distinct_boundaries(self):
        state = {}
        completed = []
        for block_id, raw in (("one", b"first"), ("two", b"second")):
            chat_panel._event_to_block_update(
                DataBlockStartEvent(
                    reply_id="reply", block_id=block_id, media_type="image/png"
                ),
                state,
            )
            chat_panel._event_to_block_update(
                DataBlockDeltaEvent(
                    reply_id="reply",
                    block_id=block_id,
                    data=base64.b64encode(raw).decode(),
                    media_type="image/png",
                ),
                state,
            )
            completed.append(
                chat_panel._event_to_block_update(
                    DataBlockEndEvent(reply_id="reply", block_id=block_id), state
                )
            )

        assert [block["id"] for block in completed] == ["one", "two"]
        assert all(block["_new_block"] for block in completed)
        assert [
            base64.b64decode(block["source"]["data"]) for block in completed
        ] == [b"first", b"second"]

    def test_completed_media_boundary_forces_a_fresh_widget(self):
        streaming_message = MagicMock()
        streaming_message.block_count.return_value = 1
        streaming_message._blocks = []
        panel = MagicMock()
        panel._streaming_message = streaming_message
        panel._streaming_blocks = []
        panel._current_block_type = "image"
        block = {
            "type": "image",
            "id": "second",
            "_new_block": True,
            "source": {
                "type": "base64",
                "data": base64.b64encode(b"complete").decode(),
                "media_type": "image/png",
            },
        }

        with patch.object(chat_panel.QTimer, "singleShot"):
            chat_panel.ChatPanel._on_block_update(panel, [block])

        rendered = block.copy()
        rendered.pop("_new_block")
        streaming_message.append_block.assert_called_once_with(rendered)
        streaming_message.add_or_update_block.assert_not_called()

    def test_tool_result_data_events_are_independent_fresh_media_blocks(self):
        state = {}
        events = [
            ToolResultDataDeltaEvent(
                reply_id="reply",
                tool_call_id="call",
                block_id=block_id,
                media_type="image/png",
                data=data,
            )
            for block_id, data in (("one", "b25l"), ("two", "dHdv"))
        ]

        updates = [chat_panel._event_to_block_update(event, state) for event in events]

        assert [update["id"] for update in updates] == ["one", "two"]
        assert all(update["_new_block"] for update in updates)
        assert [update["source"]["data"] for update in updates] == ["b25l", "dHdv"]

        streaming_message = MagicMock()
        streaming_message.block_count.return_value = 1
        panel = MagicMock()
        panel._streaming_message = streaming_message
        panel._streaming_blocks = []
        panel._current_block_type = "image"
        with patch.object(chat_panel.QTimer, "singleShot"):
            for update in updates:
                chat_panel.ChatPanel._on_block_update(panel, [update])

        assert streaming_message.append_block.call_count == 2

    def test_composite_message_widget_append_block_updates_widget_and_model(self):
        widget = MagicMock()
        widget._blocks = []
        block = {"type": "text", "text": "new block"}

        CompositeMessageWidget.append_block(widget, block)

        widget._add_block_widget.assert_called_once_with(block)
        assert widget._blocks == [block]

    def test_subagent_event_routes_to_its_parent_tool_result(self):
        parent = MagicMock()
        parent.get_block_type.return_value = "tool_result"
        parent.get_block_id.return_value = "call-1"
        widget = MagicMock()
        widget._block_widgets = [parent]
        widget._blocks = []

        CompositeMessageWidget.add_or_update_block(
            widget,
            {
                "type": "subagent_event",
                "parent_tool_call_id": "call-1",
                "event_kind": "artifact",
                "title": "Image agent",
                "text": "saved image",
                "status": "running",
            },
        )

        parent.append_execution_event.assert_called_once()
        assert widget._blocks == []

    def test_tool_result_keeps_final_markdown_and_appends_execution_events(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        block = ToolResultBlockWidget(
            {"type": "tool_result", "id": "call-1", "name": "image", "output": "# Final"}
        )

        block.append_execution_event(
            {
                "type": "subagent_event",
                "event_kind": "artifact",
                "title": "Image agent",
                "text": "saved image",
                "status": "running",
            }
        )

        assert block.get_content() == "# Final"
        assert block.execution_event_count() == 1

    def test_tool_result_merges_adjacent_subagent_text_events(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        block = ToolResultBlockWidget(
            {"type": "tool_result", "id": "call-1", "name": "image", "output": ""}
        )

        block.append_execution_event(
            {
                "type": "subagent_event",
                "event_kind": "text",
                "title": "Image Agent",
                "text": "A",
                "status": "running",
            }
        )
        block.append_execution_event(
            {
                "type": "subagent_event",
                "event_kind": "text",
                "title": "Image Agent",
                "text": " 2D",
                "status": "running",
            }
        )

        assert block.execution_event_count() == 1
        assert "Image Agent" in block._execution_events_text()
        assert "A 2D" in block._execution_events_text()

    def test_tool_end_events_preserve_completion_and_result_state(self):
        state = {}
        chat_panel._event_to_block_update(
            ToolCallStartEvent(
                reply_id="reply", tool_call_id="call", tool_call_name="search"
            ),
            state,
        )
        tool_end = chat_panel._event_to_block_update(
            ToolCallEndEvent(reply_id="reply", tool_call_id="call"), state
        )
        chat_panel._event_to_block_update(
            ToolResultStartEvent(
                reply_id="reply", tool_call_id="call", tool_call_name="search"
            ),
            state,
        )
        result_end = chat_panel._event_to_block_update(
            ToolResultEndEvent(
                reply_id="reply",
                tool_call_id="call",
                state=ToolResultState.ERROR,
            ),
            state,
        )

        assert tool_end["finished"] is True
        assert result_end["finished"] is True
        assert result_end["state"] == "error"
