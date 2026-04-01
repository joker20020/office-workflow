# -*- coding: utf-8 -*-
from typing import Any, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.theme import Theme


class ToolResultBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "tool_result"
    MAX_PREVIEW_LENGTH = 200

    expand_changed = Signal()

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._tool_id: str = ""
        self._tool_name: str = ""
        self._tool_output: str = ""
        self._is_expanded: bool = False
        self._is_error: bool = False
        self._header_frame: QFrame | None = None
        self._status_icon_label: QLabel | None = None
        self._tool_name_label: QLabel | None = None
        self._output_edit: QTextEdit | None = None
        self._toggle_button: QPushButton | None = None

        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        self._tool_id = self._block_data.get("id", "")
        self._tool_name = self._block_data.get("name", "unknown")
        output_blocks = self._block_data.get("output", "")
        for block in output_blocks:
            if block.get("type", "") == "text":
                self._tool_output += block.get("text", "")
        self._is_error = self._detect_error_state(self._tool_output)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._header_frame = QFrame()
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(6)

        self._status_icon_label = QLabel()
        self._status_icon_label.setText("✓" if not self._is_error else "✗")
        header_layout.addWidget(self._status_icon_label)

        self._tool_name_label = QLabel()
        self._tool_name_label.setText(f"Result: {self._tool_name}")
        header_layout.addWidget(self._tool_name_label)
        header_layout.addStretch()

        main_layout.addWidget(self._header_frame)

        self._output_edit = QTextEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setCursorWidth(0)
        self._output_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._output_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._output_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._output_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        self._update_output_display()

        main_layout.addWidget(self._output_edit)

        if len(self._tool_output) > self.MAX_PREVIEW_LENGTH:
            self._toggle_button = QPushButton("Show more")
            self._toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._toggle_button.clicked.connect(self.toggle_expand)
            main_layout.addWidget(self._toggle_button)

    def _apply_styles(self) -> None:
        if self._header_frame:
            self._header_frame.setStyleSheet(
                Theme.get_tool_result_block_header_frame_stylesheet(is_error=self._is_error)
            )

        if self._status_icon_label:
            self._status_icon_label.setStyleSheet(
                Theme.get_tool_result_block_status_icon_stylesheet(is_error=self._is_error)
            )

        if self._tool_name_label:
            self._tool_name_label.setStyleSheet(Theme.get_tool_result_block_name_stylesheet())

        if self._output_edit:
            self._output_edit.setStyleSheet(
                Theme.get_tool_result_block_content_stylesheet(is_error=self._is_error)
            )

        if self._toggle_button:
            self._toggle_button.setStyleSheet(Theme.get_tool_result_show_more_button_stylesheet())

    def _detect_error_state(self, output: str) -> bool:
        output_lower = output.lower()
        error_indicators = ["error", "failed", "exception", "traceback", "error:"]
        return any(indicator in output_lower for indicator in error_indicators)

    def _update_output_display(self) -> None:
        if not self._output_edit:
            return

        if self._is_expanded or len(self._tool_output) <= self.MAX_PREVIEW_LENGTH:
            self._output_edit.setPlainText(self._tool_output)
        else:
            truncated = self._tool_output[: self.MAX_PREVIEW_LENGTH] + "..."
            self._output_edit.setPlainText(truncated)

        self._adjust_height()

    def _adjust_height(self) -> None:
        if not self._output_edit:
            return

        doc = self._output_edit.document()
        doc.setTextWidth(self._output_edit.width())
        doc_height = doc.documentLayout().documentSize().height()
        margins = self._output_edit.contentsMargins()

        if not self._is_expanded:
            max_height = 150
            total_height = min(int(doc_height + margins.top() + margins.bottom() + 16), max_height)
        else:
            total_height = int(doc_height + margins.top() + margins.bottom() + 16)

        self._output_edit.setFixedHeight(max(total_height, 40))
        self.height_changed.emit()

    def get_content(self) -> str:
        return self._tool_output

    def set_content(self, content: str) -> None:
        self._tool_output = content
        self._is_error = self._detect_error_state(content)
        self._update_output_display()

        if self._status_icon_label:
            self._status_icon_label.setText("✓" if not self._is_error else "✗")

        self._apply_styles()
        self.content_changed.emit()

    def is_expanded(self) -> bool:
        return self._is_expanded

    def toggle_expand(self) -> None:
        self._is_expanded = not self._is_expanded

        if self._toggle_button:
            self._toggle_button.setText("Show less" if self._is_expanded else "Show more")

        self._update_output_display()
        self.expand_changed.emit()

    def refresh_theme(self) -> None:
        self._apply_styles()

    def update_block_data(self, new_data: Dict[str, Any]) -> None:
        super().update_block_data(new_data)
        self._tool_id = new_data.get("id", self._tool_id)
        self._tool_name = new_data.get("name", self._tool_name)
        new_output = new_data.get("output", self._tool_output)
        if new_output != self._tool_output:
            self._tool_output = new_output
            self._is_error = self._detect_error_state(self._tool_output)
            if self._tool_name_label:
                self._tool_name_label.setText(f"Result: {self._tool_name}")
            if self._status_icon_label:
                self._status_icon_label.setText("✓" if not self._is_error else "✗")
            self._apply_styles()
            self._update_output_display()
