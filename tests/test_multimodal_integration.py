# -*- coding: utf-8 -*-
import pytest
import inspect
from src.agent.api_key_manager import ApiKeyManager
from src.storage.database import Database
from src.storage.models import ApiKeyRecord


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


class TestMultimodalIntegration:
    def test_store_api_key_with_image_support(self, api_key_manager):
        api_key_manager.store_key("openai", "sk-test", supported_types=["text", "image"])
        config = api_key_manager.get_config("openai")
        assert config is not None
        assert "image" in config["supported_types"]
        assert "text" in config["supported_types"]

    def test_store_api_key_with_all_modal_types(self, api_key_manager):
        api_key_manager.store_key(
            "qwen", "sk-test", supported_types=["text", "image", "audio", "video"]
        )
        config = api_key_manager.get_config("qwen")
        assert config is not None
        assert set(config["supported_types"]) == {"text", "image", "audio", "video"}

    def test_update_supported_types(self, api_key_manager):
        api_key_manager.store_key("openai", "sk-test")
        success = api_key_manager.update_supported_types("openai", ["text", "image", "video"])
        assert success is True
        config = api_key_manager.get_config("openai")
        assert "image" in config["supported_types"]
        assert "video" in config["supported_types"]
        assert "audio" not in config["supported_types"]

    def test_default_supported_types(self, api_key_manager):
        api_key_manager.store_key("deepseek", "sk-test")
        config = api_key_manager.get_config("deepseek")
        assert config["supported_types"] == ["text"]

    def test_list_all_configs_includes_supported_types(self, api_key_manager):
        api_key_manager.store_key("openai", "sk-test-1", supported_types=["text", "image"])
        api_key_manager.store_key(
            "anthropic", "sk-test-2", supported_types=["text", "image", "audio"]
        )
        configs = api_key_manager.list_all_configs()
        assert len(configs) == 2
        openai_config = next(c for c in configs if c["provider"] == "openai")
        assert openai_config["supported_types"] == ["text", "image"]
        anthropic_config = next(c for c in configs if c["provider"] == "anthropic")
        assert anthropic_config["supported_types"] == ["text", "image", "audio"]

    def test_model_specific_supported_types(self, api_key_manager):
        api_key_manager.store_key(
            "openai", "sk-test-1", model_name="gpt-4", supported_types=["text", "image"]
        )
        api_key_manager.store_key(
            "openai", "sk-test-2", model_name="gpt-3.5-turbo", supported_types=["text"]
        )
        gpt4_config = api_key_manager.get_config("openai", "gpt-4")
        assert gpt4_config["supported_types"] == ["text", "image"]
        gpt35_config = api_key_manager.get_config("openai", "gpt-3.5-turbo")
        assert gpt35_config["supported_types"] == ["text"]

    def test_agent_integration_multimodal_message_format(self):
        from src.agent.agent_integration import AgentIntegration

        sig = inspect.signature(AgentIntegration.chat)
        params = sig.parameters
        assert "message" in params

    def test_block_widget_factory_multimodal_support(self):
        from src.ui.chat.blocks import create_block_widget

        try:
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance() or QApplication([])
        except Exception:
            pytest.skip("Qt not available; skipping widget tests.")
        image_block = {"type": "image", "source": {"type": "url", "url": "test.jpg"}}
        image_widget = create_block_widget(image_block)
        assert image_widget is not None
        assert hasattr(image_widget, "BLOCK_TYPE")
        assert image_widget.BLOCK_TYPE == "image"
        audio_block = {"type": "audio", "source": {"type": "url", "url": "test.mp3"}}
        audio_widget = create_block_widget(audio_block)
        assert audio_widget is not None
        assert audio_widget.BLOCK_TYPE == "audio"
        video_block = {"type": "video", "source": {"type": "url", "url": "test.mp4"}}
        video_widget = create_block_widget(video_block)
        assert video_widget is not None
        assert video_widget.BLOCK_TYPE == "video"


class TestMultimodalMigration:
    def test_migration_adds_supported_types_column(self, test_db):
        from sqlalchemy import text

        with test_db.engine.connect() as conn:
            result = conn.execute(text("SELECT supported_types FROM api_keys LIMIT 1"))
            _ = result.fetchone()

    def test_default_value_on_new_record(self, api_key_manager, test_db):
        from sqlalchemy import text

        api_key_manager.store_key("test", "sk-test")
        with test_db.engine.connect() as conn:
            result = conn.execute(
                text("SELECT supported_types FROM api_keys WHERE provider = 'test'")
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == '["text"]'
