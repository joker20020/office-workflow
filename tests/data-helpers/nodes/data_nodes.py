# -*- coding: utf-8 -*-
"""数据处理节点定义"""

from typing import Any, Dict, List
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 列表长度节点 ====================


def _list_length(items: list) -> dict:
    return {"length": len(items)}


data_list_length = NodeDefinition(
    node_type="data.list_length",
    display_name="列表长度",
    description="获取列表的元素数量",
    category="data",
    icon="📏",
    inputs=[
        PortDefinition("items", PortType.LIST, "列表"),
    ],
    outputs=[
        PortDefinition("length", PortType.INTEGER, "长度"),
    ],
    execute=_list_length,
)


# ==================== 列表合并节点 ====================


def _list_merge(list1: list, list2: list) -> dict:
    return {"result": list1 + list2}


data_list_merge = NodeDefinition(
    node_type="data.list_merge",
    display_name="列表合并",
    description="合并两个列表",
    category="data",
    icon="🔗",
    inputs=[
        PortDefinition("list1", PortType.LIST, "第一个列表"),
        PortDefinition("list2", PortType.LIST, "第二个列表"),
    ],
    outputs=[
        PortDefinition("result", PortType.LIST, "合并后的列表"),
    ],
    execute=_list_merge,
)


# ==================== 字典取值节点 ====================


def _dict_get(data: dict, key: str, default: Any = None) -> dict:
    return {"value": data.get(key, default)}


data_dict_get = NodeDefinition(
    node_type="data.dict_get",
    display_name="字典取值",
    description="从字典中获取指定键的值",
    category="data",
    icon="🔑",
    inputs=[
        PortDefinition("data", PortType.DICT, "字典"),
        PortDefinition("key", PortType.STRING, "键名"),
        PortDefinition("default", PortType.ANY, "默认值", default=None, required=False),
    ],
    outputs=[
        PortDefinition("value", PortType.ANY, "值"),
    ],
    execute=_dict_get,
)


# ==================== 转字符串节点 ====================


def _to_string(value: Any) -> dict:
    return {"result": str(value)}


data_to_string = NodeDefinition(
    node_type="data.to_string",
    display_name="转字符串",
    description="将任意值转换为字符串",
    category="data",
    icon="📝",
    inputs=[
        PortDefinition("value", PortType.ANY, "输入值"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "字符串"),
    ],
    execute=_to_string,
)
