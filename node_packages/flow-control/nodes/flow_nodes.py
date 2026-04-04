# -*- coding: utf-8 -*-
"""
流程控制节点定义

提供工作流级别的控制流节点：
- flow.condition: 条件判断（True/False 双分支输出）
- flow.merge: 分支合并
"""

from typing import Any, Dict, List, Optional

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 1. 条件判断 ====================


def _flow_condition(
    condition: bool,
    true_value: Any = None,
    false_value: Any = None,
) -> Dict[str, Any]:
    """条件判断：根据 condition 选择输出路径。

    引擎层通过检测输出端口的非 None 值来判断活跃分支。
    因此活跃分支必须输出非 None 值（即使没有连接数据也用布尔标记）。
    """
    if condition:
        return {
            "true_out": true_value if true_value is not None else True,
            "false_out": None,
            "result": condition,
        }
    else:
        return {
            "true_out": None,
            "false_out": false_value if false_value is not None else False,
            "result": condition,
        }


flow_condition = NodeDefinition(
    node_type="flow.condition",
    display_name="条件判断",
    description="根据布尔条件选择执行路径：True 走 true_out 分支，False 走 false_out 分支。"
    " 非活跃分支的下游节点将被跳过。",
    category="flow",
    icon="🔀",
    inputs=[
        PortDefinition("condition", PortType.BOOLEAN, "条件值", default=False),
        PortDefinition("true_value", PortType.ANY, "条件为 True 时的透传数据", required=False),
        PortDefinition("false_value", PortType.ANY, "条件为 False 时的透传数据", required=False),
    ],
    outputs=[
        PortDefinition("true_out", PortType.ANY, "condition=True 时输出 true_value，否则 None", role="branch_true"),
        PortDefinition("false_out", PortType.ANY, "condition=False 时输出 false_value，否则 None", role="branch_false"),
        PortDefinition("result", PortType.BOOLEAN, "透传 condition 值"),
    ],
    execute=_flow_condition,
)


# ==================== 2. 分支合并 ====================


def _flow_merge(true_in: Any = None, false_in: Any = None) -> Dict[str, Any]:
    """分支合并：接收两个分支的数据，输出非空值。"""
    if true_in is not None:
        return {"result": true_in, "branch": "true"}
    return {"result": false_in, "branch": "false"}


flow_merge = NodeDefinition(
    node_type="flow.merge",
    display_name="分支合并",
    description="合并 true/false 两个分支的结果，输出非空值。"
    " 通常用于两条分支最终汇入同一个下游节点。",
    category="flow",
    icon="🔀",
    inputs=[
        PortDefinition("true_in", PortType.ANY, "来自 true 分支的数据", required=False),
        PortDefinition("false_in", PortType.ANY, "来自 false 分支的数据", required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.ANY, "非空的那个输入值"),
        PortDefinition("branch", PortType.STRING, "活跃分支名 (true/false)"),
    ],
    execute=_flow_merge,
)
