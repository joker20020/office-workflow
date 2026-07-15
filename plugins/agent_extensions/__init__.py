# -*- coding: utf-8 -*-
"""
智能体扩展插件

严格按照 main.py 中的实现方式，为AI助手提供以下多智能体扩展能力：
- process_agent_tool: 工艺规划 — 查询RAG知识库 → 重排序 → AgentScope 任务工具生成工序工步文件
- unity_agent_tool: Unity AR — 通过MCP连接Unity编辑器，自动创建AR辅助装配程序
- blender_agent_tool: Blender建模 — 通过MCP连接Blender，完成三维建模任务
- comfyui_agent_tool: 图像生成 — AgentScope 2 Agent细化提示词后调用ComfyUI生成图像
"""

import asyncio
import base64
import hashlib
import json
import math
import os
from typing import Any, Dict, List

from src.core.permission_manager import Permission, PermissionSet
from src.core.plugin_base import PluginBase
from src.utils.logger import get_logger

try:
    from agentscope.credential import (
        DashScopeCredential,
        DeepSeekCredential,
        OpenAICredential,
    )
    from agentscope.agent import Agent, ReActConfig
    from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig
    from agentscope.message import (
        AssistantMsg,
        Base64Source,
        DataBlock,
        TextBlock,
        ToolResultState,
        UserMsg,
    )
    from agentscope.model import (
        DashScopeChatModel,
        DeepSeekChatModel,
        OpenAIChatModel,
    )
    from agentscope.permission import PermissionMode
    from agentscope.state import AgentState
    from agentscope.tool import (
        FunctionTool,
        TaskCreate,
        TaskGet,
        TaskList,
        TaskUpdate,
        Toolkit,
        ToolChunk,
        ToolResponse,
    )

    AGENTSCOPE_AVAILABLE = True
except ImportError:
    AGENTSCOPE_AVAILABLE = False

try:
    from pydantic.networks import AnyUrl
except ImportError:
    AnyUrl = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_logger = get_logger(__name__)

TOOL_GROUP_NAME = "agent_extensions"


def _make_response(content: str, success: bool = True) -> Any:
    if content is None:
        content = "(无返回结果)"
    return ToolResponse(
        content=[TextBlock(text=str(content))],
        state=ToolResultState.SUCCESS if success else ToolResultState.ERROR,
    )


def write_text_file(file_path: str, content: str) -> Any:
    """将完整 UTF-8 文本写入文件，并返回绝对路径与未截断内容。"""
    absolute_path = os.path.abspath(os.path.expanduser(file_path))
    parent_dir = os.path.dirname(absolute_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(absolute_path, "w", encoding="utf-8", newline="") as file_handle:
        file_handle.write(content)
    return ToolChunk(
        content=[
            TextBlock(
                text=(
                    "# 文件写入结果\n"
                    "## 状态\n成功\n"
                    f"## 绝对路径\n{absolute_path}\n"
                    "## 完整内容\n"
                    f"{content}"
                ),
            ),
        ],
        state=ToolResultState.SUCCESS,
    )


def view_text_file(file_path: str) -> Any:
    """读取 UTF-8 文本文件，并返回绝对路径与未截断完整内容。"""
    absolute_path = os.path.abspath(os.path.expanduser(file_path))
    with open(absolute_path, "r", encoding="utf-8") as file_handle:
        content = file_handle.read()
    return ToolChunk(
        content=[
            TextBlock(
                text=(
                    "# 文件读取结果\n"
                    "## 状态\n成功\n"
                    f"## 绝对路径\n{absolute_path}\n"
                    "## 完整内容\n"
                    f"{content}"
                ),
            ),
        ],
        state=ToolResultState.SUCCESS,
    )


def _message_text(msg: Any) -> str:
    if msg is None:
        return ""
    return msg.get_text_content() or ""


def _build_model(
    provider: str,
    model_name: str,
    base_url: str,
    api_key: str,
) -> Any:
    if provider == "openai":
        credential = OpenAICredential(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
        )
        return OpenAIChatModel(
            credential=credential,
            model=model_name or "gpt-4o",
            stream=True,
        )
    if provider == "deepseek":
        credential = DeepSeekCredential(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com",
        )
        return DeepSeekChatModel(
            credential=credential,
            model=model_name or "deepseek-chat",
            stream=True,
        )
    if provider == "dashscope":
        credential = DashScopeCredential(
            api_key=api_key,
            base_url=base_url or "https://api.dashscope.com",
        )
        return DashScopeChatModel(
            credential=credential,
            model=model_name or "qwen-turbo",
            stream=True,
        )
    raise ValueError(f"unsupported provider: {provider}")


def _get_timeout_seconds(name: str, default: float) -> float:
    """读取正数超时配置，无效值回退到默认值。"""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return float(default)
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = 0.0
    if not math.isfinite(value) or value <= 0:
        _logger.warning(
            "%s 必须为正数，当前值为 %r；使用默认值 %s 秒",
            name,
            raw_value,
            default,
        )
        return float(default)
    return value


def _run_async(coro):
    """在同步环境中运行异步协程（供tool函数使用）"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import threading
        result = [None, None]

        def _target():
            try:
                result[0] = asyncio.run(coro)
            except Exception as e:
                result[1] = e

        t = threading.Thread(target=_target)
        t.start()
        timeout = _get_timeout_seconds("AGENT_TOOL_TIMEOUT_SECONDS", 1800.0)
        t.join(timeout=timeout)
        if t.is_alive():
            return f"(执行超时：工具运行超过 {timeout:g} 秒)"
        if result[1]:
            raise result[1]
        if result[0] is None:
            return "(工具执行完成但无返回结果)"
        return result[0]
    else:
        return asyncio.run(coro)


class _APIRequester:
    """与 requester.py 中 APIRequester 完全一致的 HTTP 客户端"""

    def __init__(self, base_url="http://localhost:8050/api/v1",
                 data_dir="./data/",
                 workflow_path="./data/workflow/Flux-Dev-ComfyUI-Workflow.json"):
        self.base_url = base_url.rstrip("/")
        self.data_dir = data_dir
        import aiohttp

        if workflow_path and os.path.exists(workflow_path):
            with open(workflow_path, encoding="utf-8") as f:
                self.workflow = json.load(f)
        else:
            self.workflow = None

    @staticmethod
    def _image_content_type(path: str) -> str:
        extension = os.path.splitext(path)[1].lower()
        if extension == ".png":
            return "image/png"
        if extension in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if extension == ".webp":
            return "image/webp"
        return "application/octet-stream"

    @staticmethod
    async def _response_json(response, operation: str) -> Dict[str, Any]:
        if response.status < 200 or response.status >= 300:
            detail = await response.text()
            raise RuntimeError(f"{operation}失败: HTTP {response.status} - {detail}")
        return await response.json()

    @staticmethod
    async def _response_bytes(response, operation: str) -> bytes:
        if response.status < 200 or response.status >= 300:
            detail = await response.text()
            raise RuntimeError(f"{operation}失败: HTTP {response.status} - {detail}")
        return await response.read()

    @staticmethod
    def _search_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise RuntimeError("RAG 后端响应格式无效: results 必须为列表")
        return results

    @staticmethod
    def _collection_name(collection_name: str) -> str:
        from urllib.parse import quote

        return quote(collection_name, safe="")

    async def rag_create_collection(self, collection_name: str) -> Dict[str, Any]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/rag/collections",
                json={"collection_name": collection_name},
            ) as response:
                return await self._response_json(response, "创建 RAG 集合")

    async def rag_list_collections(self) -> Dict[str, Any]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/rag/collections") as response:
                return await self._response_json(response, "列出 RAG 集合")

    async def rag_delete_collection(self, collection_name: str) -> Dict[str, Any]:
        import aiohttp

        name = self._collection_name(collection_name)
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.base_url}/rag/collections/{name}"
            ) as response:
                return await self._response_json(response, "删除 RAG 集合")

    async def rag_add_text(
        self,
        collection_name: str,
        file_path: str,
        subject: str = None,
    ) -> Dict[str, Any]:
        import aiohttp

        if not os.path.isfile(file_path):
            raise FileNotFoundError(file_path)
        data = aiohttp.FormData()
        if subject is not None:
            data.add_field("subject", subject)
        name = self._collection_name(collection_name)
        with open(file_path, "rb") as file_handle:
            data.add_field(
                "file",
                file_handle,
                filename=os.path.basename(file_path),
                content_type="application/octet-stream",
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/rag/collections/{name}/text",
                    data=data,
                ) as response:
                    return await self._response_json(response, "添加 RAG 文本")

    async def rag_add_images(
        self,
        collection_name: str,
        image_paths: List[str],
        descriptions: List[str],
        subject: str = None,
    ) -> Dict[str, Any]:
        import aiohttp
        from contextlib import ExitStack

        if not image_paths or len(image_paths) != len(descriptions):
            raise ValueError("图片和描述数量必须一致且不能为空")
        missing = [path for path in image_paths if not os.path.isfile(path)]
        if missing:
            raise FileNotFoundError(missing[0])

        data = aiohttp.FormData()
        for description in descriptions:
            data.add_field("descriptions", description)
        if subject is not None:
            data.add_field("subject", subject)

        name = self._collection_name(collection_name)
        with ExitStack() as stack:
            for image_path in image_paths:
                image_file = stack.enter_context(open(image_path, "rb"))
                data.add_field(
                    "images",
                    image_file,
                    filename=os.path.basename(image_path),
                    content_type=self._image_content_type(image_path),
                )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/rag/collections/{name}/images",
                    data=data,
                ) as response:
                    return await self._response_json(response, "添加 RAG 图片")

    async def rag_search_text(
        self,
        collection_name: str,
        query: str,
        limit: int = 10,
        subject: str = None,
    ) -> List[Dict[str, Any]]:
        import aiohttp

        params = {"query": query, "limit": limit}
        if subject is not None:
            params["subject"] = subject
        name = self._collection_name(collection_name)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/rag/collections/{name}/search",
                params=params,
            ) as response:
                payload = await self._response_json(response, "RAG 文本检索")
        return self._search_results(payload)

    async def _rag_search_with_image(
        self,
        collection_name: str,
        image_path: str,
        limit: int,
        subject: str = None,
        query: str = None,
    ) -> List[Dict[str, Any]]:
        import aiohttp

        if not os.path.isfile(image_path):
            raise FileNotFoundError(image_path)
        data = aiohttp.FormData()
        if query is not None:
            data.add_field("query", query)
        data.add_field("limit", str(limit))
        if subject is not None:
            data.add_field("subject", subject)
        name = self._collection_name(collection_name)
        suffix = "/search/mixed" if query is not None else "/search"
        operation = "RAG 混合检索" if query is not None else "RAG 图片检索"
        with open(image_path, "rb") as image_file:
            data.add_field(
                "image",
                image_file,
                filename=os.path.basename(image_path),
                content_type=self._image_content_type(image_path),
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/rag/collections/{name}{suffix}",
                    data=data,
                ) as response:
                    payload = await self._response_json(response, operation)
        return self._search_results(payload)

    async def rag_search_image(
        self,
        collection_name: str,
        image_path: str,
        limit: int = 10,
        subject: str = None,
    ) -> List[Dict[str, Any]]:
        return await self._rag_search_with_image(
            collection_name=collection_name,
            image_path=image_path,
            limit=limit,
            subject=subject,
        )

    async def rag_search_mixed(
        self,
        collection_name: str,
        query: str,
        image_path: str,
        limit: int = 10,
        subject: str = None,
    ) -> List[Dict[str, Any]]:
        return await self._rag_search_with_image(
            collection_name=collection_name,
            query=query,
            image_path=image_path,
            limit=limit,
            subject=subject,
        )

    async def rag_list_entities(
        self,
        collection_name: str,
        offset: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        import aiohttp

        name = self._collection_name(collection_name)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/rag/collections/{name}/entities",
                params={"offset": offset, "limit": limit},
            ) as response:
                return await self._response_json(response, "浏览 RAG 实体")

    async def rag_delete_entity(
        self,
        collection_name: str,
        entity_id: int,
    ) -> Dict[str, Any]:
        import aiohttp

        name = self._collection_name(collection_name)
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.base_url}/rag/collections/{name}/entities/{entity_id}"
            ) as response:
                return await self._response_json(response, "删除 RAG 实体")

    async def rag_get_asset(
        self,
        collection_name: str,
        asset_path: str,
    ) -> bytes:
        import aiohttp
        from urllib.parse import quote

        name = self._collection_name(collection_name)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/rag/collections/{name}/asset",
                params={"path": asset_path},
            ) as response:
                if response.status != 404:
                    return await self._response_bytes(response, "获取 RAG 图片资源")

            filename = os.path.basename(asset_path.replace("\\", "/"))
            if not filename:
                raise FileNotFoundError(
                    f"RAG 图片资源不存在: {collection_name}/{asset_path}"
                )

            async with session.get(
                f"{self.base_url}/images/{quote(filename, safe='')}"
            ) as response:
                if response.status == 404:
                    raise FileNotFoundError(
                        f"RAG 图片资源不存在: {collection_name}/{asset_path}"
                    )
                return await self._response_bytes(
                    response,
                    "获取历史 RAG 图片资源",
                )

    async def query_embedding(self, text, embed_image_path=None):
        import aiohttp
        url = f"{self.base_url}/embed"
        if embed_image_path:
            with open(embed_image_path, "rb") as f:
                image = f.read()
        data = aiohttp.FormData()
        data.add_field("text", text or "")
        if embed_image_path:
            ext = embed_image_path.split(".")[-1]
            data.add_field("image", image, filename="embed_image.png",
                           content_type="image/png" if ext == "png" else "image/jpeg")
        else:
            data.add_field("image", b"", filename="embed_image.png", content_type="image/png")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise RuntimeError(f"嵌入请求失败: {response.status}")

    async def query_rerank(self, query_type, query_text, query_image_path,
                           doc_type, doc_text, doc_image_path):
        import aiohttp
        url = f"{self.base_url}/rerank"
        if query_image_path:
            with open(query_image_path, "rb") as f:
                query_image = f.read()
        if doc_image_path:
            with open(doc_image_path, "rb") as f:
                doc_image = f.read()
        data = aiohttp.FormData()
        data.add_field("query_type", query_type)
        if query_type == 'text':
            data.add_field("query_text", query_text if query_text else "")
        else:
            if query_image_path:
                ext = query_image_path.split(".")[-1]
                data.add_field("query_image", query_image, filename="query_image.png",
                               content_type="image/png" if ext == "png" else "image/jpeg")
        data.add_field("document_type", doc_type)
        if doc_type == 'text':
            data.add_field("document_text", doc_text if doc_text else "")
        else:
            if doc_image_path:
                ext = doc_image_path.split(".")[-1]
                data.add_field("document_image", doc_image, filename="doc_image.png",
                               content_type="image/png" if ext == "png" else "image/jpeg")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise RuntimeError(f"重排序请求失败: {response.status}")

    async def get_image(self, filename):
        import aiohttp
        url = f"{self.base_url}/images/{filename}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    img_dir = os.path.join(self.data_dir, "img")
                    os.makedirs(img_dir, exist_ok=True)
                    with open(os.path.join(img_dir, filename), "wb") as f:
                        f.write(image_data)
                    return image_data
                else:
                    raise RuntimeError(f"获取图片失败: {response.status}")

    async def text_to_image(self, prompt, output_name, negative_prompt="",
                            width=1024, height=1024, steps=20, seed=None,
                            cfg_scale=3.5, sampler_name="dpmpp_2m",
                            scheduler="simple",
                            checkpoint="flux1-dev.safetensors", loras=None):
        import aiohttp
        name_split = output_name.split(".")
        if name_split[-1] not in ["png", "jpg", "jpeg"]:
            name_split.append(".png")
            output_name = "".join(name_split)
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "checkpoint": checkpoint,
        }
        if self.workflow:
            payload["workflow"] = self.workflow
        if seed is not None:
            payload["seed"] = seed
        if loras:
            payload["loras"] = loras
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"{self.base_url}/text-to-image",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(
                        total=_get_timeout_seconds(
                            "IMAGE_REQUEST_TIMEOUT_SECONDS",
                            600.0,
                        ),
                    ),
            ) as response:
                if response.status == 200:
                    image_data = await response.read()
                    img_dir = os.path.join(self.data_dir, "img")
                    os.makedirs(img_dir, exist_ok=True)
                    with open(os.path.join(img_dir, output_name), "wb") as f:
                        f.write(image_data)
                    return True
                else:
                    error = await response.text()
                    _logger.error(f"文生图失败: {response.status} - {error}")
                    return False


# ============================================================
#  工具集
# ============================================================

class AgentExtensionTools:
    """智能体扩展工具集 — 严格对应 main.py 中的四个 agent_tool 函数"""

    def __init__(self):
        self._requester: _APIRequester = None
        self._llm_name = os.environ.get("LLM_MODEL_NAME", "deepseek-v4-pro")
        self._vlm_name = os.environ.get("VLM_MODEL_NAME", "qwen3-vl-plus")

    def _get_requester(self) -> _APIRequester:
        if self._requester is None:
            self._requester = _APIRequester(
                base_url=os.environ.get("RAG_BASE_URL", "http://localhost:8050/api/v1"),
                data_dir="./data/",
                workflow_path="./data/workflow/Flux-Dev-ComfyUI-Workflow.json",
            )
        return self._requester

    async def _search_rag_candidates(
        self,
        task: str,
        image_path: str,
        collection_name: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        requester = self._get_requester()
        if image_path:
            return await requester.rag_search_mixed(
                collection_name,
                task,
                image_path,
                limit=limit,
            )
        return await requester.rag_search_text(
            collection_name,
            task,
            limit=limit,
        )

    async def _cache_rag_asset(
        self,
        collection_name: str,
        asset_path: str,
    ) -> str:
        import hashlib
        import re

        requester = self._get_requester()
        image_data = await requester.rag_get_asset(collection_name, asset_path)
        basename = os.path.basename(asset_path.replace("\\", "/"))
        if not basename:
            raise RuntimeError(f"RAG 图片资源路径无效: {asset_path}")
        safe_basename = re.sub(
            r'[<>:"/\\|?*\x00-\x1f]',
            "_",
            basename,
        ).rstrip(" .")
        if not safe_basename:
            safe_basename = "asset"
        cache_key = f"{collection_name}\0{asset_path}"
        namespace = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:12]
        filename = f"{namespace}_{safe_basename}"
        image_dir = os.path.join(requester.data_dir, "img")
        os.makedirs(image_dir, exist_ok=True)
        local_path = os.path.join(image_dir, filename)
        with open(local_path, "wb") as file_handle:
            file_handle.write(image_data)
        return local_path

    async def _rerank_rag_candidates(
        self,
        task: str,
        collection_name: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        requester = self._get_requester()
        ranked = []
        for candidate in candidates:
            item = dict(candidate)
            rerank_kwargs = None
            if item.get("type") == "image":
                asset_path = item.get("asset_path") or item.get("path")
                if not asset_path:
                    item["_asset_error"] = "缺少可下载资源路径"
                    _logger.warning(
                        "RAG 图片候选缺少可下载资源路径，已仅保留文本描述: %s",
                        item.get("id"),
                    )
                else:
                    try:
                        image_path = await self._cache_rag_asset(
                            collection_name,
                            asset_path,
                        )
                    except FileNotFoundError as exc:
                        item["_asset_error"] = str(exc)
                        _logger.warning(
                            "RAG 图片下载失败，已仅保留文本描述: "
                            "collection=%s, id=%s, path=%s, error=%s",
                            collection_name,
                            item.get("id"),
                            asset_path,
                            exc,
                        )
                    else:
                        item["_local_asset_path"] = image_path
                        rerank_kwargs = {
                            "query_type": "text",
                            "query_text": task,
                            "query_image_path": None,
                            "doc_type": "image",
                            "doc_text": None,
                            "doc_image_path": image_path,
                        }
            elif item.get("type") == "text":
                rerank_kwargs = {
                    "query_type": "text",
                    "query_text": task,
                    "query_image_path": None,
                    "doc_type": "text",
                    "doc_text": item.get("text", ""),
                    "doc_image_path": None,
                }
            try:
                response = (
                    await requester.query_rerank(**rerank_kwargs)
                    if rerank_kwargs is not None
                    else None
                )
                if response is not None:
                    item["score"] = response["score"]
            except Exception as exc:
                _logger.warning(f"RAG 候选重排失败，保留原始分数: {exc}")
            ranked.append(item)
        return sorted(
            ranked,
            key=lambda item: item.get("score", 0.0),
            reverse=True,
        )

    def _build_rag_content_blocks(self, candidates, image_loader=None):
        if image_loader is None:
            def image_loader(path):
                with open(path, "rb") as image_file:
                    return image_file.read()

        blocks = []
        for index, candidate in enumerate(candidates):
            description = (
                f"{index + 1}.{candidate.get('text', '')}"
                f"(来源为{candidate.get('path', '')})\n"
            )
            blocks.append(TextBlock(text=description))
            if candidate.get("type") != "image":
                continue
            local_path = candidate.get("_local_asset_path")
            if not local_path:
                if not candidate.get("_asset_error"):
                    _logger.warning(
                        "RAG 图片候选缺少可用本地缓存，已仅保留文本描述: %s",
                        candidate.get("id"),
                    )
                continue
            image_data = image_loader(local_path)
            blocks.append(
                DataBlock(
                    source=Base64Source(
                        media_type=_APIRequester._image_content_type(local_path),
                        data=base64.b64encode(image_data).decode("utf-8"),
                    ),
                )
            )
        return blocks

    def get_all_tools(self) -> list:
        return [
            self.tool_unity_ar,
            self.tool_blender_model,
            self.tool_generate_process,
            self.tool_generate_image,
            self.tool_extract_json,
            self.tool_query_knowledge_base,
        ]

    # ==================== 1. Unity AR ====================

    def tool_unity_ar(self, task: str, info: str = "{}") -> Any:
        """根据提供的工序和工步信息生成Unity AR辅助装配程序。
        会自动完成：连接Unity MCP、获取实例、添加XR Rig、XR Simulator、主界面、工序组等。

        Args:
            task: 对Unity程序的需求，需要提供包含工序工步的详细描述
            info: 工序工步信息JSON字符串，格式为 {"工序名": ["工步1", "工步2"]}，默认为空

        Returns:
            Unity操作的执行结果
        """
        try:
            result = _run_async(self._unity_ar_async(task, info))
            return _make_response(result)
        except Exception as e:
            return _make_response(f"Unity操作失败: {e}", success=False)

    async def _unity_ar_async(self, task: str, info: str) -> str:
        if not AGENTSCOPE_AVAILABLE:
            return "AgentScope 未安装，无法使用 Unity MCP 功能"

        unity_timeout = _get_timeout_seconds("UNITY_MCP_TIMEOUT_SECONDS", 600.0)
        unity_config = HttpMCPConfig(
            url="http://localhost:8080/mcp",
            timeout=unity_timeout,
        )
        unity_mcp = MCPClient(
            name="unity_mcp",
            is_stateful=True,
            mcp_config=unity_config,
            execution_timeout=unity_timeout,
        )

        connected = False
        primary_error = None
        try:
            try:
                await unity_mcp.connect()
            except Exception as e:
                return f"无法连接 Unity MCP 服务(请确保 Unity 编辑器已启动且 MCP 服务运行中): {e}"
            connected = True
            return await self._unity_ar_connected(unity_mcp, task, info)
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            if connected:
                try:
                    await unity_mcp.close()
                except BaseException as cleanup_error:
                    if primary_error is None:
                        raise
                    _logger.warning(
                        "Unity MCP cleanup failed while propagating %s: %s",
                        type(primary_error).__name__,
                        cleanup_error,
                    )

    async def _unity_ar_connected(self, unity_mcp: Any, task: str, info: str) -> str:
        # AgentScope 2.0.4 does not yet publish resource operations on MCPClient.
        # Its connected ClientSession is the only API capable of preserving the
        # Unity instance-selection and custom-tool metadata protocol.
        session = getattr(unity_mcp, "_session", None)
        if session is None:
            raise RuntimeError("Unity MCP connected without an accessible session")

        # 激活当前 unity editor instance
        instances_response = await session.read_resource(AnyUrl("mcpforunity://instances"))
        instances = json.loads(instances_response.contents[0].text)["instances"]
        if not instances:
            return "未找到运行中的 Unity 编辑器实例"
        instance_hash = instances[0]["hash"]
        _logger.info(f"Unity instance hash: {instance_hash}")
        await session.call_tool("set_active_instance", {"instance": instance_hash})

        custom_tools_response = await session.read_resource(AnyUrl("mcpforunity://custom-tools"))
        custom_tools = json.loads(custom_tools_response.contents[0].text)["data"]["tools"]

        useful_tools = ["addXRRig", "addXRSimulator", "addMainCanvas", "addProcess"]
        custom_tools = [tool for tool in custom_tools if tool["name"] in useful_tools]
        _logger.info(f"Unity custom tools: {custom_tools}")

        toolkit = Toolkit(mcps=[unity_mcp])

        info_dict = json.loads(info) if isinstance(info, str) else info

        unity_agent = Agent(
            name="UnityAgent",
            system_prompt=f"""
        你是顶尖的一个Unity AR程序开发助手,你的任务是使用工具直接帮助用户完成AR程序的开发，你可以使用的custom tools 包括{custom_tools},
        当你使用custom tools中的工具时，不要直接使用，必须通过调用execute_custom_tool工具来使用，execute_custom_tool工具的使用格式如下：
        {{
            "type": "tool_use",
            "name": "execute_custom_tool",
            "input": {{
                "tool_name": "自定义工具名",
                "parameters": {{ 自定义工具参数字典，注意需要传入字典，而不是字符串 }}
            }}
        }}
        一个常用的AR应用初始化流程如下，请直接使用工具一步一步执行并检查每一步的执行结果：
        1.检查场景中是否有XR Rig对象，若不存在则使用自定义工具向场景中添加一个XR Rig对象
        2.检查场景中是否有XR Simulator对象，若不存在则添加一个XR Simulator对象使用户可以在编辑器中模拟XR操作
        3.检查场景中是否有MainCanvas，若不存在则添加一个主界面
        4.根据工序工步信息向主界面中添加工序组
        5.在unity中运行AR程序

        完成工具调用后，最终答复必须使用以下 Markdown 结构，章节不得缺失：
        # 执行结果
        ## 状态
        只能填写：成功、部分成功或失败。
        ## 完成摘要
        只总结已经通过工具实际完成的工作，不得把计划、建议或尝试写成已完成。
        ## 生成文件
        逐项列出 Unity 工程、场景、脚本、资源、构建产物等文件的类型、路径、用途和验证状态。
        路径应优先使用工具返回的绝对路径；工具未返回路径时必须写“路径未提供”，不得猜测。
        没有生成文件时必须明确写“无”。
        ## 具体结果
        列出创建或修改的场景、GameObject、组件、脚本、资源和 AR 流程，并说明关键配置。
        ## 执行记录
        列出实际调用的 MCP/custom tool、关键参数和返回结果，明确区分已执行操作与建议操作。
        ## 警告与未完成项
        没有问题时写“无”；否则列出失败、缺失或未经验证的内容及原因。
        """,
            model=_build_model(
                "openai",
                self._llm_name,
                os.environ["LLM_BASE_URL"],
                os.environ["LLM_API_KEY"],
            ),
            toolkit=toolkit,
            react_config=ReActConfig(max_iters=60),
        )

        msg = UserMsg(
            name="User",
            content=f"请完成以下任务：{task}，可用的工艺信息为：{info_dict}",
        )

        msg_res = await unity_agent.reply(msg)

        if msg_res is None:
            return "Unity Agent 未返回结果"
        return _message_text(msg_res) or "Unity Agent 未返回内容"

    # ==================== 2. Blender 建模 ====================

    def tool_blender_model(self, task: str) -> Any:
        """根据需求完成Blender建模

        Args:
            task: 对Blender模型的需求描述

        Returns:
            Blender操作的执行结果
        """
        try:
            result = _run_async(self._blender_model_async(task))
            return _make_response(result)
        except Exception as e:
            return _make_response(f"Blender操作失败: {e}", success=False)

    async def _blender_model_async(self, task: str) -> str:
        if not AGENTSCOPE_AVAILABLE:
            return "AgentScope 未安装，无法使用 Blender MCP 功能"

        blender_timeout = _get_timeout_seconds(
            "BLENDER_MCP_TIMEOUT_SECONDS",
            600.0,
        )
        blender_config = StdioMCPConfig(
            command="uvx",
            args=["blender-mcp"],
        )
        blender_mcp = MCPClient(
            name="blender_mcp",
            is_stateful=True,
            mcp_config=blender_config,
            execution_timeout=blender_timeout,
        )

        connected = False
        primary_error = None
        try:
            try:
                await blender_mcp.connect()
            except Exception as e:
                return f"无法连接 Blender MCP 服务(请确保 Blender 已启动且插件已安装): {e}"
            connected = True
            return await self._blender_model_connected(blender_mcp, task)
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            if connected:
                try:
                    await blender_mcp.close()
                except BaseException as cleanup_error:
                    if primary_error is None:
                        raise
                    _logger.warning(
                        "Blender MCP cleanup failed while propagating %s: %s",
                        type(primary_error).__name__,
                        cleanup_error,
                    )

    async def _blender_model_connected(self, blender_mcp: Any, task: str) -> str:
        toolkit = Toolkit(mcps=[blender_mcp])

        blender_agent = Agent(
            name="BlenderAgent",
            system_prompt=f"""你是一个blender建模助手,你的任务是帮助用户在blender应用中完成三维建模,注意完成建模后从多个视图进行检查。

        完成工具调用后，最终答复必须使用以下 Markdown 结构，章节不得缺失：
        # 执行结果
        ## 状态
        只能填写：成功、部分成功或失败。
        ## 完成摘要
        只总结已经通过工具实际完成的工作，不得把计划、建议或尝试写成已完成。
        ## 生成文件
        逐项列出 .blend 工程、导出模型、材质、贴图和渲染图的类型、路径、用途和验证状态。
        路径应优先使用工具返回的绝对路径；工具未返回路径时必须写“路径未提供”，不得猜测。
        未执行保存或导出时必须明确说明；没有生成文件时必须明确写“无”。
        ## 具体结果
        列出创建、修改和删除的对象，以及关键尺寸、材质、层级关系和多个检查视角的结果。
        ## 执行记录
        列出实际调用的 Blender MCP 工具、关键参数和返回结果，明确区分已执行操作与建议操作。
        ## 警告与未完成项
        没有问题时写“无”；否则列出失败、缺失或未经验证的内容及原因。
        """,
            model=_build_model(
                "openai",
                self._llm_name,
                os.environ["LLM_BASE_URL"],
                os.environ["LLM_API_KEY"],
            ),
            toolkit=toolkit,
            react_config=ReActConfig(max_iters=60),
        )

        msg = UserMsg(name="User", content=task)
        msg_res = await blender_agent.reply(msg)

        if msg_res is None:
            return "Blender Agent 未返回结果"
        return _message_text(msg_res) or "Blender Agent 未返回内容"

    # ==================== 3. 工艺规划 ====================

    def tool_generate_process(
        self,
        task: str,
        image_path: str = "",
        collection_name: str = "process",
        limit: int = 5,
    ) -> Any:
        """根据任务要求，查询向量数据库，rerank重排序后，由工艺规划Agent生成完整的工序工步文件。
        Agent会使用 Task 工具制定并跟踪计划，并使用 write_text_file 工具将工序工步写入JSON文件。

        Args:
            task: 任务要求（如"创建一份反推堵盖的安装工艺文件"）
            image_path: 参考图像路径(可选)
            collection_name: 向量数据库名称
            limit: 查询向量条数

        Returns:
            工艺规划的执行结果
        """
        try:
            result = _run_async(
                self._process_agent_async(task, image_path or None, collection_name, limit)
            )
            return _make_response(result)
        except Exception as e:
            return _make_response(f"工艺规划失败: {e}", success=False)

    async def _process_agent_async(
        self,
        task: str,
        image_path: str,
        collection_name: str,
        limit: int = 5,
    ) -> str:
        """
        通过 ProcessGen RAG 后端检索候选，重排后构建完整 prompt，
        再由带 Task 工具的 AgentScope 2 Agent 执行工艺规划。
        """
        if not AGENTSCOPE_AVAILABLE:
            return "AgentScope 未安装，无法使用工艺规划功能"

        candidates = await self._search_rag_candidates(
            task,
            image_path,
            collection_name,
            limit,
        )
        query_res = (
            await self._rerank_rag_candidates(task, collection_name, candidates)
        )[:limit]

        # ---- 构建知识库结果消息 ----
        query_content_list = self._build_rag_content_blocks(query_res)

        # ---- 4. 构建完整prompt（知识库结果 + 用户问题 + 工序/工步JSON模板） ----
        msg = UserMsg(
            name="User",
            content=[TextBlock(text="知识库中搜索有如下结果\n")] +
                    query_content_list +
                    [
                        TextBlock(
                                  text=f"用户的问题是:{task}, 请你根据知识库结果回答用户的问题，在你回答用户问题时，需要过滤掉搜索中无关的项"),
                        TextBlock(text="对于装配工序请使用以下json格式模板进行回答：\n"),
                        TextBlock(text="""
                               {
                                    "info":{
                                        "processID":"工序号",
                                        "processName":"工序名称",
                                        "processCharacteristic":"工序特征",
                                        "processType":"工序类型枚举:assemble/measure/postprocess",
                                        "note":"工序备注"
                                    },
                                    "steps":{
                                        "工步名称":"工步文件路径.json"
                                    },
                                    "processResources":[
                                        {
                                            "resourceName":"工艺资源名称",
                                            "resourceID":"工艺资源号",
                                            "specification":"工艺资源规格",
                                            "resourceType":"工艺资源类型枚举:tool/people",
                                            "model":"工艺资源模型路径.step"
                                        }
                                    ],
                                    "parts":[
                                        {
                                            "partID":"装配件代号",
                                            "partName":"装配件名称",
                                            "partNum":1,
                                            "action":"装配动作",
                                            "model":"装配件模型路径.step"
                                        }
                                    ]
                                }
                               """),
                        TextBlock(text="对于装配工步请使用以下json格式模板进行回答：\n"),
                        TextBlock(text="""
                               {
                                    "info":{
                                        "stepID":"工步号",
                                        "stepName":"工步名称"
                                    },
                                    "stepContent":[
                                        {
                                            "title":"工步基本内容标题",
                                            "detail":"工步基本内容细节1"
                                        },
                                        {
                                            "title":"测量工步内容标题",
                                            "detail": "测量工步内容细节",
                                            "target":"测量指标",
                                            "inspection_method":"检验方式",
                                            "measure_method":"测量方法",
                                            "times":1,
                                            "resource_name":"资源名称",
                                            "resource_id":"资源代号",
                                            "resource_specification":"资源规格",
                                            "digital":false
                                        }
                                    ],
                                    "annex":"工步附件路径.*",
                                    "animation":"工步装配动画"
                                }
                               """),
                    ],
        )

        # ---- 5. 创建带任务与文件工具的 AgentScope 2 工艺规划 Agent ----
        toolkit = Toolkit(
            tools=[
                TaskCreate(),
                TaskGet(),
                TaskList(),
                TaskUpdate(),
                FunctionTool(func=write_text_file),
                FunctionTool(func=view_text_file),
            ],
        )
        process_state = AgentState(
            permission_context={"mode": PermissionMode.BYPASS},
        )

        process_agent = Agent(
            name="ProcessAgent",
            system_prompt=f"""
        你是一个工艺规划师,你的任务是根据查询到的知识帮助用户进行工艺规划
        在你进行规划前，请先制定一个工艺规划计划。必须使用 TaskCreate 创建完整的工艺编写任务列表，使用 TaskList 和 TaskGet 检查任务，使用 TaskUpdate 标记进行中与已完成，并逐步执行直至全部任务完成才能结束规划。
        每当你完成一个工序或工步文件编写后请按照json模板输出将其完整写入当前文件夹下的文件内进行保存，注意输出文件结构的可读性
        同时你需要编写完成所有规划任务后再结束，请确保所有工序工步均保存，不能提前退出

        每个文件写入后必须调用 view_text_file 重新读取并核对，确认 JSON 完整且工序与工步关系一致。
        最终答复必须包含所有 TaskCreate、TaskGet、TaskList、TaskUpdate 的实际任务状态和工具返回结果，以及 write_text_file、view_text_file 的完整工具结果；不得把未执行的计划描述为已完成。
        完成工具调用后，最终答复必须使用以下 Markdown 结构，章节不得缺失：
        # 执行结果
        ## 状态
        只能填写：成功、部分成功或失败。
        ## 完成摘要
        只总结已经通过工具实际完成的工作，不得把计划、建议或尝试写成已完成。
        ## 生成文件
        逐项列出全部工序和工步 JSON 文件的类型、路径、用途和验证状态。
        路径应优先使用工具返回的绝对路径；工具未返回路径时必须写“路径未提供”，不得猜测。
        没有生成文件时必须明确写“无”。
        ## 具体结果
        按文件分别给出完整 JSON 内容，每个文件都使用带 json 语言标识的 Markdown 代码块，不得省略、截断或只给摘要。
        同时说明实际采用的检索知识、工艺决策依据和仍存在的不确定信息。
        ## 执行记录
        列出全部 Task 工具操作及其返回结果、检索知识、文件写入与 view_text_file 复核结果。
        ## 警告与未完成项
        没有问题时写“无”；否则列出失败、缺失或未经验证的内容及原因；中间文件仍须列出。
        """,
            model=_build_model(
                "openai",
                self._vlm_name,
                os.environ["VLM_BASE_URL"],
                os.environ["VLM_API_KEY"],
            ),
            toolkit=toolkit,
            state=process_state,
            react_config=ReActConfig(max_iters=60),
        )

        # ---- 6. 执行 ----
        msg_res = await process_agent.reply(msg)
        return _message_text(msg_res) or "工艺规划 Agent 未返回结果"

    # ==================== 4. ComfyUI 图像生成 ====================

    def tool_generate_image(self, task: str) -> Any:
        """根据需求生成图片资源。Agent会自动细化提示词后调用ComfyUI API生成图像。
        图像默认为2维工程图风格，以指示为主。

        Args:
            task: 对图片资源的需求描述

        Returns:
            图像生成结果
        """
        try:
            result = _run_async(self._comfyui_agent_async(task))
            return _make_response(result)
        except Exception as e:
            return _make_response(f"图像生成失败: {e}", success=False)

    async def _comfyui_agent_async(self, task: str) -> str:
        """Refine a prompt with AgentScope 2 and generate one verified image."""

        def format_result(
            status: str,
            summary: str,
            files: str,
            details: str,
            record: str,
            warnings: str,
        ) -> str:
            return (
                "# 执行结果\n"
                f"## 状态\n{status}\n"
                f"## 完成摘要\n{summary}\n"
                f"## 生成文件\n{files}\n"
                f"## 具体结果\n{details}\n"
                f"## 执行记录\n{record}\n"
                f"## 警告与未完成项\n{warnings}"
            )

        if not AGENTSCOPE_AVAILABLE:
            return format_result(
                "失败",
                "未生成图片。",
                "无",
                "AgentScope 未安装，无法细化正向提示词。",
                "未调用图像 API。",
                "AgentScope 未安装。",
            )

        toolkit = Toolkit(tools=[])
        comfyui_agent = Agent(
            name="ComfyUIAgent",
            system_prompt="""
        你是一个 AI 图片提示词优化助手。根据用户描述，返回一段可直接用于图像模型的正向提示词，不要调用工具，也不要输出 Markdown。
        提示词必须体现二维工程图、清晰装配指示、必要技术细节，并尽量避免人物元素。
        调用方会根据实际 API 返回和文件校验生成最终交接；最终交接必须包含以下 Markdown 结构，章节不得缺失：
        # 执行结果
        ## 状态
        只有图像 API 工具明确返回成功且预期本地文件存在时才能填写成功。
        ## 完成摘要
        只总结实际完成的图像生成工作。
        ## 生成文件
        每张图片必须列出经过验证的绝对路径；路径未提供时不得猜测。
        ## 具体结果
        必须列出实际使用的提示词、负向提示词、尺寸、步数、种子和 API 结果。
        ## 执行记录
        必须列出图像 API 调用参数和验证结果。
        ## 警告与未完成项
        必须列出失败、缺失或未经验证的内容；没有问题时写“无”。
        """,
            model=_build_model(
                "openai",
                self._llm_name,
                os.environ["LLM_BASE_URL"],
                os.environ["LLM_API_KEY"],
            ),
            toolkit=toolkit,
            react_config=ReActConfig(max_iters=60),
        )

        try:
            msg_res = await comfyui_agent.reply(
                UserMsg(name="User", content=task)
            )
        except Exception as exc:
            return format_result(
                "失败",
                "提示词细化失败，未生成图片。",
                "无",
                f"ComfyUI Agent 异常：{exc}",
                "未调用图像 API。",
                f"提示词细化异常：{exc}",
            )

        positive_prompt = _message_text(msg_res).strip()
        if not positive_prompt:
            reason = "ComfyUI Agent 未返回结果" if msg_res is None else "ComfyUI Agent 返回内容为空"
            return format_result(
                "失败",
                "未获得可用正向提示词，未生成图片。",
                "无",
                reason,
                "未调用图像 API。",
                reason,
            )

        negative_prompt = (
            "people, person, portrait, photorealistic, watermark, signature"
        )
        width = 1024
        height = 1024
        steps = 20
        seed = None
        prompt_hash = hashlib.sha256(
            positive_prompt.encode("utf-8")
        ).hexdigest()[:16]
        output_name = f"comfyui-{prompt_hash}.png"
        requester = self._get_requester()
        output_path = os.path.abspath(
            os.path.join(requester.data_dir, "img", output_name)
        )

        api_result = None
        api_error = None
        try:
            api_result = await requester.text_to_image(
                positive_prompt,
                output_name,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                seed=seed,
            )
        except Exception as exc:
            api_error = exc

        file_exists = os.path.isfile(output_path)
        succeeded = api_result is True and file_exists
        api_text = f"异常：{api_error}" if api_error else str(api_result)
        details = (
            f"- 实际正向提示词：{positive_prompt}\n"
            f"- 实际负向提示词：{negative_prompt}\n"
            f"- 尺寸：{width}x{height}\n"
            f"- 步数：{steps}\n"
            f"- 种子：{'未提供' if seed is None else seed}\n"
            f"- 输出名称：{output_name}\n"
            f"- 预期绝对路径：{output_path}\n"
            f"- API 返回：{api_text}\n"
            f"- 本地文件存在：{file_exists}"
        )
        record = (
            "1. AgentScope 2 Agent 已细化用户请求。\n"
            f"2. 调用 text_to_image，尺寸 {width}x{height}，步数 {steps}，"
            f"种子 {'未提供' if seed is None else seed}。\n"
            f"3. API 返回：{api_text}；文件校验：{file_exists}。"
        )
        if succeeded:
            return format_result(
                "成功",
                "图像 API 返回成功，且生成文件已在本地验证存在。",
                f"- PNG 图像：{output_path}（已验证）",
                details,
                record,
                "无",
            )

        if api_error:
            warning = f"图像 API 异常：{api_error}"
        elif api_result is True:
            warning = f"图像 API 返回成功，但预期文件不存在：{output_path}"
        else:
            warning = f"图像 API 返回：{api_result}"
        return format_result(
            "失败",
            "图像生成未通过 API 与本地文件双重验证。",
            "无",
            details,
            record,
            warning,
        )

    # ==================== 5. 提取JSON ====================

    def tool_extract_json(self, text: str) -> Any:
        """从混合文本中提取JSON对象

        Args:
            text: 包含JSON的混合文本

        Returns:
            提取到的JSON内容
        """
        group = []
        result_parts = []
        bracket_count = 0
        for ch in text:
            if ch == "{":
                bracket_count += 1
            elif ch == "}":
                bracket_count -= 1
            if bracket_count > 0:
                group.append(ch)
            elif bracket_count == 0 and ch == "}":
                group.append(ch)
                result_parts.append("".join(group))
                group = []
        combined = "".join(result_parts)
        if combined:
            try:
                parsed = json.loads(combined)
                return _make_response(json.dumps(parsed, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                return _make_response(combined)
        return _make_response("未找到JSON内容")

    # ==================== 6. 查询知识库 ====================

    def tool_query_knowledge_base(
        self,
        query: str,
        collection_name: str = "process",
        limit: int = 5,
        image_path: str = "",
    ) -> Any:
        """查询 RAG 知识库获取相关文档（仅查询，不生成）。

        提供图片时执行文本与图片混合检索，否则执行文本检索。

        Args:
            query: 查询文本
            collection_name: 集合名称
            limit: 返回条数
            image_path: 查询图片路径（可选）

        Returns:
            搜索结果列表
        """
        try:
            result = _run_async(
                self._query_knowledge_base_async(
                    query,
                    collection_name,
                    limit,
                    image_path or None,
                )
            )
            return _make_response(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            return _make_response(f"知识库查询失败: {e}", success=False)

    async def _query_knowledge_base_async(
        self,
        query: str,
        collection_name: str,
        limit: int,
        image_path: str = None,
    ) -> List[Dict]:
        requester = self._get_requester()
        if image_path:
            search_results = await requester.rag_search_mixed(
                collection_name,
                query,
                image_path,
                limit=limit,
            )
        else:
            search_results = await requester.rag_search_text(
                collection_name,
                query,
                limit=limit,
            )

        results = []
        for item in search_results:
            results.append({
                "id": item.get("id"),
                "score": round(item.get("score", 0.0), 4),
                "text": item.get("text", "")[:500],
                "path": item.get("path", ""),
                "type": item.get("type", ""),
                "subject": item.get("subject", ""),
                "asset_path": item.get("asset_path"),
            })
        return results


# ============================================================
#  插件类
# ============================================================

class AgentExtensionsPlugin(PluginBase):
    """智能体扩展插件"""

    name = "agent_extensions"
    version = "1.0.0"
    description = "为AI助手提供多智能体扩展能力（工艺规划、Unity AR、Blender建模、图像生成等）"
    author = "OfficeTools"

    permissions = PermissionSet.from_list([Permission.AGENT_TOOL, Permission.NETWORK])

    def __init__(self):
        super().__init__()
        self._tools: AgentExtensionTools = None

    def on_enable(self, context) -> None:
        self._tools = AgentExtensionTools()
        tools = self._tools.get_all_tools()
        context.tool_registry.register(TOOL_GROUP_NAME, tools)
        _logger.info(f"AgentExtensionsPlugin 已启用，注册了 {len(tools)} 个工具")

    def on_disable(self, context=None) -> None:
        if context is not None:
            context.tool_registry.unregister(TOOL_GROUP_NAME)
        self._tools = None
        _logger.info("AgentExtensionsPlugin 已禁用")


# 插件元数据（供 PluginManager 发现）
plugin_class = AgentExtensionsPlugin
