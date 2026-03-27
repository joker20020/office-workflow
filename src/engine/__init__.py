# -*- coding: utf-8 -*-
"""
节点引擎模块

提供节点编辑器的核心功能：
- 节点定义（PortDefinition, NodeDefinition）
- 图数据结构（Node, Connection, NodeGraph）
- 执行引擎（NodeEngine）
- 序列化支持

使用方式：
    from src.engine import NodeDefinition, PortDefinition, PortType
    from src.engine import NodeGraph, Node, Connection, NodeState
    from src.engine import NodeEngine, NodeRegistry
"""

from src.engine.definitions import (
    NodeDefinition,
    PortDefinition,
    PortType,
)
from src.engine.node_graph import (
    Connection,
    CyclicDependencyError,
    Node,
    NodeGraph,
    NodeState,
)
from src.engine.node_engine import (
    ExecutionResult,
    NodeEngine,
    NodeRegistry,
)
from src.engine.serialization import (
    deserialize_graph,
    serialize_graph,
)

__all__ = [
    # 定义
    "PortType",
    "PortDefinition",
    "NodeDefinition",
    # 图数据结构
    "Node",
    "Connection",
    "NodeGraph",
    "NodeState",
    "CyclicDependencyError",
    # 执行引擎
    "NodeRegistry",
    "NodeEngine",
    "ExecutionResult",
    # 序列化
    "serialize_graph",
    "deserialize_graph",
]
