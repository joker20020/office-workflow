# -*- coding: utf-8 -*-
"""
文本预览节点定义

提供文本可视化预览功能，支持非模态窗口、多窗口显示
"""

from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QToolBar,
    QWidget,
    QApplication,
)
from PySide6.QtGui import QFont

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)

_active_dialogs: list = []


class TextPreviewDialog(QDialog, ThemeAwareMixin):
    """
    文本预览对话框

    非模态、可调整大小的文本显示窗口，支持：
    - 复制到剪贴板
    - 自动换行切换
    - 等宽字体显示
    """

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._text = text
        self._word_wrap_enabled = True

        self.setWindowTitle("文本预览")
        self.setMinimumSize(500, 400)
        self.resize(700, 500)
        # 非模态窗口
        self.setModal(False)
        # 允许交互（选择、复制）和最大化
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        self._setup_ui()
        self._apply_theme()

        _logger.debug(f"文本预览对话框创建: length={len(text)}")

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {Theme.hex("background_secondary")};
                border: none;
                padding: 4px;
                spacing: 4px;
            }}
            QToolBar QToolButton {{
                background-color: transparent;
                border: 1px solid {Theme.hex("border_primary")};
                border-radius: 3px;
                padding: 4px 8px;
                color: {Theme.hex("text_primary")};
            }}
            QToolBar QToolButton:hover {{
                background-color: {Theme.hex("background_hover")};
                border-color: {Theme.hex("border_hover")};
            }}
            QToolBar QToolButton:pressed {{
                background-color: {Theme.hex("background_pressed")};
            }}
        """)

        # 复制按钮
        copy_action = toolbar.addAction("📋 复制")
        copy_action.setToolTip("复制全部文本到剪贴板")
        copy_action.triggered.connect(self._copy_to_clipboard)

        toolbar.addSeparator()

        # 自动换行按钮
        self._wrap_action = toolbar.addAction("↩️ 自动换行")
        self._wrap_action.setToolTip("切换自动换行")
        self._wrap_action.setCheckable(True)
        self._wrap_action.setChecked(True)
        self._wrap_action.triggered.connect(self._toggle_word_wrap)

        layout.addWidget(toolbar)

        # 文本显示区域
        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(self._text)
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        # 等宽字体
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._text_edit.setFont(font)

        # 文本区域样式
        self._text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.hex("background_primary")};
                color: {Theme.hex("text_primary")};
                border: none;
                padding: 8px;
            }}
            QTextEdit:focus {{
                border: none;
            }}
        """)

        layout.addWidget(self._text_edit)

        # 底部状态栏
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(8, 4, 8, 4)

        char_count = len(self._text)
        line_count = self._text.count("\n") + 1
        self._status_label = QPushButton(f"字符: {char_count} | 行数: {line_count}")
        self._status_label.setEnabled(False)
        self._status_label.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.hex("text_secondary")};
                border: none;
                font-size: 11px;
                text-align: left;
            }}
        """)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.hex("background_tertiary")};
                color: {Theme.hex("text_primary")};
                border: 1px solid {Theme.hex("border_primary")};
                border-radius: 3px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background-color: {Theme.hex("background_hover")};
                border-color: {Theme.hex("border_hover")};
            }}
        """)
        status_layout.addWidget(close_btn)

        layout.addWidget(status_widget)

    def _apply_theme(self):
        """应用主题样式"""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.hex("background_primary")};
            }}
        """)

    def refresh_theme(self):
        """刷新主题（ThemeAwareMixin要求）"""
        self._apply_theme()

    def _copy_to_clipboard(self):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._text)
        _logger.info(f"已复制文本到剪贴板: {len(self._text)} 字符")

        # 视觉反馈
        self._wrap_action.setText("✓ 已复制!")
        from PySide6.QtCore import QTimer

        QTimer.singleShot(2000, lambda: self._wrap_action.setText("↩️ 自动换行"))

    def _toggle_word_wrap(self, checked: bool):
        """切换自动换行"""
        self._word_wrap_enabled = checked
        if checked:
            self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        else:
            self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        _logger.debug(f"自动换行: {checked}")


# ==================== 文本预览节点 ====================


def _preview_text(text: str) -> Dict[str, Any]:
    """
    预览文本内容

    打开非模态窗口显示完整文本，同时将文本传递到输出端口

    Args:
        text: 要预览的文本

    Returns:
        包含相同文本的字典（透传）
    """
    # 创建并显示预览窗口（非模态）
    dialog = TextPreviewDialog(text)
    dialog.show()

    global _active_dialogs
    _active_dialogs.append(dialog)
    _active_dialogs = [d for d in _active_dialogs if d.isVisible()]

    _logger.info(f"文本预览窗口已打开: {len(text)} 字符, 活动窗口数: {len(_active_dialogs)}")

    # 透传文本
    return {"text_out": text}


text_preview = NodeDefinition(
    node_type="preview.text",
    display_name="文本预览",
    description="打开可视化窗口预览文本内容，支持复制和换行切换",
    category="preview",
    icon="👁️",
    inputs=[
        PortDefinition("text", PortType.STRING, "要预览的文本"),
    ],
    outputs=[
        PortDefinition("text_out", PortType.STRING, "预览的文本（透传）"),
    ],
    execute=_preview_text,
)
