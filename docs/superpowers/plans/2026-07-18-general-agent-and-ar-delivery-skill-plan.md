# General Agent and AR Delivery Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed AR pipeline main prompt with a general-agent prompt and provide the former pipeline as an optional project skill.

**Architecture:** `config/settings.yaml` supplies the installed prompt and `AgentIntegration._system_prompt()` provides an equivalent default when configuration is absent. The optional `skills/ar-assembly-delivery` package contains the specialised execution contract and is manually registered through the existing Skill settings UI.

**Tech Stack:** Python 3.11, PyYAML, pytest, AgentScope 2 skill directories.

## Implementation status

- [x] Replaced fixed-pipeline tests with general-prompt and optional-skill contracts.
- [x] Updated the configured prompt and hard-coded fallback to the same general-agent rules.
- [x] Created and UTF-8 validated the manually registered AR delivery Skill.
- [x] Completed focused checks, Skill validation, and the full test suite.

## Global Constraints

- Do not auto-register the project skill.
- Do not force a global process/image/model/Unity sequence in either main prompt.
- Preserve the requirement that agents do not invent tool results, artifact paths, or verification outcomes.

---

### Task 1: Add prompt and skill contract regression coverage

**Files:**

- Create: `tests/test_system_prompt.py`

**Interfaces:**

- `AgentIntegration._system_prompt() -> str` returns the configured or fallback general prompt.
- `skills/ar-assembly-delivery/SKILL.md` provides the optional specialised workflow.

- [ ] Write failing tests that assert the main prompt contains general tool-selection guidance, excludes `tool_generate_process` and mandatory fixed-stage wording, and that the skill has valid `name`/`description` frontmatter plus AR handoff guidance.
- [ ] Run `uv run pytest tests/test_system_prompt.py -q` and confirm the current configuration fails because it still embeds the fixed pipeline and the skill directory is absent.
- [ ] Replace the configured and fallback prompts, initialise the project skill directory, and write the concise specialised workflow in `SKILL.md`.
- [ ] Run `uv run pytest tests/test_system_prompt.py -q` and confirm it passes.

### Task 2: Validate and regress the migration

**Files:**

- Modify: `config/settings.yaml`
- Modify: `src/agent/agent_integration.py`
- Create: `skills/ar-assembly-delivery/SKILL.md`
- Modify: `tests/test_system_prompt.py`

- [ ] Run the skill validator against `skills/ar-assembly-delivery`.
- [ ] Run `uv run pytest tests/test_system_prompt.py tests/test_agent_integration.py -q` and then `uv run pytest -q`.
- [ ] Commit the prompt migration, skill, tests, and design records.
