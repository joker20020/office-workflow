# Subagent Final Message Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve terminal AgentScope subagent messages so Blender and Unity receive their final handoff after MCP calls.

**Architecture:** `_reply_subagent_with_progress()` consumes `_reply()` when it is available, handles `Msg` separately from events, and returns the terminal message. It falls back to `reply_stream()` for compatibility and records missing terminal events in its optional trace.

**Tech Stack:** Python, AgentScope 2.x, pytest-asyncio.

## Global Constraints

- Apply to `main` only.
- Preserve progress streaming and the public-stream fallback.
- Do not retry any MCP operation.

---

### Task 1: Preserve final subagent messages

**Files:**
- Modify: `tests/test_agent_extensions_rag.py`
- Modify: `plugins/agent_extensions/__init__.py`

- [ ] **Step 1: Write failing tests**

```python
async def test_subagent_reply_uses_terminal_message_from_private_stream():
    reply = await _reply_subagent_with_progress(agent_with_private_reply())
    assert reply.get_text_content() == "final handoff"

async def test_subagent_trace_marks_missing_terminal_events():
    trace = {}
    await _reply_subagent_with_progress(agent_with_abrupt_private_reply(), execution_trace=trace)
    assert trace["terminal_message_received"] is False
    assert trace["reply_end_received"] is False
```

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_agent_extensions_rag.py -k "terminal_message or missing_terminal_events" -q`; expected: failing because `_reply()` is not consumed and the trace keys do not exist.

- [ ] **Step 3: Implement the smallest stream selection change**

```python
private_reply = getattr(agent, "_reply", None)
stream = private_reply(inputs=inputs) if callable(private_reply) else agent.reply_stream(inputs=inputs)
async for item in stream:
    if isinstance(item, Msg):
        terminal_message = item
        continue
    # Preserve existing event handling.
return terminal_message or rebuilt_reply
```

- [ ] **Step 4: Verify GREEN**

Run `python -m pytest tests/test_agent_extensions_rag.py -k "terminal_message or missing_terminal_events" -q`; expected: PASS.

- [ ] **Step 5: Run affected modules and commit**

Run `python -m pytest tests/test_agent_extensions_rag.py tests/test_chat_panel.py -q`, then commit the plugin, tests, and this plan with message `fix: preserve subagent final messages`.
