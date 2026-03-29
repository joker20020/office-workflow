# -*- coding: utf-8 -*-
"""ConfigManager 模块测试"""

import os
import tempfile
from pathlib import Path

import pytest

from src.core.config_manager import (
    ConfigManager,
    get_config_manager,
    reset_config_manager_for_testing,
)


class TestConfigManager:
    """测试 ConfigManager 类"""

    def test_default_config_path(self):
        """测试默认配置路径是 config/settings.yaml"""
        reset_config_manager_for_testing()
        manager = ConfigManager()
        assert manager.config_path == Path("config/settings.yaml")

    def test_load_config_creates_default(self, tmp_path):
        """测试加载不存在的配置文件会创建默认配置"""
        reset_config_manager_for_testing()
        config_path = tmp_path / "config" / "settings.yaml"
        manager = ConfigManager(config_path=config_path)
        manager.load()

        # 检查默认配置值
        assert manager.get("theme") == "dark"
        # 检查文件已创建
        assert config_path.exists()

    def test_load_config_existing(self, tmp_path):
        """测试加载已存在的配置文件返回正确的值"""
        reset_config_manager_for_testing()
        config_path = tmp_path / "settings.yaml"

        # 创建一个已存在的配置文件
        config_path.write_text("theme: light\nlanguage: zh-CN\n")

        manager = ConfigManager(config_path=config_path)
        manager.load()

        assert manager.get("theme") == "light"
        assert manager.get("language") == "zh-CN"

    def test_save_config(self, tmp_path):
        """测试保存配置持久化到文件"""
        reset_config_manager_for_testing()
        config_path = tmp_path / "settings.yaml"

        manager = ConfigManager(config_path=config_path)
        manager.set("theme", "light")
        manager.set("language", "en-US")
        manager.save()

        # 重新加载验证
        manager2 = ConfigManager(config_path=config_path)
        manager2.load()
        assert manager2.get("theme") == "light"
        assert manager2.get("language") == "en-US"

    def test_get_set_value(self, tmp_path):
        """测试 get() 和 set() 方法正常工作"""
        reset_config_manager_for_testing()
        config_path = tmp_path / "settings.yaml"

        manager = ConfigManager(config_path=config_path)
        manager.load()

        # 设置值
        manager.set("theme", "light")
        assert manager.get("theme") == "light"

        # 设置新键
        manager.set("new_key", "new_value")
        assert manager.get("new_key") == "new_value"

    def test_get_default_value(self, tmp_path):
        """测试 get() 对缺失键返回默认值"""
        reset_config_manager_for_testing()
        config_path = tmp_path / "settings.yaml"

        manager = ConfigManager(config_path=config_path)
        manager.load()

        # 不存在的键返回 None
        assert manager.get("nonexistent") is None

        # 不存在的键返回指定的默认值
        assert manager.get("nonexistent", "default_value") == "default_value"

    def test_singleton_pattern(self):
        """测试 get_config_manager() 返回同一个实例"""
        reset_config_manager_for_testing()
        manager1 = get_config_manager()
        manager2 = get_config_manager()

        assert manager1 is manager2

    def test_reset_for_testing(self):
        """测试 reset_config_manager_for_testing() 重置单例"""
        manager1 = get_config_manager()
        reset_config_manager_for_testing()
        manager2 = get_config_manager()

        # 重置后应该是不同的实例
        assert manager1 is not manager2
