import asyncio
import importlib
import inspect
import sys
from dataclasses import is_dataclass
from pathlib import Path
from types import SimpleNamespace

EXPECTED_SIGNATURES = {
    "solidworks_status": [],
    "solidworks_new_part": ["session_id", "name", "unit"],
    "solidworks_create_sketch": ["document_id", "plane"],
    "solidworks_add_sketch_geometry": ["sketch_id", "geometry"],
    "solidworks_add_dimensions": ["sketch_id", "dimensions"],
    "solidworks_close_sketch": ["sketch_id"],
    "solidworks_extrude": ["document_id", "sketch_id", "depth", "direction"],
    "solidworks_revolve": ["document_id", "sketch_id", "axis", "angle"],
    "solidworks_cut_extrude": ["document_id", "sketch_id", "depth"],
    "solidworks_hole": ["document_id", "face_ref", "specification", "position"],
    "solidworks_fillet": ["document_id", "edge_refs", "radius"],
    "solidworks_chamfer": ["document_id", "edge_refs", "specification"],
    "solidworks_mirror_feature": ["document_id", "feature_refs", "plane"],
    "solidworks_pattern_feature": ["document_id", "feature_ref", "pattern"],
    "solidworks_inspect_model": ["document_id"],
    "solidworks_save_model": ["document_id"],
    "solidworks_export_step": ["document_id"],
    "solidworks_export_stl": ["document_id", "mesh_options"],
    "solidworks_capture_preview": ["document_id", "view"],
}


def _module():
    return importlib.import_module("plugins.solidworks_agent.mcp_server")


def test_types_are_typed_records():
    types = importlib.import_module("plugins.solidworks_agent.types")
    for name in (
        "ConnectionResult",
        "DocumentRef",
        "SketchRef",
        "SketchEntityRef",
        "FeatureRef",
        "FaceRef",
        "EdgeRef",
        "OperationResult",
    ):
        assert is_dataclass(getattr(types, name))


def test_pywin32_is_lazy(monkeypatch):
    sys.modules.pop("plugins.solidworks_agent.com_adapter", None)
    monkeypatch.delitem(sys.modules, "win32com.client", raising=False)
    module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    assert "win32com.client" not in sys.modules
    assert callable(module.runtime_dispatch_factory)


def test_public_functions_and_fastmcp_schema_have_exact_confirmed_signatures():
    module = _module()
    tools = {tool.name: tool for tool in asyncio.run(module.mcp.list_tools())}
    assert set(tools) == set(EXPECTED_SIGNATURES)
    for name, parameters in EXPECTED_SIGNATURES.items():
        assert list(inspect.signature(getattr(module, name)).parameters) == parameters
        assert list(tools[name].inputSchema.get("properties", {})) == parameters


class FakeAdapter:
    def __init__(self):
        self.calls = []
        self.disconnected = []
        self.document = object()
        self.sketch = object()
        self.entities = [object(), object()]
        self.feature = object()
        self.face = object()
        self.edge = object()

    def connect(self, readiness_timeout=10.0):
        types = importlib.import_module("plugins.solidworks_agent.types")
        return types.ConnectionResult(True, False, "attached")

    def disconnect(self, close_started_instance=False):
        self.disconnected.append(close_started_instance)

    def new_part(self, name, unit):
        self.calls.append(("new_part", name, unit))
        return self.document

    def create_sketch(self, document, plane):
        self.calls.append(("sketch", document, plane))
        return self.sketch

    def add_sketch_geometry(self, sketch, geometry):
        self.calls.append(("geometry", sketch, geometry))
        return self.entities[: len(geometry)]

    def add_dimensions(self, sketch, dimensions, entities):
        self.calls.append(("dimensions", sketch, dimensions, entities))
        return len(dimensions)

    def close_sketch(self, sketch):
        self.calls.append(("close", sketch))

    def extrude(self, document, sketch, depth, direction):
        self.calls.append(("extrude", document, sketch, depth, direction))
        return self.feature

    def revolve(self, document, sketch, axis, angle):
        self.calls.append(("revolve", document, sketch, axis, angle))
        return self.feature

    def cut_extrude(self, document, sketch, depth):
        self.calls.append(("cut", document, sketch, depth))
        return self.feature

    def inspect_model(self, document):
        self.calls.append(("inspect", document))
        return {
            "title": "Part",
            "features": [self.feature],
            "faces": [self.face],
            "edges": [self.edge],
        }

    def save_as(self, document, path, options=None):
        self.calls.append(("save", document, path, options))
        Path(path).write_bytes(b"generated")

    def capture_preview(self, document, path, view):
        self.calls.append(("preview", document, path, view))
        Path(path).write_bytes(b"png")


def _part(adapter=None):
    module = _module()
    adapter = adapter or FakeAdapter()
    service = module.SolidWorksService(adapter=adapter)
    document = service.new_part("session", "Widget", "mm").value
    return service, adapter, document


def _closed_sketch(service, document):
    sketch = service.create_sketch(document.id, "Front Plane").value
    geometry = service.add_sketch_geometry(
        sketch.id, [{"type": "line", "start": [0, 0], "end": [1, 0]}]
    )
    service.close_sketch(sketch.id)
    return sketch, geometry.value[0]


def test_new_part_arguments_and_ordered_feature_options_are_honored():
    service, adapter, document = _part()
    sketch, _ = _closed_sketch(service, document)
    assert service.extrude(document.id, sketch.id, 0.01, "reverse").success
    assert service.revolve(document.id, sketch.id, "horizontal", 1.5).success
    assert service.cut_extrude(document.id, sketch.id, 0.005).success
    assert ("new_part", "Widget", "mm") in adapter.calls
    assert any(call[0] == "extrude" and call[-1] == "reverse" for call in adapter.calls)
    assert any(call[0] == "revolve" and call[-2:] == ("horizontal", 1.5) for call in adapter.calls)


def test_geometry_and_dimensions_use_stable_owned_entity_references():
    service, adapter, document = _part()
    sketch = service.create_sketch(document.id, "Top Plane").value
    geometry = service.add_sketch_geometry(
        sketch.id,
        [{"type": "circle", "center": [0, 0], "radius": 0.01}],
    )
    entity = geometry.value[0]
    assert entity.sketch_id == sketch.id
    result = service.add_dimensions(
        sketch.id,
        [{"type": "diameter", "value": 0.02, "entity_refs": [entity.id], "position": [1, 1]}],
    )
    assert result.success
    assert adapter.calls[-1][-1] == [[adapter.entities[0]]]
    assert (
        service.add_dimensions(
            sketch.id,
            [{"type": "radius", "value": 0.01, "entity_refs": ["foreign"]}],
        ).success
        is False
    )


def test_inspection_returns_stable_owned_feature_face_and_edge_refs():
    service, _, document = _part()
    first = service.inspect_model(document.id).value
    second = service.inspect_model(document.id).value
    for key in ("features", "faces", "edges"):
        assert first[key][0].id == second[key][0].id
        assert first[key][0].document_id == document.id
    assert service.fillet(document.id, [first["edges"][0].id], 0.1).success is False
    assert (
        "Unsupported"
        in service.hole(
            document.id,
            first["faces"][0].id,
            {"type": "simple", "diameter": 0.01, "depth": 0.02},
            [0, 0],
        ).message
    )
    assert service.fillet(document.id, ["foreign"], 0.1).message == "invalid edge reference"


def test_adapter_selects_sketch_uses_modeldoc_manager_and_selects_dimension_entities():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    events = []

    class Selected:
        def Select4(self, append, data):  # noqa: N802
            events.append(("entity-select", append))
            return True

    class Sketch:
        def Select2(self, append, mark):  # noqa: N802
            events.append(("sketch-select", append, mark))
            return True

    class Manager:
        def CreateLine(self, *args):  # noqa: N802
            events.append("line")
            return Selected()

    dimension = SimpleNamespace(GetDimension2=lambda _: SimpleNamespace(SystemValue=0.0))
    document = SimpleNamespace(
        SketchManager=Manager(),
        ClearSelection2=lambda all_items: events.append(("clear", all_items)),
        AddDimension2=lambda *position: (events.append(("dimension", position)), dimension)[1],
        FeatureManager=SimpleNamespace(
            FeatureExtrusion2=lambda *args: (events.append(("extrude", args)), object())[1]
        ),
    )
    context = adapter_module.SketchContext(document, Sketch())
    adapter = adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace())
    created = adapter.add_sketch_geometry(
        context, [{"type": "line", "start": [0, 0], "end": [1, 0]}]
    )
    adapter.add_dimensions(
        context,
        [{"type": "distance", "value": 1.0, "position": [0, 0]}],
        [[created[0]]],
    )
    adapter.extrude(document, context, 0.01, "reverse")
    assert "line" in events
    assert ("entity-select", False) in events
    assert ("sketch-select", False, 0) in events
    extrusion_args = next(
        item[1] for item in events if isinstance(item, tuple) and item[0] == "extrude"
    )
    assert extrusion_args[1] is True


class FakePaths:
    def __init__(self, root, *, allowed=True, confirm=True):
        self.root = Path(root)
        self.allowed = allowed
        self.confirm = confirm
        self.confirmed = []

    def path_for(self, document_id, kind):
        suffix = {"native": ".sldprt", "step": ".step", "stl": ".stl", "preview": ".png"}[kind]
        return str((self.root / f"artifact{suffix}").resolve())

    def validate_output_path(self, path):
        return self.allowed

    def confirm_file(self, path):
        self.confirmed.append(path)
        return self.confirm


def test_file_success_requires_absolute_boundary_existing_and_confirmed(tmp_path):
    service, _, document = _part()
    service.path_service = FakePaths(tmp_path)
    assert service.save_model(document.id).success
    assert service.export_stl(document.id, {"quality": "fine"}).success
    assert service.capture_preview(document.id, "isometric").success
    assert len(service.path_service.confirmed) == 3

    service.path_service = FakePaths(tmp_path, allowed=False)
    assert service.export_step(document.id).success is False
    service.path_service = FakePaths(tmp_path, confirm=False)
    assert service.export_step(document.id).success is False


def test_missing_path_bridge_and_nonexistent_output_fail(tmp_path):
    service, adapter, document = _part()
    assert service.save_model(document.id).success is False
    service.path_service = FakePaths(tmp_path)
    adapter.save_as = lambda document, path, options=None: None
    result = service.export_step(document.id)
    assert result.success is False
    assert "does not exist" in result.message


def test_readiness_timeout_retains_owned_instance_until_policy_disconnect():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    calls = []

    class App:
        IsInitialized = False
        Visible = False

        def ExitApp(self):  # noqa: N802
            calls.append("exit")

    dispatch = SimpleNamespace(
        get_active_object=lambda _: (_ for _ in ()).throw(OSError()),
        dispatch=lambda _: App(),
    )
    adapter = adapter_module.SolidWorksComAdapter(dispatch=dispatch, sleep=lambda _: None)
    result = adapter.connect(readiness_timeout=0)
    assert result.success is False and result.owned is True
    assert adapter._app is not None
    adapter.disconnect(close_started_instance=True)
    assert calls == ["exit"]


def test_server_lifespan_disconnects_with_configured_owned_policy(monkeypatch):
    module = _module()
    adapter = FakeAdapter()
    monkeypatch.setattr(module, "service", module.SolidWorksService(adapter=adapter))
    monkeypatch.setenv("SOLIDWORKS_CLOSE_STARTED_INSTANCE", "true")

    async def run():
        async with module.server_lifespan(module.mcp):
            pass

    asyncio.run(run())
    assert adapter.disconnected == [True]
