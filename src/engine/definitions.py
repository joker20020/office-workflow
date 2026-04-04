# -*- coding: utf-8 -*-
"""
节点定义模块

定义节点和端口的数据结构，用于：
- 声明节点类型
- 定义输入输出端口
- 提供执行函数接口
- Agent理解节点功能

使用方式：
    from src.engine.definitions import PortType, PortDefinition, NodeDefinition

    # 定义一个文本拼接节点
    def join_text(text1: str, text2: str, separator: str = " ") -> dict:
        return {"result": f"{text1}{separator}{text2}"}

    text_join_node = NodeDefinition(
        node_type="text.join",
        display_name="文本拼接",
        description="将两个文本拼接在一起",
        category="text",
        icon="🔗",
        inputs=[
            PortDefinition("text1", PortType.STRING, "第一个文本"),
            PortDefinition("text2", PortType.STRING, "第二个文本"),
            PortDefinition("separator", PortType.STRING, "分隔符", default=" ", required=False),
        ],
        outputs=[
            PortDefinition("result", PortType.STRING, "拼接结果"),
        ],
        execute=join_text,
    )
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


class PortType:
    """
    端口数据类型

    支持预定义类型和自定义类型字符串。
    - 预定义类型: PortType.STRING, PortType.INTEGER 等
    - 自定义类型: PortType("my.custom.type")

    类型兼容性规则:
    - ANY 类型可与任何类型连接
    - 相同类型可以连接
    - 不同类型不能连接（除非其中一个是 ANY）

    Example:
        >>> PortType.STRING.is_compatible_with(PortType.ANY)
        True
        >>> PortType.STRING.is_compatible_with(PortType.INTEGER)
        False
        >>> custom = PortType("custom.data")
        >>> custom.is_compatible_with(PortType("custom.data"))
        True
    """

    # 预定义类型（作为类属性，方便使用）
    ANY = "any"
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    DATAFRAME = "dataframe"
    FILE = "file"
    LIST = "list"
    DICT = "dict"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

    # 预定义类型颜色映射
    PRESET_COLORS: Dict[str, str] = {
        "any": "#9E9E9E",  # 灰色
        "str": "#4CAF50",  # 绿色
        "int": "#2196F3",  # 蓝色
        "float": "#9C27B0",  # 紫色
        "bool": "#FF9800",  # 橙色
        "dataframe": "#F44336",  # 红色
        "file": "#FFEB3B",  # 黄色
        "list": "#00BCD4",  # 青色
        "dict": "#E91E63",  # 粉色
        "image": "#8BC34A",  # 浅绿
        "audio": "#673AB7",  # 深紫
        "video": "#FF5722",  # 深橙
    }

    def __init__(self, value: str = "any"):
        """
        初始化端口类型

        Args:
            value: 类型标识字符串
        """
        if isinstance(value, PortType):
            self._value = value._value
        else:
            self._value = str(value)

    @property
    def value(self) -> str:
        """获取类型值"""
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"PortType({self._value!r})"

    def __eq__(self, other) -> bool:
        if isinstance(other, PortType):
            return self._value == other._value
        return self._value == other

    def __hash__(self) -> int:
        return hash(self._value)

    def is_compatible_with(self, other: "PortType") -> bool:
        """
        检查类型兼容性

        两个端口可以连接的条件：
        1. 任一端口类型为 ANY
        2. 两个端口类型完全相同

        Args:
            other: 目标端口类型

        Returns:
            是否兼容（可以连接）
        """
        if isinstance(other, str):
            other = PortType(other)

        # ANY 类型可以与任何类型连接
        if self._value == "any" or other._value == "any":
            return True

        # 类型必须完全匹配
        return self._value == other._value

    @property
    def color(self) -> str:
        """
        获取端口类型的显示颜色

        Returns:
            十六进制颜色字符串
        """
        # 预定义类型使用预设颜色
        if self._value in self.PRESET_COLORS:
            return self.PRESET_COLORS[self._value]

        # 自定义类型：基于类型字符串生成一致的颜色
        return self._generate_color(self._value)

    def _generate_color(self, type_str: str) -> str:
        """
        为自定义类型生成颜色

        使用类型字符串的哈希值生成一致的颜色

        Args:
            type_str: 类型字符串

        Returns:
            十六进制颜色字符串
        """
        # 使用哈希生成稳定的颜色
        hash_bytes = hashlib.md5(type_str.encode()).digest()

        # 生成 HSL 颜色，保持饱和度和亮度一致，只变化色相
        hue = (hash_bytes[0] * 360) // 256

        # 转换为 RGB (简化版，饱和度70%，亮度50%)
        h = hue / 60
        c = 0.7 * 0.5 * 2  # 饱和度 * 亮度
        x = c * (1 - abs(h % 2 - 1))
        m = 0.5 - c / 2

        if h < 1:
            r, g, b = c, x, 0
        elif h < 2:
            r, g, b = x, c, 0
        elif h < 3:
            r, g, b = 0, c, x
        elif h < 4:
            r, g, b = 0, x, c
        elif h < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)

        return f"#{r:02X}{g:02X}{b:02X}"

    @property
    def display_name(self) -> str:
        """获取类型的显示名称"""
        # 预定义类型的友好名称
        names = {
            "any": "任意",
            "str": "文本",
            "int": "整数",
            "float": "浮点数",
            "bool": "布尔值",
            "dataframe": "数据表",
            "file": "文件",
            "list": "列表",
            "dict": "字典",
            "image": "图像",
            "audio": "音频",
            "video": "视频",
        }
        return names.get(self._value, self._value)


@dataclass
class PortDefinition:
    """端口定义"""

    name: str
    type: PortType = PortType.ANY
    description: str = ""
    required: bool = True
    default: Any = None
    widget_type: Optional[str] = None  # 输入端口内联控件类型
    show_preview: bool = False  # 输出端口是否显示预览
    role: Optional[str] = None  # 端口角色: "branch"=分支门控, "feedback"=反馈回边, None=普通

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = PortType(self.type)


@dataclass
class NodeDefinition:
    """
    节点定义

    定义一种节点类型的完整描述，包括：
    - 元数据（类型标识、显示名称、描述）
    - 输入输出端口列表
    - 执行函数

    节点定义是节点类型的"蓝图"，用于：
    - 创建节点实例
    - UI渲染节点面板
    - Agent理解可用节点
    - 验证工作流连接

    Attributes:
        node_type: 节点类型标识（全局唯一，如 "text.join"）
        display_name: 显示名称（用于UI显示）
        description: 描述（Agent可理解）
        category: 分类（用于节点面板分组，如 "text", "math", "io"）
        icon: 图标（emoji或图标名称）
        inputs: 输入端口列表
        outputs: 输出端口列表
        execute: 执行函数（接收输入参数，返回输出字典）

    Example:
        >>> def join_text(text1: str, text2: str, separator: str = " ") -> dict:
        ...     return {"result": f"{text1}{separator}{text2}"}
        ...
        >>> node_def = NodeDefinition(
        ...     node_type="text.join",
        ...     display_name="文本拼接",
        ...     description="将两个文本拼接在一起",
        ...     category="text",
        ...     icon="🔗",
        ...     inputs=[
        ...         PortDefinition("text1", PortType.STRING, "第一个文本"),
        ...         PortDefinition("text2", PortType.STRING, "第二个文本"),
        ...         PortDefinition("separator", PortType.STRING, "分隔符", default=" ", required=False),
        ...     ],
        ...     outputs=[
        ...         PortDefinition("result", PortType.STRING, "拼接结果"),
        ...     ],
        ...     execute=join_text,
        ... )
        >>> node_def.node_type
        'text.join'
        >>> node_def.get_input_port("text1").type
        <PortType.STRING: 'str'>
    """

    # 元数据
    node_type: str  # 节点类型标识（唯一）
    display_name: str  # 显示名称
    description: str = ""  # 描述（Agent可用此理解节点功能）
    category: str = "general"  # 分类
    icon: str = "🔧"  # 图标

    # 端口定义
    inputs: List[PortDefinition] = field(default_factory=list)
    outputs: List[PortDefinition] = field(default_factory=list)

    # 执行函数
    execute: Optional[Callable[..., Dict[str, Any]]] = field(default=None, repr=False)

    def get_input_port(self, name: str) -> Optional[PortDefinition]:
        """
        获取指定名称的输入端口

        Args:
            name: 端口名称

        Returns:
            端口定义，如果不存在则返回 None

        Example:
            >>> node_def.get_input_port("text1")
            PortDefinition(name='text1', type=<PortType.STRING: 'str'>, ...)
        """
        for port in self.inputs:
            if port.name == name:
                return port
        return None

    def get_output_port(self, name: str) -> Optional[PortDefinition]:
        """
        获取指定名称的输出端口

        Args:
            name: 端口名称

        Returns:
            端口定义，如果不存在则返回 None
        """
        for port in self.outputs:
            if port.name == name:
                return port
        return None

    def validate_inputs(self, inputs: Dict[str, Any]) -> List[str]:
        """
        验证输入值

        检查：
        1. 所有必需的输入是否都有值
        2. 类型是否匹配（可选，运行时检查）

        Args:
            inputs: 输入参数字典

        Returns:
            错误消息列表（空列表表示验证通过）

        Example:
            >>> errors = node_def.validate_inputs({"text1": "hello"})
            >>> if errors:
            ...     print("验证失败:", errors)
        """
        errors = []

        for port in self.inputs:
            if port.required and port.name not in inputs:
                if port.default is None:
                    errors.append(f"缺少必需的输入: {port.name}")
                # 如果有默认值，不报错

        return errors

    def get_default_inputs(self) -> Dict[str, Any]:
        """
        获取所有输入端口的默认值

        Returns:
            端口名到默认值的映射

        Example:
            >>> defaults = node_def.get_default_inputs()
            >>> defaults["separator"]
            ' '
        """
        defaults = {}
        for port in self.inputs:
            if port.default is not None:
                defaults[port.name] = port.default
        return defaults

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（用于序列化和Agent理解）

        Returns:
            包含节点定义信息的字典

        Note:
            不包含 execute 函数，因为函数不可序列化
        """
        return {
            "node_type": self.node_type,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "icon": self.icon,
            "inputs": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "widget_type": p.widget_type,
                    "role": p.role,
                }
                for p in self.inputs
            ],
            "outputs": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "description": p.description,
                    "role": p.role,
                }
                for p in self.outputs
            ],
        }

    def __repr__(self) -> str:
        """节点定义的字符串表示"""
        return f"<NodeDefinition {self.node_type} '{self.display_name}'>"
