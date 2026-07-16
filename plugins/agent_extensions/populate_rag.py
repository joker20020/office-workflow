"""通过 ProcessGen 后端初始化并填充 RAG 知识库。

后端负责文档分块、嵌入生成、向量存储和资源管理。本脚本只上传
原始文档与图片，不连接数据库。

环境变量：
    RAG_BASE_URL - ProcessGen API 地址，默认 http://localhost:8050/api/v1
"""

import asyncio
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from plugins.agent_extensions import _APIRequester  # noqa: E402

RAG_BASE_URL = os.environ.get("RAG_BASE_URL", "http://localhost:8050/api/v1")
COLLECTION_NAME = "process"
SUBJECT = "capp"

MD_PATH = _PROJECT_ROOT / "data" / "工艺卡片.md"
IMAGE_PATHS = [
    _PROJECT_ROOT / "data" / "反推堵盖2.png",
]
IMAGE_TEXTS = [
    "这是一张火箭反推堵盖图片，可以参考它进行设计",
]


async def reset_collection(requester: _APIRequester):
    """删除同名集合后重新创建。"""
    collection_payload = await requester.rag_list_collections()
    collections = collection_payload.get("collections", [])
    names = {
        item.get("name")
        for item in collections
        if isinstance(item, dict)
    }
    if COLLECTION_NAME in names:
        print(f"[*] 删除已有集合: {COLLECTION_NAME}")
        await requester.rag_delete_collection(COLLECTION_NAME)
    result = await requester.rag_create_collection(COLLECTION_NAME)
    print(f"[*] 已创建集合: {result}")
    return result


async def upload_sources(requester: _APIRequester):
    """上传存在的文档和图片源文件。"""
    if MD_PATH.exists():
        result = await requester.rag_add_text(
            COLLECTION_NAME,
            str(MD_PATH),
            subject=SUBJECT,
        )
        print(f"[*] 文档上传结果: {result}")
    else:
        print(f"[!] 文档不存在，已跳过: {MD_PATH}")

    valid_sources = [
        (path, description)
        for path, description in zip(IMAGE_PATHS, IMAGE_TEXTS, strict=True)
        if path.exists()
    ]
    missing_paths = [path for path in IMAGE_PATHS if not path.exists()]
    for path in missing_paths:
        print(f"[!] 图片不存在，已跳过: {path}")

    if valid_sources:
        result = await requester.rag_add_images(
            COLLECTION_NAME,
            [str(path) for path, _ in valid_sources],
            [description for _, description in valid_sources],
            subject=SUBJECT,
        )
        print(f"[*] 图片上传结果: {result}")


async def show_search_example(requester: _APIRequester):
    """运行一次文本检索并打印后端标准结果。"""
    results = await requester.rag_search_text(
        COLLECTION_NAME,
        "加工内表面螺纹孔",
        limit=2,
        subject=SUBJECT,
    )
    print("[*] 检索结果:")
    for item in results:
        print(
            f"  - ID: {item.get('id')}, score: {item.get('score', 0):.4f}, "
            f"text: {item.get('text', '')[:60]}"
        )


async def main():
    print("=" * 60)
    print("ProcessGen RAG 知识库填充")
    print("=" * 60)
    print(f"RAG API    : {RAG_BASE_URL}")
    print(f"Collection : {COLLECTION_NAME}")

    requester = _APIRequester(base_url=RAG_BASE_URL)
    await reset_collection(requester)
    await upload_sources(requester)
    await show_search_example(requester)
    print("[*] 执行完毕")


if __name__ == "__main__":
    asyncio.run(main())
