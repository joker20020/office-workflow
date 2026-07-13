# -*- coding: utf-8 -*-
"""
对话历史管理 - 支持内存和数据库持久化存储

使用 AgentScope Msg 对象存储消息，完整支持 Msg 的序列化和反序列化。

使用方式：
    # 内存模式
    history = ChatHistory()

    # 数据库模式
    from src.storage.database import Database
    from src.storage.repositories import ChatHistoryRepository
    db = Database(Path("data/app.db"))
    repo = ChatHistoryRepository(db)
    history = ChatHistory(repository=repo)

    # 添加消息（自动创建 Msg 对象）
    history.add_message("user", "你好")

    # 或直接传入 Msg 对象
    from agentscope.message import UserMsg
    msg = UserMsg(name="User", content="你好")
    history.add_message(msg=msg)
"""

import json
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agentscope.message import (
    AssistantMsg,
    Base64Source,
    ContentBlock,
    DataBlock,
    Msg,
    SystemMsg,
    TextBlock,
    ToolCallBlock,
    URLSource,
    UserMsg,
)
from pydantic import TypeAdapter

AGENTSCOPE_AVAILABLE = True

_CONTENT_BLOCK_ADAPTER = TypeAdapter(ContentBlock)
_NATIVE_BLOCK_TYPES = {
    "data",
    "hint",
    "text",
    "thinking",
    "tool_call",
    "tool_result",
}
_LEGACY_MEDIA_TYPES = {"image", "audio", "video"}
_LEGACY_TOOL_CALL_TYPES = {"tool_use", "tool-use", "tool-call", "toolUse", "toolCall"}


def serialize_message(msg: Msg) -> dict[str, Any]:
    """Serialize an AgentScope 2.0 message to JSON-compatible data."""
    if not isinstance(msg, Msg):
        raise TypeError("msg must be an AgentScope 2.0 Msg")
    return msg.model_dump(mode="json")


def _parse_data_source(source_data: Any) -> Base64Source | URLSource:
    """Parse a persisted AgentScope data source without losing its fields."""
    if not isinstance(source_data, dict):
        raise ValueError("media block source must be a dictionary")

    source_type = source_data.get("type")
    if source_type == "base64":
        return Base64Source.model_validate(source_data)
    if source_type == "url":
        return URLSource.model_validate(source_data)
    raise ValueError(f"unsupported media source type: {source_type!r}")


def _parse_content_block(block_data: Any, warnings: list[str]) -> ContentBlock:
    """Parse one native block or normalize a legacy persisted block."""
    if not isinstance(block_data, dict):
        warnings.append(
            f"Converted non-dictionary legacy content block: {type(block_data).__name__}",
        )
        return TextBlock(text=json.dumps(block_data, ensure_ascii=False))

    block = deepcopy(block_data)
    block_type = block.get("type")

    if block_type in _LEGACY_MEDIA_TYPES:
        source = _parse_data_source(block.get("source"))
        kwargs = {"source": source}
        if "id" in block:
            kwargs["id"] = block["id"]
        if "name" in block:
            kwargs["name"] = block["name"]
        return DataBlock(**kwargs)

    if block_type in _LEGACY_TOOL_CALL_TYPES:
        block["type"] = "tool_call"
        block_type = "tool_call"

    if block_type == "tool_call" and isinstance(block.get("input"), dict):
        block["input"] = json.dumps(block["input"], ensure_ascii=False)

    if block_type == "data":
        block["source"] = _parse_data_source(block.get("source"))

    if block_type in _NATIVE_BLOCK_TYPES:
        return _CONTENT_BLOCK_ADAPTER.validate_python(block)

    warnings.append(
        f"Converted unsupported legacy content block type {block_type!r} to text",
    )
    return TextBlock(text=json.dumps(block, ensure_ascii=False))


def deserialize_message(data: dict[str, Any]) -> Msg:
    """Load native AgentScope 2.0 data or normalize a legacy message record."""
    if not isinstance(data, dict):
        raise TypeError("message data must be a dictionary")

    message_data = deepcopy(data)
    role = message_data.get("role")
    factories = {
        "user": UserMsg,
        "assistant": AssistantMsg,
        "system": SystemMsg,
    }
    if role not in factories:
        raise ValueError(f"unsupported message role: {role!r}")

    content_data = message_data.get("content")
    migration_warnings: list[str] = []
    if isinstance(content_data, str):
        content: list[ContentBlock] = [TextBlock(text=content_data)]
    elif isinstance(content_data, list):
        content = [_parse_content_block(block, migration_warnings) for block in content_data]
    else:
        raise ValueError("message content must be a string or list")

    metadata = message_data.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("message metadata must be a dictionary")
    metadata = deepcopy(metadata)

    if migration_warnings:
        existing_warnings = metadata.get("migration_warnings")
        if existing_warnings is None:
            metadata["migration_warnings"] = migration_warnings
        elif isinstance(existing_warnings, list):
            metadata["migration_warnings"] = deepcopy(existing_warnings) + migration_warnings
        else:
            metadata["migration_warnings"] = [existing_warnings, *migration_warnings]

    kwargs: dict[str, Any] = {
        "name": message_data.get("name", role.capitalize()),
        "content": content,
        "metadata": metadata,
    }
    if "id" in message_data:
        kwargs["id"] = message_data["id"]
    created_at = message_data.get("created_at", message_data.get("timestamp"))
    if created_at is not None:
        kwargs["created_at"] = created_at
    if "finished_at" in message_data:
        kwargs["finished_at"] = message_data["finished_at"]
    if role == "assistant" and "usage" in message_data:
        kwargs["usage"] = message_data["usage"]

    return factories[role](**kwargs)

if TYPE_CHECKING:
    from src.storage.repositories import ChatHistoryRepository


class ChatHistory:
    """
    对话历史管理器

    支持两种存储模式：
    - 内存模式：使用内存列表存储，不持久化
    - 数据库模式：使用ChatHistoryRepository持久化到SQLite

    内部完全使用 AgentScope Msg 对象存储消息，支持完整的 Msg 序列化。

    Attributes:
        max_messages: 内存模式下最大消息数量（默认100）
        session_id: 当前会话ID（数据库模式必需）
        repository: 数据库存储库（可选）
    """

    def __init__(
        self,
        max_messages: int = 100,
        session_id: Optional[str] = None,
        repository: Optional["ChatHistoryRepository"] = None,
    ):
        self._messages: List[Any] = []  # 存储 Msg 对象
        self._max_messages = max_messages
        self._lock = threading.Lock()

        self._session_id: Optional[str] = session_id
        self._repository: Optional["ChatHistoryRepository"] = repository

        if self._repository and not self._session_id:
            self._session_id = self._repository.create_session()
            self._is_new_session = True
        else:
            self._is_new_session = not bool(self._session_id)

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def is_persistent(self) -> bool:
        return self._repository is not None

    def add_message(
        self,
        role: Optional[str] = None,
        content: Optional[str] = None,
        msg: Optional[Any] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加消息

        支持两种方式：
        1. 传入 Msg 对象: add_message(msg=msg)
        2. 传入参数创建 Msg: add_message(role="user", content="你好")

        Args:
            role: 角色 (user/assistant/system)，当不传入 msg 时必需
            content: 消息内容，当不传入 msg 时必需
            msg: Msg 对象，如果提供则忽略其他参数
            name: 发送者名称，默认根据 role 自动设置
            metadata: 元数据
        """
        if msg is None:
            if not AGENTSCOPE_AVAILABLE or Msg is None:
                raise RuntimeError("AgentScope 未安装，无法创建消息")

            if role is None or content is None:
                raise ValueError("当不传入 msg 时，role 和 content 参数必需")

            factories = {
                "user": UserMsg,
                "assistant": AssistantMsg,
                "system": SystemMsg,
            }
            if role not in factories:
                raise ValueError(f"不支持的消息 role: {role!r}")

            if name is None:
                name = role.capitalize()

            msg = factories[role](
                name=name,
                content=content,
                metadata=metadata if metadata is not None else {},
            )

        with self._lock:
            self._messages.append(msg)
            if len(self._messages) > self._max_messages:
                self._messages.pop(0)

            if self._repository and self._session_id:
                self._repository.add_message(
                    session_id=self._session_id,
                    msg=msg,
                )

    def get_messages(self) -> List[Any]:
        """获取所有消息（返回 Msg 对象列表）"""
        with self._lock:
            return self._messages.copy()

    def get_recent_messages(self, count: int = 10) -> List[Any]:
        """获取最近N条消息（返回 Msg 对象列表）"""
        with self._lock:
            return (
                self._messages[-count:] if len(self._messages) >= count else self._messages.copy()
            )

    def get_all_messages_persisted(self) -> List[Dict[str, Any]]:
        """
        获取所有持久化的消息

        Returns:
            AgentScope 2.0 JSON-compatible 字典列表
        """
        if self._repository and self._session_id:
            return self._repository.get_session_messages(self._session_id)
        else:
            return self.to_dict_list()

    def clear(self) -> None:
        """清空历史（仅内存，数据库中的消息保留）"""
        with self._lock:
            self._messages.clear()

    def clear_all(self) -> bool:
        """
        完全清空（包括数据库中的会话）

        Returns:
            是否成功清空
        """
        with self._lock:
            self._messages.clear()

            if self._repository and self._session_id:
                result = self._repository.delete_session(self._session_id)
                if result:
                    self._session_id = None
                    self._is_new_session = True
                return result

            return True

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """转换为 JSON-compatible 字典列表。"""
        with self._lock:
            result = []
            for msg in self._messages:
                if isinstance(msg, Msg):
                    result.append(serialize_message(msg))
                elif isinstance(msg, dict):
                    result.append(deepcopy(msg))
                else:
                    raise ValueError(f"不支持的消息类型: {type(msg)}")
            return result

    def load_from_repository(self) -> bool:
        """
        从数据库加载历史消息到内存

        Returns:
            是否成功加载
        """
        if not self._repository or not self._session_id:
            return False

        if not AGENTSCOPE_AVAILABLE or Msg is None:
            return False

        try:
            messages_data = self._repository.get_session_messages(self._session_id)
            with self._lock:
                self._messages = []
                for data in messages_data:
                    try:
                        msg = deserialize_message(data)
                        self._messages.append(msg)
                    except Exception as e:
                        # 记录错误但继续处理其他消息
                        import logging

                        logging.getLogger(__name__).warning(f"反序列化消息失败: {e}")
                        logging.getLogger(__name__).debug(f"消息数据: {data}")
                        logging.getLogger(__name__).debug(f"数据类型: {type(data)}")
                        if isinstance(data, dict):
                            logging.getLogger(__name__).debug(f"Content字段: {data.get('content')}")
                            logging.getLogger(__name__).debug(
                                f"Content类型: {type(data.get('content'))}"
                            )
            return True
        except Exception:
            return False

    def create_new_session(self, title: Optional[str] = None) -> str:
        """
        创建新会话（仅数据库模式）

        Args:
            title: 会话标题（可选）

        Returns:
            新会话ID
        """
        if not self._repository:
            raise RuntimeError("需要设置repository才能创建新会话")

        with self._lock:
            self._messages.clear()

        self._session_id = self._repository.create_session(title)
        self._is_new_session = True

        return self._session_id

    def set_session(self, session_id: str) -> bool:
        """
        切换到指定会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功切换
        """
        if not self._repository:
            return False

        session_info = self._repository.get_session(session_id)
        if not session_info:
            return False

        self._session_id = session_id
        self._is_new_session = False

        return self.load_from_repository()

    @classmethod
    def create_from_session(
        cls,
        session_id: str,
        repository: "ChatHistoryRepository",
        max_messages: int = 100,
    ) -> "ChatHistory":
        """
        从现有会话创建ChatHistory实例

        Args:
            session_id: 会话ID
            repository: 数据库存储库
            max_messages: 内存最大消息数

        Returns:
            ChatHistory实例
        """
        history = cls(
            max_messages=max_messages,
            session_id=session_id,
            repository=repository,
        )
        history.load_from_repository()
        return history
