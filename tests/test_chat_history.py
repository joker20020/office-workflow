# -*- coding: utf-8 -*-
"""会话历史管理测试"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile

from src.agent.chat_history import ChatHistory, ChatMessage
from src.storage.database import Database
from src.storage.repositories import ChatHistoryRepository


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.create_tables()
        yield db
        db.close()


@pytest.fixture
def repository(temp_db):
    """创建会话历史存储库"""
    return ChatHistoryRepository(temp_db)


class TestChatMessage:
    """ChatMessage 测试"""

    def test_create_message(self):
        """测试创建消息"""
        msg = ChatMessage(role="user", content="你好")
        assert msg.role == "user"
        assert msg.content == "你好"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_message_to_dict(self):
        """测试消息转字典"""
        msg = ChatMessage(
            role="assistant", content="你好！有什么可以帮助你的？", metadata={"tool_calls": []}
        )
        data = msg.to_dict()
        assert data["role"] == "assistant"
        assert data["content"] == "你好！有什么可以帮助你的？"
        assert "timestamp" in data
        assert data["metadata"] == {"tool_calls": []}

    def test_message_from_dict(self):
        """测试从字典创建消息"""
        data = {
            "role": "system",
            "content": "你是一个助手",
            "timestamp": "2026-03-28T10:00:00",
            "metadata": {"source": "test"},
        }
        msg = ChatMessage.from_dict(data)
        assert msg.role == "system"
        assert msg.content == "你是一个助手"
        assert msg.metadata == {"source": "test"}


class TestChatHistoryMemoryMode:
    """ChatHistory 内存模式测试"""

    def test_add_message(self):
        """测试添加消息"""
        history = ChatHistory(max_messages=10)
        history.add_message("user", "第一条消息")
        history.add_message("assistant", "回复消息")

        messages = history.get_messages()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_max_messages_limit(self):
        """测试消息数量限制"""
        history = ChatHistory(max_messages=5)
        for i in range(10):
            history.add_message("user", f"消息 {i}")

        messages = history.get_messages()
        assert len(messages) == 5
        # 应该保留最新的5条
        assert "消息 5" in messages[0].content

    def test_get_recent_messages(self):
        """测试获取最近消息"""
        history = ChatHistory()
        for i in range(10):
            history.add_message("user", f"消息 {i}")

        recent = history.get_recent_messages(3)
        assert len(recent) == 3
        assert "消息 7" in recent[0].content
        assert "消息 9" in recent[2].content

    def test_clear(self):
        """测试清空历史"""
        history = ChatHistory()
        history.add_message("user", "测试消息")
        history.clear()
        assert len(history.get_messages()) == 0

    def test_to_dict_list(self):
        """测试序列化"""
        history = ChatHistory()
        history.add_message("user", "你好")
        history.add_message("assistant", "你好！")

        data = history.to_dict_list()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"


class TestChatHistoryDatabaseMode:
    """ChatHistory 数据库模式测试"""

    def test_create_with_repository(self, repository):
        """测试使用存储库创建历史"""
        history = ChatHistory(repository=repository)

        # 应该自动创建会话
        assert history.session_id is not None
        assert history.is_persistent is True

    def test_add_and_persist_message(self, repository):
        """测试添加并持久化消息"""
        history = ChatHistory(repository=repository)
        session_id = history.session_id

        history.add_message("user", "第一条消息")
        history.add_message("assistant", "回复消息")

        # 验证内存中的消息
        messages = history.get_messages()
        assert len(messages) == 2

        # 验证数据库中的消息
        db_messages = repository.get_session_messages(session_id)
        assert len(db_messages) == 2
        assert db_messages[0]["role"] == "user"
        assert db_messages[1]["role"] == "assistant"

    def test_load_existing_session(self, repository):
        """测试加载现有会话"""
        # 创建会话并添加消息
        session_id = repository.create_session("测试会话")
        repository.add_message(session_id, "user", "已存在的消息")

        # 从现有会话创建历史
        history = ChatHistory.create_from_session(session_id=session_id, repository=repository)

        # 验证加载了消息
        messages = history.get_messages()
        assert len(messages) == 1
        assert messages[0].content == "已存在的消息"

    def test_create_new_session(self, repository):
        """测试创建新会话"""
        history = ChatHistory(repository=repository)
        old_session_id = history.session_id

        new_session_id = history.create_new_session("新会话")
        assert new_session_id is not None
        assert new_session_id != old_session_id
        assert history.session_id == new_session_id

    def test_switch_session(self, repository):
        """测试切换会话"""
        history = ChatHistory(repository=repository)

        # 添加消息到当前会话
        history.add_message("user", "第一个会话的消息")
        first_session_id = history.session_id

        # 创建并切换到新会话
        new_session_id = history.create_new_session("第二个会话")
        history.add_message("user", "第二个会话的消息")

        # 切换回第一个会话
        result = history.set_session(first_session_id)
        assert result is True
        messages = history.get_messages()
        assert len(messages) == 1
        assert "第一个会话的消息" in messages[0].content

    def test_clear_full(self, repository):
        """测试完全清空（包括数据库）"""
        history = ChatHistory(repository=repository)
        session_id = history.session_id

        # 添加消息
        history.add_message("user", "测试消息")
        messages = history.get_messages()
        assert len(messages) == 1

        # 完全清空
        result = history.clear_all()
        assert result is True

        # 验证会话被删除
        session = repository.get_session(session_id)
        assert session is None

        # 验证内存被清空
        messages = history.get_messages()
        assert len(messages) == 0

        # 验证会话被删除
        assert repository.get_session(history.session_id) is None


class TestChatHistoryRepository:
    """ChatHistoryRepository 测试"""

    def test_create_session(self, repository):
        """测试创建会话"""
        session_id = repository.create_session("测试会话")
        assert session_id is not None
        assert len(session_id) == 36  # UUID格式

    def test_get_session(self, repository):
        """测试获取会话"""
        session_id = repository.create_session("测试会话")
        session = repository.get_session(session_id)

        assert session is not None
        assert session["id"] == session_id
        assert session["title"] == "测试会话"
        assert "created_at" in session

    def test_delete_session(self, repository):
        """测试删除会话"""
        session_id = repository.create_session()
        assert repository.delete_session(session_id) is True
        assert repository.get_session(session_id) is None

    def test_add_message(self, repository):
        """测试添加消息"""
        session_id = repository.create_session()

        msg_id = repository.add_message(session_id, "user", "测试消息")
        assert msg_id is not None

        messages = repository.get_session_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["content"] == "测试消息"

    def test_add_message_with_metadata(self, repository):
        """测试添加带元数据的消息"""
        session_id = repository.create_session()

        metadata = {"tool": "search", "query": "test"}
        repository.add_message(session_id, "assistant", "搜索结果", metadata=metadata)

        messages = repository.get_session_messages(session_id)
        assert messages[0]["metadata"] == metadata

    def test_get_session_messages_with_limit(self, repository):
        """测试获取限制数量的消息"""
        session_id = repository.create_session()

        for i in range(10):
            repository.add_message(session_id, "user", f"消息 {i}")

        messages = repository.get_session_messages(session_id, limit=5)
        assert len(messages) == 5
        # 应该是最新的5条
        assert "消息 5" in messages[0]["content"]

    def test_list_sessions(self, repository):
        """测试列出会话"""
        repository.create_session("会话A")
        repository.create_session("会话B")
        repository.create_session("会话C")

        sessions = repository.list_sessions()
        assert len(sessions) == 3

    def test_list_sessions_with_pagination(self, repository):
        """测试分页列出会话"""
        for i in range(5):
            repository.create_session(f"会话 {i}")

        page1 = repository.list_sessions(limit=2, offset=0)
        assert len(page1) == 2

        page2 = repository.list_sessions(limit=2, offset=2)
        assert len(page2) == 2

    def test_update_session_title(self, repository):
        """测试更新会话标题"""
        session_id = repository.create_session("旧标题")

        result = repository.update_session_title(session_id, "新标题")
        assert result is True

        session = repository.get_session(session_id)
        assert session["title"] == "新标题"

    def test_cleanup_old_sessions(self, repository):
        """测试清理旧会话"""
        # 创建会话
        repository.create_session("会话1")
        repository.create_session("会话2")

        # 清理30天前的会话（应该删除0个）
        deleted = repository.cleanup_old_sessions(days=30)
        assert deleted == 0

    def test_auto_title_from_first_message(self, repository):
        """测试从第一条用户消息自动设置标题"""
        session_id = repository.create_session()  # 无标题

        repository.add_message(
            session_id, "user", "这是一条很长的测试消息，用于验证自动标题功能是否正常工作"
        )

        session = repository.get_session(session_id)
        assert session["title"] is not None
        assert "这是一条很长的测试消息" in session["title"]
