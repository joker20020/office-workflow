# AgentScope 2.0 Long-Lived Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the main Agent and stateful MCP clients on one long-lived event loop while preserving the existing synchronous and asynchronous public chat APIs.

**Architecture:** A focused `AgentAsyncRuntime` owns one background thread and event loop. `AgentIntegration` submits initialization, MCP lifecycle, replies, interruption cleanup, reset, session-state publication, and shutdown to that runtime so every AgentScope async resource remains on its owning loop.

**Tech Stack:** Python 3.11, asyncio, threading, concurrent.futures, AgentScope 2.0.4, pytest/pytest-asyncio

## Global Constraints

- Stateful MCP `connect()`, tool discovery/call, and `close()` must run on the same still-running event loop.
- Preserve public `initialize()`, `chat()`, `chat_async()`, `interrupt()`, `reset()`, session, and shutdown signatures.
- Preserve AgentScope event ordering, callback shape, partial assistant persistence, and interruption/error distinction.
- Do not create a per-chat event loop or a dedicated parked-reply loop/thread.
- Reinitialization failure must not expose an Agent/Toolkit that references closed MCP clients.
- Do not modify MCP database schema, Skill/permission filtering, UI APIs, provider defaults, or plugin subagents.
- Preserve existing user changes to `config/settings.yaml` and the 14 deleted JSON files.

---

## File map

- `src/agent/async_runtime.py`: generic thread/event-loop ownership and sync/async submission.
- `src/agent/agent_integration.py`: all AgentScope async work submitted to the runtime.
- `tests/test_agent_async_runtime.py`: runtime unit and lifecycle contracts.
- `tests/test_agent_integration.py`: MCP initialization/reinitialization/reset/shutdown contracts.
- `tests/test_streaming_hooks.py`: sync/async chat, event, active cancellation, parked cleanup, and partial-history regressions.
- `tests/test_multimodal_integration.py`, `tests/test_chat_panel.py`: unchanged behavioral gates.

### Task 1: Build the generic long-lived async runtime

**Files:**
- Create: `src/agent/async_runtime.py`
- Create: `tests/test_agent_async_runtime.py`

**Interfaces:**
- Produces: `AgentAsyncRuntime.start()`, `submit()`, `run()`, `run_async()`, `in_runtime_thread()`, `is_running`, and `stop()`.
- Consumed by: Task 2 `AgentIntegration`.

- [ ] **Step 1: Write runtime startup and same-loop failing tests**

```python
def test_runtime_runs_submissions_on_one_live_loop():
    runtime = AgentAsyncRuntime(thread_name="test-agent-runtime")

    async def identify():
        loop = asyncio.get_running_loop()
        return loop, threading.current_thread().name, loop.is_closed()

    first = runtime.run(identify())
    second = runtime.run(identify())
    assert first[0] is second[0]
    assert first[1] == second[1] == "test-agent-runtime"
    assert first[2] is second[2] is False
    runtime.stop()
```

Also test concurrent callers start exactly one thread/loop and `start()` is idempotent.

- [ ] **Step 2: Run startup tests and verify RED**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_agent_async_runtime.py -q -k "startup or submissions or concurrent"`

Expected: collection/import failure because `src.agent.async_runtime` does not exist.

- [ ] **Step 3: Implement the minimal runtime lifecycle**

```python
class AgentAsyncRuntime:
    def __init__(self, thread_name: str = "AgentAsyncRuntime") -> None:
        self._thread_name = thread_name
        self._lock = threading.Lock()
        self._started = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is None:
                self._started.clear()
                self._startup_error = None
                self._thread = threading.Thread(
                    target=self._thread_main,
                    name=self._thread_name,
                    daemon=True,
                )
                self._thread.start()
        self._started.wait()
        if self._startup_error is not None:
            raise RuntimeError("agent async runtime failed to start") from self._startup_error

    def _thread_main(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._started.set()
            loop.run_forever()
        except BaseException as error:
            self._startup_error = error
            self._started.set()
        finally:
            if self._loop is not None:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True),
                    )
                self._loop.close()
```

Use a startup error field so a thread failure unblocks callers with a clear `RuntimeError`.

- [ ] **Step 4: Add submission, error, async bridge, and self-deadlock tests**

```python
@pytest.mark.asyncio
async def test_run_async_bridges_without_moving_coroutine_to_caller_loop():
    caller_loop = asyncio.get_running_loop()
    runtime_loop = await runtime.run_async(current_loop())
    assert runtime_loop is not caller_loop

def test_run_from_runtime_thread_raises_instead_of_deadlocking():
    async def invoke_sync_wait():
        with pytest.raises(RuntimeError, match="runtime thread"):
            runtime.run(asyncio.sleep(0))
    runtime.run(invoke_sync_wait())
```

Also assert coroutine exceptions propagate through `run()`/`run_async()` and submission after stop fails explicitly.

- [ ] **Step 5: Implement submission APIs**

```python
def submit(self, awaitable: Awaitable[T]) -> concurrent.futures.Future[T]:
    self.start()
    if self.in_runtime_thread():
        raise RuntimeError("cannot submit synchronously from the runtime thread")
    return asyncio.run_coroutine_threadsafe(_await_value(awaitable), self._loop)

def run(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
    return self.submit(awaitable).result(timeout=timeout)

async def run_async(self, awaitable: Awaitable[T]) -> T:
    if self.in_runtime_thread():
        return await awaitable
    return await asyncio.wrap_future(self.submit(awaitable))
```

Close an unsubmitted coroutine before raising to avoid un-awaited coroutine warnings.

- [ ] **Step 6: Add stop/cleanup/idempotence tests**

Assert an optional cleanup awaitable executes on the runtime loop before stop, pending tasks are cancelled, thread terminates, loop closes, and repeated `stop()` is safe. Assert stop called from the runtime thread raises clearly rather than joining itself.

- [ ] **Step 7: Implement `stop()` and verify Task 1**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_agent_async_runtime.py -q`

Expected: PASS with no surviving runtime thread or un-awaited coroutine warnings.

- [ ] **Step 8: Commit**

```powershell
git add src/agent/async_runtime.py tests/test_agent_async_runtime.py
git commit -m "feat: add long-lived agent async runtime"
```

### Task 2: Move Agent, MCP, replies, and cleanup onto the runtime

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`
- Modify: `tests/test_streaming_hooks.py`
- Test: `tests/test_agent_async_runtime.py`

**Interfaces:**
- Consumes: `AgentAsyncRuntime` from Task 1.
- Produces: one-loop Agent/MCP runtime behind unchanged public APIs.

- [ ] **Step 1: Add a loop-sensitive MCP RED contract**

Create a fake stateful client that records the running loop in `connect()`, `list_tools()`/a simulated tool operation, and `close()`. Initialize the integration, execute one sync chat and one async chat, then shutdown. Assert every recorded loop is the same object and was open during each operation.

```python
assert client.connect_loop is client.tool_loop is client.close_loop
assert client.connect_loop is agent._async_runtime.run(current_loop())
```

The test obtains the runtime loop through a submitted coroutine; no loop property is added to production.

- [ ] **Step 2: Add reinitialization-state RED contracts**

Test these exact outcomes:

- validation failure before destructive replacement preserves the existing working runtime;
- after replacement starts, Toolkit/model/Agent failure closes newly connected clients and publishes `_initialized=False`, `_agent=None`, `_toolkit=None`, `_mcp_clients=[]`;
- successful reinitialize closes old clients on their original runtime loop before publishing replacements;
- server iteration/factory failure cannot strand already connected local clients.

- [ ] **Step 3: Run MCP/runtime RED tests**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_agent_integration.py tests/test_streaming_hooks.py -q -k "runtime_loop or loop_sensitive or reinitialize or initialization_failure"`

Expected: FAIL because current code connects on a temporary loop and sync chat creates another temporary loop.

- [ ] **Step 4: Add runtime ownership and atomic initialization**

In `__init__` create one `AgentAsyncRuntime`. Replace the temporary MCP bridge with async lifecycle methods:

```python
async def _connect_mcp_clients_async(self) -> list[MCPClient]:
    clients: list[MCPClient] = []
    try:
        for server in self._enabled_mcp_records():
            client = self._mcp_manager.create_agentscope_client(server["name"])
            if client is None:
                continue
            if client.is_stateful:
                await client.connect()
            clients.append(client)
        return clients
    except BaseException:
        await self._close_client_list_async(clients)
        raise
```

Per-server factory/connect errors remain isolated and named; function-level failures close the local list before re-raising.

Publish Agent/Toolkit/client state only after complete construction. Clear partial replacement state on failure. Do not close a working old runtime until provider/API configuration validation succeeds.

- [ ] **Step 5: Route both chat APIs through one async implementation**

```python
async def _chat_impl(
    self,
    message: str | list[dict[str, Any]],
    *,
    timeout_as_request_timeout: bool,
) -> str:
    if not self._initialized or self._agent is None:
        return "Agent未初始化，请先配置API密钥"
    msg = self._create_user_message(message)
    self._history.add_message(msg=msg)
    try:
        response_msg = await self._run_owned_reply_stream(msg)
        self._history.add_message(msg=response_msg)
        return (response_msg.get_text_content() or "").strip()
    except _ReplyStreamError as error:
        self._history.add_message(msg=error.reply)
        if timeout_as_request_timeout and isinstance(error.cause, asyncio.TimeoutError):
            return "请求超时，请检查网络连接或API配置"
        return f"错误: {error.cause}"
    except asyncio.TimeoutError:
        if timeout_as_request_timeout:
            return "请求超时，请检查网络连接或API配置"
        return "错误: " + str(asyncio.TimeoutError())
    except Exception as error:
        return f"错误: {error}"

def chat(self, message):
    return self._async_runtime.run(
        self._chat_impl(message, timeout_as_request_timeout=True),
    )

async def chat_async(self, message):
    return await self._async_runtime.run_async(
        self._chat_impl(message, timeout_as_request_timeout=False),
    )
```

Remove per-chat `asyncio.new_event_loop()`. Preserve all existing return strings and callback/event order.

- [ ] **Step 6: Simplify active and parked interruption for one runtime**

Keep active-task cancellation reservation, but use only the runtime loop. Parked cleanup is submitted to `AgentAsyncRuntime` with one future reservation and sends exactly `UserInterruptEvent(reply_id=...)`.

Delete `_parked_reply_loop`, `_parked_reply_loop_thread`, retain/handoff helpers, and their obsolete tests. Replace them with tests proving:

- active repeated/concurrent interrupt schedules one cancel;
- real cancellation yields interrupted terminal event and persists partial reply once;
- parked repeated/concurrent interrupt schedules one cleanup;
- failed/cancelled parked cleanup releases reservation and can retry;
- reset/shutdown racing cleanup leaves no future and does not stop the shared runtime prematurely.

- [ ] **Step 7: Move reset, session state, and shutdown onto the runtime**

Implement async cleanup ordering:

```python
async def _reset_runtime_async(self) -> None:
    await self._cancel_or_cleanup_reply_async()
    await self._close_mcp_clients_async()
    self._agent = None
    self._toolkit = None
    self._initialized = False

def reset(self) -> None:
    self._async_runtime.run(self._reset_runtime_async())
    self._history.clear()
```

`switch_session()` publishes a fresh `AgentState` through the runtime after repository selection succeeds. `shutdown()` calls `AgentAsyncRuntime.stop(cleanup_awaitable)` so Agent/MCP cleanup happens before loop stop and thread join. Repeated reset/shutdown remains safe.

- [ ] **Step 8: Run focused GREEN suites**

Run:

```powershell
$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path
uv run pytest tests/test_agent_async_runtime.py tests/test_agent_integration.py tests/test_streaming_hooks.py -q
```

Expected: PASS; no leaked thread/loop warnings.

- [ ] **Step 9: Run the phase regression gate and static scans**

Run:

```powershell
$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path
uv run pytest tests/test_agent_integration.py tests/test_streaming_hooks.py tests/test_multimodal_integration.py tests/test_chat_panel.py tests/test_end_to_end.py -q
rg -n "_run_mcp_awaitable|asyncio\.new_event_loop\(\)|_parked_reply_loop|_parked_reply_loop_thread|HttpStatelessClient|StdIOStatefulClient|register_mcp_client" src/agent/agent_integration.py
git diff --check
```

Expected: tests PASS; scan has no runtime matches in `agent_integration.py`; diff check clean.

- [ ] **Step 10: Commit**

```powershell
git add src/agent/agent_integration.py tests/test_agent_integration.py tests/test_streaming_hooks.py
git commit -m "fix: run agent and mcp on one async runtime"
```
