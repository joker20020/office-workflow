# -*- coding: utf-8 -*-
"""Msg 序列化测试

测试 AgentScope Msg 类的序列化和反序列化功能。
"""

import pytest
import json
from datetime import datetime

from agentscope.message import Msg, TextBlock, ImageBlock
from agentscope.message import URLSource, Base64Source


class TestMsgToDictBasic:
    """测试基本 Msg 序列化"""

    def test_msg_to_dict_with_string_content(self):
        """测试字符串内容的 Msg 序列化"""
        msg = Msg(
            name="User",
            role="user",
            content="你好，世界！",
        )

        data = msg.to_dict()

        assert data["name"] == "User"
        assert data["role"] == "user"
        assert data["content"] == "你好，世界！"
        assert "id" in data
        assert "timestamp" in data
        assert data["metadata"] == {}

    def test_msg_to_dict_with_system_role(self):
        """测试 system 角色的 Msg 序列化"""
        msg = Msg(
            name="System",
            role="system",
            content="你是一个助手",
        )

        data = msg.to_dict()

        assert data["role"] == "system"
        assert data["name"] == "System"

    def test_msg_to_dict_with_assistant_role(self):
        """测试 assistant 角色的 Msg 序列化"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="我可以帮助你",
        )

        data = msg.to_dict()

        assert data["role"] == "assistant"

    def test_msg_to_dict_has_id(self):
        """测试序列化后的消息包含唯一 ID"""
        msg1 = Msg(name="User", role="user", content="消息1")
        msg2 = Msg(name="User", role="user", content="消息2")

        data1 = msg1.to_dict()
        data2 = msg2.to_dict()

        assert "id" in data1
        assert "id" in data2
        assert data1["id"] != data2["id"]

    def test_msg_to_dict_has_timestamp(self):
        """测试序列化后的消息包含时间戳"""
        msg = Msg(name="User", role="user", content="测试")
        data = msg.to_dict()

        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)


class TestMsgToDictWithMetadata:
    """测试带元数据的 Msg 序列化"""

    def test_msg_to_dict_with_simple_metadata(self):
        """测试简单元数据的序列化"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复内容",
            metadata={"source": "test", "version": "1.0"},
        )

        data = msg.to_dict()

        assert data["metadata"] == {"source": "test", "version": "1.0"}

    def test_msg_to_dict_with_nested_metadata(self):
        """测试嵌套元数据的序列化"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复",
            metadata={
                "tool_calls": [{"id": "1", "name": "search", "args": {"query": "test"}}],
                "context": {"session_id": "abc123", "user_id": "user1"},
            },
        )

        data = msg.to_dict()

        assert "tool_calls" in data["metadata"]
        assert len(data["metadata"]["tool_calls"]) == 1
        assert data["metadata"]["tool_calls"][0]["name"] == "search"

    def test_msg_to_dict_with_empty_metadata(self):
        """测试空元数据的序列化"""
        msg = Msg(
            name="User",
            role="user",
            content="内容",
            metadata={},
        )

        data = msg.to_dict()

        assert data["metadata"] == {}

    def test_msg_to_dict_with_none_metadata(self):
        """测试 None 元数据的序列化"""
        msg = Msg(
            name="User",
            role="user",
            content="内容",
            metadata=None,
        )

        data = msg.to_dict()

        # None 元数据应该被转换为空字典
        assert data["metadata"] == {}


class TestMsgToDictWithMultimodal:
    """测试多模态内容的 Msg 序列化"""

    def test_msg_to_dict_with_text_block(self):
        """测试 TextBlock 的序列化"""
        msg = Msg(
            name="User",
            role="user",
            content=[
                TextBlock(type="text", text="这是一段文本"),
            ],
        )

        data = msg.to_dict()

        assert isinstance(data["content"], list)
        assert len(data["content"]) == 1
        assert data["content"][0]["type"] == "text"
        assert data["content"][0]["text"] == "这是一段文本"

    def test_msg_to_dict_with_image_block_url_source(self):
        """测试 ImageBlock (URL源) 的序列化"""
        msg = Msg(
            name="User",
            role="user",
            content=[
                TextBlock(type="text", text="看这张图片"),
                ImageBlock(
                    type="image",
                    source=URLSource(
                        type="url",
                        url="https://example.com/image.jpg",
                    ),
                ),
            ],
        )

        data = msg.to_dict()

        assert len(data["content"]) == 2
        assert data["content"][0]["type"] == "text"
        assert data["content"][1]["type"] == "image"
        assert data["content"][1]["source"]["type"] == "url"
        assert data["content"][1]["source"]["url"] == "https://example.com/image.jpg"

    def test_msg_to_dict_with_image_block_base64_source(self):
        """测试 ImageBlock (Base64源) 的序列化"""
        msg = Msg(
            name="User",
            role="user",
            content=[
                ImageBlock(
                    type="image",
                    source=Base64Source(
                        type="base64",
                        media_type="image/png",
                        data="iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
                    ),
                ),
            ],
        )

        data = msg.to_dict()

        assert data["content"][0]["type"] == "image"
        assert data["content"][0]["source"]["type"] == "base64"
        assert data["content"][0]["source"]["media_type"] == "image/png"
        assert "data" in data["content"][0]["source"]

    def test_msg_to_dict_with_multiple_blocks(self):
        """测试多个内容块的序列化"""
        msg = Msg(
            name="User",
            role="user",
            content=[
                TextBlock(type="text", text="第一段"),
                TextBlock(type="text", text="第二段"),
                ImageBlock(
                    type="image",
                    source=URLSource(type="url", url="https://example.com/img1.jpg"),
                ),
                TextBlock(type="text", text="第三段"),
            ],
        )

        data = msg.to_dict()

        assert len(data["content"]) == 4
        assert data["content"][0]["text"] == "第一段"
        assert data["content"][1]["text"] == "第二段"
        assert data["content"][2]["type"] == "image"
        assert data["content"][3]["text"] == "第三段"


class TestMsgFromDictBasic:
    """测试基本 Msg 反序列化"""

    def test_msg_from_dict_with_string_content(self):
        """测试字符串内容的反序列化"""
        data = {
            "id": "test_id_123",
            "name": "User",
            "role": "user",
            "content": "你好",
            "metadata": {},
            "timestamp": "2026-03-31 10:00:00",
        }

        msg = Msg.from_dict(data)

        assert msg.name == "User"
        assert msg.role == "user"
        assert msg.content == "你好"
        assert msg.metadata == {}

    def test_msg_from_dict_with_metadata(self):
        """测试带元数据的反序列化"""
        data = {
            "id": "test_id",
            "name": "Assistant",
            "role": "assistant",
            "content": "回复",
            "metadata": {"tool": "search", "query": "test"},
            "timestamp": "2026-03-31 10:00:00",
        }

        msg = Msg.from_dict(data)

        assert msg.metadata == {"tool": "search", "query": "test"}

    def test_msg_from_dict_preserves_id(self):
        """测试反序列化保留原始 ID"""
        data = {
            "id": "unique_id_abc123",
            "name": "User",
            "role": "user",
            "content": "测试",
            "metadata": {},
            "timestamp": "2026-03-31 10:00:00",
        }

        msg = Msg.from_dict(data)

        assert msg.id == "unique_id_abc123"

    def test_msg_from_dict_with_text_blocks(self):
        """测试 TextBlock 的反序列化"""
        data = {
            "id": "test_id",
            "name": "User",
            "role": "user",
            "content": [
                {"type": "text", "text": "第一段"},
                {"type": "text", "text": "第二段"},
            ],
            "metadata": {},
            "timestamp": "2026-03-31 10:00:00",
        }

        msg = Msg.from_dict(data)

        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert all(block["type"] == "text" for block in msg.content)
        assert msg.content[0]["text"] == "第一段"
        assert msg.content[1]["text"] == "第二段"

    def test_msg_from_dict_with_image_block(self):
        """测试 ImageBlock 的反序列化"""
        data = {
            "id": "test_id",
            "name": "User",
            "role": "user",
            "content": [
                {"type": "text", "text": "看图"},
                {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": "https://example.com/image.jpg",
                    },
                },
            ],
            "metadata": {},
            "timestamp": "2026-03-31 10:00:00",
        }

        msg = Msg.from_dict(data)

        assert len(msg.content) == 2
        assert msg.content[1]["type"] == "image"
        assert msg.content[1]["source"]["url"] == "https://example.com/image.jpg"


class TestMsgRoundtrip:
    """测试 Msg 序列化往返"""

    def test_roundtrip_string_content(self):
        """测试字符串内容的往返序列化"""
        original = Msg(
            name="User",
            role="user",
            content="测试内容",
            metadata={"key": "value"},
        )

        data = original.to_dict()
        restored = Msg.from_dict(data)

        assert restored.name == original.name
        assert restored.role == original.role
        assert restored.content == original.content
        assert restored.metadata == original.metadata
        assert restored.id == original.id

    def test_roundtrip_text_blocks(self):
        """测试 TextBlock 的往返序列化"""
        original = Msg(
            name="User",
            role="user",
            content=[
                TextBlock(type="text", text="段落1"),
                TextBlock(type="text", text="段落2"),
            ],
            metadata={"source": "test"},
        )

        data = original.to_dict()
        restored = Msg.from_dict(data)

        assert len(restored.content) == len(original.content)
        for i, block in enumerate(restored.content):
            assert block["type"] == "text"
            assert block["text"] == original.content[i]["text"]

    def test_roundtrip_multimodal_content(self):
        """测试多模态内容的往返序列化"""
        original = Msg(
            name="User",
            role="user",
            content=[
                TextBlock(type="text", text="描述"),
                ImageBlock(
                    type="image",
                    source=URLSource(
                        type="url",
                        url="https://example.com/photo.jpg",
                    ),
                ),
                TextBlock(type="text", text="更多描述"),
            ],
            metadata={"session": "test_session"},
        )

        data = original.to_dict()
        restored = Msg.from_dict(data)

        assert len(restored.content) == 3
        assert restored.content[0]["type"] == "text"
        assert restored.content[1]["type"] == "image"
        assert restored.content[2]["type"] == "text"
        assert restored.content[1]["source"]["url"] == "https://example.com/photo.jpg"

    def test_roundtrip_with_complex_metadata(self):
        """测试复杂元数据的往返序列化"""
        original = Msg(
            name="Assistant",
            role="assistant",
            content="回复",
            metadata={
                "tool_calls": [{"id": "call_1", "name": "search", "input": {"q": "test"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "context": {"session_id": "abc", "turn": 3},
            },
        )

        data = original.to_dict()
        restored = Msg.from_dict(data)

        assert restored.metadata == original.metadata
        assert restored.metadata["tool_calls"][0]["name"] == "search"
        assert restored.metadata["usage"]["prompt_tokens"] == 100

    def test_roundtrip_json_serializable(self):
        """测试序列化结果可以被 JSON 序列化"""
        msg = Msg(
            name="User",
            role="user",
            content=[
                TextBlock(type="text", text="文本"),
                ImageBlock(
                    type="image",
                    source=URLSource(type="url", url="https://example.com/img.jpg"),
                ),
            ],
            metadata={"key": "value", "number": 123},
        )

        data = msg.to_dict()

        # 应该能够被 JSON 序列化
        json_str = json.dumps(data, ensure_ascii=False)
        loaded = json.loads(json_str)

        # 验证加载后的数据
        assert loaded["name"] == "User"
        assert loaded["content"][0]["text"] == "文本"


class TestMsgCompatibilityWithChatMessage:
    """测试 Msg 与 ChatMessage 格式的兼容性"""

    def test_msg_dict_has_chat_message_fields(self):
        """测试 Msg 序列化包含 ChatMessage 所需字段"""
        msg = Msg(
            name="User",
            role="user",
            content="测试消息",
            metadata={"extra": "data"},
        )

        data = msg.to_dict()

        # ChatMessage 需要的字段
        assert "role" in data
        assert "content" in data
        assert "metadata" in data
        assert "timestamp" in data

    def test_msg_dict_can_create_chat_message_like_dict(self):
        """测试 Msg 字典可以转换为 ChatMessage 格式"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复内容",
            metadata={"tool": "search"},
        )

        msg_dict = msg.to_dict()

        # 模拟 ChatMessage.from_dict 的输入格式
        chat_message_data = {
            "role": msg_dict["role"],
            "content": msg_dict["content"]
            if isinstance(msg_dict["content"], str)
            else str(msg_dict["content"]),
            "timestamp": msg_dict["timestamp"],
            "metadata": msg_dict["metadata"],
        }

        assert chat_message_data["role"] == "assistant"
        assert chat_message_data["content"] == "回复内容"
        assert chat_message_data["metadata"] == {"tool": "search"}

    def test_msg_string_content_compatible_with_chat_message(self):
        """测试字符串内容的 Msg 与 ChatMessage 兼容"""
        msg = Msg(
            name="User",
            role="user",
            content="简单文本消息",
        )

        data = msg.to_dict()

        # ChatMessage 期望 content 是字符串
        assert isinstance(data["content"], str)
        assert data["content"] == "简单文本消息"

    def test_msg_multimodal_content_extraction(self):
        """测试多模态内容的文本提取"""
        msg = Msg(
            name="User",
            role="user",
            content=[
                TextBlock(type="text", text="这是文本"),
                ImageBlock(
                    type="image",
                    source=URLSource(type="url", url="https://example.com/img.jpg"),
                ),
                TextBlock(type="text", text="更多文本"),
            ],
        )

        # 使用 get_text_content 提取文本
        text_content = msg.get_text_content()

        assert "这是文本" in text_content
        assert "更多文本" in text_content


class TestMsgEdgeCases:
    """测试边缘情况"""

    def test_msg_empty_string_content(self):
        """测试空字符串内容"""
        msg = Msg(
            name="User",
            role="user",
            content="",
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.content == ""

    def test_msg_empty_content_list(self):
        """测试空内容列表"""
        msg = Msg(
            name="User",
            role="user",
            content=[],
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.content == []

    def test_msg_unicode_content(self):
        """测试 Unicode 内容"""
        msg = Msg(
            name="用户",
            role="user",
            content="你好世界！🌍🎉 特殊字符：<>&\"'",
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.content == msg.content
        assert "🌍" in restored.content

    def test_msg_long_content(self):
        """测试长内容"""
        long_text = "这是一段很长的文本。" * 1000
        msg = Msg(
            name="User",
            role="user",
            content=long_text,
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.content == long_text
        assert len(restored.content) == len(long_text)

    def test_msg_special_characters_in_metadata(self):
        """测试元数据中的特殊字符"""
        msg = Msg(
            name="User",
            role="user",
            content="测试",
            metadata={
                "special_chars": "<>&\"'\\n\\t",
                "unicode": "中文日本語한국어",
                "emoji": "😀🎉",
            },
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.metadata["special_chars"] == "<>&\"'\\n\\t"
        assert restored.metadata["unicode"] == "中文日本語한국어"
        assert restored.metadata["emoji"] == "😀🎉"

    def test_msg_numeric_metadata_values(self):
        """测试元数据中的数值类型"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复",
            metadata={
                "int_value": 42,
                "float_value": 3.14159,
                "negative": -100,
                "zero": 0,
            },
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.metadata["int_value"] == 42
        assert restored.metadata["float_value"] == 3.14159
        assert restored.metadata["negative"] == -100
        assert restored.metadata["zero"] == 0

    def test_msg_boolean_metadata_values(self):
        """测试元数据中的布尔值"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复",
            metadata={
                "is_valid": True,
                "is_deleted": False,
            },
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.metadata["is_valid"] is True
        assert restored.metadata["is_deleted"] is False

    def test_msg_null_values_in_metadata(self):
        """测试元数据中的 null 值"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复",
            metadata={
                "null_value": None,
                "nested": {"inner_null": None},
            },
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.metadata["null_value"] is None
        assert restored.metadata["nested"]["inner_null"] is None

    def test_msg_deeply_nested_metadata(self):
        """测试深层嵌套的元数据"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复",
            metadata={"level1": {"level2": {"level3": {"level4": {"value": "deep_value"}}}}},
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.metadata["level1"]["level2"]["level3"]["level4"]["value"] == "deep_value"

    def test_msg_list_in_metadata(self):
        """测试元数据中的列表"""
        msg = Msg(
            name="Assistant",
            role="assistant",
            content="回复",
            metadata={
                "tags": ["tag1", "tag2", "tag3"],
                "numbers": [1, 2, 3, 4, 5],
                "mixed": ["text", 123, True, None],
            },
        )

        data = msg.to_dict()
        restored = Msg.from_dict(data)

        assert restored.metadata["tags"] == ["tag1", "tag2", "tag3"]
        assert restored.metadata["numbers"] == [1, 2, 3, 4, 5]
        assert restored.metadata["mixed"] == ["text", 123, True, None]
