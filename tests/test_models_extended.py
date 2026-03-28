# -*- coding: utf-8 -*-
"""测试扩展的数据库模型"""

import pytest
from datetime import datetime

from src.storage.database import Database
from src.storage.models import ApiKeyRecord, McpServerRecord, SkillRecord
from sqlalchemy.orm import Session


@pytest.fixture
def db():
    """创建内存数据库"""
    database = Database(":memory:")
    database.create_tables()
    return database


class TestApiKeyRecordExtended:
    """测试ApiKeyRecord扩展字段"""

    def test_create_with_new_fields(self, db):
        """测试创建带新字段的记录"""
        with Session(db.engine) as session:
            record = ApiKeyRecord(
                provider="test_provider",
                encrypted_key="encrypted_value",
                base_url="https://api.example.com",
                model_name="gpt-4",
                enabled=True,
            )
            session.add(record)
            session.commit()

            assert record.id is not None
            assert record.base_url == "https://api.example.com"
            assert record.model_name == "gpt-4"
            assert record.enabled is True

    def test_default_enabled_is_true(self, db):
        """测试enabled默认为True"""
        with Session(db.engine) as session:
            record = ApiKeyRecord(provider="default_test", encrypted_key="key")
            session.add(record)
            session.commit()

            assert record.enabled is True

    def test_optional_fields_can_be_null(self, db):
        """测试可选字段可以为None"""
        with Session(db.engine) as session:
            record = ApiKeyRecord(
                provider="minimal", encrypted_key="key", base_url=None, model_name=None
            )
            session.add(record)
            session.commit()

            assert record.base_url is None
            assert record.model_name is None


class TestMcpServerRecord:
    """测试McpServerRecord模型"""

    def test_create_stdio_server(self, db):
        """测试创建stdio类型服务器"""
        with Session(db.engine) as session:
            record = McpServerRecord(
                name="math_tools",
                server_type="stdio",
                command="python",
                args='["-m", "math_server"]',
                env='{"DEBUG": "1"}',
                timeout=60,
                enabled=True,
            )
            session.add(record)
            session.commit()

            assert record.id is not None
            assert record.server_type == "stdio"
            assert record.command == "python"
            assert record.timeout == 60

    def test_create_http_server(self, db):
        """测试创建http类型服务器"""
        with Session(db.engine) as session:
            record = McpServerRecord(
                name="weather_api",
                server_type="http",
                url="https://api.weather.com/mcp",
                transport="streamable_http",
                enabled=True,
            )
            session.add(record)
            session.commit()

            assert record.id is not None
            assert record.server_type == "http"
            assert record.url == "https://api.weather.com/mcp"

    def test_unique_name_constraint(self, db):
        """测试name唯一性约束"""
        with Session(db.engine) as session:
            record1 = McpServerRecord(name="unique_test", server_type="stdio", command="test")
            session.add(record1)
            session.commit()

            record2 = McpServerRecord(name="unique_test", server_type="http", url="http://test.com")
            session.add(record2)

            with pytest.raises(Exception):
                session.commit()

    def test_default_values(self, db):
        """测试默认值"""
        with Session(db.engine) as session:
            record = McpServerRecord(name="defaults_test", server_type="stdio")
            session.add(record)
            session.commit()

            assert record.timeout == 30
            assert record.enabled is True


class TestSkillRecord:
    """测试SkillRecord模型"""

    def test_create_skill(self, db):
        """测试创建skill记录"""
        with Session(db.engine) as session:
            record = SkillRecord(
                name="data_analysis",
                description="数据分析技能",
                path="/skills/data-analysis",
                enabled=True,
            )
            session.add(record)
            session.commit()

            assert record.id is not None
            assert record.name == "data_analysis"
            assert record.description == "数据分析技能"

    def test_unique_name_constraint(self, db):
        """测试name唯一性约束"""
        with Session(db.engine) as session:
            record1 = SkillRecord(name="unique_skill", path="/skills/unique")
            session.add(record1)
            session.commit()

            record2 = SkillRecord(name="unique_skill", path="/skills/other")
            session.add(record2)

            with pytest.raises(Exception):
                session.commit()

    def test_optional_description(self, db):
        """测试description可选"""
        with Session(db.engine) as session:
            record = SkillRecord(name="no_desc", path="/skills/no-desc", description=None)
            session.add(record)
            session.commit()

            assert record.description is None

    def test_default_enabled(self, db):
        """测试enabled默认值"""
        with Session(db.engine) as session:
            record = SkillRecord(name="default_enabled", path="/skills/test")
            session.add(record)
            session.commit()

            assert record.enabled is True
