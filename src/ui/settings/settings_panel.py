# -*- coding: utf-8 -*-
"""
设置面板模块

提供应用程序设置界面,包括主题切换等功能。
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.ui.theme_manager import ThemeManager


class SettingsPanel(QWidget, ThemeAwareMixin):
    """设置面板"""

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._theme_manager = theme_manager or ThemeManager.instance()
        self._setup_ui()
        self._connect_signals()
        self._load_current_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)
        title_label = QLabel("设置")
        title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        content_layout.addWidget(title_label)
        appearance_frame = self._create_appearance_group()
        content_layout.addWidget(appearance_frame)
        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _create_appearance_group(self) -> QFrame:
        self._appearance_frame = QFrame()
        self._appearance_frame.setStyleSheet(Theme.get_settings_frame_stylesheet())
        layout = QVBoxLayout(self._appearance_frame)
        layout.setSpacing(16)
        self._group_title = QLabel("外观")
        self._group_title.setStyleSheet(Theme.get_settings_group_title_stylesheet())
        layout.addWidget(self._group_title)
        theme_form = QFormLayout()
        theme_form.setSpacing(12)
        self._theme_label = QLabel("主题模式")
        self._theme_label.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("深色", "dark")
        self._theme_combo.addItem("浅色", "light")
        self._theme_combo.setStyleSheet(Theme.get_combobox_stylesheet())
        theme_form.addRow(self._theme_label, self._theme_combo)
        layout.addLayout(theme_form)
        return self._appearance_frame

    def _connect_signals(self) -> None:
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        if self._theme_manager:
            self._theme_manager.theme_changed.connect(self._on_theme_manager_changed)

    def _load_current_settings(self) -> None:
        if self._theme_manager:
            current_theme = self._theme_manager.get_current_theme_name()
            index = self._theme_combo.findData(current_theme)
            if index >= 0:
                self._theme_combo.blockSignals(True)
                self._theme_combo.setCurrentIndex(index)
                self._theme_combo.blockSignals(False)

    def _on_theme_changed(self, index: int) -> None:
        theme_name = self._theme_combo.itemData(index)
        if self._theme_manager:
            self._theme_manager.apply_theme(theme_name)

    def _on_theme_manager_changed(self, theme_name: str) -> None:
        index = self._theme_combo.findData(theme_name)
        if index >= 0 and self._theme_combo.currentIndex() != index:
            self._theme_combo.blockSignals(True)
            self._theme_combo.setCurrentIndex(index)
            self._theme_combo.blockSignals(False)

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        if hasattr(self, "_appearance_frame"):
            self._appearance_frame.setStyleSheet(Theme.get_settings_frame_stylesheet())
        if hasattr(self, "_group_title"):
            self._group_title.setStyleSheet(Theme.get_settings_group_title_stylesheet())
        if hasattr(self, "_theme_label"):
            self._theme_label.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        if hasattr(self, "_theme_combo"):
            self._theme_combo.setStyleSheet(Theme.get_combobox_stylesheet())
        if hasattr(self, "_appearance_frame"):
            self._appearance_frame.setStyleSheet(Theme.get_settings_frame_stylesheet())
        if hasattr(self, "_group_title"):
            self._group_title.setStyleSheet(Theme.get_settings_group_title_stylesheet())
        if hasattr(self, "_theme_label"):
            self._theme_label.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        if hasattr(self, "_theme_combo"):
            self._theme_combo.setStyleSheet(Theme.get_combobox_stylesheet())
