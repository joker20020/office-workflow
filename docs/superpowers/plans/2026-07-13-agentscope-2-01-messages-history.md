# AgentScope 2.0 Messages and History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin AgentScope 2.0.4 and migrate message creation, multimodal blocks, serialization, and persisted 1.x history reads to the 2.0 schema.

**Architecture:** `ChatHistory` is the only legacy-data boundary. Runtime callers use `UserMsg`, `AssistantMsg`, `SystemMsg`, `DataBlock`, and Pydantic serialization directly; stored 1.x dictionaries are normalized only while loading.

**Tech Stack:** Python 3.11, AgentScope 2.0.4, Pydantic 2, SQLAlchemy, pytest, uv

## Global Constraints

- Pin exactly `agentscope==2.0.4`; do not use 2.0.5dev-only APIs.
- Do not build an AgentScope 1.x runtime compatibility facade.
- Preserve readable 1.x persisted conversations; write only 2.0 dictionaries.
- Preserve the current database schema and session behavior.
- Use TDD and commit only files named by each task.

---

## File map

- `pyproject.toml`, `uv.lock`: establish the 2.0.4 runtime.
- `src/agent/chat_history.py`: construct 2.0 messages and own legacy normalization.
- `src/storage/repositories.py`: persist `model_dump(mode="json")` dictionaries.
- `tests/test_msg_serialization.py`: verify 2.0 blocks and old-record conversion.
- `tests/test_chat_history.py`: verify memory/database behavior and mixed-version sessions.

### Task 1: Lock the AgentScope runtime

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces: an environment where `agentscope.__version__ == "2.0.4"` and Python remains `>=3.11,<3.12`.

- [ ] **Step 1: Add a version assertion test command**

Run: `uv run python -c "import agentscope; assert agentscope.__version__ == '2.0.4', agentscope.__version__"`

Expected before the edit: FAIL and print the installed 1.x version.

- [ ] **Step 2: Pin the dependency**

Replace the AgentScope dependency with:

```toml
"agentscope==2.0.4",
```

- [ ] **Step 3: Re-resolve and synchronize**

Run: `uv lock --upgrade-package agentscope`

Expected: `uv.lock` resolves AgentScope 2.0.4.

Run: `uv sync --group dev`

Expected: AgentScope 2.0.4 is installed without changing the Python constraint.

- [ ] **Step 4: Verify the exact version**

Run: `uv run python -c "import agentscope; assert agentscope.__version__ == '2.0.4'"`

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: pin agentscope 2.0.4"
```

### Task 2: Replace message serialization tests with the 2.0 contract

**Files:**
- Modify: `tests/test_msg_serialization.py`

**Interfaces:**
- Consumes: AgentScope 2.0.4 message factories.
- Produces: executable requirements for `serialize_message(data: Msg) -> dict` and `deserialize_message(data: dict) -> Msg` in `src.agent.chat_history`.

- [ ] **Step 1: Replace 1.x fixtures with explicit 2.0 and legacy cases**

```python
from agentscope.message import Base64Source, DataBlock, TextBlock, UserMsg
from src.agent.chat_history import deserialize_message, serialize_message

def test_2x_multimodal_round_trip():
    original = UserMsg(
        name="User",
        content=[
            TextBlock(text="检查图片"),
            DataBlock(source=Base64Source(data="aW1n", media_type="image/png")),
        ],
        metadata={"source": "ui"},
    )
    restored = deserialize_message(serialize_message(original))
    assert restored.model_dump(mode="json") == original.model_dump(mode="json")

def test_legacy_image_is_loaded_as_data_block():
    restored = deserialize_message({
        "name": "User", "role": "user", "content": [
            {"type": "image", "source": {
                "type": "url", "url": "file:///data/a.png", "media_type": "image/png"
            }}
        ]
    })
    assert restored.content[0].type == "data"

def test_legacy_string_content_is_wrapped():
    restored = deserialize_message({"name": "User", "role": "user", "content": "你好"})
    assert restored.get_text_content() == "你好"
```

- [ ] **Step 2: Run the focused tests and observe the missing boundary functions**

Run: `uv run pytest tests/test_msg_serialization.py -q`

Expected: FAIL because `serialize_message` and `deserialize_message` are not defined.

- [ ] **Step 3: Add invalid-record and 2.0 tool-block cases**

Add assertions that `ToolCallBlock(input='{"x": 1}', state="finished")` survives a 2.0 round trip, unknown legacy blocks become `TextBlock` containing their JSON, and the returned metadata contains a non-empty `migration_warnings` list for lossy conversion.

- [ ] **Step 4: Run the focused tests again**

Run: `uv run pytest tests/test_msg_serialization.py -q`

Expected: FAIL only at the unimplemented serialization boundary.

- [ ] **Step 5: Commit the red tests**

```bash
git add tests/test_msg_serialization.py
git commit -m "test: define agentscope 2 message contract"
```

### Task 3: Implement the 2.0 serialization boundary

**Files:**
- Modify: `src/agent/chat_history.py`
- Modify: `src/storage/repositories.py`
- Test: `tests/test_msg_serialization.py`

**Interfaces:**
- Produces: `serialize_message(msg: Msg) -> dict[str, Any]` and `deserialize_message(data: dict[str, Any]) -> Msg`.

- [ ] **Step 1: Import the 2.0 message types and define factories by role**

```python
from agentscope.message import (
    AssistantMsg, Base64Source, DataBlock, Msg, SystemMsg, TextBlock,
    ToolCallBlock, URLSource, UserMsg,
)

_MESSAGE_FACTORIES = {
    "user": UserMsg,
    "assistant": AssistantMsg,
    "system": SystemMsg,
}

def serialize_message(msg: Msg) -> dict[str, Any]:
    return msg.model_dump(mode="json")
```

- [ ] **Step 2: Normalize legacy content before Pydantic validation**

Implement `deserialize_message` so string content becomes one `TextBlock`, `image`/`audio`/`video` types become `data`, legacy tool-use dictionaries become `ToolCallBlock`, and unrecognized blocks become JSON text plus a `migration_warnings` metadata entry. Preserve `id`, `created_at` or legacy `timestamp`, `finished_at`, `name`, and metadata.

Use the factory signature exactly:

```python
return factory(
    name=normalized["name"],
    content=blocks,
    metadata=metadata,
    created_at=normalized.get("created_at") or normalized.get("timestamp"),
    finished_at=normalized.get("finished_at"),
    id=normalized.get("id"),
)
```

- [ ] **Step 3: Replace repository serialization calls**

In `ChatHistoryRepository.add_message`, replace `to_dict()`/manual object conversion with:

```python
msg_dict = msg.model_dump(mode="json")
extra_data = json.dumps(msg_dict, ensure_ascii=False)
```

Keep the existing columns, title generation, and transaction boundaries unchanged.

- [ ] **Step 4: Run serialization tests**

Run: `uv run pytest tests/test_msg_serialization.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/chat_history.py src/storage/repositories.py tests/test_msg_serialization.py
git commit -m "feat: migrate message persistence to agentscope 2"
```

### Task 4: Migrate ChatHistory construction and mixed-version loading

**Files:**
- Modify: `src/agent/chat_history.py`
- Modify: `tests/test_chat_history.py`

**Interfaces:**
- Consumes: `serialize_message` and `deserialize_message` from Task 3.
- Produces: unchanged `ChatHistory` public methods returning 2.0 `Msg` objects.

- [ ] **Step 1: Add mixed-session tests**

```python
def test_load_session_with_legacy_and_2x_records(repository):
    session_id = repository.create_session()
    repository._database.execute_for_test(session_id, [
        {"name": "User", "role": "user", "content": "旧消息"},
        UserMsg(name="User", content="新消息").model_dump(mode="json"),
    ])
    history = ChatHistory.create_from_session(session_id, repository)
    assert [m.get_text_content() for m in history.get_messages()] == ["旧消息", "新消息"]
```

Adapt fixture insertion to the repository's existing database fixture rather than adding production-only test hooks.

- [ ] **Step 2: Run the focused test**

Run: `uv run pytest tests/test_chat_history.py -q`

Expected: FAIL where `Msg.from_dict`, `Msg.to_dict`, or `Msg(name="User", role="user", content="text")` is still used.

- [ ] **Step 3: Replace construction and loading**

Use `UserMsg`, `AssistantMsg`, or `SystemMsg` in `add_message`; use `serialize_message` in `to_dict_list`; use `deserialize_message` per record in `load_from_repository`. Keep per-record exception logging so one malformed row does not block the session.

- [ ] **Step 4: Verify both message suites**

Run: `uv run pytest tests/test_msg_serialization.py tests/test_chat_history.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/chat_history.py tests/test_chat_history.py
git commit -m "feat: load legacy history into agentscope 2 messages"
```

### Task 5: Phase gate

**Files:**
- Verify only

**Interfaces:**
- Produces: a stable message/history foundation for plan 02.

- [ ] **Step 1: Run relevant integration tests**

Run: `uv run pytest tests/test_msg_serialization.py tests/test_chat_history.py tests/test_storage.py -q`

Expected: PASS.

- [ ] **Step 2: Check new writes**

Run: `uv run python -c "from agentscope.message import UserMsg; from src.agent.chat_history import serialize_message; d=serialize_message(UserMsg(name='User', content='x')); assert isinstance(d['content'], list) and d['content'][0]['type']=='text'"`

Expected: exit 0.

- [ ] **Step 3: Scan runtime message APIs**

Run: `rg -n "Msg\.from_dict|\.to_dict\(\)|ImageBlock|AudioBlock|VideoBlock" src/agent/chat_history.py src/storage/repositories.py`

Expected: no matches.

- [ ] **Step 4: Review the phase diff**

Run: `git diff HEAD~4 -- pyproject.toml uv.lock src/agent/chat_history.py src/storage/repositories.py tests/test_msg_serialization.py tests/test_chat_history.py`

Expected: only the message/history migration described above.

- [ ] **Step 5: Record the gate**

Run: `git status --short`

Expected: no uncommitted changes in the files owned by this phase; unrelated pre-existing workspace changes may remain.
