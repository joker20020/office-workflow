# -*- coding: utf-8 -*-
"""
文本处理插件

提供文本相关的节点：
- 文本输入：手动输入文本
- 文本拼接：将多个文本拼接
- 文本大小写：转换大小写
- 文本替换：替换文本内容
"""

from src.core.plugin_base import PluginBase
from src.core.permission_manager import Permission, PermissionSet
from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.utils.logger import get_logger

_logger = get_logger(__name__)

# 节点定义列表
TEXT_NODES = [
    # 文本输入节点
    NodeDefinition(
        node_type="text.input",
        display_name="文本输入",
        description="手动输入文本值",
        category="text",
        icon="📝",
        inputs=[],
        outputs=[
            PortDefinition("output", PortType.STRING, "输出的文本", widget_type="text"),
        ],
        execute=lambda text="": {"output": text},
    ),
    # 文本拼接节点
    NodeDefinition(
        node_type="text.join",
        display_name="文本拼接",
        description="将两个文本拼接在一起",
        category="text",
        icon="🔗",
        inputs=[
            PortDefinition("text1", PortType.STRING, "第一个文本", widget_type="text"),
            PortDefinition("text2", PortType.STRING, "第二个文本", widget_type="text"),
            PortDefinition("separator", PortType.STRING, "分隔符", widget_type="text"),
        ],
        outputs=[
            PortDefinition("result", PortType.STRING, "拼接结果"),
        ],
        execute=lambda text1="", text2="", separator=" ": {"result": f"{text1}{separator}{text2}"},
    ),
    # 文本大小写转换节点
    NodeDefinition(
        node_type="text.upper",
        display_name="转大写",
        description="将文本转换为大写",
        category="text",
        icon="⬆️",
        inputs=[
            PortDefinition("text", PortType.STRING, "输入文本", widget_type="text"),
        ],
        outputs=[
            PortDefinition("result", PortType.STRING, "大写文本"),
        ],
        execute=lambda text="": {"result": text.upper()},
    ),
    NodeDefinition(
        node_type="text.lower",
        display_name="转小写",
        description="将文本转换为小写",
        category="text",
        icon="⬇️",
        inputs=[
            PortDefinition("text", PortType.STRING, "输入文本", widget_type="text"),
        ],
        outputs=[
            PortDefinition("result", PortType.STRING, "小写文本"),
        ],
        execute=lambda text="": {"result": text.lower()},
    ),
    # 文本替换节点
    NodeDefinition(
        node_type="text.replace",
        display_name="文本替换",
        description="替换文本中的内容",
        category="text",
        icon="🔄",
        inputs=[
            PortDefinition("text", PortType.STRING, "原文本", widget_type="text"),
            PortDefinition("old", PortType.STRING, "要替换的内容", widget_type="text"),
            PortDefinition("new", PortType.STRING, "替换为", widget_type="text"),
        ],
        outputs=[
            PortDefinition("result", PortType.STRING, "替换后的文本"),
        ],
        execute=lambda text="", old="", new="": {"result": text.replace(old, new)},
    ),
]


class TextProcessingPlugin(PluginBase):
    """
    文本处理插件

    提供文本相关的节点功能。

    Nodes:
        - text.input: 文本输入
        - text.join: 文本拼接
        - text.upper: 转大写
        - text.lower: 转小写
        - text.replace: 文本替换

    Example:
        # 使用文本拼接节点
        graph.add_node("text.join")
        node.widget_values = {"text1": "Hello", "text2": "World", "separator": " "}
        # 执行后 outputs["result"] = "Hello World"
    """

    name = "text_processing"
    version = "1.0.0"
    description = "提供文本处理相关的节点"
    author = "OfficeTools"

    permissions = PermissionSet.from_list(
        [
            Permission.NODE_REGISTER,
        ]
    )

    def on_load(self, context):
        """插件加载时注册节点"""
        # 直接注册节点定义
        for node_def in TEXT_NODES:
            context.node_engine.register_node_type(node_def)
            _logger.info(f"注册节点: {node_def.node_type}")

    def on_unload(self):
        """插件卸载时注销节点"""
        # 节点会随引擎销毁自动清理
        pass
