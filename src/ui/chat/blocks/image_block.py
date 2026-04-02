# -*- coding: utf-8 -*-
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.theme import Theme

import base64


class ImageBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "image"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._image_label: QLabel = None  # type: ignore
        self._placeholder = False
        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setScaledContents(False)
        self._image_label.setMinimumSize(200, 150)
        self._image_label.setMaximumSize(400, 300)
        self._image_label.setWordWrap(True)

        self._load_image()

        layout.addWidget(self._image_label)

    def _show_placeholder(self, text: str = "🖼 图片") -> None:
        """Show a styled placeholder when image cannot be loaded."""
        self._placeholder = True
        self._image_label.setText(text)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _load_image(self) -> None:
        source = self._block_data.get("source", {})
        source_type = source.get("type", "")

        if source_type == "url":
            self._load_from_url(source)
        elif source_type == "base64":
            self._load_from_base64(source)
        else:
            self._show_placeholder("🖼 图片 (无来源)")

    def _load_from_url(self, source: Dict[str, Any]) -> None:
        url = source.get("url", "")
        if not url:
            self._show_placeholder("🖼 图片 (路径为空)")
            return

        if url.startswith(("http://", "https://")):
            self._show_placeholder("🖼 图片 (网络)")
        else:
            pixmap = QPixmap(url)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    400,
                    300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled_pixmap)
            else:
                self._show_placeholder("🖼 图片 (无法加载)")

    def _load_from_base64(self, source: Dict[str, Any]) -> None:
        data = source.get("data", "")

        if not data:
            self._show_placeholder("🖼 图片 (无数据)")
            return

        try:
            image_data = base64.b64decode(data)
            pixmap = QPixmap()

            if pixmap.loadFromData(image_data):
                scaled_pixmap = pixmap.scaled(
                    400,
                    300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled_pixmap)
            else:
                self._show_placeholder("🖼 图片 (数据无效)")
        except Exception:
            self._show_placeholder("🖼 图片 (加载失败)")

    def _apply_styles(self) -> None:
        if self._image_label:
            bg = Theme.hex("background_secondary")
            border = Theme.hex("border_primary")
            text_color = Theme.hex("text_hint") if self._placeholder else Theme.hex("text_secondary")
            font_size = "28px" if self._placeholder else "12px"
            self._image_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 4px;
                    padding: 4px;
                    color: {text_color};
                    font-size: {font_size};
                    {Theme.emoji_font_css()}
                }}
            """)

    def get_content(self) -> str:
        return "[图片]"

    def set_content(self, content: str) -> None:
        pass

    def refresh_theme(self) -> None:
        self._apply_styles()
