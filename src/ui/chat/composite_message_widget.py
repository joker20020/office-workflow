# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.chat.blocks import create_block_widget
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin


class CompositeMessageWidget(QWidget, ThemeAwareMixin):
    content_clicked = Signal()
    content_double_clicked = Signal()

    def __init__(
        self,
        role: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()

        self._role = role
        self._blocks = blocks if blocks else []
        self._block_widgets: List[BaseBlockWidget] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._role_label = QLabel(self._role.upper())
        self._role_label.setStyleSheet(Theme.get_message_role_label_stylesheet(self._role))
        layout.addWidget(self._role_label)

        self._blocks_container = QWidget()
        self._blocks_layout = QVBoxLayout(self._blocks_container)
        self._blocks_layout.setContentsMargins(0, 0, 0, 0)
        self._blocks_layout.setSpacing(8)
        self._blocks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for block_data in self._blocks:
            self._add_block_widget(block_data)

        layout.addWidget(self._blocks_container)

    def _add_block_widget(self, block_data: Dict[str, Any]) -> Optional[BaseBlockWidget]:
        widget = create_block_widget(block_data, self._blocks_container)
        if widget:
            widget.height_changed.connect(self._on_block_height_changed)
            self._blocks_layout.addWidget(widget)
            self._block_widgets.append(widget)
        return widget

    def _on_block_height_changed(self) -> None:
        pass

    def get_role(self) -> str:
        return self._role

    def get_blocks(self) -> List[Dict[str, Any]]:
        return self._blocks.copy()

    def get_block_widgets(self) -> List[BaseBlockWidget]:
        return self._block_widgets.copy()

    def block_count(self) -> int:
        return len(self._block_widgets)

    def get_text_content(self) -> str:
        text_parts = []
        for widget in self._block_widgets:
            if widget.get_block_type() == "text":
                text_parts.append(widget.get_content())
        return "\n".join(text_parts)

    def get_all_content(self) -> str:
        all_parts = []
        for widget in self._block_widgets:
            all_parts.append(widget.get_content())
        return "\n".join(all_parts)

    def update_last_text_block(self, new_content: str) -> bool:
        for i in range(len(self._block_widgets) - 1, -1, -1):
            widget = self._block_widgets[i]
            if widget.get_block_type() == "text":
                widget.set_content(new_content)
                return True
        return False

    def update_last_thinking_block(self, new_content: str) -> bool:
        for i in range(len(self._block_widgets) - 1, -1, -1):
            widget = self._block_widgets[i]
            if widget.get_block_type() == "thinking":
                widget.set_content(new_content)
                return True
        return False

    def update_last_tool_use_block(self, block_data: Dict[str, Any]) -> bool:
        for i in range(len(self._block_widgets) - 1, -1, -1):
            widget = self._block_widgets[i]
            if widget.get_block_type() == "tool_use":
                widget.update_block_data(block_data)
                return True
        return False

    def update_last_tool_result_block(self, block_data: Dict[str, Any]) -> bool:
        for i in range(len(self._block_widgets) - 1, -1, -1):
            widget = self._block_widgets[i]
            if widget.get_block_type() == "tool_result":
                widget.update_block_data(block_data)
                return True
        return False

    def add_or_update_block(self, block_data: Dict[str, Any]) -> None:
        block_type = block_data.get("type", "text")
        block_id = block_data.get("id", "")
        
        if len(self._block_widgets) > 0 and self._block_widgets[-1].get_block_type() == block_type:
            if block_type in ("tool_use", "tool_result") and block_id:
                for widget in self._block_widgets:
                    if widget.get_block_type() == block_type and widget.get_block_id() == block_id:
                        widget.update_block_data(block_data)
                        return

            for widget in reversed(self._block_widgets):
                if widget.get_block_type() == block_type:
                    widget.update_block_data(block_data)
                    if block_type in ("text", "thinking"):
                        content_key = "thinking" if block_type == "thinking" else "text"
                        if content_key in block_data:
                            widget.set_content(block_data[content_key])
                return

        self._add_block_widget(block_data)
        self._blocks.append(block_data)

    def refresh_theme(self) -> None:
        self._role_label.setStyleSheet(Theme.get_message_role_label_stylesheet(self._role))
        for widget in self._block_widgets:
            widget.refresh_theme()
