# -*- coding: utf-8 -*-
"""
插件管理器模块
================

本模块实现插件的发现、加载、管理和卸载功能:
- PluginInfo: 插件信息数据类
- PluginState: 插件管理器状态类
- PluginManager: 插件管理器主类

设计要点:
- 支持包插件和单文件插件两种形式
- 自动发现插件目录中的插件
- 统一的工具注册管理
"""

import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .plugin_base import PluginBase, ToolDefinition


@dataclass
class PluginInfo:
    """
    插件信息数据类

    存储单个插件的元信息和状态。
    用于PluginManager中跟踪已加载的插件。

    属性:
        name: 插件名称
        version: 插件版本
        description: 插件描述
        path: 插件文件路径
        instance: 插件实例对象（运行时）
        loaded: 是否已加载
        error: 加载错误信息（如果有）

    示例:
        >>> info = PluginInfo(
        ...     name="excel_tools",
        ...     version="1.0.0",
        ...     description="Excel处理工具",
        ...     path=Path("plugins/excel_tools"),
        ...     loaded=True
        ... )
    """

    name: str  # 插件名称
    version: str  # 插件版本
    description: str  # 插件描述
    path: Path  # 插件路径
    instance: Any = None  # 插件实例（运行时）
    loaded: bool = False  # 是否已加载
    error: Optional[str] = None  # 错误信息


class PluginState:
    """
    插件管理器状态类

    管理插件系统的全局状态，包括已注册的工具。
    这是一个纯数据容器，不包含业务逻辑。

    属性:
        plugins: 已加载的插件信息字典 {name: PluginInfo}
        tools: 已注册的工具字典 {name: ToolDefinition}

    方法:
        register_tool: 注册工具到状态中
        unregister_tool: 从状态中注销工具
    """

    def __init__(self):
        """初始化插件状态"""
        # 插件信息字典： {插件名: PluginInfo}
        self.plugins: Dict[str, PluginInfo] = {}
        # 工具定义字典: {工具名= ToolDefinition}
        self.tools: Dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """
        注册工具

        将工具定义添加到工具字典中。
        工具注册后，可以被:
        - AI Agent调用（通过Toolkit)
        - 节点引擎使用（通过NodeEngine)

        参数:
            tool: 要注册的工具定义
        """
        self.tools[tool.name] = tool

    def unregister_tool(self, tool_name: str) -> None:
        """
        注销工具

        从工具字典中移除指定的工具。
        通常在插件卸载时调用。

        参数:
            tool_name: 要注销的工具名称
        """
        if tool_name in self.tools:
            del self.tools[tool_name]


class PluginManager:
    """
    插件管理器主类

    负责插件的发现、加载、卸载和工具注册。
    是插件系统的核心组件。

    功能:
        - discover_plugins: 扫描插件目录，发现可用插件
        - load_plugin: 加载单个插件并注册其工具
        - load_all: 加载所有发现的插件
        - unload_plugin: 卸载插件并注销其工具
        - get_tool: 获取工具定义
        - get_all_tools: 获取所有已注册的工具

    属性:
        plugins_dir: 插件目录路径
        state: 插件状态对象
        _instances: 插件实例缓存

    设计说明:
        - 插件可以是包（目录+__init__.py）或单文件（xxx.py）
        - 加载时自动查找PluginBase子类
        - 工具自动注册到state.tools
    """

    def __init__(self, plugins_dir: Path, state: PluginState):
        """
        初始化插件管理器

        参数:
            plugins_dir: 插件目录路径
            state: 插件状态对象（共享状态）
        """
        self.plugins_dir = plugins_dir
        self.state = state
        # 插件实例缓存: {插件名: 插件实例}
        self._instances: Dict[str, PluginBase] = {}
        # 继承状态中的插件字典引用
        self.plugins = state.plugins
        # 继承状态中的工具字典引用
        self.tools = state.tools

    def discover_plugins(self) -> List[str]:
        """
        发现所有可用插件

        扫描插件目录，查找所有符合规范的插件。
        支持两种形式:
        1. 包插件: 目录中包含__init__.py文件
        2. 单文件插件: 目录中的.py文件（不以_开头）

        返回:
            List[str]: 发现的插件名称列表

        示例:
            >>> manager = PluginManager(Path("plugins"), state)
            >>> plugins = manager.discover_plugins()
            >>> print(plugins)  # ['excel_tools', 'table_tools']
        """
        discovered = []

        # 检查插件目录是否存在
        if not self.plugins_dir.exists():
            return discovered

        # 遍历插件目录
        for item in self.plugins_dir.iterdir():
            # 包插件: 目录中存在__init__.py
            if item.is_dir() and (item / "__init__.py").exists():
                discovered.append(item.name)
            # 单文件插件: .py文件且不以_开头
            elif (
                item.is_file()
                and item.suffix == ".py"
                and not item.stem.startswith("_")
            ):
                discovered.append(item.stem)

        return discovered

    def load_plugin(self, plugin_name: str) -> bool:
        """
        加载单个插件

        加载指定插件并注册其提供的所有工具。
        加载成功后，插件的工具会自动注册到state.tools。

        参数:
            plugin_name: 插件名称

        返回:
            bool: 加载是否成功

        加载流程:
            1. 检查是否已加载
            2. 确定插件路径（包或单文件)
            3. 动态导入模块
            4. 查找PluginBase子类
            5. 实例化并调用on_load()
            6. 注册工具
            7. 记录插件信息

        错误处理:
            - 文件不存在: 记录错误信息
            - 无PluginBase子类: 记录错误信息
            - 其他异常: 记录错误信息
        """
        # 检查是否已加载
        if plugin_name in self.plugins and self.plugins[plugin_name].loaded:
            return True

        try:
            # 尝试作为包加载
            package_path = self.plugins_dir / plugin_name / "__init__.py"
            if package_path.exists():
                # 包形式: 使用 plugins.xxx 格式的模块名
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{plugin_name}", package_path
                )
            else:
                # 尝试作为单文件加载
                file_path = self.plugins_dir / f"{plugin_name}.py"
                if not file_path.exists():
                    raise FileNotFoundError(f"Plugin not found: {plugin_name}")
                # 单文件形式: 使用 plugins.xxx 格式的模块名
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{plugin_name}", file_path
                )

            # 创建模块对象
            module = importlib.util.module_from_spec(spec)
            # 执行模块代码
            spec.loader.exec_module(module)

            # 查找PluginBase子类
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                # 检查是否是PluginBase的子类（但不是PluginBase本身）
                if (
                    isinstance(attr, type)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                ):
                    plugin_class = attr
                    break

            if plugin_class is None:
                raise ValueError(f"No PluginBase subclass found in {plugin_name}")

            # 实例化插件
            instance = plugin_class()
            # 调用加载钩子
            instance.on_load()

            # 注册工具
            tools = instance.get_tools()
            for tool in tools:
                self._register_tool(tool)

            # 缓存插件实例
            self._instances[plugin_name] = instance

            # 记录插件信息
            self.plugins[plugin_name] = PluginInfo(
                name=instance.name,
                version=instance.version,
                description=instance.description,
                path=self.plugins_dir / plugin_name,
                instance=instance,
                loaded=True,
            )

            return True

        except Exception as e:
            # 记录加载错误
            self.plugins[plugin_name] = PluginInfo(
                name=plugin_name,
                version="",
                description="",
                path=self.plugins_dir / plugin_name,
                error=str(e),
            )
            return False

    def _register_tool(self, tool: ToolDefinition) -> None:
        """
        注册工具到内部状态

        将工具注册到state.tools字典中。
        这是一个内部方法，由load_plugin调用。

        参数:
            tool: 要注册的工具定义
        """
        self.state.register_tool(tool)

    def load_all(self) -> Dict[str, bool]:
        """
        加载所有发现的插件

        扫描并加载插件目录中的所有插件。

        返回:
            Dict[str, bool]: 加载结果 {插件名: 是否成功}

        示例:
            >>> results = manager.load_all()
            >>> print(results)  # {'excel_tools': True, 'table_tools': False}
        """
        results = {}
        for name in self.discover_plugins():
            results[name] = self.load_plugin(name)
        return results

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件

        卸载指定插件并注销其提供的所有工具。

        参数:
            plugin_name: 插件名称

        返回:
            bool: 卸载是否成功

        卸载流程:
            1. 检查插件是否存在
            2. 获取插件信息
            3. 注销所有工具
            4. 调用on_unload钩子
            5. 更新加载状态
        """
        # 检查插件是否存在
        if plugin_name not in self.plugins:
            return False

        info = self.plugins[plugin_name]

        if info.instance:
            # 移除所有工具
            for tool in info.instance.get_tools():
                self.state.unregister_tool(tool.name)

            # 调用卸载钩子
            info.instance.on_unload()

        # 更新加载状态
        info.loaded = False
        return True

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """
        获取工具定义

        根据名称获取已注册的工具定义。

        参数:
            name: 工具名称

        返回:
            Optional[ToolDefinition]: 工具定义，如果不存在则返回None
        """
        return self.tools.get(name)

    def get_all_tools(self) -> List[ToolDefinition]:
        """
        获取所有已注册的工具

        返回所有已注册工具的列表。

        返回:
            List[ToolDefinition]: 所有工具定义的列表
        """
        return list(self.tools.values())
