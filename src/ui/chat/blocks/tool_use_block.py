# -*- coding: utf-8 -*-
from typing import Any, Dict
import json

from PySide6.QtCore import Qt
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
        self._input_expanded: bool = True  # Start expanded by default for debugging

        self._header_frame: QFrame | None = None
        self._tool_name_label: QLabel | None = None
        self._toggle_input_btn: QPushButton | None = None
        self._input_edit: QTextEdit | None = None

        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        self._tool_id = self._block_data.get("id", "")
        self._tool_name = self._block_data.get("name", "unknown")
        self._tool_input = self._block_data.get("input", {})

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._header_frame = QFrame()
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(6)

        tool_icon = QLabel()
        tool_icon.setText("🔧")
        header_layout.addWidget(tool_icon)

        self._tool_name_label = QLabel()
        self._tool_name_label.setText(f"Tool: {self._tool_name}")
        header_layout.addWidget(self._tool_name_label)
        header_layout.addStretch()

        self._toggle_input_btn = QPushButton("▼ Input")
        self._toggle_input_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_input_btn.clicked.connect(self.toggle_input)
        header_layout.addWidget(self._toggle_input_btn)

        main_layout.addWidget(self._header_frame)

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
        self._input_edit.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', 'Courier New', monospace;"
        )
        self._set_input_content()
        main_layout.addWidget(self._input_edit)

    def _apply_styles(self) -> None:
        if self._header_frame:
            self._header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.hex("background_secondary")};
                    border: 1px solid {Theme.hex("border_primary")};
                    border-left: 3px solid {Theme.hex("border_focus")};
                    border-radius: 4px;
                }}
            """)

        if self._tool_name_label:
            self._tool_name_label.setStyleSheet(f"""
                QLabel {{
                    color: {Theme.hex("accent_primary")};
                    font-size: 12px;
                    font-weight: bold;
                    background-color: transparent;
                }}
            """)

        if self._input_edit:
            self._input_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {Theme.hex("background_secondary")};
                    color: {Theme.hex("text_primary")};
                    border: 1px solid {Theme.hex("border_primary")};
                    border-left: 3px solid {Theme.hex("border_focus")};
                    border-radius: 4px;
                    padding: 8px;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                    font-size: 11px;
                }}
            """)

        if self._toggle_input_btn:
            self._toggle_input_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Theme.hex("text_link")};
                    border: none;
                    padding: 4px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    color: {Theme.hex("accent_hover")};
                }}
            """)

    def _set_input_content(self) -> None:
        if not self._input_edit:
            return

        input_str = json.dumps(self._tool_input, indent=2, ensure_ascii=False)
        self._input_edit.setPlainText(input_str)
        self._adjust_height()

    def _adjust_height(self) -> None:
        if not self._input_edit:
            return

        if not self._input_expanded:
            self._input_edit.setFixedHeight(0)
            self.height_changed.emit()
            return

        doc = self._input_edit.document()
        doc.setTextWidth(self._input_edit.width())
        doc_height = doc.documentLayout().documentSize().height()
        margins = self._input_edit.contentsMargins()
        total_height = int(doc_height + margins.top() + margins.bottom() + 16)
        self._input_edit.setFixedHeight(max(total_height, 40))
        self.height_changed.emit()

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

    def set_input_content(self, input: Dict[str, Any]) -> None:
        self._tool_input = input
        self._set_input_content()

    def toggle_input(self) -> None:
        self._input_expanded = not self._input_expanded

        if self._toggle_input_btn:
            arrow = "▼" if self._input_expanded else "▶"
            self._toggle_input_btn.setText(f"{arrow} Input")

        if self._input_edit:
            self._input_edit.setVisible(self._input_expanded)

        self._adjust_height()

    def is_input_expanded(self) -> bool:
        return self._input_expanded

    def refresh_theme(self) -> None:
        self._apply_styles()

    def update_block_data(self, new_data: Dict[str, Any]) -> None:
        super().update_block_data(new_data)
        self._tool_id = new_data.get("id", self._tool_id)
        self._tool_name = new_data.get("name", self._tool_name)
        self._tool_input = new_data.get("input", self._tool_input)
        if self._tool_name_label:
            self._tool_name_label.setText(f"Tool: {self._tool_name}")
        self._set_input_content()
