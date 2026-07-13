# 主 AI 助手混合 RAG 工具设计

## 目标

扩展 `agent_extensions` 已注册给主 AI 助手的 `tool_query_knowledge_base`，使其在保持文本检索兼容性的同时支持文本与图片混合检索。

## 接口

现有参数 `query`、`collection_name` 和 `limit` 保持不变，新增可选参数 `image_path: str = ""`。

- `image_path` 为空时调用 `_APIRequester.rag_search_text`。
- `image_path` 非空时调用 `_APIRequester.rag_search_mixed`，同时提交 `query` 与图片。
- 不增加第二个工具，避免主助手面对语义重复的工具选择。

## 返回与错误

返回格式继续为 JSON 文本列表，每项包含 `id`、`score`、`text`、`path`、`type`、`subject` 和 `asset_path`。图片不存在、后端错误或响应格式错误沿用工具层的 `知识库查询失败: ...` 错误响应。

本次不把检索结果图片编码进工具响应，也不增加集合或实体管理工具。

## 测试

- 验证工具仍包含在 `get_all_tools()` 中并注册给主助手。
- 验证无图时调用文本检索，且不调用混合检索。
- 验证有图时调用混合检索，且不调用文本检索。
- 验证 `image_path` 从同步工具入口传递到异步实现。
- 验证缺失图片产生清晰失败响应。
