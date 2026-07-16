from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.agent_extensions import (
    AgentExtensionTools,
    _make_process_file_tools,
    _run_async,
)
from src.core.artifact_context import (
    ArtifactExecutionContext,
    bind_artifact_context,
    current_artifact_context,
)
from src.core.artifact_paths import ArtifactCategory, ArtifactPathPolicy


class _RecordingRegistry:
    def __init__(self):
        self.calls = []

    def confirm_file(
        self,
        session_id,
        category,
        path,
        *,
        producer="Agent",
        tool_call_id=None,
    ):
        self.calls.append(
            (session_id, category, Path(path).resolve(), producer, tool_call_id)
        )
        return SimpleNamespace(id=f"artifact-{len(self.calls)}")


def _context(tmp_path):
    policy = ArtifactPathPolicy(tmp_path)
    registry = _RecordingRegistry()
    return ArtifactExecutionContext("session-1", policy, registry), registry


def test_artifact_context_is_scoped_and_restored(tmp_path):
    context, _ = _context(tmp_path)

    assert current_artifact_context() is None


def test_artifact_context_propagates_into_owned_tool_thread(tmp_path):
    context, _ = _context(tmp_path)

    async def read_session():
        return current_artifact_context().session_id

    with bind_artifact_context(context):
        assert _run_async(read_session()) == "session-1"
    with bind_artifact_context(context):
        assert current_artifact_context() is context
    assert current_artifact_context() is None


@pytest.mark.asyncio
async def test_rag_cache_uses_data_tmp_and_is_not_registered(tmp_path):
    context, registry = _context(tmp_path)
    tools = AgentExtensionTools(project_root=tmp_path)
    tools._requester = SimpleNamespace(
        data_dir=str(tmp_path / "data"),
        rag_get_asset=lambda *_: None,
    )

    async def get_asset(*_):
        return b"image"

    tools._requester.rag_get_asset = get_asset
    with bind_artifact_context(context):
        cached = Path(await tools._cache_rag_asset("process", "nested/part.png"))

    assert cached.parent == tmp_path / "data" / "tmp"
    assert cached.read_bytes() == b"image"
    assert registry.calls == []


def test_process_file_confirmation_uses_documents_session_directory(tmp_path):
    context, registry = _context(tmp_path)
    output_root = context.path_policy.destination(
        context.session_id,
        ArtifactCategory.DOCUMENTS,
        "placeholder.json",
    ).parent
    write_file, _ = _make_process_file_tools(
        output_root,
        on_verified=lambda path: context.confirm_file(
            ArtifactCategory.DOCUMENTS,
            path,
        ),
    )
    try:
        response = write_file("process.json", "{}")
    finally:
        write_file.close()

    expected = output_root / "process.json"
    assert response.state.value == "success"
    assert expected.is_file()
    assert registry.calls == [
        ("session-1", ArtifactCategory.DOCUMENTS, expected.resolve(), "Agent", None),
    ]


def test_blender_destinations_are_session_scoped_and_verified(tmp_path):
    context, registry = _context(tmp_path)
    tools = AgentExtensionTools(project_root=tmp_path)

    with bind_artifact_context(context):
        destinations = tools._blender_output_directories()
        blend = destinations[ArtifactCategory.MODELS] / "fixture.blend"
        export = destinations[ArtifactCategory.EXPORTS] / "fixture.stl"
        nested = destinations[ArtifactCategory.IMAGES] / "renders" / "preview.png"
        blend.parent.mkdir(parents=True, exist_ok=True)
        export.parent.mkdir(parents=True, exist_ok=True)
        nested.parent.mkdir(parents=True, exist_ok=True)
        blend.write_bytes(b"blend")
        export.write_bytes(b"stl")
        nested.write_bytes(b"png")
        tools._confirm_blender_outputs()

    assert blend.parent == tmp_path / "data" / "models" / "session-1"
    assert export.parent == tmp_path / "data" / "exports" / "session-1"
    assert registry.calls == [
        ("session-1", ArtifactCategory.MODELS, blend.resolve(), "BlenderAgent", None),
        ("session-1", ArtifactCategory.EXPORTS, export.resolve(), "BlenderAgent", None),
        ("session-1", ArtifactCategory.IMAGES, nested.resolve(), "BlenderAgent", None),
    ]


def test_standalone_outputs_stay_below_project_data(tmp_path, monkeypatch):
    monkeypatch.setenv("PROCESS_OUTPUT_ROOT", str(tmp_path / "outside"))
    tools = AgentExtensionTools(project_root=tmp_path)

    process_root = tools._process_output_directory()
    image = tools._destination(ArtifactCategory.IMAGES, "generated.png")

    assert process_root == tmp_path / "data" / "documents" / "standalone"
    assert image == tmp_path / "data" / "images" / "standalone" / "generated.png"
    assert not (tmp_path / "outside").exists()


@pytest.mark.asyncio
async def test_blender_tool_guard_rejects_output_path_outside_session(tmp_path):
    from plugins.agent_extensions import _ArtifactPathGuardMiddleware

    allowed = tmp_path / "data" / "models" / "session-1"
    allowed.mkdir(parents=True)
    guard = _ArtifactPathGuardMiddleware([allowed])

    async def next_handler(**kwargs):
        yield SimpleNamespace(kwargs=kwargs)

    with pytest.raises(ValueError, match="Blender output path"):
        async for _ in guard.on_tool_call(
            tool=SimpleNamespace(name="save_model"),
            input_kwargs={"filepath": str(tmp_path / "outside" / "part.blend")},
            next_handler=next_handler,
        ):
            pass


@pytest.mark.asyncio
async def test_blender_path_guard_is_installed_on_every_mcp_tool(tmp_path):
    from plugins.agent_extensions import (
        _ArtifactPathGuardMiddleware,
        _blender_tools_with_path_guard,
    )

    class FakeTool:
        def __init__(self):
            self._middlewares = []

    class FakeClient:
        def __init__(self):
            self.tools = [FakeTool(), FakeTool()]

        async def list_tools(self):
            return self.tools

    client = FakeClient()
    tools = await _blender_tools_with_path_guard(
        client,
        [tmp_path / "data" / "models"],
    )

    assert len(tools) == 2
    assert all(
        isinstance(tool._middlewares[0], _ArtifactPathGuardMiddleware)
        for tool in tools
    )


def test_blender_path_guard_allows_non_file_modeling_calls(tmp_path):
    from plugins.agent_extensions import _ArtifactPathGuardMiddleware

    guard = _ArtifactPathGuardMiddleware([tmp_path / "data" / "models"])

    guard._validate(
        "mcp__blender_mcp__execute_blender_code",
        {"code": "bpy.ops.mesh.primitive_cube_add()"},
    )


def test_blender_path_guard_validates_actual_bpy_output_argument(tmp_path):
    from plugins.agent_extensions import _ArtifactPathGuardMiddleware

    allowed = tmp_path / "data" / "models"
    allowed.mkdir(parents=True)
    guard = _ArtifactPathGuardMiddleware([allowed])
    legitimate = allowed / "part.blend"

    guard._validate(
        "mcp__blender_mcp__execute_blender_code",
        {"code": f"bpy.ops.wm.save_as_mainfile(filepath={str(legitimate)!r})"},
    )

    with pytest.raises(ValueError, match="absolute|active session"):
        guard._validate(
            "mcp__blender_mcp__execute_blender_code",
            {
                "code": (
                    "bpy.ops.wm.save_as_mainfile(filepath='//../../outside.blend')\n"
                    f"dummy = {str(legitimate)!r}"
                )
            },
        )


@pytest.mark.parametrize(
    "code",
    [
        "import os; open(os.path.join(os.environ['TEMP'], 'x.bin'), 'wb')",
        "import shutil; shutil.copy('source', 'target')",
        "import subprocess; subprocess.run(['cmd'])",
        "from pathlib import Path; Path('x').write_bytes(b'x')",
    ],
)
def test_blender_path_guard_rejects_dynamic_python_file_writes(tmp_path, code):
    from plugins.agent_extensions import _ArtifactPathGuardMiddleware

    guard = _ArtifactPathGuardMiddleware([tmp_path / "data" / "models"])

    with pytest.raises(ValueError, match="filesystem|process|file execution"):
        guard._validate(
            "mcp__blender_mcp__execute_blender_code",
            {"code": code},
        )
