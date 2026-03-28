# -*- coding: utf-8 -*-
"""端到端测试 - 验证Agent对话功能"""

import json

import pytest
from unittest.mock import Mock, patch

from src.agent.agent_integration import AgentIntegration
from src.agent.api_key_manager import ApiKeyManager
from src.agent.chat_history import ChatHistory
from src.agent.workflow_tools import WorkflowTools
from src.engine.node_engine import NodeEngine
from src.engine.node_graph import NodeGraph
from src.storage.database import Database
from src.storage.repositories import ChatHistoryRepository

try:
    from agentscope.tool import ToolResponse

    AGENTSCOPE_AVAILABLE = True
except ImportError:
    AGENTSCOPE_AVAILABLE = False
    ToolResponse = None


def _extract_result(response):
    if AGENTSCOPE_AVAILABLE and hasattr(response, "content"):
        for block in response.content:
            if isinstance(block, dict) and "text" in block:
                return json.loads(block["text"])
            elif hasattr(block, "text") and isinstance(block.text, str):
                return json.loads(block.text)
    return response


@pytest.mark.skipif(not AGENTSCOPE_AVAILABLE, reason="AgentScope not installed")
class TestEndToEnd:
    """端到端测试 - 验证完整的对话流程"""

    def test_workflow_tools_basic(self):
        graph = NodeGraph(name="测试工作流")
        engine = NodeEngine()
        tools = WorkflowTools(graph, engine)

        result = _extract_result(tools.get_tool("list_nodes")())
        assert result["success"] is True
        assert result["count"] == 0

        result = _extract_result(tools.get_tool("create_node")("text.join", (100, 100)))
        assert result["success"] is True
        assert "node_id" in result

    def test_chat_history_basic(self):
        history = ChatHistory(max_messages=10)

        history.add_message("user", "你好")
        history.add_message("assistant", "你好!有什么可以帮助你的?")

        messages = history.get_messages()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    @patch("src.agent.agent_integration.AGENTSCOPE_AVAILABLE", False)
    def test_agent_integration_without_agentscope(self):
        api_manager = Mock(spec=ApiKeyManager)
        node_engine = Mock(spec=NodeEngine)

        agent = AgentIntegration(api_manager, node_engine)

        assert not agent.is_initialized

        result = agent.initialize("openai")
        assert not result
