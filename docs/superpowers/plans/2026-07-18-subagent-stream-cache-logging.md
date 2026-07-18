# Subagent Stream, Cache, and Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render subagent execution as responsive semantic activity, load cached local images reliably, and serialize cross-process writes to the daily application log.

**Architecture:** `chat_panel` will parse the private subagent stream incrementally and emit public block updates in batches. The existing tool-result card will merge adjacent text events into a readable activity transcript. Image URLs will be normalized to local paths, while plugin cache writes become atomic. `logger.py` will own a rotating handler that locks a sidecar file around rollover and write operations.

**Tech Stack:** Python 3.11, PySide6, AgentScope 2.0, pytest/pytest-qt, stdlib logging, `msvcrt` on Windows and `fcntl` elsewhere.

## Global Constraints

- Keep cached artifacts below the project `data/tmp` directory.
- Preserve one daily rotated application log file; competing writers block until the current writer releases the lock.
- Do not add third-party dependencies.
- Apply shared changes on `main`, then cherry-pick the verified implementation commit to `solidworks`.

---

### Task 1: Parse and batch subagent stream events

**Files:**
- Modify: `src/ui/chat/chat_panel.py:77-207, 681-711, 1413-1545`
- Test: `tests/test_chat_panel.py`

**Interfaces:**
- Produces `SubagentEventDeltaDecoder.feed(delta: str) -> tuple[str, list[dict[str, Any]]]`.
- Produces `_event_to_block_updates(event: Any, state: dict[Any, Any]) -> list[dict[str, Any]]`.
- Keeps `_event_to_block_update(...) -> dict[str, Any] | None` as the compatibility wrapper for existing callers/tests.

- [ ] **Step 1: Write failing parser and batching tests**

```python
def test_event_adapter_reassembles_fragmented_subagent_marker():
    state = {("tool_result", "call-1"): {"name": "image", "output": ""}}
    marker = encode_subagent_event({"kind": "text", "title": "Image Agent", "text": "done"})
    first = ToolResultTextDeltaEvent(reply_id="r", tool_call_id="call-1", tool_call_name="image", delta=marker[:11])
    second = ToolResultTextDeltaEvent(reply_id="r", tool_call_id="call-1", tool_call_name="image", delta=marker[11:])
    assert _event_to_block_updates(first, state) == []
    updates = _event_to_block_updates(second, state)
    assert updates[-1]["type"] == "subagent_event"
    assert state[("tool_result", "call-1")]["output"] == ""

def test_event_adapter_keeps_visible_tool_output_and_removes_multiple_markers():
    state = {("tool_result", "call-1"): {"name": "image", "output": ""}}
    delta = "summary " + encode_subagent_event({"kind": "phase", "title": "Image Agent", "text": "running"}) + encode_subagent_event({"kind": "complete", "title": "Image Agent", "text": "done"})
    updates = _event_to_block_updates(ToolResultTextDeltaEvent(reply_id="r", tool_call_id="call-1", tool_call_name="image", delta=delta), state)
    assert updates[0]["output"] == "summary "
    assert [item["event_kind"] for item in updates[1:]] == ["phase", "complete"]
```

- [ ] **Step 2: Run the parser tests and verify RED**

Run: `uv run pytest tests/test_chat_panel.py -k "fragmented_subagent or multiple_markers" -q`

Expected: FAIL because `_event_to_block_updates` does not exist.

- [ ] **Step 3: Implement the incremental parser and callback batching**

```python
class SubagentEventDeltaDecoder:
    def feed(self, delta: str) -> tuple[str, list[dict[str, Any]]]:
        """Return visible tool text and all complete private events from one delta."""

def _event_to_block_updates(event: Any, state: Dict[Any, Any]) -> list[Dict[str, Any]]:
    """Translate an AgentScope event into zero or more widget payloads."""

def _event_to_block_update(event: Any, state: Dict[Any, Any]) -> Optional[Dict[str, Any]]:
    updates = _event_to_block_updates(event, state)
    return updates[-1] if updates else None
```

Add `_pending_block_updates: list[dict[str, Any]]` and a single-shot `QTimer` to `ChatPanel`. Queue ordinary updates for 75 ms, process terminal events immediately, and flush the queue before response, error, interruption, and worker-finished handlers. Make the callback emit the complete list returned by `_event_to_block_updates`.

- [ ] **Step 4: Run parser and existing stream tests and verify GREEN**

Run: `uv run pytest tests/test_chat_panel.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the verified stream parser work**

```bash
git add src/ui/chat/chat_panel.py tests/test_chat_panel.py
git commit -m "fix: batch and parse subagent stream events"
```

### Task 2: Make the subagent activity transcript readable

**Files:**
- Modify: `src/ui/chat/blocks/tool_result_block.py:182-244`
- Test: `tests/test_chat_panel.py`

**Interfaces:**
- `ToolResultBlockWidget.append_execution_event(event: dict[str, Any]) -> None` merges consecutive `text` events with equal title/status.
- `_execution_events_text() -> str` produces grouped semantic lines and never embeds protocol JSON.

- [ ] **Step 1: Write failing transcript tests**

```python
def test_tool_result_merges_adjacent_subagent_text_events():
    widget = ToolResultBlockWidget({"type": "tool_result", "id": "call", "name": "image", "output": ""})
    widget.append_execution_event({"type": "subagent_event", "event_kind": "text", "status": "running", "title": "Image Agent", "text": "A"})
    widget.append_execution_event({"type": "subagent_event", "event_kind": "text", "status": "running", "title": "Image Agent", "text": " 2D"})
    assert widget.execution_event_count() == 1
    assert "Image Agent" in widget._execution_events_text()
    assert "A 2D" in widget._execution_events_text()
```

- [ ] **Step 2: Run the transcript test and verify RED**

Run: `uv run pytest tests/test_chat_panel.py -k merges_adjacent_subagent -q`

Expected: FAIL because two text events are stored separately.

- [ ] **Step 3: Implement event coalescing and semantic labels**

```python
def append_execution_event(self, event: Dict[str, Any]) -> None:
    if self._can_merge_execution_event(event):
        self._execution_events[-1]["text"] += str(event.get("text", ""))
    else:
        self._execution_events.append(event.copy())
    self._render_execution_events()
```

Map `phase`, `tool_call`, `tool_result`, `warning`, `error`, and `complete` to concise human-readable labels; format text as a continued output line rather than one row per token. Update the QTextEdit at most once per queued UI flush.

- [ ] **Step 4: Run transcript and chat-panel tests and verify GREEN**

Run: `uv run pytest tests/test_chat_panel.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the verified transcript work**

```bash
git add src/ui/chat/blocks/tool_result_block.py tests/test_chat_panel.py
git commit -m "fix: coalesce subagent activity output"
```

### Task 3: Atomically cache and display local images

**Files:**
- Modify: `plugins/agent_extensions/__init__.py:1688-1750, 1901-1930`
- Modify: `src/ui/chat/blocks/image_block.py:1-107`
- Test: `tests/test_agent_extensions_rag.py`
- Test: `tests/test_chat_panel.py`

**Interfaces:**
- Produces `_atomic_write_bytes(destination: Path, data: bytes) -> Path` for plugin cache writers.
- Produces `resolve_local_image_path(url: str) -> str` for `ImageBlockWidget` URL sources.

- [ ] **Step 1: Write failing cache and file-URI tests**

```python
def test_image_block_loads_file_uri(tmp_path):
    image_path = tmp_path / "preview.png"
    image_path.write_bytes(PNG_1X1_BYTES)
    widget = ImageBlockWidget({"type": "image", "source": {"type": "url", "url": image_path.as_uri()}})
    assert not widget._image_label.pixmap().isNull()

@pytest.mark.asyncio
async def test_cache_rag_asset_replaces_existing_file_atomically(tmp_path):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock(rag_get_asset=AsyncMock(return_value=PNG_1X1_BYTES))
    tools._artifact_paths = ArtifactPathPolicy(tmp_path)
    path = Path(await tools._cache_rag_asset("process", "part.png"))
    assert path.parent == tmp_path / "data" / "tmp"
    assert path.read_bytes() == PNG_1X1_BYTES
    assert not list(path.parent.glob("*.part"))
```

- [ ] **Step 2: Run image tests and verify RED**

Run: `uv run pytest tests/test_chat_panel.py -k file_uri tests/test_agent_extensions_rag.py -k atomically -q`

Expected: the file-URI test fails because `QPixmap("file://...")` is not a local path, and the atomic-write helper is absent.

- [ ] **Step 3: Implement local-path normalization and atomic writes**

```python
def resolve_local_image_path(url: str) -> str:
    parsed = QUrl(url)
    return parsed.toLocalFile() if parsed.isLocalFile() else url

def _atomic_write_bytes(destination: Path, data: bytes) -> Path:
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_bytes(data)
    temporary.replace(destination)
    return destination
```

Use the helper for `get_image`, `text_to_image`, and `_cache_rag_asset`; retain `ArtifactPathPolicy.cache_path()` as the only destination resolver. The widget must display a diagnostic placeholder if the resolved local file cannot be decoded.

- [ ] **Step 4: Run image, RAG, and artifact-context tests and verify GREEN**

Run: `uv run pytest tests/test_chat_panel.py tests/test_agent_extensions_rag.py tests/test_artifact_tool_context.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the verified cache work**

```bash
git add plugins/agent_extensions/__init__.py src/ui/chat/blocks/image_block.py tests/test_chat_panel.py tests/test_agent_extensions_rag.py
git commit -m "fix: atomically cache and load local images"
```

### Task 4: Serialize daily log writes and remove noisy text-update logs

**Files:**
- Modify: `src/utils/logger.py`
- Modify: `src/ui/chat/chat_panel.py:1494-1545`
- Test: `tests/test_logger.py`
- Test: `tests/test_chat_panel.py`

**Interfaces:**
- Produces `BlockingRotatingFileHandler(RotatingFileHandler)` whose `emit(record)` holds a cross-process lock through rollover and write.
- `get_logger(...) -> logging.Logger` initializes each named logger under a process-local `threading.RLock`.

- [ ] **Step 1: Write failing blocking and log-noise tests**

```python
def test_file_handler_blocks_until_another_process_releases_lock(tmp_path):
    handler = BlockingRotatingFileHandler(tmp_path / "shared.log", maxBytes=1024, backupCount=1, encoding="utf-8")
    with handler._interprocess_lock.hold():
        thread = Thread(target=handler.emit, args=(logging.makeLogRecord({"msg": "after-lock", "levelno": logging.INFO, "levelname": "INFO"}),))
        thread.start()
        assert thread.is_alive()
    thread.join(timeout=2)
    assert not thread.is_alive()

def test_block_update_does_not_log_plain_text_at_info(panel, caplog):
    with caplog.at_level(logging.INFO, logger="src.ui.chat.chat_panel"):
        panel._apply_block_updates([{"type": "text", "id": "t", "text": "one", "_new_block": True}])
    assert "Block update: text" not in caplog.messages
```

- [ ] **Step 2: Run logging tests and verify RED**

Run: `uv run pytest tests/test_logger.py tests/test_chat_panel.py -k "blocks_until or does_not_log_plain" -q`

Expected: FAIL because the locking handler and `_apply_block_updates` do not exist, and text updates are logged at INFO.

- [ ] **Step 3: Implement the blocking rotating handler and useful logging policy**

```python
class BlockingRotatingFileHandler(RotatingFileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        with self._interprocess_lock.hold():
            super().emit(record)

_LOGGER_SETUP_LOCK = threading.RLock()

def get_logger(...) -> logging.Logger:
    with _LOGGER_SETUP_LOCK:
        # inspect handlers and attach each handler exactly once
        ...
```

Implement the lock with a one-byte sidecar lock file: loop on `msvcrt.LK_NBLCK` on Windows and `fcntl.LOCK_EX | LOCK_NB` elsewhere with a short sleep, and release in `finally`. Move block application into `_apply_block_updates`; log only non-text type changes at `DEBUG` and one aggregated batch counter at `DEBUG`, never `INFO` for token-level text updates.

- [ ] **Step 4: Run logging and UI stream tests and verify GREEN**

Run: `uv run pytest tests/test_logger.py tests/test_chat_panel.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the verified logging work**

```bash
git add src/utils/logger.py src/ui/chat/chat_panel.py tests/test_logger.py tests/test_chat_panel.py
git commit -m "fix: serialize rotating log writes"
```

### Task 5: Full verification and branch synchronization

**Files:**
- Modify: none expected

- [ ] **Step 1: Run full verification on `main`**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Cherry-pick shared commits to `solidworks` and run its full suite**

Run: `git switch solidworks && git cherry-pick <main-implementation-commits> && uv run pytest -q`

Expected: cherry-pick succeeds and all tests pass.

- [ ] **Step 3: Return to `main` and report commit IDs plus verification evidence**

Run: `git switch main && git log --oneline -5`

Expected: `main` is the active branch and the final response names the shared commit(s) and both test outcomes.

## Self-Review

- Spec coverage: Tasks 1--2 cover structured, throttled subagent display and removal of raw markers; Task 3 covers `data/tmp` cache atomicity and local file loading; Task 4 covers blocking writes, rotation and empty text-log suppression; Task 5 covers both requested branches.
- Placeholder scan: no deferred implementation tasks or unspecified test commands remain.
- Type consistency: `SubagentEventDeltaDecoder.feed` feeds `_event_to_block_updates`; `resolve_local_image_path` is consumed only by `ImageBlockWidget`; `BlockingRotatingFileHandler` is created only by `get_logger`.
