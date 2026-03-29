# -*- coding: utf-8 -*-
"""
节点执行引擎模块

提供工作流执行能力：
- 节点类型注册管理（NodeRegistry）
- 单节点执行
- 整图执行（拓扑排序 + 顺序执行）
- 执行状态回调和事件发布

核心执行流程：
1. 获取拓扑排序后的执行顺序
2. 对每个节点：
   a. 收集输入值（连接 > 控件值 > 默认值）
   b. 验证输入
   c. 调用执行函数
   d. 存储输出
   e. 更新状态

使用方式（推荐使用单例模式）：
    from src.engine.node_engine import get_node_engine, init_node_engine

    # 初始化全局引擎
    engine = init_node_engine(event_bus=event_bus)

    # 或获取已初始化的引擎
    engine = get_node_engine()

    # 注册节点类型
    engine.register_node_type(text_join_definition)

    # 执行工作流
    results = engine.execute_graph(graph)

    # 关闭
    shutdown_node_engine()
"""

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import json
import threading
import time

from src.core.event_bus import EventBus, EventType
from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.engine.node_graph import (
    Connection,
    CyclicDependencyError,
    Node,
    NodeGraph,
    NodeState,
)
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class NodeRegistry:
    """
    节点类型注册表

    管理所有已注册的节点定义，支持：
    - 注册/注销节点类型
    - 按类型查询
    - 按分类筛选
    - 获取所有节点信息（供Agent使用）

    Example:
        >>> registry = NodeRegistry()
        >>> registry.register(text_join_def)
        >>> defn = registry.get("text.join")
        >>> all_text_nodes = registry.get_by_category("text")
    """

    def __init__(self):
        """初始化节点注册表"""
        # 节点类型 -> 节点定义
        self._definitions: Dict[str, NodeDefinition] = {}

        _logger.debug("节点注册表初始化完成")

    def register(self, definition: NodeDefinition) -> None:
        """
        注册节点定义

        Args:
            definition: 节点定义

        Note:
            如果节点类型已存在，会覆盖旧定义

        Example:
            >>> registry.register(NodeDefinition(
            ...     node_type="text.join",
            ...     display_name="文本拼接",
            ... ))
        """
        if definition.node_type in self._definitions:
            _logger.warning(f"覆盖已存在的节点类型: {definition.node_type}")

        self._definitions[definition.node_type] = definition
        _logger.info(f"注册节点类型: {definition.node_type} '{definition.display_name}'")

    def unregister(self, node_type: str) -> bool:
        """
        注销节点定义

        Args:
            node_type: 节点类型标识

        Returns:
            是否成功注销（如果类型不存在则返回 False）
        """
        if node_type in self._definitions:
            del self._definitions[node_type]
            _logger.info(f"注销节点类型: {node_type}")
            return True
        return False

    def get(self, node_type: str) -> Optional[NodeDefinition]:
        """
        获取节点定义

        Args:
            node_type: 节点类型标识

        Returns:
            节点定义，如果不存在则返回 None
        """
        return self._definitions.get(node_type)

    def get_all(self) -> List[NodeDefinition]:
        """
        获取所有节点定义

        Returns:
            节点定义列表
        """
        return list(self._definitions.values())

    def get_by_category(self, category: str) -> List[NodeDefinition]:
        """
        按分类获取节点定义

        Args:
            category: 分类名称

        Returns:
            该分类下的节点定义列表
        """
        return [defn for defn in self._definitions.values() if defn.category == category]

    def get_categories(self) -> Set[str]:
        """
        获取所有分类

        Returns:
            分类名称集合
        """
        return {defn.category for defn in self._definitions.values()}

    def get_all_for_agent(self) -> List[Dict[str, Any]]:
        """
        获取所有节点信息，格式化为Agent可读的格式

        Returns:
            节点信息字典列表，每个字典包含：
            - node_type: 节点类型
            - display_name: 显示名称
            - description: 描述
            - category: 分类
            - icon: 图标
            - inputs: 输入端口列表
            - outputs: 输出端口列表

        Example:
            >>> nodes = registry.get_all_for_agent()
            >>> for node in nodes:
            ...     print(f"{node['node_type']}: {node['description']}")
        """
        return [defn.to_dict() for defn in self._definitions.values()]


@dataclass
class ExecutionResult:
    """
    执行结果

    封装单个节点的执行结果，"""

    success: bool
    node_id: str
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class ExecutionCache:
    """
    执行结果缓存

    避免重复计算，"""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[datetime, ExecutionResult]] = {}
        self._ttl = ttl_seconds

    def set(self, node_type: str, inputs: Dict, result: ExecutionResult) -> None:
        key = self._make_cache_key(node_type, inputs)
        self._cache[key] = (datetime.now(), result)

    def get(self, node_type: str, inputs: Dict) -> Optional[ExecutionResult]:
        key = self._make_cache_key(node_type, inputs)
        if key not in self._cache:
            return None
        timestamp, result = self._cache.get(key)
        if timestamp and result:
            if datetime.now() - timestamp < timedelta(seconds=self._ttl):
                return result
        return None

    def invalidate(self, node_type: str) -> None:
        keys_to_remove = [k for k in self._cache if k.startswith(node_type)]
        for key in keys_to_remove:
            del self._cache[key]

    def clear(self) -> None:
        self._cache.clear()

    def _make_cache_key(self, node_type: str, inputs: Dict) -> str:
        content = json.dumps(
            {
                "type": node_type,
                "inputs": {k: str(v) for k, v in sorted(inputs.items()) if v is not None},
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()


class NodeEngine:
    """
    节点执行引擎

    核心职责：
    - 管理节点类型注册表
    - 执行单个节点
    - 执行整个工作流图
    - 发布执行事件

    执行流程：
    1. 获取拓扑排序后的执行顺序
    2. 重置所有节点状态
    3. 按顺序执行每个节点：
       a. 收集输入值
       b. 验证输入
       c. 调用执行函数
       d. 存储输出
       e. 更新状态
    4. 发布工作流完成事件

    Example:
        >>> engine = NodeEngine(event_bus=event_bus)
        >>> engine.register_node_type(text_join_def)
        >>> results = engine.execute_graph(graph)
        >>> for node_id, result in results.items():
        ...     if result.success:
        ...         print(f"节点 {node_id} 输出: {result.outputs}")
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        初始化节点执行引擎

        Args:
            event_bus: 事件总线（可选，用于发布执行事件）

        Note:
            推荐使用单例模式获取引擎实例：
            - get_node_engine(): 获取全局实例
            - init_node_engine(event_bus): 初始化全局实例

            直接构造 NodeEngine() 仍可用于测试场景。
        """
        self._registry = NodeRegistry()
        self._event_bus = event_bus
        # self._register_builtin_nodes()

        _logger.debug("节点执行引擎初始化完成")

    # def _register_builtin_nodes(self) -> None:
    #     """注册内置节点类型"""
    #     # 文本输入节点
    #     self._registry.register(
    #         NodeDefinition(
    #             node_type="text.input",
    #             display_name="文本输入",
    #             description="输入文本内容",
    #             category="text",
    #             icon="📝",
    #             inputs=[],
    #             outputs=[
    #                 PortDefinition("text", PortType.STRING, "输入的文本"),
    #             ],
    #             execute=lambda: {"text": ""},
    #         )
    #     )

    #     # 文本拼接节点
    #     self._registry.register(
    #         NodeDefinition(
    #             node_type="text.join",
    #             display_name="文本拼接",
    #             description="将两个文本拼接在一起",
    #             category="text",
    #             icon="🔗",
    #             inputs=[
    #                 PortDefinition("text1", PortType.STRING, "第一个文本"),
    #                 PortDefinition("text2", PortType.STRING, "第二个文本"),
    #                 PortDefinition(
    #                     "separator", PortType.STRING, "分隔符", default=" ", required=False
    #                 ),
    #             ],
    #             outputs=[PortDefinition("result", PortType.STRING, "拼接结果")],
    #             execute=lambda text1, text2, separator=" ": {
    #                 "result": f"{text1}{separator}{text2}"
    #             },
    #         )
    #     )

    #     # 文本转大写节点
    #     self._registry.register(
    #         NodeDefinition(
    #             node_type="text.upper",
    #             display_name="转大写",
    #             description="将文本转换为大写",
    #             category="text",
    #             icon="🔠",
    #             inputs=[PortDefinition("text", PortType.STRING, "输入文本")],
    #             outputs=[PortDefinition("result", PortType.STRING, "大写文本")],
    #             execute=lambda text: {"result": text.upper()},
    #         )
    #     )

    #     # 文本转小写节点
    #     self._registry.register(
    #         NodeDefinition(
    #             node_type="text.lower",
    #             display_name="转小写",
    #             description="将文本转换为小写",
    #             category="text",
    #             icon="🔡",
    #             inputs=[PortDefinition("text", PortType.STRING, "输入文本")],
    #             outputs=[PortDefinition("result", PortType.STRING, "小写文本")],
    #             execute=lambda text: {"result": text.lower()},
    #         )
    #     )

    #     # 文本输出预览节点
    #     self._registry.register(
    #         NodeDefinition(
    #             node_type="text.output",
    #             display_name="文本输出",
    #             description="预览输出文本结果",
    #             category="text",
    #             icon="📄",
    #             inputs=[PortDefinition("text", PortType.STRING, "要显示的文本")],
    #             outputs=[],
    #             execute=lambda text: {},
    #         )
    #     )

    #     _logger.info(f"已注册 {len(self._registry._definitions)} 个内置节点")

    @property
    def registry(self) -> NodeRegistry:
        """获取节点注册表"""
        return self._registry

    # ==================== 节点类型管理 ====================

    def register_node_type(self, definition: NodeDefinition) -> None:
        """
        注册节点类型

        Args:
            definition: 节点定义

        Example:
            >>> engine.register_node_type(NodeDefinition(
            ...     node_type="text.upper",
            ...     display_name="转大写",
            ...     execute=lambda text: {"result": text.upper()},
            ... ))
        """
        self._registry.register(definition)

        # 发布节点注册事件
        if self._event_bus:
            self._event_bus.publish(EventType.NODE_REGISTERED, {"node_type": definition.node_type})

    def unregister_node_type(self, node_type: str) -> bool:
        """
        注销节点类型

        Args:
            node_type: 节点类型标识

        Returns:
            是否成功注销
        """
        result = self._registry.unregister(node_type)

        if result and self._event_bus:
            self._event_bus.publish(EventType.NODE_UNREGISTERED, {"node_type": node_type})

        return result

    def get_node_definition(self, node_type: str) -> Optional[NodeDefinition]:
        """
        获取节点定义

        Args:
            node_type: 节点类型标识

        Returns:
            节点定义，如果不存在则返回 None
        """
        return self._registry.get(node_type)

    def get_all_node_types(self) -> List[NodeDefinition]:
        """
        获取所有已注册的节点类型

        Returns:
            节点定义列表
        """
        return self._registry.get_all()

    # ==================== 节点执行 ====================

    def execute_node(
        self,
        node: Node,
        graph: NodeGraph,
    ) -> ExecutionResult:
        """
        执行单个节点

        执行流程：
        1. 获取节点定义
        2. 收集输入值（连接 > 控件值 > 默认值）
        3. 验证输入
        4. 调用执行函数
        5. 存储输出
        6. 更新状态
        7. 发布事件

        Args:
            node: 要执行的节点
            graph: 所属的图（用于获取连接信息）

        Returns:
            执行结果

        Example:
            >>> result = engine.execute_node(node, graph)
            >>> if result.success:
            ...     print(f"输出: {result.outputs}")
        """
        start_time = time.time()

        # 获取节点定义
        definition = self._registry.get(node.node_type)
        if definition is None:
            error_msg = f"未知的节点类型: {node.node_type}"
            node.state = NodeState.ERROR
            node.error_message = error_msg
            _logger.error(error_msg)
            return ExecutionResult(
                success=False,
                node_id=node.id,
                error=error_msg,
            )

        try:
            # 更新状态为执行中
            node.state = NodeState.RUNNING
            self._publish_node_event(EventType.WORKFLOW_STARTED, node)

            # 收集输入值
            inputs = self._collect_inputs(node, graph, definition)

            # 验证输入
            errors = definition.validate_inputs(inputs)
            if errors:
                error_msg = "; ".join(errors)
                node.state = NodeState.ERROR
                node.error_message = error_msg
                _logger.error(f"节点 {node.id[:8]}... 输入验证失败: {error_msg}")
                return ExecutionResult(
                    success=False,
                    node_id=node.id,
                    error=error_msg,
                )

            # 执行
            if definition.execute is None:
                error_msg = "节点没有执行函数"
                node.state = NodeState.ERROR
                node.error_message = error_msg
                return ExecutionResult(
                    success=False,
                    node_id=node.id,
                    error=error_msg,
                )

            _logger.debug(f"执行节点: {node.node_type} [{node.id[:8]}...]")
            outputs = definition.execute(**inputs)
            _logger.debug(f"执行返回: {outputs}")

            # 存储输出
            node.outputs = outputs or {}
            node.state = NodeState.SUCCESS
            node.error_message = None
            _logger.debug(f"节点输出已存储: {node.id[:8]}... -> {node.outputs}")

            # 计算耗时
            duration_ms = (time.time() - start_time) * 1000

            _logger.debug(
                f"节点执行成功: {node.node_type} [{node.id[:8]}...] ({duration_ms:.2f}ms)"
            )

            # 发布事件
            result = ExecutionResult(
                success=True,
                node_id=node.id,
                outputs=outputs,
                duration_ms=duration_ms,
            )
            self._publish_node_event(EventType.NODE_EXECUTED, node, result)

            return result

        except Exception as e:
            # 执行失败
            error_msg = str(e)
            node.state = NodeState.ERROR
            node.error_message = error_msg

            _logger.error(
                f"节点执行失败: {node.node_type} [{node.id[:8]}...]: {error_msg}",
                exc_info=True,
            )

            result = ExecutionResult(
                success=False,
                node_id=node.id,
                error=error_msg,
            )
            self._publish_node_event(EventType.NODE_EXECUTED, node, result)

            return result

    def execute_graph(self, graph: NodeGraph) -> Dict[str, ExecutionResult]:
        """
        执行整个工作流图

        执行流程：
        1. 获取拓扑排序后的执行顺序
        2. 重置所有节点状态
        3. 按顺序执行每个节点
        4. 如果某节点失败，停止后续执行
        5. 发布工作流完成事件

        Args:
            graph: 要执行的图

        Returns:
            节点ID到执行结果的映射

        Raises:
            CyclicDependencyError: 如果图中存在循环依赖

        Example:
            >>> results = engine.execute_graph(graph)
            >>> success_count = sum(1 for r in results.values() if r.success)
            >>> print(f"执行完成: {success_count}/{len(results)} 成功")
        """
        _logger.info(f"开始执行工作流: {graph.name}")

        results: Dict[str, ExecutionResult] = {}

        # 获取执行顺序
        try:
            execution_order = graph.get_execution_order()
        except CyclicDependencyError as e:
            _logger.error(f"工作流执行失败: {e}")
            raise

        # 重置所有节点状态
        for node in graph.nodes.values():
            node.state = NodeState.IDLE
            node.error_message = None
            node.outputs.clear()

        # 发布工作流开始事件
        if self._event_bus:
            self._event_bus.publish(
                EventType.WORKFLOW_STARTED, {"graph_id": graph.id, "name": graph.name}
            )

        # 按顺序执行
        for node_id in execution_order:
            node = graph.get_node(node_id)
            if node is None:
                continue

            result = self.execute_node(node, graph)
            results[node_id] = result

            # 如果失败，停止后续执行
            if not result.success:
                _logger.warning(f"工作流执行中断: 节点 {node_id[:8]}... 失败 - {result.error}")
                break

        # 发布工作流完成事件
        success = all(r.success for r in results.values())
        if self._event_bus:
            self._event_bus.publish(
                EventType.WORKFLOW_COMPLETED,
                {
                    "graph_id": graph.id,
                    "name": graph.name,
                    "success": success,
                    "results": {
                        node_id: {
                            "success": r.success,
                            "error": r.error,
                        }
                        for node_id, r in results.items()
                    },
                },
            )

        _logger.info(
            f"工作流执行完成: {graph.name} - "
            f"{sum(1 for r in results.values() if r.success)}/{len(results)} 成功"
        )

        return results

    def _get_execution_layers(self, graph: NodeGraph) -> List[List[Node]]:
        """
        获取执行层级（基于依赖关系的拓扑排序）

        返回执行层级列表， 每层包含可并行执行的节点

        使用Kahn算法进行拓扑排序
        """
        if not graph.nodes:
            return []

        # 构建依赖图
        dependencies: Dict[str, Set[str]] = {}  # node_id -> 依赖的节点ID集合
        in_degree: Dict[str, int] = {}  # node_id -> 入度

        for node_id in graph.nodes:
            in_degree[node_id] = 0
            dependencies[node_id] = set()

        for conn in graph.connections.values():
            target = conn.target_node
            source = conn.source_node
            if target in dependencies:
                dependencies[target].add(source)
                in_degree[target] += 1

        # Kahn算法进行拓扑排序
        layers: List[List[Node]] = []
        remaining = set(in_degree.keys())

        while remaining:
            ready = [nid for nid in remaining if in_degree[nid] == 0]

            if not ready:
                break  # 存在循环依赖

            layers.append([graph.nodes[nid] for nid in ready])
            remaining -= set(ready)

            for nid in ready:
                for dep in dependencies[nid]:
                    if dep in remaining:
                        in_degree[dep] -= 1

        return layers

    def execute_graph_parallel(
        self,
        graph: NodeGraph,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[int, int], None]] = None,
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

        layers = self._get_execution_layers(graph)
        total_nodes = sum(len(layer) for layer in layers)
        completed = 0
        results: Dict[str, ExecutionResult] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for layer_idx, layer in enumerate(layers):
                _logger.info(f"执行层级 {layer_idx + 1}/{len(layers)}")

                layer_results = []
                for node in layer:
                    future = executor.submit(self._execute_node_safe, node, graph)
                    layer_results.append((node.id, future))

                for node_id, future in layer_results:
                    try:
                        result = future.result()
                        results[node_id] = result
                        completed += 1
                    except Exception as e:
                        results[node_id] = ExecutionResult(
                            success=False, node_id=node_id, error=str(e), duration_ms=0.0
                        )

                if progress_callback:
                    progress_callback(completed, total_nodes)

        return results

    def _execute_node_safe(self, node: Node, graph: NodeGraph) -> ExecutionResult:
        """安全执行单个节点（用于并行执行）"""
        try:
            return self.execute_node(node, graph)
        except Exception as e:
            return ExecutionResult(success=False, node_id=node.id, error=str(e), duration_ms=0.0)

    # ==================== 辅助方法 ====================

    def _collect_inputs(
        self,
        node: Node,
        graph: NodeGraph,
        definition: NodeDefinition,
    ) -> Dict[str, Any]:
        """
        收集节点输入值

        优先级：连接 > 控件值 > 默认值 > None（可选端口）

        对于可选端口（required=False），如果没有值，传入 None 而不是省略该参数。

        Args:
            node: 目标节点
            graph: 所属图
            definition: 节点定义

        Returns:
            输入参数字典（包含所有端口，可选端口无值时为 None）
        """
        inputs: Dict[str, Any] = {}

        incoming_conns = graph.get_incoming_connections(node.id)
        conn_map = {conn.target_port: conn for conn in incoming_conns}

        for port in definition.inputs:
            if port.name in conn_map:
                conn = conn_map[port.name]
                source_node = graph.get_node(conn.source_node)
                if source_node and conn.source_port in source_node.outputs:
                    inputs[port.name] = source_node.outputs[conn.source_port]
            elif port.name in node.widget_values:
                inputs[port.name] = node.widget_values[port.name]
            elif port.default is not None:
                inputs[port.name] = port.default
            else:
                inputs[port.name] = None

        return inputs

    def _publish_node_event(
        self,
        event_type: EventType,
        node: Node,
        result: Optional[ExecutionResult] = None,
    ) -> None:
        """
        发布节点相关事件

        Args:
            event_type: 事件类型
            node: 节点
            result: 执行结果（可选）
        """
        if self._event_bus is None:
            return

        data = {
            "node_id": node.id,
            "node_type": node.node_type,
            "state": node.state.value,
        }

        if result:
            data["success"] = result.success
            data["duration_ms"] = result.duration_ms
            if result.error:
                data["error"] = result.error

        self._event_bus.publish(event_type, data)

    def get_available_nodes(self) -> List[Dict[str, Any]]:
        """
        获取所有可用节点信息（供Agent使用）

        委托给NodeRegistry.get_all_for_agent()

        Returns:
            节点信息字典列表

        Example:
            >>> nodes = engine.get_available_nodes()
            >>> print(f"共有 {len(nodes)} 个可用节点")
        """
        return self._registry.get_all_for_agent()


# ==================== 全局单例 ====================

# 全局节点引擎实例
_global_node_engine: Optional[NodeEngine] = None

# 线程锁，确保单例初始化的线程安全
_global_lock = threading.Lock()


def get_node_engine() -> NodeEngine:
    """
    获取全局节点引擎实例

    如果实例不存在，会自动创建一个默认实例（无 event_bus）。

    Returns:
        全局 NodeEngine 实例

    Example:
        >>> engine = get_node_engine()
        >>> engine.register_node_type(my_node_def)
    """
    global _global_node_engine
    if _global_node_engine is None:
        with _global_lock:
            # 双重检查锁定
            if _global_node_engine is None:
                _global_node_engine = NodeEngine()
                _logger.info("全局节点引擎已自动创建")
    return _global_node_engine


def init_node_engine(event_bus: Optional[EventBus] = None) -> NodeEngine:
    """
    初始化全局节点引擎

    Args:
        event_bus: 事件总线（可选，用于发布执行事件）

    Returns:
        初始化后的全局节点引擎实例

    Raises:
        RuntimeError: 如果全局引擎已初始化

    Example:
        >>> from src.core.event_bus import EventBus
        >>> event_bus = EventBus()
        >>> engine = init_node_engine(event_bus=event_bus)
    """
    global _global_node_engine
    with _global_lock:
        if _global_node_engine is not None:
            raise RuntimeError(
                "全局节点引擎已初始化，请先调用 shutdown_node_engine() 或 reset_node_engine_for_testing()"
            )
        _global_node_engine = NodeEngine(event_bus=event_bus)
        _logger.info("全局节点引擎初始化完成")
        return _global_node_engine


def shutdown_node_engine() -> None:
    """
    关闭全局节点引擎

    清理全局实例，释放资源。
    """
    global _global_node_engine
    with _global_lock:
        if _global_node_engine is not None:
            _global_node_engine = None
            _logger.info("全局节点引擎已关闭")


def reset_node_engine_for_testing() -> None:
    """
    重置全局节点引擎（仅用于测试）

    强制清除全局实例，用于测试场景下的隔离。
    """
    global _global_node_engine
    with _global_lock:
        _global_node_engine = None
        _logger.debug("全局节点引擎已重置（测试模式）")
