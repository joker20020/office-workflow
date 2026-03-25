# -*- coding: utf-8 -*-
"""
自定义节点基类模块
================

本模块定义了用户自定义节点的基类和辅助类:
- NodePort: 节点端口定义数据类
- NodeBase: 自定义节点抽象基类

设计理念:
用户可以通过继承NodeBase创建自定义节点，实现复杂的业务逻辑。
节点会自动注册到节点引擎，可在节点编辑器中使用。

与plugin_base中的区别:
- PluginBase: 用于工具插件，工具由execute函数直接执行
- NodeBase: 用于自定义节点，有完整的生命周期和状态管理
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class PortType(Enum):
    """
    端口数据类型枚举

    定义了节点端口支持的所有数据类型。
    与plugin_base.PortType保持一致。

    属性:
        ANY: 任意类型
        STRING: 字符串
        INTEGER: 整数
        FLOAT: 浮点数
        BOOLEAN: 布尔值
        DATAFRAME: Pandas DataFrame
        FILE: 文件路径
        LIST: 列表
        DICT: 字典
    """

    ANY = "any"
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    DATAFRAME = "dataframe"
    FILE = "file"
    LIST = "list"
    DICT = "dict"


@dataclass
class NodePort:
    """
    节点端口定义数据类

    定义节点的输入或输出端口。
    与plugin_base.PortDefinition类似，但用于NodeBase。

    属性:
        name: 端口名称
        type: 数据类型，默认ANY
        description: 端口描述
        default: 默认值
        required: 是否必需

    示例:
        >>> port = NodePort(
        ...     name="input_text",
        ...     type=PortType.STRING,
        ...     description="输入的文本内容"
        ... )
    """

    name: str  # 端口名称
    type: PortType = PortType.ANY  # 数据类型
    description: str = ""  # 端口描述
    default: Any = None  # 默认值
    required: bool = True  # 是否必需


class NodeBase(ABC):
    """
    自定义节点抽象基类

    用户继承此类创建自定义节点，实现复杂的业务逻辑。
    节点会自动注册到节点引擎，可在节点编辑器中使用。

    生命周期:
        1. setup(): 节点初始化时调用（可选）
        2. execute(): 执行节点逻辑（必须实现）
        3. cleanup(): 节点销毁时调用（可选）

    状态流转:
        idle -> running -> success/error

    类属性（子类必须定义）:
        node_type: 节点类型标识（唯一）
        display_name: 显示名称
        category: 分类
        icon: 图标
        description: 节点描述

    实例属性:
        inputs: 输入端口列表
        outputs: 输出端口列表

    运行时状态:
        _input_values: 输入值字典
        _output_values: 输出值字典
        _state: 当前状态
        _error: 错误信息

    核心方法:
        execute(**inputs) -> Dict[str, Any]: 抽象方法，必须实现
        get_input(name, default) -> Any: 获取输入值
        set_output(name, value): 设置输出值
        set_error(message): 设置错误状态

    内部方法（由引擎调用）:
        _set_inputs(values): 设置输入值
        _get_outputs() -> Dict: 获取输出值
        _run() -> bool: 执行节点

    示例:
        >>> class TextTransformNode(NodeBase):
        ...     node_type = "text_transform"
        ...     display_name = "文本转换"
        ...     category = "文本处理"
        ...     icon = "🔄"
        ...     description = "转换文本格式"
        ...
        ...     inputs = [
        ...         NodePort("text", PortType.STRING, "输入文本"),
        ...     ]
        ...     outputs = [
        ...         NodePort("result", PortType.STRING, "转换结果"),
        ...     ]
        ...
        ...     def execute(self, **inputs) -> Dict[str, Any]:
        ...         text = inputs.get("text", "")
        ...         return {"result": text.upper()}
    """

    # ==================== 节点元信息（子类必须定义）===================

    # 节点类型标识（唯一）
    node_type: str = ""
    # 显示名称
    display_name: str = ""
    # 分类
    category: str = "custom"
    # 图标（emoji）
    icon: str = "🔧"
    # 节点描述
    description: str = ""

    # ==================== 端口定义（子类可覆盖）===================

    # 输入端口列表
    inputs: List[NodePort] = field(default_factory=list)
    # 输出端口列表
    outputs: List[NodePort] = field(default_factory=list)

    # ==================== 初始化 ====================

    def __init__(self):
        """初始化节点"""
        # 输入值字典
        self._input_values: Dict[str, Any] = {}
        # 输出值字典
        self._output_values: Dict[str, Any] = {}
        # 当前状态: idle | running | success | error
        self._state: str = "idle"
        # 错误信息
        self._error: Optional[str] = None

    # ==================== 生命周期方法 ====================

    def setup(self) -> None:
        """
        节点初始化时调用

        可选实现，用于执行初始化操作。
        例如:
        - 加载配置文件
        - 初始化数据库连接
        - 准备资源

        默认实现为空。
        """
        pass

    def cleanup(self) -> None:
        """
        节点销毁时调用

        可选实现，用于执行清理操作。
        例如:
        - 关闭数据库连接
        - 释放资源
        - 保存状态

        默认实现为空。
        """
        pass

    # ==================== 核心方法（子类必须实现）===================

    @abstractmethod
    def execute(self, **inputs) -> Dict[str, Any]:
        """
        执行节点逻辑

        子类必须实现此方法，定义节点的核心业务逻辑。

        参数:
            **inputs: 输入端口的值，key为端口名称

        返回:
            Dict[str, Any]: 输出端口的值，key为输出端口名称

        示例:
            >>> def execute(self, **inputs):
            ...     text = inputs.get("text", "")
            ...     return {"result": text.upper()}

        注意:
            - 如果执行失败，应调用set_error()设置错误信息
            - 返回的字典key必须与outputs中定义的端口名匹配
        """
        pass

    # ==================== 辅助方法 ====================

    def get_input(self, name: str, default: Any = None) -> Any:
        """
        获取输入值

        根据端口名称获取输入值。

        参数:
            name: 端口名称
            default: 默认值（当端口不存在时返回）

        返回:
            Any: 输入值或默认值
        """
        return self._input_values.get(name, default)

    def set_output(self, name: str, value: Any) -> None:
        """
        设置输出值

        设置指定输出端口的值。

        参数:
            name: 输出端口名称
            value: 输出值
        """
        self._output_values[name] = value

    def set_error(self, message: str) -> None:
        """
        设置错误信息

        设置错误状态和错误信息。
        当节点执行失败时应调用此方法。

        参数:
            message: 错误信息
        """
        self._error = message
        self._state = "error"

    # ==================== 内部方法（由引擎调用）===================

    def _set_inputs(self, values: Dict[str, Any]) -> None:
        """
        设置输入值（引擎调用）

        由节点引擎调用，设置所有输入值。

        参数:
            values: 输入值字典 {端口名: 值}
        """
        self._input_values = values

    def _get_outputs(self) -> Dict[str, Any]:
        """
        获取输出值（引擎调用）

        由节点引擎调用，获取所有输出值。

        返回:
            Dict[str, Any]: 输出值字典
        """
        return self._output_values

    def _run(self) -> bool:
        """
        运行节点（引擎调用）

        由节点引擎调用，执行节点的完整流程。

        执行流程:
            1. 设置状态为running
            2. 清除错误信息
            3. 调用execute()执行业务逻辑
            4. 设置输出值
            5. 设置状态为success

        返回:
            bool: 执行是否成功
        """
        try:
            # 设置运行状态
            self._state = "running"
            self._error = None

            # 执行节点逻辑
            result = self.execute(**self._input_values)

            # 设置输出值
            if result:
                for key, value in result.items():
                    self._output_values[key] = value

            # 设置成功状态
            self._state = "success"
            return True

        except Exception as e:
            # 设置错误状态
            self._error = str(e)
            self._state = "error"
            return False

    # ==================== 节点信息 ====================

    def get_info(self) -> dict:
        """
        获取节点信息（用于UI显示）

        返回节点的完整信息，用于UI显示和序列化。

        返回:
            dict: 节点信息字典，包含:
                - type: 节点类型
                - name: 显示名称
                - category: 分类
                - icon: 图标
                - description: 描述
                - inputs: 输入端口列表
                - outputs: 输出端口列表
        """
        return {
            "type": self.node_type,
            "name": self.display_name,
            "category": self.category,
            "icon": self.icon,
            "description": self.description,
            "inputs": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "description": p.description,
                    "required": p.required,
                }
                for p in self.inputs
            ],
            "outputs": [
                {"name": p.name, "type": p.type.value, "description": p.description}
                for p in self.outputs
            ],
        }
