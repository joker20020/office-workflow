# SolidWorks Plugin-Subagent MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On `solidworks_version`, add a self-contained SolidWorks 2023 plugin subagent that owns a local stdio MCP, produces verified `.sldprt/.sldasm`, `.step`, `.stl`, and previews below `data`, then remove Blender-related implementation from that branch.

**Architecture:** The main agent calls one plugin tool, `tool_solidworks_model`, exactly as it currently calls `tool_blender_model`. The tool creates an AgentScope 2 subagent with a stateful MCP client and returns validated structured Markdown as the parent tool result. The complete MCP server, COM adapter, and plugin settings live below `plugins/solidworks_agent`; `src` remains unaware of SolidWorks internals.

**Tech Stack:** Python 3.11, AgentScope 2.0.4 Agent/Toolkit/MCPClient, Python stdio MCP server, pywin32 COM on Windows, SolidWorks 2023, pytest.

## Global Constraints

- Begin only after the current-branch artifact/sidebar/output-path work passes; then switch to `solidworks_version` before modifying code.
- Do not add SolidWorks MCP modules, COM imports, or manager integration to `src`.
- Attach to a running SolidWorks 2023 instance first; otherwise start it and wait for COM readiness.
- Never close a user-owned SolidWorks instance. A plugin-started instance closes only when explicit plugin configuration permits it.
- Native models use `data/models/<session-id>`; STEP/STL use `data/exports/<session-id>`; previews use `data/images/<session-id>`; all final files require shared `ArtifactRegistry.confirm_file()` verification.
- Do not expose arbitrary macros, arbitrary COM dispatch, arbitrary shell commands, or arbitrary file paths.
- After mocked and optional live SolidWorks gates pass, remove Blender-specific plugin tools, prompt/config references, and dedicated tests on `solidworks_version`.

## File map

- `plugins/solidworks_agent/plugin.json`: plugin metadata, dependency/permission declaration, and public tool registration.
- `plugins/solidworks_agent/__init__.py`: `SolidWorksAgentTools`, `tool_solidworks_model`, subagent lifecycle, MCP cleanup, structured handoff validation.
- `plugins/solidworks_agent/mcp_server.py`: stdio MCP tool definitions with strictly validated payloads.
- `plugins/solidworks_agent/com_adapter.py`: attach/start, tracked documents/sketches/features, inspect/save/export/preview.
- `plugins/solidworks_agent/types.py`: document, sketch, feature, connection, and operation-result dataclasses.
- `plugins/solidworks_agent/paths.py`: bridge to shared artifact path/registry interfaces; no path strings supplied by the model.
- `plugins/solidworks_agent/settings.py`: timeouts and MCP-started-instance cleanup defaulting to false.
- `tests/test_solidworks_plugin.py`, `tests/test_solidworks_mcp_server.py`, `tests/test_solidworks_live.py`: mocked plugin/MCP tests and opt-in real-host test.

### Task 1: Scaffold the independent plugin and mirror Blender subagent lifecycle

**Files:**
- Create: `plugins/solidworks_agent/plugin.json`, `plugins/solidworks_agent/__init__.py`, `plugins/solidworks_agent/settings.py`
- Test: `tests/test_solidworks_plugin.py`

**Interfaces:** `SolidWorksAgentTools.tool_solidworks_model(task: str, session_id: str) -> ToolResponse`; async helpers own `MCPClient.connect()` and cancellation-safe `close()`; no `src` modification.

- [ ] **Step 1: Write failing public-tool/lifecycle tests**

```python
def test_plugin_exposes_solidworks_subagent_tool_and_closes_owned_mcp(monkeypatch):
    tools = SolidWorksAgentTools(...)
    result = tools.tool_solidworks_model("create cap", session_id="s1")
    assert result.success is True
    assert fake_mcp.events == ["connect", "close"]
```

- [ ] **Step 2: Verify RED**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_solidworks_plugin.py -q`

Expected: plugin import is missing.

- [ ] **Step 3: Implement Blender-equivalent subagent wrapper**

```python
async def _solidworks_model_async(self, task: str, session_id: str) -> str:
    client = MCPClient(name="solidworks_mcp", is_stateful=True, mcp_config=self._stdio_config(), execution_timeout=self._timeout)
    try:
        await client.connect()
        return await self._run_connected_subagent(client, task, session_id)
    finally:
        await client.close()
```

The public tool validates its final Markdown with the same authoritative file/task evidence contract used by Blender, and returns a failed `ToolResponse` when connect, execution, or cleanup fails.

- [ ] **Step 4: Verify GREEN and commit**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_solidworks_plugin.py -q`

Expected: PASS.

Commit only plugin/tests: `git add plugins/solidworks_agent tests/test_solidworks_plugin.py; git commit -m "feat: add solidworks plugin subagent"`.

### Task 2: Build typed COM adapter and feature-level MCP surface inside the plugin

**Files:**
- Create: `plugins/solidworks_agent/types.py`, `plugins/solidworks_agent/com_adapter.py`, `plugins/solidworks_agent/mcp_server.py`
- Test: `tests/test_solidworks_mcp_server.py`

**Interfaces:** MCP exposes only `solidworks_status`, `solidworks_new_part`, `solidworks_create_sketch`, `solidworks_add_sketch_geometry`, `solidworks_add_dimensions`, `solidworks_close_sketch`, `solidworks_extrude`, `solidworks_revolve`, `solidworks_cut_extrude`, `solidworks_hole`, `solidworks_fillet`, `solidworks_chamfer`, `solidworks_mirror_feature`, `solidworks_pattern_feature`, `solidworks_inspect_model`, `solidworks_save_model`, `solidworks_export_step`, `solidworks_export_stl`, and `solidworks_capture_preview`.

- [ ] **Step 1: Write failing attach/start and ordered-feature tests**

```python
def test_connect_prefers_running_instance_and_never_owns_it(adapter):
    assert adapter.connect().started_by_mcp is False

def test_extrude_requires_closed_sketch(adapter):
    doc = adapter.new_part(session_id="s1", name="cap", unit="mm")
    sketch = adapter.create_sketch(doc.id, plane="Front")
    with pytest.raises(ValueError, match="closed sketch"):
        adapter.extrude(doc.id, sketch.id, depth=5, direction="normal")
```

- [ ] **Step 2: Verify RED**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_solidworks_mcp_server.py -q`

Expected: missing adapter/server imports.

- [ ] **Step 3: Implement typed attach/start and reference validation**

```python
def connect(self):
    app = self._dispatch.get_active("SldWorks.Application")
    self._started_by_plugin = app is None
    if app is None:
        app = self._dispatch.create("SldWorks.Application")
        app.Visible = True
        self._wait_for_ready(app)
    self._app = app
    return SolidWorksConnection(started_by_plugin=self._started_by_plugin)
```

For each feature validate document/sketch/face/edge/feature IDs before COM calls. Import pywin32 only in the runtime dispatch factory. On non-Windows/COM unavailability return a display-safe failed Markdown result.

- [ ] **Step 4: Implement stdio tool result contract and verify GREEN**

```python
@mcp.tool(name="solidworks_extrude")
def solidworks_extrude(document_id: str, sketch_id: str, depth: float, direction: str = "normal") -> str:
    return format_result(adapter.extrude(document_id, sketch_id, depth, direction))
```

Every result contains `## Status`, `## Execution Summary`, `## Generated Files`, `## Verification`, and `## Warnings`; it never includes a traceback or private reasoning.

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_solidworks_mcp_server.py tests/test_solidworks_plugin.py -q`

Expected: PASS.

Commit: `git add plugins/solidworks_agent tests/test_solidworks_mcp_server.py tests/test_solidworks_plugin.py; git commit -m "feat: add solidworks feature mcp"`.

### Task 3: Enforce artifact paths, exports, and default workflow replacement

**Files:**
- Create: `plugins/solidworks_agent/paths.py`
- Modify: `plugins/solidworks_agent/com_adapter.py`, `plugins/solidworks_agent/__init__.py`
- Modify: `config/settings.yaml` and only default prompt/workflow files found by `rg -n "tool_blender_model|Blender|blender" config plugins`
- Test: `tests/test_solidworks_plugin.py`, `tests/test_solidworks_live.py`

**Interfaces:** `save_model`, `export_step`, `export_stl`, and `capture_preview` obtain paths only from the shared policy and call `ArtifactRegistry.confirm_file()` after `Path.is_file()`. The parent main agent calls `tool_solidworks_model`; it never calls raw SolidWorks MCP tools.

- [ ] **Step 1: Write failing artifact/default-selection tests**

```python
def test_exports_are_registered_under_session_data_roots(plugin, artifact_repository, project_root):
    result = plugin.run_disposable_part(session_id="s1")
    assert Path(result["native"]).is_relative_to(project_root / "data" / "models" / "s1")
    assert Path(result["step"]).is_relative_to(project_root / "data" / "exports" / "s1")
    assert Path(result["stl"]).is_relative_to(project_root / "data" / "exports" / "s1")
    assert artifact_repository.list_for_session("s1")

def test_default_prompt_calls_plugin_subagent_not_raw_mcp():
    prompt = load_system_prompt()
    assert "tool_solidworks_model" in prompt
    assert "solidworks_extrude" not in prompt
```

- [ ] **Step 2: Verify RED**

Run: `.venv\\Scripts\\python.exe -m pytest tests/test_solidworks_plugin.py -q`

Expected: exports/default selection absent.

- [ ] **Step 3: Implement verified save/export and delayed preference switch**

```python
target = artifact_paths.destination(session_id, ArtifactCategory.EXPORT, "cap.step")
com_save_as(target)
if not target.is_file():
    return failed_result("STEP export did not create a file")
artifact = artifact_registry.confirm_file(session_id=session_id, category=ArtifactCategory.EXPORT, path=target, producer="SolidWorksAgent")
```

Only after mocked MCP/plugin tests pass, change the default modeling stage to call `tool_solidworks_model`; then remove `tool_blender_model`, its Blender-specific prompts/configuration, and dedicated Blender tests from `solidworks_version`.

- [ ] **Step 4: Add opt-in live test and final gates**

```python
@pytest.mark.skipif(os.getenv("SOLIDWORKS_LIVE_TEST") != "1", reason="requires local SolidWorks 2023")
def test_solidworks_2023_live_exports():
    result = run_live_disposable_part(session_id="solidworks-live-test")
    assert all(Path(path).is_file() for path in result.output_paths)
```

Run mocked gates: `.venv\\Scripts\\python.exe -m pytest tests/test_solidworks_plugin.py tests/test_solidworks_mcp_server.py -q`

After manually starting SolidWorks 2023 once, completing license sign-in, and accepting Windows COM/firewall prompts, run: `$env:SOLIDWORKS_LIVE_TEST='1'; .venv\\Scripts\\python.exe -m pytest tests/test_solidworks_live.py -q`

Then run: `.venv\\Scripts\\ruff.exe check plugins/solidworks_agent tests/test_solidworks_plugin.py tests/test_solidworks_mcp_server.py tests/test_solidworks_live.py; .venv\\Scripts\\python.exe -m pytest -q; git diff --check`

Expected: all enabled checks pass. On live-host failure preserve mocked-pass evidence and report the precise manual prerequisite; never weaken the live test.

- [ ] **Step 5: Audit and commit on the SolidWorks branch only**

Run: `git status --short`

Expected: only `solidworks_version` plugin/prompt/test files are staged; do not stage unrelated user files.

Commit: `git add plugins/solidworks_agent config/settings.yaml tests/test_solidworks_plugin.py tests/test_solidworks_mcp_server.py tests/test_solidworks_live.py; git commit -m "feat: prefer solidworks plugin modeling"`.
