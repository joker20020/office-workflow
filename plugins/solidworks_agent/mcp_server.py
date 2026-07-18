"""Constrained feature-level MCP server for SolidWorks."""

from __future__ import annotations

import json
import math
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from mcp.server.fastmcp import FastMCP

from .com_adapter import SolidWorksComAdapter
from .paths import path_bridge_from_environment
from .types import (
    DocumentRef,
    EdgeRef,
    FaceRef,
    FeatureRef,
    OperationResult,
    SketchEntityRef,
    SketchRef,
)

MAX_ITEMS = 100
PLANES = {"Front Plane", "Top Plane", "Right Plane"}
UNITS = {"mm", "cm", "m", "inch"}
DIRECTIONS = {"forward", "reverse"}
VIEWS = {"front", "top", "right", "isometric"}


class InternalPathService(Protocol):
    def path_for(self, document: DocumentRef, kind: str) -> str: ...
    def validate_output_path(self, path: str) -> bool: ...
    def confirm_file(self, path: str) -> bool: ...


def _safe_error(exc: Exception) -> str:
    return f"Unsupported operation: {exc}" if isinstance(exc, NotImplementedError) else str(exc)


def render_result(result: OperationResult) -> str:
    files = "\n".join(f"- {path}" for path in result.generated_files) or "None"
    verification = "\n".join(f"- {item}" for item in result.verification) or "Not verified."
    warnings = "\n".join(f"- {item}" for item in result.warnings) or "None"
    value = ""
    if result.value is not None:
        public = asdict(result.value) if is_dataclass(result.value) else result.value
        if isinstance(public, dict):
            public = {
                key: [asdict(item) if is_dataclass(item) else item for item in item_value]
                if isinstance(item_value, list)
                else item_value
                for key, item_value in public.items()
            }
        value = f"\nResult: `{json.dumps(public, ensure_ascii=False, sort_keys=True)}`"
    return (
        f"## Status\n{'Success' if result.success else 'Failed'}\n"
        f"## Execution Summary\n{result.message}{value}\n"
        f"## Generated Files\n{files}\n"
        f"## Verification\n{verification}\n## Warnings\n{warnings}"
    )


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or abs(number) > 1000 or (positive and number <= 0):
        raise ValueError(f"invalid {name}")
    return number


def _point(value: Any, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a two-number list")
    return [_number(item, name) for item in value]


def _items(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_ITEMS:
        raise ValueError(f"{name} must contain 1 to {MAX_ITEMS} items")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{name} items must be dictionaries")
    return value


def _geometry(value: Any) -> list[dict[str, Any]]:
    schemas = {
        "line": {"type", "start", "end"},
        "circle": {"type", "center", "radius"},
        "center_rectangle": {"type", "center", "corner"},
    }
    clean = []
    for item in _items(value, "geometry"):
        kind = item.get("type")
        if kind not in schemas or set(item) != schemas[kind]:
            raise ValueError("unsupported geometry variant or fields")
        record = {"type": kind}
        if kind == "line":
            record.update(start=_point(item["start"], "start"), end=_point(item["end"], "end"))
        elif kind == "circle":
            record.update(
                center=_point(item["center"], "center"),
                radius=_number(item["radius"], "radius", positive=True),
            )
        else:
            record.update(
                center=_point(item["center"], "center"), corner=_point(item["corner"], "corner")
            )
        clean.append(record)
    return clean


class SolidWorksService:
    def __init__(self, adapter: Any | None = None, path_service: InternalPathService | None = None):
        self.adapter = adapter or SolidWorksComAdapter()
        self.path_service = path_service
        self.documents: dict[str, tuple[DocumentRef, Any]] = {}
        self.sketches: dict[str, tuple[SketchRef, Any]] = {}
        self.entities: dict[str, tuple[SketchEntityRef, Any]] = {}
        self.features: dict[str, tuple[FeatureRef, Any]] = {}
        self.faces: dict[str, tuple[FaceRef, Any]] = {}
        self.edges: dict[str, tuple[EdgeRef, Any]] = {}
        self._persistent_refs: dict[tuple[str, str, str], str] = {}

    @staticmethod
    def _ok(message: str, value: Any = None, **kwargs: Any) -> OperationResult:
        return OperationResult(True, message, value, **kwargs)

    @staticmethod
    def _fail(message: str) -> OperationResult:
        return OperationResult(False, message, warnings=(message,))

    def status(self) -> OperationResult:
        try:
            result = self.adapter.connect()
            return (
                self._ok(result.message, result) if result.success else self._fail(result.message)
            )
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def new_part(self, session_id: str, name: str, unit: str) -> OperationResult:
        try:
            if not all(
                isinstance(value, str) and 1 <= len(value) <= 128 for value in (session_id, name)
            ):
                raise ValueError("invalid session or model name")
            if any(char in name for char in '\\/:*?"<>|') or unit not in UNITS:
                raise ValueError("invalid model name or unit")
            connected = self.status()
            if not connected.success:
                return connected
            raw = self.adapter.new_part(name, unit)
            ref = DocumentRef(uuid.uuid4().hex, session_id, name, unit)
            self.documents[ref.id] = (ref, raw)
            return self._ok("Created a new part from the installed default template.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def _document(self, document_id: str):
        if document_id not in self.documents:
            raise ValueError("invalid document reference")
        return self.documents[document_id]

    def _sketch(self, sketch_id: str):
        if sketch_id not in self.sketches:
            raise ValueError("invalid sketch reference")
        return self.sketches[sketch_id]

    def _owned(self, registry: dict, reference: str, document_id: str, label: str):
        if reference not in registry or registry[reference][0].document_id != document_id:
            raise ValueError(f"invalid {label} reference")
        return registry[reference]

    def create_sketch(self, document_id: str, plane: str) -> OperationResult:
        try:
            if plane not in PLANES:
                raise ValueError("unsupported sketch plane")
            document_ref, document = self._document(document_id)
            raw = self.adapter.create_sketch(document, plane, document_ref.unit)
            ref = SketchRef(uuid.uuid4().hex, document_id, plane)
            self.sketches[ref.id] = (ref, raw)
            return self._ok(f"Created sketch on {plane}.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def add_sketch_geometry(
        self, sketch_id: str, geometry: list[dict[str, Any]]
    ) -> OperationResult:
        try:
            sketch_ref, raw_sketch = self._sketch(sketch_id)
            if sketch_ref.closed:
                raise ValueError("sketch is closed")
            clean = _geometry(geometry)
            raw_entities = self.adapter.add_sketch_geometry(raw_sketch, clean)
            if len(raw_entities) != len(clean):
                raise RuntimeError("SolidWorks returned incomplete geometry")
            refs = []
            for item, raw in zip(clean, raw_entities, strict=True):
                ref = SketchEntityRef(
                    uuid.uuid4().hex, sketch_ref.document_id, sketch_id, item["type"]
                )
                self.entities[ref.id] = (ref, raw)
                refs.append(ref)
            return self._ok(f"Added {len(refs)} geometry item(s).", refs)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def add_dimensions(self, sketch_id: str, dimensions: list[dict[str, Any]]) -> OperationResult:
        try:
            sketch_ref, raw_sketch = self._sketch(sketch_id)
            if sketch_ref.closed:
                raise ValueError("sketch is closed")
            clean, resolved = [], []
            for item in _items(dimensions, "dimensions"):
                kind = item.get("type")
                allowed = {"type", "value", "entity_refs", "position"}
                if kind not in {"distance", "diameter", "radius"} or set(item) - allowed:
                    raise ValueError("unsupported dimension variant or fields")
                refs = item.get("entity_refs")
                expected = (1, 2) if kind == "distance" else (1, 1)
                if not isinstance(refs, list) or not expected[0] <= len(refs) <= expected[1]:
                    raise ValueError("invalid dimension entity references")
                raw_refs = []
                for ref_id in refs:
                    ref, raw = self._owned(self.entities, ref_id, sketch_ref.document_id, "entity")
                    if ref.sketch_id != sketch_id:
                        raise ValueError("invalid entity reference")
                    raw_refs.append(raw)
                record = {"type": kind, "value": _number(item["value"], "dimension", positive=True)}
                if "position" in item:
                    record["position"] = _point(item["position"], "position")
                clean.append(record)
                resolved.append(raw_refs)
            count = self.adapter.add_dimensions(raw_sketch, clean, resolved)
            return self._ok(f"Added {count} dimension(s).")
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def close_sketch(self, sketch_id: str) -> OperationResult:
        try:
            ref, raw = self._sketch(sketch_id)
            if ref.closed:
                raise ValueError("sketch is already closed")
            self.adapter.close_sketch(raw)
            ref = replace(ref, closed=True)
            self.sketches[sketch_id] = (ref, raw)
            return self._ok("Closed sketch.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def _feature_from_sketch(
        self, document_id: str, sketch_id: str, kind: str, *args: Any
    ) -> OperationResult:
        try:
            _, document = self._document(document_id)
            sketch_ref, raw_sketch = self._sketch(sketch_id)
            if sketch_ref.document_id != document_id or not sketch_ref.closed:
                raise ValueError("feature requires an owned closed sketch")
            raw = getattr(self.adapter, kind)(document, raw_sketch, *args)
            ref = FeatureRef(uuid.uuid4().hex, document_id, kind)
            self.features[ref.id] = (ref, raw)
            return self._ok(f"Created {kind} feature.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def extrude(
        self, document_id: str, sketch_id: str, depth: float, direction: str
    ) -> OperationResult:
        if direction not in DIRECTIONS:
            return self._fail("unsupported extrude direction")
        try:
            depth = _number(depth, "depth", positive=True)
        except Exception as exc:
            return self._fail(_safe_error(exc))
        return self._feature_from_sketch(document_id, sketch_id, "extrude", depth, direction)

    def revolve(self, document_id: str, sketch_id: str, axis: str, angle: float) -> OperationResult:
        try:
            angle = _number(angle, "angle", positive=True)
            sketch_ref, _ = self._sketch(sketch_id)
            entity_ref, raw_axis = self._owned(self.entities, axis, document_id, "entity")
            if entity_ref.sketch_id != sketch_id or sketch_ref.document_id != document_id:
                raise ValueError("revolve axis does not belong to sketch")
        except Exception as exc:
            return self._fail(_safe_error(exc))
        return self._feature_from_sketch(document_id, sketch_id, "revolve", raw_axis, angle)

    def cut_extrude(self, document_id: str, sketch_id: str, depth: float) -> OperationResult:
        try:
            depth = _number(depth, "depth", positive=True)
        except Exception as exc:
            return self._fail(_safe_error(exc))
        return self._feature_from_sketch(document_id, sketch_id, "cut_extrude", depth)

    def _stable_refs(
        self, registry: dict, cls: type, document_id: str, raws: list[Any], kind: str | None = None
    ):
        refs = []
        _, document = self._document(document_id)
        label = cls.__name__
        for raw in raws:
            key = self.adapter.persistent_reference_key(document, raw)
            saved_id = self._persistent_refs.get((document_id, label, key))
            existing = registry[saved_id][0] if saved_id is not None else None
            ref = existing or (
                cls(uuid.uuid4().hex, document_id, kind)
                if kind
                else cls(uuid.uuid4().hex, document_id)
            )
            registry[ref.id] = (ref, raw)
            self._persistent_refs[(document_id, label, key)] = ref.id
            refs.append(ref)
        return refs

    def inspect_model(self, document_id: str) -> OperationResult:
        try:
            _, document = self._document(document_id)
            details = self.adapter.inspect_model(document)
            value = {
                "title": details["title"],
                "features": self._stable_refs(
                    self.features, FeatureRef, document_id, details["features"], "inspected"
                ),
                "faces": self._stable_refs(self.faces, FaceRef, document_id, details["faces"]),
                "edges": self._stable_refs(self.edges, EdgeRef, document_id, details["edges"]),
            }
            return self._ok("Inspected model.", value, verification=("COM topology inspected",))
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def hole(
        self, document_id: str, face_ref: str, specification: dict[str, Any], position: list[float]
    ) -> OperationResult:
        try:
            self._owned(self.faces, face_ref, document_id, "face")
            _point(position, "position")
            if not isinstance(specification, dict):
                raise ValueError("invalid hole specification")
            schemas = {
                "simple": {"type", "diameter", "depth"},
                "counterbore": {
                    "type",
                    "diameter",
                    "depth",
                    "counterbore_diameter",
                    "counterbore_depth",
                },
                "countersink": {
                    "type",
                    "diameter",
                    "depth",
                    "countersink_diameter",
                    "angle",
                },
            }
            hole_type = specification.get("type")
            if hole_type not in schemas or set(specification) != schemas[hole_type]:
                raise ValueError("invalid hole specification")
            for key, value in specification.items():
                if key != "type":
                    _number(value, key, positive=True)
            raise NotImplementedError("hole feature is not safely mapped")
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def fillet(self, document_id: str, edge_refs: list[str], radius: float) -> OperationResult:
        try:
            _number(radius, "radius", positive=True)
        except Exception as exc:
            return self._fail(_safe_error(exc))
        return self._unsupported_many(document_id, self.edges, edge_refs, "edge", "fillet")

    def chamfer(
        self, document_id: str, edge_refs: list[str], specification: dict[str, Any]
    ) -> OperationResult:
        try:
            if (
                not isinstance(specification, dict)
                or specification.get("type") != "distance_angle"
                or set(specification) != {"type", "distance", "angle"}
            ):
                raise ValueError("invalid chamfer specification")
            _number(specification["distance"], "distance", positive=True)
            _number(specification["angle"], "angle", positive=True)
        except Exception as exc:
            return self._fail(_safe_error(exc))
        return self._unsupported_many(document_id, self.edges, edge_refs, "edge", "chamfer")

    def mirror_feature(
        self, document_id: str, feature_refs: list[str], plane: str
    ) -> OperationResult:
        if plane not in PLANES:
            return self._fail("invalid mirror plane")
        return self._unsupported_many(document_id, self.features, feature_refs, "feature", "mirror")

    def pattern_feature(
        self, document_id: str, feature_ref: str, pattern: dict[str, Any]
    ) -> OperationResult:
        try:
            if not isinstance(pattern, dict):
                raise ValueError("invalid pattern specification")
            pattern_type = pattern.get("type")
            schemas = {
                "linear": {"type", "direction", "spacing", "count"},
                "circular": {"type", "angle", "count"},
            }
            if pattern_type not in schemas or set(pattern) != schemas[pattern_type]:
                raise ValueError("invalid pattern specification")
            if pattern_type == "linear":
                if pattern["direction"] not in {"x", "y"}:
                    raise ValueError("invalid pattern direction")
                _number(pattern["spacing"], "spacing", positive=True)
            else:
                _number(pattern["angle"], "angle", positive=True)
            count = pattern["count"]
            if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 100:
                raise ValueError("invalid pattern count")
        except Exception as exc:
            return self._fail(_safe_error(exc))
        return self._unsupported_many(
            document_id, self.features, [feature_ref], "feature", "pattern"
        )

    def _unsupported_many(
        self, document_id: str, registry: dict, refs: Any, label: str, operation: str
    ) -> OperationResult:
        try:
            if not isinstance(refs, list) or not 1 <= len(refs) <= MAX_ITEMS:
                raise ValueError(f"invalid {label} references")
            for ref in refs:
                self._owned(registry, ref, document_id, label)
            raise NotImplementedError(f"{operation} feature is not safely mapped")
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def _write(
        self,
        document_id: str,
        kind: str,
        options: dict[str, Any] | None = None,
        view: str | None = None,
    ) -> OperationResult:
        try:
            document_ref, document = self._document(document_id)
            if self.path_service is None:
                raise RuntimeError("internal path service is unavailable")
            path = self.path_service.path_for(document_ref, kind)
            if not isinstance(path, str) or not Path(path).is_absolute():
                raise RuntimeError("internal path must be absolute")
            if not self.path_service.validate_output_path(path):
                raise RuntimeError("output path is outside the shared data boundary")
            if kind == "preview":
                self.adapter.capture_preview(document, path, view)
            else:
                self.adapter.save_as(document, path, options)
            if not Path(path).is_file():
                raise RuntimeError("generated file does not exist")
            if not self.path_service.confirm_file(path):
                raise RuntimeError("artifact registry did not confirm generated file")
            return self._ok(
                f"Generated {kind} file.",
                generated_files=(path,),
                verification=("file exists within data boundary and is confirmed",),
            )
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def save_model(self, document_id: str) -> OperationResult:
        return self._write(document_id, "native")

    def export_step(self, document_id: str) -> OperationResult:
        return self._write(document_id, "step")

    def export_stl(self, document_id: str, mesh_options: dict[str, Any]) -> OperationResult:
        if not isinstance(mesh_options, dict) or set(mesh_options) != {"quality"}:
            return self._fail("invalid STL mesh options")
        return self._write(document_id, "stl", options=mesh_options)

    def capture_preview(self, document_id: str, view: str) -> OperationResult:
        if view not in VIEWS:
            return self._fail("unsupported preview view")
        return self._write(document_id, "preview", view=view)


service = SolidWorksService(path_service=path_bridge_from_environment())


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    try:
        yield {}
    finally:
        close_owned = os.environ.get("SOLIDWORKS_CLOSE_STARTED_INSTANCE", "").lower() in {
            "1",
            "true",
            "yes",
        }
        for _, document in list(service.documents.values()):
            try:
                service.adapter.close_document(document)
            except Exception:
                pass
        service.documents.clear()
        service.sketches.clear()
        service.entities.clear()
        service.features.clear()
        service.faces.clear()
        service.edges.clear()
        service._persistent_refs.clear()
        service.adapter.disconnect(close_started_instance=close_owned)


mcp = FastMCP("solidworks-feature-tools", lifespan=server_lifespan)


def _tool(method, *args):
    return render_result(method(*args))


@mcp.tool()
def solidworks_status() -> str:
    return _tool(service.status)


@mcp.tool()
def solidworks_new_part(session_id: str, name: str, unit: str) -> str:
    """Create a part whose DocumentRef.unit defines all later numeric length inputs."""
    return _tool(service.new_part, session_id, name, unit)


@mcp.tool()
def solidworks_create_sketch(document_id: str, plane: str) -> str:
    return _tool(service.create_sketch, document_id, plane)


@mcp.tool()
def solidworks_add_sketch_geometry(sketch_id: str, geometry: list[dict[str, Any]]) -> str:
    """Add coordinates/radii in DocumentRef.unit; the adapter converts them to SI metres."""
    return _tool(service.add_sketch_geometry, sketch_id, geometry)


@mcp.tool()
def solidworks_add_dimensions(sketch_id: str, dimensions: list[dict[str, Any]]) -> str:
    """Add values/positions in DocumentRef.unit; the adapter converts them to SI metres."""
    return _tool(service.add_dimensions, sketch_id, dimensions)


@mcp.tool()
def solidworks_close_sketch(sketch_id: str) -> str:
    return _tool(service.close_sketch, sketch_id)


@mcp.tool()
def solidworks_extrude(document_id: str, sketch_id: str, depth: float, direction: str) -> str:
    """Extrude depth is in DocumentRef.unit and is converted to SI metres before COM."""
    return _tool(service.extrude, document_id, sketch_id, depth, direction)


@mcp.tool()
def solidworks_revolve(document_id: str, sketch_id: str, axis: str, angle: float) -> str:
    """Revolve angle is degrees and is converted to COM radians by the adapter."""
    return _tool(service.revolve, document_id, sketch_id, axis, angle)


@mcp.tool()
def solidworks_cut_extrude(document_id: str, sketch_id: str, depth: float) -> str:
    """Cut depth is in DocumentRef.unit and is converted to SI metres before COM."""
    return _tool(service.cut_extrude, document_id, sketch_id, depth)


@mcp.tool()
def solidworks_hole(
    document_id: str, face_ref: str, specification: dict[str, Any], position: list[float]
) -> str:
    """Hole positions and sizes use DocumentRef.unit; angles are degrees."""
    return _tool(service.hole, document_id, face_ref, specification, position)


@mcp.tool()
def solidworks_fillet(document_id: str, edge_refs: list[str], radius: float) -> str:
    """Fillet radius uses DocumentRef.unit."""
    return _tool(service.fillet, document_id, edge_refs, radius)


@mcp.tool()
def solidworks_chamfer(
    document_id: str, edge_refs: list[str], specification: dict[str, Any]
) -> str:
    """Chamfer distance uses DocumentRef.unit and angle uses degrees."""
    return _tool(service.chamfer, document_id, edge_refs, specification)


@mcp.tool()
def solidworks_mirror_feature(document_id: str, feature_refs: list[str], plane: str) -> str:
    return _tool(service.mirror_feature, document_id, feature_refs, plane)


@mcp.tool()
def solidworks_pattern_feature(document_id: str, feature_ref: str, pattern: dict[str, Any]) -> str:
    """Pattern spacing uses DocumentRef.unit and circular angle uses degrees."""
    return _tool(service.pattern_feature, document_id, feature_ref, pattern)


@mcp.tool()
def solidworks_inspect_model(document_id: str) -> str:
    return _tool(service.inspect_model, document_id)


@mcp.tool()
def solidworks_save_model(document_id: str) -> str:
    return _tool(service.save_model, document_id)


@mcp.tool()
def solidworks_export_step(document_id: str) -> str:
    return _tool(service.export_step, document_id)


@mcp.tool()
def solidworks_export_stl(document_id: str, mesh_options: dict[str, Any]) -> str:
    return _tool(service.export_stl, document_id, mesh_options)


@mcp.tool()
def solidworks_capture_preview(document_id: str, view: str) -> str:
    return _tool(service.capture_preview, document_id, view)


if __name__ == "__main__":
    mcp.run(transport="stdio")
