"""Artifact sidebar behavior and session binding tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QPushButton

from src.core.artifact_paths import ArtifactPathPolicy
from src.ui.i18n_manager import I18nManager


class _ArtifactRepository:
    def __init__(self, artifacts_by_session):
        self._artifacts_by_session = artifacts_by_session

    def list_session(self, session_id):
        return list(self._artifacts_by_session.get(session_id, []))


def _artifact(artifact_id, path, category="documents"):
    return SimpleNamespace(
        id=artifact_id,
        category=category,
        filename=Path(path).name,
        path=str(path),
        created_at=None,
    )


def test_sidebar_is_collapsed_by_default_and_lists_active_session_artifacts(tmp_path):
    from src.ui.chat.artifact_sidebar import ArtifactSidebar

    application = QApplication.instance() or QApplication([])
    assert application is not None
    output = tmp_path / "data" / "documents" / "session-1" / "report.md"
    output.parent.mkdir(parents=True)
    output.write_text("report", encoding="utf-8")
    repository = _ArtifactRepository(
        {"session-1": [_artifact("artifact-1", output)]},
    )

    sidebar = ArtifactSidebar(repository, ArtifactPathPolicy(tmp_path))

    assert sidebar.is_collapsed() is True
    sidebar.set_session("session-1")
    assert sidebar.visible_artifact_ids() == ["artifact-1"]
    assert not hasattr(sidebar, "session_search")
    assert not hasattr(sidebar, "session_selector")


def test_sidebar_marks_missing_and_outside_files_unavailable(tmp_path):
    from src.ui.chat.artifact_sidebar import ArtifactSidebar

    application = QApplication.instance() or QApplication([])
    assert application is not None
    missing = tmp_path / "data" / "images" / "session-1" / "missing.png"
    outside = tmp_path / "outside.txt"
    repository = _ArtifactRepository(
        {
            "session-1": [
                _artifact("missing", missing, "images"),
                _artifact("outside", outside, "documents"),
            ],
        },
    )
    sidebar = ArtifactSidebar(repository, ArtifactPathPolicy(tmp_path))

    sidebar.set_session("session-1")

    assert sidebar.status_for("missing") == "unavailable"
    assert sidebar.status_for("outside") == "unsafe"
    with patch("src.ui.chat.artifact_sidebar.QDesktopServices.openUrl") as open_url:
        assert sidebar.open_artifact("missing") is False
        assert sidebar.open_artifact("outside") is False
    open_url.assert_not_called()


def test_sidebar_safe_open_copy_and_reveal_validate_path(tmp_path):
    from src.ui.chat.artifact_sidebar import ArtifactSidebar

    application = QApplication.instance() or QApplication([])
    assert application is not None
    output = tmp_path / "data" / "models" / "session-1" / "part.blend"
    output.parent.mkdir(parents=True)
    output.write_text("blend", encoding="utf-8")
    sidebar = ArtifactSidebar(
        _ArtifactRepository({"session-1": [_artifact("part", output, "models")]}),
        ArtifactPathPolicy(tmp_path),
    )
    sidebar.set_session("session-1")

    with patch("src.ui.chat.artifact_sidebar.QDesktopServices.openUrl") as open_url:
        assert sidebar.open_artifact("part") is True
        assert sidebar.reveal_artifact("part") is True
    assert open_url.call_count == 2
    assert sidebar.copy_artifact_path("part") is True
    assert QApplication.clipboard().text() == str(output.resolve())


def test_session_deletion_refresh_clears_sidebar_without_deleting_file(tmp_path):
    from src.ui.chat.artifact_sidebar import ArtifactSidebar

    application = QApplication.instance() or QApplication([])
    assert application is not None
    output = tmp_path / "data" / "exports" / "session-1" / "part.stl"
    output.parent.mkdir(parents=True)
    output.write_text("solid", encoding="utf-8")
    records = {"session-1": [_artifact("part", output, "exports")]}
    repository = _ArtifactRepository(records)
    sidebar = ArtifactSidebar(repository, ArtifactPathPolicy(tmp_path))
    sidebar.set_session("session-1")

    records["session-1"].clear()
    sidebar.set_session(None)

    assert sidebar.visible_artifact_ids() == []
    assert output.exists()


def test_chat_panel_updates_sidebar_when_session_changes():
    from src.ui.chat.chat_panel import ChatPanel

    panel = MagicMock()
    panel._artifact_sidebar = MagicMock()

    ChatPanel._set_artifact_session(panel, "session-2")

    panel._artifact_sidebar.set_session.assert_called_once_with("session-2")


def test_chat_panel_refreshes_artifacts_after_agent_finishes():
    from src.ui.chat.chat_panel import ChatPanel

    panel = MagicMock()
    panel._artifact_sidebar = MagicMock()

    ChatPanel._refresh_artifacts(panel)

    panel._artifact_sidebar.refresh.assert_called_once_with()


def test_sidebar_refreshes_translated_labels_without_losing_session_artifacts(tmp_path):
    from src.ui.chat.artifact_sidebar import ArtifactSidebar

    application = QApplication.instance() or QApplication([])
    assert application is not None
    output = tmp_path / "data" / "documents" / "session-1" / "report.md"
    output.parent.mkdir(parents=True)
    output.write_text("report", encoding="utf-8")
    sidebar = ArtifactSidebar(
        _ArtifactRepository({"session-1": [_artifact("report", output)]}),
        ArtifactPathPolicy(tmp_path),
    )
    sidebar.set_session("session-1")
    manager = I18nManager.instance()
    manager._current_language = "en"
    manager._load_translations("en")

    sidebar.refresh_language()

    assert sidebar._title_label.text() == "Artifacts"
    assert sidebar.visible_artifact_ids() == ["report"]
    assert {button.text() for button in sidebar.findChildren(QPushButton)} == {
        "Open",
        "Reveal",
        "Copy path",
    }
    tool_button_type = type(sidebar._collapse_button)
    assert {button.text() for button in sidebar.findChildren(tool_button_type)} == {""}
