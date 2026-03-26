# AgentScope 框架初学者手册

> **版本**: v1.0.17  
> **更新日期**: 2026年3月  
> **适用人群**: 零基础初学者、Python开发者、AI应用开发者

---

## 📚 目录

1. [什么是 AgentScope?](#1-什么是-agentscope)
2. [核心特性](#2-核心特性)
3. [环境准备与安装](#3-环境准备与安装)
4. [核心概念详解](#4-核心概念详解)
5. [快速入门: Hello AgentScope](#5-快速入门-hello-agentscope)
6. [核心组件深入](#6-核心组件深入)
   - 6.5 高级功能详解
     - 6.5.1 Tool (工具系统)
     - 6.5.2 MCP (Model Context Protocol)
     - 6.5.3 Skill (智能体技能)
     - 6.5.4 Middleware (中间件)
     - 6.5.5 A2A (Agent-to-Agent) 协议
     - 6.5.6 Realtime Agent (实时智能体)
7. [多智能体系统](#7-多智能体系统)
8. [实战示例](#8-实战示例)
9. [最佳实践与反模式](#9-最佳实践与反模式)
10. [生产部署检查清单](#10-生产部署检查清单)
11. [常见问题 FAQ](#11-常见问题-faq)
12. [资源与参考](#12-资源与参考)

---

## 1. 什么是 AgentScope?

### 1.1 定义

**AgentScope** 是一个**生产就绪、易用的多智能体框架**,专为构建可扩展、结构化的 AI 智能体应用而设计。它由阿里巴巴达摩院团队开发并开源,采用 Apache-2.0 许可证。

### 1.2 核心理念

AgentScope 的设计理念围绕以下几点:

- **简洁性 (Simple)**: 5 分钟即可上手,内置 ReAct 智能体、工具、技能等
- **可扩展性 (Extensible)**: 支持丰富的生态集成,包括 MCP、A2A 协议
- **生产就绪 (Production-ready)**: 支持本地部署、云端无服务器、K8s 集群等多种部署方式

### 1.3 与其他框架的区别

| 特性 | AgentScope | LangChain | AutoGen |
|------|-----------|-----------|---------|
| 多智能体编排 | ✅ 原生支持 | ⚠️ 需扩展 | ✅ 原生支持 |
| ReAct 范式 | ✅ 内置 | ✅ 支持 | ⚠️ 需实现 |
| 状态管理 | ✅ 完整 | ⚠️ 基础 | ✅ 支持 |
| 实时交互 | ✅ 支持 | ⚠️ 有限 | ❌ 不支持 |
| 部署支持 | ✅ 全栈 | ⚠️ 部分 | ⚠️ 有限 |
| 学习曲线 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 2. 核心特性

### 2.1 智能体能力

- **ReAct 智能体**: 推理与行动结合,支持工具调用
- **实时控制 (Realtime Steering)**: 用户可随时中断智能体回复
- **并行工具调用**: 同时执行多个工具
- **结构化输出**: 支持 Pydantic 模型验证
- **MCP 协议**: 原生支持 Model Context Protocol
- **A2A 协议**: 支持 Agent-to-Agent 通信

### 2.2 记忆系统

- **短期记忆 (TemporaryMemory)**: 临时会话存储
- **长期记忆 (Long-Term Memory)**: 持久化知识库
- **记忆压缩**: 自动压缩对话历史
- **RAG 集成**: 检索增强生成

### 2.3 工具生态

- **自动解析**: 从 Python 函数自动生成 JSON Schema
- **同步/异步**: 同时支持同步和异步工具
- **流式响应**: 支持生成器类型的工具
- **内置工具**: Python 代码执行、文本转图像、语音合成等

### 2.4 工程支持

- **Pipeline**: 多智能体工作流编排
- **MsgHub**: 消息中心,管理多智能体通信
- **Middleware**: 中间件扩展机制
- **Hooks**: 智能体行为钩子
- **Tracing**: 完整的链路追踪
- **Evaluation**: 内置评估框架

---

## 3. 环境准备与安装

### 3.1 系统要求

- **Python**: 3.10 或更高版本
- **操作系统**: Windows / macOS / Linux

### 3.2 安装方式

#### 方式一: PyPI 安装 (推荐)

```bash
# 基础安装
pip install agentscope

# 使用 uv 加速
uv pip install agentscope
```

#### 方式二: 完整依赖安装

```bash
# Windows
pip install agentscope[full]

# macOS/Linux (注意转义)
pip install agentscope\[full\]
```

#### 方式三: 从源码安装

```bash
# 克隆仓库
git clone -b main https://github.com/agentscope-ai/agentscope.git
cd agentscope

# 安装
pip install -e .
# 或使用 uv
uv pip install -e .
```

### 3.3 验证安装

```python
import agentscope
print(agentscope.__version__)  # 输出: 1.0.17
```

### 3.4 API Key 配置

根据使用的模型服务配置 API Key:

```bash
# DashScope (阿里云)
export DASHSCOPE_API_KEY="your_api_key_here"

# OpenAI
export OPENAI_API_KEY="your_api_key_here"

# 其他服务请参考官方文档
```

---

## 4. 核心概念详解

### 4.1 Message (消息)

**消息是 AgentScope 中信息交换的基本数据结构**,用于:
- 智能体之间通信
- 用户界面显示
- 记忆存储
- 与不同 LLM API 交互

#### 消息结构

```python
from agentscope.message import Msg

# 基本消息
msg = Msg(
    name="Alice",           # 发送者名称
    content="Hello!",       # 消息内容
    role="user"             # 角色: system/user/assistant
)
```

#### 消息类型

AgentScope 支持多种消息内容类型:

```python
from agentscope.message import Msg, TextBlock, ToolUseBlock

# 纯文本消息
text_msg = Msg(
    name="Bot",
    content=[TextBlock(type="text", text="Hello!")],
    role="assistant"
)

# 包含工具调用的消息
tool_msg = Msg(
    name="Agent",
    content=[
        TextBlock(type="text", text="Let me check..."),
        ToolUseBlock(
            type="tool_use",
            id="tool_123",
            name="search",
            input={"query": "weather"}
        )
    ],
    role="assistant"
)
```

### 4.2 Agent (智能体)

**智能体是 AgentScope 的核心抽象**,具有以下核心行为:

#### 三大核心函数

| 函数 | 用途 | 返回值 |
|------|------|--------|
| `reply(msg)` | 处理输入消息并生成响应 | Msg |
| `observe(msg)` | 接收消息但不响应 | None |
| `print(msg)` | 显示消息到终端/界面 | None |

#### 智能体类型

1. **AgentBase**: 所有智能体的基类
2. **ReActAgentBase**: ReAct 智能体基类,增加 `reasoning` 和 `acting`
3. **ReActAgent**: 完整的 ReAct 智能体实现
4. **UserAgent**: 代表用户的智能体

#### ReAct 智能体工作流

```
用户输入 → Reasoning (推理) → Acting (执行工具) → Observation (观察结果) → 重复/返回
```

### 4.3 Tool (工具)

**工具是智能体与外部世界交互的桥梁**,可以是:
- Python 函数
- 类方法
- 可调用对象

#### 工具定义示例

```python
from agentscope.tool import Toolkit

# 定义工具函数
def search_web(query: str) -> str:
    """
    Search the web for information.
    
    Args:
        query (str): The search query.
    
    Returns:
        str: Search results.
    """
    # 实现搜索逻辑
    return f"Results for: {query}"

# 注册到工具箱
toolkit = Toolkit()
toolkit.register_tool_function(search_web)
```

#### Toolkit 核心功能

- ✅ 自动从 docstring 提取 JSON Schema
- ✅ 支持同步/异步函数
- ✅ 支持流式响应
- ✅ 支持执行中断
- ✅ 支持工具组管理

### 4.4 Memory (记忆)

**记忆系统管理智能体的上下文和历史信息**:

#### 记忆类型

```python
from agentscope.memory import TemporaryMemory, InMemoryMemory

# 临时记忆 (不持久化)
memory = TemporaryMemory()

# 内存记忆 (会话级别)
memory = InMemoryMemory()

# 基本操作
memory.add(msg)           # 添加消息
memory.get_memory()       # 获取所有记忆
memory.delete(index)      # 删除特定记忆
memory.clear()            # 清空记忆
```

### 4.5 Model (模型)

**模型封装了与各种 LLM API 的交互**:

#### 支持的模型

- DashScope (阿里云通义千问)
- OpenAI (GPT 系列)
- Anthropic (Claude)
- 本地模型 (Ollama, vLLM 等)

#### 模型使用示例

```python
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter

model = DashScopeChatModel(
    model_name="qwen-max",
    api_key="your_key"
)

# 模型调用
response = await model(messages)
```

### 4.6 Formatter (格式化器)

**格式化器负责将消息转换为 LLM API 所需的格式**:

- 处理多智能体场景下的角色区分
- 实现提示工程
- 处理消息截断和验证

### 4.7 State (状态)

**状态管理允许保存和恢复智能体的运行时数据**:

```python
# 保存状态
state = agent.state_dict()

# 恢复状态
agent.load_state_dict(state)
```

---

## 5. 快速入门: Hello AgentScope

### 5.1 最简单的示例

创建一个能与用户对话的 ReAct 智能体:

```python
import asyncio
from agentscope.agent import ReActAgent, UserAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit, execute_python_code

async def main():
    # 1. 创建工具箱并注册工具
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    
    # 2. 创建 ReAct 智能体
    agent = ReActAgent(
        name="Friday",
        sys_prompt="You're a helpful assistant named Friday.",
        model=DashScopeChatModel(
            model_name="qwen-turbo",
        ),
        formatter=DashScopeChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )
    
    # 3. 创建用户智能体
    user = UserAgent(name="User")
    
    # 4. 开始对话
    msg = None
    while True:
        # 用户输入
        msg = await user(msg)
        if msg.content.lower() in ["exit", "quit"]:
            break
        # 智能体回复
        msg = await agent(msg)

# 运行
asyncio.run(main())
```

### 5.2 运行结果

```
User: Hi Friday!
Friday: Hello! I'm Friday, your helpful assistant. How can I help you today?

User: Calculate 2^10
Friday: [Tool Call: execute_python_code]
        Result: 1024
        The result of 2^10 is 1024.

User: exit
```

---

## 6. 核心组件深入

### 6.1 自定义智能体

继承 `AgentBase` 创建自定义智能体:

```python
from agentscope.agents import AgentBase
from agentscope.message import Msg

class JarvisAgent(AgentBase):
    def __init__(self):
        super().__init__("Jarvis")
        self.name = "Jarvis"
        self.sys_prompt = "You're a helpful assistant named Jarvis."
        self.memory = TemporaryMemory()
        # 初始化模型...
    
    async def reply(self, msg: Msg) -> Msg:
        # 1. 记录输入消息
        self.memory.add(msg)
        
        # 2. 构建提示
        messages = [Msg("system", self.sys_prompt, "system")]
        messages.extend(self.memory.get_memory())
        
        # 3. 调用模型
        response = await self.model(messages)
        
        # 4. 记录并返回响应
        self.memory.add(response)
        return response

# 使用
jarvis = JarvisAgent()
reply = await jarvis(Msg("user", "Hi!", "user"))
```

### 6.2 工具系统详解

#### 工具函数规范

```python
from typing import Literal
from pydantic import BaseModel, Field

# 定义返回类型
class WeatherInfo(BaseModel):
    city: str
    temperature: float
    condition: str

# 工具函数
def get_weather(
    city: str,
    unit: Literal["celsius", "fahrenheit"] = "celsius"
) -> WeatherInfo:
    """
    Get current weather information for a city.
    
    Args:
        city (str): The city name.
        unit (str): Temperature unit, "celsius" or "fahrenheit".
    
    Returns:
        WeatherInfo: Weather information including temperature and condition.
    """
    # 实现逻辑
    return WeatherInfo(
        city=city,
        temperature=22.5,
        condition="sunny"
    )

# 注册
toolkit = Toolkit()
toolkit.register_tool_function(get_weather)
```

#### 工具组管理

```python
# 创建工具组
toolkit.create_tool_group(
    group_name="browser_use",
    tools=[search_web, open_url, extract_text]
)

# 激活/停用工具组
toolkit.update_tool_groups(
    activate=["browser_use"],
    deactivate=["database_tools"]
)

# 只有激活的工具组对智能体可见
```

#### 异步工具

```python
async def async_search(query: str) -> str:
    """Async web search."""
    await asyncio.sleep(1)  # 模拟异步操作
    return f"Results for {query}"

toolkit.register_tool_function(async_search)
```

### 6.3 记忆系统深入

#### 长期记忆

```python
from agentscope.memory import LongTermMemory

# 配置长期记忆
long_memory = LongTermMemory(
    embedding_model=...,  # 嵌入模型
    vector_store=...,     # 向量数据库
    top_k=5               # 检索数量
)

# 添加记忆
long_memory.add(Msg("user", "My name is Alice", "user"))

# 检索相关记忆
relevant = long_memory.retrieve("What's my name?")
```

### 6.4 Agent Hooks (钩子)

**钩子允许在智能体执行特定点自定义行为**:

#### 钩子类型

| 钩子 | 触发时机 | 用途 |
|------|---------|------|
| `pre_reply` | reply 之前 | 修改输入参数 |
| `post_reply` | reply 之后 | 处理响应结果 |
| `pre_reasoning` | 推理之前 | 注入额外上下文 |
| `post_acting` | 行动之后 | 记录工具调用 |

#### 钩子示例

```python
def log_tool_calls(self, kwargs):
    """记录所有工具调用"""
    result = kwargs.get("result")
    if hasattr(result, "tool_calls"):
        print(f"[LOG] Tool calls: {result.tool_calls}")
    return None  # 返回 None 不修改结果

# 注册钩子
agent.register_instance_hook(
    hook_type="post_acting",
    hook_name="tool_logger",
    hook_func=log_tool_calls
)
```

---

## 6.5 高级功能详解

### 6.5.1 Tool (工具系统) 完整指南

**Tool 是智能体与外部世界交互的核心机制**,AgentScope 提供了强大的工具管理系统。

#### 工具函数规范

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

# 1. 定义返回类型 (可选但推荐)
class SearchResult(BaseModel):
    """搜索结果数据结构"""
    title: str = Field(description="结果标题")
    url: str = Field(description="结果链接")
    snippet: str = Field(description="内容摘要")

# 2. 工具函数 - 使用 type hints 和 docstring
def web_search(
    query: str,
    num_results: int = 5,
    language: Literal["en", "zh"] = "en"
) -> list[SearchResult]:
    """
    Search the web for information.
    
    Args:
        query (str): The search query string.
        num_results (int): Number of results to return (1-10).
        language (str): Language for search results, "en" or "zh".
    
    Returns:
        list[SearchResult]: List of search results with title, URL, and snippet.
    
    Raises:
        ValueError: If num_results is not between 1 and 10.
    """
    if not 1 <= num_results <= 10:
        raise ValueError("num_results must be between 1 and 10")
    
    # 实现搜索逻辑...
    return [
        SearchResult(
            title=f"Result {i}",
            url=f"https://example.com/{i}",
            snippet=f"Snippet for query: {query}"
        )
        for i in range(num_results)
    ]

# 3. 注册工具
from agentscope.tool import Toolkit

toolkit = Toolkit()
toolkit.register_tool_function(web_search)
```

**关键规范**:
- ✅ 使用完整的 type hints (参数和返回值)
- ✅ 详细的 docstring (Args, Returns, Raises)
- ✅ 使用 Pydantic 定义复杂返回类型
- ✅ 包含参数验证和错误处理

#### Toolkit 核心功能

##### 1. 工具注册

```python
from agentscope.tool import Toolkit, execute_python_code, execute_shell_command

toolkit = Toolkit()

# 方式 1: 注册函数
toolkit.register_tool_function(my_custom_function)

# 方式 2: 注册时设置默认参数
toolkit.register_tool_function(
    tool_func=search_web,
    default_args={"language": "zh"}
)

# 方式 3: 注册类方法
class DatabaseTools:
    def query_db(self, sql: str) -> dict:
        """Execute SQL query"""
        return {"result": "data"}

db_tools = DatabaseTools()
toolkit.register_tool_function(db_tools.query_db)
```

##### 2. 工具组管理

```python
# 创建工具组
toolkit = Toolkit()

# 浏览器工具组
toolkit.register_tool_function(
    web_search, 
    group_name="browser"
)
toolkit.register_tool_function(
    open_url,
    group_name="browser"
)
toolkit.register_tool_function(
    extract_text,
    group_name="browser"
)

# 数据库工具组
toolkit.register_tool_function(
    query_db,
    group_name="database"
)

# 激活/停用工具组
toolkit.update_tool_groups(
    activate=["browser"],      # 激活浏览器工具组
    deactivate=["database"]    # 停用数据库工具组
)

# 只有激活的工具组对智能体可见!
```

**工具组的作用**:
- 🎯 限制智能体可访问的工具范围
- 🎯 减少提示词中的工具描述,提高效率
- 🎯 按场景动态切换工具集

##### 3. 异步工具

```python
import asyncio

# 异步工具函数
async def async_api_call(endpoint: str, data: dict) -> dict:
    """
    Make an async API call.
    
    Args:
        endpoint (str): API endpoint URL.
        data (dict): Request data.
    
    Returns:
        dict: API response.
    """
    # 模拟异步 HTTP 请求
    await asyncio.sleep(0.1)
    return {"status": "success", "data": data}

# 注册异步工具
toolkit.register_tool_function(async_api_call)

# AgentScope 自动处理同步/异步调用
```

##### 4. 流式工具响应

```python
from typing import AsyncGenerator
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

async def streaming_generator(text: str) -> AsyncGenerator[ToolResponse, None]:
    """
    Generate text stream.
    
    Args:
        text (str): Input text to process.
    
    Yields:
        ToolResponse: Streaming response chunks.
    """
    for i, char in enumerate(text):
        yield ToolResponse(
            content=[TextBlock(type="text", text=char)],
            metadata={"chunk_index": i}
        )

toolkit.register_tool_function(streaming_generator)
```

##### 5. 工具执行控制

```python
# 中断工具执行
async def long_running_task(duration: int) -> str:
    """A task that takes time."""
    await asyncio.sleep(duration)
    return "Done"

toolkit.register_tool_function(long_running_task)

# 在智能体中处理中断
agent = ReActAgent(
    name="Agent",
    toolkit=toolkit,
    # 支持用户中断工具执行
)

# Ctrl+C 可以中断工具执行
```

##### 6. 内置工具

AgentScope 提供多种内置工具:

| 工具 | 功能 | 示例 |
|------|------|------|
| `execute_python_code` | 执行 Python 代码 | 计算、数据处理 |
| `execute_shell_command` | 执行 Shell 命令 | 系统操作 |
| `view_text_file` | 读取文本文件 | 查看配置文件 |
| `write_text_file` | 写入文本文件 | 保存结果 |
| `dashscope_text_to_image` | 文本生成图像 | AI 绘图 |
| `dashscope_text_to_audio` | 文本转语音 | TTS |

```python
from agentscope.tool import (
    execute_python_code,
    execute_shell_command,
    view_text_file,
    write_text_file
)

toolkit = Toolkit()
toolkit.register_tool_function(execute_python_code)
toolkit.register_tool_function(execute_shell_command)
```

---

### 6.5.2 MCP (Model Context Protocol) 详解

**MCP 是标准化的模型上下文协议**,用于智能体与外部工具服务器的通信。

#### MCP 架构

```
┌─────────────────┐
│  AgentScope     │
│  (MCP Client)   │
└────────┬────────┘
         │ MCP Protocol
         │
┌────────▼────────┐
│  MCP Server     │
│  (Tool Provider)│
└─────────────────┘
```

**核心优势**:
- ✅ 标准化接口 - 统一的工具调用协议
- ✅ 解耦设计 - 工具服务器独立部署
- ✅ 生态兼容 - 支持第三方 MCP 服务器

#### MCP 客户端类型

##### 1. 无状态客户端 (Stateless)

**HTTP-based,无需维护连接**:

```python
from agentscope.mcp import HttpStatelessClient

# 创建无状态 MCP 客户端
weather_mcp = HttpStatelessClient(
    name="weather_service",
    transport="streamable_http",
    url="https://api.weather-mcp.com/mcp",
)

# 直接注册,无需 connect()
toolkit = Toolkit()
await toolkit.register_mcp_client(weather_mcp)

# 使用工具
agent = ReActAgent(
    name="WeatherAgent",
    toolkit=toolkit,
    ...
)
```

**适用场景**:
- 🎯 RESTful API 服务
- 🎯 无需会话状态的工具
- 🎯 快速集成第三方服务

##### 2. 有状态客户端 (Stateful)

**Stdio-based,需要维护连接**:

```python
from agentscope.mcp import StdioMCPClient

# 创建有状态 MCP 客户端
math_mcp = StdioMCPClient(
    name="math_tools",
    command="python",
    args=["math_mcp_server.py"],
    env={"DEBUG": "1"},  # 可选: 环境变量
)

# 必须先连接
await math_mcp.connect()

# 注册到工具箱
toolkit = Toolkit()
await toolkit.register_mcp_client(math_mcp)

# 使用后记得关闭
try:
    agent = ReActAgent(
        name="MathAgent",
        toolkit=toolkit,
        ...
    )
    # ... 使用智能体 ...
finally:
    await math_mcp.close()
```

**适用场景**:
- 🎯 本地工具服务器
- 🎯 需要会话状态的服务
- 🎯 复杂的工具交互

#### MCP 服务器开发

##### 创建简单的 MCP 服务器

```python
# math_mcp_server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

# 创建 MCP 服务器
server = Server("math-tools")

# 定义工具
@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        )
    ]

# 实现工具逻辑
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "add":
        result = arguments["a"] + arguments["b"]
        return [TextContent(type="text", text=str(result))]

# 启动服务器
if __name__ == "__main__":
    server.run()
```

##### 高级 MCP 配置

```python
from agentscope.mcp import StdioMCPClient

# 完整配置示例
mcp_client = StdioMCPClient(
    name="advanced_tools",
    command="python",
    args=["-m", "my_mcp_server"],
    env={
        "API_KEY": "xxx",
        "DEBUG": "1",
    },
    timeout=30,  # 超时设置(秒)
    retry_times=3,  # 重试次数
)

await mcp_client.connect()

# 列出可用工具
tools = await mcp_client.list_tools()
for tool in tools:
    print(f"Tool: {tool.name}")
    print(f"Description: {tool.description}")

# 获取可调用函数
add_func = await mcp_client.get_callable_function(
    func_name="add",
    wrap_tool_result=True  # 包装为 ToolResponse
)

# 直接调用
result = await add_func(a=10, b=20)
```

#### MCP 最佳实践

**1. 错误处理**:

```python
from agentscope.mcp import MCPError

try:
    await mcp_client.connect()
    result = await agent(query)
except MCPError as e:
    logger.error(f"MCP error: {e}")
    # 降级处理
    result = await fallback_agent(query)
finally:
    await mcp_client.close()
```

**2. 超时控制**:

```python
import asyncio

# 为 MCP 调用设置超时
async def call_with_timeout(agent, msg, timeout=30):
    try:
        return await asyncio.wait_for(
            agent(msg),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning("MCP call timed out")
        return None
```

**3. 连接池管理**:

```python
class MCPConnectionPool:
    """MCP 连接池"""
    
    def __init__(self):
        self.connections = {}
    
    async def get_client(self, name: str, config: dict):
        if name not in self.connections:
            client = StdioMCPClient(**config)
            await client.connect()
            self.connections[name] = client
        return self.connections[name]
    
    async def close_all(self):
        for client in self.connections.values():
            await client.close()
```

---

### 6.5.3 Skill (技能系统) 详解

**Agent Skills 是轻量级指令系统**,通过结构化文档为智能体提供专业知识。**与工具不同,技能不执行代码** — 它们提供可重用的提示模板、指令和参考材料。

#### 核心特性: 渐进式加载

**技能使用三级加载机制**,最小化初始上下文:

```python
# Level 1: 元数据 (~100 tokens) - 始终加载
# Level 2: 完整 SKILL.md 内容 - 按需加载
# Level 3: 资源 (脚本、文档) - 仅在引用时加载
```

**来源**: [官方文档](https://doc.agentscope.io/tutorial/task_agent_skill.html)

#### Skill vs Tool 关键区别

| 方面 | **Skill** | **Tool** |
|------|-----------|----------|
| **目的** | 提供指令、知识、模板 | 执行代码和执行操作 |
| **执行** | 无代码执行 - 提示驱动 | 实际函数执行 |
| **加载** | 渐进式加载 (元数据 → 完整内容) | 激活时始终在 JSON schema 中 |
| **上下文** | 按需加载到智能体上下文 | 独立执行上下文 |
| **用例** | 专业知识、工作流、最佳实践 | API 调用、文件操作、计算 |

**何时使用 Skill**:
- 📚 提供领域特定知识
- 🎯 教授工作流程和程序
- 💡 分享最佳实践和模式
- 📖 按需加载参考文档
- 🔄 一个智能体需要多个专业化,无需预先加载所有上下文

**何时使用 Tool**:
- ⚙️ 需要执行实际代码
- 📁 执行文件 I/O 操作
- 🌐 进行 API 调用
- 🔢 运行计算
- 🔗 与外部系统交互

#### Skill 目录结构

**来源**: [示例技能](https://github.com/agentscope-ai/agentscope/blob/main/examples/functionality/agent_skill/skill/analyzing-agentscope-library/SKILL.md)

```
skill-name/
├── SKILL.md          # 必需: 带 YAML 前言的入口文件
├── references/       # 可选: 详细参考文档
│   ├── api-doc.md
│   └── best-practices.md
├── examples/         # 可选: 工作示例
│   └── example1.py
└── scripts/          # 可选: 可执行脚本
    └── view_module.py
```

#### SKILL.md 格式

**来源**: [实际示例](https://raw.githubusercontent.com/agentscope-ai/agentscope/main/examples/functionality/agent_skill/skill/analyzing-agentscope-library/SKILL.md)

```markdown
---
name: analyzing-agentscope-library
description: Use this skill when analyzing or retrieving information about the AgentScope library, understanding its architecture, or finding usage examples.
---

# Analyzing AgentScope Library

## Overview
This guide covers the essential operations for retrieving and answering questions about the AgentScope library.

## Quick Start
The skill provides the following key scripts:
- Search for guidance in the AgentScope tutorial
- Search for official examples
- View AgentScope's Python library by module name

### Search for Examples
First ask for the user's permission to clone the agentscope GitHub repository:
```bash
git clone -b main https://github.com/agentscope-ai/agentscope
```
Navigate the `examples` folder to find implementations.
```

**关键**: `description` 字段至关重要!
```markdown
---
# ✅ 好: 清晰的触发条件
description: Use this skill when analyzing data, calculating statistics, or generating reports

# ❌ 差: 模糊的描述
description: A data analysis skill
---
```

**规则**: `description = [做什么] + [何时使用,包含具体触发短语]`

#### 注册和使用 Skill

**来源**: [注册 API](https://github.com/agentscope-ai/agentscope/blob/main/src/agentscope/tool/_toolkit.py#L1100-L1183)

```python
from agentscope.tool import Toolkit
import os

# 准备技能目录
os.makedirs("sample_skill", exist_ok=True)
with open("sample_skill/SKILL.md", "w", encoding="utf-8") as f:
    f.write("""---
name: sample_skill
description: Use this skill when the user asks about database schemas, SQL queries, or data relationships.
---

# Sample Skill
Instructions for using this skill...
""")

# 创建 toolkit 并注册技能
toolkit = Toolkit()
toolkit.register_agent_skill("sample_skill")

# 获取技能提示
skill_prompt = toolkit.get_agent_skill_prompt()
print(skill_prompt)

# 重要: 智能体需要文件读取工具来访问技能内容!
from agentscope.agent import ReActAgent
from agentscope.tool import execute_shell_command, view_text_file

toolkit.register_tool_function(execute_shell_command)
toolkit.register_tool_function(view_text_file)

# 创建智能体 (技能自动附加到系统提示)
agent = ReActAgent(
    name="Friday",
    sys_prompt="You are a helpful assistant named Friday.",
    model=model,
    toolkit=toolkit,  # 技能自动附加
    memory=InMemoryMemory(),
    formatter=DashScopeChatFormatter(),
)
```

**关键**: 智能体 **必须** 有文件读取或 Shell 命令工具才能访问 SKILL.md 内容!

#### 渐进式加载工作流

```python
# 高效的上下文管理
# 1. 智能体启动: 只加载元数据 (~100 tokens/技能)
# 2. 用户查询: 智能体识别相关技能
# 3. 智能体调用 read_skill() 加载完整内容
# 4. 智能体使用加载的内容完成任务

# 示例工作流:
User: "Analyze our Q4 sales data"
Agent: [看到 "sales_analytics: Database schema for sales data..."]
Agent: [调用 read_skill("sales_analytics")]
Agent: [接收完整 schema、业务逻辑、示例查询]
Agent: [基于加载的技能生成 SQL 和分析]
```

#### Skill 最佳实践

**1. 保持 SKILL.md 专注**

**来源**: [最佳实践](https://java.agentscope.io/en/task/agent-skill.html)

```markdown
# 推荐: SKILL.md 1.5-2k tokens
# 最大: 5k tokens

# 将大型技能拆分为:
skill-name/
├── SKILL.md              # 核心指令 (1.5-2k tokens)
├── references/
│   ├── api-doc.md        # 详细 API 文档
│   └── advanced.md       # 高级用法
└── examples/
    └── tutorial.md       # 分步示例
```

**2. 必需的工具**

```python
# 关键: 必须注册这些工具才能使技能工作
toolkit.register_tool_function(execute_shell_command)
toolkit.register_tool_function(view_text_file)
toolkit.register_tool_function(execute_python_code)

# 然后注册技能
toolkit.register_agent_skill("./skills/my-skill")
```

**3. 自定义技能提示**

```python
toolkit = Toolkit(
    # 技能介绍的自定义指令
    agent_skill_instruction=(
        "<system-info>You're provided a collection of skills, "
        "each in a directory and described by a SKILL.md file.</system-info>\n"
    ),
    # 每个技能的自定义模板 (必须有 {name}, {description}, {dir})
    agent_skill_template="- {name}({dir}): {description}",
)
```

**4. 技能组织模式**

```python
# 模式 1: 每个领域一个技能
skills/
├── data-analysis/
│   └── SKILL.md
├── code-review/
│   └── SKILL.md
└── documentation/
    └── SKILL.md

# 模式 2: 带资源的技能
skills/
└── api-integration/
    ├── SKILL.md
    ├── references/
    │   ├── rest-api.md
    │   └── graphql-api.md
    └── scripts/
        └── test_endpoint.py
```

#### 常见陷阱和解决方案

**陷阱 1: 技能未触发**

**解决方案**: 检查 description 字段
```markdown
---
# 问题: 太模糊
description: A helpful skill

# 解决方案: 具体触发短语
description: Use this skill when the user asks about database schemas, SQL queries, or data relationships
---
```

**陷阱 2: 智能体无法访问技能内容**

**解决方案**: 注册文件读取工具
```python
# 必须注册这些工具才能使技能工作
toolkit.register_tool_function(execute_shell_command)
toolkit.register_tool_function(view_text_file)
```

**陷阱 3: 上下文溢出**

**解决方案**: 使用渐进式加载
```python
# 不要: 把所有内容放在 SKILL.md 中
# 要: 拆分到 references
skill/
├── SKILL.md          # 核心工作流 (1.5k tokens)
└── references/
    ├── api-v1.md     # 仅在需要时加载
    ├── api-v2.md
    └── examples.md
```

#### 使用 Skill

```python
from agentscope.agent import ReActAgent
from agentscope.skill import SkillRegistry

# 方式 1: 直接使用
research_skill = ResearchSkill()
result = await research_skill.execute("AI agents", depth=5)

# 方式 2: 通过智能体使用
skill_registry = SkillRegistry()
skill_registry.register(ResearchSkill())
skill_registry.register(CodeGenerationSkill())

agent = ReActAgent(
    name="Assistant",
    skill_registry=skill_registry,
    ...
)

# 智能体可以自动调用合适的技能
response = await agent(Msg("user", "Research quantum computing", "user"))
```

#### 内置 Skills

AgentScope 提供多种内置技能:

| Skill | 功能 | 使用场景 |
|-------|------|---------|
| `RAGSkill` | 检索增强生成 | 知识问答 |
| `CodeSkill` | 代码生成与执行 | 编程助手 |
| `WebSkill` | 网页浏览与提取 | 信息收集 |
| `AnalysisSkill` | 数据分析 | 报表生成 |

```python
from agentscope.skill import RAGSkill

# 使用内置 RAG 技能
rag_skill = RAGSkill(
    knowledge_base=my_knowledge_base,
    top_k=5,
)

agent = ReActAgent(
    name="RAGAgent",
    skills=[rag_skill],
    ...
)
```

#### Skill 最佳实践

**1. 单一职责**:

```python
# ✅ 好的设计 - 专注单一能力
class WebScraperSkill(SkillBase):
    """只负责网页抓取"""
    name = "web_scraper"
    ...

# ❌ 不好的设计 - 职责过多
class SwissArmyKnifeSkill(SkillBase):
    """做太多事情"""
    name = "do_everything"
    ...
```

**2. 可组合性**:

```python
# 设计可组合的技能
class SearchSkill(SkillBase):
    """搜索技能"""
    ...

class AnalyzeSkill(SkillBase):
    """分析技能"""
    ...

class ReportSkill(SkillBase):
    """报告技能"""
    ...

# 组合使用
class ResearchWorkflow:
    def __init__(self):
        self.search = SearchSkill()
        self.analyze = AnalyzeSkill()
        self.report = ReportSkill()
    
    async def execute(self, topic):
        # 搜索 → 分析 → 报告
        data = await self.search.execute(topic)
        insights = await self.analyze.execute(data)
        report = await self.report.execute(insights)
        return report
```

**3. 错误处理**:

```python
class RobustSkill(SkillBase):
    async def execute(self, *args, **kwargs):
        try:
            return await self._do_work(*args, **kwargs)
        except Exception as e:
            logger.error(f"Skill execution failed: {e}")
            # 优雅降级
            return self._fallback_response()
```

---

### 6.5.4 Middleware (中间件)

**Middleware 在智能体之间拦截和处理消息**,用于日志、监控、转换等。

#### Middleware 架构

```
Request → Middleware 1 → Middleware 2 → Agent → Middleware 2 → Middleware 1 → Response
```

#### 创建 Middleware

```python
from agentscope.middleware import MiddlewareBase
from agentscope.message import Msg

class LoggingMiddleware(MiddlewareBase):
    """日志中间件"""
    
    async def process_request(self, msg: Msg) -> Msg:
        """处理请求消息"""
        logger.info(f"Request: {msg.content[:50]}...")
        return msg
    
    async def process_response(self, msg: Msg) -> Msg:
        """处理响应消息"""
        logger.info(f"Response: {msg.content[:50]}...")
        return msg

# 注册中间件
agent = ReActAgent(
    name="Agent",
    middleware=[LoggingMiddleware()],
    ...
)
```

#### 内置 Middleware

| Middleware | 功能 | 用途 |
|------------|------|------|
| `LoggingMiddleware` | 消息日志 | 调试、审计 |
| `TimingMiddleware` | 性能计时 | 监控延迟 |
| `ValidationMiddleware` | 消息验证 | 数据校验 |
| `TransformMiddleware` | 消息转换 | 格式转换 |

```python
from agentscope.middleware import (
    LoggingMiddleware,
    TimingMiddleware,
    ValidationMiddleware
)

agent = ReActAgent(
    name="Agent",
    middleware=[
        LoggingMiddleware(level="INFO"),
        TimingMiddleware(),
        ValidationMiddleware(schema=my_schema),
    ],
    ...
)
```

---

### 6.5.5 A2A (Agent-to-Agent) 协议

**A2A 协议用于智能体之间的标准化通信**。

#### A2A 架构

```python
from agentscope.agent import ReActAgent, A2AAgent

# 创建 A2A 智能体
a2a_agent = A2AAgent(
    name="RemoteAgent",
    endpoint="http://remote-agent:8080/a2a",
    ...
)

# 本地智能体调用远程智能体
local_agent = ReActAgent(
    name="LocalAgent",
    ...
)

# 通过 A2A 协议通信
response = await local_agent.send_a2a(
    recipient="RemoteAgent",
    message=Msg("user", "Process this data", "user")
)
```

#### A2A 消息格式

```python
{
    "protocol": "a2a",
    "version": "1.0",
    "sender": {
        "agent_id": "local_agent_001",
        "name": "LocalAgent"
    },
    "recipient": {
        "agent_id": "remote_agent_001",
        "name": "RemoteAgent"
    },
    "message": {
        "content": "Process this data",
        "metadata": {}
    },
    "timestamp": "2026-03-25T10:30:00Z"
}
```

---

### 6.5.6 Realtime Agent (实时智能体)

**Realtime Agent 支持实时语音和流式交互**。

```python
from agentscope.agent import RealtimeAgent
from agentscope.model import DashScopeChatModel

# 创建实时智能体
realtime_agent = RealtimeAgent(
    name="VoiceAssistant",
    model=DashScopeChatModel(model_name="qwen-audio"),
    voice_enabled=True,
    stream=True,
)

# 实时语音交互
async def voice_conversation():
    async for audio_chunk in audio_stream:
        # 实时处理语音
        response = await realtime_agent.process_audio(audio_chunk)
        
        # 流式返回
        async for text_chunk in response.stream():
            print(text_chunk, end="", flush=True)
```

**适用场景**:
- 🎙️ 语音助手
- 📞 实时客服
- 🎮 游戏对话

---

## 7. 多智能体系统

### 7.1 MsgHub (消息中心)

**MsgHub 管理多个智能体之间的消息交换**,是 AgentScope 多智能体协作的核心组件:

```python
from agentscope.pipeline import MsgHub
from agentscope.message import Msg

async def multi_agent_conversation():
    # 创建多个智能体
    agent1 = ...
    agent2 = ...
    agent3 = ...
    
    # 创建消息中心
    async with MsgHub(
        participants=[agent1, agent2, agent3],
        announcement=Msg("Host", "Please introduce yourselves.", "assistant")
    ) as hub:
        # 智能体按顺序发言,消息自动广播给所有参与者
        await agent1()
        await agent2()
        await agent3()
        
        # 动态管理参与者
        hub.delete(agent2)
        await hub.broadcast(Msg("system", "Agent2 has left", "system"))

asyncio.run(multi_agent_conversation())
```

**关键特性**:
- ✅ 自动广播消息给所有参与者
- ✅ 支持动态添加/删除参与者
- ✅ 支持公告消息

### 7.2 Pipeline (流水线)

**Pipeline 编排多智能体工作流**:

#### 顺序流水线 (Sequential)

```python
from agentscope.pipeline import sequential_pipeline

# 顺序执行 - 一个的输出成为下一个的输入
async def workflow():
    result = await sequential_pipeline(
        agents=[extractor, analyzer, formatter],
        msg=input_msg
    )
    return result
```

**适用场景**: 文档处理 (提取→分析→格式化)、确定性工作流

#### 并行流水线 (Fanout)

```python
from agentscope.pipeline import fanout_pipeline

# 并行执行 - 多个智能体同时处理相同输入
async def parallel_analysis():
    results = await fanout_pipeline(
        agents=[analyzer1, analyzer2, analyzer3],
        msg=input_data,
        enable_gather=True  # 启用并发执行
    )
    return results
```

**适用场景**: 多角度分析、独立任务并行处理

### 7.3 多智能体协作模式

#### 模式 1: Router-Specialist (路由专家模式)

**适用场景**: 任务需要动态路由到专业智能体

```python
from agentscope.agent import ReActAgent
from agentscope.pipeline import MsgHub
from agentscope.formatter import DashScopeMultiAgentFormatter

# 创建路由智能体
router = ReActAgent(
    name="Router",
    sys_prompt="Route tasks to appropriate specialists based on the task type.",
    model=model,
    formatter=DashScopeMultiAgentFormatter(),
)

# 创建专家智能体
researcher = ReActAgent(
    name="Researcher",
    sys_prompt="You are a research specialist.",
    model=model,
    formatter=DashScopeMultiAgentFormatter(),
)

coder = ReActAgent(
    name="Coder",
    sys_prompt="You are a coding specialist.",
    model=model,
    formatter=DashScopeMultiAgentFormatter(),
)

reviewer = ReActAgent(
    name="Reviewer",
    sys_prompt="You are a code review specialist.",
    model=model,
    formatter=DashScopeMultiAgentFormatter(),
)

# 使用 MsgHub 协调
async with MsgHub(participants=[router, researcher, coder, reviewer]):
    await router(user_query)
```

#### 模式 2: Agent as Tool (智能体作为工具)

将智能体封装为可调用工具:

```python
async def expert_consultant(query: str) -> str:
    """咨询专家智能体"""
    expert = ReActAgent(name="Expert", ...)
    msg = Msg("user", query, "user")
    response = await expert(msg)
    return response.content

# 注册为工具
toolkit.register_tool_function(expert_consultant)

# 或者使用 as_tool() 方法
orchestrator = ReActAgent(
    name="Orchestrator",
    toolkit=Toolkit(tools=[
        researcher_agent.as_tool(),
        coder_agent.as_tool(),
    ])
)
```

**适用场景**: 层级组合、专家咨询

#### 模式 3: Sequential Pipeline (顺序流水线)

```python
from agentscope.pipeline import sequential_pipeline

# 文档处理流水线
async def document_processing(doc):
    # 提取 → 分析 → 格式化
    result = await sequential_pipeline(
        agents=[extractor, analyzer, formatter],
        msg=Msg("user", doc, "user")
    )
    return result
```

**适用场景**: 有清晰线性依赖的任务

#### 模式 4: 多智能体辩论

```python
async def debate(topic: str, rounds: int = 3):
    """两个智能体就某个话题辩论"""
    proponent = ReActAgent(
        name="Proponent",
        sys_prompt="You argue FOR the topic.",
        ...
    )
    opponent = ReActAgent(
        name="Opponent",
        sys_prompt="You argue AGAINST the topic.",
        ...
    )
    
    msg = Msg("moderator", f"Debate topic: {topic}", "user")
    
    for _ in range(rounds):
        msg = await proponent(msg)
        msg = await opponent(msg)
    
    return msg
```

**适用场景**: 观点对比、决策支持

### 7.4 Formatter 选择指南 (重要!)

**关键决策**: 不同场景使用不同的 Formatter

| 场景 | Formatter | 关键特性 |
|------|-----------|---------|
| 用户-智能体 (2人) | `DashScopeChatFormatter` | 使用 `role` 区分 |
| 多智能体 (3+人) | `DashScopeMultiAgentFormatter` | 使用 `name` 字段 |

```python
# ❌ 错误: 多智能体使用普通 formatter
multi_agent = ReActAgent(
    formatter=DashScopeChatFormatter(),  # 不适合 3+ 参与者
    ...
)

# ✅ 正确: 多智能体使用 MultiAgent formatter
multi_agent = ReActAgent(
    formatter=DashScopeMultiAgentFormatter(),  # 适合 3+ 参与者
    ...
)
```

---

## 8. 实战示例

### 8.1 代码助手

```python
import asyncio
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, execute_python_code

async def code_assistant():
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    
    agent = ReActAgent(
        name="CodeHelper",
        sys_prompt="""You are an expert Python programmer.
        Help users write, debug, and optimize code.
        Always test your code suggestions.""",
        model=DashScopeChatModel(model_name="qwen-max"),
        toolkit=toolkit,
    )
    
    # 交互循环...

asyncio.run(code_assistant())
```

### 8.2 RAG 智能体

```python
from agentscope.agent import ReActAgent
from agentscope.memory import LongTermMemory

# 配置向量数据库
rag_memory = LongTermMemory(
    embedding_model=embedding_model,
    vector_store=vector_store,
)

agent = ReActAgent(
    name="RAGBot",
    memory=rag_memory,
    # 自动从知识库检索相关内容
)
```

### 8.3 Web 浏览智能体

```python
from agentscope.tool import web_search, open_url, extract_text

toolkit = Toolkit()
toolkit.register_tool_function(web_search)
toolkit.register_tool_function(open_url)
toolkit.register_tool_function(extract_text)

agent = ReActAgent(
    name="WebBrowser",
    sys_prompt="Browse the web to answer user questions.",
    toolkit=toolkit,
)
```

### 8.4 MCP 集成示例

**Mcp (Model Context Protocol)** 是标准化的工具集成协议:

```python
from agentscope.tool import Toolkit
from agentscope.mcp import StdioMCPClient, HttpStatelessClient

async def mcp_integration():
    toolkit = Toolkit()
    
    # 注册无状态 MCP 客户端 (HTTP)
    stateless_client = HttpStatelessClient(
        name="weather_service",
        transport="streamable_http",
        url="https://api.weather-mcp.com/mcp",
    )
    await toolkit.register_mcp_client(stateless_client)
    
    # 注册有状态 MCP 客户端 (stdio)
    stateful_client = StdioMCPClient(
        name="math_tools",
        command="python",
        args=["math_mcp_server.py"],
    )
    await stateful_client.connect()
    await toolkit.register_mcp_client(stateful_client)
    
    # 使用智能体
    agent = ReActAgent(
        name="Jarvis",
        sys_prompt="You're a helpful assistant named Jarvis.",
        model=DashScopeChatModel(...),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )
    
    return agent
```

**关键点**:
- ✅ 无状态客户端 (HTTP) 不需要连接
- ✅ 有状态客户端 (stdio) 需要显式 `connect()` 调用
- ✅ MCP 服务器的工具自动注册

---

## 9. 最佳实践与反模式

### 9.1 智能体设计原则

✅ **单一职责**: 每个智能体专注一个领域  
✅ **明确角色**: 通过 system prompt 清晰定义角色  
✅ **适度工具**: 提供必要但不过多的工具 (建议 5-10 个)  
✅ **记忆管理**: 定期清理或压缩长期记忆  
✅ **异步优先**: 所有操作使用 async/await

### 9.2 工具设计原则

✅ **清晰的文档**: Docstring 详细说明参数和返回值  
✅ **类型提示**: 使用 type hints 和 Pydantic  
✅ **错误处理**: 捕获异常并返回有意义的错误信息  
✅ **幂等性**: 尽量设计可重复执行的工具  
✅ **工具分组**: 使用工具组管理相关工具

### 9.3 多智能体协作原则

✅ **明确分工**: 每个智能体有清晰的职责边界  
✅ **消息协议**: 定义标准的消息格式  
✅ **错误传播**: 妥善处理智能体失败情况  
✅ **性能优化**: 并行执行独立任务  
✅ **从小开始**: 先用 2-3 个智能体验证,再扩展

### 9.4 常见反模式 (Anti-Patterns)

#### ❌ 反模式 1: "上帝智能体" (God Agent)

**错误**: 一个智能体拥有太多工具和职责

```python
# ❌ 错误: 一个智能体做所有事情
mega_agent = ReActAgent(
    tools=[search, code, analyze, review, deploy, monitor, ...]
)
```

**问题**:
1. 幻觉密度增加
2. 性能随工具数量下降
3. 难以调试

**解决方案**: 拆分为专业智能体

```python
# ✅ 正确: 专业智能体
researcher = ReActAgent(tools=[search, analyze])
coder = ReActAgent(tools=[code, test])
reviewer = ReActAgent(tools=[review])
```

#### ❌ 反模式 2: 隐式记忆假设

**错误**: 假设模型会"记住"而没有显式记忆管理

```python
# ❌ 错误: 假设智能体会记住
await agent("Remember my preference is Python")
# 稍后...
await agent("Use my preferred language")  # 可能不工作!
```

**解决方案**: 显式记忆管理

```python
# ✅ 正确: 显式记忆管理
await agent.memory.record(
    Msg("user", "My preference is Python", "user"),
    metadata={"type": "preference", "topic": "language"}
)

# 稍后显式检索
preferences = await agent.memory.retrieve(topic="language")
```

#### ❌ 反模式 3: 过度工程化智能体拓扑

**错误**: 直接跳到复杂的多智能体设置

**解决方案**: 遵循层次化方法

```
第 1 层: 基础 (工具使用, ReAct, 记忆, RAG)
第 2 层: 编排 (顺序, 并行, 条件)
第 3 层: 拓扑 (层级, 对等, 共识)
第 4 层: 质量与安全 (反思, 评估, 护栏)
```

**建议进度**:
- 第 1 周: 识别任务,构建单智能体版本
- 第 2 周: 拆分为 2-3 个专业智能体
- 第 3 周: 添加错误处理和监控
- 第 2 月: 添加并行执行
- 第 3 月: 实现高级模式

#### ❌ 反模式 4: 忽略 Token 预算

**错误**: 不监控或限制 token 使用

**风险**: "一夜之间产生 $2,400 的 API 费用,陷入无限循环"

**解决方案**:

```python
from agentscope.token import TokenCounter

token_counter = TokenCounter(model=model)

# 监控并强制限制
if token_counter.count(memory) > MAX_TOKENS:
    await compress_memory()
    
# 设置成本预算
MAX_COST_PER_SESSION = 5.00  # USD
```

#### ❌ 反模式 5: 不清理会话间记忆

**错误**: 让记忆在不相关会话间泄露

```python
# ❌ 错误: 会话间记忆污染
async def handle_user(user_id, query):
    agent = get_agent(user_id)
    # 没有清理上一次会话!
    result = await agent(query)
    return result
```

**解决方案**:

```python
# ✅ 正确: 清理会话间记忆
async def handle_user_session(user_id, query):
    agent = get_agent_for_user(user_id)
    
    # 清理上一次会话上下文
    await agent.memory.clear()
    
    # 处理新查询
    result = await agent(query)
    
    # 保存轨迹到长期记忆
    trajectory = await agent.memory.get_memory()
    await long_term_memory.save(user_id, trajectory)
    
    return result
```

### 9.5 性能优化技巧

#### 技巧 1: 全程使用异步

```python
# ✅ 正确: 异步执行
async def run_agents():
    async with MsgHub(participants=[agent1, agent2, agent3]):
        await agent1()
        await agent2()
        
asyncio.run(run_agents())
```

#### 技巧 2: 并行化独立操作

```python
# ✅ 正确: 并行执行
results = await fanout_pipeline(
    [analyzer1, analyzer2, analyzer3],
    msg=input_data,
    enable_gather=True  # 并发执行
)

# ❌ 更慢: 顺序执行
results = await fanout_pipeline(
    [analyzer1, analyzer2, analyzer3],
    msg=input_data,
    enable_gather=False  # 顺序执行
)
```

#### 技巧 3: 使用更便宜的模型压缩

```python
# 使用更小的模型进行记忆压缩
compression_model = OpenAIChatModel(
    model_name="gpt-3.5-turbo",  # 比主模型便宜
    api_key=os.environ["OPENAI_API_KEY"],
)

agent = ReActAgent(
    name="Agent",
    model=main_model,  # 昂贵的模型用于推理
    compression_config=ReActAgent.CompressionConfig(
        trigger_threshold=8000,  # token 超过 8000 时压缩
        keep_recent=3,           # 保留最近 3 条消息
        compression_model=compression_model,  # 便宜模型用于压缩
    )
)
```

**指南**:
- ✅ 设置 `trigger_threshold` 为模型上下文限制的 60-70%
- ✅ 使用更小/便宜的模型进行压缩以降低成本
- ✅ 保留工具调用/结果对 (不要拆分它们)

#### 技巧 4: 启用并行工具调用

```python
agent = ReActAgent(
    name="Agent",
    ...,
    parallel_tool_calls=True  # 启用并行调用
)
```

#### 技巧 5: 从第一天就实施可观测性

```python
import agentscope

# 启用追踪
agentscope.init(
    project="my_agent_project",
    tracing=True,
)

# 自动捕获:
# - LLM 调用
# - 工具执行
# - 智能体推理
# - 消息流
```

### 9.6 生产部署检查清单

#### 部署前
- [ ] **记忆管理**: 实现压缩和清理策略
- [ ] **错误处理**: 在智能体调用周围添加 try-catch
- [ ] **Token 预算**: 设置最大 token 和成本限制
- [ ] **可观测性**: 启用追踪和日志
- [ ] **护栏**: 为风险操作添加人工审批

#### 部署中
- [ ] **监控成本**: 跟踪每个会话的 API 使用
- [ ] **延迟跟踪**: 测量响应时间
- [ ] **错误率**: 监控失败率
- [ ] **记忆增长**: 检查记忆不会无限增长

#### 部署后
- [ ] **评估性能**: 使用 OpenJudge 进行质量评估
- [ ] **收集反馈**: 跟踪用户满意度
- [ ] **迭代**: 基于实际使用模式改进

```python
# 生产级错误处理
async def safe_agent_call(agent, msg, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await agent(msg)
            return result
        except Exception as e:
            logger.error(f"Agent call failed (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # 指数退避
```

### 9.7 快速参考: Do's and Don'ts

#### ✅ DO:
- 使用 `MsgHub` 进行多智能体广播
- 在不相关任务间清理记忆
- 实施记忆压缩
- 从 2-3 个智能体开始,逐步扩展
- 正确使用 async/await
- 监控 token 使用和成本
- 添加错误处理和重试
- 使用适当的 formatter (Chat vs MultiAgent)
- 从第一天就实施可观测性
- 在生产前用真实工作负载测试

#### ❌ DON'T:
- 创建有太多工具的 "上帝智能体"
- 假设智能体会记住而没有显式记忆
- 没有坚实基础就跳到复杂拓扑
- 忽略 token 预算和成本监控
- 在同一记忆中混合不相关的上下文
- 跳过错误处理和重试
- 没有可观测性就部署
- 过度工程化智能体交互
- 在异步框架中使用同步模式
- 忘记清理资源 (MCP 连接, 记忆)

---

## 10. 生产部署检查清单

### 10.1 部署前检查

- [ ] **记忆管理**: 实施压缩和清理策略
- [ ] **错误处理**: 在智能体调用周围添加 try-catch
- [ ] **Token 预算**: 设置最大 token 和成本限制
- [ ] **可观测性**: 启用追踪和日志
- [ ] **护栏**: 为危险操作添加人工审批

### 10.2 部署中监控

- [ ] **成本监控**: 跟踪每个会话的 API 使用
- [ ] **延迟跟踪**: 测量响应时间
- [ ] **错误率**: 监控失败率
- [ ] **记忆增长**: 检查记忆不会无限增长

### 10.3 部署后评估

- [ ] **评估性能**: 使用 OpenJudge 进行质量评估
- [ ] **收集反馈**: 跟踪用户满意度
- [ ] **迭代**: 基于真实使用模式改进

### 10.4 推荐扩展路径

```
第 1 周: 识别可以从多智能体受益的任务
第 2 周: 构建单智能体版本进行验证
第 3 周: 拆分为 2-3 个专业智能体,使用顺序编排
第 4 周: 添加错误处理和监控
第 2 月: 在适当的地方添加并行执行
第 3 月: 实现高级模式 (共识、精炼)
```

---

## 11. 常见问题 FAQ

### Q1: AgentScope 支持哪些 LLM?

**A**: 支持 OpenAI、Anthropic Claude、阿里云通义千问、本地模型(Ollama, vLLM)等主流模型。

### Q2: 如何选择记忆类型?

**A**: 
- 临时对话 → `TemporaryMemory`
- 会话级别 → `InMemoryMemory`  
- 长期存储/检索 → `LongTermMemory`

### Q3: ReActAgent 和 AgentBase 的区别?

**A**: `AgentBase` 是基类,需要自己实现所有逻辑。`ReActAgent` 内置了完整的推理-行动循环,开箱即用。

### Q4: 如何实现智能体间的通信?

**A**: 使用 `MsgHub` 管理多智能体消息广播,或直接调用 `agent.observe(msg)` 发送消息。

### Q5: 工具函数可以是异步的吗?

**A**: 可以!Toolkit 同时支持同步和异步工具函数。

### Q6: 如何调试智能体行为?

**A**: 
- 使用 `print` 钩子记录消息流
- 启用 `Tracing` 查看完整执行链路
- 使用 `AgentScope Studio` 可视化监控

### Q7: 如何部署到生产环境?

**A**: 使用 `AgentScope Runtime`:
```bash
pip install agentscope-runtime
```
支持 Docker、K8s、无服务器等多种部署方式。

### Q8: MCP 是什么?

**A**: MCP (Model Context Protocol) 是一种标准化的模型上下文协议,用于智能体与外部资源交互。AgentScope 原生支持 MCP。

---

## 12. 资源与参考

### 11.1 官方资源

- 📖 **官方文档**: https://doc.agentscope.io/
- 💻 **GitHub 仓库**: https://github.com/agentscope-ai/agentscope
- 🎯 **示例库**: https://github.com/agentscope-ai/agentscope-samples
- 📚 **论文**: [AgentScope: A Flexible yet Robust Multi-Agent Platform](https://arxiv.org/abs/2508.16279)

### 11.2 社区资源

- 💬 **Discord**: 加入官方 Discord 社区
- 📱 **钉钉群**: 查看官方文档获取群号
- 🐛 **问题反馈**: GitHub Issues

### 11.3 推荐学习路径

1. **第 1 周**: 掌握基础概念 (Message, Agent, Tool)
2. **第 2 周**: 实现单智能体应用 (ReActAgent)
3. **第 3 周**: 探索多智能体协作 (MsgHub, Pipeline)
4. **第 4 周**: 生产部署 (AgentScope Runtime)

### 11.4 进阶主题

- 🔧 **Fine-tuning**: 使用 Tuner 模块微调模型
- 📊 **Evaluation**: 使用评估框架测试智能体
- 🎙️ **Realtime Voice**: 构建实时语音智能体
- 🌐 **Distributed Agents**: 分布式智能体系统

---

## 结语

AgentScope 是一个强大而灵活的多智能体框架,通过本手册的学习,你应该已经掌握了:

✅ AgentScope 的核心概念和架构  
✅ 如何创建和配置智能体  
✅ 工具系统的使用和扩展  
✅ 多智能体协作的实现  
✅ 最佳实践和常见反模式  
✅ 性能优化技巧  
✅ 生产环境的部署方案  

**下一步建议**:

1. **动手实践**: 运行所有代码示例
2. **构建项目**: 创建你的第一个智能体应用
3. **探索示例**: 查看 [agentscope-samples](https://github.com/agentscope-ai/agentscope-samples) 仓库
4. **加入社区**: Discord / 钉钉群交流
5. **阅读论文**: [AgentScope 1.0](https://arxiv.org/abs/2508.16279) 深入理解设计理念

**学习路径推荐**:

```
Week 1: 基础概念 (Message, Agent, Tool)
Week 2: 单智能体应用 (ReActAgent)
Week 3: 多智能体协作 (MsgHub, Pipeline)
Week 4: 生产部署 (AgentScope Runtime)
Month 2: 高级模式 (MCP, RAG, Hooks)
Month 3: 性能优化和评估
```

**官方示例仓库**:

| 类别 | 示例 | 描述 |
|------|------|------|
| **浏览器使用** | `browser_use/agent_browser` | 命令行浏览器自动化 |
| **深度研究** | `deep_research/agent_deep_research` | 多智能体研究流水线 |
| **游戏** | `games/game_werewolves` | 角色扮演社交推理游戏 |
| **对话** | `conversational_agents/chatbot` | 聊天机器人应用 |
| **数据处理** | `data_juicer_agent/` | 多智能体数据处理 |

祝你使用 AgentScope 愉快! 🚀

---

**手册版本**: v1.1  
**最后更新**: 2026-03-25  
**作者**: AI Assistant  
**许可**: CC BY-SA 4.0
