import asyncio
import importlib
import inspect
import sys
from dataclasses import is_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_mcp_descriptions_publish_length_and_angle_unit_contracts():
    module = _module()
    tools = {tool.name: tool for tool in asyncio.run(module.mcp.list_tools())}
    for name in (
        "solidworks_add_sketch_geometry",
        "solidworks_add_dimensions",
        "solidworks_extrude",
        "solidworks_cut_extrude",
    ):
        description = tools[name].description.casefold()
        assert "documentref.unit" in description
        assert "si metres" in description
    revolve = tools["solidworks_revolve"].description.casefold()
    assert "degrees" in revolve
    assert "com radians" in revolve


class FakeAdapter:
    def __init__(self):
        self.calls = []
        self.disconnected = []
        self.document = object()
        self.sketch = object()
        self.entities = [object(), object()]
        self.feature = SimpleNamespace(persist_key=b"feature")
        self.face = SimpleNamespace(persist_key=b"face")
        self.edge = SimpleNamespace(persist_key=b"edge")

    def connect(self, readiness_timeout=10.0):
        types = importlib.import_module("plugins.solidworks_agent.types")
        return types.ConnectionResult(True, False, "attached")

    def disconnect(self, close_started_instance=False):
        self.disconnected.append(close_started_instance)

    def new_part(self, name, unit):
        self.calls.append(("new_part", name, unit))
        return self.document

    def create_sketch(self, document, plane, unit="m"):
        self.calls.append(("sketch", document, plane, unit))
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

    def persistent_reference_key(self, document, raw):
        return raw.persist_key.hex()

    def cut_extrude(self, document, sketch, depth):
        self.calls.append(("cut", document, sketch, depth))
        return self.feature

    def inspect_model(self, document):
        self.calls.append(("inspect", document))
        return {
            "title": "Part",
            "features": [SimpleNamespace(persist_key=b"feature")],
            "faces": [SimpleNamespace(persist_key=b"face")],
            "edges": [SimpleNamespace(persist_key=b"edge")],
        }

    def save_as(self, document, path, options=None):
        self.calls.append(("save", document, path, options))
        Path(path).write_bytes(b"generated")

    def capture_preview(self, document, path, view):
        self.calls.append(("preview", document, path, view))
        Path(path).write_bytes(b"png")

    def close_document(self, document):
        self.calls.append(("close-document", document))


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
    sketch, axis = _closed_sketch(service, document)
    assert (document.session_id, document.name, document.unit) == ("session", "Widget", "mm")
    assert service.extrude(document.id, sketch.id, 0.01, "reverse").success
    assert service.revolve(document.id, sketch.id, axis.id, 1.5).success
    assert service.cut_extrude(document.id, sketch.id, 0.005).success
    assert ("new_part", "Widget", "mm") in adapter.calls
    assert any(call[0] == "extrude" and call[-1] == "reverse" for call in adapter.calls)
    assert any(
        call[0] == "revolve" and call[-2:] == (adapter.entities[0], 1.5) for call in adapter.calls
    )
    assert service.revolve(document.id, sketch.id, "foreign", 1.5).success is False


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
        AddDiameterDimension2=lambda *position: (events.append(("diameter", position)), dimension)[
            1
        ],
        AddRadialDimension2=lambda *position: (events.append(("radius", position)), dimension)[1],
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
        [
            {"type": "distance", "value": 1.0, "position": [0, 0]},
            {"type": "diameter", "value": 1.0, "position": [0, 0]},
            {"type": "radius", "value": 1.0, "position": [0, 0]},
        ],
        [[created[0]], [created[0]], [created[0]]],
    )
    adapter.extrude(document, context, 0.01, "reverse")
    assert "line" in events
    assert ("entity-select", False) in events
    assert {event[0] for event in events if isinstance(event, tuple)} >= {
        "dimension",
        "diameter",
        "radius",
    }
    assert ("sketch-select", False, 0) in events
    extrusion_args = next(
        item[1] for item in events if isinstance(item, tuple) and item[0] == "extrude"
    )
    assert extrusion_args[1] is True


def test_adapter_converts_document_units_and_degrees_before_com_calls():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    events = []

    class Entity:
        def Select4(self, append, data):  # noqa: N802
            return True

    class Sketch:
        def Select2(self, append, mark):  # noqa: N802
            return True

    class Manager:
        def CreateLine(self, *args):  # noqa: N802
            events.append(("line", args))
            return Entity()

        def CreateCircleByRadius(self, *args):  # noqa: N802
            events.append(("circle", args))
            return Entity()

    dim_value = SimpleNamespace(SystemValue=0.0)
    dimension = SimpleNamespace(GetDimension2=lambda _: dim_value)
    features = SimpleNamespace(
        FeatureExtrusion2=lambda *args: (events.append(("extrude", args)), object())[1],
        FeatureCut3=lambda *args: (events.append(("cut", args)), object())[1],
        FeatureRevolve2=lambda *args: (events.append(("revolve", args)), object())[1],
    )
    document = SimpleNamespace(
        SketchManager=Manager(),
        ClearSelection2=lambda _: None,
        AddDimension2=lambda *position: (events.append(("dimension", position)), dimension)[1],
        AddDiameterDimension2=lambda *position: dimension,
        AddRadialDimension2=lambda *position: dimension,
        FeatureManager=features,
    )
    adapter = adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace())
    context = adapter_module.SketchContext(document, Sketch(), unit="mm")
    entities = adapter.add_sketch_geometry(
        context,
        [
            {"type": "line", "start": [10, 20], "end": [30, 40]},
            {"type": "circle", "center": [10, 20], "radius": 5},
        ],
    )
    adapter.add_dimensions(
        context,
        [{"type": "distance", "value": 10, "position": [20, 30]}],
        [[entities[0]]],
    )
    assert events[0][1] == (0.01, 0.02, 0.0, 0.03, 0.04, 0.0)
    assert events[1][1] == (0.01, 0.02, 0.0, 0.005)
    assert events[2][1] == (0.02, 0.03, 0.0)
    assert dim_value.SystemValue == 0.01

    adapter.extrude(document, context, 10, "forward")
    adapter.cut_extrude(document, context, 5)
    adapter.revolve(document, context, Entity(), 180)
    assert next(args for name, args in events if name == "extrude")[5] == 0.01
    assert next(args for name, args in events if name == "cut")[5] == 0.005
    revolve_args = next(args for name, args in events if name == "revolve")
    assert revolve_args[6] == pytest.approx(3.141592653589793)

    inch = adapter_module.SketchContext(document, Sketch(), unit="inch")
    adapter.add_sketch_geometry(
        inch, [{"type": "circle", "center": [1, 2], "radius": 0.5}]
    )
    assert events[-1][1] == (0.0254, 0.0508, 0.0, 0.0127)


def test_preview_is_real_png_and_temporary_bmp_is_removed(tmp_path):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    data = tmp_path / "data"
    target = data / "images" / "session" / "preview.png"
    target.parent.mkdir(parents=True)

    class Document:
        def ShowNamedView2(self, *args):  # noqa: N802
            pass

        def ViewZoomtofit2(self):  # noqa: N802
            pass

        def SaveBMP(self, path, width, height):  # noqa: N802
            from PIL import Image

            assert Path(path).suffix.casefold() == ".bmp"
            assert Path(path).parent == data / "tmp"
            Image.new("RGB", (2, 2), "red").save(path, format="BMP")
            return True

    adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace()).capture_preview(
        Document(), str(target), "isometric"
    )
    assert target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not list((data / "tmp").glob("*.bmp"))


def test_connect_uses_solidworks_2023_progid_and_rejects_other_major_versions():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    calls = []

    class App:
        IsInitialized = True
        RevisionNumber = "31.5.0"

    dispatch = SimpleNamespace(
        get_active_object=lambda prog_id: (calls.append(("attach", prog_id)), App())[1],
        dispatch=lambda prog_id: (calls.append(("start", prog_id)), App())[1],
    )
    result = adapter_module.SolidWorksComAdapter(dispatch=dispatch).connect()
    assert result.success and result.owned is False
    assert calls == [("attach", "SldWorks.Application.31")]

    wrong = App()
    wrong.RevisionNumber = lambda: "32.0.0"
    dispatch = SimpleNamespace(get_active_object=lambda _: wrong, dispatch=lambda _: None)
    adapter = adapter_module.SolidWorksComAdapter(dispatch=dispatch)
    result = adapter.connect()
    assert result.success is False
    assert "2023" in result.message
    assert adapter._app is None


def test_connect_starts_visible_2023_when_no_active_instance():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    calls = []

    class App:
        IsInitialized = True
        RevisionNumber = "31.0"
        Visible = False

    app = App()
    dispatch = SimpleNamespace(
        get_active_object=lambda prog_id: (_ for _ in ()).throw(OSError()),
        dispatch=lambda prog_id: (calls.append(prog_id), app)[1],
    )
    result = adapter_module.SolidWorksComAdapter(dispatch=dispatch).connect()
    assert result.success and result.owned and app.Visible
    assert calls == ["SldWorks.Application.31"]


class FakePaths:
    def __init__(self, root, *, allowed=True, confirm=True):
        self.root = Path(root)
        self.allowed = allowed
        self.confirm = confirm
        self.confirmed = []

    def path_for(self, document, kind):
        self.document = document
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
    assert service.path_service.document.session_id == "session"

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


def test_default_service_receives_the_environment_path_bridge():
    module = _module()
    assert module.service.path_service is not None


def test_readiness_timeout_retains_owned_instance_until_policy_disconnect():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    calls = []

    class App:
        IsInitialized = False
        Visible = False
        RevisionNumber = "31.0"

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


def test_server_lifespan_closes_held_documents_and_clears_all_references(monkeypatch):
    module = _module()

    class ClosingAdapter(FakeAdapter):
        def close_document(self, document):
            self.calls.append(("close-document", document))
            if document == "bad":
                raise RuntimeError("close failed")

    adapter = ClosingAdapter()
    scoped = module.SolidWorksService(adapter=adapter)
    scoped.documents = {
        "one": (SimpleNamespace(), "bad"),
        "two": (SimpleNamespace(), "good"),
    }
    for registry in (
        scoped.sketches,
        scoped.entities,
        scoped.features,
        scoped.faces,
        scoped.edges,
    ):
        registry["held"] = (SimpleNamespace(), object())
    monkeypatch.setattr(module, "service", scoped)

    async def run():
        async with module.server_lifespan(module.mcp):
            pass

    asyncio.run(run())
    assert ("close-document", "bad") in adapter.calls
    assert ("close-document", "good") in adapter.calls
    assert not scoped.documents
    assert all(
        not registry
        for registry in (
            scoped.sketches,
            scoped.entities,
            scoped.features,
            scoped.faces,
            scoped.edges,
        )
    )
    assert adapter.disconnected == [False]


def test_persistent_reference_key_uses_model_extension_and_survives_new_wrappers():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    extension = SimpleNamespace(GetPersistReference3=lambda raw: b"stable-key")
    adapter = adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace())
    assert adapter.persistent_reference_key(SimpleNamespace(Extension=extension), object()) == (
        b"stable-key".hex()
    )

    service, _, document = _part()
    first = service.inspect_model(document.id).value
    second = service.inspect_model(document.id).value
    assert first["faces"][0].id == second["faces"][0].id
    assert first["edges"][0].id == second["edges"][0].id


def test_unsupported_payloads_are_strictly_validated_before_safe_failure():
    service, _, document = _part()
    inspected = service.inspect_model(document.id).value
    face = inspected["faces"][0].id
    edge = inspected["edges"][0].id
    feature = inspected["features"][0].id

    valid_cases = [
        service.hole(
            document.id, face, {"type": "simple", "diameter": 0.01, "depth": 0.02}, [0, 0]
        ),
        service.fillet(document.id, [edge], 0.001),
        service.chamfer(
            document.id,
            [edge],
            {"type": "distance_angle", "distance": 0.001, "angle": 0.75},
        ),
        service.mirror_feature(document.id, [feature], "Front Plane"),
        service.pattern_feature(
            document.id,
            feature,
            {"type": "linear", "direction": "x", "spacing": 0.01, "count": 3},
        ),
    ]
    assert all("Unsupported operation" in result.message for result in valid_cases)

    invalid_cases = [
        service.hole(document.id, face, {"type": "simple", "diameter": -1, "depth": 1}, [0, 0]),
        service.fillet(document.id, [edge], -1),
        service.chamfer(document.id, [edge], {"type": "distance_angle", "distance": 1}),
        service.mirror_feature(document.id, [feature], "arbitrary"),
        service.pattern_feature(
            document.id,
            feature,
            {"type": "linear", "direction": "x", "spacing": 1, "count": 1, "macro": "x"},
        ),
    ]
    assert all("Unsupported operation" not in result.message for result in invalid_cases)
