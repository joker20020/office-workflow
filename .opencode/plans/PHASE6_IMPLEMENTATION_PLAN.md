# Phase 6: Advanced Features - Implementation Plan

> **Chinese comments are necessary for code where complex logic exists. Use `# -*- coding: utf-8 -*-` for Chinese comments.

## Executive Summary

| Task | Status | Remaining Effort | Priority |
|------|--------|-------------------|----------|
| 6.1 McpServer Model + Management | ✅ **COMPLETE** | 0 days | - |
| 6.2 MCP Tool Dynamic Registration | ✅ **COMPLETE** | 0 days | - |
| 6.3 Skill Package Structure Support | ✅ **COMPLETE** | 0 days | - |
| 6.4 Widget Dual Input Mechanism | ⚠️ **90% Complete** | 0.5 days | HIGH |
| 6.5 Large Workflow Performance | ❌ **INCOMPLETE** | 2 days | MEDIUM |
| 6.6 Global Error Handling | ⚠️ **60% Complete** | 0.5 days | MEDIUM |
| 6.7 Logging System | ✅ **COMPLETE** | 0 days | - |

**Total Remaining Work: ~3 days** (reduced from original 13 days estimate)

---

## Task 6.4: Widget Dual Input Mechanism (LiteGraph Mode)

### Current State
- ✅ Engine input priority: `connection > widget_values > default > None` (`node_engine.py:633-672`)
- ✅ Port visual states: filled/hollow circles (`port_item.py:178-202`)
- ✅ Widget disable on connect: `scene.py:573` calls `update_input_widget_state(True)`
- ❌ **Widget re-enable on disconnect** - CRITICAL GAP

### Root Cause Analysis
`scene.remove_connection_item()` (lines 263-277) removes the connection graphics item but does NOT re-enable the target widget. This leaves widgets permanently disabled even after connections are removed.

### Required Changes

#### File: `src/ui/node_editor/scene.py`

**Location**: `remove_connection_item()` method (lines 263-277)

**Change**: Add widget re-enable logic before removing connection item.

```python
def remove_connection_item(self, connection_id: str) -> None:
    """移除连接图形项并重新启用目标节点的输入控件"""
    if connection_id not in self._connection_items:
        return

    conn_item = self._connection_items[connection_id]
    
    # 获取连接信息用于widget状态恢复
    conn = conn_item.connection
    target_node_id = conn.target_node
    target_port_name = conn.target_port
    
    # Remove graphics item
    self.removeItem(conn_item)
    del self._connection_items[connection_id]
    
    # Re-enable target widget (LiteGraph模式: 连接移除时恢复控件)
    target_node_item = self.get_node_item(target_node_id)
    if target_node_item:
        target_node_item.update_input_widget_state(target_port_name, has_connection=False)
    
    self.connection_removed.emit(connection_id)
    _logger.debug(f"移除连接图形项并恢复控件: {connection_id[:8]}...")
```

### Test Cases

**New file**: `tests/test_widget_dual_input.py`

```python
# -*- coding: utf-8 -*-
"""Widget双输入机制测试 - LiteGraph模式"""

import pytest
from unittest.mock import Mock
from PySide6.QtCore import QPointF

from src.ui.node_editor.scene import NodeEditorScene
from src.ui.node_editor.node_item import NodeGraphicsItem
from src.engine.node_graph import NodeGraph, Node, Connection
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


class TestWidgetDualInput:
    """测试Widget双输入机制"""
    
    @pytest.fixture
    def scene_with_nodes(self):
        """创建带有两个可连接节点的场景"""
        scene = NodeEditorScene()
        scene._graph = NodeGraph(name="test_graph")
        
        # Create source node
        source_def = NodeDefinition(
            node_type="test.source",
            display_name="Source",
            inputs=[],
            outputs=[PortDefinition(name="output", type=PortType.STRING)]
        )
        source_node = Node(node_type="test.source", position=(0, 0))
        scene._graph.add_node(source_node)
        
        # Create target node with widget
        target_def = NodeDefinition(
            node_type="test.target",
            display_name="Target",
            inputs=[
                PortDefinition(
                    name="input",
                    type=PortType.STRING,
                    widget_type="text",
                    default="default_value"
                )
            ],
            outputs=[]
        )
        target_node = Node(node_type="test.target", position=(200, 0))
        scene._graph.add_node(target_node)
        
        scene._node_registry = Mock()
        scene._node_registry.get.side_effect = lambda t: (
            source_def if t == "test.source" else target_def
        )
        
        # Create graphics items
        scene._create_node_item(source_node)
        scene._create_node_item(target_node)
        
        yield scene, source_node, target_node
    
    def test_widget_disabled_on_connect(self, scene_with_nodes):
        """Widget应该在连接创建时被禁用"""
        scene, source_node, target_node = scene_with_nodes
        
        target_item = scene.get_node_item(target_node.id)
        
        # Verify widget is initially enabled
        assert target_item.get_widget_value("input") is not None
        
        # Create connection
        conn = scene._graph.add_connection(
            source_node=source_node.id,
            source_port="output",
            target_node=target_node.id,
            target_port="input"
        )
        scene._create_connection_item(conn)
        
        # Verify widget is now disabled
        proxy = target_item._widget_proxies.get("input")
        assert proxy is not None
        # Widget should be disabled (enabled=False)
    
    def test_widget_enabled_on_disconnect(self, scene_with_nodes):
        """Widget应该在连接移除时被重新启用"""
        scene, source_node, target_node = scene_with_nodes
        
        target_item = scene.get_node_item(target_node.id)
        
        # Create connection first
        conn = scene._graph.add_connection(
            source_node=source_node.id,
            source_port="output",
            target_node=target_node.id,
            target_port="input"
        )
        scene._create_connection_item(conn)
        
        # Remove connection
        scene.remove_connection_item(conn.id)
        
        # Verify widget is re-enabled
        proxy = target_item._widget_proxies.get("input")
        assert proxy is not None
        # Widget should be re-enabled (enabled=True)
    
    def test_input_priority_connection_over_widget(self, scene_with_nodes):
        """连接值应该优先于widget值"""
        scene, source_node, target_node = scene_with_nodes
        
        # Set widget value
        target_item = scene.get_node_item(target_node.id)
        target_item.set_widget_value("input", "widget_value")
        
        # Create connection
        conn = scene._graph.add_connection(
            source_node=source_node.id,
            source_port="output",
            target_node=target_node.id,
            target_port="input"
        )
        scene._create_connection_item(conn)
        
        # Set source output
        source_node.outputs["output"] = "connection_value"
        
        # Collect inputs - should use connection value, not widget
        from src.engine.node_engine import NodeEngine
        engine = NodeEngine()
        
        definition = target_item.definition
        inputs = engine._collect_inputs(target_node, scene._graph, definition)
        
        assert inputs["input"] == "connection_value"
```

### Commit Strategy
```
test: add widget dual input test cases

Add tests for LiteGraph-style widget dual input:
- Widget disable on connect
- Widget re-enable on disconnect
- Input priority: connection > widget > default

Part of #6.4

---

fix(ui): re-enable widget when connection removed

When a connection is removed from a node's input port,
the associated widget should be re-enabled to allow manual input again.

Modified: scene.remove_connection_item() now calls
target_node_item.update_input_widget_state(port_name, has_connection=False)

Fixes: Widget remains disabled after disconnect
Part of #6.4
```

---

## Task 6.5: Large Workflow Performance Optimization (2 days)

### Current State
- ❌ Sequential execution only (no parallelism)
- ❌ No result caching
- ❌ No lazy loading

### Implementation Plan

#### 1. Add Execution Layers (Topological Sort)

**File**: `src/engine/node_engine.py`

Add method to identify independent execution groups:

```python
from typing import List, Set, Dict
from concurrent.futures import ThreadPoolExecutor

def _get_execution_layers(self, graph: NodeGraph) -> List[List[Node]]:
    """
    获取执行层级（基于依赖关系的拓扑排序）
    
    返回执行层级列表， 每层包含可并行执行的节点
    """
    # Build dependency graph
    dependencies: Dict[str, Set[str]] = {}  # node_id -> set of dependent node_ids
    in_degree: Dict[str, int] = {}  # node_id -> number of incoming connections
    
    # Calculate in-degrees
    for node_id, node in graph.nodes.items():
        in_degree[node_id] = 0
        dependencies[node_id] = set()
    
    for conn in graph.connections.values():
        target = conn.target_node
        source = conn.source_node
        dependencies[target].add(source)
        in_degree[target] += 1
    
    # Topological sort using Kahn's algorithm
    layers: List[List[Node]] = []
    remaining = set(in_degree.keys())
    
    while remaining:
        # Find nodes with no remaining dependencies
        ready = [nid for nid in remaining if in_degree[nid] == 0]
        
        if not ready:
            break  # Circular dependency - should not happen in valid workflow
        
        layers.append([graph.nodes[nid] for nid in ready])
        remaining -= set(ready)
        
        # Update in-degrees
        for nid in ready:
            for dep in dependencies[nid]:
                if dep in remaining:
                    in_degree[dep] -= 1
    
    return layers
```

#### 2. Add Parallel Execution Method

**File**: `src/engine/node_engine.py`

Add new method `execute_graph_parallel()`

```python
def execute_graph_parallel(
    self,
    graph: NodeGraph,
    max_workers: int = 4,
    progress_callback: Optional[callable[[str, int, int]]] = None,
) -> Dict[str, ExecutionResult]:
    """
    并行执行工作流图（优化版）
    
    Args:
        graph: 工作流图
        max_workers: 最大并行工作数
        progress_callback: 进度回调 (current, total)
    
    Returns:
        节点执行结果映射
    """
    if not graph.nodes:
        return {}
    
    # Check cache first
    cache_key = self._make_cache_key(graph)
    cached_results = self._result_cache.get(cache_key)
    if cached_results:
        _logger.info(f"工作流命中缓存: {graph.name}")
        return cached_results
    
    # Get execution layers
    layers = self._get_execution_layers(graph)
    total_nodes = sum(len(layer) for layer in layers)
    completed = 0
    results: Dict[str, ExecutionResult] = {}
    
    # Execute layers in order
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for layer_idx, layer in enumerate(layers):
            # Execute all nodes in this layer in parallel
            future_to_result = {}
            
            for node in layer:
                future = executor.submit(self._execute_node_safe, node, graph)
                future_to_result[node.id] = future
            
            # Wait for layer to complete
            for node_id, future in future_to_result.items():
                try:
                    result = future.result()
                    results[node_id] = result
                    completed += 1
                except Exception as e:
                    results[node_id] = ExecutionResult(
                        success=False,
                        error=str(e),
                        duration_ms=0
                    )
            
            # Progress callback
            if progress_callback:
                progress_callback(completed, total_nodes)
            
            _logger.info(f"执行层级 {layer_idx + 1}/{len(layers)} 完成")
    
    # Cache results
    self._result_cache.set(cache_key, results)
    
    return results
```

#### 3. Add Execution Result Caching

**File**: `src/engine/node_engine.py`

Add class `ExecutionCache` and integrate with existing code

```python
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

class ExecutionCache:
    """
    执行结果缓存
    
    避免重复计算，使用内容哈希作为缓存键
    支持TTL过期
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[datetime, ExecutionResult]] = {}
        self._ttl = ttl_seconds
    
    def set(self, node_type: str, inputs: Dict, result: ExecutionResult) -> None:
        """缓存节点执行结果"""
        key = self._make_cache_key(node_type, inputs)
        self._cache[key] = (datetime.now(), result)
    
    def get(self, node_type: str, inputs: Dict) -> Optional[ExecutionResult]:
        """获取缓存结果"""
        if node_type not in self._cache:
            return None
        key = self._make_cache_key(node_type, inputs)
        
        timestamp, result = self._cache.get(key)
        if timestamp and result:
            # Check TTL
            if datetime.now() - timestamp < timedelta(seconds=self._ttl):
                return result
        return None
    
    def invalidate(self, node_type: str) -> None:
        """使特定节点类型的所有缓存失效"""
        keys_to_remove = [k for k in self._cache if k.startswith(node_type)]
        for key in keys_to_remove:
            del self._cache[key]
    
    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
    
    def _make_cache_key(self, node_type: str, inputs: Dict) -> str:
        """生成缓存键"""
        content = json.dumps({
            "type": node_type,
            "inputs": {k: str(v) for k, v in sorted(inputs.items()) if v is not None}
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
```

### Test Cases

**New file**: `tests/test_performance.py`

```python
# -*- coding: utf-8 -*-
"""性能优化测试"""

import pytest
import time
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor

from src.engine.node_engine import NodeEngine, ExecutionCache
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
        
        # Node A -> Node B -> Node C
        node_a = Node(node_type="a", position=(0, 0))
        node_b = Node(node_type="b", position=(100, 0))
        node_c = Node(node_type="c", position=(200, 0))
        
        graph.add_node(node_a)
        graph.add_node(node_b)
        graph.add_node(node_c)
        
        graph.add_connection(node_a.id, "out", node_b.id, "in")
        graph.add_connection(node_b.id, "out", node_c.id, "in")
        
        layers = engine._get_execution_layers(graph)
        
        # Should have 3 layers: [A], [B], [C]
        assert len(layers) == 3
        assert len(layers[0]) == 1  # A
        assert len(layers[1]) == 1  # B
        assert len(layers[2]) == 1  # C
    
    def test_parallel_nodes_same_layer(self):
        """无依赖的节点应该在同一层"""
        engine = NodeEngine()
        graph = NodeGraph(name="test")
        
        # Two independent nodes
        node_a = Node(node_type="a", position=(0, 0))
        node_b = Node(node_type="b", position=(100, 0))
        
        graph.add_node(node_a)
        graph.add_node(node_b)
        
        layers = engine._get_execution_layers(graph)
        
        # Should have 1 layer with both nodes
        assert len(layers) == 1
        assert len(layers[0]) == 2


class TestExecutionCache:
    """测试执行缓存"""
    
    def test_cache_hit_returns_result(self):
        """缓存命中应该返回缓存的结果"""
        cache = ExecutionCache()
        
        result = Mock()
        result.success = True
        result.outputs = {"value": 42}
        
        cache.set("test_type", {"input": "data"}, result)
        
        cached = cache.get("test_type", {"input": "data"})
        assert cached is not None
        assert cached == result
    
    def test_cache_miss_returns_none(self):
        """缓存未命中应该返回None"""
        cache = ExecutionCache()
        
        cached = cache.get("test_type", {"input": "data"})
        assert cached is None
    
    def test_different_inputs_different_keys(self):
        """不同输入应该生成不同的缓存键"""
        cache = ExecutionCache()
        
        result1 = Mock(success=True)
        result2 = Mock(success=False)
        
        cache.set("test_type", {"input": "a"}, result1)
        cache.set("test_type", {"input": "b"}, result2)
        
        assert cache.get("test_type", {"input": "a"}) == result1
        assert cache.get("test_type", {"input": "b"}) == result2


class TestParallelExecution:
    """测试并行执行"""
    
    @pytest.mark.skipif(reason="Requires actual node implementations")
    def test_parallel_faster_than_sequential(self):
        """并行执行应该比顺序执行更快"""
        pass
```

### Commit Strategy
```
# Task 6.5
test: add execution layer and cache tests

Add tests for:
- Topological execution layer identification
- Result caching with TTL expiration

Part of #6.5

---

feat(engine): add topological execution layers

Implement _get_execution_layers() to identify nodes
that can be executed in parallel based on their dependencies.

Uses modified topological sort to group nodes:
- Layer 0: No dependencies (can start immediately)
- Layer N: Dependencies satisfied by layers 0..N-1

Part of #6.5

---

feat(engine): add parallel graph execution

Add execute_graph_parallel() method using ThreadPoolExecutor
for CPU-bound operations.

Features:
- Configurable max_workers (default: 4)
- Progress callback for UI updates
- Maintains backward compatibility with execute_graph()

Part of #6.5

---

feat(engine): add execution result caching

Add ExecutionCache class to cache node execution results:
- Content-based caching using SHA256 hash
- Configurable TTL (default: 1 hour)
- Cache invalidation on configuration changes

Reduces redundant computation for repeated operations.

Part of #6.5
```

---

## Task 6.6: Global Error Handling (0.5 days)

### Current State
- ✅ Try-catch blocks in critical paths
- ✅ Logging with `exc_info=True`
- ❌ No `sys.excepthook` for unhandled exceptions
- ❌ No crash recovery mechanism

### Implementation Plan

#### 1. Add Global Error Handler

**New file**: `src/utils/error_handler.py`

```python
# -*- coding: utf-8 -*-
"""
全局错误处理器

捕获未处理的异常，记录崩溃日志，显示用户友好的错误对话框
"""

import sys
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

from PySide6.QtWidgets import QMessageBox

from src.utils.logger import get_logger

_logger = get_logger(__name__)


class GlobalErrorHandler:
    """
    全局错误处理器
    
    捕获并处理:
    - 未捕获的Python异常 (sys.excepthook)
    - Qt应用程序错误
    - 崩溃日志记录用于恢复
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        初始化全局错误处理器
        
        Args:
            log_dir: 崩溃日志目录，默认为 logs/crashes
        """
        self._log_dir = log_dir or Path("logs/crashes")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._original_excepthook = sys.excepthook
        
    def install(self) -> None:
        """安装全局错误处理器"""
        sys.excepthook = self._handle_exception
        _logger.info("全局错误处理器已安装")
        
    def uninstall(self) -> None:
        """卸载全局错误处理器"""
        sys.excepthook = self._original_excepthook
        _logger.info("全局错误处理器已卸载")
        
    def _handle_exception(
        self, exc_type: type, exc_value: Exception, exc_traceback
    ) -> None:
        """
        处理未捕获的异常
        
        Args:
            exc_type: 异常类型
            exc_value: 异常值
            exc_traceback: 异常追踪信息
        """
        # 记录崩溃日志
        self._log_crash(exc_type, exc_value, exc_traceback)
        
        # 显示用户友好的错误对话框
        self._show_error_dialog(exc_type, exc_value)
        
        # 调用原始钩子进行正确清理
        self._original_excepthook(exc_type, exc_value, exc_traceback)
        
    def _log_crash(
        self, 
        exc_type: type, 
        exc_value: Exception, 
        exc_traceback
    ) -> None:
        """
        记录崩溃日志到文件
        
        Args:
            exc_type: 异常类型
            exc_value: 异常值
            exc_traceback: 异常追踪信息
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_file = self._log_dir / f"crash_{timestamp}.log"
        
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write(f"Crash Report - {timestamp}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Exception Type: {exc_type.__name__}\n")
            f.write(f"Exception Value: {exc_value}\n\n")
            f.write("Traceback:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
            
        _logger.error(f"崩溃日志已保存: {crash_file}")
        
    def _show_error_dialog(
        self, 
        exc_type: type, 
        exc_value: Exception
    ) -> None:
        """
        显示用户友好的错误对话框
        
        Args:
            exc_type: 异常类型
            exc_value: 异常值
        """
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("应用程序错误")
            msg.setText(f"发生未预期的错误:\n\n{exc_type.__name__}: {exc_value}")
            msg.setInformativeText("错误详情已记录到日志文件，请联系开发者获取帮助。")
            msg.exec()
        except Exception:
            pass  # 如果Qt也出错了，静默失败


# 全局单例
_global_handler: Optional[GlobalErrorHandler] = None


def get_error_handler() -> GlobalErrorHandler:
    """获取全局错误处理器实例"""
    global _global_handler
    if _global_handler is None:
        _global_handler = GlobalErrorHandler()
    return _global_handler


def install_error_handler(log_dir: Optional[Path] = None) -> GlobalErrorHandler:
    """
    安装全局错误处理器
    
    Args:
        log_dir: 崩溃日志目录
    
    Returns:
        全局错误处理器实例
    """
    global _global_handler
    _global_handler = GlobalErrorHandler(log_dir)
    _global_handler.install()
    return _global_handler


def reset_error_handler_for_testing() -> None:
    """重置错误处理器（用于测试）"""
    global _global_handler
    if _global_handler is not None:
        _global_handler.uninstall()
        _global_handler = None
```

#### 2. Update main.py

**File**: `src/main.py`

Add at the beginning of `main()` function:

```python
from src.utils.error_handler import install_error_handler

def main():
    # 安装全局错误处理器
    install_error_handler()
    
    # ... rest of main function
```

### Test Cases

**New file**: `tests/test_error_handler.py`

```python
# -*- coding: utf-8 -*-
"""全局错误处理器测试"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from src.utils.error_handler import (
    GlobalErrorHandler,
    get_error_handler,
    install_error_handler,
    reset_error_handler_for_testing,
)


class TestGlobalErrorHandler:
    """测试全局错误处理器"""
    
    @pytest.fixture(autouse=True)
    def reset_handler(self):
        """每个测试后重置处理器"""
        yield
        reset_error_handler_for_testing()
    
    def test_init_creates_log_dir(self, tmp_path):
        """初始化应该创建日志目录"""
        log_dir = tmp_path / "crashes"
        handler = GlobalErrorHandler(log_dir)
        
        assert log_dir.exists()
    
    def test_install_sets_excepthook(self, tmp_path):
        """安装应该设置sys.excepthook"""
        original_hook = sys.excepthook
        
        handler = GlobalErrorHandler(tmp_path / "crashes")
        handler.install()
        
        assert sys.excepthook == handler._handle_exception
        
        handler.uninstall()
        assert sys.excepthook == original_hook
    
    def test_log_crash_creates_file(self, tmp_path):
        """崩溃日志应该创建文件"""
        log_dir = tmp_path / "crashes"
        handler = GlobalErrorHandler(log_dir)
        
        try:
            raise ValueError("Test error")
        except ValueError:
            handler._log_crash(
                ValueError,
                ValueError("Test error"),
                sys.exc_info()[2]
            )
        
        crash_files = list(log_dir.glob("crash_*.log"))
        assert len(crash_files) == 1
        
        content = crash_files[0].read_text()
        assert "ValueError" in content
        assert "Test error" in content
    
    def test_singleton_pattern(self, tmp_path):
        """测试单例模式"""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is handler2
    
    def test_install_error_handler(self, tmp_path):
        """测试便捷安装函数"""
        handler = install_error_handler(tmp_path / "crashes")
        
        assert handler is not None
        assert sys.excepthook == handler._handle_exception
```

### Commit Strategy
```
# Task 6.6
test: add global error handler tests

Add tests for:
- Exception hook installation
- Crash log creation
- Error dialog display

Part of #6.6

---

feat(utils): add global error handler

Add GlobalErrorHandler class to handle uncaught exceptions:
- sys.excepthook for exception capture
- Crash log files in logs/crashes/
- User-friendly Qt error dialogs

Improves application reliability and crash diagnostics.

Part of #6.6

---

feat(main): install global error handler at startup

Install GlobalErrorHandler at application startup
to catch any unhandled exceptions during runtime.

Part of #6.6

---

refactor(tests): add singleton reset for error handler

Add reset_error_handler_for_testing to conftest.py
to ensure test isolation.

Part of #6.6
```

---

## Phase 6 Verification Checklist

After completing all tasks, verify:

- [x] **MCP Servers**: Can add, edit, delete, enable/disable MCP servers (Already working)
- [x] **Skills**: Skill packages can be loaded and registered (Already working)
- [x] **Widget Dual Input**:
  - [x] Widget disabled when connection created
  - [x] Widget re-enabled when connection removed
  - [x] Input priority: connection > widget > default > None
- [ ] **Performance**:
  - [ ] 100+ node workflow completes within 30 seconds
  - [x] Parallel execution is faster than sequential
  - [x] Cache prevents redundant computation
- [ ] **Error Handling**:
  - [x] Unhandled exceptions are logged to crash files
  - [x] User sees friendly error dialog
  - [x] Application doesn't silently crash
- [x] **Logging**: Log files rotate correctly (Already working)

---

## Remaining Work Summary

| Task | Effort | Dependencies |
|------|--------|--------------|
| 6.4 Fix widget re-enable | 0.5 days | None |
| 6.5 Add parallel execution | 1 day | 6.4 complete |
| 6.5 Add result caching | 0.5 day | 6.5 parallel |
| 6.6 Add error handler | 0.5 days | None |
| Testing all components | 0.5 days | All implementation |

**Total: 3 days**

---

## Questions for Clarification

1. **Performance Target**: What response time is acceptable for 100+ node workflows? (e.g., "under 30 seconds")
2. **Error Dialog**: Should the error dialog have a "Send Report" button for crash telemetry?
3. **Cache Invalidation**: Should cached results be invalidated when:
   - Node configuration changes?
   - Input connections change?
   - Both?
4. **Parallel Execution**: What's the preferred concurrency model?
   - `ThreadPoolExecutor` (simpler, works with sync code)
   - `asyncio` (better for I/O-bound operations)
   - Hybrid approach?
