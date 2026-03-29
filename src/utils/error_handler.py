# -*- coding: utf-8 -*-
"""
全局错误处理器模块

提供应用程序级别的异常处理：
- 捕获未处理异常
- 记录崩溃日志到文件
- 显示用户友好的错误对话框

使用方式（推荐使用单例模式）：
    from src.utils.error_handler import get_error_handler, install_error_handler

    # 初始化并安装错误处理器
    handler = install_error_handler(log_dir=Path("logs/crashes"))

    # 或获取已初始化的处理器
    handler = get_error_handler()
"""

import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QMessageBox

from src.utils.logger import get_logger

_logger = get_logger(__name__)


class GlobalErrorHandler:
    """
    全局错误处理器

    捕获未处理的异常，记录崩溃日志并显示用户友好的错误对话框。

    Attributes:
        _log_dir: 崩溃日志存储目录
        _original_excepthook: 原始的 sys.excepthook
        _installed: 是否已安装
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """
        初始化错误处理器

        Args:
            log_dir: 崩溃日志存储目录，默认为 ./logs/crashes
        """
        self._log_dir = log_dir or Path("logs/crashes")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._original_excepthook = sys.excepthook
        self._installed = False

    def install(self) -> None:
        """安装全局异常处理器"""
        if not self._installed:
            self._original_excepthook = sys.excepthook
            sys.excepthook = self._handle_exception
            self._installed = True
            _logger.info("全局错误处理器已安装")

    def uninstall(self) -> None:
        """卸载全局异常处理器"""
        if self._installed:
            sys.excepthook = self._original_excepthook
            self._installed = False
            _logger.info("全局错误处理器已卸载")

    def _handle_exception(self, exc_type: type, exc_value: Exception, exc_traceback) -> None:
        """处理未捕获的异常"""
        self._log_crash(exc_type, exc_value, exc_traceback)
        self._show_error_dialog(exc_type, exc_value)
        self._original_excepthook(exc_type, exc_value, exc_traceback)

    def _log_crash(self, exc_type: type, exc_value: Exception, exc_traceback) -> None:
        """记录崩溃日志到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_file = self._log_dir / f"crash_{timestamp}.log"

        with open(crash_file, "w", encoding="utf-8") as f:
            f.write(f"Crash Report - {timestamp}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Exception Type: {exc_type.__name__}\n")
            f.write(f"Exception Value: {exc_value}\n\n")
            f.write("Traceback:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

        _logger.error(f"崩溃日志已保存: {crash_file}")

    def _show_error_dialog(self, exc_type: type, exc_value: Exception) -> None:
        """显示错误对话框"""
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("应用程序错误")
            msg.setText(f"发生未预期的错误:\n\n{exc_type.__name__}: {exc_value}")
            msg.setInformativeText("错误详情已记录到日志文件，请联系开发者获取帮助。")
            msg.exec()
        except Exception:
            # 如果对话框显示失败，静默忽略
            pass


# 全局单例实例
_global_handler: Optional[GlobalErrorHandler] = None


def get_error_handler() -> GlobalErrorHandler:
    """
    获取全局错误处理器单例

    Returns:
        GlobalErrorHandler 实例
    """
    global _global_handler
    if _global_handler is None:
        _global_handler = GlobalErrorHandler()
    return _global_handler


def install_error_handler(log_dir: Optional[Path] = None) -> GlobalErrorHandler:
    """
    安装全局错误处理器

    Args:
        log_dir: 崩溃日志存储目录

    Returns:
        已安装的 GlobalErrorHandler 实例
    """
    global _global_handler
    _global_handler = GlobalErrorHandler(log_dir)
    _global_handler.install()
    return _global_handler


def reset_error_handler_for_testing() -> None:
    """
    重置错误处理器（仅用于测试）

    卸载当前处理器并清除单例实例
    """
    global _global_handler
    if _global_handler is not None:
        _global_handler.uninstall()
        _global_handler = None
