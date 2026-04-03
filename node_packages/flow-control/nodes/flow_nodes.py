# -*- coding: utf-8 -*-
"""
流程控制节点定义

提供工作流级别的控制流节点：
- flow.if: 条件分支（then/else 双输出）
- flow.merge: 分支合并
- flow.for_each: 列表迭代循环
- flow.loop_end: 循环结束标记
"""

from typing import Any, Dict, List, Optional

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 1. 条件分支 ====================


def _flow_if(
    condition: bool,
    then_value: Any = None,
    else_value: Any = None,
) -> Dict[str, Any]:
    """条件分支：根据 condition 选择输出路径。

    引擎层会追踪非活跃分支的下游节点并标记为 SKIPPED。
    """
    if condition:
        return {
            "then_out": then_value,
            "else_out": None,
            "result": condition,
        }
    else:
        return {
            "then_out": None,
            "else_out": else_value,
            "result": condition,
        }


flow_if = NodeDefinition(
    node_type="flow.if",
    display_name="条件分支",
    description="根据布尔条件选择执行路径：True 走 then 分支，False 走 else 分支。"
    " 非活跃分支的下游节点将被跳过。",
    category="flow",
    icon="🔀",
    flow_type="branch",
    inputs=[
        PortDefinition("condition", PortType.BOOLEAN, "条件值", default=False),
        PortDefinition("then_value", PortType.ANY, "条件为 True 时的透传数据", required=False),
        PortDefinition("else_value", PortType.ANY, "条件为 False 时的透传数据", required=False),
    ],
    outputs=[
        PortDefinition("then_out", PortType.ANY, "condition=True 时输出 then_value，否则 None", role="branch"),
        PortDefinition("else_out", PortType.ANY, "condition=False 时输出 else_value，否则 None", role="branch"),
        PortDefinition("result", PortType.BOOLEAN, "透传 condition 值"),
    ],
    execute=_flow_if,
)


# ==================== 2. 分支合并 ====================


def _flow_merge(then_in: Any = None, else_in: Any = None) -> Dict[str, Any]:
    """分支合并：接收两个分支的数据，输出非空值。"""
    if then_in is not None:
        return {"result": then_in, "branch": "then"}
    return {"result": else_in, "branch": "else"}


flow_merge = NodeDefinition(
    node_type="flow.merge",
    display_name="分支合并",
    description="合并 then/else 两个分支的结果，输出非空值。"
    " 通常用于两条分支最终汇入同一个下游节点。",
    category="flow",
    icon="🔀",
    inputs=[
        PortDefinition("then_in", PortType.ANY, "来自 then 分支的数据", required=False),
        PortDefinition("else_in", PortType.ANY, "来自 else 分支的数据", required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.ANY, "非空的那个输入值"),
        PortDefinition("branch", PortType.STRING, "活跃分支名 (then/else)"),
    ],
    execute=_flow_merge,
)


# ==================== 3. 列表循环 ====================


def _flow_for_each(
    items: list,
    initial: Any = None,
) -> Dict[str, Any]:
    """列表迭代循环。

    execute 函数只负责初始校验和首次迭代的输出设置。
    实际的循环迭代由 WorkflowRunner 引擎层控制。
    当引擎不支持循环迭代时，此函数作为单次执行的降级方案。
    """
    if items is None:
        items = []

    count = len(items)
    first_item = items[0] if items else None

    return {
        "item": first_item,
        "index": 0 if items else -1,
        "accumulator": initial,
        "results": items,
        "count": count,
        "last": items[-1] if items else None,
    }


flow_for_each = NodeDefinition(
    node_type="flow.for_each",
    display_name="列表循环",
    description="遍历列表，对每个元素执行下游节点（循环体）。"
    " 下游节点从 item 获取当前元素、从 index 获取索引。"
    " 配合 flow.loop_end 使用，loop_end 的 output 可连回 accumulator 形成累积。",
    category="flow",
    icon="🔄",
    flow_type="loop_start",
    inputs=[
        PortDefinition("items", PortType.LIST, "要迭代的列表"),
        PortDefinition("initial", PortType.ANY, "初始累积值", required=False),
    ],
    outputs=[
        PortDefinition("item", PortType.ANY, "当前迭代元素"),
        PortDefinition("index", PortType.INTEGER, "当前迭代索引"),
        PortDefinition("accumulator", PortType.ANY, "当前累积值"),
        PortDefinition("results", PortType.LIST, "所有迭代结果列表"),
        PortDefinition("count", PortType.INTEGER, "迭代总次数"),
        PortDefinition("last", PortType.ANY, "最后一次迭代结果"),
    ],
    execute=_flow_for_each,
)


# ==================== 4. 循环结束标记 ====================


def _flow_loop_end(result: Any = None) -> Dict[str, Any]:
    """循环结束标记：收集每次迭代的结果并透传。

    output 端口可连接回 flow.for_each 的 accumulator 端口形成反馈环。
    """
    return {"output": result}


flow_loop_end = NodeDefinition(
    node_type="flow.loop_end",
    display_name="循环结束",
    description="标记循环体结束。每次迭代的结果从此节点的 output 输出。"
    " 可将 output 连回 for_each 的 accumulator 形成累积反馈。",
    category="flow",
    icon="⏹",
    flow_type="loop_end",
    inputs=[
        PortDefinition("result", PortType.ANY, "每次迭代的计算结果", required=False),
    ],
    outputs=[
        PortDefinition("output", PortType.ANY, "透传 result", role="feedback"),
    ],
    execute=_flow_loop_end,
)
