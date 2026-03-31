# AgentScope 钩子函数与消息序列化机制

> 版本: v1.0+  
> 更新日期: 2026-03-31  
> 适用: AgentScope 开发者

---

## 📚 目录

1. [概述](#1-概述)
2. [钩子函数机制](#2-钩子函数机制)
3. [消息序列化机制](#3-消息序列化机制)
4. [实践示例](#4-实践示例)
5. [最佳实践](#5-最佳实践)
6. [参考资源](#6-参考资源)

---

## 1. 概述

AgentScope 提供了两套核心扩展机制：

- **钩子函数 (Hooks)**: 在智能体执行的关键节点插入自定义逻辑
- **消息序列化 (Message Serialization)**: 支持多模态数据的结构化传输与存储

这两套机制协同工作，使开发者能够：
- 监控和修改智能体行为
- 实现跨智能体的标准化通信
- 持久化会话历史

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

## 4. 实践示例

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

## 5. 最佳实践

### 5.1 钩子设计原则

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

### 5.2 消息设计原则

✅ **应该做：**
- 使用 `metadata` 存储结构化数据
- 为多模态内容使用适当的内容块
- 序列化前检查数据完整性
- 使用 `get_text_content()` 提取纯文本

❌ **不应该做：**
- 在 `content` 中存储非文本/非结构化数据
- 忽略 `role` 字段的约束
- 在钩子中直接修改消息 ID

### 5.3 性能优化

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

## 6. 参考资源

### 官方文档

- [Agent Hooks 文档](https://doc.agentscope.io/tutorial/task_hook.html)
- [消息创建教程](https://doc.agentscope.io/tutorial/quickstart_message.html)
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
