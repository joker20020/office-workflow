# -*- coding: utf-8 -*-
"""
节点执行引擎模块

提供工作流执行能力：
- 节点类型注册管理（NodeRegistry）
- 单节点执行
- 支持环的有向图动态步进执行
- 执行状态回调和事件发布

核心执行流程（统一步进执行器）：
1. 发现入口节点（优先 flow.start，否则无入边节点）
2. 动态步进执行：
   a. 从队列中取出所有输入就绪的节点并行执行
   b. 每个节点完成后即时计算下一步
   c. 回边连接重置目标状态并入队（循环）
   d. 条件分支只走活跃分支下游
   e. 最大迭代保护（默认 1000 次）
3. 标记未执行节点为 SKIPPED

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

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import threading
import time

from src.core.event_bus import EventBus, EventType
from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.engine.node_graph import (
    Connection,
    Node,
    NodeGraph,
    NodeState,
)
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class _ExecutionCancelled(Exception):
    """由 on_node_completed 回调抛出以中断 execute_graph 执行。"""
    pass


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


class NodeEngine:
    """
    节点执行引擎

    核心职责：
    - 管理节点类型注册表
    - 执行单个节点
    - 支持环的有向图动态步进执行（分支 + 循环 + 并行）
    - 发布执行事件

    执行流程（统一步进执行器）：
    1. 发现入口节点（优先 flow.start，否则无入边节点）
    2. 动态步进执行：
       a. 从队列中取出所有输入就绪的节点并行执行
       b. 每个节点完成后即时计算下一步
       c. 回边连接重置目标状态并入队（循环）
       d. 条件分支只走活跃分支下游
       e. 最大迭代保护（默认 1000 次）
    3. 标记未执行节点为 SKIPPED

    """

    # 每个节点最大执行次数（防止死循环）
    MAX_ITERATIONS = 1000

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

        _logger.debug("节点执行引擎初始化完成")

    @property
    def registry(self) -> NodeRegistry:
        """获取节点注册表"""
        return self._registry

    @property
    def event_bus(self) -> Optional[EventBus]:
        """获取事件总线"""
        return self._event_bus

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
            self._publish_node_event(EventType.NODE_STARTED, node)

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

    def execute_graph(
        self,
        graph: NodeGraph,
        on_node_completed: Optional[Callable[[str, NodeState], None]] = None,
    ) -> Dict[str, ExecutionResult]:
        """
        统一步进执行器 — 支持环的有向图动态执行

        执行逻辑：
        1. 发现入口节点（优先 flow.start，否则无入边节点）
        2. 初始化队列、迭代计数器
        3. 主循环：
           a. 从队列中取出所有输入就绪的节点 -> ready_batch
           b. 如果 ready_batch 为空但队列不空 -> 死锁报错退出
           c. 并行执行 ready_batch
           d. 对每个完成的节点：
              - 记录到 completed
              - 更新 iteration_count，超过上限则报错退出
              - 计算下游节点：
                * 普通连接 -> 目标入队（等输入就绪）
                * 回边连接 -> 重置目标状态并入队
                * 条件分支 -> 只入队活跃分支下游
        4. 标记未执行节点为 SKIPPED
        5. 发布完成事件

        Args:
            graph: 要执行的图
            on_node_completed: 可选回调，每个节点执行完成后调用。
                回调接收 (node_id, state)，可用于通知 UI 或取消执行。
                抛出 _ExecutionCancelled 会中断执行。

        Returns:
            节点ID到执行结果的映射
        """
        _logger.info(f"开始执行工作流: {graph.name}")

        results: Dict[str, ExecutionResult] = {}

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

        # ---- 1. 发现入口节点 ----
        entry_nodes = graph.get_entry_nodes()
        if not entry_nodes:
            _logger.warning(f"工作流没有入口节点: {graph.name}")
            return results

        # ---- 2. 初始化 ----
        queue: deque = deque(entry_nodes)
        completed: Set[str] = set()
        iteration_count: Dict[str, int] = {}  # node_id -> 已执行次数
        skipped: Set[str] = set()  # 非活跃分支中跳过的节点

        _logger.debug(
            f"入口节点: {', '.join(n[:8] for n in entry_nodes)} "
            f"(共 {len(entry_nodes)} 个)"
        )

        # ---- 3. 主循环 ----
        while queue:
            # a. 从队列中取出所有输入就绪的节点
            ready_batch: List[str] = []
            remaining: List[str] = []

            while queue:
                node_id = queue.popleft()
                if self._is_input_ready_v2(node_id, graph, completed, skipped):
                    ready_batch.append(node_id)
                else:
                    remaining.append(node_id)

            # 将未就绪的放回队列
            for nid in remaining:
                queue.append(nid)

            # b. 如果 ready_batch 为空但 queue 不空 -> 死锁
            if not ready_batch:
                if queue:
                    _logger.error(
                        f"工作流死锁: {len(queue)} 个节点等待输入但无法就绪"
                    )
                    for nid in list(queue):
                        node = graph.get_node(nid)
                        if node:
                            node.state = NodeState.ERROR
                            node.error_message = "执行死锁：输入无法就绪"
                            results[nid] = ExecutionResult(
                                success=False, node_id=nid,
                                error=node.error_message,
                            )
                    break
                # 队列也为空，正常退出
                break

            # c. 并行执行 ready_batch
            if len(ready_batch) == 1:
                # 单节点直接执行，避免线程开销
                node_id = ready_batch[0]
                result = self._execute_single_node(node_id, graph)
                results[node_id] = result

                if on_node_completed:
                    try:
                        node = graph.get_node(node_id)
                        if node:
                            on_node_completed(node_id, node.state)
                    except _ExecutionCancelled:
                        _logger.info("执行被回调中断")
                        break

                if not result.success:
                    _logger.warning(
                        f"节点 {node_id[:8]}... 执行失败，中断执行"
                    )
                    break

                # 更新追踪集合
                completed.add(node_id)
                iteration_count[node_id] = iteration_count.get(node_id, 0) + 1

                # 检查迭代上限
                if iteration_count[node_id] > self.MAX_ITERATIONS:
                    node = graph.get_node(node_id)
                    if node:
                        node.state = NodeState.ERROR
                        node.error_message = f"超过最大迭代次数 ({self.MAX_ITERATIONS})"
                        results[node_id] = ExecutionResult(
                            success=False, node_id=node_id,
                            error=node.error_message,
                        )
                    _logger.error(f"节点 {node_id[:8]}... 超过最大迭代次数")
                    break

                # 计算下游并入队
                self._enqueue_downstream(
                    node_id, graph, completed, skipped, queue
                )
            else:
                # 多节点并行执行
                self._execute_and_enqueue(
                    ready_batch, graph, results, completed,
                    iteration_count, skipped, queue, on_node_completed,
                )

                # 检查是否有节点失败
                failed = [
                    nid for nid in ready_batch
                    if nid in results and not results[nid].success
                ]
                if failed:
                    _logger.warning(
                        f"{len(failed)} 个节点执行失败，中断执行"
                    )
                    break

                # 检查迭代上限
                over_limit = [
                    nid for nid in ready_batch
                    if iteration_count.get(nid, 0) > self.MAX_ITERATIONS
                ]
                if over_limit:
                    for nid in over_limit:
                        node = graph.get_node(nid)
                        if node:
                            node.state = NodeState.ERROR
                            node.error_message = f"超过最大迭代次数 ({self.MAX_ITERATIONS})"
                            results[nid] = ExecutionResult(
                                success=False, node_id=nid,
                                error=node.error_message,
                            )
                    _logger.error(
                        f"{len(over_limit)} 个节点超过最大迭代次数"
                    )
                    break

        # ---- 4. 标记未执行节点为 SKIPPED ----
        for node in graph.nodes.values():
            if node.id not in completed and node.id not in results:
                node.state = NodeState.SKIPPED
                node.outputs.clear()
                results[node.id] = ExecutionResult(success=True, node_id=node.id)
                _logger.debug(
                    f"跳过节点（未执行）: {node.node_type} [{node.id[:8]}...]"
                )
                self._publish_node_event(EventType.NODE_EXECUTED, node)
                if on_node_completed:
                    on_node_completed(node.id, NodeState.SKIPPED)

        # ---- 5. 发布工作流完成事件 ----
        success = all(r.success for r in results.values())
        if self._event_bus:
            self._event_bus.publish(
                EventType.WORKFLOW_COMPLETED,
                {
                    "graph_id": graph.id,
                    "name": graph.name,
                    "success": success,
                    "results": {
                        node_id: {"success": r.success, "error": r.error}
                        for node_id, r in results.items()
                    },
                },
            )

        _logger.info(
            f"工作流执行完成: {graph.name} - "
            f"{sum(1 for r in results.values() if r.success)}/{len(results)} 成功"
        )

        return results

    def _execute_single_node(
        self, node_id: str, graph: NodeGraph
    ) -> ExecutionResult:
        """执行单个节点（并行执行的辅助方法）。

        Args:
            node_id: 要执行的节点 ID
            graph: 所属的图

        Returns:
            执行结果
        """
        node = graph.get_node(node_id)
        if node is None:
            return ExecutionResult(
                success=False, node_id=node_id,
                error="节点不存在",
            )
        return self.execute_node(node, graph)

    def _execute_and_enqueue(
        self,
        batch: List[str],
        graph: NodeGraph,
        results: Dict[str, ExecutionResult],
        completed: Set[str],
        iteration_count: Dict[str, int],
        skipped: Set[str],
        queue: deque,
        on_node_completed: Optional[Callable[[str, NodeState], None]],
    ) -> None:
        """并行执行一批节点，完成后将下游节点入队。

        使用线程池并行执行所有就绪节点，每个节点完成后即时计算
        下游节点并入队。

        Args:
            batch: 本轮要执行的节点 ID 列表
            graph: 工作流图
            results: 执行结果字典（就地更新）
            completed: 已完成节点集合（就地更新）
            iteration_count: 迭代计数（就地更新）
            skipped: 跳过的节点集合（就地更新）
            queue: 执行队列（就地更新）
            on_node_completed: 节点完成回调
        """
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            future_to_node = {
                executor.submit(self._execute_single_node, nid, graph): nid
                for nid in batch
            }

            for future in as_completed(future_to_node):
                node_id = future_to_node[future]
                try:
                    result = future.result()
                except Exception as exc:
                    node = graph.get_node(node_id)
                    error_msg = str(exc)
                    if node:
                        node.state = NodeState.ERROR
                        node.error_message = error_msg
                    result = ExecutionResult(
                        success=False, node_id=node_id, error=error_msg,
                    )

                results[node_id] = result

                # 回调通知
                if on_node_completed:
                    try:
                        node = graph.get_node(node_id)
                        if node:
                            on_node_completed(node_id, node.state)
                    except _ExecutionCancelled:
                        _logger.info("执行被回调中断")

                if not result.success:
                    continue

                # 更新追踪集合
                completed.add(node_id)
                iteration_count[node_id] = iteration_count.get(node_id, 0) + 1

                # 计算下游并入队
                self._enqueue_downstream(
                    node_id, graph, completed, skipped, queue
                )

    def _enqueue_downstream(
        self,
        node_id: str,
        graph: NodeGraph,
        completed: Set[str],
        skipped: Set[str],
        queue: deque,
    ) -> None:
        """将已完成节点的下游节点加入执行队列。

        处理三种连接类型：
        - 普通连接：目标入队（等输入就绪）
        - 回边连接：重置目标状态并入队
        - 条件分支：只入队活跃分支下游，非活跃分支的下游标记为 skipped

        Args:
            node_id: 已完成的源节点 ID
            graph: 工作流图
            completed: 已完成节点集合
            skipped: 跳过的节点集合（就地更新）
            queue: 执行队列（就地更新）
        """
        node = graph.get_node(node_id)
        if node is None:
            return

        definition = self._registry.get(node.node_type)

        # 检查是否有条件分支端口
        active_branch_ports: Optional[Set[str]] = None
        if definition:
            branch_ports = [
                p for p in definition.outputs
                if p.role in ("branch_true", "branch_false")
            ]
            if branch_ports:
                # 通过端口输出值判断活跃分支
                active_branch_ports = set()
                for p in branch_ports:
                    if node.outputs.get(p.name) is not None:
                        active_branch_ports.add(p.name)

        for conn in graph.get_outgoing_connections(node_id):
            # 条件分支端口处理
            if active_branch_ports is not None and definition:
                port_def = definition.get_output_port(conn.source_port)
                if port_def and port_def.role in ("branch_true", "branch_false"):
                    if port_def.name not in active_branch_ports:
                        # 非活跃分支：标记下游为 skipped
                        inactive = graph.trace_downstream(
                            node_id, conn.source_port
                        )
                        skipped.update(inactive)
                        _logger.debug(
                            f"跳过非活跃分支 '{conn.source_port}': "
                            f"{len(inactive)} 个节点"
                        )
                        continue

            target_id = conn.target_node

            # 回边处理
            if conn.is_back_edge:
                target_node = graph.get_node(target_id)
                if target_node:
                    target_node.state = NodeState.IDLE
                    target_node.outputs.clear()
                    target_node.error_message = None
                    completed.discard(target_id)
                queue.append(target_id)
                _logger.debug(f"回边入队: {target_id[:8]}...")
            else:
                # 普通连接：目标入队
                # 如果目标节点已完成但源节点刚被重新执行（循环迭代），
                # 需要重置目标节点并重新入队
                if target_id in completed:
                    target_node = graph.get_node(target_id)
                    if target_node:
                        target_node.state = NodeState.IDLE
                        target_node.outputs.clear()
                        target_node.error_message = None
                    completed.discard(target_id)
                    skipped.discard(target_id)
                if target_id not in queue:
                    queue.append(target_id)

    def _is_input_ready_v2(
        self,
        node_id: str,
        graph: NodeGraph,
        completed: Set[str],
        skipped: Set[str],
    ) -> bool:
        """检查节点的所有输入是否就绪（v2 版本）。

        节点输入就绪条件：
        - 对于每个入边连接：
          - 普通连接：源节点必须在 completed 中
          - 回边连接：不阻塞（视为可选）
          - 来自 skipped 节点的连接：不阻塞（源节点被跳过）
        - 所有非回边、非跳过的必需输入都就绪时，节点可以执行

        Args:
            node_id: 要检查的节点 ID
            graph: 图
            completed: 已完成节点集合
            skipped: 被跳过的节点集合

        Returns:
            所有输入是否就绪
        """
        node = graph.get_node(node_id)
        if node is None:
            return True

        definition = self._registry.get(node.node_type)

        for conn in graph.get_incoming_connections(node_id):
            source = conn.source_node

            # 回边不阻塞
            if conn.is_back_edge:
                continue

            # 源已完成，输入可用
            if source in completed:
                continue

            # 源被跳过（非活跃分支），忽略此输入
            if source in skipped:
                continue

            # 源已到达但未完成：检查目标端口是否为可选端口
            if definition:
                target_port = definition.get_input_port(conn.target_port)
                if target_port is None:
                    # 目标端口不在定义中，不阻塞
                    continue
                if not target_port.required:
                    # 可选端口，不阻塞
                    continue

            return False

        return True

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
            value_found = False

            # 1. 尝试从连接获取值
            if port.name in conn_map:
                conn = conn_map[port.name]
                source_node = graph.get_node(conn.source_node)
                if source_node and conn.source_port in source_node.outputs:
                    inputs[port.name] = source_node.outputs[conn.source_port]
                    value_found = True

            # 2. 连接无值时回退到控件值 / 默认值 / None
            if not value_found:
                if port.name in node.widget_values:
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
