# -*- coding: utf-8 -*-
"""
权限代理模块

提供插件访问应用上下文的权限控制包装器：
- PermissionProxy: 包装AppContext，提供权限检查
- GuardedEventBus: 包装EventBus，控制事件订阅/发布权限
- GuardedNodeEngine: 包装NodeEngine，控制节点操作权限
- GuardedDatabase: 包装Database，控制存储访问权限

使用方式：
    from src.core.permission_proxy import PermissionProxy

    # 创建权限代理
    proxy = PermissionProxy(
        context=app_context,
        plugin_name="my_plugin",
        granted_permissions={Permission.FILE_READ, Permission.EVENT_SUBSCRIBE}
    )

    # 通过代理访问（会自动检查权限）
    bus = proxy.event_bus  # 返回 GuardedEventBus
    bus.subscribe(EventType.APP_STARTED, handler)  # 检查 EVENT_SUBSCRIBE 权限
"""

from typing import Callable, List, Optional, Set, TYPE_CHECKING

from src.core.app_context import AppContext
from src.core.event_bus import EventBus, EventType
from src.core.permission_manager import Permission, PermissionDeniedError
from src.engine.node_engine import NodeEngine
from src.engine.node_graph import NodeGraph
from src.storage.database import Database
from src.storage.repositories import PluginRepository

if TYPE_CHECKING:
    from src.agent.tool_registry import AgentToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from src.engine.definitions import NodeDefinition


class GuardedEventBus:
    """
    受保护的事件总线

    包装EventBus，在订阅和发布操作前检查权限：
    - subscribe(): 需要 EVENT_SUBSCRIBE 权限
    - publish(): 需要 EVENT_PUBLISH 权限
    - unsubscribe(): 无需权限检查
    - get_subscribers_count(): 无需权限检查

    Attributes:
        _event_bus: 被包装的EventBus实例
        _granted_permissions: 已授权的权限集合
        _plugin_name: 插件名称（用于错误消息）
    """

    def __init__(
        self,
        event_bus: EventBus,
        granted_permissions: Set[Permission],
        plugin_name: str,
    ):
        """
        初始化受保护的事件总线

        Args:
            event_bus: 要包装的EventBus实例
            granted_permissions: 已授权的权限集合
            plugin_name: 插件名称
        """
        self._event_bus = event_bus
        self._granted_permissions = granted_permissions
        self._plugin_name = plugin_name

    def subscribe(self, event_type: EventType, handler) -> str:
        """
        订阅事件（需要 EVENT_SUBSCRIBE 权限）

        Args:
            event_type: 要订阅的事件类型
            handler: 事件处理函数

        Returns:
            订阅ID

        Raises:
            PermissionDeniedError: 没有 EVENT_SUBSCRIBE 权限时
        """
        if Permission.EVENT_SUBSCRIBE not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.EVENT_SUBSCRIBE,
                f"插件 '{self._plugin_name}' 需要 EVENT_SUBSCRIBE 权限才能订阅事件",
            )
        return self._event_bus.subscribe(event_type, handler)

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅（无需权限检查）

        Args:
            subscription_id: 订阅ID

        Returns:
            是否成功取消
        """
        return self._event_bus.unsubscribe(subscription_id)

    def publish(self, event_type: EventType, data=None) -> None:
        """
        发布事件（需要 EVENT_PUBLISH 权限）

        Args:
            event_type: 要发布的事件类型
            data: 事件数据

        Raises:
            PermissionDeniedError: 没有 EVENT_PUBLISH 权限时
        """
        if Permission.EVENT_PUBLISH not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.EVENT_PUBLISH,
                f"插件 '{self._plugin_name}' 需要 EVENT_PUBLISH 权限才能发布事件",
            )
        self._event_bus.publish(event_type, data)

    def get_subscribers_count(self, event_type: EventType) -> int:
        """
        获取订阅者数量（无需权限检查）

        Args:
            event_type: 事件类型

        Returns:
            订阅者数量
        """
        return self._event_bus.get_subscribers_count(event_type)


class GuardedNodeEngine:
    """
    受保护的节点引擎

    包装NodeEngine，在操作前检查权限：
    - get_node_definition(): 需要 NODE_READ 权限
    - get_all_node_types(): 需要 NODE_READ 权限
    - get_available_nodes(): 需要 NODE_READ 权限
    - register_node_type(): 需要 NODE_REGISTER 权限
    - unregister_node_type(): 需要 NODE_REGISTER 权限
    - execute_node(): 无需权限检查
    - execute_graph(): 无需权限检查

    Attributes:
        _node_engine: 被包装的NodeEngine实例
        _granted_permissions: 已授权的权限集合
        _plugin_name: 插件名称
    """

    def __init__(
        self,
        node_engine: NodeEngine,
        granted_permissions: Set[Permission],
        plugin_name: str,
    ):
        """
        初始化受保护的节点引擎

        Args:
            node_engine: 要包装的NodeEngine实例
            granted_permissions: 已授权的权限集合
            plugin_name: 插件名称
        """
        self._node_engine = node_engine
        self._granted_permissions = granted_permissions
        self._plugin_name = plugin_name

    def get_node_definition(self, node_type: str) -> Optional["NodeDefinition"]:
        """
        获取节点定义（需要 NODE_READ 权限）

        Args:
            node_type: 节点类型标识

        Returns:
            节点定义，不存在则返回 None

        Raises:
            PermissionDeniedError: 没有 NODE_READ 权限时
        """
        if Permission.NODE_READ not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.NODE_READ,
                f"插件 '{self._plugin_name}' 需要 NODE_READ 权限才能读取节点信息",
            )
        return self._node_engine.get_node_definition(node_type)

    def get_all_node_types(self) -> list:
        """
        获取所有节点类型（需要 NODE_READ 权限）

        Returns:
            节点定义列表

        Raises:
            PermissionDeniedError: 没有 NODE_READ 权限时
        """
        if Permission.NODE_READ not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.NODE_READ,
                f"插件 '{self._plugin_name}' 需要 NODE_READ 权限才能读取节点信息",
            )
        return self._node_engine.get_all_node_types()

    def get_available_nodes(self) -> list:
        """
        获取所有可用节点信息（需要 NODE_READ 权限）

        Returns:
            节点信息字典列表

        Raises:
            PermissionDeniedError: 没有 NODE_READ 权限时
        """
        if Permission.NODE_READ not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.NODE_READ,
                f"插件 '{self._plugin_name}' 需要 NODE_READ 权限才能读取节点信息",
            )
        return self._node_engine.get_available_nodes()

    def register_node_type(self, definition: "NodeDefinition") -> None:
        """
        注册节点类型（需要 NODE_REGISTER 权限）

        Args:
            definition: 节点定义

        Raises:
            PermissionDeniedError: 没有 NODE_REGISTER 权限时
        """
        if Permission.NODE_REGISTER not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.NODE_REGISTER,
                f"插件 '{self._plugin_name}' 需要 NODE_REGISTER 权限才能注册节点",
            )
        self._node_engine.register_node_type(definition)

    def unregister_node_type(self, node_type: str) -> bool:
        """
        注销节点类型（需要 NODE_REGISTER 权限）

        Args:
            node_type: 节点类型标识

        Returns:
            是否成功注销

        Raises:
            PermissionDeniedError: 没有 NODE_REGISTER 权限时
        """
        if Permission.NODE_REGISTER not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.NODE_REGISTER,
                f"插件 '{self._plugin_name}' 需要 NODE_REGISTER 权限才能注销节点",
            )
        return self._node_engine.unregister_node_type(node_type)

    def execute_node(self, node, graph):
        """
        执行单个节点（无需权限检查）

        Args:
            node: 要执行的节点
            graph: 所属的图

        Returns:
            执行结果
        """
        return self._node_engine.execute_node(node, graph)

    def execute_graph(self, graph):
        """
        执行整个工作流图（无需权限检查）

        Args:
            graph: 要执行的图

        Returns:
            节点ID到执行结果的映射
        """
        return self._node_engine.execute_graph(graph)


class GuardedDatabase:
    """
    受保护的数据库

    包装Database，在操作前检查权限：
    - get_session(): 需要 STORAGE_READ 权限
    - session 属性: 需要 STORAGE_READ 权限
    - drop_tables(): 禁止访问，抛出 PermissionDeniedError
    - create_tables(): 无需权限检查
    - close(): 无需权限检查

    Attributes:
        _database: 被包装的Database实例
        _granted_permissions: 已授权的权限集合
        _plugin_name: 插件名称
    """

    def __init__(
        self,
        database: Database,
        granted_permissions: Set[Permission],
        plugin_name: str,
    ):
        """
        初始化受保护的数据库

        Args:
            database: 要包装的Database实例
            granted_permissions: 已授权的权限集合
            plugin_name: 插件名称
        """
        self._database = database
        self._granted_permissions = granted_permissions
        self._plugin_name = plugin_name

    def get_session(self) -> "Session":
        """
        获取数据库会话（需要 STORAGE_READ 权限）

        Returns:
            数据库会话

        Raises:
            PermissionDeniedError: 没有 STORAGE_READ 权限时
        """
        if Permission.STORAGE_READ not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.STORAGE_READ,
                f"插件 '{self._plugin_name}' 需要 STORAGE_READ 权限才能访问数据库",
            )
        return self._database.get_session()

    @property
    def session(self):
        """
        获取会话上下文管理器（需要 STORAGE_READ 权限）

        Returns:
            会话上下文管理器

        Raises:
            PermissionDeniedError: 没有 STORAGE_READ 权限时
        """
        if Permission.STORAGE_READ not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.STORAGE_READ,
                f"插件 '{self._plugin_name}' 需要 STORAGE_READ 权限才能访问数据库",
            )
        return self._database.session()

    def drop_tables(self) -> None:
        """
        删除所有表（禁止访问）

        Raises:
            PermissionDeniedError: 始终抛出，此操作被禁止
        """
        raise PermissionDeniedError(
            Permission.STORAGE_WRITE, f"插件 '{self._plugin_name}' 被禁止执行 drop_tables() 操作"
        )

    def create_tables(self) -> None:
        """
        创建所有表（无需权限检查）

        Note:
            如果表已存在则不会重新创建
        """
        self._database.create_tables()

    def close(self) -> None:
        """关闭数据库连接（无需权限检查）"""
        self._database.close()


class GuardedConfigStore:
    def __init__(
        self,
        repository: PluginRepository,
        plugin_name: str,
        granted_permissions: Set[Permission],
    ):
        """
        初始化受保护的配置存储

        Args:
            repository: PluginRepository 实例
            plugin_name: 插件名称
            granted_permissions: 已授权的权限集合
        """
        self._repository = repository
        self._plugin_name = plugin_name
        self._granted_permissions = granted_permissions

        self._config_cache: Optional[dict] = None

    def get(self) -> dict:
        if Permission.STORAGE_READ not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.STORAGE_READ,
                f"插件 '{self._plugin_name}' 需要 STORAGE_READ 权限才能读取配置",
            )
        return self._repository.get_config(self._plugin_name)

    def set(self, config: dict) -> bool:
        if Permission.STORAGE_WRITE not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.STORAGE_WRITE,
                f"插件 '{self._plugin_name}' 需要 STORAGE_WRITE 权限才能写入配置",
            )
        return self._repository.set_config(self._plugin_name, config)

    def update(self, updates: dict) -> bool:
        if Permission.STORAGE_WRITE not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.STORAGE_WRITE,
                f"插件 '{self._plugin_name}' 需要 STORAGE_WRITE 权限才能更新配置",
            )
        return self._repository.update_config(self._plugin_name, updates)


class GuardedToolRegistry:
    """
    受保护的 Agent 工具注册中心

    包装 AgentToolRegistry，在操作前检查权限：
    - register(): 需要 AGENT_TOOL 权限
    - unregister(): 需要 AGENT_TOOL 权限
    - get_all_tools(): 无需权限检查（只读）
    - has_group(): 无需权限检查（只读）
    """

    def __init__(
        self,
        tool_registry: "AgentToolRegistry",
        granted_permissions: Set[Permission],
        plugin_name: str,
    ):
        self._tool_registry = tool_registry
        self._granted_permissions = granted_permissions
        self._plugin_name = plugin_name

    def register(self, group_name: str, tools: List[Callable]) -> None:
        """
        注册一组工具函数（需要 AGENT_TOOL 权限）

        Args:
            group_name: 工具组名称
            tools: 工具函数列表

        Raises:
            PermissionDeniedError: 没有 AGENT_TOOL 权限时
        """
        if Permission.AGENT_TOOL not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.AGENT_TOOL,
                f"插件 '{self._plugin_name}' 需要 AGENT_TOOL 权限才能注册工具",
            )
        self._tool_registry.register(group_name, tools)

    def unregister(self, group_name: str) -> None:
        """
        注销一组工具函数（需要 AGENT_TOOL 权限）

        Args:
            group_name: 工具组名称

        Raises:
            PermissionDeniedError: 没有 AGENT_TOOL 权限时
        """
        if Permission.AGENT_TOOL not in self._granted_permissions:
            raise PermissionDeniedError(
                Permission.AGENT_TOOL,
                f"插件 '{self._plugin_name}' 需要 AGENT_TOOL 权限才能注销工具",
            )
        self._tool_registry.unregister(group_name)

    def get_all_tools(self) -> List[Callable]:
        """获取所有已注册的工具函数（无需权限检查）"""
        return self._tool_registry.get_all_tools()

    def has_group(self, group_name: str) -> bool:
        """检查工具组是否已注册（无需权限检查）"""
        return self._tool_registry.has_group(group_name)


class PermissionProxy:
    """
    权限代理

    包装AppContext，为插件提供受限的访问入口：
    - event_bus: 返回 GuardedEventBus
    - node_engine: 返回 GuardedNodeEngine
    - database: 返回 GuardedDatabase
    - permission_manager: 返回 None（防止权限提升）
    - plugin_manager: 返回 None（防止权限提升）
    - is_initialized: 委托给原始上下文

    提供权限检查方法：
    - check_permission(): 检查是否有某权限
    - require_permission(): 要求权限，无权限时抛出异常

    Attributes:
        plugin_name: 插件名称
        granted_permissions: 已授权的权限集合
        _context: 被包装的AppContext实例
    """

    def __init__(
        self,
        context: AppContext,
        plugin_name: str,
        granted_permissions: Set[Permission],
        config_repository: Optional[PluginRepository] = None,
    ):
        """
        初始化权限代理

        Args:
            context: 要包装的AppContext实例
            plugin_name: 插件名称
            granted_permissions: 已授权的权限集合
            config_repository: 插件配置存储库（可选）
        """
        self.plugin_name = plugin_name
        self.granted_permissions = granted_permissions
        self._context = context
        self._config_repository = config_repository

    @property
    def config(self) -> Optional[GuardedConfigStore]:
        if self._config_repository is None:
            return None
        return GuardedConfigStore(
            repository=self._config_repository,
            plugin_name=self.plugin_name,
            granted_permissions=self.granted_permissions,
        )

    @property
    def event_bus(self) -> GuardedEventBus:
        """
        获取受保护的事件总线

        Returns:
            GuardedEventBus 实例
        """
        return GuardedEventBus(
            event_bus=self._context.event_bus,
            granted_permissions=self.granted_permissions,
            plugin_name=self.plugin_name,
        )

    @property
    def node_engine(self) -> GuardedNodeEngine:
        """
        获取受保护的节点引擎

        Returns:
            GuardedNodeEngine 实例
        """
        return GuardedNodeEngine(
            node_engine=self._context.node_engine,
            granted_permissions=self.granted_permissions,
            plugin_name=self.plugin_name,
        )

    @property
    def node_graph(self) -> Optional["NodeGraph"]:
        """
        获取当前工作流图（需要 NODE_READ 权限）

        Returns:
            当前 NodeGraph 实例

        Raises:
            PermissionDeniedError: 没有 NODE_READ 权限时
        """
        if Permission.NODE_READ not in self.granted_permissions:
            raise PermissionDeniedError(
                Permission.NODE_READ,
                f"插件 '{self.plugin_name}' 需要 NODE_READ 权限才能访问工作流图",
            )
        return self._context.node_graph

    @property
    def tool_registry(self) -> GuardedToolRegistry:
        """
        获取受保护的工具注册中心

        Returns:
            GuardedToolRegistry 实例
        """
        return GuardedToolRegistry(
            tool_registry=self._context.tool_registry,
            granted_permissions=self.granted_permissions,
            plugin_name=self.plugin_name,
        )

    @property
    def database(self) -> GuardedDatabase:
        return GuardedDatabase(
            database=self._context.database,
            granted_permissions=self.granted_permissions,
            plugin_name=self.plugin_name,
        )

    @property
    def permission_manager(self) -> None:
        """
        获取权限管理器（始终返回 None，防止权限提升）

        Returns:
            None
        """
        return None

    @property
    def plugin_manager(self) -> None:
        """
        获取插件管理器（始终返回 None，防止权限提升）

        Returns:
            None
        """
        return None

    @property
    def is_initialized(self) -> bool:
        """
        检查上下文是否已初始化

        Returns:
            是否已初始化
        """
        return self._context.is_initialized

    def check_permission(self, permission: Permission) -> bool:
        """
        检查是否有某权限

        Args:
            permission: 要检查的权限

        Returns:
            是否拥有该权限
        """
        return permission in self.granted_permissions

    def require_permission(self, permission: Permission) -> None:
        """
        要求权限，无权限时抛出异常

        Args:
            permission: 要求的权限

        Raises:
            PermissionDeniedError: 没有该权限时
        """
        if not self.check_permission(permission):
            raise PermissionDeniedError(
                permission, f"插件 '{self.plugin_name}' 需要权限 '{permission.value}'"
            )
