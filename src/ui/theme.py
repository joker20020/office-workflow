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
from PySide6.QtGui import QColor


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

    # ==================== 颜色常量 ====================

    DARK_COLORS = {
        "background_primary": "#1e1e1e",
        "background_secondary": "#2d2d2d",
        "background_tertiary": "#3d3d3d",
        "background_hover": "#3a3a3a",
        "background_selected": "#454545",
        "background_pressed": "#505050",
        "background_input": "#2d2d30",
        "border_primary": "#404040",
        "border_secondary": "#555555",
        "border_focus": "#0078d4",
        "border_hover": "#4a4a4a",
        "text_primary": "#e0e0e0",
        "text_secondary": "#b0b0b0",
        "text_disabled": "#666666",
        "text_hint": "#999999",
        "text_placeholder": "#808080",
        "text_link": "#4fc3f7",
        "accent_primary": "#90CAF9",
        "accent_secondary": "#64B5F6",
        "accent_hover": "#BBDEFB",
        "state_idle": "#616161",
        "state_running": "#FFC107",
        "state_success": "#4CAF50",
        "state_error": "#F44336",
        "state_warning": "#FFA726",
        "grid_minor": "#2d2d2d",
        "grid_major": "#3c3c3c",
        "grid_background": "#232326",
        "node_bg_idle": "#2d2d30",
        "node_bg_running": "#3d3d00",
        "node_bg_success": "#1b3d1b",
        "node_bg_error": "#3d1b1b",
        "node_border_normal": "#3c3c3c",
        "node_border_hover": "#4a4a4a",
        "node_title": "#d4d4d4",
        "node_port_name": "#b4b4b4",
        # Button state colors
        "accent_hover_bg": "#1976D2",
        "accent_pressed_bg": "#1565C0",
        "danger_hover_bg": "#C62828",
        "danger_pressed_bg": "#B71C1C",
        "success_hover_bg": "#43A047",
        "success_pressed_bg": "#388E3C",
    }

    LIGHT_COLORS = {
        "background_primary": "#f5f5f5",
        "background_secondary": "#ffffff",
        "background_tertiary": "#e8e8e8",
        "background_hover": "#e0e0e0",
        "background_selected": "#d0d0d0",
        "background_pressed": "#c0c0c0",
        "background_input": "#ffffff",
        "border_primary": "#d0d0d0",
        "border_secondary": "#c0c0c0",
        "border_focus": "#0078d4",
        "border_hover": "#c0c0c0",
        "text_primary": "#1a1a1a",
        "text_secondary": "#666666",
        "text_disabled": "#999999",
        "text_hint": "#888888",
        "text_placeholder": "#a0a0a0",
        "text_link": "#29B6F2",
        "accent_primary": "#1976D2",
        "accent_secondary": "#2196F3",
        "accent_hover": "#42A5F5",
        "state_idle": "#9e9e9e",
        "state_running": "#FFC107",
        "state_success": "#4CAF50",
        "state_error": "#F44336",
        "state_warning": "#FFA726",
        "grid_minor": "#e0e0e0",
        "grid_major": "#c0c0c0",
        "grid_background": "#f5f5f5",
        "node_bg_idle": "#f5f5f5",
        "node_bg_running": "#fffde7",
        "node_bg_success": "#e8f5e8",
        "node_bg_error": "#ffebee",
        "node_border_normal": "#e0e0e0",
        "node_border_hover": "#d0d0d0",
        "node_title": "#1a1a1a",
        "node_port_name": "#666666",
        "accent_hover_bg": "#1976D2",
        "accent_pressed_bg": "#1565C0",
        "danger_hover_bg": "#D32F2F",
        "danger_pressed_bg": "#C62828",
        "success_hover_bg": "#4CAF50",
        "success_pressed_bg": "#388E3C",
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
        bg_color = cls.hex("background_selected") if selected else "transparent"
        hover_color = cls.hex("background_pressed") if selected else cls.hex("background_hover")
        text_color = cls.hex("text_primary") if selected else cls.hex("text_secondary")
        hover_text_color = cls.hex("text_primary")  # hover时文字变亮

        return f"""
            NavItem {{
                background-color: {bg_color};
                border: none;
                border-radius: 8px;
                text-align: left;
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
                padding: 4px 8px;
                border-radius: 4px;
            }}
        """

    @classmethod
    def get_toolbar_stylesheet(cls) -> str:
        """获取工具栏样式表"""
        return f"""
            QToolBar {{ 
                background-color: {cls.hex("background_secondary")}; 
                border-bottom: 1px solid {cls.hex("border_primary")};
                padding: 4px;
                spacing: 4px;
            }}
            QToolButton {{ 
                padding: 6px 12px;
                border: none;
                border-radius: 3px;
                background-color: transparent;
                color: {cls.hex("text_primary")};
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
                padding: 4px 8px;
                border-radius: 4px;
            }}
        """

    @classmethod
    def get_node_panel_title_stylesheet(cls) -> str:
        """获取节点面板标题样式表"""
        return f"""
            QLabel {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
                padding: 8px;
                font-weight: bold;
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
            }}
            QTreeWidget::item {{
                padding: 4px;
                color: {cls.hex("text_primary")};
            }}
            QTreeWidget::item:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QTreeWidget::item:selected {{
                background-color: transparent;
                border: 1px solid {cls.hex("border_secondary")};
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
        return f"color: {cls.hex('text_hint')}; padding-left: 10px;"

    @classmethod
    def get_hint_label_stylesheet(cls) -> str:
        """获取提示标签样式表"""
        return f"color: {cls.hex('text_hint')}; padding: 8px; font-size: 11px;"

    @classmethod
    def get_title_label_stylesheet(cls) -> str:
        """获取标题标签样式表"""
        return f"""
            font-size: 16px;
            font-weight: bold;
            color: {cls.hex("accent_primary")};
            padding: 8px;
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
                padding: 32px 48px;
            }}
        """

    @classmethod
    def get_home_title_stylesheet(cls) -> str:
        """获取首页标题样式表"""
        return f"""
            QLabel#homeTitle {{
                color: {cls.hex("text_primary")};
                font-size: 32px;
                font-weight: bold;
                background-color: transparent;
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
                margin-top: 8px;
            }}
        """

    @classmethod
    def get_home_section_title_stylesheet(cls) -> str:
        """获取首页区块标题样式表"""
        return f"""
            QLabel#sectionTitle {{
                color: {cls.hex("text_primary")};
                font-size: 18px;
                font-weight: bold;
                background-color: transparent;
                padding: 16px 0 8px 0;
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
                border-radius: 12px;
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
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
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
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("accent_hover_bg")};
            }}
            QPushButton:disabled {{
                background-color: {cls.hex("background_tertiary")};
            }}
        """

    @classmethod
    @classmethod
    def get_chat_stop_button_stylesheet(cls) -> str:
        """获取对话停止按钮样式表"""
        return f"""
            QPushButton {{
                background-color: {cls.hex("state_error")};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
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
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
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
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
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
            }}
            QTabBar::tab {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_secondary")};
                padding: 8px 16px;
                border: 1px solid {cls.hex("border_primary")};
            }}
            QTabBar::tab:selected {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
            }}
            QTabBar::tab:hover {{
                background-color: {cls.hex("background_tertiary")};
            }}
            QLineEdit {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus {{
                border: 1px solid {cls.hex("border_focus")};
            }}
            QDialogButtonBox QPushButton {{
                background-color: {cls.hex("background_tertiary")};
                color: {cls.hex("text_primary")};
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
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
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
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
                border: 1px solid {cls.hex("border_primary")};
            }}
            QSpinBox {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 4px;
                padding: 6px;
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
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
                padding: 2px 6px;
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
                border-radius: 3px;
                padding: 4px 12px;
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
                border-radius: 3px;
                padding: 4px 12px;
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
                border-radius: 3px;
                text-align: center;
                color: {cls.hex("text_primary")};
            }}
            QProgressBar::chunk {{
                background-color: {cls.hex("state_success")};
                border-radius: 2px;
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
            }}
            QPushButton:hover {{
                color: {cls.hex("accent_hover")};
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
