# -*- coding: utf-8 -*-
"""
应用入口模块

启动应用程序：
1. 创建 QApplication
2. 初始化 AppContext
3. 发现插件并根据启用状态加载
4. 显示主窗口
5. 处理应用退出

使用方式：
    uv run office
    或
    python -m src.main
"""

import sys
from pathlib import Path
from typing import Set, cast

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from src.core.app_context import AppContext
from src.core.permission_manager import Permission
from src.ui.main_window import MainWindow
from src.ui.theme import Theme
from src.utils.logger import get_logger
from src.utils.error_handler import install_error_handler

_logger = get_logger(__name__)


def _create_permission_request_callback():
    """
    创建权限请求回调函数

    Returns:
        权限请求回调函数，用于在插件需要权限时显示对话框
    """
    from src.ui.plugins.permission_dialog import PermissionRequestDialog

    def on_permission_request(plugin_name: str, required_permissions: Set[Permission]) -> bool:
        """
        权限请求回调函数

        Args:
            plugin_name: 插件名称
            required_permissions: 需要授权的权限集合

        Returns:
            True 表示用户授权，False 表示用户拒绝
        """
        _logger.info(f"插件 '{plugin_name}' 请求权限: {[p.value for p in required_permissions]}")

        # 获取主窗口实例（通过 QApplication）
        app = QApplication.instance()
        main_window = None
        for widget in app.topLevelWidgets():
            if isinstance(widget, MainWindow):
                main_window = widget
                break

        if main_window is None:
            _logger.warning("未找到主窗口，自动授权")
            return True

        from src.ui.main_window import MainWindow as MW

        main_window = cast(MW, main_window)

        if main_window._app_context is None:
            _logger.warning("主窗口未初始化 AppContext，自动授权")
            return True

        # 从 PluginManager 获取插件信息
        plugin_manager = main_window._app_context.plugin_manager
        plugin_info = plugin_manager.get_plugin_info_for_permission_dialog(plugin_name)

        if plugin_info is None:
            plugin_info = {
                "version": "?.?.?",
                "description": "",
                "author": "",
            }

        # 获取当前已授权的权限（用于初始化对话框的勾选状态）
        granted_permissions = main_window._permission_repository.get_permissions(plugin_name)

        # 创建并显示权限对话框
        dialog = PermissionRequestDialog(
            plugin_name=plugin_name,
            plugin_info=plugin_info,
            permissions=required_permissions,
            granted_permissions=granted_permissions,
            parent=main_window,
        )

        if dialog.exec():
            granted = dialog.get_granted_permissions()
            if granted:
                main_window._permission_repository.grant_permissions(plugin_name, granted)
                _logger.info(f"权限已更新: {plugin_name} -> {[p.value for p in granted]}")
                return True
            else:
                main_window._permission_repository.revoke_all_permissions(plugin_name)
                _logger.info(f"已清空所有权限: {plugin_name}")
                return False
        else:
            _logger.info(f"用户取消了权限对话框: {plugin_name}")
            return False

    return on_permission_request


def _setup_emoji_font(app: QApplication) -> None:
    """配置全局字体以支持 emoji 显示。

    Linux 上 Qt 默认字体（如 Ubuntu Sans）不包含 emoji 字形，
    需要将 emoji 字体加入 font-family 回退列表。
    通过 Theme.init_emoji_font() 初始化，各组件样式表引用
    Theme.emoji_font_css() 来应用。
    """
    Theme.init_emoji_font()
    if Theme._emoji_font_family:
        _logger.info(f"已设置 emoji 字体回退: {Theme._emoji_font_family}")


def _install_linux_icon(project_root: Path) -> None:
    """安装应用图标到 Linux 图标主题目录，让任务栏/Dock 能找到。

    GNOME/KDE/Wayland 任务栏通过 desktop file 的 Icon= 字段
    在 XDG 图标主题目录中查找应用图标。
    将 PNG 图标安装到 ~/.local/share/icons/ 即可被识别。
    """
    import platform
    import shutil

    if platform.system() != "Linux":
        return

    icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor"
    app_icon_name = "OfficeWorkflow"

    # 安装各尺寸 PNG 到 hicolor 图标主题目录
    sizes = [16, 24, 32, 48, 64, 128, 256]
    installed = False
    for s in sizes:
        src = project_root / "resources" / f"logo_{s}.png"
        if not src.exists():
            continue
        dest_dir = icon_dir / f"{s}x{s}" / "apps"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{app_icon_name}.png"
        if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(src, dest)
            installed = True

    # 安装 .desktop 文件
    desktop_src = project_root / "resources" / "OfficeWorkflow.desktop"
    if desktop_src.exists():
        apps_dir = Path.home() / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        desktop_dest = apps_dir / "OfficeWorkflow.desktop"
        desktop_content = desktop_src.read_text(encoding="utf-8")
        # 替换 Exec 为实际的 python 启动命令
        desktop_content = desktop_content.replace(
            "Exec=/usr/bin/env python3 %f/main.py",
            f"Exec={shutil.which('python3') or '/usr/bin/python3'} {project_root / 'main.py'}",
        )
        desktop_content = desktop_content.replace(
            "Icon=OfficeWorkflow",
            f"Icon={app_icon_name}",
        )
        desktop_dest.write_text(desktop_content, encoding="utf-8")
        import os
        desktop_dest.chmod(0o755)
        installed = True

    if installed:
        # 刷新图标缓存
        try:
            import subprocess
            subprocess.run(["gtk-update-icon-cache", "-f",
                           str(Path.home() / ".local" / "share" / "icons" / "hicolor")],
                          capture_output=True, timeout=5)
        except Exception:
            pass
        _logger.info("Linux 图标和 desktop 文件已安装")


def main() -> int:
    """
    应用程序主入口

    Returns:
        退出码 (0 表示正常退出)
    """
    _logger.info("=" * 50)
    _logger.info("办公小工具整合平台 启动")
    _logger.info("=" * 50)

    # 1. 创建 QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("OfficeWorkflow")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("OfficeTools")
    app.setDesktopFileName("OfficeWorkflow")

    # 设置应用图标（Linux 任务栏/Dock 和 Windows 任务栏需要）
    from pathlib import Path as _P
    _project_root = _P(__file__).resolve().parent.parent
    _icon_candidates = [
        _project_root / "resources" / "logo.png",
        _project_root / "resources" / "logo.ico",
        _P("resources/logo.png"),
        _P("resources/logo.ico"),
    ]
    _app_icon = QIcon()
    for _ic in _icon_candidates:
        _icon = QIcon(str(_ic))
        if not _icon.isNull():
            _app_icon = _icon
            break
    if not _app_icon.isNull():
        app.setWindowIcon(_app_icon)
        # Linux: 安装图标到用户图标主题目录，让任务栏能找到
        _install_linux_icon(_project_root)

    # Linux 上默认字体可能不包含 emoji 字形，需要设置字体回退
    _setup_emoji_font(app)

    _logger.debug("QApplication 创建完成")

    # 2. 创建应用上下文
    data_dir = Path("data")
    plugins_dir = Path("plugins")

    context = AppContext(data_dir=data_dir, plugins_dir=plugins_dir)

    # 3. 初始化上下文
    try:
        context.initialize()
        _logger.info("AppContext 初始化完成")
    except Exception as e:
        _logger.error(f"AppContext 初始化失败: {e}", exc_info=True)
        return 1

    # 4. 发现插件
    try:
        discovered = context.plugin_manager.discover_plugins()
        _logger.info(f"发现 {len(discovered)} 个插件: {discovered}")
    except Exception as e:
        _logger.error(f"插件发现失败: {e}", exc_info=True)
        discovered = []

    # 5. 创建并显示主窗口
    window = MainWindow(engine=context.node_engine, app_context=context)
    window.show()
    _logger.info("主窗口显示")

    # 6. 加载启用的插件（静默加载,
    try:
        results = context.plugin_manager.load_enabled_plugins(
            on_permission_request=None,
        )

        success_count = sum(1 for v in results.values() if v)
        _logger.info(f"插件加载完成: {success_count}/{len(results)} 个成功")
    except Exception as e:
        _logger.error(f"插件加载失败: {e}", exc_info=True)

    # 7. 刷新插件面板数据
    window.refresh_plugin_panel()

    # 8. 运行事件循环
    exit_code = app.exec()

    # 9. 清理
    _logger.info("应用关闭中...")
    context.shutdown()
    _logger.info("AppContext 已关闭")

    _logger.info("=" * 50)
    _logger.info(f"应用退出 (code: {exit_code})")
    _logger.info("=" * 50)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
