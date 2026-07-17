"""Narrow, mockable SolidWorks 2023 COM dispatch adapter."""

from __future__ import annotations

import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SketchContext:
    document: Any
    sketch: Any


class SolidWorksComAdapter:
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
            self._app = dispatch.get_active_object("SldWorks.Application")
            self._owned = False
        except Exception:
            self._app = dispatch.dispatch("SldWorks.Application")
            self._app.Visible = True
            self._owned = True
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

    def new_part(self, name: str, unit: str) -> Any:
        app = self._require_app()
        template = app.GetUserPreferenceStringValue(1)
        if not template:
            raise RuntimeError("SolidWorks default part template is unavailable")
        document = app.NewDocument(template, 0, 0.0, 0.0)
        if document is None:
            raise RuntimeError("SolidWorks failed to create a part document")
        if hasattr(document, "SetTitle2"):
            document.SetTitle2(name)
        unit_codes = {"mm": 0, "cm": 1, "m": 2, "inch": 3}
        if unit not in unit_codes:
            raise ValueError("unsupported unit")
        if hasattr(document, "SetUserPreferenceIntegerValue"):
            document.SetUserPreferenceIntegerValue(27, unit_codes[unit])
        return document

    def create_sketch(self, document: Any, plane: str) -> SketchContext:
        if not document.Extension.SelectByID2(plane, "PLANE", 0, 0, 0, False, 0, None, 0):
            raise RuntimeError(f"SolidWorks could not select plane: {plane}")
        document.SketchManager.InsertSketch(True)
        sketch = document.GetActiveSketch2()
        if sketch is None:
            raise RuntimeError("SolidWorks failed to create sketch")
        return SketchContext(document, sketch)

    def add_sketch_geometry(
        self, context: SketchContext, geometry: list[dict[str, Any]]
    ) -> list[Any]:
        manager = context.document.SketchManager
        created = []
        for item in geometry:
            if item["type"] == "line":
                raw = manager.CreateLine(*item["start"], 0.0, *item["end"], 0.0)
            elif item["type"] == "circle":
                raw = manager.CreateCircleByRadius(*item["center"], 0.0, item["radius"])
            else:
                raw = manager.CreateCenterRectangle(*item["center"], 0.0, *item["corner"], 0.0)
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
            dimension = document.AddDimension2(*item.get("position", [0.0, 0.0]), 0.0)
            if dimension is None:
                raise RuntimeError(f"SolidWorks failed to add {item['type']} dimension")
            dimension.GetDimension2(0).SystemValue = item["value"]
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
            depth,
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

    def revolve(self, document: Any, context: SketchContext, axis: str, angle: float) -> Any:
        self._select_sketch(context)
        if not document.Extension.SelectByID2(axis, "SKETCHSEGMENT", 0, 0, 0, True, 4, None, 0):
            raise RuntimeError("SolidWorks could not select revolve axis")
        feature = document.FeatureManager.FeatureRevolve2(
            True,
            True,
            False,
            False,
            False,
            False,
            angle,
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

    def cut_extrude(self, document: Any, context: SketchContext, depth: float) -> Any:
        self._select_sketch(context)
        feature = document.FeatureManager.FeatureCut3(
            True,
            False,
            False,
            0,
            0,
            depth,
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
            "title": str(document.GetTitle()),
            "features": features,
            "faces": faces,
            "edges": edges,
        }

    def save_as(self, document: Any, path: str, options: dict[str, Any] | None = None) -> None:
        if options and options.get("quality") not in {"coarse", "medium", "fine"}:
            raise ValueError("unsupported STL mesh quality")
        if not document.Extension.SaveAs(path, 0, 1, None, 0, 0):
            raise RuntimeError("SolidWorks SaveAs failed")

    def capture_preview(self, document: Any, path: str, view: str) -> None:
        views = {"front": 1, "top": 5, "right": 3, "isometric": 7}
        if view not in views:
            raise ValueError("unsupported preview view")
        document.ShowNamedView2("", views[view])
        document.ViewZoomtofit2()
        if not document.SaveBMP(path, 0, 0):
            raise RuntimeError("SolidWorks preview capture failed")
