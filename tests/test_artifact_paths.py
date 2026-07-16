from pathlib import Path

import pytest

from src.core.artifact_paths import ArtifactCategory, ArtifactPathPolicy


def test_destination_scopes_artifact_to_session_and_category(tmp_path: Path):
    policy = ArtifactPathPolicy(tmp_path)

    destination = policy.destination(
        "session-123",
        ArtifactCategory.DOCUMENTS,
        "report.docx",
    )

    assert destination == tmp_path / "data" / "documents" / "session-123" / "report.docx"
    assert policy.cache_path("preview.png") == tmp_path / "data" / "tmp" / "preview.png"


@pytest.mark.parametrize(
    "filename",
    ["../outside.txt", "nested/inside.txt", "nested\\inside.txt"],
)
def test_destination_rejects_filename_traversal(tmp_path: Path, filename: str):
    policy = ArtifactPathPolicy(tmp_path)

    with pytest.raises(ValueError):
        policy.destination("session-123", ArtifactCategory.DOCUMENTS, filename)


def test_validate_registered_path_rejects_file_outside_project_data(tmp_path: Path):
    policy = ArtifactPathPolicy(tmp_path)
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")

    with pytest.raises(ValueError):
        policy.validate_registered_path(outside_file)


def test_destination_rejects_unapproved_category(tmp_path: Path):
    policy = ArtifactPathPolicy(tmp_path)

    with pytest.raises(ValueError, match="category"):
        policy.destination("session-123", "spreadsheets", "report.xlsx")
