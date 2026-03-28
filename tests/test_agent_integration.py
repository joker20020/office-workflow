# -*- coding: utf-8 -*-
"""AgentIntegration 单元测试"""

import pytest
from unittest.mock import MagicMock

from src.agent.agent_integration import AgentIntegration
from src.agent.api_key_manager import ApiKeyManager
from src.agent.skill_manager import SkillManager
from src.agent.mcp_server_manager import McpServerManager
from src.engine.node_engine import NodeEngine
from src.storage.database import Database


@pytest.fixture
def db():
    database = Database(":memory:")
    database.create_tables()
    return database


@pytest.fixture
def api_key_manager(db):
    return ApiKeyManager(db)


@pytest.fixture
def skill_manager(db):
    return SkillManager(db)


@pytest.fixture
def mcp_manager(db):
    return McpServerManager(db)


@pytest.fixture
def node_engine():
    return NodeEngine()


@pytest.fixture
def agent(api_key_manager, node_engine, skill_manager, mcp_manager):
    workflow_tools = MagicMock()
    agent = AgentIntegration(
        api_key_manager=api_key_manager,
        node_engine=node_engine,
        workflow_tools=workflow_tools,
        mcp_manager=mcp_manager,
        skill_manager=skill_manager,
    )
    return agent


class TestAgentIntegration:
    def test_initialization(self, agent):
        assert not agent.is_initialized

    def test_initialize_without_api_key(self, api_key_manager, node_engine):
        agent = AgentIntegration(api_key_manager, node_engine)
        assert not agent.initialize("dashscope")

    def test_set_mcp_manager(self, agent, mcp_manager):
        agent.set_mcp_manager(mcp_manager)
        assert agent._mcp_manager == mcp_manager

    def test_set_skill_manager(self, agent, skill_manager):
        agent.set_skill_manager(skill_manager)
        assert agent._skill_manager == skill_manager

    def test_reset(self, agent):
        agent._history.add_message("user", "test message")
        agent.reset()
        history = agent.get_history()
        assert len(history) == 0

    def test_get_history(self, agent):
        agent._history.add_message("user", "Hello")
        agent._history.add_message("assistant", "Hi there!")
        history = agent.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"


class TestSkillManager:
    def test_add_skill(self, skill_manager):
        skill_manager.add_skill("test_skill", "/path/to/skill", "Test skill description")
        skills = skill_manager.list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "test_skill"
        assert skills[0]["description"] == "Test skill description"

    def test_add_duplicate_skill(self, skill_manager):
        skill_manager.add_skill("test_skill", "/path/to/skill", "Description")
        with pytest.raises(ValueError, match="已存在"):
            skill_manager.add_skill("test_skill", "/path/other", "Other")

    def test_delete_skill(self, skill_manager):
        skill_manager.add_skill("to_delete", "/path/to/skill")
        result = skill_manager.delete_skill("to_delete")
        assert result is True
        skills = skill_manager.list_skills()
        assert len(skills) == 0

    def test_set_enabled(self, skill_manager):
        skill_manager.add_skill("test_skill", "/path/to/skill")
        skill_manager.set_enabled("test_skill", False)
        skill = skill_manager.get_skill("test_skill")
        assert skill["enabled"] is False
        skill_manager.set_enabled("test_skill", True)
        skill = skill_manager.get_skill("test_skill")
        assert skill["enabled"] is True

    def test_get_enabled_skills(self, skill_manager):
        skill_manager.add_skill("enabled_skill", "/path/1", "Enabled")
        skill_manager.add_skill("disabled_skill", "/path/2", "Disabled")
        skill_manager.set_enabled("disabled_skill", False)
        enabled = skill_manager.get_enabled_skills()
        assert len(enabled) == 1
        assert enabled[0]["name"] == "enabled_skill"


class TestMcpServerManager:
    def test_add_stdio_server(self, mcp_manager):
        mcp_manager.add_stdio_server("test_stdio", "python", ["-m", "server"], {"DEBUG": "1"}, 30)
        servers = mcp_manager.list_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "test_stdio"
        assert servers[0]["server_type"] == "stdio"

    def test_add_http_server(self, mcp_manager):
        mcp_manager.add_http_server("test_http", "http://localhost:8080/mcp")
        servers = mcp_manager.list_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "test_http"
        assert servers[0]["server_type"] == "http"

    def test_delete_server(self, mcp_manager):
        mcp_manager.add_http_server("to_delete", "http://localhost:8080/mcp")
        result = mcp_manager.delete_server("to_delete")
        assert result is True
        servers = mcp_manager.list_servers()
        assert len(servers) == 0

    def test_set_enabled(self, mcp_manager):
        mcp_manager.add_http_server("test_server", "http://localhost:8080/mcp")
        mcp_manager.set_enabled("test_server", False)
        server = mcp_manager.get_server("test_server")
        assert server["enabled"] is False
        mcp_manager.set_enabled("test_server", True)
        server = mcp_manager.get_server("test_server")
        assert server["enabled"] is True

    def test_get_agentscope_config_stdio(self, mcp_manager):
        mcp_manager.add_stdio_server(
            "test_stdio",
            "python",
            ["-m", "server"],
            {"DEBUG": "1"},
            60,
        )
        config = mcp_manager.get_agentscope_config("test_stdio")
        assert config is not None
        assert config["name"] == "test_stdio"
        assert config["command"] == "python"
        assert config["args"] == ["-m", "server"]
        assert config["env"] == {"DEBUG": "1"}
        assert config["timeout"] == 60

    def test_get_agentscope_config_http(self, mcp_manager):
        mcp_manager.add_http_server("test_http", "http://localhost:8080/mcp", "sse")
        config = mcp_manager.get_agentscope_config("test_http")
        assert config is not None
        assert config["name"] == "test_http"
        assert config["url"] == "http://localhost:8080/mcp"
        assert config["transport"] == "sse"
