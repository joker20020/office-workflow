# -*- coding: utf-8 -*-
"""
节点编辑器视图模块

提供QGraphicsView实现，支持：
- 平移和缩放
- 节点拖放
- 连接线绘制
- 快捷键处理

使用方式：
    from src.ui.node_editor.view import NodeEditorView

    scene = NodeEditorScene()
    view = NodeEditorView(scene)
    view.show()
"""

from typing import TYPE_CHECKING, Optional

import os

from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QPoint
from PySide6.QtGui import QWheelEvent, QMouseEvent, QKeyEvent, QPainter
from PySide6.QtWidgets import QGraphicsView, QWidget, QApplication

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.ui.node_editor.scene import NodeEditorScene

_logger = get_logger(__name__)


class NodeEditorView(QGraphicsView):
    """
    节点编辑器视图

    提供交互功能：
    - 平移（中键/右键拖动)
    - 缩放(滚轮)
    - 节点拖放(从节点面板拖入)
    - 快捷键(删除、全选等)
    """

    drop_node_type = Signal(str, float, float)
    MIN_ZOOM = 0.25
    MAX_ZOOM = 4.0
    ZOOM_STEP = 0.1

    def __init__(self, scene: "NodeEditorScene", parent: Optional[QWidget] = None):
        super().__init__(scene, parent)
        self._scene = scene
        self._zoom = 1.0
        self._panning = False
        self._last_mouse_pos = QPointF()
        self._setup_view()
        _logger.debug("NodeEditorView 初始化完成")

    def _setup_view(self) -> None:
        """配置视图属性"""
        # 渲染设置
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 拖拽模式：使用 RubberBandDrag 支持左键框选
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # 场景背景：不设置背景画笔，让场景的 drawBackground 绘制网格
        # self.setBackgroundBrush(self._scene.BACKGROUND_COLOR)
        # 变换锚点
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        # 滚动条：启用滚动条以支持平移，但设置为始终隐藏
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 接受拖放
        self.setAcceptDrops(True)
        # 场景范围
        self.setSceneRect(-5000, -5000, 10000, 10000)
        # 居中视图到场景原点
        self.centerOn(0, 0)

        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

    def _center_view(self) -> None:
        """将视图居中到场景原点"""
        self.centerOn(0, 0)

    # ==================== 缩放 ====================

    def set_zoom(self, zoom: float) -> None:
        """
        设置缩放级别

        Args:
            zoom: 缩放值 (0.25 ~ 4.0)
        """
        # 限制缩放范围
        zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))
        self._zoom = zoom
        # 重置变换并应用新的缩放
        self.resetTransform()
        self.scale(zoom, zoom)
        _logger.debug(f"缩放设置为: {zoom:.2f}x")

    def get_zoom(self) -> float:
        """获取当前缩放级别"""
        return self._zoom

    def zoom_in(self) -> None:
        """放大视图"""
        self.set_zoom(self._zoom + self.ZOOM_STEP)

    def zoom_out(self) -> None:
        """缩小视图"""
        self.set_zoom(self._zoom - self.ZOOM_STEP)

    def reset_zoom(self) -> None:
        """重置缩放到 1.0"""
        self.set_zoom(1.0)
        self.centerOn(0, 0)

    def fit_to_view(self) -> None:
        self.fitInView(self._scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ==================== 鼠标事件 ====================

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
            ):
                self._restore_drag_mode = self.dragMode()
                self.setDragMode(QGraphicsView.DragMode.NoDrag)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            delta = event.position() - self._last_mouse_pos
            self._last_mouse_pos = event.position()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x()))
            v_bar.setValue(v_bar.value() - int(delta.y()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            if self._panning:
                self._panning = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, "_restore_drag_mode"):
                self.setDragMode(self._restore_drag_mode)
                delattr(self, "_restore_drag_mode")
                event.accept()
                return

        super().mouseReleaseEvent(event)

    # ==================== 滚轮事件 ====================

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        滚轮事件处理 - 实现缩放功能

        以鼠标位置为中心进行缩放，滚轮向上放大，向下缩小
        """
        # 获取滚轮滚动的角度
        delta = event.angleDelta().y()

        if delta == 0:
            super().wheelEvent(event)
            return

        # 计算新的缩放值
        if delta > 0:
            new_zoom = min(self._zoom + self.ZOOM_STEP, self.MAX_ZOOM)
        else:
            new_zoom = max(self._zoom - self.ZOOM_STEP, self.MIN_ZOOM)

        # 如果缩放值没有变化，直接返回
        if new_zoom == self._zoom:
            event.accept()
            return

        # 记录鼠标在场景中的位置（缩放前）
        mouse_scene_pos = self.mapToScene(event.position().toPoint())

        # 应用新的缩放
        self._zoom = new_zoom
        self.resetTransform()
        self.scale(new_zoom, new_zoom)

        # 调整视图中心，使鼠标保持在相同的场景位置
        # 计算缩放后鼠标在视口中的新位置
        new_mouse_viewport_pos = self.mapFromScene(mouse_scene_pos)
        # 计算需要移动的偏移量
        mouse_offset = event.position() - QPointF(new_mouse_viewport_pos)
        # 获取当前视图中心
        current_center = self.mapToScene(self.viewport().rect().center())
        # 计算新的中心点
        new_center = current_center + QPointF(
            mouse_offset.x() / new_zoom, mouse_offset.y() / new_zoom
        )
        self.centerOn(new_center)

        event.accept()
        _logger.debug(f"缩放至: {self._zoom:.2f}x")

    # ==================== 键盘事件 ====================

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        # 检查焦点是否在可编辑控件上
        # 如果是，则不拦截Delete/Backspace键，让控件正常处理
        focus_item = self.scene().focusItem()
        if focus_item:
            from PySide6.QtWidgets import QGraphicsProxyWidget

            if isinstance(focus_item, QGraphicsProxyWidget):
                if hasattr(focus_item, "widget"):
                    widget = focus_item.widget
                else:
                    widget = focus_item.widget()

                # InlineWidgetBase 子类都是可编辑控件
                if widget is not None:
                    from src.ui.node_editor.widgets import InlineWidgetBase

                    if isinstance(widget, InlineWidgetBase):
                        super().keyPressEvent(event)
                        return

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._delete_selected_items()
            event.accept()
        elif key == Qt.Key.Key_A and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._select_all_nodes()
            event.accept()
        elif key == Qt.Key.Key_0 and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.reset_zoom()
            event.accept()
        elif key == Qt.Key.Key_F and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.fit_to_view()
            event.accept()
        elif key == Qt.Key.Key_Equal and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.zoom_in()
            event.accept()
        elif key == Qt.Key.Key_Minus and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.zoom_out()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ==================== 拖放处理 ====================
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasText():
            node_type = event.mimeData().text()
            scene_pos = self.mapToScene(int(event.position().x()), int(event.position().y()))
            self.drop_node_type.emit(node_type, scene_pos.x(), scene_pos.y())
            event.acceptProposedAction()
            _logger.debug(
                f"拖放节点类型: {node_type} at ({scene_pos.x():.0f}, {scene_pos.y():.0f})"
            )
        else:
            super().dropEvent(event)

    # ==================== 辅助方法 ====================
    def _delete_selected_items(self) -> None:
        from src.ui.node_editor.scene import NodeEditorScene
        from src.ui.node_editor.connection_item import ConnectionGraphicsItem

        selected_items = self.scene().selectedItems()
        if not selected_items:
            return
        deleted_nodes: list[str] = []
        deleted_connections: list[str] = []
        # 收集要删除的节点和连接
        for item in selected_items:
            if hasattr(item, "node_id"):
                deleted_nodes.append(item.node_id)
            elif hasattr(item, "connection_id"):
                deleted_connections.append(item.connection_id)
        if not deleted_nodes and not deleted_connections:
            return
        scene = self._scene
        if not isinstance(scene, NodeEditorScene):
            return
        # 收集节点相关的所有连接
        node_related_conn_ids: set[str] = set()
        for node_id in deleted_nodes:
            if scene._graph:
                related = scene._graph.get_connections_for_node(node_id)
                for conn in related:
                    node_related_conn_ids.add(conn.id)
        # 合并所有要删除的连接
        all_conn_ids = set(deleted_connections) | node_related_conn_ids
        # 先删除连接UI项
        for conn_id in all_conn_ids:
            if conn_id in scene._connection_items:
                conn_item = scene._connection_items.pop(conn_id)
                if conn_item:
                    conn_item.cleanup()
                    scene.removeItem(conn_item)
                    _logger.info(f"删除连接: {conn_id[:8]}...")
        # 再删除节点UI项
        for node_id in deleted_nodes:
            if node_id in scene._node_items:
                scene.removeItem(scene._node_items.pop(node_id))
                _logger.info(f"删除节点: {node_id[:8]}...")
        # 最后删除数据层
        if scene._graph:
            for conn_id in all_conn_ids:
                scene._graph.remove_connection(conn_id)
            for node_id in deleted_nodes:
                scene._graph.remove_node(node_id)

    def _select_all_nodes(self) -> None:
        for node_item in self._scene._node_items.values():
            node_item.setSelected(True)
        _logger.debug("全选所有节点")

    def __repr__(self) -> str:
        return f"<NodeEditorView zoom={self._zoom:.2f}x>"
