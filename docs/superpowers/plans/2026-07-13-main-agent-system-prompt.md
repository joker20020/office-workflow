# Main Agent System Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the main agent's short system prompt with a gated four-stage orchestration prompt that preserves artifacts and stops immediately on incomplete stages.

**Architecture:** Keep runtime code and tool APIs unchanged. Store the orchestration contract entirely in `config/settings.yaml`, and protect its fixed order, stage gates, context handoff, failure behavior, and final reporting requirements with a static YAML test.

**Tech Stack:** YAML, Python 3.11, PyYAML, pytest

## Global Constraints

- Only modify `config/settings.yaml` in production configuration.
- Preserve `language`, `recent_workflows`, and `theme` exactly.
- Do not modify tool signatures, subagent prompts, response assembly, runtime code, or dependencies.
- Every task must run `tool_generate_process`, `tool_generate_image`, `tool_blender_model`, then `tool_unity_ar` in that order.
- Any partial success, failure, missing required artifact, contradiction, or unverified result stops the pipeline immediately.
- Never invent file paths, process content, or tool results.

---

### Task 1: Implement and verify the gated system prompt

**Files:**
- Create: `tests/test_main_agent_system_prompt.py`
- Modify: `config/settings.yaml:13`

**Interfaces:**
- Consumes: `system_prompt` loaded from `config/settings.yaml`
- Produces: a plain string consumed unchanged by `src/agent/agent_integration.py` as `ReActAgent.sys_prompt`

- [ ] **Step 1: Write the failing configuration tests**

Create `tests/test_main_agent_system_prompt.py`:

```python
# -*- coding: utf-8 -*-
from pathlib import Path

import yaml


SETTINGS_PATH = Path(__file__).parents[1] / "config" / "settings.yaml"


def _load_system_prompt() -> str:
    settings = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))
    return settings["system_prompt"]


def test_main_agent_system_prompt_has_fixed_tool_order():
    prompt = _load_system_prompt()
    tool_names = (
        "tool_generate_process",
        "tool_generate_image",
        "tool_blender_model",
        "tool_unity_ar",
    )

    positions = [prompt.index(name) for name in tool_names]

    assert positions == sorted(positions)
    assert "不得跳过或调换阶段" in prompt


def test_main_agent_system_prompt_gates_each_stage_and_stops_on_failure():
    prompt = _load_system_prompt()

    assert "只有当前阶段明确返回“成功”" in prompt
    assert "部分成功" in prompt
    assert "立即停止" in prompt
    assert "不调用任何后续工具" in prompt
    assert "未验证" in prompt


def test_main_agent_system_prompt_passes_complete_artifact_context():
    prompt = _load_system_prompt()

    for requirement in (
        "完整工艺与工步内容",
        "工序和工步 JSON 文件路径",
        "每张图片的文件路径",
        ".blend 工程路径",
        "导出模型、材质、贴图和渲染图路径",
        "info 参数",
        "工序工步 JSON",
    ):
        assert requirement in prompt

    assert "不得猜测" in prompt


def test_main_agent_system_prompt_requires_recoverable_final_report():
    prompt = _load_system_prompt()

    for requirement in (
        "已成功完成的阶段",
        "已生成文件的全部已知路径",
        "停止所在阶段",
        "恢复执行前需要满足的条件",
        "四个阶段全部成功",
        "按阶段分类的全部生成文件路径",
    ):
        assert requirement in prompt
```

- [ ] **Step 2: Run tests and verify the RED state**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_main_agent_system_prompt.py -q
```

Expected: four failures because the existing prompt does not contain the fixed tool names and stage-gate contract.

- [ ] **Step 3: Replace only the YAML system prompt**

Replace the current single-quoted `system_prompt` with this block scalar, leaving every other YAML key unchanged:

```yaml
system_prompt: |-
  你是一个负责完整 AR 辅助装配项目的计划与编排智能体。你的职责是理解用户目标、制定执行计划、按固定顺序调用子智能体工具、校验每个阶段的结果，并把上游的完整结果传递给下游。你不能替代工具虚构工艺、文件、路径或执行结果。

  ## 固定执行流程

  每个用户任务都必须依次完成以下四个阶段：
  1. 调用 tool_generate_process 生成完整工艺和工步文件。
  2. 调用 tool_generate_image 根据工艺生成所需图片资源。
  3. 调用 tool_blender_model 根据工艺和图片结果完成 Blender 建模。
  4. 调用 tool_unity_ar，使用之前全部结果完成 Unity AR 辅助装配程序。

  不得跳过或调换阶段。只有当前阶段明确返回“成功”，且下游所需的具体内容、文件路径和验证信息齐全时，才能调用下一阶段工具。

  ## 子智能体结果校验

  每次工具调用后，必须阅读子智能体结构化 Markdown 中的“状态”“完成摘要”“生成文件”“具体结果”“执行记录”“警告与未完成项”。只有状态为“成功”且结果完整一致时才视为阶段成功。

  如果状态为“部分成功”或“失败”，工具没有返回结果，缺少下游必需内容或路径，结果互相矛盾，或者关键文件和操作标记为“未验证”，必须立即停止，不调用任何后续工具。

  不得把计划、建议、准备调用或已经发起调用视为完成，不得猜测工具没有返回的文件路径或内容。

  ## 上下文传递

  工艺阶段成功后，向图片、Blender 和 Unity 工具传递完整工艺与工步内容、工序和工步 JSON 文件路径、关键工艺约束、警告和不确定项，不能只传摘要。

  图片阶段成功后，向 Blender 和 Unity 工具传递每张图片的文件路径、用途、实际生成提示词和验证状态。

  Blender 阶段成功后，向 Unity 工具传递 .blend 工程路径、导出模型、材质、贴图和渲染图路径，以及对象名称、层级、尺寸、关键建模结果和验证状态。

  调用 tool_unity_ar 时，info 参数必须包含根据工艺结果整理的完整工序工步 JSON；task 参数必须同时说明工艺要求、图片资源、Blender 资产路径和预期 AR 行为。缺少 Unity 必需的模型或资源路径时不得进入 Unity 阶段。

  ## 重试与失败处理

  只允许为补齐当前阶段的必需信息而重试当前阶段。不得自动重复已经明确成功的阶段，也不得在失败后假设结果并继续。

  停止流水线时，向用户说明已成功完成的阶段、已生成文件的全部已知路径、停止所在阶段、子智能体返回的原始失败原因或警告，以及恢复执行前需要满足的条件。

  ## 最终交付

  四个阶段全部成功后，使用 Markdown 汇总总体状态、四阶段完成摘要、按阶段分类的全部生成文件路径、关键工艺信息、图片资源、Blender 模型信息、Unity 配置和警告。没有警告时明确写“无”。

  最终答复必须完全基于工具实际返回内容，不得遗漏已生成文件，也不得声称未经验证的内容已经完成。
```

- [ ] **Step 4: Run focused tests and verify the GREEN state**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_main_agent_system_prompt.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Run related regression tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_config_manager.py tests\test_main_agent_system_prompt.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Verify YAML parsing and scoped whitespace**

Run:

```powershell
.venv\Scripts\python.exe -c "from pathlib import Path; import yaml; d=yaml.safe_load(Path('config/settings.yaml').read_text(encoding='utf-8')); assert isinstance(d['system_prompt'], str); print(len(d['system_prompt']))"
git -c safe.directory=E:/GitHub/office-workflow diff --check -- config/settings.yaml tests/test_main_agent_system_prompt.py
```

Expected: Python prints a positive prompt length, both commands exit 0, and `diff --check` prints nothing.

- [ ] **Step 7: Inspect scope without changing the existing index**

Run:

```powershell
git -c safe.directory=E:/GitHub/office-workflow diff -- config/settings.yaml tests/test_main_agent_system_prompt.py
git -c safe.directory=E:/GitHub/office-workflow status --short
```

Expected: implementation changes are limited to the system prompt and its new test. Existing staged plugin, RAG test, and generated sandbox entries remain untouched.

- [ ] **Step 8: Report without staging or committing implementation files**

Report focused test results, YAML validation, scoped diff-check, and the pre-existing staged index state. Do not stage or commit `config/settings.yaml` or `tests/test_main_agent_system_prompt.py` unless the user explicitly requests it.
