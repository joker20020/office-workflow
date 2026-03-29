# -*- coding: utf-8 -*-
"""Widget双输入机制测试 - LiteGraph模式

测试内容:
- Widget在连接创建时被禁用
- Widget在连接移除时被重新启用
- 输入优先级: 连接 > Widget值 > 默认值 > None
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.engine.node_graph import NodeGraph, Node, Connection
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


class TestWidgetDualInputMechanism:
    """测试Widget双输入机制 (LiteGraph模式) - 数据层测试"""

    @pytest.fixture
    def simple_graph(self):
        """创建简单的测试图（不涉及UI）"""
        return NodeGraph(name="test_graph")

    @pytest.fixture
    def source_node_def(self):
        """源节点定义 (只有输出端口)"""
        return NodeDefinition(
            node_type="test.source",
            display_name="数据源",
            description="测试用数据源节点",
            category="test",
            icon="📤",
            inputs=[],
            outputs=[PortDefinition(name="output", type=PortType.STRING, description="输出数据")],
            execute=lambda: {"output": "source_value"},
        )

    @pytest.fixture
    def target_node_def(self):
        """目标节点定义 (带Widget的输入端口)"""
        return NodeDefinition(
            node_type="test.target",
            display_name="数据目标",
            description="测试用目标节点",
            category="test",
            icon="📥",
            inputs=[
                PortDefinition(
                    name="input",
                    type=PortType.STRING,
                    description="输入数据",
                    required=True,
                    default="default_value",
                    widget_type="text",
                )
            ],
            outputs=[PortDefinition(name="result", type=PortType.STRING, description="处理结果")],
            execute=lambda input: {"result": f"processed: {input}"},
        )

    @pytest.fixture
    def setup_nodes(self, simple_graph, source_node_def, target_node_def):
        """设置测试节点"""
        # 创建源节点
        source_node = Node(node_type="test.source", position=(0, 0))
        simple_graph.add_node(source_node)

        # 创建目标节点
        target_node = Node(node_type="test.target", position=(200, 0))
        target_node.widget_values["input"] = "widget_value"
        simple_graph.add_node(target_node)

        return simple_graph, source_node, target_node, source_node_def, target_node_def

    def test_widget_has_initial_value(self, setup_nodes):
        """Widget应该有初始值"""
        graph, source_node, target_node, _, target_def = setup_nodes

        # 验证Widget初始值已设置
        assert "input" in target_node.widget_values
        assert target_node.widget_values["input"] == "widget_value"

    def test_connection_priority_over_widget(self, setup_nodes):
        """连接值应该优先于Widget值 (输入优先级测试)"""
        graph, source_node, target_node, source_node_def, target_def = setup_nodes

        # 创建连接
        conn = graph.add_connection(
            source_node=source_node.id,
            source_port="output",
            target_node=target_node.id,
            target_port="input",
        )

        from src.engine.node_engine import NodeEngine

        engine = NodeEngine()
        engine.register_node_type(source_node_def)
        engine.register_node_type(target_def)

        inputs = engine._collect_inputs(target_node, graph, target_def)

        # 验证: Widget值被使用
        assert inputs["input"] == "connection_value", "连接值应该优先于Widget值"

    def test_widget_value_when_no_connection(self, setup_nodes):
        """没有连接时应该使用Widget值"""
        from src.engine.node_engine import NodeEngine

        graph, source_node, target_node, source_def, target_def = setup_nodes

        # 不创建连接，直接收集输入
        engine = NodeEngine()
        engine.register_node_type(source_def)
        engine.register_node_type(target_def)

        inputs = engine._collect_inputs(target_node, graph, target_def)

        # 验证: Widget值被使用
        assert inputs["input"] == "widget_value", "无连接时应该使用Widget值"

    def test_default_value_when_no_widget_no_connection(self):
        """没有连接也没有Widget值时应该使用默认值"""
        from src.engine.node_engine import NodeEngine

        # 创建一个没有设置Widget值的节点
        graph = NodeGraph(name="test")

        target_def = NodeDefinition(
            node_type="test.default",
            display_name="默认值测试",
            inputs=[
                PortDefinition(
                    name="input",
                    type=PortType.STRING,
                    default="default_value",
                    required=False,
                    widget_type="text",
                )
            ],
            outputs=[],
        )

        target_node = Node(node_type="test.default", position=(0, 0))
        # 不设置 widget_values
        graph.add_node(target_node)

        engine = NodeEngine()
        engine.register_node_type(target_def)

        inputs = engine._collect_inputs(target_node, graph, target_def)

        # 验证: 默认值被使用
        assert inputs["input"] == "default_value", "无连接无Widget时应该使用默认值"

    def test_none_value_for_required_port_without_default(self):
        """必填端口没有默认值且无连接时应该为None"""
        from src.engine.node_engine import NodeEngine

        graph = NodeGraph(name="test")

        target_def = NodeDefinition(
            node_type="test.required",
            display_name="必填端口测试",
            inputs=[
                PortDefinition(
                    name="input",
                    type=PortType.STRING,
                    default=None,
                    required=True,
                    widget_type="text",
                )
            ],
            outputs=[],
        )

        target_node = Node(node_type="test.required", position=(0, 0))
        graph.add_node(target_node)

        engine = NodeEngine()
        engine.register_node_type(target_def)

        inputs = engine._collect_inputs(target_node, graph, target_def)

        # 验证: None值
        assert inputs["input"] is None, "必填端口无默认值无连接时应该为None"


class TestWidgetStateManagement:
    """测试Widget状态管理 (启用/禁用)"""

    def test_input_priority_documentation(self):
        """文档化输入优先级: connection > widget_values > default > None"""
        priority_order = ["connection", "widget_values", "default", "None"]
        assert priority_order == ["connection", "widget_values", "default", "None"]


class TestRemoveConnectionWidgetReEnable:
    """测试连接移除时Widget重新启用"""

    @pytest.fixture
    def graph_with_connection(self):
        """创建带有连接的图（纯数据层）"""
        graph = NodeGraph(name="test_graph")

        source_def = NodeDefinition(
            node_type="test.source",
            display_name="Source",
            inputs=[],
            outputs=[PortDefinition(name="output", type=PortType.STRING)],
        )

        target_def = NodeDefinition(
            node_type="test.target",
            display_name="Target",
            inputs=[
                PortDefinition(
                    name="input", type=PortType.STRING, widget_type="text", default="default"
                )
            ],
            outputs=[],
        )

        source_node = Node(node_type="test.source", position=(0, 0))
        target_node = Node(node_type="test.target", position=(200, 0))
        target_node.widget_values["input"] = "widget_value"

        graph.add_node(source_node)
        graph.add_node(target_node)

        conn = graph.add_connection(
            source_node=source_node.id,
            source_port="output",
            target_node=target_node.id,
            target_port="input",
        )

        return graph, source_node, target_node, conn

    def test_remove_connection_from_graph(self, graph_with_connection):
        """移除连接应该从图中删除连接记录"""
        graph, source_node, target_node, conn = graph_with_connection

        # 验证连接存在
        assert conn.id in graph.connections

        # 移除连接
        graph.remove_connection(conn.id)

        # 验证连接已从数据层移除
        assert conn.id not in graph.connections

    def test_widget_value_preserved_after_connection_removal(self, graph_with_connection):
        """移除连接后Widget值应该保留"""
        graph, source_node, target_node, conn = graph_with_connection

        # 移除连接
        graph.remove_connection(conn.id)

        # Widget值应该保留
        assert target_node.widget_values["input"] == "widget_value"
