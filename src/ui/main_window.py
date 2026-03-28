# -*- coding: utf-8 -*-
"""
主窗口模块

应用程序的主窗口， - NavigationRail: 左侧导航栏
 - QStackedWidget: 右侧内容区域
 - 状态栏

使用方式：
    from src.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
"""

from typing import Optional, Any

import threading
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QStackedWidget,
    QWidget,
)

from src.agent import (
    AgentIntegration,
    ApiKeyManager,
    WorkflowTools,
    McpServerManager,
    SkillManager,
)
from src.agent.chat_history import ChatHistory
from src.engine.node_engine import NodeEngine
from src.ui.navigation_rail import NavigationRail
from src.ui.node_editor import NodeEditorPanel
from src.ui.chat import ChatPanel
from src.engine.node_graph import NodeGraph
from src.storage.database import Database
from src.storage.repositories import ChatHistoryRepository
from src.utils.logger import get_logger
from src.ui.theme import Theme
from pathlib import Path

_logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """主窗口 - 应用程序的核心界面"""

    def __init__(self, engine: Optional[NodeEngine] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._pages: dict[str, QWidget] = {}
        self._node_engine = engine or NodeEngine()
        self._db = Database(Path("data") / "app.db")
        self._db.create_tables()
        self._api_key_manager = ApiKeyManager(self._db)
        self._mcp_manager = McpServerManager(self._db)
        self._skill_manager = SkillManager(self._db)
        self._history_repository = ChatHistoryRepository(self._db)
        self._node_graph = NodeGraph(name="默认工作流")
        self._workflow_tools = WorkflowTools(self._node_graph, self._node_engine)
        # 使用QueuedConnection确保跨线程信号正确传递（Agent在QThread中运行）
        self._workflow_tools.graph_changed.connect(
            self._on_graph_changed, Qt.ConnectionType.QueuedConnection
        )
        _logger.info("graph_changed信号已连接（使用QueuedConnection）")

        # 连接节点值变化信号， 用于同步控件显示
        self._workflow_tools.node_value_changed.connect(
            self._on_node_value_changed, Qt.ConnectionType.QueuedConnection
        )
        self._agent_integration = AgentIntegration(
            api_key_manager=self._api_key_manager,
            node_engine=self._node_engine,
            workflow_tools=self._workflow_tools,
            mcp_manager=self._mcp_manager,
            skill_manager=self._skill_manager,
            history_repository=self._history_repository,
        )

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
        self._content_stack.setStyleSheet(Theme.get_content_stack_stylesheet())
        main_layout.addWidget(self._content_stack, 1)

        # 状态栏（必须在 _setup_default_nav_items 之前创建）
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")
        self._status_bar.setStyleSheet(Theme.get_status_bar_stylesheet())

        # 添加默认导航项
        self._setup_default_nav_items()

        # 应用窗口样式 - 暗色主题
        self.setStyleSheet(Theme.get_main_window_stylesheet())

    def _setup_default_nav_items(self) -> None:
        """设置默认导航项"""
        welcome_page = self._create_welcome_page()
        nodes_page = self._create_nodes_page()
        agent_page = self._create_agent_page()

        self.add_page("home", welcome_page)
        self.add_page("nodes", nodes_page)
        self.add_page("agent", agent_page)
        self.add_page("plugins", self._create_placeholder_page("插件管理", "Phase 4"))
        self.add_page("packages", self._create_placeholder_page("节点包管理", "Phase 5"))

        self._nav_rail.add_item("home", "首页", "🏠")
        self._nav_rail.add_item("nodes", "节点编辑器", "🔧")
        self._nav_rail.add_item("agent", "AI 助手", "🤖")
        self._nav_rail.add_item("plugins", "插件管理", "🧩")
        self._nav_rail.add_item("packages", "节点包", "📦")

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        welcome_label = QLabel(
            "<h1>欢迎使用办公小工具整合平台</h1>"
            "<p>这是一个基于节点编辑器的办公工具整合平台</p>"
            "<p class='hint'>Phase 3: Agent集成已完成</p>"
        )
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet(Theme.get_welcome_page_stylesheet())
        layout.addWidget(welcome_label)

        return page

    def _create_nodes_page(self) -> QWidget:
        self._node_editor_panel = NodeEditorPanel(self._node_engine)
        self._node_editor_panel.set_graph(self._node_graph)
        return self._node_editor_panel


    def _create_agent_page(self) -> QWidget:
        self._chat_panel = ChatPanel(
            agent=self._agent_integration,
            api_key_manager=self._api_key_manager,
            mcp_manager=self._mcp_manager,
            skill_manager=self._skill_manager,
            history_repository=self._history_repository,
        )

        return self._chat_panel

    def _create_placeholder_page(self, title: str, phase: str) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f"<h2>{title}</h2><p class='hint'>将在 {phase} 实现</p>")
        label.setStyleSheet(Theme.get_welcome_page_stylesheet())
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

        # 切换到节点编辑器时，强制刷新显示
        if item_id == "nodes" and hasattr(self, "_node_editor_panel") and self._node_editor_panel:
            self._node_editor_panel.set_graph(self._node_graph)

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

    @property
    def node_engine(self) -> NodeEngine:
        """获取节点引擎"""
        return self._node_engine

    @property
    def node_editor_panel(self) -> NodeEditorPanel:
        """获取节点编辑器面板"""
        return self._node_editor_panel

    @property
    def chat_panel(self) -> ChatPanel:
        """获取对话面板"""
        return self._chat_panel

    @property
    def agent_integration(self) -> AgentIntegration:
        """获取Agent集成"""
        return self._agent_integration

    def _on_graph_changed(self) -> None:
        """处理graph_changed信号 - 在主线程中刷新节点编辑器"""
        import threading

        _logger.info(
            f"[Thread: {threading.current_thread().name}] 收到graph_changed信号，准备刷新节点编辑器"
        )
        if hasattr(self, "_node_editor_panel") and self._node_editor_panel is not None:
            _logger.info(
                f"[Thread: {threading.current_thread().name}] 调用set_graph刷新，节点数: {len(self._node_graph.nodes)}"
            )
            self._node_editor_panel.set_graph(self._node_graph)
            _logger.info(f"[Thread: {threading.current_thread().name}] set_graph调用完成")
        else:
            _logger.warning(
                f"[Thread: {threading.current_thread().name}] _node_editor_panel未初始化，跳过刷新"
            )

    def _on_node_value_changed(self, node_id: str, port_name: str, value: Any) -> None:
        """处理node_value_changed信号 - 同步控件显示"""
        import threading

        _logger.info(
            f"[Thread: {threading.current_thread().name}] 收到node_value_changed信号: "
            f"node={node_id[:8]}..., port={port_name}, value={value}"
        )

        if not hasattr(self, "_node_editor_panel") or self._node_editor_panel is None:
            _logger.warning("_node_editor_panel未初始化，跳过值同步")
            return

        node_item = self._node_editor_panel.get_node_item(node_id)
        if node_item is None:
            _logger.warning(f"未找到节点图形项: {node_id[:8]}...")
            return

        node_item.set_widget_value(port_name, value)
        _logger.info(f"已同步控件值: {port_name} = {value}")

    def closeEvent(self, event) -> None:
        _logger.info("主窗口关闭")
        super().closeEvent(event)
