# -*- coding: utf-8 -*-
"""
Agent工具注册中心

提供插件向Agent注册工具函数的统一入口。
AgentIntegration在初始化时从此注册中心拉取所有已注册的工具。

使用方式:
    from src.agent.tool_registry import AgentToolRegistry

    registry = AgentToolRegistry.instance()
    registry.register("my_plugin", [tool_func1, tool_func2])
    all_tools = registry.get_all_tools()
"""

import threading
from typing import Callable, Dict, List, Optional

from src.utils.logger import get_logger

_logger = get_logger(__name__)


class AgentToolRegistry:
    """
    Agent工具注册中心（单例）

    插件通过此注册中心向Agent提供工具函数：
    - register(): 注册一组工具函数
    - unregister(): 注销一组工具函数
    - get_all_tools(): 获取所有已注册的工具函数
    """

    _instance: Optional["AgentToolRegistry"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._tools: Dict[str, List[Callable]] = {}

    @classmethod
    def instance(cls) -> "AgentToolRegistry":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, group_name: str, tools: List[Callable]) -> None:
        """
        注册一组工具函数

        Args:
            group_name: 工具组名称（通常为插件名称）
            tools: 工具函数列表
        """
        if group_name in self._tools:
            _logger.warning(f"工具组 '{group_name}' 已存在，将被覆盖")
        self._tools[group_name] = list(tools)
        _logger.info(f"注册工具组 '{group_name}': {len(tools)} 个工具")

    def unregister(self, group_name: str) -> None:
        """
        注销一组工具函数

        Args:
            group_name: 工具组名称
        """
        removed = self._tools.pop(group_name, None)
        if removed is not None:
            _logger.info(f"注销工具组 '{group_name}': {len(removed)} 个工具")
        else:
            _logger.debug(f"工具组 '{group_name}' 不存在，跳过注销")

    def get_all_tools(self) -> List[Callable]:
        """
        获取所有已注册的工具函数

        Returns:
            所有工具函数列表
        """
        all_tools: List[Callable] = []
        for tools in self._tools.values():
            all_tools.extend(tools)
        return all_tools

    def get_group_names(self) -> List[str]:
        """获取所有已注册的工具组名称"""
        return list(self._tools.keys())

    def has_group(self, group_name: str) -> bool:
        """检查工具组是否已注册"""
        return group_name in self._tools

    @classmethod
    def _reset_for_testing(cls) -> None:
        """测试用：重置单例"""
        cls._instance = None
