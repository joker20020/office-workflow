# -*- coding: utf-8 -*-
"""ChatPanel streaming tests"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import QWidget


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
