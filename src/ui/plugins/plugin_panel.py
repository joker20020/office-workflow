# -*- coding: utf-8 -*-
"""
插件管理面板模块

提供插件管理界面：
- PluginItemWidget: 插件列表项控件
- PluginPanel: 插件管理面板

插件状态由启用/禁用决定，是否加载
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class PluginInstallWorker(QThread):
    """后台安装工作线程"""

    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(
        self,
        manager,
        action: str,
        repository_url: Optional[str] = None,
        branch: str = "main",
        local_path: Optional[str] = None,
        copy_mode: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._manager = manager
        self._action = action
        self._repository_url = repository_url
        self._branch = branch
        self._local_path = local_path
        self._copy_mode = copy_mode

    def run(self):
        try:
            if self._action == "install":
                result = self._manager.install_from_git(
                    self._repository_url,
                    self._branch,
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                )
                self.finished.emit(result.success, result.message)
            elif self._action == "install_local":
                if self._local_path is None:
                    self.finished.emit(False, "本地路径未设置")
                    return
                result = self._manager.install_from_local(
                    Path(self._local_path),
                    copy=self._copy_mode,
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                )
                self.finished.emit(result.success, result.message)
        except Exception as e:
            self.finished.emit(False, str(e))


class PluginInstallDialog(QDialog, ThemeAwareMixin):
    """从 Git 安装插件对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self.setWindowTitle("安装插件")
        self.setFixedSize(450, 170)
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._url_label = QLabel("Git 仓库地址:")
        layout.addWidget(self._url_label)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://github.com/user/plugin-repo")
        self._url_input.setMinimumHeight(28)
        layout.addWidget(self._url_input)

        branch_layout = QHBoxLayout()
        self._branch_label = QLabel("分支:")
        self._branch_input = QLineEdit("main")
        self._branch_input.setFixedWidth(100)
        self._branch_input.setMinimumHeight(28)
        branch_layout.addWidget(self._branch_label)
        branch_layout.addWidget(self._branch_input)
        branch_layout.addStretch()
        layout.addLayout(branch_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._install_btn = QPushButton("安装")
        self._install_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._install_btn)

        layout.addLayout(btn_layout)

    def _apply_styles(self):
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        self._url_label.setStyleSheet(f"color: {Theme.hex('text_primary')};")
        self._branch_label.setStyleSheet(f"color: {Theme.hex('text_primary')};")
        self._cancel_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        self._install_btn.setStyleSheet(Theme.get_install_button_stylesheet())

    def refresh_theme(self):
        self._apply_styles()

    def get_repository_url(self) -> str:
        return self._url_input.text().strip()

    def get_branch(self) -> str:
        return self._branch_input.text().strip() or "main"


class PluginLocalInstallDialog(QDialog, ThemeAwareMixin):
    """从本地目录安装插件对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self.setWindowTitle("从本地安装插件")
        self.setFixedSize(500, 180)
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        path_label = QLabel("本地插件目录:")
        layout.addWidget(path_label)

        path_layout = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("选择包含 __init__.py 的插件目录")
        path_layout.addWidget(self._path_input)

        self._browse_btn = QPushButton("浏览...")
        self._browse_btn.setFixedWidth(70)
        self._browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(self._browse_btn)
        layout.addLayout(path_layout)

        option_layout = QHBoxLayout()
        self._copy_radio = QCheckBox("复制到插件目录")
        self._copy_radio.setChecked(True)
        self._copy_radio.setToolTip(
            "勾选：复制文件到 plugins 目录\n不勾选：创建符号链接（开发模式推荐）"
        )
        option_layout.addWidget(self._copy_radio)
        option_layout.addStretch()
        layout.addLayout(option_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._install_btn = QPushButton("安装")
        self._install_btn.clicked.connect(self._on_install)
        btn_layout.addWidget(self._install_btn)

        layout.addLayout(btn_layout)

    def _apply_styles(self):
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        self._cancel_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        self._install_btn.setStyleSheet(Theme.get_install_button_stylesheet())

    def refresh_theme(self):
        self._apply_styles()

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择插件目录", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self._path_input.setText(folder)

    def _on_install(self) -> None:
        path = self._path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "错误", "请选择本地插件目录")
            return
        if not Path(path).exists():
            QMessageBox.warning(self, "错误", f"目录不存在: {path}")
            return
        if not (Path(path) / "__init__.py").exists():
            QMessageBox.warning(self, "错误", "所选目录不包含 __init__.py 文件")
            return
        self.accept()

    def get_local_path(self) -> str:
        return self._path_input.text().strip()

    def get_copy_mode(self) -> bool:
        return self._copy_radio.isChecked()


class PluginItemWidget(QWidget, ThemeAwareMixin):
    """插件列表项控件"""

    enabled_changed = Signal(str, bool)
    permission_edit_requested = Signal(str)
    uninstall_requested = Signal(str)

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

        self._name_label = QLabel(self._plugin_name)
        self._name_label.setStyleSheet(Theme.get_item_name_label_stylesheet())
        name_layout.addWidget(self._name_label)

        version = self._plugin_info.get("version", "?.?.?")
        self._version_label = QLabel(f"v{version}")
        self._version_label.setStyleSheet(Theme.get_item_version_label_stylesheet())
        name_layout.addWidget(self._version_label)

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
        self._desc_label = QLabel(description[:60] + ("..." if len(description) > 60 else ""))
        self._desc_label.setStyleSheet(Theme.get_item_description_label_stylesheet())
        info_layout.addWidget(self._desc_label)

        layout.addLayout(info_layout, 1)

        self._perms_btn = QPushButton("权限")
        self._perms_btn.setFixedWidth(50)
        self._perms_btn.setStyleSheet(Theme.get_item_accent_button_stylesheet())
        self._perms_btn.clicked.connect(self._on_perms_button_clicked)
        layout.addWidget(self._perms_btn)

        self._uninstall_btn = QPushButton("卸载")
        self._uninstall_btn.setFixedWidth(50)
        self._uninstall_btn.setStyleSheet(Theme.get_item_danger_button_stylesheet())
        self._uninstall_btn.clicked.connect(self._on_uninstall_clicked)
        layout.addWidget(self._uninstall_btn)

        self.setStyleSheet(Theme.get_item_widget_base_stylesheet())

    def _on_enabled_changed(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self.enabled_changed.emit(self._plugin_name, enabled)

    def _on_perms_button_clicked(self) -> None:
        self.permission_edit_requested.emit(self._plugin_name)

    def _on_uninstall_clicked(self) -> None:
        self.uninstall_requested.emit(self._plugin_name)

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
        """刷新主题样式"""
        self.setStyleSheet(Theme.get_item_widget_base_stylesheet())
        if hasattr(self, "_name_label"):
            self._name_label.setStyleSheet(Theme.get_item_name_label_stylesheet())
        if hasattr(self, "_version_label"):
            self._version_label.setStyleSheet(Theme.get_item_version_label_stylesheet())
        if hasattr(self, "_status_label"):
            status_style = (
                Theme.get_item_status_enabled_stylesheet()
                if self._is_enabled
                else Theme.get_item_status_disabled_stylesheet()
            )
            self._status_label.setStyleSheet(status_style)
        if hasattr(self, "_desc_label"):
            self._desc_label.setStyleSheet(Theme.get_item_description_label_stylesheet())
        if hasattr(self, "_perms_btn"):
            self._perms_btn.setStyleSheet(Theme.get_item_accent_button_stylesheet())
        if hasattr(self, "_uninstall_btn"):
            self._uninstall_btn.setStyleSheet(Theme.get_item_danger_button_stylesheet())


class PluginPanel(QWidget, ThemeAwareMixin):
    """插件管理面板"""

    plugin_enabled_changed = Signal(str, bool)
    permission_edit_requested = Signal(str)
    plugin_uninstall_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._plugin_widgets: dict[str, PluginItemWidget] = {}
        self._worker: Optional[PluginInstallWorker] = None
        self._plugin_manager = None

        self._setup_ui()
        self._setup_theme_awareness()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = self._create_header()
        layout.addWidget(self._header)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(Theme.get_progress_bar_stylesheet())
        self._progress_bar.setFixedHeight(3)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setVisible(False)
        self._status_label.setStyleSheet(
            f"color: {Theme.hex('accent_primary')}; padding: 4px 16px; "
            f"background-color: {Theme.hex('background_secondary')};"
        )
        layout.addWidget(self._status_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(Theme.get_scroll_area_no_border_stylesheet())

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._list_container.setStyleSheet(Theme.get_transparent_background_stylesheet())

        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        self.setStyleSheet(Theme.get_content_stack_stylesheet())

    def _create_header(self) -> QWidget:
        self._header = QFrame()
        self._header.setStyleSheet(Theme.get_header_frame_stylesheet())
        self._header.setFixedHeight(50)

        layout = QHBoxLayout(self._header)
        layout.setContentsMargins(16, 0, 16, 0)

        self._title_label = QLabel("插件管理")
        self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        layout.addWidget(self._title_label)

        layout.addStretch()

        self._install_btn = QPushButton("安装新插件")
        self._install_btn.setStyleSheet(Theme.get_install_button_stylesheet())
        self._install_btn.clicked.connect(self._on_install_clicked)
        layout.addWidget(self._install_btn)

        self._install_local_btn = QPushButton("本地安装")
        self._install_local_btn.setStyleSheet(Theme.get_primary_button_stylesheet())
        self._install_local_btn.clicked.connect(self._on_install_local_clicked)
        layout.addWidget(self._install_local_btn)

        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setFixedWidth(60)
        self._refresh_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        self._refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(self._refresh_btn)

        return self._header

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
            widget.uninstall_requested.connect(self._on_uninstall_requested)

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

    def _on_uninstall_requested(self, plugin_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "确认卸载",
            f"确定要卸载插件 {plugin_name} 吗？\n这将同时删除本地文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.plugin_uninstall_requested.emit(plugin_name)

    def set_plugin_manager(self, manager) -> None:
        self._plugin_manager = manager

    def _on_install_clicked(self) -> None:
        dialog = PluginInstallDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = dialog.get_repository_url()
            branch = dialog.get_branch()

            if not url:
                QMessageBox.warning(self, "错误", "请输入 Git 仓库地址")
                return

            self._start_install(url, branch)

    def _start_install(self, url: str, branch: str) -> None:
        if not self._plugin_manager:
            QMessageBox.warning(self, "错误", "插件管理器未初始化")
            return

        self._show_progress("正在安装插件...")

        self._worker = PluginInstallWorker(
            self._plugin_manager,
            "install",
            repository_url=url,
            branch=branch,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _on_install_local_clicked(self) -> None:
        dialog = PluginLocalInstallDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            local_path = dialog.get_local_path()
            copy_mode = dialog.get_copy_mode()

            if not local_path:
                QMessageBox.warning(self, "错误", "请选择本地插件目录")
                return

            self._start_install_local(local_path, copy_mode)

    def _start_install_local(self, local_path: str, copy_mode: bool) -> None:
        if not self._plugin_manager:
            QMessageBox.warning(self, "错误", "插件管理器未初始化")
            return

        self._show_progress("正在从本地安装插件...")

        self._worker = PluginInstallWorker(
            self._plugin_manager,
            "install_local",
            local_path=local_path,
            copy_mode=copy_mode,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _show_progress(self, status: str) -> None:
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setVisible(True)
        self._status_label.setText(status)

    def _hide_progress(self) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setVisible(False)

    def _on_progress(self, percent: int, message: str) -> None:
        self._progress_bar.setValue(percent)
        self._status_label.setText(message)

    def _on_install_finished(self, success: bool, message: str) -> None:
        self._hide_progress()

        if success:
            QMessageBox.information(self, "安装成功", message)
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "安装失败", message)

    def set_plugin_enabled(self, plugin_name: str, enabled: bool) -> None:
        if plugin_name in self._plugin_widgets:
            self._plugin_widgets[plugin_name].set_enabled(enabled)

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        self.setStyleSheet(Theme.get_content_stack_stylesheet())
        if hasattr(self, "_header"):
            self._header.setStyleSheet(Theme.get_header_frame_stylesheet())
        if hasattr(self, "_title_label"):
            self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        if hasattr(self, "_progress_bar"):
            self._progress_bar.setStyleSheet(Theme.get_progress_bar_stylesheet())
        if hasattr(self, "_status_label"):
            self._status_label.setStyleSheet(
                f"color: {Theme.hex('accent_primary')}; padding: 4px 16px; "
                f"background-color: {Theme.hex('background_secondary')};"
            )
        if hasattr(self, "_install_btn"):
            self._install_btn.setStyleSheet(Theme.get_install_button_stylesheet())
        if hasattr(self, "_install_local_btn"):
            self._install_local_btn.setStyleSheet(Theme.get_primary_button_stylesheet())
        if hasattr(self, "_scroll"):
            self._scroll.setStyleSheet(Theme.get_scroll_area_no_border_stylesheet())
        if hasattr(self, "_list_container"):
            self._list_container.setStyleSheet(Theme.get_transparent_background_stylesheet())
        for widget in self._plugin_widgets.values():
            widget.refresh_theme()
