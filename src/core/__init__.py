# -*- coding: utf-8 -*-
"""
核心模块初始化文件
====================

本模块包含办公小工具整合平台的核心组件:
- 插件系统 (Plugin System)
- 节点引擎 (Node Engine)
- 节点注册中心 (Node Registry)

Phase 1 实现内容:
- plugin_base: 插件基类和工具定义
- plugin_manager: 插件管理器
- node_base: 自定义节点基类
- node_engine: 自研节点流引擎
- node_registry: 节点注册中心
"""

from .plugin_base import (
    PluginBase,
    ToolDefinition,
    PortDefinition,
    PortType,
)
from .plugin_manager import (
    PluginInfo,
    PluginState,
    PluginManager,
)
from .node_base import (
    NodeBase,
    NodePort,
)
from .node_engine import (
    NodeState,
    Port,
    Connection,
    Node,
    NodeGraph,
    NodeEngine,
)
from .node_registry import (
    NodeRegistry,
    node_registry,
)

__all__ = [
    # 插件系统
    "PluginBase",
    "ToolDefinition",
    "PortDefinition",
    "PortType",
    "PluginInfo",
    "PluginState",
    "PluginManager",
    # 节点系统
    "NodeBase",
    "NodePort",
    "NodeState",
    "Port",
    "Connection",
    "Node",
    "NodeGraph",
    "NodeEngine",
    "NodeRegistry",
    "node_registry",
]
