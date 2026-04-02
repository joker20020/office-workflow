# -*- coding: utf-8 -*-
"""
数据输入节点定义

提供各内置数据类型的常量输入节点，用于在工作流中提供固定值。
"""

from typing import Any, Dict, List

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 字符串输入 ====================


def _input_string(value: str) -> dict:
    return {"output": value}


input_string = NodeDefinition(
    node_type="input.string",
    display_name="字符串输入",
    description="提供一个字符串常量值",
    category="input",
    icon="📝",
    inputs=[
        PortDefinition("value", PortType.STRING, "字符串值", widget_type="text_edit"),
    ],
    outputs=[
        PortDefinition("output", PortType.STRING, "输出字符串", show_preview=True),
    ],
    execute=_input_string,
)


# ==================== 整数输入 ====================


def _input_integer(value: int) -> dict:
    return {"output": value}


input_integer = NodeDefinition(
    node_type="input.integer",
    display_name="整数输入",
    description="提供一个整数常量值",
    category="input",
    icon="🔢",
    inputs=[
        PortDefinition("value", PortType.INTEGER, "整数值", default=0, widget_type="spin_box"),
    ],
    outputs=[
        PortDefinition("output", PortType.INTEGER, "输出整数"),
    ],
    execute=_input_integer,
)


# ==================== 浮点数输入 ====================


def _input_float(value: float) -> dict:
    return {"output": value}


input_float = NodeDefinition(
    node_type="input.float",
    display_name="浮点数输入",
    description="提供一个浮点数常量值",
    category="input",
    icon="🔢",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "浮点数值", default=0.0, widget_type="double_spin_box"),
    ],
    outputs=[
        PortDefinition("output", PortType.FLOAT, "输出浮点数"),
    ],
    execute=_input_float,
)


# ==================== 布尔值输入 ====================


def _input_boolean(value: bool) -> dict:
    return {"output": value}


input_boolean = NodeDefinition(
    node_type="input.boolean",
    display_name="布尔值输入",
    description="提供一个布尔值（True/False）",
    category="input",
    icon="🔘",
    inputs=[
        PortDefinition("value", PortType.BOOLEAN, "布尔值", default=False, widget_type="check_box"),
    ],
    outputs=[
        PortDefinition("output", PortType.BOOLEAN, "输出布尔值"),
    ],
    execute=_input_boolean,
)


# ==================== 列表输入 ====================


def _input_list(items: list) -> dict:
    return {"output": items}


input_list = NodeDefinition(
    node_type="input.list",
    display_name="列表输入",
    description="提供一个列表常量值（JSON 格式）",
    category="input",
    icon="📋",
    inputs=[
        PortDefinition("items", PortType.LIST, "列表值", default=[]),
    ],
    outputs=[
        PortDefinition("output", PortType.LIST, "输出列表", show_preview=True),
    ],
    execute=_input_list,
)


# ==================== 字典输入 ====================


def _input_dict(data: dict) -> dict:
    return {"output": data}


input_dict = NodeDefinition(
    node_type="input.dict",
    display_name="字典输入",
    description="提供一个字典常量值（JSON 格式）",
    category="input",
    icon="📖",
    inputs=[
        PortDefinition("data", PortType.DICT, "字典值", default={}),
    ],
    outputs=[
        PortDefinition("output", PortType.DICT, "输出字典", show_preview=True),
    ],
    execute=_input_dict,
)


# ==================== 文件路径输入 ====================


def _input_file(file_path: str) -> dict:
    return {"output": file_path}


input_file = NodeDefinition(
    node_type="input.file",
    display_name="文件输入",
    description="选择一个文件路径作为输入",
    category="input",
    icon="📁",
    inputs=[
        PortDefinition("file_path", PortType.FILE, "文件路径", widget_type="file_picker"),
    ],
    outputs=[
        PortDefinition("output", PortType.FILE, "文件路径", show_preview=True),
    ],
    execute=_input_file,
)
