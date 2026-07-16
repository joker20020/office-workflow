import asyncio
import importlib
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentscope.event import (
    ReplyEndEvent,
    ReplyStartEvent,
    TextBlockDeltaEvent,
)
from agentscope.message import ToolResultState

VALID_RESULT = """# Execution Result
## Status
Success
## Execution Summary
Created and inspected the requested part.
## Generated Files
- part.SLDPRT
- part.step
- part.stl
- preview.png
## Concrete Result
One feature was created and inspected.
## Execution Log
Feature-level tools completed.
## Verification
The part, STEP, STL, and preview were verified.
## Warnings and Unfinished Items
None
"""


def _module():
    return importlib.import_module("plugins.solidworks_agent")


def test_manifest_and_settings_define_an_independent_plugin(monkeypatch):
    module = _module()
    settings = importlib.import_module("plugins.solidworks_agent.settings")
    manifest_path = Path(module.__file__).with_name("plugin.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "solidworks_agent"
    assert manifest["entry"] == "SolidWorksAgentPlugin"
    assert manifest["permissions"] == ["agent.tool"]
    assert settings.DEFAULT_EXECUTION_TIMEOUT_SECONDS == 600.0
    monkeypatch.setenv("SOLIDWORKS_MCP_TIMEOUT_SECONDS", "37.5")
    assert settings.execution_timeout_seconds() == 37.5
    monkeypatch.setenv("SOLIDWORKS_MCP_TIMEOUT_SECONDS", "invalid")
    assert settings.execution_timeout_seconds() == 600.0


def _install_recording_runtime(monkeypatch, module, *, connect_error=None):
    events = []
    captured = {}

    class FakeConfig:
        def __init__(self, **kwargs):
            captured["config"] = kwargs

    class FakeClient:
        instances = []

        def __init__(self, **kwargs):
            events.append("client")
            captured["client_kwargs"] = kwargs
            self.connected = False
            self.close_count = 0
            self.__class__.instances.append(self)

        async def connect(self):
            events.append("connect")
            if connect_error is not None:
                raise connect_error
            self.connected = True

        async def close(self):
            events.append("close")
            self.close_count += 1
            self.connected = False

    class FakeToolkit:
        def __init__(self, *, mcps):
            events.append("toolkit")
            assert mcps[0].connected is True
            captured["toolkit_mcps"] = mcps

    class FakeAgent:
        name = "SolidWorksAgent"

        def __init__(self, **kwargs):
            events.append("agent")
            assert FakeClient.instances[-1].connected is True
            captured["agent"] = kwargs

        async def reply_stream(self, *, inputs):
            events.append("reply_stream")
            captured["message"] = inputs
            yield ReplyStartEvent(
                session_id="agent-session",
                reply_id="reply-1",
                name=self.name,
            )
            yield TextBlockDeltaEvent(
                reply_id="reply-1",
                block_id="text-1",
                delta=VALID_RESULT,
            )
            yield ReplyEndEvent(session_id="agent-session", reply_id="reply-1")

    monkeypatch.setattr(module, "StdioMCPConfig", FakeConfig)
    monkeypatch.setattr(module, "MCPClient", FakeClient)
    monkeypatch.setattr(module, "Toolkit", FakeToolkit)
    monkeypatch.setattr(module, "Agent", FakeAgent)
    monkeypatch.setattr(module, "_build_model", lambda: "model")
    return events, captured, FakeClient


@pytest.mark.asyncio
async def test_lifecycle_uses_local_stdio_session_stream_and_structured_prompt(monkeypatch):
    module = _module()
    events, captured, fake_client = _install_recording_runtime(monkeypatch, module)
    monkeypatch.setattr(
        module,
        "current_artifact_context",
        lambda: SimpleNamespace(session_id="active-session"),
    )
    public_events = []
    token = module._PROGRESS_SINK.set(public_events.append)
    try:
        result = await module.SolidWorksAgentTools()._solidworks_model_async("build it")
    finally:
        module._PROGRESS_SINK.reset(token)

    assert result == VALID_RESULT.strip()
    assert result.success is True
    assert events == ["client", "connect", "toolkit", "agent", "reply_stream", "close"]
    assert fake_client.instances[0].close_count == 1
    assert captured["client_kwargs"]["is_stateful"] is True
    assert captured["client_kwargs"]["execution_timeout"] == 600.0
    assert captured["config"]["command"] == sys.executable
    assert captured["config"]["args"] == ["-m", "plugins.solidworks_agent.mcp_server"]
    assert captured["config"]["env"]["SOLIDWORKS_SESSION_ID"] == "active-session"
    assert captured["config"]["cwd"] == str(Path(module.__file__).parents[2])
    assert captured["message"].get_text_content() == "build it"
    assert {event["kind"] for event in public_events} == {"text", "complete"}

    prompt = captured["agent"]["system_prompt"]
    progression = [
        "status/new part",
        "sketch and dimensions",
        "close sketch",
        "one feature",
        "inspect",
        "subsequent feature",
        "save",
        "STEP",
        "STL",
        "preview",
    ]
    assert all(item.casefold() in prompt.casefold() for item in progression)
    assert "arbitrary COM" in prompt
    assert "scripts" in prompt
    assert "macros" in prompt
    assert "shell commands" in prompt
    assert "arbitrary paths" in prompt
    for heading in module.REQUIRED_HEADINGS:
        assert heading in prompt


@pytest.mark.asyncio
async def test_explicit_session_overrides_artifact_context(monkeypatch):
    module = _module()
    _, captured, _ = _install_recording_runtime(monkeypatch, module)
    monkeypatch.setattr(
        module,
        "current_artifact_context",
        lambda: SimpleNamespace(session_id="active-session"),
    )

    await module.SolidWorksAgentTools()._solidworks_model_async(
        "build it",
        session_id="explicit-session",
    )

    assert captured["config"]["env"]["SOLIDWORKS_SESSION_ID"] == "explicit-session"


@pytest.mark.asyncio
async def test_connect_failure_still_closes_client_exactly_once(monkeypatch):
    module = _module()
    _, _, fake_client = _install_recording_runtime(
        monkeypatch,
        module,
        connect_error=RuntimeError("offline"),
    )

    result = await module.SolidWorksAgentTools()._solidworks_model_async("build it")

    assert result.success is False
    assert "offline" in result
    assert fake_client.instances[0].close_count == 1


@pytest.mark.asyncio
async def test_cancellation_closes_client_exactly_once_and_propagates(monkeypatch):
    module = _module()
    started = asyncio.Event()

    class FakeConfig:
        def __init__(self, **kwargs):
            pass

    class FakeClient:
        instance = None

        def __init__(self, **kwargs):
            self.connected = False
            self.close_count = 0
            FakeClient.instance = self

        async def connect(self):
            self.connected = True

        async def close(self):
            self.close_count += 1

    class FakeToolkit:
        def __init__(self, *, mcps):
            assert mcps[0].connected

    class BlockingAgent:
        name = "SolidWorksAgent"

        def __init__(self, **kwargs):
            pass

        async def reply_stream(self, *, inputs):
            started.set()
            yield ReplyStartEvent(
                session_id="agent-session",
                reply_id="reply-1",
                name=self.name,
            )
            await asyncio.Event().wait()

    monkeypatch.setattr(module, "StdioMCPConfig", FakeConfig)
    monkeypatch.setattr(module, "MCPClient", FakeClient)
    monkeypatch.setattr(module, "Toolkit", FakeToolkit)
    monkeypatch.setattr(module, "Agent", BlockingAgent)
    monkeypatch.setattr(module, "_build_model", lambda: "model")

    task = asyncio.create_task(
        module.SolidWorksAgentTools()._solidworks_model_async("build it"),
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert FakeClient.instance.close_count == 1


@pytest.mark.asyncio
async def test_public_stream_close_cancels_work_and_closes_client_once(monkeypatch):
    module = _module()
    release = threading.Event()
    cancelled = threading.Event()

    class FakeConfig:
        def __init__(self, **kwargs):
            pass

    class FakeClient:
        instance = None

        def __init__(self, **kwargs):
            self.connected = False
            self.close_count = 0
            FakeClient.instance = self

        async def connect(self):
            self.connected = True

        async def close(self):
            self.close_count += 1

    class FakeToolkit:
        def __init__(self, *, mcps):
            assert mcps[0].connected

    class BlockingAgent:
        name = "SolidWorksAgent"

        def __init__(self, **kwargs):
            pass

        async def reply_stream(self, *, inputs):
            yield TextBlockDeltaEvent(
                reply_id="reply-1",
                block_id="text-1",
                delta="working",
            )
            try:
                while not release.is_set():
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr(module, "StdioMCPConfig", FakeConfig)
    monkeypatch.setattr(module, "MCPClient", FakeClient)
    monkeypatch.setattr(module, "Toolkit", FakeToolkit)
    monkeypatch.setattr(module, "Agent", BlockingAgent)
    monkeypatch.setattr(module, "_build_model", lambda: "model")

    stream_tool = module.SolidWorksAgentTools().get_all_tools()[0]
    stream = stream_tool("build it")
    try:
        await asyncio.wait_for(anext(stream), timeout=2)
        await stream.aclose()
        assert cancelled.wait(timeout=1)
        assert FakeClient.instance.close_count == 1
    finally:
        release.set()
        for _ in range(100):
            if FakeClient.instance.close_count:
                break
            await asyncio.sleep(0.01)


def test_public_tool_returns_tool_response_and_rejects_malformed_markdown(monkeypatch):
    module = _module()
    tools = module.SolidWorksAgentTools()

    monkeypatch.setattr(
        module,
        "_run_async",
        lambda coro: (coro.close(), module._validate_result(VALID_RESULT))[1],
    )
    response = tools.tool_solidworks_model("build it", session_id="session")
    assert response.state is ToolResultState.SUCCESS
    assert response.content[0].text == VALID_RESULT.strip()

    malformed = VALID_RESULT.replace("## Verification\n", "")
    rejected = module._validate_result(malformed)
    assert rejected.success is False
    assert rejected.startswith("# Execution Result")
    assert "## Verification" in rejected
    assert "missing required heading" in rejected


def test_plugin_registers_only_the_solidworks_streaming_tool():
    module = _module()
    registered = {}

    class Registry:
        def register(self, group, tools):
            registered["group"] = group
            registered["tools"] = tools

    plugin = module.SolidWorksAgentPlugin()
    plugin.on_enable(SimpleNamespace(tool_registry=Registry()))

    assert registered["group"] == "solidworks_agent"
    assert [tool.__name__ for tool in registered["tools"]] == [
        "tool_solidworks_model",
    ]
