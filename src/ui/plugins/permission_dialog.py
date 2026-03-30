# -*- coding: utf-8 -*-
"""
权限请求对话框模块

提供插件权限请求的UI对话框：
- PermissionRequestDialog: 权限请求确认对话框

使用方式:
    from src.ui.plugins.permission_dialog import PermissionRequestDialog

    dialog = PermissionRequestDialog(
        plugin_name="my_plugin",
        plugin_info={"version": "1.0.0", "description": "示例插件", "author": "Developer"},
        permissions={Permission.FILE_READ, Permission.NETWORK},
        parent=main_window
    )

    if dialog.exec():
        granted = dialog.get_granted_permissions()
"""

from typing import Optional, Set

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.permission_manager import Permission, PermissionSet
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)


# 权限描述映射
PERMISSION_DESCRIPTIONS = {
    Permission.FILE_READ: "读取本地文件",
    Permission.FILE_WRITE: "写入本地文件（高风险）",
    Permission.NETWORK: "访问网络",
    Permission.AGENT_TOOL: "注册Agent工具",
    Permission.AGENT_MCP: "配置MCP服务",
    Permission.AGENT_SKILL: "加载Skill包",
    Permission.AGENT_CHAT: "调用Agent对话",
    Permission.EVENT_SUBSCRIBE: "订阅事件",
    Permission.EVENT_PUBLISH: "发布事件",
    Permission.NODE_READ: "读取节点信息",
    Permission.NODE_REGISTER: "注册节点",
    Permission.STORAGE_READ: "读取持久化数据",
    Permission.STORAGE_WRITE: "写入持久化数据",
}

# 高风险权限列表
HIGH_RISK_PERMISSIONS = {
    Permission.FILE_WRITE,
    Permission.NETWORK,
}


class PermissionItem(QWidget, ThemeAwareMixin):
    """单个权限项控件（复选框 + 描述）"""

    def __init__(
        self,
        permission: Permission,
        is_high_risk: bool = False,
        checked: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._permission = permission
        self._is_high_risk = is_high_risk
        self._checked = checked
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._checkbox = QCheckBox(self._get_permission_text())
        self._checkbox.setChecked(self._checked)
        layout.addWidget(self._checkbox)

        desc_text = PERMISSION_DESCRIPTIONS.get(self._permission, self._permission.value)
        if self._is_high_risk:
            desc_text = f"⚠️ {desc_text}"

        self._desc_label = QLabel(f"    {desc_text}")
        self._desc_label.setStyleSheet(f"color: {Theme.hex('text_hint')}; font-size: 11px;")
        layout.addWidget(self._desc_label)

        if self._is_high_risk:
            self._checkbox.setStyleSheet(f"color: {Theme.hex('state_warning')};")

    def refresh_theme(self):
        desc_text = PERMISSION_DESCRIPTIONS.get(self._permission, self._permission.value)
        if self._is_high_risk:
            desc_text = f"⚠️ {desc_text}"
        self._desc_label.setText(f"    {desc_text}")
        self._desc_label.setStyleSheet(f"color: {Theme.hex('text_hint')}; font-size: 11px;")
        if self._is_high_risk:
            self._checkbox.setStyleSheet(f"color: {Theme.hex('state_warning')};")
        else:
            self._checkbox.setStyleSheet(f"color: {Theme.hex('text_primary')};")

    def _get_permission_text(self) -> str:
        """获取权限显示文本"""
        text = self._permission.value
        if self._is_high_risk:
            text = f"⚠️ {text}"
        return text

    def is_checked(self) -> bool:
        """是否被选中"""
        return self._checkbox.isChecked()

    def set_checked(self, checked: bool) -> None:
        """设置选中状态"""
        self._checkbox.setChecked(checked)

    @property
    def permission(self) -> Permission:
        """获取权限"""
        return self._permission


class PermissionRequestDialog(QDialog, ThemeAwareMixin):
    """
    权限请求对话框

    在插件首次加载或请求新权限时显示， 让用户确认授权。

    Example:
        dialog = PermissionRequestDialog(
            plugin_name="my_plugin",
            plugin_info={"version": "1.0.0", "description": "示例"},
            permissions={Permission.FILE_READ},
            parent=main_window
        )

        if dialog.exec():
            granted = dialog.get_granted_permissions()
    """

    def __init__(
        self,
        plugin_name: str,
        plugin_info: dict,
        permissions: Set[Permission],
        granted_permissions: Optional[Set[Permission]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._plugin_name = plugin_name
        self._plugin_info = plugin_info
        self._requested_permissions = permissions
        self._granted_permissions = granted_permissions or set()
        self._permission_items: list[PermissionItem] = []

        self.setWindowTitle(f"插件权限请求")
        self.setModal(True)
        self.setMinimumWidth(450)
        self._setup_ui()

        _logger.debug(
            f"权限请求对话框创建: plugin={plugin_name}, permissions={[p.value for p in permissions]}, "
            f"granted={[p.value for p in self._granted_permissions]}"
        )

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel(f'插件 "{self._plugin_name}" 请求以下权限')
        title_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {Theme.hex('text_primary')};"
        )
        layout.addWidget(title_label)

        # 插件信息
        self._info_frame = QFrame()
        self._info_frame.setStyleSheet(
            f"QFrame {{ background-color: {Theme.hex('background_secondary')}; border-radius: 4px; padding: 8px; }}"
        )
        info_layout = QVBoxLayout(self._info_frame)
        info_layout.setSpacing(4)

        version = self._plugin_info.get("version", "未知")
        author = self._plugin_info.get("author", "未知")
        description = self._plugin_info.get("description", "无描述")

        # 版本
        self._version_label = QLabel(f"版本: {version}")
        self._version_label.setStyleSheet(f"color: {Theme.hex('text_secondary')}; font-size: 12px;")
        info_layout.addWidget(self._version_label)

        # 作者
        self._author_label = QLabel(f"作者: {author}")
        self._author_label.setStyleSheet(f"color: {Theme.hex('text_secondary')}; font-size: 12px;")
        info_layout.addWidget(self._author_label)

        # 描述
        self._desc_label = QLabel(f"描述: {description}")
        self._desc_label.setStyleSheet(f"color: {Theme.hex('text_secondary')}; font-size: 12px;")
        self._desc_label.setWordWrap(True)
        info_layout.addWidget(self._desc_label)

        layout.addWidget(self._info_frame)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Theme.hex('border_primary')}; border-radius: 4px; background-color: {Theme.hex('background_secondary')}; }}"
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet(Theme.get_transparent_background_stylesheet())
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(8, 8, 8, 8)

        normal_perms = self._requested_permissions - HIGH_RISK_PERMISSIONS
        high_risk_perms = self._requested_permissions & HIGH_RISK_PERMISSIONS

        for perm in sorted(normal_perms, key=lambda p: p.value):
            is_checked = perm in self._granted_permissions
            item = PermissionItem(perm, is_high_risk=False, checked=is_checked)
            self._permission_items.append(item)
            scroll_layout.addWidget(item)

        # 高风险权限（如果有）
        if high_risk_perms:
            # 添加分隔标签
            if normal_perms:
                separator = QLabel("以下权限具有较高风险，请谨慎授权：")
                separator.setStyleSheet(
                    f"color: {Theme.hex('state_warning')}; font-size: 12px; margin-top: 8px;"
                )
                scroll_layout.addWidget(separator)

            for perm in sorted(high_risk_perms, key=lambda p: p.value):
                is_checked = perm in self._granted_permissions
                item = PermissionItem(perm, is_high_risk=True, checked=is_checked)
                self._permission_items.append(item)
                scroll_layout.addWidget(item)

        # 添加弹性空间
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # 按钮区域
        # 按钮说明：
        # - "允许全部"：选中所有权限并接受，返回所有权限
        # - "拒绝全部"：清空所有权限选择并接受，返回空权限集（清空数据库中的权限）
        # - "确定"：接受当前选中的权限
        button_box = QDialogButtonBox()
        button_box.addButton("允许全部", QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton("拒绝全部", QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton("确定", QDialogButtonBox.ButtonRole.AcceptRole)

        button_box.clicked.connect(self._on_button_clicked)

        layout.addWidget(button_box)

        # 应用样式
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())

    def refresh_theme(self):
        """刷新主题样式"""
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        # 刷新权限项样式
        for item in self._permission_items:
            item.refresh_theme()

    def _on_button_clicked(self, button) -> None:
        button_text = button.text()

        if button_text == "允许全部":
            for item in self._permission_items:
                item.set_checked(True)
            self.accept()
        elif button_text == "拒绝全部":
            for item in self._permission_items:
                item.set_checked(False)
            self.accept()
        else:  # 确定
            self.accept()

    def get_granted_permissions(self) -> Set[Permission]:
        """
        获取用户授权的权限集合

        Returns:
            用户同意授权的权限集合
        """
        granted = set()
        for item in self._permission_items:
            if item.is_checked():
                granted.add(item.permission)

        _logger.info(
            f"用户授权权限: plugin={self._plugin_name}, granted={[p.value for p in granted]}"
        )
        return granted

    def get_denied_permissions(self) -> Set[Permission]:
        """
        获取用户拒绝的权限集合

        Returns:
            用户拒绝的权限集合
        """
        denied = set()
        for item in self._permission_items:
            if not item.is_checked():
                denied.add(item.permission)

        _logger.info(
            f"用户拒绝权限: plugin={self._plugin_name}, denied={[p.value for p in denied]}"
        )
        return denied
