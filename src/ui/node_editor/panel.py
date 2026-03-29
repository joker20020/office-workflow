# -*- coding: utf-8 -*-
"""
节点编辑器面板模块

整合节点编辑器的所有UI组件：
- 工具栏（节点面板、执行按钮等）
- 节点画布（NodeEditorView）
- 数据层连接
"""

from typing import TYPE_CHECKING, Optional
from pathlib import Path
import json
from PySide6.QtCore import Qt, Signal, QMimeData, QEvent
from PySide6.QtGui import QAction, QDrag
from PySide6.QtWidgets import (
    QToolBar,
    QToolButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QLabel,
    QMessageBox,
    QFileDialog,
)

from src.engine.definitions import NodeDefinition
from src.engine.node_graph import NodeGraph, NodeState
from src.engine.node_engine import NodeEngine, get_node_engine
from src.engine.serialization import serialize_graph, deserialize_graph
from src.ui.node_editor.scene import NodeEditorScene
from src.ui.node_editor.view import NodeEditorView
from src.utils.logger import get_logger
from src.ui.theme import Theme

if TYPE_CHECKING:
    from src.core.app_context import AppContext

_logger = get_logger(__name__)


class NodeEditorPanel(QWidget):
    """节点编辑器面板"""

    workflow_executed = Signal(bool)
    workflow_saved = Signal(str)

    def __init__(
        self,
        engine: Optional[NodeEngine] = None,
        event_bus: Optional["EventBus"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        # 使用全局单例引擎，若未提供 engine，则通过单例工厂获取
        self._engine = engine or get_node_engine()
        self._event_bus = event_bus
        self._subscription_id: Optional[str] = None
        self._unsubscription_id: Optional[str] = None
        self._graph: Optional[NodeGraph] = None
        self._setup_ui()
        self._connect_signals()
        if event_bus:
            from src.core.event_bus import EventBus, EventType

            self._subscription_id = event_bus.subscribe(
                EventType.NODE_REGISTERED, self._on_node_registered
            )
            self._unsubscription_id = event_bus.subscribe(
                EventType.NODE_UNREGISTERED, self._on_node_unregistered
            )
            _logger.debug("NodeEditorPanel 已订阅 NODE_REGISTERED 和 NODE_UNREGISTERED 事件")
        self._populate_node_panel()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._scene = NodeEditorScene()
        self._scene.set_node_registry(self._engine.registry)
        self._view = NodeEditorView(self._scene)

        self._toolbar = self._create_toolbar()
        main_layout.addWidget(self._toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._node_panel = self._create_node_panel()
        splitter.addWidget(self._node_panel)
        splitter.addWidget(self._view)
        splitter.setSizes([200, 800])
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

    def _create_toolbar(self) -> QToolBar:
        toolbar = QToolBar("节点编辑器工具栏")
        toolbar.setMovable(False)
        # 使用主题系统的样式表
        toolbar.setStyleSheet(Theme.get_toolbar_stylesheet())

        self._execute_btn = QToolButton()
        self._execute_btn.setText("▶ 执行")
        self._execute_btn.setToolTip("执行工作流 (F5)")
        self._execute_btn.clicked.connect(self._on_execute)
        toolbar.addWidget(self._execute_btn)

        toolbar.addSeparator()

        self._save_btn = QToolButton()
        self._save_btn.setText("💾 保存")
        self._save_btn.setToolTip("保存工作流 (Ctrl+S)")
        self._save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(self._save_btn)

        self._load_btn = QToolButton()
        self._load_btn.setText("📂 加载")
        self._load_btn.setToolTip("加载工作流 (Ctrl+O)")
        self._load_btn.clicked.connect(self._on_load)
        toolbar.addWidget(self._load_btn)

        toolbar.addSeparator()

        self._clear_btn = QToolButton()
        self._clear_btn.setText("🗑️ 清空")
        self._clear_btn.setToolTip("清空画布")
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)

        toolbar.addSeparator()

        self._fit_btn = QToolButton()
        self._fit_btn.setText("⊞ 适应")
        self._fit_btn.setToolTip("适应视图 (Ctrl+F)")
        self._fit_btn.clicked.connect(self._view.fit_to_view)
        toolbar.addWidget(self._fit_btn)

        toolbar.addSeparator()
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet(Theme.get_status_label_stylesheet())
        toolbar.addWidget(self._status_label)

        return toolbar

    def _create_node_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("节点")
        title.setStyleSheet(Theme.get_node_panel_title_stylesheet())
        layout.addWidget(title)

        self._node_tree = QTreeWidget()
        self._node_tree.setHeaderHidden(True)
        self._node_tree.setStyleSheet(Theme.get_node_tree_stylesheet())
        self._node_tree.itemDoubleClicked.connect(self._on_node_double_clicked)
        self._node_tree.setDragEnabled(True)
        self._node_tree.startDrag = self._start_drag
        layout.addWidget(self._node_tree)

        hint = QLabel("双击或拖拽添加节点")
        hint.setStyleSheet(Theme.get_hint_label_stylesheet())
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        panel.setMinimumWidth(180)
        panel.setMaximumWidth(300)

        return panel

    def _populate_node_panel(self) -> None:
        self._node_tree.clear()

        categories: dict[str, list[NodeDefinition]] = {}
        for node_def in self._engine.get_all_node_types():
            cat = node_def.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(node_def)

        category_names = {
            "text": "文本处理",
            "math": "数学运算",
            "io": "输入输出",
            "general": "通用",
            "data": "数据处理",
        }

        for cat, nodes in sorted(categories.items()):
            cat_name = category_names.get(cat, cat.title())
            cat_item = QTreeWidgetItem([f"📁 {cat_name}"])
            cat_item.setData(0, Qt.ItemDataRole.UserRole, "category")
            self._node_tree.addTopLevelItem(cat_item)

            for node_def in sorted(nodes, key=lambda n: n.display_name):
                node_item = QTreeWidgetItem([f"{node_def.icon} {node_def.display_name}"])
                node_item.setData(0, Qt.ItemDataRole.UserRole, node_def.node_type)
                node_item.setToolTip(0, node_def.description)
                cat_item.addChild(node_item)

            cat_item.setExpanded(True)

    def _on_node_registered(self, event) -> None:
        """处理节点注册事件，刷新节点面板"""
        node_type = event.data.get("node_type") if event.data else None
        _logger.info(f"收到节点注册事件: {node_type}")
        self._populate_node_panel()

    def _on_node_unregistered(self, event) -> None:
        """处理节点注销事件，刷新节点面板"""
        node_type = event.data.get("node_type") if event.data else None
        _logger.info(f"收到节点注销事件: {node_type}")
        self._populate_node_panel()

    def unsubscribe_events(self) -> None:
        """取消订阅事件，用于清理资源"""
        if self._event_bus:
            if self._subscription_id:
                self._event_bus.unsubscribe(self._subscription_id)
                self._subscription_id = None
            if hasattr(self, "_unsubscription_id") and self._unsubscription_id:
                self._event_bus.unsubscribe(self._unsubscription_id)
                self._unsubscription_id = None
            _logger.debug("NodeEditorPanel 已取消订阅节点事件")

    def _start_drag(self, supported_actions):
        item = self._node_tree.currentItem()
        if item is None:
            return

        node_type = item.data(0, Qt.ItemDataRole.UserRole)
        if node_type == "category" or node_type is None:
            return

        mime_data = QMimeData()
        mime_data.setText(node_type)

        drag = QDrag(self._node_tree)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)

    def _connect_signals(self) -> None:
        self._view.drop_node_type.connect(self._on_drop_node)

    def set_graph(self, graph: NodeGraph) -> None:
        import threading

        _logger.info(
            f"[Thread: {threading.current_thread().name}] NodeEditorPanel.set_graph被调用，"
            f"节点数: {len(graph.nodes) if graph else 0}"
        )
        self._graph = graph
        self._scene.set_graph(graph)
        self._status_label.setText(f"已加载: {graph.name}")
        # 强制刷新视图以确保节点正确显示
        self._view.viewport().update()
        _logger.info(f"[Thread: {threading.current_thread().name}] NodeEditorPanel.set_graph完成")

    def get_graph(self) -> Optional[NodeGraph]:
        return self._graph

    def get_node_item(self, node_id: str) -> Optional["NodeGraphicsItem"]:
        return self._scene.get_node_item(node_id)

    def new_graph(self, name: str = "未命名工作流") -> NodeGraph:
        self._graph = NodeGraph(name=name)
        self._scene.set_graph(self._graph)
        self._status_label.setText(f"新建: {name}")
        return self._graph

    def _on_execute(self) -> None:
        if self._graph is None:
            QMessageBox.warning(self, "警告", "没有可执行的工作流")
            return

        if not self._graph.nodes:
            QMessageBox.warning(self, "警告", "工作流为空")
            return

        self._status_label.setText("执行中...")
        self._execute_btn.setEnabled(False)

        try:
            results = self._engine.execute_graph(self._graph)
            success_count = sum(1 for r in results.values() if r.success)
            total_count = len(results)

            if success_count == total_count:
                self._status_label.setText(f"✅ 执行成功: {success_count}/{total_count}")
                self.workflow_executed.emit(True)
                self._update_all_output_widgets()
            else:
                self._status_label.setText(f"❌ 执行失败: {success_count}/{total_count}")
                self.workflow_executed.emit(False)
                self._update_all_output_widgets()

        except Exception as e:
            self._status_label.setText(f"❌ 执行错误: {str(e)}")
            self.workflow_executed.emit(False)
            _logger.error(f"执行工作流失败: {e}", exc_info=True)

        finally:
            self._execute_btn.setEnabled(True)

    def _update_all_output_widgets(self) -> None:
        """更新所有节点的输出预览控件"""
        if not self._graph or not self._scene:
            _logger.warning("无法更新输出控件: graph 或 scene 为空")
            return

        _logger.debug(f"开始更新输出控件，共 {len(self._graph.nodes)} 个节点")
        for node_id, node in self._graph.nodes.items():
            node_item = self._scene._node_items.get(node_id)
            if not node_item:
                _logger.warning(f"找不到节点图形项: {node_id[:8]}...")
                continue

            _logger.debug(f"节点 {node_id[:8]}... 状态: {node.state}, 输出: {node.outputs}")
            if node.state == NodeState.SUCCESS and node.outputs:
                for port_name, value in node.outputs.items():
                    _logger.debug(f"设置输出值: {port_name} = {value}")
                    node_item.set_output_value(port_name, value)
            elif node.state == NodeState.ERROR and node.error_message:
                for port_def in node_item._definition.outputs:
                    if port_def.show_preview:
                        node_item.set_output_error(port_def.name, node.error_message)

    def _on_save(self) -> None:
        """保存工作流到JSON文件"""
        if self._graph is None:
            QMessageBox.warning(self, "警告", "没有可保存的工作流")
            return

        # 默认保存路径
        workflows_dir = Path("workflows")
        workflows_dir.mkdir(parents=True, exist_ok=True)
        default_file = workflows_dir / f"{self._graph.name or '未命名工作流'}.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存工作流",
            str(default_file),
            "JSON文件 (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            # 确保目录存在
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            # 序列化并保存
            json_str = serialize_graph(self._graph)
            Path(file_path).write_text(json_str, encoding="utf-8")

            self._status_label.setText(f"已保存: {Path(file_path).name}")
            self.workflow_saved.emit(self._graph.id)
            _logger.info(f"工作流已保存: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
            _logger.error(f"保存工作流失败: {e}", exc_info=True)

    def _on_load(self) -> None:
        """从JSON文件加载工作流"""
        # 默认加载路径
        workflows_dir = Path("workflows")
        workflows_dir.mkdir(parents=True, exist_ok=True)

        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载工作流",
            str(workflows_dir),
            "JSON文件 (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            # 读取文件内容
            json_str = Path(file_path).read_text(encoding="utf-8")

            # 反序列化
            graph = deserialize_graph(json_str)

            # 设置到场景
            self._graph = graph
            self._scene.set_graph(graph)

            self._status_label.setText(f"已加载: {Path(file_path).name}")
            _logger.info(f"工作流已加载: {file_path}")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "错误", f"JSON格式无效: {str(e)}")
            _logger.error(f"加载工作流失败: {e}", exc_info=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载失败: {str(e)}")
            _logger.error(f"加载工作流失败: {e}", exc_info=True)

    def _on_clear(self) -> None:
        if self._graph is None:
            return

        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空画布吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._graph.nodes.clear()
            self._graph.connections.clear()
            self._scene.clear_scene()
            self._status_label.setText("已清空")

    def _on_drop_node(self, node_type: str, x: float, y: float) -> None:
        if self._graph is None:
            self.new_graph()

        node = self._graph.add_node(node_type, position=(x, y))
        self._scene._create_node_item(node)
        self._status_label.setText(f"添加节点: {node_type}")
        _logger.info(f"拖放添加节点: {node_type} at ({x:.0f}, {y:.0f})")

    def _on_node_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        node_type = item.data(0, Qt.ItemDataRole.UserRole)
        if node_type == "category" or node_type is None:
            return

        if self._graph is None:
            self.new_graph()

        center = self._view.mapToScene(
            self._view.viewport().width() // 2, self._view.viewport().height() // 2
        )

        node = self._graph.add_node(node_type, position=(center.x(), center.y()))
        self._scene._create_node_item(node)
        self._status_label.setText(f"添加节点: {node_type}")
        _logger.info(f"双击添加节点: {node_type}")

    @property
    def engine(self) -> NodeEngine:
        return self._engine

    @property
    def scene(self) -> NodeEditorScene:
        return self._scene

    @property
    def view(self) -> NodeEditorView:
        return self._view
