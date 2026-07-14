# AgentScope 2.0 Exposure Filtering and Automatic Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter AgentScope Toolkit exposure through project permissions and enabled managers, then automatically rebuild the initialized main assistant whenever exposure changes.

**Architecture:** A reusable thread-safe notifier publishes successful exposure mutations. Registry entries carry plugin-owner metadata, `AgentIntegration` constructs one filtered Toolkit and BYPASS AgentState on its long-lived runtime, and one coalescing rebuild controller preserves AgentState while serializing MCP replacement through the existing lifecycle lock.

**Tech Stack:** Python 3.11, AgentScope 2.0.4 `Toolkit`/`AgentState`/`PermissionMode`, asyncio, threading, SQLAlchemy managers, pytest

## Global Constraints

- Only project-authorized plugin tools, enabled MCP servers, and enabled valid Skills enter the main assistant Toolkit.
- Permission revocation and registry/MCP/Skill changes update an initialized assistant without application restart.
- Set `PermissionMode.BYPASS` only after project filtering and complete Toolkit construction.
- Preserve AgentState context and session id across successful rebuilds.
- Use the reviewed long-lived runtime, lifecycle lock, and exact-list cancellation-safe MCP drain.
- Never implicitly add Bash, Read, Write, Edit, Glob, Grep, arbitrary shell, or arbitrary filesystem tools.
- Keep current database schema, UI dictionary/return contracts, provider defaults, tool execution timeouts, plugin subagents, and main-assistant-only Skill scope.
- Existing callers without a PermissionManager and legacy registry calls without owner metadata remain compatible.
- Preserve the user's `config/settings.yaml` modification and deleted JSON files.

---

## File map

- `src/core/change_notifier.py`: generic immutable exposure events and listener isolation.
- `src/agent/tool_registry.py`: owner-aware immutable tool-group snapshots and tool change events.
- `src/agent/mcp_server_manager.py`: publish successful MCP mutations.
- `src/agent/skill_manager.py`: publish successful Skill mutations.
- `src/core/permission_manager.py`: publish actual grant/revoke changes.
- `src/core/permission_proxy.py`: pass plugin identity to registry ownership metadata.
- `src/agent/agent_integration.py`: permission filtering, BYPASS state, transactional rebuild, subscriptions, and coalescing.
- `src/ui/main_window.py`: pass the initialized production PermissionManager.
- `tests/test_change_notifier.py`: notification concurrency/isolation contracts.
- `tests/test_agent_integration.py`: filtering, BYPASS, rebuild, lifecycle, and coalescing contracts.
- `tests/test_permission_manager.py`, `tests/test_permission_proxy.py`: permission/owner event behavior.
- `tests/test_end_to_end.py`, `tests/test_chat_panel.py`: compatibility and regression gates.

### Task 1: Add exposure change notifications to mutable managers

**Files:**
- Create: `src/core/change_notifier.py`
- Create: `tests/test_change_notifier.py`
- Modify: `src/agent/mcp_server_manager.py`
- Modify: `src/agent/skill_manager.py`
- Modify: `src/core/permission_manager.py`
- Modify: `tests/test_agent_integration.py`
- Modify: `tests/test_permission_manager.py`

**Interfaces:**
- Produces: `ExposureChange`, `ChangeNotifier.subscribe()`, `unsubscribe()`, `notify()`.
- Produces on each manager: `subscribe_changes(callback) -> int`, `unsubscribe_changes(token) -> None`.
- Consumed by: Tasks 2 and 4.

- [ ] **Step 1: Write notifier RED tests**

Create tests with this public contract:

```python
from src.core.change_notifier import ChangeNotifier, ExposureChange

def test_notifier_snapshots_and_isolates_callbacks():
    notifier = ChangeNotifier("skills")
    seen = []
    second_token = None

    def first(event):
        seen.append(("first", event))
        notifier.unsubscribe(second_token)
        raise RuntimeError("listener exploded")

    def second(event):
        seen.append(("second", event))

    notifier.subscribe(first)
    second_token = notifier.subscribe(second)
    event = ExposureChange(source="skills", action="enabled", name="drawing")
    notifier.notify(action="enabled", name="drawing")

    assert seen == [("first", event), ("second", event)]
    notifier.notify(action="enabled", name="drawing")
    assert seen[-1] == ("first", event)
```

Also assert tokens are unique positive integers, repeated unsubscribe is safe, callbacks run outside the notifier lock by subscribing/unsubscribing from a callback, and one callback failure is logged without escaping `notify()`.

- [ ] **Step 2: Run notifier tests and verify RED**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_change_notifier.py -q`

Expected: collection failure because `src.core.change_notifier` does not exist.

- [ ] **Step 3: Implement the notifier**

```python
from dataclasses import dataclass
import threading
from typing import Callable

@dataclass(frozen=True, slots=True)
class ExposureChange:
    source: str
    action: str
    name: str | None = None

ChangeCallback = Callable[[ExposureChange], None]

class ChangeNotifier:
    def __init__(self, source: str) -> None:
        self._source = source
        self._lock = threading.Lock()
        self._next_token = 1
        self._callbacks: dict[int, ChangeCallback] = {}

    def subscribe(self, callback: ChangeCallback) -> int:
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._callbacks[token] = callback
            return token

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            self._callbacks.pop(token, None)

    def notify(self, *, action: str, name: str | None = None) -> None:
        event = ExposureChange(self._source, action, name)
        with self._lock:
            callbacks = list(self._callbacks.values())
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                _logger.exception(
                    "Exposure change listener failed: %s/%s/%s",
                    event.source,
                    event.action,
                    event.name,
                )
```

Use only the exact keyword signature `notify(*, action: str, name: str | None = None) -> None`; it constructs the immutable event with the notifier's source. Do not overload it with event-object input and do not expose the callback dictionary.

- [ ] **Step 4: Write manager publisher RED tests**

For MCP and Skill managers, subscribe a list appender and assert successful add/update/delete/enable transitions emit exactly one event after commit. Assert duplicate add, missing delete/update, and setting an already-current enabled value emit none. For `discover_and_register`, assert each new Skill emits only its successful `add_skill` event and there is no aggregate duplicate.

For PermissionManager:

```python
def test_permission_notifications_only_report_actual_changes():
    manager = PermissionManager()
    events = []
    token = manager.subscribe_changes(events.append)

    manager.grant("agent_extensions", Permission.AGENT_TOOL)
    manager.grant("agent_extensions", Permission.AGENT_TOOL)
    assert manager.revoke("agent_extensions", Permission.AGENT_TOOL) is True
    assert manager.revoke("agent_extensions", Permission.AGENT_TOOL) is False
    manager.unsubscribe_changes(token)

    assert [(e.action, e.name) for e in events] == [
        ("granted", "agent_extensions"),
        ("revoked", "agent_extensions"),
    ]
```

Cover `grant_all` with a mixed already/new set and `revoke_all` only when a plugin actually had permissions.

- [ ] **Step 5: Run publisher tests and verify RED**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_change_notifier.py tests/test_permission_manager.py tests/test_agent_integration.py -q -k "change or notification or notify"`

Expected: FAIL because managers do not expose subscription APIs or publish events.

- [ ] **Step 6: Integrate notifiers after successful mutations**

Each manager owns `ChangeNotifier(<source>)`, delegates `subscribe_changes`/`unsubscribe_changes`, computes whether a real state change occurred, commits the database mutation, exits its SQLAlchemy `Session` block, and only then calls `notify`. Use exact sources `"mcp"`, `"skills"`, and `"permissions"`; use action names `"added"`, `"updated"`, `"deleted"`, `"enabled"`, `"disabled"`, `"granted"`, and `"revoked"`.

Do not notify from failed/no-op operations. Preserve every existing return value and exception.

- [ ] **Step 7: Verify Task 1**

Run:

```powershell
$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path
uv run pytest tests/test_change_notifier.py tests/test_permission_manager.py tests/test_agent_integration.py -q -k "change or notification or notify or set_enabled or add_skill or mcp"
git diff --check
```

Expected: PASS; no listener exception escapes; diff check clean.

- [ ] **Step 8: Commit**

```powershell
git add src/core/change_notifier.py src/agent/mcp_server_manager.py src/agent/skill_manager.py src/core/permission_manager.py tests/test_change_notifier.py tests/test_permission_manager.py tests/test_agent_integration.py
git commit -m "feat: publish agent exposure changes"
```

### Task 2: Track plugin tool ownership and filter unauthorized groups

**Files:**
- Modify: `src/agent/tool_registry.py`
- Modify: `src/core/permission_proxy.py`
- Modify: `src/agent/agent_integration.py`
- Modify: `src/ui/main_window.py`
- Modify: `tests/test_agent_integration.py`
- Modify: `tests/test_permission_proxy.py`

**Interfaces:**
- Consumes: `ChangeNotifier` and `ExposureChange` from Task 1.
- Produces: `ToolGroupSnapshot`, `AgentToolRegistry.get_group_snapshots()`.
- Produces: optional `permission_manager` argument on `AgentIntegration`.
- Consumed by: Tasks 3 and 4.

- [ ] **Step 1: Add owner metadata and snapshot RED tests**

```python
def test_guarded_registry_records_plugin_owner(permission_manager):
    registry = AgentToolRegistry()
    guarded = GuardedToolRegistry(
        registry,
        {Permission.AGENT_TOOL},
        "workflow_tools",
    )
    guarded.register("workflow", [first_tool])

    snapshot = registry.get_group_snapshots()
    assert snapshot == [
        ToolGroupSnapshot(
            group_name="workflow",
            owner_name="workflow_tools",
            tools=(first_tool,),
        ),
    ]
```

Assert legacy `registry.register("core", [tool])` produces `owner_name is None`, returned tool tuples cannot mutate registry storage, register/unregister publish one `source="tools"` event, and overwriting a group updates owner metadata atomically.

- [ ] **Step 2: Run registry tests and verify RED**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_permission_proxy.py tests/test_agent_integration.py -q -k "owner or snapshot or guarded_registry"`

Expected: FAIL because registry entries contain no owner metadata or snapshots.

- [ ] **Step 3: Implement owner-aware registry**

```python
@dataclass(frozen=True, slots=True)
class ToolGroupSnapshot:
    group_name: str
    owner_name: str | None
    tools: tuple[Callable, ...]

def register(
    self,
    group_name: str,
    tools: list[Callable],
    *,
    owner_name: str | None = None,
) -> None:
    self._tools[group_name] = list(tools)
    self._owners[group_name] = owner_name
    self._change_notifier.notify(action="registered", name=group_name)

def get_group_snapshots(self) -> list[ToolGroupSnapshot]:
    return [
        ToolGroupSnapshot(name, self._owners.get(name), tuple(tools))
        for name, tools in self._tools.items()
    ]
```

Unregister removes tools and owner together and notifies only if the group existed. Existing `get_all_tools`, group names, and testing reset remain compatible. `GuardedToolRegistry.register` calls the new signature with `owner_name=self._plugin_name` after its existing permission check.

- [ ] **Step 4: Add permission-aware FunctionTool RED tests**

Register:

- owner `allowed_plugin` with `Permission.AGENT_TOOL`;
- owner `denied_plugin` without it;
- an ownerless trusted group;
- the same callable in allowed and trusted groups;
- functions named `Bash`, `Read`, `Write`, `Edit`, `Glob`, and `Grep` nowhere in the registry.

Assert `_build_registry_function_tools()` returns allowed + trusted callables in stable order, wraps duplicate identity once, excludes denied owner, and adds none of the forbidden names.

- [ ] **Step 5: Implement filtering and production injection**

Add an optional constructor parameter:

```python
permission_manager: Optional["PermissionManager"] = None
```

Store it and filter snapshots:

```python
for group in AgentToolRegistry.instance().get_group_snapshots():
    if (
        group.owner_name is not None
        and self._permission_manager is not None
        and not self._permission_manager.check(
            group.owner_name,
            Permission.AGENT_TOOL,
        )
    ):
        continue
    for tool_func in group.tools:
        if id(tool_func) in seen_ids:
            continue
        seen_ids.add(id(tool_func))
        function_tools.append(
            FunctionTool(func=tool_func, is_concurrency_safe=False),
        )
```

Import project `Permission` separately from AgentScope permission types. In `MainWindow`, pass `self._app_context.permission_manager` when AppContext exists and is initialized; otherwise pass `None` to preserve isolated UI construction.

- [ ] **Step 6: Verify Task 2**

Run:

```powershell
$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path
uv run pytest tests/test_permission_proxy.py tests/test_agent_integration.py -q -k "owner or permission or registry or forbidden"
uv run pytest tests/test_permission_manager.py tests/test_permission_proxy.py -q
git diff --check
```

Expected: PASS; denied owned tools absent; ownerless tools compatible.

- [ ] **Step 7: Commit**

```powershell
git add src/agent/tool_registry.py src/core/permission_proxy.py src/agent/agent_integration.py src/ui/main_window.py tests/test_agent_integration.py tests/test_permission_proxy.py
git commit -m "feat: filter agent tools by plugin owner"
```

### Task 3: Build BYPASS state and one state-preserving rebuild transaction

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`
- Modify: `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: permission-filtered registry snapshots from Task 2.
- Produces: `_rebuild_agent_runtime() -> bool` and `_rebuild_agent_runtime_impl() -> bool`.
- Consumed by: Task 4 automatic change callbacks.

- [ ] **Step 1: Add BYPASS ordering RED tests**

Patch `Toolkit` and `Agent` with recording fakes. Assert Toolkit receives the complete filtered `tools`, enabled `mcps`, and validated `skills_or_loaders` before Agent construction. Assert the state passed to Agent has:

```python
assert state.permission_context.mode is PermissionMode.BYPASS
```

Assert a Toolkit constructor failure publishes no Agent/Toolkit/BYPASS state and drains connected local MCP clients.

- [ ] **Step 2: Run BYPASS tests and verify RED**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_agent_integration.py -q -k "bypass or filtered_toolkit"`

Expected: FAIL because state remains `PermissionMode.DEFAULT` and no unified builder exists.

- [ ] **Step 3: Factor filtered construction and set BYPASS after filtering**

Import:

```python
from agentscope.permission import PermissionMode
```

Create one helper used by initialize and rebuild:

```python
async def _construct_agent_runtime(
    self,
    *,
    provider: str,
    model_name: str,
    base_url: str,
    api_key: str,
    state_seed: AgentState | None,
) -> tuple[Any, Toolkit, list[MCPClient]]:
    local_clients: list[MCPClient] = []
    try:
        function_tools = self._build_registry_function_tools()
        local_clients = await self._connect_mcp_clients()
        skill_paths = (
            self._skill_manager.get_enabled_skill_paths()
            if self._skill_manager is not None
            else []
        )
        toolkit = Toolkit(
            tools=function_tools,
            mcps=local_clients,
            skills_or_loaders=skill_paths,
        )
        state = (
            state_seed.model_copy(deep=True)
            if state_seed is not None
            else AgentState(context=self._history.get_messages())
        )
        state.permission_context.mode = PermissionMode.BYPASS
        agent = Agent(
            name="WorkflowAssistant",
            system_prompt=self._system_prompt(),
            model=self._create_model(provider, model_name, base_url, api_key),
            toolkit=toolkit,
            state=state,
            react_config=ReActConfig(
                max_iters=50,
                interruption_raise_cancelled_error=False,
            ),
        )
        return agent, toolkit, local_clients
    except BaseException:
        await self._close_mcp_clients_cancellation_safe(local_clients)
        raise
```

Keep existing original-error precedence and per-server cleanup semantics. Extract `_system_prompt()` without changing its configured/default text.

- [ ] **Step 4: Add successful rebuild RED tests**

Initialize with an AgentState containing a fixed `session_id`, summary, and context. Change the authorized registry exposure, call `_rebuild_agent_runtime()`, and assert:

- it returns `True`;
- old stateful clients close on the original runtime loop before replacement publication;
- new Toolkit reflects the changed exposure;
- replacement AgentState preserves session id, summary, and context values;
- replacement state is a distinct deep-copied object;
- permission mode is BYPASS;
- no raw API key is stored in integration fields.

Add failure coverage: missing current provider/key fails before destructive replacement and preserves the old working runtime; constructor failure after destructive replacement drains local clients and publishes exact empty/uninitialized state.

- [ ] **Step 5: Implement the single rebuild controller**

```python
def _rebuild_agent_runtime(self) -> bool:
    self._reject_sync_lifecycle_reentry("_rebuild_agent_runtime")
    if not self._initialized or self._agent is None:
        return False
    try:
        api_key = self._api_manager.get_key(self._provider, self._model_name)
        if not api_key:
            return False
        return self._async_runtime.run(
            self._rebuild_agent_runtime_impl(api_key=api_key),
        )
    except Exception:
        _logger.exception("Agent exposure rebuild failed")
        return False

async def _rebuild_agent_runtime_impl(self, *, api_key: str) -> bool:
    async with self._get_lifecycle_lock():
        if not self._initialized or self._agent is None:
            return False
        state_seed = self._agent.state.model_copy(deep=True)
        await self._settle_reply_work()
        await self._close_published_mcp_clients()
        agent, toolkit, clients = await self._construct_agent_runtime(
            provider=self._provider,
            model_name=self._model_name,
            base_url=self._base_url,
            api_key=api_key,
            state_seed=state_seed,
        )
        self._agent = agent
        self._toolkit = toolkit
        self._mcp_clients = clients
        self._initialized = True
        return True
```

Use the same atomic publication helper for normal initialization so construction logic is not duplicated. If construction fails after old detach, explicitly retain empty state and re-raise to the sync controller.

- [ ] **Step 6: Verify Task 3**

Run:

```powershell
$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path
uv run pytest tests/test_agent_integration.py tests/test_end_to_end.py -q -k "bypass or rebuild or filtered or state"
uv run pytest tests/test_agent_async_runtime.py tests/test_agent_integration.py tests/test_streaming_hooks.py -q
git diff --check
```

Expected: PASS; state/session preserved; lifecycle regressions green.

- [ ] **Step 7: Commit**

```powershell
git add src/agent/agent_integration.py tests/test_agent_integration.py tests/test_end_to_end.py
git commit -m "feat: rebuild filtered agentscope runtime"
```

### Task 4: Subscribe, coalesce automatic rebuilds, and run the phase gate

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`
- Test: `tests/test_change_notifier.py`
- Test: `tests/test_permission_manager.py`
- Test: `tests/test_permission_proxy.py`
- Test: `tests/test_end_to_end.py`
- Test: `tests/test_multimodal_integration.py`
- Test: `tests/test_chat_panel.py`

**Interfaces:**
- Consumes: manager/registry notifications from Tasks 1–2 and rebuild transaction from Task 3.
- Produces: automatic convergence and terminal listener cleanup.

- [ ] **Step 1: Add pre-initialization and external-thread RED tests**

Assert a tool/MCP/Skill/permission change before initialization does not start `AgentAsyncRuntime` and the next initialize sees the latest exposure. After initialization, mutate each source and assert the manager call does not return until the replacement Toolkit reflects the change.

For permission flow, revoke `AGENT_TOOL` from an owned registered group and assert it disappears; grant again and assert it reappears without re-registering.

- [ ] **Step 2: Add coalescing/runtime-thread/shutdown RED tests**

Use gates to hold one rebuild inside `_construct_agent_runtime`, then publish multiple changes concurrently. Assert:

- only one rebuild transaction runs at a time;
- one additional pass observes all changes made during the first pass;
- external notification callers wait for the drain to become idle;
- a notification emitted on the runtime thread schedules an asyncio task and never calls synchronous `runtime.run()`;
- no current runtime task waits on itself;
- shutdown removes every subscription before stopping the runtime;
- post-shutdown mutations schedule nothing and leave no task/future/thread.

- [ ] **Step 3: Run automatic rebuild tests and verify RED**

Run: `$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path; uv run pytest tests/test_agent_integration.py -q -k "automatic_rebuild or exposure_change or coalesce or unsubscribe"`

Expected: FAIL because AgentIntegration does not subscribe or coalesce.

- [ ] **Step 4: Implement subscriptions and coalescing**

Add fields:

```python
self._exposure_change_lock = threading.Lock()
self._exposure_rebuild_dirty = False
self._exposure_rebuild_in_progress = False
self._exposure_rebuild_idle = threading.Event()
self._exposure_rebuild_idle.set()
self._exposure_subscriptions: list[tuple[Any, int]] = []
self._shutdown_started = False
```

Bind registry, MCP, Skill, and optional PermissionManager through their `subscribe_changes` API. Manager replacement unbinds the old token and binds the new one.

```python
def _on_exposure_change(self, event: ExposureChange) -> None:
    with self._exposure_change_lock:
        if self._shutdown_started or not self._initialized:
            return
        self._exposure_rebuild_dirty = True
        if self._exposure_rebuild_in_progress:
            idle = self._exposure_rebuild_idle
            owns_drain = False
        else:
            self._exposure_rebuild_in_progress = True
            self._exposure_rebuild_idle.clear()
            idle = self._exposure_rebuild_idle
            owns_drain = True

    if not owns_drain:
        if not self._async_runtime.in_runtime_thread():
            idle.wait()
        return

    if self._async_runtime.in_runtime_thread():
        asyncio.create_task(self._drain_exposure_rebuilds())
        return

    self._async_runtime.run(self._drain_exposure_rebuilds())
```

The async drain clears `dirty`, obtains a fresh current API key, calls the Task 3 async rebuild implementation, then checks dirty again. In `finally`, it resets `in_progress` and sets the idle event. If a dirty change races the final transition, keep the transition and dirty check under the same short lock so no event is lost. Log event source/action/name and isolate failures from the originating mutation.

Do not call the synchronous `_rebuild_agent_runtime()` from the runtime thread. Do not hold `_exposure_change_lock` while awaiting, calling `runtime.run`, or waiting on the idle event.

- [ ] **Step 5: Unsubscribe during terminal shutdown**

After runtime-thread re-entry preflight but before `runtime.stop`, atomically set `_shutdown_started=True`, detach every `(source, token)`, call `source.unsubscribe_changes(token)`, and wait for any external in-progress rebuild to become idle without holding the exposure lock. The runtime lifecycle lock determines whether the rebuild or shutdown cleanup publishes last. Repeated shutdown/unsubscribe is safe.

- [ ] **Step 6: Run the Plan 03 phase gate**

Run:

```powershell
$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path
uv run pytest tests/test_change_notifier.py tests/test_agent_integration.py tests/test_end_to_end.py tests/test_permission_manager.py tests/test_permission_proxy.py -q
uv run pytest tests/test_agent_async_runtime.py tests/test_streaming_hooks.py tests/test_multimodal_integration.py tests/test_chat_panel.py -q
rg -n "register_tool_function|register_agent_skill|HttpStatelessClient|StdIOStatefulClient|ToolResponse\(content=\[\{" src
rg -n "FunctionTool\(.*(Bash|Read|Write|Edit|Glob|Grep)|BuiltinTool|ShellTool" src/agent
git diff --check
```

Expected: all tests PASS with only the existing environment-dependent Qt skip; both scans exit 1 with no runtime matches; diff check clean; no leaked task/thread/loop warnings.

- [ ] **Step 7: Commit**

```powershell
git add src/agent/agent_integration.py tests/test_agent_integration.py
git commit -m "feat: rebuild agent exposure automatically"
```

### Task 5: Mark Plan 03 complete after whole-phase verification

**Files:**
- Test only; no production changes expected.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: verified Plan 03 completion gate.

- [ ] **Step 1: Run the complete relevant regression set**

```powershell
$env:UV_CACHE_DIR=(Resolve-Path -LiteralPath '.tmp/uv-cache').Path
uv run pytest tests/test_agent_async_runtime.py tests/test_agent_integration.py tests/test_streaming_hooks.py tests/test_end_to_end.py tests/test_permission_manager.py tests/test_permission_proxy.py tests/test_multimodal_integration.py tests/test_chat_panel.py -q
```

Expected: PASS; only the previously documented environment-dependent Qt skip is allowed.

- [ ] **Step 2: Run full static scans**

```powershell
rg -n "register_tool_function|register_agent_skill|HttpStatelessClient|StdIOStatefulClient|ToolResponse\(content=\[\{|asyncio\.new_event_loop\(\)|run_until_complete\(|_parked_reply_loop|_parked_reply_loop_thread" src
rg -n "FunctionTool\(.*(Bash|Read|Write|Edit|Glob|Grep)|BuiltinTool|ShellTool" src/agent
git diff --check
```

Expected: no runtime matches; diff check clean.

- [ ] **Step 3: Record the phase gate**

Update `.superpowers/sdd/progress.md` with the exact pytest result and reviewed commit ranges. Do not create a tracked commit solely for the ignored progress ledger.
