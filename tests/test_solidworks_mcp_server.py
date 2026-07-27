import asyncio
import importlib
import inspect
import json
import math
import re
import sys
from dataclasses import is_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

EXPECTED_SIGNATURES = {
    "solidworks_status": [],
    "solidworks_new_part": ["session_id", "name", "unit"],
    "solidworks_create_sketch": ["document_id", "plane"],
    "solidworks_create_sketch_on_face": ["document_id", "face_ref"],
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


def test_mcp_descriptions_publish_model_facing_workflow_contracts():
    module = _module()
    tools = {tool.name: tool for tool in asyncio.run(module.mcp.list_tools())}
    descriptions = {name: tools[name].description.casefold() for name in EXPECTED_SIGNATURES}

    assert all(len(description) >= 80 for description in descriptions.values())
    for name in (
        "solidworks_create_sketch_on_face",
        "solidworks_add_dimensions",
        "solidworks_hole",
        "solidworks_fillet",
        "solidworks_chamfer",
        "solidworks_mirror_feature",
        "solidworks_pattern_feature",
    ):
        assert "server-owned" in descriptions[name]
    topology_safety = "after this call before reusing any face, edge, or feature reference"
    for name in (
        "solidworks_extrude",
        "solidworks_revolve",
        "solidworks_cut_extrude",
        "solidworks_hole",
        "solidworks_fillet",
        "solidworks_chamfer",
        "solidworks_mirror_feature",
        "solidworks_pattern_feature",
    ):
        assert topology_safety in " ".join(descriptions[name].split())
    for name in (
        "solidworks_add_sketch_geometry",
        "solidworks_add_dimensions",
        "solidworks_extrude",
        "solidworks_cut_extrude",
    ):
        assert "documentref.unit" in descriptions[name]
        assert "si metres" in descriptions[name]
    assert "degrees" in descriptions["solidworks_revolve"]
    assert "com radians" in descriptions["solidworks_revolve"]
    for unit in ("mm", "cm", "m", "inch"):
        assert f"`{unit}`" in descriptions["solidworks_new_part"]
    for plane in ("front plane", "top plane", "right plane"):
        assert f"`{plane}`" in descriptions["solidworks_create_sketch"]
    mirror_planes = set(re.findall(r"`([^`]+ plane)`", descriptions["solidworks_mirror_feature"]))
    assert mirror_planes == {"front plane", "top plane", "right plane"}
    for direction in ("forward", "reverse"):
        assert f"`{direction}`" in descriptions["solidworks_extrude"]
    for view in ("front", "top", "right", "isometric"):
        assert f"`{view}`" in descriptions["solidworks_capture_preview"]
    for quality in ("coarse", "medium", "fine"):
        assert f'"quality":"{quality}"' in descriptions["solidworks_export_stl"]
    for name in ("solidworks_save_model", "solidworks_export_step", "solidworks_export_stl", "solidworks_capture_preview"):
        assert "server-controlled" in descriptions[name]
        assert "artifact" in descriptions[name]

    examples = {}
    for name in (
        "solidworks_add_sketch_geometry",
        "solidworks_add_dimensions",
        "solidworks_hole",
        "solidworks_chamfer",
        "solidworks_pattern_feature",
    ):
        match = re.search(
            r"Example:\s*`(?P<example>\[.*?\]|\{.*?\})`", tools[name].description, re.DOTALL
        )
        assert match, f"{name} must publish a JSON-shaped example"
        examples[name] = json.loads(match.group("example"))

    assert examples["solidworks_add_sketch_geometry"] == [
        {"type": "line", "start": [0, 0], "end": [10, 0]}
    ]
    assert all(f"`{kind}`" in descriptions["solidworks_add_sketch_geometry"] for kind in (
        "line", "circle", "center_rectangle", "three_point_arc"
    ))
    assert examples["solidworks_add_dimensions"] == [
        {"type": "distance", "value": 10, "entity_refs": ["entity-id"]}
    ]
    assert all(f"`{kind}`" in descriptions["solidworks_add_dimensions"] for kind in (
        "distance", "diameter", "radius"
    ))
    assert examples["solidworks_hole"] == {"type": "simple", "diameter": 5, "depth": 10}
    for kind in ("simple", "counterbore", "countersink"):
        assert f"`{kind}`" in descriptions["solidworks_hole"]
    for field in ("counterbore_diameter", "counterbore_depth", "countersink_diameter", "angle"):
        assert f"`{field}`" in descriptions["solidworks_hole"]
    assert examples["solidworks_chamfer"] == {
        "type": "distance_angle", "distance": 2, "angle": 45
    }
    for field in ("type", "distance", "angle"):
        assert f"`{field}`" in descriptions["solidworks_chamfer"]
    assert examples["solidworks_pattern_feature"] == {
        "type": "linear", "direction": "x", "spacing": 10, "count": 3
    }
    for field in ("type", "direction", "spacing", "count", "angle"):
        assert f"`{field}`" in descriptions["solidworks_pattern_feature"]
    assert (
        "`circular` requires `type`, `angle`, and `count`, with angle in degrees and count is "
        "2 through 100"
    ) in " ".join(descriptions["solidworks_pattern_feature"].split())


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
        self.created_features = []

    def _created_feature(self, kind):
        if self.feature is None:
            return None
        raw = SimpleNamespace(persist_key=f"{kind}-{len(self.created_features)}".encode())
        self.created_features.append(raw)
        return raw

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

    def create_sketch_on_face(self, document, face, unit="m"):
        self.calls.append(("face-sketch", document, face, unit))
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

    def hole(self, document, face, specification, position, unit):
        self.calls.append(("hole", document, face, specification, position, unit))
        return self._created_feature("hole")

    def fillet(self, document, edges, radius, unit):
        self.calls.append(("fillet", document, edges, radius, unit))
        return self._created_feature("fillet")

    def chamfer(self, document, edges, specification, unit):
        self.calls.append(("chamfer", document, edges, specification, unit))
        return self._created_feature("chamfer")

    def mirror_feature(self, document, features, plane):
        self.calls.append(("mirror", document, features, plane))
        return self._created_feature("mirror")

    def pattern_feature(self, document, feature, pattern, unit):
        self.calls.append(("pattern", document, feature, pattern, unit))
        return self._created_feature("pattern")

    def inspect_model(self, document):
        self.calls.append(("inspect", document))
        return {
            "title": "Part",
            "features": [SimpleNamespace(persist_key=b"feature"), *self.created_features],
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
    assert service.fillet(document.id, [first["edges"][0].id], 0.1).success
    assert service.hole(
        document.id,
        first["faces"][0].id,
        {"type": "simple", "diameter": 0.01, "depth": 0.02},
        [0, 0],
    ).success
    assert service.fillet(document.id, ["foreign"], 0.1).message == "invalid edge reference"


def test_feature_operations_resolve_only_owned_references_and_register_results():
    service, adapter, document = _part()
    inspected = service.inspect_model(document.id).value
    face = inspected["faces"][0]
    edge = inspected["edges"][0]
    feature = inspected["features"][0]

    operations = [
        (
            service.hole(
                document.id,
                face.id,
                {"type": "simple", "diameter": 10, "depth": 20},
                [5, 6],
            ),
            "hole",
        ),
        (service.fillet(document.id, [edge.id], 2), "fillet"),
        (
            service.chamfer(
                document.id,
                [edge.id],
                {"type": "distance_angle", "distance": 3, "angle": 45},
            ),
            "chamfer",
        ),
        (service.mirror_feature(document.id, [feature.id], "Front Plane"), "mirror"),
        (
            service.pattern_feature(
                document.id,
                feature.id,
                {"type": "linear", "direction": "x", "spacing": 8, "count": 3},
            ),
            "pattern",
        ),
        (
            service.pattern_feature(
                document.id,
                feature.id,
                {"type": "circular", "angle": 180, "count": 4},
            ),
            "pattern",
        ),
    ]

    assert all(result.success for result, _ in operations)
    assert [kind for _, kind in operations] == [result.value.kind for result, _ in operations]
    assert adapter.calls[-6:] == [
        ("hole", adapter.document, adapter.face, {"type": "simple", "diameter": 10.0, "depth": 20.0}, [5.0, 6.0], "mm"),
        ("fillet", adapter.document, [adapter.edge], 2.0, "mm"),
        ("chamfer", adapter.document, [adapter.edge], {"type": "distance_angle", "distance": 3.0, "angle": 45.0}, "mm"),
        ("mirror", adapter.document, [adapter.feature], "Front Plane"),
        ("pattern", adapter.document, adapter.feature, {"type": "linear", "direction": "x", "spacing": 8.0, "count": 3}, "mm"),
        ("pattern", adapter.document, adapter.feature, {"type": "circular", "angle": 180.0, "count": 4}, "mm"),
    ]


def test_feature_operation_validation_rejects_foreign_references_and_false_com_results():
    service, adapter, document = _part()
    inspected = service.inspect_model(document.id).value
    face = inspected["faces"][0].id
    edge = inspected["edges"][0].id
    feature = inspected["features"][0].id

    assert not service.hole(document.id, "foreign", {"type": "simple", "diameter": 1, "depth": 1}, [0, 0]).success
    assert not service.fillet(document.id, [], 1).success
    assert not service.chamfer(document.id, [edge], {"type": "distance_angle", "distance": 1, "angle": 0}).success
    assert not service.mirror_feature(document.id, [feature], "arbitrary").success
    assert not service.pattern_feature(document.id, "foreign", {"type": "circular", "angle": 90, "count": 2}).success

    adapter.feature = None
    assert not service.hole(document.id, face, {"type": "simple", "diameter": 1, "depth": 1}, [0, 0]).success


def test_created_feature_reference_is_reused_by_later_inspection():
    service, _, document = _part()
    edge = service.inspect_model(document.id).value["edges"][0].id

    created = service.fillet(document.id, [edge], 2)
    inspected = service.inspect_model(document.id)

    assert created.success
    assert inspected.success
    assert created.value.id in [feature.id for feature in inspected.value["features"]]


def test_feature_operation_success_covers_counterbore_and_countersink_payloads():
    service, adapter, document = _part()
    face = service.inspect_model(document.id).value["faces"][0].id

    counterbore = service.hole(
        document.id,
        face,
        {
            "type": "counterbore",
            "diameter": 5,
            "depth": 10,
            "counterbore_diameter": 9,
            "counterbore_depth": 3,
        },
        [2, 3],
    )
    countersink = service.hole(
        document.id,
        face,
        {
            "type": "countersink",
            "diameter": 5,
            "depth": 10,
            "countersink_diameter": 9,
            "angle": 82,
        },
        [2, 3],
    )

    assert counterbore.success and countersink.success
    assert adapter.calls[-2:] == [
        (
            "hole",
            adapter.document,
            adapter.face,
            {
                "type": "counterbore",
                "diameter": 5.0,
                "depth": 10.0,
                "counterbore_diameter": 9.0,
                "counterbore_depth": 3.0,
            },
            [2.0, 3.0],
            "mm",
        ),
        (
            "hole",
            adapter.document,
            adapter.face,
            {
                "type": "countersink",
                "diameter": 5.0,
                "depth": 10.0,
                "countersink_diameter": 9.0,
                "angle": 82.0,
            },
            [2.0, 3.0],
            "mm",
        ),
    ]


def test_face_sketch_and_three_point_arc_are_public_and_owned():
    module = _module()
    tools = {tool.name: tool for tool in asyncio.run(module.mcp.list_tools())}
    assert list(inspect.signature(module.solidworks_create_sketch_on_face).parameters) == [
        "document_id",
        "face_ref",
    ]
    assert list(tools["solidworks_create_sketch_on_face"].inputSchema["properties"]) == [
        "document_id",
        "face_ref",
    ]

    service, adapter, document = _part()
    face_ref = service.inspect_model(document.id).value["faces"][0].id
    sketch = service.create_sketch_on_face(document.id, face_ref)
    assert sketch.success
    assert adapter.calls[-1] == ("face-sketch", adapter.document, adapter.face, "mm")

    arc = service.add_sketch_geometry(
        sketch.value.id,
        [{"type": "three_point_arc", "start": [0, 0], "mid": [1, 1], "end": [2, 0]}],
    )
    assert arc.success
    assert arc.value[0].kind == "three_point_arc"
    assert adapter.calls[-1] == (
        "geometry",
        adapter.sketch,
        [{"type": "three_point_arc", "start": [0.0, 0.0], "mid": [1.0, 1.0], "end": [2.0, 0.0]}],
    )
    assert service.create_sketch_on_face(document.id, "foreign").message == "invalid face reference"

    events = []
    active_sketch = object()
    face = SimpleNamespace(Select4=lambda append, data: events.append((append, data)) or True)
    face_document = SimpleNamespace(
        ClearSelection2=lambda all_items: events.append(("clear", all_items)),
        SketchManager=SimpleNamespace(InsertSketch=lambda editing: events.append(("insert", editing))),
        GetActiveSketch2=lambda: active_sketch,
    )
    context = importlib.import_module("plugins.solidworks_agent.com_adapter").SolidWorksComAdapter(
        dispatch=SimpleNamespace()
    ).create_sketch_on_face(face_document, face, "inch")
    assert context.sketch is active_sketch
    assert context.unit == "inch"
    assert events == [("clear", True), (False, None), ("insert", True)]


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


def test_create_sketch_falls_back_to_localized_standard_plane_name(monkeypatch):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    selected = []
    sketch = object()
    dispatch_nothing = object()
    monkeypatch.setattr(adapter_module, "_empty_com_dispatch", lambda: dispatch_nothing)
    callouts = []

    def select_plane(name, *args):
        selected.append(name)
        callouts.append(args[6])
        if args[6] is None:
            raise TypeError("typed callout mismatch")
        assert args[6] is dispatch_nothing
        return name == "前视基准面"

    extension = SimpleNamespace(SelectByID2=select_plane)
    manager = SimpleNamespace(InsertSketch=lambda _: None)
    document = SimpleNamespace(
        Extension=extension,
        SketchManager=manager,
        GetActiveSketch2=lambda: sketch,
    )

    context = adapter_module.SolidWorksComAdapter(
        dispatch=SimpleNamespace()
    ).create_sketch(document, "Front Plane", "mm")

    assert context.sketch is sketch
    assert selected == ["Front Plane", "Front Plane", "前视基准面", "前视基准面"]
    assert callouts == [None, dispatch_nothing, None, dispatch_nothing]


def test_close_document_accepts_get_title_as_a_com_property():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    closed = []
    adapter = adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace())
    adapter._app = SimpleNamespace(CloseDoc=closed.append)

    adapter.close_document(SimpleNamespace(GetTitle="property-title"))

    assert closed == ["property-title"]


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

        def Create3PointArc(self, *args):  # noqa: N802
            events.append(("arc", args))
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
            {"type": "three_point_arc", "start": [10, 20], "mid": [30, 40], "end": [50, 60]},
        ],
    )
    adapter.add_dimensions(
        context,
        [{"type": "distance", "value": 10, "position": [20, 30]}],
        [[entities[0]]],
    )
    assert events[0][1] == (0.01, 0.02, 0.0, 0.03, 0.04, 0.0)
    assert events[1][1] == (0.01, 0.02, 0.0, 0.005)
    assert events[2][1] == (0.01, 0.02, 0.0, 0.03, 0.04, 0.0, 0.05, 0.06, 0.0)
    assert events[3][1] == (0.02, 0.03, 0.0)
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


def test_adapter_feature_operations_use_feature_data_and_documented_hole_ray_selection(
    monkeypatch,
):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    events = []

    class ModelToSketchTransform:
        @property
        def Inverse(self):  # noqa: N802
            events.append(("inverse-transform",))
            return SketchToModelTransform()

    class SketchToModelTransform:
        def apply(self, coordinates):
            events.append(("apply-inverse-transform", coordinates))
            x, y, z = coordinates
            return (2.0 - y, 3.0 + x, 4.0 + z)

    class MathPoint:
        def __init__(self, coordinates):
            self._coordinates = tuple(coordinates)

        @property
        def ArrayData(self):  # noqa: N802
            return self._coordinates

        def MultiplyTransform(self, transform):  # noqa: N802
            return MathPoint(transform.apply(self._coordinates))

    class MathUtility:
        def CreatePoint(self, coordinates):  # noqa: N802
            events.append(("create-math-point", tuple(coordinates)))
            return MathPoint(coordinates)

    class Sketch:
        def __init__(self):
            self.ModelToSketchTransform = ModelToSketchTransform()

    class Selectable:
        def __init__(self, name, x=0.1, y=0.2, z=0.3):
            self.name = name
            self._coordinates = (x, y, z)

        @property
        def X(self):  # noqa: N802
            events.append(("model-coordinate", self.name, "X", self._coordinates[0]))
            return self._coordinates[0]

        @property
        def Y(self):  # noqa: N802
            events.append(("model-coordinate", self.name, "Y", self._coordinates[1]))
            return self._coordinates[1]

        @property
        def Z(self):  # noqa: N802
            events.append(("model-coordinate", self.name, "Z", self._coordinates[2]))
            return self._coordinates[2]

        def GetSketch(self):  # noqa: N802
            events.append(("get-sketch", self.name))
            return Sketch()

        def Select4(self, append, data):  # noqa: N802
            events.append(("select4", self.name, append, getattr(data, "Mark", None)))
            return True

        def Select2(self, append, mark):  # noqa: N802
            events.append(("select2", self.name, append, mark))
            return True

    class SketchManager:
        def InsertSketch(self, editing):  # noqa: N802
            events.append(("sketch", editing))

        def CreatePoint(self, x, y, z):  # noqa: N802
            events.append(("point", x, y, z))
            return Selectable("point", x, y, z)

    feature = object()
    definitions = []

    class FeatureData(SimpleNamespace):
        def __init__(self, kind):
            super().__init__(kind=kind)

        def Initialize(self, value):  # noqa: N802
            events.append(("initialize", self.kind, value))

    def create_definition(kind):
        data = FeatureData(kind)
        definitions.append(data)
        events.append(("definition", kind))
        return data

    manager = SimpleNamespace(
        HoleWizard5=lambda *args: (events.append(("hole5", args)), feature)[1],
        InsertFeatureChamfer=lambda *args: (events.append(("chamfer", args)), feature)[1],
        InsertMirrorFeature2=lambda *args: (events.append(("mirror2", args)), feature)[1],
        CreateDefinition=create_definition,
        CreateFeature=lambda data: (events.append(("create-feature", data.kind)), feature)[1],
    )
    document = SimpleNamespace(
        ClearSelection2=lambda all_items: events.append(("clear", all_items)),
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: SimpleNamespace()),
        SketchManager=SketchManager(),
        Extension=SimpleNamespace(
            SelectByID2=lambda name, entity_type, *args: events.append(
                ("plane", name, entity_type, args[4])
            )
            or True,
            SelectByRay=lambda *args: events.append(("ray", args))
            or (args[7] == "face" and args[9] == 0),
            GetPersistReference3=lambda raw: raw.persist_key,
        ),
        FeatureManager=manager,
    )
    face = Selectable("face")
    face.GetSurface = lambda: SimpleNamespace(IsPlane=lambda: True)
    face.Normal = (0.0, 0.0, 1.0)
    face.persist_key = b"face"
    document.SelectionManager.GetSelectedObject6 = lambda *_: face
    edge = Selectable("edge")
    seed = Selectable("seed")
    adapter = adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace())
    adapter._app = SimpleNamespace(GetMathUtility=lambda: MathUtility())
    constants = {
        "swFmFillet": "fillet",
        "swFmLPattern": "linear",
        "swFmCirPattern": "circular",
        "swConstRadiusFillet": "constant-radius",
        "swFeatureFilletCircular": "circular-profile",
        "swSelSKETCHPOINTS": "sketch-point",
        "swSelFACES": "face",
    }
    monkeypatch.setattr(
        adapter_module, "_solidworks_constant", constants.__getitem__, raising=False
    )

    adapter.hole(
        document,
        face,
        {
            "type": "counterbore",
            "diameter": 5,
            "depth": 10,
            "counterbore_diameter": 9,
            "counterbore_depth": 3,
        },
        [10, 20],
        "mm",
    )
    adapter.fillet(document, [edge], 2, "mm")
    adapter.chamfer(document, [edge], {"type": "distance_angle", "distance": 3, "angle": 45}, "mm")
    adapter.mirror_feature(document, [seed], "Front Plane")
    adapter.pattern_feature(document, seed, {"type": "linear", "direction": "x", "spacing": 8, "count": 3}, "mm")
    adapter.pattern_feature(document, seed, {"type": "circular", "angle": 180, "count": 4}, "mm")

    assert ("point", 0.01, 0.02, 0.0) in events
    assert ("select4", "face", False, 0) in events
    assert ("select4", "edge", False, 1) in events
    assert ("select4", "seed", False, 1) in events
    assert ("select4", "seed", False, 4) in events
    assert ("plane", "Front Plane", "PLANE", 2) in events
    assert ("plane", "Right Plane", "PLANE", 1) in events
    assert ("plane", "Top Plane", "PLANE", 1) in events
    ray_args = next(item[1] for item in events if item[0] == "ray")
    assert ray_args[:3] == pytest.approx((1.98, 3.01, 4.0))
    assert ray_args[3:] == (0.0, 0.0, 1.0, 1e-7, "face", False, 0, 0)
    assert [item for item in events if item[0] in {
        "get-sketch",
        "create-math-point",
        "inverse-transform",
        "apply-inverse-transform",
    }] == [
        ("get-sketch", "point"),
        ("create-math-point", (0.01, 0.02, 0.0)),
        ("inverse-transform",),
        ("apply-inverse-transform", (0.01, 0.02, 0.0)),
    ]
    assert next(item[1] for item in events if item[0] == "hole5")[5:10] == pytest.approx(
        (
        0.005,
        0.01,
        -1.0,
        0.009,
        0.003,
        )
    )
    assert [item[1] for item in events if item[0] == "definition"] == [
        "fillet",
        "linear",
        "circular",
    ]
    assert ("initialize", "fillet", "constant-radius") in events
    fillet_data, linear_data, circular_data = definitions
    assert fillet_data.DefaultRadius == pytest.approx(0.002)
    assert fillet_data.ConicTypeForCrossSectionProfile == "circular-profile"
    assert linear_data.D1Spacing == pytest.approx(0.008)
    assert linear_data.D1TotalInstances == 3
    assert circular_data.Spacing == pytest.approx(math.pi)
    assert circular_data.TotalInstances == 4
    assert next(item[1] for item in events if item[0] == "chamfer")[2:4] == pytest.approx(
        (0.003, math.pi / 4)
    )
    assert next(item[1] for item in events if item[0] == "mirror2") == (False, False, False, False, 0)
    assert events.count(("clear", True)) == 13


def test_adapter_feature_selection_is_cleared_when_com_call_raises(monkeypatch):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    clears = []
    edge = SimpleNamespace(Select4=lambda append, data: True)
    document = SimpleNamespace(
        ClearSelection2=lambda all_items: clears.append(all_items),
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: SimpleNamespace()),
        FeatureManager=SimpleNamespace(
            CreateDefinition=lambda _: SimpleNamespace(
                Initialize=lambda _: None,
                __setattr__=object.__setattr__,
            ),
            CreateFeature=lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
        ),
    )

    monkeypatch.setattr(adapter_module, "_solidworks_constant", lambda _: 1, raising=False)

    with pytest.raises(RuntimeError, match="boom"):
        adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace()).fillet(
            document, [edge], 2, "mm"
        )

    assert clears == [True, True]


def test_raw_selection_falls_back_to_select2_when_select4_is_unavailable():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    calls = []
    raw = SimpleNamespace(
        Select4=lambda append, data: (_ for _ in ()).throw(RuntimeError("missing member")),
        Select2=lambda append, mark: calls.append((append, mark)) or True,
    )
    document = SimpleNamespace(
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: SimpleNamespace())
    )

    adapter_module.SolidWorksComAdapter()._select_raw(document, raw, False, 0)

    assert calls == [(False, 0)]


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


def test_save_as_creates_parent_and_parses_typed_byref_result(tmp_path):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    target = tmp_path / "data" / "models" / "session" / "part.sldprt"
    calls = []

    def save_as(path, *args):
        calls.append((path, args))
        assert Path(path).parent.is_dir()
        Path(path).write_bytes(b"model")
        return True, 0, 0

    document = SimpleNamespace(Extension=SimpleNamespace(SaveAs=save_as))
    adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace()).save_as(
        document, str(target)
    )

    assert target.is_file()
    assert calls[0][0] == str(target.resolve())


def test_save_as_reports_typed_solidworks_error_codes(tmp_path):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    target = tmp_path / "data" / "exports" / "session" / "part.step"
    document = SimpleNamespace(
        Extension=SimpleNamespace(SaveAs=lambda *args: (False, 8, 2))
    )

    with pytest.raises(RuntimeError, match="errors=8.*warnings=2"):
        adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace()).save_as(
            document, str(target)
        )


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


def test_connect_closes_only_a_newly_started_instance_when_version_is_wrong():
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    exit_calls = []

    class WrongVersionApp:
        IsInitialized = True
        RevisionNumber = "32.0"
        Visible = False

        def ExitApp(self):  # noqa: N802
            exit_calls.append("exit")

    app = WrongVersionApp()
    dispatch = SimpleNamespace(
        get_active_object=lambda _: (_ for _ in ()).throw(OSError()),
        dispatch=lambda _: app,
    )

    result = adapter_module.SolidWorksComAdapter(dispatch=dispatch).connect()

    assert result.success is False
    assert exit_calls == ["exit"]


def test_new_part_uses_administrator_template_fallback_when_default_is_empty(
    monkeypatch, tmp_path
):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    template = tmp_path / "gb_part.prtdot"
    template.write_bytes(b"template")
    calls = []
    document = SimpleNamespace(
        SetTitle2=lambda name: calls.append(("title", name)),
        SetUserPreferenceIntegerValue=lambda key, value: calls.append(
            ("unit", key, value)
        ),
    )
    app = SimpleNamespace(
        GetUserPreferenceStringValue=lambda _: "",
        NewDocument=lambda path, *args: (calls.append(("template", path)), document)[1],
    )
    adapter = adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace())
    adapter._app = app
    monkeypatch.setenv("SOLIDWORKS_PART_TEMPLATE", str(template))

    assert adapter.new_part("fallback-part", "mm") is document
    assert ("template", str(template.resolve())) in calls


def test_new_part_wraps_a_real_com_document_with_the_generated_modeldoc_type(
    monkeypatch
):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    raw = SimpleNamespace()
    wrapped = SimpleNamespace(
        SetTitle2=lambda _: None,
        SetUserPreferenceIntegerValue=lambda *_: None,
    )
    app = SimpleNamespace(
        GetUserPreferenceStringValue=lambda _: "C:\\template.prtdot",
        NewDocument=lambda *_: raw,
    )
    adapter = adapter_module.SolidWorksComAdapter(dispatch=SimpleNamespace())
    adapter._app = app
    monkeypatch.setattr(
        adapter_module,
        "_typed_model_document",
        lambda document: wrapped if document is raw else document,
    )

    assert adapter.new_part("typed-part", "mm") is wrapped


def test_inspection_uses_partdoc_wrapper_for_part_topology(monkeypatch):
    adapter_module = importlib.import_module("plugins.solidworks_agent.com_adapter")
    edge = object()
    face = SimpleNamespace(GetEdges=(edge,))
    body = SimpleNamespace(GetFaces=(face,))
    feature = SimpleNamespace(GetTypeName2="BossExtrude")
    configuration_table = SimpleNamespace(GetTypeName2="NativeConfigurationTableFeature")
    calls = []
    document = SimpleNamespace(
        FeatureManager=SimpleNamespace(
            GetFeatures=lambda top_level: [feature, configuration_table]
        ),
        GetTitle=lambda: "Part",
    )
    part_document = SimpleNamespace(
        GetBodies2=lambda body_type, visible_only: calls.append(
            (body_type, visible_only)
        )
        or [body]
    )
    monkeypatch.setattr(adapter_module, "_typed_part_document", lambda _: part_document)

    details = adapter_module.SolidWorksComAdapter().inspect_model(document)

    assert calls == [(0, True)]
    assert details == {
        "title": "Part",
        "features": [feature],
        "faces": [face],
        "edges": [edge],
    }


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


def test_feature_payloads_are_strictly_validated_before_com_access():
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
    assert all(result.success for result in valid_cases)

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
    assert all(result.success is False for result in invalid_cases)
