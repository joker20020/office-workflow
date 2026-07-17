"""Opt-in smoke test against an installed SolidWorks instance."""

import os
from pathlib import Path

import pytest

from plugins.solidworks_agent.mcp_server import SolidWorksService
from plugins.solidworks_agent.paths import path_bridge_from_environment

pytestmark = pytest.mark.skipif(
    os.environ.get("SOLIDWORKS_LIVE_TEST") != "1",
    reason="set SOLIDWORKS_LIVE_TEST=1 to run against SolidWorks",
)


def test_live_simple_part_saves_exports_previews_and_closes_only_test_document():
    bridge = path_bridge_from_environment()
    service = SolidWorksService(path_service=bridge)
    document = None
    try:
        created = service.new_part(bridge.context.session_id, "codex-live-disposable", "mm")
        assert created.success, (
            f"SolidWorks could not create a part: {created.message}. Complete any first-use "
            "license, sign-in, template, or Windows automation prompt, then retry."
        )
        document = created.value
        sketch = service.create_sketch(document.id, "Front Plane").value
        geometry = service.add_sketch_geometry(
            sketch.id,
            [{"type": "center_rectangle", "center": [0, 0], "corner": [0.02, 0.01]}],
        )
        assert geometry.success
        assert service.close_sketch(sketch.id).success
        assert service.extrude(document.id, sketch.id, 0.01, "forward").success
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
    finally:
        if document is not None:
            service.adapter.close_document(service.documents[document.id][1])
        service.adapter.disconnect(close_started_instance=False)
