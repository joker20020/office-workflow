# Agent Tool Timeouts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent long-running subagent tools from returning early by adding configurable 30-minute total and 10-minute service timeouts with accurate timeout reporting.

**Architecture:** Centralize positive timeout parsing in one internal helper, then use it at the three timeout boundaries: the synchronous async-wrapper, ComfyUI HTTP, and Unity MCP. Keep the public tool APIs and RAG behavior unchanged, document the environment variables, and protect each boundary with isolated tests.

**Tech Stack:** Python 3.11, asyncio, threading, aiohttp, AgentScope 1.0.17, pytest

## Global Constraints

- Do not modify RAG search, `asset_path`, image download, or local RAG image loading behavior.
- Default `AGENT_TOOL_TIMEOUT_SECONDS` to `1800` seconds.
- Default `IMAGE_REQUEST_TIMEOUT_SECONDS` to `600` seconds.
- Default `UNITY_MCP_TIMEOUT_SECONDS` to `600` seconds.
- Invalid, zero, or negative environment values must fall back to defaults without preventing plugin import.
- Preserve all public tool function signatures.
- Do not modify the real `config/.env` file.
- Preserve unrelated working-tree and index changes.

---

### Task 1: Add timeout parsing and async-wrapper regression tests

**Files:**
- Modify: `tests/test_agent_extensions_rag.py`
- Modify: `plugins/agent_extensions/__init__.py:57-88`

**Interfaces:**
- Produces: `_get_timeout_seconds(name: str, default: float) -> float`
- Consumes: environment variables read through `os.environ`
- Changes: `_run_async(coro)` uses `AGENT_TOOL_TIMEOUT_SECONDS`

- [ ] **Step 1: Write failing timeout parser tests**

Append tests that assert missing values use defaults, valid values override them, and invalid values fall back:

```python
@pytest.mark.parametrize(
    ("name", "default"),
    [
        ("AGENT_TOOL_TIMEOUT_SECONDS", 1800.0),
        ("IMAGE_REQUEST_TIMEOUT_SECONDS", 600.0),
        ("UNITY_MCP_TIMEOUT_SECONDS", 600.0),
    ],
)
def test_timeout_defaults(monkeypatch, name, default):
    monkeypatch.delenv(name, raising=False)
    assert agent_extensions._get_timeout_seconds(name, default) == default


def test_timeout_environment_override(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "42.5")
    assert agent_extensions._get_timeout_seconds(
        "AGENT_TOOL_TIMEOUT_SECONDS", 1800.0
    ) == 42.5


@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_invalid_timeout_falls_back(monkeypatch, value):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", value)
    assert agent_extensions._get_timeout_seconds(
        "AGENT_TOOL_TIMEOUT_SECONDS", 1800.0
    ) == 1800.0
```

- [ ] **Step 2: Write failing `_run_async` state tests**

Add:

```python
@pytest.mark.asyncio
async def test_run_async_reports_real_thread_timeout(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "0.01")

    async def slow_result():
        await asyncio.sleep(0.05)
        return "finished"

    result = agent_extensions._run_async(slow_result())
    await asyncio.sleep(0.06)

    assert result == "(执行超时：工具运行超过 0.01 秒)"


@pytest.mark.asyncio
async def test_run_async_distinguishes_completed_none(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "1")

    async def no_result():
        return None

    assert agent_extensions._run_async(no_result()) == "(工具执行完成但无返回结果)"
```

Add `import asyncio` to the test file.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -k "timeout or run_async" -q
```

Expected: failures because `_get_timeout_seconds` does not exist and `_run_async` still uses fixed `310` seconds and ambiguous `None` handling.

- [ ] **Step 4: Implement timeout parsing and accurate wrapper state detection**

Add near `_run_async`:

```python
def _get_timeout_seconds(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return float(default)
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = 0.0
    if value <= 0:
        _logger.warning(
            "%s 必须为正数，当前值为 %r；使用默认值 %s 秒",
            name,
            raw_value,
            default,
        )
        return float(default)
    return value
```

Replace the running-loop branch's fixed join and result checks with:

```python
        timeout = _get_timeout_seconds("AGENT_TOOL_TIMEOUT_SECONDS", 1800.0)
        t.join(timeout=timeout)
        if t.is_alive():
            return f"(执行超时：工具运行超过 {timeout:g} 秒)"
        if result[1]:
            raise result[1]
        if result[0] is None:
            return "(工具执行完成但无返回结果)"
        return result[0]
```

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the Step 3 command again.

Expected: all selected tests pass.

### Task 2: Apply service-specific timeouts

**Files:**
- Modify: `tests/test_agent_extensions_rag.py`
- Modify: `plugins/agent_extensions/__init__.py:456-466`
- Modify: `plugins/agent_extensions/__init__.py:651-656`

**Interfaces:**
- Consumes: `_get_timeout_seconds`
- Produces: configured `aiohttp.ClientTimeout` and `HttpStatefulClient` constructor arguments

- [ ] **Step 1: Write the failing ComfyUI timeout test**

Add:

```python
@pytest.mark.asyncio
async def test_text_to_image_uses_configured_timeout(
    tmp_path, fake_session, monkeypatch
):
    requester = _APIRequester(data_dir=str(tmp_path), workflow_path=None)
    fake_session.queue_bytes(b"png")
    monkeypatch.setenv("IMAGE_REQUEST_TIMEOUT_SECONDS", "12.5")

    assert await requester.text_to_image("prompt", "result.png") is True

    timeout = fake_session.requests[0][2]["timeout"]
    assert timeout.total == 12.5
```

- [ ] **Step 2: Write the failing Unity MCP timeout test**

Add:

```python
@pytest.mark.asyncio
async def test_unity_client_uses_configured_timeouts(monkeypatch):
    captured = {}

    class FakeUnityClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def connect(self):
            raise RuntimeError("stop after constructor")

    monkeypatch.setenv("UNITY_MCP_TIMEOUT_SECONDS", "15")
    monkeypatch.setattr(agent_extensions, "HttpStatefulClient", FakeUnityClient)

    result = await AgentExtensionTools()._unity_ar_async("task", "{}")

    assert "stop after constructor" in result
    assert captured["timeout"] == 15.0
    assert captured["sse_read_timeout"] == 15.0
```

- [ ] **Step 3: Run service timeout tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -k "configured_timeout or configured_timeouts" -q
```

Expected: ComfyUI receives `300`, and Unity lacks both timeout keyword arguments.

- [ ] **Step 4: Implement ComfyUI and Unity timeout propagation**

Change ComfyUI to:

```python
timeout=aiohttp.ClientTimeout(
    total=_get_timeout_seconds("IMAGE_REQUEST_TIMEOUT_SECONDS", 600.0),
),
```

Before constructing the Unity client, read:

```python
unity_timeout = _get_timeout_seconds("UNITY_MCP_TIMEOUT_SECONDS", 600.0)
```

Then pass both:

```python
timeout=unity_timeout,
sse_read_timeout=unity_timeout,
```

- [ ] **Step 5: Run service timeout tests and verify GREEN**

Run the Step 3 command again.

Expected: both selected tests pass.

### Task 3: Document and verify timeout configuration

**Files:**
- Modify: `config/.env.example`
- Test: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Documents: the three environment variables consumed by the implementation

- [ ] **Step 1: Add documented defaults**

Append:

```dotenv

# 子智能体工具总等待时间（秒，默认 30 分钟）
AGENT_TOOL_TIMEOUT_SECONDS=1800
# 单张 ComfyUI 图片请求超时（秒，默认 10 分钟）
IMAGE_REQUEST_TIMEOUT_SECONDS=600
# Unity MCP 请求及流读取超时（秒，默认 10 分钟）
UNITY_MCP_TIMEOUT_SECONDS=600
```

- [ ] **Step 2: Run the complete plugin-focused test file**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Verify syntax and scoped whitespace**

Run:

```powershell
.venv\Scripts\python.exe -m py_compile plugins\agent_extensions\__init__.py
git -c safe.directory=E:/GitHub/office-workflow diff --check -- plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py config/.env.example
```

Expected: both commands exit 0; `diff --check` prints nothing.

- [ ] **Step 4: Inspect scope and preserve unrelated state**

Run:

```powershell
git -c safe.directory=E:/GitHub/office-workflow diff -- plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py config/.env.example
git -c safe.directory=E:/GitHub/office-workflow status --short
```

Expected: this task changes only timeout code/tests/docs. Existing `backend-README.md`, generated process JSON files, system-prompt work, and sandbox index entries remain untouched.

- [ ] **Step 5: Request a read-only code review**

Ask the reviewer to verify default and override values, invalid-value fallback, accurate thread-state handling, ComfyUI/Unity propagation, and explicit exclusion of RAG image behavior.

- [ ] **Step 6: Report without staging or committing implementation files**

Report test, syntax, diff-check, and review results. Do not stage or commit implementation files unless the user explicitly requests it.
