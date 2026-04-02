# -*- coding: utf-8 -*-
"""
Tool Use Block — 卡片式折叠展示

结构:
  QFrame#blockCard (卡片容器, 左侧 3px 蓝色强调)
  ├── QFrame#blockHeader (可点击标题行)
  │   ├── QLabel "🔧"
  │   ├── QLabel "Tool: {name}"
  │   ├── stretch
  │   └── AnimatedArrow
  └── CollapsibleBox
      └── QTextEdit (JSON 输入, 等宽字体)
"""
from typing import Any, Dict
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout

from src.ui.chat.blocks.animated_arrow import AnimatedArrow
from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.chat.blocks.collapsible import CollapsibleBox
from src.ui.theme import Theme


class ToolUseBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "tool_use"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._tool_id: str = ""
        self._tool_name: str = ""
        self._tool_input: Dict[str, Any] = {}
        self._input_expanded: bool = True

        self._card: QFrame | None = None
        self._header: QFrame | None = None
        self._tool_name_label: QLabel | None = None
        self._arrow: AnimatedArrow | None = None
        self._input_edit: QTextEdit | None = None
        self._collapsible: CollapsibleBox | None = None

        super().__init__(block_data, parent)

    # ------------------------------------------------------------------ UI

    def _setup_ui(self) -> None:
        self._tool_id = self._block_data.get("id", "")
        self._tool_name = self._block_data.get("name", "unknown")
        self._tool_input = self._block_data.get("input", {})

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
        self._header.mousePressEvent = lambda e: self.toggle_input()

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(6)

        icon_label = QLabel("🔧")
        icon_label.setStyleSheet(Theme.get_block_card_icon_stylesheet())
        header_layout.addWidget(icon_label)

        self._tool_name_label = QLabel()
        self._tool_name_label.setText(f"Tool: {self._tool_name}")
        self._tool_name_label.setStyleSheet(
            Theme.get_block_card_title_stylesheet("accent_primary")
        )
        header_layout.addWidget(self._tool_name_label)

        header_layout.addStretch()

        self._arrow = AnimatedArrow()
        header_layout.addWidget(self._arrow)

        card_layout.addWidget(self._header)

        # --- 内容区 ---
        self._input_edit = QTextEdit()
        self._input_edit.setReadOnly(True)
        self._input_edit.setCursorWidth(0)
        self._input_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._input_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._input_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._input_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        self._set_input_content()

        self._collapsible = CollapsibleBox(self._input_edit)
        card_layout.addWidget(self._collapsible)

        outer.addWidget(self._card)

        # 默认展开
        if self._input_expanded:
            self._collapsible.set_expanded(True, animate=False)
            self._arrow.set_expanded(True, animate=False)

    def _apply_styles(self) -> None:
        if self._card:
            self._card.setStyleSheet(Theme.get_block_card_stylesheet("tool_accent"))
        if self._header:
            self._header.setStyleSheet(Theme.get_block_card_header_stylesheet())
        if self._input_edit:
            self._input_edit.setStyleSheet(
                Theme.get_block_card_content_stylesheet(content_type="code")
            )

    # ------------------------------------------------------------------ 展开/折叠

    def toggle_input(self) -> None:
        self._input_expanded = not self._input_expanded

        if self._arrow:
            self._arrow.set_expanded(self._input_expanded, animate=True)
        if self._collapsible:
            self._collapsible.set_expanded(self._input_expanded, animate=True)
        self.height_changed.emit()

    def is_input_expanded(self) -> bool:
        return self._input_expanded

    # ------------------------------------------------------------------ 内容

    def _set_input_content(self) -> None:
        if not self._input_edit:
            return
        input_str = json.dumps(self._tool_input, indent=2, ensure_ascii=False)
        self._input_edit.setPlainText(input_str)
        if self._collapsible and self._collapsible.is_expanded():
            self._collapsible.update_content_height(animate=False)

    def get_content(self) -> str:
        return f"{self._tool_name}({json.dumps(self._tool_input, ensure_ascii=False)})"

    def set_content(self, content: str) -> None:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                self._tool_input = parsed
                self._set_input_content()
                self.content_changed.emit()
        except json.JSONDecodeError:
            pass

    def set_input_content(self, input_data: Dict[str, Any]) -> None:
        self._tool_input = input_data
        self._set_input_content()

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
        self._tool_input = new_data.get("input", self._tool_input)
        if self._tool_name_label:
            self._tool_name_label.setText(f"Tool: {self._tool_name}")
        self._set_input_content()
