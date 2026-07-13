# 子智能体工具超时优化设计

## 背景与根因

`plugins/agent_extensions/__init__.py` 中的同步转异步包装器 `_run_async` 在已有事件循环中创建工作线程，并使用固定的 `310` 秒执行 `thread.join()`。当图片智能体连续生成多张图片时，后台协程仍在正常工作，但调用方在约五分钟后提前返回“执行超时或无返回结果”。日志显示工具返回失败前，`data/img` 仍持续产生图片文件，证明退出来自包装器总超时，而不是图片生成已经停止。

此外：

- 单张 ComfyUI `/text-to-image` HTTP 请求固定为 `300` 秒；
- Unity `HttpStatefulClient` 未显式传入超时，因此使用 AgentScope 的 `timeout=30` 秒和 `sse_read_timeout=300` 秒默认值；
- `_run_async` 当前用 `result[0] is None` 同时表示“线程超时”和“协程正常返回 None”，错误原因不明确。

## 目标

提高长时间工具链的默认执行上限，并允许部署环境通过环境变量调整，使批量图片生成和 Unity MCP 操作不会在仍正常运行时过早返回。

## 范围

本次只修复问题 2：工具运行超时。

- 修改 `plugins/agent_extensions/__init__.py` 的超时读取、`_run_async`、ComfyUI 请求和 Unity MCP 客户端配置。
- 在 `config/.env.example` 记录新环境变量。
- 在 `tests/test_agent_extensions_rag.py` 增加回归测试。
- 不修改 RAG 搜索、`asset_path`、图片下载或本地图片加载逻辑；问题 1 等待新后端 API 端点后单独处理。

## 配置

增加三个可选环境变量：

| 环境变量 | 默认值 | 用途 |
| --- | ---: | --- |
| `AGENT_TOOL_TIMEOUT_SECONDS` | `1800` | 一个公开子智能体工具调用的总等待时间，默认 30 分钟 |
| `IMAGE_REQUEST_TIMEOUT_SECONDS` | `600` | 单张 ComfyUI 图片 HTTP 请求时间，默认 10 分钟 |
| `UNITY_MCP_TIMEOUT_SECONDS` | `600` | Unity MCP 建连、普通请求和流读取时间，默认 10 分钟 |

所有值必须是正数。环境变量缺失、无法转为数字、为零或为负数时，记录警告并使用对应默认值，避免配置错误导致插件导入失败。

## 超时读取

增加内部函数 `_get_timeout_seconds(name, default)`：

1. 每次调用时读取环境变量，便于测试和运行时配置；
2. 接受正整数或正浮点数；
3. 返回 `float`；
4. 无效值回退到默认值并记录警告。

不在模块导入时直接执行 `int(os.environ[...])`，防止错误配置使整个插件无法加载。

## `_run_async` 行为

在已有事件循环的分支中：

1. 使用 `AGENT_TOOL_TIMEOUT_SECONDS`，默认等待 `1800` 秒；
2. `join()` 返回后先检查 `thread.is_alive()`；
3. 线程仍存活时返回明确文本：`(执行超时：工具运行超过 N 秒)`；
4. 线程已结束且捕获异常时重新抛出原始异常；
5. 线程已结束且结果为 `None` 时返回 `(工具执行完成但无返回结果)`；
6. 其他情况返回协程结果。

本次不尝试强制杀死 Python 工作线程，因为线程终止不安全且可能中断文件写入。提高默认上限后，正常批处理应在等待期内完成；达到上限时仍允许后台线程自行收尾，但调用方会得到准确的超时原因。

无运行中事件循环时继续直接使用 `asyncio.run(coro)`，不增加额外总超时。

## ComfyUI 与 Unity

- `text_to_image` 创建 `aiohttp.ClientTimeout(total=...)` 时读取 `IMAGE_REQUEST_TIMEOUT_SECONDS`。
- 创建 Unity `HttpStatefulClient` 时同时传入：
  - `timeout=UNITY_MCP_TIMEOUT_SECONDS`
  - `sse_read_timeout=UNITY_MCP_TIMEOUT_SECONDS`
- Blender 使用的 `StdIOStatefulClient` 在当前 AgentScope 版本中不提供对应超时构造参数，因此仅受外层 30 分钟工具总等待时间保护，不传入不支持的参数。

## 文档

在 `config/.env.example` 中加入三项配置及中文注释，说明单位为秒和默认值。真实 `config/.env` 不修改，避免覆盖用户环境配置。

## 测试

测试覆盖：

1. 三个环境变量缺失时分别返回 `1800`、`600`、`600`；
2. 合法环境变量覆盖默认值；
3. 非数字、零和负数回退到默认值；
4. `_run_async` 在工作线程超时后返回明确的超时文本；
5. `_run_async` 区分正常返回 `None`；
6. ComfyUI 请求收到配置后的 `aiohttp.ClientTimeout.total`；
7. Unity `HttpStatefulClient` 收到两个 600 秒超时参数；
8. 现有 RAG 与子智能体提示词测试继续通过。

测试使用短暂睡眠和 mock 客户端，不连接 ComfyUI、Unity、后端或外部模型。
