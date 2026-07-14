# -*- coding: utf-8 -*-
"""AgentIntegration 单元测试"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentscope.message import AssistantMsg, SystemMsg, UserMsg
from agentscope.state import AgentState

import src.agent.agent_integration as agent_integration
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
    agent = AgentIntegration(
        api_key_manager=api_key_manager,
        node_engine=node_engine,
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
        previous_state = AgentState(context=agent._history.get_messages())
        agent._agent = SimpleNamespace(state=previous_state)

        agent.reset()

        history = agent.get_history()
        assert len(history) == 0
        assert agent._agent.state.context == []
        assert agent._agent.state is not previous_state

    def test_reset_without_agent_still_clears_history(self, agent):
        agent._history.add_message("user", "test message")
        agent._agent = None

        agent.reset()

        assert agent.get_history() == []

    def test_get_history(self, agent):
        agent._history.add_message("user", "Hello")
        agent._history.add_message("assistant", "Hi there!")
        history = agent.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"


@pytest.mark.parametrize(
    ("provider", "credential_name", "model_name", "default_model", "default_url"),
    [
        (
            "openai",
            "OpenAICredential",
            "OpenAIChatModel",
            "gpt-4o",
            "https://api.openai.com/v1",
        ),
        (
            "deepseek",
            "DeepSeekCredential",
            "DeepSeekChatModel",
            "deepseek-chat",
            "https://api.deepseek.com",
        ),
        (
            "dashscope",
            "DashScopeCredential",
            "DashScopeChatModel",
            "qwen-turbo",
            "https://api.dashscope.com",
        ),
    ],
)
def test_create_model_uses_provider_defaults(
    agent,
    monkeypatch,
    provider,
    credential_name,
    model_name,
    default_model,
    default_url,
):
    credential = object()
    credential_class = Mock(return_value=credential)
    model_class = Mock()
    monkeypatch.setattr(agent_integration, credential_name, credential_class, raising=False)
    monkeypatch.setattr(agent_integration, model_name, model_class, raising=False)

    agent._create_model(provider, "", "", "key")

    credential_class.assert_called_once_with(api_key="key", base_url=default_url)
    model_class.assert_called_once_with(
        credential=credential,
        model=default_model,
        stream=True,
    )


@pytest.mark.parametrize(
    ("provider", "credential_name", "model_name"),
    [
        ("openai", "OpenAICredential", "OpenAIChatModel"),
        ("deepseek", "DeepSeekCredential", "DeepSeekChatModel"),
        ("dashscope", "DashScopeCredential", "DashScopeChatModel"),
    ],
)
def test_create_model_forwards_custom_model_and_base_url(
    agent,
    monkeypatch,
    provider,
    credential_name,
    model_name,
):
    credential = object()
    credential_class = Mock(return_value=credential)
    model_class = Mock()
    monkeypatch.setattr(agent_integration, credential_name, credential_class, raising=False)
    monkeypatch.setattr(agent_integration, model_name, model_class, raising=False)

    agent._create_model(provider, "custom-model", "https://custom.example/v1", "key")

    credential_class.assert_called_once_with(
        api_key="key",
        base_url="https://custom.example/v1",
    )
    model_class.assert_called_once_with(
        credential=credential,
        model="custom-model",
        stream=True,
    )


def test_create_model_rejects_unsupported_provider(agent):
    with pytest.raises(ValueError, match="unsupported provider"):
        agent._create_model("unknown", "", "", "key")


def test_initialize_constructs_agent_with_history_state(agent, monkeypatch):
    history_messages = [
        UserMsg(name="User", content="question", metadata={"turn": 1}),
        AssistantMsg(name="Assistant", content="answer", metadata={"turn": 2}),
    ]
    for message in history_messages:
        agent._history.add_message(msg=message)

    constructed_agent = SimpleNamespace(state=None)
    agent_factory = Mock(return_value=constructed_agent)
    toolkit = object()
    model = object()
    monkeypatch.setattr(agent_integration, "Agent", agent_factory)
    monkeypatch.setattr(agent_integration, "Toolkit", Mock(return_value=toolkit))
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=model))
    monkeypatch.setattr(agent, "_register_registry_tools", Mock())
    monkeypatch.setattr(agent, "_register_mcp_tools", Mock())
    monkeypatch.setattr(agent, "_register_skills", Mock())
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="configured prompt"))

    assert agent.initialize("openai", "model", "https://example.test/v1") is True

    kwargs = agent_factory.call_args.kwargs
    assert kwargs["name"] == "WorkflowAssistant"
    assert kwargs["system_prompt"] == "configured prompt"
    assert kwargs["model"] is model
    assert kwargs["toolkit"] is toolkit
    assert isinstance(kwargs["state"], AgentState)
    assert kwargs["state"].context == history_messages
    assert kwargs["react_config"].max_iters == 50
    assert kwargs["react_config"].interruption_raise_cancelled_error is False


def test_stable_core_imports_keep_agentscope_available(monkeypatch):
    monkeypatch.setattr(agent_integration, "HttpStatelessClient", None)
    monkeypatch.setattr(agent_integration, "StdIOStatefulClient", None)

    assert agent_integration.AGENTSCOPE_AVAILABLE is True
    assert agent_integration.Agent is not None
    assert agent_integration.ReActConfig is not None
    assert agent_integration.AgentState is not None
    assert agent_integration.Toolkit is not None
    assert not hasattr(agent_integration, "ReAct" + "Agent")
    assert not hasattr(agent_integration, "InMemory" + "Memory")
    assert not hasattr(agent_integration, "DashScopeChatFormatter")
    assert not hasattr(agent_integration, "DeepSeekChatFormatter")
    assert not hasattr(agent_integration, "OpenAIChatFormatter")


def test_sync_history_assigns_fresh_agent_state(agent):
    messages = [
        UserMsg(name="User", content="one", metadata={"sequence": 1}),
        AssistantMsg(name="Assistant", content="two", metadata={"sequence": 2}),
    ]
    for message in messages:
        agent._history.add_message(msg=message)
    previous_state = AgentState()
    agent._agent = SimpleNamespace(state=previous_state)

    agent._sync_history_to_memory()

    assert agent._agent.state is not previous_state
    assert agent._agent.state.context == messages


def test_switch_session_success_refreshes_state(agent, monkeypatch):
    selected_messages = [UserMsg(name="User", content="selected")]
    previous_state = AgentState(
        context=[AssistantMsg(name="Assistant", content="previous")],
    )
    agent._agent = SimpleNamespace(state=previous_state)
    agent._history_repository = object()
    monkeypatch.setattr(agent._history, "set_session", Mock(return_value=True))
    monkeypatch.setattr(agent._history, "get_messages", Mock(return_value=selected_messages))

    assert agent.switch_session("selected-session") is True
    assert agent._agent.state is not previous_state
    assert agent._agent.state.context == selected_messages


def test_switch_session_failure_leaves_state_unchanged(agent, monkeypatch):
    previous_state = AgentState(
        context=[AssistantMsg(name="Assistant", content="previous")],
    )
    agent._agent = SimpleNamespace(state=previous_state)
    agent._history_repository = object()
    monkeypatch.setattr(agent._history, "set_session", Mock(return_value=False))

    assert agent.switch_session("missing-session") is False
    assert agent._agent.state is previous_state


def test_extract_agent_memory_reads_context_after_most_recent_user(agent):
    old_assistant = AssistantMsg(name="Assistant", content="old")
    recent_user = UserMsg(name="User", content="latest question")
    system = SystemMsg(
        name="System",
        content="note",
        id="system-message-id",
        metadata={"source": "policy"},
        created_at="2026-07-14T01:02:03",
    )
    assistant = AssistantMsg(
        name="WorkflowAssistant",
        content="latest answer",
        id="assistant-message-id",
        metadata={"trace": {"step": 2}},
        created_at="2026-07-14T01:02:04",
    )
    agent._agent = SimpleNamespace(
        state=AgentState(
            context=[old_assistant, recent_user, system, assistant],
        ),
    )

    messages = agent.extract_agent_memory()

    assert [message["role"] for message in messages] == ["system", "assistant"]
    assert messages[0]["id"] == "system-message-id"
    assert messages[0]["metadata"] == {"source": "policy"}
    assert messages[1]["id"] == "assistant-message-id"
    assert messages[1]["metadata"] == {"trace": {"step": 2}}
    assert messages[1]["content"][0]["text"] == "latest answer"


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


class TestHistorySyncPreservation:
    def test_state_context_preserves_identity_and_metadata(self, agent):
        message = UserMsg(
            name="User",
            content="test",
            id="preserved-id",
            created_at="2026-07-14T01:02:03",
            metadata={"tool_calls": [{"id": "1", "name": "search"}]},
        )
        agent._history.add_message(msg=message)
        agent._agent = SimpleNamespace(state=AgentState())

        agent._sync_history_to_memory()

        synced = agent._agent.state.context[0]
        assert synced.id == "preserved-id"
        assert synced.created_at == "2026-07-14T01:02:03"
        assert synced.metadata == {"tool_calls": [{"id": "1", "name": "search"}]}
