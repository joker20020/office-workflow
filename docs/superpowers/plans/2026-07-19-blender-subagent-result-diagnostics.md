# Blender Subagent Result Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Blender subagent activity readable during streaming and report the real MCP/reply terminal state when no final handoff is returned.

**Architecture:** The plugin captures an optional execution trace while consuming AgentScope events and turns tool lifecycle events into concise readable progress. The chat panel keeps decoding the private transport protocol and also suppresses it if it unexpectedly arrives in a normal text block.

**Tech Stack:** Python 3.12, AgentScope 2.x events, pytest, Qt chat blocks.

## Global Constraints

- Modify `main` only; do not touch the `solidworks` branch.
- Keep final structured Markdown handoff validation unchanged for non-empty replies.
- Never automatically retry Blender MCP calls, because retries can duplicate model edits or exports.
- Stream result prose incrementally, but never expose raw JSON arguments or private protocol markers in chat.

---

### Task 1: Capture and expose terminal subagent diagnostics

**Files:**
- Modify: `tests/test_agent_extensions_rag.py:1520,2218`
- Modify: `plugins/agent_extensions/__init__.py:154-220,2460-2474`

**Interfaces:**
- Produces: `_reply_subagent_with_progress(..., execution_trace: dict[str, Any] | None = None) -> AssistantMsg`.
- Produces: Blender empty-reply failure text containing the last tool, result state, and reply finish reason.

- [ ] **Step 1: Write the failing test**

```python
trace = {}
reply = await _reply_subagent_with_progress(agent, message, execution_trace=trace)
assert reply.get_text_content() == ""
assert trace["last_tool_name"] == "mcp__blender_mcp__get_scene_info"
assert trace["tool_result_state"] is None
```

- [ ] **Step 2: Verify RED**

Run `uv run pytest tests/test_agent_extensions_rag.py -k "missing_tool_result or blender_empty_reply" -q`; it must fail because `execution_trace` is not supported and the current failure is generic.

- [ ] **Step 3: Implement the minimal trace collector**

```python
async def _reply_subagent_with_progress(..., execution_trace=None):
    # Save ToolCallStart/End, ToolResultStart/End, and ReplyEnd terminal data.
    ...

def _subagent_empty_reply_failure(subject, trace):
    # Use _subagent_failure and name the last MCP tool plus missing/failed result.
    ...
```

- [ ] **Step 4: Verify GREEN**

Run `uv run pytest tests/test_agent_extensions_rag.py -k "missing_tool_result or blender_empty_reply" -q`; it must pass.

- [ ] **Step 5: Commit**

Run `git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py` then `git commit -m "fix: diagnose empty blender subagent replies"`.

### Task 2: Emit readable streaming activity and prevent marker leakage

**Files:**
- Modify: `tests/test_agent_extensions_rag.py:1520-1560`
- Modify: `tests/test_chat_panel.py`
- Modify: `plugins/agent_extensions/__init__.py:154-220`
- Modify: `src/ui/chat/chat_panel.py:119-175,293-298`

**Interfaces:**
- Produces readable progress strings such as `Reading Blender scene information`.
- Produces `_event_to_block_updates()` results that do not contain `agentscope-subagent-event:`.

- [ ] **Step 1: Write the failing tests**

```python
assert any(event["text"] == "Reading Blender scene information" for event in events)
assert not any(event["text"] in {"{", '"user_prompt"'} for event in events)
assert all("agentscope-subagent-event:" not in str(update) for update in updates)
```

- [ ] **Step 2: Verify RED**

Run `uv run pytest tests/test_agent_extensions_rag.py tests/test_chat_panel.py -k "readable_and_not_json or private_subagent_marker" -q`; it must fail because JSON fragments are published and text-block markers are ordinary text.

- [ ] **Step 3: Implement minimal readable assembly**

```python
def _readable_tool_activity(tool_name: str, phase: str) -> str:
    # Map known Blender names to readable labels; use a generic fallback.
    ...

# Accumulate ToolCallDeltaEvent input internally; publish only start/end summaries.
# Keep ToolResultTextDeltaEvent prose incremental.
# Decode private markers on TextBlockDeltaEvent before rendering visible text.
```

- [ ] **Step 4: Verify GREEN**

Run `uv run pytest tests/test_agent_extensions_rag.py tests/test_chat_panel.py -k "readable_and_not_json or private_subagent_marker" -q`; it must pass.

- [ ] **Step 5: Commit**

Run `git add plugins/agent_extensions/__init__.py src/ui/chat/chat_panel.py tests/test_agent_extensions_rag.py tests/test_chat_panel.py` then `git commit -m "fix: present subagent tool streaming clearly"`.

### Task 3: Verify integrated behavior

**Files:**
- Verify: `plugins/agent_extensions/__init__.py`
- Verify: `src/ui/chat/chat_panel.py`
- Verify: `tests/test_agent_extensions_rag.py`
- Verify: `tests/test_chat_panel.py`

- [ ] **Step 1: Run all affected modules**

Run `uv run pytest tests/test_agent_extensions_rag.py tests/test_chat_panel.py -q`; expected result: PASS.

- [ ] **Step 2: Verify scope**

Run `git -c safe.directory=E:/GitHub/office-workflow branch --show-current`; expected result: `main`.
