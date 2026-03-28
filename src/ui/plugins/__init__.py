# -*- coding: utf-8 -*-
"""
插件管理UI模块

提供插件管理相关的UI组件：
- PermissionRequestDialog: 权限请求对话框
- PluginPanel: 插件管理面板

使用方式:
    from src.ui.plugins import PermissionRequestDialog, PluginPanel

    # 显示权限请求对话框
    dialog = PermissionRequestDialog(plugin_name, permissions, parent)
    if dialog.exec():
        granted = dialog.get_granted_permissions()

    # 显示插件管理面板
    panel = PluginPanel(plugin_manager, permission_repo, parent)
"""

from src.ui.plugins.permission_dialog import PermissionRequestDialog
from src.ui.plugins.plugin_panel import PluginPanel

__all__ = ["PermissionRequestDialog", "PluginPanel"]
