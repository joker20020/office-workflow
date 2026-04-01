# -*- coding: utf-8 -*-
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QResizeEvent
from PySide6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.theme import Theme


class ThinkingBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "thinking"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._header_button: QPushButton | None = None
        self._content_edit: QTextEdit | None = None
        self._content: str = ""
        self._collapsed: bool = True
        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        self._content = self._block_data.get("thinking", "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header_button = QPushButton(self._get_header_text())
        self._header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header_button.clicked.connect(self.toggle)

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

        font = QFont()
        font.setItalic(True)
        self._content_edit.setFont(font)

        self._set_text_content(self._content)
        self._content_edit.setVisible(not self._collapsed)

        layout.addWidget(self._header_button)
        layout.addWidget(self._content_edit)

    def _apply_styles(self) -> None:
        if self._header_button:
            self._header_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.hex("background_tertiary")};
                    color: {Theme.hex("text_hint")};
                    border: none;
                    border-radius: 4px;
                    padding: 6px 10px;
                    text-align: left;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.hex("background_hover")};
                }}
            """)

        if self._content_edit:
            self._content_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {Theme.hex("background_tertiary")};
                    color: {Theme.hex("text_hint")};
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 12px;
                    font-style: italic;
                }}
            """)

    def _get_header_text(self) -> str:
        arrow = "▶" if self._collapsed else "▼"
        return f"💭 Thinking {arrow}"

    def _set_text_content(self, content: str) -> None:
        if self._content_edit:
            self._content_edit.setPlainText(content)
            self._adjust_height()

    def _adjust_height(self) -> None:
        if not self._content_edit:
            return
        if self._collapsed:
            self._content_edit.setFixedHeight(0)
        else:
            doc = self._content_edit.document()
            doc.setTextWidth(self._content_edit.width())
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
        self._set_text_content(content)
        self.content_changed.emit()

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        if self._header_button:
            self._header_button.setText(self._get_header_text())
        if self._content_edit:
            self._content_edit.setVisible(not self._collapsed)
        self._adjust_height()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def refresh_theme(self) -> None:
        self._apply_styles()
