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
    title: str = "Untitled"


@dataclass(frozen=True)
class SketchRef:
    id: str
    document_id: str
    plane: str
    closed: bool = False


@dataclass(frozen=True)
class FeatureRef:
    id: str
    document_id: str
    kind: str


@dataclass(frozen=True)
class OperationResult:
    success: bool
    message: str
    value: Any = None
    generated_files: tuple[str, ...] = field(default_factory=tuple)
    verification: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
