# -*- coding: utf-8 -*-
"""节点信息格式化器 - 将NodeDefinition转换为Agent可理解的文本"""

from typing import List, Union

from src.engine.definitions import NodeDefinition


class NodeFormatter:
    """将节点定义格式化为Agent可理解的文本描述"""

    @staticmethod
    def format_for_agent(node_def: Union[NodeDefinition, dict]) -> str:
        """
        格式化单个节点定义为可读文本

        Args:
            node_def: 节点定义（NodeDefinition对象或字典）

        Returns:
            格式化后的文本
        """
        if isinstance(node_def, dict):
            node_type = node_def.get("node_type", "未知")
            display_name = node_def.get("display_name", "未知")
            description = node_def.get("description", "")
            category = node_def.get("category", "未分类")
            icon = node_def.get("icon", "")
            inputs = node_def.get("inputs", [])
            outputs = node_def.get("outputs", [])
        else:
            node_type = node_def.node_type
            display_name = node_def.display_name
            description = node_def.description
            category = node_def.category
            icon = node_def.icon
            inputs = node_def.inputs
            outputs = node_def.outputs

        lines = [
            f"节点类型: {node_type}",
            f"名称: {display_name}",
            f"描述: {description}",
            f"分类: {category}",
            f"图标: {icon}",
            "输入端口:",
        ]

        for port in inputs:
            if isinstance(port, dict):
                port_name = port.get("name", "未知")
                port_type = port.get("type", "any")
                port_desc = port.get("description", "")
                required = port.get("required", False)
                default = port.get("default")
            else:
                port_name = port.name
                port_type = port.type.value if hasattr(port.type, "value") else str(port.type)
                port_desc = port.description
                required = port.required
                default = port.default

            required_mark = "[必需]" if required else f"[可选, 默认: {default}]"
            lines.append(f"  - {port_name} ({port_type}): {port_desc} {required_mark}")

        lines.append("输出端口:")
        for port in outputs:
            if isinstance(port, dict):
                port_name = port.get("name", "未知")
                port_type = port.get("type", "any")
                port_desc = port.get("description", "")
            else:
                port_name = port.name
                port_type = port.type.value if hasattr(port.type, "value") else str(port.type)
                port_desc = port.description
            lines.append(f"  - {port_name} ({port_type}): {port_desc}")

        return "\n".join(lines)

    @staticmethod
    def format_all_for_agent(node_defs: List[NodeDefinition]) -> str:
        """
        格式化所有节点定义为可读文本

        Args:
            node_defs: 节点定义列表

        Returns:
            格式化后的文本
        """
        sections = []
        sections.append(f"共有 {len(node_defs)} 个可用节点:\n")

        for node_def in node_defs:
            sections.append(NodeFormatter.format_for_agent(node_def))
            sections.append("")

        return "\n".join(sections)

    @staticmethod
    def get_system_prompt(node_defs: List[NodeDefinition]) -> str:
        """
        生成Agent的系统提示词

        Args:
            node_defs: 节点定义列表

        Returns:
            系统提示词文本
        """
        prompt = """你是一个工作流助手,帮助用户设计和创建节点工作流。

你可以访问以下工具来操作工作流:
1. create_node: 创建节点
2. connect_nodes: 连接节点
3. set_node_value: 设置节点值
4. execute_workflow: 执行工作流
5. list_nodes: 列出所有节点
6. get_node_types: 获取可用节点类型

可用节点类型:
"""
        prompt += NodeFormatter.format_all_for_agent(node_defs)
        prompt += """
请根据用户需求,使用合适的工具来创建和管理工作流。

注意事项:
- 创建节点时,请使用合理的坐标位置,避免节点重叠
- 连接节点时,确保端口类型匹配
- 执行工作流前,建议先验证工作流

回复格式:
- 对于简单问题,直接回答
- 对于工作流操作,先说明操作,再执行
- 对于错误,给出清晰的错误信息
"""
        return prompt
