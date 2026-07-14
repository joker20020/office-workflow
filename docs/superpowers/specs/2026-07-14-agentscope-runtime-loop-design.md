# AgentScope 2.0 长期异步运行时设计

## 背景与决策

AgentScope 2.0.4 的 stateful `MCPClient.connect()` 会创建长期存活的
`AsyncExitStack`、`ClientSession` 和 AnyIO task group。连接成功只表示会话已经建立，
不表示后台传输任务已经结束。因此，使用临时 event loop 执行 `connect()` 后立即关闭
loop，会留下表面已连接、实际不可用且无法在原上下文中关闭的客户端。

本项目采用一个主助手专属的长期异步运行时线程。stateful MCP 的连接、MCP 工具调用、
Agent `reply_stream()`、parked reply cleanup 和 MCP 关闭全部在该线程的同一个 event loop
中执行。现有同步和异步公共 API 保持不变。

不采用以下方案：

- 每次初始化创建临时 loop：会破坏 stateful MCP 的长期异步资源。
- 每轮聊天重新连接 MCP：启动成本高，会丢失 stateful 会话语义，并复杂化失败清理。
- 禁用 stdio/stateful MCP：不满足功能等价迁移。

## 组件边界

新增一个小型 `AgentAsyncRuntime` 组件，独立负责：

- 幂等启动一个命名后台线程和 event loop；
- 将 coroutine 线程安全地提交到该 loop；
- 为同步调用提供阻塞等待结果的接口；
- 为异步调用提供可在调用者 loop 中 await 的桥接接口；
- 在 shutdown 时先执行运行时清理 coroutine，再停止 loop、join 线程并关闭 loop。

该组件不理解 Agent、MCP、历史记录或 UI，只管理线程、loop 和任务提交。它不提供
fire-and-forget 业务操作；需要观察结果的操作必须返回 future 或被 await。

`AgentIntegration` 继续拥有 Agent、Toolkit、MCP clients、历史和 streaming callbacks，
但所有会触碰 AgentScope 异步对象的操作都通过 `AgentAsyncRuntime` 执行。

## 初始化与 MCP 生命周期

`initialize()` 保持同步接口，内部在长期 runtime loop 上执行一个原子初始化 coroutine：

1. 取消并收尾现有 active/parked reply；
2. 在原 runtime loop 上关闭旧 stateful MCP clients；
3. 清除旧 `_agent`、`_toolkit`、MCP ownership，并先将 `_initialized=False`；
4. 按 manager 顺序创建 enabled MCP clients；
5. 在 runtime loop 上连接 stateful clients，stateless clients 不 connect；
6. 单个服务器失败时记录名称，清理该失败 client，并继续其他服务器；
7. 使用成功 clients 构造 `Toolkit(tools=..., mcps=...)` 和 Agent；
8. 只有完整 runtime 构造成功后才发布 `_agent`、`_toolkit`、`_mcp_clients` 并设置
   `_initialized=True`。

如果模型、Toolkit 或 Agent 构造失败，当前初始化过程中成功连接的所有 stateful clients
必须在同一个 runtime loop 上关闭，并保持 `_initialized=False`、`_agent=None`、
`_toolkit=None`。不得继续暴露旧 Agent 或已关闭的旧 MCP。

## 聊天、事件和中断

同步 `chat()` 将完整聊天 coroutine 提交给 runtime 并等待结果，不再为每轮聊天创建
event loop。异步 `chat_async()` 提交同一个 coroutine，并通过线程安全 future 桥接到调用者
event loop；AgentScope 的实际执行仍发生在长期 runtime loop。

`_consume_reply_stream()`、streaming callback 顺序、AssistantMsg 累积和历史单次写入契约
保持不变。同步与异步调用返回相同的文本或兼容错误字符串。

active reply task 是 runtime loop 上的真实 task。`interrupt()` 使用 runtime loop 的
`call_soon_threadsafe(task.cancel)`，并保留现有 cancellation reservation，防止重复 cancel。
AgentScope 将取消转换为 `ReplyEndReason.INTERRUPTED` 事件，partial assistant 内容继续被
累积并只持久化一次。

`RequireUserConfirmEvent` / `RequireExternalExecutionEvent` 只保存 parked `reply_id`。
parked cleanup 直接提交到同一个 runtime loop，并发送
`UserInterruptEvent(reply_id=...)`。不再创建专用 parked loop 或 parked loop thread；原有复杂
handoff 状态应在测试保护下删除。

## reset、会话切换与 shutdown

`reset()` 保持同步接口，在 runtime loop 上：

- 取消并等待 active/parked work 收尾；
- 关闭并清空 stateful MCP ownership；
- 清空历史与 AgentState context；
- 将 runtime 标记为未初始化，避免保留引用已关闭 MCP 的 Toolkit 继续聊天。

用户重新选择模型或配置后可再次调用 `initialize()`。Task 5 的统一 rebuild 将在后续恢复
无需完整初始化的动态 Toolkit 更新；本任务不构造引用已关闭 MCP 的半可用 runtime。

`switch_session()` 对 AgentState 的发布也通过 runtime loop 执行，避免与正在执行的 reply
并发写 state。失败切换仍保持原 state 不变。

`shutdown()` 的顺序是：取消 reply → parked cleanup → 关闭 stateful MCP → 清 Agent/Toolkit
状态 → 停止 runtime loop → join 线程 → 关闭 loop。重复 shutdown 必须幂等。

不得从 runtime 线程同步等待自身 future；组件检测到这种调用时应直接执行对应 async 路径
或抛出清晰错误，不能死锁。

## 错误处理

- 单个 MCP factory/connect/close 错误包含服务器或 client 名称，不阻止独立服务器处理。
- 初始化级错误不会暴露旧 runtime；所有本轮已连接资源在同一 loop 清理。
- runtime thread 启动失败、提交到已停止 runtime、清理超时均返回明确错误并记录上下文。
- 用户中断与普通错误继续分离；中断不生成通用错误回调。
- callback 异常仍按 callback 隔离，不终止 event stream。

## 测试策略

1. `AgentAsyncRuntime` 启动、同步提交、异步桥接、禁止自等待、停止和幂等测试。
2. loop-sensitive fake MCP 记录 `connect()`、`list_tools()`/tool call、`close()` 的 running loop，
   断言全部是同一长期 loop，且运行期间 loop 未关闭。
3. 同步和异步 chat 都断言 Agent reply 与 MCP session 位于同一个 runtime loop。
4. reinitialize 成功、reinitialize 失败、部分 MCP 失败和初始化构造失败测试。
5. reset 后 `_initialized=False`，不能使用引用已关闭 MCP 的旧 Agent；资源全部关闭。
6. active cancellation、parked cleanup、partial persistence 和重复 interrupt 回归测试。
7. shutdown 并发与幂等测试，断言没有存活线程、未关闭 loop 或重复 close。
8. 完整 Plan 02/03 相关测试与旧 API 静态扫描。

## 范围

本修订允许修改或新增：

- `src/agent/agent_integration.py`
- `src/agent/async_runtime.py`
- 对应的 runtime、Agent、streaming、MCP 生命周期测试

不修改 MCP 数据库 schema、UI 公共接口、模型 provider 默认值、Skill/permission 筛选规则或
插件子智能体。后续 Plan 03 Tasks 4-5 在该长期 runtime 基础上继续。

## 完成标准

- stateful MCP connect、工具发现/调用和 close 处于同一个仍运行的 event loop；
- `chat()` / `chat_async()` API 和返回语义不变；
- active/parked interruption 与 partial history 契约保持；
- initialize/reset/shutdown 不暴露引用已关闭 MCP 的旧 runtime；
- 无临时 MCP connect loop、无专用 parked loop thread、无遗留异步线程或 loop；
- 新增和既有相关测试通过，独立任务复审批准。
