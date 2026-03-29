# -*- coding: utf-8 -*-
"""
ThemeManager 单元测试
"""

import pytest
from PySide6.QtCore import QObject

from src.ui.theme_manager import ThemeManager, reset_theme_manager_for_testing
from src.ui.theme import Theme, ThemeType
from src.core.config_manager import reset_config_manager_for_testing


@pytest.fixture(autouse=True)
def reset_singletons():
    """每个测试前重置单例"""
    reset_theme_manager_for_testing()
    reset_config_manager_for_testing()
    yield
    reset_theme_manager_for_testing()
    reset_config_manager_for_testing()


class TestThemeManagerSingleton:
    """测试单例模式"""

    def test_singleton_pattern(self):
        """instance() 返回同一个实例"""
        instance1 = ThemeManager.instance()
        instance2 = ThemeManager.instance()
        assert instance1 is instance2


class TestThemeManagerInit:
    """测试初始化"""

    def test_initial_theme_from_config(self):
        """初始主题从配置加载"""
        manager = ThemeManager.instance()
        # 默认配置是 dark
        assert manager.get_current_theme_name() == "dark"

    def test_initial_theme_light_from_config(self, tmp_path):
        """从配置加载 light 主题"""
        # 创建一个 light 主题的配置
        import yaml

        config_path = tmp_path / "settings.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"theme": "light"}, f)

        # 重置并使用新配置
        reset_theme_manager_for_testing()
        reset_config_manager_for_testing()

        from src.core.config_manager import get_config_manager

        config = get_config_manager(config_path)

        manager = ThemeManager.instance()
        assert manager.get_current_theme_name() == "light"


class TestThemeManagerApplyTheme:
    """测试应用主题"""

    def test_apply_theme_updates_config(self, tmp_path):
        """apply_theme() 保存到配置"""
        import yaml

        config_path = tmp_path / "settings.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"theme": "dark"}, f)

        reset_theme_manager_for_testing()
        reset_config_manager_for_testing()

        from src.core.config_manager import get_config_manager

        config = get_config_manager(config_path)

        manager = ThemeManager.instance()
        manager.apply_theme("light")

        # 验证配置已更新
        assert config.get("theme") == "light"

    def test_apply_theme_emits_signal(self, qtbot):
        """apply_theme() 发射 theme_changed 信号"""
        manager = ThemeManager.instance()

        with qtbot.wait_signal(manager.theme_changed, timeout=1000) as blocker:
            manager.apply_theme("light")

        assert blocker.args == ["light"]

    def test_apply_theme_updates_theme_class(self):
        """apply_theme() 更新 Theme 类"""
        manager = ThemeManager.instance()
        manager.apply_theme("light")

        assert Theme.get_current_theme() == ThemeType.LIGHT

        manager.apply_theme("dark")
        assert Theme.get_current_theme() == ThemeType.DARK


class TestThemeManagerToggle:
    """测试主题切换"""

    def test_toggle_theme(self):
        """toggle_theme() 切换 dark <-> light"""
        manager = ThemeManager.instance()

        # 初始是 dark
        manager.apply_theme("dark")
        assert manager.get_current_theme_name() == "dark"

        # 切换到 light
        manager.toggle_theme()
        assert manager.get_current_theme_name() == "light"

        # 切换回 dark
        manager.toggle_theme()
        assert manager.get_current_theme_name() == "dark"


class TestThemeManagerAvailableThemes:
    """测试可用主题列表"""

    def test_get_available_themes(self):
        """返回可用主题列表"""
        manager = ThemeManager.instance()
        themes = manager.get_available_themes()

        assert themes == ["dark", "light"]


class TestThemeManagerReset:
    """测试重置功能"""

    def test_reset_for_testing(self):
        """reset_theme_manager_for_testing() 重置单例"""
        instance1 = ThemeManager.instance()
        reset_theme_manager_for_testing()
        instance2 = ThemeManager.instance()

        assert instance1 is not instance2
