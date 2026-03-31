# -*- coding: utf-8 -*-
"""
节点图形项模块

提供节点的可视化渲染：
- 节点背景和标题栏
- 输入/输出端口
- 内联控件（文本输入、数字输入等）
- 连接状态指示

使用方式：
    from src.ui.node_editor.node_item import NodeGraphicsItem

    node_item = NodeGraphicsItem(node, definition)
    scene.addItem(node_item)
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QLinearGradient
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.engine.node_graph import Node, NodeState
from src.ui.node_editor.widgets import (
    InlineWidgetProxy,
    OutputWidgetProxy,
    create_input_widget,
    create_output_widget,
)
from src.ui.node_editor.port_item import PortGraphicsItem
from src.ui.theme import Theme
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.ui.node_editor.connection_item import ConnectionGraphicsItem

_logger = get_logger(__name__)


class NodeGraphicsItem(QGraphicsObject):
    """
    节点图形项

    渲染单个节点，包括：
    - 节点背景和标题栏
    - 输入/输出端口
    - 内联控件（根据端口定义）
    - 连接状态指示
    - 执行状态指示

    Signals:
        position_changed: 位置变化时发射 (node_id: str)
        node_double_clicked: 双击时发射 (node_id: str)
        widget_value_changed: 控件值变化时发射 (port_name: str, value: Any)

    Attributes:
        HEADER_HEIGHT: 标题栏高度
        PORT_HEIGHT: 端口行高度
        PORT_SPACING: 端口间距
        MIN_WIDTH: 最小宽度
        PADDING: 内边距
        WIDGET_WIDTH: 控件宽度

    Example:
        >>> node_item = NodeGraphicsItem(node, definition)
        >>> node_item.node_id
        'abc123...'
    """

    Type = QGraphicsItem.UserType + 1

    # 信号定义
    position_changed = Signal(str)
    node_double_clicked = Signal(str)
    widget_value_changed = Signal(str, object)

    # 布局常量
    HEADER_HEIGHT = 30
    PORT_HEIGHT = 24
    PORT_SPACING = 8
    MIN_WIDTH = 200
    PADDING = 10
    WIDGET_WIDTH = 120

    def __init__(
        self,
        node: Node,
        definition: NodeDefinition,
        parent: Optional[QGraphicsItem] = None,
    ):
        """
        初始化节点图形项

        Args:
            node: 数据节点
            definition: 节点定义
            parent: 父图形项
        """
        super().__init__(parent)

        self._node = node
        self._definition = definition

        # 端口图形项映射 {端口名: PortGraphicsItem}
        self._port_items: Dict[str, PortGraphicsItem] = {}

        # 内联控件代理映射 {端口名: InlineWidgetProxy}
        self._widget_proxies: Dict[str, InlineWidgetProxy] = {}

        # 输出控件代理映射 {端口名: OutputWidgetProxy}
        self._output_widget_proxies: Dict[str, OutputWidgetProxy] = {}

        # 拖拽状态
        self._is_dragging = False
        self._drag_start_pos = QPointF()

        # 悬停状态
        self._is_hovered = False

        # 节点尺寸
        self._width = self.MIN_WIDTH
        self._height = self.HEADER_HEIGHT

        # 设置图形项属性
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # 启用设备坐标缓存，防止Windows下拖动时出现白色边框线
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        # 设置位置
        self.setPos(node.position[0], node.position[1])

        # 创建端口和控件
        self._create_port_items_with_widgets()

        # 更新尺寸
        self._update_size()

        _logger.debug(f"创建节点图形项: {definition.display_name} [{node.id[:8]}...]")

    # ==================== 属性 ====================

    @property
    def node_id(self) -> str:
        """节点ID"""
        return self._node.id

    @property
    def node_type(self) -> str:
        """节点类型"""
        return self._node.node_type

    @property
    def definition(self) -> NodeDefinition:
        """节点定义"""
        return self._definition

    @property
    def node_state(self) -> NodeState:
        """节点状态"""
        return self._node.state

    # ==================== 端口管理 ====================

    def get_port_item(self, port_name: str) -> Optional[PortGraphicsItem]:
        """
        获取端口图形项

        Args:
            port_name: 端口名称

        Returns:
            端口图形项，如果不存在则返回 None
        """
        return self._port_items.get(port_name)

    def get_all_port_items(self) -> Dict[str, PortGraphicsItem]:
        """获取所有端口图形项"""
        return self._port_items.copy()

    def _create_port_items_with_widgets(self) -> None:
        """
        创建端口图形项和内联控件

        根据端口定义创建端口图形项，并为需要内联控件的端口创建控件代理。
        控件代理作为节点图形项的子项，确保 self.scene() 能正确返回场景。
        """
        # 输入端口
        y_offset = self.HEADER_HEIGHT + self.PORT_SPACING

        for port_def in self._definition.inputs:
            # 创建端口图形项
            port_item = PortGraphicsItem(port_def, is_output=False, parent=self)
            self._port_items[port_def.name] = port_item

            # 设置端口位置（左侧）
            port_x = self.PADDING + PortGraphicsItem.PORT_RADIUS
            port_y = y_offset
            port_item.setPos(port_x, port_y)

            # 判断是否需要创建内联控件
            if self._should_create_input_widget(port_def):
                self._create_input_widget_proxy(port_def, port_y)

            y_offset += self.PORT_HEIGHT + self.PORT_SPACING

        # 输出端口
        for port_def in self._definition.outputs:
            # 创建端口图形项
            port_item = PortGraphicsItem(port_def, is_output=True, parent=self)
            self._port_items[port_def.name] = port_item

            # 设置端口位置（右侧，位置稍后更新）
            port_x = self._width - self.PADDING - PortGraphicsItem.PORT_RADIUS
            port_y = y_offset
            port_item.setPos(port_x, port_y)

            # 判断是否需要创建输出预览控件
            if self._should_create_output_widget(port_def):
                self._create_output_widget_proxy(port_def, port_y)

            y_offset += self.PORT_HEIGHT + self.PORT_SPACING

    def _should_create_input_widget(self, port_def: PortDefinition) -> bool:
        """
        判断是否需要为输入端口创建内联控件

        只有当端口定义了 widget_type 时才创建控件

        Args:
            port_def: 端口定义

        Returns:
            是否需要创建控件
        """
        return port_def.widget_type is not None

    def _should_create_output_widget(self, port_def: PortDefinition) -> bool:
        """
        判断是否需要为输出端口创建预览控件

        根据端口定义的 show_preview 属性决定

        Args:
            port_def: 端口定义

        Returns:
            是否需要创建控件
        """
        return port_def.show_preview

    def _create_input_widget_proxy(self, port_def: PortDefinition, port_y: float) -> None:
        """
        创建输入控件代理

        Args:
            port_def: 端口定义
            port_y: 端口的Y坐标
        """
        # 创建控件
        widget = create_input_widget(port_def)
        if widget is None:
            return

        # 设置控件初始值（从节点的 widget_values 或默认值）
        initial_value = self._node.widget_values.get(port_def.name, port_def.default)
        if initial_value is not None:
            widget.set_value(initial_value)

        # 连接值变化信号
        widget.value_changed.connect(
            lambda value, name=port_def.name: self._on_widget_value_changed(name, value)
        )

        # 创建代理，parent=self 确保代理是节点的子项
        proxy = InlineWidgetProxy(widget, parent=self)
        self._widget_proxies[port_def.name] = proxy

        # 定位控件（在端口名称右侧）
        # 端口名称显示在端口圆点右侧约 20px 处
        # 控件在端口名称之后
        widget_x = self.PADDING + PortGraphicsItem.PORT_RADIUS * 2 + 60  # 端口 + 名称空间
        widget_y = port_y - widget.FIXED_HEIGHT / 2 + PortGraphicsItem.PORT_RADIUS / 2
        proxy.setPos(widget_x, widget_y)

        _logger.debug(f"创建输入控件: {port_def.name}")

    def _create_output_widget_proxy(self, port_def: PortDefinition, port_y: float) -> None:
        widget = create_output_widget(port_def)
        if widget is None:
            return

        proxy = OutputWidgetProxy(widget, parent=self)
        self._output_widget_proxies[port_def.name] = proxy

        widget_width = widget.sizeHint().width() if widget.sizeHint().width() > 0 else 80
        widget_x = self._width - self.PADDING - PortGraphicsItem.PORT_RADIUS * 2 - widget_width - 70
        widget_y = port_y - widget.FIXED_HEIGHT / 2 + PortGraphicsItem.PORT_RADIUS / 2
        proxy.setPos(widget_x, widget_y)

        _logger.debug(f"创建输出预览控件: {port_def.name} at ({widget_x:.1f}, {widget_y:.1f})")

    def _update_size(self) -> None:
        """
        更新节点尺寸

        根据端口数量和控件计算节点的最终尺寸
        """
        # 计算端口区域高度
        num_ports = len(self._definition.inputs) + len(self._definition.outputs)
        ports_height = num_ports * (self.PORT_HEIGHT + self.PORT_SPACING)

        # 计算总高度
        self._height = self.HEADER_HEIGHT + ports_height + self.PADDING

        # 计算宽度（考虑控件宽度）
        self._width = self.MIN_WIDTH

        # 如果有控件，增加宽度
        if self._widget_proxies or self._output_widget_proxies:
            self._width += self.WIDGET_WIDTH

        # 更新输出端口位置（右侧）
        y_offset = self.HEADER_HEIGHT + self.PORT_SPACING
        for port_def in self._definition.inputs:
            y_offset += self.PORT_HEIGHT + self.PORT_SPACING

        for port_def in self._definition.outputs:
            port_item = self._port_items.get(port_def.name)
            if port_item:
                port_x = self._width - self.PADDING - PortGraphicsItem.PORT_RADIUS
                port_item.setPos(port_x, port_item.pos().y())

    # ==================== 控件状态管理 ====================

    def update_input_widget_state(self, port_name: str, has_connection: bool) -> None:
        """
        更新输入控件的启用状态

        当端口有连接时，禁用控件（LiteGraph 模式）

        Args:
            port_name: 端口名称
            has_connection: 是否有连接
        """
        proxy = self._widget_proxies.get(port_name)
        if proxy:
            # 有连接时禁用控件
            proxy.set_enabled(not has_connection)
            _logger.debug(f"控件状态更新: {port_name} -> {'禁用' if has_connection else '启用'}")

    def get_widget_value(self, port_name: str) -> Any:
        """
        获取控件的当前值

        Args:
            port_name: 端口名称

        Returns:
            控件值，如果没有控件则返回 None
        """
        proxy = self._widget_proxies.get(port_name)
        return proxy.get_value() if proxy else None

    def set_widget_value(self, port_name: str, value: Any) -> None:
        """
        设置控件的值

        Args:
            port_name: 端口名称
            value: 要设置的值
        """
        proxy = self._widget_proxies.get(port_name)
        if proxy:
            proxy.set_value(value)

    def set_output_value(self, port_name: str, value: Any) -> None:
        """
        设置输出预览控件的值

        Args:
            port_name: 端口名称
            value: 输出值
        """
        proxy = self._output_widget_proxies.get(port_name)
        if proxy:
            proxy.set_value(value)

    def set_output_error(self, port_name: str, error_msg: str) -> None:
        """
        设置输出预览控件的错误状态

        Args:
            port_name: 端口名称
            error_msg: 错误消息
        """
        proxy = self._output_widget_proxies.get(port_name)
        if proxy:
            proxy.set_error(error_msg)

    def _on_widget_value_changed(self, port_name: str, value: Any) -> None:
        """
        控件值变化处理

        Args:
            port_name: 端口名称
            value: 新值
        """
        # 更新节点的 widget_values
        self._node.widget_values[port_name] = value

        # 发射信号
        self.widget_value_changed.emit(port_name, value)

        _logger.debug(f"控件值变化: {port_name} = {value}")

    # ==================== 几何 ====================

    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        return QRectF(0, 0, self._width, self._height)

    def shape(self):
        """返回形状（用于碰撞检测和点击测试）"""
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.addRoundedRect(0, 0, self._width, self._height, 5, 5)
        return path

    # ==================== 绘制 ====================

    def paint(self, painter: QPainter, option, widget) -> None:
        """绘制节点"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制背景
        self._paint_background(painter)

        # 绘制标题栏
        self._paint_header(painter)

        # 绘制端口名称
        self._paint_port_names(painter)

    def _paint_background(self, painter: QPainter) -> None:
        """绘制节点背景"""
        # 背景颜色（根据状态）
        if self._node.state == NodeState.RUNNING:
            bg_color = Theme.color("node_bg_running")
        elif self._node.state == NodeState.SUCCESS:
            bg_color = Theme.color("node_bg_success")
        elif self._node.state == NodeState.ERROR:
            bg_color = Theme.color("node_bg_error")
        else:
            bg_color = Theme.color("node_bg_idle")

        # 选中状态
        if self.isSelected():
            border_color = Theme.NODE_SELECTED_BORDER
        elif self._is_hovered:
            border_color = Theme.color("node_border_hover")
        else:
            border_color = Theme.color("node_border_normal")

        # 绘制圆角矩形背景
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2.0))
        painter.drawRoundedRect(1, 1, self._width - 2, self._height - 2, 5, 5)

    def _paint_header(self, painter: QPainter) -> None:
        """绘制标题栏"""
        # 标题栏背景渐变
        gradient = QLinearGradient(0, 0, 0, self.HEADER_HEIGHT)
        gradient.setColorAt(0, Theme.color("node_border_normal"))
        gradient.setColorAt(1, Theme.color("node_bg_idle"))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(1, 1, self._width - 2, self.HEADER_HEIGHT - 2, 5, 5)
        painter.drawRect(1, self.HEADER_HEIGHT // 2, self._width - 2, self.HEADER_HEIGHT // 2)

        # 绘制图标
        painter.setPen(QPen(Qt.GlobalColor.white))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(
            QRectF(self.PADDING, 0, 20, self.HEADER_HEIGHT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._definition.icon,
        )

        # 绘制标题
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(Theme.color("node_title")))
        painter.drawText(
            QRectF(self.PADDING + 20, 0, self._width - self.PADDING * 2 - 20, self.HEADER_HEIGHT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._definition.display_name,
        )

    def _paint_port_names(self, painter: QPainter) -> None:
        """绘制端口名称"""
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QPen(Theme.color("node_port_name")))

        # 输入端口名称
        y_offset = self.HEADER_HEIGHT + self.PORT_SPACING
        for port_def in self._definition.inputs:
            # 端口名称在端口圆点右侧
            text_x = self.PADDING + PortGraphicsItem.PORT_RADIUS * 2 + 5
            text_y = y_offset
            painter.drawText(
                QRectF(text_x, text_y - self.PORT_HEIGHT / 2, 50, self.PORT_HEIGHT),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                port_def.name,
            )
            y_offset += self.PORT_HEIGHT + self.PORT_SPACING

        # 输出端口名称（右对齐）
        for port_def in self._definition.outputs:
            # 端口名称在端口圆点左侧
            text_width = 60
            text_x = self._width - self.PADDING - PortGraphicsItem.PORT_RADIUS * 2 - text_width - 5
            text_y = y_offset
            painter.drawText(
                QRectF(text_x, text_y - self.PORT_HEIGHT / 2, text_width, self.PORT_HEIGHT),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                port_def.name,
            )
            y_offset += self.PORT_HEIGHT + self.PORT_SPACING

    # ==================== 事件处理 ====================

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()

            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.setSelected(not self.isSelected())
                event.accept()
                return

            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.setSelected(True)
                event.accept()
                return

            if not self.isSelected():
                if self.scene():
                    for item in self.scene().selectedItems():
                        item.setSelected(False)
                self.setSelected(True)

            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
            ):
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        """
        键盘按下事件

        处理 Delete 键删除选中的节点
        """
        from PySide6.QtCore import Qt

        if event.key() == Qt.Key.Key_Delete:
            # 删除节点
            if self.scene() and self.isSelected():
                # 通过场景删除节点
                if hasattr(self.scene(), "remove_node_item"):
                    self.scene().remove_node_item(self._node.id)
                    _logger.info(f"删除节点: {self._node.id[:8]}...")
            event.accept()
            return

        super().keyPressEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """项目变化事件"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            x, y = round(self.pos().x()), round(self.pos().y())
            if x != self.pos().x() or y != self.pos().y():
                self.setPos(x, y)
            self._node.position = (x, y)
            self.position_changed.emit(self._node.id)
            self._update_all_connections()

        return super().itemChange(change, value)

    def _update_all_connections(self) -> None:
        """
        更新所有与该节点相关的连接线

        当节点移动时调用，确保连接线跟随端口位置更新
        """
        for port_item in self._port_items.values():
            for conn in port_item.get_connections():
                conn.update_path()

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

    def mouseDoubleClickEvent(self, event) -> None:
        """双击事件"""
        self.node_double_clicked.emit(self._node.id)
        event.accept()

    def type(self) -> int:
        """返回类型标识"""
        return NodeGraphicsItem.Type

    def __repr__(self) -> str:
        """节点图形项的字符串表示"""
        return f"<NodeGraphicsItem {self._definition.display_name} [{self._node.id[:8]}...]>"
