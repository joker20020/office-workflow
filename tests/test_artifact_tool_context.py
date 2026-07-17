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




def test_standalone_outputs_stay_below_project_data(tmp_path, monkeypatch):
    monkeypatch.setenv("PROCESS_OUTPUT_ROOT", str(tmp_path / "outside"))
    tools = AgentExtensionTools(project_root=tmp_path)

    process_root = tools._process_output_directory()
    image = tools._destination(ArtifactCategory.IMAGES, "generated.png")

    assert process_root == tmp_path / "data" / "documents" / "standalone"
    assert image == tmp_path / "data" / "images" / "standalone" / "generated.png"
    assert not (tmp_path / "outside").exists()
