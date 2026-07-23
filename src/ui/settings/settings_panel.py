# -*- coding: utf-8 -*-
"""
设置面板模块

提供应用程序设置界面,包括主题切换和语言切换等功能。
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

from src.ui.i18n_manager import I18nManager, _
from src.ui.language_aware import LanguageAwareMixin
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.ui.theme_manager import ThemeManager


class SettingsPanel(QWidget, ThemeAwareMixin, LanguageAwareMixin):
    """设置面板"""

    def __init__(
        self,
        theme_manager: Optional[ThemeManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._setup_language_awareness()
        self._theme_manager = theme_manager or ThemeManager.instance()
        self._i18n_manager = I18nManager.instance()
        self._setup_ui()
        self._connect_signals()
        self._load_current_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet(Theme.get_scroll_area_no_border_stylesheet())

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        self._title_label = QLabel(_("settings.title"))
        self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        content_layout.addWidget(self._title_label)

        appearance_frame = self._create_appearance_group()
        content_layout.addWidget(appearance_frame)

        language_frame = self._create_language_group()
        content_layout.addWidget(language_frame)

        content_layout.addStretch()

        self._scroll_area.setWidget(self._content_widget)
        layout.addWidget(self._scroll_area)

        # 应用整体背景样式
        self.setStyleSheet(Theme.get_content_stack_stylesheet())

    def _create_appearance_group(self) -> QFrame:
        self._appearance_frame = QFrame()
        self._appearance_frame.setStyleSheet(Theme.get_settings_frame_stylesheet())
        layout = QVBoxLayout(self._appearance_frame)
        layout.setSpacing(16)
        self._appearance_group_title = QLabel(_("settings.appearance"))
        self._appearance_group_title.setStyleSheet(Theme.get_settings_group_title_stylesheet())
        layout.addWidget(self._appearance_group_title)
        theme_form = QFormLayout()
        theme_form.setSpacing(12)
        self._theme_label = QLabel(_("settings.theme_mode"))
        self._theme_label.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        self._theme_combo = QComboBox()
        self._populate_theme_combo()
        self._theme_combo.setStyleSheet(Theme.get_combobox_stylesheet())
        theme_form.addRow(self._theme_label, self._theme_combo)
        layout.addLayout(theme_form)
        return self._appearance_frame

    def _create_language_group(self) -> QFrame:
        self._language_frame = QFrame()
        self._language_frame.setStyleSheet(Theme.get_settings_frame_stylesheet())
        layout = QVBoxLayout(self._language_frame)
        layout.setSpacing(16)
        self._language_group_title = QLabel(_("settings.language"))
        self._language_group_title.setStyleSheet(Theme.get_settings_group_title_stylesheet())
        layout.addWidget(self._language_group_title)
        language_form = QFormLayout()
        language_form.setSpacing(12)
        self._language_label = QLabel(_("settings.language_label"))
        self._language_label.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        self._language_combo = QComboBox()
        self._language_combo.addItem("中文 (简体)", "zh_CN")
        self._language_combo.addItem("English", "en")
        self._language_combo.setStyleSheet(Theme.get_combobox_stylesheet())
        language_form.addRow(self._language_label, self._language_combo)
        layout.addLayout(language_form)
        return self._language_frame

    def _connect_signals(self) -> None:
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
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

        current_language = self._i18n_manager.get_current_language()
        index = self._language_combo.findData(current_language)
        if index >= 0:
            self._language_combo.blockSignals(True)
            self._language_combo.setCurrentIndex(index)
            self._language_combo.blockSignals(False)

    def _on_theme_changed(self, index: int) -> None:
        theme_name = self._theme_combo.itemData(index)
        if self._theme_manager:
            self._theme_manager.apply_theme(theme_name)

    def _populate_theme_combo(self, current_theme: Optional[str] = None) -> None:
        """Populate the selector from the themes registered by ThemeManager."""
        if current_theme is None:
            current_theme = self._theme_combo.currentData() if hasattr(self, "_theme_combo") else None
        self._theme_combo.blockSignals(True)
        self._theme_combo.clear()
        for theme_name in self._theme_manager.get_available_themes():
            self._theme_combo.addItem(_(f"theme.{theme_name}"), theme_name)
        if current_theme:
            index = self._theme_combo.findData(current_theme)
            if index >= 0:
                self._theme_combo.setCurrentIndex(index)
        self._theme_combo.blockSignals(False)

    def _on_language_changed(self, index: int) -> None:
        language = self._language_combo.itemData(index)
        if self._i18n_manager:
            self._i18n_manager.apply_language(language)

    def _on_theme_manager_changed(self, theme_name: str) -> None:
        index = self._theme_combo.findData(theme_name)
        if index >= 0 and self._theme_combo.currentIndex() != index:
            self._theme_combo.blockSignals(True)
            self._theme_combo.setCurrentIndex(index)
            self._theme_combo.blockSignals(False)

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        self.setStyleSheet(Theme.get_content_stack_stylesheet())
        if hasattr(self, "_scroll_area"):
            self._scroll_area.setStyleSheet(Theme.get_scroll_area_no_border_stylesheet())
        if hasattr(self, "_content_widget"):
            self._content_widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        if hasattr(self, "_appearance_frame"):
            self._appearance_frame.setStyleSheet(Theme.get_settings_frame_stylesheet())
        if hasattr(self, "_appearance_group_title"):
            self._appearance_group_title.setStyleSheet(Theme.get_settings_group_title_stylesheet())
        if hasattr(self, "_language_frame"):
            self._language_frame.setStyleSheet(Theme.get_settings_frame_stylesheet())
        if hasattr(self, "_language_group_title"):
            self._language_group_title.setStyleSheet(Theme.get_settings_group_title_stylesheet())
        if hasattr(self, "_theme_label"):
            self._theme_label.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        if hasattr(self, "_language_label"):
            self._language_label.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        if hasattr(self, "_theme_combo"):
            self._theme_combo.setStyleSheet(Theme.get_combobox_stylesheet())
        if hasattr(self, "_language_combo"):
            self._language_combo.setStyleSheet(Theme.get_combobox_stylesheet())

    def refresh_language(self) -> None:
        """刷新语言文本"""
        if hasattr(self, "_title_label"):
            self._title_label.setText(_("settings.title"))
        if hasattr(self, "_appearance_group_title"):
            self._appearance_group_title.setText(_("settings.appearance"))
        if hasattr(self, "_theme_label"):
            self._theme_label.setText(_("settings.theme_mode"))
        if hasattr(self, "_language_group_title"):
            self._language_group_title.setText(_("settings.language"))
        if hasattr(self, "_language_label"):
            self._language_label.setText(_("settings.language_label"))

        # 刷新下拉框文本（需要保留当前数据）
        if hasattr(self, "_theme_combo"):
            current_theme = self._theme_combo.currentData()
            self._populate_theme_combo(current_theme)
