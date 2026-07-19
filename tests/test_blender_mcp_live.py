"""Opt-in end-to-end health check for the local Blender MCP bridge."""

import os

import pytest
from agentscope.mcp import MCPClient, StdioMCPConfig
from agentscope.message import ToolResultState


@pytest.mark.asyncio
async def test_blender_mcp_lists_tools_and_reads_scene_info():
    """Connect to Blender MCP and run its read-only scene inspection tool."""
    if os.getenv("RUN_LIVE_BLENDER_MCP") != "1":
        pytest.skip(
            "Set RUN_LIVE_BLENDER_MCP=1 to run the Blender MCP live test."
        )

    timeout = float(os.getenv("BLENDER_MCP_LIVE_TIMEOUT_SECONDS", "60"))
    client = MCPClient(
        name="blender_mcp_live_test",
        is_stateful=True,
        mcp_config=StdioMCPConfig(command="uvx", args=["blender-mcp"]),
        execution_timeout=timeout,
    )
    connected = False
    try:
        await client.connect()
        connected = True
        tools = await client.list_tools()
        scene_info = next(
            (tool for tool in tools if tool.name.endswith("get_scene_info")),
            None,
        )
        assert scene_info is not None, "Blender MCP did not expose get_scene_info"

        response = await scene_info(
            user_prompt="Read the current Blender scene information only. Do not modify it."
        )

        # MCP FunctionTool exposes a terminal ToolChunk with RUNNING as its
        # default state; ``is_last`` marks completion for this direct call.
        assert response.is_last
        assert response.state != ToolResultState.ERROR
        assert response.content
    finally:
        if connected:
            await client.close()
