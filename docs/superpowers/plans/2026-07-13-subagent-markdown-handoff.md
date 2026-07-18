# Subagent Markdown Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all four `agent_extensions` subagents return detailed, structured Markdown handoffs through prompt-only changes.

**Architecture:** Keep every AgentScope call and return assembler unchanged. Strengthen each `ReActAgent.sys_prompt` with a shared Markdown contract plus domain-specific evidence and artifact requirements; protect the contract with source-level regression tests that require no external services.

**Tech Stack:** Python 3.11, pytest, AgentScope 1.0.17

## Global Constraints

- Modify prompts only in production code.
- Do not add structured output models, memory parsing, filesystem scanning, or response post-processing.
- Preserve the existing public tool signatures and `ToolResponse` behavior.
- Never allow a subagent to invent a file path or report an unverified action as complete.

---

### Task 1: Add prompt-contract regression tests

**Files:**
- Modify: `tests/test_agent_extensions_rag.py`
- Test: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Consumes: source text from `plugins/agent_extensions/__init__.py`
- Produces: regression tests covering shared Markdown headings and per-agent handoff requirements

- [ ] **Step 1: Write the failing tests**

Add tests that isolate each `sys_prompt` source region and assert:

```python
for heading in (
    "# 执行结果",
    "## 状态",
    "## 完成摘要",
    "## 生成文件",
    "## 具体结果",
    "## 执行记录",
    "## 警告与未完成项",
):
    assert heading in prompt
```

Also assert the process prompt requires complete JSON content, the image prompt requires each output and actual prompt, the Blender prompt requires saved/exported paths and object details, and the Unity prompt requires project/scene/script paths and executed tool results.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_extensions_rag.py -k "subagent_prompt" -q`

Expected: FAIL because the current prompts do not contain the required Markdown contract.

- [ ] **Step 3: Keep production code unchanged**

Review `git diff -- plugins/agent_extensions/__init__.py` and confirm this task introduced no production change.

### Task 2: Strengthen all four subagent prompts

**Files:**
- Modify: `plugins/agent_extensions/__init__.py:690`
- Modify: `plugins/agent_extensions/__init__.py:776`
- Modify: `plugins/agent_extensions/__init__.py:940`
- Modify: `plugins/agent_extensions/__init__.py:1021`
- Test: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Consumes: the shared Markdown contract asserted by Task 1
- Produces: final subagent responses that existing wrappers return unchanged as structured Markdown

- [ ] **Step 1: Add the shared final-response contract to each prompt**

Require every final answer to include the exact seven headings, explicitly report `无` when there are no files, prefer absolute paths, use `路径未提供` when tools do not expose a path, and distinguish verified execution from plans or suggestions.

- [ ] **Step 2: Add domain-specific evidence requirements**

Require the process agent to embed every generated JSON file's complete content; the image agent to report every output and actual generation prompt; the Blender agent to report objects, dimensions, materials, views, and saved/exported files; and the Unity agent to report scenes, GameObjects, components, scripts, assets, AR flow, artifact paths, and MCP/custom-tool results.

- [ ] **Step 3: Run focused tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_extensions_rag.py -k "subagent_prompt" -q`

Expected: all selected tests PASS.

- [ ] **Step 4: Run the full plugin-focused test file**

Run: `.venv\Scripts\python.exe -m pytest tests/test_agent_extensions_rag.py -q`

Expected: all tests PASS.

- [ ] **Step 5: Verify scope and syntax**

Run: `.venv\Scripts\python.exe -m py_compile plugins/agent_extensions/__init__.py`

Expected: exit code 0.

Run: `git -c safe.directory=E:/GitHub/office-workflow diff --check -- plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py`

Expected: no output.

### Task 3: Review the prompt-only implementation

**Files:**
- Review: `plugins/agent_extensions/__init__.py`
- Review: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Consumes: tested prompt changes from Task 2
- Produces: evidence that no response assembly or public API behavior changed

- [ ] **Step 1: Inspect the scoped diff**

Run: `git -c safe.directory=E:/GitHub/office-workflow diff -- plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py`

Expected: production changes are limited to the four `sys_prompt` strings; test changes only validate those strings.

- [ ] **Step 2: Confirm unrelated user changes remain untouched**

Run: `git -c safe.directory=E:/GitHub/office-workflow status --short`

Expected: `config/settings.yaml` remains present as an unrelated user change and is not modified by this plan.

- [ ] **Step 3: Report results without staging or committing**

Summarize changed prompts, focused test results, syntax result, and any pre-existing unrelated worktree changes. Do not stage or commit unless the user explicitly requests it.
