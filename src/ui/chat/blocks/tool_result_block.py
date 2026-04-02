# -*- coding: utf-8 -*-
"""
Tool Result Block — 卡片式折叠展示

结构:
  QFrame#blockCard (卡片容器, 左侧 3px 绿色/红色强调)
  ├── QFrame#blockHeader (可点击标题行)
  │   ├── QLabel "✓" / "✗"
  │   ├── QLabel "Result: {name}"
  │   ├── stretch
  │   └── AnimatedArrow
  └── CollapsibleBox
      └── QTextEdit (输出内容, 等宽字体)
"""
from typing import Any, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout

from src.ui.chat.blocks.animated_arrow import AnimatedArrow
from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.chat.blocks.collapsible import CollapsibleBox
from src.ui.theme import Theme


class ToolResultBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "tool_result"

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

        self._card: QFrame | None = None
        self._header: QFrame | None = None
        self._status_icon_label: QLabel | None = None
        self._tool_name_label: QLabel | None = None
        self._arrow: AnimatedArrow | None = None
        self._output_edit: QTextEdit | None = None
        self._collapsible: CollapsibleBox | None = None

        super().__init__(block_data, parent)

    # ------------------------------------------------------------------ UI

    def _setup_ui(self) -> None:
        self._tool_id = self._block_data.get("id", "")
        self._tool_name = self._block_data.get("name", "unknown")
        output_blocks = self._block_data.get("output", "")
        for block in output_blocks:
            if block.get("type", "") == "text":
                self._tool_output += block.get("text", "")
        self._is_error = self._detect_error_state(self._tool_output)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- 卡片容器 ---
        self._card = QFrame()
        self._card.setObjectName("blockCard")

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # --- 标题行 ---
        self._header = QFrame()
        self._header.setObjectName("blockHeader")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.mousePressEvent = lambda e: self.toggle_expand()

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(6)

        self._status_icon_label = QLabel()
        self._status_icon_label.setText("✓" if not self._is_error else "✗")
        header_layout.addWidget(self._status_icon_label)

        self._tool_name_label = QLabel()
        self._tool_name_label.setText(f"Result: {self._tool_name}")
        header_layout.addWidget(self._tool_name_label)

        header_layout.addStretch()

        self._arrow = AnimatedArrow()
        header_layout.addWidget(self._arrow)

        card_layout.addWidget(self._header)

        # --- 内容区 ---
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
        self._output_edit.setPlainText(self._tool_output)

        self._collapsible = CollapsibleBox(self._output_edit)
        card_layout.addWidget(self._collapsible)

        outer.addWidget(self._card)

    def _apply_styles(self) -> None:
        accent_key = "error_accent" if self._is_error else "success_accent"

        if self._card:
            self._card.setStyleSheet(Theme.get_block_card_stylesheet(accent_key))
        if self._header:
            self._header.setStyleSheet(Theme.get_block_card_header_stylesheet())
        if self._status_icon_label:
            color_key = "error_accent" if self._is_error else "success_accent"
            self._status_icon_label.setStyleSheet(f"""
                QLabel {{
                    color: {Theme.hex(color_key)};
                    font-size: 14px;
                    font-weight: bold;
                    background-color: transparent;
                    {Theme.emoji_font_css()}
                }}
            """)
        if self._tool_name_label:
            self._tool_name_label.setStyleSheet(
                Theme.get_block_card_title_stylesheet("text_primary")
            )
        if self._output_edit:
            self._output_edit.setStyleSheet(
                Theme.get_block_card_content_stylesheet(
                    content_type="code",
                    is_error=self._is_error,
                )
            )

    # ------------------------------------------------------------------ 展开/折叠

    def toggle_expand(self) -> None:
        self._is_expanded = not self._is_expanded

        if self._arrow:
            self._arrow.set_expanded(self._is_expanded, animate=True)
        if self._collapsible:
            self._collapsible.set_expanded(self._is_expanded, animate=True)
        self.expand_changed.emit()
        self.height_changed.emit()

    def is_expanded(self) -> bool:
        return self._is_expanded

    # ------------------------------------------------------------------ 内容

    def _detect_error_state(self, output: str) -> bool:
        output_lower = output.lower()
        error_indicators = ["error", "failed", "exception", "traceback", "error:"]
        return any(indicator in output_lower for indicator in error_indicators)

    def get_content(self) -> str:
        return self._tool_output

    def set_content(self, content: str) -> None:
        self._tool_output = content
        self._is_error = self._detect_error_state(content)

        if self._output_edit:
            self._output_edit.setPlainText(content)
        if self._status_icon_label:
            self._status_icon_label.setText("✓" if not self._is_error else "✗")
        if self._collapsible and self._collapsible.is_expanded():
            self._collapsible.update_content_height(animate=False)

        self._apply_styles()
        self.content_changed.emit()

    def refresh_theme(self) -> None:
        if self._collapsible:
            self._collapsible.stop_animation()
        if self._arrow:
            self._arrow.stop_animation()
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
            if self._output_edit:
                self._output_edit.setPlainText(self._tool_output)
            if self._collapsible and self._collapsible.is_expanded():
                self._collapsible.update_content_height(animate=False)
            self._apply_styles()
