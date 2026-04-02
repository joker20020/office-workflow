# -*- coding: utf-8 -*-
"""数学计算节点定义"""

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 加法节点 ====================


def _add(a: float, b: float) -> dict:
    return {"result": a + b}


math_add = NodeDefinition(
    node_type="math.add",
    display_name="加法",
    description="计算两个数的和",
    category="math",
    icon="➕",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个数"),
        PortDefinition("b", PortType.FLOAT, "第二个数"),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "和"),
    ],
    execute=_add,
)


# ==================== 减法节点 ====================


def _subtract(a: float, b: float) -> dict:
    return {"result": a - b}


math_subtract = NodeDefinition(
    node_type="math.subtract",
    display_name="减法",
    description="计算两个数的差",
    category="math",
    icon="➖",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "被减数"),
        PortDefinition("b", PortType.FLOAT, "减数"),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "差"),
    ],
    execute=_subtract,
)


# ==================== 乘法节点 ====================


def _multiply(a: float, b: float) -> dict:
    return {"result": a * b}


math_multiply = NodeDefinition(
    node_type="math.multiply",
    display_name="乘法",
    description="计算两个数的积",
    category="math",
    icon="✖️",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个数"),
        PortDefinition("b", PortType.FLOAT, "第二个数"),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "积"),
    ],
    execute=_multiply,
)


# ==================== 除法节点 ====================


def _divide(a: float, b: float) -> dict:
    if b == 0:
        return {"result": None, "error": "除数不能为零"}
    return {"result": a / b}


math_divide = NodeDefinition(
    node_type="math.divide",
    display_name="除法",
    description="计算两个数的商",
    category="math",
    icon="➗",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "被除数"),
        PortDefinition("b", PortType.FLOAT, "除数"),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "商"),
    ],
    execute=_divide,
)


# ==================== 平均值节点 ====================


def _average(numbers: list) -> dict:
    if not numbers:
        return {"result": 0}
    return {"result": sum(numbers) / len(numbers)}


math_average = NodeDefinition(
    node_type="math.average",
    display_name="平均值",
    description="计算数值列表的平均值",
    category="math",
    icon="📊",
    inputs=[
        PortDefinition("numbers", PortType.LIST, "数值列表"),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "平均值"),
    ],
    execute=_average,
)
