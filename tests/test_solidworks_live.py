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


def test_live_features_survive_inspection_and_export(
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
        print("[solidworks-live] create part", flush=True)
        created = service.new_part(bridge.context.session_id, "codex-live-disposable", "mm")
        assert created.success, (
            f"SolidWorks could not create a part: {created.message}. Complete any first-use "
            "license, sign-in, template, or Windows automation prompt, then retry."
        )
        document = created.value
        print("[solidworks-live] create sketch", flush=True)
        sketch_result = service.create_sketch(document.id, "Front Plane")
        assert sketch_result.success, sketch_result.message
        sketch = sketch_result.value
        print("[solidworks-live] add geometry", flush=True)
        geometry = service.add_sketch_geometry(
            sketch.id,
            [{"type": "center_rectangle", "center": [0, 0], "corner": [20, 10]}],
        )
        assert geometry.success
        print("[solidworks-live] close sketch", flush=True)
        assert service.close_sketch(sketch.id).success
        print("[solidworks-live] extrude", flush=True)
        assert service.extrude(document.id, sketch.id, 10, "forward").success
        print("[solidworks-live] inspect extruded base", flush=True)
        inspected = service.inspect_model(document.id)
        assert inspected.success, inspected.message
        assert inspected.value["faces"], "Extruded base did not expose an inspectable face"
        print("[solidworks-live] create sketch on inspected face", flush=True)
        face_sketch = service.create_sketch_on_face(
            document.id, inspected.value["faces"][0].id
        )
        assert face_sketch.success, face_sketch.message
        print("[solidworks-live] close face sketch", flush=True)
        assert service.close_sketch(face_sketch.value.id).success
        print("[solidworks-live] inspect face sketch", flush=True)
        refreshed = service.inspect_model(document.id)
        assert refreshed.success, refreshed.message
        assert refreshed.value["edges"], "Extruded base did not expose an inspectable edge"
        print("[solidworks-live] fillet inspected edge", flush=True)
        fillet = service.fillet(document.id, [refreshed.value["edges"][0].id], 1)
        assert fillet.success, fillet.message
        print("[solidworks-live] inspect fillet", flush=True)
        assert service.inspect_model(document.id).success
        print("[solidworks-live] save native", flush=True)
        native = service.save_model(document.id)
        print("[solidworks-live] export STEP", flush=True)
        step = service.export_step(document.id)
        print("[solidworks-live] export STL", flush=True)
        stl = service.export_stl(document.id, {"quality": "medium"})
        print("[solidworks-live] capture PNG", flush=True)
        preview = service.capture_preview(document.id, "isometric")
        results = [
            native,
            step,
            stl,
            preview,
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
            print("[solidworks-live] close document", flush=True)
            service.adapter.close_document(service.documents[document.id][1])
        print("[solidworks-live] disconnect", flush=True)
        service.adapter.disconnect(close_started_instance=False)
        chats.delete_session(session_id)
        assert all(path.is_file() for path in files)
        database.close()
