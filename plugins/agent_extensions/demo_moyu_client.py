# -*- coding: utf-8 -*-
"""MoyuClient 完整 CRUD 功能演示脚本。

本脚本演示 MoyuClient 的所有增删改查功能，包括：
- 集合管理：init_collection, drop_collection, list_collections
- 插入：insert, insert_texts, insert_image
- 查询：search, search_by_text, get, query
- 更新：upsert, update
- 删除：delete, delete_by_filter

运行前请确保：
1. Milvus 服务已启动 (默认 http://localhost:19530)
2. 有可用的 requester（远程嵌入服务）

用法:
    python plugins/agent_extensions/demo_moyu_client.py
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from plugins.agent_extensions.moyus_client import MoyuClient

# 配置
MILVUS_URI = os.environ.get("MILVUS_URI", "http://localhost:19530")
COLLECTION_NAME = "demo_moyu_crud"


def demo_collection_management(client: MoyuClient):
    """演示集合管理功能。"""
    print("\n" + "=" * 60)
    print("1. 集合管理 (Collection Management)")
    print("=" * 60)

    # 清理旧集合
    print("\n[1.1] 删除旧集合 (如存在)...")
    client.drop_collection(COLLECTION_NAME)
    print(f"  集合 '{COLLECTION_NAME}' 已删除或不存在")

    # 初始化集合
    print("\n[1.2] 初始化新集合...")
    state = client.init_collection(COLLECTION_NAME)
    print(f"  集合状态: {state}")

    # 列出所有集合
    print("\n[1.3] 列出所有集合...")
    collections = client.list_collections()
    print(f"  现有集合: {collections}")


def demo_insert(client: MoyuClient):
    """演示插入功能。"""
    print("\n" + "=" * 60)
    print("2. 插入 (Create)")
    print("=" * 60)

    # 插入原始数据
    print("\n[2.1] 插入原始向量数据...")
    dim = client._get_embedding_dim()
    data = [
        {
            "embedding": [0.1] * dim,
            "type": "text",
            "text": "这是第一条测试文本，关于火箭发动机装配工艺。",
            "path": "test1.md",
            "subject": "demo",
        },
        {
            "embedding": [0.2] * dim,
            "type": "text",
            "text": "这是第二条测试文本，关于反推堵盖安装工序。",
            "path": "test2.md",
            "subject": "demo",
        },
    ]
    res = client.insert(data=data, collection_name=COLLECTION_NAME)
    print(f"  插入结果: {res}")

    # 统计数量
    count = client.count(collection_name=COLLECTION_NAME)
    print(f"  当前集合实体数: {count}")


async def demo_insert_with_embedding(client: MoyuClient):
    """演示通过远程 requester 自动嵌入后插入。"""
    print("\n" + "=" * 60)
    print("2.5. 自动嵌入插入 (Insert with Embedding)")
    print("=" * 60)

    print("\n[2.5.1] 插入文本（自动计算嵌入）...")
    res = await client.insert_texts(
        texts=["这是第三条通过远程嵌入的文本", "这是第四条文本"],
        subjects=["demo", "demo"],
        collection_name=COLLECTION_NAME,
    )
    print(f"  插入结果: {res}")


async def demo_search_by_text(client: MoyuClient):
    """演示通过文本自动嵌入后搜索。"""
    print("\n" + "=" * 60)
    print("3.5. 文本搜索 (Search by Text)")
    print("=" * 60)

    print("\n[3.5.1] 通过文本查询自动嵌入后搜索...")
    search_res = await client.search_by_text(
        texts=["火箭发动机"],
        collection_name=COLLECTION_NAME,
        limit=3,
        output_fields=["text", "subject", "path"],
    )
    print(f"  搜索结果:")
    for hit in search_res[0]:
        print(f"    - ID: {hit['id']}, 距离: {hit['distance']:.4f}")
        print(f"      文本: {hit['entity']['text'][:40]}...")


def demo_read(client: MoyuClient):
    """演示查询功能。"""
    print("\n" + "=" * 60)
    print("3. 查询 (Read)")
    print("=" * 60)

    # 向量搜索
    print("\n[3.1] 向量相似度搜索...")
    dim = client._get_embedding_dim()
    search_res = client.search(
        data=[[0.1] * dim],
        collection_name=COLLECTION_NAME,
        limit=2,
        output_fields=["text", "subject", "path"],
    )
    print(f"  搜索结果:")
    for hit in search_res[0]:
        print(f"    - ID: {hit['id']}, 距离: {hit['distance']:.4f}")
        print(f"      文本: {hit['entity']['text'][:40]}...")

    # 标量过滤查询
    print("\n[3.2] 标量过滤查询 (subject == 'demo')...")
    query_res = client.query(
        collection_name=COLLECTION_NAME,
        filter="subject == 'demo'",
        output_fields=["text", "path"],
        limit=10,
    )
    print(f"  查询结果数量: {len(query_res)}")
    for item in query_res:
        print(f"    - ID: {item['id']}, 文本: {item['text'][:30]}...")


def demo_update(client: MoyuClient):
    """演示更新功能。"""
    print("\n" + "=" * 60)
    print("4. 更新 (Update)")
    print("=" * 60)

    # 先查询所有 ID
    print("\n[4.1] 获取所有实体 ID...")
    all_items = client.query(
        collection_name=COLLECTION_NAME,
        filter="",
        output_fields=["id"],
    )
    if not all_items:
        print("  没有可更新的实体")
        return

    target_id = all_items[0]["id"]
    print(f"  目标 ID: {target_id}")

    # 更新字段
    print("\n[4.2] 更新实体字段...")
    update_res = client.update(
        ids=target_id,
        data={"text": "这是更新后的文本内容", "subject": "updated"},
        collection_name=COLLECTION_NAME,
    )
    print(f"  更新结果: {update_res}")

    # 验证更新
    print("\n[4.3] 验证更新结果...")
    get_res = client.get(
        ids=target_id,
        collection_name=COLLECTION_NAME,
        output_fields=["text", "subject"],
    )
    print(f"  更新后内容: {get_res}")


def demo_delete(client: MoyuClient):
    """演示删除功能。"""
    print("\n" + "=" * 60)
    print("5. 删除 (Delete)")
    print("=" * 60)

    # 查询剩余实体
    print("\n[5.1] 删除前统计...")
    count_before = client.count(collection_name=COLLECTION_NAME)
    print(f"  删除前数量: {count_before}")

    # 通过过滤条件删除
    print("\n[5.2] 通过过滤条件删除 (subject == 'updated')...")
    delete_res = client.delete_by_filter(
        filter="subject == 'updated'",
        collection_name=COLLECTION_NAME,
    )
    print(f"  删除结果: {delete_res}")

    # 删除后统计
    print("\n[5.3] 删除后统计...")
    count_after = client.count(collection_name=COLLECTION_NAME)
    print(f"  删除后数量: {count_after}")

    # 清理：删除整个集合
    print("\n[5.4] 删除整个集合...")
    client.drop_collection(COLLECTION_NAME)
    print(f"  集合 '{COLLECTION_NAME}' 已删除")


async def main():
    print("=" * 60)
    print("MoyuClient 完整 CRUD 功能演示")
    print("=" * 60)
    print(f"Milvus URI: {MILVUS_URI}")

    # 创建 mock requester（实际使用时替换为真实的 APIRequester）
    requester = AsyncMock()
    requester.query_embedding = AsyncMock(return_value={
        "vector": [0.1] * 768,
        "dimension": 768,
    })

    print("\n[*] 初始化 MoyuClient...")
    client = MoyuClient(uri=MILVUS_URI, requester=requester, dim=768)
    print(f"[*] 嵌入维度: {client._get_embedding_dim()}")

    try:
        demo_collection_management(client)
        demo_insert(client)
        await demo_insert_with_embedding(client)
        demo_read(client)
        await demo_search_by_text(client)
        demo_update(client)
        demo_delete(client)
    except Exception as e:
        print(f"\n[!] 错误: {e}")
        raise

    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
