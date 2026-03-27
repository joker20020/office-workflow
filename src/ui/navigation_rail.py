# -*- coding: utf-8 -*-
"""
导航栏组件

提供左侧垂直导航栏，用于切换不同的功能面板：
- 支持图标 + 文字导航项
- 高亮当前选中项
- 固定宽度

使用方式：
    from src.ui.navigation_rail import NavigationRail

    nav = NavigationRail()
    nav.add_item("home", "首页", "🏠")
    nav.add_item("nodes", "节点", "🔧")

    nav.currentChanged.connect(self.on_nav_changed)
"""

from typing import Optional

from PySide6.QtCore import QPropertyAnimation, QParallelAnimationGroup, Property, Qt, Signal, QSize
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.utils.logger import get_logger
from src.ui.theme import Theme

# 模块日志记录器
_logger = get_logger(__name__)


class NavItem(QPushButton):
    """
    导航项组件

    单个导航按钮，支持：
    - 图标 + 文字
    - 选中/未选中状态
    - 悬停效果

    Attributes:
        item_id: 导航项ID
        icon: 图标字符
        text: 显示文字
    """

    def __init__(
        self,
        item_id: str,
        text: str,
        icon: str = "",
        parent: Optional[QWidget] = None,
    ):
        """
        初始化导航项

        Args:
            item_id: 导航项唯一标识
            text: 显示文字
            icon: 图标字符（如 emoji）
            parent: 父组件
        """
        super().__init__(parent)

        self.item_id = item_id
        self._icon = icon
        self._text = text
        self._selected = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """设置UI"""
        # 设置固定高度
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 创建布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # 图标标签
        if self._icon:
            icon_label = QLabel(self._icon)
            icon_label.setStyleSheet("font-size: 18px;")
            layout.addWidget(icon_label)

        # 文字标签
        text_label = QLabel(self._text)
        layout.addWidget(text_label)

        layout.addStretch()

        # 应用样式
        self._apply_style()

    def _apply_style(self) -> None:
        """应用样式 - 使用主题系统"""
        self.setStyleSheet(Theme.get_nav_item_stylesheet(self._selected))

    @property
    def selected(self) -> bool:
        """是否选中"""
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        """设置选中状态"""
        if self._selected != value:
            self._selected = value
            self._apply_style()


class NavigationRail(QWidget):
    """
    导航栏组件

    左侧垂直导航栏，提供：
    - 多个导航项
    - 单选模式
    - 选中状态高亮

    Signals:
        currentChanged: 当前选中项改变 (item_id: str)

    Example:
        nav = NavigationRail()
        nav.add_item("home", "首页", "🏠")
        nav.add_item("nodes", "节点编辑器", "🔧")

        nav.currentChanged.connect(self.on_nav_changed)
    """

    # 信号：当前选中项改变
    currentChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        """
        初始化导航栏

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        self._items: dict[str, NavItem] = {}
        self._current_id: Optional[str] = None

        self._setup_ui()

        _logger.debug("NavigationRail 初始化完成")

    def _setup_ui(self) -> None:
        """设置UI"""
        # 固定宽度
        self.setFixedWidth(200)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 16, 8, 16)
        main_layout.setSpacing(4)

        # 标题区域
        title_label = QLabel("办公小工具")
        title_label.setStyleSheet(Theme.get_title_label_stylesheet())
        main_layout.addWidget(title_label)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(Theme.get_separator_stylesheet())
        main_layout.addWidget(separator)

        # 导航项容器
        self._items_widget = QWidget()
        self._items_widget.setStyleSheet(Theme.get_navigation_rail_container_stylesheet())
        self._items_layout = QVBoxLayout(self._items_widget)
        self._items_layout.setContentsMargins(0, 8, 0, 0)
        self._items_layout.setSpacing(4)
        self._items_layout.addStretch()

        main_layout.addWidget(self._items_widget)
        main_layout.addStretch()

        # 应用整体样式 - 使用主题系统
        self.setStyleSheet(Theme.get_navigation_rail_stylesheet())

    def add_item(self, item_id: str, text: str, icon: str = "") -> None:
        """
        添加导航项

        Args:
            item_id: 导航项唯一标识
            text: 显示文字
            icon: 图标字符（如 emoji）
        """
        if item_id in self._items:
            _logger.warning(f"导航项已存在: {item_id}")
            return

        # 创建导航项
        item = NavItem(item_id, text, icon)
        item.clicked.connect(lambda: self._on_item_clicked(item_id))

        # 插入到 stretch 之前
        index = self._items_layout.count() - 1
        self._items_layout.insertWidget(index, item)

        self._items[item_id] = item

        _logger.debug(f"添加导航项: {item_id}")

        # 如果是第一个项，自动选中
        if len(self._items) == 1:
            self.set_current(item_id)

    def remove_item(self, item_id: str) -> bool:
        """
        移除导航项

        Args:
            item_id: 导航项ID

        Returns:
            是否成功移除
        """
        if item_id not in self._items:
            return False

        item = self._items.pop(item_id)
        item.deleteLater()

        # 如果移除的是当前选中项，选择第一个
        if self._current_id == item_id:
            self._current_id = None
            if self._items:
                first_id = next(iter(self._items.keys()))
                self.set_current(first_id)

        _logger.debug(f"移除导航项: {item_id}")
        return True

    def set_current(self, item_id: str) -> None:
        """
        设置当前选中项

        Args:
            item_id: 导航项ID
        """
        if item_id not in self._items:
            _logger.warning(f"导航项不存在: {item_id}")
            return

        for iid, item in self._items.items():
            item.selected = iid == item_id

        old_id = self._current_id
        self._current_id = item_id

        if old_id != item_id:
            self.currentChanged.emit(item_id)
            _logger.debug(f"导航切换: {old_id} -> {item_id}")

    def _on_item_clicked(self, item_id: str) -> None:
        """导航项点击处理"""
        self.set_current(item_id)

    def get_current(self) -> Optional[str]:
        """
        获取当前选中项ID

        Returns:
            当前选中项ID，如果没有则返回 None
        """
        return self._current_id

    def sizeHint(self) -> QSize:
        """建议尺寸"""
        return QSize(200, 600)
