# -*- coding: utf-8 -*-
"""
日志配置模块

提供统一的日志配置和管理功能，支持：
- 控制台输出（开发模式）
- 文件输出（带轮转）
- 统一格式化

使用方式：
    from src.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("这是一条日志")
"""

import logging
import os
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator, Optional


# 日志格式配置
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 默认日志目录
DEFAULT_LOG_DIR = Path(os.environ.get("OFFICE_LOG_DIR", "logs"))
_LOGGER_SETUP_LOCK = threading.RLock()
_LOCAL_FILE_LOCKS: dict[str, threading.RLock] = {}
_LOCAL_FILE_LOCKS_GUARD = threading.Lock()


class _InterProcessFileLock:
    """Block competing writers until a sidecar file lock becomes available."""

    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        key = str(lock_path.resolve()).casefold()
        with _LOCAL_FILE_LOCKS_GUARD:
            self._thread_lock = _LOCAL_FILE_LOCKS.setdefault(key, threading.RLock())

    @contextmanager
    def hold(self) -> Iterator[None]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with open(self._lock_path, "a+b") as lock_file:
                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                self._acquire(lock_file)
                try:
                    yield
                finally:
                    self._release(lock_file)

    @staticmethod
    def _acquire(lock_file) -> None:
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    time.sleep(0.02)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

    @staticmethod
    def _release(lock_file) -> None:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class BlockingRotatingFileHandler(RotatingFileHandler):
    """Serialize write and rollover operations across application processes."""

    def __init__(self, filename, *args, **kwargs) -> None:
        super().__init__(filename, *args, **kwargs)
        path = Path(filename)
        self._interprocess_lock = _InterProcessFileLock(
            path.with_name(f"{path.name}.lock")
        )

    def emit(self, record: logging.LogRecord) -> None:
        with self._interprocess_lock.hold():
            super().emit(record)

    def doRollover(self) -> None:
        """Wait for external file handles before renaming the active log."""
        while True:
            try:
                super().doRollover()
                return
            except PermissionError:
                time.sleep(0.05)


def _synchronized_logger_setup(func):
    def wrapper(*args, **kwargs):
        with _LOGGER_SETUP_LOCK:
            return func(*args, **kwargs)

    return wrapper


@_synchronized_logger_setup
def get_logger(
    name: str,
    level: int = logging.DEBUG,
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_dir: Optional[Path] = None,
) -> logging.Logger:
    """
    获取配置好的Logger实例

    Args:
        name: 日志记录器名称，通常使用 __name__
        level: 日志级别，默认 DEBUG
        log_to_file: 是否输出到文件，默认 True
        log_to_console: 是否输出到控制台，默认 True
        log_dir: 日志文件目录，默认为 logs/

    Returns:
        配置好的 Logger 实例

    Example:
        logger = get_logger(__name__)
        logger.info("应用启动")
        logger.error("发生错误", exc_info=True)
    """
    logger = logging.getLogger(name)

    # 如果已有处理器，直接返回（避免重复添加）
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 控制台处理器
    if log_to_console:
        console_stream = (
            sys.stderr
            if os.environ.get("OFFICE_LOG_STREAM", "").casefold() == "stderr"
            else sys.stdout
        )
        console_handler = logging.StreamHandler(console_stream)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 文件处理器（带轮转）
    if log_to_file:
        # 确定日志目录
        target_log_dir = log_dir or DEFAULT_LOG_DIR
        target_log_dir.mkdir(parents=True, exist_ok=True)

        # 日志文件路径
        log_file = target_log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

        # 创建轮转文件处理器
        # maxBytes: 10MB, backupCount: 5
        file_handler = BlockingRotatingFileHandler(
            filename=str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # 防止日志向上传播到根记录器
    logger.propagate = False

    return logger


def configure_root_logger(level: int = logging.INFO) -> None:
    """
    配置根日志记录器

    用于设置第三方库的日志级别，避免过多的调试输出

    Args:
        level: 根日志级别

    Example:
        # 生产环境时减少第三方库的日志输出
        configure_root_logger(logging.WARNING)
    """
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )


# 模块级日志记录器（用于本模块内部日志）
_logger = get_logger(__name__)
