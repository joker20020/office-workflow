# -*- coding: utf-8 -*-
"""
主题系统测试模块

测试 Theme 类的多主题支持功能。
"""

import pytest
from enum import Enum

from src.ui.theme import Theme


class TestThemeColors:
    """测试主题颜色定义"""

    REQUIRED_COLOR_KEYS = [
        "background_primary",
        "background_secondary",
        "background_tertiary",
        "background_hover",
        "background_selected",
        "border_primary",
        "border_secondary",
        "border_focus",
        "text_primary",
        "text_secondary",
        "text_disabled",
        "text_hint",
        "accent_primary",
        "accent_secondary",
        "accent_hover",
    ]

    def test_dark_theme_colors_exist(self):
        """测试暗色主题包含所有必需的颜色键"""
        for key in self.REQUIRED_COLOR_KEYS:
            assert key in Theme.DARK_COLORS, f"DARK_COLORS 缺少键: {key}"
            assert Theme.DARK_COLORS[key].startswith("#"), (
                f"DARK_COLORS[{key}] 不是有效的十六进制颜色"
            )

    def test_light_theme_colors_exist(self):
        """测试亮色主题包含所有必需的颜色键"""
        for key in self.REQUIRED_COLOR_KEYS:
            assert key in Theme.LIGHT_COLORS, f"LIGHT_COLORS 缺少键: {key}"
            assert Theme.LIGHT_COLORS[key].startswith("#"), (
                f"LIGHT_COLORS[{key}] 不是有效的十六进制颜色"
            )


class TestThemeSwitching:
    """测试主题切换功能"""

    def test_default_theme_is_dark(self):
        """测试默认主题是暗色主题"""
        from src.ui.theme import ThemeType

        assert Theme.get_current_theme() == ThemeType.DARK

    def test_set_theme_changes_colors(self):
        """测试 set_theme() 改变当前颜色"""
        from src.ui.theme import ThemeType

        # 保存原始主题
        original_theme = Theme.get_current_theme()

        try:
            # 切换到亮色主题
            Theme.set_theme(ThemeType.LIGHT)
            light_bg = Theme.hex("background_primary")

            # 切换到暗色主题
            Theme.set_theme(ThemeType.DARK)
            dark_bg = Theme.hex("background_primary")

            # 验证颜色不同
            assert light_bg != dark_bg, "亮色和暗色主题的背景色应该不同"
        finally:
            # 恢复原始主题
            Theme.set_theme(original_theme)

    def test_get_theme_returns_current(self):
        """测试 get_current_theme() 返回当前主题"""
        from src.ui.theme import ThemeType

        original_theme = Theme.get_current_theme()

        try:
            Theme.set_theme(ThemeType.LIGHT)
            assert Theme.get_current_theme() == ThemeType.LIGHT

            Theme.set_theme(ThemeType.DARK)
            assert Theme.get_current_theme() == ThemeType.DARK
        finally:
            Theme.set_theme(original_theme)

    def test_invalid_theme_raises_error(self):
        """测试无效主题名称引发 ValueError"""
        with pytest.raises(ValueError):
            Theme.set_theme("invalid_theme")


class TestThemeMethods:
    """测试主题方法"""

    def test_hex_uses_current_theme(self):
        """测试 hex() 返回当前主题的颜色"""
        from src.ui.theme import ThemeType

        original_theme = Theme.get_current_theme()

        try:
            # 暗色主题
            Theme.set_theme(ThemeType.DARK)
            dark_color = Theme.hex("background_primary")
            assert dark_color == Theme.DARK_COLORS["background_primary"]

            # 亮色主题
            Theme.set_theme(ThemeType.LIGHT)
            light_color = Theme.hex("background_primary")
            assert light_color == Theme.LIGHT_COLORS["background_primary"]
        finally:
            Theme.set_theme(original_theme)

    def test_color_returns_qcolor(self):
        """测试 color() 返回 QColor 对象"""
        from PySide6.QtGui import QColor

        color = Theme.color("background_primary")
        assert isinstance(color, QColor)

    def test_hex_returns_default_for_unknown_key(self):
        """测试 hex() 对未知键返回默认颜色"""
        result = Theme.hex("nonexistent_color")
        assert result == "#ffffff"


class TestThemeTypeEnum:
    """测试 ThemeType 枚举"""

    def test_theme_type_has_dark_and_light(self):
        """测试 ThemeType 包含 DARK 和 LIGHT 值"""
        from src.ui.theme import ThemeType

        assert hasattr(ThemeType, "DARK")
        assert hasattr(ThemeType, "LIGHT")

        # 验证是枚举类型
        assert isinstance(ThemeType.DARK, ThemeType)
        assert isinstance(ThemeType.LIGHT, ThemeType)
