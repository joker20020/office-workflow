# -*- coding: utf-8 -*-
"""
节点引擎测试模块
==================

测试节点引擎的核心功能
"""

import pytest
import asyncio
from pathlib import Path

from src.core.node_engine import (
    NodeState,
    Port,
    Connection,
    Node,
    NodeGraph,
    NodeEngine,
)
from src.core.plugin_base import (
    ToolDefinition,
    PortDefinition,
    PortType,
)


class TestNodeState:
    """测试NodeState枚举"""

    def test_state_values(self):
        """测试状态值"""
        assert NodeState.IDLE.value == "idle"
        assert NodeState.RUNNING.value == "running"
        assert NodeState.SUCCESS.value == "success"
        assert NodeState.ERROR.value == "error"
        assert NodeState.SKIPPED.value == "skipped"


class TestPort:
    """测试Port类"""

    def test_create_port(self):
        """测试创建端口"""
        port = Port(
            id="port_1",
            name="input",
            type=PortType.STRING,
            node_id="node_1",
            is_input=True,
            value="test value",
        )

        assert port.id == "port_1"
        assert port.name == "input"
        assert port.type == PortType.STRING
        assert port.node_id == "node_1"
        assert port.is_input == True
        assert port.value == "test value"


class TestConnection:
    """测试Connection类"""

    def test_create_connection(self):
        """测试创建连接"""
        conn = Connection(
            id="conn_1",
            source_node="node_1",
            source_port="output",
            target_node="node_2",
            target_port="input",
        )

        assert conn.id == "conn_1"
        assert conn.source_node == "node_1"
        assert conn.source_port == "output"
        assert conn.target_node == "node_2"
        assert conn.target_port == "input"


class TestNode:
    """测试Node类"""

    def test_create_node(self):
        """测试创建节点"""
        node = Node(
            id="node_1",
            type="add_numbers",
            name="数字相加",
            position=(100, 100),
        )

        assert node.id == "node_1"
        assert node.type == "add_numbers"
        assert node.name == "数字相加"
        assert node.position == (100, 100)
        assert node.state == NodeState.IDLE

    def test_set_get_port_values(self):
        """测试设置和获取端口值"""
        node = Node(
            id="node_1",
            type="test",
            name="测试节点",
            position=(0, 0),
            inputs={
                "a": Port("p1", "a", PortType.INTEGER, "node_1", True, 10),
            },
            outputs={
                "result": Port("p2", "result", PortType.INTEGER, "node_1", False),
            },
        )

        node.set_input("a", 20)
        assert node.inputs["a"].value == 20

        node.outputs["result"].value = 30
        assert node.get_output("result") == 30

        assert node.get_output("nonexistent") is None


class TestNodeGraph:
    """测试NodeGraph类"""

    def test_create_graph(self):
        """测试创建节点图"""
        graph = NodeGraph(id="graph_1", name="测试图")

        assert graph.id == "graph_1"
        assert graph.name == "测试图"
        assert len(graph.nodes) == 0
        assert len(graph.connections) == 0

    def test_add_remove_nodes(self):
        """测试添加和移除节点"""
        graph = NodeGraph(id="graph_1", name="测试图")

        node1 = Node(id="n1", type="t1", name="节点1", position=(0, 0))
        node2 = Node(id="n2", type="t2", name="节点2", position=(100, 0))

        graph.add_node(node1)
        graph.add_node(node2)
        assert len(graph.nodes) == 2

        graph.remove_node("n1")
        assert len(graph.nodes) == 1
        assert "n1" not in graph.nodes

    def test_add_remove_connections(self):
        """测试添加和移除连接"""
        graph = NodeGraph(id="graph_1", name="测试图")

        node1 = Node(id="n1", type="t1", name="节点1", position=(0, 0))
        node2 = Node(id="n2", type="t2", name="节点2", position=(100, 0))

        graph.add_node(node1)
        graph.add_node(node2)

        conn = Connection(
            id="c1",
            source_node="n1",
            source_port="out",
            target_node="n2",
            target_port="in",
        )
        graph.add_connection(conn)
        assert len(graph.connections) == 1

        graph.remove_connection("c1")
        assert len(graph.connections) == 0

    def test_get_predecessors_successors(self):
        """测试获取前驱和后继节点"""
        graph = NodeGraph(id="graph_1", name="测试图")

        node1 = Node(id="n1", type="t1", name="节点1", position=(0, 0))
        node2 = Node(id="n2", type="t2", name="节点2", position=(100, 0))
        node3 = Node(id="n3", type="t3", name="节点3", position=(200, 0))

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)

        graph.add_connection(
            Connection(
                id="c1",
                source_node="n1",
                source_port="out",
                target_node="n2",
                target_port="in",
            )
        )
        graph.add_connection(
            Connection(
                id="c2",
                source_node="n2",
                source_port="out",
                target_node="n3",
                target_port="in",
            )
        )

        assert graph.get_predecessors("n2") == ["n1"]
        assert graph.get_predecessors("n3") == ["n2"]
        assert graph.get_predecessors("n1") == []

        assert graph.get_successors("n1") == ["n2"]
        assert graph.get_successors("n2") == ["n3"]
        assert graph.get_successors("n3") == []

    def test_topological_sort(self):
        """测试拓扑排序"""
        graph = NodeGraph(id="graph_1", name="测试图")

        node1 = Node(id="n1", type="t1", name="节点1", position=(0, 0))
        node2 = Node(id="n2", type="t2", name="节点2", position=(100, 0))
        node3 = Node(id="n3", type="t3", name="节点3", position=(200, 0))

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)

        graph.add_connection(
            Connection(
                id="c1",
                source_node="n1",
                source_port="out",
                target_node="n2",
                target_port="in",
            )
        )
        graph.add_connection(
            Connection(
                id="c2",
                source_node="n2",
                source_port="out",
                target_node="n3",
                target_port="in",
            )
        )

        order = graph.topological_sort()

        assert order.index("n1") < order.index("n2")
        assert order.index("n2") < order.index("n3")

    def test_topological_sort_with_cycle(self):
        """测试带环的图的拓扑排序"""
        graph = NodeGraph(id="graph_1", name="测试图")

        node1 = Node(id="n1", type="t1", name="节点1", position=(0, 0))
        node2 = Node(id="n2", type="t2", name="节点2", position=(100, 0))

        graph.add_node(node1)
        graph.add_node(node2)

        graph.add_connection(
            Connection(
                id="c1",
                source_node="n1",
                source_port="out",
                target_node="n2",
                target_port="in",
            )
        )
        graph.add_connection(
            Connection(
                id="c2",
                source_node="n2",
                source_port="out",
                target_node="n1",
                target_port="in",
            )
        )

        with pytest.raises(ValueError, match="Graph contains cycles"):
            graph.topological_sort()

    def test_serialization(self):
        """测试序列化和反序列化"""
        graph = NodeGraph(id="graph_1", name="测试图")

        node1 = Node(
            id="n1",
            type="add",
            name="相加",
            position=(0, 0),
            inputs={"a": Port("p1", "a", PortType.INTEGER, "n1", True, 10)},
        )

        graph.add_node(node1)

        data = graph.to_dict()
        assert data["id"] == "graph_1"
        assert data["name"] == "测试图"
        assert len(data["nodes"]) == 1

        restored = NodeGraph.from_dict(data)
        assert restored.id == graph.id
        assert restored.name == graph.name
        assert len(restored.nodes) == 1


class TestNodeEngine:
    """测试NodeEngine类"""

    def test_register_node_type(self):
        """测试注册节点类型"""
        engine = NodeEngine()

        tool = ToolDefinition(
            name="add",
            display_name="相加",
            description="两个数字相加",
            inputs=[
                PortDefinition("a", PortType.INTEGER, "第一个数字"),
                PortDefinition("b", PortType.INTEGER, "第二个数字"),
            ],
            outputs=[
                PortDefinition("result", PortType.INTEGER, "结果"),
            ],
            execute=lambda a, b: {"result": a + b},
        )

        engine.register_node_type(tool)
        assert "add" in engine.node_types

    def test_create_node(self):
        """测试创建节点"""
        engine = NodeEngine()

        tool = ToolDefinition(
            name="double",
            display_name="加倍",
            description="将数字加倍",
            inputs=[
                PortDefinition("x", PortType.INTEGER, "输入数字"),
            ],
            outputs=[
                PortDefinition("result", PortType.INTEGER, "结果"),
            ],
            execute=lambda x: {"result": x * 2},
        )

        engine.register_node_type(tool)

        node = engine.create_node("double", (50, 50))
        assert node is not None
        assert node.type == "double"
        assert node.name == "加倍"
        assert node.position == (50, 50)
        assert "x" in node.inputs
        assert "result" in node.outputs

    def test_create_graph(self):
        """测试创建图"""
        engine = NodeEngine()

        graph = engine.create_graph("测试图")
        assert graph.name == "测试图"
        assert graph.id in engine.graphs

    def test_execute_node(self):
        """测试执行节点"""
        engine = NodeEngine()

        tool = ToolDefinition(
            name="square",
            display_name="平方",
            description="计算平方",
            inputs=[
                PortDefinition("x", PortType.INTEGER, "输入数字"),
            ],
            outputs=[
                PortDefinition("result", PortType.INTEGER, "结果"),
            ],
            execute=lambda x: {"result": x * x},
        )

        engine.register_node_type(tool)

        node = engine.create_node("square")
        assert node is not None
        node.set_input("x", 5)

        graph = engine.create_graph("测试")
        graph.add_node(node)

        success = asyncio.run(engine.execute_node(node, graph))
        assert success
        assert node.state == NodeState.SUCCESS
        assert node.get_output("result") == 25

    def test_execute_graph(self):
        """测试执行整个图"""
        engine = NodeEngine()

        engine.register_node_type(
            ToolDefinition(
                name="double",
                display_name="加倍",
                description="加倍",
                inputs=[PortDefinition("x", PortType.INTEGER, "数字")],
                outputs=[PortDefinition("result", PortType.INTEGER, "结果")],
                execute=lambda x: {"result": x * 2},
            )
        )

        engine.register_node_type(
            ToolDefinition(
                name="add_ten",
                display_name="加十",
                description="加十",
                inputs=[PortDefinition("x", PortType.INTEGER, "数字")],
                outputs=[PortDefinition("result", PortType.INTEGER, "结果")],
                execute=lambda x: {"result": x + 10},
            )
        )

        graph = engine.create_graph("流水线")

        node1 = engine.create_node("double", (0, 0))
        node2 = engine.create_node("add_ten", (200, 0))
        assert node1 is not None
        assert node2 is not None

        node1.set_input("x", 5)

        graph.add_node(node1)
        graph.add_node(node2)

        graph.add_connection(
            Connection(
                id="c1",
                source_node=node1.id,
                source_port="result",
                target_node=node2.id,
                target_port="x",
            )
        )

        success = asyncio.run(engine.execute_graph(graph))
        assert success
        assert node1.get_output("result") == 10
        assert node2.get_output("result") == 20

    def test_get_available_nodes(self):
        """测试获取可用节点列表"""
        engine = NodeEngine()

        tool = ToolDefinition(
            name="test",
            display_name="测试",
            description="测试",
            category="测试分类",
            icon="🔧",
            inputs=[PortDefinition("input_text", PortType.STRING, "输入")],
            outputs=[PortDefinition("output_text", PortType.STRING, "输出")],
            execute=lambda input_text: {"output_text": input_text},
        )

        engine.register_node_type(tool)

        nodes = engine.get_available_nodes()
        assert len(nodes) == 1
        assert nodes[0]["type"] == "test"
        assert nodes[0]["name"] == "测试"
        assert nodes[0]["category"] == "测试分类"
