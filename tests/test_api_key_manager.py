# -*- coding: utf-8 -*-
"""测试 API密钥管理器和功能"""

import pytest

from src.agent.api_key_manager import ApiKeyManager
from src.storage.database import Database


@pytest.fixture
def db():
    database = Database(":memory:")
    database.create_tables()
    return database


@pytest.fixture
def api_key_manager(db):
    return ApiKeyManager(db)


class TestApiKeyManager:
    """测试ApiKeyManager的基本功能"""

    def test_store_and_get_key(self, api_key_manager: api_key_manager):
        api_key_manager.store_key("test_provider", "test_key_123")
        key = api_key_manager.get_key("test_provider")
        assert key == "test_key_123"

    def test_delete_key(self, api_key_manager: api_key_manager):
        api_key_manager.store_key("test_provider", "test_key_123")
        result = api_key_manager.delete_key("test_provider")
        assert result is True

        key = api_key_manager.get_key("test_provider")
        assert key is None

    def test_list_providers(self, api_key_manager: api_key_manager):
        api_key_manager.store_key("provider1", "key1")
        api_key_manager.store_key("provider2", "key2")

        providers = api_key_manager.list_providers()
        assert "provider1" in providers
        assert "provider2" in providers

    def test_has_key(self, api_key_manager: api_key_manager):
        assert not api_key_manager.has_key("nonexistent")

        api_key_manager.store_key("test_provider", "test_key")
        assert api_key_manager.has_key("test_provider")
