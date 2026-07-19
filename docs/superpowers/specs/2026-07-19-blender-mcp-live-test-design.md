# Blender MCP Live Test Design

## Goal

Provide an opt-in end-to-end test for the Blender MCP used by the main branch.
The test proves that the stdio MCP process can connect to the locally running
Blender integration and that a read-only scene query completes successfully.

## Scope

- Add `tests/test_blender_mcp_live.py`.
- Do not change Blender scenes, create files, or call export/modeling tools.
- Do not test Unity, SolidWorks, or user-configured MCP records in this change.

## Execution Contract

The test is skipped unless `RUN_LIVE_BLENDER_MCP=1` is present. When enabled,
it creates the same `StdioMCPConfig(command="uvx", args=["blender-mcp"])`
and stateful `MCPClient` used by the Blender plugin. It connects, loads tools,
asserts the read-only `get_scene_info` tool exists, invokes it once, asserts a
successful response, and closes the client in `finally`.

`BLENDER_MCP_LIVE_TIMEOUT_SECONDS` may override the default 60-second client
timeout. Failures are intentionally not converted to skips once the live gate
is enabled: they are evidence that Blender, its MCP add-on, or the MCP bridge
is unavailable.

## Verification

- Without the live gate the test is skipped.
- With Blender and its MCP add-on running, `RUN_LIVE_BLENDER_MCP=1` executes
  the connect/list/query/close sequence and passes.
- The test result contains no write, export, or scene-modifying operation.
