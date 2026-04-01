# AgentScope 钩子函数、消息序列化与记忆机制

> 版本: v1.1+  
> 更新日期: 2026-04-01  
> 适用: AgentScope 开发者

---

## 📚 目录

1. [概述](#1-概述)
2. [钩子函数机制](#2-钩子函数机制)
3. [消息序列化机制](#3-消息序列化机制)
4. [记忆机制](#4-记忆机制)
5. [实践示例](#5-实践示例)
6. [最佳实践](#6-最佳实践)
7. [参考资源](#7-参考资源)

---

## 1. 概述

AgentScope 提供了三套核心扩展机制：

- **钩子函数 (Hooks)**: 在智能体执行的关键节点插入自定义逻辑
- **消息序列化 (Message Serialization)**: 支持多模态数据的结构化传输与存储
- **记忆机制 (Memory)**: 管理智能体的短期和长期记忆，支持上下文感知和知识积累

这三套机制协同工作，使开发者能够：
- 监控和修改智能体行为
- 实现跨智能体的标准化通信
- 持久化会话历史
- 管理对话上下文和跨会话知识

---

## 2. 钩子函数机制

### 2.1 钩子类型

AgentScope 围绕智能体的核心函数提供钩子扩展点：

#### AgentBase 及其子类

| 核心函数 | 钩子类型 | 触发时机 |
|---------|---------|---------|
| `reply` | `pre_reply` / `post_reply` | 智能体回复消息前后 |
| `print` | `pre_print` / `post_print` | 打印消息到目标输出前后 |
| `observe` | `pre_observe` / `post_observe` | 观察环境或其他智能体消息前后 |

#### ReActAgentBase 及其子类（额外）

| 核心函数 | 钩子类型 | 触发时机 |
|---------|---------|---------|
| `_reasoning` | `pre_reasoning` / `post_reasoning` | 智能体推理过程前后 |
| `_acting` | `pre_acting` / `post_acting` | 智能体行动过程前后 |

### 2.2 钩子签名

#### Pre-Hook 签名

```python
def pre_hook_template(
    self: AgentBase | ReActAgentBase,
    kwargs: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Pre-hook 模板
    
    参数:
        self: 智能体实例
        kwargs: 目标函数的所有参数（位置参数和关键字参数）
    
    返回:
        修改后的参数字典，或 None（使用最近的非 None 返回值）
    """
    pass
```

#### Post-Hook 签名

```python
def post_hook_template(
    self: AgentBase | ReActAgentBase,
    kwargs: dict[str, Any],
    output: Any,  # 目标函数的输出
) -> Any:
    """
    Post-hook 模板
    
    参数:
        self: 智能体实例
        kwargs: 目标函数的所有参数
        output: 目标函数的输出（若无输出则为 None）
    
    返回:
        修改后的输出
    """
    pass
```

### 2.3 钩子管理

AgentScope 支持两个层级的钩子管理：

#### 实例级钩子

```python
# 注册实例钩子
agent.register_instance_hook(
    hook_type="pre_reply",
    hook_name="my_pre_reply_hook",
    hook=my_hook_function,
)

# 移除实例钩子
agent.remove_instance_hook(
    hook_type="pre_reply",
    hook_name="my_pre_reply_hook",
)

# 清除所有实例钩子
agent.clear_instance_hooks(hook_type="pre_reply")
```

#### 类级钩子

```python
# 注册类钩子（对所有实例生效）
MyAgent.register_class_hook(
    hook_type="pre_reply",
    hook_name="global_hook",
    hook=global_hook_function,
)

# 移除类钩子
MyAgent.remove_class_hook(
    hook_type="pre_reply",
    hook_name="global_hook",
)

# 清除所有类钩子
MyAgent.clear_class_hooks(hook_type="pre_reply")
```

### 2.4 执行顺序

钩子按照以下顺序执行：

```
┌─────────────────────────────────────────┐
│ 1. 类级 Pre-Hooks（按注册顺序）          │
├─────────────────────────────────────────┤
│ 2. 实例级 Pre-Hooks（按注册顺序）        │
├─────────────────────────────────────────┤
│ 3. 核心函数执行                          │
├─────────────────────────────────────────┤
│ 4. 实例级 Post-Hooks（按注册顺序）       │
├─────────────────────────────────────────┤
│ 5. 类级 Post-Hooks（按注册顺序）         │
└─────────────────────────────────────────┘
```

### 2.5 返回值处理规则

**Pre-Hooks:**
- 非 `None` 返回值传递给下一个钩子或核心函数
- 当钩子返回 `None` 时，使用最近的前置钩子的非 `None` 返回值
- 如果所有前置钩子都返回 `None`，则使用原始参数

**Post-Hooks:**
- 与 Pre-Hooks 规则相同，但作用于输出值

**⚠️ 重要：禁止在钩子内部调用核心函数（reply/speak/observe/_reasoning/_acting），否则会导致无限循环！**

---

## 3. 消息序列化机制

### 3.1 Msg 类结构

消息是 AgentScope 的核心概念，用于支持多模态数据、工具 API、信息存储/交换和提示词构建。

```python
from agentscope.message import Msg

msg = Msg(
    name="Jarvis",           # 发送者名称/身份
    role="assistant",        # 角色: "system" | "assistant" | "user"
    content="Hello!",        # 内容: str | list[ContentBlock]
    metadata=None,           # 元数据: dict | None
)
```

#### 字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| `name` | `str` | 消息发送者的名称/身份 |
| `role` | `Literal["system", "assistant", "user"]` | 发送者角色 |
| `content` | `str \| list[ContentBlock]` | 消息数据，可以是字符串或内容块列表 |
| `metadata` | `dict[str, JSONSerializableObject] \| None` | 附加元数据，不包含在提示词构建中 |

### 3.2 内容块类型

AgentScope 支持多种内容块类型：

#### 文本块

```python
from agentscope.message import TextBlock

text_block = TextBlock(
    type="text",
    text="Hello, world!"
)
```

#### 多媒体块

```python
from agentscope.message import (
    ImageBlock,
    AudioBlock,
    VideoBlock,
    Base64Source,
    URLSource,
)

# 使用 URL 源
image_block = ImageBlock(
    type="image",
    source=URLSource(
        type="url",
        url="https://example.com/image.jpg"
    )
)

# 使用 Base64 源
audio_block = AudioBlock(
    type="audio",
    source=Base64Source(
        type="base64",
        media_type="audio/mpeg",
        data="SUQzBAAAAA...",
    )
)
```

#### 思维块（推理模型）

```python
from agentscope.message import ThinkingBlock

thinking_block = ThinkingBlock(
    type="thinking",
    thinking="我正在分析用户的问题..."
)
```

#### 工具调用块

```python
from agentscope.message import ToolUseBlock, ToolResultBlock

# 工具使用
tool_use = ToolUseBlock(
    type="tool_use",
    id="343",
    name="get_weather",
    input={"location": "Beijing"},
)

# 工具结果
tool_result = ToolResultBlock(
    type="tool_result",
    id="343",
    name="get_weather",
    output="北京天气晴朗，温度 25°C",
)
```

### 3.3 序列化与反序列化

#### to_dict() 方法

```python
msg = Msg(
    name="Jarvis",
    role="assistant",
    content=[
        TextBlock(type="text", text="Hello"),
        ImageBlock(type="image", source=...)
    ]
)

# 序列化为字典
serialized = msg.to_dict()

# serialized 结构：
# {
#     "id": "emsXSPvYjucXoT4uFWhkjp",
#     "name": "Jarvis",
#     "role": "assistant",
#     "content": [
#         {"type": "text", "text": "Hello"},
#         {"type": "image", "source": {...}}
#     ],
#     "metadata": {},
#     "timestamp": "2026-03-27 14:19:52.171"
# }
```

#### from_dict() 方法

```python
# 从字典反序列化
new_msg = Msg.from_dict(serialized)

print(new_msg.name)      # "Jarvis"
print(new_msg.role)      # "assistant"
print(new_msg.content)   # [TextBlock(...), ImageBlock(...)]
```

### 3.4 属性函数

Msg 类提供便捷方法：

| 方法 | 参数 | 描述 |
|------|------|------|
| `get_text_content()` | - | 获取所有 TextBlock 的文本，用 `\n` 连接 |
| `get_content_blocks()` | `block_type` | 返回指定类型的内容块列表 |
| `has_content_blocks()` | `block_type` | 检查是否包含指定类型的内容块 |

```python
# 获取所有文本内容
all_text = msg.get_text_content()

# 获取所有图片块
images = msg.get_content_blocks("image")

# 检查是否包含工具调用
if msg.has_content_blocks("tool_use"):
    tool_blocks = msg.get_content_blocks("tool_use")
```

---

## 4. 记忆机制

AgentScope 提供了完整的记忆管理系统，包括短期记忆（Short-term Memory）和长期记忆（Long-term Memory），用于存储和管理智能体的对话历史和上下文信息。

### 4.1 记忆机制概述

AgentScope 的记忆模块负责：

- **存储消息**: 保存智能体的对话历史
- **标记管理**: 使用标签（mark）对消息进行分类和过滤
- **持久化支持**: 支持多种存储后端（内存、数据库、Redis）
- **长期记忆**: 支持跨会话的知识存储与检索

记忆系统与钩子函数、消息序列化机制协同工作，为智能体提供上下文感知和知识积累能力。

---

### 4.2 短期记忆 (Memory)

#### 4.2.1 记忆类型

AgentScope 提供三种短期记忆实现：

| 记忆类 | 描述 | 适用场景 |
|--------|------|----------|
| `InMemoryMemory` | 内存存储实现 | 开发测试、临时会话 |
| `AsyncSQLAlchemyMemory` | 异步 SQLAlchemy 数据库存储 | 生产环境、关系型数据库 |
| `RedisMemory` | Redis NoSQL 存储 | 高性能、分布式场景 |

所有记忆类继承自基类 `MemoryBase`，提供统一的 API 接口。

#### 4.2.2 核心方法

| 方法 | 描述 |
|------|------|
| `add(msgs, marks)` | 添加消息到记忆，可附加标记 |
| `get_memory(mark)` | 获取记忆内容，可按标记过滤 |
| `delete_by_mark(mark)` | 按标记删除消息 |
| `clear()` | 清空记忆内容 |
| `size()` | 获取记忆大小 |
| `state_dict()` | 导出记忆状态字典 |
| `load_state_dict()` | 从状态字典加载记忆 |

#### 4.2.3 标记系统 (Marks)

**标记**是与每条消息关联的字符串标签，用于：

- **分类**: 按类型组织消息（如 "hint"、"tool_use"、"user_input"）
- **过滤**: 快速检索特定类型的消息
- **管理**: 批量删除或更新特定标记的消息

```python
# 添加带标记的消息
await memory.add(
    Msg("system", "系统提示内容", "system"),
    marks="hint"  # 添加 "hint" 标记
)

# 检索带特定标记的消息
hint_msgs = await memory.get_memory(mark="hint")

# 删除带特定标记的消息
deleted_count = await memory.delete_by_mark("hint")
```

#### 4.2.4 使用示例

##### InMemoryMemory（内存记忆）

```python
import asyncio
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

async def in_memory_example():
    """使用 InMemoryMemory 存储消息"""
    memory = InMemoryMemory()
    
    # 添加用户消息
    await memory.add(
        Msg("Alice", "生成关于 AgentScope 的报告", "user")
    )
    
    # 添加带标记的提示消息
    await memory.add(
        Msg(
            "system",
            "<system-hint>先制定计划，收集信息并逐步生成报告。</system-hint>",
            "system"
        ),
        marks="hint"
    )
    
    # 获取带 "hint" 标记的消息
    hint_msgs = await memory.get_memory(mark="hint")
    for msg in hint_msgs:
        print(f"- {msg}")
    
    # 导出记忆状态
    state = memory.state_dict()
    
    # 按标记删除消息
    deleted_count = await memory.delete_by_mark("hint")
    print(f"已删除 {deleted_count} 条标记为 'hint' 的消息")

asyncio.run(in_memory_example())
```

##### AsyncSQLAlchemyMemory（数据库记忆）

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from agentscope.memory import AsyncSQLAlchemyMemory
from agentscope.message import Msg

async def sqlalchemy_example():
    """使用 AsyncSQLAlchemyMemory 存储到数据库"""
    # 创建异步数据库引擎
    engine = create_async_engine("sqlite+aiosqlite:///./memory.db")
    
    # 创建记忆实例（支持用户和会话管理）
    memory = AsyncSQLAlchemyMemory(
        engine_or_session=engine,
        user_id="user_1",
        session_id="session_1",
    )
    
    # 添加消息
    await memory.add(
        Msg("Alice", "生成关于 AgentScope 的报告", "user")
    )
    
    # 获取所有记忆
    all_msgs = await memory.get_memory()
    for msg in all_msgs:
        print(f"- {msg}")
    
    # 关闭连接
    await memory.close()

asyncio.run(sqlalchemy_example())
```

**使用上下文管理器（推荐）:**

```python
async def sqlalchemy_context_example():
    """使用上下文管理器自动管理会话"""
    engine = create_async_engine("sqlite+aiosqlite:///./memory.db")
    
    async with AsyncSQLAlchemyMemory(
        engine_or_session=engine,
        user_id="user_1",
        session_id="session_1",
    ) as memory:
        await memory.add(Msg("Alice", "你好！", "user"))
        msgs = await memory.get_memory()
        print(f"共有 {len(msgs)} 条消息")
    # 退出上下文时自动关闭会话

asyncio.run(sqlalchemy_context_example())
```

##### RedisMemory（Redis 记忆）

```python
import asyncio
from redis.asyncio import ConnectionPool
from agentscope.memory import RedisMemory
from agentscope.message import Msg

async def redis_example():
    """使用 RedisMemory 存储"""
    # 创建 Redis 连接池
    redis_pool = ConnectionPool(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        max_connections=10,
    )
    
    # 创建记忆实例
    memory = RedisMemory(
        connection_pool=redis_pool,
        user_id="user_1",
        session_id="session_1",
    )
    
    # 添加消息
    await memory.add(
        Msg("Alice", "生成报告", "user")
    )
    
    # 检索消息
    msgs = await memory.get_memory()
    for msg in msgs:
        print(f"- {msg}")
    
    # 关闭连接
    client = memory.get_client()
    await client.aclose()

asyncio.run(redis_example())
```

#### 4.2.5 生产环境集成

##### FastAPI + SQLAlchemy（连接池）

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from agentscope.memory import AsyncSQLAlchemyMemory
from agentscope.agent import ReActAgent
from typing import AsyncGenerator

app = FastAPI()

# 创建带连接池的数据库引擎
engine = create_async_engine(
    "sqlite+aiosqlite:///./memory.db",
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

# 创建会话工厂
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话依赖"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

@app.post("/chat")
async def chat_endpoint(
    user_id: str,
    session_id: str,
    input: str,
    db_session: AsyncSession = Depends(get_db),
):
    # 创建带数据库记忆的智能体
    agent = ReActAgent(
        name="Assistant",
        # ... 其他配置
        memory=AsyncSQLAlchemyMemory(
            engine_or_session=db_session,
            user_id=user_id,
            session_id=session_id,
        ),
    )
    
    # 处理对话
    response = await agent(Msg("user", input, "user"))
    return {"response": response.content}
```

##### FastAPI + Redis（连接池）

```python
from fastapi import FastAPI, HTTPException
from redis.asyncio import ConnectionPool
from contextlib import asynccontextmanager
from agentscope.memory import RedisMemory

# 全局 Redis 连接池
redis_pool: ConnectionPool | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理 Redis 连接池生命周期"""
    global redis_pool
    redis_pool = ConnectionPool(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        max_connections=10,
    )
    print("✅ Redis 连接已建立")
    yield
    await redis_pool.disconnect()
    print("✅ Redis 连接已关闭")

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat_endpoint(user_id: str, session_id: str, input: str):
    global redis_pool
    
    if redis_pool is None:
        raise HTTPException(status_code=500, detail="Redis 未初始化")
    
    # 创建 Redis 记忆
    memory = RedisMemory(
        connection_pool=redis_pool,
        user_id=user_id,
        session_id=session_id,
    )
    
    # ... 使用 memory 处理对话
    
    # 关闭客户端连接
    client = memory.get_client()
    await client.aclose()
    
    return {"status": "ok"}
```

---

### 4.3 长期记忆 (Long-Term Memory)

AgentScope 提供长期记忆系统，支持跨会话的知识存储和检索，实现智能体的"记忆"能力。

#### 4.3.1 长期记忆类型

| 记忆类 | 描述 | 特点 |
|--------|------|------|
| `Mem0LongTermMemory` | 基于 mem0 库的实现 | 向量存储、语义检索 |
| `ReMePersonalLongTermMemory` | 基于 ReMe 框架的实现 | 个人记忆管理、强大的检索能力 |

所有长期记忆类继承自 `LongTermMemoryBase`。

#### 4.3.2 长期记忆模式

AgentScope 提供两种长期记忆管理模式：

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| `static_control` | 开发者显式控制记忆操作 | 可控性强、确定性场景 |
| `agent_control` | 智能体通过工具调用自主管理 | 智能体自主性、动态场景 |
| `both` | 同时启用两种模式 | 混合控制 |

在 `agent_control` 模式下，系统会自动注册两个工具函数：
- `record_to_memory`: 记录记忆
- `retrieve_from_memory`: 检索记忆

#### 4.3.3 使用 Mem0 长期记忆

##### 基本使用

```python
import asyncio
import os
from agentscope.memory import Mem0LongTermMemory
from agentscope.model import DashScopeChatModel
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.message import Msg

# 创建 mem0 长期记忆实例
long_term_memory = Mem0LongTermMemory(
    agent_name="Friday",
    user_name="user_123",
    model=DashScopeChatModel(
        model_name="qwen-max-latest",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
    ),
    embedding_model=DashScopeTextEmbedding(
        model_name="text-embedding-v2",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
    ),
    on_disk=False,  # 是否持久化到磁盘
)

async def basic_usage():
    """基本使用示例"""
    # 记录记忆
    await long_term_memory.record(
        [Msg("user", "我喜欢住在民宿", "user")]
    )
    
    # 检索记忆
    results = await long_term_memory.retrieve(
        [Msg("user", "我的住宿偏好", "user")]
    )
    print(f"检索结果: {results}")

asyncio.run(basic_usage())
```

##### 与 ReActAgent 集成

```python
from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit

# 创建带长期记忆的 ReActAgent
agent = ReActAgent(
    name="Friday",
    sys_prompt="你是一个具有长期记忆能力的助手。",
    model=DashScopeChatModel(
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        model_name="qwen-max-latest",
    ),
    toolkit=Toolkit(),
    memory=InMemoryMemory(),  # 短期记忆
    long_term_memory=long_term_memory,  # 长期记忆
    long_term_memory_mode="static_control",  # 静态控制模式
)

async def record_preferences():
    """记录用户偏好"""
    msg = Msg(
        "user",
        "我去杭州旅行时，喜欢住在民宿",
        "user"
    )
    await agent(msg)

async def retrieve_preferences():
    """检索用户偏好"""
    # 清空短期记忆，测试长期记忆
    await agent.memory.clear()
    
    msg2 = Msg("user", "我有什么偏好？请简短回答。", "user")
    response = await agent(msg2)
    print(response.content)

asyncio.run(record_preferences())
asyncio.run(retrieve_preferences())
```

#### 4.3.4 使用 ReMe 长期记忆

##### 基本使用

```python
import asyncio
from agentscope.memory import ReMePersonalLongTermMemory
from agentscope.model import DashScopeChatModel
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.message import Msg

# 创建 ReMe 长期记忆实例
reme_memory = ReMePersonalLongTermMemory(
    agent_name="Friday",
    user_name="user_123",
    model=DashScopeChatModel(
        model_name="qwen3-max",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
    ),
    embedding_model=DashScopeTextEmbedding(
        model_name="text-embedding-v4",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        dimensions=1024,
    ),
)

# 使用工具函数接口
async def tool_interface_example():
    """工具函数接口示例"""
    async with reme_memory:
        # 记录记忆
        result = await reme_memory.record_to_memory(
            thinking="用户正在分享旅行偏好",
            content=[
                "我去杭州旅行时喜欢住在民宿",
                "我喜欢早上逛西湖",
                "我喜欢喝龙井茶",
            ],
        )
        print(f"记录结果: {result.get_text_content()}")
        
        # 检索记忆
        result = await reme_memory.retrieve_from_memory(
            keywords=["杭州旅行", "茶偏好"]
        )
        print(f"检索到的记忆: {result.get_text_content()}")

# 使用直接接口
async def direct_interface_example():
    """直接接口示例"""
    async with reme_memory:
        # 直接记录对话消息
        await reme_memory.record(
            msgs=[
                Msg("user", "我是一名软件工程师，喜欢远程工作", "user"),
                Msg("assistant", "了解！您是一名重视远程工作灵活性的软件工程师。", "assistant"),
            ]
        )
        
        # 直接检索记忆
        memories = await reme_memory.retrieve(
            msg=Msg("user", "我的工作偏好是什么？", "user")
        )
        print(f"检索到的记忆: {memories}")

asyncio.run(tool_interface_example())
asyncio.run(direct_interface_example())
```

##### 与 ReActAgent 集成（agent_control 模式）

```python
# 创建带 ReMe 长期记忆的 ReActAgent（agent_control 模式）
agent_with_reme = ReActAgent(
    name="Friday",
    sys_prompt=(
        "你是一个名为 Friday 的助手，具有长期记忆能力。\n\n"
        "## 记忆管理指南：\n"
        "1. **记录记忆**: 当用户分享个人信息、偏好、习惯或事实时，"
        "务必使用 `record_to_memory` 记录以备将来参考。\n"
        "2. **检索记忆**: 在回答关于用户偏好、过去信息或个人细节的问题之前，"
        "必须先调用 `retrieve_from_memory` 检查是否有相关的存储信息。\n"
        "3. **何时检索**: 当用户询问'我喜欢什么？'、'我的偏好是什么？'、"
        "'你知道我什么？'等问题时，务必先检索记忆。\n"
    ),
    model=DashScopeChatModel(
        model_name="qwen3-max",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
    ),
    toolkit=Toolkit(),
    memory=InMemoryMemory(),
    long_term_memory=reme_memory,
    long_term_memory_mode="agent_control",  # 智能体自主控制
)

async def agent_control_example():
    """智能体自主控制长期记忆示例"""
    async with reme_memory:
        # 用户分享偏好（智能体会自动记录）
        msg = Msg(
            "user",
            "我去杭州旅行时，喜欢住在民宿",
            "user"
        )
        response = await agent_with_reme(msg)
        print(f"智能体响应: {response.get_text_content()}")
        
        # 清空短期记忆
        await agent_with_reme.memory.clear()
        
        # 查询偏好（智能体会自动检索长期记忆）
        msg2 = Msg("user", "我有什么偏好？", "user")
        response2 = await agent_with_reme(msg2)
        print(f"智能体响应: {response2.get_text_content()}")

asyncio.run(agent_control_example())
```

---

### 4.4 自定义记忆实现

#### 4.4.1 自定义短期记忆

继承 `MemoryBase` 并实现以下方法：

```python
from agentscope.memory import MemoryBase
from agentscope.message import Msg
from typing import List

class CustomMemory(MemoryBase):
    """自定义记忆实现"""
    
    async def add(self, msgs: Msg | List[Msg], marks: str | List[str] = None) -> None:
        """添加消息到记忆"""
        # 实现添加逻辑
        pass
    
    async def delete(self, msg_ids: str | List[str]) -> int:
        """删除消息"""
        # 实现删除逻辑
        pass
    
    async def delete_by_mark(self, mark: str) -> int:
        """按标记删除消息"""
        # 实现按标记删除逻辑
        pass
    
    async def size(self) -> int:
        """获取记忆大小"""
        # 实现大小计算逻辑
        pass
    
    async def clear(self) -> None:
        """清空记忆"""
        # 实现清空逻辑
        pass
    
    async def get_memory(self, mark: str = None) -> List[Msg]:
        """获取记忆内容"""
        # 实现检索逻辑
        pass
    
    async def update_messages_mark(
        self,
        msg_ids: str | List[str],
        marks: str | List[str]
    ) -> None:
        """更新消息标记"""
        # 实现更新逻辑
        pass
    
    def state_dict(self) -> dict:
        """导出状态字典"""
        # 实现导出逻辑
        pass
    
    def load_state_dict(self, state: dict) -> None:
        """加载状态字典"""
        # 实现加载逻辑
        pass
```

#### 4.4.2 自定义长期记忆

继承 `LongTermMemoryBase` 并实现以下方法：

```python
from agentscope.memory import LongTermMemoryBase
from agentscope.message import Msg
from typing import List

class CustomLongTermMemory(LongTermMemoryBase):
    """自定义长期记忆实现"""
    
    # static_control 模式必须实现
    async def record(self, msgs: List[Msg]) -> None:
        """记录消息到长期记忆"""
        # 实现记录逻辑
        pass
    
    async def retrieve(self, msg: Msg) -> str | None:
        """从长期记忆检索相关信息"""
        # 实现检索逻辑
        pass
    
    # agent_control 模式必须实现
    async def record_to_memory(
        self,
        thinking: str,
        content: List[str]
    ) -> Msg:
        """工具函数：记录记忆"""
        # 实现工具函数记录逻辑
        pass
    
    async def retrieve_from_memory(
        self,
        keywords: List[str]
    ) -> Msg:
        """工具函数：检索记忆"""
        # 实现工具函数检索逻辑
        pass
```

---

### 4.5 记忆与钩子的协同

记忆机制可以与钩子函数结合，实现自动记忆管理：

```python
from agentscope.agent import AgentBase
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

class AutoMemoryAgent(AgentBase):
    """自动记忆管理的智能体"""
    
    def __init__(self, name: str, **kwargs):
        super().__init__(name=name, **kwargs)
        self.memory = InMemoryMemory()
        
        # 注册钩子：自动记录输入消息
        self.register_instance_hook(
            hook_type="pre_reply",
            hook_name="auto_record_input",
            hook=self._auto_record_input_hook
        )
        
        # 注册钩子：自动记录输出消息
        self.register_instance_hook(
            hook_type="post_reply",
            hook_name="auto_record_output",
            hook=self._auto_record_output_hook
        )
    
    async def _auto_record_input_hook(self, kwargs):
        """自动记录输入消息"""
        msg = kwargs.get("msg")
        if msg:
            await self.memory.add(msg, marks="input")
        return kwargs
    
    async def _auto_record_output_hook(self, kwargs, output):
        """自动记录输出消息"""
        if output:
            await self.memory.add(output, marks="output")
        return output
    
    async def reply(self, msg: Msg) -> Msg:
        """回复消息"""
        # 使用记忆中的上下文
        context = await self.memory.get_memory()
        # ... 基于上下文生成回复
        return Msg(self.name, "回复内容", "assistant")

# 使用示例
async def main():
    agent = AutoMemoryAgent(name="AutoBot")
    response = await agent(Msg("user", "你好", "user"))
    
    # 获取记录的所有消息
    all_msgs = await agent.memory.get_memory()
    print(f"共记录 {len(all_msgs)} 条消息")

asyncio.run(main())
```

---

### 4.6 记忆机制最佳实践

#### ✅ 应该做

- **使用标记系统**: 为不同类型的消息添加标记，便于分类和检索
- **选择合适的存储后端**: 
  - 开发测试 → `InMemoryMemory`
  - 生产环境 → `AsyncSQLAlchemyMemory` 或 `RedisMemory`
- **使用上下文管理器**: 自动管理数据库/Redis 连接
- **启用连接池**: 在生产环境中使用连接池提高性能
- **分离短期和长期记忆**: 
  - 短期记忆存储当前会话上下文
  - 长期记忆存储跨会话的知识和偏好
- **选择合适的长期记忆模式**:
  - 需要精确控制 → `static_control`
  - 需要智能体自主性 → `agent_control`
  - 混合需求 → `both`

#### ❌ 不应该做

- 在生产环境使用 `InMemoryMemory` 而不配合持久化机制
- 忽略连接管理（忘记关闭数据库/Redis 连接）
- 在钩子中执行耗时的记忆操作（影响智能体响应速度）
- 混用不同用户的记忆实例（导致数据混乱）
- 在 `agent_control` 模式下不提供清晰的记忆管理指南

#### 性能优化建议

```python
# ✅ 使用类级钩子减少重复注册
class MemoryAwareAgent(AgentBase):
    @classmethod
    def enable_auto_memory(cls):
        """启用类级自动记忆钩子"""
        cls.register_class_hook("pre_reply", "auto_mem", cls._auto_mem_hook)

# ✅ 批量操作减少 I/O
await memory.add([msg1, msg2, msg3])  # 一次性添加多条消息

# ✅ 使用标记过滤减少检索范围
hint_msgs = await memory.get_memory(mark="hint")  # 只检索提示消息

# ❌ 避免频繁的单独操作
for msg in msgs:
    await memory.add(msg)  # 低效：每次都触发 I/O
```

---

## 5. 实践示例

### 4.1 日志记录钩子

```python
import time
from agentscope.agent import AgentBase
from agentscope.message import Msg

def logging_hook(
    self: AgentBase,
    kwargs: dict[str, Any],
) -> dict[str, Any] | None:
    """记录消息内容的钩子"""
    msg = kwargs.get("msg")
    if msg:
        print(f"[{time.strftime('%H:%M:%S')}] {msg.name}: {msg.content[:50]}...")
    return None  # 不修改参数

# 注册钩子
agent.register_instance_hook(
    hook_type="pre_reply",
    hook_name="logging",
    hook=logging_hook,
)
```

### 4.2 消息修改钩子

```python
def add_timestamp_hook(
    self: AgentBase,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """为消息添加时间戳元数据"""
    msg = kwargs["msg"]
    if msg.metadata is None:
        msg.metadata = {}
    msg.metadata["timestamp"] = time.time()
    return kwargs

agent.register_instance_hook(
    hook_type="pre_reply",
    hook_name="timestamp",
    hook=add_timestamp_hook,
)
```

### 4.3 响应后处理钩子

```python
def response_validator_hook(
    self: AgentBase,
    kwargs: dict[str, Any],
    output: Any,
) -> Any:
    """验证响应格式的钩子"""
    if isinstance(output, Msg):
        # 确保响应不为空
        if not output.content:
            output.content = "抱歉，我无法生成有效的响应。"
        # 添加处理标记
        if output.metadata is None:
            output.metadata = {}
        output.metadata["validated"] = True
    return output

agent.register_instance_hook(
    hook_type="post_reply",
    hook_name="validator",
    hook=response_validator_hook,
)
```

### 4.4 消息序列化与持久化

```python
import json

# 创建消息
msg = Msg(
    name="Assistant",
    role="assistant",
    content=[
        TextBlock(type="text", text="这是回复内容"),
        ToolUseBlock(
            type="tool_use",
            id="1",
            name="search",
            input={"query": "agentscope"}
        )
    ],
    metadata={"session_id": "abc123"}
)

# 序列化
serialized = msg.to_dict()

# 持久化到文件
with open("message.json", "w", encoding="utf-8") as f:
    json.dump(serialized, f, ensure_ascii=False, indent=2)

# 从文件加载
with open("message.json", "r", encoding="utf-8") as f:
    loaded = json.load(f)

# 反序列化
restored_msg = Msg.from_dict(loaded)
```

### 4.5 完整工作流示例

```python
import asyncio
from agentscope.agent import AgentBase
from agentscope.message import Msg

class MyAgent(AgentBase):
    """自定义智能体示例"""
    
    async def reply(self, msg: Msg) -> Msg:
        """回复消息"""
        return Msg(
            name=self.name,
            role="assistant",
            content=f"收到: {msg.content}"
        )

# 创建钩子
def pre_reply_logger(self, kwargs):
    msg = kwargs["msg"]
    print(f"📥 接收消息: {msg.name} -> {msg.content}")
    return kwargs

def post_reply_logger(self, kwargs, output):
    print(f"📤 发送消息: {output.name} -> {output.content}")
    return output

# 注册类级钩子
MyAgent.register_class_hook("pre_reply", "logger", pre_reply_logger)
MyAgent.register_class_hook("post_reply", "logger", post_reply_logger)

# 使用智能体
async def main():
    agent = MyAgent(name="Bot")
    msg = Msg(name="User", role="user", content="你好！")
    
    # 注册实例级钩子
    def instance_hook(self, kwargs):
        print("🎯 实例钩子触发")
        return kwargs
    
    agent.register_instance_hook("pre_reply", "instance", instance_hook)
    
    # 执行
    response = await agent(msg)
    print(f"✅ 最终响应: {response.content}")

asyncio.run(main())
```

---

## 6. 最佳实践

### 6.1 钩子设计原则

✅ **应该做：**
- 保持钩子函数简洁、单一职责
- 在钩子中记录日志、监控性能
- 使用 `metadata` 字段传递额外信息
- 返回 `None` 时不修改参数

❌ **不应该做：**
- 在钩子中调用核心函数（避免无限循环）
- 执行耗时的阻塞操作
- 修改不可序列化的对象
- 依赖全局状态

### 6.2 消息设计原则

✅ **应该做：**
- 使用 `metadata` 存储结构化数据
- 为多模态内容使用适当的内容块
- 序列化前检查数据完整性
- 使用 `get_text_content()` 提取纯文本

❌ **不应该做：**
- 在 `content` 中存储非文本/非结构化数据
- 忽略 `role` 字段的约束
- 在钩子中直接修改消息 ID

### 6.3 性能优化

```python
# ✅ 好的做法：使用类级钩子减少重复注册
class LoggingMixin:
    @classmethod
    def enable_logging(cls):
        cls.register_class_hook("pre_reply", "log", cls._log_pre)
        cls.register_class_hook("post_reply", "log", cls._log_post)

# ❌ 避免的做法：每次创建实例都注册钩子
agent = MyAgent()
agent.register_instance_hook("pre_reply", "log", log_func)  # 性能浪费
```

---

## 7. 参考资源

### 官方文档

- [Agent Hooks 文档](https://doc.agentscope.io/tutorial/task_hook.html)
- [消息创建教程](https://doc.agentscope.io/tutorial/quickstart_message.html)
- [Memory 文档](https://doc.agentscope.io/tutorial/task_memory.html)
- [Long-Term Memory 文档](https://doc.agentscope.io/tutorial/task_long_term_memory.html)
- [AgentScope 官方文档](https://doc.agentscope.io/)

### 本地资源

- [AgentScope 初学者手册](./AgentScope_初学者手册.md)
- [项目架构文档](./ARCHITECTURE.md)

### 相关源码

- `src/agent/agent_integration.py` - 本项目的 AgentScope 集成实现
- `agentscope.message.Msg` - 消息基类
- `agentscope.agent.AgentBase` - 智能体基类

---

## 附录：常见问题

### Q1: 钩子执行顺序是否可以调整？

A: 钩子按注册顺序执行。如需特定顺序，请按预期顺序依次注册。

### Q2: 如何在钩子中访问智能体状态？

A: 通过 `self` 参数访问智能体实例：
```python
def my_hook(self, kwargs):
    agent_name = self.name
    # 访问智能体属性...
    return kwargs
```

### Q3: 消息序列化支持哪些数据类型？

A: 支持 JSON 可序列化的所有类型：
- 基本类型：str, int, float, bool, None
- 容器类型：list, dict
- 特殊类型：datetime（自动转换为字符串）

### Q4: 如何调试钩子问题？

A: 建议方法：
1. 在钩子中添加详细日志
2. 检查返回值是否为预期类型
3. 使用 `print()` 输出中间状态
4. 查看智能体的 `supported_hook_types` 属性

---

**文档版本**: 1.0  
**最后更新**: 2026-03-31  
**维护者**: Office Project Team
