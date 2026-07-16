"""Narrow, mockable SolidWorks 2023 COM dispatch adapter."""

from __future__ import annotations

import time
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
    """Import pywin32 only when a real COM connection is requested."""
    import win32com.client  # type: ignore[import-not-found]

    return _PyWin32Dispatch(win32com.client)


class SolidWorksComAdapter:
    """All raw COM calls are kept behind this deliberately small interface."""

    def __init__(self, dispatch: DispatchApi | None = None, sleep=time.sleep):
        self._dispatch = dispatch
        self._sleep = sleep
        self._app: Any = None
        self._owned = False

    def connect(self, readiness_timeout: float = 10.0) -> ConnectionResult:
        if self._app is not None:
            return ConnectionResult(True, self._owned, "already connected")
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
                initialized = getattr(self._app, "IsInitialized", True)
                if initialized:
                    return ConnectionResult(
                        True,
                        self._owned,
                        "started" if self._owned else "attached",
                    )
            except Exception:
                pass
            if time.monotonic() >= deadline:
                self._app = None
                self._owned = False
                return ConnectionResult(False, False, "SolidWorks readiness timed out")
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

    def new_part(self) -> Any:
        app = self._require_app()
        template = app.GetUserPreferenceStringValue(1)
        if not template:
            raise RuntimeError("SolidWorks default part template is unavailable")
        document = app.NewDocument(template, 0, 0.0, 0.0)
        if document is None:
            raise RuntimeError("SolidWorks failed to create a part document")
        return document

    def create_sketch(self, document: Any, plane: str) -> Any:
        if not document.Extension.SelectByID2(plane, "PLANE", 0, 0, 0, False, 0, None, 0):
            raise RuntimeError(f"SolidWorks could not select plane: {plane}")
        document.SketchManager.InsertSketch(True)
        sketch = document.GetActiveSketch2()
        if sketch is None:
            raise RuntimeError("SolidWorks failed to create sketch")
        return sketch

    def add_sketch_geometry(self, sketch: Any, geometry: list[dict[str, Any]]) -> int:
        manager = sketch.GetSketchManager() if hasattr(sketch, "GetSketchManager") else sketch
        for item in geometry:
            kind = item["type"]
            if kind == "line":
                manager.CreateLine(*item["start"], 0.0, *item["end"], 0.0)
            elif kind == "circle":
                manager.CreateCircleByRadius(*item["center"], 0.0, item["radius"])
            elif kind == "center_rectangle":
                manager.CreateCenterRectangle(*item["center"], 0.0, *item["corner"], 0.0)
        return len(geometry)

    def add_dimensions(self, sketch: Any, dimensions: list[dict[str, Any]]) -> int:
        document = sketch.GetModelDoc2() if hasattr(sketch, "GetModelDoc2") else sketch
        for item in dimensions:
            dimension = document.AddDimension2(*item.get("position", [0.0, 0.0]), 0.0)
            if dimension is None:
                raise RuntimeError(f"SolidWorks failed to add {item['type']} dimension")
            dimension.GetDimension2(0).SystemValue = item["value"]
        return len(dimensions)

    def close_sketch(self, sketch: Any) -> None:
        document = sketch.GetModelDoc2() if hasattr(sketch, "GetModelDoc2") else sketch
        document.SketchManager.InsertSketch(True)

    def create_feature(
        self,
        document: Any,
        sketch: Any,
        kind: str,
        parameters: dict[str, Any],
    ) -> Any:
        if kind == "extrude":
            feature = document.FeatureManager.FeatureExtrusion2(
                True,
                False,
                False,
                0,
                0,
                parameters["depth"],
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
        elif kind == "revolve":
            feature = document.FeatureManager.FeatureRevolve2(
                True,
                True,
                False,
                False,
                False,
                False,
                parameters["angle"],
                0.0,
                False,
                False,
                0.0,
                0.0,
                0,
                0,
                0,
            )
        elif kind == "cut_extrude":
            feature = document.FeatureManager.FeatureCut3(
                True,
                False,
                False,
                0,
                0,
                parameters["depth"],
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
        else:
            raise NotImplementedError(f"{kind} feature is not safely mapped")
        if feature is None:
            raise RuntimeError(f"SolidWorks failed to create {kind} feature")
        return feature

    def inspect_model(self, document: Any) -> dict[str, Any]:
        return {
            "title": str(document.GetTitle()),
            "feature_count": int(document.GetFeatureCount()),
        }

    def save_as(self, document: Any, path: str) -> None:
        errors, warnings = 0, 0
        result = document.Extension.SaveAs(path, 0, 1, None, errors, warnings)
        if not result:
            raise RuntimeError("SolidWorks SaveAs failed")

    def capture_preview(self, document: Any, path: str) -> None:
        if not document.SaveBMP(path, 0, 0):
            raise RuntimeError("SolidWorks preview capture failed")
