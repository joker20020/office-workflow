# -*- coding: utf-8 -*-
"""工作流操作工具集 - Agent通过这些工具操作节点编辑器"""

import json
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from src.agent.node_formatter import NodeFormatter
from src.engine.node_engine import NodeEngine
from src.engine.node_graph import NodeGraph
from src.utils.logger import get_logger

try:
    from agentscope.tool import ToolResponse

    AGENTSCOPE_AVAILABLE = True
except ImportError:
    AGENTSCOPE_AVAILABLE = False
    ToolResponse = None

_logger = get_logger(__name__)


def _make_response(content: Any, success: bool = True, metadata: Optional[Dict] = None) -> Any:
    if AGENTSCOPE_AVAILABLE and ToolResponse is not None:
        content_str = (
            json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
        )
        return ToolResponse(
            content=[{"type": "text", "text": content_str}],
            metadata={"success": success, **(metadata or {})},
        )
    return content


class WorkflowTools(QObject):
    """
    工作流操作工具集

    提供Agent操作节点编辑器的工具函数：
    - create_node: 创建节点
    - delete_node: 删除节点
    - connect_nodes: 连接节点
    - disconnect_nodes: 断开连接
    - set_node_value: 设置节点值
    - execute_workflow: 执行工作流
    - list_nodes: 列出所有节点
    - list_connections: 列出所有连接
    - get_node_types: 获取可用节点类型
    - get_node_info: 获取节点详细信息
    - search_nodes: 搜索节点
    - clear_workflow: 清空工作流

    信号:
        - graph_changed: 图发生变化时发出（节点添加/删除/连接等）
        - node_value_changed: 节点值变化时发出（用于UI同步控件值）
    """

    graph_changed = Signal()
    node_value_changed = Signal(str, str, object)  # node_id, port_name, value

    def __init__(self, node_graph: NodeGraph, node_engine: NodeEngine, parent=None):
        super().__init__(parent)
        self._graph = node_graph
        self._engine = node_engine
        self._tools: Dict[str, callable] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        self._tools = {
            "create_node": self._tool_create_node,
            "delete_node": self._tool_delete_node,
            "connect_nodes": self._tool_connect_nodes,
            "disconnect_nodes": self._tool_disconnect_nodes,
            "set_node_value": self._tool_set_node_value,
            "execute_workflow": self._tool_execute_workflow,
            "list_nodes": self._tool_list_nodes,
            "list_connections": self._tool_list_connections,
            "get_node_types": self._tool_get_node_types,
            "get_node_info": self._tool_get_node_info,
            "search_nodes": self._tool_search_nodes,
            "clear_workflow": self._tool_clear_workflow,
        }

    def get_all_tools(self) -> List[callable]:
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[callable]:
        return self._tools.get(name)

    def _tool_create_node(
        self, node_type: str, position: Optional[Tuple[float, float]] = None
    ) -> Any:
        try:
            if position is None:
                position = (100 + len(self._graph.nodes) * 50, 100)

            node = self._graph.add_node(node_type, position=position)

            _logger.info(
                f"[Thread: {threading.current_thread().name}] 创建节点成功: {node_type}, id={node.id[:8]}..., "
                f"graph节点数: {len(self._graph.nodes)}"
            )
            self.graph_changed.emit()
            _logger.info(f"[Thread: {threading.current_thread().name}] graph_changed信号已发出")

            return _make_response(
                {
                    "success": True,
                    "node_id": node.id,
                    "node_type": node.node_type,
                    "position": node.position,
                    "message": f"已创建节点: {node_type}",
                }
            )
        except Exception as e:
            _logger.error(f"创建节点失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_delete_node(self, node_id: str) -> Any:
        try:
            success = self._graph.remove_node(node_id)
            if success:
                self.graph_changed.emit()
            return _make_response(
                {
                    "success": success,
                    "message": f"已删除节点: {node_id}" if success else f"节点不存在: {node_id}",
                }
            )
        except Exception as e:
            _logger.error(f"删除节点失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_connect_nodes(
        self,
        source_node_id: str,
        source_port: str,
        target_node_id: str,
        target_port: str,
    ) -> Any:
        try:
            connection = self._graph.add_connection(
                source_node_id, source_port, target_node_id, target_port
            )
            self.graph_changed.emit()
            return _make_response(
                {
                    "success": True,
                    "connection_id": connection.id,
                    "message": f"已连接: {source_node_id}:{source_port} -> {target_node_id}:{target_port}",
                }
            )
        except Exception as e:
            _logger.error(f"连接节点失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_disconnect_nodes(self, node_id: str, port_name: str) -> Any:
        try:
            connections = self._graph.get_connections_for_node(node_id)
            removed_count = 0

            for conn in connections:
                if (conn.source_node == node_id and conn.source_port == port_name) or (
                    conn.target_node == node_id and conn.target_port == port_name
                ):
                    self._graph.remove_connection(conn.id)
                    removed_count += 1

            if removed_count > 0:
                self.graph_changed.emit()

            return _make_response(
                {
                    "success": True,
                    "removed_count": removed_count,
                    "message": f"已断开 {removed_count} 个连接",
                }
            )
        except Exception as e:
            _logger.error(f"断开连接失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_set_node_value(self, node_id: str, port_name: str, value: Any) -> Any:
        try:
            node = self._graph.get_node(node_id)
            if node is None:
                return _make_response(
                    {"success": False, "error": f"节点不存在: {node_id}"}, success=False
                )

            node.widget_values[port_name] = value

            # 发出值变化信号，通知UI更新控件
            self.node_value_changed.emit(node_id, port_name, value)

            _logger.info(
                f"[Thread: {threading.current_thread().name}] 设置节点值: "
                f"node={node_id[:8]}..., port={port_name}, value={value}"
            )

            return _make_response(
                {
                    "success": True,
                    "node_id": node_id,
                    "port_name": port_name,
                    "value": value,
                    "message": f"已设置节点 {node_id[:8]}... 的 {port_name} 值",
                }
            )
        except Exception as e:
            _logger.error(f"设置节点值失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_execute_workflow(self) -> Any:
        try:
            results = self._engine.execute_graph(self._graph)

            success_count = sum(1 for r in results.values() if r.success)
            failed_count = len(results) - success_count

            return _make_response(
                {
                    "success": failed_count == 0,
                    "total_nodes": len(results),
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "results": {
                        node_id: {
                            "success": r.success,
                            "outputs": r.outputs if r.success else None,
                            "error": r.error if not r.success else None,
                        }
                        for node_id, r in results.items()
                    },
                }
            )
        except Exception as e:
            _logger.error(f"执行工作流失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_list_nodes(self) -> Any:
        try:
            nodes = []
            for node in self._graph.nodes.values():
                nodes.append(
                    {
                        "node_id": node.id,
                        "node_type": node.node_type,
                        "position": node.position,
                        "state": node.state.value,
                        "inputs": list(node.widget_values.keys()) if node.widget_values else [],
                    }
                )

            return _make_response({"success": True, "nodes": nodes, "count": len(nodes)})
        except Exception as e:
            _logger.error(f"列出节点失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_list_connections(self) -> Any:
        try:
            connections = []
            for conn in self._graph.connections.values():
                connections.append(
                    {
                        "connection_id": conn.id,
                        "source": {"node_id": conn.source_node, "port": conn.source_port},
                        "target": {"node_id": conn.target_node, "port": conn.target_port},
                    }
                )

            return _make_response(
                {"success": True, "connections": connections, "count": len(connections)}
            )
        except Exception as e:
            _logger.error(f"列出连接失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_get_node_types(self) -> Any:
        try:
            node_types = self._engine.get_available_nodes()
            simplified_list = []
            for node_type in node_types:
                simplified_list.append(
                    {
                        "node_type": node_type.get("node_type", node_type),
                        "display_name": node_type.get("display_name", node_type),
                        "category": node_type.get("category", node_type),
                        "description": node_type.get("description", "")[:50],
                    }
                )
            return _make_response(
                {
                    "success": True,
                    "node_types": simplified_list,
                }
            )
        except Exception as e:
            _logger.error(f"获取节点类型失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_get_node_info(self, node_type: str) -> Any:
        try:
            node_defs = self._engine.get_available_nodes()
            for node_def in node_defs:
                if (
                    node_def.get("node_type") == node_type
                    or isinstance(node_def, dict)
                    and node_def.get("node_type") == node_type
                ):
                    return _make_response(
                        {"success": True, "node_info": NodeFormatter.format_for_agent(node_def)}
                    )
            return _make_response(
                {"success": False, "error": f"未找到节点类型: {node_type}"}, success=False
            )
        except Exception as e:
            _logger.error(f"获取节点信息失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_search_nodes(self, query: str, category: Optional[str] = None) -> Any:
        try:
            node_types = self._engine.get_available_nodes()
            results = []
            query_lower = query.lower()

            for node_def in node_types:
                node_type = node_def.get("node_type", "")
                display_name = node_def.get("display_name", "")
                description = node_def.get("description", "")
                node_category = node_def.get("category", "")

                if category and category.lower() != node_category.lower():
                    continue

                if (
                    query_lower in node_type
                    or query_lower in display_name.lower()
                    or query_lower in description.lower()
                ):
                    results.append(
                        {
                            "node_type": node_type,
                            "display_name": display_name,
                            "category": node_category,
                            "description": description[:100],
                        }
                    )

            return _make_response(
                {
                    "success": True,
                    "query": query,
                    "category": category,
                    "results": results,
                    "count": len(results),
                }
            )
        except Exception as e:
            _logger.error(f"搜索节点失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)

    def _tool_clear_workflow(self) -> Any:
        try:
            node_count = len(self._graph.nodes)
            conn_count = len(self._graph.connections)

            self._graph.nodes.clear()
            self._graph.connections.clear()

            self.graph_changed.emit()

            return _make_response(
                {
                    "success": True,
                    "message": f"已清空工作流（删除 {node_count} 个节点， {conn_count} 个连接）",
                }
            )
        except Exception as e:
            _logger.error(f"清空工作流失败: {e}", exc_info=True)
            return _make_response({"success": False, "error": str(e)}, success=False)
