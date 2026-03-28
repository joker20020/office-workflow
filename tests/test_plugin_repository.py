# -*- coding: utf-8 -*-
"""PluginRepository 测试

测试统一的插件状态和配置存储库：
- 状态管理: get_enabled, set_enabled, ensure_plugin_exists
- 配置管理: get_config, set_config, update_config
- 安全隔离: 每个插件只能访问自己的配置
"""

from pathlib import Path

import pytest

from src.storage.database import Database
from src.storage.repositories import PluginRepository
from src.storage.models import PluginRecord, SettingRecord


# ==================== Fixtures ====================


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """创建测试数据库"""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.create_tables()
    yield db
    db.close()


@pytest.fixture
def repository(database: Database) -> PluginRepository:
    """创建 PluginRepository 实例"""
    return PluginRepository(database)


# ==================== 状态管理测试 ====================


class TestPluginStatusManagement:
    """测试插件状态管理"""

    def test_get_enabled_returns_true_by_default(self, repository: PluginRepository):
        """测试默认启用状态"""
        # 未设置过的插件默认启用
        result = repository.get_enabled("new_plugin")

        assert result is True

    def test_set_enabled_creates_plugin_if_not_exists(self, repository: PluginRepository):
        """测试设置状态时自动创建插件记录"""
        # 设置新插件的状态
        result = repository.set_enabled("new_plugin", False)

        assert result is True
        # 验证插件记录已创建
        assert repository.get_enabled("new_plugin") is False

    def test_set_enabled_updates_existing_plugin(self, repository: PluginRepository):
        """测试更新已存在插件的状态"""
        # 先创建插件
        repository.set_enabled("existing_plugin", True)

        # 更新状态
        result = repository.set_enabled("existing_plugin", False)

        assert result is True
        assert repository.get_enabled("existing_plugin") is False

    def test_set_enabled_to_true(self, repository: PluginRepository):
        """测试启用插件"""
        # 先禁用
        repository.set_enabled("test_plugin", False)

        # 启用
        result = repository.set_enabled("test_plugin", True)

        assert result is True
        assert repository.get_enabled("test_plugin") is True

    def test_set_enabled_to_false(self, repository: PluginRepository):
        """测试禁用插件"""
        # 启用
        repository.set_enabled("test_plugin", True)

        # 禁用
        result = repository.set_enabled("test_plugin", False)

        assert result is True
        assert repository.get_enabled("test_plugin") is False

    def test_ensure_plugin_exists_creates_new_plugin(self, repository: PluginRepository):
        """测试确保插件存在时创建新插件"""
        with repository._database.session() as session:
            repository._ensure_plugin_exists(session, "brand_new_plugin")

            # 验证插件已创建
            from sqlalchemy import select

            stmt = select(PluginRecord).where(PluginRecord.name == "brand_new_plugin")
            record = session.execute(stmt).scalar_one_or_none()

            assert record is not None
            assert record.name == "brand_new_plugin"
            assert record.enabled is True  # 默认启用

    def test_ensure_plugin_exists_does_not_duplicate(self, repository: PluginRepository):
        """测试已存在的插件不会被重复创建"""
        # 先创建插件
        repository.set_enabled("existing_plugin", True)

        # 再次确保存在
        with repository._database.session() as session:
            repository._ensure_plugin_exists(session, "existing_plugin")

            # 验证只有一条记录
            from sqlalchemy import select

            stmt = select(PluginRecord).where(PluginRecord.name == "existing_plugin")
            records = session.execute(stmt).scalars().all()

            assert len(records) == 1


# ==================== 配置管理测试 ====================


class TestPluginConfigManagement:
    """测试插件配置管理"""

    def test_get_config_returns_empty_dict_when_not_set(self, repository: PluginRepository):
        """测试未设置配置时返回空字典"""
        config = repository.get_config("new_plugin")

        assert config == {}

    def test_set_config_stores_json_in_plugin_record(self, repository: PluginRepository):
        """测试设置配置存储到 PluginRecord.config_json"""
        config_data = {"api_key": "test123", "enabled": True}

        result = repository.set_config("test_plugin", config_data)

        assert result is True

        # 验证存储的值在 PluginRecord.config_json 字段
        with repository._database.session() as session:
            from sqlalchemy import select
            import json

            stmt = select(PluginRecord).where(PluginRecord.name == "test_plugin")
            record = session.execute(stmt).scalar_one_or_none()

            assert record is not None
            assert record.config_json is not None
            assert json.loads(record.config_json) == config_data

    def test_get_config_retrieves_stored_config(self, repository: PluginRepository):
        """测试获取已存储的配置"""
        config_data = {"api_key": "test123", "timeout": 30}

        # 设置配置
        repository.set_config("test_plugin", config_data)

        # 获取配置
        result = repository.get_config("test_plugin")

        assert result == config_data

    def test_set_config_overwrites_existing(self, repository: PluginRepository):
        """测试设置配置会覆盖已存在的配置"""
        # 设置初始配置
        repository.set_config("test_plugin", {"old_key": "old_value"})

        # 覆盖配置
        new_config = {"new_key": "new_value"}
        result = repository.set_config("test_plugin", new_config)

        assert result is True

        # 验证配置已更新
        config = repository.get_config("test_plugin")
        assert config == new_config
        assert "old_key" not in config

    def test_update_config_merges_with_existing(self, repository: PluginRepository):
        """测试更新配置会合并到已存在的配置"""
        # 设置初始配置
        repository.set_config("test_plugin", {"key1": "value1", "key2": "value2"})

        # 部分更新
        updates = {"key2": "new_value2", "key3": "value3"}
        result = repository.update_config("test_plugin", updates)

        assert result is True

        # 验证配置已合并
        config = repository.get_config("test_plugin")
        assert config == {
            "key1": "value1",  # 保留
            "key2": "new_value2",  # 更新
            "key3": "value3",  # 新增
        }

    def test_update_config_creates_if_not_exists(self, repository: PluginRepository):
        """测试更新不存在的配置会创建新配置"""
        updates = {"key1": "value1"}

        result = repository.update_config("new_plugin", updates)

        assert result is True

        config = repository.get_config("new_plugin")
        assert config == updates

    def test_update_config_with_empty_dict(self, repository: PluginRepository):
        """测试空更新不影响配置"""
        # 设置初始配置
        repository.set_config("test_plugin", {"key1": "value1"})

        # 空更新
        result = repository.update_config("test_plugin", {})

        assert result is True

        # 验证配置未变
        config = repository.get_config("test_plugin")
        assert config == {"key1": "value1"}

    def test_set_config_with_complex_nested_data(self, repository: PluginRepository):
        """测试存储复杂嵌套数据"""
        config_data = {
            "api_keys": {
                "openai": "sk-xxx",
                "anthropic": "sk-yyy",
            },
            "settings": {
                "timeout": 30,
                "retries": 3,
                "endpoints": ["https://api.example.com"],
            },
            "features": ["feature1", "feature2"],
        }

        result = repository.set_config("complex_plugin", config_data)

        assert result is True

        retrieved = repository.get_config("complex_plugin")
        assert retrieved == config_data

    def test_config_stored_in_plugin_record_field(self, repository: PluginRepository):
        """测试配置存储在 PluginRecord.config_json 字段"""
        repository.set_config("my_plugin", {"key": "value"})

        with repository._database.session() as session:
            from sqlalchemy import select
            import json

            stmt = select(PluginRecord).where(PluginRecord.name == "my_plugin")
            record = session.execute(stmt).scalar_one_or_none()

            assert record is not None
            assert record.config_json is not None
            assert json.loads(record.config_json) == {"key": "value"}


# ==================== 配置隔离测试 ====================


class TestPluginConfigIsolation:
    """测试插件配置隔离"""

    def test_configs_are_isolated_per_plugin(self, repository: PluginRepository):
        """测试每个插件的配置是隔离的"""
        # 设置不同插件的配置
        repository.set_config("plugin_a", {"key": "value_a"})
        repository.set_config("plugin_b", {"key": "value_b"})

        # 验证配置隔离
        config_a = repository.get_config("plugin_a")
        config_b = repository.get_config("plugin_b")

        assert config_a == {"key": "value_a"}
        assert config_b == {"key": "value_b"}

    def test_update_does_not_affect_other_plugins(self, repository: PluginRepository):
        """测试更新一个插件的配置不影响其他插件"""
        # 设置两个插件的配置
        repository.set_config("plugin_a", {"shared_key": "a_value"})
        repository.set_config("plugin_b", {"shared_key": "b_value"})

        # 更新 plugin_a
        repository.update_config("plugin_a", {"new_key": "new_value"})

        # 验证 plugin_b 未受影响
        config_b = repository.get_config("plugin_b")
        assert config_b == {"shared_key": "b_value"}
        assert "new_key" not in config_b

    def test_set_config_does_not_affect_other_plugins(self, repository: PluginRepository):
        """测试设置一个插件的配置不影响其他插件"""
        # 设置两个插件的配置
        repository.set_config("plugin_a", {"key": "value_a"})
        repository.set_config("plugin_b", {"key": "value_b"})

        # 覆盖 plugin_a
        repository.set_config("plugin_a", {"new_key": "new_value"})

        # 验证 plugin_b 未受影响
        config_b = repository.get_config("plugin_b")
        assert config_b == {"key": "value_b"}


# ==================== 综合测试 ====================


class TestPluginRepositoryIntegration:
    """测试 PluginRepository 综合功能"""

    def test_status_and_config_are_independent(self, repository: PluginRepository):
        """测试状态和配置是独立的"""
        # 设置状态
        repository.set_enabled("test_plugin", False)

        # 设置配置
        repository.set_config("test_plugin", {"key": "value"})

        # 验证状态
        assert repository.get_enabled("test_plugin") is False

        # 验证配置
        assert repository.get_config("test_plugin") == {"key": "value"}

    def test_disabled_plugin_can_still_have_config(self, repository: PluginRepository):
        """测试禁用的插件仍然可以有配置"""
        # 禁用插件
        repository.set_enabled("test_plugin", False)

        # 设置配置
        repository.set_config("test_plugin", {"key": "value"})

        # 验证配置可访问
        assert repository.get_config("test_plugin") == {"key": "value"}

    def test_multiple_operations_on_same_plugin(self, repository: PluginRepository):
        """测试对同一插件的多次操作"""
        plugin_name = "multi_op_plugin"

        # 初始状态
        assert repository.get_enabled(plugin_name) is True
        assert repository.get_config(plugin_name) == {}

        # 设置配置
        repository.set_config(plugin_name, {"v1": 1})
        assert repository.get_config(plugin_name) == {"v1": 1}

        # 更新配置
        repository.update_config(plugin_name, {"v2": 2})
        assert repository.get_config(plugin_name) == {"v1": 1, "v2": 2}

        # 禁用插件
        repository.set_enabled(plugin_name, False)
        assert repository.get_enabled(plugin_name) is False

        # 配置仍然存在
        assert repository.get_config(plugin_name) == {"v1": 1, "v2": 2}

        # 覆盖配置
        repository.set_config(plugin_name, {"v3": 3})
        assert repository.get_config(plugin_name) == {"v3": 3}

    def test_concurrent_plugin_management(self, repository: PluginRepository):
        """测试管理多个插件"""
        plugins = ["plugin_1", "plugin_2", "plugin_3"]

        # 为每个插件设置不同的状态和配置
        for i, plugin in enumerate(plugins):
            repository.set_enabled(plugin, i % 2 == 0)
            repository.set_config(plugin, {"index": i})

        # 验证每个插件
        for i, plugin in enumerate(plugins):
            assert repository.get_enabled(plugin) == (i % 2 == 0)
            assert repository.get_config(plugin) == {"index": i}
