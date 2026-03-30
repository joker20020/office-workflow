# -*- coding: utf-8 -*-
"""
节点内联控件模块

提供节点端口的内联控件，包括：
- 输入控件：文本输入、数字输入、复选框、下拉选择、文件选择
- 输出预览：文本输出、数字输出、数据预览、错误显示

使用方式：
    from src.ui.node_editor.widgets import create_input_widget, create_output_widget

    # 创建输入控件
    widget = create_input_widget(port_def)
    widget.value_changed.connect(on_value_changed)

    # 创建输出预览
    output = create_output_widget(port_def)
    output.set_value(result)

设计说明：
- 使用 QGraphicsProxyWidget 将 QWidget 嵌入到节点中
- 控件值变化通过信号通知
- 连接状态可禁用/启用控件
- 遵循 LiteGraph 模式：连接 > 控件值 > 默认值
"""

from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Signal, Qt, Slot
from PySide6.QtGui import QColor, QFocusEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsProxyWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from src.engine.definitions import PortDefinition, PortType
from src.ui.theme import Theme
from src.utils.logger import get_logger

_logger = get_logger(__name__)


# =============================================================================
# 基础控件类
# =============================================================================


class InlineWidgetBase(QWidget):
    """
    内联控件基类

    所有节点内联控件的基类，提供统一的接口：
    - 值的获取和设置
    - 值变化信号
    - 启用/禁用状态
    - 控件样式

    子类需要实现：
    - get_value(): 获取当前值
    - set_value(value): 设置值
    - set_enabled(enabled): 设置启用状态

    Signals:
        value_changed: 值变化时发射 (value: Any)
    """

    # 值变化信号
    value_changed = Signal(object)

    # 控件尺寸
    FIXED_HEIGHT = 24
    MIN_WIDTH = 120

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """
        初始化内联控件

        Args:
            port_def: 端口定义
            parent: 父控件
        """
        super().__init__(parent)

        self._port_def = port_def
        self._is_enabled = True

        # 设置固定高度
        self.setFixedHeight(self.FIXED_HEIGHT)
        self.setMinimumWidth(self.MIN_WIDTH)

        # 应用样式
        self._apply_style()

        _logger.debug(f"创建内联控件: {port_def.name}")

    @property
    def port_name(self) -> str:
        """端口名称"""
        return self._port_def.name

    @property
    def port_type(self) -> PortType:
        """端口数据类型"""
        return self._port_def.type

    def get_value(self) -> Any:
        """
        获取当前值

        子类必须实现此方法

        Returns:
            当前控件值
        """
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        """
        设置控件值

        子类必须实现此方法

        Args:
            value: 要设置的值
        """
        raise NotImplementedError

    def set_enabled(self, enabled: bool) -> None:
        """
        设置控件启用状态

        当端口有连接时，控件应被禁用（LiteGraph 模式）

        Args:
            enabled: 是否启用
        """
        self._is_enabled = enabled
        self.setEnabled(enabled)

    def _apply_style(self) -> None:
        """应用控件样式"""
        # 使用主题颜色
        self.setStyleSheet(
            f"""
            {self.__class__.__name__} {{
                background-color: transparent;
                border: none;
                font-size: 11px;
            }}
        """
        )


# =============================================================================
# 输入控件
# =============================================================================


class TextLineEdit(InlineWidgetBase):
    """
    文本输入控件

    用于 STRING 类型端口的文本输入

    Features:
        - 单行文本输入
        - 自动去空格
        - 值变化信号

    Example:
        >>> widget = TextLineEdit(port_def)
        >>> widget.set_value("Hello")
        >>> widget.get_value()
        'Hello'
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化文本输入控件"""
        super().__init__(port_def, parent)

        # 创建布局和控件
        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 文本输入框
        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText(port_def.description or "输入文本...")
        self._line_edit.setStyleSheet(Theme.get_inline_input_base_stylesheet())

        # 设置默认值
        if port_def.default is not None:
            self._line_edit.setText(str(port_def.default))

        # 连接信号
        self._line_edit.textChanged.connect(self._on_text_changed)

        layout.addWidget(self._line_edit)

    def get_value(self) -> str:
        """获取文本值"""
        return self._line_edit.text().strip()

    def set_value(self, value: Any) -> None:
        """设置文本值"""
        if value is not None:
            self._line_edit.setText(str(value))
        else:
            self._line_edit.clear()

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        super().set_enabled(enabled)
        self._line_edit.setEnabled(enabled)

    @Slot(str)
    def _on_text_changed(self, text: str) -> None:
        """文本变化处理"""
        self.value_changed.emit(text.strip())


class NumberSpinBox(InlineWidgetBase):
    """
    数字输入控件

    用于 INTEGER 和 FLOAT 类型端口的数字输入

    Features:
        - 整数或浮点数输入
        - 支持最小/最大值限制
        - 支持步长设置
        - 值变化信号

    Example:
        >>> widget = NumberSpinBox(port_def)  # for INTEGER
        >>> widget.set_value(42)
        >>> widget.get_value()
        42
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化数字输入控件"""
        super().__init__(port_def, parent)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 根据类型选择控件
        is_float = port_def.type == PortType.FLOAT

        if is_float:
            self._spin_box = QDoubleSpinBox()
            self._spin_box.setDecimals(3)
            self._spin_box.setRange(-999999.0, 999999.0)
            self._spin_box.setSingleStep(0.1)
        else:
            self._spin_box = QSpinBox()
            self._spin_box.setRange(-999999, 999999)
            self._spin_box.setSingleStep(1)

        self._spin_box.setStyleSheet(Theme.get_inline_spinbox_stylesheet())

        # 设置默认值
        if port_def.default is not None:
            self._spin_box.setValue(float(port_def.default) if is_float else int(port_def.default))

        # 连接信号
        if is_float:
            self._spin_box.valueChanged.connect(self._on_float_changed)
        else:
            self._spin_box.valueChanged.connect(self._on_int_changed)

        layout.addWidget(self._spin_box)

    def get_value(self) -> Any:
        """获取数值"""
        return self._spin_box.value()

    def set_value(self, value: Any) -> None:
        """设置数值"""
        if value is not None:
            self._spin_box.setValue(value)

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        super().set_enabled(enabled)
        self._spin_box.setEnabled(enabled)

    @Slot(int)
    def _on_int_changed(self, value: int) -> None:
        """整数值变化处理"""
        self.value_changed.emit(value)

    @Slot(float)
    def _on_float_changed(self, value: float) -> None:
        """浮点数值变化处理"""
        self.value_changed.emit(value)


class BooleanCheckBox(InlineWidgetBase):
    """
    布尔值复选框控件

    用于 BOOLEAN 类型端口的复选框输入

    Features:
        - 复选框切换
        - 可选标签文本
        - 值变化信号

    Example:
        >>> widget = BooleanCheckBox(port_def)
        >>> widget.set_value(True)
        >>> widget.get_value()
        True
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化布尔复选框控件"""
        super().__init__(port_def, parent)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 复选框
        self._checkbox = QCheckBox()
        self._checkbox.setText(port_def.description or "")
        self._checkbox.setStyleSheet(Theme.get_inline_checkbox_stylesheet())

        # 设置默认值
        if port_def.default is not None:
            self._checkbox.setChecked(bool(port_def.default))

        # 连接信号
        self._checkbox.stateChanged.connect(self._on_state_changed)

        layout.addWidget(self._checkbox)
        layout.addStretch()

    def get_value(self) -> bool:
        """获取布尔值"""
        return self._checkbox.isChecked()

    def set_value(self, value: Any) -> None:
        """设置布尔值"""
        if value is not None:
            self._checkbox.setChecked(bool(value))

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        super().set_enabled(enabled)
        self._checkbox.setEnabled(enabled)

    @Slot(int)
    def _on_state_changed(self, state: int) -> None:
        """状态变化处理"""
        self.value_changed.emit(state == Qt.CheckState.Checked.value)


class DropdownComboBox(InlineWidgetBase):
    """
    下拉选择控件

    用于下拉选择类型的端口输入

    Features:
        - 下拉列表选择
        - 支持自定义选项
        - 值变化信号

    Note:
        选项通过 PortDefinition 的 widget_options 字段定义

    Example:
        >>> port_def.widget_options = ["选项1", "选项2", "选项3"]
        >>> widget = DropdownComboBox(port_def)
        >>> widget.set_value("选项2")
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化下拉选择控件"""
        super().__init__(port_def, parent)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 下拉框
        self._combo_box = QComboBox()
        self._combo_box.setStyleSheet(Theme.get_inline_combobox_stylesheet())

        # 添加选项（从 widget_options 或使用默认选项）
        options = getattr(port_def, "widget_options", None) or ["是", "否"]
        self._combo_box.addItems(options)

        # 设置默认值
        if port_def.default is not None:
            index = self._combo_box.findText(str(port_def.default))
            if index >= 0:
                self._combo_box.setCurrentIndex(index)

        # 连接信号
        self._combo_box.currentTextChanged.connect(self._on_text_changed)

        layout.addWidget(self._combo_box)

    def get_value(self) -> str:
        """获取选中的文本"""
        return self._combo_box.currentText()

    def set_value(self, value: Any) -> None:
        """设置选中的文本"""
        if value is not None:
            index = self._combo_box.findText(str(value))
            if index >= 0:
                self._combo_box.setCurrentIndex(index)

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        super().set_enabled(enabled)
        self._combo_box.setEnabled(enabled)

    @Slot(str)
    def _on_text_changed(self, text: str) -> None:
        """文本变化处理"""
        self.value_changed.emit(text)


class FilePickerButton(InlineWidgetBase):
    """
    文件选择控件

    用于 FILE 类型端口的文件选择

    Features:
        - 点击打开文件对话框
        - 显示选中的文件名
        - 支持文件类型过滤
        - 值变化信号

    Note:
        文件过滤通过 PortDefinition 的 widget_options 字段定义
        例如: widget_options = ["*.xlsx", "*.csv"]

    Example:
        >>> port_def.widget_options = ["*.xlsx", "*.csv"]
        >>> widget = FilePickerButton(port_def)
        >>> widget.set_value("/path/to/file.xlsx")
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化文件选择控件"""
        super().__init__(port_def, parent)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 文件路径显示
        self._path_label = QLabel()
        self._path_label.setStyleSheet(Theme.get_inline_file_picker_label_stylesheet())
        self._path_label.setText("选择文件...")
        self._path_label.setMinimumWidth(80)

        # 选择按钮
        self._button = QPushButton("...")
        self._button.setFixedWidth(30)
        self._button.setStyleSheet(Theme.get_inline_file_picker_button_stylesheet())

        # 连接信号
        self._button.clicked.connect(self._on_button_clicked)

        layout.addWidget(self._path_label, 1)
        layout.addWidget(self._button)

        # 保存完整路径
        self._file_path: str = ""

        # 文件过滤
        self._filters = getattr(port_def, "widget_options", None) or ["所有文件 (*)"]

    def get_value(self) -> str:
        """获取文件路径"""
        return self._file_path

    def set_value(self, value: Any) -> None:
        """设置文件路径"""
        if value is not None:
            self._file_path = str(value)
            # 只显示文件名，避免路径过长
            import os

            filename = os.path.basename(self._file_path)
            self._path_label.setText(filename if len(filename) <= 20 else filename[:17] + "...")
            self._path_label.setToolTip(self._file_path)
            self._path_label.setStyleSheet(Theme.get_inline_output_label_link_stylesheet())

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        super().set_enabled(enabled)
        self._button.setEnabled(enabled)
        self._path_label.setEnabled(enabled)

    @Slot()
    def _on_button_clicked(self) -> None:
        """按钮点击处理"""
        # 构建过滤器字符串
        filter_str = ";;".join(self._filters) if self._filters else "所有文件 (*)"

        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filter_str)

        if file_path:
            self.set_value(file_path)
            self.value_changed.emit(file_path)


# =============================================================================
# 输出预览控件
# =============================================================================


class OutputLabelBase(QWidget):
    """
    输出标签基类

    用于显示节点输出值的只读标签

    Features:
        - 只读显示
        - 值更新时自动刷新
        - 支持空值占位符
        - 错误状态显示

    Example:
        >>> widget = OutputTextLabel(port_def)
        >>> widget.set_value("Hello World")
    """

    # 控件尺寸
    FIXED_HEIGHT = 20
    MIN_WIDTH = 100

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """
        初始化输出标签

        Args:
            port_def: 端口定义
            parent: 父控件
        """
        super().__init__(parent)

        self._port_def = port_def
        self._is_error = False

        # 设置固定高度
        self.setFixedHeight(self.FIXED_HEIGHT)
        self.setMinimumWidth(self.MIN_WIDTH)

        _logger.debug(f"创建输出预览控件: {port_def.name}")

    @property
    def port_name(self) -> str:
        """端口名称"""
        return self._port_def.name

    def set_value(self, value: Any) -> None:
        """
        设置显示值

        Args:
            value: 要显示的值
        """
        raise NotImplementedError

    def set_error(self, error_msg: str) -> None:
        """
        设置错误状态

        Args:
            error_msg: 错误消息
        """
        raise NotImplementedError

    def clear(self) -> None:
        """清除显示"""
        raise NotImplementedError


class OutputTextLabel(OutputLabelBase):
    """
    文本输出标签

    用于显示 STRING 类型端口的输出

    Features:
        - 单行文本显示
        - 过长文本自动截断
        - 空值显示占位符

    Example:
        >>> widget = OutputTextLabel(port_def)
        >>> widget.set_value("Hello World")
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化文本输出标签"""
        super().__init__(port_def, parent)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 输出标签
        self._label = QLabel()
        self._label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._label.setText("—")  # 占位符
        self._label.setToolTip("")

        layout.addWidget(self._label)

    def set_value(self, value: Any) -> None:
        """设置显示值"""
        if value is None:
            self._label.setText("—")
            self._label.setToolTip("")
            return

        text = str(value)
        # 截断过长的文本
        display_text = text[:30] + "..." if len(text) > 30 else text
        self._label.setText(display_text)
        self._label.setToolTip(text)
        self._label.setStyleSheet(Theme.get_inline_output_label_link_stylesheet())

    def set_error(self, error_msg: str) -> None:
        """设置错误状态"""
        self._label.setText(f"错误: {error_msg[:20]}...")
        self._label.setToolTip(error_msg)
        self._label.setStyleSheet(Theme.get_inline_output_label_error_stylesheet())
        self._is_error = True

    def clear(self) -> None:
        """清除显示"""
        self._label.setText("—")
        self._label.setToolTip("")
        self._label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._is_error = False


class OutputNumberLabel(OutputLabelBase):
    """
    数字输出标签

    用于显示 INTEGER 和 FLOAT 类型端口的输出

    Features:
        - 数字格式化显示
        - 空值显示占位符

    Example:
        >>> widget = OutputNumberLabel(port_def)
        >>> widget.set_value(42.5)
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化数字输出标签"""
        super().__init__(port_def, parent)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 输出标签
        self._label = QLabel()
        self._is_float = port_def.type == PortType.FLOAT
        self._label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._label.setText("—")
        self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._label)

    def set_value(self, value: Any) -> None:
        """设置显示值"""
        if value is None:
            self._label.setText("—")
            return

        try:
            if self._is_float:
                display_text = f"{float(value):.3f}"
            else:
                display_text = str(int(value))

            self._label.setText(display_text)
            self._label.setStyleSheet(Theme.get_inline_output_label_link_stylesheet())
        except (ValueError, TypeError):
            self._label.setText(str(value))

    def set_error(self, error_msg: str) -> None:
        """设置错误状态"""
        self._label.setText(f"错误")
        self._label.setToolTip(error_msg)
        self._label.setStyleSheet(Theme.get_inline_output_label_error_stylesheet())
        self._is_error = True

    def clear(self) -> None:
        """清除显示"""
        self._label.setText("—")
        self._label.setToolTip("")
        self._label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._is_error = False


class OutputDataPreview(OutputLabelBase):
    """
    数据预览控件

    用于显示 LIST, DICT, DATAFRAME 类型端口的输出预览

    Features:
        - 显示数据类型和大小
        - 简短的预览信息
        - 空值显示占位符

    Example:
        >>> widget = OutputDataPreview(port_def)
        >>> widget.set_value([1, 2, 3, 4, 5])
    """

    def __init__(self, port_def: PortDefinition, parent: Optional[QWidget] = None):
        """初始化数据预览控件"""
        super().__init__(port_def, parent)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 类型标签
        self._type_label = QLabel()
        self._type_label.setFixedWidth(60)
        self._type_label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._type_label.setText("—")

        # 大小/预览标签
        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._preview_label.setText("—")

        layout.addWidget(self._type_label)
        layout.addWidget(self._preview_label, 1)

    def set_value(self, value: Any) -> None:
        """设置显示值"""
        if value is None:
            self._type_label.setText("None")
            self._preview_label.setText("—")
            return

        # 确定类型和大小
        type_name = type(value).__name__
        preview = "—"

        if isinstance(value, list):
            type_name = "list"
            preview = f"[{len(value)} 项]"
            if value:
                preview += f" {repr(value[0])[:20]}..."
        elif isinstance(value, dict):
            type_name = "dict"
            preview = f"{{{len(value)} 键}}"
        elif hasattr(value, "shape"):
            # DataFrame 或类似结构
            try:
                shape = value.shape
                type_name = "DataFrame"
                preview = f"{shape[0]}行 × {shape[1]}列"
            except Exception:
                pass

        self._type_label.setText(type_name)
        self._type_label.setStyleSheet(Theme.get_inline_output_label_link_stylesheet())
        self._preview_label.setText(preview)
        self._preview_label.setStyleSheet(Theme.get_inline_output_label_link_stylesheet())

    def set_error(self, error_msg: str) -> None:
        """设置错误状态"""
        self._type_label.setText("ERROR")
        self._preview_label.setText(error_msg[:20] + "...")
        self._type_label.setStyleSheet(Theme.get_inline_output_label_error_stylesheet())
        self._is_error = True

    def clear(self) -> None:
        """清除显示"""
        self._type_label.setText("—")
        self._preview_label.setText("—")
        self._type_label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._preview_label.setStyleSheet(Theme.get_inline_output_label_idle_stylesheet())
        self._is_error = False


# =============================================================================
# 控件工厂
# =============================================================================


def create_input_widget(
    port_def: PortDefinition, parent: Optional[QWidget] = None
) -> Optional[InlineWidgetBase]:
    """
    创建输入控件

    根据 PortDefinition 的 widget_type 和 type 创建合适的输入控件

    Args:
        port_def: 端口定义
        parent: 父控件

    Returns:
        创建的输入控件，如果无法确定类型则返回 None

    Example:
        >>> port_def.widget_type = "text"
        >>> widget = create_input_widget(port_def)
        >>> isinstance(widget, TextLineEdit)
        True
    """
    widget_type = port_def.widget_type
    port_type = port_def.type

    # 优先使用 widget_type
    if widget_type == "text":
        return TextLineEdit(port_def, parent)
    elif widget_type == "number":
        return NumberSpinBox(port_def, parent)
    elif widget_type == "checkbox":
        return BooleanCheckBox(port_def, parent)
    elif widget_type == "dropdown":
        return DropdownComboBox(port_def, parent)
    elif widget_type == "file":
        return FilePickerButton(port_def, parent)

    # 根据 PortType 自动选择（确保类型比较正确）
    if isinstance(port_type, PortType):
        if port_type.value == PortType.STRING:
            return TextLineEdit(port_def, parent)
        elif port_type.value in (PortType.INTEGER, PortType.FLOAT):
            return NumberSpinBox(port_def, parent)
        elif port_type.value == PortType.BOOLEAN:
            return BooleanCheckBox(port_def, parent)
        elif port_type.value == PortType.FILE:
            return FilePickerButton(port_def, parent)
    elif isinstance(port_type, str):
        # 如果是字符串
        if port_type == PortType.STRING:
            return TextLineEdit(port_def, parent)
        elif port_type in (PortType.INTEGER, PortType.FLOAT):
            return NumberSpinBox(port_def, parent)
        elif port_type == PortType.BOOLEAN:
            return BooleanCheckBox(port_def, parent)
        elif port_type == PortType.FILE:
            return FilePickerButton(port_def, parent)

    # 默认使用文本输入
    return TextLineEdit(port_def, parent)


def create_output_widget(
    port_def: PortDefinition, parent: Optional[QWidget] = None
) -> OutputLabelBase:
    """
    创建输出预览控件

    根据 PortDefinition 的 type 创建合适的输出预览控件

    Args:
        port_def: 端口定义
        parent: 父控件

    Returns:
        创建的输出预览控件

    Example:
        >>> port_def.type = PortType.STRING
        >>> widget = create_output_widget(port_def)
        >>> isinstance(widget, OutputTextLabel)
        True
    """
    port_type = port_def.type

    if port_type in (PortType.INTEGER, PortType.FLOAT):
        return OutputNumberLabel(port_def, parent)
    elif port_type in (PortType.LIST, PortType.DICT, PortType.DATAFRAME):
        return OutputDataPreview(port_def, parent)
    else:
        # 默认使用文本输出
        return OutputTextLabel(port_def, parent)


# =============================================================================
# 代理控件包装器
# =============================================================================


class InlineWidgetProxy(QGraphicsProxyWidget):
    """
    内联控件代理

    将 QWidget 包装为 QGraphicsProxyWidget，用于嵌入到节点中

    Features:
        - 管理 QWidget 的生命周期
        - 处理启用/禁用状态
        - 转发值变化信号
        - 允许控件接收输入事件
        - 不拦截节点的拖拽和选择事件

    Example:
        >>> proxy = InlineWidgetProxy(widget)
        >>> scene.addItem(proxy)
    """

    def __init__(self, widget: InlineWidgetBase, parent: Optional[QGraphicsProxyWidget] = None):
        """
        初始化代理控件

        Args:
            widget: 要包装的内联控件
            parent: 父图形项
        """
        super().__init__(parent)

        self._widget = widget
        self.setWidget(widget)

        # 启用焦点，允许控件接收键盘输入
        self.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsFocusable, True)
        # 控件本身不可选择（选择由节点处理）
        self.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsSelectable, False)
        # 控件不可移动（只有节点可移动）
        self.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsMovable, False)

        # 关键：只接受左键事件
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        _logger.debug(f"创建内联控件代理: {widget.port_name}")

    def focusInEvent(self, event: QFocusEvent) -> None:
        """焦点进入事件 - 取消所有节点选中，防止误删"""
        super().focusInEvent(event)

        # 获取场景并取消所有节点的选中状态
        scene = self.scene()
        if scene:
            for item in scene.selectedItems():
                item.setSelected(False)
            _logger.debug("控件获得焦点，已取消所有节点选中")

    def boundingRect(self):
        """返回边界矩形"""
        if self._widget:
            return self._widget.rect()
        return super().boundingRect()

    def shape(self):
        """
        返回控件的精确形状

        确保只有点击控件实际区域时才触发控件事件
        """
        if self._widget:
            from PySide6.QtGui import QPainterPath

            path = QPainterPath()
            path.addRect(self._widget.rect())
            return path

        return super().shape()

    def mousePressEvent(self, event):
        """
        鼠标按下事件

        如果点击在控件区域内，由控件处理；否则传递给父节点
        """
        # 检查点击位置是否在控件区域内
        if self._widget and self._widget.rect().contains(event.pos().toPoint()):
            # 在控件区域内，由控件处理
            super().mousePressEvent(event)
        else:
            # 不在控件区域内，忽略事件，让父节点处理
            event.ignore()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self._widget and self._widget.rect().contains(event.pos().toPoint()):
            super().mouseReleaseEvent(event)
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._widget and self._widget.rect().contains(event.pos().toPoint()):
            super().mouseMoveEvent(event)
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self._widget and self._widget.rect().contains(event.pos().toPoint()):
            super().mouseReleaseEvent(event)
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._widget and self._widget.rect().contains(event.pos().toPoint()):
            super().mouseMoveEvent(event)
        else:
            event.ignore()

    @property
    def widget(self) -> InlineWidgetBase:
        """获取包装的控件"""
        return self._widget

    def get_value(self) -> Any:
        """获取控件值"""
        return self._widget.get_value() if self._widget else None

    def set_value(self, value: Any) -> None:
        """设置控件值"""
        if self._widget:
            self._widget.set_value(value)

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态"""
        if self._widget:
            self._widget.set_enabled(enabled)

    def cleanup(self) -> None:
        """清理资源"""
        if self._widget:
            self._widget.deleteLater()
            self._widget = None


class OutputWidgetProxy(QGraphicsProxyWidget):
    """
    输出控件代理

    将 OutputLabelBase 包装为 QGraphicsProxyWidget

    Example:
        >>> proxy = OutputWidgetProxy(output_widget)
        >>> scene.addItem(proxy)
    """

    def __init__(self, widget: OutputLabelBase, parent: Optional[QGraphicsProxyWidget] = None):
        """初始化输出控件代理"""
        super().__init__(parent)

        self._widget = widget
        self.setWidget(widget)

        self.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsFocusable, False)

        _logger.debug(f"创建输出控件代理: {widget.port_name}")

    @property
    def widget(self) -> OutputLabelBase:
        """获取包装的控件"""
        return self._widget

    def set_value(self, value: Any) -> None:
        """设置显示值"""
        if self._widget:
            self._widget.set_value(value)

    def set_error(self, error_msg: str) -> None:
        """设置错误状态"""
        if self._widget:
            self._widget.set_error(error_msg)

    def clear(self) -> None:
        """清除显示"""
        if self._widget:
            self._widget.clear()

    def cleanup(self) -> None:
        """清理资源"""
        if self._widget:
            self._widget.deleteLater()
            self._widget = None
