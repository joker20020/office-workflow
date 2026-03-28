# -*- coding: utf-8 -*-
"""测试节点信息格式化器功能"""

import pytest

from src.agent.node_formatter import NodeFormatter
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


@pytest.fixture
def sample_node_def():
    return NodeDefinition(
        node_type="text.join",
        display_name="文本拼接",
        description="将两个文本拼接在一起",
        category="text",
        icon="🔗",
        inputs=[
            PortDefinition("text1", PortType.STRING, "第一个文本"),
            PortDefinition("text2", PortType.STRING, "第二个文本"),
            PortDefinition("separator", PortType.STRING, "分隔符", required=False, default=" "),
        ],
        outputs=[
            PortDefinition("result", PortType.STRING, "拼接结果"),
        ],
    )


class TestNodeFormatter:
    """测试NodeFormatter的基本功能"""

    def test_format_for_agent(self, sample_node_def: NodeDefinition):
        result = NodeFormatter.format_for_agent(sample_node_def)

        assert "text.join" in result
        assert "文本拼接" in result
        assert "输入端口:" in result
        assert "text1" in result

    def test_format_all_for_agent(self, sample_node_def: NodeDefinition):
        node_defs = [sample_node_def]
        result = NodeFormatter.format_all_for_agent(node_defs)

        assert "共有 1 个可用节点" in result
        assert "text.join" in result

    def test_get_system_prompt(self, sample_node_def: NodeDefinition):
        node_defs = [sample_node_def]
        result = NodeFormatter.get_system_prompt(node_defs)

        assert "你是一个工作流助手" in result
        assert "可用节点类型" in result
        assert "text.join" in result
