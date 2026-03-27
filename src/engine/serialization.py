# -*- coding: utf-8 -*-
"""
工作流序列化模块

提供工作流图的JSON序列化和反序列化功能：
- 将NodeGraph转换为JSON字符串
- 从JSON字符串重建NodeGraph

序列化格式：
{
    "id": "graph-uuid",
    "name": "工作流名称",
    "nodes": [
        {
            "id": "node-uuid",
            "node_type": "text.join",
            "position": [100.0, 200.0],
            "widget_values": {"separator": " "}
        }
    ],
    "connections": [
        {
            "id": "conn-uuid",
            "source_node": "node1-id",
            "source_port": "output",
            "target_node": "node2-id",
            "target_port": "input"
        }
    ]
}

使用方式：
    from src.engine.serialization import serialize_graph, deserialize_graph

    # 序列化
    json_str = serialize_graph(graph)

    # 反序列化
    graph = deserialize_graph(json_str)
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from src.engine.node_graph import Connection, Node, NodeGraph, NodeState
from src.utils.logger import get_logger

_logger = get_logger(__name__)


def serialize_graph(graph: NodeGraph) -> str:
    """
    序列化工作流图为JSON字符串

    Args:
        graph: 要序列化的工作流图

    Returns:
        JSON字符串

    Note:
        - 不序列化执行状态（state, inputs, outputs）
        - 只序列化结构和widget_values

    Example:
        >>> json_str = serialize_graph(graph)
        >>> len(json_str) > 0
        True
    """
    data = {
        "id": graph.id,
        "name": graph.name,
        "nodes": [],
        "connections": [],
    }

    # 序列化节点
    for node in graph.nodes.values():
        node_data = {
            "id": node.id,
            "node_type": node.node_type,
            "position": list(node.position),
            "widget_values": node.widget_values,
        }
        data["nodes"].append(node_data)

    # 序列化连接
    for conn in graph.connections.values():
        conn_data = {
            "id": conn.id,
            "source_node": conn.source_node,
            "source_port": conn.source_port,
            "target_node": conn.target_node,
            "target_port": conn.target_port,
        }
        data["connections"].append(conn_data)

    _logger.debug(
        f"序列化图: {graph.name}, {len(data['nodes'])} 节点, {len(data['connections'])} 连接"
    )
    return json.dumps(data, ensure_ascii=False, indent=2)


def deserialize_graph(json_str: str) -> NodeGraph:
    """
    从JSON字符串反序列化工作流图

    Args:
        json_str: JSON字符串

    Returns:
        重建的工作流图

    Raises:
        ValueError: JSON格式无效

    Example:
        >>> graph = deserialize_graph(json_str)
        >>> graph.name
        '我的工作流'
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"无效的JSON格式: {e}") from e

    # 创建图
    graph = NodeGraph(
        id=data.get("id"),
        name=data.get("name", "Untitled"),
    )

    # 反序列化节点
    for node_data in data.get("nodes", []):
        node = graph.add_node(
            node_type=node_data["node_type"],
            position=tuple(node_data.get("position", [0.0, 0.0])),
            node_id=node_data["id"],
        )
        # 恢复widget_values
        node.widget_values = node_data.get("widget_values", {})

    # 反序列化连接
    for conn_data in data.get("connections", []):
        graph.add_connection(
            source_node=conn_data["source_node"],
            source_port=conn_data["source_port"],
            target_node=conn_data["target_node"],
            target_port=conn_data["target_port"],
        )

    _logger.debug(
        f"反序列化图: {graph.name}, {len(graph.nodes)} 节点, {len(graph.connections)} 连接"
    )
    return graph


def serialize_node(node: Node) -> Dict[str, Any]:
    """
    序列化单个节点

    Args:
        node: 要序列化的节点

    Returns:
        节点数据字典
    """
    return {
        "id": node.id,
        "node_type": node.node_type,
        "position": list(node.position),
        "widget_values": node.widget_values,
        "state": node.state.value,
    }


def serialize_connection(conn: Connection) -> Dict[str, Any]:
    """
    序列化单个连接

    Args:
        conn: 要序列化的连接

    Returns:
        连接数据字典
    """
    return {
        "id": conn.id,
        "source_node": conn.source_node,
        "source_port": conn.source_port,
        "target_node": conn.target_node,
        "target_port": conn.target_port,
    }
