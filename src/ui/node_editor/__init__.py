# -*- coding: utf-8 -*-
"""
节点编辑器UI模块

提供节点编辑器的图形界面组件：
- NodeEditorScene: QGraphicsScene场景管理
- NodeEditorView: QGraphicsView视图和交互
- NodeGraphicsItem: 节点图形项
- PortGraphicsItem: 端口图形项
- ConnectionGraphicsItem: 连接图形项
- NodeEditorPanel: 完整的节点编辑器面板

使用方式：
    from src.ui.node_editor import NodeEditorPanel

    panel = NodeEditorPanel(engine)
    panel.show()
"""

from src.ui.node_editor.scene import NodeEditorScene
from src.ui.node_editor.view import NodeEditorView
from src.ui.node_editor.panel import NodeEditorPanel

__all__ = [
    "NodeEditorScene",
    "NodeEditorView",
    "NodeEditorPanel",
]
