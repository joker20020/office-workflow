"""Session-bound artifact sidebar for the assistant chat page."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.artifact_paths import ArtifactPathPolicy
from src.ui.i18n_manager import _
from src.ui.language_aware import LanguageAwareMixin
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin

_CATEGORY_LABEL_KEYS = {
    "documents": "artifacts.categories.documents",
    "images": "artifacts.categories.images",
    "models": "artifacts.categories.models",
    "exports": "artifacts.categories.exports",
}


def _value(artifact: Any, key: str, default: Any = None) -> Any:
    if isinstance(artifact, dict):
        return artifact.get(key, default)
    return getattr(artifact, key, default)


class ArtifactSidebar(QFrame, ThemeAwareMixin, LanguageAwareMixin):
    """Display verified artifacts belonging to the active chat session."""

    artifact_activated = Signal(str)
    MINIMUM_WIDTH = 240
    MAXIMUM_WIDTH = 520
    DEFAULT_WIDTH = 320

    def __init__(
        self,
        repository: Any,
        policy: ArtifactPathPolicy,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._setup_theme_awareness()
        self._setup_language_awareness()
        self._repository = repository
        self._policy = policy
        self._session_id: str | None = None
        self._artifacts: dict[str, Any] = {}
        self._statuses: dict[str, str] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("artifactSidebar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(self.MINIMUM_WIDTH)
        self.setMaximumWidth(self.MAXIMUM_WIDTH)
        self.setStyleSheet(Theme.get_artifact_sidebar_stylesheet())
        root = QVBoxLayout(self)
        compact_gap = Theme.METRICS["section_gap"] // 2
        root.setContentsMargins(compact_gap, compact_gap, compact_gap, compact_gap)
        root.setSpacing(compact_gap)

        header = QHBoxLayout()
        self._title_label = QLabel(_("artifacts.title"))
        self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        header.addWidget(self._title_label)
        header.addStretch()
        root.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("artifactSidebarScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content.setObjectName("artifactSidebarContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(Theme.METRICS["section_gap"] // 2)
        self._content_layout.addStretch()
        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll, 1)

    def set_session(self, session_id: str | None) -> None:
        """Follow an existing chat session; the sidebar never selects sessions."""
        self._session_id = session_id
        self.refresh()

    def refresh(self) -> None:
        """Reload artifact metadata for the active session."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._artifacts.clear()
        self._statuses.clear()
        records = (
            self._repository.list_session(self._session_id)
            if self._session_id
            else []
        )
        grouped: dict[str, list[Any]] = {key: [] for key in _CATEGORY_LABEL_KEYS}
        for artifact in records:
            artifact_id = str(_value(artifact, "id"))
            self._artifacts[artifact_id] = artifact
            category = str(_value(artifact, "category", "exports"))
            grouped.setdefault(category, []).append(artifact)
            self._statuses[artifact_id] = self._path_status(artifact)

        if not records:
            empty = QLabel(_("artifacts.empty"))
            empty.setObjectName("artifactEmptyState")
            empty.setWordWrap(True)
            self._content_layout.addWidget(empty)
        else:
            for category, artifacts in grouped.items():
                if artifacts:
                    self._content_layout.addWidget(
                        self._category_widget(
                            _(
                                _CATEGORY_LABEL_KEYS.get(
                                    category,
                                    "artifacts.categories.other",
                                ),
                                category.title(),
                            ),
                            artifacts,
                        ),
                    )
        self._content_layout.addStretch()

    def _category_widget(self, title: str, artifacts: list[Any]) -> QWidget:
        section = QFrame()
        section.setObjectName("artifactCategory")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setObjectName("artifactCategoryTitle")
        layout.addWidget(label)
        for artifact in artifacts:
            layout.addWidget(self._artifact_widget(artifact))
        return section

    def _artifact_widget(self, artifact: Any) -> QWidget:
        artifact_id = str(_value(artifact, "id"))
        card = QFrame()
        card.setObjectName("artifactCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        name = QLabel(str(_value(artifact, "filename", "Artifact")))
        name.setWordWrap(True)
        name.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_primary"))
        layout.addWidget(name)
        path = QLabel(str(_value(artifact, "path", "")))
        path.setWordWrap(True)
        path.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_secondary"))
        path.setTextInteractionFlags(path.textInteractionFlags())
        layout.addWidget(path)

        producer = str(_value(artifact, "producer", "Agent"))
        created = _value(artifact, "created_at")
        if isinstance(created, datetime):
            created_text = created.isoformat(timespec="seconds")
        else:
            created_text = str(created or "")
        status = self._statuses[artifact_id]
        metadata = QLabel(" · ".join(part for part in (producer, created_text, status) if part))
        metadata.setStyleSheet(Theme.get_simple_text_label_stylesheet("text_hint"))
        layout.addWidget(metadata)

        actions = QHBoxLayout()
        for key, callback in (
            (
                "artifacts.open",
                lambda _=False, item_id=artifact_id: self.open_artifact(item_id),
            ),
            (
                "artifacts.reveal",
                lambda _=False, item_id=artifact_id: self.reveal_artifact(item_id),
            ),
            (
                "artifacts.copy_path",
                lambda _=False, item_id=artifact_id: self.copy_artifact_path(item_id),
            ),
        ):
            button = QPushButton(_(key))
            button.setStyleSheet(Theme.get_compact_button_stylesheet())
            button.clicked.connect(callback)
            button.setEnabled(status == "available")
            actions.addWidget(button)
        layout.addLayout(actions)
        return card

    def _validated_existing_path(self, artifact_id: str) -> Path | None:
        artifact = self._artifacts.get(str(artifact_id))
        if artifact is None:
            return None
        try:
            path = self._policy.validate_registered_path(_value(artifact, "path", ""))
        except (TypeError, ValueError, OSError):
            self._statuses[str(artifact_id)] = "unsafe"
            return None
        if not path.is_file():
            self._statuses[str(artifact_id)] = "unavailable"
            return None
        return path

    def _path_status(self, artifact: Any) -> str:
        try:
            path = self._policy.validate_registered_path(_value(artifact, "path", ""))
        except (TypeError, ValueError, OSError):
            return "unsafe"
        return "available" if path.is_file() else "unavailable"

    def open_artifact(self, artifact_id: str) -> bool:
        path = self._validated_existing_path(artifact_id)
        if path is None:
            return False
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if opened:
            self.artifact_activated.emit(str(artifact_id))
        return bool(opened)

    def reveal_artifact(self, artifact_id: str) -> bool:
        path = self._validated_existing_path(artifact_id)
        if path is None:
            return False
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))))

    def copy_artifact_path(self, artifact_id: str) -> bool:
        path = self._validated_existing_path(artifact_id)
        if path is None:
            return False
        QApplication.clipboard().setText(str(path))
        return True

    def refresh_language(self) -> None:
        """Refresh static labels while retaining the active artifact session."""
        self._title_label.setText(_("artifacts.title"))
        self.refresh()

    def refresh_theme(self) -> None:
        self.setStyleSheet(Theme.get_artifact_sidebar_stylesheet())
        self._title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        self.refresh()

    def visible_artifact_ids(self) -> list[str]:
        return list(self._artifacts)

    def status_for(self, artifact_id: str) -> str | None:
        return self._statuses.get(str(artifact_id))
