# -*- coding: utf-8 -*-
"""存储模块测试"""

from pathlib import Path

import pytest

from src.storage.database import Database
from src.storage.models import (
    ApiKeyRecord,
    Base,
    PluginPermissionRecord,
    PluginRecord,
    SettingRecord,
    WorkflowRecord,
    NodePackageRecord,
)


class TestDatabase:
    """测试 Database 类"""

    def test_database_creation(self, db_path: Path):
        """测试数据库创建"""
        db = Database(db_path)

        assert db.db_path == db_path

        db.close()

    def test_create_tables(self, db_path: Path):
        """测试创建表"""
        db = Database(db_path)
        db.create_tables()

        # 数据库文件应该存在
        assert db_path.exists()

        db.close()

    def test_get_session(self, db_path: Path):
        """测试获取会话"""
        db = Database(db_path)
        db.create_tables()

        session = db.get_session()
        assert session is not None

        session.close()
        db.close()

    def test_session_context_manager(self, db_path: Path):
        """测试会话上下文管理器"""
        db = Database(db_path)
        db.create_tables()

        with db.session() as session:
            # 在会话中执行操作
            record = PluginRecord(name="test_plugin")
            session.add(record)

        # 会话应该已提交并关闭
        with db.session() as session:
            retrieved = session.query(PluginRecord).filter_by(name="test_plugin").first()
            assert retrieved is not None
            assert retrieved.name == "test_plugin"

        db.close()

    def test_session_rollback_on_error(self, db_path: Path):
        """测试会话在错误时回滚"""
        db = Database(db_path)
        db.create_tables()

        # 插入一条记录
        with db.session() as session:
            record = PluginRecord(name="test_plugin")
            session.add(record)

        # 尝试插入重复记录（会失败）
        with pytest.raises(Exception):
            with db.session() as session:
                record = PluginRecord(name="test_plugin")  # 重复的 name
                session.add(record)
                raise Exception("模拟错误")

        # 验证没有重复记录
        with db.session() as session:
            count = session.query(PluginRecord).filter_by(name="test_plugin").count()
            assert count == 1

        db.close()

    def test_context_manager(self, db_path: Path):
        """测试数据库上下文管理器"""
        with Database(db_path) as db:
            db.create_tables()
            assert db_path.exists()

        # 退出上下文后应该已关闭


class TestPluginRecord:
    """测试 PluginRecord 模型"""

    @pytest.fixture
    def db(self, db_path: Path):
        """创建数据库 fixture"""
        database = Database(db_path)
        database.create_tables()
        yield database
        database.close()

    def test_create_plugin_record(self, db: Database):
        """测试创建插件记录"""
        with db.session() as session:
            record = PluginRecord(
                name="test_plugin",
                version="1.0.0",
                enabled=True,
            )
            session.add(record)

        with db.session() as session:
            retrieved = session.query(PluginRecord).filter_by(name="test_plugin").first()
            assert retrieved is not None
            assert retrieved.name == "test_plugin"
            assert retrieved.version == "1.0.0"
            assert retrieved.enabled is True

    def test_unique_plugin_name(self, db: Database):
        """测试插件名称唯一约束"""
        with db.session() as session:
            record1 = PluginRecord(name="unique_plugin", version="1.0.0")
            session.add(record1)

        # 尝试创建同名插件应该失败
        with pytest.raises(Exception):  # 应该抛出 IntegrityError
            with db.session() as session:
                record2 = PluginRecord(name="unique_plugin", version="2.0.0")
                session.add(record2)


class TestSettingRecord:
    """测试 SettingRecord 模型"""

    @pytest.fixture
    def db(self, db_path: Path):
        """创建数据库 fixture"""
        database = Database(db_path)
        database.create_tables()
        yield database
        database.close()

    def test_create_setting_record(self, db: Database):
        """测试创建设置记录"""
        with db.session() as session:
            record = SettingRecord(
                key="test_setting",
                value='{"option": "value"}',
            )
            session.add(record)

        with db.session() as session:
            retrieved = session.query(SettingRecord).filter_by(key="test_setting").first()
            assert retrieved is not None
            assert retrieved.value == '{"option": "value"}'


class TestPluginPermissionRecord:
    """测试 PluginPermissionRecord 模型"""

    @pytest.fixture
    def db(self, db_path: Path):
        """创建数据库 fixture"""
        database = Database(db_path)
        database.create_tables()
        yield database
        database.close()

    def test_create_permission_record(self, db: Database):
        """测试创建权限记录"""
        # 先创建插件
        with db.session() as session:
            plugin = PluginRecord(name="test_plugin", version="1.0.0")
            session.add(plugin)

        # 创建权限记录
        with db.session() as session:
            record = PluginPermissionRecord(
                plugin_name="test_plugin",
                permission="file.read",
            )
            session.add(record)

        with db.session() as session:
            retrieved = (
                session.query(PluginPermissionRecord).filter_by(plugin_name="test_plugin").first()
            )
            assert retrieved is not None
            assert retrieved.permission == "file.read"
