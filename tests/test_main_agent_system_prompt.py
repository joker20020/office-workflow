"""Contracts for the general main agent prompt and optional AR delivery skill."""

from pathlib import Path
from types import SimpleNamespace

import yaml

PROJECT_ROOT = Path(__file__).parents[1]
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"
AR_DELIVERY_SKILL = PROJECT_ROOT / "skills" / "ar-assembly-delivery" / "SKILL.md"
AR_DELIVERY_METADATA = AR_DELIVERY_SKILL.parent / "agents" / "openai.yaml"


def _load_system_prompt() -> str:
    settings = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))
    return settings["system_prompt"]


def test_configured_main_prompt_is_general_and_not_a_fixed_pipeline():
    prompt = _load_system_prompt()

    assert "通用任务代理" in prompt
    assert "按需选择" in prompt
    assert "不得虚构" in prompt
    for prohibited in (
        "tool_generate_process",
        "tool_generate_image",
        "tool_blender_model",
        "tool_unity_ar",
        "固定执行流程",
        "四个阶段",
    ):
        assert prohibited not in prompt


def test_hard_coded_fallback_is_the_same_general_agent_contract():
    from src.agent.agent_integration import AgentIntegration

    agent = object.__new__(AgentIntegration)
    agent.config = SimpleNamespace(get=lambda _key, default: default)

    prompt = agent._system_prompt()

    assert "通用任务代理" in prompt
    assert "按需选择" in prompt
    assert "不得虚构" in prompt
    assert "创建和配置节点" not in prompt
    assert "执行工作流" not in prompt


def test_ar_assembly_delivery_skill_keeps_specialised_handoff_rules():
    content = AR_DELIVERY_SKILL.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(content.split("---", 2)[1])

    assert frontmatter["name"] == "ar-assembly-delivery"
    assert "完整 AR 辅助装配" in frontmatter["description"]
    for requirement in (
        "工艺规划",
        "图像资源",
        "Blender",
        "Unity AR",
        "不得虚构",
        "完整交接",
        "部分成功",
    ):
        assert requirement in content


def test_ar_assembly_delivery_metadata_is_utf8_and_ascii_safe():
    content = AR_DELIVERY_METADATA.read_text(encoding="utf-8")
    metadata = yaml.safe_load(content)

    assert content.isascii()
    assert metadata["interface"]["display_name"] == "AR Assembly Delivery"
