# -*- coding: utf-8 -*-
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QTextEdit, QVBoxLayout

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.theme import Theme


class TextBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "text"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._content: str = ""
        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        self._content = self._block_data.get("text", "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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
        self._content_edit.document().contentsChanged.connect(self._adjust_height)
        self._set_markdown_content(self._content)

        layout.addWidget(self._content_edit)

    def _apply_styles(self) -> None:
        if self._content_edit:
            self._content_edit.setStyleSheet(Theme.get_message_content_edit_stylesheet())

    def _set_markdown_content(self, content: str) -> None:
        if self._content_edit:
            self._content_edit.setMarkdown(content)
            self._adjust_height()

    def _adjust_height(self) -> None:
        if not self._content_edit:
            return
        doc = self._content_edit.document()

        # 获取可用文本宽度：优先用自身宽度，否则向上查找父级
        w = self._content_edit.width()
        if w <= 0:
            p = self.parentWidget()
            while p:
                if p.width() > 0:
                    w = p.width()
                    break
                p = p.parentWidget()
        if w <= 0:
            w = 600

        # 减去 QSS padding (get_message_content_edit_stylesheet: padding 8px)
        text_w = w - 16
        doc.setTextWidth(max(text_w, 50))

        doc_height = doc.documentLayout().documentSize().height()
        margins = self._content_edit.contentsMargins()
        total_height = int(doc_height + margins.top() + margins.bottom() + 16)
        self._content_edit.setFixedHeight(max(total_height, 40))
        self.height_changed.emit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._adjust_height()

    def get_content(self) -> str:
        return self._content

    def set_content(self, content: str) -> None:
        self._content = content
        self._set_markdown_content(content)
        self.content_changed.emit()

    def refresh_theme(self) -> None:
        self._apply_styles()
