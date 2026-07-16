"""Constrained feature-level MCP server for SolidWorks."""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, is_dataclass, replace
from typing import Any, Protocol

from mcp.server.fastmcp import FastMCP

from .com_adapter import SolidWorksComAdapter
from .types import DocumentRef, FeatureRef, OperationResult, SketchRef

SUPPORTED_PLANES = {"Front Plane", "Top Plane", "Right Plane"}
MAX_ITEMS = 100
MAX_ABS_COORDINATE = 1000.0
MAX_DIMENSION = 1000.0


class InternalPathService(Protocol):
    def path_for(self, document_id: str, kind: str) -> str: ...


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, NotImplementedError):
        return f"Unsupported operation: {exc}"
    return str(exc) or type(exc).__name__


def render_result(result: OperationResult) -> str:
    files = "\n".join(f"- {path}" for path in result.generated_files) or "None"
    verification = "\n".join(f"- {item}" for item in result.verification) or "Not verified."
    warnings = "\n".join(f"- {item}" for item in result.warnings) or "None"
    value = ""
    if result.value is not None:
        public_value = asdict(result.value) if is_dataclass(result.value) else result.value
        value = f"\nResult: `{json.dumps(public_value, ensure_ascii=False, sort_keys=True)}`"
    return (
        f"## Status\n{'Success' if result.success else 'Failed'}\n"
        f"## Execution Summary\n{result.message}{value}\n"
        f"## Generated Files\n{files}\n"
        f"## Verification\n{verification}\n"
        f"## Warnings\n{warnings}"
    )


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if positive and number <= 0:
        raise ValueError(f"{name} must be positive")
    if abs(number) > MAX_DIMENSION:
        raise ValueError(f"{name} is outside the supported bound")
    return number


def _point(value: Any, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a two-number list")
    point = [_number(item, name) for item in value]
    if any(abs(item) > MAX_ABS_COORDINATE for item in point):
        raise ValueError(f"{name} is outside the supported bound")
    return point


def _bounded_items(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_ITEMS:
        raise ValueError(f"{name} must contain 1 to {MAX_ITEMS} items")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{name} items must be dictionaries")
    return value


def _geometry_payload(value: Any) -> list[dict[str, Any]]:
    result = []
    schemas = {
        "line": {"type", "start", "end"},
        "circle": {"type", "center", "radius"},
        "center_rectangle": {"type", "center", "corner"},
    }
    for item in _bounded_items(value, "geometry"):
        kind = item.get("type")
        if kind not in schemas or set(item) != schemas[kind]:
            raise ValueError("unsupported geometry variant or fields")
        clean = {"type": kind}
        if kind == "line":
            clean.update(start=_point(item["start"], "start"), end=_point(item["end"], "end"))
        elif kind == "circle":
            clean.update(
                center=_point(item["center"], "center"),
                radius=_number(item["radius"], "radius", positive=True),
            )
        else:
            clean.update(
                center=_point(item["center"], "center"),
                corner=_point(item["corner"], "corner"),
            )
        result.append(clean)
    return result


def _dimension_payload(value: Any) -> list[dict[str, Any]]:
    result = []
    for item in _bounded_items(value, "dimensions"):
        if item.get("type") not in {"distance", "diameter", "radius"}:
            raise ValueError("unsupported dimension variant")
        if not {"type", "value"} <= set(item) <= {"type", "value", "position"}:
            raise ValueError("unsupported dimension fields")
        clean = {
            "type": item["type"],
            "value": _number(item["value"], "dimension value", positive=True),
        }
        if "position" in item:
            clean["position"] = _point(item["position"], "position")
        result.append(clean)
    return result


class SolidWorksService:
    def __init__(
        self,
        adapter: Any | None = None,
        path_service: InternalPathService | None = None,
    ):
        self.adapter = adapter or SolidWorksComAdapter()
        self.path_service = path_service
        self.documents: dict[str, tuple[DocumentRef, Any]] = {}
        self.sketches: dict[str, tuple[SketchRef, Any]] = {}
        self.features: dict[str, tuple[FeatureRef, Any]] = {}

    @staticmethod
    def _ok(message: str, value: Any = None, **kwargs: Any) -> OperationResult:
        return OperationResult(True, message, value, **kwargs)

    @staticmethod
    def _fail(message: str) -> OperationResult:
        return OperationResult(False, message, warnings=(message,))

    def status(self) -> OperationResult:
        try:
            connection = self.adapter.connect()
            if not connection.success:
                return self._fail(connection.message)
            return self._ok(connection.message, connection, verification=("COM connection ready",))
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def new_part(self) -> OperationResult:
        status = self.status()
        if not status.success:
            return status
        try:
            raw = self.adapter.new_part()
            ref = DocumentRef(uuid.uuid4().hex)
            self.documents[ref.id] = (ref, raw)
            return self._ok("Created a new part from the installed default template.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def _document(self, document_id: str) -> tuple[DocumentRef, Any]:
        if not isinstance(document_id, str) or document_id not in self.documents:
            raise ValueError("invalid document reference")
        return self.documents[document_id]

    def _sketch(self, document_id: str, sketch_id: str) -> tuple[SketchRef, Any]:
        self._document(document_id)
        if not isinstance(sketch_id, str) or sketch_id not in self.sketches:
            raise ValueError("invalid sketch reference")
        ref, raw = self.sketches[sketch_id]
        if ref.document_id != document_id:
            raise ValueError("sketch does not belong to document")
        return ref, raw

    def _feature(self, document_id: str, feature_id: str) -> tuple[FeatureRef, Any]:
        self._document(document_id)
        if not isinstance(feature_id, str) or feature_id not in self.features:
            raise ValueError("invalid feature reference")
        ref, raw = self.features[feature_id]
        if ref.document_id != document_id:
            raise ValueError("feature does not belong to document")
        return ref, raw

    def create_sketch(self, document_id: str, plane: str) -> OperationResult:
        try:
            if plane not in SUPPORTED_PLANES:
                raise ValueError("unsupported sketch plane")
            _, document = self._document(document_id)
            raw = self.adapter.create_sketch(document, plane)
            ref = SketchRef(uuid.uuid4().hex, document_id, plane)
            self.sketches[ref.id] = (ref, raw)
            return self._ok(f"Created sketch on {plane}.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def add_sketch_geometry(
        self, document_id: str, sketch_id: str, geometry: list[dict[str, Any]]
    ) -> OperationResult:
        try:
            ref, sketch = self._sketch(document_id, sketch_id)
            if ref.closed:
                raise ValueError("sketch is closed")
            clean = _geometry_payload(geometry)
            count = self.adapter.add_sketch_geometry(sketch, clean)
            return self._ok(f"Added {count} sketch geometry item(s).")
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def add_dimensions(
        self, document_id: str, sketch_id: str, dimensions: list[dict[str, Any]]
    ) -> OperationResult:
        try:
            ref, sketch = self._sketch(document_id, sketch_id)
            if ref.closed:
                raise ValueError("sketch is closed")
            clean = _dimension_payload(dimensions)
            count = self.adapter.add_dimensions(sketch, clean)
            return self._ok(f"Added {count} dimension(s).")
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def close_sketch(self, document_id: str, sketch_id: str) -> OperationResult:
        try:
            ref, sketch = self._sketch(document_id, sketch_id)
            if ref.closed:
                raise ValueError("sketch is already closed")
            self.adapter.close_sketch(sketch)
            ref = replace(ref, closed=True)
            self.sketches[sketch_id] = (ref, sketch)
            return self._ok("Closed sketch.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def _sketch_feature(
        self, document_id: str, sketch_id: str, kind: str, parameters: dict[str, Any]
    ) -> OperationResult:
        try:
            _, document = self._document(document_id)
            sketch_ref, sketch = self._sketch(document_id, sketch_id)
            if not sketch_ref.closed:
                raise ValueError("feature requires a closed sketch")
            if not isinstance(parameters, dict):
                raise ValueError("parameters must be a dictionary")
            if kind in {"extrude", "cut_extrude"}:
                if set(parameters) != {"depth"}:
                    raise ValueError(f"{kind} supports only depth")
                clean = {"depth": _number(parameters["depth"], "depth", positive=True)}
            elif kind == "revolve":
                if set(parameters) != {"angle"}:
                    raise ValueError("revolve supports only angle")
                clean = {"angle": _number(parameters["angle"], "angle", positive=True)}
            else:
                clean = parameters
            raw = self.adapter.create_feature(document, sketch, kind, clean)
            ref = FeatureRef(uuid.uuid4().hex, document_id, kind)
            self.features[ref.id] = (ref, raw)
            return self._ok(f"Created {kind} feature.", ref)
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def extrude(
        self, document_id: str, sketch_id: str, parameters: dict[str, Any]
    ) -> OperationResult:
        return self._sketch_feature(document_id, sketch_id, "extrude", parameters)

    def revolve(
        self, document_id: str, sketch_id: str, parameters: dict[str, Any]
    ) -> OperationResult:
        return self._sketch_feature(document_id, sketch_id, "revolve", parameters)

    def cut_extrude(
        self, document_id: str, sketch_id: str, parameters: dict[str, Any]
    ) -> OperationResult:
        return self._sketch_feature(document_id, sketch_id, "cut_extrude", parameters)

    def _unsupported_sketch_feature(
        self, document_id: str, sketch_id: str, kind: str
    ) -> OperationResult:
        try:
            sketch_ref, _ = self._sketch(document_id, sketch_id)
            if not sketch_ref.closed:
                raise ValueError("feature requires a closed sketch")
            raise NotImplementedError(f"{kind} feature is not safely mapped")
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def hole(self, document_id: str, sketch_id: str, parameters: dict[str, Any]) -> OperationResult:
        return self._unsupported_sketch_feature(document_id, sketch_id, "hole")

    def _unsupported_ref_feature(
        self, document_id: str, feature_id: str, kind: str
    ) -> OperationResult:
        try:
            self._feature(document_id, feature_id)
            raise NotImplementedError(f"{kind} feature is not safely mapped")
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def fillet(
        self, document_id: str, feature_id: str, parameters: dict[str, Any]
    ) -> OperationResult:
        return self._unsupported_ref_feature(document_id, feature_id, "fillet")

    def chamfer(
        self, document_id: str, feature_id: str, parameters: dict[str, Any]
    ) -> OperationResult:
        return self._unsupported_ref_feature(document_id, feature_id, "chamfer")

    def mirror_feature(
        self, document_id: str, feature_id: str, parameters: dict[str, Any]
    ) -> OperationResult:
        return self._unsupported_ref_feature(document_id, feature_id, "mirror")

    def pattern_feature(
        self, document_id: str, feature_id: str, parameters: dict[str, Any]
    ) -> OperationResult:
        return self._unsupported_ref_feature(document_id, feature_id, "pattern")

    def inspect_model(self, document_id: str) -> OperationResult:
        try:
            _, document = self._document(document_id)
            details = self.adapter.inspect_model(document)
            return self._ok("Inspected model.", details, verification=(str(details),))
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def _write(self, document_id: str, kind: str) -> OperationResult:
        try:
            _, document = self._document(document_id)
            if self.path_service is None:
                raise RuntimeError("internal path service is unavailable")
            path = self.path_service.path_for(document_id, kind)
            if not isinstance(path, str) or not path:
                raise RuntimeError("internal path service returned no path")
            if kind == "preview":
                self.adapter.capture_preview(document, path)
            else:
                self.adapter.save_as(document, path)
            return self._ok(
                f"Generated {kind} file.",
                generated_files=(path,),
                verification=("SolidWorks reported successful file generation",),
            )
        except Exception as exc:
            return self._fail(_safe_error(exc))

    def save_model(self, document_id: str) -> OperationResult:
        return self._write(document_id, "native")

    def export_step(self, document_id: str) -> OperationResult:
        return self._write(document_id, "step")

    def export_stl(self, document_id: str) -> OperationResult:
        return self._write(document_id, "stl")

    def capture_preview(self, document_id: str) -> OperationResult:
        return self._write(document_id, "preview")


service = SolidWorksService()
mcp = FastMCP("solidworks-feature-tools")


def _tool(method, *args):
    return render_result(method(*args))


@mcp.tool()
def solidworks_status() -> str:
    return _tool(service.status)


@mcp.tool()
def solidworks_new_part() -> str:
    return _tool(service.new_part)


@mcp.tool()
def solidworks_create_sketch(document_id: str, plane: str) -> str:
    return _tool(service.create_sketch, document_id, plane)


@mcp.tool()
def solidworks_add_sketch_geometry(
    document_id: str, sketch_id: str, geometry: list[dict[str, Any]]
) -> str:
    return _tool(service.add_sketch_geometry, document_id, sketch_id, geometry)


@mcp.tool()
def solidworks_add_dimensions(
    document_id: str, sketch_id: str, dimensions: list[dict[str, Any]]
) -> str:
    return _tool(service.add_dimensions, document_id, sketch_id, dimensions)


@mcp.tool()
def solidworks_close_sketch(document_id: str, sketch_id: str) -> str:
    return _tool(service.close_sketch, document_id, sketch_id)


@mcp.tool()
def solidworks_extrude(document_id: str, sketch_id: str, parameters: dict[str, Any]) -> str:
    return _tool(service.extrude, document_id, sketch_id, parameters)


@mcp.tool()
def solidworks_revolve(document_id: str, sketch_id: str, parameters: dict[str, Any]) -> str:
    return _tool(service.revolve, document_id, sketch_id, parameters)


@mcp.tool()
def solidworks_cut_extrude(document_id: str, sketch_id: str, parameters: dict[str, Any]) -> str:
    return _tool(service.cut_extrude, document_id, sketch_id, parameters)


@mcp.tool()
def solidworks_hole(document_id: str, sketch_id: str, parameters: dict[str, Any]) -> str:
    return _tool(service.hole, document_id, sketch_id, parameters)


@mcp.tool()
def solidworks_fillet(document_id: str, feature_id: str, parameters: dict[str, Any]) -> str:
    return _tool(service.fillet, document_id, feature_id, parameters)


@mcp.tool()
def solidworks_chamfer(document_id: str, feature_id: str, parameters: dict[str, Any]) -> str:
    return _tool(service.chamfer, document_id, feature_id, parameters)


@mcp.tool()
def solidworks_mirror_feature(document_id: str, feature_id: str, parameters: dict[str, Any]) -> str:
    return _tool(service.mirror_feature, document_id, feature_id, parameters)


@mcp.tool()
def solidworks_pattern_feature(
    document_id: str, feature_id: str, parameters: dict[str, Any]
) -> str:
    return _tool(service.pattern_feature, document_id, feature_id, parameters)


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
def solidworks_export_stl(document_id: str) -> str:
    return _tool(service.export_stl, document_id)


@mcp.tool()
def solidworks_capture_preview(document_id: str) -> str:
    return _tool(service.capture_preview, document_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
