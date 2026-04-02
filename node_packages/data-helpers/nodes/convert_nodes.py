# -*- coding: utf-8 -*-
"""
数据类型转换节点定义

提供各基本数据类型之间的相互转换节点。
"""

import json
from typing import Any

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 转字符串 ====================


def _to_string(value: Any) -> dict:
    return {"result": str(value)}


convert_to_string = NodeDefinition(
    node_type="convert.to_string",
    display_name="转字符串",
    description="将任意值转换为字符串表示",
    category="convert",
    icon="📝",
    inputs=[
        PortDefinition("value", PortType.ANY, "输入值"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "字符串结果", show_preview=True),
    ],
    execute=_to_string,
)


# ==================== 转整数 ====================


def _to_integer(value: Any) -> dict:
    try:
        if isinstance(value, bool):
            return {"result": int(value), "success": True}
        if isinstance(value, float):
            return {"result": int(value), "success": True}
        if isinstance(value, str):
            # 尝试先解析浮点再转整数（处理 "3.14" 这种情况）
            try:
                return {"result": int(float(value)), "success": True}
            except ValueError:
                return {"result": int(value), "success": True}
        return {"result": int(value), "success": True}
    except (ValueError, TypeError) as e:
        return {"result": None, "success": False, "error": str(e)}


convert_to_integer = NodeDefinition(
    node_type="convert.to_integer",
    display_name="转整数",
    description="将值转换为整数，支持字符串、浮点数等",
    category="convert",
    icon="🔢",
    inputs=[
        PortDefinition("value", PortType.ANY, "输入值"),
    ],
    outputs=[
        PortDefinition("result", PortType.INTEGER, "整数结果"),
        PortDefinition("success", PortType.BOOLEAN, "是否成功"),
    ],
    execute=_to_integer,
)


# ==================== 转浮点数 ====================


def _to_float(value: Any) -> dict:
    try:
        return {"result": float(value), "success": True}
    except (ValueError, TypeError) as e:
        return {"result": None, "success": False, "error": str(e)}


convert_to_float = NodeDefinition(
    node_type="convert.to_float",
    display_name="转浮点数",
    description="将值转换为浮点数，支持字符串、整数等",
    category="convert",
    icon="🔢",
    inputs=[
        PortDefinition("value", PortType.ANY, "输入值"),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "浮点数结果"),
        PortDefinition("success", PortType.BOOLEAN, "是否成功"),
    ],
    execute=_to_float,
)


# ==================== 转布尔值 ====================


def _to_boolean(value: Any) -> dict:
    """将值转换为布尔值"""
    if isinstance(value, bool):
        return {"result": value, "truth_type": "bool"}
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "yes", "1", "on"):
            return {"result": True, "truth_type": "string_true"}
        if lower in ("false", "no", "0", "off", ""):
            return {"result": False, "truth_type": "string_false"}
        # 非空非标准字符串 -> truthy
        return {"result": bool(value), "truth_type": "string_truthy"}
    if isinstance(value, (int, float)):
        return {"result": value != 0, "truth_type": "numeric"}
    if isinstance(value, (list, dict)):
        return {"result": len(value) > 0, "truth_type": "collection"}
    return {"result": bool(value), "truth_type": "other"}


convert_to_boolean = NodeDefinition(
    node_type="convert.to_boolean",
    display_name="转布尔值",
    description='将值转换为布尔值。支持 "true"/"false" 字符串、0/1 数值等',
    category="convert",
    icon="🔘",
    inputs=[
        PortDefinition("value", PortType.ANY, "输入值"),
    ],
    outputs=[
        PortDefinition("result", PortType.BOOLEAN, "布尔值结果"),
    ],
    execute=_to_boolean,
)


# ==================== 转列表 ====================


def _to_list(value: Any, separator: str = ",") -> dict:
    if isinstance(value, list):
        return {"result": value}
    if isinstance(value, dict):
        return {"result": list(value.keys())}
    if isinstance(value, str):
        return {"result": [item.strip() for item in value.split(separator)]}
    return {"result": [value]}


convert_to_list = NodeDefinition(
    node_type="convert.to_list",
    display_name="转列表",
    description="将值转换为列表。字符串按分隔符拆分，字典取键列表，其他值包装为单元素列表",
    category="convert",
    icon="📋",
    inputs=[
        PortDefinition("value", PortType.ANY, "输入值"),
        PortDefinition("separator", PortType.STRING, "分隔符（字符串拆分用）", default=",", required=False, widget_type="line_edit"),
    ],
    outputs=[
        PortDefinition("result", PortType.LIST, "列表结果", show_preview=True),
    ],
    execute=_to_list,
)


# ==================== 转字典 ====================


def _to_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return {"result": value, "success": True}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return {"result": parsed, "success": True}
            return {"result": None, "success": False, "error": "JSON 解析结果不是字典"}
        except json.JSONDecodeError as e:
            return {"result": None, "success": False, "error": f"JSON 解析失败: {e}"}
    if isinstance(value, list):
        # 列表转字典：[[key,val], ...] 或 [(key,val), ...]
        try:
            return {"result": dict(value), "success": True}
        except (TypeError, ValueError) as e:
            return {"result": None, "success": False, "error": str(e)}
    return {"result": None, "success": False, "error": f"无法将 {type(value).__name__} 转换为字典"}


convert_to_dict = NodeDefinition(
    node_type="convert.to_dict",
    display_name="转字典",
    description="将值转换为字典。支持 JSON 字符串解析和键值对列表转换",
    category="convert",
    icon="📖",
    inputs=[
        PortDefinition("value", PortType.ANY, "输入值"),
    ],
    outputs=[
        PortDefinition("result", PortType.DICT, "字典结果", show_preview=True),
        PortDefinition("success", PortType.BOOLEAN, "是否成功"),
    ],
    execute=_to_dict,
)


# ==================== 字符串转 JSON ====================


def _string_to_json(text: str) -> dict:
    try:
        parsed = json.loads(text)
        return {"result": parsed, "success": True, "is_dict": isinstance(parsed, dict)}
    except json.JSONDecodeError as e:
        return {"result": None, "success": False, "error": f"JSON 解析失败: {e}"}


convert_string_to_json = NodeDefinition(
    node_type="convert.string_to_json",
    display_name="字符串解析JSON",
    description="将 JSON 格式字符串解析为列表或字典",
    category="convert",
    icon="📄",
    inputs=[
        PortDefinition("text", PortType.STRING, "JSON 字符串", widget_type="text_edit"),
    ],
    outputs=[
        PortDefinition("result", PortType.ANY, "解析结果", show_preview=True),
        PortDefinition("success", PortType.BOOLEAN, "是否成功"),
    ],
    execute=_string_to_json,
)
