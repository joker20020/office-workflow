# -*- coding: utf-8 -*-
"""
端口图形项模块

提供端口的可视化渲染：
- 端口圆点（类型颜色）
- 端口名称
- 悬停高亮
- 连接点位置
"""

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import QGraphicsItem

from src.engine.definitions import PortDefinition, PortType
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.ui.node_editor.connection_item import ConnectionGraphicsItem

_logger = get_logger(__name__)


class PortGraphicsItem(QGraphicsItem):
    """
    端口图形项

    渲染单个端口，包括：
    - 端口圆点（颜色根据类型）
    - 端口名称
    - 悬停高亮效果
    - 连接状态指示

    Attributes:
        PORT_RADIUS: 端口圆点半径

    Example:
        >>> port_item = PortGraphicsItem(port_def, is_output=True)
        >>> port_item.get_connection_point()  # 获取连接点
    """

    Type = QGraphicsItem.UserType + 2

    # 端口尺寸
    PORT_RADIUS = 6

    def __init__(
        self,
        port_def: PortDefinition,
        is_output: bool = False,
        parent: Optional[QGraphicsItem] = None,
    ):
        """
        初始化端口图形项

        Args:
            port_def: 端口定义
            is_output: 是否为输出端口
            parent: 父图形项（通常是NodeGraphicsItem）
        """
        super().__init__(parent)

        self._port_def = port_def
        self._is_output = is_output
        self._is_hovered = False
        self._is_connected = False

        # 连接的图形项列表
        self._connections: list["ConnectionGraphicsItem"] = []

        # 设置可悬停和可选择
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

        # 端口颜色（使用 PortType.color 属性，支持预设和自定义类型的哈希颜色）
        self._color = QColor(port_def.type.color)

        _logger.debug(f"创建端口图形项: {port_def.name} ({'输出' if is_output else '输入'})")

    # ==================== 属性 ====================

    @property
    def port_name(self) -> str:
        """端口名称"""
        return self._port_def.name

    @property
    def port_type(self) -> PortType:
        """端口数据类型"""
        return self._port_def.type

    @property
    def is_output(self) -> bool:
        """是否为输出端口"""
        return self._is_output

    @property
    def color(self) -> QColor:
        """端口颜色"""
        return self._color

    @property
    def description(self) -> str:
        """端口描述"""
        return self._port_def.description

    # ==================== 连接管理 ====================

    def add_connection(self, conn: "ConnectionGraphicsItem") -> None:
        """添加连接"""
        if conn not in self._connections:
            self._connections.append(conn)
            self._is_connected = True
            self.update()

    def remove_connection(self, conn: "ConnectionGraphicsItem") -> None:
        """移除连接"""
        if conn in self._connections:
            self._connections.remove(conn)
            self._is_connected = len(self._connections) > 0
            self.update()

    def get_connections(self) -> list["ConnectionGraphicsItem"]:
        """获取所有连接"""
        return self._connections.copy()

    def set_connected(self, connected: bool) -> None:
        """设置连接状态"""
        self._is_connected = connected
        self.update()

    # ==================== 几何 ====================

    def get_connection_point(self) -> QPointF:
        """
        获取连接点位置（场景坐标）

        Returns:
            连接点的场景坐标
        """
        # 端口圆点的中心位置
        if self._is_output:
            # 输出端口在节点右侧
            return self.scenePos() + QPointF(self.PORT_RADIUS, 0)
        else:
            # 输入端口在节点左侧
            return self.scenePos() + QPointF(-self.PORT_RADIUS, 0)

    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        # 包含端口圆点和名称文本
        return QRectF(
            -self.PORT_RADIUS - 2,
            -self.PORT_RADIUS - 2,
            self.PORT_RADIUS * 2 + 4,
            self.PORT_RADIUS * 2 + 4,
        )

    # ==================== 绘制 ====================

    def paint(self, painter: QPainter, option, widget) -> None:
        """绘制端口"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 确定端口颜色
        if self._is_hovered:
            color = self._color.lighter(130)
        else:
            color = self._color

        # 如果悬停，先绘制外圈光晕
        if self._is_hovered:
            from PySide6.QtGui import QColor
            glow_color = QColor(color)
            glow_color.setAlpha(60)
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(0, 0), self.PORT_RADIUS + 4, self.PORT_RADIUS + 4)

        # 绘制端口圆点
        if self._is_connected:
            # 已连接：填充 + 细边框
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(140), 1.0))
        else:
            # 未连接：空心 + 较粗边框
            painter.setBrush(QBrush(Qt.GlobalColor.transparent))
            painter.setPen(QPen(color, 1.8))

        painter.drawEllipse(
            QPointF(0, 0),
            self.PORT_RADIUS,
            self.PORT_RADIUS,
        )

    # ==================== 事件处理 ====================

    def hoverEnterEvent(self, event) -> None:
        """悬停进入"""
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        """悬停离开"""
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.scene() is None:
            return

        scene_pos = self.scenePos() + QPointF(
            event.pos().x() - self.boundingRect().width() / 2,
            event.pos().y() - self.boundingRect().height() / 2,
        )

        self.scene().start_port_drag(self, scene_pos)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self.scene() is None:
            return

        scene_pos = self.scenePos() + QPointF(
            event.pos().x() - self.boundingRect().width() / 2,
            event.pos().y() - self.boundingRect().height() / 2,
        )
        self.scene().update_port_drag(scene_pos)

    def mouseReleaseEvent(self, event) -> None:
        if self.scene() is None:
            return

        scene_pos = self.scenePos() + QPointF(
            event.pos().x() - self.boundingRect().width() / 2,
            event.pos().y() - self.boundingRect().height() / 2,
        )

        end_port = self.scene().get_port_at(scene_pos)
        self.scene().finish_port_drag(end_port)

    def type(self) -> int:
        """返回类型标识"""
        return PortGraphicsItem.Type

    def __repr__(self) -> str:
        """端口图形项的字符串表示"""
        return f"<PortGraphicsItem {self.port_name} ({'输出' if self._is_output else '输入'})>"
