# Blender MCP Live Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in end-to-end test that proves the local Blender MCP can serve a read-only scene query.

**Architecture:** A dedicated pytest module creates the same stateful AgentScope stdio client used by the plugin. It is skipped unless `RUN_LIVE_BLENDER_MCP=1`; a `finally` block closes the client after tool discovery and the read-only query.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, AgentScope MCP client, `uvx blender-mcp`.

## Global Constraints

- Work on the user-authorized `main` branch.
- Do not create, modify, save, or export Blender scene data.
- Default test runs must skip the live test.
- A live-gated connection or query failure must fail the test rather than silently skip it.

---

### Task 1: Add the opt-in Blender MCP live test

**Files:**
- Create: `tests/test_blender_mcp_live.py`

**Interfaces:**
- Consumes: `RUN_LIVE_BLENDER_MCP`, optional `BLENDER_MCP_LIVE_TIMEOUT_SECONDS`, `StdioMCPConfig`, and `MCPClient`.
- Produces: `test_blender_mcp_lists_tools_and_reads_scene_info()`.

- [ ] **Step 1: Write the test**

```python
@pytest.mark.asyncio
async def test_blender_mcp_lists_tools_and_reads_scene_info():
    if os.getenv("RUN_LIVE_BLENDER_MCP") != "1":
        pytest.skip("Set RUN_LIVE_BLENDER_MCP=1 to run the Blender MCP live test")
    client = MCPClient(... StdioMCPConfig(command="uvx", args=["blender-mcp"]) ...)
    try:
        await client.connect()
        tools = await client.list_tools()
        scene_info = next(tool for tool in tools if tool.name.endswith("get_scene_info"))
        response = await scene_info()
        assert response is not None
    finally:
        await client.close()
```

- [ ] **Step 2: Verify the default gate**

Run: `python -m pytest tests/test_blender_mcp_live.py -q`

Expected: one skipped test and no Blender process launch.

- [ ] **Step 3: Verify the live path**

Run: `$env:RUN_LIVE_BLENDER_MCP='1'; python -m pytest tests/test_blender_mcp_live.py -q -s`

Expected: one passing test after a read-only `get_scene_info` call. If Blender or its MCP add-on is unavailable, report the connection failure without changing the scene.

- [ ] **Step 4: Commit**

Run: `git add tests/test_blender_mcp_live.py docs/superpowers/plans/2026-07-19-blender-mcp-live-test.md` then `git commit -m "test: add blender mcp live check"`.
