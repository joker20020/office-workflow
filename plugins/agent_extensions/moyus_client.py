# -*- coding: utf-8 -*-
"""MoyuClient - Milvus 向量数据库客户端，支持完整的 CRUD 操作。

所有嵌入均通过远程 APIRequester 完成，嵌入向量维度根据首次嵌入结果动态确定，
不再写死为固定值。
"""

import asyncio
import os
from typing import List, Optional, Dict, Any, Union

from pymilvus import MilvusClient, DataType


class MoyuClient(MilvusClient):
    """Milvus 向量数据库客户端，支持远程嵌入和完整的 CRUD 操作。

    Args:
        uri: Milvus 服务地址，默认 "http://localhost:19530"
        user: 用户名
        password: 密码
        db_name: 数据库名
        token: 认证令牌
        timeout: 超时时间
        requester: 远程嵌入服务请求器（必需）
        dim: 嵌入向量维度（可选，未提供时通过 requester 动态检测）
        **kwargs: 传递给 MilvusClient 的其他参数
    """

    def __init__(
        self,
        uri: str = "http://localhost:19530",
        user: str = "",
        password: str = "",
        db_name: str = "",
        token: str = "",
        timeout: Optional[float] = None,
        requester=None,
        dim: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(uri, user, password, db_name, token, timeout, **kwargs)
        self.requester = requester
        self._dim = dim

    # ------------------------------------------------------------------ #
    #  Collection 管理
    # ------------------------------------------------------------------ #

    def init_collection(self, collection_name: str = "rag_embeddings") -> Dict[str, Any]:
        """初始化集合。如果集合已存在则返回加载状态，否则创建新集合。

        Args:
            collection_name: 集合名称

        Returns:
            集合加载状态信息
        """
        if self.has_collection(collection_name=collection_name):
            return self.get_load_state(collection_name=collection_name)

        dim = self._get_embedding_dim()

        schema = self.create_schema(
            auto_id=True,
            enable_dynamic_field=True,
        )

        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field(field_name="type", datatype=DataType.VARCHAR, max_length=16)
        schema.add_field(field_name="path", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="subject", datatype=DataType.VARCHAR, max_length=64)

        index_params = self.prepare_index_params()

        index_params.add_index(
            field_name="id",
            index_type="",
        )

        index_params.add_index(
            field_name="embedding",
            index_type="",
            metric_type="COSINE",
        )

        self.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )

        return self.get_load_state(collection_name=collection_name)

    def drop_collection(self, collection_name: str) -> None:
        """删除指定集合。

        Args:
            collection_name: 要删除的集合名称
        """
        if self.has_collection(collection_name=collection_name):
            super().drop_collection(collection_name=collection_name)

    def list_collections(self) -> List[str]:
        """列出所有集合名称。

        Returns:
            集合名称列表
        """
        return super().list_collections()

    def get_collection_stats(self, collection_name: str, **kwargs) -> Dict[str, Any]:
        """获取集合统计信息。

        Args:
            collection_name: 集合名称
            **kwargs: 其他参数

        Returns:
            集合统计信息，包含实体数量等
        """
        return super().get_collection_stats(collection_name=collection_name, **kwargs)

    def count(self, collection_name: str, **kwargs) -> int:
        """统计集合中的实体数量。

        Args:
            collection_name: 集合名称
            **kwargs: 其他参数

        Returns:
            实体数量
        """
        stats = self.get_collection_stats(collection_name=collection_name, **kwargs)
        return stats.get("row_count", 0)

    # ------------------------------------------------------------------ #
    #  Create (插入)
    # ------------------------------------------------------------------ #

    def insert(
        self,
        data: List[Dict[str, Any]],
        collection_name: str = "rag_embeddings",
        timeout: Optional[float] = None,
        partition_name: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """插入数据到集合。

        Args:
            data: 要插入的数据列表，每个元素为字典
            collection_name: 集合名称
            timeout: 超时时间
            partition_name: 分区名称
            **kwargs: 其他参数

        Returns:
            插入结果，包含插入的 ID 列表
        """
        return super().insert(
            collection_name=collection_name,
            data=data,
            timeout=timeout,
            partition_name=partition_name,
            **kwargs,
        )

    async def insert_texts(
        self,
        texts: List[str],
        paths: Optional[List[str]] = None,
        subjects: Optional[List[str]] = None,
        collection_name: str = "rag_embeddings",
        timeout: Optional[float] = None,
        partition_name: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """插入文本数据，通过远程 requester 自动计算嵌入向量。

        Args:
            texts: 文本列表
            paths: 文件路径列表 (可选，默认为空字符串)
            subjects: 主题标签列表 (可选，默认为 "capp")
            collection_name: 集合名称
            timeout: 超时时间
            partition_name: 分区名称
            **kwargs: 其他参数

        Returns:
            插入结果
        """
        vectors = await self.get_text_embeddings(texts=texts)
        if paths is None:
            paths = [""] * len(texts)
        if subjects is None:
            subjects = ["capp"] * len(texts)

        data = [
            {
                "embedding": vectors[i],
                "type": "text",
                "text": texts[i],
                "path": paths[i],
                "subject": subjects[i],
            }
            for i in range(len(vectors))
        ]
        return self.insert(
            data=data,
            collection_name=collection_name,
            timeout=timeout,
            partition_name=partition_name,
            **kwargs,
        )

    async def insert_image(
        self,
        image_paths: List[str],
        texts: List[str],
        collection_name: str = "rag_embeddings",
        timeout: Optional[float] = None,
        partition_name: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """插入图像数据，通过远程 requester 自动计算融合嵌入向量。

        Args:
            image_paths: 图像文件路径列表
            texts: 图像描述文本列表
            collection_name: 集合名称
            timeout: 超时时间
            partition_name: 分区名称
            **kwargs: 其他参数

        Returns:
            插入结果

        Raises:
            AssertionError: image_paths 和 texts 长度不一致时抛出
        """
        assert len(image_paths) == len(texts), "image_paths 和 texts 长度必须相同"
        vectors = []
        for i in range(len(texts)):
            vec = await self.get_fused_embeddings(text=texts[i], image_path=image_paths[i])
            vectors.append(vec)

        data = [
            {
                "embedding": vectors[i],
                "type": "image",
                "text": texts[i],
                "path": os.path.abspath(image_paths[i]).split(r'/')[-1],
                "subject": "capp",
            }
            for i in range(len(vectors))
        ]
        return self.insert(
            data=data,
            collection_name=collection_name,
            timeout=timeout,
            partition_name=partition_name,
            **kwargs,
        )

    # ------------------------------------------------------------------ #
    #  Read (查询)
    # ------------------------------------------------------------------ #

    def search(
        self,
        data: List[List[float]],
        collection_name: str = "rag_embeddings",
        filter: str = "",
        limit: int = 10,
        output_fields: Optional[List[str]] = None,
        search_params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        partition_names: Optional[List[str]] = None,
        anns_field: Optional[str] = None,
        ranker=None,
        **kwargs,
    ) -> List[List[Dict[str, Any]]]:
        """向量相似度搜索。

        Args:
            data: 查询向量列表
            collection_name: 集合名称
            filter: 标量过滤表达式
            limit: 返回结果数量上限
            output_fields: 需要返回的字段列表
            search_params: 搜索参数
            timeout: 超时时间
            partition_names: 分区名称列表
            anns_field: 向量字段名
            ranker: 重排序器
            **kwargs: 其他参数

        Returns:
            搜索结果列表
        """
        return super().search(
            collection_name=collection_name,
            data=data,
            filter=filter,
            limit=limit,
            output_fields=output_fields,
            search_params=search_params,
            timeout=timeout,
            partition_names=partition_names,
            anns_field=anns_field,
            ranker=ranker,
            **kwargs,
        )

    async def search_by_text(
        self,
        texts: List[str],
        collection_name: str = "rag_embeddings",
        filter: str = "",
        limit: int = 10,
        output_fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[List[Dict[str, Any]]]:
        """通过文本进行向量搜索，自动计算查询向量。

        Args:
            texts: 查询文本列表
            collection_name: 集合名称
            filter: 标量过滤表达式
            limit: 返回结果数量上限
            output_fields: 需要返回的字段列表
            **kwargs: 其他搜索参数

        Returns:
            搜索结果列表
        """
        vectors = []
        for text in texts:
            vec = await self.get_text_embeddings(text=text)
            vectors.append(vec)
        return self.search(
            data=vectors,
            collection_name=collection_name,
            filter=filter,
            limit=limit,
            output_fields=output_fields,
            **kwargs,
        )

    def get(
        self,
        ids: Union[int, str, List[int], List[str]],
        collection_name: str = "rag_embeddings",
        output_fields: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        partition_names: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """根据主键 ID 获取实体。

        Args:
            ids: 实体 ID 或 ID 列表
            collection_name: 集合名称
            output_fields: 需要返回的字段列表
            timeout: 超时时间
            partition_names: 分区名称列表
            **kwargs: 其他参数

        Returns:
            实体列表
        """
        return super().get(
            collection_name=collection_name,
            ids=ids,
            output_fields=output_fields,
            timeout=timeout,
            partition_names=partition_names,
            **kwargs,
        )

    def query(
        self,
        collection_name: str = "rag_embeddings",
        filter: str = "",
        output_fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        timeout: Optional[float] = None,
        partition_names: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """根据标量过滤表达式查询实体。

        Args:
            collection_name: 集合名称
            filter: 标量过滤表达式，例如 "subject == 'capp'"
            output_fields: 需要返回的字段列表
            limit: 返回结果数量上限
            offset: 跳过的结果数量
            timeout: 超时时间
            partition_names: 分区名称列表
            **kwargs: 其他参数

        Returns:
            符合条件的实体列表
        """
        return super().query(
            collection_name=collection_name,
            filter=filter,
            output_fields=output_fields,
            limit=limit,
            offset=offset,
            timeout=timeout,
            partition_names=partition_names,
            **kwargs,
        )

    # ------------------------------------------------------------------ #
    #  Update (更新)
    # ------------------------------------------------------------------ #

    def upsert(
        self,
        data: List[Dict[str, Any]],
        collection_name: str = "rag_embeddings",
        timeout: Optional[float] = None,
        partition_name: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """更新或插入数据。如果 ID 已存在则更新，否则插入。

        Args:
            data: 数据列表，必须包含主键 id 字段
            collection_name: 集合名称
            timeout: 超时时间
            partition_name: 分区名称
            **kwargs: 其他参数

        Returns:
            upsert 结果
        """
        return super().upsert(
            collection_name=collection_name,
            data=data,
            timeout=timeout,
            partition_name=partition_name,
            **kwargs,
        )

    def update(
        self,
        ids: Union[int, str, List[int], List[str]],
        data: Dict[str, Any],
        collection_name: str = "rag_embeddings",
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """根据 ID 更新实体字段。

        注意：Milvus 的 update 语义是先删除再插入，需要确保数据包含完整字段。

        Args:
            ids: 要更新的实体 ID 或 ID 列表
            data: 要更新的字段字典
            collection_name: 集合名称
            timeout: 超时时间
            **kwargs: 其他参数

        Returns:
            更新结果
        """
        if not isinstance(ids, list):
            ids = [ids]

        # 获取现有实体
        existing = self.get(
            ids=ids,
            collection_name=collection_name,
            output_fields=["*"],
            timeout=timeout,
        )

        if not existing:
            return {"upsert_count": 0}

        # 合并更新字段
        upsert_data = []
        for entity in existing:
            updated = {**entity, **data}
            # 移除 Milvus 内部字段
            updated.pop("_distance", None)
            updated.pop("_score", None)
            upsert_data.append(updated)

        return self.upsert(
            data=upsert_data,
            collection_name=collection_name,
            timeout=timeout,
            **kwargs,
        )

    # ------------------------------------------------------------------ #
    #  Delete (删除)
    # ------------------------------------------------------------------ #

    def delete(
        self,
        ids: Optional[Union[int, str, List[int], List[str]]] = None,
        collection_name: str = "rag_embeddings",
        filter: str = "",
        timeout: Optional[float] = None,
        partition_name: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """删除实体。可以通过 ID 或过滤条件删除。

        Args:
            ids: 要删除的实体 ID 或 ID 列表
            collection_name: 集合名称
            filter: 标量过滤表达式，用于条件删除
            timeout: 超时时间
            partition_name: 分区名称
            **kwargs: 其他参数

        Returns:
            删除结果

        Raises:
            ValueError: 同时提供了 ids 和 filter，或两者都未提供时抛出
        """
        if ids and filter:
            raise ValueError("不能同时指定 ids 和 filter，请选择一种删除方式")

        return super().delete(
            collection_name=collection_name,
            ids=ids,
            filter=filter,
            timeout=timeout,
            partition_name=partition_name,
            **kwargs,
        )

    def delete_by_filter(
        self,
        filter: str,
        collection_name: str = "rag_embeddings",
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """根据过滤条件删除实体。

        Args:
            filter: 标量过滤表达式
            collection_name: 集合名称
            timeout: 超时时间
            **kwargs: 其他参数

        Returns:
            删除结果
        """
        return self.delete(
            collection_name=collection_name,
            filter=filter,
            timeout=timeout,
            **kwargs,
        )

    # ------------------------------------------------------------------ #
    #  Embedding (嵌入向量) — 全部通过远程 requester
    # ------------------------------------------------------------------ #

    async def get_text_embeddings(self, text: str = None, texts: List[str] = None):
        """获取文本嵌入向量（远程 API）。

        Args:
            text: 单个查询文本
            texts: 批量文本列表

        Returns:
            单个向量或向量列表

        Raises:
            RuntimeError: 未配置 requester 时抛出
        """
        if self.requester is None:
            raise RuntimeError("未配置 requester")
        if text is not None:
            result = await self.requester.query_embedding(text, None)
            return result["vector"]
        if texts is not None:
            vectors = []
            for t in texts:
                result = await self.requester.query_embedding(t, None)
                vectors.append(result["vector"])
            return vectors
        raise ValueError("text 或 texts 至少提供一个")

    async def get_image_embeddings(self, image_path: str):
        """获取图像嵌入向量（远程 API）。

        Args:
            image_path: 图像文件路径

        Returns:
            图像嵌入向量

        Raises:
            RuntimeError: 未配置 requester 时抛出
        """
        if self.requester is None:
            raise RuntimeError("未配置 requester")
        result = await self.requester.query_embedding(None, image_path)
        return result["vector"]

    async def get_fused_embeddings(self, text: str, image_path: str = None):
        """获取文本和图像的融合嵌入向量（远程 API）。

        Args:
            text: 查询文本
            image_path: 图像文件路径（可选）

        Returns:
            融合嵌入向量

        Raises:
            RuntimeError: 未配置 requester 时抛出
        """
        if self.requester is None:
            raise RuntimeError("未配置 requester")
        result = await self.requester.query_embedding(text, image_path)
        return result["vector"]

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _get_embedding_dim(self) -> int:
        """获取嵌入向量维度。

        优先使用已缓存的 _dim，否则通过 requester 获取测试向量来动态检测。

        Returns:
            嵌入向量维度

        Raises:
            RuntimeError: 未配置 requester 且 dim 未知时抛出
        """
        if self._dim is not None:
            return self._dim
        if self.requester is None:
            raise RuntimeError("未配置 requester，无法检测嵌入维度。请传入 dim 参数或配置 requester")

        # 通过 requester 获取一个测试嵌入向量来检测维度
        coro = self.requester.query_embedding("dimension detection", None)
        result = self._run_sync(coro)
        vector = result["vector"]
        self._dim = len(vector) if isinstance(vector, list) else vector.shape[-1]
        return self._dim

    @staticmethod
    def _run_sync(coro):
        """在同步上下文中执行异步协程。

        兼容已有/无事件循环的场景。
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        # 已有事件循环，使用线程池避免冲突
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
