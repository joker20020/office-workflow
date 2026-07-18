# SolidWorks Skill and Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the SolidWorks branch use a general main-agent prompt and an optional AR delivery Skill that produces verified native SolidWorks deliverables.

**Architecture:** The configured prompt and `DEFAULT_SYSTEM_PROMPT` are identical generic contracts. The existing manually registered `ar-assembly-delivery` Skill remains at the same path, but delegates its CAD phase to the public `tool_solidworks_model` subagent and describes only SolidWorks output handoff.

**Tech Stack:** Python, PyYAML, pytest, AgentScope 2 Skills, Markdown, YAML.

## Global Constraints

- Keep the Skill name and path `skills/ar-assembly-delivery` unchanged.
- Do not expose raw SolidWorks MCP tools through the main-agent prompt or the Skill.
- Require verified `.sldprt`, `.step`, `.stl`, and preview outputs for a successful CAD phase.
- Keep `agents/openai.yaml` ASCII-only and UTF-8 readable.

---

### Task 1: Define the SolidWorks prompt and Skill contract

**Files:**
- Modify: `tests/test_main_agent_system_prompt.py`

**Interfaces:**
- Consumes: `config/settings.yaml`, `src/agent/agent_integration.py`, and `skills/ar-assembly-delivery`.
- Produces: Tests requiring a generic, SolidWorks-aware prompt and a SolidWorks-only AR delivery Skill.

- [ ] **Step 1: Write the failing test**

```python
assert "通用任务代理" in prompt
assert "SolidWorks" in prompt
assert "tool_solidworks_model" in skill
assert ".sldprt" in skill and ".step" in skill and ".stl" in skill
assert "Blender" not in skill
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main_agent_system_prompt.py -q`

Expected: FAIL because this branch still has the fixed pipeline and Blender Skill text.

### Task 2: Replace the configured and fallback prompt

**Files:**
- Modify: `config/settings.yaml`
- Modify: `src/agent/agent_integration.py`

**Interfaces:**
- Consumes: `AgentIntegration._system_prompt()` returns configured non-empty text or `DEFAULT_SYSTEM_PROMPT`.
- Produces: Identical generic prompts that mention SolidWorks only as an on-demand native CAD option.

- [ ] **Step 1: Write minimal implementation**

```text
你是一个通用任务代理。理解用户目标、当前上下文和可用能力，并以最合适的方式推进任务。
- 任务需要原生三维 CAD 且 SolidWorks 能力可用时，优先使用 SolidWorks；不要把某个建模流程强加给不相关任务。
```

- [ ] **Step 2: Run prompt contract tests**

Run: `uv run pytest tests/test_main_agent_system_prompt.py -q`

Expected: prompt assertions pass; Skill assertions remain red until Task 3.

### Task 3: Convert the optional AR delivery Skill to SolidWorks

**Files:**
- Modify: `skills/ar-assembly-delivery/SKILL.md`
- Modify: `skills/ar-assembly-delivery/agents/openai.yaml`

**Interfaces:**
- Consumes: public `tool_solidworks_model(task, session_id=None)` and its structured Markdown result.
- Produces: SolidWorks Skill handoff requiring `.sldprt`, `.step`, `.stl`, preview, dimensions, feature tree, validation, and warnings.

- [ ] **Step 1: Write minimal implementation**

```markdown
3. 使用 `tool_solidworks_model` 完成原生 SolidWorks 建模。

- SolidWorks 阶段交接 `.sldprt`、`.step`、`.stl`、preview、尺寸、特征树、验证状态与警告。
```

- [ ] **Step 2: Set ASCII metadata**

```yaml
interface:
  display_name: "SolidWorks AR Assembly Delivery"
  short_description: "Verified AR assembly delivery using native SolidWorks CAD"
  default_prompt: "Use $ar-assembly-delivery to deliver a complete AR-assisted assembly solution with SolidWorks."
```

Expected: metadata display name is `SolidWorks AR Assembly Delivery` and contains only ASCII characters.

### Task 4: Validate and commit

**Files:**
- Verify: all modified files.

- [ ] **Step 1: Run focused tests and Skill validation**

Run: `uv run pytest tests/test_main_agent_system_prompt.py -q` and `python -X utf8 C:\Users\40599\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\ar-assembly-delivery`

Expected: all focused tests pass and the Skill validator reports success.

- [ ] **Step 2: Run repository verification**

Run: `uv run pytest -q` and `git diff --check`

Expected: test suite passes and diff check prints no errors.

- [ ] **Step 3: Commit**

```bash
git add config/settings.yaml src/agent/agent_integration.py skills/ar-assembly-delivery tests/test_main_agent_system_prompt.py docs/superpowers
git commit -m "feat: tailor prompt and skill for solidworks"
```
