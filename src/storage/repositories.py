# -*- coding: utf-8 -*-
"""
存储库模块

提供数据持久化操作：
- WorkflowRepository: 工作流CRUD操作
- ChatHistoryRepository: 会话历史CRUD操作

使用方式：
    from src.storage.repositories import WorkflowRepository, ChatHistoryRepository

    # 工作流
    wf_repo = WorkflowRepository(database)
    wf_repo.save(graph)
    graph = wf_repo.load(graph_id)

    # 会话历史
    chat_repo = ChatHistoryRepository(database)
    session_id = chat_repo.create_session("我的对话")
    chat_repo.add_message(session_id, "user", "你好")
    messages = chat_repo.get_session_messages(session_id)
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
import uuid

from sqlalchemy import select, delete, desc, func
from sqlalchemy.orm import Session

from src.engine.node_graph import NodeGraph
from src.engine.serialization import deserialize_graph, serialize_graph
from src.storage.database import Database
from src.storage.models import WorkflowRecord, ChatSessionRecord, ChatMessageRecord
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class WorkflowRepository:
    """
    工作流存储库

    提供工作流的CRUD操作：
    - save: 保存工作流
    - load: 加载工作流
    - delete: 删除工作流
    - list_all: 列出所有工作流
    - exists: 检查是否存在

    Example:
        >>> repo = WorkflowRepository(database)
        >>> repo.save(graph)
        >>> loaded = repo.load(graph.id)
    """

    def __init__(self, database: Database):
        """
        初始化存储库

        Args:
            database: 数据库实例
        """
        self._database = database

    def save(self, graph: NodeGraph) -> bool:
        """
        保存工作流

        如果工作流已存在则更新，否则创建新记录。

        Args:
            graph: 要保存的工作流图

        Returns:
            是否保存成功

        Example:
            >>> repo.save(graph)
            True
        """
        try:
            with self._database.session() as session:
                # 检查是否已存在
                stmt = select(WorkflowRecord).where(WorkflowRecord.id == graph.id)
                existing = session.execute(stmt).scalar_one_or_none()

                # 序列化图
                graph_json = serialize_graph(graph)

                if existing:
                    # 更新
                    existing.name = graph.name
                    existing.graph_json = graph_json
                    existing.updated_at = datetime.now()
                    _logger.info(f"更新工作流: {graph.name} [{graph.id[:8]}...]")
                else:
                    # 创建
                    record = WorkflowRecord(
                        id=graph.id,
                        name=graph.name,
                        graph_json=graph_json,
                    )
                    session.add(record)
                    _logger.info(f"保存新工作流: {graph.name} [{graph.id[:8]}...]")

                return True

        except Exception as e:
            _logger.error(f"保存工作流失败: {e}", exc_info=True)
            return False

    def load(self, graph_id: str) -> Optional[NodeGraph]:
        """
        加载工作流

        Args:
            graph_id: 工作流ID

        Returns:
            工作流图，如果不存在则返回 None

        Example:
            >>> graph = repo.load("graph-uuid")
            >>> graph.name
            '我的工作流'
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord).where(WorkflowRecord.id == graph_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record is None:
                    _logger.warning(f"工作流不存在: {graph_id[:8]}...")
                    return None

                # 反序列化
                graph = deserialize_graph(record.graph_json)
                _logger.info(f"加载工作流: {graph.name} [{graph_id[:8]}...]")
                return graph

        except Exception as e:
            _logger.error(f"加载工作流失败: {e}", exc_info=True)
            return None

    def delete(self, graph_id: str) -> bool:
        """
        删除工作流

        Args:
            graph_id: 工作流ID

        Returns:
            是否删除成功

        Example:
            >>> repo.delete("graph-uuid")
            True
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord).where(WorkflowRecord.id == graph_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record:
                    session.delete(record)
                    _logger.info(f"删除工作流: {graph_id[:8]}...")
                    return True
                else:
                    _logger.warning(f"工作流不存在，无法删除: {graph_id[:8]}...")
                    return False

        except Exception as e:
            _logger.error(f"删除工作流失败: {e}", exc_info=True)
            return False

    def list_all(self) -> List[dict]:
        """
        列出所有工作流（仅元信息）

        Returns:
            工作流元信息列表，每项包含 id, name, created_at, updated_at

        Example:
            >>> workflows = repo.list_all()
            >>> len(workflows)
            5
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord).order_by(WorkflowRecord.updated_at.desc())
                records = session.execute(stmt).scalars().all()

                result = [
                    {
                        "id": r.id,
                        "name": r.name,
                        "created_at": r.created_at.isoformat(),
                        "updated_at": r.updated_at.isoformat(),
                    }
                    for r in records
                ]

                _logger.debug(f"列出工作流: {len(result)} 个")
                return result

        except Exception as e:
            _logger.error(f"列出工作流失败: {e}", exc_info=True)
            return []

    def exists(self, graph_id: str) -> bool:
        """
        检查工作流是否存在

        Args:
            graph_id: 工作流ID

        Returns:
            是否存在
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord.id).where(WorkflowRecord.id == graph_id)
                result = session.execute(stmt).scalar_one_or_none()
                return result is not None
        except Exception:
            return False


class ChatHistoryRepository:
    """
    对话历史存储库

    提供会话和消息的CRUD操作：
    - create_session: 创建新会话
    - get_session: 获取会话
    - delete_session: 删除会话及其消息
    - add_message: 添加消息到会话
    - get_session_messages: 获取会话的所有消息
    - list_sessions: 列出所有会话
    - cleanup_old_sessions: 清理过期会话

    Example:
        >>> repo = ChatHistoryRepository(database)
        >>> session_id = repo.create_session("我的对话")
        >>> repo.add_message(session_id, "user", "你好")
        >>> messages = repo.get_session_messages(session_id)
    """

    def __init__(self, database: Database):
        """
        初始化存储库

        Args:
            database: 数据库实例
        """
        self._database = database

    def create_session(self, title: Optional[str] = None) -> str:
        """
        创建新会话

        Args:
            title: 会话标题（可选）

        Returns:
            新会话的ID

        Example:
            >>> session_id = repo.create_session("工作流设计对话")
        """
        session_id = str(uuid.uuid4())
        try:
            with self._database.session() as session:
                record = ChatSessionRecord(
                    id=session_id,
                    title=title,
                )
                session.add(record)
                _logger.info(f"创建会话: {session_id[:8]}...")
                return session_id
        except Exception as e:
            _logger.error(f"创建会话失败: {e}", exc_info=True)
            raise

    def get_session(self, session_id: str) -> Optional[dict]:
        """
        获取会话信息

        Args:
            session_id: 会话ID

        Returns:
            会话信息字典，如果不存在则返回 None
        """
        try:
            with self._database.session() as session:
                stmt = select(ChatSessionRecord).where(ChatSessionRecord.id == session_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record is None:
                    return None

                return {
                    "id": record.id,
                    "title": record.title,
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                }
        except Exception as e:
            _logger.error(f"获取会话失败: {e}", exc_info=True)
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话及其所有消息

        Args:
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        try:
            with self._database.session() as session:
                stmt = select(ChatSessionRecord).where(ChatSessionRecord.id == session_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record:
                    session.delete(record)
                    _logger.info(f"删除会话: {session_id[:8]}...")
                    return True
                else:
                    _logger.warning(f"会话不存在: {session_id[:8]}...")
                    return False
        except Exception as e:
            _logger.error(f"删除会话失败: {e}", exc_info=True)
            return False

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        添加消息到会话

        Args:
            session_id: 会话ID
            role: 消息角色 (user/assistant/system)
            content: 消息内容
            metadata: 消息元数据（可选）

        Returns:
            新消息的ID，失败返回 None

        Example:
            >>> repo.add_message(session_id, "user", "请帮我设计工作流")
        """
        try:
            with self._database.session() as session:
                # 验证会话存在
                session_stmt = select(ChatSessionRecord).where(ChatSessionRecord.id == session_id)
                session_record = session.execute(session_stmt).scalar_one_or_none()

                if session_record is None:
                    _logger.warning(f"会话不存在，无法添加消息: {session_id[:8]}...")
                    return None

                # 创建消息记录
                message_record = ChatMessageRecord(
                    session_id=session_id,
                    role=role,
                    content=content,
                    extra_data=json.dumps(metadata or {}, ensure_ascii=False),
                )
                session.add(message_record)

                # 如果没有标题，使用第一条用户消息设置标题
                if session_record.title is None and role == "user":
                    session_record.title = content[:50] + ("..." if len(content) > 50 else "")

                session.flush()  # 获取自增ID
                message_id = message_record.id
                _logger.debug(f"添加消息: session={session_id[:8]}..., role={role}")
                return message_id

        except Exception as e:
            _logger.error(f"添加消息失败: {e}", exc_info=True)
            return None

    def get_session_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[dict]:
        """
        获取会话的所有消息

        Args:
            session_id: 会话ID
            limit: 限制返回数量（可选，从最新开始）

        Returns:
            消息列表，每项包含 id, role, content, timestamp, metadata

        Example:
            >>> messages = repo.get_session_messages(session_id, limit=10)
        """
        try:
            with self._database.session() as session:
                if limit:
                    # 获取最近N条消息
                    stmt = (
                        select(ChatMessageRecord)
                        .where(ChatMessageRecord.session_id == session_id)
                        .order_by(desc(ChatMessageRecord.timestamp))
                        .limit(limit)
                    )
                    records = session.execute(stmt).scalars().all()
                    records = list(reversed(records))  # 恢复时间顺序
                else:
                    stmt = (
                        select(ChatMessageRecord)
                        .where(ChatMessageRecord.session_id == session_id)
                        .order_by(ChatMessageRecord.timestamp)
                    )
                    records = session.execute(stmt).scalars().all()

                result = [
                    {
                        "id": r.id,
                        "role": r.role,
                        "content": r.content,
                        "timestamp": r.timestamp.isoformat(),
                        "metadata": json.loads(r.extra_data) if r.extra_data else {},
                    }
                    for r in records
                ]

                _logger.debug(f"获取会话消息: session={session_id[:8]}..., count={len(result)}")
                return result

        except Exception as e:
            _logger.error(f"获取会话消息失败: {e}", exc_info=True)
            return []

    def list_sessions(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[dict]:
        """
        列出所有会话（按更新时间倒序）

        Args:
            limit: 限制返回数量
            offset: 偏移量（分页用）

        Returns:
            会话列表，每项包含 id, title, created_at, updated_at, message_count
        """
        try:
            with self._database.session() as session:
                stmt = (
                    select(
                        ChatSessionRecord,
                        func.count(ChatMessageRecord.id).label("message_count"),
                    )
                    .outerjoin(ChatMessageRecord)
                    .group_by(ChatSessionRecord.id)
                    .order_by(desc(ChatSessionRecord.updated_at))
                )

                if limit:
                    stmt = stmt.limit(limit).offset(offset)

                results = session.execute(stmt).all()

                result = [
                    {
                        "id": r[0].id,
                        "title": r[0].title or "未命名会话",
                        "created_at": r[0].created_at.isoformat(),
                        "updated_at": r[0].updated_at.isoformat(),
                        "message_count": r[1],
                    }
                    for r in results
                ]

                _logger.debug(f"列出会话: count={len(result)}")
                return result

        except Exception as e:
            _logger.error(f"列出会话失败: {e}", exc_info=True)
            return []

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        清理指定天数前的旧会话

        Args:
            days: 保留天数

        Returns:
            删除的会话数量
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)

            with self._database.session() as session:
                stmt = delete(ChatSessionRecord).where(ChatSessionRecord.updated_at < cutoff)
                result = session.execute(stmt)
                deleted_count = result.rowcount

                _logger.info(f"清理旧会话: 删除 {deleted_count} 条（{days}天前）")
                return deleted_count

        except Exception as e:
            _logger.error(f"清理旧会话失败: {e}", exc_info=True)
            return 0

    def update_session_title(self, session_id: str, title: str) -> bool:
        """
        更新会话标题

        Args:
            session_id: 会话ID
            title: 新标题

        Returns:
            是否更新成功
        """
        try:
            with self._database.session() as session:
                stmt = select(ChatSessionRecord).where(ChatSessionRecord.id == session_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record:
                    record.title = title
                    _logger.info(f"更新会话标题: {session_id[:8]}... -> {title}")
                    return True
                else:
                    _logger.warning(f"会话不存在: {session_id[:8]}...")
                    return False
        except Exception as e:
            _logger.error(f"更新会话标题失败: {e}", exc_info=True)
            return False
