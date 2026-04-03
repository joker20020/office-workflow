# -*- coding: utf-8 -*-
"""
数据输入节点定义

提供各内置数据类型的常量输入节点，用于在工作流中提供固定值。
"""

import json
import threading
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, QObject, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QApplication,
)

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)


# ==================== 线程安全的阻塞式对话框桥接 ====================


class _BlockingDialogBridge(QObject):
    """将模态对话框调度到主线程执行，并阻塞工作线程直到用户响应。

    使用 Signal + BlockingQueuedConnection 实现：
    - 工作线程 emit 信号后自动阻塞
    - 主线程执行 slot（创建并 exec 对话框）
    - slot 返回后工作线程自动恢复
    """

    _request = Signal(object)  # 传入 Callable[[], None]

    def __init__(self):
        super().__init__()
        self._request.connect(self._on_request, Qt.ConnectionType.BlockingQueuedConnection)
        self._result = None

    @Slot(object)
    def _on_request(self, func: Callable[[], None]) -> None:
        try:
            func()
        except Exception as e:
            _logger.error(f"阻塞对话框执行失败: {e}", exc_info=True)

    def invoke(self, func: Callable[[], None]) -> None:
        if threading.current_thread() is threading.main_thread():
            func()
        else:
            self._request.emit(func)


_bridge: Optional[_BlockingDialogBridge] = None
_bridge_lock = threading.Lock()


def _get_bridge() -> _BlockingDialogBridge:
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                app = QApplication.instance()
                bridge = _BlockingDialogBridge()
                if app and threading.current_thread() is not threading.main_thread():
                    bridge.moveToThread(app.thread())
                _bridge = bridge
    return _bridge


# ==================== JSON 编辑对话框 ====================


class _JsonEditDialog(QDialog, ThemeAwareMixin):
    """模态 JSON 编辑对话框，用于列表和字典输入。"""

    def __init__(self, title: str, initial_value: Any, parent=None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._result_value = initial_value
        self._init_ui(title, initial_value)

    def _init_ui(self, title: str, initial_value: Any) -> None:
        self.setWindowTitle(title)
        self.setMinimumSize(500, 400)
        self.resize(600, 450)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # 提示标签
        hint = QLabel("请输入 JSON 格式数据（列表或字典）：")
        hint.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("text_secondary")};
                font-size: 12px;
                background: transparent;
            }}
        """)
        layout.addWidget(hint)

        # JSON 编辑器
        self._editor = QTextEdit()
        initial_text = json.dumps(initial_value, ensure_ascii=False, indent=2)
        self._editor.setPlainText(initial_text)
        self._editor.setFont(QFont("Monospace", 11))
        self._editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.hex("background_input")};
                color: {Theme.hex("text_primary")};
                border: 1px solid {Theme.hex("border_primary")};
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border: 1px solid {Theme.hex("border_focus")};
            }}
        """)
        layout.addWidget(self._editor, 1)

        # 错误提示
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("state_error")};
                font-size: 12px;
                background: transparent;
            }}
        """)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.hex("background_tertiary")};
                color: {Theme.hex("text_primary")};
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {Theme.hex("background_hover")};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("确定")
        confirm_btn.setFixedSize(80, 32)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.hex("border_focus")};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {Theme.hex("accent_hover_bg")};
            }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.hex("background_primary")};
            }}
        """)

    def _on_confirm(self) -> None:
        text = self._editor.toPlainText().strip()
        if not text:
            self._result_value = None
            self.accept()
            return
        try:
            parsed = json.loads(text)
            self._result_value = parsed
            self._error_label.hide()
            self.accept()
        except json.JSONDecodeError as e:
            self._error_label.setText(f"JSON 格式错误: {e}")
            self._error_label.show()

    def get_value(self) -> Any:
        return self._result_value


def _show_json_dialog(title: str, initial: Any) -> Any:
    """在主线程显示 JSON 编辑对话框，阻塞调用线程。"""
    dialog_ref = [None]

    def _create_and_exec():
        dialog = _JsonEditDialog(title, initial)
        dialog_ref[0] = dialog
        dialog.exec()

    _get_bridge().invoke(_create_and_exec)

    if dialog_ref[0] and dialog_ref[0].result() == QDialog.DialogCode.Accepted:
        return dialog_ref[0].get_value()
    return initial  # 取消时返回初始值


# ==================== 字符串输入 ====================


def _input_string(value: str) -> dict:
    return {"output": value}


input_string = NodeDefinition(
    node_type="input.string",
    display_name="字符串输入",
    description="提供一个字符串常量值",
    category="input",
    icon="📝",
    inputs=[
        PortDefinition("value", PortType.STRING, "字符串值", widget_type="text_edit"),
    ],
    outputs=[
        PortDefinition("output", PortType.STRING, "输出字符串", show_preview=True),
    ],
    execute=_input_string,
)


# ==================== 整数输入 ====================


def _input_integer(value: int) -> dict:
    return {"output": value}


input_integer = NodeDefinition(
    node_type="input.integer",
    display_name="整数输入",
    description="提供一个整数常量值",
    category="input",
    icon="🔢",
    inputs=[
        PortDefinition("value", PortType.INTEGER, "整数值", default=0, widget_type="spin_box"),
    ],
    outputs=[
        PortDefinition("output", PortType.INTEGER, "输出整数"),
    ],
    execute=_input_integer,
)


# ==================== 浮点数输入 ====================


def _input_float(value: float) -> dict:
    return {"output": value}


input_float = NodeDefinition(
    node_type="input.float",
    display_name="浮点数输入",
    description="提供一个浮点数常量值",
    category="input",
    icon="🔢",
    inputs=[
        PortDefinition("value", PortType.FLOAT, "浮点数值", default=0.0, widget_type="double_spin_box"),
    ],
    outputs=[
        PortDefinition("output", PortType.FLOAT, "输出浮点数"),
    ],
    execute=_input_float,
)


# ==================== 布尔值输入 ====================


def _input_boolean(value: bool) -> dict:
    return {"output": value}


input_boolean = NodeDefinition(
    node_type="input.boolean",
    display_name="布尔值输入",
    description="提供一个布尔值（True/False）",
    category="input",
    icon="🔘",
    inputs=[
        PortDefinition("value", PortType.BOOLEAN, "布尔值", default=False, widget_type="check_box"),
    ],
    outputs=[
        PortDefinition("output", PortType.BOOLEAN, "输出布尔值"),
    ],
    execute=_input_boolean,
)


# ==================== 列表输入 ====================


def _input_list(items: list) -> dict:
    result = _show_json_dialog("列表输入 — JSON 编辑器", items)
    if result is None:
        result = items
    return {"output": result}


input_list = NodeDefinition(
    node_type="input.list",
    display_name="列表输入",
    description="执行时弹出对话框编辑列表（JSON 格式）",
    category="input",
    icon="📋",
    inputs=[
        PortDefinition("items", PortType.LIST, "列表值", default=[]),
    ],
    outputs=[
        PortDefinition("output", PortType.LIST, "输出列表", show_preview=True),
    ],
    execute=_input_list,
)


# ==================== 字典输入 ====================


def _input_dict(data: dict) -> dict:
    result = _show_json_dialog("字典输入 — JSON 编辑器", data)
    if result is None:
        result = data
    return {"output": result}


input_dict = NodeDefinition(
    node_type="input.dict",
    display_name="字典输入",
    description="执行时弹出对话框编辑字典（JSON 格式）",
    category="input",
    icon="📖",
    inputs=[
        PortDefinition("data", PortType.DICT, "字典值", default={}),
    ],
    outputs=[
        PortDefinition("output", PortType.DICT, "输出字典", show_preview=True),
    ],
    execute=_input_dict,
)


# ==================== 文件输入 ====================


def _input_file(file_path: str) -> dict:
    if not file_path:
        return {"output": ""}
    try:
        from pathlib import Path
        text = Path(file_path).read_text(encoding="utf-8")
        return {"output": text}
    except Exception as e:
        _logger.error(f"文件读取失败: {file_path} - {e}")
        return {"output": f"[读取失败: {e}]"}


input_file = NodeDefinition(
    node_type="input.file",
    display_name="文件输入",
    description="读取文件内容并输出文本",
    category="input",
    icon="📁",
    inputs=[
        PortDefinition("file_path", PortType.FILE, "文件路径", widget_type="file_picker"),
    ],
    outputs=[
        PortDefinition("output", PortType.STRING, "文件内容", show_preview=True),
    ],
    execute=_input_file,
)
