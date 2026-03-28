# -*- coding: utf-8 -*-
"""AppContext 模块测试"""

from pathlib import Path

import pytest

from src.core.app_context import AppContext, get_context, init_context, shutdown_context
from src.core.event_bus import EventBus, EventType
from src.core.permission_manager import Permission, PermissionManager
from src.core.plugin_manager import PluginManager


class TestAppContext:
    """测试 AppContext 类"""

    @pytest.fixture
    def context(self, tmp_path: Path) -> AppContext:
        """创建应用上下文"""
        data_dir = tmp_path / "data"
        plugins_dir = tmp_path / "plugins"

        context = AppContext(
            data_dir=data_dir,
            plugins_dir=plugins_dir,
        )

        yield context

        # 清理
        if context.is_initialized:
            context.shutdown()

    def test_context_creation(self, context: AppContext):
        """测试上下文创建"""
        assert context.data_dir is not None
        assert context.plugins_dir is not None
        assert not context.is_initialized

    def test_initialize(self, context: AppContext):
        """测试初始化"""
        context.initialize()

        assert context.is_initialized
        assert context._event_bus is not None
        assert context._permission_manager is not None
        assert context._plugin_manager is not None
        assert context._database is not None

    def test_initialize_twice_raises_error(self, context: AppContext):
        """测试重复初始化抛出错误"""
        context.initialize()

        with pytest.raises(RuntimeError):
            context.initialize()

    def test_properties_raise_before_initialize(self, context: AppContext):
        """测试初始化前访问属性抛出错误"""
        with pytest.raises(RuntimeError):
            _ = context.event_bus

        with pytest.raises(RuntimeError):
            _ = context.permission_manager

        with pytest.raises(RuntimeError):
            _ = context.plugin_manager

        with pytest.raises(RuntimeError):
            _ = context.database

    def test_event_bus_property(self, context: AppContext):
        """测试 event_bus 属性"""
        context.initialize()

        assert isinstance(context.event_bus, EventBus)

    def test_permission_manager_property(self, context: AppContext):
        """测试 permission_manager 属性"""
        context.initialize()

        assert isinstance(context.permission_manager, PermissionManager)

    def test_plugin_manager_property(self, context: AppContext):
        """测试 plugin_manager 属性"""
        context.initialize()

        assert isinstance(context.plugin_manager, PluginManager)

    def test_database_property(self, context: AppContext):
        """测试 database 属性"""
        context.initialize()

        assert context.database is not None

    def test_shutdown(self, context: AppContext):
        """测试关闭"""
        context.initialize()
        context.shutdown()

        assert not context.is_initialized

    def test_shutdown_clears_event_bus(self, context: AppContext):
        """测试关闭清除事件总线"""
        context.initialize()

        # 订阅事件
        context.event_bus.subscribe(EventType.APP_STARTED, lambda e: None)

        context.shutdown()

        # 重新初始化后应该没有订阅
        context.initialize()
        count = context.event_bus.get_subscribers_count(EventType.APP_STARTED)
        assert count == 0

    def test_data_directory_created(self, context: AppContext, tmp_path: Path):
        """测试数据目录被创建"""
        context.initialize()

        assert context.data_dir.exists()

    def test_database_file_created(self, context: AppContext, tmp_path: Path):
        """测试数据库文件被创建"""
        context.initialize()

        db_file = context.data_dir / "app.db"
        assert db_file.exists()


class TestGlobalContext:
    """测试全局上下文函数"""

    def teardown_method(self):
        """每个测试后清理全局上下文"""
        try:
            shutdown_context()
        except RuntimeError:
            pass

    def test_init_context(self, tmp_path: Path):
        """测试初始化全局上下文"""
        context = init_context(
            data_dir=tmp_path / "data",
            plugins_dir=tmp_path / "plugins",
        )

        assert context.is_initialized

    def test_init_context_twice_raises_error(self, tmp_path: Path):
        """测试重复初始化全局上下文抛出错误"""
        init_context(
            data_dir=tmp_path / "data",
            plugins_dir=tmp_path / "plugins",
        )

        with pytest.raises(RuntimeError):
            init_context()

    def test_get_context(self, tmp_path: Path):
        """测试获取全局上下文"""
        init_context(
            data_dir=tmp_path / "data",
            plugins_dir=tmp_path / "plugins",
        )

        context = get_context()

        assert context is not None
        assert context.is_initialized

    def test_get_context_before_init_raises_error(self):
        """测试初始化前获取全局上下文抛出错误"""
        # 先确保没有初始化
        try:
            shutdown_context()
        except RuntimeError:
            pass

        with pytest.raises(RuntimeError):
            get_context()

    def test_shutdown_context(self, tmp_path: Path):
        """测试关闭全局上下文"""
        init_context(
            data_dir=tmp_path / "data",
            plugins_dir=tmp_path / "plugins",
        )

        shutdown_context()

        # 关闭后获取应该抛出错误
        with pytest.raises(RuntimeError):
            get_context()
