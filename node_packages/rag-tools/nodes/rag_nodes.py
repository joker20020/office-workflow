# -*- coding: utf-8 -*-
"""
RAG 检索增强节点定义

提供：
- rag.query_embedding: 查询向量嵌入
- rag.vector_search: 向量数据库搜索
- rag.rerank: 重排序
"""

import asyncio
import json
from typing import Any, Dict, List

import aiohttp

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.utils.logger import get_logger

_logger = get_logger(__name__)


def _run_async(coro):
    """在同步环境中运行异步协程"""
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
        t.join(timeout=120)
        if result[1]:
            raise result[1]
        return result[0]
    else:
        return asyncio.run(coro)


# ==================== 1. 查询向量嵌入 ====================


async def _query_embedding_async(
    text: str,
    image_path: str = "",
    base_url: str = "http://localhost:8000/api/v1",
) -> Dict[str, Any]:
    url = f"{base_url}/embed"
    data = aiohttp.FormData()
    data.add_field("text", text or "")

    if image_path:
        import os
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                image = f.read()
            ext = image_path.split(".")[-1]
            content_type = "image/png" if ext == "png" else "image/jpeg"
            data.add_field("image", image, filename=f"image.{ext}", content_type=content_type)
        else:
            data.add_field("image", b"", filename="image.png", content_type="image/png")
    else:
        data.add_field("image", b"", filename="image.png", content_type="image/png")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            if response.status == 200:
                result = await response.json()
                return {"vector": result["vector"], "dimension": result["dimension"], "success": True}
            else:
                error = await response.text()
                return {"vector": [], "dimension": 0, "success": False, "error": f"HTTP {response.status}: {error}"}


def _execute_query_embedding(
    text: str,
    image_path: str = "",
    base_url: str = "http://localhost:8000/api/v1",
) -> Dict[str, Any]:
    result = _run_async(_query_embedding_async(text, image_path, base_url))
    if result.get("success"):
        return {"vector": json.dumps(result["vector"][:8]), "dimension": result["dimension"]}
    return {"vector": f"错误: {result.get('error', '未知')}", "dimension": 0}


rag_query_embedding = NodeDefinition(
    node_type="rag.query_embedding",
    display_name="查询向量嵌入",
    description="将文本或图像转换为向量嵌入表示，用于后续相似度搜索",
    category="rag",
    icon="🔍",
    inputs=[
        PortDefinition("text", PortType.STRING, "查询文本", widget_type="text_edit"),
        PortDefinition("image_path", PortType.FILE, "查询图像路径(可选)",
                       default="", required=False, widget_type="file_picker"),
        PortDefinition("base_url", PortType.STRING, "API地址",
                       default="http://localhost:8000/api/v1", required=False),
    ],
    outputs=[
        PortDefinition("vector", PortType.STRING, "嵌入向量(截断预览)"),
        PortDefinition("dimension", PortType.INTEGER, "向量维度"),
    ],
    execute=_execute_query_embedding,
)


# ==================== 2. 向量搜索 ====================


def _execute_vector_search(
    text: str,
    collection_name: str = "rag_embeddings",
    limit: int = 5,
    milvus_uri: str = "http://localhost:19530",
    embed_base_url: str = "http://localhost:8000/api/v1",
) -> Dict[str, Any]:
    async def _search():
        # 获取嵌入向量
        embed_result = await _query_embedding_async(text, "", embed_base_url)
        if not embed_result.get("success"):
            return {"results": "[]", "count": 0, "error": embed_result.get("error", "嵌入失败")}

        from pymilvus import MilvusClient
        client = MilvusClient(uri=milvus_uri)

        if not client.has_collection(collection_name):
            return {"results": "[]", "count": 0, "error": f"集合 {collection_name} 不存在"}

        search_res = client.search(
            collection_name=collection_name,
            data=[embed_result["vector"]],
            limit=limit,
            output_fields=["text", "subject", "path", "type"],
        )

        results = []
        for hit in search_res[0]:
            results.append({
                "score": hit["distance"],
                "text": hit["entity"].get("text", ""),
                "path": hit["entity"].get("path", ""),
                "type": hit["entity"].get("type", ""),
            })
        return {"results": json.dumps(results, ensure_ascii=False), "count": len(results)}

    result = _run_async(_search())
    if "error" in result:
        return {"results": f"错误: {result['error']}", "count": 0}
    return result


rag_vector_search = NodeDefinition(
    node_type="rag.vector_search",
    display_name="向量搜索",
    description="在向量数据库中搜索与查询文本最相似的文档",
    category="rag",
    icon="🔎",
    inputs=[
        PortDefinition("text", PortType.STRING, "查询文本", widget_type="text_edit"),
        PortDefinition("collection_name", PortType.STRING, "集合名称",
                       default="rag_embeddings"),
        PortDefinition("limit", PortType.INTEGER, "返回条数", default=5),
        PortDefinition("milvus_uri", PortType.STRING, "Milvus地址",
                       default="http://localhost:19530", required=False),
        PortDefinition("embed_base_url", PortType.STRING, "嵌入API地址",
                       default="http://localhost:8000/api/v1", required=False),
    ],
    outputs=[
        PortDefinition("results", PortType.STRING, "搜索结果(JSON)", show_preview=True),
        PortDefinition("count", PortType.INTEGER, "结果数量"),
    ],
    execute=_execute_vector_search,
)


# ==================== 3. 重排序 ====================


async def _rerank_async(
    query_text: str,
    doc_text: str,
    query_type: str = "text",
    doc_type: str = "text",
    query_image_path: str = "",
    doc_image_path: str = "",
    base_url: str = "http://localhost:8000/api/v1",
) -> Dict[str, Any]:
    url = f"{base_url}/rerank"
    data = aiohttp.FormData()
    data.add_field("query_type", query_type)
    data.add_field("document_type", doc_type)

    if query_type == "text":
        data.add_field("query_text", query_text or "")
    elif query_image_path:
        with open(query_image_path, "rb") as f:
            data.add_field("query_image", f.read(), filename="query.png", content_type="image/png")

    if doc_type == "text":
        data.add_field("document_text", doc_text or "")
    elif doc_image_path:
        with open(doc_image_path, "rb") as f:
            data.add_field("document_image", f.read(), filename="doc.png", content_type="image/png")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            if response.status == 200:
                result = await response.json()
                return {"score": result["score"], "success": True}
            else:
                error = await response.text()
                return {"score": 0.0, "success": False, "error": f"HTTP {response.status}: {error}"}


def _execute_rerank(
    query_text: str,
    doc_text: str,
    base_url: str = "http://localhost:8000/api/v1",
) -> Dict[str, Any]:
    result = _run_async(_rerank_async(query_text, doc_text, base_url=base_url))
    if result.get("success"):
        return {"score": result["score"]}
    return {"score": 0.0}


rag_rerank = NodeDefinition(
    node_type="rag.rerank",
    display_name="重排序",
    description="对查询和文档进行相关性重排序评分",
    category="rag",
    icon="📊",
    inputs=[
        PortDefinition("query_text", PortType.STRING, "查询文本", widget_type="text_edit"),
        PortDefinition("doc_text", PortType.STRING, "文档文本", widget_type="text_edit"),
        PortDefinition("base_url", PortType.STRING, "API地址",
                       default="http://localhost:8000/api/v1", required=False),
    ],
    outputs=[
        PortDefinition("score", PortType.FLOAT, "相关性分数"),
    ],
    execute=_execute_rerank,
)
