# AgentScope 2.0 Cleanup and Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove remaining AgentScope 1.x runtime references, update documentation/tests, and prove the complete project is functionally equivalent on AgentScope 2.0.4.

**Architecture:** Static scans define the removal boundary, then focused, full, syntax, lint, and live-backend checks validate the migrated system. Existing unrelated workspace changes remain untouched.

**Tech Stack:** AgentScope 2.0.4, pytest, ruff, uv, ProcessGen HTTP API

## Global Constraints

- Runtime code contains no AgentScope 1.x agent, memory, hook, block, MCP client, skill registration, or PlanNotebook use.
- References in migration documentation and explicit legacy test fixtures are allowed.
- Preserve ProcessGen backend URL configurability; live test target is `http://192.168.1.5:8050/api/v1` only when reachable.
- Do not delete or reset unrelated dirty/staged files.
- Completion requires fresh command output, not prior test results.

---

## File map

- `src/agent/__init__.py`, module docstrings, and tests: update remaining terminology/examples.
- `README.md` or project docs only where they show obsolete runtime usage.
- All runtime/test files: static scan and regression verification.

### Task 1: Convert remaining tests and examples

**Files:**
- Modify: files returned by the static scan, excluding migration design/plan documents and intentional legacy fixture dictionaries.
- Modify: `src/agent/__init__.py`
- Modify: `src/storage/repositories.py` docstrings

**Interfaces:**
- Produces: no executable import or call to an AgentScope 1.x API.

- [ ] **Step 1: Generate the exact remaining-reference list**

Run:

```bash
rg -n "ReActAgent|InMemoryMemory|register_(instance|class)_hook|post_print|register_agent_skill|Http(Stateful|Stateless)Client|StdIOStatefulClient|ImageBlock|AudioBlock|VideoBlock|PlanNotebook|Msg\.from_dict|\.to_dict\(\)" src plugins tests README.md
```

Expected: only files missed by plans 01-04 plus explicit legacy fixture data.

- [ ] **Step 2: Replace executable examples**

Use `UserMsg(name="User", content="你好")`, `model_dump(mode="json")`, and the 2.0 Agent/Toolkit names in docstrings. Keep legacy fixture dictionaries with `"type": "image"` only where they verify historical loading.

- [ ] **Step 3: Run tests for every changed test module**

Run: `uv run pytest tests/test_agent_integration.py tests/test_chat_history.py tests/test_msg_serialization.py tests/test_streaming_hooks.py tests/test_agent_extensions_rag.py tests/test_end_to_end.py -q`

Expected: PASS.

- [ ] **Step 4: Repeat the static scan**

Expected: no runtime matches; any test match is inside an explicitly named legacy conversion fixture.

- [ ] **Step 5: Commit**

```bash
git add src/agent/__init__.py src/storage/repositories.py tests/test_agent_integration.py tests/test_chat_history.py tests/test_msg_serialization.py tests/test_streaming_hooks.py tests/test_agent_extensions_rag.py tests/test_end_to_end.py
git commit -m "chore: remove remaining agentscope 1 runtime usage"
```

### Task 2: Run syntax, import, and lint gates

**Files:**
- Modify only files that fail these checks

**Interfaces:**
- Produces: importable Python 3.11 code and a consistent dependency lock.

- [ ] **Step 1: Compile runtime and tests**

Run: `uv run python -m compileall -q src plugins tests`

Expected: exit 0.

- [ ] **Step 2: Verify important imports**

Run: `uv run python -c "from src.agent.agent_integration import AgentIntegration; from plugins.agent_extensions import AgentExtensionTools; print('imports-ok')"`

Expected: `imports-ok`.

- [ ] **Step 3: Run Ruff on migration-owned files**

Run: `uv run ruff check src/agent plugins/agent_extensions tests/test_agent_integration.py tests/test_chat_history.py tests/test_msg_serialization.py tests/test_streaming_hooks.py tests/test_agent_extensions_rag.py`

Expected: exit 0. Fix only migration-introduced findings; do not perform unrelated formatting.

- [ ] **Step 4: Verify lock consistency**

Run: `uv lock --check`

Expected: lockfile is current and resolves AgentScope 2.0.4.

- [ ] **Step 5: Commit any gate fixes**

```bash
git add src/agent plugins/agent_extensions tests/test_agent_integration.py tests/test_chat_history.py tests/test_msg_serialization.py tests/test_streaming_hooks.py tests/test_agent_extensions_rag.py
git commit -m "fix: satisfy agentscope 2 migration gates"
```

Skip the commit when no file changed.

### Task 3: Run the full automated regression suite

**Files:**
- Modify only tests or runtime code for confirmed migration regressions

**Interfaces:**
- Produces: all repository tests passing under AgentScope 2.0.4.

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q`

Expected: PASS with zero failures.

- [ ] **Step 2: Classify any failure before editing**

For each failure, rerun its exact node id with `-vv`; determine whether it is a migration regression, environment dependency, or unrelated pre-existing failure. Record the command and traceback in the task notes.

- [ ] **Step 3: Fix only confirmed migration regressions with a red-green cycle**

Add or tighten the smallest failing assertion, rerun to confirm failure, implement the minimal correction, and rerun the node id to PASS.

- [ ] **Step 4: Re-run the full suite after every correction batch**

Run: `uv run pytest -q`

Expected: PASS with zero failures.

- [ ] **Step 5: Commit confirmed regression fixes**

```bash
git add src/agent plugins/agent_extensions tests/test_agent_integration.py tests/test_chat_history.py tests/test_msg_serialization.py tests/test_streaming_hooks.py tests/test_multimodal_integration.py tests/test_agent_extensions_rag.py tests/test_end_to_end.py
git commit -m "fix: resolve agentscope 2 migration regressions"
```

Skip the commit when the first full run passes.

### Task 4: Verify the live RAG image path without database access

**Files:**
- Verify only unless a migration regression is reproduced

**Interfaces:**
- Produces: evidence that the migrated plugin downloads, overwrites, and locally loads RAG images.

- [ ] **Step 1: Check backend reachability**

Run: `uv run python -c "import urllib.request; print(urllib.request.urlopen('http://192.168.1.5:8050/api/v1/health', timeout=10).status)"`

Expected: HTTP success. If the documented health path differs, use the exact endpoint in `backend-README.md`.

- [ ] **Step 2: Run the existing live probe against the configured backend**

Set `PROCESSGEN_API_BASE_URL=http://192.168.1.5:8050/api/v1` for the process only and execute the repository's RAG asset probe/test helper. Do not store the address in source code.

Expected: asset bytes are downloaded to `data/img`, an existing sentinel file is overwritten, and the returned user message contains a local `DataBlock`.

- [ ] **Step 3: Verify no direct database module was loaded**

Run the probe with an assertion that `pymilvus`, database-specific plugin modules, and direct SQL clients are absent from `sys.modules`.

Expected: exit 0.

- [ ] **Step 4: Re-run offline RAG regression tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q`

Expected: PASS.

- [ ] **Step 5: Record environmental unavailability without changing code**

If the backend is unreachable, preserve the successful offline test output and report the live check as not executed; do not weaken or delete the live test.

### Task 5: Final acceptance and workspace audit

**Files:**
- Verify only

**Interfaces:**
- Produces: final evidence for the approved migration design.

- [ ] **Step 1: Verify dependency and APIs**

Run: `uv run python -c "import agentscope; assert agentscope.__version__ == '2.0.4'"`

Run the static old-API scan from Task 1.

Expected: version assertion passes and runtime scan is empty.

- [ ] **Step 2: Verify all critical feature suites together**

Run: `uv run pytest tests/test_msg_serialization.py tests/test_chat_history.py tests/test_agent_integration.py tests/test_streaming_hooks.py tests/test_multimodal_integration.py tests/test_agent_extensions_rag.py tests/test_end_to_end.py -q`

Expected: PASS.

- [ ] **Step 3: Run the full suite one final time**

Run: `uv run pytest -q`

Expected: PASS with zero failures.

- [ ] **Step 4: Audit changed files and unrelated work**

Run: `git status --short`

Run: `git diff --stat b366983..HEAD`

Expected: migration commits contain only intended files; unrelated pre-existing dirty/staged files remain untouched.

- [ ] **Step 5: Prepare the completion report**

Report the exact AgentScope version, commit list, focused/full test counts, live RAG result or reachability limitation, old-API scan result, and any preserved unrelated workspace changes.
