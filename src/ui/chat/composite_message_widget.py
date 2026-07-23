# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.chat.blocks import create_block_widget
from src.ui.chat.message_widget import text_editor_natural_width
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
        self._block_containers: List[QFrame] = []
        self._bubble_card: Optional[QFrame] = None
        self.setObjectName(f"chatMessage{role.capitalize()}")

        self._setup_ui()

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        self._role_label = QLabel(self._role.upper())
        self._role_label.setStyleSheet(Theme.get_message_role_label_stylesheet(self._role))

        if self._role == "user":
            self._role_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            root_layout.addWidget(self._role_label)
            self._bubble_card = QFrame(self)
            self._bubble_card.setObjectName("chatUserBubble")
            self._bubble_card.setStyleSheet(
                Theme.get_chat_message_bubble_stylesheet(self._role),
            )
            layout = QVBoxLayout(self._bubble_card)
            layout.setContentsMargins(10, 10, 10, 10)
            root_layout.addWidget(self._bubble_card)
        else:
            self.setStyleSheet(Theme.get_chat_message_bubble_stylesheet(self._role))
            layout = root_layout
            layout.setContentsMargins(8, 8, 8, 8)
            layout.addWidget(self._role_label)
        layout.setSpacing(4)

        self._blocks_container = QWidget(self._bubble_card or self)
        self._blocks_layout = QVBoxLayout(self._blocks_container)
        self._blocks_layout.setContentsMargins(0, 0, 0, 0)
        self._blocks_layout.setSpacing(12)
        self._blocks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for block_data in self._blocks:
            self._add_block_widget(block_data)

        layout.addWidget(self._blocks_container)

    def _add_block_widget(self, block_data: Dict[str, Any]) -> Optional[BaseBlockWidget]:
        # Build the renderer first. Unsupported persisted blocks (for example
        # AgentScope ``tool_call`` records) must not leave an unlaid-out child
        # frame at (0, 0), where it would cover the first visible text block.
        widget = create_block_widget(block_data)
        if widget is None:
            return None

        container = QFrame(self._blocks_container)
        # Keep this default aligned with create_block_widget(), which treats a
        # missing type as normal text.  Otherwise the first streamed text block
        # receives a structural card border by mistake.
        is_text_block = block_data.get("type", "text") == "text"
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(0)
        self._style_block_container(container, is_text_block)

        widget.setParent(container)
        widget.height_changed.connect(self._on_block_height_changed)
        container_layout.addWidget(widget)
        self._blocks_layout.addWidget(container)
        self._block_widgets.append(widget)
        self._block_containers.append(container)
        return widget

    @staticmethod
    def _style_block_container(container: QFrame, is_text_block: bool) -> None:
        """Apply the correct frame identity, spacing and theme for one block."""
        container.setObjectName(
            "chatMessageTextBlock" if is_text_block else "chatMessageBlock"
        )
        container.setStyleSheet(
            Theme.get_chat_message_text_block_stylesheet()
            if is_text_block
            else Theme.get_chat_message_block_stylesheet()
        )
        margin = 0 if is_text_block else 6
        layout = container.layout()
        if layout is not None:
            layout.setContentsMargins(margin, margin, margin, margin)

    def _on_block_height_changed(self) -> None:
        pass

    def append_block(self, block_data: Dict[str, Any]) -> None:
        """Append a distinct block to both the widget tree and block model."""
        self._add_block_widget(block_data)
        self._blocks.append(block_data)

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

    def preferred_user_width(self, maximum_width: int) -> int:
        """Return a compact width for text-only user messages.

        Rich user input (images, audio, video, etc.) keeps the available card
        width so its preview is never unnecessarily compressed.
        """
        if self._role != "user":
            return maximum_width

        content_width = self._role_label.sizeHint().width()
        for block in self._block_widgets:
            if block.get_block_type() != "text":
                return maximum_width
            editor = getattr(block, "_content_edit", None)
            if editor is not None:
                content_width = max(
                    content_width,
                    text_editor_natural_width(editor),
                )

        margins = self._bubble_card.layout().contentsMargins() if self._bubble_card else None
        horizontal_margins = (margins.left() + margins.right()) if margins else 0
        return min(maximum_width, max(96, content_width + horizontal_margins))

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

        if block_type == "subagent_event":
            parent_id = block_data.get("parent_tool_call_id", "")
            for widget in self._block_widgets:
                if (
                    widget.get_block_type() == "tool_result"
                    and widget.get_block_id() == parent_id
                ):
                    append_event = getattr(widget, "append_execution_event", None)
                    if append_event is not None:
                        append_event(block_data)
                    return
            return

        # tool_use / tool_result: 按 id 去重，id 不匹配时始终新增，不覆盖已有块
        if block_type in ("tool_use", "tool_result"):
            if block_id:
                for widget in self._block_widgets:
                    if widget.get_block_type() == block_type and widget.get_block_id() == block_id:
                        widget.update_block_data(block_data)
                        return
            # 没有 id 或 id 没有匹配 → 新增
            self._add_block_widget(block_data)
            self._blocks.append(block_data)
            return

        # text / thinking: 更新最后一个同类型 widget（流式追加）
        if len(self._block_widgets) > 0 and self._block_widgets[-1].get_block_type() == block_type:
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
        if self._bubble_card:
            self._bubble_card.setStyleSheet(
                Theme.get_chat_message_bubble_stylesheet(self._role),
            )
        else:
            self.setStyleSheet(Theme.get_chat_message_bubble_stylesheet(self._role))
        self._role_label.setStyleSheet(Theme.get_message_role_label_stylesheet(self._role))
        for container, widget in zip(self._block_containers, self._block_widgets):
            self._style_block_container(
                container,
                widget.get_block_type() == "text",
            )
        for widget in self._block_widgets:
            widget.refresh_theme()
