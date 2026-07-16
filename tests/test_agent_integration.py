# -*- coding: utf-8 -*-
"""AgentIntegration 单元测试"""

import asyncio
import builtins
import concurrent.futures
import importlib.util
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig
from agentscope.message import AssistantMsg, SystemMsg, UserMsg
from agentscope.permission import PermissionMode
from agentscope.state import AgentState
from agentscope.tool import FunctionTool

import src.agent.agent_integration as agent_integration
import src.agent.mcp_server_manager as mcp_server_manager
import src.agent.skill_manager as skill_manager_module
from src.agent.agent_integration import AgentIntegration
from src.agent.api_key_manager import ApiKeyManager
from src.agent.mcp_server_manager import McpServerManager
from src.agent.skill_manager import SkillManager
from src.agent.tool_registry import AgentToolRegistry
from src.core.permission_manager import Permission, PermissionManager
from src.engine.node_engine import NodeEngine
from src.storage.database import Database


class _LifecycleClient:
    def __init__(self, name, *, stateful, events, connect_error=None, close_error=None):
        self.name = name
        self.is_stateful = stateful
        self.events = events
        self.connect_error = connect_error
        self.close_error = close_error
        self.connect_calls = 0
        self.close_calls = 0
        self.loop_observations = []

    def _record_loop(self, operation):
        loop = asyncio.get_running_loop()
        self.loop_observations.append((operation, loop, loop.is_closed()))

    async def connect(self):
        self._record_loop("connect")
        self.connect_calls += 1
        self.events.append(f"connect:{self.name}")
        if self.connect_error:
            raise self.connect_error

    async def close(self):
        self._record_loop("close")
        self.close_calls += 1
        self.events.append(f"close:{self.name}")
        if self.close_error:
            raise self.close_error

    async def operate(self, operation):
        self._record_loop(operation)


class _GatedConnectClient(_LifecycleClient):
    def __init__(self, name, *, events):
        super().__init__(name, stateful=True, events=events)
        self.connect_started = threading.Event()
        self.release_connect = threading.Event()
        self.close_finished = threading.Event()

    async def connect(self):
        self._record_loop("connect")
        self.connect_calls += 1
        self.events.append(f"connect:{self.name}")
        self.connect_started.set()
        while not self.release_connect.is_set():
            await asyncio.sleep(0.001)

    async def close(self):
        await super().close()
        self.close_finished.set()


class _GatedCloseAfterConnectErrorClient(_LifecycleClient):
    def __init__(self, name, *, events):
        super().__init__(
            name,
            stateful=True,
            events=events,
            connect_error=RuntimeError("connect boom"),
        )
        self.close_started = threading.Event()
        self.release_close = threading.Event()
        self.close_finished = threading.Event()

    async def close(self):
        self._record_loop("close")
        self.close_calls += 1
        self.events.append(f"close:{self.name}")
        self.close_started.set()
        while not self.release_close.is_set():
            await asyncio.sleep(0.001)
        self.close_finished.set()


class _CleanupAbort(BaseException):
    pass


class _SelectionAbort(BaseException):
    pass


async def _current_loop():
    return asyncio.get_running_loop()


def _configure_successful_initialize(
    agent,
    monkeypatch,
    *,
    toolkit_factory=None,
    mock_skill_paths=True,
):
    toolkit_factory = toolkit_factory or Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(agent_integration, "Toolkit", toolkit_factory)
    monkeypatch.setattr(
        agent_integration,
        "Agent",
        Mock(return_value=SimpleNamespace(state=None)),
    )
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=object()))
    monkeypatch.setattr(agent, "_build_registry_function_tools", Mock(return_value=[]))
    if agent._skill_manager is not None and mock_skill_paths:
        monkeypatch.setattr(
            agent._skill_manager,
            "get_enabled_skill_paths",
            Mock(return_value=[]),
            raising=False,
        )
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="configured prompt"))
    return toolkit_factory


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
    yield agent
    agent.shutdown()


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
        assert agent._agent is None
        assert agent._toolkit is None
        assert agent._initialized is False

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


def test_registry_callables_are_wrapped_once_in_order(agent, monkeypatch):
    def first_tool():
        """First tool docs."""

    def second_tool():
        """Second tool docs."""

    AgentToolRegistry._reset_for_testing()
    registry = AgentToolRegistry.instance()
    registry.register("first", [first_tool, second_tool])
    registry.register("duplicate", [first_tool])
    wrapped_funcs = []

    def recording_function_tool(*, func, **kwargs):
        wrapped_funcs.append(func)
        return FunctionTool(func=func, **kwargs)

    monkeypatch.setattr(agent_integration, "FunctionTool", recording_function_tool)

    try:
        tools = agent._build_registry_function_tools()
    finally:
        AgentToolRegistry._reset_for_testing()

    assert all(isinstance(tool, FunctionTool) for tool in tools)
    assert wrapped_funcs == [first_tool, second_tool]
    assert [tool.name for tool in tools] == ["first_tool", "second_tool"]
    assert [tool.description for tool in tools] == [
        "First tool docs.",
        "Second tool docs.",
    ]
    assert [tool.is_concurrency_safe for tool in tools] == [False, False]


def test_registry_function_tools_filter_owned_groups_before_dedup(agent, monkeypatch):
    def allowed_tool():
        """Allowed tool docs."""

    def trusted_tool():
        """Trusted tool docs."""

    def denied_tool():
        """Denied tool docs."""

    forbidden_names = {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}
    permission_manager = PermissionManager()
    permission_manager.grant("allowed_plugin", Permission.AGENT_TOOL)
    agent._permission_manager = permission_manager
    AgentToolRegistry._reset_for_testing()
    registry = AgentToolRegistry.instance()
    registry.register(
        "denied",
        [allowed_tool, denied_tool],
        owner_name="denied_plugin",
    )
    registry.register(
        "allowed",
        [allowed_tool, trusted_tool],
        owner_name="allowed_plugin",
    )
    registry.register("trusted", [trusted_tool])
    wrapped_funcs = []

    def recording_function_tool(*, func, **kwargs):
        wrapped_funcs.append(func)
        return FunctionTool(func=func, **kwargs)

    monkeypatch.setattr(agent_integration, "FunctionTool", recording_function_tool)

    try:
        tools = agent._build_registry_function_tools()
    finally:
        AgentToolRegistry._reset_for_testing()

    assert wrapped_funcs == [allowed_tool, trusted_tool]
    assert [tool.name for tool in tools] == ["allowed_tool", "trusted_tool"]
    assert denied_tool not in wrapped_funcs
    assert forbidden_names.isdisjoint(tool.name for tool in tools)
    assert all(tool.is_concurrency_safe is False for tool in tools)


def test_registry_owned_groups_remain_visible_without_permission_manager(
    api_key_manager,
    node_engine,
    monkeypatch,
):
    def owned_tool():
        """Owned tool docs."""

    agent = AgentIntegration(api_key_manager, node_engine, permission_manager=None)
    AgentToolRegistry._reset_for_testing()
    registry = AgentToolRegistry.instance()
    registry.register("owned", [owned_tool], owner_name="legacy_plugin")
    wrapped_funcs = []
    monkeypatch.setattr(
        agent_integration,
        "FunctionTool",
        lambda *, func, **kwargs: wrapped_funcs.append(func)
        or FunctionTool(func=func, **kwargs),
    )

    try:
        tools = agent._build_registry_function_tools()
    finally:
        AgentToolRegistry._reset_for_testing()
        agent.shutdown()

    assert wrapped_funcs == [owned_tool]
    assert [tool.name for tool in tools] == ["owned_tool"]


def test_initialize_constructs_toolkit_with_wrapped_tools_and_agent_state(
    agent,
    monkeypatch,
):
    history_messages = [
        UserMsg(name="User", content="question", metadata={"turn": 1}),
        AssistantMsg(name="Assistant", content="answer", metadata={"turn": 2}),
    ]
    for message in history_messages:
        agent._history.add_message(msg=message)

    constructed_agent = SimpleNamespace(state=None)
    agent_factory = Mock(return_value=constructed_agent)
    toolkit = SimpleNamespace(register_tool_function=Mock())
    toolkit_factory = Mock(return_value=toolkit)
    model = object()
    monkeypatch.setattr(agent_integration, "Agent", agent_factory)
    monkeypatch.setattr(agent_integration, "Toolkit", toolkit_factory)
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=model))
    wrapped_tools = [object(), object()]
    monkeypatch.setattr(
        agent,
        "_build_registry_function_tools",
        Mock(return_value=wrapped_tools),
    )
    prepared_clients = [
        SimpleNamespace(is_stateful=False),
        SimpleNamespace(is_stateful=False),
    ]
    monkeypatch.setattr(
        agent,
        "_connect_mcp_clients",
        AsyncMock(return_value=prepared_clients),
    )
    skill_paths = ["C:\\skills\\first", "C:\\skills\\second"]
    get_skill_paths = Mock(return_value=skill_paths)
    monkeypatch.setattr(
        agent._skill_manager,
        "get_enabled_skill_paths",
        get_skill_paths,
        raising=False,
    )
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="configured prompt"))

    assert agent.initialize("openai", "model", "https://example.test/v1") is True

    get_skill_paths.assert_called_once_with()
    toolkit_factory.assert_called_once_with(
        tools=wrapped_tools,
        mcps=prepared_clients,
        skills_or_loaders=skill_paths,
    )
    assert toolkit_factory.call_args.kwargs["skills_or_loaders"] is skill_paths
    assert agent._mcp_clients is prepared_clients
    toolkit.register_tool_function.assert_not_called()
    kwargs = agent_factory.call_args.kwargs
    assert kwargs["name"] == "WorkflowAssistant"
    assert kwargs["system_prompt"] == "configured prompt"
    assert kwargs["model"] is model
    assert kwargs["toolkit"] is toolkit
    assert isinstance(kwargs["state"], AgentState)
    assert kwargs["state"].context == history_messages
    assert kwargs["state"].permission_context.mode is PermissionMode.BYPASS
    assert kwargs["react_config"].max_iters == 50
    assert kwargs["react_config"].interruption_raise_cancelled_error is False


def test_initialize_builds_complete_filtered_toolkit_before_bypass_agent(
    agent,
    monkeypatch,
):
    events = []
    wrapped_tools = [object()]
    prepared_clients = [SimpleNamespace(is_stateful=False)]
    skill_paths = ["C:\\skills\\validated"]
    toolkit = SimpleNamespace()

    def build_tools():
        events.append("tools")
        return wrapped_tools

    async def connect_clients():
        events.append("mcps")
        return prepared_clients

    def load_skills():
        events.append("skills")
        return skill_paths

    def construct_toolkit(**kwargs):
        events.append(("toolkit", kwargs))
        return toolkit

    def construct_agent(**kwargs):
        events.append(("agent", kwargs["state"].permission_context.mode))
        return SimpleNamespace(state=kwargs["state"])

    monkeypatch.setattr(agent, "_build_registry_function_tools", build_tools)
    monkeypatch.setattr(agent, "_connect_mcp_clients", connect_clients)
    monkeypatch.setattr(
        agent._skill_manager,
        "get_enabled_skill_paths",
        load_skills,
    )
    monkeypatch.setattr(agent_integration, "Toolkit", construct_toolkit)
    monkeypatch.setattr(agent_integration, "Agent", construct_agent)
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=object()))
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="configured prompt"))

    assert agent.initialize("openai", "model", "https://example.test/v1") is True

    assert events[:3] == ["tools", "mcps", "skills"]
    assert events[3] == (
        "toolkit",
        {
            "tools": wrapped_tools,
            "mcps": prepared_clients,
            "skills_or_loaders": skill_paths,
        },
    )
    assert events[4] == ("agent", PermissionMode.BYPASS)


def test_successful_rebuild_preserves_deep_copied_state_and_closes_old_clients_first(
    agent,
    monkeypatch,
):
    events = []
    previous_client = _LifecycleClient(
        "previous",
        stateful=True,
        events=events,
    )
    previous_state = AgentState(
        session_id="fixed-session",
        summary="fixed summary",
        context=[UserMsg(name="User", content="keep me", metadata={"nested": [1]})],
    )
    previous_agent = SimpleNamespace(state=previous_state)
    agent._agent = previous_agent
    agent._toolkit = object()
    agent._mcp_clients = [previous_client]
    agent._initialized = True
    agent._provider = "openai"
    agent._model_name = "model"
    agent._base_url = "https://example.test/v1"
    replacement_client = SimpleNamespace(is_stateful=False)

    async def connect_replacement():
        events.append("connect:replacement")
        return [replacement_client]

    def construct_agent(**kwargs):
        events.append("publish:replacement")
        return SimpleNamespace(state=kwargs["state"])

    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="raw-secret"))
    monkeypatch.setattr(agent, "_connect_mcp_clients", connect_replacement)
    monkeypatch.setattr(agent, "_build_registry_function_tools", Mock(return_value=[]))
    monkeypatch.setattr(
        agent._skill_manager,
        "get_enabled_skill_paths",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(agent_integration, "Toolkit", Mock(return_value=object()))
    monkeypatch.setattr(agent_integration, "Agent", construct_agent)
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=object()))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="configured prompt"))

    assert agent._rebuild_agent_runtime() is True

    assert events == ["close:previous", "connect:replacement", "publish:replacement"]
    assert agent._agent is not previous_agent
    replacement_state = agent._agent.state
    assert replacement_state is not previous_state
    assert replacement_state.session_id == previous_state.session_id
    assert replacement_state.summary == previous_state.summary
    assert replacement_state.context == previous_state.context
    assert replacement_state.context is not previous_state.context
    assert replacement_state.context[0] is not previous_state.context[0]
    assert replacement_state.permission_context.mode is PermissionMode.BYPASS
    assert agent._mcp_clients == [replacement_client]
    assert all(value != "raw-secret" for value in vars(agent).values())


def test_rebuild_missing_key_preserves_published_runtime(agent, monkeypatch):
    previous_agent = SimpleNamespace(state=AgentState())
    previous_toolkit = object()
    previous_client = _LifecycleClient(
        "previous",
        stateful=True,
        events=[],
    )
    agent._agent = previous_agent
    agent._toolkit = previous_toolkit
    agent._mcp_clients = [previous_client]
    agent._initialized = True
    agent._provider = "openai"
    agent._model_name = "model"
    agent._base_url = "https://example.test/v1"
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value=""))

    assert agent._rebuild_agent_runtime() is False

    assert agent._agent is previous_agent
    assert agent._toolkit is previous_toolkit
    assert agent._mcp_clients == [previous_client]
    assert agent._initialized is True
    assert previous_client.close_calls == 0


def test_rebuild_failure_after_detach_drains_local_clients_and_leaves_empty_state(
    agent,
    monkeypatch,
):
    events = []
    previous_client = _LifecycleClient("previous", stateful=True, events=events)
    replacement_client = _LifecycleClient("replacement", stateful=True, events=events)
    agent._agent = SimpleNamespace(state=AgentState(context=[]))
    agent._toolkit = object()
    agent._mcp_clients = [previous_client]
    agent._initialized = True
    agent._provider = "openai"
    agent._model_name = "model"
    agent._base_url = "https://example.test/v1"
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(
        agent,
        "_connect_mcp_clients",
        AsyncMock(return_value=[replacement_client]),
    )
    monkeypatch.setattr(agent, "_build_registry_function_tools", Mock(return_value=[]))
    monkeypatch.setattr(
        agent._skill_manager,
        "get_enabled_skill_paths",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(agent_integration, "Toolkit", Mock(return_value=object()))
    monkeypatch.setattr(
        agent_integration,
        "Agent",
        Mock(side_effect=RuntimeError("replacement boom")),
    )
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=object()))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="configured prompt"))

    assert agent._rebuild_agent_runtime() is False

    assert events == ["close:previous", "close:replacement"]
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []
    assert agent._initialized is False


def test_sync_rebuild_runtime_thread_reentry_is_rejected_without_mutation(agent):
    previous_agent = SimpleNamespace(state=AgentState())
    previous_toolkit = object()
    agent._agent = previous_agent
    agent._toolkit = previous_toolkit
    agent._initialized = True
    agent._provider = "openai"
    agent._model_name = "model"

    async def call_sync_rebuild():
        agent._rebuild_agent_runtime()

    with pytest.raises(RuntimeError, match="_rebuild_agent_runtime"):
        agent._async_runtime.run(call_sync_rebuild())

    assert agent._agent is previous_agent
    assert agent._toolkit is previous_toolkit
    assert agent._initialized is True


def _publishable_agent_runtime(agent):
    agent._agent = SimpleNamespace(state=AgentState())
    agent._toolkit = object()
    agent._initialized = True
    agent._provider = "openai"
    agent._model_name = "model"
    agent._base_url = "https://example.test/v1"


def test_exposure_change_before_initialization_does_not_start_runtime(
    agent,
    monkeypatch,
):
    registry = AgentToolRegistry.instance()
    def preinit_tool():
        return "preinit"

    toolkit_factory = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(agent_integration, "Toolkit", toolkit_factory)
    monkeypatch.setattr(
        agent_integration,
        "Agent",
        lambda **kwargs: SimpleNamespace(state=kwargs["state"]),
    )
    monkeypatch.setattr(agent, "_connect_mcp_clients", AsyncMock(return_value=[]))
    monkeypatch.setattr(agent._skill_manager, "get_enabled_skill_paths", Mock(return_value=[]))
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=object()))
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="prompt"))

    registry.register("preinit-automatic-rebuild", [preinit_tool])
    try:
        assert agent._async_runtime.is_running is False
        assert agent._exposure_rebuild_dirty is False
        assert agent._exposure_rebuild_in_progress is False
        assert agent._exposure_rebuild_idle.is_set()
        assert agent.initialize("openai", "model", "https://example.test/v1") is True
        assert len(agent._toolkit.tools) == 1
        assert agent._toolkit.tools[0]._func is preinit_tool
    finally:
        agent.shutdown()
        registry.unregister("preinit-automatic-rebuild")


def test_external_exposure_change_waits_for_automatic_rebuild(agent, monkeypatch):
    registry = AgentToolRegistry.instance()
    _publishable_agent_runtime(agent)
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    async def rebuild(*, api_key):
        assert api_key == "fresh-secret"
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.001)
        finished.set()
        return True

    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="fresh-secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)
    caller_returned = threading.Event()

    def publish():
        registry.register("external-automatic-rebuild", [lambda: None])
        caller_returned.set()

    caller = threading.Thread(target=publish)
    caller.start()
    assert started.wait(2)
    assert not caller_returned.is_set()
    release.set()
    caller.join(2)
    try:
        assert not caller.is_alive()
        assert finished.is_set()
        assert caller_returned.is_set()
        assert agent._exposure_rebuild_idle.is_set()
    finally:
        registry.unregister("external-automatic-rebuild")


def test_exposure_changes_coalesce_one_follow_up_and_all_callers_wait(
    agent,
    monkeypatch,
):
    class CountingIdleEvent:
        def __init__(self):
            self._event = threading.Event()
            self._event.set()
            self._lock = threading.Lock()
            self._waiters = 0
            self.two_followers_waiting = threading.Event()

        def clear(self):
            self._event.clear()

        def set(self):
            self._event.set()

        def is_set(self):
            return self._event.is_set()

        def wait(self, timeout=None):
            with self._lock:
                self._waiters += 1
                if self._waiters == 2:
                    self.two_followers_waiting.set()
            return self._event.wait(timeout)

    _publishable_agent_runtime(agent)
    controlled_idle = CountingIdleEvent()
    agent._exposure_rebuild_idle = controlled_idle
    first_started = threading.Event()
    release_first = threading.Event()
    calls = 0
    active = 0
    max_active = 0
    call_lock = threading.Lock()

    async def rebuild(*, api_key):
        nonlocal calls, active, max_active
        with call_lock:
            calls += 1
            call_number = calls
            active += 1
            max_active = max(max_active, active)
        try:
            if call_number == 1:
                first_started.set()
                while not release_first.is_set():
                    await asyncio.sleep(0.001)
            return True
        finally:
            with call_lock:
                active -= 1

    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)
    returned = [threading.Event(), threading.Event(), threading.Event()]

    def notify(index):
        change = SimpleNamespace(source="tools", action="changed", name=str(index))
        agent._on_exposure_change(change)
        returned[index].set()

    threads = [threading.Thread(target=notify, args=(index,)) for index in range(3)]
    threads[0].start()
    assert first_started.wait(2)
    threads[1].start()
    threads[2].start()
    assert controlled_idle.two_followers_waiting.wait(2)
    assert not any(event.is_set() for event in returned)
    release_first.set()
    for thread in threads:
        thread.join(2)

    assert all(not thread.is_alive() for thread in threads)
    assert all(event.is_set() for event in returned)
    assert calls == 2
    assert max_active == 1
    assert agent._exposure_rebuild_idle.is_set()


def test_exposure_change_in_idle_transition_is_not_lost(agent, monkeypatch):
    class PauseAfterThirdRelease:
        def __init__(self):
            self._lock = threading.Lock()
            self._release_count = 0
            self.gap_open = threading.Event()
            self.second_change_marked = threading.Event()
            self.release_gap = threading.Event()

        def __enter__(self):
            self._lock.acquire()
            return self

        def __exit__(self, exc_type, exc, tb):
            self._release_count += 1
            release_number = self._release_count
            self._lock.release()
            if release_number == 3:
                self.gap_open.set()
                assert self.release_gap.wait(2)
            elif release_number == 4:
                self.second_change_marked.set()

    _publishable_agent_runtime(agent)
    controlled_lock = PauseAfterThirdRelease()
    agent._exposure_change_lock = controlled_lock
    calls = 0

    async def rebuild(*, api_key):
        nonlocal calls
        calls += 1
        return True

    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)
    first = threading.Thread(
        target=lambda: agent._on_exposure_change(
            SimpleNamespace(source="tools", action="first", name=None),
        ),
    )
    second = threading.Thread(
        target=lambda: agent._on_exposure_change(
            SimpleNamespace(source="tools", action="second", name=None),
        ),
    )

    first.start()
    assert controlled_lock.gap_open.wait(2)
    second.start()
    assert controlled_lock.second_change_marked.wait(2)
    controlled_lock.release_gap.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert calls == 2
    assert agent._exposure_rebuild_idle.is_set()


def test_exposure_submit_failure_restores_idle_state(agent):
    _publishable_agent_runtime(agent)
    agent._async_runtime.stop()

    try:
        agent._on_exposure_change(
            SimpleNamespace(source="tools", action="changed", name=None),
        )

        assert agent._exposure_rebuild_dirty is False
        assert agent._exposure_rebuild_in_progress is False
        assert agent._exposure_rebuild_idle.is_set()
    finally:
        # Keep teardown bounded while this RED test demonstrates the stuck state.
        agent._exposure_rebuild_dirty = False
        agent._exposure_rebuild_in_progress = False
        agent._exposure_rebuild_idle.set()


def test_runtime_thread_exposure_change_schedules_without_sync_wait(
    agent,
    monkeypatch,
):
    _publishable_agent_runtime(agent)
    rebuild_started = threading.Event()
    release = threading.Event()

    async def rebuild(*, api_key):
        rebuild_started.set()
        while not release.is_set():
            await asyncio.sleep(0.001)
        return True

    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)

    async def publish_on_runtime():
        agent._on_exposure_change(
            SimpleNamespace(source="skills", action="enabled", name="writer"),
        )
        return "callback-returned"

    future = agent._async_runtime.submit(publish_on_runtime())
    assert future.result(timeout=2) == "callback-returned"
    assert rebuild_started.wait(2)
    assert not agent._exposure_rebuild_idle.is_set()
    release.set()
    assert agent._exposure_rebuild_idle.wait(2)


def test_runtime_thread_task_creation_failure_restores_idle_and_isolates_callback(
    agent,
    monkeypatch,
):
    _publishable_agent_runtime(agent)
    rebuild = AsyncMock(return_value=True)
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)
    real_create_task = asyncio.create_task
    attempts = 0

    def create_task(coroutine):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("task creation rejected")
        return real_create_task(coroutine)

    monkeypatch.setattr(agent_integration.asyncio, "create_task", create_task)

    async def publish_on_runtime():
        agent._on_exposure_change(
            SimpleNamespace(source="tools", action="changed", name="first"),
        )
        return "callback-isolated"

    try:
        assert agent._async_runtime.submit(publish_on_runtime()).result(timeout=2) == (
            "callback-isolated"
        )
        assert agent._exposure_rebuild_dirty is False
        assert agent._exposure_rebuild_in_progress is False
        assert agent._exposure_rebuild_idle.is_set()

        completed = threading.Event()
        follower = threading.Thread(
            target=lambda: (
                agent._on_exposure_change(
                    SimpleNamespace(source="tools", action="changed", name="second"),
                ),
                completed.set(),
            ),
        )
        follower.start()
        follower.join(2)
        assert not follower.is_alive()
        assert completed.is_set()
        assert rebuild.await_count == 1
        shutdown = threading.Thread(target=agent.shutdown)
        shutdown.start()
        shutdown.join(2)
        assert not shutdown.is_alive()
    finally:
        agent._exposure_rebuild_dirty = False
        agent._exposure_rebuild_in_progress = False
        agent._exposure_rebuild_idle.set()


def test_manager_replacement_rebinds_exposure_subscription(
    agent,
    monkeypatch,
    db,
):
    _publishable_agent_runtime(agent)
    old_manager = agent._skill_manager
    new_manager = SkillManager(db)
    rebuild = AsyncMock(return_value=True)
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)

    agent.set_skill_manager(new_manager)
    after_replacement = rebuild.await_count
    old_manager.add_skill("old-unsubscribed", "/old")
    assert rebuild.await_count == after_replacement
    new_manager.add_skill("new-subscribed", "/new")
    assert rebuild.await_count == after_replacement + 1
    agent.set_skill_manager(new_manager)
    assert rebuild.await_count == after_replacement + 1

    old_mcp_manager = agent._mcp_manager
    new_mcp_manager = McpServerManager(db)
    agent.set_mcp_manager(new_mcp_manager)
    after_mcp_replacement = rebuild.await_count
    old_mcp_manager.add_http_server("old-unsubscribed", "https://old.test/mcp")
    assert rebuild.await_count == after_mcp_replacement
    new_mcp_manager.add_http_server("new-subscribed", "https://new.test/mcp")
    assert rebuild.await_count == after_mcp_replacement + 1
    agent.set_mcp_manager(new_mcp_manager)
    assert rebuild.await_count == after_mcp_replacement + 1


def test_concurrent_manager_replacement_detaches_intermediate_subscription(
    agent,
    monkeypatch,
    db,
):
    class FirstPairRendezvousLock:
        def __init__(self):
            self._lock = threading.Lock()
            self._counter_lock = threading.Lock()
            self._enters = 0
            self._barrier = threading.Barrier(2)

        def __enter__(self):
            with self._counter_lock:
                self._enters += 1
                should_rendezvous = self._enters <= 2
            if should_rendezvous:
                self._barrier.wait(timeout=2)
            self._lock.acquire()
            return self

        def __exit__(self, exc_type, exc, tb):
            self._lock.release()

    old_manager = agent._skill_manager
    first_manager = SkillManager(db)
    second_manager = SkillManager(db)
    agent._exposure_change_lock = FirstPairRendezvousLock()
    replacements = [
        threading.Thread(target=agent.set_skill_manager, args=(first_manager,)),
        threading.Thread(target=agent.set_skill_manager, args=(second_manager,)),
    ]
    for replacement in replacements:
        replacement.start()
    for replacement in replacements:
        replacement.join(2)
    assert all(not replacement.is_alive() for replacement in replacements)

    final_manager = agent._skill_manager
    intermediate_manager = (
        second_manager if final_manager is first_manager else first_manager
    )
    bound_skill_managers = [
        source
        for source, _token in agent._exposure_subscriptions
        if source in {old_manager, first_manager, second_manager}
    ]
    assert bound_skill_managers == [final_manager]

    _publishable_agent_runtime(agent)
    rebuild = AsyncMock(return_value=True)
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)
    intermediate_manager.add_skill("intermediate", "/intermediate")
    assert rebuild.await_count == 0
    final_manager.add_skill("final", "/final")
    assert rebuild.await_count == 1


def test_mcp_and_skill_events_trigger_automatic_rebuild(agent, monkeypatch):
    _publishable_agent_runtime(agent)
    rebuild = AsyncMock(return_value=True)
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)

    agent._mcp_manager.add_http_server("automatic", "https://example.test/mcp")
    assert rebuild.await_count == 1
    agent._skill_manager.add_skill("automatic", "/skills/automatic")
    assert rebuild.await_count == 2


def test_permission_changes_automatically_filter_and_restore_owned_group(
    api_key_manager,
    node_engine,
    mcp_manager,
    skill_manager,
    monkeypatch,
):
    AgentToolRegistry._reset_for_testing()
    registry = AgentToolRegistry.instance()
    permissions = PermissionManager()
    integration = AgentIntegration(
        api_key_manager,
        node_engine,
        mcp_manager=mcp_manager,
        skill_manager=skill_manager,
        permission_manager=permissions,
    )
    def tool():
        return "owned"

    monkeypatch.setattr(integration._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(integration, "_connect_mcp_clients", AsyncMock(return_value=[]))
    monkeypatch.setattr(skill_manager, "get_enabled_skill_paths", Mock(return_value=[]))
    monkeypatch.setattr(
        agent_integration,
        "Toolkit",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        agent_integration,
        "Agent",
        lambda **kwargs: SimpleNamespace(state=kwargs["state"]),
    )
    monkeypatch.setattr(integration, "_create_model", Mock(return_value=object()))
    monkeypatch.setattr(integration.config, "get", Mock(return_value="prompt"))
    _publishable_agent_runtime(integration)

    try:
        registry.register("owned-automatic", [tool], owner_name="owned-plugin")
        assert integration._toolkit.tools == []

        permissions.grant("owned-plugin", Permission.AGENT_TOOL)
        assert len(integration._toolkit.tools) == 1
        assert integration._toolkit.tools[0]._func is tool

        assert permissions.revoke("owned-plugin", Permission.AGENT_TOOL) is True
        assert integration._toolkit.tools == []
    finally:
        integration.shutdown()
        registry.unregister("owned-automatic")
        AgentToolRegistry._reset_for_testing()


def test_shutdown_waits_for_running_exposure_drain(agent, monkeypatch):
    registry = AgentToolRegistry.instance()
    _publishable_agent_runtime(agent)
    started = threading.Event()
    release = threading.Event()

    async def rebuild(*, api_key):
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.001)
        return True

    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)
    publisher = threading.Thread(
        target=lambda: registry.register("shutdown-waits", [lambda: None]),
    )
    publisher.start()
    assert started.wait(2)
    shutdown = threading.Thread(target=agent.shutdown)
    shutdown.start()
    time.sleep(0.05)
    assert shutdown.is_alive()
    release.set()
    publisher.join(2)
    shutdown.join(2)
    try:
        assert not publisher.is_alive()
        assert not shutdown.is_alive()
        assert agent._exposure_rebuild_idle.is_set()
        assert agent._async_runtime.is_running is False
    finally:
        registry.unregister("shutdown-waits")


def test_shutdown_unsubscribes_before_stop_and_post_shutdown_is_terminal(
    agent,
    monkeypatch,
):
    registry = AgentToolRegistry.instance()
    _publishable_agent_runtime(agent)
    rebuild = AsyncMock(return_value=True)
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent, "_rebuild_agent_runtime_impl", rebuild)

    agent.shutdown()
    agent.shutdown()
    before = rebuild.await_count
    registry.register("post-shutdown-unsubscribe", [lambda: None])
    try:
        assert rebuild.await_count == before
        assert agent._async_runtime.is_running is False
        assert agent._exposure_subscriptions == []
        assert agent._exposure_rebuild_idle.is_set()
    finally:
        registry.unregister("post-shutdown-unsubscribe")


@pytest.mark.parametrize("api_key", ["short", "a-very-long-raw-api-key"])
def test_initialize_never_stores_raw_api_key(agent, monkeypatch, api_key):
    _configure_successful_initialize(agent, monkeypatch)
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value=api_key))
    monkeypatch.setattr(agent, "_connect_mcp_clients", AsyncMock(return_value=[]))

    assert agent.initialize("openai", "model", "https://example.test/v1") is True

    assert agent._api_key != api_key
    assert api_key not in agent._api_key
    assert all(value != api_key for value in vars(agent).values())


def test_initialize_without_skill_manager_uses_empty_constructor_skills(
    api_key_manager,
    node_engine,
    monkeypatch,
):
    agent = AgentIntegration(
        api_key_manager=api_key_manager,
        node_engine=node_engine,
        skill_manager=None,
    )
    try:
        toolkit_factory = _configure_successful_initialize(agent, monkeypatch)

        assert agent.initialize("openai", "model", "https://example.test/v1") is True

        toolkit_factory.assert_called_once_with(
            tools=[],
            mcps=[],
            skills_or_loaders=[],
        )
    finally:
        agent.shutdown()


def test_initialize_filters_invalid_skill_before_toolkit_construction(
    agent,
    monkeypatch,
    tmp_path,
):
    valid_dir = tmp_path / "valid-skill"
    valid_dir.mkdir()
    (valid_dir / "SKILL.md").write_text(
        "---\nname: valid-skill\ndescription: A test skill.\n---\n\n# Valid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        agent._skill_manager,
        "get_enabled_skills",
        Mock(
            return_value=[
                {
                    "name": "missing-skill",
                    "path": str(tmp_path / "missing"),
                    "description": None,
                },
                {
                    "name": "valid-skill",
                    "path": str(valid_dir),
                    "description": None,
                },
            ],
        ),
    )
    monkeypatch.setattr(agent, "_connect_mcp_clients", AsyncMock(return_value=[]))
    toolkit_factory = _configure_successful_initialize(
        agent,
        monkeypatch,
        mock_skill_paths=False,
    )

    assert agent.initialize("openai", "model", "https://example.test/v1") is True

    toolkit_factory.assert_called_once_with(
        tools=[],
        mcps=[],
        skills_or_loaders=[str(valid_dir.resolve())],
    )


def test_connect_mcp_clients_prepares_enabled_clients_in_manager_order(agent, monkeypatch):
    events = []
    stateful = _LifecycleClient("stdio", stateful=True, events=events)
    stateless = _LifecycleClient("http", stateful=False, events=events)
    factory = Mock(side_effect=lambda name: {"stdio": stateful, "http": stateless}[name])
    monkeypatch.setattr(
        agent._mcp_manager,
        "list_servers",
        Mock(
            return_value=[
                {"name": "stdio", "enabled": True},
                {"name": "disabled", "enabled": False},
                {"name": "http", "enabled": True},
            ],
        ),
    )
    monkeypatch.setattr(agent._mcp_manager, "create_agentscope_client", factory)

    clients = agent._async_runtime.run(agent._connect_mcp_clients())

    assert clients == [stateful, stateless]
    assert events == ["connect:stdio"]
    assert factory.call_args_list == [call("stdio"), call("http")]


def test_connect_mcp_clients_excludes_named_failures_and_keeps_successes(
    agent,
    monkeypatch,
):
    events = []
    first = _LifecycleClient("first", stateful=True, events=events)
    broken = _LifecycleClient(
        "broken-connect",
        stateful=True,
        events=events,
        connect_error=RuntimeError("connect boom"),
    )
    last = _LifecycleClient("last", stateful=False, events=events)

    def create(name):
        if name == "factory-error":
            raise RuntimeError("factory boom")
        return {
            "first": first,
            "missing": None,
            "broken-connect": broken,
            "last": last,
        }[name]

    names = ["first", "missing", "factory-error", "broken-connect", "last"]
    monkeypatch.setattr(
        agent._mcp_manager,
        "list_servers",
        Mock(return_value=[{"name": name, "enabled": True} for name in names]),
    )
    monkeypatch.setattr(
        agent._mcp_manager,
        "create_agentscope_client",
        Mock(side_effect=create),
    )
    warning = Mock()
    error = Mock()
    monkeypatch.setattr(agent_integration._logger, "warning", warning)
    monkeypatch.setattr(agent_integration._logger, "error", error)

    clients = agent._async_runtime.run(agent._connect_mcp_clients())

    assert clients == [first, last]
    assert broken.close_calls == 1
    assert events == [
        "connect:first",
        "connect:broken-connect",
        "close:broken-connect",
    ]
    logged = " ".join(
        str(args[0])
        for logger in (warning, error)
        for args, _ in logger.call_args_list
    )
    for name in ("missing", "factory-error", "broken-connect"):
        assert name in logged


def test_initialize_failure_closes_owned_stateful_clients(agent, monkeypatch):
    events = []
    stateful = _LifecycleClient("stdio", stateful=True, events=events)
    stateless = _LifecycleClient("http", stateful=False, events=events)
    monkeypatch.setattr(
        agent,
        "_connect_mcp_clients",
        AsyncMock(return_value=[stateful, stateless]),
    )
    _configure_successful_initialize(
        agent,
        monkeypatch,
        toolkit_factory=Mock(side_effect=RuntimeError("toolkit boom")),
    )

    assert agent.initialize("openai", "model", "https://example.test/v1") is False

    assert stateful.close_calls == 1
    assert stateless.close_calls == 0
    assert agent._mcp_clients == []


def test_shutdown_closes_stateful_once_continues_after_named_failure(
    agent,
    monkeypatch,
):
    events = []
    first = _LifecycleClient(
        "first",
        stateful=True,
        events=events,
        close_error=RuntimeError("close boom"),
    )
    stateless = _LifecycleClient("http", stateful=False, events=events)
    last = _LifecycleClient("last", stateful=True, events=events)
    agent._mcp_clients = [first, stateless, last]
    warning = Mock()
    monkeypatch.setattr(agent_integration._logger, "warning", warning)

    agent.shutdown()
    agent.shutdown()

    assert first.close_calls == 1
    assert stateless.close_calls == 0
    assert last.close_calls == 1
    assert events == ["close:first", "close:last"]
    assert "first" in str(warning.call_args.args[0])
    assert agent._mcp_clients == []


def test_reset_closes_owned_stateful_client(agent):
    client = _LifecycleClient("reset", stateful=True, events=[])
    agent._mcp_clients = [client]

    agent.reset()

    assert client.close_calls == 1
    assert agent._mcp_clients == []


def test_reinitialize_closes_previous_clients_before_connecting_new_ones(
    agent,
    monkeypatch,
):
    events = []
    previous = _LifecycleClient("previous", stateful=True, events=events)
    replacement = _LifecycleClient("replacement", stateful=False, events=events)
    agent._mcp_clients = [previous]

    async def connect_replacement():
        events.append("prepare:replacement")
        return [replacement]

    monkeypatch.setattr(agent, "_connect_mcp_clients", connect_replacement)
    toolkit_factory = _configure_successful_initialize(agent, monkeypatch)

    assert agent.initialize("openai", "model", "https://example.test/v1") is True

    assert events == ["close:previous", "prepare:replacement"]
    assert agent._mcp_clients == [replacement]
    toolkit_factory.assert_called_once_with(
        tools=[],
        mcps=[replacement],
        skills_or_loaders=[],
    )


def test_validation_failure_preserves_working_runtime_state(agent, monkeypatch):
    previous_agent = object()
    previous_toolkit = object()
    previous_client = _LifecycleClient("previous", stateful=True, events=[])
    agent._agent = previous_agent
    agent._toolkit = previous_toolkit
    agent._mcp_clients = [previous_client]
    agent._initialized = True
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value=""))

    assert agent.initialize("openai", "model", "https://example.test/v1") is False

    assert agent._agent is previous_agent
    assert agent._toolkit is previous_toolkit
    assert agent._mcp_clients == [previous_client]
    assert agent._initialized is True
    assert previous_client.close_calls == 0


def test_config_validation_exception_preserves_working_runtime_state(
    agent,
    monkeypatch,
):
    previous_agent = object()
    previous_toolkit = object()
    previous_client = _LifecycleClient("previous", stateful=True, events=[])
    agent._agent = previous_agent
    agent._toolkit = previous_toolkit
    agent._mcp_clients = [previous_client]
    agent._initialized = True
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(
        agent._api_manager,
        "get_config",
        Mock(side_effect=RuntimeError("config invalid")),
    )

    assert agent.initialize("openai", "model", "https://example.test/v1") is False
    assert agent._agent is previous_agent
    assert agent._toolkit is previous_toolkit
    assert agent._mcp_clients == [previous_client]
    assert agent._initialized is True
    assert previous_client.close_calls == 0


@pytest.mark.parametrize("failure_stage", ["toolkit", "model", "agent"])
def test_replacement_construction_failure_publishes_exact_empty_state(
    agent,
    monkeypatch,
    failure_stage,
):
    client = _LifecycleClient("new", stateful=True, events=[])
    monkeypatch.setattr(
        agent,
        "_connect_mcp_clients",
        AsyncMock(return_value=[client]),
    )
    toolkit_factory = (
        Mock(side_effect=RuntimeError("toolkit boom"))
        if failure_stage == "toolkit"
        else None
    )
    _configure_successful_initialize(agent, monkeypatch, toolkit_factory=toolkit_factory)
    if failure_stage == "model":
        monkeypatch.setattr(
            agent,
            "_create_model",
            Mock(side_effect=RuntimeError("model boom")),
        )
    if failure_stage == "agent":
        monkeypatch.setattr(
            agent_integration,
            "Agent",
            Mock(side_effect=RuntimeError("agent boom")),
        )
    agent._agent = object()
    agent._toolkit = object()
    agent._initialized = True

    assert agent.initialize("openai", "model", "https://example.test/v1") is False

    assert client.close_calls == 1
    assert agent._initialized is False
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []


def test_toolkit_rejection_of_validated_skill_closes_connected_mcp_and_clears_state(
    agent,
    monkeypatch,
):
    client = _LifecycleClient("new", stateful=True, events=[])
    skill_paths = ["C:\\skills\\malformed-metadata"]
    monkeypatch.setattr(
        agent,
        "_connect_mcp_clients",
        AsyncMock(return_value=[client]),
    )
    monkeypatch.setattr(
        agent._skill_manager,
        "get_enabled_skill_paths",
        Mock(return_value=skill_paths),
        raising=False,
    )
    toolkit_factory = Mock(side_effect=ValueError("invalid skill metadata"))
    monkeypatch.setattr(agent_integration, "Toolkit", toolkit_factory)
    monkeypatch.setattr(agent, "_build_registry_function_tools", Mock(return_value=[]))
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))

    assert agent.initialize("openai", "model", "https://example.test/v1") is False

    toolkit_factory.assert_called_once_with(
        tools=[],
        mcps=[client],
        skills_or_loaders=skill_paths,
    )
    assert client.close_calls == 1
    assert agent._initialized is False
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []


def test_function_level_server_record_failure_closes_local_successes(
    agent,
    monkeypatch,
):
    first = _LifecycleClient("first", stateful=True, events=[])
    records = iter([
        {"name": "first", "enabled": True},
        {"enabled": True},
    ])
    monkeypatch.setattr(agent._mcp_manager, "list_servers", Mock(return_value=records))
    monkeypatch.setattr(
        agent._mcp_manager,
        "create_agentscope_client",
        Mock(return_value=first),
    )

    with pytest.raises(KeyError):
        agent._async_runtime.run(agent._connect_mcp_clients())

    assert first.close_calls == 1


def test_sync_and_async_chat_share_stateful_mcp_runtime_loop(agent, monkeypatch):
    client = _LifecycleClient("stateful", stateful=True, events=[])
    monkeypatch.setattr(
        agent._mcp_manager,
        "list_servers",
        Mock(return_value=[{"name": "stateful", "enabled": True}]),
    )
    monkeypatch.setattr(
        agent._mcp_manager,
        "create_agentscope_client",
        Mock(return_value=client),
    )
    monkeypatch.setattr(agent, "_build_registry_function_tools", Mock(return_value=[]))
    monkeypatch.setattr(agent, "_create_model", Mock(return_value=object()))
    monkeypatch.setattr(
        agent._skill_manager,
        "get_enabled_skill_paths",
        Mock(return_value=[]),
        raising=False,
    )
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))
    monkeypatch.setattr(agent.config, "get", Mock(return_value="prompt"))
    monkeypatch.setattr(agent_integration, "Toolkit", Mock(return_value=object()))

    class LoopUsingAgent:
        def __init__(self, **kwargs):
            self.state = kwargs["state"]

        async def reply_stream(self, *, inputs):
            operation = inputs.get_text_content()
            await client.operate(operation)
            from agentscope.event import ReplyEndEvent, ReplyStartEvent

            yield ReplyStartEvent(
                session_id="session",
                reply_id=f"reply-{operation}",
                name="Assistant",
            )
            yield ReplyEndEvent(session_id="session", reply_id=f"reply-{operation}")

    monkeypatch.setattr(agent_integration, "Agent", LoopUsingAgent)

    assert agent.initialize("openai", "model", "https://example.test/v1") is True
    runtime_loop = agent._async_runtime.run(_current_loop())
    assert agent.chat("sync-chat") == ""
    asyncio.run(agent.chat_async("async-chat"))
    agent.reset()

    assert [item[0] for item in client.loop_observations] == [
        "connect",
        "sync-chat",
        "async-chat",
        "close",
    ]
    assert all(loop is runtime_loop for _, loop, _ in client.loop_observations)
    assert all(closed is False for _, _, closed in client.loop_observations)


def _configure_gated_runtime_initialize(agent, monkeypatch, client):
    _configure_successful_initialize(agent, monkeypatch)
    monkeypatch.setattr(
        agent._mcp_manager,
        "list_servers",
        Mock(return_value=[{"name": client.name, "enabled": True}]),
    )
    monkeypatch.setattr(
        agent._mcp_manager,
        "create_agentscope_client",
        Mock(return_value=client),
    )


def test_cancelled_initialize_future_closes_connected_local_client(
    agent,
    monkeypatch,
):
    client = _GatedConnectClient("gated", events=[])
    _configure_gated_runtime_initialize(agent, monkeypatch, client)
    future = agent._async_runtime.submit(
        agent._initialize_impl(
            provider="openai",
            model_name="model",
            base_url="https://example.test/v1",
            api_key="secret",
        ),
    )
    assert client.connect_started.wait(timeout=1)

    assert future.cancel() is True
    with pytest.raises(concurrent.futures.CancelledError):
        future.result(timeout=1)

    assert client.close_finished.wait(timeout=1)
    assert client.close_calls == 1
    assert agent._initialized is False
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []


def test_initialize_old_published_fatal_close_drains_and_exposes_empty_state(
    agent,
    monkeypatch,
):
    first = _LifecycleClient(
        "first",
        stateful=True,
        events=[],
        close_error=asyncio.CancelledError(),
    )
    later = _LifecycleClient("later", stateful=True, events=[])
    agent._agent = object()
    agent._toolkit = object()
    agent._mcp_clients = [first, later]
    agent._initialized = True
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))

    assert agent.initialize("openai", "model", "https://example.test/v1") is False

    assert first.close_calls == 1
    assert later.close_calls == 1
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []
    assert agent._initialized is False


def test_local_cleanup_fatal_close_drains_all_and_preserves_construct_error(
    agent,
    monkeypatch,
):
    first = _LifecycleClient(
        "first",
        stateful=True,
        events=[],
        close_error=_CleanupAbort("cleanup abort"),
    )
    later = _LifecycleClient("later", stateful=True, events=[])
    monkeypatch.setattr(
        agent,
        "_connect_mcp_clients",
        AsyncMock(return_value=[first, later]),
    )
    _configure_successful_initialize(
        agent,
        monkeypatch,
        toolkit_factory=Mock(side_effect=RuntimeError("construct boom")),
    )

    with pytest.raises(RuntimeError, match="construct boom"):
        agent._async_runtime.run(
            agent._initialize_impl(
                provider="openai",
                model_name="model",
                base_url="https://example.test/v1",
                api_key="secret",
            ),
        )

    assert first.close_calls == 1
    assert later.close_calls == 1


def test_connect_error_is_not_replaced_by_cleanup_fatal(agent, monkeypatch):
    client = _LifecycleClient(
        "broken",
        stateful=True,
        events=[],
        connect_error=RuntimeError("connect boom"),
        close_error=_CleanupAbort("cleanup abort"),
    )
    monkeypatch.setattr(
        agent._mcp_manager,
        "list_servers",
        Mock(return_value=[{"name": "broken", "enabled": True}]),
    )
    monkeypatch.setattr(
        agent._mcp_manager,
        "create_agentscope_client",
        Mock(return_value=client),
    )
    error = Mock()
    monkeypatch.setattr(agent_integration._logger, "error", error)

    assert agent._async_runtime.run(agent._connect_mcp_clients()) == []
    assert client.close_calls == 1
    assert "connect boom" in str(error.call_args.args[0])


def test_cancel_during_isolated_connect_failure_cleanup_stops_initialize(
    agent,
    monkeypatch,
):
    failed = _GatedCloseAfterConnectErrorClient("failed", events=[])
    later = _LifecycleClient("later", stateful=False, events=[])
    created_servers = []

    def create_client(server_name):
        created_servers.append(server_name)
        return {"failed": failed, "later": later}[server_name]

    _configure_successful_initialize(agent, monkeypatch)
    monkeypatch.setattr(
        agent._mcp_manager,
        "list_servers",
        Mock(
            return_value=[
                {"name": "failed", "enabled": True},
                {"name": "later", "enabled": True},
            ],
        ),
    )
    monkeypatch.setattr(
        agent._mcp_manager,
        "create_agentscope_client",
        Mock(side_effect=create_client),
    )
    initialize_finished = threading.Event()

    async def initialize_with_completion_signal():
        try:
            return await agent._initialize_impl(
                provider="openai",
                model_name="model",
                base_url="https://example.test/v1",
                api_key="secret",
            )
        finally:
            initialize_finished.set()

    future = agent._async_runtime.submit(initialize_with_completion_signal())
    assert failed.close_started.wait(timeout=1)

    assert future.cancel() is True
    failed.release_close.set()

    assert failed.close_finished.wait(timeout=1)
    assert initialize_finished.wait(timeout=1)
    with pytest.raises(concurrent.futures.CancelledError):
        future.result(timeout=1)
    assert created_servers == ["failed"]
    assert failed.close_calls == 1
    assert agent._initialized is False
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []


@pytest.mark.parametrize("competing_lifecycle", ["reset", "shutdown"])
def test_initialize_transaction_serializes_with_reset_or_shutdown(
    agent,
    monkeypatch,
    competing_lifecycle,
):
    client = _GatedConnectClient("gated", events=[])
    _configure_gated_runtime_initialize(agent, monkeypatch, client)
    initialize_result = []
    initialize_thread = threading.Thread(
        target=lambda: initialize_result.append(
            agent.initialize("openai", "model", "https://example.test/v1")
        ),
    )
    lifecycle_done = threading.Event()
    lifecycle_thread = threading.Thread(
        target=lambda: (
            getattr(agent, competing_lifecycle)(),
            lifecycle_done.set(),
        ),
    )

    initialize_thread.start()
    assert client.connect_started.wait(timeout=1)
    lifecycle_thread.start()
    time.sleep(0.05)
    completed_before_initialize_released = lifecycle_done.is_set()
    client.release_connect.set()
    initialize_thread.join(timeout=2)
    lifecycle_thread.join(timeout=2)

    assert completed_before_initialize_released is False
    assert not initialize_thread.is_alive()
    assert not lifecycle_thread.is_alive()
    assert initialize_result == [True]
    assert client.close_calls == 1
    assert agent._initialized is False
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []
    assert agent._async_runtime.is_running is (competing_lifecycle == "reset")


def test_reset_first_serializes_history_clear_before_initialize_state(
    agent,
    monkeypatch,
):
    agent._history.add_message(
        msg=UserMsg(name="User", content="must be cleared before initialize"),
    )
    _configure_successful_initialize(agent, monkeypatch)
    monkeypatch.setattr(
        agent,
        "_connect_mcp_clients",
        AsyncMock(return_value=[]),
    )
    constructed_agent = SimpleNamespace(state=None)
    agent_factory = Mock(return_value=constructed_agent)
    monkeypatch.setattr(agent_integration, "Agent", agent_factory)
    reset_at_tail = threading.Event()
    release_reset = threading.Event()
    original_reset_transaction = agent._reset_transaction

    async def gated_reset_transaction():
        await original_reset_transaction()
        reset_at_tail.set()
        while not release_reset.is_set():
            await asyncio.sleep(0.001)

    monkeypatch.setattr(agent, "_reset_transaction", gated_reset_transaction)
    reset_thread = threading.Thread(target=agent.reset)
    initialize_result = []
    initialize_thread = threading.Thread(
        target=lambda: initialize_result.append(
            agent.initialize("openai", "model", "https://example.test/v1")
        ),
    )

    reset_thread.start()
    assert reset_at_tail.wait(timeout=1)
    initialize_thread.start()
    time.sleep(0.05)
    initialize_waited_for_reset = initialize_thread.is_alive()
    release_reset.set()
    reset_thread.join(timeout=2)
    initialize_thread.join(timeout=2)

    assert initialize_waited_for_reset is True
    assert not reset_thread.is_alive()
    assert not initialize_thread.is_alive()
    assert initialize_result == [True]
    published_state = agent_factory.call_args.kwargs["state"]
    assert published_state.context == []
    assert agent._history.get_messages() == []


@pytest.mark.parametrize(
    "lifecycle_method",
    ["initialize", "reset", "switch_session", "shutdown"],
)
def test_sync_lifecycle_reentry_from_runtime_thread_raises_without_mutation(
    agent,
    monkeypatch,
    lifecycle_method,
):
    client = _LifecycleClient("owned", stateful=True, events=[])
    original_agent = object()
    original_toolkit = object()
    agent._agent = original_agent
    agent._toolkit = original_toolkit
    agent._mcp_clients = [client]
    agent._initialized = True
    agent._history_repository = object()
    monkeypatch.setattr(agent._api_manager, "get_key", Mock(return_value="secret"))
    monkeypatch.setattr(agent._api_manager, "get_config", Mock(return_value=None))

    async def invoke():
        if lifecycle_method == "initialize":
            return agent.initialize("openai", "model", "https://example.test/v1")
        if lifecycle_method == "switch_session":
            return agent.switch_session("selected")
        return getattr(agent, lifecycle_method)()

    with pytest.raises(RuntimeError, match="runtime thread"):
        agent._async_runtime.run(invoke())

    assert agent._agent is original_agent
    assert agent._toolkit is original_toolkit
    assert agent._mcp_clients == [client]
    assert agent._initialized is True
    assert client.close_calls == 0
    assert agent._async_runtime.is_running is True


def test_reset_failure_preserves_history_and_published_state(agent, monkeypatch):
    original_agent = object()
    original_toolkit = object()
    agent._agent = original_agent
    agent._toolkit = original_toolkit
    agent._initialized = True
    agent._history.add_message("user", "preserve me")

    async def fail_reset():
        raise RuntimeError("reset failed")

    monkeypatch.setattr(agent, "_reset_impl", fail_reset)

    with pytest.raises(RuntimeError, match="reset failed"):
        agent.reset()

    assert len(agent.get_history()) == 1
    assert agent._agent is original_agent
    assert agent._toolkit is original_toolkit
    assert agent._initialized is True


def test_reset_published_fatal_close_drains_to_empty_but_preserves_history(agent):
    first = _LifecycleClient(
        "first",
        stateful=True,
        events=[],
        close_error=asyncio.CancelledError(),
    )
    later = _LifecycleClient("later", stateful=True, events=[])
    agent._agent = object()
    agent._toolkit = object()
    agent._mcp_clients = [first, later]
    agent._initialized = True
    agent._history.add_message("user", "preserve until cleanup succeeds")

    with pytest.raises(concurrent.futures.CancelledError):
        agent.reset()

    assert first.close_calls == 1
    assert later.close_calls == 1
    assert agent._agent is None
    assert agent._toolkit is None
    assert agent._mcp_clients == []
    assert agent._initialized is False
    assert len(agent.get_history()) == 1


def test_stable_core_imports_keep_agentscope_available(monkeypatch):
    module_path = agent_integration.__file__
    spec = importlib.util.spec_from_file_location(
        "isolated_agent_integration_mcp_failure",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    isolated_module = importlib.util.module_from_spec(spec)
    real_import = builtins.__import__
    blocked_imports = []

    def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "agentscope.mcp":
            blocked_imports.append(name)
            raise ImportError("simulated missing MCP integration")
        return real_import(name, globals, locals, fromlist, level)

    with monkeypatch.context() as import_patch:
        import_patch.setattr(builtins, "__import__", controlled_import)
        spec.loader.exec_module(isolated_module)

    assert blocked_imports == ["agentscope.mcp"]
    assert isolated_module.AGENTSCOPE_AVAILABLE is True
    assert isolated_module.Agent is not None
    assert isolated_module.ReActConfig is not None
    assert isolated_module.AgentState is not None
    assert isolated_module.Toolkit is not None
    assert not hasattr(isolated_module, "ReAct" + "Agent")
    assert not hasattr(isolated_module, "InMemory" + "Memory")
    assert not hasattr(isolated_module, "DashScopeChatFormatter")
    assert not hasattr(isolated_module, "DeepSeekChatFormatter")
    assert not hasattr(isolated_module, "OpenAIChatFormatter")


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


def test_switch_session_false_after_partial_history_mutation_restores_snapshot(agent):
    previous_messages = [AssistantMsg(name="Assistant", content="previous")]
    previous_state = AgentState(context=previous_messages)
    agent._agent = SimpleNamespace(state=previous_state)
    agent._history_repository = object()

    class PartialFailureHistory:
        def __init__(self):
            self._lock = threading.Lock()
            self._session_id = "old-session"
            self._is_new_session = False
            self._messages = list(previous_messages)

        @property
        def session_id(self):
            return self._session_id

        def get_messages(self):
            return list(self._messages)

        def set_session(self, session_id):
            self._session_id = session_id
            self._is_new_session = False
            self._messages = [UserMsg(name="User", content="partially loaded")]
            return False

    history = PartialFailureHistory()
    agent._history = history

    assert agent.switch_session("broken-session") is False
    assert history._session_id == "old-session"
    assert history._is_new_session is False
    assert history._messages == previous_messages
    assert agent._agent.state is previous_state


@pytest.mark.parametrize(
    "selection_error",
    [RuntimeError("selection failed"), _SelectionAbort("selection aborted")],
)
def test_switch_session_raise_after_partial_mutation_restores_snapshot(
    agent,
    selection_error,
):
    previous_messages = [AssistantMsg(name="Assistant", content="previous")]
    previous_state = AgentState(context=previous_messages)
    agent._agent = SimpleNamespace(state=previous_state)
    agent._history_repository = object()

    class RaisingHistory:
        def __init__(self):
            self._lock = threading.Lock()
            self._session_id = "old-session"
            self._is_new_session = False
            self._messages = list(previous_messages)

        def set_session(self, session_id):
            self._session_id = session_id
            self._is_new_session = True
            self._messages = [UserMsg(name="User", content="partial")]
            raise selection_error

    history = RaisingHistory()
    agent._history = history

    if isinstance(selection_error, Exception):
        assert agent.switch_session("broken-session") is False
    else:
        with pytest.raises(_SelectionAbort, match="selection aborted"):
            agent.switch_session("broken-session")

    assert history._session_id == "old-session"
    assert history._is_new_session is False
    assert history._messages == previous_messages
    assert agent._agent.state is previous_state


def test_switch_session_state_publication_failure_rolls_back_empty_selection(
    agent,
    monkeypatch,
):
    previous_messages = [AssistantMsg(name="Assistant", content="previous")]
    previous_state = AgentState(context=previous_messages)
    agent._agent = SimpleNamespace(state=previous_state)
    agent._history_repository = object()

    class SwitchingHistory:
        def __init__(self):
            import threading

            self._lock = threading.Lock()
            self._session_id = None
            self._is_new_session = True
            self._messages = list(previous_messages)

        @property
        def session_id(self):
            return self._session_id

        def set_session(self, session_id):
            self._session_id = session_id
            self._messages = [UserMsg(name="User", content="selected")]
            return True

        def get_messages(self):
            return list(self._messages)

    history = SwitchingHistory()
    agent._history = history
    async def partially_publish_then_fail():
        agent._agent.state = AgentState(
            context=[UserMsg(name="User", content="incorrect new state")],
        )
        raise RuntimeError("publish failed")

    monkeypatch.setattr(
        agent,
        "_sync_history_to_memory_impl",
        partially_publish_then_fail,
    )

    assert agent.switch_session("selected-session") is False
    assert history.session_id is None
    assert history._messages == previous_messages
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

    def test_change_notifications_cover_skill_mutations_and_noops(
        self, skill_manager, tmp_path
    ):
        events = []
        observations = []

        def listener(event):
            events.append((event.source, event.action, event.name))
            observations.append(skill_manager.get_skill(event.name))

        token = skill_manager.subscribe_changes(listener)
        skill_manager.add_skill("writer", "/skills/writer", "first")
        with pytest.raises(ValueError):
            skill_manager.add_skill("writer", "/duplicate")
        assert skill_manager.update_skill("missing", path="/missing") is False
        assert skill_manager.update_skill("writer", description="second") is True
        assert skill_manager.set_enabled("writer", True) is True
        assert skill_manager.set_enabled("missing", False) is False
        assert skill_manager.set_enabled("writer", False) is True
        assert skill_manager.set_enabled("writer", True) is True
        assert skill_manager.delete_skill("missing") is False
        assert skill_manager.delete_skill("writer") is True

        discovered = tmp_path / "skills"
        child = discovered / "discovered"
        child.mkdir(parents=True)
        (child / "SKILL.md").write_text(
            "---\ndescription: discovered\n---\n", encoding="utf-8"
        )
        assert skill_manager.discover_and_register(discovered) == 1
        assert skill_manager.discover_and_register(discovered) == 0
        skill_manager.unsubscribe_changes(token)
        skill_manager.delete_skill("discovered")

        assert events == [
            ("skills", "added", "writer"),
            ("skills", "updated", "writer"),
            ("skills", "disabled", "writer"),
            ("skills", "enabled", "writer"),
            ("skills", "deleted", "writer"),
            ("skills", "added", "discovered"),
        ]
        assert observations[0]["description"] == "first"
        assert observations[1]["description"] == "second"
        assert observations[2]["enabled"] is False
        assert observations[3]["enabled"] is True
        assert observations[4] is None
        assert observations[5]["name"] == "discovered"

    def test_get_enabled_skill_paths_filters_invalid_entries_in_manager_order(
        self,
        skill_manager,
        tmp_path,
        monkeypatch,
    ):
        warning = Mock()
        monkeypatch.setattr(skill_manager_module._logger, "warning", warning)

        def write_skill(directory, name):
            directory.mkdir()
            (directory / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: A test skill.\n---\n\n"
                f"# {name}\n\nFollow these instructions.\n",
                encoding="utf-8",
            )

        first_valid = tmp_path / "first-valid"
        disabled_valid = tmp_path / "disabled-valid"
        missing_manifest = tmp_path / "missing-manifest"
        file_path = tmp_path / "not-a-directory"
        undecodable = tmp_path / "undecodable"
        later_valid = tmp_path / "later-valid"
        write_skill(first_valid, "first-valid")
        write_skill(disabled_valid, "disabled-valid")
        missing_manifest.mkdir()
        file_path.write_text("not a directory", encoding="utf-8")
        undecodable.mkdir()
        (undecodable / "SKILL.md").write_bytes(b"\xff\xfe")
        write_skill(later_valid, "later-valid")

        records = [
            ("first-valid", first_valid, True),
            ("disabled-valid", disabled_valid, False),
            ("missing-manifest", missing_manifest, True),
            ("missing-path", tmp_path / "does-not-exist", True),
            ("file-path", file_path, True),
            ("undecodable", undecodable, True),
            ("later-valid", later_valid, True),
        ]
        for name, path, enabled in records:
            skill_manager.add_skill(name, str(path))
            if not enabled:
                skill_manager.set_enabled(name, False)

        assert hasattr(skill_manager, "get_enabled_skill_paths"), (
            "SkillManager must expose validated enabled Skill paths"
        )
        paths = skill_manager.get_enabled_skill_paths()

        assert paths == [str(first_valid.resolve()), str(later_valid.resolve())]
        warning_text = "\n".join(item.args[0] for item in warning.call_args_list)
        for name, path, enabled in records:
            if enabled and name not in {"first-valid", "later-valid"}:
                assert name in warning_text
                assert str(path) in warning_text
        assert "disabled-valid" not in warning_text
        assert str(disabled_valid) not in warning_text

    def test_get_enabled_skill_paths_rejects_empty_and_non_string_paths(
        self,
        skill_manager,
        monkeypatch,
    ):
        warning = Mock()
        monkeypatch.setattr(skill_manager_module._logger, "warning", warning)
        enabled_records = [
            {"name": "missing-path", "path": None, "description": None},
            {"name": "empty-path", "path": "", "description": None},
            {"name": "non-string-path", "path": 42, "description": None},
        ]
        get_enabled = Mock(return_value=enabled_records)
        monkeypatch.setattr(skill_manager, "get_enabled_skills", get_enabled)

        assert hasattr(skill_manager, "get_enabled_skill_paths"), (
            "SkillManager must expose validated enabled Skill paths"
        )
        assert skill_manager.get_enabled_skill_paths() == []

        get_enabled.assert_called_once_with()
        warning_text = "\n".join(item.args[0] for item in warning.call_args_list)
        for record in enabled_records:
            assert record["name"] in warning_text
            assert str(record["path"]) in warning_text


def test_agent_runtime_source_has_no_skill_mutation_api_references():
    source = Path("src/agent/agent_integration.py").read_text(encoding="utf-8")

    assert "_register_skills" not in source
    assert "register_agent_skill" not in source


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

    def test_change_notifications_cover_mcp_mutations_and_noops(self, mcp_manager):
        events = []
        observations = []

        def listener(event):
            events.append((event.source, event.action, event.name))
            observations.append(mcp_manager.get_server(event.name))

        mcp_manager.subscribe_changes(listener)
        mcp_manager.add_stdio_server("stdio", "python")
        with pytest.raises(ValueError):
            mcp_manager.add_stdio_server("stdio", "other")
        assert mcp_manager.update_stdio_server("missing", command="x") is False
        assert mcp_manager.update_http_server("stdio", url="https://wrong") is False
        assert mcp_manager.update_stdio_server("stdio", command="python3") is True
        assert mcp_manager.set_enabled("stdio", True) is True
        assert mcp_manager.set_enabled("missing", False) is False
        assert mcp_manager.set_enabled("stdio", False) is True
        assert mcp_manager.set_enabled("stdio", True) is True
        assert mcp_manager.delete_server("missing") is False
        assert mcp_manager.delete_server("stdio") is True
        mcp_manager.add_http_server("http", "https://first")
        assert mcp_manager.update_stdio_server("http", command="wrong") is False
        assert mcp_manager.update_http_server("http", url="https://second") is True
        assert mcp_manager.delete_server("http") is True

        assert events == [
            ("mcp", "added", "stdio"),
            ("mcp", "updated", "stdio"),
            ("mcp", "disabled", "stdio"),
            ("mcp", "enabled", "stdio"),
            ("mcp", "deleted", "stdio"),
            ("mcp", "added", "http"),
            ("mcp", "updated", "http"),
            ("mcp", "deleted", "http"),
        ]
        assert observations[0]["command"] == "python"
        assert observations[1]["command"] == "python3"
        assert observations[2]["enabled"] is False
        assert observations[3]["enabled"] is True
        assert observations[4] is None
        assert observations[5]["url"] == "https://first"
        assert observations[6]["url"] == "https://second"
        assert observations[7] is None

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

    def test_create_agentscope_mcp_client_for_stdio_preserves_config(
        self,
        mcp_manager,
        monkeypatch,
    ):
        mcp_manager.add_stdio_server(
            "test_stdio",
            "python",
            ["-m", "server"],
            {"DEBUG": "1"},
            61,
        )
        stdio_config_factory = Mock(wraps=StdioMCPConfig)
        client_factory = Mock(wraps=MCPClient)
        monkeypatch.setattr(
            mcp_server_manager,
            "StdioMCPConfig",
            stdio_config_factory,
            raising=False,
        )
        monkeypatch.setattr(
            mcp_server_manager,
            "MCPClient",
            client_factory,
            raising=False,
        )

        client = mcp_manager.create_agentscope_client("test_stdio")

        stdio_config_factory.assert_called_once_with(
            command="python",
            args=["-m", "server"],
            env={"DEBUG": "1"},
            cwd=None,
        )
        config = client.mcp_config
        client_factory.assert_called_once_with(
            name="test_stdio",
            is_stateful=True,
            mcp_config=config,
            enable_tools=None,
            disable_tools=None,
            execution_timeout=61.0,
        )
        assert isinstance(client, MCPClient)
        assert client.mcp_config.args == ["-m", "server"]
        assert client.mcp_config.env == {"DEBUG": "1"}
        assert client.is_stateful is True
        assert client.execution_timeout == 61.0

    def test_create_agentscope_mcp_client_for_http_omits_legacy_transport(
        self,
        mcp_manager,
        monkeypatch,
    ):
        server = {
            "name": "test_http",
            "server_type": "http",
            "url": "https://example.test/mcp",
            "headers": {"Authorization": "Bearer secret"},
            "transport": "sse",
            "timeout": 47,
            "enable_tools": ["search"],
            "disable_tools": ["delete"],
        }
        monkeypatch.setattr(mcp_manager, "get_server", Mock(return_value=server))
        http_config_factory = Mock(wraps=HttpMCPConfig)
        client_factory = Mock(wraps=MCPClient)
        monkeypatch.setattr(
            mcp_server_manager,
            "HttpMCPConfig",
            http_config_factory,
            raising=False,
        )
        monkeypatch.setattr(
            mcp_server_manager,
            "MCPClient",
            client_factory,
            raising=False,
        )

        client = mcp_manager.create_agentscope_client("test_http")

        http_config_factory.assert_called_once_with(
            url="https://example.test/mcp",
            headers={"Authorization": "Bearer secret"},
            timeout=47.0,
        )
        config = client.mcp_config
        client_factory.assert_called_once_with(
            name="test_http",
            is_stateful=False,
            mcp_config=config,
            enable_tools=["search"],
            disable_tools=["delete"],
            execution_timeout=47.0,
        )
        assert isinstance(client, MCPClient)
        assert client.mcp_config.headers == {"Authorization": "Bearer secret"}
        assert client.is_stateful is False
        assert client.execution_timeout == 47.0

    def test_create_agentscope_mcp_client_for_stored_http_server(
        self,
        mcp_manager,
    ):
        mcp_manager.add_http_server(
            "stored_http",
            "https://stored.example/mcp",
            "sse",
        )

        client = mcp_manager.create_agentscope_client("stored_http")

        assert isinstance(client, MCPClient)
        assert isinstance(client.mcp_config, HttpMCPConfig)
        assert client.mcp_config.url == "https://stored.example/mcp"
        assert client.mcp_config.timeout == 30.0
        assert "transport" not in client.mcp_config.model_dump()
        assert client.is_stateful is False
        assert client.execution_timeout == 30.0
        assert mcp_manager.get_server("stored_http")["transport"] == "sse"

    def test_update_stored_http_server_url_is_used_by_agentscope_client(
        self,
        mcp_manager,
    ):
        mcp_manager.add_http_server(
            "updated_http",
            "https://before.example/mcp",
            "sse",
        )
        assert mcp_manager.update_http_server(
            "updated_http",
            url="https://after.example/mcp",
            transport="streamable_http",
        )

        client = mcp_manager.create_agentscope_client("updated_http")

        assert client.mcp_config.url == "https://after.example/mcp"
        assert "transport" not in client.mcp_config.model_dump()
        assert client.is_stateful is False

    def test_create_agentscope_mcp_client_missing_server_constructs_nothing(
        self,
        mcp_manager,
        monkeypatch,
    ):
        config_factory = Mock()
        client_factory = Mock()
        monkeypatch.setattr(
            mcp_server_manager,
            "StdioMCPConfig",
            config_factory,
            raising=False,
        )
        monkeypatch.setattr(
            mcp_server_manager,
            "HttpMCPConfig",
            config_factory,
            raising=False,
        )
        monkeypatch.setattr(
            mcp_server_manager,
            "MCPClient",
            client_factory,
            raising=False,
        )

        assert mcp_manager.create_agentscope_client("missing") is None
        config_factory.assert_not_called()
        client_factory.assert_not_called()

    def test_create_agentscope_mcp_client_without_agentscope_returns_none(
        self,
        db,
        monkeypatch,
    ):
        module_path = mcp_server_manager.__file__
        spec = importlib.util.spec_from_file_location(
            "isolated_mcp_server_manager_without_agentscope",
            module_path,
        )
        assert spec is not None
        assert spec.loader is not None
        isolated_module = importlib.util.module_from_spec(spec)
        real_import = builtins.__import__

        def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "agentscope.mcp":
                raise ImportError("simulated missing AgentScope MCP")
            return real_import(name, globals, locals, fromlist, level)

        with monkeypatch.context() as import_patch:
            import_patch.setattr(builtins, "__import__", controlled_import)
            spec.loader.exec_module(isolated_module)

        manager = isolated_module.McpServerManager(db)
        manager.add_http_server("test_http", "https://example.test/mcp")

        assert isolated_module.MCPClient is None
        assert manager.create_agentscope_client("test_http") is None


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
