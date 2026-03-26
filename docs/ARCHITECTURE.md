# 办公小工具整合平台 - 架构设计文档

> **目标受众**: AI Agent  
> **文档类型**: 架构设计（计划中的系统）  
> **核心目标**: 定义系统边界、组件职责、接口契约、关键决策

---

## 1. 系统概述

### 1.1 项目定位

基于PySide6的桌面办公工具整合平台，核心特性：

- **节点编辑器** - 可视化工作流设计，支持自定义节点扩展办公功能
- **Agent辅助** - AI助手读取节点列表，辅助设计工作流
- **插件系统** - 通过事件系统扩展功能，暴露程序上下文
- **统一存储** - SQLite + SQLAlchemy 持久化

### 1.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **PySide6原生** | Qt信号槽机制 + QSS样式 |
| **插件优先** | 所有工具以插件形式注册 |
| **自研引擎** | 节点流引擎与UI深度集成 |
| **统一Schema** | ToolDefinition同时服务Agent和节点流 |
| **事件驱动** | 插件通过事件系统通信 |

### 1.3 技术栈

| 层次 | 技术 |
|------|------|
| UI框架 | PySide6 (Qt) |
| 节点渲染 | QGraphicsView/QGraphicsScene |
| AI框架 | AgentScope |
| 持久化 | SQLite + SQLAlchemy |
| 插件加载 | importlib动态导入 |

---

## 2. 系统上下文 (C4 Level 1)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌─────────────┐      ┌─────────────────────────────────────┐  │
│  │   用户      │ ───▶ │      办公小工具整合平台             │  │
│  │  (办公人员) │ ◀─── │  • 节点编辑器                       │  │
│  └─────────────┘      │  • AI对话辅助                       │  │
│                       │  • 插件化工具集                      │  │
│                       └──────────────┬──────────────────────┘  │
│                                      │                          │
│                       ┌──────────────┼──────────────┐          │
│                       ▼              ▼              ▼          │
│               ┌───────────┐  ┌───────────┐  ┌───────────┐     │
│               │ OpenAI    │  │ 本地文件  │  │ SQLite    │     │
│               │ API       │  │ 系统      │  │ 数据库    │     │
│               └───────────┘  └───────────┘  └───────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**外部系统交互**:

| 外部系统 | 交互方式 | 用途 |
|----------|----------|------|
| OpenAI API | HTTP | Agent对话能力 |
| 本地文件系统 | 文件读写 | Excel/文档处理 |
| SQLite | 本地数据库 | 持久化存储 |

---

## 3. 容器视图 (C4 Level 2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PySide6 桌面应用                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐   │
│  │   主窗口       │  │   AI对话面板   │  │    节点编辑器      │   │
│  │  (QMainWindow) │  │   (QWidget)    │  │  (QGraphicsView)   │   │
│  └───────┬────────┘  └───────┬────────┘  └─────────┬──────────┘   │
│          │                   │                     │               │
│          └───────────────────┼─────────────────────┘               │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     插件管理器                               │   │
│  │  • 插件发现与加载                                            │   │
│  │  • 工具注册                                                  │   │
│  │  • 事件总线                                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│         ┌────────────────────┼────────────────────┐                │
│         ▼                    ▼                    ▼                │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐        │
│  │ AgentScope  │      │ NodeEngine  │      │  持久化层   │        │
│  │  Toolkit    │      │  (自研)     │      │ (SQLite)    │        │
│  └─────────────┘      └─────────────┘      └─────────────┘        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        插件目录 (plugins/)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ excel_tools │  │ table_tools │  │ chat_tools  │  ...            │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

**容器职责**:

| 容器 | 职责 | 技术选型 |
|------|------|----------|
| 主窗口 | 应用入口、布局管理、菜单导航 | PySide6 QMainWindow |
| AI对话面板 | Agent交互、对话历史、API Key管理 | PySide6 QWidget |
| 节点编辑器 | 可视化工作流设计、节点拖放、连线 | QGraphicsView |
| 插件管理器 | 插件生命周期、工具注册、事件分发 | Python |
| AgentScope Toolkit | AI工具注册、ReAct模式执行 | AgentScope |
| NodeEngine | 图执行、拓扑排序、数据传递 | 自研 |
| 持久化层 | 工作流存储、配置、对话历史 | SQLite + SQLAlchemy |

---

## 4. 核心接口契约

### 4.1 端口类型定义

```python
class PortType(Enum):
    ANY = "any"
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    DATAFRAME = "dataframe"
    FILE = "file"
    LIST = "list"
    DICT = "dict"
```

### 4.2 工具定义 (统一Schema)

```python
@dataclass
class ToolDefinition:
    """工具定义 - 同时服务AI和节点流"""
    name: str                    # 唯一标识
    display_name: str            # 显示名称
    description: str             # 描述（AI理解用）
    category: str = "general"    # 分类
    icon: str = "🔧"             # 图标
    inputs: List[PortDefinition] = field(default_factory=list)
    outputs: List[PortDefinition] = field(default_factory=list)
    execute: Callable = field(default=None, repr=False)
```

### 4.3 插件基类接口

```python
class PluginBase(ABC):
    """插件基类"""
    name: str = "unknown"
    version: str = "1.0.0"
    description: str = ""
    
    @abstractmethod
    def get_tools(self) -> List[ToolDefinition]:
        """返回插件提供的所有工具"""
        pass
    
    def on_load(self, context: "AppContext") -> None: ...
    def on_unload(self) -> None: ...
```

### 4.4 事件系统接口

```python
class EventType(Enum):
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    NODE_EXECUTED = "node.executed"
    WORKFLOW_SAVED = "workflow.saved"
    AGENT_MESSAGE = "agent.message"

class EventBus:
    def subscribe(self, event_type: EventType, handler: Callable) -> str: ...
    def unsubscribe(self, subscription_id: str) -> None: ...
    def publish(self, event_type: EventType, data: Any) -> None: ...
```

### 4.5 应用上下文接口

```python
class AppContext:
    """暴露给插件的程序上下文"""
    event_bus: EventBus
    plugin_manager: "PluginManager"
    node_engine: "NodeEngine"
    agent_toolkit: "AgentToolkit"
    storage: "StorageService"
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]: ...
    def register_tool(self, tool: ToolDefinition) -> None: ...
```

---

## 5. 节点编辑器架构

### 5.1 核心模型

```
┌─────────────────────────────────────────────────────┐
│                   NodeGraph                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Node   │  │  Node   │  │  Node   │            │
│  │  ┌───┐  │  │  ┌───┐  │  │  ┌───┐  │            │
│  │  │In │──┼──┼─▶│Out│──┼──┼─▶│In │  │            │
│  │  └───┘  │  │  └───┘  │  │  └───┘  │            │
│  └─────────┘  └─────────┘  └─────────┘            │
│       │            │            │                  │
│       └────────────┴────────────┘                  │
│                    │                               │
│              Connection                            │
└─────────────────────────────────────────────────────┘
```

### 5.2 执行模型

| 阶段 | 操作 |
|------|------|
| 1. 拓扑排序 | 基于连接关系计算执行顺序 |
| 2. 数据传递 | 从前驱节点输出传递到当前节点输入 |
| 3. 节点执行 | 调用ToolDefinition.execute() |
| 4. 状态更新 | 更新节点状态 (idle→running→success/error) |

### 5.3 Widget双输入机制

**参考**: LiteGraph模式

```
┌────────────────────────────────────┐
│           节点端口                 │
│  ┌──────────────────────────────┐  │
│  │  输入来源 (二选一):          │  │
│  │  1. 连接线 (从其他节点)      │  │
│  │  2. Widget (用户直接输入)    │  │
│  │                              │  │
│  │  规则: 连接线优先级 > Widget │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

### 5.4 节点状态

| 状态 | 说明 | UI颜色 |
|------|------|--------|
| IDLE | 待执行 | 灰色 |
| RUNNING | 执行中 | 黄色 |
| SUCCESS | 成功 | 绿色 |
| ERROR | 失败 | 红色 |

---

## 6. Agent系统架构

### 6.1 AgentScope集成

```
┌─────────────────────────────────────────────────────┐
│                  Agent Layer                        │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ API Key     │  │   Tool      │  │    MCP     │  │
│  │ Manager     │  │  Registry   │  │  Manager   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬─────┘  │
│         │                │                │        │
│         └────────────────┼────────────────┘        │
│                          ▼                         │
│  ┌───────────────────────────────────────────────┐ │
│  │              AgentScope Agent                 │ │
│  │  • ReAct模式执行                              │ │
│  │  • 工具调用                                   │ │
│  │  • 对话历史管理                               │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 6.2 Agent核心能力

| 能力 | 说明 |
|------|------|
| 节点列表读取 | 获取所有可用节点类型和描述 |
| 工作流建议 | 基于用户需求推荐节点组合 |
| 工作流验证 | 检查连接合理性、类型匹配 |
| 自然语言生成工作流 | 从描述生成节点图 |

### 6.3 资源管理

| 资源类型 | 存储位置 | 用途 |
|----------|----------|------|
| API Key | SQLite加密存储 | OpenAI/其他LLM认证 |
| Tool | ToolDefinition注册表 | Agent可调用工具 |
| MCP | 配置文件 + SQLite | Model Context Protocol服务 |
| Skill | 插件目录 | 预定义技能包 |

### 6.4 Agent-工作流交互

```
User Request ──▶ Agent ──▶ 读取节点列表
                               │
                               ▼
                        分析用户需求
                               │
                               ▼
                    ┌─────────────────────┐
                    │  生成/建议工作流    │
                    │  (节点+连接)        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  节点编辑器渲染     │
                    │  (可视化展示)       │
                    └─────────────────────┘
```

---

## 7. 插件系统架构

### 7.1 插件生命周期

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  发现   │───▶│  加载   │───▶│  注册   │───▶│  活跃   │
└─────────┘    └─────────┘    └─────────┘    └────┬────┘
                                                   │
                                                   ▼
                                              ┌─────────┐
                                              │  卸载   │
                                              └─────────┘
```

| 阶段 | 操作 |
|------|------|
| 发现 | 扫描plugins/目录，识别插件包/模块 |
| 加载 | importlib动态导入，实例化PluginBase子类 |
| 注册 | 调用get_tools()，注册到Toolkit和NodeEngine |
| 活跃 | 响应事件，提供工具执行 |
| 卸载 | 移除工具，调用on_unload()，释放资源 |

### 7.2 事件系统

```
┌─────────────────────────────────────────────────────┐
│                    EventBus                         │
│                                                     │
│  Plugin A ──┬──▶ [PLUGIN_LOADED] ──┬──▶ Plugin B  │
│             │                       │               │
│             └──▶ [NODE_EXECUTED] ───┴──▶ Logger    │
│                                                     │
│  NodeEngine ──▶ [WORKFLOW_SAVED] ──▶ Storage       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**核心事件类型**:

| 事件 | 发布者 | 订阅者 |
|------|--------|--------|
| PLUGIN_LOADED | PluginManager | UI, Logger |
| PLUGIN_UNLOADED | PluginManager | UI, NodeEngine |
| NODE_EXECUTED | NodeEngine | UI, Logger |
| WORKFLOW_SAVED | NodeEngine | Storage |
| AGENT_MESSAGE | AgentLayer | ChatPanel |

### 7.3 上下文暴露

插件通过`AppContext`访问程序功能:

```python
class MyPlugin(PluginBase):
    def on_load(self, context: AppContext):
        # 订阅事件
        context.event_bus.subscribe(EventType.NODE_EXECUTED, self.on_node_done)
        
        # 获取其他插件的工具
        tool = context.get_tool("excel_read")
        
        # 注册新工具
        context.register_tool(my_tool)
```

---

## 8. 持久化层架构

### 8.1 存储策略

| 数据类型 | 存储方式 | 生命周期 |
|----------|----------|----------|
| 工作流定义 | SQLite | 持久 |
| 插件配置 | SQLite | 持久 |
| API Key | SQLite (加密) | 持久 |
| 对话历史 | SQLite | 可配置保留期 |
| 运行时缓存 | 内存 | 会话级 |

### 8.2 核心实体

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Workflow   │     │  ApiKey     │     │  ChatHistory│
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id          │     │ id          │     │ id          │
│ name        │     │ provider    │     │ session_id  │
│ graph_json  │     │ key(encrypted)  │ │ role        │
│ created_at  │     │ created_at  │     │ content     │
│ updated_at  │     │             │     │ timestamp   │
└─────────────┘     └─────────────┘     └─────────────┘

┌─────────────┐     ┌─────────────┐
│  PluginConfig│     │  McpServer  │
├─────────────┤     ├─────────────┤
│ id          │     │ id          │
│ plugin_name │     │ name        │
│ config_json │     │ endpoint    │
│ enabled     │     │ enabled     │
└─────────────┘     └─────────────┘
```

### 8.3 SQLAlchemy模型模式

```python
class Workflow(Base):
    __tablename__ = "workflows"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    graph_json: Mapped[str] = mapped_column(Text)  # JSON序列化的NodeGraph
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
```

### 8.4 数据库位置

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%/OfficeTools/data.db` |
| macOS | `~/Library/Application Support/OfficeTools/data.db` |
| Linux | `~/.local/share/OfficeTools/data.db` |

---

## 9. 数据流

### 9.1 插件注册流程

```
1. 应用启动
       │
       ▼
2. PluginManager.discover_plugins() ──▶ 扫描plugins/
       │
       ▼
3. PluginManager.load_plugin(name)
       │
       ├──▶ importlib动态导入
       │
       ├──▶ 实例化PluginBase子类
       │
       └──▶ plugin.on_load(context)
              │
              ▼
4. plugin.get_tools() ──▶ List[ToolDefinition]
              │
              ├──▶ Toolkit.register_tool()
              │
              └──▶ NodeEngine.register_node_type()
              │
              ▼
5. EventBus.publish(PLUGIN_LOADED)
```

### 9.2 节点执行流程

```
1. 用户点击"执行"
       │
       ▼
2. NodeEngine.execute_graph(graph)
       │
       ▼
3. graph.topological_sort() ──▶ 执行顺序
       │
       ▼
4. For each node in order:
       │
       ├──▶ 传递数据 (前驱输出 → 当前输入)
       │
       ├──▶ node.state = RUNNING
       │
       ├──▶ tool.execute(**inputs)
       │
       ├──▶ 设置输出端口值
       │
       └──▶ node.state = SUCCESS/ERROR
       │
       ▼
5. EventBus.publish(NODE_EXECUTED)
```

### 9.3 Agent-工具调用流程

```
1. 用户输入自然语言请求
       │
       ▼
2. AgentScope Agent处理
       │
       ▼
3. Agent决定调用工具
       │
       ├──▶ 读取节点列表 (get_available_nodes)
       │
       └──▶ 生成工作流建议
              │
              ▼
4. 返回建议给用户
       │
       ▼
5. 用户确认/调整
       │
       ▼
6. 节点编辑器渲染工作流
```

---

## 10. 架构决策记录 (ADR)

### ADR-001: UI框架选择

**状态**: 已决定

**背景**: 需要选择桌面UI框架，要求支持复杂图形渲染（节点编辑器）和原生性能。

**决策**: 选择PySide6而非Flet/Electron。

**理由**:
- QGraphicsView原生支持复杂图形场景
- 信号槽机制适合事件驱动架构
- 无需额外运行时，启动快

**后果**:
- 仅支持桌面平台
- 需要学习Qt API

---

### ADR-002: AI框架选择

**状态**: 已决定

**背景**: 需要AI Agent能力，支持工具调用和对话。

**决策**: 选择AgentScope而非LangChain。

**理由**:
- 阿里开源，中文支持好
- Toolkit机制与我们的ToolDefinition契合
- ReAct模式内置支持

**后果**:
- 依赖阿里生态
- 社区相对较小

---

### ADR-003: 节点引擎选择

**状态**: 已决定

**背景**: 需要可视化节点编辑器，支持工作流执行。

**决策**: 自研节点引擎，不使用ComfyUI/Node-RED等现有方案。

**理由**:
- 需要与QGraphicsView深度集成
- 需要精确控制UI交互行为
- 需要统一ToolDefinition schema

**后果**:
- 开发成本较高
- 完全可控

---

### ADR-004: 持久化选择

**状态**: 已决定

**背景**: 需要存储工作流、配置、对话历史等数据。

**决策**: SQLite + SQLAlchemy。

**理由**:
- 单文件数据库，部署简单
- SQLAlchemy提供ORM抽象
- 无需额外数据库服务

**后果**:
- 不适合大规模并发
- 适合单用户桌面应用

---

### ADR-005: 插件系统设计

**状态**: 已决定

**背景**: 需要扩展机制，允许第三方添加功能。

**决策**: 自研轻量级插件系统 + 事件总线。

**理由**:
- 需要暴露AppContext给插件
- 需要事件驱动通信
- 不需要复杂的依赖注入

**后果**:
- 插件需要遵循我们的接口规范
- 无插件隔离（崩溃会影响主程序）

---

### ADR-006: Widget双输入机制

**状态**: 已决定

**背景**: 节点输入可以来自连接或用户直接输入。

**决策**: 采用LiteGraph模式 - 连接优先于Widget。

**理由**:
- 用户友好的默认值
- 连接时自动忽略Widget值
- 断开连接时恢复Widget值

**后果**:
- 需要在UI上清晰指示当前输入来源

---

### ADR-007: Agent辅助范围

**状态**: 已决定

**背景**: Agent在系统中的角色定位。

**决策**: Agent用于工作流设计和建议，不直接执行工作流。

**理由**:
- 用户需要审核和调整AI建议
- 避免AI误操作
- 保持用户控制权

**后果**:
- Agent不执行敏感操作
- 工作流执行由用户触发

---

## 11. 目录结构

```
office/
├── src/
│   ├── main.py                 # 应用入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── app_context.py      # 应用上下文
│   │   ├── event_bus.py        # 事件系统
│   │   ├── plugin_base.py      # 插件基类
│   │   ├── plugin_manager.py   # 插件管理器
│   │   ├── tool_definition.py  # 工具定义
│   │   └── node_base.py        # 自定义节点基类
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── node_engine.py      # 节点执行引擎
│   │   ├── node_graph.py       # 图数据结构
│   │   └── executor.py         # 执行器
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent_manager.py    # Agent管理
│   │   ├── toolkit.py          # AgentScope集成
│   │   ├── api_key_manager.py  # API Key管理
│   │   ├── mcp_manager.py      # MCP管理
│   │   └── skill_manager.py    # Skill管理
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py         # 数据库连接
│   │   ├── models.py           # SQLAlchemy模型
│   │   └── repositories.py     # 数据访问层
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # 主窗口
│   │   ├── chat_panel.py       # AI对话面板
│   │   └── node_editor/
│   │       ├── __init__.py
│   │       ├── scene.py        # QGraphicsScene
│   │       ├── view.py         # QGraphicsView
│   │       ├── node_item.py    # 节点图元
│   │       ├── connection_item.py  # 连接线图元
│   │       └── port_item.py    # 端口图元
│   └── utils/
│       ├── __init__.py
│       └── crypto.py           # 加密工具
├── plugins/
│   ├── __init__.py
│   ├── excel_tools/            # Excel工具插件
│   ├── table_tools/            # 表格工具插件
│   └── chat_tools/             # 聊天工具插件
├── docs/
│   └── ARCHITECTURE.md         # 本文档
├── tests/
│   └── ...
├── pyproject.toml
└── README.md
```

---

## 12. 依赖清单

### 12.1 核心依赖

| 包 | 版本 | 用途 |
|---|------|------|
| PySide6 | >=6.5 | UI框架 |
| agentscope | >=0.0.5 | AI Agent框架 |
| sqlalchemy | >=2.0 | ORM |
| cryptography | >=41.0 | API Key加密 |

### 12.2 可选依赖

| 包 | 用途 |
|---|------|
| pandas | 数据处理节点 |
| openpyxl | Excel读写 |
| python-docx | Word文档处理 |
| pillow | 图像处理 |

---

## 13. 术语表

| 术语 | 定义 |
|------|------|
| **节点(Node)** | 工作流中的执行单元，对应一个Tool |
| **端口(Port)** | 节点的输入/输出接口，有类型约束 |
| **连接(Connection)** | 节点间的数据传递通道 |
| **工作流(Workflow)** | 由节点和连接组成的有向无环图 |
| **插件(Plugin)** | 扩展功能的模块，提供一组Tool |
| **Tool** | 可执行的功能单元，同时服务Agent和节点 |
| **Widget** | 节点上的UI控件，允许用户直接输入 |
| **Agent** | AI助手，辅助设计工作流 |
| **MCP** | Model Context Protocol，外部服务接口 |
| **Skill** | 预定义的技能包，包含多个Tool |
| **AppContext** | 暴露给插件的程序上下文接口 |
| **EventBus** | 事件发布/订阅系统 |

---

*文档版本: 2.0*  
*最后更新: 2026-03-26*
