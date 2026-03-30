# -*- coding: utf-8 -*-
"""
插件管理面板模块

提供插件管理界面：
- PluginItemWidget: 插件列表项控件
- PluginPanel: 插件管理面板

插件状态由启用/禁用决定，是否加载
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class PluginItemWidget(QWidget, ThemeAwareMixin):
    """插件列表项控件"""

    enabled_changed = Signal(str, bool)
    permission_edit_requested = Signal(str)

    def __init__(
        self,
        plugin_name: str,
        plugin_info: dict,
        is_enabled: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._plugin_name = plugin_name
        self._plugin_info = plugin_info
        self._is_enabled = is_enabled

        self._setup_ui()
        self._setup_theme_awareness()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._enabled_checkbox = QCheckBox()
        self._enabled_checkbox.setChecked(self._is_enabled)
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._enabled_checkbox)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)

        name_label = QLabel(self._plugin_name)
        name_label.setStyleSheet(Theme.get_item_name_label_stylesheet())
        name_layout.addWidget(name_label)

        version = self._plugin_info.get("version", "?.?.?")
        version_label = QLabel(f"v{version}")
        version_label.setStyleSheet(Theme.get_item_version_label_stylesheet())
        name_layout.addWidget(version_label)

        self._status_label = QLabel("已启用" if self._is_enabled else "已禁用")
        status_style = (
            Theme.get_item_status_enabled_stylesheet()
            if self._is_enabled
            else Theme.get_item_status_disabled_stylesheet()
        )
        self._status_label.setStyleSheet(status_style)
        name_layout.addWidget(self._status_label)

        name_layout.addStretch()
        info_layout.addLayout(name_layout)

        description = self._plugin_info.get("description", "无描述")
        desc_label = QLabel(description[:60] + ("..." if len(description) > 60 else ""))
        desc_label.setStyleSheet(Theme.get_item_description_label_stylesheet())
        info_layout.addWidget(desc_label)

        layout.addLayout(info_layout, 1)

        self._perms_btn = QPushButton("权限")
        self._perms_btn.setFixedWidth(50)
        self._perms_btn.setStyleSheet(Theme.get_item_accent_button_stylesheet())
        self._perms_btn.clicked.connect(self._on_perms_button_clicked)
        layout.addWidget(self._perms_btn)

        self.setStyleSheet(Theme.get_item_widget_base_stylesheet())

    def _on_enabled_changed(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self.enabled_changed.emit(self._plugin_name, enabled)

    def _on_perms_button_clicked(self) -> None:
        self.permission_edit_requested.emit(self._plugin_name)

    def set_enabled(self, enabled: bool) -> None:
        self._is_enabled = enabled
        self._enabled_checkbox.setChecked(enabled)
        status_text = "已启用" if enabled else "已禁用"
        self._status_label.setText(status_text)
        status_style = (
            Theme.get_item_status_enabled_stylesheet()
            if enabled
            else Theme.get_item_status_disabled_stylesheet()
        )
        self._status_label.setStyleSheet(status_style)

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    def refresh_theme(self) -> None:
        self.setStyleSheet(Theme.get_item_widget_base_stylesheet())


class PluginPanel(QWidget, ThemeAwareMixin):
    """插件管理面板"""

    plugin_enabled_changed = Signal(str, bool)
    permission_edit_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._plugin_widgets: dict[str, PluginItemWidget] = {}

        self._setup_ui()
        self._setup_theme_awareness()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = self._create_header()
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(Theme.get_scroll_area_no_border_stylesheet())

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

        self.setStyleSheet(Theme.get_content_stack_stylesheet())

    def _create_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet(Theme.get_header_frame_stylesheet())
        header.setFixedHeight(50)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)

        self._title_label = QLabel("插件管理")
        self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        layout.addWidget(self._title_label)

        layout.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(refresh_btn)

        return header

    def _on_refresh(self) -> None:
        _logger.debug("用户请求刷新插件列表")
        self.refresh_requested.emit()

    def set_plugins(
        self,
        discovered: dict,
        enabled_status: dict,
        permissions: dict,
    ) -> None:
        self._clear_list()

        for name, info in discovered.items():
            is_enabled = enabled_status.get(name, True)
            perms = permissions.get(name, set())

            plugin_info = {
                "version": info.plugin_class.version if info.plugin_class else "?.?.?",
                "description": info.plugin_class.description if info.plugin_class else "",
                "author": info.plugin_class.author if info.plugin_class else "",
                "enabled": is_enabled,
                "permissions": perms,
            }

            widget = PluginItemWidget(name, plugin_info, is_enabled)
            widget.enabled_changed.connect(self._on_enabled_changed)
            widget.permission_edit_requested.connect(self._on_permission_edit_requested)

            self._plugin_widgets[name] = widget
            self._list_layout.insertWidget(self._list_layout.count() - 1, widget)

        _logger.debug(f"插件列表已更新: {len(discovered)} 个插件")

    def _clear_list(self) -> None:
        for widget in self._plugin_widgets.values():
            widget.deleteLater()
        self._plugin_widgets.clear()

    def _on_enabled_changed(self, plugin_name: str, enabled: bool) -> None:
        _logger.info(f"用户更改插件启用状态: {plugin_name} -> {enabled}")
        self.plugin_enabled_changed.emit(plugin_name, enabled)

    def _on_permission_edit_requested(self, plugin_name: str) -> None:
        _logger.info(f"用户请求修改权限: {plugin_name}")
        self.permission_edit_requested.emit(plugin_name)

    def set_plugin_enabled(self, plugin_name: str, enabled: bool) -> None:
        if plugin_name in self._plugin_widgets:
            self._plugin_widgets[plugin_name].set_enabled(enabled)

    def refresh_theme(self) -> None:
        self.setStyleSheet(Theme.get_content_stack_stylesheet())
        self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())

        for widget in self._plugin_widgets.values():
            widget.refresh_theme()
