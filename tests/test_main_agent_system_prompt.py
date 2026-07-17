from pathlib import Path

import yaml

SETTINGS_PATH = Path(__file__).parents[1] / "config" / "settings.yaml"


def _load_system_prompt() -> str:
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))["system_prompt"]


def test_main_agent_system_prompt_has_fixed_tool_order():
    prompt = _load_system_prompt()
    tool_names = (
        "tool_generate_process",
        "tool_generate_image",
        "tool_solidworks_model",
        "tool_unity_ar",
    )
    positions = [prompt.index(name) for name in tool_names]
    assert positions == sorted(positions)
    assert "不得跳过或调换阶段" in prompt


def test_main_agent_system_prompt_gates_each_stage_and_stops_on_failure():
    prompt = _load_system_prompt()
    for text in ("明确返回“成功”", "部分成功", "立即停止", "不调用后续工具", "未验证"):
        assert text in prompt


def test_main_agent_passes_complete_solidworks_artifacts_to_unity():
    prompt = _load_system_prompt()
    for text in (
        "native model",
        "STEP",
        "STL",
        "preview",
        "dimensions",
        "feature tree",
        "validation",
        "warnings",
        "工序工步 JSON",
        "info 参数",
        "task 参数",
    ):
        assert text in prompt


def test_main_agent_uses_only_the_solidworks_plugin_subagent_for_modeling():
    prompt = _load_system_prompt()
    assert "只调用公开的 tool_solidworks_model 子智能体" in prompt
    assert "原始 SolidWorks MCP 工具" in prompt
