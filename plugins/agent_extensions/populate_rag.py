# -*- coding: utf-8 -*-
"""RAG 知识库数据填充辅助脚本。

功能：
1. 读取 Markdown 文件，按标题结构分块
2. 通过远程 embedding 服务获取文本嵌入向量
3. 将文本块和图像插入到 Milvus 向量数据库
4. 支持向量相似度搜索和标量过滤查询

用法：
    python plugins/agent_extensions/populate_rag.py

环境变量：
    MILVUS_BASE_URL - Milvus 服务地址 (默认: http://localhost:19530)
    RAG_BASE_URL    - Embedding 服务地址 (默认: http://localhost:8000/api/v1)
"""

import asyncio
import os
import sys
from pathlib import Path

# 将项目根目录加入路径
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from plugins.agent_extensions.moyus_client import MoyuClient
from requester import APIRequester
from text import TextProcessor


# 默认配置
MILVUS_URI = os.environ.get("MILVUS_BASE_URL", "http://localhost:19530")
RAG_BASE_URL = os.environ.get("RAG_BASE_URL", "http://localhost:8050/api/v1")
COLLECTION_NAME = "rag_embeddings"

# Markdown 文件路径（相对于项目根目录）
MD_PATH = _PROJECT_ROOT / "data" / "工艺卡片.md"

# 图像文件路径列表
IMAGE_PATHS = [
    _PROJECT_ROOT / "data" / "反推堵盖2.png",
]
IMAGE_TEXTS = [
    "这是一张火箭反推堵盖图片，可以参考他进行设计",
]


async def init_collection(client: MoyuClient):
    """初始化 Milvus 集合。如已存在则先删除再重建。"""
    print("\n[*] 初始化集合...")
    if client.has_collection(collection_name=COLLECTION_NAME):
        print(f"    删除已存在的集合: {COLLECTION_NAME}")
        client.drop_collection(collection_name=COLLECTION_NAME)
    res = client.init_collection(collection_name=COLLECTION_NAME)
    print(f"    集合状态: {res}")
    return res


async def insert_markdown_chunks(client: MoyuClient, md_path: Path):
    """读取 Markdown 文件，分块后插入到 Milvus。"""
    print(f"\n[*] 读取 Markdown: {md_path}")

    if not md_path.exists():
        print(f"    [!] 文件不存在: {md_path}")
        return None

    text_processor = TextProcessor()
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    chunks = text_processor.split_markdown_for_rag(
        content, min_words=10, include_subsections=False
    )
    print(f"    分块数量: {len(chunks)}")

    if not chunks:
        print("    [!] 未提取到有效文本块")
        return None

    # 获取嵌入向量
    print("    正在获取文本嵌入向量...")
    vectors = await client.get_text_embeddings(texts=chunks)

    # 输出维度信息
    dim = len(vectors[0]) if isinstance(vectors[0], list) else vectors[0].shape[-1]
    print(f"    嵌入维度: {dim}")

    # 构造数据
    filename = md_path.name
    data = [
        {
            "embedding": vectors[i] if isinstance(vectors[i], list) else vectors[i].tolist(),
            "type": "text",
            "text": chunks[i],
            "path": filename,
            "subject": "capp",
        }
        for i in range(len(vectors))
    ]

    print(f"    数据实体数: {len(data)}")
    print(f"    字段: {list(data[0].keys())}")
    print(f"    向量维度: {len(data[0]['embedding'])}")

    # 插入数据
    res = client.insert(data=data, collection_name=COLLECTION_NAME)
    print(f"    插入结果: {res}")
    return res


async def insert_images(client: MoyuClient, image_paths: list, texts: list):
    """插入图像数据到 Milvus。"""
    print(f"\n[*] 插入图像...")

    # 过滤不存在的文件
    valid_paths = []
    valid_texts = []
    for p, t in zip(image_paths, texts):
        if p.exists():
            valid_paths.append(str(p))
            valid_texts.append(t)
        else:
            print(f"    [!] 跳过不存在的图像: {p}")

    if not valid_paths:
        print("    [!] 没有有效的图像文件")
        return None

    res = await client.insert_image(
        image_paths=valid_paths,
        texts=valid_texts,
        collection_name=COLLECTION_NAME,
    )
    print(f"    插入结果: {res}")
    return res


async def search_by_text(client: MoyuClient, query: str, limit: int = 2):
    """通过文本查询进行向量搜索。"""
    print(f"\n[*] 搜索: '{query}'")

    # 获取查询向量
    query_vector = await client.get_text_embeddings(text=query)
    if not isinstance(query_vector, list):
        query_vector = query_vector.tolist()

    res = client.search(
        data=[query_vector],
        collection_name=COLLECTION_NAME,
        limit=limit,
        output_fields=["text", "subject", "path"],
    )

    print(f"    结果数量: {len(res[0])}")
    for hit in res[0]:
        entity = hit["entity"]
        print(f"    - ID: {hit['id']}, 距离: {hit['distance']:.4f}")
        print(f"      文本: {entity.get('text', '')[:60]}...")
        print(f"      来源: {entity.get('path', '')}")

    return res


async def search_with_filter(client: MoyuClient, query: str, filter_expr: str, limit: int = 2):
    """带标量过滤条件的向量搜索。"""
    print(f"\n[*] 过滤搜索: '{query}' (filter: {filter_expr})")

    query_vector = await client.get_text_embeddings(text=query)
    if not isinstance(query_vector, list):
        query_vector = query_vector.tolist()

    res = client.search(
        data=[query_vector],
        collection_name=COLLECTION_NAME,
        filter=filter_expr,
        limit=limit,
        output_fields=["text", "subject", "path"],
    )

    print(f"    结果数量: {len(res[0])}")
    for hit in res[0]:
        entity = hit["entity"]
        print(f"    - ID: {hit['id']}, 距离: {hit['distance']:.4f}")
        print(f"      文本: {entity.get('text', '')[:60]}...")
        print(f"      来源: {entity.get('path', '')}")

    return res


async def query_by_filter(client: MoyuClient, filter_expr: str):
    """纯标量过滤查询。"""
    print(f"\n[*] 标量查询: {filter_expr}")

    res = client.query(
        collection_name=COLLECTION_NAME,
        filter=filter_expr,
        output_fields=["text", "path", "subject"],
        limit=100,
    )

    print(f"    结果数量: {len(res)}")
    for item in res:
        print(f"    - ID: {item['id']}, path: {item.get('path', '')}")

    return res


async def main():
    """主流程。"""
    print("=" * 60)
    print("RAG 知识库数据填充脚本")
    print("=" * 60)
    print(f"Milvus URI : {MILVUS_URI}")
    print(f"RAG API    : {RAG_BASE_URL}")
    print(f"Collection : {COLLECTION_NAME}")

    # 创建 requester 和 client
    requester = APIRequester(base_url=RAG_BASE_URL)
    client = MoyuClient(uri=MILVUS_URI, requester=requester)

    # 1. 初始化集合
    await init_collection(client)

    # 2. 插入 Markdown 文本
    if MD_PATH.exists():
        await insert_markdown_chunks(client, MD_PATH)
    else:
        print(f"\n[!] Markdown 文件不存在: {MD_PATH}")
        print("    跳过文本插入")

    # 3. 插入图像
    await insert_images(client, IMAGE_PATHS, IMAGE_TEXTS)

    # 4. 搜索演示
    print("\n" + "=" * 60)
    print("搜索演示")
    print("=" * 60)

    await search_by_text(client, "加工内表面螺纹孔", limit=2)
    await search_with_filter(client, "安装反推火箭堵盖", "subject == 'capp'", limit=2)

    print("\n" + "=" * 60)
    print("执行完毕!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
