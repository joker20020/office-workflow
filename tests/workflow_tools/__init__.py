# -*- coding: utf-8 -*-
"""
工作流工具插件

为AI助手提供工作流和节点操作能力，包括：
- 创建/删除节点
- 连接/断开节点
- 设置节点值
- 执行工作流
- 查询节点信息

启用此插件后，AI助手将获得操作节点编辑器的能力。
禁用后，AI助手将无法操作工作流。

使用方式：
    通过插件管理界面启用/禁用此插件。
"""

from src.agent.workflow_tools import WorkflowTools
from src.core.permission_manager import Permission, PermissionSet
from src.core.plugin_base import PluginBase
from src.utils.logger import get_logger

_logger = get_logger(__name__)

TOOL_GROUP_NAME = "workflow"


class WorkflowToolsPlugin(PluginBase):
    """
    工作流工具插件

    启用时创建WorkflowTools并注册到AgentToolRegistry，
    禁用时从注册中心移除。
    """

    name = "workflow_tools"
    version = "1.0.0"
    description = "为AI助手提供工作流和节点操作能力"
    author = "OfficeTools"

    permissions = PermissionSet.from_list([Permission.AGENT_TOOL, Permission.NODE_READ])

    def __init__(self):
        super().__init__()
        self._workflow_tools: WorkflowTools = None

    def on_enable(self, context) -> None:
        """
        启用插件：从上下文获取 node_graph 和 node_engine，创建工具并通过 context 注册。

        Args:
            context: PermissionProxy 或 AppContext 实例
        """
        node_graph = context.node_graph
        node_engine = context.node_engine

        self._workflow_tools = WorkflowTools(node_graph, node_engine)

        # 通过 context 的 tool_registry 注册工具（受权限检查保护）
        tools = self._workflow_tools.get_all_tools()
        context.tool_registry.register(TOOL_GROUP_NAME, tools)

        # 连接信号到 EventBus（通过 context 的事件总线转发）
        event_bus = context.event_bus
        self._workflow_tools.graph_changed.connect(
            lambda: _publish_graph_changed(event_bus)
        )
        self._workflow_tools.node_value_changed.connect(
            lambda node_id, port_name, value: _publish_node_value_changed(
                event_bus, node_id, port_name, value
            )
        )

        _logger.info(f"WorkflowToolsPlugin 已启用，注册了 {len(tools)} 个工具")

    def on_disable(self, context=None) -> None:
        """
        禁用插件：通过 context 注销工具，清理资源。
        """
        if context is not None:
            context.tool_registry.unregister(TOOL_GROUP_NAME)

        if self._workflow_tools is not None:
            self._workflow_tools.deleteLater()
            self._workflow_tools = None

        _logger.info("WorkflowToolsPlugin 已禁用")


def _publish_graph_changed(event_bus) -> None:
    """发布 graph_changed 事件到 EventBus"""
    try:
        from src.core.event_bus import EventType
        event_bus.publish(EventType.WORKFLOW_STARTED, {})
    except Exception as e:
        _logger.error(f"发布 graph_changed 事件失败: {e}")


def _publish_node_value_changed(event_bus, node_id: str, port_name: str, value) -> None:
    """发布 node_value_changed 事件到 EventBus"""
    try:
        from src.core.event_bus import EventType
        event_bus.publish(
            EventType.NODE_EXECUTED,
            {"node_id": node_id, "port_name": port_name, "value": value},
        )
    except Exception as e:
        _logger.error(f"发布 node_value_changed 事件失败: {e}")


# 插件元数据（供 PluginManager 发现）
plugin_class = WorkflowToolsPlugin
