# -*- coding: utf-8 -*-
"""
数学运算节点定义

提供完整的数学运算节点集：
- 基础运算：加、减、乘、除、取模、幂运算
- 一元运算：绝对值、取反、符号
- 比较运算：等于、不等于、大于、小于、大于等于、小于等于
- 聚合运算：最大值、最小值、求和、范围
- 舍入运算：四舍五入、向上取整、向下取整
- 三角函数：正弦、余弦、正切
- 其他：随机数、开方、对数
"""

import math
import random
from typing import Any, List

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# =====================================================================
# 基础四则运算
# =====================================================================


def _add(a: float, b: float) -> dict:
    return {"result": a + b}


math_add = NodeDefinition(
    node_type="math.add",
    display_name="加法",
    description="计算两个数的和 (a + b)",
    category="math",
    icon="➕",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个数", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个数", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "和"),
    ],
    execute=_add,
)


def _subtract(a: float, b: float) -> dict:
    return {"result": a - b}


math_subtract = NodeDefinition(
    node_type="math.subtract",
    display_name="减法",
    description="计算两个数的差 (a - b)",
    category="math",
    icon="➖",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "被减数", default=0),
        PortDefinition("b", PortType.FLOAT, "减数", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "差"),
    ],
    execute=_subtract,
)


def _multiply(a: float, b: float) -> dict:
    return {"result": a * b}


math_multiply = NodeDefinition(
    node_type="math.multiply",
    display_name="乘法",
    description="计算两个数的积 (a × b)",
    category="math",
    icon="✖️",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个数", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个数", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "积"),
    ],
    execute=_multiply,
)


def _divide(a: float, b: float) -> dict:
    if b == 0:
        raise ValueError("除数不能为零")
    return {"result": a / b}


math_divide = NodeDefinition(
    node_type="math.divide",
    display_name="除法",
    description="计算两个数的商 (a ÷ b)",
    category="math",
    icon="➗",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "被除数", default=0),
        PortDefinition("b", PortType.FLOAT, "除数", default=1),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "商"),
    ],
    execute=_divide,
)


def _modulo(a: float, b: float) -> dict:
    if b == 0:
        raise ValueError("取模除数不能为零")
    return {"result": a % b}


math_modulo = NodeDefinition(
    node_type="math.modulo",
    display_name="取模",
    description="计算取模运算 (a % b)",
    category="math",
    icon="%",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "被除数", default=0),
        PortDefinition("b", PortType.FLOAT, "除数", default=1),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "余数"),
    ],
    execute=_modulo,
)


def _power(base: float, exponent: float) -> dict:
    return {"result": base ** exponent}


math_power = NodeDefinition(
    node_type="math.power",
    display_name="幂运算",
    description="计算幂运算 (base ^ exponent)",
    category="math",
    icon="^",
    inputs=[
        PortDefinition("base", PortType.FLOAT, "底数", default=0),
        PortDefinition("exponent", PortType.FLOAT, "指数", default=2),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "结果"),
    ],
    execute=_power,
)


def _integer_divide(a: int, b: int) -> dict:
    if b == 0:
        raise ValueError("除数不能为零")
    return {"result": a // b}


math_integer_divide = NodeDefinition(
    node_type="math.integer_divide",
    display_name="整数除法",
    description="计算整数除法，返回商的整数部分 (a // b)",
    category="math",
    icon="⌠除",
    inputs=[
        PortDefinition("a", PortType.INTEGER, "被除数", default=0),
        PortDefinition("b", PortType.INTEGER, "除数", default=1),
    ],
    outputs=[
        PortDefinition("result", PortType.INTEGER, "整数商"),
    ],
    execute=_integer_divide,
)


# =====================================================================
# 一元运算
# =====================================================================


def _absolute(value: float) -> dict:
    return {"result": abs(value)}


math_absolute = NodeDefinition(
    node_type="math.absolute",
    display_name="绝对值",
    description="计算一个数的绝对值",
    category="math",
    icon="||",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "绝对值"),
    ],
    execute=_absolute,
)


def _negate(value: float) -> dict:
    return {"result": -value}


math_negate = NodeDefinition(
    node_type="math.negate",
    display_name="取反",
    description="将数值取反（正变负、负变正）",
    category="math",
    icon="±",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "取反结果"),
    ],
    execute=_negate,
)


def _sign(value: float) -> dict:
    if value > 0:
        return {"result": 1}
    elif value < 0:
        return {"result": -1}
    return {"result": 0}


math_sign = NodeDefinition(
    node_type="math.sign",
    display_name="符号函数",
    description="返回数值的符号：正数返回1，负数返回-1，零返回0",
    category="math",
    icon="±",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.INTEGER, "符号值 (-1/0/1)"),
    ],
    execute=_sign,
)


# =====================================================================
# 比较运算
# =====================================================================


def _compare_equal(a: float, b: float) -> dict:
    return {"result": a == b}


math_equal = NodeDefinition(
    node_type="math.equal",
    display_name="等于",
    description="判断两个值是否相等 (a == b)",
    category="math",
    icon="=",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个值", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.BOOLEAN, "是否相等"),
    ],
    execute=_compare_equal,
)


def _compare_not_equal(a: float, b: float) -> dict:
    return {"result": a != b}


math_not_equal = NodeDefinition(
    node_type="math.not_equal",
    display_name="不等于",
    description="判断两个值是否不相等 (a != b)",
    category="math",
    icon="≠",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个值", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.BOOLEAN, "是否不相等"),
    ],
    execute=_compare_not_equal,
)


def _compare_greater(a: float, b: float) -> dict:
    return {"result": a > b}


math_greater = NodeDefinition(
    node_type="math.greater",
    display_name="大于",
    description="判断第一个值是否大于第二个值 (a > b)",
    category="math",
    icon=">",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个值", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.BOOLEAN, "是否大于"),
    ],
    execute=_compare_greater,
)


def _compare_less(a: float, b: float) -> dict:
    return {"result": a < b}


math_less = NodeDefinition(
    node_type="math.less",
    display_name="小于",
    description="判断第一个值是否小于第二个值 (a < b)",
    category="math",
    icon="<",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个值", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.BOOLEAN, "是否小于"),
    ],
    execute=_compare_less,
)


def _compare_greater_equal(a: float, b: float) -> dict:
    return {"result": a >= b}


math_greater_equal = NodeDefinition(
    node_type="math.greater_equal",
    display_name="大于等于",
    description="判断第一个值是否大于等于第二个值 (a >= b)",
    category="math",
    icon="≥",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个值", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.BOOLEAN, "是否大于等于"),
    ],
    execute=_compare_greater_equal,
)


def _compare_less_equal(a: float, b: float) -> dict:
    return {"result": a <= b}


math_less_equal = NodeDefinition(
    node_type="math.less_equal",
    display_name="小于等于",
    description="判断第一个值是否小于等于第二个值 (a <= b)",
    category="math",
    icon="≤",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个值", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.BOOLEAN, "是否小于等于"),
    ],
    execute=_compare_less_equal,
)


# =====================================================================
# 聚合运算
# =====================================================================


def _minimum(a: float, b: float) -> dict:
    return {"result": min(a, b)}


math_min = NodeDefinition(
    node_type="math.min",
    display_name="最小值",
    description="返回两个数中的较小值",
    category="math",
    icon="⬇️",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个数", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个数", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "较小值"),
    ],
    execute=_minimum,
)


def _maximum(a: float, b: float) -> dict:
    return {"result": max(a, b)}


math_max = NodeDefinition(
    node_type="math.max",
    display_name="最大值",
    description="返回两个数中的较大值",
    category="math",
    icon="⬆️",
    inputs=[
        PortDefinition("a", PortType.FLOAT, "第一个数", default=0),
        PortDefinition("b", PortType.FLOAT, "第二个数", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "较大值"),
    ],
    execute=_maximum,
)


def _clamp(value: float, min_val: float, max_val: float) -> dict:
    return {"result": max(min_val, min(value, max_val))}


math_clamp = NodeDefinition(
    node_type="math.clamp",
    display_name="范围限制",
    description="将数值限制在指定范围内 (min <= result <= max)",
    category="math",
    icon="📐",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
        PortDefinition("min_val", PortType.FLOAT, "最小值", default=0),
        PortDefinition("max_val", PortType.FLOAT, "最大值", default=100),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "限制后的值"),
    ],
    execute=_clamp,
)


def _sum_list(numbers: list) -> dict:
    return {"result": sum(numbers), "count": len(numbers)}


math_sum = NodeDefinition(
    node_type="math.sum",
    display_name="求和",
    description="计算数值列表的总和",
    category="math",
    icon="∑",
    inputs=[
        PortDefinition("numbers", PortType.LIST, "数值列表"),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "总和"),
        PortDefinition("count", PortType.INTEGER, "元素数量"),
    ],
    execute=_sum_list,
)


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


# =====================================================================
# 舍入运算
# =====================================================================


def _round_value(value: float, decimals: int = 0) -> dict:
    return {"result": round(value, decimals)}


math_round = NodeDefinition(
    node_type="math.round",
    display_name="四舍五入",
    description="将浮点数四舍五入到指定小数位数",
    category="math",
    icon="🔄",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
        PortDefinition("decimals", PortType.INTEGER, "小数位数", default=0, required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "舍入结果"),
    ],
    execute=_round_value,
)


def _ceil(value: float) -> dict:
    return {"result": math.ceil(value)}


math_ceil = NodeDefinition(
    node_type="math.ceil",
    display_name="向上取整",
    description="将浮点数向上取整为不小于它的最小整数",
    category="math",
    icon="⬆",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.INTEGER, "向上取整结果"),
    ],
    execute=_ceil,
)


def _floor(value: float) -> dict:
    return {"result": math.floor(value)}


math_floor = NodeDefinition(
    node_type="math.floor",
    display_name="向下取整",
    description="将浮点数向下取整为不大于它的最大整数",
    category="math",
    icon="⬇",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.INTEGER, "向下取整结果"),
    ],
    execute=_floor,
)


# =====================================================================
# 数学函数
# =====================================================================


def _sqrt(value: float) -> dict:
    if value < 0:
        raise ValueError("不能对负数开平方根")
    return {"result": math.sqrt(value)}


math_sqrt = NodeDefinition(
    node_type="math.sqrt",
    display_name="平方根",
    description="计算平方根 (√value)",
    category="math",
    icon="√",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "输入值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "平方根"),
    ],
    execute=_sqrt,
)


def _logarithm(value: float, base: float = 2.718281828459045) -> dict:
    if value <= 0:
        raise ValueError("对数运算的值必须大于零")
    if base <= 0 or base == 1:
        raise ValueError("对数的底数必须大于零且不等于1")
    return {"result": math.log(value, base)}


math_log = NodeDefinition(
    node_type="math.log",
    display_name="对数",
    description="计算对数 log_base(value)，默认自然对数",
    category="math",
    icon="log",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "真数", default=1),
        PortDefinition("base", PortType.FLOAT, "底数（默认e）", default=2.718281828459045, required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "对数值"),
    ],
    execute=_logarithm,
)


def _sin(value: float) -> dict:
    return {"result": math.sin(value)}


math_sin = NodeDefinition(
    node_type="math.sin",
    display_name="正弦",
    description="计算正弦值（弧度制）",
    category="math",
    icon="sin",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "弧度值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "正弦值"),
    ],
    execute=_sin,
)


def _cos(value: float) -> dict:
    return {"result": math.cos(value)}


math_cos = NodeDefinition(
    node_type="math.cos",
    display_name="余弦",
    description="计算余弦值（弧度制）",
    category="math",
    icon="cos",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "弧度值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "余弦值"),
    ],
    execute=_cos,
)


def _tan(value: float) -> dict:
    return {"result": math.tan(value)}


math_tan = NodeDefinition(
    node_type="math.tan",
    display_name="正切",
    description="计算正切值（弧度制）",
    category="math",
    icon="tan",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "弧度值", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "正切值"),
    ],
    execute=_tan,
)


def _degrees_to_radians(degrees: float) -> dict:
    return {"result": math.radians(degrees)}


math_deg_to_rad = NodeDefinition(
    node_type="math.deg_to_rad",
    display_name="角度转弧度",
    description="将角度值转换为弧度值",
    category="math",
    icon="rad",
    inputs=[
        PortDefinition("degrees", PortType.FLOAT, "角度", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "弧度"),
    ],
    execute=_degrees_to_radians,
)


def _radians_to_degrees(radians: float) -> dict:
    return {"result": math.degrees(radians)}


math_rad_to_deg = NodeDefinition(
    node_type="math.rad_to_deg",
    display_name="弧度转角度",
    description="将弧度值转换为角度值",
    category="math",
    icon="deg",
    inputs=[
        PortDefinition("radians", PortType.FLOAT, "弧度", default=0),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "角度"),
    ],
    execute=_radians_to_degrees,
)


# =====================================================================
# 随机数
# =====================================================================


def _random_number(min_val: float = 0, max_val: float = 100) -> dict:
    return {"result": random.uniform(min_val, max_val)}


math_random = NodeDefinition(
    node_type="math.random",
    display_name="随机数",
    description="生成指定范围内的随机浮点数",
    category="math",
    icon="🎲",
    inputs=[
        PortDefinition("min_val", PortType.FLOAT, "最小值", default=0),
        PortDefinition("max_val", PortType.FLOAT, "最大值", default=100),
    ],
    outputs=[
        PortDefinition("result", PortType.FLOAT, "随机数"),
    ],
    execute=_random_number,
)


def _random_integer(min_val: int = 0, max_val: int = 100) -> dict:
    return {"result": random.randint(min_val, max_val)}


math_random_int = NodeDefinition(
    node_type="math.random_int",
    display_name="随机整数",
    description="生成指定范围内的随机整数",
    category="math",
    icon="🎲",
    inputs=[
        PortDefinition("min_val", PortType.INTEGER, "最小值", default=0),
        PortDefinition("max_val", PortType.INTEGER, "最大值", default=100),
    ],
    outputs=[
        PortDefinition("result", PortType.INTEGER, "随机整数"),
    ],
    execute=_random_integer,
)


# =====================================================================
# 条件运算
# =====================================================================


def _condition(condition: bool, true_value: Any = None, false_value: Any = None) -> dict:
    return {"result": true_value if condition else false_value}


math_condition = NodeDefinition(
    node_type="math.condition",
    display_name="条件选择",
    description="根据布尔条件选择输出值：条件为真输出 true_value，否则输出 false_value",
    category="math",
    icon="🔀",
    inputs=[
        PortDefinition("condition", PortType.BOOLEAN, "条件", default=False),
        PortDefinition("true_value", PortType.ANY, "真值", required=False),
        PortDefinition("false_value", PortType.ANY, "假值", required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.ANY, "选择结果"),
    ],
    execute=_condition,
)
