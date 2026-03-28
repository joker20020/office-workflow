# -*- coding: utf-8 -*-
"""
对话历史管理 - 支持内存和数据库持久化存储

提供两种存储模式：
1. 内存模式：适合临时会话，数据不持久化
2. 数据库模式：适合需要持久化的会话，使用SQLite存储

使用方式：
    # 内存模式
    history = ChatHistory()

    # 数据库模式
    from src.storage.database import Database
    from src.storage.repositories import ChatHistoryRepository
    db = Database(Path("data/app.db"))
    repo = ChatHistoryRepository(db)
    history = ChatHistory(repository=repo)
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.repositories import ChatHistoryRepository


@dataclass
class ChatMessage:
    """对话消息数据类"""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """从字典创建"""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()

        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )


class ChatHistory:
    """
    对话历史管理器

    支持两种存储模式：
    - 内存模式：使用内存列表存储，不持久化
    - 数据库模式：使用ChatHistoryRepository持久化到SQLite

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
        """
        初始化历史管理器

        Args:
            max_messages: 内存模式下最大消息数量
            session_id: 会话ID（数据库模式必需）
            repository: 数据库存储库（使用数据库模式时必需）
        """
        # 内存存储
        self._messages: List[ChatMessage] = []
        self._max_messages = max_messages
        self._lock = threading.Lock()

        # 数据库存储
        self._session_id: Optional[str] = session_id
        self._repository: Optional["ChatHistoryRepository"] = repository

        # 如果提供了repository但没有session_id，自动创建新会话
        if self._repository and not self._session_id:
            self._session_id = self._repository.create_session()
            self._is_new_session = True
        else:
            self._is_new_session = not bool(self._session_id)

    @property
    def session_id(self) -> Optional[str]:
        """获取当前会话ID"""
        return self._session_id

    @property
    def is_persistent(self) -> bool:
        """是否使用持久化存储"""
        return self._repository is not None

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加消息

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
            metadata: 元数据（可选）
        """
        message = ChatMessage(role=role, content=content, metadata=metadata or {})

        with self._lock:
            # 添加到内存
            self._messages.append(message)
            if len(self._messages) > self._max_messages:
                self._messages.pop(0)

            # 如果使用数据库模式，持久化到数据库
            if self._repository and self._session_id:
                self._repository.add_message(
                    session_id=self._session_id,
                    role=role,
                    content=content,
                    metadata=metadata,
                )

    def get_messages(self) -> List[ChatMessage]:
        """获取所有消息（内存中的消息）"""
        with self._lock:
            return self._messages.copy()

    def get_recent_messages(self, count: int = 10) -> List[ChatMessage]:
        """获取最近N条消息"""
        with self._lock:
            return (
                self._messages[-count:] if len(self._messages) >= count else self._messages.copy()
            )

    def get_all_messages_persisted(self) -> List[Dict[str, Any]]:
        """
        获取所有持久化的消息（仅数据库模式）

        Returns:
            消息字典列表，如果未使用数据库模式则返回内存中的消息
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

    def to_dict_list(self) -> List[Dict]:
        """转换为字典列表（用于序列化内存中的消息）"""
        with self._lock:
            return [msg.to_dict() for msg in self._messages]

    def load_from_repository(self) -> bool:
        """
        从数据库加载历史消息到内存

        Returns:
            是否成功加载
        """
        if not self._repository or not self._session_id:
            return False

        try:
            messages_data = self._repository.get_session_messages(self._session_id)
            with self._lock:
                self._messages = [ChatMessage.from_dict(data) for data in messages_data]
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

        # 清空内存
        with self._lock:
            self._messages.clear()

        # 创建新会话
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

        # 加载会话消息到内存
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
