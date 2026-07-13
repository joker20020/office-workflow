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
