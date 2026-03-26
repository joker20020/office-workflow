# -*- coding: utf-8 -*-
"""
应用入口模块

启动应用程序：
1. 创建 QApplication
2. 初始化 AppContext
3. 显示主窗口
4. 处理应用退出

使用方式：
    uv run office
    或
    python -m src.main
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.core.app_context import AppContext
from src.ui.main_window import MainWindow
from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


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
    app.setApplicationName("办公小工具整合平台")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("OfficeTools")

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

    # 4. 发现并加载插件
    try:
        discovered = context.plugin_manager.discover_plugins()
        _logger.info(f"发现 {len(discovered)} 个插件: {discovered}")

        for plugin_name in discovered:
            try:
                context.plugin_manager.load_plugin(plugin_name, context)
                _logger.info(f"插件加载成功: {plugin_name}")
            except Exception as e:
                _logger.error(f"插件加载失败: {plugin_name}, 错误: {e}", exc_info=True)
    except Exception as e:
        _logger.error(f"插件发现失败: {e}", exc_info=True)

    # 5. 创建并显示主窗口
    window = MainWindow()
    window.show()
    _logger.info("主窗口显示")

    # 6. 运行事件循环
    exit_code = app.exec()

    # 7. 清理
    _logger.info("应用关闭中...")
    context.shutdown()
    _logger.info("AppContext 已关闭")

    _logger.info("=" * 50)
    _logger.info(f"应用退出 (code: {exit_code})")
    _logger.info("=" * 50)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
