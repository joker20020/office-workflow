# AgentScope 2.0 Core Agent and Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the main assistant's ReActAgent, model constructors, memory, hooks, chat execution, and interruption with AgentScope 2.0 Agent, AgentState, event streaming, and Middleware.

**Architecture:** `AgentIntegration` constructs provider credentials/models and directly consumes `reply_stream()`. Each event updates one `AssistantMsg` with `append_event()` and is forwarded through the existing callback list; hooks are removed rather than emulated.

**Tech Stack:** AgentScope 2.0.4 Agent/Event/Middleware APIs, asyncio, PySide6 callbacks, pytest

## Global Constraints

- Preserve synchronous and asynchronous `AgentIntegration` public methods and UI-visible behavior.
- Use AgentScope 2.0 events for streaming; do not recreate `post_print` as middleware.
- Keep existing system prompts and model-provider defaults.
- Preserve partial assistant output on cancellation and distinguish interruption from errors.
- Do not modify Toolkit/MCP/Skill behavior beyond constructor seams; plan 03 owns those.

---

## File map

- `src/agent/agent_integration.py`: provider model factory, Agent lifecycle, reply stream, AgentState, cancellation.
- `src/ui/chat/chat_panel.py`: consume the project callback payload without hook terminology.
- `tests/test_agent_integration.py`: construction, reply, history/state synchronization, cancellation.
- `tests/test_streaming_hooks.py`: replaced with 2.0 event reconstruction and middleware tests.
- `tests/test_multimodal_integration.py`: verify UI input becomes DataBlock.

### Task 1: Define event reconstruction behavior

**Files:**
- Replace: `tests/test_streaming_hooks.py`

**Interfaces:**
- Produces: requirements for `AgentIntegration._consume_reply_stream(inputs: Msg) -> Msg` and `_notify_stream_event(event: AgentEvent) -> None`.

- [ ] **Step 1: Replace old hook-registration tests with event accumulation tests**

```python
from agentscope.event import ReplyEndEvent, TextBlockDeltaEvent, TextBlockStartEvent
from agentscope.message import AssistantMsg

def test_stream_events_rebuild_assistant_message():
    msg = AssistantMsg(name="Assistant", content=[], id="reply-1")
    for event in (
        TextBlockStartEvent(reply_id="reply-1", block_id="text-1"),
        TextBlockDeltaEvent(reply_id="reply-1", block_id="text-1", delta="完成"),
        ReplyEndEvent(session_id="session-1", reply_id="reply-1"),
    ):
        msg.append_event(event)
    assert msg.get_text_content() == "完成"
    assert msg.finished_at is not None
```

Use `ReplyStartEvent(session_id="session-1", reply_id="reply-1", name="Assistant")`, block events with `reply_id="reply-1"`, and `ReplyEndEvent(session_id="session-1", reply_id="reply-1")`; these are the complete required 2.0.4 fields for this test sequence.

- [ ] **Step 2: Add callback and interruption tests**

Use a fake agent whose `reply_stream()` yields text start/delta/end and `ReplyEndReason.INTERRUPTED`. Assert callbacks receive the original event objects in order, history stores the accumulated `AssistantMsg`, and `_last_response_interrupted` is true only for interrupted replies.

- [ ] **Step 3: Add a real MiddlewareBase ordering test**

Define two `MiddlewareBase` subclasses implementing `on_reply`; each appends `before-X`, yields all items from `next_handler`, then appends `after-X`. Assert order is `before-1, before-2, after-2, after-1`.

- [ ] **Step 4: Run the red suite**

Run: `uv run pytest tests/test_streaming_hooks.py -q`

Expected: FAIL because `AgentIntegration` still uses 1.x hooks and has no event consumer.

- [ ] **Step 5: Commit the red tests**

```bash
git add tests/test_streaming_hooks.py
git commit -m "test: define agentscope 2 event streaming behavior"
```

### Task 2: Migrate credential and model construction

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`

**Interfaces:**
- Produces: `_create_model(provider: str, model_name: str, base_url: str, api_key: str) -> ChatModelBase`.

- [ ] **Step 1: Add provider constructor tests**

Patch `OpenAIChatModel`, `DeepSeekChatModel`, and `DashScopeChatModel`. For OpenAI assert `OpenAICredential(api_key="key", base_url="https://api.openai.com/v1")` and `OpenAIChatModel(credential=credential, model="gpt-4o", stream=True)`; use the existing defaults `deepseek-chat`/`https://api.deepseek.com` and `qwen-turbo`/the configured DashScope URL for the other providers.

- [ ] **Step 2: Run the provider tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k "model or provider"`

Expected: FAIL on old `model_name=`/`api_key=` constructor calls.

- [ ] **Step 3: Implement 2.0 model construction**

Use these exact imports and shapes:

```python
from agentscope.credential import DeepSeekCredential, DashScopeCredential, OpenAICredential
from agentscope.model import DeepSeekChatModel, DashScopeChatModel, OpenAIChatModel

credential = OpenAICredential(api_key=api_key, base_url=final_url)
model = OpenAIChatModel(credential=credential, model=final_model, stream=True)
```

Use the provider-specific credential/model for DeepSeek and DashScope. Do not pass a 1.x formatter separately; 2.0 models own their formatter.

- [ ] **Step 4: Verify provider construction**

Run: `uv run pytest tests/test_agent_integration.py -q -k "model or provider"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/agent_integration.py tests/test_agent_integration.py
git commit -m "feat: migrate main assistant models to agentscope 2"
```

### Task 3: Construct Agent with AgentState and ReActConfig

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`

**Interfaces:**
- Produces: `Agent(name, system_prompt, model, toolkit, state, react_config)` stored in `self._agent`.

- [ ] **Step 1: Add Agent construction and state-sync tests**

Assert `Agent` is called with the configured `system_prompt`, `AgentState(context=history.get_messages())`, and `ReActConfig(max_iters=50, interruption_raise_cancelled_error=False)`. Assert switching sessions assigns a fresh `AgentState` context without `InMemoryMemory`.

- [ ] **Step 2: Run the focused tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k "initialize or sync or state"`

Expected: FAIL while `ReActAgent`, `sys_prompt`, and `InMemoryMemory` remain.

- [ ] **Step 3: Replace the core constructor**

```python
from agentscope.agent import Agent, ReActConfig
from agentscope.state import AgentState

self._agent = Agent(
    name="Assistant",
    system_prompt=system_prompt,
    model=model,
    toolkit=self._toolkit,
    state=AgentState(context=self._history.get_messages()),
    react_config=ReActConfig(max_iters=50),
)
```

Delete formatter and memory fields. Make `_sync_history_to_memory` update `self._agent.state.context`; rename its docstring to state/context synchronization while retaining the method name temporarily only if UI/tests call it.

- [ ] **Step 4: Verify construction and synchronization**

Run: `uv run pytest tests/test_agent_integration.py -q -k "initialize or sync or state"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/agent_integration.py tests/test_agent_integration.py
git commit -m "feat: construct agentscope 2 main agent"
```

### Task 4: Replace hooks and agent calls with reply_stream

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `src/ui/chat/chat_panel.py`
- Modify: `tests/test_streaming_hooks.py`
- Modify: `tests/test_multimodal_integration.py`

**Interfaces:**
- Consumes: 2.0 `UserMsg` and Agent event stream.
- Produces: existing `chat()`/`chat_async()` return text plus callback delivery of each event.

- [ ] **Step 1: Convert UI inputs to 2.0 messages**

Use `UserMsg(name="User", content=content_blocks)`; convert `image`, `audio`, and `video` UI blocks to `DataBlock(source=URLSource(url=block["url"], media_type=media_type))` or `DataBlock(source=Base64Source(data=block["data"], media_type=media_type))`. Remove `_create_image_source`, `_create_audio_source`, and `_create_video_source` duplication in favor of one `_create_data_block`.

- [ ] **Step 2: Implement the stream consumer**

```python
async def _consume_reply_stream(self, inputs: Msg) -> Msg:
    reply = AssistantMsg(name="Assistant", content=[], id=self._agent.state.reply_id)
    async for event in self._agent.reply_stream(inputs=inputs):
        reply.append_event(event)
        self._notify_stream_event(event)
    return reply
```

Derive the final reply id from `ReplyStartEvent` if AgentScope changes it before the first block; initialize or replace the accumulator at that event. Persist the user and assistant messages once each.

- [ ] **Step 3: Remove hook plumbing and update the UI callback description**

Delete `_create_streaming_hook` and `register_instance_hook`. Keep `register_streaming_callback`/`unregister_streaming_callback`, but callbacks now receive `(agent, {"event": event}, event)` so the existing three-argument call shape is preserved while the UI is migrated. Update `chat_panel.py` to dispatch on event class/type and remove references to `post_print`.

- [ ] **Step 4: Verify event and multimodal behavior**

Run: `uv run pytest tests/test_streaming_hooks.py tests/test_multimodal_integration.py tests/test_agent_integration.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/agent_integration.py src/ui/chat/chat_panel.py tests/test_streaming_hooks.py tests/test_multimodal_integration.py tests/test_agent_integration.py
git commit -m "feat: stream main assistant with agentscope 2 events"
```

### Task 5: Migrate interruption and shutdown

**Files:**
- Modify: `src/agent/agent_integration.py`
- Modify: `tests/test_agent_integration.py`

**Interfaces:**
- Produces: cancellation of the active asyncio task and `UserInterruptEvent` cleanup for parked replies.

- [ ] **Step 1: Add active and parked interruption tests**

Store a fake running task and assert `interrupt()` schedules `task.cancel()`. For a fake parked agent, assert the next reply input is `UserInterruptEvent(reason="用户中断")`; partial accumulated output remains in history and no generic error callback is sent.

- [ ] **Step 2: Run the interruption tests**

Run: `uv run pytest tests/test_agent_integration.py -q -k interrupt`

Expected: FAIL because interruption currently injects a 1.x system `Msg`.

- [ ] **Step 3: Implement task ownership and cleanup**

Set `self._active_reply_task = asyncio.current_task()` around `_consume_reply_stream` in `try/finally`. `interrupt()` uses `loop.call_soon_threadsafe(task.cancel)` for a running task. When AgentScope emits a confirmation/external-execution requirement, store its `reply_id`, mark the reply parked, and use `await agent.reply(UserInterruptEvent(reply_id=parked_reply_id))` during cleanup.

- [ ] **Step 4: Verify interruption and phase suite**

Run: `uv run pytest tests/test_agent_integration.py tests/test_streaming_hooks.py tests/test_multimodal_integration.py tests/test_chat_panel.py -q`

Expected: PASS.

- [ ] **Step 5: Commit and scan**

Run: `rg -n "ReActAgent|InMemoryMemory|register_.*hook|post_print|agent\(msg\)" src/agent/agent_integration.py src/ui/chat/chat_panel.py`

Expected: no runtime matches.

```bash
git add src/agent/agent_integration.py tests/test_agent_integration.py
git commit -m "feat: migrate agent interruption to agentscope 2"
```
