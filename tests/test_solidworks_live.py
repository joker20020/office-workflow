"""Opt-in smoke test against an installed SolidWorks instance."""

import os
from pathlib import Path

import pytest

from plugins.solidworks_agent.mcp_server import SolidWorksService
from plugins.solidworks_agent.paths import path_bridge_from_environment
from src.storage.database import Database
from src.storage.repositories import ArtifactRepository, ChatHistoryRepository

pytestmark = pytest.mark.skipif(
    os.environ.get("SOLIDWORKS_LIVE_TEST") != "1",
    reason="set SOLIDWORKS_LIVE_TEST=1 to run against SolidWorks",
)


def test_live_simple_part_saves_exports_previews_and_closes_only_test_document(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "solidworks-live.db"
    database = Database(database_path)
    database.create_tables()
    chats = ChatHistoryRepository(database)
    artifacts = ArtifactRepository(database)
    session_id = chats.create_session("Disposable SolidWorks live test")
    monkeypatch.setenv("SOLIDWORKS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SOLIDWORKS_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("SOLIDWORKS_SESSION_ID", session_id)
    monkeypatch.setenv("SOLIDWORKS_TOOL_CALL_ID", "solidworks-live-test")
    bridge = path_bridge_from_environment()
    service = SolidWorksService(path_service=bridge)
    document = None
    files = []
    try:
        created = service.new_part(bridge.context.session_id, "codex-live-disposable", "mm")
        assert created.success, (
            f"SolidWorks could not create a part: {created.message}. Complete any first-use "
            "license, sign-in, template, or Windows automation prompt, then retry."
        )
        document = created.value
        sketch_result = service.create_sketch(document.id, "Front Plane")
        assert sketch_result.success, sketch_result.message
        sketch = sketch_result.value
        geometry = service.add_sketch_geometry(
            sketch.id,
            [{"type": "center_rectangle", "center": [0, 0], "corner": [20, 10]}],
        )
        assert geometry.success
        assert service.close_sketch(sketch.id).success
        assert service.extrude(document.id, sketch.id, 10, "forward").success
        results = [
            service.save_model(document.id),
            service.export_step(document.id),
            service.export_stl(document.id, {"quality": "medium"}),
            service.capture_preview(document.id, "isometric"),
        ]
        assert all(result.success for result in results), [result.message for result in results]
        files = [Path(path) for result in results for path in result.generated_files]
        assert {path.suffix.casefold() for path in files} == {".sldprt", ".step", ".stl", ".png"}
        assert all(
            path.is_file() and path.is_relative_to(bridge.context.path_policy.data_root)
            for path in files
        )
        records = artifacts.list_session(session_id)
        assert {Path(record.path).suffix.casefold() for record in records} == {
            ".sldprt",
            ".step",
            ".stl",
            ".png",
        }
        assert all(
            record.producer == "SolidWorksAgent"
            and record.tool_call_id == "solidworks-live-test"
            for record in records
        )
    finally:
        if document is not None:
            service.adapter.close_document(service.documents[document.id][1])
        service.adapter.disconnect(close_started_instance=False)
        chats.delete_session(session_id)
        assert all(path.is_file() for path in files)
        database.close()
