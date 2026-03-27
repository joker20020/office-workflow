# -*- coding: utf-8 -*-
"""
暗色主题配置模块

集中管理所有UI组件的颜色常量和QSS样式，方便统一修改和维护。

使用方式：
    from src.ui.theme import Theme

    # 获取颜色
    color = Theme.COLORS['background']

    # 获取样式表
    stylesheet = Theme.get_toolbar_stylesheet()
"""

from PySide6.QtGui import QColor


class Theme:
    """
    暗色主题配置类

    提供统一的颜色常量和样式表定义。
    所有UI组件应使用此处的颜色，确保视觉一致性。
    """

    # ==================== 颜色常量 ====================

    COLORS = {
        # 背景色
        "background_primary": "#1e1e1e",  # 主背景色（最深）
        "background_secondary": "#2d2d2d",  # 次级背景色
        "background_tertiary": "#3d3d3d",  # 三级背景色
        "background_hover": "#3a3a3a",  # 悬停背景色
        "background_selected": "#454545",  # 选中背景色
        "background_pressed": "#505050",  # 按下背景色
        # 边框色
        "border_primary": "#404040",  # 主边框色
        "border_secondary": "#555555",  # 次级边框色
        "border_focus": "#0078d4",  # 焦点边框色（蓝色）
        # 文字色
        "text_primary": "#e0e0e0",  # 主文字色（最亮）
        "text_secondary": "#b0b0b0",  # 次级文字色
        "text_disabled": "#666666",  # 禁用文字色
        "text_hint": "#999999",  # 提示文字色
        # 强调色
        "accent_primary": "#90CAF9",  # 主强调色（浅蓝）
        "accent_secondary": "#64B5F6",  # 次级强调色
        "accent_hover": "#BBDEFB",  # 悬停强调色
        # 状态色
        "state_idle": "#616161",  # 空闲状态（灰色）
        "state_running": "#FFC107",  # 运行状态（黄色）
        "state_success": "#4CAF50",  # 成功状态（绿色）
        "state_error": "#F44336",  # 错误状态（红色）
        # 网格色
        "grid_minor": "#2d2d2d",  # 细网格线
        "grid_major": "#3c3c3c",  # 粗网格线
        "grid_background": "#232326",  # 网格背景
    }

    # QColor 对象缓存
    _QCOLORS = {}

    @classmethod
    def color(cls, name: str) -> QColor:
        """
        获取 QColor 对象

        Args:
            name: 颜色名称（如 'background_primary'）

        Returns:
            QColor 对象
        """
        if name not in cls._QCOLORS:
            hex_color = cls.COLORS.get(name, "#ffffff")
            cls._QCOLORS[name] = QColor(hex_color)
        return cls._QCOLORS[name]

    @classmethod
    def hex(cls, name: str) -> str:
        """
        获取十六进制颜色字符串

        Args:
            name: 颜色名称

        Returns:
            十六进制颜色字符串（如 '#2d2d2d'）
        """
        return cls.COLORS.get(name, "#ffffff")

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
        """获取欢迎页面样式表"""
        return f"""
            QLabel {{
                padding: 40px;
            }}
            h1 {{
                color: {cls.hex("accent_primary")};
                font-size: 28px;
            }}
            h2 {{
                color: {cls.hex("text_primary")};
                font-size: 24px;
            }}
            p {{
                color: {cls.hex("text_hint")};
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
