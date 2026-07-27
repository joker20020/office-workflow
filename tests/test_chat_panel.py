"""ChatPanel streaming tests"""

import base64

import pytest
from unittest.mock import MagicMock, patch
from typing import Any
from PIL import Image

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import QApplication, QFrame, QTextEdit, QWidget

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
    ToolResultEndEvent,
    ToolResultStartEvent,
    ToolResultTextDeltaEvent,
)
from agentscope.message import Base64Source, DataBlock, ToolResultState, UserMsg

import src.ui.chat.chat_panel as chat_panel
import src.ui.chat.composite_message_widget as composite_message_widget
import src.ui.chat.blocks.tool_result_block as tool_result_block
from src.ui.chat.composite_message_widget import CompositeMessageWidget
from src.ui.chat.blocks import create_block_widget as create_real_block_widget
from src.ui.chat.message_widget import MarkdownMessageWidget
from src.ui.chat.blocks.image_block import ImageBlockWidget
from src.ui.chat.blocks.tool_result_block import ToolResultBlockWidget
from src.ui.theme import Theme


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
        state = {("tool_result", "call-1"): {"name": "tool_solidworks_model", "output": ""}}
        marker = chat_panel.encode_subagent_event(
            {"kind": "phase", "title": "SolidWorks", "text": "started"}
        )
        event = ToolResultTextDeltaEvent(
            reply_id="reply-1",
            tool_call_id="call-1",
            tool_call_name="tool_solidworks_model",
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
        chat_panel._event_to_block_update(
            TextBlockStartEvent(reply_id="reply", block_id="text"), state
        )
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

    def test_composite_message_blocks_use_spaced_visual_containers(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None

        widget = CompositeMessageWidget(
            "assistant",
            [
                {"type": "text", "text": "First block"},
                {"type": "thinking", "thinking": "Second block"},
            ],
        )

        assert widget._blocks_layout.spacing() == 12
        text_container = widget._blocks_layout.itemAt(0).widget()
        thinking_container = widget._blocks_layout.itemAt(1).widget()
        assert text_container.objectName() == "chatMessageTextBlock"
        assert "border: none" in text_container.styleSheet()
        assert thinking_container.objectName() == "chatMessageBlock"
        assert "border" in thinking_container.styleSheet()
        assert "background-color: transparent" in thinking_container.styleSheet()
        assert thinking_container.layout().contentsMargins().left() == 6

    def test_composite_missing_type_defaults_to_unframed_text_container(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None

        widget = CompositeMessageWidget("assistant", [{"text": "First block"}])
        container = widget._blocks_layout.itemAt(0).widget()

        assert widget.get_block_widgets()[0].get_block_type() == "text"
        assert container.objectName() == "chatMessageTextBlock"
        assert "border: none" in container.styleSheet()

    def test_unsupported_history_block_does_not_leave_overlay_frame(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        widget = CompositeMessageWidget(
            "assistant",
            [
                {"type": "text", "text": "Visible text"},
                {
                    "type": "tool_call",
                    "id": "call-1",
                    "name": "tool_query_knowledge_base",
                },
            ],
        )

        direct_frames = [
            child
            for child in widget._blocks_container.children()
            if isinstance(child, QFrame)
        ]

        assert direct_frames == widget._block_containers
        assert len(direct_frames) == 1

    def test_history_blocks_are_created_with_a_parent_and_keep_no_orphan_frame(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        parents = []

        def create_with_parent(block_data, parent=None):
            parents.append(parent)
            return create_real_block_widget(block_data, parent)

        with patch.object(
            composite_message_widget,
            "create_block_widget",
            side_effect=create_with_parent,
        ):
            widget = CompositeMessageWidget(
                "assistant",
                [
                    {"type": "text", "text": "Visible text"},
                    {"type": "tool_call", "id": "call-1", "name": "tool"},
                ],
            )

        assert all(parent is not None for parent in parents)
        direct_frames = [
            child
            for child in widget._blocks_container.children()
            if isinstance(child, QFrame)
        ]
        assert direct_frames == widget._block_containers

    def test_theme_refresh_repairs_legacy_text_container_classification(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        widget = CompositeMessageWidget("assistant", [{"text": "First block"}])
        container = widget._block_containers[0]
        container.setObjectName("chatMessageBlock")
        container.setStyleSheet(Theme.get_chat_message_block_stylesheet())
        container.layout().setContentsMargins(6, 6, 6, 6)

        widget.refresh_theme()

        assert container.objectName() == "chatMessageTextBlock"
        assert "border: none" in container.styleSheet()
        assert container.layout().contentsMargins().left() == 0

    def test_message_bubble_style_does_not_apply_to_descendant_blocks(self):
        stylesheet = Theme.get_chat_message_bubble_stylesheet("assistant")

        assert "QWidget#chatMessageAssistant" in stylesheet
        assert "QWidget {" not in stylesheet
        assert Theme.hex("background_primary") in stylesheet
        assert "border: none" in stylesheet
        assert Theme.hex("accent_primary") in Theme.get_chat_message_bubble_stylesheet("user")
        assert "background-color: transparent" in Theme.get_message_content_edit_stylesheet()
        assert "background-color: transparent" in Theme.get_block_card_stylesheet()

    def test_user_messages_use_a_dedicated_card_bubble(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None

        composite = CompositeMessageWidget(
            "user",
            [{"type": "text", "text": "User input"}],
        )
        markdown = MarkdownMessageWidget("user", "User input")

        for widget in (composite, markdown):
            bubble = widget._bubble_card
            assert isinstance(bubble, QFrame)
            assert bubble.objectName() == "chatUserBubble"
            assert Theme.hex("background_selected") in bubble.styleSheet()
            assert Theme.hex("accent_primary") in bubble.styleSheet()
            assert bubble.layout().contentsMargins().left() == 10
            assert bubble.layout().indexOf(widget._role_label) == -1
            assert widget.layout().indexOf(widget._role_label) == 0
            assert (
                widget._role_label.alignment()
                & Qt.AlignmentFlag.AlignRight
            )

    def test_chat_panel_theme_refresh_reaches_inner_message_widgets(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()
        panel._add_message_widget("assistant", [{"text": "First block"}])
        message_widget = panel._messages[0]._message_widget
        message_widget.refresh_theme = MagicMock()

        panel.refresh_theme()

        message_widget.refresh_theme.assert_called_once_with()

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
        assert "<h1" in block._output_edit.document().toHtml()

    def test_tool_result_places_execution_events_above_final_output(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        block = ToolResultBlockWidget(
            {
                "type": "tool_result",
                "id": "call-1",
                "name": "image",
                "output": "# Final output",
                "execution_events": [
                    {
                        "event_kind": "phase",
                        "title": "Image Agent",
                        "text": "started",
                    },
                ],
            },
        )
        layout = block._output_edit.parentWidget().layout()

        assert layout.indexOf(block._execution_edit) < layout.indexOf(block._output_edit)
        assert "font-family: monospace" not in block._output_edit.styleSheet()

    def test_history_execution_log_is_never_shown_as_a_top_level_window(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        visibility_states = []

        class TrackingTextEdit(QTextEdit):
            def setVisible(self, visible):
                if self.objectName() == "subagentExecutionEvents" and visible:
                    visibility_states.append(
                        (self.parentWidget() is not None, self.isWindow()),
                    )
                super().setVisible(visible)

        parent = QWidget()
        with patch.object(tool_result_block, "QTextEdit", TrackingTextEdit):
            block = ToolResultBlockWidget(
                {
                    "type": "tool_result",
                    "id": "call-1",
                    "name": "image",
                    "output": "# Final output",
                    "execution_events": [
                        {
                            "event_kind": "phase",
                            "title": "Image Agent",
                            "text": "started",
                        },
                    ],
                },
                parent,
            )

        assert block._execution_edit.parentWidget() is not None
        assert visibility_states == [(True, False)]

    def test_tool_result_output_and_execution_logs_allow_scrolling(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        block = ToolResultBlockWidget(
            {"type": "tool_result", "id": "call-1", "name": "image", "output": "result"},
        )

        assert block._output_edit.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert block._execution_edit.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert block._output_edit.maximumHeight() == 280
        assert block._execution_edit.maximumHeight() == 240

    def test_tool_result_extracts_text_from_agentscope_response_repr(self):
        output = "content=[TextBlock(type='text', text='[\\n  {\\n    \\\"id\\\": 1\\n  }\\n]', id='block')] state=<ToolResultState.SUCCESS: 'success'>"

        assert ToolResultBlockWidget._output_text(output) == '[\n  {\n    "id": 1\n  }\n]'

    def test_message_layout_keeps_messages_top_aligned_and_roles_separated(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()
        panel.resize(1200, 800)
        panel.show()
        application.processEvents()

        panel._add_message_widget("assistant", "assistant")
        panel._add_message_widget("user", "user")
        application.processEvents()

        assert panel._messages_layout.itemAt(panel._messages_layout.count() - 1).spacerItem()
        assistant_row, user_row = panel._messages
        assistant = assistant_row._message_widget
        user = user_row._message_widget

        assert assistant_row.layout().itemAt(0).widget() is assistant
        assert assistant_row.layout().stretch(0) == 1
        assert assistant.width() == assistant_row.width()
        assert user_row.layout().itemAt(0).spacerItem()
        assert user_row.layout().itemAt(1).widget() is user
        assert 0 < user.width() <= int(user_row.width() * 0.8)

        panel.resize(900, 800)
        application.processEvents()
        assert 0 < user.width() <= int(user_row.width() * 0.8)
        assert "accent_primary" not in assistant.styleSheet()
        assert assistant.objectName() == "chatMessageAssistant"
        assert user.objectName() == "chatMessageUser"

    def test_message_width_policy_uses_full_assistant_and_eighty_percent_user_width(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()

        assert panel._message_maximum_width("assistant", 1000) == 16777215
        assert panel._message_maximum_width("user", 1000) == 800

    def test_short_user_message_uses_content_width_below_eighty_percent_cap(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()
        panel.resize(1200, 800)
        panel.show()
        application.processEvents()

        panel._add_message_widget("user", "Short input")
        application.processEvents()

        row = panel._messages[0]
        user_message = row._message_widget
        assert user_message.width() < int(row.width() * 0.8)

    def test_long_user_message_uses_the_eighty_percent_width_cap(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()
        panel.resize(1200, 800)
        panel.show()
        application.processEvents()

        panel._add_message_widget("user", "Long message content " * 80)
        application.processEvents()

        row = panel._messages[0]
        user_message = row._message_widget
        assert user_message.width() == int(row.width() * 0.8)

    def test_multimodal_user_message_keeps_the_eighty_percent_width_cap(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        widget = CompositeMessageWidget(
            "user",
            [
                {
                    "type": "image",
                    "source": {"type": "base64", "data": "aW1hZ2U="},
                },
            ],
        )

        assert widget.preferred_user_width(800) == 800

    def test_history_extracts_persisted_subagent_execution_events(self):
        message = type(
            "Message",
            (),
            {
                "content": [
                    type(
                        "ToolResult",
                        (),
                        {
                            "type": "tool_result",
                            "id": "call-1",
                            "name": "tool_unity_ar",
                            "output": "# Result",
                            "metadata": {
                                "execution_events": [
                                    {
                                        "event_kind": "phase",
                                        "title": "Unity Agent",
                                        "text": "started",
                                    },
                                ],
                            },
                        },
                    )(),
                ],
            },
        )()

        blocks = chat_panel._extract_blocks_from_msg(message)

        assert blocks[0]["execution_events"][0]["title"] == "Unity Agent"

    def test_history_normalizes_nested_tool_result_text_for_display(self):
        blocks = chat_panel._normalize_blocks(
            [
                {
                    "type": "tool_result",
                    "id": "call-1",
                    "name": "tool_blender_model",
                    "output": {
                        "content": [
                            {
                                "type": "text",
                                "text": "# 执行结果\n\n## 状态\n成功",
                            },
                        ],
                        "state": "success",
                    },
                },
            ],
        )

        assert blocks == [
            {
                "type": "tool_result",
                "id": "call-1",
                "name": "tool_blender_model",
                "output": "# 执行结果\n\n## 状态\n成功",
            },
        ]

    def test_history_normalizes_persisted_native_image_data_block_for_display(self):
        blocks = chat_panel._normalize_blocks(
            [
                {
                    "type": "data",
                    "name": "image",
                    "source": {
                        "type": "base64",
                        "data": "aW1hZ2U=",
                        "media_type": "image/png",
                    },
                },
            ],
        )

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

    def test_direct_subagent_ui_events_bypass_agentscope_event_adapter(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()
        panel._worker = MagicMock()
        callback = panel._create_streaming_callback()
        direct_event = {
            "type": "subagent_event",
            "parent_tool_call_id": "call-1",
            "event_kind": "phase",
            "title": "Unity Agent",
            "text": "started",
            "status": "running",
        }

        callback(None, {"event": direct_event}, None)

        panel._worker.block_update.emit.assert_called_once_with([direct_event])

    def test_message_widgets_do_not_schedule_automatic_scroll(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        panel = chat_panel.ChatPanel()

        with patch.object(chat_panel.QTimer, "singleShot") as single_shot:
            panel._add_message_widget("assistant", "# Markdown")

        single_shot.assert_not_called()

    def test_running_agent_locks_session_switching_and_blocks_direct_selection(self):
        application = QApplication.instance() or QApplication([])
        assert application is not None
        history_repository = MagicMock()
        history_repository.list_sessions.return_value = []
        panel = chat_panel.ChatPanel(history_repository=history_repository)
        panel._agent = MagicMock()

        panel._set_session_switching_enabled(False)
        panel._on_session_selected("other-session")

        assert not panel._session_list._list_widget.isEnabled()
        assert not panel._session_list._new_btn.isEnabled()
        panel._agent.switch_session.assert_not_called()

        panel._set_session_switching_enabled(True)
        assert panel._session_list._list_widget.isEnabled()
        assert panel._session_list._new_btn.isEnabled()

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
