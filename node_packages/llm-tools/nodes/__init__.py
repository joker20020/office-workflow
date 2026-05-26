# -*- coding: utf-8 -*-
"""
大语言模型节点包

导出的节点定义:
- llm_chat: 通用LLM对话
- llm_markdown_structure: CAPP→结构化Markdown
"""

from .llm_nodes import (
    llm_chat,
    llm_markdown_structure,
)

__all__ = [
    "llm_chat",
    "llm_markdown_structure",
]
