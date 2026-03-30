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
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)


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


class InstallDialog(QDialog):
    """安装新包对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("安装节点包")
        self.setFixedSize(450, 150)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        url_label = QLabel("Git 仓库地址:")
        layout.addWidget(url_label)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://github.com/user/node-package")
        layout.addWidget(self._url_input)

        branch_layout = QHBoxLayout()
        branch_label = QLabel("分支:")
        self._branch_input = QLineEdit("main")
        self._branch_input.setFixedWidth(100)
        branch_layout.addWidget(branch_label)
        branch_layout.addWidget(self._branch_input)
        branch_layout.addStretch()
        layout.addLayout(branch_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        install_btn = QPushButton("安装")
        install_btn.clicked.connect(self.accept)
        install_btn.setStyleSheet(Theme.get_install_button_stylesheet())
        btn_layout.addWidget(install_btn)

        layout.addLayout(btn_layout)

    def get_repository_url(self) -> str:
        return self._url_input.text().strip()

    def get_branch(self) -> str:
        return self._branch_input.text().strip() or "main"


class LocalInstallDialog(QDialog):
    """Dialog for installing packages from local directory"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("从本地安装节点包")
        self.setFixedSize(500, 180)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        path_label = QLabel("本地包目录:")
        layout.addWidget(path_label)

        path_layout = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("选择包含 package.json 的目录")
        path_layout.addWidget(self._path_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        option_layout = QHBoxLayout()
        self._copy_radio = QCheckBox("复制到包目录")
        self._copy_radio.setChecked(True)
        self._copy_radio.setToolTip(
            "勾选：复制文件到 node_packages 目录\n不勾选：创建符号链接（开发模式推荐）"
        )
        option_layout.addWidget(self._copy_radio)
        option_layout.addStretch()
        layout.addLayout(option_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        install_btn = QPushButton("安装")
        install_btn.clicked.connect(self._on_install)
        install_btn.setStyleSheet(Theme.get_install_button_stylesheet())
        btn_layout.addWidget(install_btn)

        layout.addLayout(btn_layout)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择节点包目录", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self._path_input.setText(folder)

    def _on_install(self) -> None:
        path = self._path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "错误", "请选择本地包目录")
            return
        from pathlib import Path

        if not Path(path).exists():
            QMessageBox.warning(self, "错误", f"目录不存在: {path}")
            return
        if not (Path(path) / "package.json").exists():
            QMessageBox.warning(self, "错误", "所选目录不包含 package.json 文件")
            return
        self.accept()

    def get_local_path(self) -> str:
        return self._path_input.text().strip()

    def get_copy_mode(self) -> bool:
        return self._copy_radio.isChecked()


class PackageItemWidget(QWidget, ThemeAwareMixin):
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

        name_label = QLabel(self._package_info.get("name", "Unknown"))
        name_label.setStyleSheet(Theme.get_item_name_label_stylesheet())
        name_layout.addWidget(name_label)

        version = self._package_info.get("version", "?.?.?")
        version_label = QLabel(f"v{version}")
        version_label.setStyleSheet(Theme.get_item_version_label_stylesheet())
        name_layout.addWidget(version_label)

        self._status_label = QLabel("已启用" if self._is_enabled else "已禁用")
        self._status_label.setStyleSheet(
            Theme.get_item_status_enabled_stylesheet()
            if self._is_enabled
            else Theme.get_item_status_disabled_stylesheet()
        )
        name_layout.addWidget(self._status_label)

        nodes_count = len(self._package_info.get("nodes", []))
        if nodes_count > 0:
            nodes_label = QLabel(f"{nodes_count} 个节点")
            nodes_label.setStyleSheet(f"color: {Theme.hex('accent_primary')}; font-size: 11px;")
            name_layout.addWidget(nodes_label)

        name_layout.addStretch()
        info_layout.addLayout(name_layout)

        desc = self._package_info.get("description", "无描述")
        if len(desc) > 80:
            desc = desc[:77] + "..."
        desc_label = QLabel(desc)
        desc_label.setStyleSheet(Theme.get_item_description_label_stylesheet())
        info_layout.addWidget(desc_label)

        layout.addLayout(info_layout, 1)

        self._update_btn = QPushButton("更新")
        self._update_btn.setFixedWidth(50)
        self._update_btn.setStyleSheet(Theme.get_item_accent_button_stylesheet())
        self._update_btn.clicked.connect(self._on_update_clicked)
        layout.addWidget(self._update_btn)

        self._delete_btn = QPushButton("删除")
        self._delete_btn.setFixedWidth(50)
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
        status_text = "已启用" if enabled else "已禁用"
        self._status_label.setText(status_text)
        self._status_label.setStyleSheet(
            Theme.get_item_status_enabled_stylesheet()
            if enabled
            else Theme.get_item_status_disabled_stylesheet()
        )

    def set_updating(self, updating: bool) -> None:
        self._update_btn.setEnabled(not updating)
        self._update_btn.setText("更新中..." if updating else "更新")

    def refresh_theme(self) -> None:
        pass

    @property
    def package_id(self) -> str:
        return self._package_id


class PackagePanel(QWidget, ThemeAwareMixin):
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

        title = QLabel("节点包管理")
        title.setStyleSheet(Theme.get_title_label_stylesheet())
        layout.addWidget(title)

        layout.addStretch()

        install_btn = QPushButton("安装新包")
        install_btn.setStyleSheet(Theme.get_install_button_stylesheet())
        install_btn.clicked.connect(self._on_install_clicked)
        layout.addWidget(install_btn)

        install_local_btn = QPushButton("本地安装")
        install_local_btn.setStyleSheet(Theme.get_primary_button_stylesheet())
        install_local_btn.clicked.connect(self._on_install_local_clicked)
        layout.addWidget(install_local_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(refresh_btn)

        return header

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
                QMessageBox.warning(self, "错误", "请输入 Git 仓库地址")
                return

            self._start_install(url, branch)

    def _start_install(self, url: str, branch: str) -> None:
        if not self._package_manager:
            QMessageBox.warning(self, "错误", "包管理器未初始化")
            return

        self._show_progress("正在安装...")

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
                QMessageBox.warning(self, "错误", "请选择本地包目录")
                return

            self._start_install_local(local_path, copy_mode)

    def _start_install_local(self, local_path: str, copy_mode: bool) -> None:
        if not self._package_manager:
            QMessageBox.warning(self, "错误", "包管理器未初始化")
            return

        self._show_progress("正在从本地安装...")

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
            QMessageBox.warning(self, "错误", "包管理器未初始化")
            return

        if package_id in self._package_widgets:
            self._package_widgets[package_id].set_updating(True)

        self._show_progress("正在更新...")

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
            "确认删除",
            f"确定要删除包 {package_id} 吗？\n这将同时删除本地文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._do_delete(package_id)

    def _do_delete(self, package_id: str) -> None:
        if not self._package_manager:
            QMessageBox.warning(self, "错误", "包管理器未初始化")
            return

        try:
            success = self._package_manager.delete(package_id)
            if success:
                if package_id in self._package_widgets:
                    self._package_widgets[package_id].deleteLater()
                    del self._package_widgets[package_id]
                self.package_deleted.emit(package_id)
                QMessageBox.information(self, "成功", f"包 {package_id} 已删除")
            else:
                QMessageBox.warning(self, "失败", f"删除包 {package_id} 失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败: {e}")

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
                QMessageBox.warning(self, "失败", f"无法{'启用' if enabled else '禁用'}包")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败: {e}")

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
            self._on_refresh()
        else:
            QMessageBox.warning(self, "安装失败", message)

    def _on_update_finished(self, package_id: str, success: bool, message: str) -> None:
        self._hide_progress()

        if package_id in self._package_widgets:
            self._package_widgets[package_id].set_updating(False)

        if success:
            QMessageBox.information(self, "更新成功", message)
            self.package_updated.emit(package_id)
        else:
            QMessageBox.warning(self, "更新失败", message)

    def _on_refresh(self) -> None:
        if self._package_manager:
            packages = self._package_manager.discover_packages()
            self.set_packages(packages)
            _logger.debug("包列表已刷新")

    def set_package_enabled(self, package_id: str, enabled: bool) -> None:
        if package_id in self._package_widgets:
            self._package_widgets[package_id].set_enabled(enabled)

    def refresh_theme(self) -> None:
        self.setStyleSheet(Theme.get_content_stack_stylesheet())
        for widget in self._package_widgets.values():
            widget.refresh_theme()
