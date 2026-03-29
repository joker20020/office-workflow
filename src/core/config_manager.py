# -*- coding: utf-8 -*-
"""
配置管理器模块

提供 YAML 格式的配置文件持久化管理，支持：
- 配置的加载和保存
- 配置值的读取和设置
- 单例模式访问

使用方式：
    from src.core.config_manager import get_config_manager

    # 获取配置管理器实例
    config = get_config_manager()

    # 读取配置
    theme = config.get("theme", "dark")

    # 设置配置
    config.set("theme", "light")
    config.save()
"""

import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src.utils.logger import get_logger

_logger = get_logger(__name__)

_global_config_manager_instance: Optional["ConfigManager"] = None
_global_lock = threading.Lock()

DEFAULT_CONFIG: Dict[str, Any] = {"theme": "dark"}


def get_config_manager(config_path: Optional[Path] = None) -> "ConfigManager":
    """
    获取配置管理器单例实例

    Args:
        config_path: 可选的配置文件路径，仅在首次创建时生效

    Returns:
        ConfigManager 实例
    """
    global _global_config_manager_instance, _global_lock
    if _global_config_manager_instance is None:
        with _global_lock:
            if _global_config_manager_instance is None:
                _global_config_manager_instance = ConfigManager(config_path=config_path)
                _global_config_manager_instance.load()
    return _global_config_manager_instance


def reset_config_manager_for_testing() -> None:
    """
    重置配置管理器单例

    用于测试隔离，确保每个测试使用独立的配置管理器实例
    """
    global _global_config_manager_instance, _global_lock
    with _global_lock:
        _global_config_manager_instance = None


class ConfigManager:
    """
    配置管理器

    管理 YAML 格式的配置文件，支持：
    - 加载配置文件（不存在则创建默认配置）
    - 保存配置到文件
    - 读取和设置配置值

    Attributes:
        config_path: 配置文件路径
        _config: 配置数据字典
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径，默认为 config/settings.yaml
        """
        self.config_path = config_path or Path("config/settings.yaml")
        self._config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        _logger.debug(f"配置管理器初始化，路径: {self.config_path}")

    def load(self) -> None:
        """
        加载配置文件

        如果配置文件不存在，则创建默认配置并保存到文件
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or DEFAULT_CONFIG.copy()
                _logger.info(f"配置加载成功: {self.config_path}")
            except Exception as e:
                _logger.error(f"配置加载失败: {e}")
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()
            self._ensure_config_dir()
            self.save()
            _logger.info(f"创建默认配置文件: {self.config_path}")

    def save(self) -> None:
        """
        保存当前配置到文件
        """
        self._ensure_config_dir()
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
        _logger.info(f"配置保存成功: {self.config_path}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键名
            default: 键不存在时的默认返回值

        Returns:
            配置值，如果键不存在则返回 default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            key: 配置键名
            value: 配置值
        """
        self._config[key] = value
        _logger.debug(f"配置更新: {key} = {value}")

    def _ensure_config_dir(self) -> None:
        """
        确保配置文件目录存在
        """
        config_dir = self.config_path.parent
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            _logger.debug(f"创建配置目录: {config_dir}")
