# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.chat.blocks.text_block import TextBlockWidget
from src.ui.chat.blocks.thinking_block import ThinkingBlockWidget
from src.ui.chat.blocks.tool_use_block import ToolUseBlockWidget
from src.ui.chat.blocks.tool_result_block import ToolResultBlockWidget
from src.ui.chat.blocks.image_block import ImageBlockWidget
from src.ui.chat.blocks.audio_block import AudioBlockWidget
from src.ui.chat.blocks.video_block import VideoBlockWidget

__all__ = [
    "BaseBlockWidget",
    "TextBlockWidget",
    "ThinkingBlockWidget",
    "ToolUseBlockWidget",
    "ToolResultBlockWidget",
    "ImageBlockWidget",
    "AudioBlockWidget",
    "VideoBlockWidget",
    "create_block_widget",
]


def create_block_widget(
    block_data: Dict[str, Any],
    parent: Optional[QWidget] = None,
) -> Optional[BaseBlockWidget]:
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
    elif block_type == "image":
        widget_class = ImageBlockWidget
    elif block_type == "audio":
        widget_class = AudioBlockWidget
    elif block_type == "video":
        widget_class = VideoBlockWidget
    else:
        return None

    return widget_class(block_data, parent)
