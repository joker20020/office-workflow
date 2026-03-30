# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QTextCursor, QResizeEvent
from PySide6.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QLabel

from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin


class MarkdownMessageWidget(QWidget, ThemeAwareMixin):
    content_clicked = Signal()
    content_double_clicked = Signal()

    def __init__(
        self,
        role: str,
        content: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()

        self._role = role
        self._content = content
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._role_label = QLabel(self._role.upper())
        self._role_label.setStyleSheet(Theme.get_message_role_label_stylesheet(self._role))

        self._content_edit = QTextEdit()
        self._content_edit.setReadOnly(True)
        self._content_edit.setCursorWidth(0)
        self._content_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._content_edit.setStyleSheet(Theme.get_message_content_edit_stylesheet())
        self._content_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._content_edit.document().contentsChanged.connect(self._adjust_height)
        self._content_edit.mousePressEvent = self._on_content_mouse_press
        self._content_edit.mouseDoubleClickEvent = self._on_content_mouse_double_click
        self._set_markdown_content(self._content)

        layout.addWidget(self._role_label)
        layout.addWidget(self._content_edit)

    def _on_content_mouse_press(self, event):
        # Call parent's handler first to preserve text selection functionality
        QTextEdit.mousePressEvent(self._content_edit, event)
        self.content_clicked.emit()

    def _on_content_mouse_double_click(self, event):
        # Call parent's handler first to preserve text selection functionality
        QTextEdit.mouseDoubleClickEvent(self._content_edit, event)
        self.content_double_clicked.emit()

    def _set_markdown_content(self, content: str) -> None:
        self._content_edit.setMarkdown(content)
        self._adjust_height()

    def _adjust_height(self) -> None:
        doc = self._content_edit.document()
        doc.setTextWidth(self._content_edit.width())
        doc_height = doc.documentLayout().documentSize().height()
        margins = self._content_edit.contentsMargins()
        total_height = int(doc_height + margins.top() + margins.bottom() + 16)
        self._content_edit.setFixedHeight(max(total_height, 40))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._adjust_height()

    def set_content(self, content: str) -> None:
        self._content = content
        self._set_markdown_content(content)

    def get_content(self) -> str:
        return self._content

    def refresh_theme(self) -> None:
        self._role_label.setStyleSheet(Theme.get_message_role_label_stylesheet(self._role))
        self._content_edit.setStyleSheet(Theme.get_message_content_edit_stylesheet())
