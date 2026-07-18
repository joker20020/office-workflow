"""Contracts for the SolidWorks branch main-agent prompt and delivery Skill."""

from pathlib import Path
from types import SimpleNamespace

import yaml

from src.agent.agent_integration import DEFAULT_SYSTEM_PROMPT, AgentIntegration

PROJECT_ROOT = Path(__file__).parents[1]
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"
AR_DELIVERY_SKILL = PROJECT_ROOT / "skills" / "ar-assembly-delivery" / "SKILL.md"
AR_DELIVERY_METADATA = AR_DELIVERY_SKILL.parent / "agents" / "openai.yaml"


def _load_system_prompt() -> str:
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))["system_prompt"]


def test_configured_main_prompt_is_general_and_solidworks_aware():
    prompt = _load_system_prompt()

    for requirement in ("通用任务代理", "按需选择", "SolidWorks", "不得虚构"):
        assert requirement in prompt
    for prohibited in (
        "tool_generate_process",
        "tool_generate_image",
        "tool_solidworks_model",
        "tool_unity_ar",
        "固定执行流程",
        "四个阶段",
        "Blender",
    ):
        assert prohibited not in prompt


def test_hard_coded_fallback_matches_the_configured_general_contract():
    agent = object.__new__(AgentIntegration)
    agent.config = SimpleNamespace(get=lambda _key, default: default)

    assert _load_system_prompt() == DEFAULT_SYSTEM_PROMPT
    assert agent._system_prompt() == DEFAULT_SYSTEM_PROMPT


def test_ar_assembly_delivery_skill_requires_solidworks_deliverables():
    content = AR_DELIVERY_SKILL.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(content.split("---", 2)[1])

    assert frontmatter["name"] == "ar-assembly-delivery"
    assert "SolidWorks" in frontmatter["description"]
    for requirement in (
        "工艺规划",
        "图像资源",
        "SolidWorks",
        "tool_solidworks_model",
        ".sldprt",
        ".step",
        ".stl",
        "preview",
        "Unity AR",
        "不得虚构",
        "完整交接",
        "部分成功",
    ):
        assert requirement in content
    assert "Blender" not in content


def test_ar_assembly_delivery_metadata_is_utf8_ascii_safe_and_solidworks_specific():
    content = AR_DELIVERY_METADATA.read_text(encoding="utf-8")
    metadata = yaml.safe_load(content)

    assert content.isascii()
    assert metadata["interface"]["display_name"] == "SolidWorks AR Assembly Delivery"
    assert "SolidWorks" in metadata["interface"]["short_description"]
