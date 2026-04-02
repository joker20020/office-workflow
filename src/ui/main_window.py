# -*- coding: utf-8 -*-
"""
主窗口模块

应用程序的主窗口，- NavigationRail: 左侧导航栏
 - QStackedWidget: 右侧内容区域
 - 状态栏

使用方式:
    from src.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
"""

from typing import Optional, Any
from pathlib import Path

import threading
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QStackedWidget,
    QWidget,
)

from src.agent import (
    AgentIntegration,
    WorkflowTools,
)
from src.agent.api_key_manager import get_api_key_manager
from src.agent.mcp_server_manager import get_mcp_server_manager
from src.agent.skill_manager import get_skill_manager
from src.engine.node_engine import get_node_engine

try:
    from src.nodes.package_manager import NodePackageManager, get_node_package_manager

    _HAS_PACKAGE_MANAGER_SINGLETON = True
except Exception:
    NodePackageManager = None
    get_node_package_manager = None
    _HAS_PACKAGE_MANAGER_SINGLETON = False
from src.agent.chat_history import ChatHistory
from src.core.app_context import AppContext
from src.core.permission_manager import Permission, PermissionSet
from src.engine.node_engine import NodeEngine
from src.ui.navigation_rail import NavigationRail
from src.ui.node_editor import NodeEditorPanel
from src.ui.chat import ChatPanel
from src.ui.home_page import HomePage
from src.ui.plugins import PluginPanel
from src.ui.packages import PackagePanel
from src.nodes.package_manager import NodePackageManager
from src.engine.node_graph import NodeGraph
from src.storage.database import Database
from src.storage.repositories import (
    ChatHistoryRepository,
    PluginPermissionRepository,
    PluginRepository,
)
from src.utils.logger import get_logger
from src.ui.theme import Theme
from src.ui.theme_manager import ThemeManager

_logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """主窗口 - 应用程序的核心界面"""

    def __init__(
        self,
        engine: Optional[NodeEngine] = None,
        app_context: Optional[AppContext] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._pages: dict[str, QWidget] = {}
        self._app_context = app_context
        event_bus = app_context.event_bus if app_context else None

        if engine is not None:
            self._node_engine = engine
            try:
                import src.engine.node_engine as _ne

                with getattr(_ne, "_global_lock", threading.Lock()):
                    _ne._global_node_engine = engine
            except Exception:
                pass
        else:
            self._node_engine = get_node_engine()

        if app_context is not None:
            self._db = app_context.database
        else:
            self._db = Database(Path("data") / "app.db")
            self._db.create_tables()

        self._api_key_manager = get_api_key_manager()
        self._mcp_manager = get_mcp_server_manager()
        self._skill_manager = get_skill_manager()
        self._history_repository = ChatHistoryRepository(self._db)
        self._permission_repository = PluginPermissionRepository(self._db)
        self._plugin_repository = PluginRepository(self._db)
        self._node_graph = NodeGraph(name="默认工作流")
        self._workflow_tools = WorkflowTools(self._node_graph, self._node_engine)

        packages_dir = Path("node_packages")
        if _HAS_PACKAGE_MANAGER_SINGLETON and get_node_package_manager is not None:
            try:
                self._package_manager = get_node_package_manager()
            except Exception:
                self._package_manager = NodePackageManager(
                    packages_dir=packages_dir,
                    database=self._db,
                    node_engine=self._node_engine,
                    event_bus=event_bus,
                )
        else:
            self._package_manager = NodePackageManager(
                packages_dir=packages_dir,
                database=self._db,
                node_engine=self._node_engine,
                event_bus=event_bus,
            )

        # 加载所有已启用的节点包
        loaded_count = self._package_manager.load_all_enabled()
        _logger.info(f"已加载 {loaded_count} 个节点包")

        self._workflow_tools = WorkflowTools(self._node_graph, self._node_engine)

        self._agent_integration = AgentIntegration(
            api_key_manager=self._api_key_manager,
            node_engine=self._node_engine,
            workflow_tools=self._workflow_tools,
            mcp_manager=self._mcp_manager,
            skill_manager=self._skill_manager,
            history_repository=self._history_repository,
        )

        self._theme_manager = ThemeManager.instance()
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

        self._setup_ui()

        _logger.info("MainWindow 初始化完成")

    def _setup_ui(self) -> None:
        """设置UI"""
        self.setWindowTitle("办公小工具整合平台")
        self.setMinimumSize(1200, 800)
        self.resize(1280, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 1, 0, 0)
        main_layout.setSpacing(0)

        self._nav_rail = NavigationRail()
        self._nav_rail.currentChanged.connect(self._on_nav_changed)
        main_layout.addWidget(self._nav_rail)

        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet(Theme.get_content_stack_stylesheet())
        main_layout.addWidget(self._content_stack, 1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")
        self._status_bar.setStyleSheet(Theme.get_status_bar_stylesheet())

        self._setup_default_nav_items()

        self.setStyleSheet(Theme.get_main_window_stylesheet())

    def _setup_default_nav_items(self) -> None:
        """设置默认导航项"""
        home_page = self._create_home_page()
        nodes_page = self._create_nodes_page()
        agent_page = self._create_agent_page()

        self.add_page("home", home_page)
        self.add_page("nodes", nodes_page)
        self.add_page("agent", agent_page)
        self.add_page("plugins", self._create_plugins_page())
        self.add_page("packages", self._create_packages_page())
        self.add_page("settings", self._create_settings_page())

        self._nav_rail.add_item("home", "首页", "🏠")
        self._nav_rail.add_item("nodes", "节点编辑器", "🔧")
        self._nav_rail.add_item("agent", "AI 助手", "🤖")
        self._nav_rail.add_item("plugins", "插件管理", "🧩")
        self._nav_rail.add_item("packages", "节点包", "📦")
        self._nav_rail.add_item("settings", "设置", "⚙️")

    def _create_home_page(self) -> QWidget:
        """创建首页"""
        self._home_page = HomePage()
        self._home_page.navigate_requested.connect(self._on_home_navigate)
        self._home_page.load_workflow_requested.connect(self._on_load_workflow_requested)
        return self._home_page

    def _create_nodes_page(self) -> QWidget:
        event_bus = self._app_context.event_bus if self._app_context else None
        self._node_editor_panel = NodeEditorPanel(self._node_engine, event_bus)
        self._node_editor_panel.set_graph(self._node_graph)
        self._node_editor_panel.workflow_saved.connect(self._on_workflow_saved)
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

    def _create_plugins_page(self) -> QWidget:
        """创建插件管理页面"""
        self._plugin_panel = PluginPanel()

        if self._app_context is not None:
            self._plugin_panel.set_plugin_manager(self._app_context.plugin_manager)

        self._plugin_panel.plugin_enabled_changed.connect(self._on_plugin_enabled_changed)
        self._plugin_panel.permission_edit_requested.connect(self._on_permission_edit_requested)
        self._plugin_panel.plugin_uninstall_requested.connect(self._on_plugin_uninstall_requested)
        self._plugin_panel.refresh_requested.connect(self._on_plugin_refresh_requested)

        return self._plugin_panel

    def _create_packages_page(self) -> QWidget:
        """创建节点包管理页面"""
        self._package_panel = PackagePanel(package_manager=self._package_manager)

        self._package_panel.package_enabled_changed.connect(self._on_package_enabled_changed)
        self._package_panel.package_installed.connect(self._on_package_installed)
        self._package_panel.package_updated.connect(self._on_package_updated)
        self._package_panel.package_deleted.connect(self._on_package_deleted)

        packages = self._package_manager.discover_packages()
        self._package_panel.set_packages(packages)

        return self._package_panel

    def _create_settings_page(self) -> QWidget:
        from src.ui.settings.settings_panel import SettingsPanel

        self._settings_panel = SettingsPanel(theme_manager=self._theme_manager)
        return self._settings_panel

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

        if item_id == "nodes" and hasattr(self, "_node_editor_panel") and self._node_editor_panel:
            self._node_editor_panel.set_graph(self._node_graph)

    def _on_home_navigate(self, item_id: str) -> None:
        """处理首页导航请求"""
        self._nav_rail.set_current(item_id)
        self.show_page(item_id)
        self._status_bar.showMessage(f"当前: {item_id}")

    def _on_load_workflow_requested(self, page_id: str, file_path: str) -> None:
        """处理加载工作流请求"""
        if not Path(file_path).exists():
            _logger.warning(f"工作流文件不存在: {file_path}")
            return

        self._nav_rail.set_current("nodes")
        self._node_editor_panel.load_workflow(file_path)
        self._status_bar.showMessage(f"已加载: {Path(file_path).name}")

        if hasattr(self, "_home_page") and self._node_graph:
            node_count = len(self._node_graph.nodes)
            self._home_page.add_recent_workflow(
                self._node_graph.id,
                title=self._node_graph.name or "未命名工作流",
                node_count=node_count,
                file_path=file_path,
            )

    def _on_workflow_saved(self, workflow_id: str, file_path: str) -> None:
        """处理工作流保存事件"""
        if hasattr(self, "_home_page"):
            node_count = len(self._node_graph.nodes) if self._node_graph else 0
            self._home_page.add_recent_workflow(
                workflow_id,
                title=self._node_graph.name or "未命名工作流",
                node_count=node_count,
                file_path=file_path,
            )
        else:
            _logger.info(f"工作流已保存: {self._node_graph.name or '未命名工作流'}")

        self._status_bar.showMessage(f"工作流已保存: {self._node_graph.name or '未命名工作流'}")

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

    def _on_plugin_enabled_changed(self, plugin_name: str, enabled: bool) -> None:
        """处理插件启用状态改变事件"""
        _logger.info(f"用户更改插件启用状态: {plugin_name} -> {enabled}")

        if self._app_context is None:
            return

        plugin_manager = self._app_context.plugin_manager

        if enabled:
            plugin_manager.enable_plugin(plugin_name)
            _logger.info(f"插件已启用: {plugin_name}")
        else:
            plugin_manager.disable_plugin(plugin_name)
            _logger.info(f"插件已禁用: {plugin_name}")

        self.refresh_plugin_panel()

    def _on_permission_edit_requested(self, plugin_name: str) -> None:
        _logger.info(f"用户请求修改权限: {plugin_name}")
        self._show_permission_dialog(plugin_name)

    def _on_plugin_refresh_requested(self) -> None:
        """Handle plugin refresh request"""
        _logger.info("用户请求刷新插件列表")
        if self._app_context is None:
            _logger.warning("AppContext未初始化，无法刷新插件")
            return
        plugin_manager = self._app_context.plugin_manager
        results = plugin_manager.refresh_plugins()
        self.refresh_plugin_panel()
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        self._status_bar.showMessage(f"插件刷新完成: {success_count}/{total_count} 成功")
        _logger.info(f"插件刷新完成: {success_count}/{total_count} 成功")

    def _on_plugin_uninstall_requested(self, plugin_name: str) -> None:
        """Handle plugin uninstall request"""
        _logger.info(f"用户请求卸载插件: {plugin_name}")
        if self._app_context is None:
            _logger.warning("AppContext未初始化，无法卸载插件")
            return
        plugin_manager = self._app_context.plugin_manager
        success = plugin_manager.uninstall_plugin(plugin_name)
        if success:
            self._status_bar.showMessage(f"插件已卸载: {plugin_name}")
            self.refresh_plugin_panel()
        else:
            QMessageBox.warning(self, "失败", f"卸载插件 {plugin_name} 失败")

    def _show_permission_dialog(self, plugin_name: str) -> None:
        if self._app_context is None:
            _logger.warning("AppContext未初始化，无法显示权限对话框")
            return

        from src.ui.plugins.permission_dialog import PermissionRequestDialog

        plugin_manager = self._app_context.plugin_manager

        discovered = plugin_manager.get_discovered_plugins()

        if plugin_name not in discovered:
            _logger.warning(f"插件未发现: {plugin_name}")
            return

        plugin_info = discovered[plugin_name]
        requested_permissions = (
            plugin_info.plugin_class.get_required_permissions()
            if plugin_info.plugin_class
            else PermissionSet.empty()
        )

        granted_permissions = self._permission_repository.get_permissions(plugin_name)

        plugin_info_dict = {
            "version": plugin_info.plugin_class.version if plugin_info.plugin_class else "?.?.?",
            "description": plugin_info.plugin_class.description if plugin_info.plugin_class else "",
            "author": plugin_info.plugin_class.author if plugin_info.plugin_class else "Unknown",
        }

        dialog = PermissionRequestDialog(
            plugin_name=plugin_name,
            plugin_info=plugin_info_dict,
            permissions=requested_permissions.permissions,
            granted_permissions=granted_permissions,
            parent=self,
        )

        if dialog.exec():
            granted = dialog.get_granted_permissions()
            if granted:
                self._permission_repository.grant_permissions(plugin_name, granted)
                _logger.info(
                    f"权限已更新: {plugin_name} -> {[p.value for p in granted_permissions]}"
                )
            else:
                self._permission_repository.revoke_all_permissions(plugin_name)
                _logger.info(f"已清空所有权限: {plugin_name}")
        else:
            _logger.debug("用户取消了权限对话框")

    def refresh_plugin_panel(self) -> None:
        if not hasattr(self, "_plugin_panel"):
            return

        if self._app_context is not None:
            plugin_manager = self._app_context.plugin_manager
            discovered = plugin_manager.get_discovered_plugins()

            enabled_status = {}
            permissions = {}
            for name in discovered:
                enabled_status[name] = self._plugin_repository.get_enabled(name)
                permissions[name] = self._permission_repository.get_permissions(name)
        else:
            discovered = {}
            enabled_status = {}
            permissions = {}

        self._plugin_panel.set_plugins(discovered, enabled_status, permissions)

    def _on_package_enabled_changed(self, package_id: str, enabled: bool) -> None:
        """处理包启用状态改变事件"""
        _logger.info(f"用户更改包启用状态: {package_id} -> {enabled}")

    def _on_package_installed(self, package_id: str) -> None:
        """处理包安装完成事件"""
        _logger.info(f"包安装完成: {package_id}")
        self._status_bar.showMessage(f"包已安装: {package_id}")

    def _on_package_updated(self, package_id: str) -> None:
        """处理包更新完成事件"""
        _logger.info(f"包更新完成: {package_id}")
        self._status_bar.showMessage(f"包已更新: {package_id}")

    def _on_package_deleted(self, package_id: str) -> None:
        """处理包删除完成事件"""
        _logger.info(f"包已删除: {package_id}")
        self._status_bar.showMessage(f"包已删除: {package_id}")

    def closeEvent(self, event) -> None:
        _logger.info("主窗口关闭")
        super().closeEvent(event)

    def _on_theme_changed(self, theme_name: str) -> None:
        self.setStyleSheet(Theme.get_main_window_stylesheet())
        self._content_stack.setStyleSheet(Theme.get_content_stack_stylesheet())
        self._status_bar.setStyleSheet(Theme.get_status_bar_stylesheet())
        theme_display = "深色" if theme_name == "dark" else "浅色"
        self._status_bar.showMessage(f"主题已切换为: {theme_display}")
