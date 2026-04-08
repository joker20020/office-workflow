# -*- coding: utf-8 -*-
"""
连接图形项模块

提供连接线的可视化渲染：
- 贝塞尔曲线（cubicTo）
- 动态跟随端口位置
- 悬停/选中高亮
- 类型颜色

使用方式：
    from src.ui.node_editor.connection_item import ConnectionGraphicsItem

    conn_item = ConnectionGraphicsItem(conn, source_port, target_port)
    scene.addItem(conn_item)
"""

from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsItem, QMenu
from src.engine.node_graph import Connection
from src.utils.logger import get_logger
from src.ui.theme import Theme

if TYPE_CHECKING:
    from src.ui.node_editor.port_item import PortGraphicsItem
    from src.ui.node_editor.scene import NodeEditorScene

_logger = get_logger(__name__)


class ConnectionGraphicsItem(QGraphicsPathItem):
    """
    连接图形项

    使用贝塞尔曲线渲染两个端口之间的连接。

    特性：
    - 自动计算贝塞尔曲线控制点
    - 动态跟随端口位置
    - 选中/悬停高亮
    - 根据端口类型显示颜色
    - 支持右键菜单删除

    """

    context_menu_requested = Signal(str)  # connection_id
    Type = QGraphicsPathItem.UserType + 3

    LINE_WIDTH = 2
    LINE_WIDTH_HOVER = 3
    LINE_WIDTH_SELECTED = 4
    CONTROL_POINT_DISTANCE = 80

    def __init__(
        self,
        connection: Connection,
        source_port: "PortGraphicsItem",
        target_port: "PortGraphicsItem",
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent)
        self._connection = connection
        self._source_port = source_port
        self._target_port = target_port
        self._is_hovered = False
        self._is_highlighted = False
        self._context_menu: Optional[QMenu] = None
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        color = source_port.color
        self._pen = QPen(color)
        self._pen.setWidth(self.LINE_WIDTH)
        self._pen.setCosmetic(True)
        if connection.is_back_edge:
            self._pen.setStyle(Qt.PenStyle.DashLine)

        self._pen_hover = QPen(color.lighter(130))
        self._pen_hover.setWidth(self.LINE_WIDTH_HOVER)
        self._pen_hover.setCosmetic(True)
        if connection.is_back_edge:
            self._pen_hover.setStyle(Qt.PenStyle.DashLine)

        self._pen_selected = QPen(color.lighter(150))
        self._pen_selected.setWidth(self.LINE_WIDTH_SELECTED)
        self._pen_selected.setCosmetic(True)
        if connection.is_back_edge:
            self._pen_selected.setStyle(Qt.PenStyle.DashLine)
        self.setPen(self._pen)
        source_port.add_connection(self)
        target_port.add_connection(self)
        self.update_path()
        _logger.debug(f"创建连接图形项: [{connection.id[:8]}...]")

    @property
    def connection_id(self) -> str:
        return self._connection.id

    @property
    def connection(self) -> Connection:
        return self._connection

    @property
    def source_port(self) -> "PortGraphicsItem":
        return self._source_port

    @property
    def target_port(self) -> "PortGraphicsItem":
        return self._target_port

    def set_highlighted(self, highlighted: bool) -> None:
        if self._is_highlighted != highlighted:
            self._is_highlighted = highlighted
            self._update_pen()

    def _update_pen(self) -> None:
        if self.isSelected() or self._is_highlighted:
            self.setPen(self._pen_selected)
        elif self._is_hovered:
            self.setPen(self._pen_hover)
        else:
            self.setPen(self._pen)

    def update_path(self) -> None:
        p1 = self._source_port.get_connection_point()
        p2 = self._target_port.get_connection_point()
        dx = p2.x() - p1.x()
        distance = abs(dx)
        ctrl_offset = min(self.CONTROL_POINT_DISTANCE, distance * 0.4)
        ctrl_offset = max(ctrl_offset, 25)
        path = QPainterPath()
        path.moveTo(p1)
        ctrl1 = QPointF(p1.x() + ctrl_offset, p1.y())
        ctrl2 = QPointF(p2.x() - ctrl_offset, p2.y())
        path.cubicTo(ctrl1, ctrl2, p2)
        self.setPath(path)

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True
        self._update_pen()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False
        self._update_pen()
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu()
        delete_action = menu.addAction("删除连接")
        delete_action.triggered.connect(self._delete_connection)
        menu.exec(event.screenPos())

    def _delete_connection(self) -> None:
        from src.ui.node_editor.scene import NodeEditorScene

        scene = self.scene()
        if scene and isinstance(scene, NodeEditorScene):
            # 先从数据层删除
            if scene._graph:
                scene._graph.remove_connection(self._connection.id)
            # 再从UI层删除
            scene.remove_connection_item(self._connection.id)
        _logger.info(f"删除连接: {self._connection.id[:8]}...")

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_pen()
        return super().itemChange(change, value)

    def cleanup(self) -> None:
        if self._source_port:
            self._source_port.remove_connection(self)
        if self._target_port:
            self._target_port.remove_connection(self)

    def type(self) -> int:
        return ConnectionGraphicsItem.Type

    def __repr__(self) -> str:
        return (
            f"<ConnectionGraphicsItem "
            f"{self._connection.source_node[:8]}...:{self._connection.source_port} -> "
            f"{self._connection.target_node[:8]}...:{self._connection.target_port}>"
        )


class DragConnectionItem(QGraphicsPathItem):
    """
    拖拽连接图形项

    用于创建新连接时的临时连接线。
    起点是固定端口，终点跟随鼠标移动。

    Example:
        >>> drag_conn = DragConnectionItem(start_port)
        >>> drag_conn.set_end_pos(mouse_pos)
    """

    Type = QGraphicsPathItem.UserType + 4

    def __init__(
        self,
        start_port: "PortGraphicsItem",
        parent: Optional[QGraphicsItem] = None,
    ):
        """
        初始化拖拽连接

        Args:
            start_port: 起始端口
            parent: 父图形项
        """
        super().__init__(parent)

        self._start_port = start_port
        self._end_pos: Optional[QPointF] = None

        # 设置属性
        self.setZValue(100)  # 拖拽连接在最上层
        self.setAcceptHoverEvents(False)

        # 画笔
        color = start_port.color
        self._pen = QPen(color)
        self._pen.setWidth(2)
        self._pen.setStyle(Qt.PenStyle.DashLine)
        self._pen.setCosmetic(True)
        self.setPen(self._pen)

        _logger.debug("创建拖拽连接")

    def set_end_pos(self, pos: QPointF) -> None:
        """
        设置终点位置

        Args:
            pos: 终点位置（场景坐标）
        """
        self._end_pos = pos
        self._update_path()

    def _update_path(self) -> None:
        """更新路径"""
        if self._end_pos is None:
            return

        p1 = self._start_port.get_connection_point()
        p2 = self._end_pos

        path = QPainterPath()
        path.moveTo(p1)

        # S 形曲线
        dx = p2.x() - p1.x()
        ctrl_offset = min(80, abs(dx) * 0.4)
        ctrl_offset = max(ctrl_offset, 25)

        if self._start_port.is_output:
            ctrl1 = QPointF(p1.x() + ctrl_offset, p1.y())
            ctrl2 = QPointF(p2.x() - ctrl_offset, p2.y())
        else:
            ctrl1 = QPointF(p1.x() - ctrl_offset, p1.y())
            ctrl2 = QPointF(p2.x() + ctrl_offset, p2.y())

        path.cubicTo(ctrl1, ctrl2, p2)
        self.setPath(path)

    def type(self) -> int:
        """返回类型标识"""
        return DragConnectionItem.Type
