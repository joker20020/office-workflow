# 办公小工具整合平台 - 架构设计文档

> **目标受众**: AI Agent  
> **文档类型**: 架构设计（计划中的系统）  
> **核心目标**: 定义系统边界、组件职责、接口契约、关键决策

---

## 1. 系统概述

### 1.1 项目定位

基于PySide6的桌面办公工具整合平台，核心特性：

- **节点编辑器** - 可视化工作流设计，支持自定义节点扩展办公功能
- **节点包管理** - 从Git仓库下载、更新、启用/禁用、删除自定义节点包
- **Agent辅助** - AI助手读取节点列表，辅助设计工作流
- **插件系统** - 通过事件系统扩展功能，暴露程序上下文
- **统一存储** - SQLite + SQLAlchemy 持久化

### 1.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **PySide6原生** | Qt信号槽机制 + QSS样式 |
| **节点包扩展** | 办公功能通过节点包扩展，支持Git下载和管理 |
| **自研引擎** | 节点流引擎与UI深度集成 |
| **统一Schema** | NodeDefinition定义节点，同时服务Agent和工作流 |
| **事件驱动** | 插件通过事件系统通信，扩展程序功能 |
| **AgentScope集成** | Agent的tool/mcp/skill由AgentScope框架管理 |

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
| Git仓库 | git clone/pull | 自定义节点包下载与更新 |

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
│                              │                                     │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  节点包管理器 (NodePackageManager)           │   │
│  │  • Git下载/更新节点包                                        │   │
│  │  • 节点包启用/禁用                                           │   │
│  │  • 节点包删除                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     节点包目录 (node_packages/)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ 节点包A     │  │ 节点包B     │  │ 节点包C     │  ...            │
│  │ (git)       │  │ (git)       │  │ (local)     │                 │
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
| 节点包管理器 | 自定义节点包的下载、更新、启用、删除 | GitPython |

---

## 4. 核心接口契约

### 4.1 节点定义

每个办公小功能用一个节点表示。节点是工作流中的基本执行单元，通过节点包进行管理。

```python
@dataclass
class NodeDefinition:
    """节点定义 - 办公小功能的基本单元"""
    node_type: str              # 节点类型标识 (唯一)
    display_name: str           # 显示名称
    description: str            # 描述 (Agent可用此理解节点功能)
    category: str = "general"   # 分类
    icon: str = "🔧"            # 图标
    inputs: List["PortDefinition"] = field(default_factory=list)
    outputs: List["PortDefinition"] = field(default_factory=list)
    execute: Callable = field(default=None, repr=False)  # 执行函数
```

### 4.2 端口定义

端口定义节点间的数据类型约束。

```python
class PortType(Enum):
    """端口数据类型"""
    ANY = "any"
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    DATAFRAME = "dataframe"
    FILE = "file"
    LIST = "list"
    DICT = "dict"

@dataclass
class PortDefinition:
    """端口定义"""
    name: str
    type: PortType = PortType.ANY
    description: str = ""
    required: bool = True
    default: Any = None
```

### 4.3 插件权限定义

插件必须显式声明所需权限，遵循最低权限原则。

```python
class Permission(Enum):
    """插件权限枚举"""
    # 文件系统权限
    FILE_READ = "file.read"           # 读取文件
    FILE_WRITE = "file.write"         # 写入文件
    
    # 网络权限
    NETWORK = "network"               # 网络访问
    
    # Agent相关权限
    AGENT_TOOL = "agent.tool"         # 注册/注销Agent工具
    AGENT_MCP = "agent.mcp"           # 配置MCP服务
    AGENT_SKILL = "agent.skill"       # 加载/卸载Skill
    AGENT_CHAT = "agent.chat"         # 调用Agent对话
    
    # 事件系统权限
    EVENT_SUBSCRIBE = "event.subscribe"   # 订阅事件
    EVENT_PUBLISH = "event.publish"       # 发布事件
    
    # 节点权限
    NODE_READ = "node.read"           # 读取节点信息
    NODE_REGISTER = "node.register"   # 注册节点
    
    # 存储权限
    STORAGE_READ = "storage.read"     # 读取持久化数据
    STORAGE_WRITE = "storage.write"   # 写入持久化数据

@dataclass
class PermissionSet:
    """权限集合 - 用于声明插件所需权限"""
    permissions: Set[Permission] = field(default_factory=set)
    
    @classmethod
    def from_list(cls, perms: List[Union[Permission, str]]) -> "PermissionSet":
        """从列表创建权限集合"""
        return cls(permissions={Permission(p) if isinstance(p, str) else p for p in perms})
    
    def has(self, permission: Permission) -> bool:
        """检查是否包含某权限"""
        return permission in self.permissions
    
    def __or__(self, other: "PermissionSet") -> "PermissionSet":
        """权限集合并集"""
        return PermissionSet(self.permissions | other.permissions)
```

### 4.4 插件基类接口

插件用于扩展程序功能，通过事件系统与程序或其他插件通信。插件不提供节点。插件必须声明所需权限。

```python
class PluginBase(ABC):
    """插件基类 - 扩展程序功能"""
    name: str = "unknown"
    version: str = "1.0.0"
    description: str = ""
    author: str = ""                    # 作者信息
    permissions: PermissionSet = PermissionSet()  # 显式声明所需权限
    
    @classmethod
    def get_required_permissions(cls) -> PermissionSet:
        """获取插件所需权限（类方法，加载前检查）"""
        return cls.permissions
    
    def on_load(self, context: "AppContext") -> None:
        """插件加载时调用，可访问程序上下文（仅限已授权的权限）"""
        pass
    
    def on_unload(self) -> None:
        """插件卸载时调用，清理资源"""
        pass
```

**权限检查流程**:

```
插件加载流程:
┌─────────────────────────────────────────────────────────────────┐
│  1. PluginManager扫描插件                                        │
│           │                                                      │
│           ▼                                                      │
│  2. 读取 PluginBase.get_required_permissions()                   │
│           │                                                      │
│           ▼                                                      │
│  3. 检查权限是否已授权（用户确认或配置）                          │
│           │                                                      │
│     ┌─────┴─────┐                                                │
│     ▼           ▼                                                │
│  [已授权]    [未授权]                                             │
│     │           │                                                │
│     ▼           ▼                                                │
│  加载插件    弹窗请求用户确认                                     │
│                 │                                                │
│           ┌─────┴─────┐                                          │
│           ▼           ▼                                          │
│        [允许]      [拒绝]                                         │
│           │           │                                          │
│           ▼           ▼                                          │
│     授权并加载   跳过该插件                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 插件示例 - 使用AgentScope功能

```python
class MyAgentPlugin(PluginBase):
    """示例插件 - 利用AgentScope扩展功能"""
    name = "my_agent_plugin"
    version = "1.0.0"
    description = "使用AgentScope能力的插件"
    author = "Developer"
    
    # 显式声明所需权限
    permissions = PermissionSet.from_list([
        Permission.EVENT_SUBSCRIBE,   # 订阅事件
        Permission.AGENT_TOOL,        # 注册Agent工具
        Permission.AGENT_MCP,         # 配置MCP服务
        Permission.AGENT_SKILL,       # 加载Skill
    ])
    
    def on_load(self, context: AppContext):
        # 所有操作都在已声明的权限范围内
        # 1. 订阅事件 (需要 EVENT_SUBSCRIBE)
        context.event_bus.subscribe(EventType.NODE_EXECUTED, self.on_node_done)
        
        # 2. 注册Agent工具 (需要 AGENT_TOOL)
        context.agent.register_tool(
            name="my_custom_tool",
            description="自定义工具描述",
            func=self._my_tool_func
        )
        
        # 3. 配置MCP服务 (需要 AGENT_MCP)
        context.agent.add_mcp_server(
            name="my_mcp",
            endpoint="http://localhost:8080/mcp"
        )
        
        # 4. 加载Skill包 (需要 AGENT_SKILL)
        context.agent.load_skill("path/to/skill")
    
    def on_unload(self):
        # 清理注册的资源
        pass
    
    def _my_tool_func(self, param: str) -> dict:
        """自定义工具实现"""
        return {"result": f"processed: {param}"}
```

### 4.6 事件系统接口

```python
class EventType(Enum):
    # 插件事件
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    PLUGIN_PERMISSION_REQUEST = "plugin.permission_request"  # 权限请求事件
    # 节点事件
    NODE_REGISTERED = "node.registered"
    NODE_UNREGISTERED = "node.unregistered"
    NODE_EXECUTED = "node.executed"
    # 工作流事件
    WORKFLOW_SAVED = "workflow.saved"
    WORKFLOW_LOADED = "workflow.loaded"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    # Agent事件
    AGENT_MESSAGE = "agent.message"
    AGENT_TOOL_CALLED = "agent.tool_called"

class EventBus:
    def subscribe(self, event_type: EventType, handler: Callable) -> str: ...
    def unsubscribe(self, subscription_id: str) -> None: ...
    def publish(self, event_type: EventType, data: Any) -> None: ...
```

### 4.7 应用上下文接口

AppContext暴露程序功能给插件，所有访问都经过权限检查。

```python
class AppContext:
    """暴露给插件的程序上下文（带权限检查）"""
    
    # 基础组件
    event_bus: EventBus
    plugin_manager: "PluginManager"
    node_engine: "NodeEngine"
    storage: "StorageService"
    
    # AgentScope管理接口
    agent: "AgentScopeInterface"
    
    # 当前插件的权限信息
    _plugin_permissions: PermissionSet  # 内部使用
    
    def check_permission(self, permission: Permission) -> bool:
        """检查当前插件是否拥有指定权限"""
        return self._plugin_permissions.has(permission)
    def require_permission(self, permission: Permission) -> None:
        """要求权限，无权限时抛出PermissionDeniedError"""
        if not self.check_permission(permission):
            raise PermissionDeniedError(
                f"Plugin requires {permission.value} permission"
            )
    
    # 节点管理（需要 NODE_READ / NODE_REGISTER 权限）
    def register_node(self, node_def: NodeDefinition) -> None:
        self.require_permission(Permission.NODE_REGISTER)
        ...
    
    def unregister_node(self, node_type: str) -> None:
        self.require_permission(Permission.NODE_REGISTER)
        ...
    
    def get_node_definition(self, node_type: str) -> Optional[NodeDefinition]:
        self.require_permission(Permission.NODE_READ)
        ...
    
    def get_all_nodes(self) -> List[NodeDefinition]:
        self.require_permission(Permission.NODE_READ)
        ...
```

### 4.8 权限管理器接口

```python
@dataclass
class PluginPermissionRecord:
    """插件权限授权记录"""
    plugin_name: str
    granted_permissions: Set[Permission]
    granted_at: datetime
    granted_by_user: bool  # 是否由用户显式授权

class PermissionManager:
    """权限管理器"""
    
    def get_granted_permissions(self, plugin_name: str) -> Set[Permission]:
        """获取插件已授权的权限"""
        ...
    
    def grant_permissions(self, plugin_name: str, 
                          permissions: Set[Permission]) -> None:
        """授权给插件（用户确认后调用）"""
        ...
    
    def revoke_permissions(self, plugin_name: str,
                           permissions: Set[Permission]) -> None:
        """撤销插件权限"""
        ...
    
    def check_permission(self, plugin_name: str, 
                        permission: Permission) -> bool:
        """检查插件是否拥有某权限"""
        ...
    
    def request_permissions(self, plugin_name: str,
                           requested: Set[Permission]) -> bool:
        """请求权限授权（触发用户确认流程）"""
        ...
    
    def get_all_plugin_permissions(self) -> Dict[str, Set[Permission]]:
        """获取所有插件的权限配置"""
        ...
```

**权限请求流程**:

```
插件首次加载（需要新权限）:
┌─────────────────────────────────────────────────────────────────┐
│  PluginManager.load_plugin(name)                                 │
│           │                                                      │
│           ▼                                                      │
│  1. 获取插件声明的 permissions                                    │
│           │                                                      │
│           ▼                                                      │
│  2. PermissionManager.check_permission() 检查已授权权限           │
│           │                                                      │
│           ▼                                                      │
│  3. 计算未授权的权限 = requested - granted                        │
│           │                                                      │
│           ▼                                                      │
│  4. 如有未授权权限 → 弹窗请求用户确认                             │
│     ┌───────────────────────────────────────────────────────┐   │
│     │  插件 "my_agent_plugin" 请求以下权限:                   │   │
│     │                                                        │   │
│     │  ☑ EVENT_SUBSCRIBE - 订阅事件                          │   │
│     │  ☑ AGENT_TOOL - 注册Agent工具                          │   │
│     │  ☑ AGENT_MCP - 配置MCP服务                             │   │
│     │  ☐ FILE_WRITE - 写入文件          [额外风险]           │   │
│     │                                                        │   │
│     │  [允许全部]  [仅允许选中]  [拒绝]                        │   │
│     └───────────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│  5. 用户选择后，保存授权记录到SQLite                              │
│           │                                                      │
│           ▼                                                      │
│  6. 创建带权限限制的AppContext                                    │
│           │                                                      │
│           ▼                                                      │
│  7. 调用 plugin.on_load(context)                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.9 AgentScope接口

暴露给插件的AgentScope管理能力，所有操作都经过权限检查。

```python
class AgentScopeInterface:
    """AgentScope管理接口 - 暴露给插件使用（带权限检查）"""
    _context: AppContext  # 用于权限检查
    
    # API Key管理（需要 STORAGE_READ/WRITE）
    def set_api_key(self, provider: str, key: str) -> None:
        self._context.require_permission(Permission.STORAGE_WRITE)
        ...
    
    def get_api_key(self, provider: str) -> Optional[str]:
        self._context.require_permission(Permission.STORAGE_READ)
        ...
    
    def list_providers(self) -> List[str]:
        self._context.require_permission(Permission.STORAGE_READ)
        ...
    
    # Tool管理（需要 AGENT_TOOL）
    def register_tool(self, name: str, description: str, 
                      func: Callable, parameters: dict = None) -> None:
        self._context.require_permission(Permission.AGENT_TOOL)
        ...
    
    def unregister_tool(self, name: str) -> None:
        self._context.require_permission(Permission.AGENT_TOOL)
        ...
    
    def list_tools(self) -> List[dict]:
        self._context.require_permission(Permission.AGENT_TOOL)
        ...
    
    # MCP管理（需要 AGENT_MCP）
    def add_mcp_server(self, name: str, endpoint: str, 
                       config: dict = None) -> None:
        self._context.require_permission(Permission.AGENT_MCP)
        ...
    
    def remove_mcp_server(self, name: str) -> None:
        self._context.require_permission(Permission.AGENT_MCP)
        ...
    
    def list_mcp_servers(self) -> List[dict]:
        self._context.require_permission(Permission.AGENT_MCP)
        ...
    
    def enable_mcp_server(self, name: str) -> None:
        self._context.require_permission(Permission.AGENT_MCP)
        ...
    
    def disable_mcp_server(self, name: str) -> None:
        self._context.require_permission(Permission.AGENT_MCP)
        ...
    
    # Skill管理（需要 AGENT_SKILL）
    def load_skill(self, path: str) -> None:
        self._context.require_permission(Permission.AGENT_SKILL)
        ...
    
    def unload_skill(self, name: str) -> None:
        self._context.require_permission(Permission.AGENT_SKILL)
        ...
    
    def list_skills(self) -> List[dict]:
        self._context.require_permission(Permission.AGENT_SKILL)
        ...
    
    # Agent调用（需要 AGENT_CHAT）
    def chat(self, message: str, tools: List[str] = None) -> str:
        self._context.require_permission(Permission.AGENT_CHAT)
        ...
    
    def get_available_nodes_info(self) -> List[dict]:
        """获取所有节点信息，供Agent理解（需要 NODE_READ）"""
        self._context.require_permission(Permission.NODE_READ)
        ...
```

### 4.10 节点包管理接口

```python
@dataclass
class NodePackageMeta:
    """节点包元信息"""
    id: str                    # 唯一标识
    name: str                  # 显示名称
    version: str               # 版本号
    author: str                # 作者
    description: str           # 描述
    repository_url: str        # Git仓库地址
    branch: str = "main"       # 分支
    local_path: Path = None    # 本地安装路径
    enabled: bool = True       # 是否启用

class NodePackageManager:
    """节点包管理器"""
    def install_from_git(self, url: str, branch: str = "main") -> bool: ...
    def update_package(self, package_id: str) -> bool: ...
    def enable_package(self, package_id: str) -> None: ...
    def disable_package(self, package_id: str) -> None: ...
    def remove_package(self, package_id: str) -> bool: ...
    def get_installed_packages(self) -> List[NodePackageMeta]: ...
    def get_available_updates(self) -> List[str]: ...
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

**节点执行流程**:

```
┌─────────────────────────────────────────────────────┐
│                    Node (节点)                      │
│  ┌───────────────────────────────────────────────┐  │
│  │  node_type: str      # 节点类型               │  │
│  │  inputs: Dict        # 输入端口值             │  │
│  │  outputs: Dict       # 输出端口值             │  │
│  │  position: Tuple     # UI位置                 │  │
│  │  state: NodeState    # 执行状态               │  │
│  └───────────────────────────────────────────────┘  │
│                       │                             │
│                       ▼                             │
│  ┌───────────────────────────────────────────────┐  │
│  │     NodeDefinition.execute(**inputs)          │  │
│  │                    ↓                          │  │
│  │           outputs = result                    │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 5.2 执行模型

| 阶段 | 操作 |
|------|------|
| 1. 拓扑排序 | 基于连接关系计算执行顺序 |
| 2. 数据传递 | 从前驱节点输出传递到当前节点输入 |
| 3. 节点执行 | 调用 `node_def.execute(**inputs)` 获取结果 |
| 4. 状态更新 | 更新节点状态 (idle→running→success/error) |

### 5.3 NodeEngine接口

```python
class NodeEngine:
    """节点执行引擎"""
    
    def register_node_type(self, node_def: NodeDefinition) -> None: ...
    def unregister_node_type(self, node_type: str) -> None: ...
    def create_node(self, node_type: str, position: Tuple) -> Node: ...
    def execute_node(self, node: Node) -> bool: ...
    def execute_graph(self, graph: NodeGraph) -> bool: ...
```

### 5.4 Widget双输入机制

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

Agent的tool/mcp/skill由**AgentScope框架**管理，本程序通过AgentScope提供的接口进行集成。

```
┌─────────────────────────────────────────────────────────────────────┐
│                          本程序                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    NodeEngine                                  │  │
│  │  • 节点注册表 (NodeDefinition列表)                             │  │
│  │  • get_available_nodes() → 节点描述列表                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              │ 提供节点信息                          │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                 AgentScope Integration Layer                   │  │
│  │  • 将节点信息转换为Agent可理解的格式                            │  │
│  │  • 接收Agent生成的工作流描述                                   │  │
│  │  • 渲染工作流到节点编辑器                                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ 调用
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AgentScope Framework                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Agent     │  │   Tool      │  │    MCP      │                 │
│  │  Instance   │  │  Registry   │  │  Manager    │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│  ┌─────────────┐  ┌─────────────┐                                  │
│  │   Skill     │  │  API Key    │  (由AgentScope管理)              │
│  │  Manager    │  │  Manager    │                                  │
│  └─────────────┘  └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 程序与AgentScope的交互

| 方向 | 内容 | 说明 |
|------|------|------|
| 程序 → AgentScope | 节点列表 | 所有可用节点的类型、描述、参数 |
| AgentScope → 程序 | 工作流建议 | Agent生成的节点+连接描述 |

### 6.3 Agent核心能力

| 能力 | 说明 |
|------|------|
| 节点列表读取 | 获取所有可用节点类型和描述 (通过本程序接口) |
| 工作流建议 | 基于用户需求推荐节点组合 |
| 工作流验证 | 检查连接合理性、类型匹配 |
| 自然语言生成工作流 | 从描述生成节点图 |

**注意**: Agent的tool/mcp/skill管理完全由AgentScope框架负责，本程序不涉及。

### 6.4 Agent-工作流交互

```
User Request ──▶ AgentScope Agent ──▶ 读取节点列表 (本程序提供)
                                           │
                                           ▼
                                    分析用户需求
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │  生成/建议工作流    │
                                │  (节点+连接描述)    │
                                └──────────┬──────────┘
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │  本程序接收描述      │
                                │  渲染到节点编辑器    │
                                └─────────────────────┘
```

### 6.5 API Key存储

虽然AgentScope管理API Key的使用，但本程序提供安全的存储：

| 资源类型 | 存储方式 | 用途 |
|----------|----------|------|
| API Key | SQLite (加密) | 供AgentScope读取使用 |

---

## 7. 插件系统架构

### 7.1 插件定位

插件用于**扩展程序功能**，通过事件系统与程序或其他插件通信。插件**不提供节点**（节点通过节点包管理）。

插件可以：
- 订阅和发布事件
- 访问AgentScope的tool/mcp/skill管理接口
- 扩展程序UI
- 添加自定义功能

### 7.2 插件生命周期

```
┌─────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────┐
│  发现   │───▶│  权限检查    │───▶│  加载       │───▶│  活跃   │
└─────────┘    └──────────────┘    └─────────────┘    └────┬────┘
                      │                                     │
                      ▼                                     ▼
               ┌─────────────┐                        ┌─────────┐
               │ 用户确认    │                        │  卸载   │
               │ (如需权限)  │                        └─────────┘
               └─────────────┘
```

| 阶段 | 操作 |
|------|------|
| 发现 | 扫描plugins/目录，识别插件包/模块 |
| 权限检查 | 读取插件声明的permissions，检查是否已授权 |
| 用户确认 | 未授权权限弹窗请求用户确认（首次加载） |
| 加载 | importlib动态导入，创建带权限限制的AppContext，调用on_load(context) |
| 活跃 | 在已授权权限范围内响应事件、使用接口 |
| 卸载 | 调用on_unload()，清理注册的资源 |

### 7.3 事件系统

```
┌─────────────────────────────────────────────────────┐
│                    EventBus                         │
│                                                     │
│  Plugin A ──▶ [PLUGIN_LOADED] ──▶ Plugin B         │
│                                                     │
│  NodeEngine ──▶ [NODE_EXECUTED] ──▶ Plugin A, UI   │
│                                                     │
│  NodeEngine ──▶ [WORKFLOW_SAVED] ──▶ Storage       │
│                                                     │
│  AgentScope ──▶ [AGENT_MESSAGE] ──▶ Plugin A, UI   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**核心事件类型**:

| 事件 | 发布者 | 订阅者 |
|------|--------|--------|
| PLUGIN_LOADED | PluginManager | UI, Logger |
| PLUGIN_UNLOADED | PluginManager | UI |
| NODE_REGISTERED | NodePackageManager | UI |
| NODE_EXECUTED | NodeEngine | UI, Logger, Plugins |
| WORKFLOW_SAVED | NodeEngine | Storage |
| AGENT_MESSAGE | AgentScope | UI, Plugins |

### 7.4 插件示例

```python
class MyAgentPlugin(PluginBase):
    """示例插件 - 利用AgentScope扩展功能"""
    name = "my_agent_plugin"
    version = "1.0.0"
    description = "使用AgentScope能力的插件"
    author = "Developer"
    
    # 显式声明所需权限（最低权限原则）
    permissions = PermissionSet.from_list([
        Permission.EVENT_SUBSCRIBE,   # 订阅事件
        Permission.AGENT_TOOL,        # 注册Agent工具
        Permission.AGENT_MCP,         # 配置MCP服务
        Permission.AGENT_SKILL,       # 加载Skill
        Permission.NODE_READ,         # 读取节点信息
    ])
    
    def on_load(self, context: AppContext):
        # 所有操作都在已声明的权限范围内
        # 超出权限的操作会抛出 PermissionDeniedError
        
        # 1. 订阅事件 (需要 EVENT_SUBSCRIBE)
        context.event_bus.subscribe(
            EventType.NODE_EXECUTED, 
            self.on_node_done
        )
        
        # 2. 注册Agent工具 (需要 AGENT_TOOL)
        context.agent.register_tool(
            name="my_custom_tool",
            description="自定义工具描述",
            func=self._my_tool_func
        )
        
        # 3. 配置MCP服务 (需要 AGENT_MCP)
        context.agent.add_mcp_server(
            name="my_mcp",
            endpoint="http://localhost:8080/mcp"
        )
        
        # 4. 加载Skill包 (需要 AGENT_SKILL)
        context.agent.load_skill("path/to/skill")
        
        # 5. 获取节点信息 (需要 NODE_READ)
        nodes = context.get_all_nodes()
    
    def on_unload(self):
        # 清理注册的资源
        pass
    
    def on_node_done(self, event_data):
        # 处理节点执行完成事件
        pass
    
    def _my_tool_func(self, param: str) -> dict:
        return {"result": f"processed: {param}"}
```

### 7.5 权限管理界面

插件首次加载时，用户会看到权限请求对话框：

```
┌──────────────────────────────────────────────────────────────────┐
│  ⚠️ 插件权限请求                                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  插件 "my_agent_plugin" v1.0.0                                   │
│  作者: Developer                                                 │
│  描述: 使用AgentScope能力的插件                                   │
│                                                                  │
│  请求以下权限:                                                    │
│                                                                  │
│  ✅ EVENT_SUBSCRIBE                                              │
│     订阅事件，接收系统事件通知                                     │
│                                                                  │
│  ✅ AGENT_TOOL                                                   │
│     注册Agent工具，扩展AI能力                                     │
│                                                                  │
│  ✅ AGENT_MCP                                                    │
│     配置MCP服务，连接外部工具                                     │
│                                                                  │
│  ✅ AGENT_SKILL                                                  │
│     加载Skill包，增强Agent技能                                    │
│                                                                  │
│  ✅ NODE_READ                                                    │
│     读取节点信息（只读）                                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  [允许全部]    [选择允许]    [拒绝]    [以后再说]           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  💡 提示: 您可以随时在设置中修改已授权的权限                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. 自定义节点管理架构

### 8.1 节点包结构

```
node_packages/
├── package_A/                    # 从Git安装的节点包
│   ├── package.json             # 包元信息
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── node_1.py            # 节点实现
│   │   └── node_2.py
│   └── requirements.txt         # 依赖（可选）
├── package_B/                    # 另一个节点包
│   └── ...
└── local_nodes/                  # 用户本地自定义节点
    └── my_node.py
```

**package.json 格式**:

```json
{
    "id": "com.example.text-tools",
    "name": "文本处理工具",
    "version": "1.2.0",
    "author": "Developer",
    "description": "文本处理相关节点",
    "repository": "https://github.com/example/text-tools",
    "branch": "main",
    "nodes": ["text_split", "text_join", "text_replace"]
}
```

### 8.2 节点包生命周期

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Git下载    │───▶│   安装      │───▶│   启用      │───▶│   活跃      │
└─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
       │                  │                  │                   │
       │                  │                  │                   ▼
       │                  │                  │            ┌─────────────┐
       │                  │                  └───────────▶│   禁用      │
       │                  │                                └──────┬──────┘
       │                  │                                       │
       │                  ▼                                       ▼
       │            ┌─────────────┐                        ┌─────────────┐
       │            │   更新      │                        │   删除      │
       │            └─────────────┘                        └─────────────┘
       │                  │
       └──────────────────┘
```

| 操作 | 说明 |
|------|------|
| **Git下载** | `git clone` 到 `node_packages/{package_id}/` |
| **安装** | 解析package.json，安装requirements.txt依赖 |
| **启用** | 加载节点模块，注册到NodeEngine |
| **禁用** | 从NodeEngine注销节点，保留本地文件 |
| **更新** | `git pull`，重新加载节点 |
| **删除** | 删除本地目录，清理注册信息 |

### 8.3 管理流程

#### 8.3.1 从Git安装节点包

```
1. 用户提供Git URL
       │
       ▼
2. NodePackageManager.install_from_git(url, branch)
       │
       ├──▶ 验证URL有效性
       │
       ├──▶ git clone 到临时目录
       │
       ├──▶ 解析 package.json
       │
       ├──▶ 检查依赖兼容性
       │
       ├──▶ pip install -r requirements.txt (如有)
       │
       ├──▶ 移动到 node_packages/{package_id}/
       │
       ├──▶ 存储元信息到SQLite
       │
       └──▶ EventBus.publish(PACKAGE_INSTALLED)
              │
              ▼
3. 自动启用（或等待用户手动启用）
```

#### 8.3.2 更新节点包

```
1. 用户点击"更新"
       │
       ▼
2. NodePackageManager.update_package(package_id)
       │
       ├──▶ git fetch + git pull
       │
       ├──▶ 检查版本变化
       │
       ├──▶ 如有requirements变化，重新安装
       │
       ├──▶ 更新SQLite中的元信息
       │
       └──▶ EventBus.publish(PACKAGE_UPDATED)
              │
              ▼
3. 如已启用，重新加载节点
```

#### 8.3.3 启用/禁用节点包

```
启用:
┌─────────────────────────────────────────┐
│ NodePackageManager.enable_package(id)   │
│         │                               │
│         ├──▶ importlib加载节点模块       │
│         │                               │
│         ├──→ 注册节点到NodeEngine        │
│         │                               │
│         └──▶ 更新SQLite enabled=true    │
└─────────────────────────────────────────┘

禁用:
┌─────────────────────────────────────────┐
│ NodePackageManager.disable_package(id)  │
│         │                               │
│         ├──▶ 从NodeEngine注销节点        │
│         │                               │
│         ├──▶ 保留本地文件                │
│         │                               │
│         └──▶ 更新SQLite enabled=false   │
└─────────────────────────────────────────┘
```

### 8.4 安全考虑

| 风险 | 缓解措施 |
|------|----------|
| 恶意代码 | 用户确认后才安装；显示package.json内容 |
| 依赖冲突 | 使用虚拟环境或pip check |
| 网络问题 | 超时机制；重试逻辑；离线模式 |
| 版本不兼容 | 版本检查；降级提示 |

### 8.5 节点包市场（未来扩展）

```
┌─────────────────────────────────────────────────────┐
│                  节点包市场 (可选)                   │
├─────────────────────────────────────────────────────┤
│  • 官方维护的节点包索引                             │
│  • 社区提交的节点包                                 │
│  • 评分和下载统计                                   │
│  • 一键安装                                         │
└─────────────────────────────────────────────────────┘
```

---

## 9. 持久化层架构

### 9.1 存储策略

| 数据类型 | 存储方式 | 生命周期 |
|----------|----------|----------|
| 工作流定义 | SQLite | 持久 |
| 插件配置 | SQLite | 持久 |
| 插件权限授权 | SQLite | 持久 |
| API Key | SQLite (加密) | 持久 |
| 对话历史 | SQLite | 可配置保留期 |
| 节点包元信息 | SQLite | 持久 |
| 运行时缓存 | 内存 | 会话级 |

### 9.2 核心实体

```
    ┌─────────────┐     ┌─────────────┐
    │  ApiKey     │     │  ChatHistory│
    ├─────────────┤     ├─────────────┤
    │ id          │     │ id          │
    │ provider    │     │ session_id  │
    │ key(encrypted)  │ │ role        │
    │ created_at  │     │ content     │
    │             │     │ timestamp   │
    └─────────────┘     └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  PluginConfig│     │  McpServer  │     │  NodePackage    │
├─────────────┤     ├─────────────┤     ├─────────────────┤
│ id          │     │ id          │     │ id              │
│ plugin_name │     │ name        │     │ name            │
│ config_json │     │ endpoint    │     │ version         │
│ enabled     │     │ enabled     │     │ author          │
└─────────────┘     └─────────────┘     │ repository_url  │
                                        │ branch           │
┌─────────────────────┐                 │ local_path       │
│ PluginPermission    │                 │ enabled          │
├─────────────────────┤                 │ installed_at     │
│ id                  │                 │ updated_at       │
│ plugin_name         │                 └─────────────────┘
│ permission          │
│ granted_at          │
│ granted_by_user     │
└─────────────────────┘
```

### 9.3 SQLAlchemy模型模式

```python
class Workflow(Base):
    __tablename__ = "workflows"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    graph_json: Mapped[str] = mapped_column(Text)  # JSON序列化的NodeGraph
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
```

### 9.4 数据库位置

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%/OfficeTools/data.db` |
| macOS | `~/Library/Application Support/OfficeTools/data.db` |
| Linux | `~/.local/share/OfficeTools/data.db` |

---

## 10. 数据流

### 10.1 插件加载流程（含权限检查）

```
1. 应用启动
       │
       ▼
2. PluginManager.discover_plugins() ──▶ 扫描plugins/
       │
       ▼
3. 对每个发现的插件:
       │
       ├──▶ 读取 PluginBase.permissions 获取声明的权限
       │
       ├──▶ PermissionManager.check_permissions(name, permissions)
       │         │
       │         ├──▶ 查询已授权权限
       │         │
       │         └──▶ 计算未授权权限 = requested - granted
       │
       ▼
4. 如有未授权权限 → 弹窗请求用户确认
       │
       ├──▶ [用户允许] → PermissionManager.grant_permissions()
       │
       └──▶ [用户拒绝] → 跳过该插件
       │
       ▼
5. PluginManager.load_plugin(name)
       │
       ├──▶ importlib动态导入
       │
       ├──▶ 创建 AppContext（带权限限制）
       │
       └──▶ plugin.on_load(context)
              │
              ├──▶ 订阅事件（权限检查）
              │
              ├──▶ 注册Agent工具（权限检查）
              │
              └──▶ 配置MCP/Skill（权限检查）
```

### 10.2 节点包安装流程

```
1. 用户提供Git仓库URL
       │
       ▼
2. NodePackageManager.install_from_git(url, branch)
       │
       ├──▶ git clone 到临时目录
       │
       ├──▶ 解析 package.json
       │
       ├──▶ 检查依赖并安装
       │
       ├──▶ 移动到 node_packages/{id}/
       │
       └──▶ 保存到 NodePackage 表
              │
              ▼
3. EventBus.publish(PACKAGE_INSTALLED)
       │
       ▼
4. 默认启用 → NodePackageManager.enable_package(id)
       │
       ├──▶ 加载节点模块
       │
       └──▶ 注册到 NodeEngine
```

### 10.3 节点包更新流程

```
1. 检测可用更新 / 用户点击更新
       │
       ▼
2. NodePackageManager.update_package(id)
       │
       ├──▶ git fetch + git pull (node_packages/{id}/)
       │
       ├──▶ 比较版本变化
       │
       ├──▶ 如有新依赖，执行安装
       │
       └──▶ 更新 NodePackage 表
              │
              ▼
3. EventBus.publish(PACKAGE_UPDATED)
       │
       ▼
4. 如已启用，重新加载节点
```

### 10.4 节点执行流程

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
       ├──▶ node_def = get_node_definition(node.node_type)
       │
       ├──▶ result = node_def.execute(**inputs)
       │
       ├──▶ 设置输出端口值
       │
       └──▶ node.state = SUCCESS/ERROR
       │
       ▼
5. EventBus.publish(NODE_EXECUTED)
```

### 10.5 Agent-工作流交互流程

```
1. 用户输入自然语言请求
       │
       ▼
2. 程序将节点列表发送给AgentScope
       │
       ├──▶ NodeEngine.get_available_nodes()
       │
       └──▶ 转换为Agent可理解的格式
       │
       ▼
3. AgentScope Agent处理
       │
       ▼
4. Agent生成工作流建议
       │
       ├──▶ 节点类型 + 参数
       │
       └──▶ 节点连接关系
       │
       ▼
5. 返回建议给用户
       │
       ▼
6. 用户确认/调整
       │
       ▼
7. 程序解析工作流描述 ──▶ 节点编辑器渲染
```

### 10.6 节点包管理流程

#### 安装节点包

```
1. 用户提供Git URL和分支
       │
       ▼
2. NodePackageManager.install_from_git(url, branch)
       │
       ├──▶ git clone 到临时目录
       │
       ├──▶ 解析 package.json
       │
       ├──▶ 验证节点包格式
       │
       ├──▶ pip install -r requirements.txt
       │
       ├──▶ 移动到 node_packages/{id}/
       │
       ├──▶ 保存到SQLite (NodePackage表)
       │
       └──▶ EventBus.publish(PACKAGE_INSTALLED)
              │
              ▼
3. 自动启用（或等待用户启用）
```

#### 更新节点包

```
1. 用户点击"更新"
       │
       ▼
2. NodePackageManager.update_package(id)
       │
       ├──▶ cd node_packages/{id}
       │
       ├──▶ git fetch && git pull
       │
       ├──▶ 对比版本变化
       │
       ├──▶ 如有新依赖， pip install
       │
       ├──▶ 更新SQLite中的version
       │
       └──▶ EventBus.publish(PACKAGE_UPDATED)
              │
              ▼
3. 如已启用，重新加载节点
```

#### 启用/禁用节点包

```
启用:
1. NodePackageManager.enable_package(id)
       │
       ├──▶ 更新SQLite enabled=true
       │
       ├──▶ importlib加载节点模块
       │
       ├──▶ 注册节点到NodeEngine
       │
       └──▶ EventBus.publish(PACKAGE_ENABLED)

禁用:
1. NodePackageManager.disable_package(id)
       │
       ├──▶ 从NodeEngine注销节点
       │
       ├──▶ 更新SQLite enabled=false
       │
       └──▶ EventBus.publish(PACKAGE_DISABLED)
```

#### 删除节点包

```
1. NodePackageManager.remove_package(id)
       │
       ├──▶ 如已启用，先禁用
       │
       ├──▶ 删除 node_packages/{id}/ 目录
       │
       ├──▶ 从SQLite删除记录
       │
       └──▶ EventBus.publish(PACKAGE_REMOVED)
```

---

## 11. 架构决策记录 (ADR)

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

### ADR-008: 自定义节点包管理

**状态**: 已决定

**背景**: 用户需要从Git仓库下载和管理自定义节点包，支持更新、启用、禁用、删除操作。

**决策**: 实现NodePackageManager组件，使用GitPython库管理Git操作，SQLite存储元信息。

**理由**:
- 用户需要便捷地获取社区贡献的节点
- 需要版本管理和更新机制
- 需要灵活启用/禁用节点包而不删除

**后果**:
- 需要GitPython依赖
- 需要处理网络异常
- 节点包可能包含恶意代码（需要用户确认）

---

### ADR-009: 插件权限管理

**状态**: 已决定

**背景**: 插件可以访问程序上下文和AgentScope能力，存在安全风险。需要防止恶意插件滥用权限。

**决策**: 实现显式权限声明 + 用户授权机制，遵循最低权限原则。

**理由**:
- 插件可能来自第三方，需要安全隔离
- 用户需要了解插件访问了哪些资源
- 最小权限原则降低安全风险
- 权限持久化避免重复确认

**权限类别**:

| 类别 | 权限 | 风险等级 |
|------|------|----------|
| 文件系统 | FILE_READ, FILE_WRITE | 高 |
| 网络 | NETWORK | 中 |
| Agent | AGENT_TOOL, AGENT_MCP, AGENT_SKILL, AGENT_CHAT | 中 |
| 事件 | EVENT_SUBSCRIBE, EVENT_PUBLISH | 低 |
| 节点 | NODE_READ, NODE_REGISTER | 低 |
| 存储 | STORAGE_READ, STORAGE_WRITE | 中 |

**后果**:
- 插件必须显式声明权限
- 首次加载需用户确认
- 增加少量开发复杂度
- 提升系统安全性

---

## 12. 目录结构

```
office/
├── src/
│   ├── main.py                 # 应用入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── app_context.py      # 应用上下文（带权限检查）
│   │   ├── event_bus.py        # 事件系统
│   │   ├── plugin_base.py      # 插件基类（含权限声明）
│   │   ├── plugin_manager.py   # 插件管理器
│   │   └── permission_manager.py # 权限管理器
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── node_engine.py      # 节点执行引擎
│   │   ├── node_graph.py       # 图数据结构
│   │   └── executor.py         # 执行器
│   ├── agent/                  # AgentScope集成层
│   │   ├── __init__.py
│   │   ├── agent_integration.py # AgentScope集成
│   │   ├── node_adapter.py     # 节点信息适配器
│   │   └── workflow_renderer.py # 工作流渲染
│   ├── nodes/                  # 节点包管理模块
│   │   ├── __init__.py
│   │   ├── package_manager.py  # 节点包管理器
│   │   ├── package_loader.py   # 节点包加载器
│   │   └── git_utils.py        # Git操作工具
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py         # 数据库连接
│   │   ├── models.py           # SQLAlchemy模型
│   │   └── repositories.py     # 数据访问层
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # 主窗口
│   │   ├── chat_panel.py       # AI对话面板
│   │   ├── package_panel.py    # 节点包管理面板
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
├── plugins/                     # 内置插件目录
│   ├── __init__.py
│   ├── excel_tools/            # Excel工具插件
│   ├── table_tools/            # 表格工具插件
│   └── chat_tools/             # 聊天工具插件
├── node_packages/              # 自定义节点包目录
│   ├── package_A/              # 从Git安装的节点包
│   ├── package_B/              # 另一个节点包
│   └── local_nodes/            # 用户本地自定义节点
├── docs/
│   └── ARCHITECTURE.md         # 本文档
├── tests/
│   └── ...
├── pyproject.toml
└── README.md
```

---

## 13. 依赖清单

### 13.1 核心依赖

| 包 | 版本 | 用途 |
|---|------|------|
| PySide6 | >=6.5 | UI框架 |
| agentscope | >=0.0.5 | AI Agent框架 |
| sqlalchemy | >=2.0 | ORM |
| cryptography | >=41.0 | API Key加密 |
| GitPython | >=3.1 | 自定义节点包Git操作 |

### 13.2 可选依赖

| 包 | 用途 |
|---|------|
| pandas | 数据处理节点 |
| openpyxl | Excel读写 |
| python-docx | Word文档处理 |
| pillow | 图像处理 |

---

## 14. 术语表

| 术语 | 定义 |
|------|------|
| **节点(Node)** | 工作流中的执行单元，包含输入输出端口和执行函数 |
| **端口(Port)** | 节点的输入/输出接口，有类型约束 |
| **连接(Connection)** | 节点间的数据传递通道 |
| **工作流(Workflow)** | 由节点和连接组成的有向无环图 |
| **插件(Plugin)** | 扩展程序功能的模块，通过事件系统通信，不提供节点 |
| **节点定义(NodeDefinition)** | 节点的元信息，包括类型、端口、执行函数等 |
| **Widget** | 节点上的UI控件，允许用户直接输入 |
| **Agent** | AI助手（由AgentScope框架管理），辅助设计工作流 |
| **AgentScope** | 阿里开源的AI Agent框架，管理tool/mcp/skill |
| **MCP** | Model Context Protocol（由AgentScope管理） |
| **Skill** | 预定义技能包（由AgentScope管理） |
| **AppContext** | 暴露给插件的程序上下文接口（带权限检查） |
| **EventBus** | 事件发布/订阅系统 |
| **节点包(NodePackage)** | 从Git仓库安装的自定义节点集合 |
| **NodeEngine** | 节点执行引擎，管理节点注册和工作流执行 |
| **权限(Permission)** | 插件访问系统资源的授权，需显式声明 |
| **权限集(PermissionSet)** | 插件声明的所需权限集合 |
| **最低权限原则** | 插件只申请其功能所需的最小权限集合 |

---

## 15. 渐进式实现路线

### 总体原则

- **垂直切片优先** - 每个阶段交付可运行的端到端功能
- **依赖优先** - 先实现被依赖的底层模块
- **增量验证** - 每个阶段完成后进行集成测试
- **用户价值导向** - 优先交付用户可感知的功能

---

### Phase 1: 基础框架 (2-3周)

**目标**: 建立可运行的桌面应用骨架

```
┌─────────────────────────────────────────────────────┐
│                 Phase 1 交付物                      │
├─────────────────────────────────────────────────────┤
│  ✓ PySide6主窗口 + NavigationRail                   │
│  ✓ EventBus事件系统                                 │
│  ✓ SQLite数据库初始化                               │
│  ✓ AppContext基础实现                               │
│  ✓ 基本的插件加载机制                               │
└─────────────────────────────────────────────────────┘
```

**任务清单**:

| # | 任务 | 依赖 | 预估 |
|---|------|------|------|
| 1.1 | 项目结构初始化 | - | 1天 |
| 1.2 | PySide6主窗口 + 侧边栏导航 | 1.1 | 2天 |
| 1.3 | EventBus实现 (subscribe/publish) | 1.1 | 1天 |
| 1.4 | SQLAlchemy数据库连接 + 基础模型 | 1.1 | 1天 |
| 1.5 | PluginBase抽象类 | 1.1 | 0.5天 |
| 1.6 | PluginManager基础版 (发现/加载) | 1.5 | 2天 |
| 1.7 | AppContext整合 | 1.3, 1.4, 1.6 | 1天 |

**验证标准**:
- [ ] 应用启动显示主窗口
- [ ] EventBus可正常发布/订阅事件
- [ ] SQLite数据库文件正确创建
- [ ] 可加载一个空插件

---

### Phase 2: 节点编辑器核心 (3-4周)

**目标**: 实现可视化节点编辑和执行

```
┌─────────────────────────────────────────────────────┐
│                 Phase 2 交付物                      │
├─────────────────────────────────────────────────────┤
│  ✓ QGraphicsView节点画布                            │
│  ✓ 节点拖放 + 连线                                  │
│  ✓ NodeEngine执行引擎                               │
│  ✓ 工作流保存/加载                                  │
│  ✓ 第一个内置插件 (如文本处理)                      │
└─────────────────────────────────────────────────────┘
```

**任务清单**:

| # | 任务 | 依赖 | 预估 |
|---|------|------|------|
| 2.1 | PortDefinition | Phase 1 | 1天 |
| 2.2 | NodeGraph数据结构 (Node/Connection) | 2.1 | 2天 |
| 2.3 | NodeEngine执行引擎 (拓扑排序+执行) | 2.2 | 3天 |
| 2.4 | QGraphicsScene节点场景 | Phase 1 | 2天 |
| 2.5 | NodeGraphicsItem (节点渲染) | 2.4 | 2天 |
| 2.6 | ConnectionGraphicsItem (贝塞尔曲线) | 2.5 | 2天 |
| 2.7 | 节点拖放 + 端口连接交互 | 2.5, 2.6 | 3天 |
| 2.8 | NodeEngine与UI状态同步 | 2.3, 2.7 | 2天 |
| 2.9 | 工作流JSON序列化/反序列化 | 2.2 | 1天 |
| 2.10 | 内置插件: 文本处理节点 | 2.1, 2.3 | 2天 |

**验证标准**:
- [ ] 可拖放节点到画布
- [ ] 可连接节点端口
- [ ] 点击执行可运行工作流
- [ ] 工作流可保存和重新加载
- [ ] 文本处理节点正常工作

---

### Phase 3: Agent集成 (2-3周)

**目标**: AI助手可读取节点并辅助工作流设计

```
┌─────────────────────────────────────────────────────┐
│                 Phase 3 交付物                      │
├─────────────────────────────────────────────────────┤
│  ✓ AgentScope框架集成                                │
│  ✓ AI对话面板                                       │
│  ✓ API Key安全存储                                  │
│  ✓ 节点列表查询接口                                 │
│  ✓ 工作流建议生成功能                               │
└─────────────────────────────────────────────────────┘
```

**任务清单**:

| # | 任务 | 依赖 | 预估 |
|---|------|------|------|
| 3.1 | ApiKeyManager + 加密存储 | Phase 1.4 | 1天 |
| 3.2 | AgentScope框架集成 | 3.1 | 2天 |
| 3.3 | NodeEngine.get_available_nodes() 接口 | Phase 2.3 | 1天 |
| 3.4 | ChatPanel UI (对话界面) | Phase 1.2 | 2天 |
| 3.5 | 对话历史存储 | 3.4, Phase 1.4 | 1天 |
| 3.6 | 节点信息转换为Agent可读格式 | 3.2, 3.3 | 1天 |
| 3.7 | Agent工作流建议生成 | 3.6 | 2天 |
| 3.8 | Agent响应解析并渲染到节点编辑器 | 3.7, Phase 2.7 | 2天 |

**验证标准**:
- [ ] 可配置API Key
- [ ] AI对话面板可发送消息
- [ ] Agent可返回可用节点列表
- [ ] Agent可根据描述建议工作流
- [ ] 建议的工作流可渲染到画布

---

### Phase 4: 插件系统完善 + 权限管理 (2-3周)

**目标**: 完整的插件生命周期、权限管理和事件通信

```
┌─────────────────────────────────────────────────────┐
│                 Phase 4 交付物                      │
├─────────────────────────────────────────────────────┤
│  ✓ 完整的插件生命周期                               │
│  ✓ 权限声明与检查机制                               │
│  ✓ 权限授权UI（用户确认对话框）                     │
│  ✓ 事件系统完善                                     │
│  ✓ 插件配置持久化                                   │
│  ✓ 迁移现有脚本为插件                               │
└─────────────────────────────────────────────────────┘
```

**任务清单**:

| # | 任务 | 依赖 | 预估 |
|---|------|------|------|
| 4.1 | Permission枚举 + PermissionSet类 | Phase 1.1 | 0.5天 |
| 4.2 | PluginBase添加permissions属性 | 4.1 | 0.5天 |
| 4.3 | PermissionManager实现 | 4.1, Phase 1.4 | 1.5天 |
| 4.4 | AppContext权限检查装饰器 | 4.3 | 1天 |
| 4.5 | 权限请求对话框UI | 4.3, Phase 1.2 | 1.5天 |
| 4.6 | 插件启用/禁用功能 | Phase 1.6 | 1天 |
| 4.7 | PluginPermissionRepository | Phase 1.4 | 1天 |
| 4.8 | 事件类型扩展 (更多EventType) | Phase 1.3 | 1天 |
| 4.9 | 插件面板UI（含权限显示） | Phase 1.2, 4.5 | 2天 |

**验证标准**:
- [ ] 插件必须声明权限才能使用对应功能
- [ ] 首次加载插件时弹出权限确认对话框
- [ ] 用户可查看和修改已授权权限
- [ ] 无权限操作抛出PermissionDeniedError
- [ ] 插件可启用/禁用
- [ ] 插件配置可保存

---

### Phase 5: 节点包管理 (2周)

**目标**: 从Git仓库管理自定义节点包

```
┌─────────────────────────────────────────────────────┐
│                 Phase 5 交付物                      │
├─────────────────────────────────────────────────────┤
│  ✓ Git节点包下载                                    │
│  ✓ 节点包更新                                       │
│  ✓ 节点包启用/禁用/删除                             │
│  ✓ 节点包管理UI                                     │
└─────────────────────────────────────────────────────┘
```

**任务清单**:

| # | 任务 | 依赖 | 预估 |
|---|------|------|------|
| 5.1 | NodePackage数据库模型 | Phase 1.4 | 0.5天 |
| 5.2 | GitUtils (clone/pull) | - | 1天 |
| 5.3 | PackageLoader (解析package.json) | 5.1 | 1天 |
| 5.4 | NodePackageManager核心 | 5.2, 5.3 | 3天 |
| 5.5 | 节点包启用/禁用逻辑 | 5.4, Phase 2.3 | 1天 |
| 5.6 | 节点包更新逻辑 | 5.4 | 1天 |
| 5.7 | 节点包删除逻辑 | 5.4 | 0.5天 |
| 5.8 | 节点包管理面板UI | 5.4, Phase 1.2 | 2天 |
| 5.9 | 安装进度显示 | 5.8 | 1天 |

**验证标准**:
- [ ] 可从Git URL安装节点包
- [ ] 可更新已安装的节点包
- [ ] 可启用/禁用节点包
- [ ] 可删除节点包
- [ ] 安装过程有进度反馈

---

### Phase 6: 高级功能 (2-3周)

**目标**: MCP集成、Skill管理、性能优化

```
┌─────────────────────────────────────────────────────┐
│                 Phase 6 交付物                      │
├─────────────────────────────────────────────────────┤
│  ✓ MCP服务器管理                                    │
│  ✓ Skill包支持                                      │
│  ✓ Widget双输入机制                                 │
│  ✓ 性能优化                                         │
│  ✓ 错误处理完善                                     │
└─────────────────────────────────────────────────────┘
```

**任务清单**:

| # | 任务 | 依赖 | 预估 |
|---|------|------|------|
| 6.1 | McpServer模型 + 管理 | Phase 3.2 | 2天 |
| 6.2 | MCP工具动态注册 | 6.1 | 2天 |
| 6.3 | Skill包结构支持 | Phase 5.4 | 2天 |
| 6.4 | Widget双输入机制 (LiteGraph模式) | Phase 2.7 | 3天 |
| 6.5 | 大型工作流性能优化 | Phase 2.3 | 2天 |
| 6.6 | 全局错误处理 | Phase 1 | 1天 |
| 6.7 | 日志系统 | Phase 1 | 1天 |

**验证标准**:
- [ ] 可配置和启用MCP服务器
- [ ] Skill包可正常加载
- [ ] Widget值与连接值正确切换
- [ ] 100+节点工作流流畅运行

---

### 里程碑总览

```
Phase 1 ──────────▶ Phase 2 ──────────▶ Phase 3
  基础框架            节点编辑器          Agent集成
  (2-3周)             (3-4周)             (2-3周)
     │                    │                   │
     └────────────────────┴───────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   MVP 可发布版本       │
              │   (约8-10周)          │
              └───────────────────────┘
                          │
                          ▼
Phase 4 ──────────▶ Phase 5 ──────────▶ Phase 6
  插件完善           节点包管理          高级功能
  (2周)              (2周)               (2-3周)
```

### 优先级矩阵

| 功能 | 用户价值 | 技术风险 | 优先级 |
|------|----------|----------|--------|
| 节点编辑器 | 高 | 中 | **P0** |
| 工作流执行 | 高 | 中 | **P0** |
| 插件系统 | 高 | 低 | **P0** |
| Agent辅助 | 中 | 中 | **P1** |
| 节点包管理 | 中 | 低 | **P1** |
| MCP集成 | 低 | 高 | **P2** |
| Widget双输入 | 低 | 低 | **P2** |

### 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| AgentScope API变化 | 中 | 高 | 封装Adapter层 |
| Git操作不稳定 | 中 | 中 | 超时+重试机制 |
| 大型工作流性能问题 | 高 | 中 | 增量渲染+虚拟化 |
| 节点包依赖冲突 | 中 | 中 | 隔离安装+版本检查 |

---

*文档版本: 2.1*  
*最后更新: 2026-03-26*
