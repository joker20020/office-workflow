# AgentScope 2.0 Toolkit, MCP, and Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate project tools, MCP clients, permission exposure, and enabled Agent Skills to the AgentScope 2.0 Toolkit constructor model.

**Architecture:** Build one filtered Toolkit from `FunctionTool` instances, connected `MCPClient` instances, and enabled skill directories. The existing project `PermissionManager` decides exposure; AgentScope uses BYPASS only after filtering.

**Tech Stack:** AgentScope 2.0.4 Toolkit/FunctionTool/MCPClient/Skill APIs, project permission system, pytest

## Global Constraints

- Only enabled and project-authorized tools, MCP servers, and Skills enter Toolkit.
- Do not expose generic Bash or arbitrary filesystem tools.
- Keep current SkillManager database/UI contracts and main-assistant-only scope.
- Close every stateful MCP client in failure, reset, and shutdown paths.
- Preserve configured tool execution timeouts.

---

## File map

- `src/agent/workflow_tools.py`: return 2.0 tool-compatible values.
- `src/agent/mcp_server_manager.py`: emit `MCPClient` constructor data.
- `src/agent/skill_manager.py`: validate enabled `SKILL.md` directories.
- `src/agent/agent_integration.py`: build Toolkit and own MCP lifecycle/rebuilds.
- `tests/test_agent_integration.py`, `tests/test_end_to_end.py`: verify filtering and lifecycle.

### Task 1: Migrate custom function tools

**Files:**
- Modify: `src/agent/workflow_tools.py`
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_end_to_end.py`

**Interfaces:**
- Produces: `list[FunctionTool]` passed as `Toolkit(tools=function_tools)`.

- [ ] **Step 1: Add response and registration tests**

Assert `_make_response("ok", True)` returns a 2.0 `ToolResponse` whose `content[0]` is `TextBlock(text="ok")` and `state == ToolResultState.SUCCESS`. Assert each authorized registry callable is wrapped as `FunctionTool(func=callable)` exactly once.

- [ ] **Step 2: Run the focused tests**

Run: `uv run pytest tests/test_end_to_end.py -q -k "tool or response"`

Expected: FAIL because response content still uses raw dictionaries and Toolkit registration uses 1.x mutation methods.

- [ ] **Step 3: Implement 2.0 responses and wrappers**

```python
from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import FunctionTool, ToolResponse

def _make_response(content, success=True, metadata=None):
    return ToolResponse(
        content=[TextBlock(text=str(content))],
        state=ToolResultState.SUCCESS if success else ToolResultState.ERROR,
        metadata=metadata or {},
    )
```

Build `FunctionTool` values before Toolkit construction. Set `is_concurrency_safe=False` for workflow-mutating functions and preserve their names/docstrings.

- [ ] **Step 4: Verify tool tests**

Run: `uv run pytest tests/test_end_to_end.py tests/test_agent_integration.py -q -k "tool or response or registry"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/workflow_tools.py src/agent/agent_integration.py tests/test_end_to_end.py tests/test_agent_integration.py
git commit -m "feat: migrate custom tools to agentscope 2 toolkit"
```

### Task 2: Produce 2.0 MCP configurations

**Files:**
- Modify: `src/agent/mcp_server_manager.py`
- Modify: `tests/test_agent_integration.py`

**Interfaces:**
- Produces: `create_agentscope_client(name: str) -> MCPClient | None`.

- [ ] **Step 1: Replace old configuration assertions**

For stdio, assert `MCPClient(name="test_stdio", is_stateful=True, mcp_config=StdioMCPConfig(command="python", args=["server.py"], env={"MODE": "test"}), execution_timeout=30)`. For HTTP, assert `HttpMCPConfig(url="http://localhost:8000/mcp", headers=None, timeout=30.0)` and `is_stateful=False`, matching the current main-assistant HTTP lifecycle.

- [ ] **Step 2: Run MCP manager tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k mcp`

Expected: FAIL because `get_agentscope_config` returns 1.x client-class data.

- [ ] **Step 3: Implement the client factory**

```python
from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig

return MCPClient(
    name=server["name"],
    is_stateful=True,
    mcp_config=StdioMCPConfig(
        command=server["command"], args=server.get("args"),
        env=server.get("env"), cwd=server.get("cwd"),
    ),
    enable_tools=server.get("enable_tools"),
    disable_tools=server.get("disable_tools"),
    execution_timeout=server.get("execution_timeout"),
)
```

Use `HttpMCPConfig(timeout=float(server.get("timeout", 30)))` and `execution_timeout=float(server.get("timeout", 30))` for calls.

- [ ] **Step 4: Verify MCP construction**

Run: `uv run pytest tests/test_agent_integration.py -q -k mcp`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/mcp_server_manager.py tests/test_agent_integration.py
git commit -m "feat: build agentscope 2 mcp clients"
```

### Task 3: Connect, filter, and close MCP clients

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`

**Interfaces:**
- Consumes: `MCPClient` from Task 2.
- Produces: `_connect_mcp_clients() -> list[MCPClient]` and `_close_mcp_clients() -> None`.

- [ ] **Step 1: Add lifecycle tests**

Use fake stateful and stateless clients. Assert stateful `connect()` occurs before `Toolkit(mcps=connected_clients)`; stateless does not connect; one failed client is logged by server name and excluded; previously connected clients remain tracked; shutdown closes each connected stateful client exactly once.

- [ ] **Step 2: Run lifecycle tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k "mcp and (connect or close or failure)"`

Expected: FAIL on old `StdIOStatefulClient`/`HttpStatelessClient` behavior.

- [ ] **Step 3: Implement lifecycle ownership**

Create clients from enabled servers only. Await `connect()` for stateful clients before Toolkit creation. Append only successful clients to `self._mcp_clients`. In reset/shutdown, close connected stateful clients in `try/finally`, log the client name on cleanup errors, and clear the list.

- [ ] **Step 4: Verify lifecycle tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k mcp`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/agent_integration.py tests/test_agent_integration.py
git commit -m "feat: manage agentscope 2 mcp lifecycle"
```

### Task 4: Load enabled Agent Skills through Toolkit

**Files:**
- Modify: `src/agent/skill_manager.py`
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`

**Interfaces:**
- Produces: `SkillManager.get_enabled_skill_paths() -> list[str]` containing valid directories with `SKILL.md`.

- [ ] **Step 1: Add valid, disabled, and malformed Skill tests**

Create temporary directories for one enabled valid Skill, one disabled valid Skill, one missing `SKILL.md`, and one invalid path. Assert only `str(enabled_skill_dir)` is passed in `Toolkit(skills_or_loaders=[str(enabled_skill_dir)])`; invalid entries emit named warnings but do not prevent Agent initialization.

- [ ] **Step 2: Run Skill tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k skill`

Expected: FAIL while `register_agent_skill` remains.

- [ ] **Step 3: Implement validation and constructor integration**

`get_enabled_skill_paths` resolves each configured directory, verifies it is a directory and contains a readable `SKILL.md`, logs skipped skill name/path, and returns strings. Build Toolkit with `skills_or_loaders=paths`; use `LocalSkillLoader(directory=parent, scan_subdir=True)` only for explicit parent-directory discovery.

- [ ] **Step 4: Verify Skill tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k skill`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/skill_manager.py src/agent/agent_integration.py tests/test_agent_integration.py
git commit -m "feat: load enabled skills with agentscope 2"
```

### Task 5: Enforce exposure permissions and Toolkit rebuilds

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `src/core/permission_manager.py` only if a read-only query helper is missing
- Modify: `tests/test_permission_manager.py`
- Modify: `tests/test_agent_integration.py`

**Interfaces:**
- Produces: `_build_toolkit() -> Toolkit` and `_rebuild_agent_runtime() -> None`.

- [ ] **Step 1: Add deny/exclusion tests**

Disable one plugin tool, MCP server, and Skill through existing project managers. Assert none appears in Toolkit tools/MCPs/skills. Assert no `Bash`, `Read`, `Write`, `Edit`, `Glob`, or `Grep` tool is added implicitly.

- [ ] **Step 2: Add permission mode assertion**

Assert the created `AgentState.permission_context.mode` is `PermissionMode.BYPASS` only after the project-filtered Toolkit is assembled.

- [ ] **Step 3: Implement one rebuild path**

Collect authorized `FunctionTool`s, connected clients, and valid Skill paths, then call:

```python
self._toolkit = Toolkit(tools=tools, mcps=clients, skills_or_loaders=skill_paths)
self._agent.state.permission_context.mode = PermissionMode.BYPASS
```

Rebuild the Toolkit/Agent after tool registry, MCP enablement, or Skill enablement changes while preserving `AgentState.context` and session id.

- [ ] **Step 4: Run the phase gate**

Run: `uv run pytest tests/test_agent_integration.py tests/test_end_to_end.py tests/test_permission_manager.py tests/test_permission_proxy.py -q`

Expected: PASS.

Run: `rg -n "register_tool_function|register_agent_skill|HttpStatelessClient|StdIOStatefulClient|ToolResponse\(content=\[\{" src`

Expected: no runtime matches.

- [ ] **Step 5: Commit**

```bash
git add src/agent/agent_integration.py src/core/permission_manager.py tests/test_permission_manager.py tests/test_agent_integration.py
git commit -m "feat: enforce filtered agentscope 2 toolkit"
```
