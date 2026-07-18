# Artifact Sidebar and Output Path Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist verified agent artifacts per existing chat session, present subagent execution events inside parent tool-result cards, add a default-collapsed artifact sidebar, and force current generators including Blender to write session-scoped outputs under `data`.

**Architecture:** Add a small storage/repository boundary for artifact metadata and a project-root-aware `ArtifactPathPolicy`. The chat panel owns display-only artifact/sidebar state and consumes normalized execution events; the current chat session remains owned by `ChatHistory` and left-side session management. File producers obtain destinations from the policy and call a registry-facing confirmation function only after a file exists.

**Tech Stack:** Python 3.11, PySide6, SQLAlchemy/SQLite, AgentScope 2.0.4 events, pytest, pathlib.

## Global Constraints

- Implement every task in the current `main` branch; do not switch to or change `solidworks_version` for this plan.
- Do not add SolidWorks MCP code, SolidWorks settings, or default workflow replacement; those belong exclusively to `solidworks_version`.
- Keep Blender code and the current Blender modeling stage on `main`; this plan only routes its files through the shared `data` output-path policy and artifact registry.
- Session deletion deletes artifact registry rows but never deletes files below `data`.
- The sidebar never creates, searches, or switches sessions; it follows the currently active existing chat session.
- User-visible artifacts must resolve below project-root `data`; unsafe, missing, or out-of-root files cannot be registered or opened.
- Internal RAG/download cache lives below `data/tmp` and is never displayed as an artifact.
- User-visible destinations are exactly `data/documents/<session-id>`, `data/images/<session-id>`, `data/models/<session-id>`, and `data/exports/<session-id>`.
- Subagent final Markdown remains the parent tool result. Only displayable execution/tool events stream within that same result card; never render private reasoning.
- Preserve user-owned `.gitignore` and the existing untracked plan/spec files.

---

## File map

- `src/core/artifact_paths.py` — new canonical output category enum, session destination resolution, boundary validation, cache path resolution, and safe-open eligibility.
- `src/storage/models.py` — new `ArtifactRecord` relationship owned by `ChatSessionRecord`.
- `src/storage/repositories.py` — `ArtifactRepository` CRUD and session-scoped list/delete methods.
- `src/core/artifact_registry.py` — new service which verifies an existing output with `ArtifactPathPolicy` and writes a record.
- `src/agent/agent_integration.py` — normalized display-safe subagent execution events and current session ID exposure; no hidden reasoning payloads.
- `src/ui/chat/artifact_sidebar.py` — new collapsible session-bound artifact panel and safe open/copy/reveal actions.
- `src/ui/chat/chat_panel.py` — own artifact panel, refresh on session selection, and append nested execution-event blocks to the parent tool-result block.
- `src/ui/chat/blocks/tool_result_block.py` and `src/ui/chat/blocks/__init__.py` — render nested execution events in an existing tool-result card.
- `plugins/agent_extensions/__init__.py`, `plugins/agent_extensions/populate_rag.py`, and Blender-facing tool modules — receive session-scoped output roots and confirm final artifacts; move cache to `data/tmp`.
- `tests/test_artifact_paths.py`, `tests/test_artifact_registry.py`, `tests/test_chat_panel.py`, `tests/test_agent_integration.py`, `tests/test_agent_extensions_rag.py`, and Blender plugin tests — regression coverage.

### Task 1: Define artifact path policy and persistent artifact repository

**Files:**
- Create: `src/core/artifact_paths.py`
- Create: `src/core/artifact_registry.py`
- Modify: `src/storage/models.py`
- Modify: `src/storage/repositories.py`
- Test: `tests/test_artifact_paths.py`
- Test: `tests/test_artifact_registry.py`

**Interfaces:**
- Produces `ArtifactCategory(str, Enum)` with `DOCUMENT`, `IMAGE`, `MODEL`, and `EXPORT`.
- Produces `ArtifactPathPolicy(project_root: Path)` with `destination(session_id, category, filename) -> Path`, `cache_path(filename) -> Path`, and `validate_registered_path(path) -> Path`.
- Produces `ArtifactRepository.create_verified(...) -> dict`, `list_for_session(session_id) -> list[dict]`, and `delete_for_session(session_id) -> int`.
- Produces `ArtifactRegistry.confirm_file(...) -> dict` which validates an existing final file before persistence.

- [ ] **Step 1: Write failing path-boundary tests**

```python
def test_destination_is_session_scoped_under_category(tmp_path):
    policy = ArtifactPathPolicy(tmp_path)
    result = policy.destination("session-1", ArtifactCategory.MODEL, "shell.sldprt")
    assert result == tmp_path / "data" / "models" / "session-1" / "shell.sldprt"


def test_policy_rejects_escape_and_outside_paths(tmp_path):
    policy = ArtifactPathPolicy(tmp_path)
    with pytest.raises(ValueError, match="data"):
        policy.validate_registered_path(tmp_path / "outside.txt")
    with pytest.raises(ValueError, match="filename"):
        policy.destination("session-1", ArtifactCategory.IMAGE, "../escape.png")
```

- [ ] **Step 2: Run path tests to verify RED**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_artifact_paths.py -q`

Expected: import failure for `ArtifactPathPolicy` and `ArtifactCategory`.

- [ ] **Step 3: Implement the minimal policy**

```python
class ArtifactCategory(str, Enum):
    DOCUMENT = "documents"
    IMAGE = "images"
    MODEL = "models"
    EXPORT = "exports"


class ArtifactPathPolicy:
    def destination(self, session_id: str, category: ArtifactCategory, filename: str) -> Path:
        if not session_id or Path(filename).name != filename:
            raise ValueError("session_id and filename are required")
        target = (self._data_root / category.value / session_id / filename).resolve()
        self._assert_under_data(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
```

Implement `cache_path()` under `data/tmp`, and validate real resolved paths beneath `data` without registering cache paths.

- [ ] **Step 4: Write failing repository/session-delete tests**

```python
def test_delete_session_cascades_artifact_rows_but_keeps_file(database, tmp_path):
    history = ChatHistoryRepository(database)
    session_id = history.create_session("artifact session")
    output = tmp_path / "data" / "documents" / session_id / "report.md"
    output.parent.mkdir(parents=True)
    output.write_text("report", encoding="utf-8")
    artifacts = ArtifactRepository(database)
    artifacts.create_verified(session_id=session_id, category="documents", absolute_path=output)

    assert history.delete_session(session_id) is True
    assert artifacts.list_for_session(session_id) == []
    assert output.exists()
```

- [ ] **Step 5: Run repository test to verify RED**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_artifact_registry.py::test_delete_session_cascades_artifact_rows_but_keeps_file -q`

Expected: import failure for `ArtifactRepository` or missing artifact relationship/table.

- [ ] **Step 6: Add `ArtifactRecord` and repository implementation**

```python
class ArtifactRecord(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    absolute_path: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    producer: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="verified")
```

Add `ChatSessionRecord.artifacts` with `cascade="all, delete-orphan"`. Repository serialization must expose ISO timestamps and must not delete filesystem paths.

- [ ] **Step 7: Implement confirmation-only registry and run GREEN tests**

```python
def confirm_file(self, *, session_id, category, path, producer, tool_call_id=None):
    verified_path = self._policy.validate_registered_path(Path(path))
    if not verified_path.is_file():
        raise FileNotFoundError(verified_path)
    return self._repository.create_verified(...)
```

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_artifact_paths.py tests/test_artifact_registry.py -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```powershell
git add src/core/artifact_paths.py src/core/artifact_registry.py src/storage/models.py src/storage/repositories.py tests/test_artifact_paths.py tests/test_artifact_registry.py
git commit -m "feat: persist verified session artifacts"
```

### Task 2: Stream subagent execution inside parent tool-result cards

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `src/ui/chat/chat_panel.py`
- Modify: `src/ui/chat/composite_message_widget.py`
- Modify: `src/ui/chat/blocks/tool_result_block.py`
- Modify: `src/ui/chat/blocks/__init__.py`
- Test: `tests/test_agent_integration.py`
- Test: `tests/test_chat_panel.py`

**Interfaces:**
- Produces display-only block payload type `subagent_event` with `parent_tool_call_id`, `event_kind`, `title`, `text`, `status`, and optional `artifact_id`.
- Extends existing `tool_result` payload with `execution_events: list[dict]` without changing final `output` Markdown semantics.
- Produces `ToolResultBlock.append_execution_event(event: dict) -> None` and performs updates by parent tool-call ID.

- [ ] **Step 1: Write a failing event-normalization test**

```python
def test_subagent_progress_is_nested_under_parent_tool_result():
    state = {}
    update = normalize_subagent_execution_event(
        parent_tool_call_id="call-1",
        event={"kind": "tool_result", "tool": "generate_image", "text": "saved image"},
        state=state,
    )
    assert update == {
        "type": "subagent_event",
        "parent_tool_call_id": "call-1",
        "event_kind": "tool_result",
        "title": "generate_image",
        "text": "saved image",
        "status": "running",
    }
```

- [ ] **Step 2: Run RED test**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_agent_integration.py::test_subagent_progress_is_nested_under_parent_tool_result -q`

Expected: import failure for `normalize_subagent_execution_event`.

- [ ] **Step 3: Implement a display-safe normalizer**

```python
def normalize_subagent_execution_event(*, parent_tool_call_id: str, event: Mapping[str, Any], state: dict) -> dict:
    kind = str(event.get("kind", "progress"))
    if kind not in {"phase", "text", "tool_call", "tool_result", "artifact", "warning", "error", "complete"}:
        kind = "progress"
    return {
        "type": "subagent_event",
        "parent_tool_call_id": parent_tool_call_id,
        "event_kind": kind,
        "title": str(event.get("tool") or event.get("title") or "Subagent"),
        "text": str(event.get("text", "")),
        "status": "failed" if kind == "error" else "completed" if kind == "complete" else "running",
    }
```

Do not accept or render keys named `reasoning`, `thought`, `chain_of_thought`, or arbitrary raw event dictionaries.

- [ ] **Step 4: Write failing widget behavior tests**

```python
def test_tool_result_widget_keeps_final_markdown_and_appends_execution_events(qtbot):
    widget = ToolResultBlock({"type": "tool_result", "id": "call-1", "output": "# Final"})
    widget.append_execution_event({"type": "subagent_event", "event_kind": "artifact", "text": "saved report"})
    assert widget.get_content() == "# Final"
    assert widget.execution_event_count() == 1
```

- [ ] **Step 5: Run RED widget and panel tests**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_chat_panel.py -q`

Expected: failure because `ToolResultBlock` has no nested event API.

- [ ] **Step 6: Implement nested event rendering and event-to-block routing**

```python
def add_or_update_block(self, block_data: dict) -> None:
    if block_data.get("type") == "subagent_event":
        parent = self._find_tool_result(block_data["parent_tool_call_id"])
        if parent is not None:
            parent.append_execution_event(block_data)
        return
    # existing behavior unchanged
```

Use a collapsible event container inside `ToolResultBlock`; final Markdown remains in its existing result content widget.

- [ ] **Step 7: Run GREEN tests**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_agent_integration.py tests/test_chat_panel.py -q`

Expected: PASS, including existing AgentScope event translation tests.

- [ ] **Step 8: Commit Task 2**

```powershell
git add src/agent/agent_integration.py src/ui/chat/chat_panel.py src/ui/chat/composite_message_widget.py src/ui/chat/blocks/tool_result_block.py src/ui/chat/blocks/__init__.py tests/test_agent_integration.py tests/test_chat_panel.py
git commit -m "feat: stream subagent events in tool results"
```

### Task 3: Add default-collapsed session-bound artifact sidebar

**Files:**
- Create: `src/ui/chat/artifact_sidebar.py`
- Modify: `src/ui/chat/chat_panel.py`
- Modify: `src/ui/main_window.py`
- Test: `tests/test_chat_panel.py`

**Interfaces:**
- Produces `ArtifactSidebar(repository, policy, parent=None)` with `set_session(session_id: str | None)`, `refresh()`, and `set_collapsed(collapsed: bool)`.
- Produces `artifact_activated: Signal(str)` carrying artifact ID for chat-card coordination.
- `ChatPanel` supplies its active `ChatHistory.session_id` whenever a session is loaded, reset, switched, or deleted.

- [ ] **Step 1: Write failing sidebar/session binding tests**

```python
def test_sidebar_is_collapsed_by_default_and_lists_active_session_artifacts(qtbot, artifact_repository, path_policy):
    sidebar = ArtifactSidebar(artifact_repository, path_policy)
    qtbot.addWidget(sidebar)
    assert sidebar.is_collapsed() is True
    sidebar.set_session("session-1")
    assert sidebar.visible_artifact_ids() == ["artifact-1"]
```

- [ ] **Step 2: Run RED UI test**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_chat_panel.py::test_sidebar_is_collapsed_by_default_and_lists_active_session_artifacts -q`

Expected: import failure for `ArtifactSidebar`.

- [ ] **Step 3: Implement sidebar grouping and safe actions**

```python
class ArtifactSidebar(QFrame):
    def set_session(self, session_id: str | None) -> None:
        self._session_id = session_id
        self.refresh()

    def _open_artifact(self, artifact: dict) -> None:
        path = self._policy.validate_registered_path(Path(artifact["absolute_path"]))
        if not path.is_file():
            self._mark_unavailable(artifact["id"])
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
```

Render documents, images, models, and exports in category sections; include absolute path, producer, timestamp, status, copy-path, reveal, and open controls. The sidebar must not include session search or selection widgets.

- [ ] **Step 4: Wire the chat-panel button and active-session refresh**

```python
def _on_session_changed(self, session_id: str | None) -> None:
    self._artifact_sidebar.set_session(session_id)

def _toggle_artifact_sidebar(self) -> None:
    self._artifact_sidebar.set_collapsed(not self._artifact_sidebar.is_collapsed())
```

Place the toggle in the existing chat header. Use a `QSplitter` or stable right-side layout so the collapsed state preserves chat input usability.

- [ ] **Step 5: Add missing-file and delete-session tests, then run GREEN**

```python
def test_sidebar_marks_deleted_file_unavailable_without_removing_registry_row(...):
    # create registered record, remove only the disk file, refresh sidebar
    assert sidebar.status_for("artifact-1") == "unavailable"

def test_session_delete_refreshes_sidebar_without_deleting_artifact_file(...):
    # delete session via existing ChatHistory flow
    assert sidebar.visible_artifact_ids() == []
    assert output.exists()
```

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_chat_panel.py tests/test_chat_history.py tests/test_artifact_registry.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```powershell
git add src/ui/chat/artifact_sidebar.py src/ui/chat/chat_panel.py src/ui/main_window.py tests/test_chat_panel.py tests/test_chat_history.py
git commit -m "feat: add session artifact sidebar"
```

### Task 4: Route current generators and Blender through the policy

**Files:**
- Modify: `plugins/agent_extensions/__init__.py`
- Modify: `plugins/agent_extensions/populate_rag.py`
- Modify: Blender subagent/plugin output modules found by `rg -n "blend|\.stl|\.step|render|output_path|save_as" plugins src`
- Modify: `src/agent/workflow_tools.py` only if it constructs file-producing tool context
- Test: `tests/test_agent_extensions_rag.py`
- Test: Blender/plugin tests identified by the same search

**Interfaces:**
- File-producing contexts accept `session_id: str` and an `ArtifactPathPolicy` or a typed destination mapping.
- Final write/export functions call `ArtifactRegistry.confirm_file()` after successful existence verification.
- RAG cache requests use `ArtifactPathPolicy.cache_path()` and do not call the registry.

- [ ] **Step 1: Inventory current output paths and add failing cache/destination tests**

Run: `rg -n "data/img|data/images|\.blend|\.stl|\.step|render|output_path|save_as" plugins src`

Add assertions such as:

```python
def test_rag_cache_uses_data_tmp_and_is_not_registered(tmp_path):
    tools = make_extension_tools(data_dir=tmp_path / "data")
    cached = tools._cache_rag_asset(...)
    assert cached.parent == tmp_path / "data" / "tmp"
    assert artifact_repository.list_for_session("session-1") == []

def test_blender_outputs_are_session_scoped_and_registered(...):
    result = run_blender_export(session_id="session-1", ...)
    assert Path(result["blend_path"]).is_relative_to(project_root / "data" / "models" / "session-1")
    assert Path(result["stl_path"]).is_relative_to(project_root / "data" / "exports" / "session-1")
```

- [ ] **Step 2: Run RED tests**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_agent_extensions_rag.py -q`

Run the identified Blender plugin test node(s) with `-q`.

Expected: cache/path assertions fail against legacy locations.

- [ ] **Step 3: Replace ad-hoc write destinations with typed policy calls**

```python
cache_path = self._artifact_paths.cache_path(cache_filename)
model_path = self._artifact_paths.destination(session_id, ArtifactCategory.MODEL, f"{safe_name}.blend")
export_path = self._artifact_paths.destination(session_id, ArtifactCategory.EXPORT, f"{safe_name}.stl")
```

For each final document/image/model/export, verify `Path.is_file()` and call `confirm_file()` with producer and parent tool-call ID. Return the registry-backed absolute paths in the existing structured Markdown result. Do not register RAG cache bytes.

- [ ] **Step 4: Add path-policy failure tests and run GREEN**

```python
def test_outside_generator_path_is_reported_as_failure_and_not_registered(...):
    result = finalize_output("C:/outside/model.stl")
    assert result["status"] == "failed"
    assert artifact_repository.list_for_session("session-1") == []
```

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_agent_extensions_rag.py <identified-blender-tests> -q`

Expected: PASS.

- [ ] **Step 5: Run current-branch integration gates**

Run:

```powershell
.venv\\Scripts\\ruff.exe check src/agent src/core src/storage src/ui/chat plugins/agent_extensions tests/test_agent_integration.py tests/test_chat_panel.py tests/test_chat_history.py tests/test_agent_extensions_rag.py tests/test_artifact_paths.py tests/test_artifact_registry.py
.venv\\Scripts\\python.exe -m pytest tests/test_agent_integration.py tests/test_chat_panel.py tests/test_chat_history.py tests/test_agent_extensions_rag.py tests/test_artifact_paths.py tests/test_artifact_registry.py -q
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit Task 4**

```powershell
git add plugins/agent_extensions src/agent/workflow_tools.py tests/test_agent_extensions_rag.py <identified-blender-test-files>
git commit -m "feat: constrain generator artifacts to data"
```

### Task 5: Current-branch acceptance and handoff boundary

**Files:**
- Verify only; modify test/runtime code only for a confirmed regression from Tasks 1-4.

**Interfaces:**
- Produces final evidence that current-branch scope is complete and has not introduced SolidWorks MCP code.

- [ ] **Step 1: Scan branch scope before full test**

Run:

```powershell
rg -n "solidworks|SLDWORKS|win32com|pythoncom" src plugins tests pyproject.toml
git status --short
```

Expected: no new SolidWorks MCP implementation in current-branch files; preserve unrelated user changes.

- [ ] **Step 2: Run full suite**

Run: `.venv\\Scripts\\python.exe -m pytest -q`

Expected: zero failures. Remove only test-created `plugins/_sandbox_test_*` directories after resolving and verifying every target lies under the repository `plugins` root.

- [ ] **Step 3: Audit intended changes and commit only owned files**

Run:

```powershell
git diff --check
git status --short
git diff --stat HEAD~4..HEAD
```

Expected: no user-owned `.gitignore` or untracked docs are staged. Do not create or modify the `solidworks_version` branch.

- [ ] **Step 4: Record SolidWorks handoff**

Document that the SolidWorks MCP plan starts only after current-branch acceptance and must be implemented on `solidworks_version`, including its first-use SolidWorks 2023 license/COM prompt preparation.
