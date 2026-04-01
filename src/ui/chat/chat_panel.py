# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional, List, Dict

from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer
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
)

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
                blocks.append(block_dict)
        return blocks

    return [{"type": "text", "text": str(content)}]


class AgentWorker(QThread):
    response_ready = Signal(str)
    block_update = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        agent: AgentIntegration,
        message: str,
        streaming_callback: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._agent = agent
        self._message = message
        self._streaming_callback = streaming_callback

    def run(self) -> None:
        try:
            _logger.info(f"AgentWorker: 开始处理消息: {self._message[:50]}...")

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
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list_widget, 1)

        self._delete_area = QFrame()
        self._delete_area.setStyleSheet(Theme.get_delete_area_stylesheet())
        delete_layout = QHBoxLayout(self._delete_area)
        delete_layout.setContentsMargins(8, 8, 8, 8)

        self._delete_btn = QPushButton("删除选中会话")
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        self._delete_btn.setStyleSheet(Theme.get_session_delete_button_stylesheet())
        delete_layout.addWidget(self._delete_btn)

        layout.addWidget(self._delete_area)

        self.setMinimumWidth(200)
        self.setMaximumWidth(300)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.session_selected.emit(session_id)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.session_selected.emit(session_id)

    def _on_delete_clicked(self) -> None:
        current_item = self._list_widget.currentItem()
        if current_item:
            session_id = current_item.data(Qt.ItemDataRole.UserRole)
            if session_id:
                self.session_delete_requested.emit(session_id)

    def set_sessions(self, sessions: List[Dict]) -> None:
        """设置会话列表"""
        self._list_widget.clear()
        for session in sessions:
            item = QListWidgetItem()
            title = session.get("title", "未命名会话")
            msg_count = session.get("message_count", 0)
            updated = session.get("updated_at", "")[:10]  # 只取日期部分

            item.setText(f"{title}\n{msg_count}条消息 · {updated}")
            item.setData(Qt.ItemDataRole.UserRole, session["id"])
            self._list_widget.addItem(item)

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
        if hasattr(self, "_delete_area"):
            self._delete_area.setStyleSheet(Theme.get_delete_area_stylesheet())
        if hasattr(self, "_delete_btn"):
            self._delete_btn.setStyleSheet(Theme.get_session_delete_button_stylesheet())


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
        self._current_block_type = "unkonwn"

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
        self._input_area_frame.setMaximumHeight(200)
        layout = QVBoxLayout(self._input_area_frame)
        layout.setContentsMargins(12, 8, 12, 8)

        self._input_text = QTextEdit()
        self._input_text.setPlaceholderText("输入消息，与AI助手对话...")
        self._input_text.setStyleSheet(Theme.get_chat_input_stylesheet())

        button_layout = QHBoxLayout()

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedHeight(32)
        self._send_btn.clicked.connect(self._send_message)
        self._send_btn.setStyleSheet(Theme.get_chat_send_button_stylesheet())
        self._send_btn.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self._send_btn)

        layout.addWidget(self._input_text, 1)
        layout.addLayout(button_layout)

        return self._input_area_frame

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
                blocks = content
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

        if self._api_key_manager:
            config = self._api_key_manager.get_config(provider, model_name)
        if config:
            model_name = config.get("model_name", "") if config else model_name
            base_url = config.get("base_url", "") if config else ""
        model_name = config.get("model_name", "") if config else model_name
        base_url = config.get("base_url", "") if config else ""

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
        if not text:
            return

        self._input_text.clear()
        self.add_message("user", text)
        self.message_sent.emit(text)

        if not self._agent or not self._agent.is_initialized:
            self.add_message("system", "请先选择API密钥")
            return

        self._set_status("思考中...")
        self._send_btn.setEnabled(False)

        self._worker = AgentWorker(self._agent, text, self._create_streaming_callback())
        self._worker.response_ready.connect(self._on_agent_response)
        self._worker.block_update.connect(self._on_block_update)
        self._worker.error_occurred.connect(self._on_agent_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()  # Start the worker thread

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
