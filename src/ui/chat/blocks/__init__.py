# -*- coding: utf-8 -*-
"""
Content block widgets for message rendering.

This package provides widgets for rendering different types of content blocks
in chat messages:
- TextBlockWidget: Plain text and markdown content
- ThinkingBlockWidget: AI reasoning/thinking content (collapsible)
- ToolUseBlockWidget: Tool/function call information
- ToolResultBlockWidget: Tool/function execution results

All block widgets inherit from BaseBlockWidget and support theme switching.
"""

from typing import Any, Dict, Optional, Union

from PySide6.QtWidgets import QWidget

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.chat.blocks.text_block import TextBlockWidget
from src.ui.chat.blocks.thinking_block import ThinkingBlockWidget
from src.ui.chat.blocks.tool_use_block import ToolUseBlockWidget
from src.ui.chat.blocks.tool_result_block import ToolResultBlockWidget

__all__ = [
    "BaseBlockWidget",
    "TextBlockWidget",
    "ThinkingBlockWidget",
    "ToolUseBlockWidget",
    "ToolResultBlockWidget",
    "create_block_widget",
]


def create_block_widget(
    block_data: Dict[str, Any],
    parent: Optional[QWidget] = None,
) -> Optional[BaseBlockWidget]:
    """
    Factory function to create the appropriate block widget for a block type.

    Args:
        block_data: The block data dictionary with a "type" field
        parent: Parent widget

    Returns:
        The appropriate block widget, or None if the block type is not supported

    Example:
        >>> block = {"type": "text", "text": "Hello"}
        >>> widget = create_block_widget(block)
        >>> isinstance(widget, TextBlockWidget)
        True
    """
    block_type = block_data.get("type", "text")

    widget_class: Optional[type] = None

    if block_type == "text":
        widget_class = TextBlockWidget
    elif block_type == "thinking":
        widget_class = ThinkingBlockWidget
    elif block_type == "tool_use":
        widget_class = ToolUseBlockWidget
    elif block_type == "tool_result":
        widget_class = ToolResultBlockWidget
    # Future block types can be added here:
    # elif block_type == "image":
    #     widget_class = ImageBlockWidget
    # elif block_type == "audio":
    #     widget_class = AudioBlockWidget
    else:
        # Unknown block type - return None or create a fallback
        return None

    return widget_class(block_data, parent)
