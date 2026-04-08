# -*- coding: utf-8 -*-
"""
主题配置模块

集中管理所有UI组件的颜色常量和QSS样式，支持暗色和亮色主题切换。

使用方式：
    from src.ui.theme import Theme, ThemeType

    # 切换主题
    Theme.set_theme(ThemeType.LIGHT)

    # 获取颜色
    color = Theme.hex('background_primary')

    # 获取样式表
    stylesheet = Theme.get_toolbar_stylesheet()
"""

from enum import Enum
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication


class ThemeType(Enum):
    """主题类型枚举"""

    DARK = "dark"
    LIGHT = "light"


class Theme:
    """
    暗色主题配置类

    提供统一的颜色常量和样式表定义。
    所有UI组件应使用此处的颜色，确保视觉一致性。
    """

    # Emoji 字体回退（用于包含 emoji 图标的组件样式）
    _emoji_font_family: str = ""

    # ==================== 颜色常量 ====================

    DARK_COLORS = {
        "background_primary": "#18181b",
        "background_secondary": "#1e1e24",
        "background_tertiary": "#2a2a35",
        "background_hover": "#2e2e3a",
        "background_selected": "#35354a",
        "background_pressed": "#40405a",
        "background_input": "#22222c",
        "border_primary": "#2e2e3a",
        "border_secondary": "#3d3d50",
        "border_focus": "#6366f1",
        "border_hover": "#36364a",
        "text_primary": "#f0f0f5",
        "text_secondary": "#a0a0b8",
        "text_disabled": "#55556a",
        "text_hint": "#707088",
        "text_placeholder": "#606078",
        "text_link": "#818cf8",
        "accent_primary": "#818cf8",
        "accent_secondary": "#6366f1",
        "accent_hover": "#a5b4fc",
        "state_idle": "#4a4a60",
        "state_running": "#fbbf24",
        "state_success": "#34d399",
        "state_error": "#f87171",
        "state_warning": "#fbbf24",
        "grid_minor": "#1e1e26",
        "grid_major": "#252530",
        "grid_background": "#131318",
        "node_bg_idle": "#1e1e28",
        "node_bg_running": "#2a2800",
        "node_bg_success": "#0a2a1a",
        "node_bg_error": "#2a0a0a",
        "node_bg_skipped": "#252530",
        "node_border_normal": "#2a2a38",
        "node_border_hover": "#35354a",
        "node_title": "#eeeef5",
        "node_port_name": "#9898b0",
        # Button state colors
        "accent_hover_bg": "#4f46e5",
        "accent_pressed_bg": "#4338ca",
        "danger_hover_bg": "#dc2626",
        "danger_pressed_bg": "#b91c1c",
        "success_hover_bg": "#059669",
        "success_pressed_bg": "#047857",
        # Block card colors
        "card_background": "#1a1a24",
        "card_border": "#2a2a38",
        "card_header_hover": "#22222e",
        "thinking_accent": "#fbbf24",
        "tool_accent": "#818cf8",
        "success_accent": "#34d399",
        "error_accent": "#f87171",
    }

    LIGHT_COLORS = {
        "background_primary": "#fafafa",
        "background_secondary": "#ffffff",
        "background_tertiary": "#f0f0f5",
        "background_hover": "#eeeef5",
        "background_selected": "#e0e0f0",
        "background_pressed": "#d0d0e0",
        "background_input": "#ffffff",
        "border_primary": "#e0e0ea",
        "border_secondary": "#d0d0da",
        "border_focus": "#6366f1",
        "border_hover": "#d0d0da",
        "text_primary": "#111122",
        "text_secondary": "#555570",
        "text_disabled": "#9999aa",
        "text_hint": "#8888a0",
        "text_placeholder": "#aaaabc",
        "text_link": "#6366f1",
        "accent_primary": "#6366f1",
        "accent_secondary": "#818cf8",
        "accent_hover": "#a5b4fc",
        "state_idle": "#8888a0",
        "state_running": "#f59e0b",
        "state_success": "#10b981",
        "state_error": "#ef4444",
        "state_warning": "#f59e0b",
        "grid_minor": "#f0f0f5",
        "grid_major": "#e0e0ea",
        "grid_background": "#fafafe",
        "node_bg_idle": "#ffffff",
        "node_bg_running": "#fffbeb",
        "node_bg_success": "#ecfdf5",
        "node_bg_error": "#fef2f2",
        "node_bg_skipped": "#f0f0f5",
        "node_border_normal": "#e0e0ea",
        "node_border_hover": "#d0d0da",
        "node_title": "#111122",
        "node_port_name": "#555570",
        "accent_hover_bg": "#4f46e5",
        "accent_pressed_bg": "#4338ca",
        "danger_hover_bg": "#dc2626",
        "danger_pressed_bg": "#b91c1c",
        "success_hover_bg": "#059669",
        "success_pressed_bg": "#047857",
        # Block card colors
        "card_background": "#ffffff",
        "card_border": "#e0e0ea",
        "card_header_hover": "#f0f0f5",
        "thinking_accent": "#f59e0b",
        "tool_accent": "#6366f1",
        "success_accent": "#10b981",
        "error_accent": "#ef4444",
    }

    _current_theme: ThemeType = ThemeType.DARK
    _QCOLORS: dict = {}

    @classmethod
    def _get_colors(cls) -> dict:
        """获取当前主题的颜色字典"""
        if cls._current_theme == ThemeType.DARK:
            return cls.DARK_COLORS
        return cls.LIGHT_COLORS

    @classmethod
    def init_emoji_font(cls) -> None:
        """初始化 emoji 字体回退字符串，供包含 emoji 的组件样式使用。

        应在 QApplication 创建后调用一次。
        """
        import platform
        if platform.system() != "Linux":
            return
        app = QApplication.instance()
        if app is None:
            return
        default_family = app.font().family()
        candidates = ["Noto Color Emoji", "Emoji One", "Twemoji Mozilla", "Segoe UI Emoji"]
        available = [default_family]
        try:
            from PySide6.QtGui import QFontDatabase
            db = QFontDatabase
            for c in candidates:
                if db.families().__contains__(c):
                    available.append(c)
        except Exception:
            available.append("Noto Color Emoji")
        cls._emoji_font_family = ", ".join(f'"{f}"' for f in available)

    @classmethod
    def emoji_font_css(cls) -> str:
        """返回用于 QSS 的 font-family 声明（含 emoji 回退）。

        在样式表中使用: font-family: {Theme.emoji_font_css()};
        如果尚未初始化或非 Linux，返回空字符串。
        """
        if cls._emoji_font_family:
            return f"font-family: {cls._emoji_font_family};"
        return ""

    @classmethod
    def apply_emoji_to_font(cls, font: QFont) -> None:
        """将 emoji 字体回退应用到一个 QFont 对象上（用于 QPainter 绘制 emoji）。

        Args:
            font: 要修改的 QFont 对象
        """
        if not cls._emoji_font_family:
            return
        families = [f.strip('" ') for f in cls._emoji_font_family.split(",")]
        if len(families) >= 2:
            font.setFamily(families[0])
            for sub in families[1:]:
                font.insertSubstitution(families[0], sub)

    @classmethod
    def set_theme(cls, theme: ThemeType) -> None:
        """
        设置当前主题

        Args:
            theme: 主题类型（ThemeType.DARK 或 ThemeType.LIGHT）

        Raises:
            ValueError: 当传入无效的主题类型时
        """
        if not isinstance(theme, ThemeType):
            raise ValueError(f"无效的主题类型: {theme}，必须是 ThemeType.DARK 或 ThemeType.LIGHT")
        cls._current_theme = theme
        cls._QCOLORS.clear()
        # Update class-level QColor constants to match current theme
        cls._update_color_attributes()

    @classmethod
    def get_current_theme(cls) -> ThemeType:
        """获取当前主题类型"""
        return cls._current_theme

    @classmethod
    def color(cls, name: str) -> QColor:
        """
        获取 QColor 对象

        Args:
            name: 颜色名称（如 'background_primary'）

        Returns:
            QColor 对象
        """
        cache_key = f"{cls._current_theme.value}_{name}"
        if cache_key not in cls._QCOLORS:
            hex_color = cls._get_colors().get(name, "#ffffff")
            cls._QCOLORS[cache_key] = QColor(hex_color)
        return cls._QCOLORS[cache_key]

    @classmethod
    def hex(cls, name: str) -> str:
        """
        获取十六进制颜色字符串

        Args:
            name: 颜色名称

        Returns:
            十六进制颜色字符串（如 '#2d2d2d'）
        """
        return cls._get_colors().get(name, "#ffffff")

    # ==================== 样式表 ====================

    @classmethod
    def get_main_window_stylesheet(cls) -> str:
        """获取主窗口样式表（包含状态栏）"""
        return f"""
            QMainWindow {{
                background-color: {cls.hex("background_primary")};
            }}
            QStatusBar {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_secondary")};
                border-top: 1px solid {cls.hex("border_primary")};
            }}
            QStatusBar::item {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_secondary")};
            }}
        """

    @classmethod
    def get_status_bar_stylesheet(cls) -> str:
        """获取状态栏样式表"""
        return f"""
            QStatusBar {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_secondary")};
                border-top: 1px solid {cls.hex("border_primary")};
            }}
            QStatusBar::item {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_secondary")};
            }}
        """

    @classmethod
    def get_content_stack_stylesheet(cls) -> str:
        """获取内容区域样式表"""
        return f"""
            QStackedWidget {{
                background-color: {cls.hex("background_primary")};
            }}
        """

    @classmethod
    def get_navigation_rail_stylesheet(cls) -> str:
        """获取导航栏样式表"""
        return f"""
            NavigationRail {{
                background-color: {cls.hex("background_secondary")};
                border-right: 1px solid {cls.hex("border_primary")};
            }}
        """

    @classmethod
    def get_navigation_rail_container_stylesheet(cls) -> str:
        """获取导航栏容器样式表"""
        return f"""
            QWidget {{
                background-color: {cls.hex("background_secondary")};
            }}
        """

    @classmethod
    def get_nav_item_stylesheet(cls, selected: bool = False) -> str:
        """
        获取导航项样式表

        Args:
            selected: 是否选中状态
        """
        if selected:
            bg_color = cls.hex("background_selected")
            hover_color = cls.hex("background_pressed")
        else:
            bg_color = "transparent"
            hover_color = cls.hex("background_hover")

        text_color = cls.hex("text_primary") if selected else cls.hex("text_secondary")
        hover_text_color = cls.hex("text_primary")

        # 选中时左侧显示强调色指示条
        indicator = f"2px solid {cls.hex('border_focus')}" if selected else "2px solid transparent"

        return f"""
            NavItem {{
                background-color: {bg_color};
                border: none;
                border-left: {indicator};
                border-radius: 0 6px 6px 0;
                text-align: left;
                margin: 1px 8px 1px 0;
            }}
            NavItem:hover {{
                background-color: {hover_color};
            }}
            NavItem QLabel {{
                color: {text_color};
                background-color: transparent;
            }}
            NavItem:hover QLabel {{
                color: {hover_text_color};
                background-color: transparent;
            }}
            QToolTip {{
                background-color: {cls.hex("background_pressed")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_secondary")};
                padding: 6px 10px;
                border-radius: 6px;
            }}
        """

    @classmethod
    def get_toolbar_stylesheet(cls) -> str:
        """获取工具栏样式表"""
        return f"""
            QToolBar {{
                background-color: {cls.hex("background_secondary")};
                border-bottom: 1px solid {cls.hex("border_primary")};
                padding: 6px 8px;
                spacing: 6px;
            }}
            QToolButton {{
                padding: 6px 14px;
                border: none;
                border-radius: 6px;
                background-color: transparent;
                color: {cls.hex("text_primary")};
                {cls.emoji_font_css()}
            }}
            QToolButton:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QToolButton:pressed {{
                background-color: {cls.hex("background_pressed")};
            }}
            QToolBar::separator {{
                margin: 0;
                border-image: none;
            }}
            QToolTip {{
                background-color: {cls.hex("background_pressed")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_secondary")};
                padding: 6px 10px;
                border-radius: 6px;
            }}
        """

    @classmethod
    def get_node_panel_title_stylesheet(cls) -> str:
        """获取节点面板标题样式表"""
        return f"""
            QLabel {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
                padding: 10px 12px;
                font-weight: bold;
                font-size: 12px;
                border-bottom: 1px solid {cls.hex("border_secondary")};
            }}
        """

    @classmethod
    def get_node_tree_stylesheet(cls) -> str:
        """获取节点树样式表"""
        return f"""
            QTreeWidget {{
                border: none;
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                outline: none;
                {cls.emoji_font_css()}
            }}
            QTreeWidget::item {{
                padding: 6px 4px;
                color: {cls.hex("text_primary")};
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QTreeWidget::item:selected {{
                background-color: {cls.hex("background_selected")};
                color: {cls.hex("text_primary")};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {cls.hex("background_secondary")};
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cls.hex("background_tertiary")};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.hex("background_selected")};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background-color: {cls.hex("background_secondary")};
                height: 8px;
                margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {cls.hex("background_tertiary")};
                border-radius: 4px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {cls.hex("background_selected")};
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            QToolTip {{
                background-color: {cls.hex("background_pressed")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_secondary")};
                padding: 4px 8px;
                border-radius: 4px;
            }}
        """

    @classmethod
    def get_status_label_stylesheet(cls) -> str:
        """获取状态标签样式表"""
        return f"color: {cls.hex('text_hint')}; padding-left: 12px; font-size: 12px;"

    @classmethod
    def get_hint_label_stylesheet(cls) -> str:
        """获取提示标签样式表"""
        return f"color: {cls.hex('text_hint')}; padding: 10px; font-size: 11px;"

    @classmethod
    def get_title_label_stylesheet(cls) -> str:
        """获取标题标签样式表"""
        return f"""
            font-size: 16px;
            font-weight: bold;
            color: {cls.hex("accent_primary")};
            padding: 8px 8px 8px 4px;
            letter-spacing: 0.5px;
        """

    @classmethod
    def get_separator_stylesheet(cls) -> str:
        """获取分隔线样式表"""
        return f"background-color: {cls.hex('border_primary')};"

    @classmethod
    def get_welcome_page_stylesheet(cls) -> str:
        """获取欢迎页面样式表（兼容旧代码）"""
        return cls.get_home_page_stylesheet()

    @classmethod
    def get_home_page_stylesheet(cls) -> str:
        """获取首页样式表"""
        return f"""
            HomePage {{
                background-color: {cls.hex("background_primary")};
            }}
        """

    @classmethod
    def get_home_header_stylesheet(cls) -> str:
        """获取首页头部样式表"""
        return f"""
            QFrame#homeHeader {{
                background-color: {cls.hex("background_secondary")};
                border-bottom: 1px solid {cls.hex("border_primary")};
                border-radius: 0;
                padding: 40px 48px;
            }}
        """

    @classmethod
    def get_home_title_stylesheet(cls) -> str:
        """获取首页标题样式表"""
        return f"""
            QLabel#homeTitle {{
                color: {cls.hex("text_primary")};
                font-size: 28px;
                font-weight: bold;
                background-color: transparent;
                letter-spacing: -0.5px;
            }}
        """

    @classmethod
    def get_home_subtitle_stylesheet(cls) -> str:
        """获取首页副标题样式表"""
        return f"""
            QLabel#homeSubtitle {{
                color: {cls.hex("text_secondary")};
                font-size: 14px;
                background-color: transparent;
                margin-top: 6px;
            }}
        """

    @classmethod
    def get_home_section_title_stylesheet(cls) -> str:
        """获取首页区块标题样式表"""
        return f"""
            QLabel#sectionTitle {{
                color: {cls.hex("text_primary")};
                font-size: 15px;
                font-weight: bold;
                background-color: transparent;
                padding: 20px 0 8px 0;
                letter-spacing: 0.3px;
            }}
        """

    @classmethod
    def get_quick_action_card_stylesheet(cls, is_hover: bool = False) -> str:
        """获取快速操作卡片样式表"""
        bg = cls.hex("background_hover") if is_hover else cls.hex("background_secondary")
        border = cls.hex("border_focus") if is_hover else cls.hex("border_primary")
        return f"""
            QFrame#quickActionCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 20px;
            }}
            QFrame#quickActionCard:hover {{
                background-color: {cls.hex("background_hover")};
                border-color: {cls.hex("border_focus")};
            }}
        """

    @classmethod
    def get_quick_action_icon_stylesheet(cls) -> str:
        """获取快速操作图标样式表"""
        return f"""
            QLabel#quickActionIcon {{
                font-size: 32px;
                background-color: transparent;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_quick_action_title_stylesheet(cls) -> str:
        """获取快速操作标题样式表"""
        return f"""
            QLabel#quickActionTitle {{
                color: {cls.hex("text_primary")};
                font-size: 16px;
                font-weight: bold;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_quick_action_desc_stylesheet(cls) -> str:
        """获取快速操作描述样式表"""
        return f"""
            QLabel#quickActionDesc {{
                color: {cls.hex("text_secondary")};
                font-size: 12px;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_recent_item_stylesheet(cls, is_hover: bool = False) -> str:
        """获取最近工作流项样式表"""
        bg = cls.hex("background_hover") if is_hover else cls.hex("background_secondary")
        return f"""
            QFrame#recentItem {{
                background-color: {bg};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 8px;
                padding: 12px 16px;
            }}
            QFrame#recentItem:hover {{
                background-color: {cls.hex("background_hover")};
                border-color: {cls.hex("border_hover")};
            }}
        """

    @classmethod
    def get_recent_item_title_stylesheet(cls) -> str:
        """获取最近工作流标题样式表"""
        return f"""
            QLabel#recentItemTitle {{
                color: {cls.hex("text_primary")};
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_recent_item_meta_stylesheet(cls) -> str:
        """获取最近工作流元信息样式表"""
        return f"""
            QLabel#recentItemMeta {{
                color: {cls.hex("text_hint")};
                font-size: 11px;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_empty_state_stylesheet(cls) -> str:
        """获取空状态样式表"""
        return f"""
            QLabel#emptyState {{
                color: {cls.hex("text_hint")};
                font-size: 14px;
                padding: 40px;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_footer_stylesheet(cls) -> str:
        """获取页脚样式表"""
        return f"""
            QFrame#homeFooter {{
                background-color: {cls.hex("background_secondary")};
                border-top: 1px solid {cls.hex("border_primary")};
                padding: 12px 24px;
            }}
        """

    @classmethod
    def get_footer_status_stylesheet(cls) -> str:
        """获取页脚状态样式表"""
        return f"""
            QLabel#footerStatus {{
                color: {cls.hex("text_hint")};
                font-size: 12px;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_chat_panel_stylesheet(cls) -> str:
        """获取对话面板样式表"""
        return f"""
            ChatPanel {{
                background-color: {cls.hex("background_primary")};
            }}
        """

    @classmethod
    def get_chat_scroll_area_stylesheet(cls) -> str:
        """获取对话滚动区域样式表"""
        return f"""
            QScrollArea {{
                border: none;
                background-color: {cls.hex("background_primary")};
            }}
            QScrollBar:vertical {{
                background-color: {cls.hex("background_secondary")};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cls.hex("background_tertiary")};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.hex("background_selected")};
            }}
        """

    @classmethod
    def get_message_role_label_stylesheet(cls, role: str) -> str:
        """获取消息角色标签样式表"""
        color = cls.hex("accent_primary") if role == "user" else "#81C784"
        return f"""
            QLabel {{
                color: {color};
                font-size: 11px;
                font-weight: bold;
            }}
        """

    @classmethod
    def get_chat_input_stylesheet(cls) -> str:
        """获取对话输入框样式表"""
        return f"""
            QTextEdit {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
                {cls.emoji_font_css()}
            }}
            QTextEdit:focus {{
                border: 1px solid {cls.hex("border_focus")};
            }}
        """

    @classmethod
    def get_chat_send_button_stylesheet(cls) -> str:
        """获取对话发送按钮样式表"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("border_focus")};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
                {cls.emoji_font_css()}
            }}
            QPushButton:hover {{
                background-color: {cls.hex("accent_hover_bg")};
            }}
            QPushButton:disabled {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_disabled")};
            }}
        """

    @classmethod
    def get_chat_stop_button_stylesheet(cls) -> str:
        """获取对话停止按钮样式表"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("state_error")};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
                {cls.emoji_font_css()}
            }}
            QPushButton:hover {{
                background-color: {cls.hex("danger_hover_bg")};
            }}
            QPushButton:disabled {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_secondary")};
            }}
        """

    @classmethod
    def get_chat_clear_button_stylesheet(cls) -> str:
        """获取对话清空按钮样式表"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                {cls.emoji_font_css()}
            }}
            QPushButton:hover {{
                background-color: {cls.hex("background_selected")};
            }}
        """

    @classmethod
    def get_chat_title_label_stylesheet(cls) -> str:
        """获取对话标题标签样式表"""
        return f"""
            QLabel {{
                color: {cls.hex("accent_primary")};
                font-size: 16px;
                font-weight: bold;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_chat_status_label_stylesheet(cls) -> str:
        """获取对话状态标签样式表"""
        return f"""
            QLabel {{
                color: {cls.hex("text_hint")};
                font-size: 12px;
            }}
        """

    @classmethod
    def get_chat_header_stylesheet(cls) -> str:
        """获取对话头部样式表"""
        return f"""
            QFrame {{
                background-color: {cls.hex("background_secondary")};
                border-bottom: 1px solid {cls.hex("border_primary")};
            }}
        """

    @classmethod
    def get_chat_input_area_stylesheet(cls) -> str:
        """获取对话输入区域样式表"""
        return f"""
            QFrame {{
                background-color: {cls.hex("background_secondary")};
                border-top: 1px solid {cls.hex("border_primary")};
            }}
        """

    @classmethod
    def get_panel_button_stylesheet(cls) -> str:
        return f"""
            QPushButton {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 12px;
                {cls.emoji_font_css()}
            }}
            QPushButton:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QPushButton:pressed {{
                background-color: {cls.hex("background_selected")};
            }}
        """

    @classmethod
    def get_media_play_button_stylesheet(cls) -> str:
        return f"""
            QPushButton {{
                background-color: {cls.hex("border_focus")};
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 12px;
                {cls.emoji_font_css()}
            }}
            QPushButton:hover {{
                background-color: {cls.hex("accent_hover_bg")};
            }}
            QPushButton:pressed {{
                background-color: {cls.hex("accent_pressed_bg")};
            }}
        """

    @classmethod
    def get_small_icon_button_stylesheet(cls) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                color: {cls.hex("text_hint")};
                border: none;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: #e74c3c;
            }}
        """

    @classmethod
    def get_settings_dialog_stylesheet(cls) -> str:
        """获取设置对话框样式表"""
        return f"""
            QDialog {{
                background-color: {cls.hex("background_primary")};
            }}
            QTabWidget::pane {{
                border: 1px solid {cls.hex("border_primary")};
                background-color: {cls.hex("background_primary")};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: {cls.hex("text_secondary")};
                padding: 8px 18px;
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {cls.hex("text_primary")};
                border-bottom: 2px solid {cls.hex("border_focus")};
            }}
            QTabBar::tab:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QLineEdit {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 6px;
                padding: 8px 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {cls.hex("border_focus")};
            }}
            QDialogButtonBox QPushButton {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                min-width: 80px;
            }}
            QDialogButtonBox QPushButton:hover {{
                background-color: {cls.hex("background_selected")};
            }}
            QLabel {{
                color: {cls.hex("text_primary")};
            }}
            QCheckBox {{
                color: {cls.hex("text_primary")};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {cls.hex("grid_major")};
                background-color: {cls.hex("background_input")};
            }}
            QCheckBox::indicator:checked {{
                background-color: {cls.hex("border_focus")};
                border-color: {cls.hex("border_focus")};
            }}
            QCheckBox::indicator:hover {{
                border-color: {cls.hex("border_hover")};
            }}
            QComboBox {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 120px;
            }}
            QComboBox:hover {{
                border-color: {cls.hex("border_secondary")};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                selection-background-color: {cls.hex("background_selected")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 6px;
            }}
            QSpinBox {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 6px;
                padding: 8px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {cls.hex("background_tertiary")};
                border: none;
                width: 16px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {cls.hex("background_selected")};
            }}
            QPushButton {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("background_hover")};
            }}
        """

    @classmethod
    def get_list_widget_stylesheet(cls) -> str:
        return f"""
            QListWidget {{
                border: 1px solid {cls.hex("border_primary")};
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {cls.hex("border_primary")};
            }}
            QListWidget::item:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QListWidget::item:selected {{
                background-color: {cls.hex("background_selected")};
                color: {cls.hex("text_primary")};
            }}
        """

    @classmethod
    def get_checkbox_stylesheet(cls) -> str:
        return f"""
            QCheckBox {{
                color: {cls.hex("text_primary")};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {cls.hex("border_secondary")};
                border-radius: 4px;
                background-color: {cls.hex("background_secondary")};
            }}
            QCheckBox::indicator:checked {{
                background-color: {cls.hex("border_focus")};
                border-color: {cls.hex("border_focus")};
            }}
        """

    @classmethod
    def get_combobox_stylesheet(cls) -> str:
        return f"""
            QComboBox {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 120px;
            }}
            QComboBox:hover {{
                border-color: {cls.hex("border_secondary")};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                selection-background-color: {cls.hex("background_selected")};
            }}
        """

    @classmethod
    def get_chat_messages_widget_stylesheet(cls) -> str:
        """获取聊天消息区域样式表"""
        return f"""
            QWidget {{
                background-color: {cls.hex("background_primary")};
            }}
        """

    @classmethod
    def get_message_content_edit_stylesheet(cls) -> str:
        return f"""
            QTextEdit {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                {cls.emoji_font_css()}
            }}
        """

    # ==================== 会话管理样式 ====================

    @classmethod
    def get_session_list_stylesheet(cls) -> str:
        """获取会话列表样式表"""
        return f"""
            QWidget#sessionListContainer {{
                background-color: {cls.hex("background_secondary")};
                border-right: 1px solid {cls.hex("border_primary")};
            }}
        """

    @classmethod
    def get_session_list_widget_stylesheet(cls) -> str:
        """获取会话列表控件样式表"""
        return f"""
            QListWidget {{
                background-color: {cls.hex("background_secondary")};
                border: none;
                outline: none;
                color: {cls.hex("text_primary")};
            }}
            QListWidget::item {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                margin: 1px 4px;
                padding: 0px;
            }}
            QListWidget::item:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QListWidget::item:selected {{
                background-color: {cls.hex("background_selected")};
                color: {cls.hex("text_primary")};
            }}
            QListWidget::item:selected QLabel {{
                color: {cls.hex("text_primary")};
            }}
            QScrollBar:vertical {{
                background-color: {cls.hex("background_secondary")};
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cls.hex("background_tertiary")};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.hex("background_selected")};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """

    @classmethod
    def get_session_item_title_stylesheet(cls, is_selected: bool = False) -> str:
        """获取会话项标题样式表"""
        color = cls.hex("text_primary") if is_selected else cls.hex("text_primary")
        return f"""
            QLabel {{
                color: {color};
                font-size: 13px;
                font-weight: bold;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_session_item_meta_stylesheet(cls) -> str:
        """获取会话项元信息样式表（日期、消息数等）"""
        return f"""
            QLabel {{
                color: {cls.hex("text_hint")};
                font-size: 11px;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_session_list_header_stylesheet(cls) -> str:
        """获取会话列表头部样式表"""
        return f"""
            QFrame {{
                background-color: {cls.hex("background_tertiary")};
                border-bottom: 1px solid {cls.hex("border_primary")};
                padding: 8px 12px;
            }}
            QLabel {{
                color: {cls.hex("text_primary")};
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_session_new_button_stylesheet(cls) -> str:
        """获取新建会话按钮样式表"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("border_focus")};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("accent_hover_bg")};
            }}
            QPushButton:pressed {{
                background-color: {cls.hex("accent_pressed_bg")};
            }}
        """

    @classmethod
    def get_session_delete_button_stylesheet(cls) -> str:
        """获取删除会话按钮样式表"""
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {cls.hex("text_hint")};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("danger_hover_bg")};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {cls.hex("danger_pressed_bg")};
                color: white;
            }}
        """

    @classmethod
    def get_session_empty_label_stylesheet(cls) -> str:
        """获取空会话列表提示标签样式表"""
        return f"""
            QLabel {{
                color: {cls.hex("text_hint")};
                font-size: 12px;
                padding: 20px;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_splitter_stylesheet(cls) -> str:
        """获取分割器样式表"""
        return f"""
            QSplitter {{
                background-color: {cls.hex("background_primary")};
            }}
            QSplitter::handle {{
                background-color: {cls.hex("border_primary")};
            }}
            QSplitter::handle:hover {{
                background-color: {cls.hex("border_secondary")};
            }}
            QSplitter::handle:horizontal {{
                width: 1px;
            }}
            QSplitter::handle:vertical {{
                height: 1px;
            }}
        """

    # ==================== 内联控件样式 ====================

    @classmethod
    def get_inline_input_base_stylesheet(cls) -> str:
        """获取内联输入控件基础样式 (QLineEdit)"""
        return f"""
            QLineEdit {{
                background-color: {cls.hex("background_input")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("text_primary")};
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {cls.hex("border_focus")};
            }}
            QLineEdit:disabled {{
                background-color: {cls.hex("background_primary")};
                color: {cls.hex("text_disabled")};
            }}
        """

    @classmethod
    def get_inline_spinbox_stylesheet(cls) -> str:
        """获取内联数字输入控件样式 (QSpinBox, QDoubleSpinBox)"""
        return f"""
            QSpinBox, QDoubleSpinBox {{
                background-color: {cls.hex("background_input")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("text_primary")};
                font-size: 11px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {cls.hex("border_focus")};
            }}
            QSpinBox:disabled, QDoubleSpinBox:disabled {{
                background-color: {cls.hex("background_primary")};
                color: {cls.hex("text_disabled")};
            }}
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: {cls.hex("background_tertiary")};
                border: none;
                width: 16px;
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow,
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {{
                width: 8px;
                height: 8px;
            }}
        """

    @classmethod
    def get_inline_checkbox_stylesheet(cls) -> str:
        """获取内联复选框控件样式"""
        return f"""
            QCheckBox {{
                color: {cls.hex("text_primary")};
                font-size: 11px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 4px;
                border: 1px solid {cls.hex("grid_major")};
                background-color: {cls.hex("background_input")};
            }}
            QCheckBox::indicator:checked {{
                background-color: {cls.hex("border_focus")};
                border-color: {cls.hex("border_focus")};
            }}
            QCheckBox::indicator:hover {{
                border-color: {cls.hex("border_hover")};
            }}
            QCheckBox:disabled {{
                color: {cls.hex("text_disabled")};
            }}
            QCheckBox::indicator:disabled {{
                background-color: {cls.hex("background_primary")};
                border-color: {cls.hex("grid_minor")};
            }}
        """

    @classmethod
    def get_inline_combobox_stylesheet(cls) -> str:
        """获取内联下拉框控件样式"""
        return f"""
            QComboBox {{
                background-color: {cls.hex("background_input")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("text_primary")};
                font-size: 11px;
                min-width: 80px;
            }}
            QComboBox:focus {{
                border-color: {cls.hex("border_focus")};
            }}
            QComboBox:disabled {{
                background-color: {cls.hex("background_primary")};
                color: {cls.hex("text_disabled")};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid {cls.hex("text_placeholder")};
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cls.hex("background_input")};
                border: 1px solid {cls.hex("grid_major")};
                selection-background-color: {cls.hex("border_focus")};
            }}
        """

    @classmethod
    def get_inline_file_picker_button_stylesheet(cls) -> str:
        """获取内联文件选择按钮样式"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("background_tertiary")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("text_primary")};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("border_hover")};
                border-color: {cls.hex("border_hover")};
            }}
            QPushButton:pressed {{
                background-color: {cls.hex("background_pressed")};
            }}
            QPushButton:disabled {{
                background-color: {cls.hex("background_primary")};
                color: {cls.hex("text_disabled")};
                border-color: {cls.hex("grid_minor")};
            }}
        """

    @classmethod
    def get_inline_file_picker_label_stylesheet(cls) -> str:
        """获取内联文件路径标签样式"""
        return f"""
            QLabel {{
                background-color: {cls.hex("background_input")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("text_placeholder")};
                font-size: 11px;
            }}
        """

    @classmethod
    def get_inline_output_label_base_stylesheet(cls) -> str:
        """获取内联输出标签基础样式"""
        return f"""
            QLabel {{
                background-color: {cls.hex("background_secondary")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
        """

    @classmethod
    def get_inline_output_label_idle_stylesheet(cls) -> str:
        """获取内联输出标签空闲状态样式"""
        return f"""
            QLabel {{
                background-color: {cls.hex("background_secondary")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("text_placeholder")};
                font-size: 11px;
            }}
        """

    @classmethod
    def get_inline_output_label_link_stylesheet(cls) -> str:
        """获取内联输出标签链接状态样式"""
        return f"""
            QLabel {{
                background-color: {cls.hex("background_secondary")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("text_link")};
                font-size: 11px;
            }}
        """

    @classmethod
    def get_inline_output_label_error_stylesheet(cls) -> str:
        """获取内联输出标签错误状态样式"""
        return f"""
            QLabel {{
                background-color: {cls.hex("background_secondary")};
                border: 1px solid {cls.hex("grid_major")};
                border-radius: 4px;
                padding: 2px 8px;
                color: {cls.hex("state_error")};
                font-size: 11px;
            }}
        """

    # ==================== 列表项样式 ====================

    @classmethod
    def get_item_widget_base_stylesheet(cls) -> str:
        """获取列表项基础样式"""
        return f"""
            QWidget {{
                border-bottom: 1px solid {cls.hex("grid_minor")};
                background-color: transparent;
            }}
            QWidget:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QWidget:selected {{
                background-color: {cls.hex("background_selected")};
            }}
        """

    @classmethod
    def get_item_name_label_stylesheet(cls) -> str:
        """获取列表项名称标签样式"""
        return f"font-weight: bold; color: {cls.hex('text_primary')};"

    @classmethod
    def get_item_version_label_stylesheet(cls) -> str:
        """获取列表项版本标签样式"""
        return f"color: {cls.hex('text_hint')}; font-size: 11px;"

    @classmethod
    def get_item_description_label_stylesheet(cls) -> str:
        """获取列表项描述标签样式"""
        return f"color: {cls.hex('text_hint')}; font-size: 11px;"

    @classmethod
    def get_item_status_enabled_stylesheet(cls) -> str:
        """获取列表项启用状态标签样式"""
        return f"color: {cls.hex('state_success')}; font-size: 11px;"

    @classmethod
    def get_item_status_disabled_stylesheet(cls) -> str:
        """获取列表项禁用状态标签样式"""
        return f"color: {cls.hex('text_disabled')}; font-size: 11px;"

    @classmethod
    def get_item_accent_button_stylesheet(cls) -> str:
        """获取列表项强调按钮样式"""
        return f"color: {cls.hex('accent_primary')}; font-size: 11px;"

    @classmethod
    def get_item_danger_button_stylesheet(cls) -> str:
        """获取列表项危险按钮样式"""
        return f"color: {cls.hex('state_error')}; font-size: 11px;"

    @classmethod
    def get_item_warning_checkbox_stylesheet(cls) -> str:
        """获取列表项警告复选框样式"""
        return f"color: {cls.hex('state_warning')};"

    # ==================== 按钮样式 ====================

    @classmethod
    def get_install_button_stylesheet(cls) -> str:
        """获取安装按钮样式"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("state_success")};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 5px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("success_hover_bg")};
            }}
            QPushButton:pressed {{
                background-color: {cls.hex("success_pressed_bg")};
            }}
        """

    @classmethod
    def get_primary_button_stylesheet(cls) -> str:
        """获取主要按钮样式 (蓝色)"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("accent_secondary")};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 5px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("accent_hover")};
            }}
            QPushButton:pressed {{
                background-color: {cls.hex("border_focus")};
            }}
        """

    @classmethod
    def get_header_frame_stylesheet(cls) -> str:
        """获取头部框架样式"""
        return f"""
            QFrame {{
                background-color: {cls.hex("background_secondary")};
                border-bottom: 1px solid {cls.hex("border_primary")};
            }}
        """

    @classmethod
    def get_scroll_area_no_border_stylesheet(cls) -> str:
        """获取无边框滚动区域样式"""
        return f"""
            QScrollArea {{
                border: none;
                background-color: {cls.hex("background_primary")};
            }}
        """

    @classmethod
    def get_progress_bar_stylesheet(cls) -> str:
        """获取进度条样式"""
        return f"""
            QProgressBar {{
                background-color: {cls.hex("background_secondary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 6px;
                text-align: center;
                color: {cls.hex("text_primary")};
                min-height: 6px;
                max-height: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {cls.hex("border_focus")};
                border-radius: 3px;
            }}
        """

    @classmethod
    def get_info_frame_stylesheet(cls) -> str:
        """获取信息框架样式"""
        return f"""
            QFrame {{
                background-color: {cls.hex("background_secondary")};
                border-radius: 4px;
                padding: 8px;
            }}
        """

    # ==================== 提取的硬编码样式方法 ====================

    @classmethod
    def get_transparent_background_stylesheet(cls) -> str:
        """Get transparent background stylesheet for container widgets"""
        return "background-color: transparent;"

    @classmethod
    def get_icon_label_stylesheet(cls, size: int = 20) -> str:
        """
        Get icon label stylesheet with configurable font size.

        Args:
            size: Font size in pixels (default: 20)
        """
        return f"""
            QLabel {{
                font-size: {size}px;
                background-color: transparent;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_arrow_indicator_stylesheet(cls) -> str:
        """Get arrow indicator stylesheet for navigation hints"""
        return f"""
            QLabel {{
                color: {cls.hex("text_hint")};
                font-size: 18px;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_home_scroll_area_stylesheet(cls) -> str:
        """Get scroll area stylesheet for home page with scrollbar styling"""
        return f"""
            QScrollArea {{
                border: none;
                background-color: {cls.hex("background_primary")};
            }}
            QScrollBar:vertical {{
                background-color: {cls.hex("background_secondary")};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cls.hex("background_tertiary")};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.hex("background_selected")};
            }}
        """

    @classmethod
    def get_session_list_title_stylesheet(cls) -> str:
        """Get session list title label stylesheet"""
        return f"""
            QLabel {{
                color: {cls.hex("text_primary")};
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_delete_area_stylesheet(cls) -> str:
        """Get delete area container stylesheet for session list"""
        return f"""
            QFrame {{
                background-color: {cls.hex("background_secondary")};
                padding: 8px;
            }}
        """

    @classmethod
    def get_node_panel_container_stylesheet(cls) -> str:
        """Get node panel container stylesheet"""
        return f"""
            QWidget {{
                background-color: {cls.hex("background_secondary")};
                border-right: 1px solid {cls.hex("border_primary")};
            }}
        """

    @classmethod
    def get_settings_frame_stylesheet(cls) -> str:
        """Get settings group frame stylesheet"""
        return f"""
            QFrame {{
                background-color: {cls.hex("background_secondary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 8px;
                padding: 16px;
            }}
        """

    @classmethod
    def get_settings_group_title_stylesheet(cls) -> str:
        """Get settings group title stylesheet"""
        return f"""
            QLabel {{
                color: {cls.hex("text_primary")};
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }}
        """

    @classmethod
    def get_simple_text_label_stylesheet(cls, color_key: str = "text_primary") -> str:
        """
        Get simple text label stylesheet with configurable color.

        Args:
            color_key: Theme color key (default: "text_primary")
        """
        return f"color: {cls.hex(color_key)};"

    @classmethod
    def get_dialog_title_label_stylesheet(cls) -> str:
        """获取对话框标题标签样式"""
        return f"font-size: 14px; font-weight: bold; color: {cls.hex('text_primary')};"

    @classmethod
    def get_dialog_info_label_stylesheet(cls) -> str:
        """获取对话框信息标签样式"""
        return f"color: {cls.hex('text_secondary')}; font-size: 12px;"

    @classmethod
    def get_warning_label_stylesheet(cls) -> str:
        """获取警告标签样式"""
        return f"color: {cls.hex('state_warning')}; font-size: 12px; margin-top: 8px;"

    @classmethod
    def get_scroll_area_with_border_stylesheet(cls) -> str:
        """获取带边框滚动区域样式"""
        return f"""
            QScrollArea {{
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 4px;
            }}
        """

    # ==================== 内容块样式 ====================

    @classmethod
    def get_thinking_block_header_stylesheet(cls) -> str:
        return f"""
            QPushButton {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_hint")};
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                text-align: left;
                font-size: 12px;
                {cls.emoji_font_css()}
            }}
            QPushButton:hover {{
                background-color: {cls.hex("background_selected")};
            }}
        """

    @classmethod
    def get_thinking_block_content_stylesheet(cls) -> str:
        return f"""
            QTextEdit {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_hint")};
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-style: italic;
                font-size: 12px;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_tool_use_block_header_stylesheet(cls) -> str:
        return f"""
            QLabel {{
                color: {cls.hex("accent_primary")};
                font-size: 12px;
                font-weight: bold;
                padding: 4px 0;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_tool_use_block_header_frame_stylesheet(cls) -> str:
        return f"""
        QFrame {{
            background-color: {cls.hex("background_secondary")};
            border: 1px solid {cls.hex("border_primary")};
            border-left: 3px solid {cls.hex("border_focus")};
            border-radius: 4px;
        }}
        """

    @classmethod
    def get_tool_use_block_toggle_button_stylesheet(cls) -> str:
        return f"""
        QPushButton {{
            background-color: transparent;
            color: {cls.hex("text_link")};
            border: none;
            padding: 4px;
            font-size: 11px;
            {cls.emoji_font_css()}
        }}
        QPushButton:hover {{
            color: {cls.hex("accent_hover")};
        }}
        """

    @classmethod
    def get_tool_result_block_header_frame_stylesheet(cls, is_error: bool = False) -> str:
        border_color = cls.hex("border_primary") if not is_error else cls.hex("state_error")
        return f"""
        QFrame {{
            background-color: {cls.hex("background_secondary")};
            border: 1px solid {border_color};
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        }}
        """

    @classmethod
    def get_tool_result_block_status_icon_stylesheet(cls, is_error: bool = False) -> str:
        color = cls.hex("state_success") if not is_error else cls.hex("state_error")
        return f"""
        QLabel {{
            color: {color};
            font-size: 14px;
            font-weight: bold;
            background-color: transparent;
            {cls.emoji_font_css()}
        }}
        """

    @classmethod
    def get_tool_result_block_name_stylesheet(cls) -> str:
        return f"""
        QLabel {{
            color: {cls.hex("text_primary")};
            font-size: 12px;
            font-weight: bold;
            background-color: transparent;
        }}
        """

    @classmethod
    def get_tool_use_block_input_stylesheet(cls) -> str:
        return f"""
            QTextEdit {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-left: 3px solid {cls.hex("border_focus")};
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 11px;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_tool_result_block_header_stylesheet(cls, is_error: bool = False) -> str:
        color = cls.hex("state_error") if is_error else cls.hex("state_success")
        return f"""
            QLabel {{
                color: {color};
                font-size: 12px;
                font-weight: bold;
                padding: 4px 0;
            }}
        """

    @classmethod
    def get_tool_result_block_content_stylesheet(cls, is_error: bool = False) -> str:
        color = cls.hex("state_error") if is_error else cls.hex("text_primary")
        border_color = cls.hex("state_error") if is_error else cls.hex("border_secondary")
        return f"""
            QTextEdit {{
                background-color: {cls.hex("background_secondary")};
                color: {color};
                border: 1px solid {cls.hex("border_primary")};
                border-left: 3px solid {border_color};
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 11px;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_tool_result_show_more_button_stylesheet(cls) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {cls.hex("text_link")};
                border: none;
                padding: 4px 8px;
                font-size: 11px;
                text-align: left;
                {cls.emoji_font_css()}
            }}
            QPushButton:hover {{
                color: {cls.hex("accent_hover")};
            }}
        """

    # ==================== Block 卡片统一样式 ====================

    @classmethod
    def get_block_card_stylesheet(cls, accent_color_key: str = "tool_accent") -> str:
        """获取 block 卡片外框样式。

        Args:
            accent_color_key: 左侧强调色 key (thinking_accent/tool_accent/success_accent/error_accent)
        """
        return f"""
            QFrame#blockCard {{
                background-color: {cls.hex("card_background")};
                border: 1px solid {cls.hex("card_border")};
                border-left: 3px solid {cls.hex(accent_color_key)};
                border-radius: 6px;
            }}
        """

    @classmethod
    def get_block_card_header_stylesheet(cls, accent_color_key: str = "tool_accent") -> str:
        """获取 block 卡片标题区样式。

        Args:
            accent_color_key: 悬停时的左侧强调色
        """
        return f"""
            QFrame#blockHeader {{
                background-color: transparent;
                border: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                padding: 6px 10px;
            }}
            QFrame#blockHeader:hover {{
                background-color: {cls.hex("card_header_hover")};
            }}
        """

    @classmethod
    def get_block_card_icon_stylesheet(cls) -> str:
        """获取 block 卡片图标标签样式"""
        return f"""
            QLabel {{
                background-color: transparent;
                border: none;
                font-size: 14px;
                {cls.emoji_font_css()}
            }}
        """

    @classmethod
    def get_block_card_title_stylesheet(cls, color_key: str = "text_primary") -> str:
        """获取 block 卡片标题标签样式"""
        return f"""
            QLabel {{
                color: {cls.hex(color_key)};
                font-size: 12px;
                font-weight: bold;
                background-color: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_block_card_content_stylesheet(
        cls,
        content_type: str = "code",
        is_error: bool = False,
    ) -> str:
        """获取 block 卡片内容区样式。

        Args:
            content_type: "code" (等宽字体) 或 "text" (普通字体, 用于 thinking)
            is_error: 是否错误状态
        """
        if is_error:
            text_color = cls.hex("state_error")
        elif content_type == "thinking":
            text_color = cls.hex("text_hint")
        else:
            text_color = cls.hex("text_primary")

        font_family = "font-family: monospace;" if content_type == "code" else ""
        font_style = "font-style: italic;" if content_type == "thinking" else ""

        return f"""
            QTextEdit {{
                background-color: transparent;
                color: {text_color};
                border: none;
                border-bottom-left-radius: 5px;
                border-bottom-right-radius: 5px;
                padding: 6px 10px;
                font-size: 12px;
                {font_family}
                {font_style}
                {cls.emoji_font_css()}
            }}
        """

    # ==================== 节点编辑器特定颜色 ====================

    # 节点颜色
    NODE_BACKGROUND = QColor(45, 45, 48)
    NODE_BORDER = QColor(70, 70, 73)
    NODE_SELECTED_BORDER = QColor(33, 150, 243)
    NODE_TEXT = QColor(220, 220, 220)
    NODE_HEADER = QColor(55, 55, 58)

    # 节点状态颜色
    NODE_STATE_IDLE = QColor(97, 97, 97)
    NODE_STATE_RUNNING = QColor(255, 193, 7)
    NODE_STATE_SUCCESS = QColor(76, 175, 80)
    NODE_STATE_ERROR = QColor(244, 67, 54)

    # 网格颜色
    GRID_MINOR = QColor(45, 45, 45)
    GRID_MAJOR = QColor(60, 60, 60)
    GRID_BACKGROUND = QColor(35, 35, 38)

    # 连接线颜色
    CONNECTION_DEFAULT = QColor(180, 180, 180)
    CONNECTION_HOVER = QColor(220, 220, 220)
    CONNECTION_SELECTED = QColor(33, 150, 243)

    @classmethod
    def _update_color_attributes(cls) -> None:
        """Update class-level QColor constants to match current theme"""
        cls.NODE_BACKGROUND = cls.color("node_bg_idle")
        cls.NODE_BORDER = cls.color("node_border_normal")
        cls.NODE_SELECTED_BORDER = cls.color("border_focus")
        cls.NODE_TEXT = cls.color("node_title")
        cls.NODE_HEADER = cls.color("node_border_normal")
        cls.NODE_STATE_IDLE = cls.color("state_idle")
        cls.NODE_STATE_RUNNING = cls.color("state_running")
        cls.NODE_STATE_SUCCESS = cls.color("state_success")
        cls.NODE_STATE_ERROR = cls.color("state_error")
        cls.GRID_MINOR = cls.color("grid_minor")
        cls.GRID_MAJOR = cls.color("grid_major")
        cls.GRID_BACKGROUND = cls.color("grid_background")
        cls.CONNECTION_DEFAULT = cls.color("text_secondary")
        cls.CONNECTION_HOVER = cls.color("text_primary")
        cls.CONNECTION_SELECTED = cls.color("border_focus")


# 创建全局主题实例
theme = Theme()
