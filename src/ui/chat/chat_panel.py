# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional, List, Dict

from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer, QUrl, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QTextEdit,
    QPushButton,
    QFrame,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from src.agent.agent_integration import AgentIntegration
from src.agent.api_key_manager import ApiKeyManager
from src.ui.chat.settings_panel import AgentSettingsDialog
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.agent.mcp_server_manager import McpServerManager
    from src.agent.skill_manager import SkillManager
    from src.storage.repositories import ChatHistoryRepository

_logger = get_logger(__name__)


def _extract_text_from_msg(msg: Any) -> str:
    """Extract text content from AgentScope Msg object.

    Handles both string content and list[ContentBlock] formats.

    Args:
        msg: AgentScope Msg object

    Returns:
        Extracted text string, or empty string if extraction fails
    """
    if msg is None:
        return ""

    content = getattr(msg, "content", None)
    if content is None:
        return ""

    # Case 1: Content is a plain string
    if isinstance(content, str):
        return content

    # Case 2: Content is a list of ContentBlocks
    if isinstance(content, list):
        text_parts = []
        for block in content:
            # Handle dict-style content blocks
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            # Handle object-style content blocks (TextBlock, etc.)
            elif hasattr(block, "type") and block.type == "text":
                text_parts.append(getattr(block, "text", ""))

        return "".join(text_parts)

    # Fallback: convert to string
    return str(content)


def _extract_blocks_from_msg(msg: Any) -> List[Dict[str, Any]]:
    """Extract all content blocks from AgentScope Msg object.

    Handles both string content and list[ContentBlock] formats.

    Args:
        msg: AgentScope Msg object

    Returns:
        List of content block dictionaries
    """
    if msg is None:
        return []

    content = getattr(msg, "content", None)
    if content is None:
        return []

    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    if isinstance(content, list):
        blocks = []
        for block in content:
            if isinstance(block, dict):
                blocks.append(block)
            elif hasattr(block, "type"):
                block_dict = {"type": getattr(block, "type", "unknown")}
                if block_dict["type"] == "text":
                    block_dict["text"] = getattr(block, "text", "")
                elif block_dict["type"] == "thinking":
                    block_dict["thinking"] = getattr(block, "thinking", "")
                elif block_dict["type"] == "tool_use":
                    block_dict["id"] = getattr(block, "id", "")
                    block_dict["name"] = getattr(block, "name", "")
                    block_dict["input"] = getattr(block, "input", {})
                elif block_dict["type"] == "tool_result":
                    block_dict["id"] = getattr(block, "id", "")
                    block_dict["name"] = getattr(block, "name", "")
                    block_dict["output"] = getattr(block, "output", "")
                elif block_dict["type"] == "image":
                    source = getattr(block, "source", None)
                    if source:
                        block_dict["source"] = {
                            "type": getattr(source, "type", "url"),
                            "url": getattr(source, "url", ""),
                        }
                elif block_dict["type"] == "audio":
                    source = getattr(block, "source", None)
                    if source:
                        block_dict["source"] = {
                            "type": getattr(source, "type", "url"),
                            "url": getattr(source, "url", ""),
                        }
                elif block_dict["type"] == "video":
                    source = getattr(block, "source", None)
                    if source:
                        block_dict["source"] = {
                            "type": getattr(source, "type", "url"),
                            "url": getattr(source, "url", ""),
                        }
                blocks.append(block_dict)
        return blocks

    return [{"type": "text", "text": str(content)}]


def _normalize_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize block data to ensure media blocks have proper 'source' format.

    Converts legacy formats like {"type": "image", "url": "..."} to
    {"type": "image", "source": {"type": "url", "url": "..."}}.
    """
    normalized = []
    for block in blocks:
        block_type = block.get("type", "text")
        if block_type in ("image", "audio", "video") and "source" not in block:
            url = block.get("url", "")
            if url.startswith("file://"):
                url = url[7:]
            block = {
                "type": block_type,
                "source": {
                    "type": "url",
                    "url": url,
                },
            }
        normalized.append(block)
    return normalized


class AgentWorker(QThread):
    response_ready = Signal(str)
    block_update = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        agent: AgentIntegration,
        message: str | List[Dict[str, Any]],
        streaming_callback: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._agent = agent
        self._message = message
        self._streaming_callback = streaming_callback

    def run(self) -> None:
        try:
            msg_preview = (
                self._message[:50]
                if isinstance(self._message, str)
                else f"[multimodal: {len(self._message)} blocks]"
            )
            _logger.info(f"AgentWorker: 开始处理消息: {msg_preview}...")

            if self._streaming_callback:
                self._agent.register_streaming_callback(self._streaming_callback)

            response = self._agent.chat(self._message)
            _logger.info(f"AgentWorker: 获取到响应， length: {len(response)}")

            if self._streaming_callback:
                self._agent.unregister_streaming_callback(self._streaming_callback)

            self.response_ready.emit(response)
        except Exception as e:
            _logger.error(f"AgentWorker: 发生错误: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


from src.ui.chat.message_widget import MarkdownMessageWidget
from src.ui.chat.composite_message_widget import CompositeMessageWidget


class SessionItemWidget(QWidget):
    """单个会话项组件 — 悬停时显示删除按钮"""

    def __init__(self, session: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_id = session.get("id", "")
        self._setup_ui(session)

    def _setup_ui(self, session: Dict) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 4, 8)
        layout.setSpacing(6)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        title = session.get("title", "未命名会话")
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("text_primary")};
                font-size: 13px;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        info_layout.addWidget(self._title_label)

        msg_count = session.get("message_count", 0)
        updated = session.get("updated_at", "")[:10]
        self._meta_label = QLabel(f"{msg_count}条消息 · {updated}")
        self._meta_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("text_secondary")};
                font-size: 11px;
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        info_layout.addWidget(self._meta_label)

        layout.addLayout(info_layout, 1)

        self._delete_btn = QPushButton("✕")
        self._delete_btn.setFixedSize(22, 22)
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setToolTip("删除此会话")
        self._delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.hex("text_hint")};
                border: none;
                font-size: 13px;
                border-radius: 11px;
            }}
            QPushButton:hover {{
                background-color: {Theme.hex("danger_hover_bg")};
                color: white;
            }}
        """)
        self._delete_btn.hide()
        layout.addWidget(self._delete_btn)

    def set_delete_handler(self, handler) -> None:
        self._delete_btn.clicked.connect(handler)

    def enterEvent(self, event) -> None:
        self._delete_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._delete_btn.hide()
        super().leaveEvent(event)


class SessionListWidget(QWidget, ThemeAwareMixin):
    """会话列表组件 - 显示历史会话，支持切换、新建和删除"""

    session_selected = Signal(str)  # session_id
    session_delete_requested = Signal(str)  # session_id
    new_session_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QFrame()
        self._header.setStyleSheet(Theme.get_session_list_header_stylesheet())
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        self._title_label = QLabel("会话历史")
        self._title_label.setStyleSheet(Theme.get_session_list_title_stylesheet())
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        self._new_btn = QPushButton("+ 新建")
        self._new_btn.setFixedSize(60, 24)
        self._new_btn.clicked.connect(self.new_session_requested.emit)
        self._new_btn.setStyleSheet(Theme.get_session_new_button_stylesheet())
        header_layout.addWidget(self._new_btn)

        layout.addWidget(self._header)

        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(Theme.get_session_list_widget_stylesheet())
        self._list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list_widget, 1)

        self.setMinimumWidth(200)
        self.setMaximumWidth(300)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.session_selected.emit(session_id)

    def _on_delete_session(self, session_id: str) -> None:
        self.session_delete_requested.emit(session_id)

    def set_sessions(self, sessions: List[Dict]) -> None:
        """设置会话列表"""
        self._list_widget.clear()
        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, session["id"])
            item.setSizeHint(QSize(0, 58))
            self._list_widget.addItem(item)

            widget = SessionItemWidget(session, self._list_widget)
            widget.set_delete_handler(lambda checked, sid=session["id"]: self._on_delete_session(sid))
            self._list_widget.setItemWidget(item, widget)

    def select_session(self, session_id: str) -> None:
        self._list_widget.blockSignals(True)
        try:
            for i in range(self._list_widget.count()):
                item = self._list_widget.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == session_id:
                    self._list_widget.setCurrentItem(item)
                    break
        finally:
            self._list_widget.blockSignals(False)

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        if hasattr(self, "_header"):
            self._header.setStyleSheet(Theme.get_session_list_header_stylesheet())
        if hasattr(self, "_title_label"):
            self._title_label.setStyleSheet(Theme.get_session_list_title_stylesheet())
        if hasattr(self, "_new_btn"):
            self._new_btn.setStyleSheet(Theme.get_session_new_button_stylesheet())
        if hasattr(self, "_list_widget"):
            self._list_widget.setStyleSheet(Theme.get_session_list_widget_stylesheet())


class ChatPanel(QWidget, ThemeAwareMixin):
    message_sent = Signal(str)

    def __init__(
        self,
        agent: Optional[AgentIntegration] = None,
        api_key_manager: Optional[ApiKeyManager] = None,
        mcp_manager: Optional["McpServerManager"] = None,
        skill_manager: Optional["SkillManager"] = None,
        history_repository: Optional["ChatHistoryRepository"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_theme_awareness()
        self._agent = agent
        self._api_key_manager = api_key_manager
        self._mcp_manager = mcp_manager
        self._skill_manager = skill_manager
        self._history_repository = history_repository
        self._messages: list[MarkdownMessageWidget | CompositeMessageWidget] = []
        self._current_provider: Optional[str] = None
        self._worker: Optional[AgentWorker] = None
        self._current_session_id: Optional[str] = None
        self._streaming_message: Optional[MarkdownMessageWidget | CompositeMessageWidget] = None
        self._streaming_text: str = ""
        self._streaming_blocks: List[Dict[str, Any]] = []
        self._current_block_type = "unknown"
        self._attachments: List[Dict[str, Any]] = []

        self._setup_ui()
        self._connect_signals()
        self._load_api_keys()

        # 如果有持久化存储，加载会话列表
        if self._history_repository:
            self._load_sessions()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(Theme.get_splitter_stylesheet())

        # 左侧：会话列表（如果有持久化存储）
        if self._history_repository:
            self._session_list = SessionListWidget()
            self._session_list.session_selected.connect(self._on_session_selected)
            self._session_list.session_delete_requested.connect(self._on_session_delete)
            self._session_list.new_session_requested.connect(self._on_new_session)
            splitter.addWidget(self._session_list)

        # 右侧：聊天区域
        self._chat_widget = QWidget()
        chat_layout = QVBoxLayout(self._chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self._header = self._create_header()
        chat_layout.addWidget(self._header)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet(Theme.get_chat_scroll_area_stylesheet())

        self._messages_widget = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._messages_layout.setSpacing(8)
        self._messages_layout.setContentsMargins(12, 12, 12, 12)
        self._messages_widget.setStyleSheet(Theme.get_chat_messages_widget_stylesheet())

        self._scroll_area.setWidget(self._messages_widget)
        chat_layout.addWidget(self._scroll_area, 1)

        self._input_area = self._create_input_area()
        chat_layout.addWidget(self._input_area)

        self._chat_widget.setStyleSheet(Theme.get_chat_panel_stylesheet())
        splitter.addWidget(self._chat_widget)

        # 设置分割比例
        splitter.setSizes([200, 600])

        main_layout.addWidget(splitter)

    def _create_header(self) -> QWidget:
        self._header_frame = QFrame()
        self._header_frame.setFixedHeight(50)
        self._header_frame.setStyleSheet(Theme.get_chat_header_stylesheet())
        layout = QHBoxLayout(self._header_frame)
        layout.setContentsMargins(16, 0, 16, 0)

        title_layout = QVBoxLayout()
        self._title_label = QLabel("🤖 AI 助手")
        self._title_label.setStyleSheet(Theme.get_chat_title_label_stylesheet())
        title_layout.addWidget(self._title_label)

        self._status_label = QLabel("请选择API密钥")
        self._status_label.setStyleSheet(Theme.get_chat_status_label_stylesheet())
        title_layout.addWidget(self._status_label)
        layout.addLayout(title_layout)

        self._api_key_combo = QComboBox()
        self._api_key_combo.setPlaceholderText("选择API密钥")
        self._api_key_combo.setMinimumWidth(200)
        self._api_key_combo.setStyleSheet(Theme.get_combobox_stylesheet())
        self._api_key_combo.currentIndexChanged.connect(self._on_api_key_changed)
        layout.addWidget(self._api_key_combo)

        layout.addStretch()

        self._settings_btn = QPushButton("⚙ 设置")
        self._settings_btn.setFixedHeight(28)
        self._settings_btn.clicked.connect(self._open_settings)
        self._settings_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.clicked.connect(self._clear_chat)
        self._clear_btn.setStyleSheet(Theme.get_chat_clear_button_stylesheet())

        layout.addWidget(self._settings_btn)
        layout.addWidget(self._clear_btn)

        return self._header_frame

    def _create_input_area(self) -> QWidget:
        self._input_area_frame = QFrame()
        self._input_area_frame.setMinimumHeight(120)
        layout = QVBoxLayout(self._input_area_frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 附件预览区域 — 独立滚动，不影响输入框高度
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setFixedHeight(90)
        self._preview_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._preview_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._preview_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)

        self._preview_container = QWidget()
        self._preview_layout = QHBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_layout.setSpacing(8)
        self._preview_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._preview_scroll.setWidget(self._preview_container)
        self._preview_scroll.hide()

        self._input_text = QTextEdit()
        self._input_text.setPlaceholderText("输入消息，与AI助手对话...")
        self._input_text.setStyleSheet(Theme.get_chat_input_stylesheet())

        # 底部按钮行：附件按钮居左 + 发送按钮居右
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # 多模态附件按钮（默认隐藏，根据 API Key 支持类型显示）
        self._image_btn = QPushButton("📷 图片")
        self._image_btn.setToolTip("添加图片")
        self._image_btn.setFixedSize(70, 32)
        self._image_btn.clicked.connect(self._select_image)
        self._image_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        self._image_btn.hide()

        self._audio_btn = QPushButton("🎤 音频")
        self._audio_btn.setToolTip("添加音频")
        self._audio_btn.setFixedSize(70, 32)
        self._audio_btn.clicked.connect(self._select_audio)
        self._audio_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        self._audio_btn.hide()

        self._video_btn = QPushButton("🎬 视频")
        self._video_btn.setToolTip("添加视频")
        self._video_btn.setFixedSize(70, 32)
        self._video_btn.clicked.connect(self._select_video)
        self._video_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        self._video_btn.hide()

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedHeight(32)
        self._send_btn.clicked.connect(self._send_message)
        self._send_btn.setStyleSheet(Theme.get_chat_send_button_stylesheet())
        self._send_btn.setEnabled(False)

        # 左侧附件按钮
        button_layout.addWidget(self._image_btn)
        button_layout.addWidget(self._audio_btn)
        button_layout.addWidget(self._video_btn)
        button_layout.addStretch()
        # 右侧发送按钮
        button_layout.addWidget(self._send_btn)

        layout.addWidget(self._preview_scroll)
        layout.addWidget(self._input_text, 1)
        layout.addLayout(button_layout)

        return self._input_area_frame

    def _select_image(self):
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if file_path:
            self._add_multimodal_attachment("image", file_path)

    def _select_audio(self):
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择音频", "", "Audio (*.mp3 *.wav *.aac *.ogg *.flac)"
        )
        if file_path:
            self._add_multimodal_attachment("audio", file_path)

    def _select_video(self):
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频", "", "Video (*.mp4 *.avi *.mov *.mkv *.webm)"
        )
        if file_path:
            self._add_multimodal_attachment("video", file_path)

    def _add_multimodal_attachment(self, media_type: str, file_path: str):
        from pathlib import Path

        attachment = {
            "type": media_type,
            "path": file_path,
            "url": f"file://{file_path}",
        }
        self._attachments.append(attachment)

        # 创建预览卡片
        card = self._create_preview_card(attachment)
        self._preview_layout.addWidget(card)

        self._preview_scroll.show()
        _logger.info(f"添加{media_type}附件: {file_path}")

    def _create_preview_card(self, attachment: Dict[str, Any]) -> QFrame:
        """创建附件预览卡片，包含可视化预览和删除按钮"""
        from pathlib import Path

        media_type = attachment["type"]
        file_path = attachment["path"]
        file_name = Path(file_path).name

        card = QFrame()
        card.setFixedHeight(80)
        card.setMinimumWidth(100)
        card.setMaximumWidth(160)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.hex("background_secondary")};
                border: 1px solid {Theme.hex("border_primary")};
                border-radius: 6px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        # 预览内容区域
        preview_widget = self._create_media_preview(media_type, file_path)
        card_layout.addWidget(preview_widget, 1)

        # 底部：文件名 + 删除按钮
        bottom = QHBoxLayout()
        bottom.setSpacing(4)

        name_label = QLabel(file_name)
        name_label.setFixedHeight(16)
        name_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("text_secondary")};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        name_label.setToolTip(file_path)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(16, 16)
        remove_btn.setStyleSheet(Theme.get_small_icon_button_stylesheet())
        remove_btn.clicked.connect(lambda checked, a=attachment: self._remove_attachment(a))

        bottom.addWidget(name_label, 1)
        bottom.addWidget(remove_btn)
        card_layout.addLayout(bottom)

        # 存储附件引用到卡片，方便后续删除
        card._attachment_ref = attachment
        return card

    def _create_media_preview(self, media_type: str, file_path: str) -> QWidget:
        """根据媒体类型创建预览控件"""
        if media_type == "image":
            return self._create_image_preview(file_path)
        elif media_type == "audio":
            return self._create_audio_preview(file_path)
        elif media_type == "video":
            return self._create_video_preview(file_path)
        else:
            label = QLabel("未知类型")
            label.setStyleSheet(f"color: {Theme.hex('text_secondary')}; background: transparent;")
            return label

    def _create_image_preview(self, file_path: str) -> QLabel:
        """创建图片缩略图预览"""
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(44)

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                140, 44,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(scaled)
        else:
            label.setText("[无法加载]")
            label.setStyleSheet(f"color: {Theme.hex('text_secondary')}; background: transparent; border: none;")

        return label

    def _create_audio_preview(self, file_path: str) -> QWidget:
        """创建音频文件预览（带播放按钮）"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        icon = QLabel("🎵")
        icon.setFixedWidth(20)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        play_btn = QPushButton("▶")
        play_btn.setFixedSize(28, 28)
        play_btn.setStyleSheet(Theme.get_media_play_button_stylesheet())

        player = QMediaPlayer(widget)
        audio_output = QAudioOutput(widget)
        player.setAudioOutput(audio_output)
        player.setSource(QUrl.fromLocalFile(file_path))

        def toggle_play():
            if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.pause()
                play_btn.setText("▶")
            else:
                player.play()
                play_btn.setText("⏸")

        play_btn.clicked.connect(toggle_play)

        layout.addWidget(icon)
        layout.addWidget(play_btn)
        layout.addStretch()

        return widget

    def _create_video_preview(self, file_path: str) -> QWidget:
        """创建视频缩略图预览"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # 视频预览使用小型播放控件
        video_widget = QVideoWidget()
        video_widget.setFixedHeight(36)
        video_widget.setMinimumWidth(80)
        video_widget.setStyleSheet(f"""
            QVideoWidget {{
                background-color: #000;
                border-radius: 3px;
            }}
        """)

        player = QMediaPlayer(widget)
        audio_output = QAudioOutput(widget)
        player.setAudioOutput(audio_output)
        player.setVideoOutput(video_widget)
        player.setSource(QUrl.fromLocalFile(file_path))

        # 播放/暂停按钮
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(22, 22)
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.hex("border_focus")};
                color: white;
                border: none;
                border-radius: 11px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {Theme.hex("accent_hover_bg")};
            }}
        """)

        def toggle_play():
            if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.pause()
                play_btn.setText("▶")
            else:
                player.play()
                play_btn.setText("⏸")

        play_btn.clicked.connect(toggle_play)

        controls = QHBoxLayout()
        controls.addWidget(play_btn)
        controls.addStretch()

        layout.addWidget(video_widget)
        layout.addLayout(controls)

        return widget

    def _remove_attachment(self, attachment: Dict[str, Any]):
        """移除指定附件及其预览卡片"""
        if attachment in self._attachments:
            self._attachments.remove(attachment)

        # 找到并删除对应的预览卡片
        layout = self._preview_layout
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, QFrame) and hasattr(widget, "_attachment_ref"):
                if widget._attachment_ref is attachment:
                    layout.removeWidget(widget)
                    widget.deleteLater()
                    break

        # 没有附件时隐藏预览区
        if not self._attachments:
            self._preview_scroll.hide()

        _logger.info(f"移除附件: {attachment['path']}")

    def _clear_preview_area(self):
        """清空所有预览卡片"""
        layout = self._preview_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._preview_scroll.hide()

    def _connect_signals(self) -> None:
        self._input_text.textChanged.connect(self._on_text_changed)

    def _load_api_keys(self) -> None:
        self._api_key_combo.blockSignals(True)
        self._api_key_combo.clear()

        if self._api_key_manager:
            configs = self._api_key_manager.list_all_configs()
            enabled_configs = [c for c in configs if c.get("enabled")]

            for config in enabled_configs:
                provider = config["provider"]
                model_name = config.get("model_name", "")
                display_text = f"{provider}"
                if model_name:
                    display_text += f" ({model_name})"
                self._api_key_combo.addItem(display_text, (provider, model_name))

        self._api_key_combo.blockSignals(False)

    def _load_sessions(self) -> None:
        """加载会话列表"""
        if not self._history_repository:
            return

        sessions = self._history_repository.list_sessions(limit=50)
        self._session_list.set_sessions(sessions)

    def _on_session_selected(self, session_id: str) -> None:
        """切换到选中的会话"""
        if not self._agent or not self._history_repository:
            return

        success = self._agent.switch_session(session_id)
        if success:
            self._current_session_id = session_id
            self._load_session_messages()
            self._load_sessions()
            self._session_list.select_session(session_id)
            _logger.info(f"切换到会话: {session_id}")
        else:
            _logger.warning(f"切换会话失败: {session_id}")

    def _on_session_delete(self, session_id: str) -> None:
        if not self._history_repository:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这个会话吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            is_current_session = session_id == self._current_session_id

            self._history_repository.delete_session(session_id)
            self._load_sessions()
            _logger.info(f"已删除会话: {session_id}")

            if is_current_session:
                self._clear_messages_ui()
                self._current_session_id = None
                sessions = self._history_repository.list_sessions(limit=1)
                if sessions:
                    self._on_session_selected(sessions[0]["id"])

    def _on_new_session(self) -> None:
        if not self._agent:
            return

        # 清空当前消息
        self._clear_messages_ui()

        # 创建新会话
        if self._history_repository and self._agent.is_persisted:
            new_session_id = self._agent.create_new_session()
            self._current_session_id = new_session_id
            self._load_sessions()
            self._agent._sync_history_to_memory()
            _logger.info("重置为新的内存会话")

    def _load_session_messages(self) -> None:
        """加载当前会话的消息到UI"""
        self._clear_messages_ui()

        if not self._agent:
            return

        history = self._agent.get_history()
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list) and content and isinstance(content[0], dict):
                blocks = _normalize_blocks(content)
            elif isinstance(content, str):
                blocks = [{"type": "text", "text": content}]
            else:
                blocks = _extract_blocks_from_msg(msg)

            self._add_message_widget(role, blocks)

    def _clear_messages_ui(self) -> None:
        """清空消息UI"""
        for message in self._messages:
            message.deleteLater()
        self._messages.clear()

    def _on_api_key_changed(self, index: int) -> None:
        if index < 0:
            self._current_provider = None
            self._send_btn.setEnabled(False)
            self._set_status("请选择API密钥")
            return

        item_data = self._api_key_combo.itemData(index)
        if not item_data:
            self._send_btn.setEnabled(False)
            return

        provider, model_name = item_data if isinstance(item_data, tuple) else (item_data, "")
        self._current_provider = provider

        config = None
        if self._api_key_manager:
            config = self._api_key_manager.get_config(provider, model_name)
        if config:
            model_name = config.get("model_name", "") if config else model_name
            base_url = config.get("base_url", "") if config else ""
        model_name = config.get("model_name", "") if config else model_name
        base_url = config.get("base_url", "") if config else ""

        supported_types = config.get("supported_types", ["text"]) if config else ["text"]
        has_image = "image" in supported_types
        has_audio = "audio" in supported_types
        has_video = "video" in supported_types

        self._image_btn.setVisible(has_image)
        self._audio_btn.setVisible(has_audio)
        self._video_btn.setVisible(has_video)

        has_multimodal = any([has_image, has_audio, has_video])

        # 移除当前附件中不受支持的类型
        if self._attachments:
            type_map = {"image": has_image, "audio": has_audio, "video": has_video}
            removed_types = [t for t, ok in type_map.items() if not ok]
            if removed_types:
                to_remove = [a for a in self._attachments if a.get("type") in removed_types]
                for attachment in to_remove:
                    self._remove_attachment(attachment)
                if to_remove:
                    _logger.info(f"切换API密钥后移除不支持的附件: {[a['type'] for a in to_remove]}")

        _logger.info(
            f"切换API密钥: {provider}/{model_name or 'default'}, "
            f"支持类型: {supported_types}, 多模态: {has_multimodal}"
        )

        if model_name:
            self._set_status(f"已选择: {provider} ({model_name})")
        else:
            self._set_status(f"已选择: {provider}")

        self._send_btn.setEnabled(True)

        if self._agent:
            _logger.info(f"开始初始化Agent: provider={provider}, model_name={model_name}")
            success = self._agent.initialize(provider, model_name=model_name, base_url=base_url)
            if success:
                _logger.info(f"Agent初始化成功: {provider}")
                # 同步当前会话历史到新Agent的memory
                self._agent._sync_history_to_memory()
                # 如果有持久化存储且没有当前会话，加载最新会话
                if self._history_repository and not self._current_session_id:
                    sessions = self._history_repository.list_sessions(limit=1)
                    if sessions:
                        self._on_session_selected(sessions[0]["id"])
            else:
                _logger.error(f"Agent初始化失败: {provider}")
                self._set_status("Agent初始化失败")

    def _on_text_changed(self) -> None:
        has_text = bool(self._input_text.toPlainText().strip())
        self._send_btn.setEnabled(has_text and self._current_provider is not None)

    def _create_streaming_callback(self) -> Callable:
        """Create streaming callback for real-time block updates.

        This callback is invoked by the agent's post_print hook during streaming.
        It extracts content blocks (thinking, tool_use, tool_result, text) from
        the Msg output and emits block_update signals for UI rendering.

        Returns:
            Callable: The streaming callback function
        """

        def callback(agent_self: Any, kwargs: dict, output: Any) -> None:
            if kwargs is None:
                return
            msg = kwargs.get("msg", None)
            # Extract all content blocks from the Msg object
            blocks = _extract_blocks_from_msg(msg)
            if self._worker:
                self._worker.block_update.emit(blocks)

        return callback

    def _send_message(self) -> None:
        if not self._current_provider:
            self._set_status("请先选择API密钥")
            return

        text = self._input_text.toPlainText().strip()
        if not text and not self._attachments:
            return

        display_blocks = None
        if self._attachments:
            content = [{"type": "text", "text": text}]
            for attachment in self._attachments:
                content.append(
                    {
                        "type": attachment["type"],
                        "url": attachment["url"],
                    }
                )
            message_content = content

            # Build display blocks with proper source for block widgets
            display_blocks = [{"type": "text", "text": text}] if text else []
            for attachment in self._attachments:
                display_blocks.append(
                    {
                        "type": attachment["type"],
                        "source": {
                            "type": "url",
                            "url": attachment["path"],
                        },
                    }
                )
        else:
            message_content = text

        self._input_text.clear()
        self._attachments.clear()
        self._clear_preview_area()

        if display_blocks:
            self._add_message_widget("user", display_blocks)
        else:
            self._add_message_widget("user", text)
        self.message_sent.emit(text)

        if not self._agent or not self._agent.is_initialized:
            self.add_message("system", "请先选择API密钥")
            return

        self._set_status("思考中...")
        self._send_btn.setEnabled(False)

        self._worker = AgentWorker(self._agent, message_content, self._create_streaming_callback())
        self._worker.response_ready.connect(self._on_agent_response)
        self._worker.block_update.connect(self._on_block_update)
        self._worker.error_occurred.connect(self._on_agent_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_block_update(self, block_datas: List[Dict[str, Any]]) -> None:
        block_data = block_datas[-1]
        _logger.info(f"Block update: {block_data.get('type', 'unknown')}")
        block_type = block_data.get("type", "text")

        if self._streaming_message is None:
            self._streaming_message = CompositeMessageWidget("assistant")
            self._messages_layout.addWidget(self._streaming_message)
            self._messages.append(self._streaming_message)
            self._streaming_blocks = []

        self._streaming_blocks.append(block_data)

        if block_type == "thinking":
            thinking_content = block_data.get("thinking", "")
            # Try to update existing thinking block, if not found, add new one
            if self._current_block_type == block_type:
                self._streaming_message.update_last_thinking_block(thinking_content)
            else:
                self._streaming_message.add_or_update_block(block_data)
        elif block_type == "tool_use":
            self._streaming_message.add_or_update_block(block_data)
        elif block_type == "tool_result":
            self._streaming_message.add_or_update_block(block_data)
        elif block_type == "text":
            text_content = block_data.get("text", "")
            # Try to update existing text block, if not found, add new one
            if self._current_block_type == block_type:
                self._streaming_message.update_last_text_block(text_content)
            else:
                self._streaming_message.add_or_update_block(block_data)
        elif block_type in ("image", "audio", "video"):
            self._streaming_message.add_or_update_block(block_data)

        if self._current_block_type != block_type:
            self._current_block_type = block_type

        QTimer.singleShot(100, self._scroll_to_bottom)

    def _on_agent_response(self, response: str) -> None:
        _logger.info(f"Agent response received, length: {len(response)}")
        self._set_status("就绪" if self._current_provider else "请选择API密钥")

        if self._streaming_message and isinstance(self._streaming_message, CompositeMessageWidget):
            if self._streaming_blocks:
                self._streaming_message._blocks = self._streaming_blocks.copy()
            self._streaming_message = None
            self._streaming_blocks = []
            self._streaming_text = ""

        QTimer.singleShot(10, self._scroll_to_bottom)

    def _on_agent_error(self, error: str) -> None:
        _logger.error(f"Agent error: {error}")
        self._set_status(f"错误: {error}")
        self._streaming_message = None
        self._streaming_blocks = []
        self._streaming_text = ""

    def _on_worker_finished(self) -> None:
        _logger.info("AgentWorker完成")
        self._send_btn.setEnabled(self._current_provider is not None)
        self._current_block_type = "unknown"
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _add_message_widget(self, role: str, content: Any) -> None:
        if isinstance(content, list) and content and isinstance(content[0], dict):
            message_widget = CompositeMessageWidget(role, content)
        elif isinstance(content, str):
            message_widget = MarkdownMessageWidget(role, content)
        else:
            message_widget = MarkdownMessageWidget(role, str(content))

        self._messages_layout.addWidget(message_widget)
        self._messages.append(message_widget)
        QTimer.singleShot(100, self._scroll_to_bottom)

    def add_message(self, role: str, content: str) -> None:
        """添加消息（公开接口）"""
        self._add_message_widget(role, content)

    def _scroll_to_bottom(self) -> None:
        scrollbar = self._scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _set_status(self, status: str) -> None:
        self._status_label.setText(status)

    def _clear_chat(self) -> None:
        """清空当前对话"""
        self._clear_messages_ui()

        if self._agent:
            self._agent.reset()

        self._set_status("就绪" if self._current_provider else "请选择API密钥")
        _logger.info("对话已清空")

    def set_agent(self, agent: AgentIntegration) -> None:
        self._agent = agent
        if self._current_provider:
            self._set_status("就绪")

    def set_api_key_manager(self, manager: ApiKeyManager) -> None:
        self._api_key_manager = manager
        self._load_api_keys()

    def set_mcp_manager(self, manager: McpServerManager) -> None:
        self._mcp_manager = manager

    def set_skill_manager(self, manager: SkillManager) -> None:
        self._skill_manager = manager

    def set_history_repository(self, repository: "ChatHistoryRepository") -> None:
        """设置会话历史存储库"""
        self._history_repository = repository
        self._load_sessions()

    def _open_settings(self) -> None:
        if self._api_key_manager:
            dialog = AgentSettingsDialog(
                api_key_manager=self._api_key_manager,
                mcp_manager=self._mcp_manager,
                skill_manager=self._skill_manager,
                on_api_key_changed=self._load_api_keys,
                parent=self,
            )
            dialog.setStyleSheet(Theme.get_settings_dialog_stylesheet())
            dialog.exec()
        else:
            _logger.warning("API密钥管理器未初始化")

    def refresh_theme(self) -> None:
        """刷新主题样式"""
        if hasattr(self, "_session_list"):
            self._session_list.refresh_theme()
        if hasattr(self, "_scroll_area"):
            self._scroll_area.setStyleSheet(Theme.get_chat_scroll_area_stylesheet())
        if hasattr(self, "_chat_widget"):
            self._chat_widget.setStyleSheet(Theme.get_chat_panel_stylesheet())
        if hasattr(self, "_header_frame"):
            self._header_frame.setStyleSheet(Theme.get_chat_header_stylesheet())
        if hasattr(self, "_title_label"):
            self._title_label.setStyleSheet(Theme.get_chat_title_label_stylesheet())
        if hasattr(self, "_status_label"):
            self._status_label.setStyleSheet(Theme.get_chat_status_label_stylesheet())
        if hasattr(self, "_api_key_combo"):
            self._api_key_combo.setStyleSheet(Theme.get_combobox_stylesheet())
        if hasattr(self, "_settings_btn"):
            self._settings_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        if hasattr(self, "_clear_btn"):
            self._clear_btn.setStyleSheet(Theme.get_chat_clear_button_stylesheet())
        if hasattr(self, "_messages_widget"):
            self._messages_widget.setStyleSheet(Theme.get_chat_messages_widget_stylesheet())
        if hasattr(self, "_input_area"):
            self._input_area.setStyleSheet(Theme.get_chat_input_area_stylesheet())
        if hasattr(self, "_input_text"):
            self._input_text.setStyleSheet(Theme.get_chat_input_stylesheet())
        if hasattr(self, "_send_btn"):
            self._send_btn.setStyleSheet(Theme.get_chat_send_button_stylesheet())
        if hasattr(self, "_image_btn"):
            self._image_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        if hasattr(self, "_audio_btn"):
            self._audio_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
        if hasattr(self, "_video_btn"):
            self._video_btn.setStyleSheet(Theme.get_panel_button_stylesheet())
