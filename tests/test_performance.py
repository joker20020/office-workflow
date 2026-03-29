# -*- coding: utf-8 -*-
"""性能优化测试"""

import pytest
import time
from unittest.mock import Mock

from typing import Callable

from src.engine.node_engine import NodeEngine, ExecutionResult, ExecutionCache
from src.engine.node_graph import NodeGraph, Node
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


class TestExecutionLayers:
    """测试执行层级划分"""

    def test_single_node_single_layer(self):
        """单个节点应该在单层中"""
        engine = NodeEngine()
        graph = NodeGraph(name="test")

        node = Node(node_type="test", position=(0, 0))
        graph.add_node(node)

        layers = engine._get_execution_layers(graph)
        assert len(layers) == 1
        assert len(layers[0]) == 1

    def test_sequential_chain_creates_layers(self):
        """顺序依赖链应该创建多个层级"""
        engine = NodeEngine()
        graph = NodeGraph(name="test")

        node_a = Node(node_type="a", position=(0, 0))
        node_b = Node(node_type="b", position=(100, 0))
        node_c = Node(node_type="c", position=(200, 0))

        graph.add_node(node_a)
        graph.add_node(node_b)
        graph.add_node(node_c)

        graph.add_connection(node_a.id, "out", node_b.id, "in")
        graph.add_connection(node_b.id, "out", node_c.id, "in")

        layers = engine._get_execution_layers(graph)

        assert len(layers) == 3
        assert len(layers[0]) == 1
        assert len(layers[1]) == 1
        assert len(layers[2]) == 1

    def test_parallel_nodes_same_layer(self):
        """无依赖的节点应该在同一层"""
        engine = NodeEngine()
        graph = NodeGraph(name="test")

        node_a = Node(node_type="a", position=(0, 0))
        node_b = Node(node_type="b", position=(100, 0))

        graph.add_node(node_a)
        graph.add_node(node_b)

        layers = engine._get_execution_layers(graph)

        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_empty_graph_empty_layers(self):
        """空图应该返回空列表"""
        engine = NodeEngine()
        graph = NodeGraph(name="test")

        layers = engine._get_execution_layers(graph)
        assert layers == []


class TestExecutionCache:
    """测试执行结果缓存"""

    def test_cache_hit_returns_result(self):
        """缓存命中应该返回缓存的结果"""
        cache = ExecutionCache()

        result = ExecutionResult(success=True, outputs={"value": 42})
        cache.set("test_type", {"input": "data"}, result)

        cached = cache.get("test_type", {"input": "data"})
        assert cached is not None
        assert cached.success
        assert cached.outputs == {"value": 42}

    def test_cache_miss_returns_none(self):
        """缓存未命中应该返回None"""
        cache = ExecutionCache()

        cached = cache.get("test_type", {"input": "data"})
        assert cached is None

    def test_different_inputs_different_keys(self):
        """不同输入应该生成不同的缓存键"""
        cache = ExecutionCache()

        result1 = ExecutionResult(success=True, outputs={"value": 1})
        result2 = ExecutionResult(success=False, error="failed")

        cache.set("test_type", {"input": "a"}, result1)
        cache.set("test_type", {"input": "b"}, result2)

        assert cache.get("test_type", {"input": "a"}) == result1
        assert cache.get("test_type", {"input": "b"}) == result2

    def test_cache_invalidation(self):
        """缓存失效应该清除相关缓存"""
        cache = ExecutionCache()

        result = ExecutionResult(success=True, outputs={"value": 1})
        cache.set("test_type", {"input": "a"}, result)
        cache.set("test_type", {"input": "b"}, result)

        cache.invalidate("test_type")

        assert cache.get("test_type", {"input": "a"}) is None
        assert cache.get("test_type", {"input": "b"}) is None

    def test_cache_clear(self):
        """清空缓存应该清除所有条目"""
        cache = ExecutionCache()

        result = ExecutionResult(success=True, outputs={"value": 1})
        cache.set("test_type", {"input": "a"}, result)

        cache.clear()

        assert cache.get("test_type", {"input": "a"}) is None
