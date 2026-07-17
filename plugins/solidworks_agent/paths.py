"""Session-scoped artifact paths for the SolidWorks MCP server."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from src.core.artifact_context import ArtifactExecutionContext
from src.core.artifact_paths import ArtifactCategory, ArtifactPathPolicy
from src.core.artifact_registry import ArtifactRegistry
from src.storage.database import Database
from src.storage.repositories import ArtifactRepository

_OUTPUTS = {
    "native": (ArtifactCategory.MODELS, ".sldprt"),
    "step": (ArtifactCategory.EXPORTS, ".step"),
    "stl": (ArtifactCategory.EXPORTS, ".stl"),
    "preview": (ArtifactCategory.IMAGES, ".png"),
}


def sanitize_model_name(value: str) -> str:
    """Return a conservative filename stem, never a path."""
    stem = re.sub(r"(?i)\.(?:sldprt|sldasm|step|stp|stl|png)$", "", str(value))
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    if not stem:
        return "solidworks-model"
    return stem[:96]


class SolidWorksArtifactPathBridge:
    """Issue and register only the four fixed SolidWorks artifact classes."""

    def __init__(
        self,
        context: ArtifactExecutionContext,
        *,
        tool_call_id: str | None = None,
    ) -> None:
        self.context = context
        self.tool_call_id = tool_call_id
        self._issued: dict[Path, ArtifactCategory] = {}

    def path_for(self, document: Any, kind: str) -> str:
        if document.session_id != self.context.session_id:
            raise ValueError("document session does not match the artifact session")
        if kind not in _OUTPUTS:
            raise ValueError("unsupported SolidWorks artifact kind")
        category, suffix = _OUTPUTS[kind]
        if kind == "native" and str(document.name).casefold().endswith(".sldasm"):
            suffix = ".sldasm"
        path = self.context.destination(category, f"{sanitize_model_name(document.name)}{suffix}")
        resolved = self.context.path_policy.validate_registered_path(path)
        self._issued[resolved] = category
        return str(resolved)

    def validate_output_path(self, path: str) -> bool:
        try:
            resolved = self.context.path_policy.validate_registered_path(path)
        except (OSError, ValueError):
            return False
        return resolved in self._issued

    def confirm_file(self, path: str) -> bool:
        try:
            resolved = self.context.path_policy.validate_registered_path(path)
            category = self._issued[resolved]
            if not resolved.is_file():
                return False
            self.context.confirm_file(
                category,
                resolved,
                producer="SolidWorksAgent",
                tool_call_id=self.tool_call_id,
            )
        except (KeyError, OSError, ValueError):
            return False
        return True


def path_bridge_from_environment() -> SolidWorksArtifactPathBridge:
    """Build the MCP-process bridge from trusted launcher environment values."""
    project_root = Path(os.environ.get("SOLIDWORKS_PROJECT_ROOT", Path.cwd())).resolve()
    session_id = os.environ.get("SOLIDWORKS_SESSION_ID", "solidworks-live")
    policy = ArtifactPathPolicy(project_root)
    database_path = os.environ.get("SOLIDWORKS_DATABASE_PATH", policy.data_root / "app.db")
    database = Database(Path(database_path))
    registry = ArtifactRegistry(policy, ArtifactRepository(database))
    context = ArtifactExecutionContext(session_id, policy, registry)
    return SolidWorksArtifactPathBridge(
        context,
        tool_call_id=os.environ.get("SOLIDWORKS_TOOL_CALL_ID"),
    )
