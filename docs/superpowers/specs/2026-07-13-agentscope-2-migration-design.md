# AgentScope 2.0 完全迁移设计

## 目标

将当前项目从 AgentScope 1.0.17 逐文件直接迁移到稳定版
`agentscope==2.0.4`，彻底删除运行时代码中的 1.x API。第一阶段只追求现有功能
等价，不引入 AgentScope Agent Service、Workspace/Sandbox 或内置 RAG Service。

官方 `main` 分支用于核对源码和 API 方向，但实现只能使用 2.0.4 已发布接口，不能依赖
2.0.5dev 专有能力。

## 范围

迁移范围包括：

- 主 AI 助手及其模型、上下文、消息和流式回复；
- 聊天历史序列化、旧 1.x 消息兼容读取和 UI 内容块渲染；
- Toolkit、自定义函数工具和工具返回协议；
- Stateful/Stateless MCP 客户端及其生命周期；
- Skill 管理、加载、启停和 Toolkit 集成；
- Hook 到事件流或 Middleware 的迁移；
- Unity、Blender、工艺规划和 ComfyUI 子智能体；
- 工艺规划的计划工具；
- 项目依赖、锁文件和相关测试。

ProcessGen RAG 后端、插件系统的外部工具接口、UI 对外行为和数据库中的 Skill 管理记录
保持不变。

## 迁移策略

采用逐文件直接替换，不建立 AgentScope 1.x API 兼容层。唯一的旧格式兼容逻辑位于
历史记录反序列化边界，用于把已经存储的 1.x 消息转换成 2.0 消息。

迁移分为五个阶段，每个阶段必须通过自己的测试门禁后才能进入下一阶段：

1. 消息、内容块和历史持久化；
2. 核心 Agent、模型、事件流、取消和 Middleware；
3. Toolkit、MCP 和 Skill；
4. 四个 `agent_extensions` 子智能体；
5. 全库清理、依赖锁定和完整回归。

## API 映射

| AgentScope 1.x | AgentScope 2.0 |
|---|---|
| `ReActAgent` | `Agent` |
| `sys_prompt` | `system_prompt` |
| `agent(msg)` | `agent.reply(msg)` 或 `agent.reply_stream(msg)` |
| `max_iters` | `ReActConfig` |
| `InMemoryMemory` | `AgentState` 中的上下文 |
| `Msg(role=...)` | `UserMsg` / `AssistantMsg` / `SystemMsg` |
| `ImageBlock` / `AudioBlock` / `VideoBlock` | `DataBlock` |
| `ToolUseBlock` | `ToolCallBlock` |
| 1.x `ToolResponse` 原始字典内容 | 2.0 `ToolResponse` / `ToolChunk` + `TextBlock` / `DataBlock` 状态协议 |
| `register_tool_function` | `FunctionTool` 或 2.0 Toolkit 工具构造 |
| 多个 MCP Client 类 | `MCPClient` + `StdioMCPConfig` / `HttpMCPConfig` |
| `register_agent_skill` | `Toolkit(skills_or_loaders=...)` |
| `PlanNotebook` | `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` |
| Agent Hook | `MiddlewareBase` 或原生事件流 |

## 消息与历史记录

UI 输入先转换为 `UserMsg`。纯文本使用 `TextBlock`，图片、音频和视频统一使用带正确
MIME 类型的 `DataBlock`。主 Agent 的回复通过 `reply_stream()` 产生事件；事件同时发送给
UI，并通过 `AssistantMsg.append_event()` 累积成完整消息。完成后只使用 Pydantic
`model_dump()` 结果持久化。

旧消息兼容读取遵循以下规则：

- 根据旧 `role` 选择 `UserMsg`、`AssistantMsg` 或 `SystemMsg`；
- 将 `image`、`audio`、`video` 内容块转换成 `DataBlock`；
- 将 `tool_use` 转换成 `ToolCallBlock` 并补齐 2.0 要求的 ID 和状态；
- 对缺失字段尽量降级为文本内容；
- 无法无损转换时在 metadata 中记录迁移警告，不静默丢弃整段会话；
- 新写入数据只允许 2.0 格式。

## 模型与 Agent

`ReActAgent` 直接替换为 `Agent`。OpenAI 兼容服务使用
`OpenAICredential` 和 `OpenAIChatModel`；DeepSeek、DashScope 使用各自的 Credential
和 Model。Formatter 放在 Model 配置中，单 Agent 使用默认 formatter，需要保留多 Agent
语义时显式使用对应 MultiAgent formatter。

主助手使用 `reply_stream()`，插件子智能体在不需要 UI 流式更新时使用 `reply()`。
原 `max_iters` 映射到 `ReActConfig`。原短期 Memory 数据迁入 `AgentState` 的上下文，
不再创建 `InMemoryMemory`。

运行中断通过取消当前 asyncio task 实现。Agent 暂停在用户确认或外部执行状态时，使用
`UserInterruptEvent` 清理挂起调用。取消产生的部分消息保留并标记 interrupted，不作为普通
运行异常展示。

## Hook 与 Middleware

删除所有 `register_instance_hook`、`register_class_hook`、`pre_reply`、`post_reply` 和
`post_print` 使用。

当前生产代码中的 `post_print` 只承担 UI 流式输出，因此直接由 `reply_stream()` 事件替代，
不实现成 Middleware。`AgentIntegration` 映射文本、思考、工具调用、工具结果、回复结束、
确认和中断事件，并向 UI 发出项目内部的块更新。

真正修改 Agent 行为的逻辑才实现 `MiddlewareBase`：

- 完整回复前后处理使用 `on_reply`；
- 单轮推理使用 `on_reasoning`；
- 工具调用使用 `on_acting`；
- 模型调用使用 `on_model_call`；
- 动态系统提示词使用 `on_system_prompt`。

Middleware 顺序遵循洋葱模型：列表靠前者位于外层，前置逻辑按列表顺序执行，后置逻辑
反向执行。原 Hook 测试全部重写为项目实际使用的事件和 Middleware 测试。

## Toolkit、工具与权限

工具函数改用 2.0 `FunctionTool` 或等价的 Toolkit 构造方式。工具结果使用 2.0 的流式
工具输出协议，插件对外返回的结构化成功/失败格式保持不变。

只将项目中已经启用和允许的插件工具、MCP 和 Skill 放入 Toolkit，不额外引入通用 Bash
或任意文件工具。现有 `PermissionManager` 继续作为工具暴露边界。为保持当前非交互式自动
执行行为，AgentScope 使用受限 Toolkit 和 BYPASS 权限模式；BYPASS 只作用于已筛选的工具
集合。工艺文件写入仍限制到当前工作目录或配置的数据目录。

测试必须证明禁用的插件、MCP 和 Skill 不会进入 Toolkit。

## MCP

所有旧 MCP 客户端统一替换成 `MCPClient`：

- STDIO 使用 `StdioMCPConfig`；
- HTTP 使用 `HttpMCPConfig`；
- Stateful 客户端先 `connect()`，再传入 `Toolkit(mcps=[...])`；
- Stateless HTTP 客户端不建立持久生命周期；
- `enable_tools` 和 `disable_tools` 保留服务级工具过滤；
- Stateful 客户端必须在 `try/finally` 中关闭。

单个 MCP 连接失败时，日志必须包含服务器名称，已经连接的资源必须关闭；其他独立 MCP
服务器可以继续加载。

## Skill

保留现有 `SkillManager`、数据库记录、启停状态和设置界面。删除
`toolkit.register_agent_skill()`。创建 2.0 Toolkit 时，将启用的 Skill 路径通过
`skills_or_loaders` 传入；需要扫描父目录时使用 `LocalSkillLoader`。

Skill 继续采用包含 `SKILL.md` 的目录格式。Skill 增删、路径修改或启停后，重建主 Agent
的 Toolkit。第一阶段保持现有作用域：用户配置的 Skill 只加载到主助手，不自动注入四个
插件子智能体。

无效 Skill 路径或不合法 `SKILL.md` 只导致该 Skill 被跳过并记录明确错误，不能阻止主
Agent 初始化。

## 工艺规划

删除 `PlanNotebook`，在工艺规划 Agent 的 Toolkit 中注册 `TaskCreate`、`TaskGet`、
`TaskList`、`TaskUpdate`。计划状态保存在 `agent.state.tasks_context`，由 2.0 AgentState
负责序列化。现有工艺提示词和 JSON 文件输出契约保持不变。

## 子智能体

Unity、Blender、工艺规划和 ComfyUI 逐个迁移，每个子智能体都直接构造 2.0 Agent、
Credential、Model、Toolkit 和 MCP。子智能体输出继续使用结构化 Markdown，让主助手获得
具体内容、生成文件路径、状态和错误信息。

每个子智能体必须在独立测试通过后才迁移下一个。资源创建后无论正常、异常或取消都必须
关闭 Stateful MCP 客户端。

## 错误处理

- `reply_stream()` 异常时保留已累积的部分 AssistantMsg，并向 UI 发出错误；
- 用户取消与普通错误分开处理；
- 模型、Toolkit 和消息验证错误包含具体配置或字段上下文；
- 插件工具继续返回结构化失败结果，不把 Python 异常对象直接交给主 Agent；
- Stateful MCP 和子智能体资源使用 `try/finally` 清理；
- 历史消息和 Skill 的单项错误不得阻止其他有效项目加载。

## 测试策略

1. 在隔离环境安装 `agentscope==2.0.4`，先探测计划中使用的构造函数、字段和返回类型；
2. 重写消息序列化测试，覆盖文本、多模态、工具块和旧历史转换；
3. 重写流式 Hook 测试，覆盖事件到 UI 的映射、消息重建、Middleware 顺序和错误传播；
4. 测试模型 Credential、Agent 构造、`reply()`、`reply_stream()` 和取消；
5. 使用临时 MCP 服务器或假客户端验证 Stateful/Stateless 生命周期和工具过滤；
6. 使用临时 `SKILL.md` 验证加载、禁用、错误目录和 Toolkit 重建；
7. 逐个验证四个插件子智能体的构造、工具调用、结果提取和清理；
8. 运行完整项目测试；
9. 运行语法、静态搜索、锁文件和工作区范围检查。

## 完成标准

- `pyproject.toml` 精确固定 `agentscope==2.0.4`；
- `uv.lock` 解析到 2.0.4；
- 主助手文本、多模态、流式显示、中断、历史记录、插件工具、MCP 和 Skill 功能等价；
- 四个子智能体及 ProcessGen RAG 功能等价；
- 旧 1.x 历史记录仍可读取，新记录只使用 2.0 格式；
- 完整测试通过；
- 运行时代码中不存在 `ReActAgent`、`InMemoryMemory`、旧 Hook 注册、
  `register_agent_skill`、旧 MCP Client、`ImageBlock`、`AudioBlock`、`VideoBlock`、
  `PlanNotebook` 或把原始字典作为内容块传给 `ToolResponse` 的 1.x 用法。

## 参考资料

- https://github.com/agentscope-ai/agentscope/tree/main
- https://pypi.org/project/agentscope/
- https://docs.agentscope.io/versions/2.0.5dev/en/others/change-log
- https://docs.agentscope.io/versions/2.0.5dev/en/building-blocks/agent
- https://docs.agentscope.io/versions/2.0.5dev/en/building-blocks/message-and-event
- https://docs.agentscope.io/versions/2.0.5dev/en/building-blocks/model
- https://docs.agentscope.io/versions/2.0.5dev/en/building-blocks/tool
- https://docs.agentscope.io/versions/2.0.5dev/en/building-blocks/plan
- https://docs.agentscope.io/versions/2.0.5dev/en/building-blocks/middleware
- https://docs.agentscope.io/versions/2.0.5dev/en/building-blocks/permission-system
