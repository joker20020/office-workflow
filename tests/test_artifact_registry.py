from pathlib import Path

import pytest

from src.core.artifact_paths import ArtifactCategory, ArtifactPathPolicy
from src.core.artifact_registry import ArtifactRegistry
from src.storage.database import Database
from src.storage.repositories import ArtifactRepository, ChatHistoryRepository


@pytest.fixture
def database(tmp_path: Path):
    database = Database(tmp_path / "artifacts.db")
    database.create_tables()
    yield database
    database.close()


def test_confirm_file_persists_verified_file_and_session_deletion_keeps_disk_file(
    tmp_path: Path, database: Database
):
    chat_repository = ChatHistoryRepository(database)
    artifact_repository = ArtifactRepository(database)
    session_id = chat_repository.create_session("artifact session")
    policy = ArtifactPathPolicy(tmp_path)
    final_path = policy.destination(session_id, ArtifactCategory.DOCUMENTS, "report.docx")
    final_path.parent.mkdir(parents=True)
    final_path.write_text("verified", encoding="utf-8")
    registry = ArtifactRegistry(policy, artifact_repository)

    record = registry.confirm_file(session_id, ArtifactCategory.DOCUMENTS, final_path)

    assert record.session_id == session_id
    assert artifact_repository.list_session(session_id)[0].path == str(final_path)
    assert chat_repository.delete_session(session_id) is True
    assert artifact_repository.list_session(session_id) == []
    assert final_path.exists()


def test_confirm_file_rejects_missing_final_file(tmp_path: Path, database: Database):
    policy = ArtifactPathPolicy(tmp_path)
    registry = ArtifactRegistry(policy, ArtifactRepository(database))
    missing_path = policy.destination("session-123", ArtifactCategory.DOCUMENTS, "missing.docx")

    with pytest.raises(ValueError, match="exist"):
        registry.confirm_file("session-123", ArtifactCategory.DOCUMENTS, missing_path)
