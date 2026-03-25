# 办公小工具整合平台 - 架构文档

## 1. 项目概述

### 1.1 目标
构建一个统一的办公小工具整合平台，支持：
- **AI对话操作** - 自然语言调用工具
- **节点流编辑** - 可视化工作流编排
- **插件化扩展** - 灵活添加新工具

### 1.2 核心设计原则
- **声明式UI** - 使用Flet声明式编程（`@ft.observable` + `@ft.component` + `use_state`）
- **插件优先** - 所有工具以插件形式注册，便于扩展
- **自研引擎** - 节点流引擎自主研发，便于UI深度集成
- **统一Schema** - 工具定义同时服务AI对话和节点流

### 1.3 声明式编程模式

> 参考：https://docs.flet.dev/cookbook/declarative-vs-imperative-crud-app/

**核心理念**：`UI = f(state)` - UI是状态的函数

```python
# 声明式编程三大支柱

# 1. @ft.observable - 响应式数据模型
@ft.observable
@dataclass
class AppState:
    tools: list[Tool] = field(default_factory=list)
    selected_tool: Optional[Tool] = None

# 2. @ft.component - 组件函数（返回UI）
@ft.component
def ToolList(state: AppState) -> ft.Control:
    return ft.Column([
        ft.Text(f"工具数量: {len(state.tools)}"),
        *[ToolItem(tool) for tool in state.tools],
    ])

# 3. ft.use_state - 本地状态Hook
@ft.component
def SearchBox() -> ft.Control:
    query, set_query = ft.use_state("")
    return ft.TextField(
        value=query,
        on_change=lambda e: set_query(e.control.value),
    )
```

**声明式 vs 命令式对比**：

| 操作 | 命令式 | 声明式 |
|------|--------|--------|
| 更新UI | `control.value = x; page.update()` | `state.field = x` |
| 显示/隐藏 | `control.visible = True/False` | `if condition: return A else: return B` |
| 列表更新 | `list.controls.append(x)` | `return [Item(i) for i in state.items]` |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Flet 桌面应用                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │  插件面板   │  │  AI对话面板 │  │      节点流编辑器           │  │
│  │  (工具UI)   │  │  (Chat UI)  │  │      (Flet Canvas)          │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────────┘  │
│         │                │                     │                     │
│         └────────────────┼─────────────────────┘                     │
│                          ▼                                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    插件管理器 (PluginManager)                  │  │
│  │  • 插件发现与加载                                              │  │
│  │  • 工具注册到 AgentScope Toolkit                              │  │
│  │  • 节点类型注册到 NodeEngine                                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                          │                                           │
│         ┌────────────────┴────────────────┐                         │
│         ▼                                 ▼                          │
│  ┌─────────────────┐              ┌─────────────────┐               │
│  │ AgentScope      │              │  NodeEngine     │               │
│  │ Toolkit         │              │  (自研)         │               │
│  │ (AI工具调用)    │              │  (节点流执行)   │               │
│  └─────────────────┘              └─────────────────┘               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        插件目录 (plugins/)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │ excel_tools │  │ table_tools │  │ wechat_tools│  ...             │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块

### 3.1 插件系统设计

#### 3.1.1 插件接口定义

```python
# src/core/plugin_base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Optional
from enum import Enum
import flet as ft

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


@ft.observable
@dataclass
class PortDefinition:
    """端口定义 - 响应式"""
    name: str
    type: PortType = PortType.ANY
    description: str = ""
    required: bool = True
    default: Any = None


@ft.observable
@dataclass
class ToolDefinition:
    """工具定义 - 响应式数据模型，同时服务AI和节点流"""
    name: str                           # 工具唯一标识
    display_name: str                   # 显示名称
    description: str                    # 工具描述（AI用此理解功能）
    category: str = "general"           # 分类
    icon: str = "🔧"                    # 图标
    
    # 输入输出定义
    inputs: List[PortDefinition] = field(default_factory=list)
    outputs: List[PortDefinition] = field(default_factory=list)
    
    # 执行函数（非响应式）
    execute: Callable = field(default=None, repr=False)
    
    def get_json_schema(self) -> dict:
        """生成 OpenAI 兼容的 JSON Schema"""
        properties = {}
        required = []
        for inp in self.inputs:
            properties[inp.name] = {
                "type": self._port_type_to_json(inp.type),
                "description": inp.description,
            }
            if inp.default is not None:
                properties[inp.name]["default"] = inp.default
            if inp.required:
                required.append(inp.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }
    
    @staticmethod
    def _port_type_to_json(pt: PortType) -> str:
        mapping = {
            PortType.STRING: "string",
            PortType.INTEGER: "integer",
            PortType.FLOAT: "number",
            PortType.BOOLEAN: "boolean",
            PortType.LIST: "array",
            PortType.DICT: "object",
            PortType.ANY: "object",
            PortType.DATAFRAME: "object",
            PortType.FILE: "string",
        }
        return mapping.get(pt, "object")


class PluginBase(ABC):
    """插件基类"""
    
    # 插件元信息
    name: str = "unknown"
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    
    @abstractmethod
    def get_tools(self) -> List[ToolDefinition]:
        """返回插件提供的所有工具"""
        pass
    
    def on_load(self):
        """插件加载时调用"""
        pass
    
    def on_unload(self):
        """插件卸载时调用"""
        pass
```

#### 3.1.2 插件管理器（声明式）

```python
# src/core/plugin_manager.py
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional
import flet as ft


@ft.observable
class PluginInfo:
    """插件信息 - 响应式"""
    name: str
    version: str
    description: str
    path: Path
    loaded: bool = False
    error: Optional[str] = None


@ft.observable  
class PluginState:
    """插件管理器状态 - 响应式数据模型"""
    plugins: Dict[str, PluginInfo] = field(default_factory=dict)
    tools: Dict[str, ToolDefinition] = field(default_factory=dict)
    
    def register_tool(self, tool: ToolDefinition):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def unregister_tool(self, tool_name: str):
        """注销工具"""
        if tool_name in self.tools:
            del self.tools[tool_name]


class PluginManager:
    """插件管理器 - 操作响应式状态"""
    
    def __init__(self, plugins_dir: Path, state: PluginState):
        self.plugins_dir = plugins_dir
        self.state = state  # 响应式状态
        self._instances: Dict[str, PluginBase] = {}  # 非响应式实例缓存
    
    def discover_plugins(self) -> List[str]:
        """发现所有插件"""
        discovered = []
        if not self.plugins_dir.exists():
            return discovered
        
        for item in self.plugins_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                discovered.append(item.name)
            elif item.is_file() and item.suffix == ".py" and not item.stem.startswith("_"):
                discovered.append(item.stem)
        
        return discovered
    
    def load_plugin(self, plugin_name: str) -> bool:
        """加载单个插件"""
        if plugin_name in self.plugins and self.plugins[plugin_name].loaded:
            return True
        
        try:
            # 尝试作为包加载
            package_path = self.plugins_dir / plugin_name / "__init__.py"
            if package_path.exists():
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{plugin_name}", package_path
                )
            else:
                # 作为单文件加载
                file_path = self.plugins_dir / f"{plugin_name}.py"
                if not file_path.exists():
                    raise FileNotFoundError(f"Plugin not found: {plugin_name}")
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{plugin_name}", file_path
                )
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找 PluginBase 子类
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, PluginBase) and 
                    attr is not PluginBase):
                    plugin_class = attr
                    break
            
            if plugin_class is None:
                raise ValueError(f"No PluginBase subclass found in {plugin_name}")
            
            # 实例化并加载
            instance = plugin_class()
            instance.on_load()
            
            # 注册工具
            tools = instance.get_tools()
            for tool in tools:
                self._register_tool(tool)
            
            # 记录插件信息
            self.plugins[plugin_name] = PluginInfo(
                name=instance.name,
                version=instance.version,
                description=instance.description,
                path=self.plugins_dir / plugin_name,
                instance=instance,
                loaded=True,
            )
            
            return True
            
        except Exception as e:
            self.plugins[plugin_name] = PluginInfo(
                name=plugin_name,
                version="",
                description="",
                path=self.plugins_dir / plugin_name,
                error=str(e),
            )
            return False
    
    def _register_tool(self, tool: ToolDefinition):
        """注册工具到 Toolkit 和 NodeEngine"""
        self.tools[tool.name] = tool
        
        # 注册到 AgentScope Toolkit
        self.toolkit.register_tool_function(
            self._create_tool_function(tool)
        )
        
        # 注册到节点引擎
        self.node_engine.register_node_type(tool)
    
    def _create_tool_function(self, tool: ToolDefinition):
        """为 AgentScope 创建工具函数"""
        from agentscope.tool import ToolResponse
        from agentscope.message import TextBlock
        
        def tool_func(**kwargs) -> ToolResponse:
            result = tool.execute(**kwargs)
            return ToolResponse(
                content=[TextBlock(type="text", text=str(result))]
            )
        
        tool_func.__name__ = tool.name
        tool_func.__doc__ = f"{tool.description}\n\n" + "\n".join(
            f"    {inp.name} ({inp.type.value}): {inp.description}"
            for inp in tool.inputs
        )
        
        return tool_func
    
    def load_all(self) -> Dict[str, bool]:
        """加载所有插件"""
        results = {}
        for name in self.discover_plugins():
            results[name] = self.load_plugin(name)
        return results
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        if plugin_name not in self.plugins:
            return False
        
        info = self.plugins[plugin_name]
        if info.instance:
            # 移除工具
            for tool in info.instance.get_tools():
                if tool.name in self.tools:
                    del self.tools[tool.name]
            
            info.instance.on_unload()
        
        info.loaded = False
        return True
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[ToolDefinition]:
        """获取所有工具"""
        return list(self.tools.values())
```

#### 3.1.3 插件示例

```python
# plugins/excel_tools/__init__.py
from core.plugin_base import PluginBase, ToolDefinition, PortDefinition, PortType

class ExcelToolsPlugin(PluginBase):
    """Excel 工具插件"""
    
    name = "excel_tools"
    version = "1.0.0"
    description = "Excel 文件处理工具集"
    author = "Office Team"
    
    def get_tools(self) -> list:
        return [
            self._create_compare_tool(),
            self._create_merge_tool(),
        ]
    
    def _create_compare_tool(self) -> ToolDefinition:
        def compare_excel(file1: str, file2: str, col1: str, col2: str) -> dict:
            """执行Excel对比"""
            # 实际调用 excel_compare.py 的逻辑
            from excel_compare import ExcelComparator
            comparator = ExcelComparator(file1, file2)
            comparator.load_files()
            return comparator.compare_columns(col1, col2)
        
        return ToolDefinition(
            name="excel_compare",
            display_name="Excel对比",
            description="对比两个Excel文件中指定列的内容，找出差异",
            category="数据处理",
            icon="📊",
            inputs=[
                PortDefinition("file1", PortType.FILE, "基准Excel文件路径"),
                PortDefinition("file2", PortType.FILE, "对比Excel文件路径"),
                PortDefinition("col1", PortType.STRING, "文件1的对比列名"),
                PortDefinition("col2", PortType.STRING, "文件2的对比列名"),
            ],
            outputs=[
                PortDefinition("result", PortType.DICT, "对比结果"),
            ],
            execute=compare_excel,
        )
    
    def _create_merge_tool(self) -> ToolDefinition:
        # 类似实现...
        pass
```

---

### 3.2 自研节点流引擎

#### 3.2.1 核心数据结构

```python
# core/node_engine.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Callable
from uuid import uuid4
from enum import Enum
import asyncio
import json

class NodeState(Enum):
    """节点状态"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class Port:
    """端口"""
    id: str
    name: str
    type: PortType
    node_id: str
    is_input: bool
    value: Any = None


@dataclass
class Connection:
    """连接线"""
    id: str
    source_node: str
    source_port: str
    target_node: str
    target_port: str


@dataclass
class Node:
    """节点"""
    id: str
    type: str                    # 工具名称
    name: str                    # 显示名称
    position: tuple              # UI位置 (x, y)
    inputs: Dict[str, Port] = field(default_factory=dict)
    outputs: Dict[str, Port] = field(default_factory=dict)
    state: NodeState = NodeState.IDLE
    error: Optional[str] = None
    result: Any = None
    
    def set_input(self, port_name: str, value: Any):
        """设置输入值"""
        if port_name in self.inputs:
            self.inputs[port_name].value = value
    
    def get_output(self, port_name: str) -> Any:
        """获取输出值"""
        if port_name in self.outputs:
            return self.outputs[port_name].value
        return None


@dataclass
class NodeGraph:
    """节点图"""
    id: str
    name: str
    nodes: Dict[str, Node] = field(default_factory=dict)
    connections: Dict[str, Connection] = field(default_factory=dict)
    
    def add_node(self, node: Node):
        self.nodes[node.id] = node
    
    def remove_node(self, node_id: str):
        if node_id in self.nodes:
            del self.nodes[node_id]
            # 移除相关连接
            self.connections = {
                k: v for k, v in self.connections.items()
                if v.source_node != node_id and v.target_node != node_id
            }
    
    def add_connection(self, conn: Connection):
        self.connections[conn.id] = conn
    
    def remove_connection(self, conn_id: str):
        if conn_id in self.connections:
            del self.connections[conn_id]
    
    def get_predecessors(self, node_id: str) -> List[str]:
        """获取前驱节点"""
        predecessors = []
        for conn in self.connections.values():
            if conn.target_node == node_id:
                predecessors.append(conn.source_node)
        return predecessors
    
    def get_successors(self, node_id: str) -> List[str]:
        """获取后继节点"""
        successors = []
        for conn in self.connections.values():
            if conn.source_node == node_id:
                successors.append(conn.target_node)
        return successors
    
    def topological_sort(self) -> List[str]:
        """拓扑排序，返回执行顺序"""
        in_degree = {nid: 0 for nid in self.nodes}
        
        for conn in self.connections.values():
            if conn.target_node in in_degree:
                in_degree[conn.target_node] += 1
        
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []
        
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            
            for successor in self.get_successors(node_id):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)
        
        if len(result) != len(self.nodes):
            raise ValueError("Graph contains cycles")
        
        return result
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "name": n.name,
                    "position": n.position,
                    "inputs": {k: {"value": v.value} for k, v in n.inputs.items()},
                }
                for n in self.nodes.values()
            ],
            "connections": [
                {
                    "id": c.id,
                    "source_node": c.source_node,
                    "source_port": c.source_port,
                    "target_node": c.target_node,
                    "target_port": c.target_port,
                }
                for c in self.connections.values()
            ],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "NodeGraph":
        """从字典反序列化"""
        graph = cls(id=data["id"], name=data["name"])
        
        for node_data in data["nodes"]:
            node = Node(
                id=node_data["id"],
                type=node_data["type"],
                name=node_data["name"],
                position=tuple(node_data["position"]),
            )
            for port_name, port_data in node_data.get("inputs", {}).items():
                if port_name in node.inputs:
                    node.inputs[port_name].value = port_data.get("value")
            graph.add_node(node)
        
        for conn_data in data["connections"]:
            graph.add_connection(Connection(
                id=conn_data["id"],
                source_node=conn_data["source_node"],
                source_port=conn_data["source_port"],
                target_node=conn_data["target_node"],
                target_port=conn_data["target_port"],
            ))
        
        return graph
```

#### 3.2.2 节点引擎

```python
# core/node_engine.py (续)

class NodeEngine:
    """节点流执行引擎"""
    
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self.node_types: Dict[str, ToolDefinition] = {}
        self.graphs: Dict[str, NodeGraph] = {}
        self._execution_callbacks: List[Callable] = []
    
    def register_node_type(self, tool: ToolDefinition):
        """注册节点类型"""
        self.node_types[tool.name] = tool
    
    def create_node(self, node_type: str, position: tuple = (0, 0)) -> Optional[Node]:
        """创建节点实例"""
        if node_type not in self.node_types:
            return None
        
        tool = self.node_types[node_type]
        node_id = str(uuid4())
        
        # 创建端口
        inputs = {}
        for inp in tool.inputs:
            inputs[inp.name] = Port(
                id=f"{node_id}_in_{inp.name}",
                name=inp.name,
                type=inp.type,
                node_id=node_id,
                is_input=True,
                value=inp.default,
            )
        
        outputs = {}
        for out in tool.outputs:
            outputs[out.name] = Port(
                id=f"{node_id}_out_{out.name}",
                name=out.name,
                type=out.type,
                node_id=node_id,
                is_input=False,
            )
        
        return Node(
            id=node_id,
            type=node_type,
            name=tool.display_name,
            position=position,
            inputs=inputs,
            outputs=outputs,
        )
    
    def create_graph(self, name: str = "Untitled") -> NodeGraph:
        """创建新图"""
        graph = NodeGraph(id=str(uuid4()), name=name)
        self.graphs[graph.id] = graph
        return graph
    
    def on_node_state_change(self, callback: Callable):
        """注册状态变化回调"""
        self._execution_callbacks.append(callback)
    
    async def _notify_state_change(self, node: Node):
        """通知状态变化"""
        for callback in self._execution_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(node)
            else:
                callback(node)
    
    async def execute_node(self, node: Node, graph: NodeGraph) -> bool:
        """执行单个节点"""
        if node.type not in self.node_types:
            node.state = NodeState.ERROR
            node.error = f"Unknown node type: {node.type}"
            await self._notify_state_change(node)
            return False
        
        tool = self.node_types[node.type]
        
        try:
            node.state = NodeState.RUNNING
            await self._notify_state_change(node)
            
            # 收集输入参数
            kwargs = {}
            for port_name, port in node.inputs.items():
                kwargs[port_name] = port.value
            
            # 执行工具
            result = tool.execute(**kwargs)
            
            # 设置输出
            if isinstance(result, dict):
                for key, value in result.items():
                    if key in node.outputs:
                        node.outputs[key].value = value
            else:
                # 单输出情况
                if "result" in node.outputs:
                    node.outputs["result"].value = result
            
            node.result = result
            node.state = NodeState.SUCCESS
            await self._notify_state_change(node)
            return True
            
        except Exception as e:
            node.state = NodeState.ERROR
            node.error = str(e)
            await self._notify_state_change(node)
            return False
    
    async def execute_graph(self, graph: NodeGraph) -> bool:
        """执行整个图"""
        try:
            order = graph.topological_sort()
        except ValueError as e:
            return False
        
        for node_id in order:
            node = graph.nodes[node_id]
            
            # 传递数据：从前驱节点的输出到当前节点的输入
            for conn in graph.connections.values():
                if conn.target_node == node_id:
                    source_node = graph.nodes[conn.source_node]
                    if conn.source_port in source_node.outputs:
                        value = source_node.outputs[conn.source_port].value
                        if conn.target_port in node.inputs:
                            node.inputs[conn.target_port].value = value
            
            # 执行节点
            success = await self.execute_node(node, graph)
            if not success:
                return False
        
        return True
    
    def save_graph(self, graph: NodeGraph, filepath: str):
        """保存图到文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(graph.to_dict(), f, ensure_ascii=False, indent=2)
    
    def load_graph(self, filepath: str) -> NodeGraph:
        """从文件加载图"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        graph = NodeGraph.from_dict(data)
        self.graphs[graph.id] = graph
        return graph
    
    def get_available_nodes(self) -> List[dict]:
        """获取可用节点类型列表（用于UI）"""
        return [
            {
                "type": tool.name,
                "name": tool.display_name,
                "category": tool.category,
                "icon": tool.icon,
                "inputs": [
                    {"name": i.name, "type": i.type.value, "required": i.required}
                    for i in tool.inputs
                ],
                "outputs": [
                    {"name": o.name, "type": o.type.value}
                    for o in tool.outputs
                ],
            }
            for tool in self.node_types.values()
        ]
```

#### 3.2.3 自定义节点基类

用户可以通过继承 `NodeBase` 创建自定义节点，实现更复杂的逻辑。

```python
# src/core/node_base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import flet as ft


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
class NodePort:
    """节点端口定义"""
    name: str
    type: PortType = PortType.ANY
    description: str = ""
    default: Any = None
    required: bool = True


class NodeBase(ABC):
    """
    自定义节点基类
    
    用户继承此类创建自定义节点，实现复杂的业务逻辑。
    节点会自动注册到节点引擎，可在节点编辑器中使用。
    """
    
    # ===== 节点元信息（子类必须定义）=====
    node_type: str = ""          # 节点类型标识（唯一）
    display_name: str = ""       # 显示名称
    category: str = "custom"     # 分类
    icon: str = "🔧"             # 图标
    description: str = ""        # 节点描述
    
    # ===== 端口定义（子类可覆盖）=====
    inputs: List[NodePort] = field(default_factory=list)
    outputs: List[NodePort] = field(default_factory=list)
    
    def __init__(self):
        # 运行时状态
        self._input_values: Dict[str, Any] = {}
        self._output_values: Dict[str, Any] = {}
        self._state: str = "idle"  # idle | running | success | error
        self._error: Optional[str] = None
    
    # ===== 生命周期方法 =====
    
    def setup(self):
        """节点初始化时调用（可选覆盖）"""
        pass
    
    def cleanup(self):
        """节点销毁时调用（可选覆盖）"""
        pass
    
    # ===== 核心方法（子类必须实现）=====
    
    @abstractmethod
    def execute(self, **inputs) -> Dict[str, Any]:
        """
        执行节点逻辑（子类必须实现）
        
        Args:
            **inputs: 输入端口的值
            
        Returns:
            Dict[str, Any]: 输出端口的值，key为输出端口名称
        """
        pass
    
    # ===== 辅助方法 =====
    
    def get_input(self, name: str, default: Any = None) -> Any:
        """获取输入值"""
        return self._input_values.get(name, default)
    
    def set_output(self, name: str, value: Any):
        """设置输出值"""
        self._output_values[name] = value
    
    def set_error(self, message: str):
        """设置错误信息"""
        self._error = message
        self._state = "error"
    
    # ===== 内部方法（由引擎调用）=====
    
    def _set_inputs(self, values: Dict[str, Any]):
        """设置输入值（引擎调用）"""
        self._input_values = values
    
    def _get_outputs(self) -> Dict[str, Any]:
        """获取输出值（引擎调用）"""
        return self._output_values
    
    def _run(self) -> bool:
        """运行节点（引擎调用）"""
        try:
            self._state = "running"
            self._error = None
            
            # 执行节点逻辑
            result = self.execute(**self._input_values)
            
            # 设置输出
            if result:
                for key, value in result.items():
                    self._output_values[key] = value
            
            self._state = "success"
            return True
            
        except Exception as e:
            self._error = str(e)
            self._state = "error"
            return False
    
    # ===== 节点信息 =====
    
    def get_info(self) -> dict:
        """获取节点信息（用于UI显示）"""
        return {
            "type": self.node_type,
            "name": self.display_name,
            "category": self.category,
            "icon": self.icon,
            "description": self.description,
            "inputs": [
                {"name": p.name, "type": p.type.value, "description": p.description, "required": p.required}
                for p in self.inputs
            ],
            "outputs": [
                {"name": p.name, "type": p.type.value, "description": p.description}
                for p in self.outputs
            ],
        }
```

#### 3.2.4 自定义节点示例

```python
# src/plugins/custom_nodes/text_process.py
from src.core.node_base import NodeBase, NodePort, PortType
from typing import Dict, Any


class TextInputNode(NodeBase):
    """文本输入节点"""
    
    node_type = "text_input"
    display_name = "文本输入"
    category = "基础"
    icon = "📝"
    description = "输入文本内容"
    
    # 无输入端口
    inputs = []
    
    # 一个输出端口
    outputs = [
        NodePort("text", PortType.STRING, "输入的文本"),
    ]
    
    def __init__(self, default_text: str = ""):
        super().__init__()
        self._default_text = default_text
    
    def execute(self, **inputs) -> Dict[str, Any]:
        return {"text": self._default_text}


class TextTransformNode(NodeBase):
    """文本转换节点"""
    
    node_type = "text_transform"
    display_name = "文本转换"
    category = "文本处理"
    icon = "🔄"
    description = "转换文本格式（大写/小写/首字母大写）"
    
    inputs = [
        NodePort("text", PortType.STRING, "输入文本", required=True),
        NodePort("mode", PortType.STRING, "转换模式: upper/lower/capitalize", default="upper"),
    ]
    
    outputs = [
        NodePort("result", PortType.STRING, "转换后的文本"),
    ]
    
    def execute(self, **inputs) -> Dict[str, Any]:
        text = inputs.get("text", "")
        mode = inputs.get("mode", "upper")
        
        if mode == "upper":
            result = text.upper()
        elif mode == "lower":
            result = text.lower()
        elif mode == "capitalize":
            result = text.capitalize()
        else:
            result = text
        
        return {"result": result}


class TextConcatNode(NodeBase):
    """文本拼接节点"""
    
    node_type = "text_concat"
    display_name = "文本拼接"
    category = "文本处理"
    icon = "🔗"
    description = "拼接多个文本"
    
    inputs = [
        NodePort("text1", PortType.STRING, "第一个文本"),
        NodePort("text2", PortType.STRING, "第二个文本"),
        NodePort("separator", PortType.STRING, "分隔符", default=" "),
    ]
    
    outputs = [
        NodePort("result", PortType.STRING, "拼接结果"),
    ]
    
    def execute(self, **inputs) -> Dict[str, Any]:
        text1 = inputs.get("text1", "")
        text2 = inputs.get("text2", "")
        sep = inputs.get("separator", " ")
        
        return {"result": f"{text1}{sep}{text2}"}


class ExcelReadNode(NodeBase):
    """Excel读取节点"""
    
    node_type = "excel_read"
    display_name = "Excel读取"
    category = "数据处理"
    icon = "📊"
    description = "读取Excel文件"
    
    inputs = [
        NodePort("file_path", PortType.FILE, "Excel文件路径"),
        NodePort("sheet_name", PortType.STRING, "工作表名称", default="Sheet1"),
    ]
    
    outputs = [
        NodePort("data", PortType.DATAFRAME, "数据表格"),
        NodePort("row_count", PortType.INTEGER, "行数"),
    ]
    
    def execute(self, **inputs) -> Dict[str, Any]:
        import pandas as pd
        
        file_path = inputs.get("file_path")
        sheet_name = inputs.get("sheet_name", "Sheet1")
        
        if not file_path:
            self.set_error("文件路径不能为空")
            return {}
        
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            return {
                "data": df,
                "row_count": len(df),
            }
        except Exception as e:
            self.set_error(f"读取Excel失败: {str(e)}")
            return {}
```

#### 3.2.5 节点注册与发现

```python
# src/core/node_registry.py
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Type
from src.core.node_base import NodeBase


class NodeRegistry:
    """节点注册中心"""
    
    def __init__(self):
        self._node_types: Dict[str, Type[NodeBase]] = {}
    
    def register(self, node_class: Type[NodeBase]):
        """注册节点类型"""
        if not issubclass(node_class, NodeBase):
            raise ValueError(f"{node_class} 必须继承自 NodeBase")
        
        if not node_class.node_type:
            raise ValueError(f"{node_class} 必须定义 node_type")
        
        self._node_types[node_class.node_type] = node_class
    
    def unregister(self, node_type: str):
        """注销节点类型"""
        if node_type in self._node_types:
            del self._node_types[node_type]
    
    def get(self, node_type: str) -> Type[NodeBase]:
        """获取节点类型"""
        return self._node_types.get(node_type)
    
    def create_instance(self, node_type: str, **kwargs) -> NodeBase:
        """创建节点实例"""
        node_class = self.get(node_type)
        if node_class is None:
            raise ValueError(f"未知的节点类型: {node_type}")
        return node_class(**kwargs)
    
    def get_all(self) -> List[Type[NodeBase]]:
        """获取所有节点类型"""
        return list(self._node_types.values())
    
    def get_by_category(self, category: str) -> List[Type[NodeBase]]:
        """按分类获取节点"""
        return [
            node_class for node_class in self._node_types.values()
            if node_class.category == category
        ]
    
    def discover_from_module(self, module_path: str):
        """从模块发现并注册节点"""
        module = importlib.import_module(module_path)
        
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, NodeBase) and 
                obj is not NodeBase and
                obj.node_type):  # 确保有node_type
                self.register(obj)
    
    def discover_from_directory(self, directory: Path):
        """从目录发现并注册节点"""
        for py_file in directory.glob("**/*.py"):
            if py_file.name.startswith("_"):
                continue
            
            # 转换为模块路径
            module_path = str(py_file.with_suffix("")).replace("/", ".")
            try:
                self.discover_from_module(module_path)
            except Exception as e:
                print(f"发现节点失败 {module_path}: {e}")


# 全局节点注册中心
node_registry = NodeRegistry()
```

#### 3.2.6 使用自定义节点

```python
# src/main.py 或 src/ui/node_editor.py
from src.core.node_registry import node_registry
from src.core.node_engine import NodeEngine

# 方式1: 手动注册
from src.plugins.custom_nodes.text_process import (
    TextInputNode, TextTransformNode, TextConcatNode
)

node_registry.register(TextInputNode)
node_registry.register(TextTransformNode)
node_registry.register(TextConcatNode)

# 方式2: 自动发现
from pathlib import Path
node_registry.discover_from_directory(Path("src/plugins/custom_nodes"))

# 创建节点引擎并导入注册的节点
engine = NodeEngine()

for node_class in node_registry.get_all():
    # 创建临时实例获取信息
    temp_instance = node_class()
    engine.register_custom_node_type(temp_instance)


# 在NodeEngine中添加支持自定义节点的方法
class NodeEngine:
    # ... 原有代码 ...
    
    def register_custom_node_type(self, node_instance: NodeBase):
        """注册自定义节点类型"""
        info = node_instance.get_info()
        
        # 转换为ToolDefinition兼容的格式
        from src.core.plugin_base import ToolDefinition, PortDefinition, PortType
        
        tool = ToolDefinition(
            name=info["type"],
            display_name=info["name"],
            description=info["description"],
            category=info["category"],
            icon=info["icon"],
            inputs=[
                PortDefinition(
                    name=i["name"],
                    type=PortType(i["type"]),
                    description=i.get("description", ""),
                    required=i.get("required", True),
                )
                for i in info["inputs"]
            ],
            outputs=[
                PortDefinition(
                    name=o["name"],
                    type=PortType(o["type"]),
                    description=o.get("description", ""),
                )
                for o in info["outputs"]
            ],
            execute=lambda **kw, ni=node_instance: self._execute_custom_node(ni, **kw),
        )
        
        self.node_types[tool.name] = tool
    
    def _execute_custom_node(self, node_instance: NodeBase, **kwargs):
        """执行自定义节点"""
        node_instance._set_inputs(kwargs)
        success = node_instance._run()
        if success:
            return node_instance._get_outputs()
        else:
            raise Exception(node_instance._error or "节点执行失败")
```

#### 3.2.7 与UI集成

```python
# ui/node_editor.py
import flet as ft
from core.node_engine import NodeEngine, Node, NodeState, NodeGraph

class NodeEditor(ft.Container):
    """节点编辑器UI组件"""
    
    def __init__(self, engine: NodeEngine):
        super().__init__()
        self.engine = engine
        self.graph: NodeGraph = None
        self.selected_node: Node = None
        
        # UI组件
        self.canvas = ft.Stack()
        self.node_palette = ft.Column()
        self.properties_panel = ft.Column()
        
        self._setup_ui()
        self._bind_events()
    
    def _setup_ui(self):
        """设置UI布局"""
        self.content = ft.Row([
            # 左侧：节点面板
            ft.Container(
                width=200,
                content=ft.Column([
                    ft.Text("节点", size=16, weight="bold"),
                    self.node_palette,
                ]),
            ),
            # 中间：画布
            ft.Container(
                expand=True,
                content=self.canvas,
                bgcolor=ft.colors.GREY_100,
            ),
            # 右侧：属性面板
            ft.Container(
                width=250,
                content=ft.Column([
                    ft.Text("属性", size=16, weight="bold"),
                    self.properties_panel,
                ]),
            ),
        ])
    
    def _bind_events(self):
        """绑定事件"""
        # 节点状态变化时更新UI
        self.engine.on_node_state_change(self._on_node_state_change)
    
    async def _on_node_state_change(self, node: Node):
        """节点状态变化回调"""
        # 更新节点UI
        self.update()
    
    def load_graph(self, graph: NodeGraph):
        """加载图到编辑器"""
        self.graph = graph
        self._render_nodes()
        self._render_connections()
    
    def _render_nodes(self):
        """渲染所有节点"""
        self.canvas.controls.clear()
        for node in self.graph.nodes.values():
            self.canvas.controls.append(self._create_node_widget(node))
        self.update()
    
    def _create_node_widget(self, node: Node) -> ft.Container:
        """创建节点UI组件"""
        # 根据状态设置颜色
        colors = {
            NodeState.IDLE: ft.colors.BLUE_GREY,
            NodeState.RUNNING: ft.colors.ORANGE,
            NodeState.SUCCESS: ft.colors.GREEN,
            NodeState.ERROR: ft.colors.RED,
        }
        
        return ft.Container(
            left=node.position[0],
            top=node.position[1],
            width=150,
            content=ft.Column([
                ft.Container(
                    content=ft.Text(node.name, size=12),
                    bgcolor=colors.get(node.state, ft.colors.GREY),
                    padding=5,
                ),
                ft.Column([
                    *[ft.Text(f"→ {p}", size=10) for p in node.inputs],
                    *[ft.Text(f"← {p}", size=10) for p in node.outputs],
                ]),
            ]),
            border=ft.border.all(1, ft.colors.GREY),
            on_click=lambda e, n=node: self._select_node(n),
            draggable=True,
        )
    
    def _select_node(self, node: Node):
        """选中节点"""
        self.selected_node = node
        self._update_properties_panel()
    
    def _update_properties_panel(self):
        """更新属性面板"""
        self.properties_panel.controls.clear()
        
        if self.selected_node:
            for port_name, port in self.selected_node.inputs.items():
                self.properties_panel.controls.append(
                    ft.TextField(
                        label=port_name,
                        value=str(port.value) if port.value else "",
                        on_change=lambda e, p=port: setattr(p, "value", e.control.value),
                    )
                )
        
        self.update()
    
    def add_node(self, node_type: str, x: int, y: int):
        """添加节点"""
        node = self.engine.create_node(node_type, (x, y))
        if node:
            self.graph.add_node(node)
            self._render_nodes()
    
    async def execute(self):
        """执行图"""
        if self.graph:
            await self.engine.execute_graph(self.graph)
```

---

### 3.3 AI对话模块 (AgentScope)

```python
# src/agents/office_agent.py
import os
from agentscope.agent import ReActAgent
from agentscope.model import OpenAIChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit

def create_office_agent(toolkit: Toolkit) -> ReActAgent:
    """创建办公助手Agent"""
    return ReActAgent(
        name="OfficeAssistant",
        sys_prompt="""你是办公小助手，帮助用户处理各种办公任务。

你可以使用的工具包括：
- Excel对比：对比两个Excel文件的差异
- 表格合并：合并多个Excel表格
- 消息发送：通过微信发送消息

请根据用户的需求选择合适的工具来完成任务。""",
        model=OpenAIChatModel(
            model_name="gpt-4o",
            api_key=os.environ.get("OPENAI_API_KEY"),
            stream=True,
        ),
        formatter=OpenAIChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
        max_iters=10,
        parallel_tool_calls=True,
    )
```

---

### 3.4 UI组件（声明式）

#### 3.4.1 应用状态模型

```python
# src/ui/state.py
import flet as ft
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@ft.observable
@dataclass
class AppState:
    """应用全局状态 - 响应式"""
    # 当前视图
    current_view: str = "chat"  # "chat" | "node_editor" | "plugins"
    
    # 对话状态
    messages: List[dict] = field(default_factory=list)
    is_loading: bool = False
    
    # 节点编辑器状态
    current_graph_id: Optional[str] = None
    selected_node_id: Optional[str] = None
    
    # 插件状态
    loaded_plugins: List[str] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    
    def switch_view(self, view_name: str):
        """切换视图"""
        self.current_view = view_name
    
    def add_message(self, role: str, content: str):
        """添加消息"""
        self.messages.append({"role": role, "content": content})
    
    def clear_messages(self):
        """清空消息"""
        self.messages.clear()
```

#### 3.4.2 声明式组件示例

```python
# src/ui/components/chat_panel.py
import flet as ft
from src.ui.state import AppState


@ft.component
def MessageItem(message: dict) -> ft.Control:
    """单条消息组件"""
    is_user = message["role"] == "user"
    
    return ft.Container(
        content=ft.Column([
            ft.Text(
                "你" if is_user else "助手",
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.BLUE if is_user else ft.Colors.GREEN,
            ),
            ft.Text(message["content"], selectable=True),
        ]),
        bgcolor=ft.Colors.BLUE_50 if is_user else ft.Colors.GREEN_50,
        border_radius=10,
        padding=10,
        margin=ft.margin.only(left=50 if is_user else 0, right=0 if is_user else 50),
    )


@ft.component
def ChatPanel(state: AppState, send_message: callable) -> ft.Control:
    """AI对话面板 - 声明式组件"""
    # 本地状态：输入框内容
    input_text, set_input_text = ft.use_state("")
    
    def on_submit(e):
        if input_text.strip():
            send_message(input_text)
            set_input_text("")  # 清空输入框
    
    return ft.Column([
        # 消息列表
        ft.ListView(
            controls=[MessageItem(msg) for msg in state.messages],
            expand=True,
            auto_scroll=True,
            spacing=10,
            padding=10,
        ),
        
        # 加载指示器（条件渲染）
        ft.ProgressIndicator() if state.is_loading else ft.Container(),
        
        # 输入区域
        ft.Row([
            ft.TextField(
                value=input_text,
                on_change=lambda e: set_input_text(e.control.value),
                on_submit=on_submit,
                hint_text="输入消息...",
                expand=True,
            ),
            ft.IconButton(
                icon=ft.Icons.SEND,
                on_click=on_submit,
                disabled=state.is_loading or not input_text.strip(),
            ),
        ], spacing=10),
    ], expand=True)


@ft.component
def NavigationRail(state: AppState) -> ft.Control:
    """导航栏 - 声明式"""
    return ft.NavigationRail(
        selected_index=["chat", "node_editor", "plugins"].index(state.current_view),
        on_change=lambda e: state.switch_view(
            ["chat", "node_editor", "plugins"][e.control.selected_index]
        ),
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.CHAT, label="对话"),
            ft.NavigationRailDestination(icon=ft.Icons.ACCOUNT_TREE, label="节点流"),
            ft.NavigationRailDestination(icon=ft.Icons.EXTENSION, label="插件"),
        ],
    )


@ft.component
def MainView() -> ft.Control:
    """主视图 - 根组件"""
    # 全局状态
    state, _ = ft.use_state(lambda: AppState())
    
    # 根据当前视图返回不同内容（条件渲染）
    if state.current_view == "chat":
        content = ChatPanel(state, lambda msg: state.add_message("user", msg))
    elif state.current_view == "node_editor":
        content = ft.Text("节点编辑器（待实现）")
    else:
        content = ft.Text("插件管理（待实现）")
    
    return ft.Row([
        NavigationRail(state),
        ft.VerticalDivider(width=1),
        ft.Container(content=content, expand=True),
    ], expand=True)
```

#### 3.4.3 入口文件

```python
# src/main.py
import flet as ft
from src.ui.components.main_view import MainView


def main(page: ft.Page):
    """应用入口"""
    page.title = "办公小工具整合平台"
    page.theme_mode = ft.ThemeMode.LIGHT
    
    # 声明式渲染
    page.render(MainView)


if __name__ == "__main__":
    ft.run(main)
```

---

## 4. 目录结构

> 遵循 `uv run flet create` 标准项目结构

```
office/                         # 项目根目录
├── README.md                   # 项目说明
├── pyproject.toml              # 项目配置（依赖、元信息）
│
├── src/                        # 源代码目录
│   ├── assets/                 # 静态资源（图片、图标等）
│   │   └── icon.png
│   │
│   ├── main.py                 # 应用入口
│   │
│   ├── core/                   # 核心模块
│   │   ├── __init__.py
│   │   ├── plugin_base.py      # 插件基类和工具定义
│   │   ├── plugin_manager.py   # 插件管理器
│   │   └── node_engine.py      # 自研节点流引擎
│   │
│   ├── agents/                 # AI Agent模块
│   │   ├── __init__.py
│   │   └── office_agent.py     # AgentScope Agent配置
│   │
│   ├── ui/                     # UI组件
│   │   ├── __init__.py
│   │   ├── main_app.py         # Flet主应用
│   │   ├── chat_panel.py       # AI对话面板
│   │   └── node_editor.py      # 节点编辑器UI
│   │
│   ├── plugins/                # 插件目录
│   │   ├── __init__.py
│   │   ├── excel_tools/        # Excel工具插件
│   │   │   └── __init__.py
│   │   ├── table_tools/        # 表格处理插件
│   │   │   └── __init__.py
│   │   └── wechat_tools/       # 微信工具插件
│   │       └── __init__.py
│   │
│   └── config/                 # 配置文件
│       └── settings.yaml
│
├── storage/                    # 存储目录
│   ├── data/                   # 持久化数据
│   └── temp/                   # 临时文件
│
├── docs/                       # 文档目录
│   ├── ARCHITECTURE.md         # 架构文档
│   └── FLET_GUIDE.md           # Flet使用指南
│
├── excel_compare.py            # 现有: Excel对比工具 (待迁移为插件)
├── table.py                    # 现有: 表格处理 (待迁移为插件)
└── chat.py                     # 现有: 微信助手 (待迁移为插件)
```

### 运行命令

```bash
# 开发运行
uv run flet run src/main.py

# Web模式运行
uv run flet run --web src/main.py

# 打包发布
uv run flet build windows src/main.py
```

---

## 5. 数据流

### 5.1 声明式数据流

```
用户操作 (Event)
    │
    ▼
更新 @ft.observable 状态
    │
    ▼
Flet 自动检测变化
    │
    ▼
重新渲染 @ft.component
    │
    ▼
UI 更新（无需 page.update()）
```

### 5.2 插件注册流程

```
插件目录扫描
    │
    ▼
PluginManager.discover_plugins()
    │
    ▼
PluginManager.load_plugin()
    │
    ├─► 加载Python模块
    │
    ├─► 实例化 PluginBase 子类
    │
    ├─► 调用 plugin.get_tools()
    │
    └─► 注册到：
        ├─► AgentScope Toolkit (AI调用)
        └─► NodeEngine (节点流)
```

### 5.3 节点执行流程

```
用户点击"执行"
    │
    ▼
NodeEngine.execute_graph()
    │
    ├─► topological_sort() → 执行顺序
    │
    └─► 依次执行每个节点：
        │
        ├─► 传递数据（从前驱到当前）
        │
        ├─► tool.execute(**kwargs)
        │
        ├─► 设置输出端口值
        │
        └─► 更新 observable 状态 → UI 自动刷新
```

---

## 6. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| **UI范式** | 声明式 | `@ft.observable` + `@ft.component` + `use_state`，UI自动响应状态变化 |
| **AI框架** | AgentScope | ReAct范式，Toolkit管理，支持MCP |
| **插件系统** | 自研 | 轻量、灵活、与AgentScope/NodeEngine深度集成 |
| **节点引擎** | 自研 | 无第三方依赖，与Flet声明式UI深度集成 |
| **工具Schema** | ToolDefinition | 统一格式，同时生成OpenAI Schema和节点端口 |

---

## 7. 依赖清单

```toml
[project]
dependencies = [
    "flet>=0.21.0",           # UI框架 (声明式支持)
    "agentscope>=1.0.0",      # AI多Agent框架
    # 以下为插件可能需要的依赖
    "pandas>=2.3.0",          # 数据处理
    "openpyxl>=3.1.0",        # Excel读写
    "wxauto>=39.0.0",         # 微信自动化 (可选)
]
```

---

## 8. 实施路线

| 阶段 | 内容 | 周期 |
|------|------|------|
| **Phase 1** | 插件系统 + 节点引擎核心 | 1-2周 |
| **Phase 2** | 声明式UI组件 + AI对话 | 2周 |
| **Phase 3** | 节点编辑器UI + 连线功能 | 2周 |
| **Phase 4** | 迁移现有工具为插件 | 1周 |
| **Phase 5** | 打磨优化 + 文档 | 1周 |

---

*文档版本: 4.0 | 最后更新: 2026-03-25 | Flet声明式编程 + AgentScope + 自研节点引擎*
