# AgentScope 2.0 Exposure Filtering and Automatic Rebuild Design

## Decision

Use event-driven automatic rebuilds. Tool registry, MCP manager, Skill manager, and project PermissionManager changes notify the main `AgentIntegration`, which coalesces changes and rebuilds one filtered AgentScope 2.0 Toolkit/Agent transactionally on its long-lived runtime.

This replaces two rejected alternatives:

- UI-only rebuild callbacks: changes made outside the settings dialog would leave a stale Agent.
- Lazy rebuild on the next chat: configuration errors would be discovered late and dirty-state handling would complicate chat/interruption ordering.

## Goals

- Only project-authorized plugin tools, enabled MCP servers, and enabled valid Skills enter the main assistant Toolkit.
- Permission revocation and registry/MCP/Skill changes update an initialized assistant without restarting the application.
- AgentScope permission mode becomes `PermissionMode.BYPASS` only after project filtering has completed.
- Rebuild preserves Agent conversation context and AgentScope session identity.
- Rebuild uses the reviewed long-lived runtime and MCP cancellation-safe lifecycle.
- No generic shell or arbitrary filesystem tool is implicitly added.

## Non-goals

- Do not change plugin permission declarations, permission UI, MCP/Skill database schema, provider defaults, tool execution timeouts, plugin subagents, or the AgentScope runtime implementation.
- Do not grant permissions automatically.
- Do not add AgentScope built-in Bash, Read, Write, Edit, Glob, Grep, or similar unrestricted tools.
- Do not make Agent Skills available to plugin subagents in this task; the existing main-assistant-only scope remains.

## Change notification boundary

Introduce a small thread-safe change notification utility with this contract:

- subscribers register a callback and receive an opaque subscription token;
- removal by token is idempotent;
- notification snapshots subscribers under a lock and invokes them outside the lock;
- one failing callback is logged and isolated from the mutating manager and other subscribers;
- notifications carry a small immutable event containing source, action, and optional item name;
- a notification is emitted only after a mutation succeeds.

The following sources publish changes:

- `AgentToolRegistry`: successful register and unregister;
- `McpServerManager`: successful add, update, delete, and enable/disable;
- `SkillManager`: successful add, update, delete, discover/register, and enable/disable;
- `PermissionManager`: successful grant, grant-all, revoke, and revoke-all operations.

An event represents an actual exposure-state change. Granting an already granted permission, revoking an absent permission, deleting an absent entry, or another no-op/failure emits nothing. `SkillManager.discover_and_register()` relies on the successful `add_skill` notifications for each newly registered Skill and does not emit a second aggregate event.

Loading initial permissions does not require a rebuild because the main assistant subscribes after application service initialization. No listener is allowed to mutate the originating manager while its internal/database lock or session is held.

## Authorized tool ownership

Current registry group names do not always equal plugin names: the `workflow_tools` plugin registers the `workflow` group. Therefore authorization cannot safely infer ownership from the group string.

Extend registry registration with optional owner metadata while preserving compatibility:

```python
registry.register(group_name, tools, *, owner_name=None)
```

`GuardedToolRegistry`, which already knows the plugin identity and enforces `Permission.AGENT_TOOL` at registration time, passes `owner_name=self._plugin_name`. Direct legacy/core registration without an owner remains trusted for compatibility and is included. The registry exposes an immutable/read-only snapshot of `(group_name, owner_name, tools)`; callers cannot mutate registry storage through the snapshot.

At Toolkit build time:

- ownerless trusted/core groups are included;
- owned groups are included only when `PermissionManager.check(owner_name, Permission.AGENT_TOOL)` is true;
- duplicate callable objects across authorized groups are wrapped only once, retaining current order;
- permission revocation does not need to unregister the group—the next automatic rebuild filters it out;
- re-granting permission makes the still-registered group visible again on rebuild.

When no PermissionManager is supplied, all registered groups are included for backward compatibility with tests and standalone integrations. The production `MainWindow` passes the initialized application PermissionManager.

## Filtered Toolkit construction

One internal builder gathers all inputs before Agent construction:

1. Snapshot authorized registry groups and wrap unique callables as `FunctionTool(is_concurrency_safe=False)`.
2. Read enabled MCP records in manager order, create clients, and connect stateful clients on the owned runtime loop using the reviewed cancellation-safe lifecycle.
3. Read enabled, validated Skill paths from `SkillManager.get_enabled_skill_paths()`.
4. Construct exactly one `Toolkit(tools=..., mcps=..., skills_or_loaders=...)`.
5. Construct the Agent state and set `state.permission_context.mode = PermissionMode.BYPASS` only after steps 1–4 have filtered exposure.

No AgentScope default or generic tool is appended. The project-filtered lists are the complete exposure set.

## Rebuild transaction

Expose one synchronous controller method, `_rebuild_agent_runtime() -> bool`, and one runtime-loop async implementation. All automatic notifications use this same path.

If the assistant is not initialized or has already shut down, a change only updates manager/registry state; no rebuild is scheduled. The next normal initialization reads the latest exposure.

For an initialized assistant, rebuild:

1. snapshots the current AgentState context, session id, summary, and other state fields needed for functional continuity;
2. obtains the current provider/model/base URL and a fresh API key through `ApiKeyManager` without persisting the raw key;
3. enters the existing runtime lifecycle lock;
4. settles active/parked reply work;
5. detaches and closes published MCP clients with exact-list cancellation-safe drain;
6. builds the filtered Toolkit and replacement Agent;
7. publishes Agent, Toolkit, MCP ownership, and initialized state only after full success;
8. restores the preserved AgentState context/session identity on the replacement and sets BYPASS after filtering.

After destructive replacement begins, failure follows the existing atomic contract: all locally connected clients are drained and the integration remains empty/uninitialized. Manager mutations are not rolled back. The failure is logged with source/action context.

## Notification coalescing and threading

Notifications may originate from the UI thread, plugin-management thread, or the Agent runtime thread.

- A small lock protects only dirty/in-progress flags; it is never held while waiting for the runtime.
- Multiple changes arriving during one rebuild are coalesced. At most one rebuild executes at a time, and one additional pass runs if the dirty flag was set during the first pass.
- From an external thread, the callback synchronously uses the single rebuild controller so the change is effective when the manager call returns.
- From the owned runtime thread, the callback schedules the async rebuild implementation with `asyncio.create_task` and returns; it must never synchronously wait on its own runtime.
- Callback/rebuild failure is logged and isolated from the successful manager mutation.
- Shutdown unsubscribes all listener tokens before terminal runtime stop. Repeated shutdown/unsubscription is safe.
- Replacing MCP/Skill/Permission managers removes old subscriptions before adding new ones.

## Public compatibility

- Existing constructor callers remain valid because the PermissionManager parameter is optional.
- Existing registry `register(group_name, tools)` calls remain valid.
- Existing manager mutation return values and database/UI formats do not change.
- Existing `initialize`, `chat`, `chat_async`, interruption, reset, session, and shutdown signatures remain unchanged.
- `MainWindow` passes `AppContext.permission_manager` when available so production uses owner-aware filtering.

## Testing

### Notification utility and publishers

- snapshot/invoke-outside-lock behavior;
- listener failure isolation;
- idempotent unsubscribe;
- successful mutations notify exactly once with source/action/name;
- failed/no-op mutations do not notify.

### Exposure filtering

- an owned authorized group enters Toolkit;
- an owned denied/revoked group does not;
- an ownerless trusted group remains compatible;
- disabled MCP and Skill entries are excluded by their managers;
- no forbidden generic tool names appear;
- duplicate callable identity is wrapped once in stable order.

### Permission mode

- AgentState starts with project-filtered Toolkit inputs;
- `permission_context.mode` is `PermissionMode.BYPASS` only on the successfully constructed replacement;
- construction failure never publishes a BYPASS Agent with an unfiltered/partial Toolkit.

### Rebuild

- registry register/unregister, MCP enablement, Skill enablement, and permission revoke/grant automatically rebuild an initialized assistant;
- changes before initialization do not start the runtime and are picked up on initialize;
- context and session id survive a successful rebuild;
- stateful old clients close before replacement publication on the same runtime loop;
- rebuild failure drains local clients and publishes empty state;
- concurrent notifications coalesce without overlapping lifecycle transactions;
- runtime-thread notifications schedule without self-deadlock;
- shutdown removes listeners and leaves no rebuild future/task or runtime thread.

### Regression gate

Run Agent integration, runtime, streaming, permission manager/proxy, end-to-end, multimodal, and chat panel suites. Static scans reject legacy Toolkit mutation APIs, legacy MCP client classes, and forbidden implicit tool construction.

## Completion criteria

- Production uses owner-aware project filtering when a PermissionManager is available.
- All successful exposure mutations automatically converge an initialized assistant through one rebuild path.
- Rebuild preserves conversation state/session identity and uses one long-lived runtime loop.
- BYPASS is set only after complete project filtering.
- No unrestricted generic tool is exposed implicitly.
- All new and existing relevant tests pass and an independent task review approves the result.
