# -*- coding: utf-8 -*-
"""插件管理器模块测试"""

from pathlib import Path

import pytest

from src.core.event_bus import EventBus, EventType
from src.core.permission_manager import Permission, PermissionManager, PermissionSet
from src.core.plugin_base import PluginBase
from src.core.plugin_manager import PluginInfo, PluginManager, PluginLoadError


class TestPluginInfo:
    """测试 PluginInfo 数据类"""

    def test_plugin_info_creation(self, tmp_path: Path):
        """测试插件信息创建"""
        info = PluginInfo(
            name="test_plugin",
            module_path=tmp_path / "test_plugin",
        )

        assert info.name == "test_plugin"
        assert info.module_path == tmp_path / "test_plugin"
        assert info.plugin_class is None
        assert info.instance is None
        assert info.loaded is False


class MockPlugin(PluginBase):
    """测试用模拟插件"""

    name = "mock_plugin"
    version = "1.0.0"
    description = "测试插件"
    author = "Test Author"

    permissions = PermissionSet.from_list(
        [
            Permission.FILE_READ,
            Permission.EVENT_SUBSCRIBE,
        ]
    )

    def __init__(self):
        super().__init__()
        self.load_called = False
        self.unload_called = False

    def on_load(self, context):
        self.load_called = True

    def on_unload(self):
        self.unload_called = True


class TestPluginManager:
    """测试 PluginManager 类"""

    @pytest.fixture
    def plugins_dir(self, tmp_path: Path) -> Path:
        """创建插件目录"""
        plugins_path = tmp_path / "plugins"
        plugins_path.mkdir()
        return plugins_path

    @pytest.fixture
    def event_bus(self) -> EventBus:
        """创建事件总线"""
        return EventBus()

    @pytest.fixture
    def permission_manager(self) -> PermissionManager:
        """创建权限管理器"""
        return PermissionManager()

    @pytest.fixture
    def manager(
        self,
        plugins_dir: Path,
        event_bus: EventBus,
        permission_manager: PermissionManager,
    ) -> PluginManager:
        """创建插件管理器"""
        return PluginManager(
            plugins_dir=plugins_dir,
            event_bus=event_bus,
            permission_manager=permission_manager,
        )

    def test_manager_creation(self, plugins_dir: Path):
        """测试管理器创建"""
        manager = PluginManager(plugins_dir)

        assert manager.plugins_dir == plugins_dir
        assert manager._discovered == {}
        assert manager._loaded == {}

    def test_discover_empty_directory(self, manager: PluginManager):
        """测试发现空目录"""
        discovered = manager.discover_plugins()

        assert discovered == []

    def test_discover_plugins(self, manager: PluginManager, plugins_dir: Path):
        """测试发现插件"""
        # 创建测试插件目录
        plugin_dir = plugins_dir / "test_plugin"
        plugin_dir.mkdir()

        # 创建 __init__.py
        init_content = """
from src.core.plugin_base import PluginBase
from src.core.permission_manager import PermissionSet, Permission

class TestPlugin(PluginBase):
    name = "test_plugin"
    version = "1.0.0"
    
    permissions = PermissionSet.from_list([
        Permission.FILE_READ,
    ])
    
    def on_load(self, context):
        pass
    
    def on_unload(self):
        pass
"""
        (plugin_dir / "__init__.py").write_text(init_content, encoding="utf-8")

        discovered = manager.discover_plugins()

        assert "test_plugin" in discovered

    def test_load_plugin(self, manager: PluginManager):
        """测试加载插件"""
        # 手动添加发现的插件
        manager._discovered["mock_plugin"] = PluginInfo(
            name="mock_plugin",
            module_path=Path("/fake"),
            plugin_class=MockPlugin,
        )

        instance = manager.load_plugin("mock_plugin")

        assert instance is not None
        assert isinstance(instance, PluginBase)
        assert instance.load_called is True
        assert manager.is_loaded("mock_plugin")

    def test_load_nonexistent_plugin(self, manager: PluginManager):
        """测试加载不存在的插件"""
        with pytest.raises(PluginLoadError):
            manager.load_plugin("nonexistent")

    def test_unload_plugin(self, manager: PluginManager):
        """测试卸载插件"""
        # 先加载
        manager._discovered["mock_plugin"] = PluginInfo(
            name="mock_plugin",
            module_path=Path("/fake"),
            plugin_class=MockPlugin,
        )
        instance = manager.load_plugin("mock_plugin")

        # 卸载
        result = manager.unload_plugin("mock_plugin")

        assert result is True
        assert instance.unload_called is True
        assert not manager.is_loaded("mock_plugin")

    def test_unload_nonexistent_plugin(self, manager: PluginManager):
        """测试卸载不存在的插件"""
        result = manager.unload_plugin("nonexistent")
        assert result is False

    def test_get_plugin(self, manager: PluginManager):
        """测试获取插件"""
        manager._discovered["mock_plugin"] = PluginInfo(
            name="mock_plugin",
            module_path=Path("/fake"),
            plugin_class=MockPlugin,
        )
        manager.load_plugin("mock_plugin")

        instance = manager.get_plugin("mock_plugin")

        assert instance is not None
        assert isinstance(instance, MockPlugin)

    def test_get_nonexistent_plugin(self, manager: PluginManager):
        """测试获取不存在的插件"""
        instance = manager.get_plugin("nonexistent")
        assert instance is None

    def test_get_loaded_plugins(self, manager: PluginManager):
        """测试获取所有已加载插件"""
        manager._discovered["mock_plugin"] = PluginInfo(
            name="mock_plugin",
            module_path=Path("/fake"),
            plugin_class=MockPlugin,
        )
        manager.load_plugin("mock_plugin")

        loaded = manager.get_loaded_plugins()

        assert "mock_plugin" in loaded
        assert len(loaded) == 1

    def test_unload_all(self, manager: PluginManager):
        """测试卸载所有插件"""
        manager._discovered["mock_plugin"] = PluginInfo(
            name="mock_plugin",
            module_path=Path("/fake"),
            plugin_class=MockPlugin,
        )
        manager.load_plugin("mock_plugin")

        manager.unload_all_plugins()

        assert not manager.is_loaded("mock_plugin")
        assert len(manager.get_loaded_plugins()) == 0

    def test_event_published_on_load(
        self,
        manager: PluginManager,
        event_bus: EventBus,
    ):
        """测试加载时发布事件"""
        events: list = []
        event_bus.subscribe(
            EventType.PLUGIN_LOADED,
            lambda e: events.append(e.data),
        )

        manager._discovered["mock_plugin"] = PluginInfo(
            name="mock_plugin",
            module_path=Path("/fake"),
            plugin_class=MockPlugin,
        )
        manager.load_plugin("mock_plugin")

        assert len(events) == 1
        assert events[0]["name"] == "mock_plugin"

    def test_event_published_on_unload(
        self,
        manager: PluginManager,
        event_bus: EventBus,
    ):
        """测试卸载时发布事件"""
        events: list = []
        event_bus.subscribe(
            EventType.PLUGIN_UNLOADED,
            lambda e: events.append(e.data),
        )

        manager._discovered["mock_plugin"] = PluginInfo(
            name="mock_plugin",
            module_path=Path("/fake"),
            plugin_class=MockPlugin,
        )
        manager.load_plugin("mock_plugin")
        manager.unload_plugin("mock_plugin")

        assert len(events) == 1
        assert events[0]["name"] == "mock_plugin"
