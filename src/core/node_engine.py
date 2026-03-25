# -*- coding: utf-8 -*-
"""
自研节点流引擎模块
====================

本模块实现了完整的节点流执行引擎，包括:
- NodeState: 节点状态枚举
- Port: 端口数据类
- Connection: 连接线数据类
- Node: 节点数据类
- NodeGraph: 节点图数据类
- NodeEngine: 节点流执行引擎

设计特点:
- 支持异步执行
- 拓扑排序自动确定执行顺序
- 支持序列化/反序列化
- 通过回调通知状态变化

参考:
- SpatialNode设计模式
- LiteGraph执行流程
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Callable
from uuid import uuid4
from enum import Enum
import asyncio
import json

from .plugin_base import PortType, ToolDefinition


class NodeState(Enum):
    """
    节点状态枚举

    定义节点在执行过程中的所有可能状态。
    用于UI显示和执行控制。

    状态流转:
        IDLE -> RUNNING -> SUCCESS/ERROR/SKIPPED

    属性:
        IDLE: 空闲状态，等待执行
        RUNNING: 正在执行中
        SUCCESS: 执行成功
        ERROR: 执行失败
        SKIPPED: 被跳过（当前驱失败时）
    """

    IDLE = "idle"  # 空闲
    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 成功
    ERROR = "error"  # 失败
    SKIPPED = "skipped"  # 跳过


@dataclass
class Port:
    """
    端口数据类

    表示节点的一个输入或输出端口。
    端口是节点间数据流动的接口。

    属性:
        id: 端口唯一标识
        name: 端口名称（在节点内唯一）
        type: 数据类型
        node_id: 所属节点ID
        is_input: 是否为输入端口
        value: 当前值（运行时）
    """

    id: str  # 端口唯一标识
    name: str  # 端口名称
    type: PortType  # 数据类型
    node_id: str  # 所属节点ID
    is_input: bool  # 是否为输入端口
    value: Any = None  # 当前值


@dataclass
class Connection:
    """
    连接线数据类

    表示两个节点之间的数据连接。
    从源节点的输出端口连接到目标节点的输入端口。

    属性:
        id: 连接唯一标识
        source_node: 源节点ID
        source_port: 源端口名称
        target_node: 目标节点ID
        target_port: 目标端口名称

    数据流向:
        source_node.source_port -> target_node.target_port
    """

    id: str  # 连接唯一标识
    source_node: str  # 源节点ID
    source_port: str  # 源端口名称
    target_node: str  # 目标节点ID
    target_port: str  # 目标端口名称


@dataclass
class Node:
    """
    节点数据类

    表示节点图中的一个节点实例。
    节点是执行的基本单元，封装了一个工具的执行。

    属性:
        id: 节点唯一标识
        type: 节点类型（工具名称）
        name: 显示名称
        position: UI位置 (x, y)
        inputs: 输入端口字典 {name: Port}
        outputs: 输出端口字典 {name: Port}
        state: 当前状态
        error: 错误信息（如果有）
        result: 执行结果

    方法:
        set_input(): 设置输入端口值
        get_output(): 获取输出端口值
    """

    id: str  # 节点唯一标识
    type: str  # 节点类型（工具名称）
    name: str  # 显示名称
    position: tuple  # UI位置 (x, y)
    inputs: Dict[str, Port] = field(default_factory=dict)  # 输入端口
    outputs: Dict[str, Port] = field(default_factory=dict)  # 输出端口
    state: NodeState = NodeState.IDLE  # 当前状态
    error: Optional[str] = None  # 错误信息
    result: Any = None  # 执行结果

    def set_input(self, port_name: str, value: Any) -> None:
        """
        设置输入端口值

        将值设置到指定的输入端口。

        参数:
            port_name: 端口名称
            value: 要设置的值
        """
        if port_name in self.inputs:
            self.inputs[port_name].value = value

    def get_output(self, port_name: str) -> Any:
        """
        获取输出端口值

        获取指定输出端口的当前值。

        参数:
            port_name: 端口名称

        返回:
            Any: 端口值，如果不存在返回None
        """
        if port_name in self.outputs:
            return self.outputs[port_name].value
        return None


@dataclass
class NodeGraph:
    """
    节点图数据类

    表示完整的节点流程图。
    包含所有节点和连接，以及图操作方法。

    属性:
        id: 图唯一标识
        name: 图名称
        nodes: 节点字典 {id: Node}
        connections: 连接字典 {id: Connection}

    方法:
        add_node(): 添加节点
        remove_node(): 移除节点（同时移除相关连接）
        add_connection(): 添加连接
        remove_connection(): 移除连接
        get_predecessors(): 获取前驱节点列表
        get_successors(): 获取后继节点列表
        topological_sort(): 拓扑排序，确定执行顺序
        to_dict(): 序列化为字典
        from_dict(): 从字典反序列化
    """

    id: str  # 图唯一标识
    name: str  # 图名称
    nodes: Dict[str, Node] = field(default_factory=dict)  # 节点字典
    connections: Dict[str, Connection] = field(default_factory=dict)  # 连接字典

    def add_node(self, node: Node) -> None:
        """
        添加节点

        将节点添加到图中。

        参数:
            node: 要添加的节点
        """
        self.nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        """
        移除节点

        移除指定节点及其所有相关连接。

        参数:
            node_id: 要移除的节点ID
        """
        if node_id in self.nodes:
            # 删除节点
            del self.nodes[node_id]
            # 移除相关的所有连接
            self.connections = {
                k: v
                for k, v in self.connections.items()
                if v.source_node != node_id and v.target_node != node_id
            }

    def add_connection(self, conn: Connection) -> None:
        """
        添加连接

        将连接添加到图中。

        参数:
            conn: 要添加的连接
        """
        self.connections[conn.id] = conn

    def remove_connection(self, conn_id: str) -> None:
        """
        移除连接

        移除指定的连接。

        参数:
            conn_id: 要移除的连接ID
        """
        if conn_id in self.connections:
            del self.connections[conn_id]

    def get_predecessors(self, node_id: str) -> List[str]:
        """
        获取前驱节点列表

        返回所有连接到指定节点输入的源节点ID列表。

        参数:
            node_id: 目标节点ID

        返回:
            List[str]: 前驱节点ID列表
        """
        predecessors = []
        for conn in self.connections.values():
            if conn.target_node == node_id:
                predecessors.append(conn.source_node)
        return predecessors

    def get_successors(self, node_id: str) -> List[str]:
        """
        获取后继节点列表

        返回所有从指定节点输出连接的目标节点ID列表。

        参数:
            node_id: 源节点ID

        返回:
            List[str]: 后继节点ID列表
        """
        successors = []
        for conn in self.connections.values():
            if conn.source_node == node_id:
                successors.append(conn.target_node)
        return successors

    def topological_sort(self) -> List[str]:
        """
        拓扑排序

        对节点进行拓扑排序，返回执行顺序。
        执行顺序保证每个节点在其所有前驱节点执行完毕后才执行。

        返回:
            List[str]: 节点ID列表（按执行顺序排列）

        异常:
            ValueError: 如果图中存在环

        算法:
            使用Kahn算法进行拓扑排序:
            1. 计算每个节点的入度（前驱数量）
            2. 将入度为0的节点加入队列
            3. 依次取出节点，减少其后继节点的入度
            4. 如果最终节点数不等于总节点数，说明存在环
        """
        # 初始化入度字典
        in_degree = {nid: 0 for nid in self.nodes}

        # 计算每个节点的入度
        for conn in self.connections.values():
            if conn.target_node in in_degree:
                in_degree[conn.target_node] += 1

        # 找出所有入度为0的节点
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        # 拓扑排序
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            # 减少后继节点的入度
            for successor in self.get_successors(node_id):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        # 检查是否存在环
        if len(result) != len(self.nodes):
            raise ValueError("Graph contains cycles")

        return result

    def to_dict(self) -> dict:
        """
        序列化为字典

        将节点图序列化为可JSON化的字典。
        用于保存到文件。

        返回:
            dict: 序列化后的字典
        """
        return {
            "id": self.id,
            "name": self.name,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "name": n.name,
                    "position": n.position,
                    "inputs": {k: {"value": v.value} for k, v in n.inputs.items()},
                }
                for n in self.nodes.values()
            ],
            "connections": [
                {
                    "id": c.id,
                    "source_node": c.source_node,
                    "source_port": c.source_port,
                    "target_node": c.target_node,
                    "target_port": c.target_port,
                }
                for c in self.connections.values()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodeGraph":
        """
        从字典反序列化

        从字典数据创建节点图实例。
        用于从文件加载。

        参数:
            data: 序列化的字典数据

        返回:
            NodeGraph: 反序列化后的节点图
        """
        # 创建图实例
        graph = cls(id=data["id"], name=data["name"])

        # 添加节点
        for node_data in data["nodes"]:
            node = Node(
                id=node_data["id"],
                type=node_data["type"],
                name=node_data["name"],
                position=tuple(node_data["position"]),
            )
            # 恢复输入值
            for port_name, port_data in node_data.get("inputs", {}).items():
                if port_name in node.inputs:
                    node.inputs[port_name].value = port_data.get("value")
            graph.add_node(node)

        # 添加连接
        for conn_data in data["connections"]:
            graph.add_connection(
                Connection(
                    id=conn_data["id"],
                    source_node=conn_data["source_node"],
                    source_port=conn_data["source_port"],
                    target_node=conn_data["target_node"],
                    target_port=conn_data["target_port"],
                )
            )

        return graph


class NodeEngine:
    """
    节点流执行引擎

    核心执行引擎，负责节点的创建、管理和执行。

    功能:
        - register_node_type(): 注册节点类型
        - create_node(): 创建节点实例
        - create_graph(): 创建新图
        - execute_node(): 执行单个节点
        - execute_graph(): 执行整个图
        - save_graph()/load_graph(): 序列化

    属性:
        node_types: 已注册的节点类型 {name: ToolDefinition}
        graphs: 已创建的图 {id: NodeGraph}
        _execution_callbacks: 状态变化回调列表

    执行流程:
        1. topological_sort()确定执行顺序
        2. 依次执行每个节点:
           - 从前驱节点传递数据
           - 执行节点逻辑
           - 设置输出值
           - 通知状态变化
    """

    def __init__(self):
        """初始化节点引擎"""
        # 已注册的节点类型
        self.node_types: Dict[str, ToolDefinition] = {}
        # 已创建的图
        self.graphs: Dict[str, NodeGraph] = {}
        # 状态变化回调列表
        self._execution_callbacks: List[Callable] = []

    def register_node_type(self, tool: ToolDefinition) -> None:
        """
        注册节点类型

        将工具定义注册为可用的节点类型。
        注册后可以在create_node()中使用。

        参数:
            tool: 工具定义
        """
        self.node_types[tool.name] = tool

    def create_node(self, node_type: str, position: tuple = (0, 0)) -> Optional[Node]:
        """
        创建节点实例

        根据节点类型创建节点实例。
        自动创建输入输出端口。

        参数:
            node_type: 节点类型（工具名称）
            position: UI位置，默认(0, 0)

        返回:
            Optional[Node]: 创建的节点，如果类型不存在返回None
        """
        if node_type not in self.node_types:
            return None

        tool = self.node_types[node_type]
        node_id = str(uuid4())

        # 创建输入端口
        inputs = {}
        for inp in tool.inputs:
            inputs[inp.name] = Port(
                id=f"{node_id}_in_{inp.name}",
                name=inp.name,
                type=inp.type,
                node_id=node_id,
                is_input=True,
                value=inp.default,
            )

        # 创建输出端口
        outputs = {}
        for out in tool.outputs:
            outputs[out.name] = Port(
                id=f"{node_id}_out_{out.name}",
                name=out.name,
                type=out.type,
                node_id=node_id,
                is_input=False,
            )

        return Node(
            id=node_id,
            type=node_type,
            name=tool.display_name,
            position=position,
            inputs=inputs,
            outputs=outputs,
        )

    def create_graph(self, name: str = "Untitled") -> NodeGraph:
        """
        创建新图

        创建一个空的节点图。

        参数:
            name: 图名称，默认"Untitled"

        返回:
            NodeGraph: 创建的图
        """
        graph = NodeGraph(id=str(uuid4()), name=name)
        self.graphs[graph.id] = graph
        return graph

    def on_node_state_change(self, callback: Callable) -> None:
        """
        注册状态变化回调

        当节点状态变化时，回调将被调用。

        参数:
            callback: 回调函数，签名为(node: Node) -> None
        """
        self._execution_callbacks.append(callback)

    async def _notify_state_change(self, node: Node) -> None:
        """
        通知状态变化

        调用所有注册的回调。

        参数:
            node: 状态变化的节点
        """
        for callback in self._execution_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(node)
            else:
                callback(node)

    async def execute_node(self, node: Node, graph: NodeGraph) -> bool:
        """
        执行单个节点

        执行指定节点的业务逻辑。

        参数:
            node: 要执行的节点
            graph: 节点所属的图

        返回:
            bool: 执行是否成功
        """
        # 检查节点类型
        if node.type not in self.node_types:
            node.state = NodeState.ERROR
            node.error = f"Unknown node type: {node.type}"
            await self._notify_state_change(node)
            return False

        tool = self.node_types[node.type]

        try:
            # 设置运行状态
            node.state = NodeState.RUNNING
            await self._notify_state_change(node)

            # 收集输入参数
            kwargs = {}
            for port_name, port in node.inputs.items():
                kwargs[port_name] = port.value

            # 执行工具
            result = tool.execute(**kwargs)

            # 设置输出
            if isinstance(result, dict):
                for key, value in result.items():
                    if key in node.outputs:
                        node.outputs[key].value = value
            else:
                # 单输出情况
                if "result" in node.outputs:
                    node.outputs["result"].value = result

            node.result = result
            node.state = NodeState.SUCCESS
            await self._notify_state_change(node)
            return True

        except Exception as e:
            node.state = NodeState.ERROR
            node.error = str(e)
            await self._notify_state_change(node)
            return False

    async def execute_graph(self, graph: NodeGraph) -> bool:
        """
        执行整个图

        按拓扑顺序执行图中的所有节点。
        数据会按连接自动传递。

        参数:
            graph: 要执行的图

        返回:
            bool: 执行是否成功（所有节点都成功）

        执行流程:
            1. 拓扑排序确定执行顺序
            2. 依次执行每个节点:
               - 从前驱节点传递数据
               - 执行节点
               - 如果失败，停止执行
        """
        try:
            # 获取执行顺序
            order = graph.topological_sort()
        except ValueError as e:
            # 存在环
            return False

        # 按顺序执行节点
        for node_id in order:
            node = graph.nodes[node_id]

            # 传递数据： 从前驱节点的输出到当前节点的输入
            for conn in graph.connections.values():
                if conn.target_node == node_id:
                    source_node = graph.nodes[conn.source_node]
                    if conn.source_port in source_node.outputs:
                        value = source_node.outputs[conn.source_port].value
                        if conn.target_port in node.inputs:
                            node.inputs[conn.target_port].value = value

            # 执行节点
            success = await self.execute_node(node, graph)
            if not success:
                return False

        return True

    def save_graph(self, graph: NodeGraph, filepath: str) -> None:
        """
        保存图到文件

        将节点图序列化并保存到JSON文件。

        参数:
            graph: 要保存的图
            filepath: 目标文件路径
        """
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(graph.to_dict(), f, ensure_ascii=False, indent=2)

    def load_graph(self, filepath: str) -> NodeGraph:
        """
        从文件加载图

        从JSON文件反序列化节点图。

        参数:
            filepath: 源文件路径

        返回:
            NodeGraph: 加载的图
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        graph = NodeGraph.from_dict(data)
        self.graphs[graph.id] = graph
        return graph

    def get_available_nodes(self) -> List[dict]:
        """
        获取可用节点类型列表

        返回所有已注册节点类型的信息。
        用于UI显示节点列表。

        返回:
            List[dict]: 节点类型信息列表，每个包含:
                - type: 节点类型
                - name: 显示名称
                - category: 分类
                - icon: 图标
                - inputs: 输入端口列表
                - outputs: 输出端口列表
        """
        return [
            {
                "type": tool.name,
                "name": tool.display_name,
                "category": tool.category,
                "icon": tool.icon,
                "inputs": [
                    {"name": i.name, "type": i.type.value, "required": i.required}
                    for i in tool.inputs
                ],
                "outputs": [
                    {"name": o.name, "type": o.type.value} for o in tool.outputs
                ],
            }
            for tool in self.node_types.values()
        ]
