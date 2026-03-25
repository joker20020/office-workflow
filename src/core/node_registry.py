# -*- coding: utf-8 -*-
"""
节点注册中心模块
==================

本模块实现节点的发现和注册功能:
- NodeRegistry: 节点注册中心类
- node_registry: 全局节点注册中心实例

设计特点:
- 支持手动注册和自动发现
- 从Python模块和目录发现NodeBase子类
- 按分类筛选节点

使用方式:
    # 手动注册
    node_registry.register(MyCustomNode)

    # 自动发现
    node_registry.discover_from_directory(Path("nodes"))
"""

import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Type, Optional

from .node_base import NodeBase


class NodeRegistry:
    """
    节点注册中心类

    管理所有可用节点类型的注册和发现。
    是自定义节点系统的核心组件。

    功能:
        - register(): 手动注册节点类型
        - unregister(): 注销节点类型
        - get(): 获取节点类型
        - create_instance(): 创建节点实例
        - get_all(): 获取所有节点类型
        - get_by_category(): 按分类获取节点
        - discover_from_module(): 从模块发现节点
        - discover_from_directory(): 从目录发现节点

    属性:
        _node_types: 已注册的节点类型字典 {type: NodeBase类}

    使用示例:
        >>> from src.core.node_registry import node_registry
        >>> from src.plugins.custom_nodes.text_process import TextInputNode
        >>>
        >>> # 手动注册
        >>> node_registry.register(TextInputNode)
        >>>
        >>> # 获取节点类
        >>> node_class = node_registry.get("text_input")
        >>>
        >>> # 创建实例
        >>> node = node_registry.create_instance("text_input")
    """

    def __init__(self):
        """初始化节点注册中心"""
        # 已注册的节点类型: {node_type: NodeBase类}
        self._node_types: Dict[str, Type[NodeBase]] = {}

    def register(self, node_class: Type[NodeBase]) -> None:
        """
        注册节点类型

        将一个NodeBase子类注册到注册中心。
        注册后可以通过create_instance()创建实例。

        参数:
            node_class: 要注册的节点类（必须继承自NodeBase）

        异常:
            ValueError: 如果类不是NodeBase的子类，或没有定义node_type

        示例:
            >>> node_registry.register(TextInputNode)
        """
        # 验证是否是NodeBase的子类
        if not (isinstance(node_class, type) and issubclass(node_class, NodeBase)):
            raise ValueError(f"{node_class} 必须继承自 NodeBase")

        # 验证是否定义了node_type
        if not node_class.node_type:
            raise ValueError(f"{node_class} 必须定义 node_type")

        # 注册到字典
        self._node_types[node_class.node_type] = node_class

    def unregister(self, node_type: str) -> None:
        """
        注销节点类型

        从注册中心移除指定的节点类型。

        参数:
            node_type: 要注销的节点类型标识

        示例:
            >>> node_registry.unregister("text_input")
        """
        if node_type in self._node_types:
            del self._node_types[node_type]

    def get(self, node_type: str) -> Optional[Type[NodeBase]]:
        """
        获取节点类型类

        根据节点类型标识获取节点类。

        参数:
            node_type: 节点类型标识

        返回:
            Optional[Type[NodeBase]]: 节点类，如果不存在返回None

        示例:
            >>> node_class = node_registry.get("text_input")
        """
        return self._node_types.get(node_type)

    def create_instance(self, node_type: str, **kwargs) -> NodeBase:
        """
        创建节点实例

        根据节点类型创建节点实例。
        传入的kwargs会传递给节点类的构造函数。

        参数:
            node_type: 节点类型标识
            **kwargs: 传递给节点构造函数的参数

        返回:
            NodeBase: 创建的节点实例

        异常:
            ValueError: 如果节点类型不存在

        示例:
            >>> node = node_registry.create_instance("text_input", default_text="Hello")
        """
        node_class = self.get(node_type)
        if node_class is None:
            raise ValueError(f"未知的节点类型: {node_type}")
        return node_class(**kwargs)

    def get_all(self) -> List[Type[NodeBase]]:
        """
        获取所有已注册的节点类型

        返回:
            List[Type[NodeBase]]: 所有节点类的列表

        示例:
            >>> all_nodes = node_registry.get_all()
            >>> for node_class in all_nodes:
            ...     print(node_class.node_type)
        """
        return list(self._node_types.values())

    def get_by_category(self, category: str) -> List[Type[NodeBase]]:
        """
        按分类获取节点

        返回指定分类下的所有节点类型。

        参数:
            category: 分类名称

        返回:
            List[Type[NodeBase]]: 该分类下的节点类列表

        示例:
            >>> text_nodes = node_registry.get_by_category("文本处理")
        """
        return [
            node_class
            for node_class in self._node_types.values()
            if node_class.category == category
        ]

    def discover_from_module(self, module_path: str) -> None:
        """
        从Python模块发现并注册节点

        扫描指定模块，查找所有NodeBase子类并注册。

        参数:
            module_path: Python模块路径（如"src.plugins.custom_nodes"）

        发现规则:
            - 必须是NodeBase的子类
            - 不能是NodeBase本身
            - 必须定义了node_type属性

        示例:
            >>> node_registry.discover_from_module("src.plugins.custom_nodes")
        """
        # 导入模块
        module = importlib.import_module(module_path)

        # 遍历模块中的所有成员
        for name, obj in inspect.getmembers(module):
            # 检查是否是类
            if not inspect.isclass(obj):
                continue

            # 检查是否是NodeBase的子类（但不是NodeBase本身）
            if not (issubclass(obj, NodeBase) and obj is not NodeBase):
                continue

            # 检查是否定义了node_type
            if not hasattr(obj, "node_type") or not obj.node_type:
                continue

            # 注册节点
            self.register(obj)

    def discover_from_directory(self, directory: Path) -> None:
        """
        从目录发现并注册节点

        扫描指定目录下的所有Python文件，查找并注册NodeBase子类。

        参数:
            directory: 要扫描的目录路径

        发现规则:
            - 递归扫描所有.py文件
            - 跳过以_开头的文件
            - 将文件路径转换为模块路径进行导入

        示例:
            >>> from pathlib import Path
            >>> node_registry.discover_from_directory(Path("src/plugins/custom_nodes"))

        注意:
            - 目录必须在Python路径中
            - 导入失败会打印错误信息但不会抛出异常
        """
        # 递归查找所有Python文件
        for py_file in directory.glob("**/*.py"):
            # 跳过以_开头的文件
            if py_file.name.startswith("_"):
                continue

            # 将文件路径转换为模块路径
            # 例如: src/plugins/nodes/text.py -> src.plugins.nodes.text
            module_path = str(py_file.with_suffix("")).replace("/", ".")

            try:
                # 从模块发现节点
                self.discover_from_module(module_path)
            except Exception as e:
                # 打印错误信息但不中断
                print(f"发现节点失败 {module_path}: {e}")


# 全局节点注册中心实例
# 敇活后可直接使用，无需手动创建
node_registry = NodeRegistry()
