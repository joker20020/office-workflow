# -*- coding: utf-8 -*-
"""数学工具节点包"""

from .math_nodes import (
    # 基础四则运算
    math_add,
    math_subtract,
    math_multiply,
    math_divide,
    math_modulo,
    math_power,
    math_integer_divide,
    # 一元运算
    math_absolute,
    math_negate,
    math_sign,
    # 比较运算
    math_equal,
    math_not_equal,
    math_greater,
    math_less,
    math_greater_equal,
    math_less_equal,
    # 聚合运算
    math_min,
    math_max,
    math_clamp,
    math_sum,
    math_average,
    # 舍入运算
    math_round,
    math_ceil,
    math_floor,
    # 数学函数
    math_sqrt,
    math_log,
    math_sin,
    math_cos,
    math_tan,
    math_deg_to_rad,
    math_rad_to_deg,
    # 随机数
    math_random,
    math_random_int,
    # 条件运算
    math_condition,
)

__all__ = [
    "math_add", "math_subtract", "math_multiply", "math_divide",
    "math_modulo", "math_power", "math_integer_divide",
    "math_absolute", "math_negate", "math_sign",
    "math_equal", "math_not_equal", "math_greater", "math_less",
    "math_greater_equal", "math_less_equal",
    "math_min", "math_max", "math_clamp", "math_sum", "math_average",
    "math_round", "math_ceil", "math_floor",
    "math_sqrt", "math_log",
    "math_sin", "math_cos", "math_tan",
    "math_deg_to_rad", "math_rad_to_deg",
    "math_random", "math_random_int",
    "math_condition",
]
