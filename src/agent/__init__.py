# -*- coding: utf-8 -*-
"""
Agent模块

集成AgentScope框架，为节点编辑器提供AI助手功能。

核心组件:
- ApiKeyManager: API密钥加密存储和管理
- NodeFormatter: 节点信息格式化为Agent可读文本
- WorkflowTools: Agent操作节点编辑器的工具集
- AgentIntegration: AgentScope框架集成层
- ChatHistory: 对话历史管理
- McpServerManager: MCP服务配置管理
- SkillManager: Skill技能包管理

使用方式:
    from src.agent import AgentIntegration, ApiKeyManager

    # 初始化
    api_manager = ApiKeyManager()
    agent = AgentIntegration(api_manager, node_engine)

    # 对话
    response = agent.chat("帮我创建一个文本处理工作流")
"""

from src.agent.api_key_manager import ApiKeyManager
from src.agent.node_formatter import NodeFormatter
from src.agent.workflow_tools import WorkflowTools
from src.agent.agent_integration import AgentIntegration
from src.agent.chat_history import ChatHistory
from src.agent.mcp_server_manager import McpServerManager
from src.agent.skill_manager import SkillManager
from src.agent.tool_registry import AgentToolRegistry

__all__ = [
    "ApiKeyManager",
    "NodeFormatter",
    "WorkflowTools",
    "AgentIntegration",
    "ChatHistory",
    "McpServerManager",
    "SkillManager",
    "AgentToolRegistry",
]
