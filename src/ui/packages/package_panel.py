# -*- coding: utf-8 -*-
"""
节点包管理面板模块

提供节点包管理界面：
- PackageItemWidget: 包列表项控件
- PackagePanel: 包管理面板

功能：
- 显示已安装的节点包列表
- 从Git URL安装新包
- 更新、启用/禁用、删除包
- 显示安装/更新进度
"""

from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from src.ui.i18n_manager import _
from src.ui.language_aware import LanguageAwareMixin
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)

def _package_status(enabled: bool) -> str:
    return _("package.enabled") if enabled else _("package.disabled")


class InstallWorker(QThread):
    """后台安装/更新工作线程"""

    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(
        self,
        manager,
        action: str,
        package_id: Optional[str] = None,
        repository_url: Optional[str] = None,
        branch: str = "main",
        local_path: Optional[str] = None,
        copy_mode: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._manager = manager
        self._action = action
        self._package_id = package_id
        self._repository_url = repository_url
        self._branch = branch
        self._local_path = local_path
        self._copy_mode = copy_mode

    def run(self):
        try:
            if self._action == "install":
                result = self._manager.install(
                    self._repository_url,
                    self._branch,
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                )
                self.finished.emit(result.success, result.message)
            elif self._action == "install_local":
                from pathlib import Path

                if self._local_path is None:
                    self.finished.emit(False, "本地路径未设置")
                    return

                result = self._manager.install_local(
                    Path(self._local_path),
                    copy=self._copy_mode,
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                )
                self.finished.emit(result.success, result.message)
            elif self._action == "update":
                result = self._manager.update(
                    self._package_id,
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                )
                self.finished.emit(result.success, result.message)
        except Exception as e:
            self.finished.emit(False, str(e))


class InstallDialog(QDialog, ThemeAwareMixin):
    """安装新包对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self.setWindowTitle(_("package.install"))
        self.setMinimumWidth(450)
        self.resize(450, 170)
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._url_label = QLabel(_("package.git_url"))
        layout.addWidget(self._url_label)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://github.com/user/node-package")
        self._url_input.setMinimumHeight(28)
        layout.addWidget(self._url_input)

        branch_layout = QHBoxLayout()
        self._branch_label = QLabel(_("package.branch"))
        self._branch_input = QLineEdit("main")
        self._branch_input.setMinimumWidth(120)
        self._branch_input.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._branch_input.setMinimumHeight(28)
        branch_layout.addWidget(self._branch_label)
        branch_layout.addWidget(self._branch_input)
        branch_layout.addStretch()
        layout.addLayout(branch_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton(_("package.cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._install_btn = QPushButton(_("package.install_btn"))
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


class LocalInstallDialog(QDialog, ThemeAwareMixin):
    """Dialog for installing packages from local directory"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self.setWindowTitle(_("package.install_local_title"))
        self.setMinimumWidth(500)
        self.resize(500, 200)
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        path_label = QLabel(_("package.local_dir"))
        layout.addWidget(path_label)

        path_layout = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText(_("package.local_dir_hint"))
        path_layout.addWidget(self._path_input)

        self._browse_btn = QPushButton(_("package.browse"))
        self._browse_btn.setMinimumWidth(80)
        self._browse_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(self._browse_btn)
        layout.addLayout(path_layout)

        option_layout = QHBoxLayout()
        self._copy_radio = QCheckBox(_("package.copy_to_packages"))
        self._copy_radio.setChecked(True)
        self._copy_radio.setToolTip(_("package.copy_tooltip"))
        option_layout.addWidget(self._copy_radio)
        option_layout.addStretch()
        layout.addLayout(option_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton(_("package.cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._install_btn = QPushButton(_("package.install_btn"))
        self._install_btn.clicked.connect(self._on_install)
        btn_layout.addWidget(self._install_btn)

        layout.addLayout(btn_layout)

    def _apply_styles(self):
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        self._install_btn.setStyleSheet(Theme.get_install_button_stylesheet())

    def refresh_theme(self):
        self._apply_styles()

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("package.choose_package_dir"), "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self._path_input.setText(folder)

    def _on_install(self) -> None:
        path = self._path_input.text().strip()
        if not path:
            QMessageBox.warning(self, _("package.error"), _("package.select_local_dir"))
            return
        from pathlib import Path

        if not Path(path).exists():
            QMessageBox.warning(self, _("package.error"), f"{_('package.dir_not_exist')}: {path}")
            return
        if not (Path(path) / "package.json").exists():
            QMessageBox.warning(self, _("package.error"), _("package.no_package_json"))
            return
        self.accept()

    def get_local_path(self) -> str:
        return self._path_input.text().strip()

    def get_copy_mode(self) -> bool:
        return self._copy_radio.isChecked()


class PackageItemWidget(QWidget, ThemeAwareMixin, LanguageAwareMixin):
    """包列表项控件"""

    enabled_changed = Signal(str, bool)
    update_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(
        self,
        package_info: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._setup_language_awareness()
        self._package_info = package_info
        self._package_id = package_info.get("id", "")
        self._is_enabled = package_info.get("enabled", True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._enabled_checkbox = QCheckBox()
        self._enabled_checkbox.setChecked(self._is_enabled)
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._enabled_checkbox)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)

        self._name_label = QLabel(self._package_info.get("name", "Unknown"))
        self._name_label.setStyleSheet(Theme.get_item_name_label_stylesheet())
        name_layout.addWidget(self._name_label)

        version = self._package_info.get("version", "?.?.?")
        self._version_label = QLabel(f"v{version}")
        self._version_label.setStyleSheet(Theme.get_item_version_label_stylesheet())
        name_layout.addWidget(self._version_label)

        self._status_label = QLabel(_package_status(self._is_enabled))
        self._status_label.setStyleSheet(
            Theme.get_item_status_enabled_stylesheet()
            if self._is_enabled
            else Theme.get_item_status_disabled_stylesheet()
        )
        name_layout.addWidget(self._status_label)

        nodes_count = len(self._package_info.get("nodes", []))
        self._nodes_label = None
        if nodes_count > 0:
            self._nodes_label = QLabel(f"{nodes_count}{_('package.nodes')}")
            self._nodes_label.setStyleSheet(
                f"color: {Theme.hex('accent_primary')}; font-size: 11px;"
            )
            name_layout.addWidget(self._nodes_label)

        name_layout.addStretch()
        info_layout.addLayout(name_layout)

        desc = self._package_info.get("description", _("package.no_description"))
        self._desc_label = QLabel(desc)
        self._desc_label.setStyleSheet(Theme.get_item_description_label_stylesheet())
        self._desc_label.setWordWrap(True)
        info_layout.addWidget(self._desc_label)

        layout.addLayout(info_layout, 1)

        self._update_btn = QPushButton(_("package.update"))
        self._update_btn.setMinimumWidth(72)
        self._update_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._update_btn.setStyleSheet(Theme.get_item_accent_button_stylesheet())
        self._update_btn.clicked.connect(self._on_update_clicked)
        layout.addWidget(self._update_btn)

        self._delete_btn = QPushButton(_("package.delete"))
        self._delete_btn.setMinimumWidth(72)
        self._delete_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._delete_btn.setStyleSheet(Theme.get_item_danger_button_stylesheet())
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self._delete_btn)

        self.setStyleSheet(Theme.get_item_widget_base_stylesheet())

    def _on_enabled_changed(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self.enabled_changed.emit(self._package_id, enabled)

    def _on_update_clicked(self) -> None:
        self.update_requested.emit(self._package_id)

    def _on_delete_clicked(self) -> None:
        self.delete_requested.emit(self._package_id)

    def set_enabled(self, enabled: bool) -> None:
        self._is_enabled = enabled
        self._enabled_checkbox.setChecked(enabled)
        self._status_label.setText(_package_status(enabled))
        self._status_label.setStyleSheet(
            Theme.get_item_status_enabled_stylesheet()
            if enabled
            else Theme.get_item_status_disabled_stylesheet()
        )

    def set_updating(self, updating: bool) -> None:
        self._update_btn.setEnabled(not updating)
        self._update_btn.setText(_("package.updating") if updating else _("package.update"))

    def refresh_language(self) -> None:
        """刷新语言文本"""
        desc = self._package_info.get("description", _("package.no_description"))
        if hasattr(self, "_desc_label"):
            self._desc_label.setText(desc)
            self._desc_label.setWordWrap(True)
        if hasattr(self, "_status_label"):
            self._status_label.setText(_package_status(self._is_enabled))
        if hasattr(self, "_update_btn"):
            self._update_btn.setText(_("package.update"))
        if hasattr(self, "_delete_btn"):
            self._delete_btn.setText(_("package.delete"))
        nodes_count = len(self._package_info.get("nodes", []))
        if hasattr(self, "_nodes_label") and self._nodes_label:
            self._nodes_label.setText(f"{nodes_count}{_('package.nodes')}")

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        self.setStyleSheet(Theme.get_item_widget_base_stylesheet())
        if hasattr(self, "_name_label"):
            self._name_label.setStyleSheet(Theme.get_item_name_label_stylesheet())
        if hasattr(self, "_version_label"):
            self._version_label.setStyleSheet(Theme.get_item_version_label_stylesheet())
        if hasattr(self, "_status_label"):
            self._status_label.setStyleSheet(
                Theme.get_item_status_enabled_stylesheet()
                if self._is_enabled
                else Theme.get_item_status_disabled_stylesheet()
            )
        if hasattr(self, "_nodes_label"):
            self._nodes_label.setStyleSheet(
                f"color: {Theme.hex('accent_primary')}; font-size: 11px;"
            )
        if hasattr(self, "_desc_label"):
            self._desc_label.setStyleSheet(Theme.get_item_description_label_stylesheet())
        if hasattr(self, "_update_btn"):
            self._update_btn.setStyleSheet(Theme.get_item_accent_button_stylesheet())
        if hasattr(self, "_delete_btn"):
            self._delete_btn.setStyleSheet(Theme.get_item_danger_button_stylesheet())

    @property
    def package_id(self) -> str:
        return self._package_id


class PackagePanel(QWidget, ThemeAwareMixin, LanguageAwareMixin):
    """节点包管理面板"""

    package_enabled_changed = Signal(str, bool)
    package_installed = Signal(str)
    package_updated = Signal(str)
    package_deleted = Signal(str)

    def __init__(
        self,
        package_manager=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._setup_language_awareness()
        self._package_manager = package_manager
        self._package_widgets: Dict[str, PackageItemWidget] = {}
        self._worker: Optional[InstallWorker] = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = self._create_header()
        layout.addWidget(header)

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

        self._title_label = QLabel(_("nav.packages"))
        self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        layout.addWidget(self._title_label)

        layout.addStretch()

        self._install_btn = QPushButton(_("package.install_new"))
        self._install_btn.setStyleSheet(Theme.get_install_button_stylesheet())
        self._install_btn.clicked.connect(self._on_install_clicked)
        layout.addWidget(self._install_btn)

        self._install_local_btn = QPushButton(_("package.install_local"))
        self._install_local_btn.setStyleSheet(Theme.get_primary_button_stylesheet())
        self._install_local_btn.clicked.connect(self._on_install_local_clicked)
        layout.addWidget(self._install_local_btn)

        self._refresh_btn = QPushButton(_("package.refresh"))
        self._refresh_btn.setMinimumWidth(80)
        self._refresh_btn.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._refresh_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        self._refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(self._refresh_btn)

        return self._header

    def set_package_manager(self, manager) -> None:
        self._package_manager = manager

    def set_packages(self, packages: List[Dict[str, Any]]) -> None:
        self._clear_list()

        for pkg_info in packages:
            widget = PackageItemWidget(pkg_info)
            widget.enabled_changed.connect(self._on_enabled_changed)
            widget.update_requested.connect(self._on_update_requested)
            widget.delete_requested.connect(self._on_delete_requested)

            self._package_widgets[pkg_info["id"]] = widget
            self._list_layout.insertWidget(self._list_layout.count() - 1, widget)

        _logger.debug(f"包列表已更新: {len(packages)} 个包")

    def _clear_list(self) -> None:
        for widget in self._package_widgets.values():
            widget.deleteLater()
        self._package_widgets.clear()

    def _on_install_clicked(self) -> None:
        dialog = InstallDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = dialog.get_repository_url()
            branch = dialog.get_branch()

            if not url:
                QMessageBox.warning(self, _("package.error"), _("package.enter_git_url"))
                return

            self._start_install(url, branch)

    def _start_install(self, url: str, branch: str) -> None:
        if not self._package_manager:
            QMessageBox.warning(self, _("package.error"), _("package.manager_not_initialized"))
            return

        self._show_progress(_("package.installing"))

        self._worker = InstallWorker(
            self._package_manager,
            "install",
            repository_url=url,
            branch=branch,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _on_install_local_clicked(self) -> None:
        dialog = LocalInstallDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            local_path = dialog.get_local_path()
            copy_mode = dialog.get_copy_mode()

            if not local_path:
                QMessageBox.warning(self, _("package.error"), _("package.select_local_dir"))
                return

            self._start_install_local(local_path, copy_mode)

    def _start_install_local(self, local_path: str, copy_mode: bool) -> None:
        if not self._package_manager:
            QMessageBox.warning(self, _("package.error"), _("package.manager_not_initialized"))
            return

        self._show_progress(_("package.installing_local"))

        self._worker = InstallWorker(
            self._package_manager,
            "install_local",
            local_path=local_path,
            copy_mode=copy_mode,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _on_update_requested(self, package_id: str) -> None:
        if not self._package_manager:
            QMessageBox.warning(self, _("package.error"), _("package.manager_not_initialized"))
            return

        if package_id in self._package_widgets:
            self._package_widgets[package_id].set_updating(True)

        self._show_progress(_("package.updating"))

        self._worker = InstallWorker(
            self._package_manager,
            "update",
            package_id=package_id,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(lambda s, m: self._on_update_finished(package_id, s, m))
        self._worker.start()

    def _on_delete_requested(self, package_id: str) -> None:
        reply = QMessageBox.question(
            self,
            _("package.confirm_delete"),
            f"{_('package.delete_message')} {package_id} ?\n{_('package.delete_warning')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._do_delete(package_id)

    def _do_delete(self, package_id: str) -> None:
        if not self._package_manager:
            QMessageBox.warning(self, _("package.error"), _("package.manager_not_initialized"))
            return

        try:
            success = self._package_manager.delete(package_id)
            if success:
                if package_id in self._package_widgets:
                    self._package_widgets[package_id].deleteLater()
                    del self._package_widgets[package_id]
                self.package_deleted.emit(package_id)
                QMessageBox.information(self, _("package.success"), f"{_('package.deleted')}: {package_id}")
            else:
                QMessageBox.warning(self, _("package.fail"), f"{_('package.delete_failed')}: {package_id}")
        except Exception as e:
            QMessageBox.critical(self, _("package.error"), f"{_('package.delete_error')}: {e}")

    def _on_enabled_changed(self, package_id: str, enabled: bool) -> None:
        if not self._package_manager:
            return

        try:
            if enabled:
                success = self._package_manager.enable(package_id)
            else:
                success = self._package_manager.disable(package_id)

            if success:
                if package_id in self._package_widgets:
                    self._package_widgets[package_id].set_enabled(enabled)
                self.package_enabled_changed.emit(package_id, enabled)
            else:
                if package_id in self._package_widgets:
                    self._package_widgets[package_id].set_enabled(not enabled)
                QMessageBox.warning(self, _("package.fail"), _("package.enable_failed") if enabled else _("package.disable_failed"))
        except Exception as e:
            QMessageBox.critical(self, _("package.error"), f"{_('package.operation_failed')}: {e}")

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
            QMessageBox.information(self, _("package.install_success"), message)
            self._on_refresh()
        else:
            QMessageBox.warning(self, _("package.install_failed"), message)

    def _on_update_finished(self, package_id: str, success: bool, message: str) -> None:
        self._hide_progress()

        if package_id in self._package_widgets:
            self._package_widgets[package_id].set_updating(False)

        if success:
            QMessageBox.information(self, _("package.update_success"), message)
            self.package_updated.emit(package_id)
        else:
            QMessageBox.warning(self, _("package.update_failed"), message)

    def _on_refresh(self) -> None:
        if self._package_manager:
            packages = self._package_manager.discover_packages()
            self.set_packages(packages)
            _logger.debug("包列表已刷新")

    def set_package_enabled(self, package_id: str, enabled: bool) -> None:
        if package_id in self._package_widgets:
            self._package_widgets[package_id].set_enabled(enabled)

    def refresh_language(self) -> None:
        """刷新语言文本"""
        if hasattr(self, "_title_label"):
            self._title_label.setText(_("nav.packages"))
        if hasattr(self, "_install_btn"):
            self._install_btn.setText(_("package.install_new"))
        if hasattr(self, "_install_local_btn"):
            self._install_local_btn.setText(_("package.install_local"))
        if hasattr(self, "_refresh_btn"):
            self._refresh_btn.setText(_("package.refresh"))
        for widget in self._package_widgets.values():
            if hasattr(widget, "refresh_language"):
                widget.refresh_language()

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
        for widget in self._package_widgets.values():
            widget.refresh_theme()
