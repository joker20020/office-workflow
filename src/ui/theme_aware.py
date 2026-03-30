# -*- coding: utf-8 -*-
"""
主题感知混入类

为Widget提供自动主题切换支持的混入类。使用ThemeManager单例连接主题变更信号,
当主题改变时自动调用refresh_theme()方法。

使用方式:
    from src.ui.theme_aware import ThemeAwareMixin

    class MyWidget(QWidget, ThemeAwareMixin):
        def __init__(self):
            super().__init__()
            self._setup_theme_awareness()
            self._apply_styles()

        def refresh_theme(self):
            self._apply_styles()

        def _apply_styles(self):
            self.setStyleSheet(Theme.get_xxx_stylesheet())
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt

if TYPE_CHECKING:
    from src.ui.theme_manager import ThemeManager


class ThemeAwareMixin:
    _theme_manager = None  # type: ignore
    _theme_connection_active: bool = False

    def _setup_theme_awareness(self) -> None:
        from src.ui.theme_manager import ThemeManager
        self._theme_manager = ThemeManager.instance()
        # 连接主题变更信号
        # 使用UniqueConnection防止重复连接
        try:
            self._theme_manager.theme_changed.connect(
                self._on_theme_signal,
                type=Qt.ConnectionType.UniqueConnection,  # Qt.UniqueConnection
            )
            self._theme_connection_active = True
        except RuntimeError:
            # 如果已经连接, 忽略错误
            pass

        # 立即应用当前主题
        # self.refresh_theme()

    def _on_theme_signal(self, theme_name: str) -> None:
        """
        主题变更信号处理

        Args:
            theme_name: 新主题名称 ("dark" 或 "light")
        """
        # 调用子类的refresh_theme方法
        self.refresh_theme()

    def refresh_theme(self) -> None:
        """
        刷新主题

        子类必须重写此方法来更新样式表。

        默认实现为空, 子类应该:
        1. 重新应用self的样式表
        2. 重新应用子控件的样式表
        3. 调用子组件的refresh_theme()方法(如果子组件也使用ThemeAwareMixin)
        """
        pass

    def _disconnect_theme_signal(self) -> None:
        """
        断开主题变更信号

        在widget销毁时可以调用此方法来断开信号连接。
        通常不需要手动调用, Qt会在widget销毁时自动断开连接。
        """
        if self._theme_connection_active and self._theme_manager is not None:
            try:
                self._theme_manager.theme_changed.disconnect(self._on_theme_signal)
                self._theme_connection_active = False
            except RuntimeError:
                # 如果已经断开, 忽略错误
                pass
