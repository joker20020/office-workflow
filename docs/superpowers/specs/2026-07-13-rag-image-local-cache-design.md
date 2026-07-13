# RAG 图片下载与本地加载设计

## 背景与根因

新后端将 RAG 图片资源端点从全局路径：

```text
GET /api/v1/rag/asset?path=...
```

调整为集合级路径：

```text
GET /api/v1/rag/collections/{name}/asset?path=...
```

检索结果中的图片 `asset_path` 现在是相对 `data/images/{collection}/` 的路径。当前插件仍调用旧全局端点，且 `rag_get_asset`、`_cache_rag_asset` 和 `_rerank_rag_candidates` 都没有传递 `collection_name`，因此无法按新契约下载图片。

当前 `_build_rag_content_blocks` 实际检查 `_local_asset_path`，但缺失时固定输出“RAG 图片候选缺少 asset_path”，导致下载失败、本地路径缺失和字段缺失被混为同一种错误。

## 在线验证证据

在 `http://192.168.1.5:8050/api/v1` 上进行了只读测试：

- 集合列表包含 `rag_embeddings` 和 `process`。
- `rag_embeddings/1783869853_0.png` 通过集合级端点返回 HTTP 200、241653 字节。
- `process/1783937076_0.png` 通过集合级端点返回 HTTP 200、241653 字节。
- 历史记录 `process/反推堵盖2.png` 的检索结果包含 `asset_path`，但集合级端点返回 HTTP 404。
- 同一历史图片通过通用端点 `GET /api/v1/images/反推堵盖2.png` 返回 HTTP 200、241653 字节。

因此集合级端点适用于新数据，通用图片端点可用于兼容尚未迁移的历史数据。

## 目标

确保每个图片候选在用于重排和传给工艺智能体前，按以下流程处理：

1. 从后端下载图片；
2. 覆盖写入插件本地 `data/img`；
3. 将本地路径写入 `_local_asset_path`；
4. 重排服务从本地文件读取图片；
5. AgentScope 多模态消息块也从同一本地文件读取图片。

不得把后端路径直接当作本地文件读取，不得因为缓存文件已存在而跳过下载。

## 下载端点策略

### 首选端点

`_APIRequester.rag_get_asset` 改为接收：

```python
rag_get_asset(collection_name: str, asset_path: str) -> bytes
```

首先请求：

```text
/rag/collections/{URL 编码后的 collection_name}/asset?path={asset_path}
```

`asset_path` 作为查询参数交给 HTTP 客户端编码，不手工拼接。

### 历史数据回退

仅当集合级端点返回 HTTP 404 时，使用 `asset_path` 的安全文件名部分请求：

```text
/images/{URL 编码后的 filename}
```

如果 `asset_path` 没有有效文件名，则不执行回退。集合级端点返回 401、403、500 等其他错误时直接报告错误，不用通用端点掩盖权限或服务故障。

如果两个端点均返回 404，`rag_get_asset` 抛出包含集合名和资源路径的 `FileNotFoundError`。候选处理层只捕获该异常，使图片候选保留文本描述和原始向量分数，但不参与图片重排，也不生成图片内容块。

## 本地缓存

`_cache_rag_asset` 改为接收集合名和相对资源路径：

```python
_cache_rag_asset(collection_name: str, asset_path: str) -> str
```

本地文件名使用：

```text
{sha256(collection_name + NUL + asset_path) 前 12 位}_{asset_path basename}
```

这样不同集合中的同名图片不会冲突。

每次调用都必须重新请求后端，并以 `wb` 模式覆盖本地文件。即使目标文件已经存在且非空，也不能直接复用。下载成功且写入完成后返回本地路径。

写入目录固定为：

```text
{requester.data_dir}/img
```

## 候选处理与重排

`_rerank_rag_candidates` 增加 `collection_name` 参数：

```python
_rerank_rag_candidates(
    task: str,
    collection_name: str,
    candidates: list[dict],
) -> list[dict]
```

图片候选的下载路径来源按以下顺序确定：

1. 非空 `asset_path`；
2. 如果 `asset_path` 缺失，使用非空 `path` 作为兼容字段。新文档规定图片 `path` 同样是集合内相对路径。

下载成功后：

- 设置 `item["_local_asset_path"]`；
- 调用重排接口时把该本地路径作为 `doc_image_path`；
- 保留原始 `asset_path` 和 `path` 供结果展示。

两个端点均无法下载时：

- 设置内部 `_asset_error`，记录包含集合名、候选 id、资源路径和 HTTP 原因的准确警告；
- 保留原始向量分数；
- 不让单个历史坏记录中断其他候选和整个工艺规划。

非 404 服务错误继续向上抛出，防止后端整体故障被静默忽略。

## 本地图片内容块

`_build_rag_content_blocks` 继续只接受本地 `_local_asset_path`：

- 使用 `open(local_path, "rb")` 读取本地字节；
- 根据本地文件扩展名设置 MIME；
- 生成 AgentScope `ImageBlock`。

如果 `_local_asset_path` 缺失：

- 始终保留文本描述块；
- 已有 `_asset_error` 时不重复打印第二条警告；
- 确实既没有 `asset_path` 也没有 `path` 时，输出“RAG 图片候选缺少可下载资源路径”；
- 不再输出误导性的“缺少 asset_path”固定文案。

## 调用链更新

工艺智能体调用链调整为：

```text
_process_agent_async
  -> _search_rag_candidates(collection_name, ...)
  -> _rerank_rag_candidates(task, collection_name, candidates)
  -> _cache_rag_asset(collection_name, asset_path)
  -> _APIRequester.rag_get_asset(collection_name, asset_path)
  -> 写入 data/img
  -> query_rerank(doc_image_path=本地路径)
  -> _build_rag_content_blocks
  -> 从本地路径读取 ImageBlock
```

主智能体独立使用的 `tool_query_knowledge_base` 只返回检索元数据，不构建图片内容块，因此保持现有行为。

## 测试

单元测试覆盖：

1. 集合名正确 URL 编码，并调用新集合级 asset 端点；
2. 集合级 404 时调用通用 `/images/{filename}`；
3. 非 404 错误不回退；
4. 两个端点都 404 时产生可识别的资源不存在结果；
5. 缓存文件已存在时仍再次请求并覆盖内容；
6. 缓存哈希同时包含集合名和资源路径；
7. 重排接收 `collection_name`，下载成功后使用本地路径；
8. 缺少 `asset_path` 时可使用文档规定的图片 `path`；
9. 历史图片无法下载时保留文本和分数，不中断其他候选；
10. 内容块通过本地文件读取，并保持 PNG/JPEG/WebP MIME；
11. 不再出现“RAG 图片候选缺少 asset_path，已仅保留文本描述”文案。

完成单元测试后，对用户指定后端执行只读集成验证：

- 下载一个集合级端点有效的新图片；
- 下载一个需要通用端点回退的历史图片；
- 确认本地文件存在、字节数大于零且内容哈希与 HTTP 响应一致；
- 重新下载并确认覆盖逻辑执行；
- 从本地文件构建 AgentScope 图片内容块。

集成验证不创建、修改或删除后端集合与实体。
