"""Narrow, mockable SolidWorks 2023 COM dispatch adapter."""

from __future__ import annotations

import math
import os
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from .types import ConnectionResult


class DispatchApi(Protocol):
    def get_active_object(self, prog_id: str) -> Any: ...
    def dispatch(self, prog_id: str) -> Any: ...


class _PyWin32Dispatch:
    def __init__(self, client: Any):
        self._client = client

    def get_active_object(self, prog_id: str) -> Any:
        return self._client.GetActiveObject(prog_id)

    def dispatch(self, prog_id: str) -> Any:
        return self._client.Dispatch(prog_id)


def runtime_dispatch_factory() -> DispatchApi:
    import win32com.client  # type: ignore[import-not-found]

    return _PyWin32Dispatch(win32com.client)


def _empty_com_dispatch() -> Any:
    """Return the typed null dispatch pointer required by SolidWorks COM."""
    import pythoncom  # type: ignore[import-not-found]

    return pythoncom.Nothing


@lru_cache(maxsize=1)
def _model_document_class() -> Any:
    """Load the generated SolidWorks 2023 IModelDoc2 dispatch wrapper."""
    import win32com.client  # type: ignore[import-not-found]

    generated = win32com.client.gencache.EnsureModule(
        "{83A33D31-27C5-11CE-BFD4-00400513BB57}",
        0,
        31,
        0,
    )
    return generated.IModelDoc2


def _typed_model_document(document: Any) -> Any:
    """Wrap an untyped pywin32 document with its generated IModelDoc2 class."""
    ole_object = getattr(document, "_oleobj_", None)
    if ole_object is None:
        return document
    return _model_document_class()(ole_object)


@dataclass(frozen=True)
class SketchContext:
    document: Any
    sketch: Any
    unit: str = "m"


class SolidWorksComAdapter:
    PROG_ID = "SldWorks.Application.31"
    VERSION_MAJOR = 31
    _UNIT_TO_METERS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "inch": 0.0254}
    _PLANE_ALIASES = {
        "Front Plane": ("Front Plane", "前视基准面"),
        "Top Plane": ("Top Plane", "上视基准面"),
        "Right Plane": ("Right Plane", "右视基准面"),
    }

    def __init__(self, dispatch: DispatchApi | None = None, sleep=time.sleep):
        self._dispatch = dispatch
        self._sleep = sleep
        self._app: Any = None
        self._owned = False

    def connect(self, readiness_timeout: float = 10.0) -> ConnectionResult:
        if self._app is not None:
            initialized = bool(getattr(self._app, "IsInitialized", True))
            return ConnectionResult(initialized, self._owned, "already connected")
        dispatch = self._dispatch or runtime_dispatch_factory()
        try:
            self._app = dispatch.get_active_object(self.PROG_ID)
            self._owned = False
        except Exception:
            self._app = dispatch.dispatch(self.PROG_ID)
            self._app.Visible = True
            self._owned = True
        revision = self._com_value(self._app, "RevisionNumber", "")
        try:
            major = int(str(revision).split(".", 1)[0])
        except (TypeError, ValueError):
            major = -1
        if major != self.VERSION_MAJOR:
            if self._owned:
                try:
                    self._app.ExitApp()
                except Exception:
                    return ConnectionResult(
                        False,
                        True,
                        "SolidWorks 2023 is required and the incompatible "
                        "started instance could not be closed",
                    )
            self._app = None
            self._owned = False
            return ConnectionResult(False, False, "SolidWorks 2023 (major 31) is required")
        deadline = time.monotonic() + max(0.0, readiness_timeout)
        while True:
            try:
                if bool(getattr(self._app, "IsInitialized", True)):
                    return ConnectionResult(
                        True, self._owned, "started" if self._owned else "attached"
                    )
            except Exception:
                pass
            if time.monotonic() >= deadline:
                return ConnectionResult(False, self._owned, "SolidWorks readiness timed out")
            self._sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    def disconnect(self, close_started_instance: bool = False) -> None:
        app, owned = self._app, self._owned
        self._app = None
        self._owned = False
        if app is not None and owned and close_started_instance:
            app.ExitApp()

    def _require_app(self) -> Any:
        if self._app is None:
            raise RuntimeError("SolidWorks is not connected")
        return self._app

    @staticmethod
    def _com_value(obj: Any, name: str, default: Any = None) -> Any:
        value = getattr(obj, name, default)
        return value() if callable(value) else value

    def new_part(self, name: str, unit: str) -> Any:
        app = self._require_app()
        template = app.GetUserPreferenceStringValue(1)
        if not template:
            candidates = []
            configured = os.environ.get("SOLIDWORKS_PART_TEMPLATE")
            if configured:
                candidates.append(Path(configured))
            program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
            candidates.append(
                program_data
                / "SOLIDWORKS"
                / "SOLIDWORKS 2023"
                / "templates"
                / "gb_part.prtdot"
            )
            template_path = next(
                (
                    candidate.resolve()
                    for candidate in candidates
                    if candidate.is_absolute()
                    and candidate.suffix.casefold() == ".prtdot"
                    and candidate.is_file()
                ),
                None,
            )
            if template_path is None:
                raise RuntimeError("SolidWorks default part template is unavailable")
            template = str(template_path)
        document = app.NewDocument(template, 0, 0.0, 0.0)
        if document is None:
            raise RuntimeError("SolidWorks failed to create a part document")
        document = _typed_model_document(document)
        if hasattr(document, "SetTitle2"):
            document.SetTitle2(name)
        unit_codes = {"mm": 0, "cm": 1, "m": 2, "inch": 3}
        if unit not in unit_codes:
            raise ValueError("unsupported unit")
        if hasattr(document, "SetUserPreferenceIntegerValue"):
            document.SetUserPreferenceIntegerValue(27, unit_codes[unit])
        return document

    def create_sketch(self, document: Any, plane: str, unit: str = "m") -> SketchContext:
        aliases = self._PLANE_ALIASES.get(plane, (plane,))
        selected = False
        last_error = None
        for candidate in aliases:
            for callout_factory in (lambda: None, _empty_com_dispatch):
                try:
                    selected = bool(
                        document.Extension.SelectByID2(
                            candidate,
                            "PLANE",
                            0,
                            0,
                            0,
                            False,
                            0,
                            callout_factory(),
                            0,
                        )
                    )
                except Exception as exc:
                    last_error = exc
                    continue
                if selected:
                    break
            if selected:
                break
        if not selected:
            detail = f": {last_error}" if last_error is not None else ""
            raise RuntimeError(f"SolidWorks could not select plane: {plane}{detail}")
        document.SketchManager.InsertSketch(True)
        sketch = document.GetActiveSketch2()
        if sketch is None:
            raise RuntimeError("SolidWorks failed to create sketch")
        self._scale(unit)
        return SketchContext(document, sketch, unit)

    def create_sketch_on_face(self, document: Any, face: Any, unit: str = "m") -> SketchContext:
        document.ClearSelection2(True)
        if not face.Select4(False, None):
            raise RuntimeError("SolidWorks could not select face")
        document.SketchManager.InsertSketch(True)
        sketch = document.GetActiveSketch2()
        if sketch is None:
            raise RuntimeError("SolidWorks failed to create sketch")
        self._scale(unit)
        return SketchContext(document, sketch, unit)

    @classmethod
    def _scale(cls, unit: str) -> float:
        try:
            return cls._UNIT_TO_METERS[unit]
        except KeyError as exc:
            raise ValueError("unsupported unit") from exc

    @classmethod
    def _length(cls, value: float, unit: str) -> float:
        return float(value) * cls._scale(unit)

    @classmethod
    def _point_si(cls, point: list[float], unit: str) -> tuple[float, float]:
        return cls._length(point[0], unit), cls._length(point[1], unit)

    def add_sketch_geometry(
        self, context: SketchContext, geometry: list[dict[str, Any]]
    ) -> list[Any]:
        manager = context.document.SketchManager
        created = []
        for item in geometry:
            if item["type"] == "line":
                raw = manager.CreateLine(
                    *self._point_si(item["start"], context.unit),
                    0.0,
                    *self._point_si(item["end"], context.unit),
                    0.0,
                )
            elif item["type"] == "circle":
                raw = manager.CreateCircleByRadius(
                    *self._point_si(item["center"], context.unit),
                    0.0,
                    self._length(item["radius"], context.unit),
                )
            elif item["type"] == "three_point_arc":
                raw = manager.Create3PointArc(
                    *self._point_si(item["start"], context.unit),
                    0.0,
                    *self._point_si(item["mid"], context.unit),
                    0.0,
                    *self._point_si(item["end"], context.unit),
                    0.0,
                )
            else:
                raw = manager.CreateCenterRectangle(
                    *self._point_si(item["center"], context.unit),
                    0.0,
                    *self._point_si(item["corner"], context.unit),
                    0.0,
                )
            if raw is None:
                raise RuntimeError(f"SolidWorks failed to create {item['type']}")
            created.append(raw)
        return created

    def add_dimensions(
        self,
        context: SketchContext,
        dimensions: list[dict[str, Any]],
        entities: list[list[Any]],
    ) -> int:
        document = context.document
        for item, selected in zip(dimensions, entities, strict=True):
            document.ClearSelection2(True)
            for index, entity in enumerate(selected):
                if not entity.Select4(index > 0, None):
                    raise RuntimeError("SolidWorks could not select dimension entity")
            factory = {
                "distance": document.AddDimension2,
                "diameter": document.AddDiameterDimension2,
                "radius": document.AddRadialDimension2,
            }[item["type"]]
            position = self._point_si(item.get("position", [0.0, 0.0]), context.unit)
            dimension = factory(*position, 0.0)
            if dimension is None:
                raise RuntimeError(f"SolidWorks failed to add {item['type']} dimension")
            dimension.GetDimension2(0).SystemValue = self._length(item["value"], context.unit)
        document.ClearSelection2(True)
        return len(dimensions)

    def close_sketch(self, context: SketchContext) -> None:
        context.document.SketchManager.InsertSketch(True)

    @staticmethod
    def _select_sketch(context: SketchContext) -> None:
        context.document.ClearSelection2(True)
        if not context.sketch.Select2(False, 0):
            raise RuntimeError("SolidWorks could not select sketch")

    def extrude(self, document: Any, context: SketchContext, depth: float, direction: str) -> Any:
        self._select_sketch(context)
        reverse = direction == "reverse"
        feature = document.FeatureManager.FeatureExtrusion2(
            True,
            reverse,
            False,
            0,
            0,
            self._length(depth, context.unit),
            0.0,
            False,
            False,
            False,
            False,
            0.0,
            0.0,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            0,
            0.0,
            False,
        )
        if feature is None:
            raise RuntimeError("SolidWorks failed to create extrude feature")
        return feature

    def revolve(self, document: Any, context: SketchContext, axis: Any, angle: float) -> Any:
        self._select_sketch(context)
        if not axis.Select4(True, None):
            raise RuntimeError("SolidWorks could not select revolve axis")
        feature = document.FeatureManager.FeatureRevolve2(
            True,
            True,
            False,
            False,
            False,
            False,
            math.radians(angle),
            0.0,
            False,
            False,
            0.0,
            0.0,
            0,
            0,
            0,
        )
        if feature is None:
            raise RuntimeError("SolidWorks failed to create revolve feature")
        return feature

    def persistent_reference_key(self, document: Any, raw: Any) -> str:
        reference = document.Extension.GetPersistReference3(raw)
        if not reference:
            raise RuntimeError("SolidWorks returned no persistent reference")
        return bytes(reference).hex()

    def cut_extrude(self, document: Any, context: SketchContext, depth: float) -> Any:
        self._select_sketch(context)
        feature = document.FeatureManager.FeatureCut3(
            True,
            False,
            False,
            0,
            0,
            self._length(depth, context.unit),
            0.0,
            False,
            False,
            False,
            False,
            0.0,
            0.0,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            False,
            0,
            0.0,
            False,
        )
        if feature is None:
            raise RuntimeError("SolidWorks failed to create cut extrude feature")
        return feature

    @staticmethod
    def _selection_data(document: Any, mark: int) -> Any:
        manager = getattr(document, "SelectionManager", None)
        if manager is None or not hasattr(manager, "CreateSelectData"):
            return None
        data = manager.CreateSelectData()
        data.Mark = mark
        return data

    def _select_raw(self, document: Any, raw: Any, append: bool, mark: int) -> None:
        if hasattr(raw, "Select4"):
            selected = raw.Select4(append, self._selection_data(document, mark))
        elif hasattr(raw, "Select2"):
            selected = raw.Select2(append, mark)
        else:
            raise RuntimeError("SolidWorks entity does not support selection")
        if not selected:
            raise RuntimeError("SolidWorks could not select owned entity")

    def _select_plane(self, document: Any, plane: str, mark: int) -> None:
        aliases = self._PLANE_ALIASES.get(plane, (plane,))
        for candidate in aliases:
            for callout_factory in (lambda: None, _empty_com_dispatch):
                try:
                    selected = document.Extension.SelectByID2(
                        candidate, "PLANE", 0, 0, 0, False, mark, callout_factory(), 0
                    )
                except Exception:
                    continue
                if selected:
                    return
        raise RuntimeError(f"SolidWorks could not select plane: {plane}")

    def _create_hole_location(
        self, document: Any, face: Any, position: list[float], unit: str
    ) -> None:
        surface = face.GetSurface() if hasattr(face, "GetSurface") else None
        if surface is None or not bool(self._com_value(surface, "IsPlane", False)):
            raise ValueError("hole positions require an owned planar face")
        x, y = self._point_si(position, unit)
        self._select_raw(document, face, False, 0)
        try:
            document.SketchManager.InsertSketch(True)
            point = document.SketchManager.CreatePoint(x, y, 0.0)
            if point is None:
                raise RuntimeError("SolidWorks failed to create hole location point")
        finally:
            document.SketchManager.InsertSketch(True)
        self._select_raw(document, point, False, 0)

    def hole(
        self,
        document: Any,
        face: Any,
        specification: dict[str, Any],
        position: list[float],
        unit: str,
    ) -> Any:
        """Create one blind Hole Wizard hole at an owned face position."""
        document.ClearSelection2(True)
        try:
            self._create_hole_location(document, face, position, unit)
            hole_type = {"counterbore": 0, "countersink": 1, "simple": 2}[specification["type"]]
            values = [-1.0] * 12
            if specification["type"] == "counterbore":
                values[0] = self._length(specification["counterbore_diameter"], unit)
                values[1] = self._length(specification["counterbore_depth"], unit)
            elif specification["type"] == "countersink":
                values[0] = self._length(specification["countersink_diameter"], unit)
                values[1] = math.radians(specification["angle"])
            feature = document.FeatureManager.HoleWizard5(
                hole_type,
                0,
                0,
                "",
                0,
                self._length(specification["diameter"], unit),
                self._length(specification["depth"], unit),
                -1.0,
                *values,
                "",
                False,
                False,
                True,
                False,
                False,
                False,
            )
            if not feature:
                raise RuntimeError("SolidWorks failed to create Hole Wizard feature")
            return feature
        finally:
            document.ClearSelection2(True)

    def fillet(self, document: Any, edges: list[Any], radius: float, unit: str) -> Any:
        document.ClearSelection2(True)
        try:
            for index, edge in enumerate(edges):
                self._select_raw(document, edge, index > 0, 1)
            feature = document.FeatureManager.FeatureFillet3(
                2,
                self._length(radius, unit),
                0.0,
                0.0,
                0,
                0,
                0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
            if not feature:
                raise RuntimeError("SolidWorks failed to create fillet feature")
            return feature
        finally:
            document.ClearSelection2(True)

    def chamfer(
        self, document: Any, edges: list[Any], specification: dict[str, Any], unit: str
    ) -> Any:
        document.ClearSelection2(True)
        try:
            for index, edge in enumerate(edges):
                self._select_raw(document, edge, index > 0, 0)
            feature = document.FeatureManager.InsertFeatureChamfer(
                0,
                1,
                self._length(specification["distance"], unit),
                math.radians(specification["angle"]),
                0.0,
                0.0,
                0.0,
                0.0,
            )
            if not feature:
                raise RuntimeError("SolidWorks failed to create chamfer feature")
            return feature
        finally:
            document.ClearSelection2(True)

    def mirror_feature(self, document: Any, features: list[Any], plane: str) -> Any:
        document.ClearSelection2(True)
        try:
            for index, feature in enumerate(features):
                self._select_raw(document, feature, index > 0, 1)
            self._select_plane(document, plane, 2)
            feature = document.FeatureManager.InsertMirrorFeature2(False, False, False, False, 0)
            if not feature:
                raise RuntimeError("SolidWorks failed to create mirror feature")
            return feature
        finally:
            document.ClearSelection2(True)

    def pattern_feature(self, document: Any, feature: Any, pattern: dict[str, Any], unit: str) -> Any:
        document.ClearSelection2(True)
        try:
            self._select_raw(document, feature, False, 4)
            if pattern["type"] == "linear":
                # Standard planes provide the two supported global pattern directions.
                self._select_plane(document, "Right Plane" if pattern["direction"] == "x" else "Front Plane", 1)
                created = document.FeatureManager.FeatureLinearPattern3(
                    pattern["count"],
                    self._length(pattern["spacing"], unit),
                    1,
                    0.0,
                    False,
                    False,
                    "",
                    "",
                    False,
                    False,
                )
            else:
                self._select_plane(document, "Top Plane", 1)
                created = document.FeatureManager.FeatureCircularPattern3(
                    pattern["count"], math.radians(pattern["angle"]), False, "", False, True
                )
            if not created:
                raise RuntimeError("SolidWorks failed to create pattern feature")
            return created
        finally:
            document.ClearSelection2(True)

    def inspect_model(self, document: Any) -> dict[str, Any]:
        features = []
        feature = document.FirstFeature()
        while feature is not None:
            features.append(feature)
            feature = feature.GetNextFeature()
        bodies = list(document.GetBodies2(0, True) or [])
        faces = [face for body in bodies for face in list(body.GetFaces() or [])]
        edges = [edge for face in faces for edge in list(face.GetEdges() or [])]
        return {
            "title": str(self._com_value(document, "GetTitle", "")),
            "features": features,
            "faces": faces,
            "edges": edges,
        }

    def save_as(self, document: Any, path: str, options: dict[str, Any] | None = None) -> None:
        if options and options.get("quality") not in {"coarse", "medium", "fine"}:
            raise ValueError("unsupported STL mesh quality")
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        result = document.Extension.SaveAs(str(target), 0, 1, None, 0, 0)
        errors = 0
        warnings = 0
        if isinstance(result, (tuple, list)):
            success = bool(result[0]) if result else False
            errors = result[1] if len(result) > 1 else 0
            warnings = result[2] if len(result) > 2 else 0
        else:
            success = bool(result)
        if not success:
            raise RuntimeError(
                f"SolidWorks SaveAs failed: errors={errors}, warnings={warnings}"
            )

    def capture_preview(self, document: Any, path: str, view: str) -> None:
        views = {"front": 1, "top": 5, "right": 3, "isometric": 7}
        if view not in views:
            raise ValueError("unsupported preview view")
        document.ShowNamedView2("", views[view])
        document.ViewZoomtofit2()
        target = Path(path).resolve()
        if target.suffix.casefold() != ".png":
            raise ValueError("preview output must be PNG")
        try:
            data_root = next(
                parent for parent in target.parents if parent.name.casefold() == "data"
            )
        except StopIteration as exc:
            raise ValueError("preview output must be below data") from exc
        temp_dir = (data_root / "tmp").resolve()
        temp_dir.relative_to(data_root)
        temp_dir.mkdir(parents=True, exist_ok=True)
        temporary = temp_dir / f"{target.stem}-{uuid.uuid4().hex}.bmp"
        target.unlink(missing_ok=True)
        try:
            if not document.SaveBMP(str(temporary), 0, 0):
                raise RuntimeError("SolidWorks preview capture failed")
            from PIL import Image

            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(temporary) as bitmap:
                bitmap.save(target, format="PNG")
            if not target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("SolidWorks preview conversion did not produce PNG")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def close_document(self, document: Any) -> None:
        """Close one explicitly owned test document without exiting SolidWorks."""
        if self._app is None:
            return
        title = str(self._com_value(document, "GetTitle", ""))
        self._app.CloseDoc(title)
