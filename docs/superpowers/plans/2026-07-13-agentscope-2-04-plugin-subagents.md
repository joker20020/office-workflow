# AgentScope 2.0 Plugin Subagents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Directly migrate Unity, Blender, process-planning, ComfyUI, and RAG-facing plugin tools to AgentScope 2.0 while preserving structured Markdown handoffs and generated artifact paths.

**Architecture:** Each plugin method constructs its own 2.0 credential/model/Toolkit/Agent and owns its MCP clients with `try/finally`. Shared local helpers create 2.0 responses, extract message text, and close resources; no 1.x compatibility wrapper is introduced.

**Tech Stack:** AgentScope 2.0.4 Agent/Toolkit/MCP/task tools, existing ProcessGen HTTP API, asyncio, pytest

## Global Constraints

- Preserve all public plugin tool names, parameters, timeout defaults, and ProcessGen RAG HTTP behavior.
- Preserve the current redownload-and-overwrite RAG image cache behavior and local DataBlock loading.
- Subagents must return structured Markdown containing concrete operations, file contents, generated paths, tool results, status, and errors.
- Main-assistant Skills are not injected into plugin subagents in this phase.
- Every stateful MCP client is closed on success, failure, timeout, and cancellation.

---

## File map

- `plugins/agent_extensions/__init__.py`: all four subagents, RAG blocks, response helpers, MCP lifecycle.
- `tests/test_agent_extensions_rag.py`: existing RAG/cache/timeout/prompt tests plus 2.0 construction and cleanup tests.

### Task 1: Migrate shared plugin message and response helpers

**Files:**
- Modify: `plugins/agent_extensions/__init__.py`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Produces: `_make_response(content: str, success: bool = True) -> ToolResponse`, `_message_text(msg: Msg) -> str`, `_build_model(provider: str, model_name: str, base_url: str, api_key: str) -> ChatModelBase`, and DataBlock-based RAG content.

- [ ] **Step 1: Add helper tests**

Assert `_make_response("ok")` contains a `TextBlock`; `_message_text(AssistantMsg(name="Agent", content=[TextBlock(text="a"), TextBlock(text="b")])) == "a\nb"`; `_build_rag_content_blocks` returns `DataBlock` with `Base64Source.media_type` for every cached local image and retains textual descriptions for unavailable images without the old `asset_path` warning.

- [ ] **Step 2: Run helper tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k "response or content_blocks or message_text"`

Expected: FAIL on 1.x `ImageBlock`/raw response dictionaries.

- [ ] **Step 3: Implement 2.0 helpers**

Use:

```python
from agentscope.message import AssistantMsg, Base64Source, DataBlock, TextBlock, ToolResultState, UserMsg
from agentscope.tool import ToolResponse

def _message_text(msg):
    return msg.get_text_content() or ""

def _make_response(content, success=True):
    return ToolResponse(
        content=[TextBlock(text=str(content))],
        state=ToolResultState.SUCCESS if success else ToolResultState.ERROR,
    )
```

Read cached files, base64 encode bytes into `encoded`, and construct `DataBlock(source=Base64Source(data=encoded, media_type=_APIRequester._image_content_type(asset_path)))`.

- [ ] **Step 4: Verify helper and existing RAG tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k "rag or response or content_blocks"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
git commit -m "feat: migrate plugin helpers to agentscope 2 blocks"
```

### Task 2: Migrate the Unity subagent

**Files:**
- Modify: `plugins/agent_extensions/__init__.py`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Produces: unchanged `tool_unity_ar(task: str, info: str = "{}")` output contract.

- [ ] **Step 1: Add constructor, reply, and cleanup tests**

Patch `MCPClient`, `Toolkit`, and `Agent`. Assert Unity uses `StdioMCPConfig`, `is_stateful=True`, configured connection/execution timeouts, `await connect()` before Toolkit construction, `await agent.reply(UserMsg(name="User", content=prompt))`, and `await close()` in both success and raised-exception cases.

- [ ] **Step 2: Run Unity tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k unity`

Expected: FAIL on old client and `ReActAgent` constructors.

- [ ] **Step 3: Implement the Unity 2.0 path**

Construct provider credential/model with the same configuration as the main assistant, wrap each existing Unity custom callable as `FunctionTool(func=tool_func)`, build `Toolkit(mcps=[unity_client], tools=unity_tools)`, and construct:

```python
Agent(
    name="UnityAgent", system_prompt=unity_prompt, model=model,
    toolkit=toolkit, react_config=ReActConfig(max_iters=60),
)
```

Wrap the connected lifetime in `try/finally`. Return `_message_text(reply)` and preserve structured Markdown prompt requirements.

- [ ] **Step 4: Verify Unity behavior**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k unity`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
git commit -m "feat: migrate unity subagent to agentscope 2"
```

### Task 3: Migrate the Blender subagent

**Files:**
- Modify: `plugins/agent_extensions/__init__.py`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Produces: unchanged `tool_blender_model(task: str)` output contract.

- [ ] **Step 1: Add Blender lifecycle tests**

Assert HTTP/stdio transport matches current configuration, configured timeout reaches `HttpMCPConfig.timeout` and `MCPClient.execution_timeout`, Agent receives `system_prompt`, `reply()` receives `UserMsg`, and stateful cleanup runs after timeout and cancellation.

- [ ] **Step 2: Run Blender tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k blender`

Expected: FAIL on 1.x constructors.

- [ ] **Step 3: Implement Blender 2.0 construction**

Use `MCPClient`, connected before `Toolkit(mcps=[client])`, then `Agent(name="BlenderAgent", system_prompt=blender_prompt, model=model, toolkit=toolkit, react_config=ReActConfig(max_iters=60))`. Preserve the prompt sections requiring executed tools, object names, scene state, and absolute artifact paths.

- [ ] **Step 4: Verify Blender behavior**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k blender`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
git commit -m "feat: migrate blender subagent to agentscope 2"
```

### Task 4: Migrate process planning and task tools

**Files:**
- Modify: `plugins/agent_extensions/__init__.py`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Produces: unchanged `tool_generate_process(task: str, image_path: str = "", collection_name: str = "process", limit: int = 5) -> Any` and RAG/cache contracts, using AgentState task context.

- [ ] **Step 1: Add planning-tool tests**

Assert Toolkit receives `TaskCreate()`, `TaskGet()`, `TaskList()`, and `TaskUpdate()` from `agentscope.tool`; Agent receives `UserMsg` containing text plus local RAG `DataBlock`s; generated Markdown includes complete process JSON content and every output path.

- [ ] **Step 2: Run process tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k process`

Expected: FAIL while `PlanNotebook` and 1.x messages remain.

- [ ] **Step 3: Replace PlanNotebook**

```python
from agentscope.tool import TaskCreate, TaskGet, TaskList, TaskUpdate, Toolkit

toolkit = Toolkit(tools=[TaskCreate(), TaskGet(), TaskList(), TaskUpdate(), *process_tools])
process_agent = Agent(
    name="ProcessAgent", system_prompt=process_prompt, model=model,
    toolkit=toolkit, react_config=ReActConfig(max_iters=existing_max_iters),
)
```

Keep `_APIRequester` and all backend endpoints unchanged. Preserve the local overwrite cache before building DataBlocks.

- [ ] **Step 4: Verify process and RAG behavior**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k "process or rag or asset_cache"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
git commit -m "feat: migrate process subagent to agentscope 2 tasks"
```

### Task 5: Migrate the ComfyUI subagent

**Files:**
- Modify: `plugins/agent_extensions/__init__.py`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Produces: unchanged `tool_generate_image(task: str)` contract and structured list of generated image paths.

- [ ] **Step 1: Add ComfyUI reply and artifact tests**

Assert Agent refines the prompt through `reply(UserMsg(name="User", content=task))`; the resulting prompt is passed to `_APIRequester.text_to_image`; every generated path, actual positive prompt, negative prompt, dimensions, seed when available, and error appears in the structured Markdown result.

- [ ] **Step 2: Run ComfyUI tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k "comfyui or image_requires"`

Expected: FAIL on old Agent/message extraction.

- [ ] **Step 3: Implement the 2.0 path**

Build `Toolkit(tools=[])`, create `Agent(name="ComfyUIAgent", system_prompt=comfyui_prompt, model=model, toolkit=toolkit, react_config=ReActConfig(max_iters=60))`, use `await reply(UserMsg(name="User", content=task))`, and extract the prompt with `_message_text`. Preserve `_APIRequester.text_to_image` and its configured timeout.

- [ ] **Step 4: Verify ComfyUI and timeout behavior**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k "comfyui or image or timeout"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
git commit -m "feat: migrate comfyui subagent to agentscope 2"
```

### Task 6: Plugin phase gate

**Files:**
- Verify only

**Interfaces:**
- Produces: a fully 2.0 plugin ready for repository-wide cleanup.

- [ ] **Step 1: Run the complete plugin suite**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q`

Expected: PASS.

- [ ] **Step 2: Verify RAG has no direct database access**

Run: `rg -n "pymilvus|MilvusClient|psycopg|sqlalchemy|create_engine" plugins/agent_extensions`

Expected: no matches.

- [ ] **Step 3: Scan old AgentScope APIs**

Run: `rg -n "ReActAgent|InMemoryMemory|PlanNotebook|HttpStatefulClient|StdIOStatefulClient|ImageBlock|Msg\(" plugins/agent_extensions`

Expected: no runtime matches.

- [ ] **Step 4: Re-run prompt contract tests**

Run: `uv run pytest tests/test_agent_extensions_rag.py -q -k "structured_markdown or complete_file or artifact_paths or tool_results"`

Expected: PASS.

- [ ] **Step 5: Confirm owned files are clean**

Run: `git status --short -- plugins/agent_extensions tests/test_agent_extensions_rag.py`

Expected: no uncommitted changes after the task commits.
