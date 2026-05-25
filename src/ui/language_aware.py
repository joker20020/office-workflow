# -*- coding: utf-8 -*-
"""
语言感知混入类

为Widget提供自动语言切换支持的混入类。使用I18nManager单例连接语言变更信号,
当语言改变时自动调用refresh_language()方法。

使用方式:
    from src.ui.language_aware import LanguageAwareMixin

    class MyWidget(QWidget, LanguageAwareMixin):
        def __init__(self):
            super().__init__()
            self._setup_language_awareness()
            self._setup_ui()

        def refresh_language(self):
            self._title_label.setText(_("app.title"))
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from src.ui.i18n_manager import I18nManager


class LanguageAwareMixin:
    _i18n_manager = None  # type: ignore
    _language_connection_active: bool = False

    def _setup_language_awareness(self) -> None:
        from src.ui.i18n_manager import I18nManager
        self._i18n_manager = I18nManager.instance()
        # 连接语言变更信号
        # 使用UniqueConnection防止重复连接
        try:
            self._i18n_manager.language_changed.connect(
                self._on_language_signal,
                type=Qt.ConnectionType.UniqueConnection,
            )
            self._language_connection_active = True
        except RuntimeError:
            # 如果已经连接, 忽略错误
            pass

    def _on_language_signal(self, language: str) -> None:
        """
        语言变更信号处理

        Args:
            language: 新语言代码
        """
        # 调用子类的refresh_language方法
        self.refresh_language()

    def refresh_language(self) -> None:
        """
        刷新语言文本

        子类必须重写此方法来更新所有显示的文本。

        默认实现为空, 子类应该:
        1. 重新设置所有 QLabel、QPushButton 等控件的文本
        2. 更新窗口标题
        3. 更新 placeholder text、tooltips 等
        4. 调用子组件的refresh_language()方法(如果子组件也使用LanguageAwareMixin)
        """
        pass

    def _disconnect_language_signal(self) -> None:
        """
        断开语言变更信号

        在widget销毁时可以调用此方法来断开信号连接。
        通常不需要手动调用, Qt会在widget销毁时自动断开连接。
        """
        if self._language_connection_active and self._i18n_manager is not None:
            try:
                self._i18n_manager.language_changed.disconnect(self._on_language_signal)
                self._language_connection_active = False
            except RuntimeError:
                # 如果已经断开, 忽略错误
                pass
