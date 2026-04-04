# -*- coding: utf-8 -*-
"""
节点图数据结构模块

定义工作流的核心数据结构：
- Node: 节点实例（工作流中的一个节点）
- Connection: 节点间的连接（端口到端口）
- NodeGraph: 完整的工作流图

核心功能：
- 节点和连接的管理
- 动态流程执行辅助（入口节点发现、循环体发现、分支追踪）

使用方式：
    from src.engine.node_graph import NodeGraph, Node, Connection, NodeState

    # 创建图
    graph = NodeGraph(name="我的工作流")

    # 添加节点
    node1 = graph.add_node("text.input", position=(100, 100))
    node2 = graph.add_node("text.upper", position=(300, 100))

    # 添加连接
    graph.add_connection(node1.id, "output", node2.id, "input")
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


class NodeState(Enum):
    """
    节点执行状态

    用于表示节点在工作流执行过程中的状态，同时影响UI颜色。

    Attributes:
        IDLE: 待执行（灰色）- 节点尚未执行
        RUNNING: 执行中（黄色）- 节点正在执行
        SUCCESS: 成功（绿色）- 节点执行成功
        ERROR: 失败（红色）- 节点执行失败

    Example:
        >>> node.state = NodeState.RUNNING
        >>> node.state == NodeState.SUCCESS
        False
    """

    IDLE = "idle"  # 待执行（灰色）
    RUNNING = "running"  # 执行中（黄色）
    SUCCESS = "success"  # 成功（绿色）
    ERROR = "error"  # 失败（红色）
    SKIPPED = "skipped"  # 已跳过（暗灰色）— 因分支未激活而被跳过

    @property
    def color(self) -> str:
        """获取状态对应的显示颜色（十六进制）"""
        colors = {
            NodeState.IDLE: "#616161",  # 灰色
            NodeState.RUNNING: "#FFC107",  # 黄色
            NodeState.SUCCESS: "#4CAF50",  # 绿色
            NodeState.ERROR: "#F44336",  # 红色
            NodeState.SKIPPED: "#9E9E9E",  # 暗灰色（跳过）
        }
        return colors.get(self, "#616161")


@dataclass
class Node:
    """
    节点实例

    表示工作流中的一个节点实例，包含：
    - 唯一标识和类型
    - UI位置
    - 执行状态和结果
    - 输入值（来自连接或控件）

    Note:
        Node 是节点实例，而 NodeDefinition 是节点类型定义。
        一个 NodeDefinition 可以创建多个 Node 实例。

    Attributes:
        id: 节点实例ID（全局唯一）
        node_type: 节点类型（对应 NodeDefinition.node_type）
        position: UI位置 (x, y)
        state: 执行状态
        inputs: 输入端口值（来自连接）
        outputs: 输出端口值（执行后填充）
        widget_values: 内联控件值（用户直接输入）
        error_message: 错误信息（执行失败时）

    Example:
        >>> node = Node(
        ...     node_type="text.join",
        ...     position=(100.0, 200.0)
        ... )
        >>> node.id  # 自动生成UUID
        'a1b2c3d4-...'
        >>> node.state
        <NodeState.IDLE: 'idle'>
    """

    # 基础信息
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: str = ""

    # UI位置
    position: Tuple[float, float] = (0.0, 0.0)

    # 执行状态
    state: NodeState = NodeState.IDLE

    # 端口值
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)

    # 内联控件值（用户直接输入，当没有连接时使用）
    widget_values: Dict[str, Any] = field(default_factory=dict)

    # 错误信息
    error_message: Optional[str] = None

    def reset_state(self) -> None:
        """
        重置节点状态

        清空执行结果和状态，准备重新执行
        """
        self.state = NodeState.IDLE
        self.outputs.clear()
        self.error_message = None


@dataclass
class Connection:
    """
    节点连接

    表示两个节点端口之间的连接关系。

    连接方向：源节点的输出端口 -> 目标节点的输入端口

    Attributes:
        id: 连接ID（全局唯一）
        source_node: 源节点ID
        source_port: 源端口名称（输出端口）
        target_node: 目标节点ID
        target_port: 目标端口名称（输入端口）

    Example:
        >>> conn = Connection(
        ...     source_node="node-001",
        ...     source_port="output",
        ...     target_node="node-002",
        ...     target_port="input"
        ... )
        >>> conn.source_node
        'node-001'
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node: str = ""
    source_port: str = ""
    target_node: str = ""
    target_port: str = ""
    is_back_edge: bool = False  # 回边标记（循环反馈连接）


@dataclass
class NodeGraph:
    """
    节点图

    表示完整的工作流图，包含：
    - 节点集合
    - 连接集合
    - 图操作方法
    - 动态流程执行辅助方法

    核心功能：
    - 添加/删除节点和连接
    - 查询连接关系
    - 入口节点发现
    - 循环体自动发现
    - 分支下游追踪

    Attributes:
        id: 图ID（全局唯一）
        name: 工作流名称
        nodes: 节点字典 {节点ID: Node}
        connections: 连接字典 {连接ID: Connection}

    Example:
        >>> graph = NodeGraph(name="我的工作流")
        >>> node1 = graph.add_node("text.input", position=(0, 0))
        >>> node2 = graph.add_node("text.upper", position=(200, 0))
        >>> graph.add_connection(node1.id, "output", node2.id, "input")
    """

    # 图信息
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled"

    # 节点和连接
    nodes: Dict[str, Node] = field(default_factory=dict)
    connections: Dict[str, Connection] = field(default_factory=dict)

    # ==================== 节点操作 ====================

    def add_node(
        self,
        node_type: str,
        position: Tuple[float, float] = (0.0, 0.0),
        node_id: Optional[str] = None,
    ) -> Node:
        """
        添加节点

        Args:
            node_type: 节点类型（对应 NodeDefinition.node_type）
            position: UI位置 (x, y)
            node_id: 指定节点ID（可选，用于反序列化）

        Returns:
            创建的节点实例

        Example:
            >>> node = graph.add_node("text.input", position=(100, 100))
            >>> node.node_type
            'text.input'
        """
        node = Node(
            id=node_id or str(uuid.uuid4()),
            node_type=node_type,
            position=position,
        )
        self.nodes[node.id] = node

        _logger.debug(f"添加节点: {node_type} [{node.id[:8]}...]")
        return node

    def remove_node(self, node_id: str) -> bool:
        """
        删除节点及其所有相关连接

        Args:
            node_id: 节点ID

        Returns:
            是否成功删除

        Example:
            >>> graph.remove_node(node.id)
            True
        """
        if node_id not in self.nodes:
            _logger.warning(f"节点不存在: {node_id[:8]}...")
            return False

        # 删除相关连接
        related_conns = self.get_connections_for_node(node_id)
        for conn in related_conns:
            self.remove_connection(conn.id)

        # 删除节点
        del self.nodes[node_id]

        _logger.debug(f"删除节点: {node_id[:8]}... (同时删除 {len(related_conns)} 个连接)")
        return True

    def get_node(self, node_id: str) -> Optional[Node]:
        """
        获取节点

        Args:
            node_id: 节点ID

        Returns:
            节点实例，如果不存在则返回 None
        """
        return self.nodes.get(node_id)

    # ==================== 连接操作 ====================

    def add_connection(
        self,
        source_node: str,
        source_port: str,
        target_node: str,
        target_port: str,
    ) -> Optional[Connection]:
        """
        添加连接

        Args:
            source_node: 源节点ID
            source_port: 源端口名称（输出端口）
            target_node: 目标节点ID
            target_port: 目标端口名称（输入端口）

        Returns:
            创建的连接，如果节点不存在则返回 None

        Note:
            - 不会检查端口类型兼容性（由 NodeEngine 负责）
            - 不会删除已有的目标端口连接（由调用方负责）

        Example:
            >>> conn = graph.add_connection(node1.id, "output", node2.id, "input")
            >>> conn.source_node == node1.id
            True
        """
        # 验证节点存在
        if source_node not in self.nodes or target_node not in self.nodes:
            _logger.warning(
                f"无法创建连接: 节点不存在 "
                f"(source={source_node[:8]}..., target={target_node[:8]}...)"
            )
            return None

        # 创建连接
        conn = Connection(
            source_node=source_node,
            source_port=source_port,
            target_node=target_node,
            target_port=target_port,
        )
        self.connections[conn.id] = conn

        _logger.debug(
            f"添加连接: {source_node[:8]}...:{source_port} -> {target_node[:8]}...:{target_port}"
        )
        return conn

    def remove_connection(self, connection_id: str) -> bool:
        """
        删除连接

        Args:
            connection_id: 连接ID

        Returns:
            是否成功删除
        """
        if connection_id not in self.connections:
            return False

        del self.connections[connection_id]
        _logger.debug(f"删除连接: {connection_id[:8]}...")
        return True

    # ==================== 连接查询 ====================

    def get_connections_for_node(self, node_id: str) -> List[Connection]:
        """
        获取与节点相关的所有连接（输入+输出）

        Args:
            node_id: 节点ID

        Returns:
            连接列表

        Example:
            >>> conns = graph.get_connections_for_node(node.id)
            >>> len(conns)
            2
        """
        return [
            conn
            for conn in self.connections.values()
            if conn.source_node == node_id or conn.target_node == node_id
        ]

    def get_incoming_connections(self, node_id: str) -> List[Connection]:
        """
        获取节点的输入连接

        Args:
            node_id: 节点ID

        Returns:
            输入连接列表（目标节点为该节点的连接）
        """
        return [conn for conn in self.connections.values() if conn.target_node == node_id]

    def get_outgoing_connections(self, node_id: str) -> List[Connection]:
        """
        获取节点的输出连接

        Args:
            node_id: 节点ID

        Returns:
            输出连接列表（源节点为该节点的连接）
        """
        return [conn for conn in self.connections.values() if conn.source_node == node_id]

    def get_connection_to_port(self, node_id: str, port_name: str) -> Optional[Connection]:
        """
        获取连接到指定端口的连接

        Args:
            node_id: 节点ID
            port_name: 输入端口名称

        Returns:
            连接实例，如果没有则返回 None
        """
        for conn in self.connections.values():
            if conn.target_node == node_id and conn.target_port == port_name:
                return conn
        return None

    # ==================== 动态流程执行辅助 ====================

    def get_entry_nodes(self) -> List[str]:
        """获取入口节点。

        优先查找 flow.start 节点，否则使用无入边（排除回边）的节点。

        Returns:
            入口节点 ID 列表
        """
        # 1. 优先查找 flow.start 节点
        start_nodes = [
            nid for nid, node in self.nodes.items()
            if node.node_type == "flow.start"
        ]
        if start_nodes:
            return start_nodes

        # 2. 回退：没有入边（排除回边）的节点
        entry_nodes = []
        for node_id in self.nodes:
            incoming = [
                c for c in self.get_incoming_connections(node_id)
                if not c.is_back_edge
            ]
            if not incoming:
                entry_nodes.append(node_id)
        return entry_nodes

    def detect_back_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """检测从 source 到 target 是否构成回边。

        通过 BFS 从 target 沿着出边（下游方向）搜索，如果能在已有连接中
        找到 source，说明已存在 target → ... → source 的路径，
        此时添加 source → target 将形成环路，因此是回边。

        注意：调用时连接已添加到图中，但由于 BFS 从 target 出发沿出边搜索，
        新连接（source → target）属于 source 的出边，不影响 BFS 结果。

        Args:
            source_node_id: 连接的源节点 ID（输出端口所在节点）
            target_node_id: 连接的目标节点 ID（输入端口所在节点）

        Returns:
            是否为回边
        """
        if source_node_id == target_node_id:
            return False

        visited = set()
        queue = [target_node_id]

        while queue:
            current = queue.pop(0)
            for conn in self.get_outgoing_connections(current):
                if conn.is_back_edge:
                    continue
                next_node = conn.target_node
                if next_node not in visited:
                    if next_node == source_node_id:
                        return True
                    visited.add(next_node)
                    queue.append(next_node)
        return False

    def get_outgoing_targets(self, node_id: str, port_name: str) -> List[str]:
        """获取指定输出端口连接的目标节点 ID 列表。

        Args:
            node_id: 源节点 ID
            port_name: 输出端口名称

        Returns:
            目标节点 ID 列表
        """
        return [
            conn.target_node
            for conn in self.get_outgoing_connections(node_id)
            if conn.source_port == port_name
        ]

    def trace_downstream(self, node_id: str, port_name: str) -> Set[str]:
        """从指定节点的指定输出端口出发，BFS 追踪所有下游可达节点。

        用于分支追踪：从 flow.if 的非活跃输出端口找出需要跳过的节点。

        Args:
            node_id: 起始节点 ID
            port_name: 起始输出端口名称

        Returns:
            所有下游可达节点的 ID 集合（不含起始节点自身）
        """
        visited: Set[str] = set()
        queue: List[str] = []

        # 找到从指定端口出发的所有直接下游节点
        for conn in self.get_outgoing_connections(node_id):
            if conn.source_port == port_name:
                target = conn.target_node
                if target not in visited:
                    visited.add(target)
                    queue.append(target)

        # BFS 追踪
        while queue:
            current = queue.pop(0)
            for conn in self.get_outgoing_connections(current):
                target = conn.target_node
                if target not in visited:
                    visited.add(target)
                    queue.append(target)

        return visited

    # ==================== 其他操作 ====================

    def clear(self) -> None:
        """
        清空图

        删除所有节点和连接
        """
        self.nodes.clear()
        self.connections.clear()
        _logger.info(f"图已清空: {self.name}")

    def clone(self) -> "NodeGraph":
        """
        克隆图

        创建图的深拷贝，包括所有节点和连接。
        新图中的节点和连接都有新的ID。

        Returns:
            克隆后的新图
        """
        new_graph = NodeGraph(name=f"{self.name} (副本)")

        # 节点ID映射（旧ID -> 新ID）
        id_mapping: Dict[str, str] = {}

        # 克隆节点
        for node in self.nodes.values():
            new_node = new_graph.add_node(
                node_type=node.node_type,
                position=node.position,
            )
            new_node.widget_values = node.widget_values.copy()
            id_mapping[node.id] = new_node.id

        # 克隆连接
        for conn in self.connections.values():
            new_graph.add_connection(
                source_node=id_mapping[conn.source_node],
                source_port=conn.source_port,
                target_node=id_mapping[conn.target_node],
                target_port=conn.target_port,
            )

        _logger.debug(f"克隆图: {self.name} -> {new_graph.name}")
        return new_graph

    def __repr__(self) -> str:
        """图的字符串表示"""
        return (
            f"<NodeGraph '{self.name}' nodes={len(self.nodes)} connections={len(self.connections)}>"
        )
