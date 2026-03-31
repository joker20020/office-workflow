import os
import sys

import pytest

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontMetrics

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.engine.node_graph import Node
from src.ui.node_editor.node_item import NodeGraphicsItem
from src.ui.node_editor.port_item import PortGraphicsItem


@pytest.fixture(scope="session", autouse=True)
def _ensure_app():
    # Ensure a QApplication exists for PySide widgets
    app = QApplication.instance()
    if app is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication(sys.argv)
    yield app


def _build_node_and_item(defn: NodeDefinition, inputs: list, outputs: list) -> NodeGraphicsItem:
    node = Node(id="node-test", node_type=defn.node_type, position=(0.0, 0.0))
    item = NodeGraphicsItem(node, defn)
    return item


def test_height_calculation_no_extra_padding():
    inputs = [PortDefinition("in1", PortType.STRING, "input1"), PortDefinition("in2", PortType.STRING, "input2")]
    outputs = [PortDefinition("out1", PortType.STRING, "output1")]
    definition = NodeDefinition(node_type="test.node", display_name="Test Node", inputs=inputs, outputs=outputs)
    node = Node(id="node-1", node_type=definition.node_type, position=(0.0, 0.0))
    item = NodeGraphicsItem(node, definition)

    expected = item.HEADER_HEIGHT + (len(inputs) + len(outputs)) * (item.PORT_HEIGHT + item.PORT_SPACING)
    assert item._height == expected


def test_output_ports_position_respects_width_change():
    inputs = [PortDefinition("in1", PortType.STRING, "input1")]
    outputs = [PortDefinition("out1", PortType.STRING, "output1")]
    definition = NodeDefinition(node_type="test.node.simple", display_name="Test Node", inputs=inputs, outputs=outputs)
    node = Node(id="node-2", node_type=definition.node_type, position=(0.0, 0.0))
    item = NodeGraphicsItem(node, definition)

    for port_def in outputs:
        port_item = item.get_port_item(port_def.name)
        assert port_item is not None
        expected_x = item._width - item.PADDING - PortGraphicsItem.PORT_RADIUS
        assert int(port_item.pos().x()) == int(expected_x)


def test_width_adapts_to_widget_width():
    # Define an input with an inline text widget
    inputs = [PortDefinition("long_input_name", PortType.STRING, "input", widget_type="text")]
    outputs = [PortDefinition("out", PortType.STRING, "output")]
    definition = NodeDefinition(node_type="test.node.widget", display_name="Test Node Widget", inputs=inputs, outputs=outputs)
    node = Node(id="node-3", node_type=definition.node_type, position=(0.0, 0.0))
    item = NodeGraphicsItem(node, definition)

    # Compute expected width based on internal algorithm
    font = QFont()
    font.setPointSize(9)
    fm = QFontMetrics(font)
    max_port_name_width = 0
    for p in inputs + outputs:
        w = fm.horizontalAdvance(p.name)
        max_port_name_width = max(max_port_name_width, w)

    max_widget_width = 0
    for proxy in item._widget_proxies.values():
        w = proxy.widget.sizeHint().width()
        if w > max_widget_width:
            max_widget_width = w
    for proxy in item._output_widget_proxies.values():
        w = proxy.widget.sizeHint().width()
        if w > max_widget_width:
            max_widget_width = w

    expected_width = max(
        item.MIN_WIDTH,
        item.PADDING + PortGraphicsItem.PORT_RADIUS * 2 + max_port_name_width + 10 + max_widget_width + item.PADDING,
    )
    assert item._width == expected_width
