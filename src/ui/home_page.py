# -*- coding: utf-8 -*-
"""
首页组件模块

提供应用程序的首页界面，包含：
- 欢迎标题和副标题
- 快速操作卡片（导航到各个功能模块）
- 最近工作流列表（从配置文件加载）
- 状态页脚

使用方式：
    from src.ui.home_page import HomePage

    home_page = HomePage()
    home_page.navigate_requested.connect(self._on_navigate)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from src.core.config_manager import get_config_manager
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class QuickActionCard(QFrame, ThemeAwareMixin):
    """快速操作卡片组件 - 可点击的功能入口卡片"""

    clicked = Signal(str)

    def __init__(
        self,
        action_id: str,
        title: str,
        icon: str,
        description: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._action_id = action_id
        self._title = title
        self._icon = icon
        self._description = description

        self.setObjectName("quickActionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(140)
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # 图标
        self._icon_label = QLabel(self._icon)
        self._icon_label.setObjectName("quickActionIcon")
        self._icon_label.setStyleSheet(Theme.get_quick_action_icon_stylesheet())
        layout.addWidget(self._icon_label)

        # 标题
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("quickActionTitle")
        self._title_label.setStyleSheet(Theme.get_quick_action_title_stylesheet())
        layout.addWidget(self._title_label)

        # 描述
        self._desc_label = QLabel(self._description)
        self._desc_label.setObjectName("quickActionDesc")
        self._desc_label.setStyleSheet(Theme.get_quick_action_desc_stylesheet())
        self._desc_label.setWordWrap(True)
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._desc_label, 1)

    def _apply_style(self) -> None:
        self.setStyleSheet(Theme.get_quick_action_card_stylesheet())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._action_id)
        super().mousePressEvent(event)

    def refresh_theme(self) -> None:
        self._apply_style()
        self._icon_label.setStyleSheet(Theme.get_quick_action_icon_stylesheet())
        self._title_label.setStyleSheet(Theme.get_quick_action_title_stylesheet())
        self._desc_label.setStyleSheet(Theme.get_quick_action_desc_stylesheet())


class RecentWorkflowItem(QFrame, ThemeAwareMixin):
    """最近工作流项组件"""

    clicked = Signal(str, str)  # workflow_id, file_path

    def __init__(
        self,
        workflow_id: str,
        title: str,
        modified_time: str,
        file_path: str = "",
        node_count: int = 0,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._workflow_id = workflow_id
        self._title = title
        self._modified_time = modified_time
        self._file_path = file_path
        self._node_count = node_count

        self.setObjectName("recentItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._icon_label = QLabel("📄")
        self._icon_label.setStyleSheet(Theme.get_icon_label_stylesheet(20))
        layout.addWidget(self._icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("recentItemTitle")
        self._title_label.setStyleSheet(Theme.get_recent_item_title_stylesheet())
        info_layout.addWidget(self._title_label)

        meta_text = f"{self._modified_time}"
        if self._node_count > 0:
            meta_text += f" · {self._node_count} 个节点"
        self._meta_label = QLabel(meta_text)
        self._meta_label.setObjectName("recentItemMeta")
        self._meta_label.setStyleSheet(Theme.get_recent_item_meta_stylesheet())
        info_layout.addWidget(self._meta_label)

        layout.addLayout(info_layout, 1)

        self._arrow_label = QLabel("›")
        self._arrow_label.setStyleSheet(Theme.get_arrow_indicator_stylesheet())
        layout.addWidget(self._arrow_label)

    def _apply_style(self) -> None:
        self.setStyleSheet(Theme.get_recent_item_stylesheet())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._workflow_id, self._file_path)
        super().mousePressEvent(event)

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        self._apply_style()
        self._title_label.setStyleSheet(Theme.get_recent_item_title_stylesheet())
        self._meta_label.setStyleSheet(Theme.get_recent_item_meta_stylesheet())
        self._icon_label.setStyleSheet(Theme.get_icon_label_stylesheet(20))
        self._arrow_label.setStyleSheet(Theme.get_arrow_indicator_stylesheet())


class HomePage(QWidget, ThemeAwareMixin):
    """
    首页组件

    显示欢迎信息、快速操作入口和最近工作流列表。
    支持主题切换和导航请求信号。

    Signals:
        navigate_requested: 请求导航到指定页面 (page_id: str)
    """

    navigate_requested = Signal(str)
    load_workflow_requested = Signal(str, str)  # page_id, file_path

    # 快速操作配置
    QUICK_ACTIONS = [
        {"id": "nodes", "icon": "🔧", "title": "节点编辑器", "desc": "创建和编辑节点工作流"},
        {"id": "agent", "icon": "🤖", "title": "AI 助手", "desc": "与 AI 对话获取帮助"},
        {"id": "plugins", "icon": "🧩", "title": "插件管理", "desc": "管理已安装的插件"},
        {"id": "packages", "icon": "📦", "title": "节点包", "desc": "浏览和安装节点包"},
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self.setObjectName("HomePage")
        self._recent_items: List[Any] = []
        self._quick_action_cards: List[QuickActionCard] = []
        self._setup_ui()
        self._load_recent_workflows()
        _logger.debug("HomePage 初始化完成")

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 滚动区域
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet(Theme.get_home_scroll_area_stylesheet())

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet(Theme.get_transparent_background_stylesheet())
        content_layout = QVBoxLayout(self._scroll_content)
        content_layout.setContentsMargins(48, 0, 48, 24)
        content_layout.setSpacing(0)

        # 头部区域
        self._header = self._create_header()
        content_layout.addWidget(self._header)

        # 快速操作区域
        self._quick_actions_widget = self._create_quick_actions()
        content_layout.addWidget(self._quick_actions_widget)

        # 最近工作流区域
        self._recent_section = self._create_recent_section()
        content_layout.addWidget(self._recent_section)

        content_layout.addStretch()

        self._scroll_area.setWidget(self._scroll_content)
        main_layout.addWidget(self._scroll_area)

        # 页脚
        self._footer = self._create_footer()
        main_layout.addWidget(self._footer)

        # 应用整体样式
        self.setStyleSheet(Theme.get_home_page_stylesheet())

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("homeHeader")
        header.setStyleSheet(Theme.get_home_header_stylesheet())

        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 32, 0, 32)
        layout.setSpacing(8)

        self._title_label = QLabel("欢迎使用办公小工具整合平台")
        self._title_label.setObjectName("homeTitle")
        self._title_label.setStyleSheet(Theme.get_home_title_stylesheet())
        layout.addWidget(self._title_label)

        self._subtitle_label = QLabel("基于节点编辑器的智能办公工具 · Phase 3: Agent 集成已完成")
        self._subtitle_label.setObjectName("homeSubtitle")
        self._subtitle_label.setStyleSheet(Theme.get_home_subtitle_stylesheet())
        layout.addWidget(self._subtitle_label)

        return header

    def _create_quick_actions(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(16)

        # 区域标题
        section_title = QLabel("快速开始")
        section_title.setObjectName("sectionTitle")
        section_title.setStyleSheet(Theme.get_home_section_title_stylesheet())
        layout.addWidget(section_title)

        # 卡片网格
        grid = QGridLayout()
        grid.setSpacing(16)

        # 设置列拉伸因子，确保每列宽度相等
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        for i, action in enumerate(self.QUICK_ACTIONS):
            card = QuickActionCard(
                action_id=action["id"],
                title=action["title"],
                icon=action["icon"],
                description=action["desc"],
            )
            card.setMinimumWidth(200)  # 设置最小宽度
            card.clicked.connect(self._on_action_clicked)
            self._quick_action_cards.append(card)
            row, col = divmod(i, 2)
            grid.addWidget(card, row, col)

        layout.addLayout(grid)
        return widget

    def _create_recent_section(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        self._recent_layout = QVBoxLayout(widget)
        self._recent_layout.setContentsMargins(0, 24, 0, 0)
        self._recent_layout.setSpacing(12)

        # 区域标题
        self._recent_title = QLabel("最近工作流")
        self._recent_title.setObjectName("sectionTitle")
        self._recent_title.setStyleSheet(Theme.get_home_section_title_stylesheet())
        self._recent_layout.addWidget(self._recent_title)

        # 工作流列表容器
        self._recent_list_widget = QWidget()
        self._recent_list_widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        self._recent_list_layout = QVBoxLayout(self._recent_list_widget)
        self._recent_list_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_list_layout.setSpacing(8)
        self._recent_layout.addWidget(self._recent_list_widget)

        return widget

    def _create_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("homeFooter")
        footer.setStyleSheet(Theme.get_footer_stylesheet())

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 12, 24, 12)

        self._status_label = QLabel("💡 点击左侧导航栏或上方快速操作卡片开始使用")
        self._status_label.setObjectName("footerStatus")
        self._status_label.setStyleSheet(Theme.get_footer_status_stylesheet())
        layout.addWidget(self._status_label)
        layout.addStretch()

        return footer

    def _load_recent_workflows(self) -> None:
        """从配置文件加载最近工作流"""
        config = get_config_manager()
        recent_workflows = config.get("recent_workflows") or []

        # 清空现有项
        for item in self._recent_items:
            item.deleteLater()
        self._recent_items.clear()

        if not recent_workflows:
            empty_label = QLabel("暂无最近工作流")
            empty_label.setObjectName("emptyState")
            empty_label.setStyleSheet(Theme.get_empty_state_stylesheet())
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._recent_list_layout.addWidget(empty_label)
            self._recent_items.append(empty_label)
            return

        for workflow in recent_workflows[:5]:
            item = RecentWorkflowItem(
                workflow_id=workflow.get("id", ""),
                title=workflow.get("title", "未命名工作流"),
                modified_time=workflow.get("modified", "未知时间"),
                file_path=workflow.get("file_path", ""),
                node_count=workflow.get("node_count", 0),
            )
            item.clicked.connect(self._on_recent_clicked)
            self._recent_list_layout.addWidget(item)
            self._recent_items.append(item)

    def add_recent_workflow(
        self,
        workflow_id: str,
        title: str,
        file_path: str = "",
        node_count: int = 0,
    ) -> None:
        """添加工作流到最近列表"""
        config = get_config_manager()
        recent_workflows = config.get("recent_workflows") or []

        # 移除重复项
        recent_workflows = [w for w in recent_workflows if w.get("file_path") != file_path]

        # 添加到列表开头
        recent_workflows.insert(
            0,
            {
                "id": workflow_id,
                "title": title,
                "modified": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "node_count": node_count,
                "file_path": file_path,
            },
        )

        # 只保留最近5个
        recent_workflows = recent_workflows[:5]

        # 保存到配置
        config.set("recent_workflows", recent_workflows)
        config.save()

        # 刷新显示
        self._load_recent_workflows()

        _logger.info(f"最近工作流已更新: {title}")

    def _on_action_clicked(self, action_id: str) -> None:
        """处理快速操作点击"""
        _logger.info(f"快速操作点击: {action_id}")
        self.navigate_requested.emit(action_id)

    def _on_recent_clicked(self, workflow_id: str, file_path: str = "") -> None:
        """处理最近工作流点击"""
        _logger.info(f"最近工作流点击: {workflow_id}, file_path={file_path}")
        self.load_workflow_requested.emit("nodes", file_path)

    def _apply_styles(self) -> None:
        if hasattr(self, "_scroll_area"):
            self._scroll_area.setStyleSheet(Theme.get_home_scroll_area_stylesheet())
        if hasattr(self, "_scroll_content"):
            self._scroll_content.setStyleSheet(Theme.get_transparent_background_stylesheet())
        if hasattr(self, "_quick_actions_widget"):
            self._quick_actions_widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        if hasattr(self, "_recent_section"):
            self._recent_section.setStyleSheet(Theme.get_transparent_background_stylesheet())
        if hasattr(self, "_recent_list_widget"):
            self._recent_list_widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        if hasattr(self, "_quick_actions_widget"):
            self._quick_actions_widget.setStyleSheet(Theme.get_transparent_background_stylesheet())
        if hasattr(self, "_recent_section"):
            self._recent_section.setStyleSheet(Theme.get_transparent_background_stylesheet())
        if hasattr(self, "_recent_list_widget"):
            self._recent_list_widget.setStyleSheet(Theme.get_transparent_background_stylesheet())

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        self.setStyleSheet(Theme.get_home_page_stylesheet())
        self._apply_styles()

        # 刷新头部
        self._header.setStyleSheet(Theme.get_home_header_stylesheet())
        self._title_label.setStyleSheet(Theme.get_home_title_stylesheet())
        self._subtitle_label.setStyleSheet(Theme.get_home_subtitle_stylesheet())

        # 刷新快速操作卡片
        for card in self._quick_action_cards:
            card.refresh_theme()

        # 刷新最近工作流区域标题
        self._recent_title.setStyleSheet(Theme.get_home_section_title_stylesheet())

        # 刷新最近工作流项
        for item in self._recent_items:
            if isinstance(item, RecentWorkflowItem):
                item.refresh_theme()

        # 刷新页脚
        self._footer.setStyleSheet(Theme.get_footer_stylesheet())
        self._status_label.setStyleSheet(Theme.get_footer_status_stylesheet())
