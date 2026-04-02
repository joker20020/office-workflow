# -*- coding: utf-8 -*-
"""
文本处理节点定义

提供常用的文本处理功能
"""

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 文本拼接节点 ====================


def _join_text(text1: str, text2: str, separator: str = " ") -> dict:
    """拼接两个文本"""
    result = f"{text1}{separator}{text2}"
    return {"result": result}


text_join = NodeDefinition(
    node_type="text.join",
    display_name="文本拼接",
    description="将两个文本按指定分隔符拼接",
    category="text",
    icon="🔗",
    inputs=[
        PortDefinition("text1", PortType.STRING, "第一个文本"),
        PortDefinition("text2", PortType.STRING, "第二个文本"),
        PortDefinition("separator", PortType.STRING, "分隔符", default=" ", required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "拼接结果"),
    ],
    execute=_join_text,
)


# ==================== 大写转换节点 ====================


def _to_uppercase(text: str) -> dict:
    """转换为大写"""
    return {"result": text.upper()}


text_uppercase = NodeDefinition(
    node_type="text.uppercase",
    display_name="转大写",
    description="将文本转换为大写",
    category="text",
    icon="🔠",
    inputs=[
        PortDefinition("text", PortType.STRING, "输入文本"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "大写文本"),
    ],
    execute=_to_uppercase,
)


# ==================== 小写转换节点 ====================


def _to_lowercase(text: str) -> dict:
    """转换为小写"""
    return {"result": text.lower()}


text_lowercase = NodeDefinition(
    node_type="text.lowercase",
    display_name="转小写",
    description="将文本转换为小写",
    category="text",
    icon="🔡",
    inputs=[
        PortDefinition("text", PortType.STRING, "输入文本"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "小写文本"),
    ],
    execute=_to_lowercase,
)


# ==================== 字符串替换节点 ====================


def _replace_text(text: str, old: str, new: str) -> dict:
    """替换文本"""
    return {"result": text.replace(old, new)}


text_replace = NodeDefinition(
    node_type="text.replace",
    display_name="文本替换",
    description="将文本中的指定内容替换为新内容",
    category="text",
    icon="🔄",
    inputs=[
        PortDefinition("text", PortType.STRING, "原始文本"),
        PortDefinition("old", PortType.STRING, "要替换的内容"),
        PortDefinition("new", PortType.STRING, "替换为"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "替换结果"),
    ],
    execute=_replace_text,
)
