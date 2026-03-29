# -*- coding: utf-8 -*-
"""
主题管理器模块

协调 ConfigManager 和 Theme，提供运行时主题切换功能，支持信号通知。

使用方式：
    from src.ui.theme_manager import ThemeManager

    # 获取单例实例
    manager = ThemeManager.instance()

    # 应用主题
    manager.apply_theme("light")

    # 切换主题
    manager.toggle_theme()

    # 连接信号
    manager.theme_changed.connect(lambda theme: print(f"主题已切换为: {theme}"))
"""

from typing import Optional

from PySide6.QtCore import QObject, Signal

from src.core.config_manager import get_config_manager
from src.ui.theme import Theme, ThemeType


class ThemeManager(QObject):
    """
    主题管理器

    协调配置管理和主题系统，提供：
    - 单例模式访问
    - 运行时主题切换
    - 主题变更信号通知
    - 配置持久化

    Attributes:
        theme_changed: 主题变更信号，参数为新主题名称
    """

    theme_changed = Signal(str)

    _instance: Optional["ThemeManager"] = None

    @classmethod
    def instance(cls) -> "ThemeManager":
        """
        获取单例实例

        Returns:
            ThemeManager 实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """
        初始化主题管理器

        从 ConfigManager 加载当前主题并应用到 Theme 类
        """
        super().__init__()
        config = get_config_manager()
        theme_name = config.get("theme", "dark")
        self._current_theme_name = theme_name
        self._apply_theme_to_class(theme_name)

    def _apply_theme_to_class(self, theme_name: str) -> None:
        """
        将主题应用到 Theme 类

        Args:
            theme_name: 主题名称 ("dark" 或 "light")
        """
        theme_type = ThemeType.DARK if theme_name == "dark" else ThemeType.LIGHT
        Theme.set_theme(theme_type)

    def apply_theme(self, theme_name: str) -> None:
        """
        应用指定主题

        更新 Theme 类、保存到配置、发射信号

        Args:
            theme_name: 主题名称 ("dark" 或 "light")
        """
        if theme_name not in self.get_available_themes():
            return

        self._current_theme_name = theme_name
        self._apply_theme_to_class(theme_name)

        config = get_config_manager()
        config.set("theme", theme_name)
        config.save()

        self.theme_changed.emit(theme_name)

    def get_current_theme_name(self) -> str:
        """
        获取当前主题名称

        Returns:
            当前主题名称 ("dark" 或 "light")
        """
        return self._current_theme_name

    def get_available_themes(self) -> list[str]:
        """
        获取可用主题列表

        Returns:
            可用主题名称列表
        """
        return ["dark", "light"]

    def toggle_theme(self) -> None:
        """
        切换到相反主题

        dark <-> light
        """
        current = self.get_current_theme_name()
        new_theme = "light" if current == "dark" else "dark"
        self.apply_theme(new_theme)


def reset_theme_manager_for_testing() -> None:
    """
    重置主题管理器单例

    用于测试隔离，确保每个测试使用独立的主题管理器实例
    """
    ThemeManager._instance = None
