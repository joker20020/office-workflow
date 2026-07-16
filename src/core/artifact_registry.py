"""Verification boundary for persisted session artifact records."""

from pathlib import Path

from src.core.artifact_paths import ArtifactCategory, ArtifactPathPolicy
from src.storage.models import ArtifactRecord
from src.storage.repositories import ArtifactRepository


class ArtifactRegistry:
    """Persist metadata only for verified final artifact files."""

    def __init__(self, path_policy: ArtifactPathPolicy, repository: ArtifactRepository):
        self._path_policy = path_policy
        self._repository = repository

    def confirm_file(
        self,
        session_id: str,
        category: ArtifactCategory | str,
        path: str | Path,
    ) -> ArtifactRecord:
        """Verify a final session artifact exists, then persist its metadata."""
        final_path = self._path_policy.validate_registered_path(path)
        if not final_path.is_file():
            raise ValueError("artifact file must exist before it can be registered")

        expected_path = self._path_policy.destination(session_id, category, final_path.name)
        if final_path != expected_path.resolve():
            raise ValueError("artifact file must be stored in its session category destination")

        category_value = category.value if isinstance(category, ArtifactCategory) else str(category)
        return self._repository.create(
            session_id=session_id,
            category=category_value,
            filename=final_path.name,
            path=str(final_path),
        )
