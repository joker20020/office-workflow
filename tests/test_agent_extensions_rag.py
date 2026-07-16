"""agent_extensions 的 ProcessGen RAG HTTP 契约测试。"""

import asyncio
import base64
import hashlib
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import aiohttp
import pytest
from agentscope.credential import (
    DashScopeCredential,
    DeepSeekCredential,
    OpenAICredential,
)
from agentscope.message import (
    AssistantMsg,
    Base64Source,
    DataBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultState,
)
from agentscope.model import (
    DashScopeChatModel,
    DeepSeekChatModel,
    OpenAIChatModel,
)
from agentscope.permission import (
    PermissionBehavior,
    PermissionEngine,
    PermissionMode,
)
from agentscope.state import AgentState, Task
from agentscope.tool import (
    FunctionTool as RealFunctionTool,
)
from agentscope.tool import (
    ToolChunk,
    ToolResponse,
)
from agentscope.tool import (
    Toolkit as RealToolkit,
)

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


def _valid_handoff(details: str) -> str:
    return (
        "# 执行结果\n"
        "## 状态\n成功\n"
        "## 完成摘要\n已完成。\n"
        "## 生成文件\n无\n"
        f"## 具体结果\n{details}\n"
        "## 执行记录\n已执行。\n"
        "## 警告与未完成项\n无"
    )


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
async def test_rag_asset_uses_collection_endpoint(requester, fake_session):
    fake_session.queue_bytes(b"image-data")
    result = await requester.rag_get_asset("工艺 库", "nested/1.png")
    assert result == b"image-data"
    assert fake_session.requests[-1] == (
        "GET",
        "http://backend/api/v1/rag/collections/%E5%B7%A5%E8%89%BA%20%E5%BA%93/asset",
        {"params": {"path": "nested/1.png"}},
    )


@pytest.mark.asyncio
async def test_rag_asset_falls_back_to_general_image_on_404(
    requester, fake_session
):
    fake_session.queue_bytes(b"", status=404, text="missing")
    fake_session.queue_bytes(b"legacy-image")

    result = await requester.rag_get_asset("process", "legacy/反推堵盖2.png")

    assert result == b"legacy-image"
    assert fake_session.requests == [
        (
            "GET",
            "http://backend/api/v1/rag/collections/process/asset",
            {"params": {"path": "legacy/反推堵盖2.png"}},
        ),
        (
            "GET",
            "http://backend/api/v1/images/%E5%8F%8D%E6%8E%A8%E5%A0%B5%E7%9B%962.png",
            {},
        ),
    ]


@pytest.mark.asyncio
async def test_rag_asset_does_not_fallback_on_non_404(requester, fake_session):
    fake_session.queue_bytes(b"", status=500, text="backend failed")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        await requester.rag_get_asset("process", "1.png")

    assert len(fake_session.requests) == 1


@pytest.mark.asyncio
async def test_rag_asset_double_404_is_not_found(requester, fake_session):
    fake_session.queue_bytes(b"", status=404, text="collection missing")
    fake_session.queue_bytes(b"", status=404, text="legacy missing")

    with pytest.raises(FileNotFoundError, match=r"process.*missing\.png"):
        await requester.rag_get_asset("process", "missing.png")


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

    result = await tools._rerank_rag_candidates("问题", "process", candidates)

    assert [item["id"] for item in result] == [2, 1]
    assert [item["score"] for item in result] == [0.9, 0.2]
    cache.assert_awaited_once_with("process", "images/process/part.png")
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

    result = await tools._rerank_rag_candidates("问题", "process", candidates)

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
        await tools._rerank_rag_candidates("问题", "process", candidates)


@pytest.mark.asyncio
async def test_rerank_image_uses_path_when_asset_path_is_missing(monkeypatch):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.query_rerank.return_value = {"score": 0.9}
    cache = AsyncMock(return_value="data/img/local.png")
    monkeypatch.setattr(tools, "_cache_rag_asset", cache)

    result = await tools._rerank_rag_candidates(
        "问题",
        "process",
        [{"id": 1, "score": 0.2, "type": "image", "path": "1.png"}],
    )

    cache.assert_awaited_once_with("process", "1.png")
    assert result[0]["_local_asset_path"] == "data/img/local.png"


@pytest.mark.asyncio
async def test_rerank_double_404_keeps_text_and_original_score(monkeypatch):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    cache = AsyncMock(side_effect=FileNotFoundError("missing"))
    monkeypatch.setattr(tools, "_cache_rag_asset", cache)

    result = await tools._rerank_rag_candidates(
        "问题",
        "process",
        [{"id": 1, "score": 0.42, "type": "image", "asset_path": "1.png"}],
    )

    assert result[0]["score"] == 0.42
    assert result[0]["_asset_error"] == "missing"
    tools._requester.query_rerank.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_agent_passes_collection_to_rerank(monkeypatch):
    class StopAfterRerankError(Exception):
        pass

    tools = AgentExtensionTools()
    candidates = [{"id": 1, "type": "text", "text": "内容"}]
    tools._search_rag_candidates = AsyncMock(return_value=candidates)
    tools._rerank_rag_candidates = AsyncMock(side_effect=StopAfterRerankError)
    monkeypatch.setattr(agent_extensions, "AGENTSCOPE_AVAILABLE", True)

    with pytest.raises(StopAfterRerankError):
        await tools._process_agent_async("任务", None, "process", 5)

    tools._rerank_rag_candidates.assert_awaited_once_with(
        "任务",
        "process",
        candidates,
    )


@pytest.mark.asyncio
async def test_asset_cache_redownloads_and_overwrites_existing_file(tmp_path):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.data_dir = str(tmp_path)
    tools._requester.rag_get_asset.side_effect = [b"first", b"second"]

    first = await tools._cache_rag_asset("process", "shared.png")
    second = await tools._cache_rag_asset("process", "shared.png")

    assert first == second
    assert Path(second).read_bytes() == b"second"
    assert tools._requester.rag_get_asset.await_args_list == [
        call("process", "shared.png"),
        call("process", "shared.png"),
    ]


@pytest.mark.asyncio
async def test_asset_cache_names_include_collection_and_path(tmp_path):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.data_dir = str(tmp_path)
    tools._requester.rag_get_asset.return_value = b"image"

    first = await tools._cache_rag_asset("one", "shared.png")
    second = await tools._cache_rag_asset("two", "shared.png")

    expected_namespace = hashlib.sha256(b"one\0shared.png").hexdigest()[:12]

    assert first != second
    assert Path(first).name == f"{expected_namespace}_shared.png"
    assert Path(first).name.endswith("_shared.png")
    assert Path(second).name.endswith("_shared.png")


@pytest.mark.asyncio
async def test_asset_cache_sanitizes_remote_basename_for_local_file(tmp_path):
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.data_dir = str(tmp_path)
    tools._requester.rag_get_asset.return_value = b"image"

    local_path = await tools._cache_rag_asset(
        "process",
        "nested/bad:name?.png",
    )

    assert Path(local_path).read_bytes() == b"image"
    assert Path(local_path).name.endswith("_bad_name_.png")


def test_response_uses_agentscope_2_text_blocks_and_state():
    success = agent_extensions._make_response("ok")
    error = agent_extensions._make_response("bad", success=False)
    empty = agent_extensions._make_response(None)

    assert agent_extensions.AGENTSCOPE_AVAILABLE is True
    assert isinstance(success, ToolResponse)
    assert success.state is ToolResultState.SUCCESS
    assert len(success.content) == 1
    assert isinstance(success.content[0], TextBlock)
    assert success.content[0].text == "ok"
    assert error.state is ToolResultState.ERROR
    assert error.content[0].text == "bad"
    assert empty.content[0].text == "(无返回结果)"


def test_message_text_joins_multiple_text_blocks_and_handles_empty_replies():
    reply = AssistantMsg(
        name="Agent",
        content=[TextBlock(text="a"), TextBlock(text="b")],
    )

    assert agent_extensions._message_text(reply) == "a\nb"
    assert agent_extensions._message_text(
        AssistantMsg(name="Agent", content=[]),
    ) == ""
    assert agent_extensions._message_text(None) == ""


@pytest.mark.parametrize(
    ("provider", "model_type", "credential_type", "model_name", "base_url"),
    [
        (
            "openai",
            OpenAIChatModel,
            OpenAICredential,
            "gpt-4o",
            "https://api.openai.com/v1",
        ),
        (
            "deepseek",
            DeepSeekChatModel,
            DeepSeekCredential,
            "deepseek-chat",
            "https://api.deepseek.com",
        ),
        (
            "dashscope",
            DashScopeChatModel,
            DashScopeCredential,
            "qwen-turbo",
            "https://api.dashscope.com",
        ),
    ],
)
def test_build_model_uses_project_provider_defaults_and_secret_credentials(
    provider,
    model_type,
    credential_type,
    model_name,
    base_url,
):
    model = agent_extensions._build_model(provider, "", "", "raw-secret")

    assert isinstance(model, model_type)
    assert isinstance(model.credential, credential_type)
    assert model.model == model_name
    assert model.credential.base_url == base_url
    assert model.credential.api_key.get_secret_value() == "raw-secret"
    assert "raw-secret" not in repr(model.credential)


def test_build_model_preserves_openai_compatible_endpoint():
    model = agent_extensions._build_model(
        "openai",
        "compatible-vlm",
        "http://localhost:8000/v1",
        "secret",
    )

    assert isinstance(model, OpenAIChatModel)
    assert model.model == "compatible-vlm"
    assert model.credential.base_url == "http://localhost:8000/v1"


def test_rag_content_blocks_preserve_webp_mime_and_skip_missing_asset(caplog):
    tools = AgentExtensionTools()
    loaded = []

    def image_loader(path):
        loaded.append(path)
        return b"webp"

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
                "_asset_error": "not found",
            },
        ],
        image_loader=image_loader,
    )

    assert loaded == ["cached/one.webp"]
    assert len(blocks) == 3
    assert isinstance(blocks[0], TextBlock)
    assert isinstance(blocks[1], DataBlock)
    assert isinstance(blocks[1].source, Base64Source)
    assert blocks[1].source.media_type == "image/webp"
    assert blocks[1].source.data == base64.b64encode(b"webp").decode("utf-8")
    assert isinstance(blocks[2], TextBlock)
    assert "missing image" in blocks[2].text
    assert "asset_path" not in caplog.text


def test_rag_content_blocks_reload_cached_image_bytes_on_every_call(tmp_path):
    tools = AgentExtensionTools()
    image = tmp_path / "cached.png"
    candidate = {
        "id": 1,
        "type": "image",
        "text": "cached image",
        "path": "remote.png",
        "_local_asset_path": str(image),
    }
    image.write_bytes(b"first")

    first = tools._build_rag_content_blocks([candidate])
    image.write_bytes(b"second")
    second = tools._build_rag_content_blocks([candidate])

    assert isinstance(first[1], DataBlock)
    assert first[1].source.data == base64.b64encode(b"first").decode("utf-8")
    assert second[1].source.data == base64.b64encode(b"second").decode("utf-8")


def test_rag_content_blocks_do_not_use_misleading_asset_path_warning():
    source = Path(agent_extensions.__file__).read_text(encoding="utf-8")
    assert "RAG 图片候选缺少 asset_path，已仅保留文本描述" not in source


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


@pytest.mark.parametrize(
    ("name", "default"),
    [
        ("AGENT_TOOL_TIMEOUT_SECONDS", 1800.0),
        ("IMAGE_REQUEST_TIMEOUT_SECONDS", 600.0),
        ("UNITY_MCP_TIMEOUT_SECONDS", 600.0),
    ],
)
def test_timeout_defaults(monkeypatch, name, default):
    monkeypatch.delenv(name, raising=False)
    assert agent_extensions._get_timeout_seconds(name, default) == default


def test_timeout_environment_override(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "42.5")
    assert agent_extensions._get_timeout_seconds(
        "AGENT_TOOL_TIMEOUT_SECONDS", 1800.0
    ) == 42.5


@pytest.mark.parametrize("value", ["invalid", "0", "-1", "nan", "inf", "-inf"])
def test_invalid_timeout_falls_back(monkeypatch, value):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", value)
    assert agent_extensions._get_timeout_seconds(
        "AGENT_TOOL_TIMEOUT_SECONDS", 1800.0
    ) == 1800.0


@pytest.mark.asyncio
async def test_run_async_reports_real_thread_timeout(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "0.01")

    async def slow_result():
        await asyncio.sleep(0.05)
        return "finished"

    with pytest.raises(
        agent_extensions._AgentToolTimeoutError,
        match="执行超时：工具运行超过 0.01 秒",
    ):
        agent_extensions._run_async(slow_result())


@pytest.mark.asyncio
async def test_unity_public_timeout_cancels_work_and_closes_before_return(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "0.01")
    cancelled = threading.Event()
    post_timeout_mutation = threading.Event()
    events, captured = _install_unity_recording_fakes(monkeypatch)
    tools = AgentExtensionTools()

    async def wait_for_cancellation(unity_mcp, task, info):
        try:
            await asyncio.sleep(10)
            post_timeout_mutation.set()
        finally:
            cancelled.set()

    monkeypatch.setattr(tools, "_unity_ar_connected", wait_for_cancellation)

    response = tools.tool_unity_ar("task")

    assert response.state is ToolResultState.ERROR
    assert "执行超时" in response.content[0].text
    assert cancelled.is_set()
    assert captured["client_instance"].close_count == 1
    assert events[-1] == "close"
    assert not post_timeout_mutation.is_set()


@pytest.mark.asyncio
async def test_run_async_timeout_cancels_spawned_tasks_before_loop_close(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "0.01")
    child_cancelled = threading.Event()

    async def child_work():
        try:
            await asyncio.sleep(10)
        finally:
            child_cancelled.set()

    async def parent_work():
        asyncio.create_task(child_work())
        await asyncio.sleep(10)

    with pytest.raises(agent_extensions._AgentToolTimeoutError):
        agent_extensions._run_async(parent_work())

    assert child_cancelled.is_set()


def test_run_async_bounds_cancellation_resistant_child_cleanup(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("AGENT_TOOL_CLEANUP_GRACE_SECONDS", "0.02")
    release = threading.Event()
    timer = threading.Timer(0.2, release.set)
    timer.start()

    async def resistant_child():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            while not release.is_set():
                await asyncio.sleep(0.005)

    async def parent_work():
        asyncio.create_task(resistant_child())
        await asyncio.sleep(10)

    started = time.monotonic()
    with pytest.raises(agent_extensions._AgentToolTimeoutError) as exc_info:
        agent_extensions._run_async(parent_work())
    elapsed = time.monotonic() - started
    release.set()
    timer.join()

    assert elapsed < 0.15
    assert "清理未完成" in str(exc_info.value)
    assert "仍在运行" in str(exc_info.value)


def test_run_async_reports_live_default_executor_without_waiting_forever(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("AGENT_TOOL_CLEANUP_GRACE_SECONDS", "0.02")
    release = threading.Event()
    mutated = threading.Event()
    timer = threading.Timer(0.2, release.set)
    timer.start()

    def executor_work():
        release.wait()
        mutated.set()

    async def parent_work():
        await asyncio.get_running_loop().run_in_executor(None, executor_work)

    started = time.monotonic()
    with pytest.raises(agent_extensions._AgentToolTimeoutError) as exc_info:
        agent_extensions._run_async(parent_work())
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert "默认执行器" in str(exc_info.value)
    assert "清理未完成" in str(exc_info.value)
    assert not mutated.is_set()
    release.set()
    timer.join()


@pytest.mark.asyncio
async def test_unity_timeout_bounds_hanging_mcp_close_and_reports_incomplete_cleanup(
    monkeypatch,
):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("AGENT_TOOL_CLEANUP_GRACE_SECONDS", "0.02")
    release = threading.Event()
    timer = threading.Timer(0.2, release.set)
    timer.start()
    events, captured = _install_unity_recording_fakes(monkeypatch)
    tools = AgentExtensionTools()

    async def wait_for_cancel(unity_mcp, task, info):
        await asyncio.sleep(10)

    original_close = captured.get("client_instance")
    monkeypatch.setattr(tools, "_unity_ar_connected", wait_for_cancel)

    class HangingCloseClient(agent_extensions.MCPClient):
        async def close(self):
            events.append("close-start")
            while not release.is_set():
                await asyncio.sleep(0.005)
            await super().close()

    monkeypatch.setattr(agent_extensions, "MCPClient", HangingCloseClient)
    started = time.monotonic()
    response = tools.tool_unity_ar("task")
    elapsed = time.monotonic() - started
    release.set()
    timer.join()

    assert original_close is None
    assert elapsed < 0.15
    assert response.state is ToolResultState.ERROR
    assert "清理未完成" in response.content[0].text
    assert "仍在运行" in response.content[0].text
    assert "close-start" in events


@pytest.mark.asyncio
async def test_run_async_distinguishes_completed_none(monkeypatch):
    monkeypatch.setenv("AGENT_TOOL_TIMEOUT_SECONDS", "1")

    async def no_result():
        return None

    assert agent_extensions._run_async(no_result()) == "(工具执行完成但无返回结果)"


@pytest.mark.asyncio
async def test_text_to_image_uses_configured_timeout(
    tmp_path, fake_session, monkeypatch
):
    requester = _APIRequester(data_dir=str(tmp_path), workflow_path=None)
    fake_session.queue_bytes(b"png")
    monkeypatch.setenv("IMAGE_REQUEST_TIMEOUT_SECONDS", "12.5")

    assert await requester.text_to_image("prompt", "result.png") is True

    timeout = fake_session.requests[0][2]["timeout"]
    assert timeout.total == 12.5


def _install_comfyui_recording_fakes(
    monkeypatch,
    tmp_path,
    *,
    reply="refined positive prompt",
    reply_error=None,
    api_result=True,
    api_error=None,
    write_file=True,
):
    captured = {"api_calls": []}

    class FakeToolkit:
        def __init__(self, **kwargs):
            captured["toolkit"] = kwargs
            captured["toolkit_instance"] = self

    class FakeReActConfig:
        def __init__(self, **kwargs):
            captured["react_config"] = kwargs
            captured["react_config_instance"] = self
            self.max_iters = kwargs["max_iters"]

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs

        async def reply(self, msg):
            captured["message"] = msg
            if reply_error is not None:
                raise reply_error
            if reply is None:
                return None
            return AssistantMsg(name="ComfyUIAgent", content=reply)

    class FakeRequester:
        data_dir = str(tmp_path)

        async def text_to_image(self, prompt, output_name, **kwargs):
            captured["api_calls"].append((prompt, output_name, kwargs))
            if api_error is not None:
                raise api_error
            if api_result and write_file:
                target = tmp_path / "img" / output_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"png")
            return api_result

    def fake_build_model(provider, model_name, base_url, api_key):
        captured["model"] = (provider, model_name, base_url, api_key)
        return "comfyui-model"

    real_user_msg = agent_extensions.UserMsg

    def fake_user_msg(**kwargs):
        captured["user_msg"] = kwargs
        return real_user_msg(**kwargs)

    monkeypatch.setattr(agent_extensions, "Toolkit", FakeToolkit)
    monkeypatch.setattr(agent_extensions, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(agent_extensions, "ReActConfig", FakeReActConfig, raising=False)
    monkeypatch.setattr(agent_extensions, "_build_model", fake_build_model)
    monkeypatch.setattr(agent_extensions, "UserMsg", fake_user_msg)
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "http://model/v1")
    tools = AgentExtensionTools()
    tools._requester = FakeRequester()
    return tools, captured


@pytest.mark.asyncio
async def test_comfyui_uses_agentscope2_agent_and_reports_written_image(
    monkeypatch,
    tmp_path,
):
    refined_prompt = "refined positive prompt"
    tools, captured = _install_comfyui_recording_fakes(
        monkeypatch,
        tmp_path,
        reply=refined_prompt,
    )

    result = await tools._comfyui_agent_async("draw an assembly guide")

    expected_name = (
        f"comfyui-{hashlib.sha256(refined_prompt.encode('utf-8')).hexdigest()[:16]}.png"
    )
    expected_path = str((tmp_path / "img" / expected_name).resolve())
    assert captured["toolkit"] == {"tools": []}
    assert captured["agent"]["name"] == "ComfyUIAgent"
    assert captured["agent"]["model"] == "comfyui-model"
    assert captured["agent"]["toolkit"] is captured["toolkit_instance"]
    assert captured["react_config"] == {"max_iters": 60}
    assert captured["react_config_instance"].max_iters == 60
    assert (
        captured["agent"]["react_config"]
        is captured["react_config_instance"]
    )
    assert captured["model"] == (
        "openai",
        tools._llm_name,
        "http://model/v1",
        "secret",
    )
    assert captured["user_msg"] == {
        "name": "User",
        "content": "draw an assembly guide",
    }
    assert captured["message"].role == "user"
    assert captured["api_calls"] == [
        (
            refined_prompt,
            expected_name,
            {
                "negative_prompt": (
                    "people, person, portrait, photorealistic, watermark, signature"
                ),
                "width": 1024,
                "height": 1024,
                "steps": 20,
                "seed": None,
            },
        )
    ]
    for heading in (
        "# 执行结果",
        "## 状态",
        "## 完成摘要",
        "## 生成文件",
        "## 具体结果",
        "## 执行记录",
        "## 警告与未完成项",
    ):
        assert heading in result
    assert "成功" in result
    assert refined_prompt in result
    assert "people, person, portrait, photorealistic, watermark, signature" in result
    assert "1024x1024" in result
    assert "20" in result
    assert "未提供" in result
    assert expected_path in result
    assert "API 返回：True" in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "reply_error", "expected"),
    [
        (None, None, "未返回"),
        ("", None, "空"),
        ("unused", RuntimeError("agent failed"), "agent failed"),
    ],
)
async def test_comfyui_agent_failures_are_structured_without_image_api_call(
    monkeypatch,
    tmp_path,
    reply,
    reply_error,
    expected,
):
    tools, captured = _install_comfyui_recording_fakes(
        monkeypatch,
        tmp_path,
        reply=reply,
        reply_error=reply_error,
    )

    result = await tools._comfyui_agent_async("task")

    assert "## 状态\n失败" in result
    assert expected in result
    assert "## 生成文件\n无" in result
    assert captured["api_calls"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("api_result", "api_error", "write_file", "expected"),
    [
        (False, None, False, "API 返回：False"),
        (True, None, False, "预期文件不存在"),
        (True, RuntimeError("backend offline"), False, "backend offline"),
    ],
)
async def test_comfyui_image_failures_never_report_success(
    monkeypatch,
    tmp_path,
    api_result,
    api_error,
    write_file,
    expected,
):
    tools, _ = _install_comfyui_recording_fakes(
        monkeypatch,
        tmp_path,
        api_result=api_result,
        api_error=api_error,
        write_file=write_file,
    )

    result = await tools._comfyui_agent_async("task")

    assert "## 状态\n失败" in result
    assert expected in result
    assert "## 状态\n成功" not in result


@pytest.mark.asyncio
async def test_comfyui_sync_wrapper_preserves_success_tool_response(
    monkeypatch,
    tmp_path,
):
    tools, _ = _install_comfyui_recording_fakes(monkeypatch, tmp_path)
    internal_result = await tools._comfyui_agent_async("task")

    def fake_run_async(coro):
        coro.close()
        return internal_result

    monkeypatch.setattr(
        agent_extensions,
        "_run_async",
        fake_run_async,
    )

    response = tools.tool_generate_image("task")

    assert isinstance(response, ToolResponse)
    assert response.state == ToolResultState.SUCCESS
    assert response.content[0].text == internal_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "api_result", "api_error", "write_file", "expected"),
    [
        (None, True, None, True, "未返回"),
        ("refined prompt", False, None, False, "API 返回：False"),
        (
            "refined prompt",
            True,
            RuntimeError("backend offline"),
            False,
            "backend offline",
        ),
        ("refined prompt", True, None, False, "预期文件不存在"),
    ],
)
async def test_comfyui_sync_wrapper_marks_structured_failures_as_error(
    monkeypatch,
    tmp_path,
    reply,
    api_result,
    api_error,
    write_file,
    expected,
):
    tools, _ = _install_comfyui_recording_fakes(
        monkeypatch,
        tmp_path,
        reply=reply,
        api_result=api_result,
        api_error=api_error,
        write_file=write_file,
    )
    internal_result = await tools._comfyui_agent_async("task")

    def fake_run_async(coro):
        coro.close()
        return internal_result

    monkeypatch.setattr(agent_extensions, "_run_async", fake_run_async)

    response = tools.tool_generate_image("task")

    assert response.state == ToolResultState.ERROR
    assert response.content[0].text == internal_result
    assert "## 状态\n失败" in response.content[0].text
    assert expected in response.content[0].text


def test_comfyui_sync_wrapper_marks_timeout_as_structured_error(monkeypatch):
    def fake_run_async(coro):
        coro.close()
        return "(执行超时：工具运行超过 1 秒)"

    monkeypatch.setattr(agent_extensions, "_run_async", fake_run_async)

    response = AgentExtensionTools().tool_generate_image("task")

    assert response.state == ToolResultState.ERROR
    for heading in (
        "# 执行结果",
        "## 状态",
        "## 完成摘要",
        "## 生成文件",
        "## 具体结果",
        "## 执行记录",
        "## 警告与未完成项",
    ):
        assert heading in response.content[0].text
    assert "## 状态\n失败" in response.content[0].text
    assert "执行超时" in response.content[0].text


def test_comfyui_public_response_preserves_non_2xx_status_and_body(
    monkeypatch,
    tmp_path,
    fake_session,
):
    tools, _ = _install_comfyui_recording_fakes(monkeypatch, tmp_path)
    tools._requester = _APIRequester(data_dir=str(tmp_path), workflow_path=None)
    fake_session.queue_bytes(
        b"",
        status=503,
        text='{"error":"queue full"}',
    )

    response = tools.tool_generate_image("draw an assembly guide")

    assert response.state is ToolResultState.ERROR
    assert "HTTP 503" in response.content[0].text
    assert '{"error":"queue full"}' in response.content[0].text
    details = response.content[0].text.split("## 具体结果\n", 1)[1].split(
        "## 执行记录",
        1,
    )[0]
    warnings = response.content[0].text.split("## 警告与未完成项\n", 1)[1]
    assert "HTTP 503" in details
    assert "queue full" in warnings


@pytest.mark.parametrize(
    ("call_tool", "expected"),
    [
        (lambda tools: tools.tool_unity_ar("task"), "Unity"),
        (lambda tools: tools.tool_blender_model("task"), "Blender"),
        (lambda tools: tools.tool_generate_process("task"), "工艺规划"),
    ],
)
def test_public_subagent_wrappers_mark_agentscope_unavailable_as_error(
    monkeypatch,
    call_tool,
    expected,
):
    monkeypatch.setattr(agent_extensions, "AGENTSCOPE_AVAILABLE", False)

    response = call_tool(AgentExtensionTools())

    assert response.state is ToolResultState.ERROR
    assert "## 状态\n失败" in response.content[0].text
    assert expected in response.content[0].text
    for heading in (
        "## 完成摘要",
        "## 生成文件",
        "## 具体结果",
        "## 执行记录",
        "## 警告与未完成项",
    ):
        assert heading in response.content[0].text


@pytest.mark.parametrize(
    "call_tool",
    [
        lambda tools: tools.tool_unity_ar("task"),
        lambda tools: tools.tool_blender_model("task"),
        lambda tools: tools.tool_generate_process("task"),
        lambda tools: tools.tool_generate_image("task"),
    ],
)
def test_public_subagent_wrappers_reject_invalid_handoff_status(
    monkeypatch,
    call_tool,
):
    invalid = agent_extensions._SubagentResult(
        "# 执行结果\n"
        "## 状态\n完成\n"
        "## 完成摘要\nsummary\n"
        "## 生成文件\n无\n"
        "## 具体结果\ndetails\n"
        "## 执行记录\nrecord\n"
        "## 警告与未完成项\n无",
        success=True,
    )

    def fake_run_async(coro):
        coro.close()
        return invalid

    monkeypatch.setattr(agent_extensions, "_run_async", fake_run_async)

    response = call_tool(AgentExtensionTools())

    assert response.state is ToolResultState.ERROR
    assert "状态值无效" in response.content[0].text
    assert "完成" in response.content[0].text


@pytest.mark.parametrize(
    "call_tool",
    [
        lambda tools: tools.tool_unity_ar("task"),
        lambda tools: tools.tool_blender_model("task"),
        lambda tools: tools.tool_generate_process("task"),
        lambda tools: tools.tool_generate_image("task"),
    ],
)
def test_public_subagent_wrappers_reject_missing_handoff_headings(
    monkeypatch,
    call_tool,
):
    malformed = agent_extensions._SubagentResult(
        "# 执行结果\n## 状态\n成功",
        success=True,
    )

    def fake_run_async(coro):
        coro.close()
        return malformed

    monkeypatch.setattr(agent_extensions, "_run_async", fake_run_async)

    response = call_tool(AgentExtensionTools())

    assert response.state is ToolResultState.ERROR
    assert "缺少必需章节" in response.content[0].text


@pytest.mark.parametrize(
    "malformed",
    [
        _valid_handoff("details").replace("# 执行结果", "## 执行结果", 1),
        (
            "# 执行结果\n"
            "## 状态\n成功\n"
            "## 生成文件\n无\n"
            "## 完成摘要\nsummary\n"
            "## 具体结果\ndetails\n"
            "## 执行记录\nrecord\n"
            "## 警告与未完成项\n无"
        ),
        _valid_handoff("details") + "\n## 完成摘要\nduplicate",
        "```markdown\n" + _valid_handoff("details") + "\n```",
        (
            "# 执行结果\n"
            "## 状态\n成功\n"
            "## 完成摘要\n\n"
            "## 生成文件\n\n"
            "## 具体结果\n\n"
            "## 执行记录\n\n"
            "## 警告与未完成项\n"
        ),
    ],
)
def test_handoff_parser_rejects_wrong_order_levels_duplicates_fences_and_empty(
    malformed,
):
    result = agent_extensions._validate_subagent_handoff(malformed, "测试")

    assert result.success is False
    assert "## 状态\n失败" in result


def test_process_normalization_uses_fence_longer_than_artifact_backticks(tmp_path):
    path = tmp_path / "工序100.json"
    content = '{"note": "contains ``` and ```` runs"}'
    file_records = [
        {
            "operation": "write_text_file",
            "success": True,
            "result": "written",
            "path": str(path),
            "content": content,
        },
    ]

    result = agent_extensions._validate_subagent_handoff(
        _valid_handoff("model details"),
        "工艺规划",
        file_records=file_records,
    )

    assert "`````json\n" in result
    assert f"\n{content}\n`````" in result


@pytest.mark.asyncio
async def test_task_observation_middleware_records_real_tool_result_and_state():
    records = []
    middleware = agent_extensions._TaskObservationMiddleware(records)
    state = AgentState()
    toolkit = RealToolkit(
        tools=[agent_extensions.TaskCreate(middlewares=[middleware])],
    )

    results = [
        result
        async for result in toolkit.call_tool(
            ToolCallBlock(
                id="create-task",
                name="TaskCreate",
                input=agent_extensions.json.dumps(
                    {"subject": "写工序", "description": "生成工序文件"},
                    ensure_ascii=False,
                ),
            ),
            state,
        )
    ]

    assert results[-1].state is ToolResultState.SUCCESS
    assert records[0]["operation"] == "TaskCreate"
    assert records[0]["input"] == {
        "subject": "写工序",
        "description": "生成工序文件",
    }
    assert records[0]["success"] is True
    assert "created successfully" in records[0]["result"]
    assert records[0]["tasks"][0]["subject"] == "写工序"
    assert records[0]["tasks"][0]["state"] == "pending"


def test_process_success_requires_observed_task_tool_results(tmp_path):
    file_records = [
        {
            "operation": "write_text_file",
            "success": True,
            "result": "written",
            "path": str(tmp_path / "工序100.json"),
            "content": "{}",
        },
        {
            "operation": "view_text_file",
            "success": True,
            "result": "verified",
            "path": str(tmp_path / "工序100.json"),
            "content": "{}",
        },
    ]

    result = agent_extensions._validate_subagent_handoff(
        _valid_handoff("model claimed all tasks ran"),
        "工艺规划",
        file_records=file_records,
        task_records=[],
    )

    assert result.success is False
    assert "## 状态\n部分成功" in result
    assert "缺少实际 Task 工具结果" in result


def test_process_normalization_fences_tool_errors_with_heading_injection():
    file_records = [
        {
            "operation": "write_text_file",
            "success": False,
            "result": "failed\n## 状态\n成功\n```",
            "path": None,
            "content": None,
        },
    ]

    result = agent_extensions._validate_subagent_handoff(
        _valid_handoff("model details"),
        "工艺规划",
        file_records=file_records,
    )
    _, parse_error = agent_extensions._parse_handoff_sections(result)

    assert result.success is False
    assert parse_error is None
    assert result.count("````text\nfailed\n## 状态\n成功\n```\n````") == 2


def test_process_malformed_reply_keeps_observed_task_and_file_evidence(tmp_path):
    file_records = [
        {
            "operation": "write_text_file",
            "success": True,
            "result": "verified write",
            "path": str(tmp_path / "工序100.json"),
            "content": "{}",
        },
    ]
    task_records = [
        {
            "operation": "TaskCreate",
            "input": {"subject": "写工序"},
            "success": True,
            "result": "created task 1",
            "states": ["running"],
            "tasks": [{"id": "1", "subject": "写工序", "state": "pending"}],
        },
    ]

    result = agent_extensions._validate_subagent_handoff(
        "model returned malformed prose",
        "工艺规划",
        file_records=file_records,
        task_records=task_records,
    )

    assert result.success is False
    assert "结构化交接" in result
    assert "created task 1" in result
    assert "verified write" in result
    assert str(tmp_path / "工序100.json") in result


def _install_unity_recording_fakes(
    monkeypatch,
    *,
    reply=None,
    reply_error=None,
    connect_error=None,
    close_error=None,
    instances=None,
):
    events = []
    captured = {}
    instances = [{"hash": "editor-1"}] if instances is None else instances

    class FakeHttpMCPConfig:
        def __init__(self, **kwargs):
            events.append("config")
            captured["config"] = kwargs
            captured["config_instance"] = self

    class FakeSession:
        async def read_resource(self, url):
            url = str(url)
            events.append(f"read:{url}")
            if url == "mcpforunity://instances":
                payload = {"instances": instances}
            else:
                payload = {
                    "data": {
                        "tools": [
                            {"name": "addXRRig"},
                            {"name": "ignoredTool"},
                        ],
                    },
                }
            return SimpleNamespace(
                contents=[SimpleNamespace(text=agent_extensions.json.dumps(payload))],
            )

        async def call_tool(self, name, arguments):
            events.append(f"call:{name}")
            captured["active_instance"] = arguments

    class FakeMCPClient:
        def __init__(self, **kwargs):
            events.append("client")
            captured["client"] = kwargs
            captured["client_instance"] = self
            self._session = FakeSession()
            self.connected = False
            self.close_count = 0

        @property
        def is_connected(self):
            return self.connected

        async def connect(self):
            events.append("connect")
            if connect_error is not None:
                raise connect_error
            self.connected = True

        async def close(self):
            events.append("close")
            self.close_count += 1
            if close_error is not None:
                raise close_error
            self.connected = False

    class FakeToolkit:
        def __init__(self, **kwargs):
            events.append("toolkit")
            captured["toolkit"] = kwargs
            captured["toolkit_instance"] = self
            assert kwargs["mcps"][0].connected is True

    class FakeAgent:
        def __init__(self, **kwargs):
            events.append("agent")
            captured["agent"] = kwargs

        async def reply(self, msg):
            events.append("reply")
            captured["message"] = msg
            if reply_error is not None:
                raise reply_error
            return (
                reply
                if reply is not None
                else AssistantMsg(
                    name="UnityAgent",
                    content=_valid_handoff("unity result"),
                )
            )

    class FakeReActConfig:
        def __init__(self, **kwargs):
            captured["react_config"] = kwargs

    def fake_build_model(provider, model_name, base_url, api_key):
        captured["model"] = (provider, model_name, base_url, api_key)
        return "model"

    real_user_msg = agent_extensions.UserMsg

    def fake_user_msg(**kwargs):
        captured["user_msg"] = kwargs
        return real_user_msg(**kwargs)

    monkeypatch.setattr(agent_extensions, "HttpMCPConfig", FakeHttpMCPConfig, raising=False)
    monkeypatch.setattr(agent_extensions, "MCPClient", FakeMCPClient, raising=False)
    monkeypatch.setattr(agent_extensions, "Toolkit", FakeToolkit)
    monkeypatch.setattr(agent_extensions, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(agent_extensions, "ReActConfig", FakeReActConfig, raising=False)
    monkeypatch.setattr(agent_extensions, "_build_model", fake_build_model)
    monkeypatch.setattr(agent_extensions, "UserMsg", fake_user_msg)
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "http://model/v1")
    return events, captured


@pytest.mark.asyncio
async def test_unity_uses_agentscope2_http_mcp_agent_and_user_message(monkeypatch):
    monkeypatch.setenv("UNITY_MCP_TIMEOUT_SECONDS", "15")
    events, captured = _install_unity_recording_fakes(monkeypatch)

    result = await AgentExtensionTools()._unity_ar_async(
        "build an AR guide",
        '{"assembly": ["step one"]}',
    )

    assert result == _valid_handoff("unity result")
    assert captured["config"] == {
        "url": "http://localhost:8080/mcp",
        "timeout": 15.0,
    }
    assert captured["client"] == {
        "name": "unity_mcp",
        "is_stateful": True,
        "mcp_config": captured["config_instance"],
        "execution_timeout": 15.0,
    }
    assert events.index("connect") < events.index("toolkit")
    assert captured["toolkit"] == {"mcps": [captured["client_instance"]]}
    assert captured["agent"]["name"] == "UnityAgent"
    assert captured["agent"]["model"] == "model"
    assert captured["agent"]["toolkit"] is captured["toolkit_instance"]
    assert captured["react_config"] == {"max_iters": 60}
    assert captured["model"] == (
        "openai",
        AgentExtensionTools()._llm_name,
        "http://model/v1",
        "secret",
    )
    assert captured["message"].name == "User"
    assert captured["message"].role == "user"
    assert captured["user_msg"]["name"] == "User"
    assert captured["user_msg"]["content"] == captured["message"].get_text_content()
    prompt = captured["message"].get_text_content()
    assert "build an AR guide" in prompt
    assert "assembly" in prompt
    assert captured["active_instance"] == {"instance": "editor-1"}
    assert "close" == events[-1]
    assert events.count("close") == 1


@pytest.mark.asyncio
async def test_unity_prompt_keeps_structured_markdown_contract(monkeypatch):
    _, captured = _install_unity_recording_fakes(monkeypatch)

    await AgentExtensionTools()._unity_ar_async("task", "{}")

    prompt = captured["agent"]["system_prompt"]
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
    assert "GameObject" in prompt
    assert "MCP/custom tool" in prompt
    assert "addXRRig" in prompt
    assert "ignoredTool" not in prompt


@pytest.mark.asyncio
async def test_unity_empty_reply_uses_no_content_fallback_and_closes(monkeypatch):
    events, _ = _install_unity_recording_fakes(
        monkeypatch,
        reply=AssistantMsg(name="UnityAgent", content=""),
    )

    result = await AgentExtensionTools()._unity_ar_async("task", "{}")

    assert result.success is False
    assert "Unity Agent 未返回内容" in result
    assert events.count("close") == 1
    assert events[-1] == "close"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply_error",
    [RuntimeError("agent failed"), TimeoutError(), asyncio.CancelledError()],
)
async def test_unity_closes_once_and_propagates_reply_errors(monkeypatch, reply_error):
    events, _ = _install_unity_recording_fakes(
        monkeypatch,
        reply_error=reply_error,
    )

    with pytest.raises(type(reply_error)):
        await AgentExtensionTools()._unity_ar_async("task", "{}")

    assert events.count("close") == 1
    assert events[-1] == "close"


@pytest.mark.asyncio
async def test_unity_connect_failure_does_not_close_invalid_client(monkeypatch):
    events, _ = _install_unity_recording_fakes(
        monkeypatch,
        connect_error=RuntimeError("offline"),
    )

    result = await AgentExtensionTools()._unity_ar_async("task", "{}")

    assert "offline" in result
    assert "close" not in events


@pytest.mark.asyncio
async def test_unity_no_active_instance_still_closes_once(monkeypatch):
    events, _ = _install_unity_recording_fakes(monkeypatch, instances=[])

    result = await AgentExtensionTools()._unity_ar_async("task", "{}")

    assert "Unity" in result
    assert events.count("close") == 1


@pytest.mark.asyncio
async def test_unity_cleanup_error_does_not_hide_agent_error(monkeypatch):
    events, _ = _install_unity_recording_fakes(
        monkeypatch,
        reply_error=RuntimeError("primary failure"),
        close_error=ValueError("cleanup failure"),
    )

    with pytest.raises(RuntimeError, match="primary failure"):
        await AgentExtensionTools()._unity_ar_async("task", "{}")

    assert events.count("close") == 1


def _install_blender_recording_fakes(
    monkeypatch,
    *,
    reply=...,
    reply_error=None,
    connect_error=None,
    close_error=None,
    toolkit_error=None,
):
    events = []
    captured = {}

    class FakeStdioMCPConfig:
        def __init__(self, **kwargs):
            events.append("config")
            captured["config"] = kwargs
            captured["config_instance"] = self

    class FakeMCPClient:
        def __init__(self, **kwargs):
            events.append("client")
            captured["client"] = kwargs
            captured["client_instance"] = self
            self.connected = False
            self.close_count = 0

        async def connect(self):
            events.append("connect")
            if connect_error is not None:
                raise connect_error
            self.connected = True

        async def close(self):
            events.append("close")
            self.close_count += 1
            if close_error is not None:
                raise close_error
            self.connected = False

    class FakeToolkit:
        def __init__(self, **kwargs):
            events.append("toolkit")
            if toolkit_error is not None:
                raise toolkit_error
            captured["toolkit"] = kwargs
            captured["toolkit_instance"] = self
            assert kwargs["mcps"][0].connected is True

    class FakeAgent:
        def __init__(self, **kwargs):
            events.append("agent")
            captured["agent"] = kwargs

        async def reply(self, msg):
            events.append("reply")
            captured["message"] = msg
            if reply_error is not None:
                raise reply_error
            if reply is ...:
                return AssistantMsg(
                    name="BlenderAgent",
                    content=_valid_handoff("blender result"),
                )
            return reply

    class FakeReActConfig:
        def __init__(self, **kwargs):
            captured["react_config"] = kwargs

    def fake_build_model(provider, model_name, base_url, api_key):
        captured["model"] = (provider, model_name, base_url, api_key)
        return "model"

    real_user_msg = agent_extensions.UserMsg

    def fake_user_msg(**kwargs):
        captured["user_msg"] = kwargs
        return real_user_msg(**kwargs)

    monkeypatch.setattr(
        agent_extensions,
        "StdioMCPConfig",
        FakeStdioMCPConfig,
        raising=False,
    )
    monkeypatch.setattr(agent_extensions, "MCPClient", FakeMCPClient, raising=False)
    monkeypatch.setattr(agent_extensions, "Toolkit", FakeToolkit)
    monkeypatch.setattr(agent_extensions, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(agent_extensions, "ReActConfig", FakeReActConfig, raising=False)
    monkeypatch.setattr(agent_extensions, "_build_model", fake_build_model)
    monkeypatch.setattr(agent_extensions, "UserMsg", fake_user_msg)
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "http://model/v1")
    return events, captured


@pytest.mark.asyncio
async def test_blender_uses_agentscope2_stdio_mcp_agent_and_user_message(monkeypatch):
    monkeypatch.setenv("BLENDER_MCP_TIMEOUT_SECONDS", "27.5")
    events, captured = _install_blender_recording_fakes(monkeypatch)

    result = await AgentExtensionTools()._blender_model_async("build a fixture")

    assert result == _valid_handoff("blender result")
    assert captured["config"] == {
        "command": "uvx",
        "args": ["blender-mcp"],
    }
    assert captured["client"] == {
        "name": "blender_mcp",
        "is_stateful": True,
        "mcp_config": captured["config_instance"],
        "execution_timeout": 27.5,
    }
    assert events.index("connect") < events.index("toolkit")
    assert captured["toolkit"] == {"mcps": [captured["client_instance"]]}
    assert captured["agent"]["name"] == "BlenderAgent"
    assert captured["agent"]["model"] == "model"
    assert captured["agent"]["toolkit"] is captured["toolkit_instance"]
    assert captured["react_config"] == {"max_iters": 60}
    assert captured["model"] == (
        "openai",
        AgentExtensionTools()._llm_name,
        "http://model/v1",
        "secret",
    )
    assert captured["message"].name == "User"
    assert captured["message"].role == "user"
    assert captured["user_msg"] == {"name": "User", "content": "build a fixture"}
    assert events[-1] == "close"
    assert events.count("close") == 1


@pytest.mark.asyncio
async def test_blender_default_timeout_and_structured_prompt_contract(monkeypatch):
    monkeypatch.delenv("BLENDER_MCP_TIMEOUT_SECONDS", raising=False)
    _, captured = _install_blender_recording_fakes(monkeypatch)

    await AgentExtensionTools()._blender_model_async("task")

    assert captured["client"]["execution_timeout"] == 600.0
    prompt = captured["agent"]["system_prompt"]
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
    assert "Blender MCP" in prompt
    assert ".blend" in prompt
    assert "绝对路径" in prompt
    assert "创建、修改和删除的对象" in prompt
    assert "多个检查视角" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (None, "Blender Agent 未返回结果"),
        (AssistantMsg(name="BlenderAgent", content=""), "Blender Agent 未返回内容"),
    ],
)
async def test_blender_empty_results_use_fallback_and_close(monkeypatch, reply, expected):
    events, _ = _install_blender_recording_fakes(monkeypatch, reply=reply)

    result = await AgentExtensionTools()._blender_model_async("task")

    assert result.success is False
    assert expected in result
    assert events.count("close") == 1
    assert events[-1] == "close"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply_error",
    [RuntimeError("agent failed"), TimeoutError(), asyncio.CancelledError()],
)
async def test_blender_closes_once_and_propagates_reply_errors(monkeypatch, reply_error):
    events, _ = _install_blender_recording_fakes(
        monkeypatch,
        reply_error=reply_error,
    )

    with pytest.raises(type(reply_error)):
        await AgentExtensionTools()._blender_model_async("task")

    assert events.count("close") == 1
    assert events[-1] == "close"


@pytest.mark.asyncio
async def test_blender_connect_failure_does_not_close_invalid_client(monkeypatch):
    events, _ = _install_blender_recording_fakes(
        monkeypatch,
        connect_error=RuntimeError("offline"),
    )

    result = await AgentExtensionTools()._blender_model_async("task")

    assert "offline" in result
    assert "close" not in events


@pytest.mark.asyncio
async def test_blender_toolkit_error_closes_connected_client(monkeypatch):
    events, _ = _install_blender_recording_fakes(
        monkeypatch,
        toolkit_error=RuntimeError("toolkit failed"),
    )

    with pytest.raises(RuntimeError, match="toolkit failed"):
        await AgentExtensionTools()._blender_model_async("task")

    assert events.count("close") == 1
    assert events[-1] == "close"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primary_error",
    [RuntimeError("primary failure"), asyncio.CancelledError("cancelled")],
)
async def test_blender_cleanup_error_does_not_hide_primary_error(
    monkeypatch,
    primary_error,
):
    events, _ = _install_blender_recording_fakes(
        monkeypatch,
        reply_error=primary_error,
        close_error=ValueError("cleanup failure"),
    )

    with pytest.raises(type(primary_error), match=str(primary_error)):
        await AgentExtensionTools()._blender_model_async("task")

    assert events.count("close") == 1


def test_process_file_tools_write_and_read_complete_utf8_content(tmp_path):
    target = tmp_path / "工序100.json"
    content = '{\n  "工序": "反推堵盖",\n  "说明": "完整内容"\n}\n'

    write_file, view_file = agent_extensions._make_process_file_tools(tmp_path)
    write_response = write_file(target.name, content)
    absolute_path = str(target.resolve())

    assert isinstance(write_response, ToolChunk)
    assert write_response.state == ToolResultState.SUCCESS
    assert target.read_text(encoding="utf-8") == content
    write_result = write_response.content[0].text
    assert absolute_path in write_result
    assert content in write_result

    read_response = view_file(target.name)

    assert isinstance(read_response, ToolChunk)
    assert read_response.state == ToolResultState.SUCCESS
    read_result = read_response.content[0].text
    assert absolute_path in read_result
    assert content in read_result


@pytest.mark.asyncio
async def test_process_file_tools_keep_markdown_through_real_function_tool_and_toolkit(
    tmp_path,
):
    target = tmp_path / "工步1.json"
    content = '{\n  "stepName": "安装堵盖",\n  "detail": "完整工步内容"\n}\n'
    absolute_path = str(target.resolve())
    write_file, view_file = agent_extensions._make_process_file_tools(tmp_path)
    write_tool = RealFunctionTool(func=write_file)

    direct_chunk = await write_tool(file_path=target.name, content=content)

    assert isinstance(direct_chunk, ToolChunk)
    assert direct_chunk.state == ToolResultState.SUCCESS
    direct_text = direct_chunk.content[0].text
    assert direct_text.startswith("# 文件写入结果\n")
    assert absolute_path in direct_text
    assert content in direct_text
    assert "content=[TextBlock" not in direct_text

    toolkit = RealToolkit(
        tools=[RealFunctionTool(func=view_file)]
    )
    results = [
        result
        async for result in toolkit.call_tool(
            ToolCallBlock(
                id="read-process-file",
                name="view_text_file",
                input=agent_extensions.json.dumps(
                    {"file_path": target.name},
                    ensure_ascii=False,
                ),
            ),
            AgentState(),
        )
    ]

    final_response = results[-1]
    assert isinstance(final_response, ToolResponse)
    assert final_response.state == ToolResultState.SUCCESS
    response_text = final_response.content[0].text
    assert response_text.startswith("# 文件读取结果\n")
    assert absolute_path in response_text
    assert content in response_text
    assert "content=[TextBlock" not in response_text


@pytest.mark.asyncio
async def test_bound_process_function_tools_allow_basename_json_in_root(tmp_path):
    output_root = tmp_path / "output"
    write_file, view_file = agent_extensions._make_process_file_tools(output_root)
    content = '{"stepName": "安装堵盖"}'

    write_chunk = await RealFunctionTool(func=write_file)(
        file_path="工步1.json",
        content=content,
    )
    view_chunk = await RealFunctionTool(func=view_file)(
        file_path="工步1.json",
    )

    target = (output_root / "工步1.json").resolve()
    assert write_chunk.state is ToolResultState.SUCCESS
    assert view_chunk.state is ToolResultState.SUCCESS
    assert target.read_text(encoding="utf-8") == content
    assert str(target) in write_chunk.content[0].text
    assert content in view_chunk.content[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["write", "view"])
async def test_bound_process_function_tools_reject_outside_root_without_mutation(
    tmp_path,
    operation,
):
    output_root = tmp_path / "output"
    outside = tmp_path / "outside.json"
    outside.write_text("sentinel", encoding="utf-8")
    write_file, view_file = agent_extensions._make_process_file_tools(output_root)
    tool = RealFunctionTool(func=write_file if operation == "write" else view_file)
    kwargs = {"file_path": str(outside)}
    if operation == "write":
        kwargs["content"] = "overwritten"

    chunk = await tool(**kwargs)

    assert chunk.state is ToolResultState.ERROR
    assert "根目录中的文件名" in chunk.content[0].text
    assert outside.read_text(encoding="utf-8") == "sentinel"


@pytest.mark.asyncio
async def test_bound_process_function_tools_reject_nested_paths(tmp_path):
    output_root = tmp_path / "output"
    write_file, _ = agent_extensions._make_process_file_tools(output_root)

    chunk = await RealFunctionTool(func=write_file)(
        file_path="nested/工步1.json",
        content="{}",
    )

    assert chunk.state is ToolResultState.ERROR
    assert "根目录中的文件名" in chunk.content[0].text
    assert not (output_root / "nested" / "工步1.json").exists()


@pytest.mark.asyncio
async def test_bound_process_write_atomically_replaces_existing_hardlink(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("sentinel", encoding="utf-8")
    target = output_root / "工序100.json"
    os.link(outside, target)
    write_file, _ = agent_extensions._make_process_file_tools(output_root)

    chunk = await RealFunctionTool(func=write_file)(
        file_path=target.name,
        content='{"safe": true}',
    )

    assert chunk.state is ToolResultState.SUCCESS
    assert outside.read_text(encoding="utf-8") == "sentinel"
    assert target.read_text(encoding="utf-8") == '{"safe": true}'
    assert os.stat(outside).st_ino != os.stat(target).st_ino


@pytest.mark.asyncio
async def test_bound_process_write_replaces_existing_symlink_without_following(
    tmp_path,
):
    output_root = tmp_path / "output"
    output_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("sentinel", encoding="utf-8")
    target = output_root / "工序100.json"
    try:
        target.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    write_file, _ = agent_extensions._make_process_file_tools(output_root)

    chunk = await RealFunctionTool(func=write_file)(
        file_path=target.name,
        content='{"safe": true}',
    )

    assert chunk.state is ToolResultState.SUCCESS
    assert not target.is_symlink()
    assert outside.read_text(encoding="utf-8") == "sentinel"
    assert target.read_text(encoding="utf-8") == '{"safe": true}'


@pytest.mark.asyncio
async def test_bound_process_view_only_returns_artifacts_verified_this_run(tmp_path):
    output_root = tmp_path / "output"
    output_root.mkdir()
    preexisting = output_root / "secret.json"
    preexisting.write_text("host-secret", encoding="utf-8")
    _, view_file = agent_extensions._make_process_file_tools(output_root)

    chunk = await RealFunctionTool(func=view_file)(file_path=preexisting.name)

    assert chunk.state is ToolResultState.ERROR
    assert "本次运行写入并验证" in chunk.content[0].text
    assert "host-secret" not in chunk.content[0].text


@pytest.mark.asyncio
async def test_bound_process_write_swap_before_atomic_replace_cannot_escape(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "output"
    output_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("sentinel", encoding="utf-8")
    target = output_root / "工序100.json"
    write_file, _ = agent_extensions._make_process_file_tools(output_root)
    real_replace = os.replace
    swapped = threading.Event()

    def swap_then_replace(source, destination):
        os.link(outside, target)
        swapped.set()
        real_replace(source, destination)

    monkeypatch.setattr(agent_extensions.os, "replace", swap_then_replace)

    chunk = await RealFunctionTool(func=write_file)(
        file_path=target.name,
        content='{"safe": true}',
    )

    assert swapped.is_set()
    assert chunk.state is ToolResultState.SUCCESS
    assert outside.read_text(encoding="utf-8") == "sentinel"
    assert target.read_text(encoding="utf-8") == '{"safe": true}'


@pytest.mark.asyncio
async def test_bound_process_write_rejects_output_root_swap_before_temp_open(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "output"
    output_root.mkdir()
    held_root = tmp_path / "held-output"
    outside_root = tmp_path / "outside-root"
    outside_root.mkdir()
    probe = tmp_path / "symlink-probe"
    try:
        probe.symlink_to(outside_root, target_is_directory=True)
        probe.rmdir()
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    write_file, _ = agent_extensions._make_process_file_tools(output_root)
    real_mkstemp = agent_extensions.tempfile.mkstemp

    def swap_root_during_open(**kwargs):
        output_root.rename(held_root)
        output_root.symlink_to(outside_root, target_is_directory=True)
        try:
            return real_mkstemp(**kwargs)
        finally:
            output_root.rmdir()
            held_root.rename(output_root)

    monkeypatch.setattr(agent_extensions.tempfile, "mkstemp", swap_root_during_open)

    chunk = await RealFunctionTool(func=write_file)(
        file_path="工序100.json",
        content='{"must_not_escape": true}',
    )

    assert chunk.state is ToolResultState.ERROR
    assert list(outside_root.iterdir()) == []
    assert not (output_root / "工序100.json").exists()


@pytest.mark.asyncio
async def test_bound_process_write_rejects_output_root_swap_at_final_replace(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "output"
    output_root.mkdir()
    held_root = tmp_path / "held-output"
    replacement_root = tmp_path / "replacement-output"
    write_file, _ = agent_extensions._make_process_file_tools(output_root)
    real_replace = os.replace
    escaped_artifact = replacement_root / "process.json"

    def swap_root_at_final_replace(source, destination, *args, **kwargs):
        output_root.rename(held_root)
        replacement_root.mkdir()
        replacement_root.rename(output_root)
        real_replace(held_root / Path(source).name, output_root / Path(source).name)
        return real_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(agent_extensions.os, "replace", swap_root_at_final_replace)
    try:
        chunk = await RealFunctionTool(func=write_file)(
            file_path="process.json",
            content='{"must_not_escape": true}',
        )
    finally:
        close = getattr(write_file, "close", None)
        if close is not None:
            close()
        if output_root.exists() and held_root.exists():
            output_root.rename(replacement_root)
            held_root.rename(output_root)

    assert chunk.state is ToolResultState.ERROR
    assert not escaped_artifact.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tamper",
    ["delete", "replace", "modify", "rewrite_same", "hardlink"],
)
async def test_bound_process_view_rejects_post_write_tampering(tmp_path, tamper):
    output_root = tmp_path / "output"
    output_root.mkdir()
    target = output_root / "process.json"
    write_file, view_file = agent_extensions._make_process_file_tools(output_root)
    original = '{"safe": true}'
    write_chunk = await RealFunctionTool(func=write_file)(
        file_path=target.name,
        content=original,
    )
    assert write_chunk.state is ToolResultState.SUCCESS

    if tamper == "delete":
        target.unlink()
    elif tamper == "replace":
        replacement = tmp_path / "replacement.json"
        replacement.write_text('{"replaced": true}', encoding="utf-8")
        os.replace(replacement, target)
    elif tamper == "modify":
        target.write_text('{"modified": true}', encoding="utf-8")
    elif tamper == "rewrite_same":
        target.write_text(original, encoding="utf-8")
    else:
        outside = tmp_path / "outside.json"
        outside.write_text('{"linked": true}', encoding="utf-8")
        target.unlink()
        os.link(outside, target)

    try:
        view_chunk = await RealFunctionTool(func=view_file)(file_path=target.name)
    finally:
        close = getattr(write_file, "close", None)
        if close is not None:
            close()

    assert view_chunk.state is ToolResultState.ERROR
    assert original not in view_chunk.content[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "tool_input"),
    [
        (
            agent_extensions.write_text_file,
            {"file_path": "工序100.json", "content": "{}"},
        ),
        (
            agent_extensions.view_text_file,
            {"file_path": "工序100.json"},
        ),
    ],
)
async def test_process_file_tools_are_allowed_by_explicit_bypass_state(
    helper,
    tool_input,
):
    state = AgentState(permission_context={"mode": PermissionMode.BYPASS})
    tool = RealFunctionTool(func=helper)

    decision = await PermissionEngine(state.permission_context).check_permission(
        tool,
        tool_input,
    )

    assert state.permission_context.mode == PermissionMode.BYPASS
    assert decision.behavior == PermissionBehavior.ALLOW


def _install_process_recording_fakes(
    monkeypatch,
    *,
    reply=...,
    reply_error=None,
    file_calls=(),
    task_calls=("TaskCreate", "TaskGet", "TaskList", "TaskUpdate"),
    task_state="completed",
):
    captured = {"task_tools": [], "task_results": [], "file_results": []}

    def task_tool(name):
        class FakeTaskTool:
            def __init__(self, middlewares=None):
                self.name = name
                self._middlewares = list(middlewares or [])
                captured["task_tools"].append(self)

        return FakeTaskTool

    class FakeFunctionTool:
        def __init__(self, *, func):
            self.func = func
            self.name = func.__name__

    class FakeToolkit:
        def __init__(self, **kwargs):
            captured["toolkit"] = kwargs
            captured["toolkit_instance"] = self

    class FakeReActConfig:
        def __init__(self, **kwargs):
            captured["react_config"] = kwargs

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs

        async def reply(self, msg):
            captured["message"] = msg
            tools_by_name = {
                tool.name: tool for tool in captured["toolkit"]["tools"]
            }
            captured["agent"]["state"].tasks_context.tasks = [
                Task(
                    subject="write process artifact",
                    description="write and verify one process artifact",
                    metadata={},
                    state=task_state,
                ),
            ]
            for tool_name in task_calls:
                tool = tools_by_name[tool_name]

                async def next_handler(tool_name=tool_name, **kwargs):
                    yield ToolChunk(
                        content=[TextBlock(text=f"observed {tool_name}")],
                    )

                for middleware in tool._middlewares:
                    captured["task_results"].extend(
                        [
                            chunk
                            async for chunk in middleware.on_tool_call(
                                tool,
                                {
                                    "_agent_state": captured["agent"]["state"],
                                },
                                next_handler,
                            )
                        ],
                    )
            for tool_name, kwargs in file_calls:
                captured["file_results"].append(
                    tools_by_name[tool_name].func(**kwargs),
                )
            if reply_error is not None:
                raise reply_error
            if reply is ...:
                return AssistantMsg(
                    name="ProcessAgent",
                    content=(
                        "# 执行结果\n## 状态\n成功\n"
                        "## 完成摘要\n已完成。\n"
                        "## 生成文件\n无\n"
                        "## 具体结果\n模型未列出文件内容。\n"
                        "## 执行记录\n已调用工具。\n"
                        "## 警告与未完成项\n无"
                    ),
                )
            return reply

    def fake_build_model(provider, model_name, base_url, api_key):
        captured["model"] = (provider, model_name, base_url, api_key)
        return "process-model"

    real_user_msg = agent_extensions.UserMsg

    def fake_user_msg(**kwargs):
        captured["user_msg"] = kwargs
        return real_user_msg(**kwargs)

    monkeypatch.setattr(agent_extensions, "TaskCreate", task_tool("TaskCreate"), raising=False)
    monkeypatch.setattr(agent_extensions, "TaskGet", task_tool("TaskGet"), raising=False)
    monkeypatch.setattr(agent_extensions, "TaskList", task_tool("TaskList"), raising=False)
    monkeypatch.setattr(agent_extensions, "TaskUpdate", task_tool("TaskUpdate"), raising=False)
    monkeypatch.setattr(agent_extensions, "FunctionTool", FakeFunctionTool, raising=False)
    monkeypatch.setattr(agent_extensions, "Toolkit", FakeToolkit)
    monkeypatch.setattr(agent_extensions, "ReActConfig", FakeReActConfig, raising=False)
    monkeypatch.setattr(agent_extensions, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(agent_extensions, "_build_model", fake_build_model)
    monkeypatch.setattr(agent_extensions, "UserMsg", fake_user_msg)
    monkeypatch.setenv("VLM_API_KEY", "vlm-secret")
    monkeypatch.setenv("VLM_BASE_URL", "http://vlm/v1")
    return captured


@pytest.mark.asyncio
async def test_process_uses_agentscope2_task_file_tools_agent_and_user_message(
    monkeypatch,
):
    captured = _install_process_recording_fakes(monkeypatch)
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[{"id": 7}])
    tools._rerank_rag_candidates = AsyncMock(return_value=[{"id": 7}])
    rag_data = DataBlock(
        source=Base64Source(data="aW1hZ2U=", media_type="image/png")
    )
    tools._build_rag_content_blocks = MagicMock(
        return_value=[TextBlock(text="检索知识全文"), rag_data]
    )

    result = await tools._process_agent_async("编制堵盖工艺", None, "process", 5)

    assert "## 状态\n部分成功" in result
    assert "缺少实际成功文件工具结果" in result
    toolkit_tools = captured["toolkit"]["tools"]
    assert [tool.name for tool in toolkit_tools] == [
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskUpdate",
        "write_text_file",
        "view_text_file",
    ]
    assert [tool.func.__name__ for tool in toolkit_tools[-2:]] == [
        "write_text_file",
        "view_text_file",
    ]
    assert all(tool._middlewares for tool in captured["task_tools"])
    assert len({id(tool._middlewares[0]) for tool in captured["task_tools"]}) == 1
    assert captured["agent"]["name"] == "ProcessAgent"
    assert captured["agent"]["model"] == "process-model"
    assert captured["agent"]["toolkit"] is captured["toolkit_instance"]
    assert isinstance(captured["agent"]["state"], AgentState)
    assert (
        captured["agent"]["state"].permission_context.mode
        == PermissionMode.BYPASS
    )
    assert captured["react_config"] == {"max_iters": 60}
    assert captured["model"] == (
        "openai",
        tools._vlm_name,
        "http://vlm/v1",
        "vlm-secret",
    )
    message = captured["message"]
    assert message.name == "User"
    assert message.role == "user"
    assert rag_data in message.content
    assert "检索知识全文" in message.get_text_content()
    assert "编制堵盖工艺" in message.get_text_content()
    assert '"processID"' in message.get_text_content()
    assert '"stepID"' in message.get_text_content()


@pytest.mark.asyncio
async def test_process_handoff_normalizes_observed_file_path_and_content_into_sections(
    monkeypatch,
    tmp_path,
):
    output_root = tmp_path / "output"
    content = '{"processName": "反推堵盖"}'
    _install_process_recording_fakes(
        monkeypatch,
        file_calls=(
            (
                "write_text_file",
                {"file_path": "工序100.json", "content": content},
            ),
            ("view_text_file", {"file_path": "工序100.json"}),
        ),
    )
    monkeypatch.setenv("PROCESS_OUTPUT_ROOT", str(output_root))
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[])
    tools._rerank_rag_candidates = AsyncMock(return_value=[])

    result = await tools._process_agent_async("task", None, "process", 5)

    absolute_path = str((output_root / "工序100.json").resolve())
    generated_files = result.split("## 生成文件\n", 1)[1].split(
        "## 具体结果",
        1,
    )[0]
    details = result.split("## 具体结果\n", 1)[1].split("## 执行记录", 1)[0]
    assert absolute_path in generated_files
    assert content in details


@pytest.mark.asyncio
async def test_process_handoff_includes_recorded_file_error_and_marks_error(
    monkeypatch,
    tmp_path,
):
    output_root = tmp_path / "output"
    outside = tmp_path / "outside.json"
    outside.write_text("sentinel", encoding="utf-8")
    _install_process_recording_fakes(
        monkeypatch,
        file_calls=((
            "write_text_file",
            {"file_path": str(outside), "content": "overwritten"},
        ),),
    )
    monkeypatch.setenv("PROCESS_OUTPUT_ROOT", str(output_root))
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[])
    tools._rerank_rag_candidates = AsyncMock(return_value=[])

    result = await tools._process_agent_async("task", None, "process", 5)

    assert result.success is False
    assert "## 状态\n部分成功" in result
    assert "根目录中的文件名" in result
    assert outside.read_text(encoding="utf-8") == "sentinel"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (None, "工艺规划 Agent 未返回结果"),
        (AssistantMsg(name="ProcessAgent", content=""), "工艺规划 Agent 未返回结果"),
    ],
)
async def test_process_empty_reply_uses_safe_fallback(monkeypatch, reply, expected):
    _install_process_recording_fakes(monkeypatch, reply=reply)
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[])
    tools._rerank_rag_candidates = AsyncMock(return_value=[])

    result = await tools._process_agent_async("task", None, "process", 5)

    assert result.success is False
    assert expected in result


@pytest.mark.asyncio
async def test_process_reply_error_propagates(monkeypatch):
    _install_process_recording_fakes(
        monkeypatch,
        reply_error=RuntimeError("process agent failed"),
    )
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[])
    tools._rerank_rag_candidates = AsyncMock(return_value=[])

    result = await tools._process_agent_async("task", None, "process", 5)

    assert result.success is False
    assert "process agent failed" in result
    assert "TaskCreate" in result


@pytest.mark.asyncio
@pytest.mark.parametrize("task_state", ["pending", "in_progress"])
async def test_process_requires_authoritative_completed_task_state(
    monkeypatch,
    tmp_path,
    task_state,
):
    output_root = tmp_path / "output"
    content = '{"processName": "observed"}'
    _install_process_recording_fakes(
        monkeypatch,
        task_state=task_state,
        file_calls=(
            ("write_text_file", {"file_path": "process.json", "content": content}),
            ("view_text_file", {"file_path": "process.json"}),
        ),
    )
    monkeypatch.setenv("PROCESS_OUTPUT_ROOT", str(output_root))
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[])
    tools._rerank_rag_candidates = AsyncMock(return_value=[])

    result = await tools._process_agent_async("task", None, "process", 5)

    assert result.success is False
    assert task_state in result
    assert "TaskCreate" in result
    assert content in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "reply_error", "expected"),
    [
        (None, None, "Agent"),
        (..., RuntimeError("reply exploded"), "reply exploded"),
    ],
)
async def test_process_failure_after_observations_preserves_task_and_file_evidence(
    monkeypatch,
    tmp_path,
    reply,
    reply_error,
    expected,
):
    output_root = tmp_path / "output"
    content = '{"processName": "observed-before-failure"}'
    _install_process_recording_fakes(
        monkeypatch,
        reply=reply,
        reply_error=reply_error,
        file_calls=(
            ("write_text_file", {"file_path": "process.json", "content": content}),
            ("view_text_file", {"file_path": "process.json"}),
        ),
    )
    monkeypatch.setenv("PROCESS_OUTPUT_ROOT", str(output_root))
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[])
    tools._rerank_rag_candidates = AsyncMock(return_value=[])

    result = await tools._process_agent_async("task", None, "process", 5)

    assert result.success is False
    assert expected in result
    assert "TaskCreate" in result
    assert "write_text_file" in result
    assert "view_text_file" in result
    assert content in result


@pytest.mark.asyncio
async def test_process_closes_trusted_root_when_setup_fails(monkeypatch):
    close_root = MagicMock()

    def fake_make_file_tools(output_root, records):
        def write_text_file(file_path, content):
            return ToolChunk(content=[TextBlock(text="write")])

        def view_text_file(file_path):
            return ToolChunk(content=[TextBlock(text="view")])

        write_text_file.close = close_root
        view_text_file.close = close_root
        return write_text_file, view_text_file

    monkeypatch.setattr(
        agent_extensions,
        "_make_process_file_tools",
        fake_make_file_tools,
    )
    monkeypatch.setattr(
        agent_extensions,
        "Toolkit",
        MagicMock(side_effect=RuntimeError("toolkit setup failed")),
    )
    tools = AgentExtensionTools()
    tools._search_rag_candidates = AsyncMock(return_value=[])
    tools._rerank_rag_candidates = AsyncMock(return_value=[])

    with pytest.raises(RuntimeError, match="toolkit setup failed"):
        await tools._process_agent_async("task", None, "process", 5)

    close_root.assert_called_once_with()


def _subagent_prompt_source(agent_name: str) -> str:
    source = Path(agent_extensions.__file__).read_text(encoding="utf-8")
    runtime_name = {
        "unity_agent": "UnityAgent",
        "blender_agent": "BlenderAgent",
        "process_agent": "ProcessAgent",
        "comfyui_agent": "ComfyUIAgent",
    }.get(agent_name, agent_name)
    start = source.index(f'name="{runtime_name}"')
    model_constructor = (
        "model=_build_model("
        if agent_name in {
            "unity_agent",
            "blender_agent",
            "process_agent",
            "comfyui_agent",
        }
        else "model=OpenAIChatModel("
    )
    end = source.index(model_constructor, start)
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
    assert "完整工具结果" in prompt
    assert "Task 工具操作及其返回结果" in prompt


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
