# -*- coding: utf-8 -*-
"""
Thinking Block — 卡片式折叠展示

结构:
  QFrame#blockCard (卡片容器, 左侧 3px 橙色强调)
  ├── QFrame#blockHeader (可点击标题行)
  │   ├── QLabel "💭"
  │   ├── QLabel "Thinking"
  │   ├── stretch
  │   └── AnimatedArrow
  └── CollapsibleBox
      └── QTextEdit (内容, 斜体)
"""
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QResizeEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout

from src.ui.chat.blocks.animated_arrow import AnimatedArrow
from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.chat.blocks.collapsible import CollapsibleBox
from src.ui.theme import Theme


class ThinkingBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "thinking"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._content: str = ""
        self._collapsed: bool = True
        self._card: QFrame | None = None
        self._header: QFrame | None = None
        self._arrow: AnimatedArrow | None = None
        self._content_edit: QTextEdit | None = None
        self._collapsible: CollapsibleBox | None = None
        super().__init__(block_data, parent)

    # ------------------------------------------------------------------ UI

    def _setup_ui(self) -> None:
        self._content = self._block_data.get("thinking", "")

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
        self._header.mousePressEvent = lambda e: self.toggle()

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(6)

        icon_label = QLabel("💭")
        icon_label.setStyleSheet(Theme.get_block_card_icon_stylesheet())
        header_layout.addWidget(icon_label)

        title_label = QLabel("Thinking")
        title_label.setStyleSheet(Theme.get_block_card_title_stylesheet("text_hint"))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self._arrow = AnimatedArrow()
        header_layout.addWidget(self._arrow)

        card_layout.addWidget(self._header)

        # --- 内容区 (折叠容器) ---
        self._content_edit = QTextEdit()
        self._content_edit.setReadOnly(True)
        self._content_edit.setCursorWidth(0)
        self._content_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._content_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        font = QFont()
        font.setItalic(True)
        self._content_edit.setFont(font)

        self._content_edit.setPlainText(self._content)

        self._collapsible = CollapsibleBox(self._content_edit)
        card_layout.addWidget(self._collapsible)

        outer.addWidget(self._card)

    def _apply_styles(self) -> None:
        if self._card:
            self._card.setStyleSheet(Theme.get_block_card_stylesheet("thinking_accent"))
        if self._header:
            self._header.setStyleSheet(Theme.get_block_card_header_stylesheet())
        if self._content_edit:
            self._content_edit.setStyleSheet(
                Theme.get_block_card_content_stylesheet(content_type="thinking")
            )

    # ------------------------------------------------------------------ 展开/折叠

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        expanded = not self._collapsed

        if self._arrow:
            self._arrow.set_expanded(expanded, animate=True)
        if self._collapsible:
            self._collapsible.set_expanded(expanded, animate=True)
        self.height_changed.emit()

    # ------------------------------------------------------------------ 内容

    def _adjust_content_height(self) -> None:
        """通知 collapsible 内容高度变化。"""
        if self._collapsible and self._collapsible.is_expanded():
            self._collapsible.update_content_height(animate=False)
            self.height_changed.emit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._adjust_content_height()

    def get_content(self) -> str:
        return self._content

    def set_content(self, content: str) -> None:
        self._content = content
        if self._content_edit:
            self._content_edit.setPlainText(content)
            self._adjust_content_height()
        self.content_changed.emit()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def refresh_theme(self) -> None:
        if self._collapsible:
            self._collapsible.stop_animation()
        if self._arrow:
            self._arrow.stop_animation()
        self._apply_styles()
