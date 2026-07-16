"""Independent AgentScope 2 SolidWorks modeling plugin."""

import asyncio
import contextvars
import functools
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.event import (
    ReplyEndEvent,
    ReplyStartEvent,
    TextBlockDeltaEvent,
    ToolCallDeltaEvent,
    ToolCallStartEvent,
    ToolResultStartEvent,
    ToolResultTextDeltaEvent,
)
from agentscope.mcp import MCPClient, StdioMCPConfig
from agentscope.message import AssistantMsg, TextBlock, ToolResultState, UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.tool import ToolChunk, Toolkit, ToolResponse

from src.agent.agent_integration import encode_subagent_event
from src.core.artifact_context import current_artifact_context
from src.core.permission_manager import Permission, PermissionSet
from src.core.plugin_base import PluginBase
from src.utils.logger import get_logger

from .settings import execution_timeout_seconds

TOOL_GROUP_NAME = "solidworks_agent"
_logger = get_logger(__name__)
_PROGRESS_SINK: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "solidworks_progress_sink",
    default=None,
)

REQUIRED_HEADINGS = (
    "# Execution Result",
    "## Status",
    "## Execution Summary",
    "## Generated Files",
    "## Concrete Result",
    "## Execution Log",
    "## Verification",
    "## Warnings and Unfinished Items",
)
_VALID_STATUSES = {"Success", "Partial Success", "Failed"}

SYSTEM_PROMPT = """You are a SolidWorks feature-level modeling subagent.
Use only the dedicated, feature-level SolidWorks MCP tools. Follow this progression:
1. Check status/new part.
2. Create a sketch and dimensions.
3. Close sketch.
4. Create one feature, then inspect it.
5. Create each subsequent feature, then inspect after every feature.
6. Save the native part.
7. Export both STEP and STL.
8. Capture a preview.

Never expose, request, or encourage arbitrary COM access, scripts, macros, shell commands,
or arbitrary paths. Use only paths authorized for the active session by the MCP tools.

Return Markdown with every heading below exactly once and in this order. Status must be
Success, Partial Success, or Failed. Report only tool-verified work and files:
# Execution Result
## Status
## Execution Summary
## Generated Files
## Concrete Result
## Execution Log
## Verification
## Warnings and Unfinished Items
"""


class _StructuredResult(str):
    success: bool

    def __new__(cls, content: str, *, success: bool):
        value = super().__new__(cls, content)
        value.success = success
        return value


def _failure(message: str) -> _StructuredResult:
    return _StructuredResult(
        "# Execution Result\n"
        "## Status\nFailed\n"
        "## Execution Summary\nThe SolidWorks task was not completed.\n"
        "## Generated Files\nNone\n"
        f"## Concrete Result\n{message}\n"
        "## Execution Log\nNo complete, verifiable execution result was obtained.\n"
        "## Verification\nNot verified.\n"
        f"## Warnings and Unfinished Items\n{message}",
        success=False,
    )


def _validate_result(content: str) -> _StructuredResult:
    text = str(content or "").strip()
    positions = []
    for heading in REQUIRED_HEADINGS:
        if text.count(heading) != 1:
            return _failure(f"missing required heading or duplicate heading: {heading}")
        positions.append(text.index(heading))
    if positions != sorted(positions):
        return _failure("required headings are out of order")
    status_start = positions[1] + len(REQUIRED_HEADINGS[1])
    status_end = positions[2]
    status_lines = [
        line.strip() for line in text[status_start:status_end].splitlines() if line.strip()
    ]
    if len(status_lines) != 1 or status_lines[0] not in _VALID_STATUSES:
        return _failure("invalid structured result status")
    return _StructuredResult(text, success=status_lines[0] == "Success")


def _build_model() -> Any:
    credential = OpenAICredential(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1",
    )
    return OpenAIChatModel(
        credential=credential,
        model=os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        stream=True,
    )


def _run_async(coro):
    """Run async work from the synchronous public tool interface."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[Any] = [None, None]
    caller_context = contextvars.copy_context()

    def run() -> None:
        try:
            result[0] = caller_context.run(asyncio.run, coro)
        except BaseException as exc:
            result[1] = exc

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()
    if result[1] is not None:
        raise result[1]
    return result[0]


async def _consume_reply_stream(agent: Any, inputs: Any) -> AssistantMsg:
    """Rebuild the reply while forwarding only public subagent events."""
    reply = AssistantMsg(name=getattr(agent, "name", "SolidWorksAgent"), content=[])
    sink = _PROGRESS_SINK.get()
    tool_names: dict[str, str] = {}
    text_deltas: list[str] = []
    async for event in agent.reply_stream(inputs=inputs):
        if isinstance(event, ReplyStartEvent):
            reply.id = event.reply_id
        reply.append_event(event)
        public = None
        if isinstance(event, ToolCallStartEvent):
            tool_names[event.tool_call_id] = event.tool_call_name
            public = {
                "kind": "tool_call",
                "tool": event.tool_call_name,
                "text": "tool call started",
            }
        elif isinstance(event, ToolCallDeltaEvent):
            public = {
                "kind": "tool_call",
                "tool": tool_names.get(event.tool_call_id, "tool"),
                "text": event.delta,
            }
        elif isinstance(event, ToolResultStartEvent):
            tool_names[event.tool_call_id] = event.tool_call_name
        elif isinstance(event, ToolResultTextDeltaEvent):
            public = {
                "kind": "tool_result",
                "tool": tool_names.get(event.tool_call_id, "tool"),
                "text": event.delta,
            }
        elif isinstance(event, TextBlockDeltaEvent):
            text_deltas.append(event.delta)
            public = {
                "kind": "text",
                "title": getattr(agent, "name", "SolidWorksAgent"),
                "text": event.delta,
            }
        elif isinstance(event, ReplyEndEvent):
            public = {
                "kind": "complete",
                "title": getattr(agent, "name", "SolidWorksAgent"),
                "text": "subagent reply completed",
            }
        if public is not None and sink is not None:
            sink(public)
    if not reply.get_text_content() and text_deltas:
        reply.content = [TextBlock(text="".join(text_deltas))]
    return reply


class SolidWorksAgentTools:
    """Public SolidWorks subagent tools."""

    def tool_solidworks_model(
        self,
        task: str,
        session_id: str | None = None,
    ) -> ToolResponse:
        try:
            result = _run_async(self._solidworks_model_async(task, session_id))
            result = _validate_result(result)
        except Exception as exc:
            result = _failure(f"SolidWorks execution failed: {exc}")
        return ToolResponse(
            content=[TextBlock(text=str(result))],
            state=ToolResultState.SUCCESS if result.success else ToolResultState.ERROR,
        )

    async def _solidworks_model_async(
        self,
        task: str,
        session_id: str | None = None,
    ) -> _StructuredResult:
        context = current_artifact_context()
        active_session = session_id or (context.session_id if context is not None else "standalone")
        project_root = Path(__file__).resolve().parents[2]
        child_env = dict(os.environ)
        child_env["SOLIDWORKS_SESSION_ID"] = active_session
        config = StdioMCPConfig(
            command=sys.executable,
            args=["-m", "plugins.solidworks_agent.mcp_server"],
            env=child_env,
            cwd=str(project_root),
        )
        client = MCPClient(
            name="solidworks_mcp",
            is_stateful=True,
            mcp_config=config,
            execution_timeout=execution_timeout_seconds(),
        )
        primary_error: BaseException | None = None
        try:
            try:
                await client.connect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return _failure(f"Unable to connect to the project-local SolidWorks MCP: {exc}")

            toolkit = Toolkit(mcps=[client])
            agent = Agent(
                name="SolidWorksAgent",
                system_prompt=SYSTEM_PROMPT,
                model=_build_model(),
                toolkit=toolkit,
                react_config=ReActConfig(max_iters=60),
            )
            response = await _consume_reply_stream(
                agent,
                UserMsg(name="User", content=task),
            )
            return _validate_result(response.get_text_content() or "")
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                await client.close()
            except BaseException as cleanup_error:
                if primary_error is None:
                    raise
                _logger.warning(
                    "SolidWorks MCP cleanup failed while propagating %s: %s",
                    type(primary_error).__name__,
                    cleanup_error,
                )

    def get_all_tools(self) -> list[Any]:
        sync_tool = self.tool_solidworks_model

        @functools.wraps(sync_tool)
        async def streaming(*args, **kwargs):
            progress: queue.Queue = queue.Queue()
            token = _PROGRESS_SINK.set(progress.put)
            task = asyncio.create_task(asyncio.to_thread(sync_tool, *args, **kwargs))
            try:
                while not task.done() or not progress.empty():
                    while not progress.empty():
                        yield ToolChunk(
                            content=[TextBlock(text=encode_subagent_event(progress.get_nowait()))],
                            is_last=False,
                        )
                    if not task.done():
                        await asyncio.wait({task}, timeout=0.05)
                yield await task
            finally:
                _PROGRESS_SINK.reset(token)

        streaming.__name__ = "tool_solidworks_model"
        return [streaming]


class SolidWorksAgentPlugin(PluginBase):
    name = "solidworks_agent"
    version = "1.0.0"
    description = "Feature-level SolidWorks modeling subagent"
    author = "OfficeTools"
    permissions = PermissionSet.from_list([Permission.AGENT_TOOL])

    def __init__(self):
        super().__init__()
        self._tools: SolidWorksAgentTools | None = None

    def on_enable(self, context) -> None:
        self._tools = SolidWorksAgentTools()
        context.tool_registry.register(TOOL_GROUP_NAME, self._tools.get_all_tools())

    def on_disable(self, context=None) -> None:
        if context is not None:
            context.tool_registry.unregister(TOOL_GROUP_NAME)
        self._tools = None


plugin_class = SolidWorksAgentPlugin
