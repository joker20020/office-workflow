# -*- coding: utf-8 -*-
"""
折叠容器组件

通过 QVariantAnimation 平滑改变 fixedHeight，实现展开/折叠过渡动画。
"""

from PySide6.QtCore import QVariantAnimation, QEasingCurve, Signal, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class CollapsibleBox(QWidget):
    """可折叠容器。

    收起时 fixedHeight 动画到 0，展开时动画到内容自然高度。
    """

    expansion_finished = Signal()

    def __init__(self, content_widget: QWidget, parent=None):
        super().__init__(parent)
        self._content = content_widget
        self._expanded = False
        self._target_height: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._content)

        self._init_animation()

        # 初始收起
        self.setFixedHeight(0)

    def _init_animation(self) -> None:
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(250)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.valueChanged.connect(self._on_value_changed)
        self._animation.finished.connect(self._on_animation_finished)

    def _text_edit_width(self) -> int:
        """获取 QTextEdit 实际可用的文本排版宽度。

        从卡片容器或最近的有效父级获取宽度，减去 QSS 中定义的
        卡片边框和 QTextEdit 的水平 padding。
        """
        # 向上找卡片容器 blockCard
        w = 0
        p = self.parentWidget()
        while p:
            if p.objectName() == "blockCard":
                w = p.width()
                break
            p = p.parentWidget()

        # 回退：找最近的有宽度的父级
        if w <= 0:
            p = self.parentWidget()
            while p:
                if p.width() > 0:
                    w = p.width()
                    break
                p = p.parentWidget()

        if w <= 0:
            w = 600

        # 减去卡片边框 (左 3px accent + 1px + 右 1px = 5px)
        # 减去 QTextEdit QSS padding (左右各 10px = 20px)
        return max(w - 25, 50)

    def _compute_content_height(self) -> int:
        """计算内容 widget 的自然高度。"""
        if isinstance(self._content, QTextEdit):
            doc = self._content.document()
            doc.setTextWidth(self._text_edit_width())
            doc_height = doc.documentLayout().documentSize().height()
            m = self._content.contentsMargins()
            return int(doc_height + m.top() + m.bottom() + 4)
        return self._content.sizeHint().height()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded

        if expanded:
            # 临时解除高度限制以获取准确的内容高度
            self.setFixedHeight(16777215)
            self._target_height = max(self._compute_content_height(), 20)
        else:
            self._target_height = 0

        start_h = self.height() if self.height() > 0 else 0
        # 展开时 snap 回起点再做动画
        if expanded:
            self.setFixedHeight(start_h)

        if not animate:
            self._animation.stop()
            self.setFixedHeight(self._target_height)
            return

        self._animation.stop()
        distance = abs(self._target_height - start_h)
        # 根据动画距离动态调整时长：最小 300ms，最大 450ms
        duration = int(max(300, min(450, distance * 3)))
        self._animation.setDuration(duration)
        self._animation.setStartValue(start_h)
        self._animation.setEndValue(self._target_height)
        self._animation.start()

    def update_content_height(self, animate: bool = False) -> None:
        """内容变化后更新高度。"""
        if not self._expanded:
            return

        new_height = self._compute_content_height()
        new_height = max(new_height, 20)
        self._target_height = new_height

        if not animate:
            self._animation.stop()
            self.setFixedHeight(new_height)
        else:
            self._animation.stop()
            distance = abs(new_height - self.height())
            duration = int(max(300, min(400, distance * 2)))
            self._animation.setDuration(duration)
            self._animation.setStartValue(self.height())
            self._animation.setEndValue(new_height)
            self._animation.start()

    def stop_animation(self) -> None:
        if self._animation and self._animation.state() == QVariantAnimation.State.Running:
            self._animation.stop()

    def _on_value_changed(self, value) -> None:
        h = value.toInt() if hasattr(value, 'toInt') else int(value)
        self.setFixedHeight(h)

    def _on_animation_finished(self) -> None:
        self.setFixedHeight(self._target_height)
        self.expansion_finished.emit()

    def sizeHint(self) -> QSize:
        w = super().sizeHint().width()
        if self._expanded:
            h = self._compute_content_height()
            return QSize(w, max(h, 20))
        return QSize(w, 0)

    def minimumSizeHint(self) -> QSize:
        w = super().minimumSizeHint().width()
        if self._expanded:
            h = self._compute_content_height()
            return QSize(w, max(h, 20))
        return QSize(w, 0)
