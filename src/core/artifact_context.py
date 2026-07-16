"""Per-reply artifact destinations shared with file-producing tools."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.artifact_paths import ArtifactCategory, ArtifactPathPolicy


@dataclass(frozen=True)
class ArtifactExecutionContext:
    """The active chat session's artifact services."""

    session_id: str
    path_policy: ArtifactPathPolicy
    registry: Any

    def destination(
        self,
        category: ArtifactCategory | str,
        filename: str,
    ) -> Path:
        return self.path_policy.destination(self.session_id, category, filename)

    def confirm_file(
        self,
        category: ArtifactCategory | str,
        path: str | Path,
        *,
        producer: str = "Agent",
        tool_call_id: str | None = None,
    ) -> Any:
        return self.registry.confirm_file(
            self.session_id,
            category,
            path,
            producer=producer,
            tool_call_id=tool_call_id,
        )


_CURRENT_ARTIFACT_CONTEXT: ContextVar[ArtifactExecutionContext | None] = ContextVar(
    "current_artifact_context",
    default=None,
)


def current_artifact_context() -> ArtifactExecutionContext | None:
    """Return the context active for the current reply/tool call, if any."""
    return _CURRENT_ARTIFACT_CONTEXT.get()


@contextmanager
def bind_artifact_context(
    context: ArtifactExecutionContext | None,
) -> Iterator[ArtifactExecutionContext | None]:
    """Temporarily expose one session's artifact services to tool calls."""
    token = _CURRENT_ARTIFACT_CONTEXT.set(context)
    try:
        yield context
    finally:
        _CURRENT_ARTIFACT_CONTEXT.reset(token)
