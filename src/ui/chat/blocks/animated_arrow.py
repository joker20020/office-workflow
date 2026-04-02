# -*- coding: utf-8 -*-
"""
动画箭头组件

QPainter 绘制三角形箭头，通过 QPropertyAnimation 实现 0°→90° 平滑旋转。
用于 block 卡片的展开/折叠指示。
"""

from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, Qt, QSize
from PySide6.QtGui import QPainter, QPainterPath, QColor
from PySide6.QtWidgets import QWidget

from src.ui.theme import Theme


class AnimatedArrow(QWidget):
    """可旋转的三角形箭头指示器。

    rotation=0  → 右箭头（收起状态）
    rotation=90 → 下箭头（展开状态）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation = 0.0
        self._animation = QPropertyAnimation(self, b"rotation")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setFixedSize(14, 14)

    def sizeHint(self) -> QSize:
        return QSize(14, 14)

    # ---- QPropertyAnimation property ----

    def get_rotation(self) -> float:
        return self._rotation

    def set_rotation(self, value: float) -> None:
        self._rotation = value
        self.update()

    rotation = Property(float, get_rotation, set_rotation)

    # ---- public API ----

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        target = 90.0 if expanded else 0.0
        if not animate:
            self._animation.stop()
            self._rotation = target
            self.update()
            return
        self._animation.stop()
        self._animation.setStartValue(self._rotation)
        self._animation.setEndValue(target)
        self._animation.start()

    def stop_animation(self) -> None:
        if self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()

    # ---- paint ----

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 移到中心点并旋转
        cx = self.width() / 2
        cy = self.height() / 2
        painter.translate(cx, cy)
        painter.rotate(self._rotation)

        # 绘制右箭头三角形
        s = 4
        path = QPainterPath()
        path.moveTo(-s, -s)
        path.lineTo(s, 0)
        path.lineTo(-s, s)
        path.closeSubpath()

        color = QColor(Theme.hex("text_hint"))
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        painter.end()
