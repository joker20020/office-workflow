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

from src.core.artifact_context import ArtifactExecutionContext
from src.core.artifact_paths import ArtifactCategory, ArtifactPathPolicy
from src.core.artifact_registry import ArtifactRegistry
from src.storage.database import Database
from src.storage.repositories import ArtifactRepository, ChatHistoryRepository

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


def _valid_result(root: Path, session_id: str = "session") -> str:
    paths = {
        "native": root / "models" / session_id / "part.sldprt",
        "step": root / "exports" / session_id / "part.step",
        "stl": root / "exports" / session_id / "part.stl",
        "preview": root / "images" / session_id / "preview.png",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"artifact")
    files = "\n".join(f"- {path.resolve()}" for path in paths.values())
    return VALID_RESULT.replace(
        "- part.SLDPRT\n- part.step\n- part.stl\n- preview.png",
        files,
    )


def _module():
    return importlib.import_module("plugins.solidworks_agent")


def _active_context(module):
    root = Path(module.__file__).parents[2]
    return SimpleNamespace(
        session_id="active-session",
        path_policy=ArtifactPathPolicy(root),
        registry=SimpleNamespace(database_path=root / "data" / "app.db"),
    )


def test_manifest_and_settings_define_an_independent_plugin(monkeypatch):
    module = _module()
    settings = importlib.import_module("plugins.solidworks_agent.settings")
    manifest_path = Path(module.__file__).with_name("plugin.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "solidworks_agent"
    assert manifest["entry"] == "SolidWorksAgentPlugin"
    assert set(manifest["permissions"]) == {"agent.tool", "network"}
    assert settings.DEFAULT_EXECUTION_TIMEOUT_SECONDS == 600.0
    monkeypatch.setenv("SOLIDWORKS_MCP_TIMEOUT_SECONDS", "37.5")
    assert settings.execution_timeout_seconds() == 37.5
    monkeypatch.setenv("SOLIDWORKS_MCP_TIMEOUT_SECONDS", "invalid")
    assert settings.execution_timeout_seconds() == 600.0


def _install_recording_runtime(
    monkeypatch,
    module,
    *,
    connect_error=None,
    result=VALID_RESULT,
    register_artifacts=False,
):
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
        def __init__(self, *, mcps, skills_or_loaders=None):
            events.append("toolkit")
            assert mcps[0].connected is True
            captured["toolkit_mcps"] = mcps
            captured["toolkit_skills_or_loaders"] = skills_or_loaders

    class FakeAgent:
        name = "SolidWorksAgent"

        def __init__(self, **kwargs):
            events.append("agent")
            assert FakeClient.instances[-1].connected is True
            captured["agent"] = kwargs

        async def reply_stream(self, *, inputs):
            events.append("reply_stream")
            captured["message"] = inputs
            if register_artifacts:
                context = module.current_artifact_context()
                categories = {
                    ".sldprt": ArtifactCategory.MODELS,
                    ".sldasm": ArtifactCategory.MODELS,
                    ".step": ArtifactCategory.EXPORTS,
                    ".stl": ArtifactCategory.EXPORTS,
                    ".png": ArtifactCategory.IMAGES,
                }
                for line in result.splitlines():
                    if not line.startswith("- "):
                        continue
                    path = Path(line[2:])
                    category = categories.get(path.suffix.casefold())
                    if category is not None:
                        context.registry.confirm_file(
                            context.session_id,
                            category,
                            path,
                            producer="SolidWorksAgent",
                            tool_call_id=captured["config"]["env"]["SOLIDWORKS_TOOL_CALL_ID"],
                        )
            yield ReplyStartEvent(
                session_id="agent-session",
                reply_id="reply-1",
                name=self.name,
            )
            yield TextBlockDeltaEvent(
                reply_id="reply-1",
                block_id="text-1",
                delta=result,
            )
            yield ReplyEndEvent(session_id="agent-session", reply_id="reply-1")

    monkeypatch.setattr(module, "StdioMCPConfig", FakeConfig)
    monkeypatch.setattr(module, "MCPClient", FakeClient)
    monkeypatch.setattr(module, "Toolkit", FakeToolkit)
    monkeypatch.setattr(module, "Agent", FakeAgent)
    monkeypatch.setattr(module, "_build_model", lambda: "model")
    return events, captured, FakeClient


@pytest.mark.asyncio
async def test_lifecycle_uses_local_stdio_session_stream_and_structured_prompt(
    monkeypatch, tmp_path
):
    module = _module()
    policy = ArtifactPathPolicy(tmp_path / "custom-project")
    database = Database(tmp_path / "custom-state" / "history.sqlite3")
    database.create_tables()
    session_id = ChatHistoryRepository(database).create_session("solidworks test")
    valid_result = _valid_result(policy.data_root, session_id)
    context = ArtifactExecutionContext(
        session_id,
        policy,
        ArtifactRegistry(policy, ArtifactRepository(database)),
    )
    events, captured, fake_client = _install_recording_runtime(
        monkeypatch, module, result=valid_result, register_artifacts=True
    )
    monkeypatch.setattr(module, "current_artifact_context", lambda: context)
    public_events = []
    token = module._PROGRESS_SINK.set(public_events.append)
    try:
        result = await module.SolidWorksAgentTools()._solidworks_model_async("build it")
    finally:
        module._PROGRESS_SINK.reset(token)

    assert result == valid_result.strip()
    assert result.success is True
    assert events == ["client", "connect", "toolkit", "agent", "reply_stream", "close"]
    assert fake_client.instances[0].close_count == 1
    assert captured["client_kwargs"]["is_stateful"] is True
    assert captured["client_kwargs"]["execution_timeout"] == 600.0
    assert captured["config"]["command"] == sys.executable
    assert captured["config"]["args"] == ["-m", "plugins.solidworks_agent.mcp_server"]
    assert captured["config"]["env"]["SOLIDWORKS_SESSION_ID"] == session_id
    assert captured["config"]["env"]["SOLIDWORKS_PROJECT_ROOT"] == str(
        policy.project_root
    )
    assert captured["config"]["env"]["SOLIDWORKS_DATABASE_PATH"] == str(
        database.db_path.resolve()
    )
    correlation_id = captured["config"]["env"]["SOLIDWORKS_TOOL_CALL_ID"]
    assert correlation_id
    assert captured["config"]["cwd"] == str(Path(module.__file__).parents[2])
    message = captured["message"].get_text_content()
    assert "build it" in message
    assert session_id in message
    assert correlation_id in message
    assert "solidworks_new_part" in message
    skill_paths = captured["toolkit_skills_or_loaders"]
    assert skill_paths and len(skill_paths) == 1
    skill_path = Path(skill_paths[0])
    assert skill_path.name == "solidworks-feature-modeling"
    assert (skill_path / "SKILL.md").is_file()
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
async def test_success_markdown_is_rejected_without_four_matching_persisted_records(
    monkeypatch, tmp_path
):
    module = _module()
    policy = ArtifactPathPolicy(tmp_path)
    database = Database(tmp_path / "history.sqlite3")
    database.create_tables()
    session_id = ChatHistoryRepository(database).create_session("solidworks test")
    context = ArtifactExecutionContext(
        session_id,
        policy,
        ArtifactRegistry(policy, ArtifactRepository(database)),
    )
    _install_recording_runtime(
        monkeypatch,
        module,
        result=_valid_result(policy.data_root),
        register_artifacts=False,
    )
    monkeypatch.setattr(module, "current_artifact_context", lambda: context)

    result = await module.SolidWorksAgentTools()._solidworks_model_async("build it")

    assert result.success is False
    assert "persisted artifact" in result


@pytest.mark.asyncio
async def test_explicit_session_cannot_override_artifact_context(monkeypatch):
    module = _module()
    events, _, _ = _install_recording_runtime(monkeypatch, module)
    monkeypatch.setattr(
        module,
        "current_artifact_context",
        lambda: SimpleNamespace(
            session_id="active-session",
            path_policy=ArtifactPathPolicy(Path(module.__file__).parents[2]),
        ),
    )

    result = await module.SolidWorksAgentTools()._solidworks_model_async(
        "build it",
        session_id="explicit-session",
    )

    assert result.success is False
    assert "active-session" in result
    assert "explicit-session" in result
    assert events == []


@pytest.mark.asyncio
async def test_matching_explicit_session_is_allowed_with_artifact_context(
    monkeypatch, tmp_path
):
    module = _module()
    database = Database(tmp_path / "history.sqlite3")
    database.create_tables()
    session_id = ChatHistoryRepository(database).create_session("solidworks test")
    policy = ArtifactPathPolicy(tmp_path)
    _, captured, _ = _install_recording_runtime(
        monkeypatch,
        module,
        result=_valid_result(tmp_path / "data", session_id),
        register_artifacts=True,
    )
    monkeypatch.setattr(
        module,
        "current_artifact_context",
        lambda: SimpleNamespace(
            session_id=session_id,
            path_policy=policy,
            registry=ArtifactRegistry(policy, ArtifactRepository(database)),
        ),
    )

    result = await module.SolidWorksAgentTools()._solidworks_model_async(
        "build it", session_id=session_id
    )

    assert result.success is True
    assert captured["config"]["env"]["SOLIDWORKS_SESSION_ID"] == session_id


@pytest.mark.asyncio
async def test_missing_artifact_context_rejects_before_starting_mcp(monkeypatch):
    module = _module()
    events, _, _ = _install_recording_runtime(
        monkeypatch,
        module,
        result=VALID_RESULT,
    )
    monkeypatch.setattr(module, "current_artifact_context", lambda: None)

    result = await module.SolidWorksAgentTools()._solidworks_model_async(
        "build it", session_id="explicit-session"
    )

    assert result.success is False
    assert "active artifact context" in result
    assert events == []


def test_legacy_main_entrypoint_contains_no_blender_runtime():
    legacy_entrypoint = Path(__file__).parents[1] / "main.py"
    if not legacy_entrypoint.exists():
        pytest.skip("legacy root main.py entrypoint is no longer part of this application")

    source = legacy_entrypoint.read_text(encoding="utf-8")

    assert "blender" not in source.casefold()


@pytest.mark.asyncio
async def test_connect_failure_still_closes_client_exactly_once(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "current_artifact_context", lambda: _active_context(module))
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
    monkeypatch.setattr(module, "current_artifact_context", lambda: _active_context(module))
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
        def __init__(self, *, mcps, skills_or_loaders=None):
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
    monkeypatch.setattr(module, "current_artifact_context", lambda: _active_context(module))
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
        def __init__(self, *, mcps, skills_or_loaders=None):
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


def test_public_tool_returns_tool_response_and_rejects_malformed_markdown(
    monkeypatch, tmp_path
):
    module = _module()
    tools = module.SolidWorksAgentTools()
    valid_result = _valid_result(tmp_path / "data")

    monkeypatch.setattr(
        module,
        "_run_async",
        lambda coro: (
            coro.close(),
            module._verify_persisted_artifacts(
                module._validate_result(valid_result, tmp_path),
                [
                    SimpleNamespace(path=line[2:])
                    for line in valid_result.splitlines()
                    if line.startswith("- ")
                ],
                project_root=tmp_path,
            ),
        )[1],
    )
    monkeypatch.setattr(
        module,
        "current_artifact_context",
        lambda: SimpleNamespace(path_policy=ArtifactPathPolicy(tmp_path)),
    )
    response = tools.tool_solidworks_model("build it", session_id="session")
    assert response.state is ToolResultState.SUCCESS
    assert response.content[0].text == valid_result.strip()

    malformed = valid_result.replace("## Verification\n", "")
    rejected = module._validate_result(malformed, tmp_path)
    assert rejected.success is False
    assert rejected.startswith("# Execution Result")
    assert "## Verification" in rejected
    assert "missing required heading" in rejected


@pytest.mark.parametrize("missing_suffix", [".sldprt", ".step", ".stl", ".png"])
def test_success_result_requires_all_real_absolute_data_deliverables(tmp_path, missing_suffix):
    module = _module()
    valid = _valid_result(tmp_path / "data")
    lines = [line for line in valid.splitlines() if not line.casefold().endswith(missing_suffix)]
    rejected = module._validate_result("\n".join(lines), tmp_path)
    assert rejected.success is False
    assert "deliverable" in rejected


def test_success_result_rejects_nonexistent_relative_and_outside_paths(tmp_path):
    module = _module()
    valid = _valid_result(tmp_path / "data")
    native = next(line[2:] for line in valid.splitlines() if line.casefold().endswith(".sldprt"))
    bad_paths = [
        "missing.sldprt",
        str((tmp_path / "data" / "models" / "session" / "missing.sldprt").resolve()),
        str((tmp_path / "outside.sldprt").resolve()),
    ]
    for bad in bad_paths:
        rejected = module._validate_result(valid.replace(native, bad), tmp_path)
        assert rejected.success is False
        assert "deliverable" in rejected


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


def test_manifest_and_plugin_declare_network_and_agent_tool_permissions():
    module = _module()
    manifest = json.loads(Path(module.__file__).with_name("plugin.json").read_text("utf-8"))
    assert set(manifest["permissions"]) == {"agent.tool", "network"}
    assert module.SolidWorksAgentPlugin.permissions.has_all(
        {module.Permission.AGENT_TOOL, module.Permission.NETWORK}
    )


class _RecordingRegistry:
    def __init__(self):
        self.calls = []

    def confirm_file(self, session_id, category, path, **kwargs):
        self.calls.append((session_id, category, Path(path), kwargs))
        return SimpleNamespace(path=str(path))


def test_solidworks_path_bridge_classifies_sanitizes_and_confirms_outputs(tmp_path):
    paths = importlib.import_module("plugins.solidworks_agent.paths")
    policy = ArtifactPathPolicy(tmp_path)
    registry = _RecordingRegistry()
    context = ArtifactExecutionContext("session-7", policy, registry)
    bridge = paths.SolidWorksArtifactPathBridge(context, tool_call_id="call-9")
    document = SimpleNamespace(session_id="session-7", name="Widget / unsafe", unit="mm")
    expected = {
        "native": (ArtifactCategory.MODELS, ".sldprt"),
        "step": (ArtifactCategory.EXPORTS, ".step"),
        "stl": (ArtifactCategory.EXPORTS, ".stl"),
        "preview": (ArtifactCategory.IMAGES, ".png"),
    }
    for kind, (category, suffix) in expected.items():
        output = Path(bridge.path_for(document, kind))
        assert output.parent == policy.data_root / category / "session-7"
        assert output.suffix.casefold() == suffix
        assert output.name.startswith("Widget_unsafe")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"artifact")
        assert bridge.validate_output_path(str(output))
        assert bridge.confirm_file(str(output))
    assert [call[1] for call in registry.calls] == [item[0] for item in expected.values()]
    assert all(
        call[3] == {"producer": "SolidWorksAgent", "tool_call_id": "call-9"}
        for call in registry.calls
    )


def test_solidworks_path_bridge_rejects_cross_session_and_unissued_paths(tmp_path):
    paths = importlib.import_module("plugins.solidworks_agent.paths")
    context = ArtifactExecutionContext(
        "session-7", ArtifactPathPolicy(tmp_path), _RecordingRegistry()
    )
    bridge = paths.SolidWorksArtifactPathBridge(context)
    with pytest.raises(ValueError, match="session"):
        bridge.path_for(SimpleNamespace(session_id="other", name="part"), "native")
    rogue = tmp_path / "data" / "exports" / "session-7" / "rogue.step"
    assert bridge.validate_output_path(str(rogue)) is False
    assert bridge.validate_output_path(str(tmp_path / "outside.step")) is False
