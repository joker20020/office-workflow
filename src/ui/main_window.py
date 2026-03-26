# -*- coding: utf-8 -*-
"""
主窗口模块

应用程序的主窗口，包含：
- NavigationRail: 左侧导航栏
- QStackedWidget: 右侧内容区域
- 状态栏

使用方式：
    from src.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QStackedWidget,
    QWidget,
)

from src.ui.navigation_rail import NavigationRail
from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    主窗口

    应用程序的主窗口，提供：
    - 左侧导航栏
    - 右侧内容区域（堆叠布局）
    - 状态栏

    Example:
        window = MainWindow()
        window.add_page("home", home_widget)
        window.show()
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        初始化主窗口

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # 页面映射：页面ID -> QWidget
        self._pages: dict[str, QWidget] = {}

        self._setup_ui()

        _logger.info("MainWindow 初始化完成")

    def _setup_ui(self) -> None:
        """设置UI"""
        # 窗口属性
        self.setWindowTitle("办公小工具整合平台")
        self.setMinimumSize(1200, 800)
        self.resize(1280, 900)

        # 中央组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航栏
        self._nav_rail = NavigationRail()
        self._nav_rail.currentChanged.connect(self._on_nav_changed)
        main_layout.addWidget(self._nav_rail)

        # 右侧内容区域
        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: white;
            }
        """)
        main_layout.addWidget(self._content_stack, 1)

        # 状态栏（必须在 _setup_default_nav_items 之前创建）
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

        # 添加默认导航项
        self._setup_default_nav_items()

        # 应用窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FAFAFA;
            }
        """)

    def _setup_default_nav_items(self) -> None:
        """设置默认导航项"""
        # 首页
        self._nav_rail.add_item("home", "首页", "🏠")
        welcome_page = self._create_welcome_page()
        self.add_page("home", welcome_page)

        # 节点编辑器（Phase 2 实现）
        self._nav_rail.add_item("nodes", "节点编辑器", "🔧")
        nodes_page = self._create_placeholder_page("节点编辑器", "Phase 2")
        self.add_page("nodes", nodes_page)

        # AI 对话（Phase 3 实现）
        self._nav_rail.add_item("agent", "AI 助手", "🤖")
        agent_page = self._create_placeholder_page("AI 助手", "Phase 3")
        self.add_page("agent", agent_page)

        # 插件管理（Phase 4 实现）
        self._nav_rail.add_item("plugins", "插件管理", "🧩")
        plugins_page = self._create_placeholder_page("插件管理", "Phase 4")
        self.add_page("plugins", plugins_page)

        # 节点包管理（Phase 5 实现）
        self._nav_rail.add_item("packages", "节点包", "📦")
        packages_page = self._create_placeholder_page("节点包管理", "Phase 5")
        self.add_page("packages", packages_page)

        # 设置默认显示首页
        self._nav_rail.set_current("home")

    def _create_welcome_page(self) -> QWidget:
        """创建欢迎页面"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        welcome_label = QLabel(
            "<h1>欢迎使用办公小工具整合平台</h1>"
            "<p style='color: #666; font-size: 14px;'>"
            "这是一个基于节点编辑器的办公工具整合平台"
            "</p>"
            "<p style='color: #999; font-size: 12px;'>"
            "Phase 1: 基础框架已就绪"
            "</p>"
        )
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("""
            QLabel {
                padding: 40px;
            }
            h1 {
                color: #1976D2;
                font-size: 28px;
            }
        """)
        layout.addWidget(welcome_label)

        return page

    def _create_placeholder_page(self, title: str, phase: str) -> QWidget:
        """创建占位页面"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f"<h2>{title}</h2><p style='color: #999;'>将在 {phase} 实现</p>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                padding: 40px;
            }
            h2 {
                color: #9E9E9E;
                font-size: 24px;
            }
        """)
        layout.addWidget(label)

        return page

    def add_page(self, page_id: str, page: QWidget) -> None:
        """
        添加页面

        Args:
            page_id: 页面ID（应与导航项ID对应）
            page: 页面组件
        """
        if page_id in self._pages:
            _logger.warning(f"页面已存在: {page_id}")
            return

        self._pages[page_id] = page
        self._content_stack.addWidget(page)

        _logger.debug(f"添加页面: {page_id}")

    def remove_page(self, page_id: str) -> bool:
        """
        移除页面

        Args:
            page_id: 页面ID

        Returns:
            是否成功移除
        """
        if page_id not in self._pages:
            return False

        page = self._pages.pop(page_id)
        self._content_stack.removeWidget(page)
        page.deleteLater()

        _logger.debug(f"移除页面: {page_id}")
        return True

    def show_page(self, page_id: str) -> None:
        """
        显示指定页面

        Args:
            page_id: 页面ID
        """
        if page_id not in self._pages:
            _logger.warning(f"页面不存在: {page_id}")
            return

        self._content_stack.setCurrentWidget(self._pages[page_id])
        _logger.debug(f"显示页面: {page_id}")

    def _on_nav_changed(self, item_id: str) -> None:
        """导航项改变处理"""
        self.show_page(item_id)
        self._status_bar.showMessage(f"当前: {item_id}")

    def set_status(self, message: str) -> None:
        """
        设置状态栏消息

        Args:
            message: 状态消息
        """
        self._status_bar.showMessage(message)

    @property
    def nav_rail(self) -> NavigationRail:
        """获取导航栏"""
        return self._nav_rail

    def closeEvent(self, event) -> None:
        """窗口关闭事件"""
        _logger.info("主窗口关闭")
        super().closeEvent(event)
