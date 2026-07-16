import asyncio
import importlib
import sys
from dataclasses import is_dataclass
from types import SimpleNamespace

import pytest

EXPECTED_TOOLS = {
    "solidworks_status",
    "solidworks_new_part",
    "solidworks_create_sketch",
    "solidworks_add_sketch_geometry",
    "solidworks_add_dimensions",
    "solidworks_close_sketch",
    "solidworks_extrude",
    "solidworks_revolve",
    "solidworks_cut_extrude",
    "solidworks_hole",
    "solidworks_fillet",
    "solidworks_chamfer",
    "solidworks_mirror_feature",
    "solidworks_pattern_feature",
    "solidworks_inspect_model",
    "solidworks_save_model",
    "solidworks_export_step",
    "solidworks_export_stl",
    "solidworks_capture_preview",
}


def test_types_are_typed_records():
    types = importlib.import_module("plugins.solidworks_agent.types")

    for name in (
        "ConnectionResult",
        "DocumentRef",
        "SketchRef",
        "FeatureRef",
        "OperationResult",
    ):
        assert is_dataclass(getattr(types, name))


def test_runtime_dispatch_factory_imports_pywin32_lazily(monkeypatch):
    sys.modules.pop("plugins.solidworks_agent.com_adapter", None)
    monkeypatch.delitem(sys.modules, "win32com", raising=False)
    monkeypatch.delitem(sys.modules, "win32com.client", raising=False)

    module = importlib.import_module("plugins.solidworks_agent.com_adapter")

    assert "win32com.client" not in sys.modules
    assert callable(module.runtime_dispatch_factory)


def test_adapter_attaches_before_dispatch_and_preserves_user_instance():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    calls = []

    class App:
        IsInitialized = True
        Visible = False

        def ExitApp(self):  # noqa: N802 - mirrors the COM API
            calls.append("exit")

    app = App()

    class Dispatch:
        def get_active_object(self, prog_id):
            calls.append(("attach", prog_id))
            return app

        def dispatch(self, prog_id):
            calls.append(("dispatch", prog_id))
            return app

    adapter = adapter_module.SolidWorksComAdapter(dispatch=Dispatch(), sleep=lambda _: None)
    connected = adapter.connect(readiness_timeout=0.1)
    adapter.disconnect(close_started_instance=True)

    assert connected.success is True
    assert connected.owned is False
    assert calls == [("attach", "SldWorks.Application")]


def test_adapter_starts_visible_and_only_explicitly_closes_owned_instance():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    calls = []

    class App:
        IsInitialized = True
        Visible = False

        def ExitApp(self):  # noqa: N802 - mirrors the COM API
            calls.append("exit")

    app = App()

    class Dispatch:
        def get_active_object(self, prog_id):
            raise OSError("not running")

        def dispatch(self, prog_id):
            calls.append(("dispatch", prog_id))
            return app

    adapter = adapter_module.SolidWorksComAdapter(dispatch=Dispatch(), sleep=lambda _: None)
    connected = adapter.connect(readiness_timeout=0.1)
    adapter.disconnect()
    assert calls == [("dispatch", "SldWorks.Application")]
    assert app.Visible is True
    assert connected.owned is True

    adapter.connect(readiness_timeout=0.1)
    adapter.disconnect(close_started_instance=True)
    assert calls[-1] == "exit"


class FakeAdapter:
    def __init__(self):
        self.calls = []
        self.connected = False

    def connect(self, readiness_timeout=10.0):
        types = importlib.import_module("plugins.solidworks_agent.types")
        self.connected = True
        self.calls.append(("connect", readiness_timeout))
        return types.ConnectionResult(True, False, "attached")

    def new_part(self):
        self.calls.append(("new_part",))
        return object()

    def create_sketch(self, document, plane):
        self.calls.append(("create_sketch", document, plane))
        return object()

    def add_sketch_geometry(self, sketch, geometry):
        self.calls.append(("geometry", sketch, geometry))
        return len(geometry)

    def add_dimensions(self, sketch, dimensions):
        self.calls.append(("dimensions", sketch, dimensions))
        return len(dimensions)

    def close_sketch(self, sketch):
        self.calls.append(("close_sketch", sketch))

    def create_feature(self, document, sketch, kind, parameters):
        self.calls.append(("feature", document, sketch, kind, parameters))
        if kind == "mirror":
            raise NotImplementedError("mirror feature is not safely mapped")
        return object()

    def inspect_model(self, document):
        self.calls.append(("inspect", document))
        return {"feature_count": 1}


def _service(adapter=None):
    module = importlib.import_module("plugins.solidworks_agent.mcp_server")
    return module.SolidWorksService(adapter=adapter or FakeAdapter())


def test_mcp_exposes_exact_constrained_tool_set():
    module = importlib.import_module("plugins.solidworks_agent.mcp_server")
    names = {tool.name for tool in asyncio.run(module.mcp.list_tools())}

    assert names == EXPECTED_TOOLS


def test_ordered_progression_and_reference_validation_happen_before_com_calls():
    adapter = FakeAdapter()
    service = _service(adapter)
    document = service.new_part()
    sketch = service.create_sketch(document.value.id, "Front Plane")

    rejected = service.extrude(document.value.id, sketch.value.id, {"depth": 0.01})
    missing = service.add_sketch_geometry(
        document.value.id,
        "missing-sketch",
        [{"type": "line", "start": [0, 0], "end": [1, 0]}],
    )

    assert rejected.success is False
    assert "closed" in rejected.message
    assert missing.success is False
    assert [call[0] for call in adapter.calls].count("feature") == 0

    assert service.close_sketch(document.value.id, sketch.value.id).success is True
    feature = service.extrude(document.value.id, sketch.value.id, {"depth": 0.01})
    assert feature.success is True
    assert feature.value.kind == "extrude"


@pytest.mark.parametrize(
    "geometry",
    [
        [{"type": "spline", "points": [[0, 0], [1, 1]]}],
        [{"type": "line", "start": [0, 0], "end": [1, 0], "macro": "x"}],
        [{"type": "circle", "center": [0, 0], "radius": -1}],
    ],
)
def test_geometry_payload_is_bounded_and_explicit(geometry):
    adapter = FakeAdapter()
    service = _service(adapter)
    document = service.new_part().value
    sketch = service.create_sketch(document.id, "Top Plane").value

    result = service.add_sketch_geometry(document.id, sketch.id, geometry)

    assert result.success is False
    assert not any(call[0] == "geometry" for call in adapter.calls)


def test_dimensions_are_explicit_and_unsupported_features_fail_safely():
    adapter = FakeAdapter()
    service = _service(adapter)
    document = service.new_part().value
    sketch = service.create_sketch(document.id, "Right Plane").value

    bad = service.add_dimensions(
        document.id,
        sketch.id,
        [{"type": "angle", "value": 1.0}],
    )
    service.close_sketch(document.id, sketch.id)
    feature = service.extrude(document.id, sketch.id, {"depth": 0.01}).value
    unsupported = service.mirror_feature(
        document.id,
        feature.id,
        {"plane": "Front Plane"},
    )

    assert bad.success is False
    assert unsupported.success is False
    assert "unsupported" in unsupported.message.casefold()


def test_files_use_internal_path_service_and_results_are_display_safe():
    module = importlib.import_module("plugins.solidworks_agent.mcp_server")
    service = module.SolidWorksService(adapter=FakeAdapter(), path_service=None)
    document = service.new_part().value

    result = service.save_model(document.id)
    rendered = module.render_result(result)

    assert result.success is False
    assert "path service" in result.message
    for heading in (
        "## Status",
        "## Execution Summary",
        "## Generated Files",
        "## Verification",
        "## Warnings",
    ):
        assert heading in rendered
    assert "Traceback" not in rendered


def test_rendered_results_expose_generated_typed_references():
    module = importlib.import_module("plugins.solidworks_agent.mcp_server")
    document = module.SolidWorksService(adapter=FakeAdapter()).new_part()

    rendered = module.render_result(document)

    assert document.value.id in rendered
    assert '"id"' in rendered


def test_new_part_uses_default_template_and_fails_clearly_when_missing():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")

    class App:
        def GetUserPreferenceStringValue(self, preference):  # noqa: N802 - COM API
            assert preference == 1
            return ""

    adapter = adapter_module.SolidWorksComAdapter(
        dispatch=SimpleNamespace(),
        sleep=lambda _: None,
    )
    adapter._app = App()

    with pytest.raises(RuntimeError, match="default part template"):
        adapter.new_part()
