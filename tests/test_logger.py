# -*- coding: utf-8 -*-
"""日志模块测试"""

import logging
from pathlib import Path

import pytest

from src.utils.logger import get_logger, configure_root_logger


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


class TestConfigureRootLogger:
    """测试 configure_root_logger 函数"""

    def test_configures_root_logger(self):
        """测试配置根日志记录器"""
        configure_root_logger(logging.WARNING)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
