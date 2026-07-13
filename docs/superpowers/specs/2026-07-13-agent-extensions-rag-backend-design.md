# Agent Extensions RAG 后端统一设计

## 目标

将 `agent_extensions` 插件的全部 RAG 能力迁移到 ProcessGen 新后端的 `/api/v1/rag/*` HTTP 接口。插件、辅助脚本和演示代码不再直接连接 Milvus，不再生成或传递向量，也不再依赖 `pymilvus`。

## 范围

- 扩展 `plugins/agent_extensions/__init__.py` 中现有 `_APIRequester`，不新增独立 RAG 客户端。
- 迁移工艺规划和知识库查询工具。
- 迁移 RAG 数据填充脚本，使其上传原始文件并由后端负责分块、嵌入和存储。
- 删除 `MoyuClient`、Milvus CRUD 演示、相关测试及 `pymilvus` 依赖。
- 删除后端不支持的原始向量插入、upsert、update、按过滤表达式查询和删除能力，不提供兼容占位方法。
- 保留现有嵌入、重排、普通图片管理和 ComfyUI 请求功能。
- 保留工作区中已有的未提交修改，包括最新后端文档和图片生成提示词修改。

## 配置

插件只使用 `RAG_BASE_URL` 定位 ProcessGen 后端，默认值为 `http://localhost:8050/api/v1`。`_APIRequester` 初始化时移除 URL 末尾的 `/`，避免路径拼接产生双斜线。

删除插件及辅助脚本中的 `MILVUS_BASE_URL`、`MILVUS_URI` 等 Milvus 配置入口。

## HTTP 客户端设计

在 `_APIRequester` 中加入与后端文档一一对应的异步方法：

- 创建、列出和删除集合；
- 上传 Markdown、TXT 或 PDF 文本文件；
- 批量上传图片及一一对应的描述；
- 文本检索；
- 图片检索；
- 通过 `POST /api/v1/rag/collections/{name}/search/mixed` 执行文本与图片混合检索；
- 分页浏览实体；
- 按实体 ID 删除；
- 通过 `/api/v1/rag/asset` 获取图片资源。

集合名和资源路径作为 URL 路径或查询参数传递，不手工拼入未经编码的查询字符串。文件上传使用上下文管理器及时关闭文件，图片 MIME 类型按扩展名确定。

## 工艺规划数据流

`_process_agent_async` 不再计算查询向量，也不创建数据库客户端。

1. 无 `image_path` 时调用文本检索接口。
2. 有 `image_path` 时调用混合检索接口，同时提交任务文本和图片。
3. 从后端通用搜索响应的 `results` 获取候选项。
4. 对文本候选调用文本到文本 rerank；对图片候选先通过 `asset_path` 下载图片，再调用文本到图片 rerank。
5. rerank 成功时使用重排分数；单条重排失败时记录警告并保留该候选的原始 RAG `score`。
6. 按最终分数降序排序并只保留前 `limit` 条。
7. 按实际结果数量构建 AgentScope 消息，避免结果少于 `limit` 时越界。
8. 图片候选缺少 `asset_path` 时保留描述文本，跳过图片块并记录警告。

图片缓存可继续写入插件现有 `data/img` 目录，但图片来源必须是后端 `/api/v1/rag/asset`，不得再依据数据库绝对路径或旧图片文件名接口推断资源位置。

## 知识库查询数据流

`_query_knowledge_base_async` 直接调用后端文本检索接口，返回每条候选的 `id`、`score`、`text`、`path`、`type`、`subject` 和 `asset_path`。该流程不调用 embedding、rerank 或任何数据库客户端。

## 数据填充与演示

`populate_rag.py` 使用 `_APIRequester`：

1. 删除同名旧集合并重新创建；
2. 将完整 Markdown、TXT 或 PDF 文件上传到文本接口；
3. 将图片与描述批量上传到图片接口；
4. 使用文本或混合检索展示结果。

分块、嵌入、向量维度和底层存储全部由后端负责。脚本不再导入 `MoyuClient`、`TextProcessor` 或项目根部的另一套 `APIRequester`。

删除 `moyus_client.py` 和 `demo_moyu_client.py`，避免继续公开后端没有提供的旧 Milvus CRUD 语义。

## 错误处理

- 所有新增 HTTP 方法验证状态码；失败异常包含操作名称、HTTP 状态码和后端响应正文。
- 搜索响应必须包含列表类型的 `results`，否则抛出明确的后端响应格式错误。
- 上传前验证文件存在、图片数量与描述数量一致。
- 单个候选 rerank 失败不终止整个规划；集合检索或资源请求整体失败则向上抛出，由工具层转换为用户可读错误。
- 不吞掉文件打开错误、网络超时或 JSON 解析错误。

## 测试与验收

使用测试替身隔离 HTTP，不要求真实 ProcessGen 或 Milvus 服务。

- 验证 RAG 方法使用正确的 URL、HTTP 方法、查询参数、JSON 和 multipart 字段。
- 验证文本、图片、混合搜索响应的解析和异常响应。
- 验证工艺规划在无图时调用文本检索、有图时调用混合检索。
- 验证图片通过 `asset_path` 获取，rerank 排序正确，结果不足 `limit` 不越界，单条 rerank 失败按原始分数降级。
- 验证知识库查询直接返回后端结果。
- 替换并删除所有以 Milvus CRUD 为中心的旧测试。
- 运行相关测试和全量测试。
- 最终搜索插件、测试和项目依赖，确保不存在 `pymilvus`、`MilvusClient`、`MoyuClient`、`MILVUS_BASE_URL` 或其他数据库直连入口。

## 非目标

- 不修改 ProcessGen 后端实现。
- 不重构 `_APIRequester` 现有的 embedding、rerank、图片管理或 ComfyUI 方法。
- 不为新后端尚未提供的 CRUD 能力增加客户端模拟或兼容层。
