# -*- coding: utf-8 -*-
"""Mock node definitions for testing"""

from src.engine.definitions import NodeDefinition, PortDefinition, PortType


def mock_process(text: str) -> dict:
    """Mock process function"""
    return {"result": text.upper()}


mock_process_definition = NodeDefinition(
    node_type="mock.process",
    display_name="Mock Process",
    description="Mock node for testing",
    category="test",
    icon="🧪",
    inputs=[
        PortDefinition("text", PortType.STRING, "Input text"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "Processed text"),
    ],
    execute=mock_process,
)


def mock_transform(value: int, multiplier: int = 2) -> dict:
    """Mock transform function"""
    return {"output": value * multiplier}


mock_transform_definition = NodeDefinition(
    node_type="mock.transform",
    display_name="Mock Transform",
    description="Mock transform node for testing",
    category="test",
    icon="🔧",
    inputs=[
        PortDefinition("value", PortType.INTEGER, "Input value"),
        PortDefinition("multiplier", PortType.INTEGER, "Multiplier", default=2, required=False),
    ],
    outputs=[
        PortDefinition("output", PortType.INTEGER, "Output value"),
    ],
    execute=mock_transform,
)
