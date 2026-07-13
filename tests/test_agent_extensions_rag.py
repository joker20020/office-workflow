# -*- coding: utf-8 -*-
"""agent_extensions 的 ProcessGen RAG HTTP 契约测试。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

import plugins.agent_extensions as agent_extensions
from plugins.agent_extensions import (
    AgentExtensionsPlugin,
    AgentExtensionTools,
    _APIRequester,
)


class FakeResponse:
    def __init__(self, status=200, payload=None, text="", body=b""):
        self.status = status
        self._payload = payload
        self._text = text
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return self._text

    async def read(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.responses = []
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def queue_json(self, payload, status=200, text=""):
        self.responses.append(FakeResponse(status=status, payload=payload, text=text))

    def queue_bytes(self, body, status=200, text=""):
        self.responses.append(FakeResponse(status=status, text=text, body=body))

    def _request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._request("DELETE", url, **kwargs)


class FakeFormData:
    def __init__(self):
        self.fields = {}

    def add_field(self, name, value, **kwargs):
        stored = (value, kwargs) if kwargs else value
        if name in self.fields:
            current = self.fields[name]
            if not isinstance(current, list):
                current = [current]
            current.append(stored)
            self.fields[name] = current
        else:
            self.fields[name] = stored


@pytest.fixture
def fake_session(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: session)
    monkeypatch.setattr(aiohttp, "FormData", FakeFormData)
    return session


@pytest.fixture
def requester():
    return _APIRequester(
        base_url="http://backend/api/v1/",
        workflow_path=None,
    )


def test_base_url_is_normalized(requester):
    assert requester.base_url == "http://backend/api/v1"


def test_default_base_url_uses_processgen_port():
    requester = _APIRequester(workflow_path=None)
    assert requester.base_url == "http://localhost:8050/api/v1"


@pytest.mark.asyncio
async def test_rag_collection_methods_use_documented_endpoints(requester, fake_session):
    fake_session.queue_json({"name": "process", "loaded": True})
    fake_session.queue_json({"collections": [], "count": 0})
    fake_session.queue_json({"status": "success"})

    await requester.rag_create_collection("process")
    await requester.rag_list_collections()
    await requester.rag_delete_collection("process")

    assert fake_session.requests == [
        (
            "POST",
            "http://backend/api/v1/rag/collections",
            {"json": {"collection_name": "process"}},
        ),
        ("GET", "http://backend/api/v1/rag/collections", {}),
        ("DELETE", "http://backend/api/v1/rag/collections/process", {}),
    ]


@pytest.mark.asyncio
async def test_rag_search_text_uses_backend_query_params(requester, fake_session):
    expected = [{"id": 1, "score": 0.8, "type": "text"}]
    fake_session.queue_json({"results": expected})

    result = await requester.rag_search_text(
        "process", "堵盖", limit=3, subject="capp"
    )

    assert result == expected
    assert fake_session.requests[-1] == (
        "GET",
        "http://backend/api/v1/rag/collections/process/search",
        {"params": {"query": "堵盖", "limit": 3, "subject": "capp"}},
    )


@pytest.mark.asyncio
async def test_rag_search_mixed_posts_query_image_and_limit(
    requester, fake_session, tmp_path
):
    image = tmp_path / "query.png"
    image.write_bytes(b"png")
    fake_session.queue_json({"results": []})

    result = await requester.rag_search_mixed(
        "process", "堵盖", str(image), limit=5
    )

    assert result == []
    method, url, kwargs = fake_session.requests[-1]
    assert method == "POST"
    assert url == "http://backend/api/v1/rag/collections/process/search/mixed"
    assert kwargs["data"].fields["query"] == "堵盖"
    assert kwargs["data"].fields["limit"] == "5"
    _, image_options = kwargs["data"].fields["image"]
    assert image_options == {"filename": "query.png", "content_type": "image/png"}


@pytest.mark.asyncio
async def test_rag_search_image_posts_image_limit_and_subject(
    requester, fake_session, tmp_path
):
    image = tmp_path / "query.jpg"
    image.write_bytes(b"jpg")
    fake_session.queue_json({"results": [{"id": 3, "type": "image"}]})

    result = await requester.rag_search_image(
        "process", str(image), limit=4, subject="capp"
    )

    assert result == [{"id": 3, "type": "image"}]
    method, url, kwargs = fake_session.requests[-1]
    assert method == "POST"
    assert url == "http://backend/api/v1/rag/collections/process/search"
    assert kwargs["data"].fields["limit"] == "4"
    assert kwargs["data"].fields["subject"] == "capp"
    assert kwargs["data"].fields["image"][1]["content_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_rag_upload_and_entity_methods_match_backend_contract(
    requester, fake_session, tmp_path
):
    text_file = tmp_path / "manual.md"
    text_file.write_text("content", encoding="utf-8")
    image = tmp_path / "part.jpg"
    image.write_bytes(b"jpg")
    for payload in (
        {"chunks_inserted": 1},
        {"images_inserted": 1},
        {"entities": [], "total": 0},
        {"status": "success"},
    ):
        fake_session.queue_json(payload)

    await requester.rag_add_text("process", str(text_file), subject="capp")
    await requester.rag_add_images(
        "process", [str(image)], ["零件图片"], subject="capp"
    )
    await requester.rag_list_entities("process", offset=10, limit=20)
    await requester.rag_delete_entity("process", 7)

    text_data = fake_session.requests[0][2]["data"].fields
    assert text_data["subject"] == "capp"
    assert text_data["file"][1]["filename"] == "manual.md"
    image_data = fake_session.requests[1][2]["data"].fields
    assert image_data["descriptions"] == "零件图片"
    assert image_data["images"][1]["filename"] == "part.jpg"
    assert fake_session.requests[2] == (
        "GET",
        "http://backend/api/v1/rag/collections/process/entities",
        {"params": {"offset": 10, "limit": 20}},
    )
    assert fake_session.requests[3][:2] == (
        "DELETE",
        "http://backend/api/v1/rag/collections/process/entities/7",
    )


@pytest.mark.asyncio
async def test_rag_asset_returns_bytes(requester, fake_session):
    fake_session.queue_bytes(b"image-data")
    result = await requester.rag_get_asset("images/process/1.png")
    assert result == b"image-data"
    assert fake_session.requests[-1] == (
        "GET",
        "http://backend/api/v1/rag/asset",
        {"params": {"path": "images/process/1.png"}},
    )


@pytest.mark.asyncio
async def test_rag_search_rejects_invalid_response_shape(requester, fake_session):
    fake_session.queue_json({"count": 0})
    with pytest.raises(
        RuntimeError, match="RAG 后端响应格式无效: results 必须为列表"
    ):
        await requester.rag_search_text("process", "query")


@pytest.mark.asyncio
async def test_rag_search_rejects_non_object_json(requester, fake_session):
    fake_session.queue_json(None)
    with pytest.raises(
        RuntimeError, match="RAG 后端响应格式无效: results 必须为列表"
    ):
        await requester.rag_search_text("process", "query")


@pytest.mark.asyncio
async def test_rag_http_error_includes_status_and_backend_detail(requester, fake_session):
    fake_session.queue_json(None, status=503, text="milvus unavailable")
    with pytest.raises(RuntimeError, match="HTTP 503 - milvus unavailable"):
        await requester.rag_list_collections()


@pytest.mark.asyncio
async def test_rag_add_images_rejects_mismatched_descriptions(requester):
    with pytest.raises(ValueError, match="图片和描述数量必须一致且不能为空"):
        await requester.rag_add_images("process", ["one.png"], [])


def test_population_script_path_is_stable():
    assert Path("plugins/agent_extensions/populate_rag.py").exists()


def test_population_script_uses_backend_rag_api_only():
    source = Path("plugins/agent_extensions/populate_rag.py").read_text("utf-8")
    assert "from plugins.agent_extensions import _APIRequester" in source
    assert "rag_add_text" in source
    assert "rag_add_images" in source
    assert "MILVUS" not in source
    assert "MoyuClient" not in source
    assert "TextProcessor" not in source


def test_agent_extensions_has_no_direct_database_client():
    paths = [Path("plugins/agent_extensions"), Path("pyproject.toml")]
    forbidden = (
        "pymilvus",
        "MilvusClient",
        "MoyuClient",
        "MILVUS_BASE_URL",
        "MILVUS_URI",
    )
    for path in paths:
        files = path.rglob("*.py") if path.is_dir() else [path]
        for file_path in files:
            source = file_path.read_text("utf-8")
            assert not any(token in source for token in forbidden), file_path


@pytest.mark.asyncio
async def test_search_candidates_uses_text_endpoint_without_image():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.rag_search_text.return_value = [{"id": 1, "score": 0.6}]

    result = await tools._search_rag_candidates("堵盖", None, "process", 5)

    assert result == [{"id": 1, "score": 0.6}]
    tools._requester.rag_search_text.assert_awaited_once_with(
        "process", "堵盖", limit=5
    )
    tools._requester.rag_search_mixed.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_candidates_uses_mixed_endpoint_when_image_is_present():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.rag_search_mixed.return_value = [{"id": 1, "score": 0.6}]

    result = await tools._search_rag_candidates(
        "堵盖", "query.png", "process", 5
    )

    assert result == [{"id": 1, "score": 0.6}]
    tools._requester.rag_search_mixed.assert_awaited_once_with(
        "process", "堵盖", "query.png", limit=5
    )
    tools._requester.rag_search_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_rerank_candidates_sorts_scores_and_uses_asset_path(monkeypatch):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.query_rerank.side_effect = [{"score": 0.2}, {"score": 0.9}]
    cache = AsyncMock(return_value="data/img/part.png")
    monkeypatch.setattr(tools, "_cache_rag_asset", cache, raising=False)
    candidates = [
        {"id": 1, "score": 0.8, "type": "text", "text": "文本"},
        {
            "id": 2,
            "score": 0.1,
            "type": "image",
            "text": "图片",
            "asset_path": "images/process/part.png",
        },
    ]

    result = await tools._rerank_rag_candidates("问题", candidates)

    assert [item["id"] for item in result] == [2, 1]
    assert [item["score"] for item in result] == [0.9, 0.2]
    cache.assert_awaited_once_with("images/process/part.png")
    tools._requester.query_rerank.assert_any_await(
        query_type="text",
        query_text="问题",
        query_image_path=None,
        doc_type="image",
        doc_text=None,
        doc_image_path="data/img/part.png",
    )


@pytest.mark.asyncio
async def test_rerank_failure_keeps_original_rag_score():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.query_rerank.side_effect = RuntimeError("offline")
    candidates = [
        {"id": 1, "score": 0.42, "type": "text", "text": "内容"}
    ]

    result = await tools._rerank_rag_candidates("问题", candidates)

    assert result[0]["score"] == 0.42


@pytest.mark.asyncio
async def test_rerank_propagates_asset_fetch_failure(monkeypatch):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    cache = AsyncMock(side_effect=RuntimeError("asset unavailable"))
    monkeypatch.setattr(tools, "_cache_rag_asset", cache)
    candidates = [
        {
            "id": 1,
            "score": 0.42,
            "type": "image",
            "asset_path": "images/process/part.png",
        }
    ]

    with pytest.raises(RuntimeError, match="asset unavailable"):
        await tools._rerank_rag_candidates("问题", candidates)


@pytest.mark.asyncio
async def test_asset_cache_names_include_path_namespace(tmp_path):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.data_dir = str(tmp_path)
    tools._requester.rag_get_asset.return_value = b"image"

    first = await tools._cache_rag_asset("images/one/shared.png")
    second = await tools._cache_rag_asset("images/two/shared.png")

    assert first != second
    assert Path(first).name.endswith("_shared.png")
    assert Path(second).name.endswith("_shared.png")


def test_rag_content_blocks_preserve_webp_mime_and_skip_missing_asset():
    tools = AgentExtensionTools()
    blocks = tools._build_rag_content_blocks(
        [
            {
                "id": 1,
                "type": "image",
                "text": "webp image",
                "path": "/data/one.webp",
                "_local_asset_path": "cached/one.webp",
            },
            {
                "id": 2,
                "type": "image",
                "text": "missing image",
                "path": "/data/two.png",
            },
        ],
        image_loader=lambda path: b"webp" if path.endswith("one.webp") else b"",
    )

    assert len(blocks) == 3
    assert blocks[1]["source"]["media_type"] == "image/webp"
    assert blocks[2]["type"] == "text"


@pytest.mark.asyncio
async def test_query_knowledge_base_maps_backend_results():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.rag_search_text.return_value = [
        {
            "id": 7,
            "score": 0.812345,
            "type": "image",
            "text": "x" * 600,
            "path": "/data/image.png",
            "subject": "capp",
            "asset_path": "images/process/7.png",
        }
    ]

    result = await tools._query_knowledge_base_async("堵盖", "process", 3)

    assert result == [
        {
            "id": 7,
            "score": 0.8123,
            "text": "x" * 500,
            "path": "/data/image.png",
            "type": "image",
            "subject": "capp",
            "asset_path": "images/process/7.png",
        }
    ]
    tools._requester.rag_search_text.assert_awaited_once_with(
        "process", "堵盖", limit=3
    )


def test_main_assistant_registers_existing_rag_tool():
    context = MagicMock()
    plugin = AgentExtensionsPlugin()

    plugin.on_enable(context)

    registered_tools = context.tool_registry.register.call_args.args[1]
    assert "tool_query_knowledge_base" in [tool.__name__ for tool in registered_tools]


@pytest.mark.asyncio
async def test_main_assistant_rag_tool_uses_text_search_without_image():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.rag_search_text.return_value = []

    result = await tools._query_knowledge_base_async(
        "堵盖", "process", 3, image_path=None
    )

    assert result == []
    tools._requester.rag_search_text.assert_awaited_once_with(
        "process", "堵盖", limit=3
    )
    tools._requester.rag_search_mixed.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_assistant_rag_tool_uses_mixed_search_with_image():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.rag_search_mixed.return_value = []

    result = await tools._query_knowledge_base_async(
        "堵盖", "process", 3, image_path="query.png"
    )

    assert result == []
    tools._requester.rag_search_mixed.assert_awaited_once_with(
        "process", "堵盖", "query.png", limit=3
    )
    tools._requester.rag_search_text.assert_not_awaited()


def test_main_assistant_sync_rag_tool_forwards_image_path(monkeypatch):
    tools = AgentExtensionTools()
    async_entry = MagicMock(return_value="query-coroutine")
    monkeypatch.setattr(tools, "_query_knowledge_base_async", async_entry)
    monkeypatch.setattr(agent_extensions, "_run_async", lambda coro: [])

    tools.tool_query_knowledge_base(
        "堵盖", collection_name="process", limit=3, image_path="query.png"
    )

    async_entry.assert_called_once_with("堵盖", "process", 3, "query.png")


def _subagent_prompt_source(agent_name: str) -> str:
    source = Path(agent_extensions.__file__).read_text(encoding="utf-8")
    start = source.index(f'name="{agent_name}"')
    end = source.index("model=OpenAIChatModel(", start)
    return source[start:end]


@pytest.mark.parametrize(
    "agent_name",
    ["unity_agent", "blender_agent", "process_agent", "comfyui_agent"],
)
def test_subagent_prompt_requires_structured_markdown_handoff(agent_name):
    prompt = _subagent_prompt_source(agent_name)

    for heading in (
        "# 执行结果",
        "## 状态",
        "## 完成摘要",
        "## 生成文件",
        "## 具体结果",
        "## 执行记录",
        "## 警告与未完成项",
    ):
        assert heading in prompt

    assert "路径未提供" in prompt
    assert "不得猜测" in prompt
    assert "绝对路径" in prompt


def test_subagent_prompt_process_requires_complete_file_contents():
    prompt = _subagent_prompt_source("process_agent")

    assert "完整 JSON 内容" in prompt
    assert "工序与工步" in prompt
    assert "view_text_file" in prompt
    assert "检索知识" in prompt


def test_subagent_prompt_image_requires_each_output_and_actual_prompt():
    prompt = _subagent_prompt_source("comfyui_agent")

    assert "每张图片" in prompt
    assert "实际使用的提示词" in prompt
    assert "工具明确返回成功" in prompt


def test_subagent_prompt_blender_requires_objects_and_artifact_paths():
    prompt = _subagent_prompt_source("blender_agent")

    assert "创建、修改和删除的对象" in prompt
    assert "关键尺寸" in prompt
    assert ".blend" in prompt
    assert "导出" in prompt


def test_subagent_prompt_unity_requires_scene_assets_and_tool_results():
    prompt = _subagent_prompt_source("unity_agent")

    assert "GameObject" in prompt
    assert "组件、脚本、资源" in prompt
    assert "工程、场景、脚本" in prompt
    assert "MCP/custom tool" in prompt


@pytest.mark.asyncio
async def test_main_assistant_mixed_rag_reports_missing_image(requester):
    with pytest.raises(FileNotFoundError, match="missing.png"):
        await requester.rag_search_mixed(
            "process", "堵盖", "missing.png", limit=3
        )
