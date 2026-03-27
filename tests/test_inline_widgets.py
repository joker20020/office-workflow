# -*- coding: utf-8 -*-
"""
内联控件单元测试

测试内联控件的功能：
- 各种类型的控件创建
- 值变化信号
- 启用/禁用状态
- 节点项集成

运行方式:
    uv run pytest -xvs tests/test_inline_widgets.py
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# 确保 QApplication 在导入模块之前就存在
# PySide6 要求在创建任何 QWidget 之前必须有 QApplication
if QApplication.instance() is None:
    QApplication([])

from src.engine.definitions import PortDefinition, PortType
from src.ui.node_editor.widgets import (
    TextLineEdit,
    NumberSpinBox,
    BooleanCheckBox,
    DropdownComboBox,
    FilePickerButton,
    OutputTextLabel,
    OutputNumberLabel,
    OutputDataPreview,
    create_input_widget,
    create_output_widget,
    InlineWidgetProxy,
    OutputWidgetProxy,
)


# 确保 QApplication 实例存在
@pytest.fixture(scope="session")
def qapp():
    """创建 QApplication fixture"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestInlineWidgets:
    """内联控件测试类"""

    def test_text_line_edit(self):
        """测试文本输入控件"""
        port_def = PortDefinition(
            name="test_text",
            type=PortType.STRING,
            description="测试文本输入",
            default="默认值",
        )

        widget = TextLineEdit(port_def)

        # 测试默认值
        assert widget.get_value() == "默认值"

        # 测试设置值
        widget.set_value("Hello")
        assert widget.get_value() == "Hello"

        # 测试值变化信号
        values_changed = []

        def on_value_changed(value):
            values_changed.append(value)

        widget._line_edit.setText("Changed")
        widget._line_edit.setText("World")

        assert len(values_changed) == 2
        assert values_changed[-1] == "World"

    def test_number_spin_box(self):
        """测试数字输入控件（整数）"""
        port_def = PortDefinition(
            name="test_int",
            type=PortType.INTEGER,
            description="测试整数输入",
            default=42,
        )

        widget = NumberSpinBox(port_def)

        # 测试默认值
        assert widget.get_value() == 42

        # 测试设置值
        widget.set_value(100)
        assert widget.get_value() == 100

        # 测试值变化信号
        values_changed = []

        def on_value_changed(value):
            values_changed.append(value)

        widget._spin_box.setValue(200)

        assert len(values_changed) == 1
        assert values_changed[-1] == 200

    def test_number_spin_box_float(self):
        """测试数字输入控件（浮点数）"""
        port_def = PortDefinition(
            name="test_float",
            type=PortType.FLOAT,
            description="测试浮点数输入",
            default=3.14,
        )

        widget = NumberSpinBox(port_def)

        # 测试默认值
        assert widget.get_value() == 3.14

        # 测试设置值
        widget.set_value(2.718)
        assert widget.get_value() == 2.718

        # 测试值变化信号
        values_changed = []

        def on_value_changed(value):
            values_changed.append(value)

        widget._spin_box.setValue(1.414)

        assert len(values_changed) == 1
        assert values_changed[-1] == 1.414

    def test_boolean_check_box(self):
        """测试布尔值复选框"""
        port_def = PortDefinition(
            name="test_bool",
            type=PortType.BOOLEAN,
            description="测试布尔值",
            default=True,
        )

        widget = BooleanCheckBox(port_def)

        # 测试默认值
        assert widget.get_value() == True

        # 测试设置值
        widget.set_value(False)
        assert widget.get_value() == False

        # 测试值变化信号
        values_changed = []

        def on_value_changed(value):
            values_changed.append(value)

        widget._checkbox.setChecked(True)

        assert len(values_changed) == 1
        assert values_changed[-1] == True

    def test_dropdown_combo_box(self):
        """测试下拉选择框"""
        port_def = PortDefinition(
            name="test_dropdown",
            type=PortType.STRING,
            description="测试下拉选择",
            default="option1",
            widget_type="dropdown",
        )

        widget = DropdownComboBox(port_def)

        # 测试默认值
        assert widget.get_value() == "option1"

        # 测试设置值
        widget.set_value("option2")
        assert widget.get_value() == "option2"

        # 测试值变化信号
        values_changed = []

        def on_value_changed(value):
            values_changed.append(value)

        widget._combo_box.setCurrentIndex(1)

        assert len(values_changed) == 1
        assert values_changed[-1] == "option2"

    def test_file_picker_button(self):
        """测试文件选择按钮"""
        port_def = PortDefinition(
            name="test_file",
            type=PortType.FILE,
            description="测试文件选择",
        )

        widget = FilePickerButton(port_def)

        # 测试设置值（模拟选择文件）
        widget.set_value("/path/to/file.txt")
        assert widget.get_value() == "/path/to/file.txt"

    def test_output_text_label(self):
        """测试输出文本标签"""
        port_def = PortDefinition(
            name="test_output",
            type=PortType.STRING,
            description="测试输出",
        )

        widget = OutputTextLabel(port_def)

        # 测试初始状态
        assert widget.get_value() is None

        # 测试设置值
        widget.set_value("Hello World")
        assert widget.get_value() == "Hello World"

    def test_output_number_label(self):
        """测试输出数字标签"""
        port_def = PortDefinition(
            name="test_output_num",
            type=PortType.INTEGER,
            description="测试输出数字",
        )

        widget = OutputNumberLabel(port_def)

        # 测试初始状态
        assert widget.get_value() is None

        # 测试设置值
        widget.set_value(12345)
        assert widget.get_value() == 12345

    def test_output_data_preview(self):
        """测试输出数据预览"""
        port_def = PortDefinition(
            name="test_output_data",
            type=PortType.LIST,
            description="测试输出数据",
        )

        widget = OutputDataPreview(port_def)

        # 测试列表预览
        widget.set_value([1, 2, 3])
        # OutputDataPreview doesn't return value, just displays it
        # We can verify the internal label was updated
        assert widget._type_label.text() == "list"

    def test_create_input_widget_factory(self):
        """测试 create_input_widget 工厂函数"""
        # 文本类型
        port_def = PortDefinition(name="text", type=PortType.STRING)
        widget = create_input_widget(port_def)
        assert isinstance(widget, TextLineEdit)

        # 整数类型
        port_def = PortDefinition(name="num", type=PortType.INTEGER)
        widget = create_input_widget(port_def)
        assert isinstance(widget, NumberSpinBox)

        # 布尔类型
        port_def = PortDefinition(name="flag", type=PortType.BOOLEAN)
        widget = create_input_widget(port_def)
        assert isinstance(widget, BooleanCheckBox)

        # 下拉选择类型
        port_def = PortDefinition(
            name="choice",
            type=PortType.STRING,
            widget_type="dropdown",
        )
        widget = create_input_widget(port_def)
        assert isinstance(widget, DropdownComboBox)

        # 文件类型
        port_def = PortDefinition(name="file", type=PortType.FILE)
        widget = create_input_widget(port_def)
        assert isinstance(widget, FilePickerButton)

        # 未知类型，默认回退到文本输入
        port_def = PortDefinition(name="unknown", type=PortType.ANY)
        widget = create_input_widget(port_def)
        assert isinstance(widget, TextLineEdit)  # 默认回退到文本输入

    def test_create_output_widget_factory(self):
        """测试 create_output_widget 工厂函数"""
        # 字符串类型
        port_def = PortDefinition(name="output", type=PortType.STRING)
        widget = create_output_widget(port_def)
        assert isinstance(widget, OutputTextLabel)

        # 数字类型
        port_def = PortDefinition(name="output_num", type=PortType.INTEGER)
        widget = create_output_widget(port_def)
        assert isinstance(widget, OutputNumberLabel)

        # 列表/字典/数据表类型
        port_def = PortDefinition(name="output_data", type=PortType.LIST)
        widget = create_output_widget(port_def)
        assert isinstance(widget, OutputDataPreview)

    def test_inline_widget_proxy(self):
        """测试内联控件代理"""
        port_def = PortDefinition(
            name="test_widget",
            type=PortType.STRING,
            default="default",
        )

        widget = TextLineEdit(port_def)
        proxy = InlineWidgetProxy(widget)

        # 测试代理包装了正确的控件
        assert proxy.widget is widget

        # 测试获取/设置值
        assert proxy.get_value() == "default"
        proxy.set_value("test value")
        assert proxy.get_value() == "test value"

        # 测试启用/禁用
        proxy.set_enabled(False)
        assert not proxy.widget._is_enabled

        proxy.set_enabled(True)
        assert proxy.widget._is_enabled

        # 测试清理
        proxy.cleanup()
        assert proxy.widget is None


class TestOutputWidgetProxy:
    """测试输出控件代理"""

    def test_output_widget_proxy(self):
        """测试输出控件代理"""
        port_def = PortDefinition(
            name="test_output",
            type=PortType.STRING,
        )

        widget = OutputTextLabel(port_def)
        proxy = OutputWidgetProxy(widget)

        # 测试代理包装了正确的控件
        assert proxy.widget is widget

        # 测试设置值
        proxy.set_value("test output")
        assert proxy.get_value() == "test output"

        # 测试清除
        proxy.clear()
        assert "—" in widget._label.text()

        # 测试清理
        proxy.cleanup()
        assert proxy.widget is None


if __name__ == "__main__":
    pytest.main()
