# -*- coding: utf-8 -*-
from abc import abstractmethod
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from src.ui.theme_aware import ThemeAwareMixin


class BaseBlockWidget(QWidget, ThemeAwareMixin):
    content_changed = Signal()
    height_changed = Signal()
    BLOCK_TYPE: str = "base"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._block_data = block_data
        self._block_id = block_data.get("id", "")
        self._setup_ui()
        self._apply_styles()

    @abstractmethod
    def _setup_ui(self) -> None:
        pass

    def _apply_styles(self) -> None:
        pass

    @abstractmethod
    def get_content(self) -> str:
        pass

    @abstractmethod
    def set_content(self, content: str) -> None:
        pass

    def get_block_data(self) -> Dict[str, Any]:
        return self._block_data.copy()

    def get_block_type(self) -> str:
        return self._block_data.get("type", self.BLOCK_TYPE)

    def get_block_id(self) -> str:
        return self._block_id

    def refresh_theme(self) -> None:
        self._apply_styles()

    def update_block_data(self, new_data: Dict[str, Any]) -> None:
        self._block_data.update(new_data)
        self.content_changed.emit()
