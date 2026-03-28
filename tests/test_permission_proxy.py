# -*- coding: utf-8 -*-
"""权限代理模块测试

测试 PermissionProxy 及其受保护的包装器：
- GuardedEventBus: 事件订阅/发布权限检查
- GuardedNodeEngine: 节点读取/注册权限检查
- GuardedDatabase: 数据库访问权限检查
- PermissionProxy: 代理集成测试
- Blocked managers: 阻止访问权限管理器和插件管理器
- Plugin load integration: 插件加载集成测试
"""

from pathlib import Path
from typing import Set
from unittest.mock import MagicMock, patch

import pytest

from src.core.event_bus import EventBus, EventType
from src.core.permission_manager import Permission, PermissionDeniedError, PermissionManager
from src.core.permission_proxy import (
    GuardedDatabase,
    GuardedEventBus,
    GuardedNodeEngine,
    PermissionProxy,
)
from src.core.plugin_base import PluginBase
from src.core.plugin_manager import PluginInfo, PluginManager
from src.engine.node_engine import NodeEngine
from src.storage.database import Database


# ==================== Fixtures ====================


@pytest.fixture
def event_bus() -> EventBus:
    """创建事件总线"""
    return EventBus()


@pytest.fixture
def node_engine() -> NodeEngine:
    """创建节点引擎"""
    return NodeEngine()


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """创建数据库"""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.create_tables()
    yield db
    db.close()


@pytest.fixture
def permission_manager() -> PermissionManager:
    """创建权限管理器"""
    return PermissionManager()


@pytest.fixture
def plugin_name() -> str:
    """测试插件名称"""
    return "test_plugin"


@pytest.fixture
def granted_permissions() -> Set[Permission]:
    """已授权的权限集合"""
    return {
        Permission.EVENT_SUBSCRIBE,
        Permission.EVENT_PUBLISH,
        Permission.NODE_READ,
        Permission.NODE_REGISTER,
        Permission.STORAGE_READ,
    }


# ==================== GuardedEventBus Tests ====================


class TestGuardedEventBus:
    """测试 GuardedEventBus 类"""

    def test_subscribe_with_permission(self, event_bus: EventBus, plugin_name: str):
        """测试有权限时订阅事件成功"""
        # 授权 EVENT_SUBSCRIBE 权限
        granted = {Permission.EVENT_SUBSCRIBE}
        guarded_bus = GuardedEventBus(event_bus, granted, plugin_name)

        # 订阅事件
        sub_id = guarded_bus.subscribe(EventType.APP_STARTED, lambda e: None)

        assert sub_id is not None
        assert event_bus.get_subscribers_count(EventType.APP_STARTED) == 1

    def test_subscribe_without_permission(self, event_bus: EventBus, plugin_name: str):
        """测试无权限时订阅事件抛出异常"""
        # 不授权 EVENT_SUBSCRIBE 权限
        granted: Set[Permission] = set()
        guarded_bus = GuardedEventBus(event_bus, granted, plugin_name)

        # 尝试订阅事件，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_bus.subscribe(EventType.APP_STARTED, lambda e: None)

        assert exc_info.value.permission == Permission.EVENT_SUBSCRIBE
        assert plugin_name in str(exc_info.value.message)

    def test_publish_with_permission(self, event_bus: EventBus, plugin_name: str):
        """测试有权限时发布事件成功"""
        # 授权 EVENT_PUBLISH 权限
        granted = {Permission.EVENT_PUBLISH}
        guarded_bus = GuardedEventBus(event_bus, granted, plugin_name)

        # 先订阅一个处理器
        called = []
        event_bus.subscribe(EventType.APP_STARTED, lambda e: called.append(e))

        # 发布事件
        guarded_bus.publish(EventType.APP_STARTED, {"test": "data"})

        assert len(called) == 1
        assert called[0].data == {"test": "data"}

    def test_publish_without_permission(self, event_bus: EventBus, plugin_name: str):
        """测试无权限时发布事件抛出异常"""
        # 不授权 EVENT_PUBLISH 权限
        granted: Set[Permission] = set()
        guarded_bus = GuardedEventBus(event_bus, granted, plugin_name)

        # 尝试发布事件，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_bus.publish(EventType.APP_STARTED, {"test": "data"})

        assert exc_info.value.permission == Permission.EVENT_PUBLISH
        assert plugin_name in str(exc_info.value.message)

    def test_unsubscribe_no_permission_required(self, event_bus: EventBus, plugin_name: str):
        """测试取消订阅不需要权限"""
        # 不授权任何权限
        granted: Set[Permission] = set()
        guarded_bus = GuardedEventBus(event_bus, granted, plugin_name)

        # 先在原始事件总线上订阅
        sub_id = event_bus.subscribe(EventType.APP_STARTED, lambda e: None)

        # 通过 GuardedEventBus 取消订阅（不需要权限）
        result = guarded_bus.unsubscribe(sub_id)

        assert result is True
        assert event_bus.get_subscribers_count(EventType.APP_STARTED) == 0

    def test_get_subscribers_count_no_permission_required(
        self, event_bus: EventBus, plugin_name: str
    ):
        """测试获取订阅者数量不需要权限"""
        # 不授权任何权限
        granted: Set[Permission] = set()
        guarded_bus = GuardedEventBus(event_bus, granted, plugin_name)

        # 先在原始事件总线上订阅
        event_bus.subscribe(EventType.APP_STARTED, lambda e: None)

        # 通过 GuardedEventBus 获取订阅者数量（不需要权限）
        count = guarded_bus.get_subscribers_count(EventType.APP_STARTED)

        assert count == 1

    def test_subscribe_and_publish_with_both_permissions(
        self, event_bus: EventBus, plugin_name: str
    ):
        """测试同时有订阅和发布权限"""
        granted = {Permission.EVENT_SUBSCRIBE, Permission.EVENT_PUBLISH}
        guarded_bus = GuardedEventBus(event_bus, granted, plugin_name)

        # 订阅
        called = []
        sub_id = guarded_bus.subscribe(EventType.APP_STARTED, lambda e: called.append(e))

        # 发布
        guarded_bus.publish(EventType.APP_STARTED, {"test": "data"})

        assert len(called) == 1
        assert called[0].data == {"test": "data"}

        # 取消订阅
        result = guarded_bus.unsubscribe(sub_id)
        assert result is True


# ==================== GuardedNodeEngine Tests ====================


class TestGuardedNodeEngine:
    """测试 GuardedNodeEngine 类"""

    def test_get_node_definition_with_permission(self, node_engine: NodeEngine, plugin_name: str):
        """测试有权限时获取节点定义成功"""
        # 授权 NODE_READ 权限
        granted = {Permission.NODE_READ}
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 获取不存在的节点定义（返回 None，但不抛出异常）
        result = guarded_engine.get_node_definition("nonexistent_node")

        assert result is None

    def test_get_node_definition_without_permission(
        self, node_engine: NodeEngine, plugin_name: str
    ):
        """测试无权限时获取节点定义抛出异常"""
        # 不授权 NODE_READ 权限
        granted: Set[Permission] = set()
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 尝试获取节点定义，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_engine.get_node_definition("some_node")

        assert exc_info.value.permission == Permission.NODE_READ
        assert plugin_name in str(exc_info.value.message)

    def test_get_all_node_types_with_permission(self, node_engine: NodeEngine, plugin_name: str):
        """测试有权限时获取所有节点类型成功"""
        # 授权 NODE_READ 权限
        granted = {Permission.NODE_READ}
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 获取所有节点类型
        result = guarded_engine.get_all_node_types()

        assert isinstance(result, list)

    def test_get_all_node_types_without_permission(self, node_engine: NodeEngine, plugin_name: str):
        """测试无权限时获取所有节点类型抛出异常"""
        # 不授权 NODE_READ 权限
        granted: Set[Permission] = set()
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 尝试获取所有节点类型，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_engine.get_all_node_types()

        assert exc_info.value.permission == Permission.NODE_READ

    def test_get_available_nodes_with_permission(self, node_engine: NodeEngine, plugin_name: str):
        """测试有权限时获取可用节点成功"""
        # 授权 NODE_READ 权限
        granted = {Permission.NODE_READ}
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 获取可用节点
        result = guarded_engine.get_available_nodes()

        assert isinstance(result, list)

    def test_get_available_nodes_without_permission(
        self, node_engine: NodeEngine, plugin_name: str
    ):
        """测试无权限时获取可用节点抛出异常"""
        # 不授权 NODE_READ 权限
        granted: Set[Permission] = set()
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 尝试获取可用节点，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_engine.get_available_nodes()

        assert exc_info.value.permission == Permission.NODE_READ

    def test_register_node_type_with_permission(self, node_engine: NodeEngine, plugin_name: str):
        """测试有权限时注册节点类型成功"""
        # 授权 NODE_REGISTER 权限
        granted = {Permission.NODE_REGISTER}
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 创建模拟节点定义
        from src.engine.definitions import NodeDefinition, PortDefinition, PortType

        definition = NodeDefinition(
            node_type="test.custom_node",
            display_name="自定义节点",
            description="测试节点",
            category="test",
            inputs=[PortDefinition("input1", PortType.STRING, "输入")],
            outputs=[PortDefinition("output1", PortType.STRING, "输出")],
            execute=lambda input1: {"output1": input1},
        )

        # 注册节点类型
        guarded_engine.register_node_type(definition)

        # 验证注册成功
        result = node_engine.get_node_definition("test.custom_node")
        assert result is not None
        assert result.node_type == "test.custom_node"

    def test_register_node_type_without_permission(self, node_engine: NodeEngine, plugin_name: str):
        """测试无权限时注册节点类型抛出异常"""
        # 不授权 NODE_REGISTER 权限
        granted: Set[Permission] = set()
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 创建模拟节点定义
        from src.engine.definitions import NodeDefinition, PortDefinition, PortType

        definition = NodeDefinition(
            node_type="test.custom_node",
            display_name="自定义节点",
            description="测试节点",
            category="test",
            inputs=[PortDefinition("input1", PortType.STRING, "输入")],
            outputs=[PortDefinition("output1", PortType.STRING, "输出")],
            execute=lambda input1: {"output1": input1},
        )

        # 尝试注册节点类型，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_engine.register_node_type(definition)

        assert exc_info.value.permission == Permission.NODE_REGISTER
        assert plugin_name in str(exc_info.value.message)

    def test_unregister_node_type_with_permission(self, node_engine: NodeEngine, plugin_name: str):
        """测试有权限时注销节点类型成功"""
        # 授权 NODE_REGISTER 权限
        granted = {Permission.NODE_REGISTER}
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 先注册一个节点
        from src.engine.definitions import NodeDefinition, PortDefinition, PortType

        definition = NodeDefinition(
            node_type="test.temp_node",
            display_name="临时节点",
            description="测试节点",
            category="test",
            inputs=[PortDefinition("input1", PortType.STRING, "输入")],
            outputs=[PortDefinition("output1", PortType.STRING, "输出")],
            execute=lambda input1: {"output1": input1},
        )
        node_engine.register_node_type(definition)

        # 注销节点类型
        result = guarded_engine.unregister_node_type("test.temp_node")

        assert result is True
        assert node_engine.get_node_definition("test.temp_node") is None

    def test_unregister_node_type_without_permission(
        self, node_engine: NodeEngine, plugin_name: str
    ):
        """测试无权限时注销节点类型抛出异常"""
        # 不授权 NODE_REGISTER 权限
        granted: Set[Permission] = set()
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 尝试注销节点类型，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_engine.unregister_node_type("some_node")

        assert exc_info.value.permission == Permission.NODE_REGISTER
        assert plugin_name in str(exc_info.value.message)

    def test_execute_node_no_permission_required(self, node_engine: NodeEngine, plugin_name: str):
        """测试执行节点不需要权限"""
        # 不授权任何权限
        granted: Set[Permission] = set()
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 创建模拟节点和图
        mock_node = MagicMock()
        mock_graph = MagicMock()

        # 执行节点（不需要权限）
        # 注意：这里只是测试权限检查，实际执行可能会失败
        # 但不应该因为权限问题抛出异常
        try:
            guarded_engine.execute_node(mock_node, mock_graph)
        except PermissionDeniedError:
            pytest.fail("execute_node 不应该需要权限检查")

    def test_execute_graph_no_permission_required(self, node_engine: NodeEngine, plugin_name: str):
        """测试执行图不需要权限"""
        # 不授权任何权限
        granted: Set[Permission] = set()
        guarded_engine = GuardedNodeEngine(node_engine, granted, plugin_name)

        # 创建模拟图
        mock_graph = MagicMock()

        # 执行图（不需要权限）
        try:
            guarded_engine.execute_graph(mock_graph)
        except PermissionDeniedError:
            pytest.fail("execute_graph 不应该需要权限检查")


# ==================== GuardedDatabase Tests ====================


class TestGuardedDatabase:
    """测试 GuardedDatabase 类"""

    def test_get_session_with_permission(self, database: Database, plugin_name: str):
        """测试有权限时获取会话成功"""
        # 授权 STORAGE_READ 权限
        granted = {Permission.STORAGE_READ}
        guarded_db = GuardedDatabase(database, granted, plugin_name)

        # 获取会话
        session = guarded_db.get_session()

        assert session is not None
        session.close()

    def test_get_session_without_permission(self, database: Database, plugin_name: str):
        """测试无权限时获取会话抛出异常"""
        # 不授权 STORAGE_READ 权限
        granted: Set[Permission] = set()
        guarded_db = GuardedDatabase(database, granted, plugin_name)

        # 尝试获取会话，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_db.get_session()

        assert exc_info.value.permission == Permission.STORAGE_READ
        assert plugin_name in str(exc_info.value.message)

    def test_session_property_with_permission(self, database: Database, plugin_name: str):
        """测试有权限时访问 session 属性成功"""
        # 授权 STORAGE_READ 权限
        granted = {Permission.STORAGE_READ}
        guarded_db = GuardedDatabase(database, granted, plugin_name)

        # 访问 session 属性 - 需要调用返回的上下文管理器
        session_cm = guarded_db.session
        with session_cm as session:
            assert session is not None

    def test_session_property_without_permission(self, database: Database, plugin_name: str):
        """测试无权限时访问 session 属性抛出异常"""
        # 不授权 STORAGE_READ 权限
        granted: Set[Permission] = set()
        guarded_db = GuardedDatabase(database, granted, plugin_name)

        # 尝试访问 session 属性，应抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            _ = guarded_db.session

        assert exc_info.value.permission == Permission.STORAGE_READ
        assert plugin_name in str(exc_info.value.message)

    def test_drop_tables_always_denied(self, database: Database, plugin_name: str):
        """测试 drop_tables 始终被拒绝"""
        # 即使授权了所有权限
        granted = {Permission.STORAGE_READ, Permission.STORAGE_WRITE}
        guarded_db = GuardedDatabase(database, granted, plugin_name)

        # 尝试删除表，应始终抛出异常
        with pytest.raises(PermissionDeniedError) as exc_info:
            guarded_db.drop_tables()

        assert exc_info.value.permission == Permission.STORAGE_WRITE
        assert plugin_name in str(exc_info.value.message)

    def test_create_tables_no_permission_required(self, database: Database, plugin_name: str):
        """测试创建表不需要权限"""
        # 不授权任何权限
        granted: Set[Permission] = set()
        guarded_db = GuardedDatabase(database, granted, plugin_name)

        # 创建表（不需要权限）
        try:
            guarded_db.create_tables()
        except PermissionDeniedError:
            pytest.fail("create_tables 不应该需要权限检查")

    def test_close_no_permission_required(self, database: Database, plugin_name: str):
        """测试关闭数据库不需要权限"""
        # 不授权任何权限
        granted: Set[Permission] = set()
        guarded_db = GuardedDatabase(database, granted, plugin_name)

        # 关闭数据库（不需要权限）
        try:
            guarded_db.close()
        except PermissionDeniedError:
            pytest.fail("close 不应该需要权限检查")


# ==================== PermissionProxy Tests ====================


class TestPermissionProxy:
    """测试 PermissionProxy 类"""

    @pytest.fixture
    def mock_context(self, event_bus, node_engine, database):
        """创建模拟应用上下文"""
        context = MagicMock()
        context.event_bus = event_bus
        context.node_engine = node_engine
        context.database = database
        context.is_initialized = True
        return context

    def test_event_bus_returns_guarded_event_bus(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 event_bus 属性返回 GuardedEventBus"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        result = proxy.event_bus

        assert isinstance(result, GuardedEventBus)
        assert result._event_bus == mock_context.event_bus
        assert result._granted_permissions == granted_permissions
        assert result._plugin_name == plugin_name

    def test_node_engine_returns_guarded_node_engine(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 node_engine 属性返回 GuardedNodeEngine"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        result = proxy.node_engine

        assert isinstance(result, GuardedNodeEngine)
        assert result._node_engine == mock_context.node_engine
        assert result._granted_permissions == granted_permissions
        assert result._plugin_name == plugin_name

    def test_database_returns_guarded_database(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 database 属性返回 GuardedDatabase"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        result = proxy.database

        assert isinstance(result, GuardedDatabase)
        assert result._database == mock_context.database
        assert result._granted_permissions == granted_permissions
        assert result._plugin_name == plugin_name

    def test_permission_manager_returns_none(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 permission_manager 属性返回 None（防止权限提升）"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        result = proxy.permission_manager

        assert result is None

    def test_plugin_manager_returns_none(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 plugin_manager 属性返回 None（防止权限提升）"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        result = proxy.plugin_manager

        assert result is None

    def test_is_initialized_delegates_to_context(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 is_initialized 属性委托给原始上下文"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        result = proxy.is_initialized

        assert result == mock_context.is_initialized

    def test_check_permission_returns_true_when_granted(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 check_permission 在有权限时返回 True"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        result = proxy.check_permission(Permission.EVENT_SUBSCRIBE)

        assert result is True

    def test_check_permission_returns_false_when_not_granted(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 check_permission 在无权限时返回 False"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # FILE_READ 不在 granted_permissions 中
        result = proxy.check_permission(Permission.FILE_READ)

        assert result is False

    def test_require_permission_does_not_raise_when_granted(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 require_permission 在有权限时不抛出异常"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 不应抛出异常
        proxy.require_permission(Permission.EVENT_SUBSCRIBE)

    def test_require_permission_raises_when_not_granted(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 require_permission 在无权限时抛出异常"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # FILE_READ 不在 granted_permissions 中
        with pytest.raises(PermissionDeniedError) as exc_info:
            proxy.require_permission(Permission.FILE_READ)

        assert exc_info.value.permission == Permission.FILE_READ
        assert plugin_name in str(exc_info.value.message)

    def test_plugin_name_attribute(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 plugin_name 属性"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        assert proxy.plugin_name == plugin_name

    def test_granted_permissions_attribute(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试 granted_permissions 属性"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        assert proxy.granted_permissions == granted_permissions


# ==================== Blocked Managers Tests ====================


class TestBlockedManagers:
    """测试阻止访问管理器"""

    @pytest.fixture
    def mock_context(self, event_bus, node_engine, database):
        """创建模拟应用上下文"""
        context = MagicMock()
        context.event_bus = event_bus
        context.node_engine = node_engine
        context.database = database
        context.permission_manager = MagicMock()
        context.plugin_manager = MagicMock()
        context.is_initialized = True
        return context

    def test_cannot_access_permission_manager(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试无法通过代理访问权限管理器"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 代理应该返回 None
        assert proxy.permission_manager is None

        # 原始上下文有权限管理器
        assert mock_context.permission_manager is not None

    def test_cannot_access_plugin_manager(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试无法通过代理访问插件管理器"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 代理应该返回 None
        assert proxy.plugin_manager is None

        # 原始上下文有插件管理器
        assert mock_context.plugin_manager is not None

    def test_cannot_grant_permissions_via_proxy(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试无法通过代理授权限"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 无法访问权限管理器
        pm = proxy.permission_manager
        assert pm is None

        # 无法调用授权方法
        with pytest.raises(AttributeError):
            pm.grant("other_plugin", Permission.FILE_READ)  # type: ignore

    def test_cannot_load_plugins_via_proxy(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试无法通过代理加载插件"""
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 无法访问插件管理器
        plm = proxy.plugin_manager
        assert plm is None

        # 无法调用加载方法
        with pytest.raises(AttributeError):
            plm.load_plugin("other_plugin")  # type: ignore


# ==================== Plugin Load Integration Tests ====================


class TestPluginLoadIntegration:
    """测试插件加载集成"""

    @pytest.fixture
    def mock_context(self, event_bus, node_engine, database, permission_manager):
        """创建模拟应用上下文"""
        context = MagicMock()
        context.event_bus = event_bus
        context.node_engine = node_engine
        context.database = database
        context.permission_manager = permission_manager
        context.is_initialized = True
        return context

    def test_proxy_passed_to_plugin_on_load(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试插件加载时收到的是代理而非原始上下文"""

        # 创建一个测试插件
        class TestPlugin(PluginBase):
            name = "test_integration_plugin"
            version = "1.0.0"
            received_context = None

            def on_load(self, context):
                self.received_context = context

            def on_unload(self):
                pass

        # 创建代理
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 创建插件实例并调用 on_load
        plugin = TestPlugin()
        plugin.on_load(proxy)

        # 验证插件收到的是代理
        assert plugin.received_context is proxy
        assert isinstance(plugin.received_context, PermissionProxy)

    def test_plugin_can_use_guarded_event_bus(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试插件可以使用受保护的事件总线"""
        # 创建代理
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 获取受保护的事件总线
        guarded_bus = proxy.event_bus

        # 订阅事件（有权限）
        called = []
        sub_id = guarded_bus.subscribe(EventType.APP_STARTED, lambda e: called.append(e))

        # 发布事件（有权限）
        guarded_bus.publish(EventType.APP_STARTED, {"test": "data"})

        assert len(called) == 1
        assert called[0].data == {"test": "data"}

    def test_plugin_cannot_subscribe_without_permission(self, mock_context, plugin_name: str):
        """测试插件无权限时无法订阅事件"""
        # 不授权 EVENT_SUBSCRIBE 权限
        granted: Set[Permission] = set()
        proxy = PermissionProxy(mock_context, plugin_name, granted)

        # 获取受保护的事件总线
        guarded_bus = proxy.event_bus

        # 尝试订阅事件，应抛出异常
        with pytest.raises(PermissionDeniedError):
            guarded_bus.subscribe(EventType.APP_STARTED, lambda e: None)

    def test_plugin_can_check_own_permissions(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试插件可以检查自己的权限"""
        # 创建代理
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 检查权限
        assert proxy.check_permission(Permission.EVENT_SUBSCRIBE) is True
        assert proxy.check_permission(Permission.FILE_READ) is False

    def test_plugin_can_require_permissions(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试插件可以要求权限"""
        # 创建代理
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 有权限时不抛出异常
        proxy.require_permission(Permission.EVENT_SUBSCRIBE)

        # 无权限时抛出异常
        with pytest.raises(PermissionDeniedError):
            proxy.require_permission(Permission.FILE_READ)

    def test_full_plugin_workflow_with_proxy(
        self, mock_context, plugin_name: str, granted_permissions: Set[Permission]
    ):
        """测试完整的插件工作流程"""

        # 创建一个完整的测试插件
        class FullTestPlugin(PluginBase):
            name = "full_test_plugin"
            version = "1.0.0"
            subscription_id = None
            events_received = []

            def on_load(self, context):
                # 检查权限
                if context.check_permission(Permission.EVENT_SUBSCRIBE):
                    # 订阅事件
                    self.subscription_id = context.event_bus.subscribe(
                        EventType.APP_STARTED, self.on_app_started
                    )

            def on_unload(self):
                pass

            def on_app_started(self, event):
                self.events_received.append(event)

        # 创建代理
        proxy = PermissionProxy(mock_context, plugin_name, granted_permissions)

        # 创建并加载插件
        plugin = FullTestPlugin()
        plugin.on_load(proxy)

        # 验证订阅成功
        assert plugin.subscription_id is not None

        # 发布事件
        proxy.event_bus.publish(EventType.APP_STARTED, {"test": "data"})

        # 验证事件被接收
        assert len(plugin.events_received) == 1
        assert plugin.events_received[0].data == {"test": "data"}

    def test_proxy_with_empty_permissions(self, mock_context, plugin_name: str):
        """测试空权限的代理"""
        # 创建空权限代理
        granted: Set[Permission] = set()
        proxy = PermissionProxy(mock_context, plugin_name, granted)

        # 所有需要权限的操作都应该失败
        with pytest.raises(PermissionDeniedError):
            proxy.event_bus.subscribe(EventType.APP_STARTED, lambda e: None)

        with pytest.raises(PermissionDeniedError):
            proxy.event_bus.publish(EventType.APP_STARTED, {})

        with pytest.raises(PermissionDeniedError):
            proxy.node_engine.get_node_definition("test")

        with pytest.raises(PermissionDeniedError):
            proxy.node_engine.get_all_node_types()

        with pytest.raises(PermissionDeniedError):
            proxy.node_engine.get_available_nodes()

        with pytest.raises(PermissionDeniedError):
            proxy.node_engine.register_node_type(MagicMock())

        with pytest.raises(PermissionDeniedError):
            proxy.node_engine.unregister_node_type("test")

        with pytest.raises(PermissionDeniedError):
            proxy.database.get_session()

        with pytest.raises(PermissionDeniedError):
            _ = proxy.database.session

        # drop_tables 始终被拒绝
        with pytest.raises(PermissionDeniedError):
            proxy.database.drop_tables()

    def test_proxy_with_all_permissions(self, mock_context, plugin_name: str):
        """测试拥有所有权限的代理"""
        # 创建拥有所有权限的代理
        granted = {
            Permission.FILE_READ,
            Permission.FILE_WRITE,
            Permission.NETWORK,
            Permission.AGENT_TOOL,
            Permission.AGENT_MCP,
            Permission.AGENT_SKILL,
            Permission.AGENT_CHAT,
            Permission.EVENT_SUBSCRIBE,
            Permission.EVENT_PUBLISH,
            Permission.NODE_READ,
            Permission.NODE_REGISTER,
            Permission.STORAGE_READ,
            Permission.STORAGE_WRITE,
        }
        proxy = PermissionProxy(mock_context, plugin_name, granted)

        # 所有需要权限的操作都应该成功
        sub_id = proxy.event_bus.subscribe(EventType.APP_STARTED, lambda e: None)
        assert sub_id is not None

        proxy.event_bus.publish(EventType.APP_STARTED, {})

        proxy.node_engine.get_node_definition("test")
        proxy.node_engine.get_all_node_types()
        proxy.node_engine.get_available_nodes()

        # 注册节点需要有效的定义
        from src.engine.definitions import NodeDefinition, PortDefinition, PortType

        definition = NodeDefinition(
            node_type="test.all_perms_node",
            display_name="全权限节点",
            description="测试节点",
            category="test",
            inputs=[PortDefinition("input1", PortType.STRING, "输入")],
            outputs=[PortDefinition("output1", PortType.STRING, "输出")],
            execute=lambda input1: {"output1": input1},
        )
        proxy.node_engine.register_node_type(definition)

        session = proxy.database.get_session()
        session.close()

        # 但 drop_tables 仍然被拒绝
        with pytest.raises(PermissionDeniedError):
            proxy.database.drop_tables()
