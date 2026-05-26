# -*- coding: utf-8 -*-
"""MoyuClient 单元测试 — 覆盖完整的 CRUD 功能。

由于 Milvus 服务和 requester 为外部依赖，本测试使用 unittest.mock
模拟底层调用，重点验证：
1. 接口参数传递正确性
2. 数据格式转换正确性
3. 业务逻辑分支覆盖

如需测试真实 Milvus 交互，请确保：
  - Milvus 服务已启动 (默认 http://localhost:19530)
  - 有可用的 requester（远程嵌入服务）
然后设置环境变量 RUN_INTEGRATION=1 后运行 pytest。
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# 通过 importlib 直接加载模块，绕过 plugins/__init__.py 中不存在的依赖
_MOYU_MODULE_PATH = Path(__file__).parent.parent / "plugins" / "agent_extensions" / "moyus_client.py"
_spec = importlib.util.spec_from_file_location("moyus_client", _MOYU_MODULE_PATH)
moyus_client_mod = importlib.util.module_from_spec(_spec)
sys.modules["moyus_client"] = moyus_client_mod
_spec.loader.exec_module(moyus_client_mod)
MoyuClient = moyus_client_mod.MoyuClient


@pytest.fixture
def mock_milvus_methods():
    """Mock MilvusClient 的方法，模拟 pymilvus 底层行为。"""
    methods = {
        "has_collection": MagicMock(return_value=False),
        "get_load_state": MagicMock(return_value={"state": "Loaded"}),
        "create_schema": MagicMock(return_value=MagicMock()),
        "prepare_index_params": MagicMock(return_value=MagicMock()),
        "create_collection": MagicMock(),
        "drop_collection": MagicMock(),
        "list_collections": MagicMock(return_value=["rag_embeddings", "test_collection"]),
        "get_collection_stats": MagicMock(return_value={"row_count": 10}),
        "insert": MagicMock(return_value={"insert_count": 2, "ids": [1, 2]}),
        "upsert": MagicMock(return_value={"upsert_count": 2}),
        "delete": MagicMock(return_value={"delete_count": 1}),
        "search": MagicMock(return_value=[[
            {"id": 1, "distance": 0.95, "entity": {"text": "hello", "subject": "capp"}},
            {"id": 2, "distance": 0.85, "entity": {"text": "world", "subject": "capp"}},
        ]]),
        "get": MagicMock(return_value=[
            {"id": 1, "text": "hello", "subject": "capp", "type": "text"},
        ]),
        "query": MagicMock(return_value=[
            {"id": 1, "text": "hello", "subject": "capp"},
            {"id": 2, "text": "world", "subject": "capp"},
        ]),
    }
    return methods


@pytest.fixture
def mock_requester():
    """Mock requester，模拟远程嵌入服务。"""
    req = MagicMock()
    req.query_embedding = AsyncMock(return_value={
        "vector": [0.1] * 768,
        "dimension": 768,
    })
    return req


@pytest.fixture
def moyu_client(mock_milvus_methods, mock_requester):
    """构建带 mock 依赖的 MoyuClient 实例。

    通过 patch MilvusClient 的类方法，使得 self.xxx() 和 super().xxx()
    都走到 mock 上，从而测试 MoyuClient 的业务逻辑。
    """
    from pymilvus import MilvusClient as _MilvusClient

    patches = []
    for name, method in mock_milvus_methods.items():
        p = patch.object(_MilvusClient, name, method)
        p.start()
        patches.append(p)

    # patch __init__ 避免连接服务器
    p_init = patch.object(_MilvusClient, "__init__", return_value=None)
    p_init.start()
    patches.append(p_init)

    client = MoyuClient(
        uri="http://localhost:19530",
        requester=mock_requester,
        dim=768,
    )

    yield client

    for p in patches:
        p.stop()


class TestCollectionManagement:
    """测试集合管理相关方法。"""

    def test_init_collection_creates_new(self, moyu_client, mock_milvus_methods):
        """init_collection：集合不存在时应创建并返回状态。"""
        mock_milvus_methods["has_collection"].return_value = False

        result = moyu_client.init_collection(collection_name="test_collection")

        mock_milvus_methods["has_collection"].assert_called_once_with(collection_name="test_collection")
        mock_milvus_methods["create_collection"].assert_called_once()
        assert result == {"state": "Loaded"}

    def test_init_collection_existing(self, moyu_client, mock_milvus_methods):
        """init_collection：集合已存在时应直接返回加载状态。"""
        mock_milvus_methods["has_collection"].return_value = True

        result = moyu_client.init_collection(collection_name="existing_collection")

        mock_milvus_methods["has_collection"].assert_called_once_with(collection_name="existing_collection")
        mock_milvus_methods["create_collection"].assert_not_called()
        assert result == {"state": "Loaded"}

    def test_drop_collection(self, moyu_client, mock_milvus_methods):
        """drop_collection：应删除已存在的集合。"""
        mock_milvus_methods["has_collection"].return_value = True

        moyu_client.drop_collection(collection_name="to_drop")

        mock_milvus_methods["drop_collection"].assert_called_once_with(collection_name="to_drop")

    def test_drop_collection_not_exists(self, moyu_client, mock_milvus_methods):
        """drop_collection：集合不存在时不应抛出异常。"""
        mock_milvus_methods["has_collection"].return_value = False

        moyu_client.drop_collection(collection_name="not_exists")

        mock_milvus_methods["drop_collection"].assert_not_called()

    def test_list_collections(self, moyu_client, mock_milvus_methods):
        """list_collections：应返回集合名称列表。"""
        mock_milvus_methods["list_collections"].return_value = ["c1", "c2", "c3"]

        result = moyu_client.list_collections()

        assert result == ["c1", "c2", "c3"]

    def test_count(self, moyu_client, mock_milvus_methods):
        """count：应返回集合实体数量。"""
        mock_milvus_methods["get_collection_stats"].return_value = {"row_count": 42}

        result = moyu_client.count(collection_name="test")

        mock_milvus_methods["get_collection_stats"].assert_called_once_with(
            collection_name="test",
        )
        assert result == 42


class TestInsert:
    """测试插入相关方法。"""

    def test_insert_raw_data(self, moyu_client, mock_milvus_methods):
        """insert：应正确传递原始数据到 MilvusClient。"""
        data = [
            {"embedding": [0.1] * 768, "type": "text", "text": "hello", "path": "", "subject": "capp"},
        ]

        moyu_client.insert(data=data, collection_name="test_coll")

        mock_milvus_methods["insert"].assert_called_once()
        call_args = mock_milvus_methods["insert"].call_args
        assert call_args.kwargs["collection_name"] == "test_coll"
        assert call_args.kwargs["data"] == data

    @pytest.mark.asyncio
    async def test_insert_texts(self, moyu_client, mock_milvus_methods, mock_requester):
        """insert_texts：应自动通过 requester 计算文本嵌入并插入。"""
        result = await moyu_client.insert_texts(
            texts=["文本1", "文本2"],
            collection_name="rag_embeddings",
        )

        assert mock_requester.query_embedding.call_count == 2
        mock_milvus_methods["insert"].assert_called_once()
        call_data = mock_milvus_methods["insert"].call_args.kwargs["data"]
        assert len(call_data) == 2
        assert call_data[0]["type"] == "text"
        assert call_data[0]["text"] == "文本1"
        assert call_data[0]["subject"] == "capp"

    @pytest.mark.asyncio
    async def test_insert_image(self, moyu_client, mock_milvus_methods, mock_requester):
        """insert_image：应自动通过 requester 计算融合嵌入并插入图像数据。"""
        result = await moyu_client.insert_image(
            image_paths=["/path/to/img1.png", "/path/to/img2.jpg"],
            texts=["描述1", "描述2"],
            collection_name="rag_embeddings",
        )

        assert mock_requester.query_embedding.call_count == 2
        mock_milvus_methods["insert"].assert_called_once()
        call_data = mock_milvus_methods["insert"].call_args.kwargs["data"]
        assert len(call_data) == 2
        assert call_data[0]["type"] == "image"
        assert call_data[0]["path"] == "/path/to/img1.png"

    @pytest.mark.asyncio
    async def test_insert_image_length_mismatch(self, moyu_client):
        """insert_image：image_paths 和 texts 长度不一致时应抛出 AssertionError。"""
        with pytest.raises(AssertionError, match="长度必须相同"):
            await moyu_client.insert_image(
                image_paths=["/path/1.png"],
                texts=["描述1", "描述2"],
            )


class TestRead:
    """测试查询相关方法。"""

    def test_search(self, moyu_client, mock_milvus_methods):
        """search：应正确传递参数并返回搜索结果。"""
        query_vector = [[0.1] * 768]

        result = moyu_client.search(
            data=query_vector,
            collection_name="test",
            filter="subject == 'capp'",
            limit=5,
            output_fields=["text", "path"],
        )

        mock_milvus_methods["search"].assert_called_once()
        call_args = mock_milvus_methods["search"].call_args
        assert call_args.kwargs["data"] == query_vector
        assert call_args.kwargs["collection_name"] == "test"
        assert call_args.kwargs["filter"] == "subject == 'capp'"
        assert call_args.kwargs["limit"] == 5
        assert len(result[0]) == 2

    @pytest.mark.asyncio
    async def test_search_by_text(self, moyu_client, mock_milvus_methods, mock_requester):
        """search_by_text：应自动通过 requester 计算文本嵌入后执行搜索。"""
        result = await moyu_client.search_by_text(
            texts=["查询文本"],
            collection_name="test",
            limit=3,
        )

        mock_requester.query_embedding.assert_called_once_with("查询文本", None)
        mock_milvus_methods["search"].assert_called_once()

    def test_get_by_single_id(self, moyu_client, mock_milvus_methods):
        """get：应支持单 ID 查询。"""
        moyu_client.get(ids=1, collection_name="test", output_fields=["text"])

        mock_milvus_methods["get"].assert_called_once()
        call_kwargs = mock_milvus_methods["get"].call_args.kwargs
        assert call_kwargs["collection_name"] == "test"
        assert call_kwargs["ids"] == 1
        assert call_kwargs["output_fields"] == ["text"]

    def test_get_by_id_list(self, moyu_client, mock_milvus_methods):
        """get：应支持 ID 列表查询。"""
        moyu_client.get(ids=[1, 2, 3], collection_name="test")

        mock_milvus_methods["get"].assert_called_once()
        call_kwargs = mock_milvus_methods["get"].call_args.kwargs
        assert call_kwargs["collection_name"] == "test"
        assert call_kwargs["ids"] == [1, 2, 3]

    def test_query(self, moyu_client, mock_milvus_methods):
        """query：应正确执行标量过滤查询。"""
        moyu_client.query(
            collection_name="test",
            filter="subject == 'capp'",
            output_fields=["text", "path"],
            limit=10,
            offset=0,
        )

        mock_milvus_methods["query"].assert_called_once()
        call_args = mock_milvus_methods["query"].call_args
        assert call_args.kwargs["filter"] == "subject == 'capp'"
        assert call_args.kwargs["limit"] == 10
        assert call_args.kwargs["offset"] == 0


class TestUpdate:
    """测试更新相关方法。"""

    def test_upsert(self, moyu_client, mock_milvus_methods):
        """upsert：应正确传递数据到 MilvusClient。"""
        data = [{"id": 1, "text": "updated", "subject": "capp"}]

        moyu_client.upsert(data=data, collection_name="test")

        mock_milvus_methods["upsert"].assert_called_once()
        call_kwargs = mock_milvus_methods["upsert"].call_args.kwargs
        assert call_kwargs["collection_name"] == "test"
        assert call_kwargs["data"] == data

    def test_update(self, moyu_client, mock_milvus_methods):
        """update：应先获取再合并字段后 upsert。"""
        mock_milvus_methods["get"].return_value = [
            {"id": 1, "text": "old", "subject": "capp", "type": "text", "path": "a.md"},
        ]
        mock_milvus_methods["upsert"].return_value = {"upsert_count": 1}

        moyu_client.update(
            ids=1,
            data={"text": "new text", "subject": "updated"},
            collection_name="test",
        )

        mock_milvus_methods["get"].assert_called_once()
        call_kwargs = mock_milvus_methods["get"].call_args.kwargs
        assert call_kwargs["collection_name"] == "test"
        assert call_kwargs["ids"] == [1]
        assert call_kwargs["output_fields"] == ["*"]

        mock_milvus_methods["upsert"].assert_called_once()
        upsert_data = mock_milvus_methods["upsert"].call_args.kwargs["data"]
        assert upsert_data[0]["text"] == "new text"
        assert upsert_data[0]["subject"] == "updated"
        assert upsert_data[0]["type"] == "text"  # 保留原字段

    def test_update_not_found(self, moyu_client, mock_milvus_methods):
        """update：ID 不存在时应返回 upsert_count=0。"""
        mock_milvus_methods["get"].return_value = []

        result = moyu_client.update(ids=999, data={"text": "new"}, collection_name="test")

        assert result == {"upsert_count": 0}
        mock_milvus_methods["upsert"].assert_not_called()


class TestDelete:
    """测试删除相关方法。"""

    def test_delete_by_ids(self, moyu_client, mock_milvus_methods):
        """delete：通过 ID 删除实体。"""
        moyu_client.delete(ids=[1, 2], collection_name="test")

        mock_milvus_methods["delete"].assert_called_once()
        call_kwargs = mock_milvus_methods["delete"].call_args.kwargs
        assert call_kwargs["collection_name"] == "test"
        assert call_kwargs["ids"] == [1, 2]

    def test_delete_by_filter(self, moyu_client, mock_milvus_methods):
        """delete：通过过滤条件删除实体。"""
        moyu_client.delete(filter="subject == 'temp'", collection_name="test")

        mock_milvus_methods["delete"].assert_called_once()
        call_kwargs = mock_milvus_methods["delete"].call_args.kwargs
        assert call_kwargs["collection_name"] == "test"
        assert call_kwargs["ids"] is None
        assert call_kwargs["filter"] == "subject == 'temp'"

    def test_delete_conflict(self, moyu_client):
        """delete：同时指定 ids 和 filter 时应抛出 ValueError。"""
        with pytest.raises(ValueError, match="不能同时指定"):
            moyu_client.delete(ids=[1], filter="subject == 'x'")

    def test_delete_by_filter_method(self, moyu_client, mock_milvus_methods):
        """delete_by_filter：应正确委托给 delete。"""
        moyu_client.delete_by_filter(
            filter="subject == 'temp'",
            collection_name="test",
        )

        mock_milvus_methods["delete"].assert_called_once()
        call_kwargs = mock_milvus_methods["delete"].call_args.kwargs
        assert call_kwargs["collection_name"] == "test"
        assert call_kwargs["filter"] == "subject == 'temp'"


class TestEmbedding:
    """测试嵌入向量相关方法。"""

    @pytest.mark.asyncio
    async def test_get_text_embeddings(self, moyu_client, mock_requester):
        """get_text_embeddings：应调用 requester 获取文本嵌入。"""
        result = await moyu_client.get_text_embeddings(text="hello")

        mock_requester.query_embedding.assert_called_once_with("hello", None)
        assert result == [0.1] * 768

    @pytest.mark.asyncio
    async def test_get_image_embeddings(self, moyu_client, mock_requester):
        """get_image_embeddings：应调用 requester 获取图像嵌入。"""
        result = await moyu_client.get_image_embeddings(image_path="/path/to/img.png")

        mock_requester.query_embedding.assert_called_once_with(None, "/path/to/img.png")
        assert result == [0.1] * 768

    @pytest.mark.asyncio
    async def test_get_fused_embeddings(self, moyu_client, mock_requester):
        """get_fused_embeddings：应调用 requester 获取融合嵌入。"""
        result = await moyu_client.get_fused_embeddings(text="test", image_path="/path/to/img.png")

        mock_requester.query_embedding.assert_called_once_with("test", "/path/to/img.png")
        assert result == [0.1] * 768

    def test_get_embedding_dim_cached(self, moyu_client):
        """_get_embedding_dim：应返回已缓存的 dim 值。"""
        dim = moyu_client._get_embedding_dim()
        assert dim == 768

    def test_get_embedding_dim_detection(self, mock_milvus_methods, mock_requester):
        """_get_embedding_dim：未缓存时应通过 requester 动态检测。"""
        from pymilvus import MilvusClient as _MilvusClient

        patches = []
        for name, method in mock_milvus_methods.items():
            p = patch.object(_MilvusClient, name, method)
            p.start()
            patches.append(p)
        p_init = patch.object(_MilvusClient, "__init__", return_value=None)
        p_init.start()
        patches.append(p_init)

        try:
            client = MoyuClient(
                uri="http://localhost:19530",
                requester=mock_requester,
                dim=None,
            )
            dim = client._get_embedding_dim()
            assert dim == 768
            mock_requester.query_embedding.assert_called_with("dimension detection", None)
        finally:
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_embedding_no_provider(self, moyu_client):
        """未配置 requester 时应抛出 RuntimeError。"""
        moyu_client.requester = None

        with pytest.raises(RuntimeError, match="未配置 requester"):
            await moyu_client.get_text_embeddings(text="hello")


# ============================================================================
#  集成测试（可选）
# ============================================================================

@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="需要真实 Milvus 服务和 requester，设置 RUN_INTEGRATION=1 后运行",
)
class TestIntegration:
    """集成测试 — 需要真实 Milvus 服务。"""

    def test_real_connection(self):
        """测试真实 Milvus 连接。"""
        client = MoyuClient(uri="http://localhost:19530")
        collections = client.list_collections()
        assert isinstance(collections, list)

    def test_real_crud(self):
        """测试真实 CRUD 流程。"""
        client = MoyuClient(uri="http://localhost:19530")
        coll_name = "test_moyu_crud"

        # 清理
        client.drop_collection(coll_name)

        # 创建
        state = client.init_collection(coll_name)
        assert state is not None

        # 插入
        data = [
            {"embedding": [0.1] * 1536, "type": "text", "text": "test1", "path": "", "subject": "test"},
            {"embedding": [0.2] * 1536, "type": "text", "text": "test2", "path": "", "subject": "test"},
        ]
        insert_res = client.insert(data=data, collection_name=coll_name)
        assert insert_res["insert_count"] == 2

        # 查询
        count = client.count(collection_name=coll_name)
        assert count == 2

        # 搜索
        search_res = client.search(
            data=[[0.1] * 1536],
            collection_name=coll_name,
            limit=2,
        )
        assert len(search_res[0]) == 2

        # 标量查询
        query_res = client.query(
            collection_name=coll_name,
            filter="subject == 'test'",
        )
        assert len(query_res) == 2

        # 获取
        ids = insert_res["ids"]
        get_res = client.get(ids=ids, collection_name=coll_name)
        assert len(get_res) == 2

        # 删除
        delete_res = client.delete(ids=ids, collection_name=coll_name)
        assert delete_res["delete_count"] == 2

        # 清理
        client.drop_collection(coll_name)
