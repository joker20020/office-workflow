"""Safe project-local paths for session artifacts."""

from enum import StrEnum
from pathlib import Path


class ArtifactCategory(StrEnum):
    """Categories used to group persisted session artifacts."""

    DOCUMENTS = "documents"
    IMAGES = "images"
    MODELS = "models"
    EXPORTS = "exports"


class ArtifactPathPolicy:
    """Build and validate artifact paths rooted below a project's ``data`` directory."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.data_root = self.project_root / "data"

    def destination(
        self,
        session_id: str,
        category: ArtifactCategory | str,
        filename: str,
    ) -> Path:
        """Return the final path for one session artifact without creating it."""
        safe_session_id = self._component(session_id, "session_id")
        safe_filename = self._filename(filename)
        safe_category = self._category(category)
        destination = self.data_root / safe_category / safe_session_id / safe_filename
        self._ensure_within_data(destination)
        return destination

    def cache_path(self, filename: str) -> Path:
        """Return a temporary cache path under ``data/tmp``."""
        path = self.data_root / "tmp" / self._filename(filename)
        self._ensure_within_data(path)
        return path

    def validate_registered_path(self, path: str | Path) -> Path:
        """Return a resolved path only when it remains inside project ``data``."""
        candidate = Path(path).resolve()
        self._ensure_within_data(candidate)
        return candidate

    def _category(self, category: ArtifactCategory | str) -> str:
        value = category.value if isinstance(category, ArtifactCategory) else str(category)
        try:
            return ArtifactCategory(value).value
        except ValueError as exc:
            raise ValueError(
                "category must be one of documents, images, models, or exports"
            ) from exc

    @staticmethod
    def _component(value: str, name: str) -> str:
        if not value or Path(value).name != value or value in {".", ".."}:
            raise ValueError(f"{name} must be a single path component")
        return value

    def _filename(self, filename: str) -> str:
        return self._component(filename, "filename")

    def _ensure_within_data(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.data_root.resolve())
        except ValueError as exc:
            raise ValueError("artifact path must remain inside the project data directory") from exc
