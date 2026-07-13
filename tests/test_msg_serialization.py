"""Message persistence contracts for AgentScope 2.0 and legacy records."""

import json

import pytest
from agentscope.message import (
    AssistantMsg,
    Base64Source,
    DataBlock,
    TextBlock,
    ToolCallBlock,
    UserMsg,
)

from src.agent.chat_history import deserialize_message, serialize_message


def test_2x_multimodal_message_round_trips_exactly():
    original = UserMsg(
        name="User",
        content=[
            TextBlock(text="检查这张图片"),
            DataBlock(
                source=Base64Source(
                    data="aW1hZ2UtYnl0ZXM=",
                    media_type="image/png",
                ),
            ),
        ],
        metadata={"source": "ui"},
    )

    restored = deserialize_message(serialize_message(original))

    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_2x_string_message_serializes_as_json_compatible_text_block_list():
    message = UserMsg(name="User", content="你好，AgentScope 2.0！")

    serialized = serialize_message(message)

    json.dumps(serialized, ensure_ascii=False)
    assert isinstance(serialized["content"], list)
    assert len(serialized["content"]) == 1
    assert serialized["content"][0]["type"] == "text"
    assert serialized["content"][0]["text"] == "你好，AgentScope 2.0！"


def test_legacy_string_content_is_loaded_as_a_2x_text_block():
    restored = deserialize_message(
        {
            "name": "User",
            "role": "user",
            "content": "保留这段旧消息",
        },
    )

    assert len(restored.content) == 1
    assert isinstance(restored.content[0], TextBlock)
    assert restored.content[0].type == "text"
    assert restored.get_text_content() == "保留这段旧消息"


@pytest.mark.parametrize(
    ("legacy_type", "legacy_source", "expected_source"),
    [
        (
            "image",
            {
                "type": "url",
                "url": "https://example.com/diagram.png",
                "media_type": "image/png",
            },
            {
                "type": "url",
                "url": "https://example.com/diagram.png",
                "media_type": "image/png",
            },
        ),
        (
            "audio",
            {
                "type": "base64",
                "data": "YXVkaW8=",
                "media_type": "audio/wav",
            },
            {
                "type": "base64",
                "data": "YXVkaW8=",
                "media_type": "audio/wav",
            },
        ),
        (
            "video",
            {
                "type": "url",
                "url": "https://example.com/clip.mp4",
                "media_type": "video/mp4",
            },
            {
                "type": "url",
                "url": "https://example.com/clip.mp4",
                "media_type": "video/mp4",
            },
        ),
    ],
)
def test_legacy_media_blocks_are_loaded_as_2x_data_blocks(
    legacy_type,
    legacy_source,
    expected_source,
):
    restored = deserialize_message(
        {
            "name": "User",
            "role": "user",
            "content": [
                {
                    "type": legacy_type,
                    "source": legacy_source,
                },
            ],
        },
    )

    assert len(restored.content) == 1
    assert isinstance(restored.content[0], DataBlock)
    assert restored.content[0].type == "data"
    assert restored.content[0].source.model_dump(mode="json") == expected_source


def test_2x_assistant_tool_call_round_trips_exactly():
    original = AssistantMsg(
        name="Assistant",
        content=[
            ToolCallBlock(
                id="call-stable-2x",
                name="lookup",
                input='{"x": 1}',
                state="finished",
            ),
        ],
    )

    restored = deserialize_message(serialize_message(original))

    assert restored.model_dump(mode="json") == original.model_dump(mode="json")


def test_legacy_tool_use_is_normalized_to_a_2x_tool_call_block():
    restored = deserialize_message(
        {
            "name": "Assistant",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call-legacy",
                    "name": "lookup",
                    "input": {"x": 1},
                    "state": "finished",
                },
            ],
        },
    )

    assert len(restored.content) == 1
    block = restored.content[0]
    assert isinstance(block, ToolCallBlock)
    assert block.type == "tool_call"
    assert block.id == "call-legacy"
    assert block.name == "lookup"
    assert block.input == '{"x": 1}'
    assert block.state == "finished"


def test_unknown_legacy_block_becomes_json_text_with_a_migration_warning():
    unknown_block = {
        "type": "custom_legacy_block",
        "payload": {"answer": 42},
    }

    restored = deserialize_message(
        {
            "name": "Assistant",
            "role": "assistant",
            "content": [unknown_block],
            "metadata": {"session": "legacy"},
        },
    )

    assert len(restored.content) == 1
    assert isinstance(restored.content[0], TextBlock)
    assert restored.content[0].type == "text"
    assert json.loads(restored.content[0].text) == unknown_block
    assert restored.metadata["session"] == "legacy"
    assert isinstance(restored.metadata["migration_warnings"], list)
    assert restored.metadata["migration_warnings"]


def test_legacy_identity_timestamp_and_metadata_are_preserved():
    restored = deserialize_message(
        {
            "id": "legacy-message-id",
            "name": "User",
            "role": "user",
            "content": "旧会话内容",
            "timestamp": "2026-03-31T10:00:00+08:00",
            "metadata": {
                "session_id": "session-123",
                "turn": 7,
            },
        },
    )

    assert restored.id == "legacy-message-id"
    assert restored.created_at == "2026-03-31T10:00:00+08:00"
    assert restored.metadata == {
        "session_id": "session-123",
        "turn": 7,
    }


def test_unsupported_legacy_role_raises_a_clear_value_error():
    with pytest.raises(ValueError, match="(?i)role"):
        deserialize_message(
            {
                "name": "Moderator",
                "role": "moderator",
                "content": "不能静默改成其他角色",
            },
        )
