# -*- coding: utf-8 -*-
"""
节点编辑器场景模块

提供QGraphicsScene实现，管理：
- 节点图形项
- 连接图形项
- 场景事件处理
- 背景网格绘制

使用方式：
    from src.ui.node_editor.scene import NodeEditorScene

    scene = NodeEditorScene()
    scene.set_graph(graph)  # 绑定数据图
"""

from typing import TYPE_CHECKING, Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem, QGraphicsSceneMouseEvent
from src.utils.logger import get_logger
from src.ui.theme import Theme

if TYPE_CHECKING:
    from src.engine.node_engine import NodeRegistry
    from src.engine.node_graph import NodeGraph, Node, Connection
    from src.ui.node_editor.node_item import NodeGraphicsItem
    from src.ui.node_editor.connection_item import ConnectionGraphicsItem
    from src.ui.node_editor.port_item import PortGraphicsItem
_logger = get_logger(__name__)


class NodeEditorScene(QGraphicsScene):
    """
    节点编辑器场景

    继承QGraphicsScene，提供：
    - 节点和连接的图形管理
    - 背景网格绘制
    - 场景事件分发
    - 数据图同步

    Signals:
        node_added: 节点添加时发射 (node_id: str)
        node_removed: 节点移除时发射 (node_id: str)
        connection_added: 连接添加时发射 (connection_id: str)
        connection_removed: 连接移除时发射 (connection_id: str)
        selection_changed: 选择变化时发射 (node_ids: List[str])

    Example:
        >>> scene = NodeEditorScene()
        >>> scene.node_added.connect(self.on_node_added)
        >>> scene.add_node_item(node_item)
    """

    # 信号定义
    node_added = Signal(str)
    node_removed = Signal(str)
    connection_added = Signal(str)
    connection_removed = Signal(str)
    selection_changed = Signal(list)

    # 网格设置 - 使用主题系统
    GRID_SIZE = 20
    GRID_COLOR_MAJOR = Theme.GRID_MAJOR
    GRID_COLOR_MINOR = Theme.GRID_MINOR
    BACKGROUND_COLOR = Theme.GRID_BACKGROUND

    def __init__(self, parent=None):
        """
        初始化场景

        Args:
            parent: 父对象
        """
        super().__init__(parent)

        # 节点和连接的图形项映射
        self._node_items: Dict[str, "NodeGraphicsItem"] = {}
        self._connection_items: Dict[str, "ConnectionGraphicsItem"] = {}

        # 数据层引用
        self._node_registry: Optional["NodeRegistry"] = None
        self._graph: Optional["NodeGraph"] = None

        # 拖拽连接状态
        self._drag_connection: Optional["DragConnectionItem"] = None
        self._drag_start_port: Optional["PortGraphicsItem"] = None
        self._drag_existing_connection: Optional["Connection"] = None

        # 场景设置
        self.setSceneRect(-5000, -5000, 10000, 10000)

        # 网格画笔
        self._grid_pen_minor = Theme.color("grid_minor")
        self._grid_pen_major = Theme.color("grid_major")

        _logger.debug("NodeEditorScene 初始化完成")

    def set_node_registry(self, registry: "NodeRegistry") -> None:
        """
        设置节点注册表

        Args:
            registry: 节点注册表
        """
        self._node_registry = registry
        _logger.debug("节点注册表已设置")

    def set_graph(self, graph: "NodeGraph") -> None:
        import threading

        _logger.info(
            f"[Thread: {threading.current_thread().name}] NodeEditorScene.set_graph被调用， "
            f"节点数: {len(graph.nodes) if graph else 0}"
        )
        self._graph = graph

        if graph is None:
            self.clear_scene()
            return

        # 增量更新：只添加新节点，不清空现有节点
        existing_ids = set(self._node_items.keys())
        new_ids = set(graph.nodes.keys())

        # 移除不再存在的节点
        for node_id in existing_ids - new_ids:
            self.remove_node_item(node_id)
            _logger.debug(f"移除旧节点: {node_id[:8]}...")

        # 添加新节点
        added_count = 0
        for node_id, node in graph.nodes.items():
            if node_id not in existing_ids:
                if self._create_node_item(node):
                    added_count += 1

        # 移除不再存在的连接
        existing_conn_ids = set(self._connection_items.keys())
        new_conn_ids = set(graph.connections.keys())
        for conn_id in existing_conn_ids - new_conn_ids:
            self.remove_connection_item(conn_id)

        # 添加新连接
        for conn_id, conn in graph.connections.items():
            if conn_id not in existing_conn_ids:
                self._create_connection_item(conn)

        _logger.info(
            f"[Thread: {threading.current_thread().name}] 场景增量更新完成: "
            f"新增 {added_count} 节点, 共 {len(self._node_items)} 节点, {len(self._connection_items)} 连接"
        )

    def get_graph(self) -> Optional["NodeGraph"]:
        """获取绑定的数据图"""
        return self._graph

    # ==================== 节点管理 ====================

    def add_node_item(self, node_item: "NodeGraphicsItem") -> None:
        """
        添加节点图形项

        Args:
            node_item: 节点图形项
        """
        if node_item.node_id in self._node_items:
            _logger.warning(f"节点已存在: {node_item.node_id[:8]}...")
            return

        self.addItem(node_item)
        self._node_items[node_item.node_id] = node_item
        self.node_added.emit(node_item.node_id)

        _logger.debug(f"添加节点图形项: {node_item.node_id[:8]}...")

    def remove_node_item(self, node_id: str) -> None:
        """
        移除节点图形项

        同时移除该节点相关的所有连接图形项

        Args:
            node_id: 节点ID
        """
        if node_id not in self._node_items:
            return

        # 先删除相关连接的图形项
        if self._graph:
            related_conns = self._graph.get_connections_for_node(node_id)
            for conn in related_conns:
                conn_item = self._connection_items.pop(conn.id, None)
                if conn_item:
                    conn_item.cleanup()
                    self.removeItem(conn_item)
                    _logger.debug(f"删除连接图形项: {conn.id[:8]}...")

        # 删除节点图形项
        node_item = self._node_items.pop(node_id)
        self.removeItem(node_item)
        self.node_removed.emit(node_id)

        _logger.debug(f"移除节点图形项: {node_id[:8]}...")

    def get_node_item(self, node_id: str) -> Optional["NodeGraphicsItem"]:
        """
        获取节点图形项

        Args:
            node_id: 节点ID

        Returns:
            节点图形项，如果不存在则返回 None
        """
        return self._node_items.get(node_id)

    def _create_node_item(self, node: "Node") -> "NodeGraphicsItem":
        import threading

        _logger.info(
            f"[Thread: {threading.current_thread().name}] _create_node_item: "
            f"创建节点图形项 {node.node_type}, id={node.id[:8]}..."
        )
        from src.ui.node_editor.node_item import NodeGraphicsItem

        if self._node_registry is None:
            _logger.warning("节点注册表未设置，无法创建节点图形项")
            return None

        definition = self._node_registry.get(node.node_type)
        if definition is None:
            _logger.warning(f"未找到节点定义: {node.node_type}")
            return None

        node_item = NodeGraphicsItem(node, definition)
        self.add_node_item(node_item)
        _logger.info(
            f"[Thread: {threading.current_thread().name}] 节点图形项创建完成: {node.id[:8]}..."
        )
        return node_item

    # ==================== 连接管理 ====================

    def add_connection_item(self, conn_item: "ConnectionGraphicsItem") -> None:
        """
        添加连接图形项

        Args:
            conn_item: 连接图形项
        """
        if conn_item.connection_id in self._connection_items:
            return

        self.addItem(conn_item)
        self._connection_items[conn_item.connection_id] = conn_item
        self.connection_added.emit(conn_item.connection_id)

        _logger.debug(f"添加连接图形项: {conn_item.connection_id[:8]}...")

    def remove_connection_item(self, connection_id: str) -> None:
        """移除连接图形项并并重新启用目标节点的输入控件（LiteGraph模式）

        当连接被移除时，目标端口的Widget应该重新启用，允许用户再次手动输入值。
        """
        if connection_id not in self._connection_items:
            return

        conn_item = self._connection_items[connection_id]

        # 获取连接信息用于恢复控件状态
        conn = conn_item.connection
        target_node_id = conn.target_node
        target_port_name = conn.target_port

        # 从端口移除连接引用
        source_port = conn_item.source_port
        target_port = conn_item.target_port
        source_port.remove_connection(conn_item)
        target_port.remove_connection(conn_item)

        # 移除图形项
        self.removeItem(conn_item)
        del self._connection_items[connection_id]

        # 重新启用目标节点的输入控件
        target_node_item = self.get_node_item(target_node_id)
        if target_node_item:
            target_node_item.update_input_widget_state(target_port_name, has_connection=False)

        self.connection_removed.emit(connection_id)
        _logger.debug(f"移除连接图形项并恢复控件: {connection_id[:8]}...")

    def _re_enable_widget_for_connection(self, connection: "Connection") -> None:
        """
        Re-enable widget for a connection being removed

        Used when connection is removed without going through remove_connection_item(),
        """
        target_node_id = connection.target_node
        target_port_name = connection.target_port

        target_node_item = self.get_node_item(target_node_id)
        if target_node_item:
            target_node_item.update_input_widget_state(target_port_name, has_connection=False)
            _logger.debug(f"通过helper恢复控件状态: {target_port_name}")

    def get_connection_item(self, connection_id: str) -> Optional["ConnectionGraphicsItem"]:
        """
        获取连接图形项

        Args:
            connection_id: 连接ID

        Returns:
            连接图形项，如果不存在则返回 None
        """
        return self._connection_items.get(connection_id)

    def _create_connection_item(self, conn: "Connection") -> Optional["ConnectionGraphicsItem"]:
        """
        创建连接图形项（内部方法）

        Args:
            conn: 数据连接

        Returns:
            创建的连接图形项
        """
        from src.ui.node_editor.connection_item import ConnectionGraphicsItem

        source_item = self.get_node_item(conn.source_node)
        target_item = self.get_node_item(conn.target_node)

        if source_item is None or target_item is None:
            _logger.warning(f"无法创建连接: 节点图形项不存在")
            return None

        source_port = source_item.get_port_item(conn.source_port)
        target_port = target_item.get_port_item(conn.target_port)

        if source_port is None or target_port is None:
            _logger.warning(f"无法创建连接: 端口图形项不存在")
            return None

        conn_item = ConnectionGraphicsItem(conn, source_port, target_port)
        self.add_connection_item(conn_item)
        return conn_item

    # ==================== 场景操作 ====================

    def clear_scene(self) -> None:
        """
        清空场景

        删除所有节点和连接图形项
        """
        # 先清空连接（避免悬空引用）
        for conn_id in list(self._connection_items.keys()):
            self.remove_connection_item(conn_id)

        # 再清空节点
        for node_id in list(self._node_items.keys()):
            self.remove_node_item(node_id)

        _logger.info("场景已清空")

    def get_selected_node_ids(self) -> List[str]:
        """
        获取选中的节点ID列表

        Returns:
            选中的节点ID列表
        """
        selected = []
        for item in self.selectedItems():
            if hasattr(item, "node_id"):
                selected.append(item.node_id)
        return selected

    def get_all_node_items(self) -> Dict[str, "NodeGraphicsItem"]:
        """获取所有节点图形项"""
        return self._node_items.copy()

    def get_all_connection_items(self) -> Dict[str, "ConnectionGraphicsItem"]:
        """获取所有连接图形项"""
        return self._connection_items.copy()

    # ==================== 背景绘制 ====================

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """
        绘制背景网格

        Args:
            painter: 画笔
            rect: 需要绘制的区域
        """
        super().drawBackground(painter, rect)

        # 填充背景
        painter.fillRect(rect, self.BACKGROUND_COLOR)

        # 计算网格范围
        left = int(rect.left()) - (int(rect.left()) % self.GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % self.GRID_SIZE)

        # 绘制细网格
        painter.setPen(self._grid_pen_minor)
        x = left
        while x <= rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += self.GRID_SIZE

        y = top
        while y <= rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += self.GRID_SIZE

        # 绘制粗网格（每5格）
        painter.setPen(self._grid_pen_major)
        x = left
        while x <= rect.right():
            if x % (self.GRID_SIZE * 5) == 0:
                painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += self.GRID_SIZE

        y = top
        while y <= rect.bottom():
            if y % (self.GRID_SIZE * 5) == 0:
                painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += self.GRID_SIZE

    # ==================== 端口拖拽连接 ====================

    def start_port_drag(self, start_port: "PortGraphicsItem", scene_pos: QPointF) -> None:
        """
        开始端口拖拽连接

        Args:
            start_port: 起始端口
            scene_pos: 场景坐标
        """
        from src.ui.node_editor.connection_item import DragConnectionItem
        from src.ui.node_editor.node_item import NodeGraphicsItem

        # 清理之前的拖拽
        if self._drag_connection:
            self.removeItem(self._drag_connection)

        self._drag_start_port = start_port

        # 如果从输入端口拖拽，检查是否有已有连接
        if not start_port.is_output:
            node_item = start_port.parentItem()
            if isinstance(node_item, NodeGraphicsItem):
                # 查找连接到该输入端口的连接
                existing_conn = (
                    self._graph.get_connection_to_port(node_item.node_id, start_port.port_name)
                    if self._graph
                    else None
                )

                if existing_conn:
                    # 保存已有连接信息，用于取消时恢复或删除
                    self._drag_existing_connection = existing_conn
                    self._re_enable_widget_for_connection(existing_conn)
                    conn_item = self._connection_items.pop(existing_conn.id, None)
                    if conn_item:
                        conn_item.cleanup()
                        self.removeItem(conn_item)
                    _logger.debug(f"从输入端口拖拽已有连接: {existing_conn.id[:8]}...")
                else:
                    self._drag_existing_connection = None
            else:
                self._drag_existing_connection = None
        else:
            self._drag_existing_connection = None

        self._drag_connection = DragConnectionItem(start_port)
        self.addItem(self._drag_connection)
        self._drag_connection.set_end_pos(scene_pos)

        _logger.debug(f"开始端口拖拽: {start_port.port_name}")

    def update_port_drag(self, scene_pos: QPointF) -> None:
        """
        更新拖拽连接位置

        Args:
            scene_pos: 当前鼠标场景坐标
        """
        if self._drag_connection:
            self._drag_connection.set_end_pos(scene_pos)

    def finish_port_drag(self, end_port: Optional["PortGraphicsItem"]) -> None:
        """
        完成端口拖拽连接

        Args:
            end_port: 目标端口（None表示取消）
        """
        from src.ui.node_editor.node_item import NodeGraphicsItem

        if not self._drag_connection:
            return

        # 清理拖拽图形项
        drag_item = self._drag_connection
        self._drag_connection = None
        start_port = self._drag_start_port
        self._drag_start_port = None
        existing_conn = getattr(self, "_drag_existing_connection", None)
        self._drag_existing_connection = None
        self.removeItem(drag_item)

        # 取消拖拽
        if end_port is None:
            # 如果从 input 端拖拽了已有连接，现在取消了，需要删除该连接
            if existing_conn and self._graph:
                self._re_enable_widget_for_connection(existing_conn)
                self._graph.remove_connection(existing_conn.id)
                _logger.info(f"取消拖拽，删除已有连接: {existing_conn.id[:8]}...")
            else:
                _logger.debug("端口拖拽取消")
            return

        # 验证连接有效性
        if not self._can_connect(start_port, end_port):
            # 如果从 input 端拖拽了已有连接但连接失败，也需要删除
            if existing_conn and self._graph:
                self._re_enable_widget_for_connection(existing_conn)
                self._graph.remove_connection(existing_conn.id)
                _logger.debug(f"连接失败，删除已有连接: {existing_conn.id[:8]}...")
            else:
                _logger.debug(f"无法连接: 类型不兼容或同端口")
            return

        # 创建数据层连接
        if self._graph is None:
            _logger.warning("无法创建连接: 数据图未设置")
            return

        # 获取节点信息
        start_node_item = start_port.parentItem()
        end_node_item = end_port.parentItem()

        if not isinstance(start_node_item, NodeGraphicsItem) or not isinstance(
            end_node_item, NodeGraphicsItem
        ):
            return

        # 确定源和目标（输出端口 -> 输入端口)
        if start_port.is_output:
            source_node = start_node_item.node_id
            source_port = start_port.port_name
            target_node = end_node_item.node_id
            target_port = end_port.port_name
        else:
            source_node = end_node_item.node_id
            source_port = end_port.port_name
            target_node = start_node_item.node_id
            target_port = start_port.port_name

        # 检查并删除目标端口的已有连接（输入端口只能有一个连接）
        if not end_port.is_output:
            existing_conns = self._graph.get_incoming_connections(target_node)
            for conn in existing_conns:
                if conn.target_port == target_port:
                    # 跳过我们正在拖拽的连接（它已经在数据层被删除了 UI）
                    if existing_conn and conn.id == existing_conn.id:
                        continue
                    _logger.debug(f"删除已有连接: {conn.id[:8]}...")
                    # 删除UI连接
                    conn_item = self._connection_items.pop(conn.id, None)
                    if conn_item:
                        self._re_enable_widget_for_connection(conn)
                        conn_item.cleanup()
                        self.removeItem(conn_item)
                    # 删除数据层连接
                    self._graph.remove_connection(conn.id)
                    break

        # 创建数据层连接
        try:
            conn = self._graph.add_connection(
                source_node=source_node,
                source_port=source_port,
                target_node=target_node,
                target_port=target_port,
            )
        except Exception as e:
            _logger.error(f"创建连接失败: {e}")
            return
        # 创建UI连接
        try:
            conn_item = self._create_connection_item(conn)
        except Exception as e:
            _logger.error(f"创建连接图形项失败: {e}")
            return
        # 通知目标节点的输入控件被禁用
        if conn_item:
            target_node_item = self.get_node_item(target_node)
            if target_node_item:
                target_node_item.update_input_widget_state(target_port, has_connection=True)

            _logger.info(
                f"创建连接: {source_node[:8]}...:{source_port} -> {target_node[:8]}...:{target_port}"
            )

    def cancel_port_drag(self) -> None:
        """取消端口拖拽"""
        if self._drag_connection:
            self.removeItem(self._drag_connection)
            self._drag_connection = None
            self._drag_start_port = None
            _logger.debug("端口拖拽已取消")

    def _can_connect(self, start_port: "PortGraphicsItem", end_port: "PortGraphicsItem") -> bool:
        """
        检查两个端口是否可以连接

        Args:
            start_port: 起始端口
            end_port: 目标端口

        Returns:
            是否可以连接
        """
        # 不能连接到同一个端口
        if start_port == end_port:
            return False

        # 必须是输出端口连接到输入端口
        if start_port.is_output == end_port.is_output:
            return False

        # 类型兼容性检查
        if not start_port.port_type.is_compatible_with(end_port.port_type):
            return False

        # 不能连接到同一个节点
        start_node = start_port.parentItem()
        end_node = end_port.parentItem()
        if start_node == end_node:
            return False

        return True

    def get_port_at(self, scene_pos: QPointF) -> Optional["PortGraphicsItem"]:
        """
        获取指定场景位置的端口

        Args:
            scene_pos: 场景坐标

        Returns:
            端口图形项，如果没有则返回 None
        """
        from src.ui.node_editor.port_item import PortGraphicsItem

        items = self.items(scene_pos)
        for item in items:
            if isinstance(item, PortGraphicsItem):
                return item
        return None

    def __repr__(self) -> str:
        """场景的字符串表示"""
        return (
            f"<NodeEditorScene "
            f"nodes={len(self._node_items)} "
            f"connections={len(self._connection_items)}>"
        )
