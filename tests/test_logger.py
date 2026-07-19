# -*- coding: utf-8 -*-
"""日志模块测试"""

import logging
import threading
import time
from pathlib import Path

import pytest

from src.utils.logger import get_logger, configure_root_logger
import src.utils.logger as logger_module


class TestGetLogger:
    """测试 get_logger 函数"""

    def test_returns_logger_instance(self):
        """测试返回 Logger 实例"""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_logger_has_handlers(self):
        """测试 Logger 有处理器"""
        logger = get_logger("test.handlers")
        assert len(logger.handlers) > 0

    def test_same_name_returns_same_logger(self):
        """测试相同名称返回相同 Logger"""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        assert logger1 is logger2

    def test_logger_can_log_messages(self, tmp_path: Path):
        """测试 Logger 可以记录消息"""
        logger = get_logger(
            "test.log",
            log_to_file=True,
            log_to_console=True,
            log_dir=tmp_path,
        )

        # 记录不同级别的消息
        logger.debug("调试消息")
        logger.info("信息消息")
        logger.warning("警告消息")
        logger.error("错误消息")

        # 验证日志文件创建
        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) > 0

    def test_file_handler_blocks_until_lock_is_released(self, tmp_path: Path):
        handler = logger_module.BlockingRotatingFileHandler(
            tmp_path / "shared.log",
            maxBytes=1024,
            backupCount=1,
            encoding="utf-8",
        )
        record = logging.makeLogRecord({"levelno": logging.INFO, "msg": "after-lock"})
        worker = threading.Thread(target=handler.emit, args=(record,))

        with handler._interprocess_lock.hold():
            worker.start()
            time.sleep(0.05)
            assert worker.is_alive()

        worker.join(timeout=2)
        handler.close()

        assert not worker.is_alive()
        assert "after-lock" in (tmp_path / "shared.log").read_text(encoding="utf-8")

    def test_file_handler_retries_rollover_while_file_is_in_use(self, tmp_path: Path, monkeypatch):
        handler = logger_module.BlockingRotatingFileHandler(
            tmp_path / "shared.log",
            maxBytes=1,
            backupCount=1,
            encoding="utf-8",
        )
        attempts = 0

        def retry_once(_handler):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise PermissionError("file is in use")

        monkeypatch.setattr(logging.handlers.RotatingFileHandler, "doRollover", retry_once)

        handler.doRollover()
        handler.close()

        assert attempts == 2


class TestConfigureRootLogger:
    """测试 configure_root_logger 函数"""

    def test_configures_root_logger(self):
        """测试配置根日志记录器"""
        configure_root_logger(logging.WARNING)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
