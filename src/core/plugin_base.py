# -*- coding: utf-8 -*-
"""
插件基类模块
============

本模块定义了插件系统的核心接口和数据结构:
- PortType: 端口数据类型枚举
- PortDefinition: 端口定义数据类
- ToolDefinition: 工具定义数据类（同时服务AI对话和节点流）
- PluginBase: 插件抽象基类

设计原则:
- 统一Schema: 工具定义同时服务AI对话和节点流
- 插件优先: 所有工具以插件形式注册，便于扩展
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Optional
from enum import Enum


class PortType(Enum):
    """
    端口数据类型枚举

    定义了节点端口支持的所有数据类型，用于:
    - 类型检查: 确保连接的端口类型兼容
    - UI渲染: 不同类型显示不同颜色
    - 数据转换: 在节点间传递数据时进行类型适配

    属性:
        ANY: 任意类型，不进行类型检查
        STRING: 字符串类型
        INTEGER: 整数类型
        FLOAT: 浮点数类型
        BOOLEAN: 布尔类型
        DATAFRAME: Pandas DataFrame类型（表格数据）
        FILE: 文件路径类型
        LIST: 列表类型
        DICT: 字典类型
    """

    ANY = "any"  # 任意类型
    STRING = "str"  # 字符串
    INTEGER = "int"  # 整数
    FLOAT = "float"  # 浮点数
    BOOLEAN = "bool"  # 布尔值
    DATAFRAME = "dataframe"  # DataFrame（表格数据）
    FILE = "file"  # 文件路径
    LIST = "list"  # 列表
    DICT = "dict"  # 字典


@dataclass
class PortDefinition:
    """
    端口定义数据类

    定义节点的输入或输出端口，包含端口的名称、类型、描述等信息。
    用于ToolDefinition中定义工具的输入输出规范。

    属性:
        name: 端口名称，用于在代码中引用此端口
        type: 端口数据类型，默认为ANY（任意类型）
        description: 端口描述，用于UI显示和AI理解
        required: 是否为必需参数，默认为True
        default: 默认值，当required=False时可提供默认值

    示例:
        >>> port = PortDefinition(
        ...     name="file_path",
        ...     type=PortType.FILE,
        ...     description="Excel文件路径",
        ...     required=True
        ... )
    """

    name: str  # 端口名称
    type: PortType = PortType.ANY  # 数据类型，默认任意类型
    description: str = ""  # 端口描述
    required: bool = True  # 是否必需
    default: Any = None  # 默认值


@dataclass
class ToolDefinition:
    """
    工具定义数据类 - 同时服务AI对话和节点流

    这是插件系统的核心数据结构，定义了一个完整的工具。
    一个工具可以:
    1. 被AI Agent调用（通过OpenAI兼容的JSON Schema）
    2. 作为节点流中的一个节点使用

    属性:
        name: 工具唯一标识符（用于代码中引用）
        display_name: 显示名称（用于UI显示）
        description: 工具描述（AI用此理解工具功能）
        category: 工具分类，默认为"general"
        icon: 工具图标（emoji或图标名称）
        inputs: 输入端口定义列表
        outputs: 输出端口定义列表
        execute: 执行函数，接收kwargs参数，返回执行结果

    方法:
        get_json_schema(): 生成OpenAI兼容的JSON Schema
        _port_type_to_json(): 将PortType转换为JSON Schema类型

    示例:
        >>> def my_execute(a: int, b: int) -> int:
        ...     return a + b
        >>> tool = ToolDefinition(
        ...     name="add",
        ...     display_name="加法",
        ...     description="计算两个数的和",
        ...     inputs=[
        ...         PortDefinition("a", PortType.INTEGER, "第一个数"),
        ...         PortDefinition("b", PortType.INTEGER, "第二个数"),
        ...     ],
        ...     outputs=[
        ...         PortDefinition("result", PortType.INTEGER, "计算结果"),
        ...     ],
        ...     execute=my_execute
        ... )
    """

    name: str  # 工具唯一标识
    display_name: str  # 显示名称
    description: str  # 工具描述（AI用此理解功能）
    category: str = "general"  # 分类
    icon: str = "🔧"  # 图标

    # 输入输出定义
    inputs: List[PortDefinition] = field(default_factory=list)
    outputs: List[PortDefinition] = field(default_factory=list)

    # 执行函数（非响应式）
    execute: Callable | None = field(default=None, repr=False)

    def get_json_schema(self) -> dict:
        """
        生成OpenAI兼容的JSON Schema

        将工具定义转换为OpenAI Function Calling兼容的JSON Schema格式。
        用于AI Agent调用工具时的参数验证和类型提示。

        返回:
            dict: OpenAI兼容的JSON Schema字典，包含:
                - type: "function"
                - function.name: 工具名称
                - function.description: 工具描述
                - function.parameters: 参数定义（JSON Schema格式）

        示例:
            >>> schema = tool.get_json_schema()
            >>> print(schema["function"]["name"])
            "add"
        """
        # 构建参数属性
        properties = {}
        required = []

        for inp in self.inputs:
            # 为每个输入端口生成属性定义
            properties[inp.name] = {
                "type": self._port_type_to_json(inp.type),
                "description": inp.description,
            }
            # 如果有默认值，添加到schema
            if inp.default is not None:
                properties[inp.name]["default"] = inp.default
            # 如果是必需参数，添加到required列表
            if inp.required:
                required.append(inp.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @staticmethod
    def _port_type_to_json(pt: PortType) -> str:
        """
        将PortType转换为JSON Schema类型

        用于生成OpenAI兼容的参数定义。
        将内部端口类型映射到标准的JSON Schema类型。

        参数:
            pt: 端口类型枚举值

        返回:
            str: JSON Schema类型字符串

        类型映射:
            - STRING -> "string"
            - INTEGER -> "integer"
            - FLOAT -> "number"
            - BOOLEAN -> "boolean"
            - LIST -> "array"
            - DICT -> "object"
            - ANY -> "object"
            - DATAFRAME -> "object"
            - FILE -> "string"
        """
        # 端口类型到JSON Schema类型的映射表
        mapping = {
            PortType.STRING: "string",
            PortType.INTEGER: "integer",
            PortType.FLOAT: "number",
            PortType.BOOLEAN: "boolean",
            PortType.LIST: "array",
            PortType.DICT: "object",
            PortType.ANY: "object",
            PortType.DATAFRAME: "object",
            PortType.FILE: "string",
        }
        return mapping.get(pt, "object")


class PluginBase(ABC):
    """
    插件抽象基类

    所有插件必须继承此类，并实现get_tools()方法。
    插件用于封装一组相关的工具，便于管理和扩展。

    生命周期:
        1. 插件被PluginManager发现
        2. PluginManager加载插件，调用on_load()
        3. 插件通过get_tools()返回工具列表
        4. 工具被注册到Toolkit和NodeEngine
        5. 插件卸载时，on_unload()被调用

    类属性:
        name: 插件名称（唯一标识）
        version: 插件版本号
        description: 插件描述
        author: 插件作者

    抽象方法:
        get_tools(): 返回插件提供的所有工具定义

    可选方法:
        on_load(): 插件加载时调用，用于初始化
        on_unload(): 插件卸载时调用，用于清理资源

    示例:
        >>> class ExcelToolsPlugin(PluginBase):
        ...     name = "excel_tools"
        ...     version = "1.0.0"
        ...     description = "Excel处理工具"
        ...     author = "Office Team"
        ...
        ...     def get_tools(self) -> List[ToolDefinition]:
        ...         return [self._create_read_tool()]
        ...
        ...     def _create_read_tool(self) -> ToolDefinition:
        ...         def read_excel(file_path: str) -> dict:
        ...             import pandas as pd
        ...             return pd.read_excel(file_path).to_dict()
        ...
        ...         return ToolDefinition(
        ...             name="read_excel",
        ...             display_name="读取Excel",
        ...             description="读取Excel文件内容",
        ...             inputs=[PortDefinition("file_path", PortType.FILE, "文件路径")],
        ...             outputs=[PortDefinition("data", PortType.DICT, "表格数据")],
        ...             execute=read_excel,
        ...         )
    """

    # 插件元信息（子类必须定义）
    name: str = "unknown"  # 插件名称
    version: str = "1.0.0"  # 版本号
    description: str = ""  # 插件描述
    author: str = ""  # 作者

    @abstractmethod
    def get_tools(self) -> List[ToolDefinition]:
        """
        返回插件提供的所有工具定义

        子类必须实现此方法，返回该插件提供的所有工具。
        每个工具都是一个ToolDefinition实例。

        返回:
            List[ToolDefinition]: 工具定义列表

        示例:
            >>> def get_tools(self) -> List[ToolDefinition]:
            ...     return [
            ...         self._create_tool1(),
            ...         self._create_tool2(),
            ...     ]
        """
        pass

    def on_load(self):
        """
        插件加载时调用

        可选实现。用于执行插件初始化操作，例如:
        - 加载配置文件
        - 初始化资源
        - 建立数据库连接

        默认实现为空，子类可根据需要覆盖。
        """
        pass

    def on_unload(self):
        """
        插件卸载时调用

        可选实现。用于执行插件清理操作，例如:
        - 关闭数据库连接
        - 释放资源
        - 保存状态

        默认实现为空，子类可根据需要覆盖。
        """
        pass
