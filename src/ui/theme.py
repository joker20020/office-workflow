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
        "border_primary": "#404040",
        "border_secondary": "#555555",
        "border_focus": "#0078d4",
        "text_primary": "#e0e0e0",
        "text_secondary": "#b0b0b0",
        "text_disabled": "#666666",
        "text_hint": "#999999",
        "accent_primary": "#90CAF9",
        "accent_secondary": "#64B5F6",
        "accent_hover": "#BBDEFB",
        "state_idle": "#616161",
        "state_running": "#FFC107",
        "state_success": "#4CAF50",
        "state_error": "#F44336",
        "grid_minor": "#2d2d2d",
        "grid_major": "#3c3c3c",
        "grid_background": "#232326",
    }

    LIGHT_COLORS = {
        "background_primary": "#f5f5f5",
        "background_secondary": "#ffffff",
        "background_tertiary": "#e8e8e8",
        "background_hover": "#e0e0e0",
        "background_selected": "#d0d0d0",
        "background_pressed": "#c0c0c0",
        "border_primary": "#d0d0d0",
        "border_secondary": "#c0c0c0",
        "border_focus": "#0078d4",
        "text_primary": "#1a1a1a",
        "text_secondary": "#666666",
        "text_disabled": "#999999",
        "text_hint": "#888888",
        "accent_primary": "#1976D2",
        "accent_secondary": "#2196F3",
        "accent_hover": "#42A5F5",
        "state_idle": "#9e9e9e",
        "state_running": "#FFC107",
        "state_success": "#4CAF50",
        "state_error": "#F44336",
        "grid_minor": "#e0e0e0",
        "grid_major": "#c0c0c0",
        "grid_background": "#f5f5f5",
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
            QTreeWidget::branch {{
                background-color: {cls.hex("background_secondary")};
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
                background-color: #1976D2;
            }}
            QPushButton:disabled {{
                background-color: {cls.hex("background_tertiary")};
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
                padding: 6px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {cls.hex("background_selected")};
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
    def get_message_content_label_stylesheet(cls) -> str:
        return f"""
            QLabel {{
                background-color: {cls.hex("background_secondary")};
                color: {cls.hex("text_primary")};
                border: 1px solid {cls.hex("border_primary")};
                border-radius: 4px;
                padding: 8px;
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
                margin: 2px 4px;
                padding: 8px 12px;
            }}
            QListWidget::item:hover {{
                background-color: {cls.hex("background_hover")};
            }}
            QListWidget::item:selected {{
                background-color: {cls.hex("background_selected")};
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
                background-color: #1976D2;
            }}
            QPushButton:pressed {{
                background-color: #1565C0;
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
                background-color: #C62828;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #B71C1C;
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


# 创建全局主题实例
theme = Theme()
