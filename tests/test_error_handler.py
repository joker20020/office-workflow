# -*- coding: utf-8 -*-
"""全局错误处理器测试"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from src.utils.error_handler import (
    GlobalErrorHandler,
    get_error_handler,
    install_error_handler,
    reset_error_handler_for_testing,
)


class TestGlobalErrorHandler:
    """测试全局错误处理器"""

    @pytest.fixture(autouse=True)
    def reset_handler(self):
        yield
        reset_error_handler_for_testing()

    def test_init_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "crashes"
        handler = GlobalErrorHandler(log_dir)
        assert log_dir.exists()

    def test_install_sets_excepthook(self, tmp_path):
        original_hook = sys.excepthook
        handler = GlobalErrorHandler(tmp_path / "crashes")
        handler.install()
        assert sys.excepthook == handler._handle_exception
        handler.uninstall()
        assert sys.excepthook == original_hook

    def test_log_crash_creates_file(self, tmp_path):
        log_dir = tmp_path / "crashes"
        handler = GlobalErrorHandler(log_dir)
        try:
            raise ValueError("Test error")
        except ValueError:
            handler._log_crash(ValueError, ValueError("Test error"), sys.exc_info()[2])
        crash_files = list(log_dir.glob("crash_*.log"))
        assert len(crash_files) == 1
        content = crash_files[0].read_text()
        assert "ValueError" in content
        assert "Test error" in content

    def test_singleton_pattern(self, tmp_path):
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        assert handler1 is handler2

    def test_install_error_handler(self, tmp_path):
        handler = install_error_handler(tmp_path / "crashes")
        assert handler is not None
        assert sys.excepthook == handler._handle_exception
        reset_error_handler_for_testing()
