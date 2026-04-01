import pytest
from src.agent.api_key_manager import ApiKeyManager
from src.storage.database import Database


@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.create_tables()
    yield db


@pytest.fixture
def api_key_manager(test_db):
    manager = ApiKeyManager(db=test_db)
    yield manager


def test_store_key_with_supported_types(api_key_manager):
    api_key_manager.store_key("openai", "sk-test", supported_types=["text", "image"])

    config = api_key_manager.get_config("openai")
    assert config is not None
    assert config["supported_types"] == ["text", "image"]


def test_get_config_returns_supported_types(api_key_manager):
    api_key_manager.store_key("anthropic", "sk-test", supported_types=["text", "image", "audio"])

    config = api_key_manager.get_config("anthropic")
    assert config["supported_types"] == ["text", "image", "audio"]


def test_update_supported_types(api_key_manager):
    api_key_manager.store_key("openai", "sk-test")

    success = api_key_manager.update_supported_types("openai", ["text", "image", "video"])
    assert success is True

    config = api_key_manager.get_config("openai")
    assert config["supported_types"] == ["text", "image", "video"]


def test_default_supported_types(api_key_manager):
    api_key_manager.store_key("deepseek", "sk-test")

    config = api_key_manager.get_config("deepseek")
    assert config["supported_types"] == ["text"]
