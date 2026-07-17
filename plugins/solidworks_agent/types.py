"""Typed public records used by the SolidWorks MCP boundary."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectionResult:
    success: bool
    owned: bool
    message: str


@dataclass(frozen=True)
class DocumentRef:
    id: str
    session_id: str
    name: str
    unit: str

    @property
    def title(self) -> str:
        return self.name


@dataclass(frozen=True)
class SketchRef:
    id: str
    document_id: str
    plane: str
    closed: bool = False


@dataclass(frozen=True)
class SketchEntityRef:
    id: str
    document_id: str
    sketch_id: str
    kind: str


@dataclass(frozen=True)
class FeatureRef:
    id: str
    document_id: str
    kind: str


@dataclass(frozen=True)
class FaceRef:
    id: str
    document_id: str


@dataclass(frozen=True)
class EdgeRef:
    id: str
    document_id: str


@dataclass(frozen=True)
class OperationResult:
    success: bool
    message: str
    value: Any = None
    generated_files: tuple[str, ...] = field(default_factory=tuple)
    verification: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
