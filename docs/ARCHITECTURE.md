# 办公小工具整合平台 - 架构文档

## 1. 项目概述

### 1.1 目标
构建一个统一的办公小工具整合平台，支持：
- **AI对话操作** - 自然语言调用工具
- **节点流编辑** - 可视化工作流编排
- **插件化扩展** - 灵活添加新工具

### 1.2 核心设计原则
- **PySide6原生UI** - 使用PySide6 + QSS样式表，自行设计现代化外观
- **信号槽机制** - Qt的信号槽系统实现组件通信
- **插件优先** - 所有工具以插件形式注册，便于扩展
- **自研引擎** - 节点流引擎自主研发，便于UI深度集成
- **统一Schema** - 工具定义同时服务AI对话和节点流

### 1.3 PySide6 UI设计模式

**核心理念**：使用Qt的信号槽机制 + QSS样式表

```python
# PySide6 三大核心概念

# 1. 信号与槽 (Signals & Slots)
button = QPushButton("点击")
button.clicked.connect(self.on_click)  # 连接信号到槽

# 2. 布局管理 (Layout Management)
layout = QVBoxLayout()
layout.addWidget(QLabel("标题"))
layout.addWidget(QLineEdit())

# 3. QSS样式表 (Qt Style Sheets)
widget.setStyleSheet("""
    QPushButton {
        background-color: #2196F3;
        color: white;
        border-radius: 4px;
        padding: 8px 16px;
    }
""")
```

**自定义主题设计**：
- 现代化扁平风格
- 统一色彩体系（主色、辅助色、背景色）
- 响应式布局适配不同窗口大小

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PySide6 桌面应用                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │  插件面板   │  │  AI对话面板 │  │      节点流编辑器           │  │
│  │  (QWidget)  │  │  (QWidget)  │  │      (QGraphicsView)        │  │
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


@dataclass
class ToolDefinition:
    """工具定义 - 同时服务AI和节点流"""
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

#### 3.1.2 插件管理器

```python
# src/core/plugin_manager.py
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    description: str
    path: Path
    instance: Any = None
    loaded: bool = False
    error: Optional[str] = None


class PluginState:
    """插件管理器状态"""
    def __init__(self):
        self.plugins: Dict[str, PluginInfo] = {}
        self.tools: Dict[str, ToolDefinition] = {}
    
    def register_tool(self, tool: ToolDefinition):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def unregister_tool(self, tool_name: str):
        """注销工具"""
        if tool_name in self.tools:
            del self.tools[tool_name]


class PluginManager:
    """插件管理器"""
    
    def __init__(self, plugins_dir: Path, state: PluginState):
        self.plugins_dir = plugins_dir
        self.state = state
        self._instances: Dict[str, PluginBase] = {}
    
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
from typing import Dict, List, Any, Optional
from enum import Enum


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

---

### 3.2.8 PySide6节点编辑器UI架构

基于Qt Graphics View Framework实现高性能的节点图编辑器。

#### 核心架构：Model-View分离

```
┌─────────────────────────────────────────────────────────────────┐
│                      NodeEditorView (QGraphicsView)              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │               NodeEditorScene (QGraphicsScene)              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │  │
│  │  │ NodeGraphics │  │ Connection   │  │ PortGraphics    │    │  │
│  │  │ Item         │  │ GraphicsItem │  │ Item             │    │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

#### 关键类设计

```python
# src/ui/components/node_editor/__init__.py
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath

class NodeEditorScene(QGraphicsScene):
    """节点编辑器场景 - 管理所有图元"""
    
    connection_created = Signal(object)  # 连接创建信号
    connection_deleted = Signal(str)   # 连接删除信号
    node_selected = Signal(object)     # 节点选中信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid_size = 20  # 网格大小
        self._show_grid = True
        
    def drawBackground(self, painter, rect):
        """绘制网格背景"""
        super().drawBackground(painter, rect)
        if self._show_grid:
            self._draw_grid(painter, rect)
    
    def _draw_grid(self, painter, rect):
        """绘制点状网格"""
        pen = QPen(QColor(200, 200, 200, 100))
        pen.setWidth(1)
        painter.setPen(pen)
        
        left = int(rect.left()) - (int(rect.left()) % self._grid_size)
        top = int(rect.top()) - (int(rect.top()) % self._grid_size)
        
        for x in range(left, int(rect.right()), self._grid_size):
            for y in range(top, int(rect.bottom()), self._grid_size):
                painter.drawPoint(x, y)


class NodeEditorView(QGraphicsView):
    """节点编辑器视图 - 处理视口变换和用户交互"""
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._zoom_factor = 1.0
        self._pan_mode = False
        self._last_mouse_pos = None
        
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        delta = event.angleDelta().y()
        factor = 1.1 if delta < 0 else 0.9
        self._zoom_factor *= factor
        self._zoom_factor = max(0.1, min(self._zoom_factor, 5.0))
        self.scale(self._zoom_factor, self._zoom_factor, self.mapToScene(event.pos()))
    
    def mousePressEvent(self, event):
        """鼠标按下 - 中键平移"""
        if event.button() == Qt.MiddleButton:
            self._pan_mode = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        if self._pan_mode and self._last_mouse_pos:
            delta = event.pos() - self._last_mouse_pos
            self.translate(delta.x(), delta.y())
            self._last_mouse_pos = event.pos()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if event.button() == Qt.MiddleButton:
            self._pan_mode = False
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)


class NodeGraphicsItem(QGraphicsItem):
    """节点图元 - 可拖拽、可选中"""
    
    def __init__(self, node_data, parent=None):
        super().__init__(parent)
        self._node_data = node_data
        self._width = 180
        self._height = 100
        
        # 启用拖拽和选中
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(1)
        
        # 输入输出端口
        self._input_ports = {}  # name -> PortGraphicsItem
        self._output_ports = {}
    
    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)
    
    def paint(self, painter, option, widget):
        """绘制节点"""
        # 绘制节点背景
        self._draw_background(painter)
        # 绘制节点标题
        self._draw_title(painter)
        # 绘制端口标签
        self._draw_port_labels(painter)
    
    def _draw_background(self, painter):
        """绘制圆角矩形背景"""
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._width, self._height, 8, 8)
        
        # 根据状态选择颜色
        state_colors = {
            "idle": QColor(240, 240, 240),
            "running": QColor(255, 193, 7),
            "success": QColor(76, 175, 80),
            "error": QColor(244, 67, 54),
        }
        color = state_colors.get(self._node_data.state, state_colors["idle"])
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        painter.drawPath(path)
    
    def _draw_title(self, painter):
        """绘制节点标题"""
        from PySide6.QtGui import QFont
        font = QFont("Microsoft YaHei", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor(33, 33, 33)))
        painter.drawText(QRectF(10, 5, self._width - 20, 25), Qt.AlignLeft, self._node_data.name)
    
    def _draw_port_labels(self, painter):
        """绘制端口标签"""
        from PySide6.QtGui import QFont
        font = QFont("Microsoft YaHei", 9)
        painter.setFont(font)
        painter.setPen(QPen(QColor(100, 100, 100)))
        
        # 绘制输入端口标签
        y = 35
        for name in self._input_ports:
            painter.drawText(QRectF(25, y, 80, 20), Qt.AlignLeft, f"→ {name}")
            y += 20
        
        # 绘制输出端口标签
        y = 35
        for name in self._output_ports:
            painter.drawText(QRectF(self._width - 95, y, 70, 20), Qt.AlignRight, f"{name} ←")
            y += 20
    
    def itemChange(self, change, value):
        """节点位置变化时更新连接线"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            for conn in self.scene().items():
                if isinstance(conn, ConnectionGraphicsItem):
                    conn.update_path()
        return super().itemChange(change, value)
    
    def get_port_position(self, port_name: str, is_input: bool) -> QPointF:
        """获取端口的场景坐标"""
        if is_input:
            if port_name in self._input_ports:
                index = list(self._input_ports.keys()).index(port_name)
                return self.mapToScene(QPointF(0, 45 + index * 20))
        else:
            if port_name in self._output_ports:
                index = list(self._output_ports.keys()).index(port_name)
                return self.mapToScene(QPointF(self._width, 45 + index * 20))
        return QPointF()


class ConnectionGraphicsItem(QGraphicsItem):
    """连接线图元 - 贝塞尔曲线"""
    
    def __init__(self, source_node, source_port, target_node, target_port, parent=None):
        super().__init__(parent)
        self._source_node = source_node
        self._source_port = source_port
        self._target_node = target_node
        self._target_port = target_port
        
        self.setZValue(-1)  # 连接线在节点下方
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
    
    def boundingRect(self) -> QRectF:
        """返回包围盒"""
        start = self._source_node.get_port_position(self._source_port, False)
        end = self._target_node.get_port_position(self._target_port, True)
        
        # 计算贝塞尔曲线的控制点范围
        extra = 50
        return QRectF(
            min(start.x(), end.x()) - extra,
            min(start.y(), end.y()) - extra,
            abs(end.x() - start.x()) + extra * 2,
            abs(end.y() - start.y()) + extra * 2
        )
    
    def paint(self, painter, option, widget):
        """绘制贝塞尔曲线"""
        start = self._source_node.get_port_position(self._source_port, False)
        end = self._target_node.get_port_position(self._target_port, True)
        
        # 计算控制点
        offset = abs(end.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + offset, start.y())
        ctrl2 = QPointF(end.x() - offset, end.y())
        
        # 创建贝塞尔曲线路径
        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(ctrl1, ctrl2, end)
        
        # 绘制曲线
        pen = QPen(QColor(100, 150, 200), 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
    
    def update_path(self):
        """更新路径（当节点移动时调用）"""
        self.prepareGeometryChange()
        self.update()


class PortGraphicsItem(QGraphicsItem):
    """端口图元 - 可连接的输入/输出点"""
    
    def __init__(self, port_name: str, data_type: str, is_input: bool, parent=None):
        super().__init__(parent)
        self._port_name = port_name
        self._data_type = data_type
        self._is_input = is_input
        self._radius = 6
        self._connected = False
        
        self.setAcceptHoverEvents(True)
    
    def boundingRect(self) -> QRectF:
        return QRectF(-self._radius, -self._radius, 
                      self._radius * 2, self._radius * 2)
    
    def paint(self, painter, option, widget):
        """绘制端口圆点"""
        # 根据数据类型选择颜色
        type_colors = {
            "str": QColor(76, 175, 80),    # 绿色 - 字符串
            "int": QColor(33, 150, 243),   # 蓝色 - 整数
            "float": QColor(156, 39, 176), # 紫色 - 浮点
            "bool": QColor(255, 152, 0),   # 橙色 - 布尔
            "dataframe": QColor(244, 67, 54),  # 红色 - DataFrame
            "file": QColor(0, 188, 212),     # 青色 - 文件
        }
        color = type_colors.get(self._data_type, QColor(150, 150, 150))
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(self.boundingRect().center(), self._radius, self._radius)
```

---

### 3.2.9 参考LiteGraph的Widget系统设计

参考LiteGraph的节点Widget系统，实现双重输入机制：节点输入既可以来自上一节点的连接，也可以来自用户通过UI组件的直接输入。

#### Widget类型定义

```python
# src/core/widget_types.py
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

class WidgetType(Enum):
    """Widget类型枚举"""
    NUMBER = "number"       # 数字输入
    SLIDER = "slider"       # 滑块
    COMBO = "combo"         # 下拉选择
    TEXT = "text"           # 文本输入
    TOGGLE = "toggle"       # 开关
    BUTTON = "button"       # 按钮


@dataclass
class WidgetDefinition:
    """Widget定义"""
    type: WidgetType
    name: str
    default_value: Any = None
    callback: Optional[Callable] = None
    options: dict = field(default_factory=dict)  # min, max, step, values等
    
    # 属性绑定（参考LiteGraph的property机制）
    property_name: Optional[str] = None  # 绑定到node.properties的属性名
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "name": self.name,
            "default": self.default_value,
            "options": self.options,
            "property": self.property_name,
        }
```

#### 双重输入机制

```python
# src/core/dual_input.py
from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class DualInput:
    """
    双重输入机制 - 参考LiteGraph设计
    
    输入优先级:
    1. 连接输入（来自上一节点）
    2. Widget输入（用户通过UI组件输入）
    """
    
    name: str
    data_type: str
    description: str = ""
    required: bool = True
    default: Any = None
    
    # 运行时状态
    _connection_value: Optional[Any] = None  # 来自连接的值
    _widget_value: Optional[Any] = None     # 来自Widget的值
    
    def get_value(self) -> Any:
        """
        获取输入值 - Fallback机制
        
        优先级: 连接值 > Widget值 > 默认值
        """
        if self._connection_value is not None:
            return self._connection_value
        if self._widget_value is not None:
            return self._widget_value
        return self.default
    
    def set_connection_value(self, value: Any):
        """设置连接值（由引擎调用）"""
        self._connection_value = value
    
    def set_widget_value(self, value: Any):
        """设置Widget值（由UI组件调用）"""
        self._widget_value = value
    
    def has_connection(self) -> bool:
        """是否有连接"""
        return self._connection_value is not None
    
    def reset(self):
        """重置状态"""
        self._connection_value = None
        # 注意: Widget值不重置，保持用户输入
```

#### 节点扩展：支持Widget

```python
# src/core/node_base.py (扩展)
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from .widget_types import WidgetDefinition, WidgetType
from .dual_input import DualInput

@dataclass
class NodeBaseWithWidgets:
    """
    支持Widget的节点基类
    
    参考LiteGraph设计:
    - 节点可以有连接输入和Widget输入
    - Widget可以绑定到properties
    - 执行时使用Fallback机制获取值
    """
    
    # 节点元信息
    node_type: str = ""
    display_name: str = ""
    category: str = "custom"
    icon: str = "🔧"
    description: str = ""
    
    # 输入定义（支持双重输入）
    inputs: List[DualInput] = field(default_factory=list)
    outputs: List[dict] = field(default_factory=list)
    
    # Widget定义
    widgets: List[WidgetDefinition] = field(default_factory=list)
    
    # 属性字典（Widget可以绑定到这里）
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # 运行时状态
    _state: str = "idle"
    _error: Optional[str] = None
    
    def add_widget(self, widget_type: WidgetType, name: str, 
                   default: Any = None, property_name: str = None,
                   **options) -> WidgetDefinition:
        """添加Widget"""
        widget = WidgetDefinition(
            type=widget_type,
            name=name,
            default_value=default,
            property_name=property_name,
            options=options,
        )
        self.widgets.append(widget)
        
        # 如果绑定了属性，初始化属性值
        if property_name and property_name not in self.properties:
            self.properties[property_name] = default
        
        return widget
    
    def get_input_value(self, name: str) -> Any:
        """获取输入值（使用Fallback机制）"""
        for inp in self.inputs:
            if inp.name == name:
                return inp.get_value()
        return None
    
    def execute(self, **inputs) -> Dict[str, Any]:
        """执行节点逻辑（子类实现）"""
        raise NotImplementedError
    
    def _run(self) -> bool:
        """运行节点（引擎调用）"""
        try:
            self._state = "running"
            self._error = None
            
            # 收集所有输入值
            input_values = {inp.name: inp.get_value() for inp in self.inputs}
            
            # 执行
            result = self.execute(**input_values)
            
            self._state = "success"
            return True
        except Exception as e:
            self._error = str(e)
            self._state = "error"
            return False
```

#### Widget示例：带Widget的节点

```python
# src/plugins/custom_nodes/widget_examples.py
from src.core.node_base import NodeBaseWithWidgets
from src.core.widget_types import WidgetType
from src.core.dual_input import DualInput
from typing import Dict, Any

class NumberFilterNode(NodeBaseWithWidgets):
    """数字过滤节点 - 演示Widget系统"""
    
    node_type = "number_filter"
    display_name = "数字过滤"
    category = "数据处理"
    icon = "🔢"
    description = "过滤数字，支持阈值和模式选择"
    
    def __init__(self):
        # 定义双重输入
        self.inputs = [
            DualInput("input", "float", "输入数字", required=True),
        ]
        
        self.outputs = [
            {"name": "output", "type": "float", "description": "过滤后的数字"},
            {"name": "filtered_count", "type": "int", "description": "被过滤的数量"},
        ]
        
        # 添加Widgets
        # 1. 阈值滑块 - 绑定到properties
        self.add_widget(
            WidgetType.SLIDER, "阈值", 0.5, 
            property_name="threshold",
            min=0, max=1, step=0.01
        )
        
        # 2. 模式选择下拉框 - 绑定到properties
        self.add_widget(
            WidgetType.COMBO, "模式", "大于",
            property_name="mode",
            values=["大于", "小于", "等于"]
        )
        
        # 3. 启用开关
        self.add_widget(
            WidgetType.TOGGLE, "启用过滤", True,
            property_name="enabled"
        )
    
    def execute(self, **inputs) -> Dict[str, Any]:
        """执行过滤逻辑"""
        if not self.properties.get("enabled", True):
            # 未启用,直接返回输入
            return {
                "output": inputs.get("input", 0),
                "filtered_count": 0,
            }
        
        input_value = inputs.get("input", 0)
        threshold = self.properties.get("threshold", 0.5)
        mode = self.properties.get("mode", "大于")
        
        # 根据模式过滤
        if mode == "大于":
            passed = input_value > threshold
        elif mode == "小于":
            passed = input_value < threshold
        else:  # 等于
            passed = abs(input_value - threshold) < 0.001
        
        return {
            "output": input_value if passed else None,
            "filtered_count": 0 if passed else 1,
        }
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

### 3.4 UI组件（PySide6）

#### 3.4.1 应用状态模型

```python
# src/ui/state.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    """应用全局状态 - 使用Qt信号实现响应式"""
    
    # 信号定义
    view_changed = Signal(str)           # 视图切换信号
    messages_changed = Signal()          # 消息列表变化信号
    loading_changed = Signal(bool)       # 加载状态变化信号
    plugins_changed = Signal(list)       # 插件列表变化信号
    
    def __init__(self):
        super().__init__()
        self._current_view: str = "chat"
        self._messages: List[dict] = []
        self._is_loading: bool = False
        self._current_graph_id: Optional[str] = None
        self._selected_node_id: Optional[str] = None
        self._loaded_plugins: List[str] = []
        self._available_tools: List[str] = []
    
    # 属性访问器（带信号通知）
    @property
    def current_view(self) -> str:
        return self._current_view
    
    @current_view.setter
    def current_view(self, value: str):
        if self._current_view != value:
            self._current_view = value
            self.view_changed.emit(value)
    
    @property
    def is_loading(self) -> bool:
        return self._is_loading
    
    @is_loading.setter
    def is_loading(self, value: bool):
        if self._is_loading != value:
            self._is_loading = value
            self.loading_changed.emit(value)
    
    def switch_view(self, view_name: str):
        """切换视图"""
        self.current_view = view_name
    
    def add_message(self, role: str, content: str):
        """添加消息"""
        self._messages.append({"role": role, "content": content})
        self.messages_changed.emit()
    
    def clear_messages(self):
        """清空消息"""
        self._messages.clear()
        self.messages_changed.emit()
    
    def get_messages(self) -> List[dict]:
        """获取消息列表"""
        return self._messages.copy()
```

#### 3.4.2 AI对话面板

```python
# src/ui/components/chat_panel.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QScrollArea, QLabel, QFrame
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QFont
from src.ui.state import AppState


class MessageBubble(QFrame):
    """单条消息气泡组件"""
    
    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.setup_ui(content)
    
    def setup_ui(self, content: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        
        # 角色标签
        role_label = QLabel("你" if self.role == "user" else "助手")
        role_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        role_label.setStyleSheet(
            "color: #2196F3;" if self.role == "user" else "color: #4CAF50;"
        )
        
        # 消息内容
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        layout.addWidget(role_label)
        layout.addWidget(content_label)
        
        # 样式
        if self.role == "user":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #E3F2FD;
                    border-radius: 10px;
                    margin-left: 50px;
                }
            """)
        else:
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #E8F5E9;
                    border-radius: 10px;
                    margin-right: 50px;
                }
            """)


class ChatPanel(QWidget):
    """AI对话面板"""
    
    message_sent = Signal(str)  # 发送消息信号
    
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 消息滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                background-color: #FAFAFA;
            }
        """)
        
        # 消息容器
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(10)
        self.scroll_area.setWidget(self.messages_container)
        
        # 输入区域
        input_layout = QHBoxLayout()
        
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.setMaximumHeight(80)
        self.input_field.setStyleSheet("""
            QTextEdit {
                border: 1px solid #BDBDBD;
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 1px solid #2196F3;
            }
        """)
        
        self.send_button = QPushButton("发送")
        self.send_button.setFixedSize(80, 40)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.send_button.clicked.connect(self.on_send)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        
        layout.addWidget(self.scroll_area, stretch=1)
        layout.addLayout(input_layout)
    
    def connect_signals(self):
        """连接状态信号"""
        self.state.messages_changed.connect(self.refresh_messages)
        self.state.loading_changed.connect(self.on_loading_changed)
    
    @Slot()
    def refresh_messages(self):
        """刷新消息列表"""
        # 清空现有消息
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新消息
        for msg in self.state.get_messages():
            bubble = MessageBubble(msg["role"], msg["content"])
            self.messages_layout.addWidget(bubble)
        
        # 滚动到底部
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
    
    @Slot(bool)
    def on_loading_changed(self, loading: bool):
        """加载状态变化"""
        self.send_button.setEnabled(not loading)
        if loading:
            self.send_button.setText("发送中...")
        else:
            self.send_button.setText("发送")
    
    @Slot()
    def on_send(self):
        """发送消息"""
        text = self.input_field.toPlainText().strip()
        if text:
            self.message_sent.emit(text)
            self.input_field.clear()
```

#### 3.4.3 导航栏

```python
# src/ui/components/navigation.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class NavigationButton(QPushButton):
    """导航按钮"""
    
    def __init__(self, icon: str, label: str, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setup_ui(icon, label)
    
    def setup_ui(self, icon: str, label: str):
        self.setText(f"{icon}\n{label}")
        self.setFixedSize(80, 70)
        self.setFont(QFont("Segoe UI Emoji", 10))
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #616161;
                border: none;
                border-radius: 8px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #E3F2FD;
                color: #2196F3;
            }
            QPushButton:checked {
                background-color: #2196F3;
                color: white;
            }
        """)
        self.setCheckable(True)


class NavigationRail(QWidget):
    """侧边导航栏"""
    
    view_changed = Signal(str)  # 视图切换信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_index = 0
        self.buttons = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 10, 5, 10)
        
        # 应用标题
        title = QLabel("办公工具箱")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #2196F3; padding: 10px;")
        layout.addWidget(title)
        
        # 导航按钮
        nav_items = [
            ("💬", "对话", "chat"),
            ("🔗", "节点流", "node_editor"),
            ("🧩", "插件", "plugins"),
        ]
        
        for i, (icon, label, view_name) in enumerate(nav_items):
            btn = NavigationButton(icon, label, i)
            btn.clicked.connect(lambda checked, idx=i, view=view_name: self.on_nav_click(idx, view))
            self.buttons.append(btn)
            layout.addWidget(btn)
        
        # 默认选中第一个
        self.buttons[0].setChecked(True)
        
        layout.addStretch()
        
        # 设置导航栏样式
        self.setFixedWidth(100)
        self.setStyleSheet("""
            NavigationRail {
                background-color: #FAFAFA;
                border-right: 1px solid #E0E0E0;
            }
        """)
    
    def on_nav_click(self, index: int, view_name: str):
        """导航按钮点击"""
        # 更新选中状态
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        
        self.current_index = index
        self.view_changed.emit(view_name)
    
    def set_current_view(self, view_name: str):
        """设置当前视图（外部调用）"""
        view_map = {"chat": 0, "node_editor": 1, "plugins": 2}
        if view_name in view_map:
            index = view_map[view_name]
            for i, btn in enumerate(self.buttons):
                btn.setChecked(i == index)
            self.current_index = index
```

#### 3.4.4 主窗口

```python
# src/ui/main_window.py
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from src.ui.state import AppState
from src.ui.components.chat_panel import ChatPanel
from src.ui.components.navigation import NavigationRail


class PlaceholderWidget(QWidget):
    """占位组件（待实现功能）"""
    
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Microsoft YaHei", 16))
        label.setStyleSheet("color: #9E9E9E;")
        
        layout.addWidget(label)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        self.setWindowTitle("办公小工具整合平台")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 导航栏
        self.nav_rail = NavigationRail()
        
        # 内容区域（堆叠布局）
        self.content_stack = QStackedWidget()
        
        # 创建各视图
        self.chat_panel = ChatPanel(self.state)
        self.node_editor = NodeEditorWidget(self.state)  # 节点编辑器
        self.plugin_panel = PlaceholderWidget("🚧 插件管理（待实现）")
        
        self.content_stack.addWidget(self.chat_panel)      # index 0
        self.content_stack.addWidget(self.node_editor)     # index 1
        self.content_stack.addWidget(self.plugin_panel)    # index 2
        
        main_layout.addWidget(self.nav_rail)
        main_layout.addWidget(self.content_stack, stretch=1)
        
        # 应用全局样式
        self.apply_global_style()
    
    def connect_signals(self):
        """连接信号"""
        # 导航切换
        self.nav_rail.view_changed.connect(self.on_view_changed)
        self.state.view_changed.connect(self.on_state_view_changed)
        
        # 聊天消息
        self.chat_panel.message_sent.connect(self.on_message_sent)
    
    @Slot(str)
    def on_view_changed(self, view_name: str):
        """导航切换响应"""
        self.state.switch_view(view_name)
    
    @Slot(str)
    def on_state_view_changed(self, view_name: str):
        """状态变化响应"""
        view_index = {"chat": 0, "node_editor": 1, "plugins": 2}
        if view_name in view_index:
            self.content_stack.setCurrentIndex(view_index[view_name])
    
    @Slot(str)
    def on_message_sent(self, message: str):
        """发送消息"""
        # 添加用户消息
        self.state.add_message("user", message)
        
        # 模拟AI响应（实际应调用AgentScope）
        self.state.is_loading = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self.simulate_ai_response(message))
    
    def simulate_ai_response(self, user_message: str):
        """模拟AI响应"""
        self.state.is_loading = False
        self.state.add_message("assistant", f"收到您的消息：{user_message}\n\n我是办公助手，可以帮您处理Excel对比、表格合并等任务。")
    
    def apply_global_style(self):
        """应用全局样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
            QStackedWidget {
                background-color: #FFFFFF;
            }
        """)
```

#### 3.4.5 入口文件

```python
# src/main.py
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow


def main():
    """应用入口"""
    # 高DPI支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 启动事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

#### 3.4.6 QSS主题样式表

```python
# src/ui/theme.py
"""现代化扁平主题样式表"""

# 色彩体系
COLORS = {
    "primary": "#2196F3",       # 主色（蓝色）
    "primary_dark": "#1976D2",  # 主色深
    "secondary": "#4CAF50",     # 辅助色（绿色）
    "accent": "#FF9800",        # 强调色（橙色）
    "background": "#FAFAFA",    # 背景色
    "surface": "#FFFFFF",       # 表面色
    "error": "#F44336",         # 错误色
    "text_primary": "#212121",  # 主文本色
    "text_secondary": "#757575",# 次文本色
    "divider": "#E0E0E0",       # 分割线色
}

# 全局样式表
GLOBAL_STYLESHEET = f"""
/* 全局字体 */
QWidget {{
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 14px;
    color: {COLORS['text_primary']};
}}

/* 主窗口 */
QMainWindow {{
    background-color: {COLORS['background']};
}}

/* 按钮 */
QPushButton {{
    background-color: {COLORS['primary']};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {COLORS['primary_dark']};
}}

QPushButton:pressed {{
    background-color: #1565C0;
}}

QPushButton:disabled {{
    background-color: #BDBDBD;
    color: #9E9E9E;
}}

/* 输入框 */
QLineEdit, QTextEdit {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['divider']};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {COLORS['primary']};
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 2px solid {COLORS['primary']};
}}

/* 滚动条 */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: #BDBDBD;
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #9E9E9E;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* 滚动区域 */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

/* 标签 */
QLabel {{
    color: {COLORS['text_primary']};
    background-color: transparent;
}}

/* 下拉框 */
QComboBox {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['divider']};
    border-radius: 6px;
    padding: 8px;
}}

QComboBox:focus {{
    border: 2px solid {COLORS['primary']};
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

/* 标签页 */
QTabWidget::pane {{
    border: 1px solid {COLORS['divider']};
    border-radius: 6px;
    background-color: {COLORS['surface']};
}}

QTabBar::tab {{
    background-color: {COLORS['background']};
    border: 1px solid {COLORS['divider']};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['surface']};
    border-bottom: 2px solid {COLORS['primary']};
}}

/* 工具提示 */
QToolTip {{
    background-color: #424242;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px;
}}
"""

def apply_theme(app: QApplication):
    """应用主题到应用"""
    app.setStyleSheet(GLOBAL_STYLESHEET)
```

#### 3.4.7 节点编辑器UI组件

完整的节点编辑器实现，基于 `QGraphicsView` 框架，参考 **SpatialNode** 和 **LiteGraph** 的设计模式。

##### 文件结构

```
src/ui/components/node_editor/
├── __init__.py
├── scene.py              # NodeEditorScene - 场景管理
├── view.py               # NodeEditorView - 视图和交互
├── items/
│   ├── __init__.py
│   ├── node_item.py        # 节点图元
│   ├── connection_item.py  # 连接线图元
│   ├── port_item.py       # 端口图元
│   └── widget_item.py     # Widget图元
└── widgets/
    ├── __init__.py
    ├── widget_base.py     # Widget基类
    ├── number_widget.py  # 数字Widget
    ├── combo_widget.py   # 下拉Widget
    └── text_widget.py    # 文本Widget
```

##### 节点编辑器主窗口

```python
# src/ui/components/node_editor/__init__.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Signal
from .scene import NodeEditorScene
from .view import NodeEditorView

class NodeEditorWidget(QWidget):
    """
    节点编辑器主组件
    
    布局:
    ┌─────────────────────────────────────────────────────────────────┐
    │  左侧面板  │              中间画布              │  右侧属性面板 │
    │  节点列表  │          QGraphicsView            │   节点属性    │
    │           │                              │   Widget配置  │
    └─────────────────────────────────────────────────────────────────┘
    """
    
    node_selected = Signal(object)   # 节点选中信号
    graph_executed = Signal(dict)   # 图执行完成信号
    
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._scene = None
        self._view = None
        self._selected_node = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧：节点面板
        left_panel = self._create_node_panel()
        layout.addWidget(left_panel)
        
        # 中间：节点画布
        self._scene = NodeEditorScene(self)
        self._view = NodeEditorView(self._scene, self)
        layout.addWidget(self._view, stretch=1)
        
        # 右侧：属性面板
        right_panel = self._create_properties_panel()
        layout.addWidget(right_panel)
    
    def _create_node_panel(self) -> QWidget:
        """创建节点面板"""
        from PySide6.QtWidgets import QLabel, QListWidget, QLineEdit
        from PySide6.QtCore import Qt
        
        panel = QWidget()
        panel.setFixedWidth(200)
        layout = QVBoxLayout(panel)
        
        # 搜索框
        search = QLineEdit()
        search.setPlaceholderText("搜索节点...")
        layout.addWidget(search)
        
        # 节点分类列表
        layout.addWidget(QLabel("节点类型"))
        
        node_list = QListWidget()
        # 填充可用节点类型
        for node_type in self._engine.get_available_nodes():
            node_list.addItem(f"{node_type['icon']} {node_type['name']}")
        layout.addWidget(node_list)
        
        # 双击添加节点
        node_list.itemDoubleClicked.connect(
            lambda: self._add_selected_node_type(node_list.currentItem())
        )
        
        return panel
    
    def _create_properties_panel(self) -> QWidget:
        """创建属性面板"""
        from PySide6.QtWidgets import QLabel, QScrollArea, QWidget, QVBoxLayout
        from .widgets import create_widget_for_definition
        
        panel = QWidget()
        panel.setFixedWidth(280)
        layout = QVBoxLayout(panel)
        
        layout.addWidget(QLabel("节点属性"))
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._properties_container = QWidget()
        self._properties_layout = QVBoxLayout(self._properties_container)
        scroll.setWidget(self._properties_container)
        layout.addWidget(scroll)
        
        return panel
    
    def _add_selected_node_type(self, item):
        """添加选中的节点类型到画布"""
        if item:
            # 获取场景中心位置
            center = self._view.mapToScene(
                self._view.viewport().rect().center()
            )
            # 创建节点
            self._engine.create_node(item.text(), (center.x(), center.y()))
    
    def load_graph(self, graph):
        """加载节点图到编辑器"""
        # 清空场景
        self._scene.clear()
        
        # 创建节点图元
        for node in graph.nodes.values():
            from .items import NodeGraphicsItem
            node_item = NodeGraphicsItem(node, self._engine)
            self._scene.addItem(node_item)
        
        # 创建连接线图元
        for conn in graph.connections.values():
            from .items import ConnectionGraphicsItem
            source = self._scene.node_item(conn.source_node)
            target = self._scene.node_item(conn.target_node)
            if source and target:
                conn_item = ConnectionGraphicsItem(
                    source, conn.source_port,
                    target, conn.target_port
                )
                self._scene.addItem(conn_item)
    
    def update_properties_panel(self, node):
        """更新属性面板"""
        # 清空现有内容
        while self._properties_layout.count():
            item = self._properties_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not node:
            return
        
        # 获取节点定义
        node_def = self._engine.node_types.get(node.type)
        if not node_def:
            return
        
        # 创建Widget
        from .widgets import create_widget_for_definition
        
        for widget_def in node_def.widgets:
            widget = create_widget_for_definition(widget_def, self._properties_container)
            if widget:
                self._properties_layout.addWidget(widget)
```

##### 动态Widget渲染

参考LiteGraph的Widget系统，动态渲染不同类型的输入组件。

```python
# src/ui/components/node_editor/widgets/widget_base.py
from abc import ABC, abstractmethod
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

class NodeWidgetBase(QWidget, ABC):
    """
    节点Widget基类
    
    参考LiteGraph设计:
    - Widget可以绑定到节点属性
    - 值变化时发射信号
    - 支持序列化
    """
    
    value_changed = Signal(object)  # 值变化信号
    
    def __init__(self, definition, parent=None):
        super().__init__(parent)
        self._definition = definition
        self._value = definition.default_value
        
        # 绑定到属性
        if definition.property_name:
            self.value_changed.connect(
                lambda v: self._on_property_change(definition.property_name, v)
            )
    
    @abstractmethod
    def get_value(self) -> object:
        """获取当前值"""
        pass
    
    @abstractmethod
    def set_value(self, value: object):
        """设置值"""
        pass
    
    def _on_property_change(self, property_name: str, value: object):
        """属性变化回调（子类可覆盖）"""
        pass


# src/ui/components/node_editor/widgets/number_widget.py
from PySide6.QtWidgets import QDoubleSpinBox, QLabel, QVBoxLayout
from PySide6.QtCore import Qt
from .widget_base import NodeWidgetBase

class NumberWidget(NodeWidgetBase):
    """数字输入Widget"""
    
    def __init__(self, definition, parent=None):
        super().__init__(definition, parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标签
        label = QLabel(self._definition.name)
        layout.addWidget(label)
        
        # 数字输入框
        self._spinbox = QDoubleSpinBox()
        options = self._definition.options
        self._spinbox.setRange(
            options.get("min", -999999),
            options.get("max", 999999)
        )
        self._spinbox.setSingleStep(options.get("step", 1))
        self._spinbox.setValue(self._value or 0)
        self._spinbox.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self._spinbox)
    
    def get_value(self) -> float:
        return self._spinbox.value()
    
    def set_value(self, value: float):
        self._spinbox.setValue(value)
    
    def _on_value_changed(self, value: float):
        self._value = value
        self.value_changed.emit(value)


# src/ui/components/node_editor/widgets/combo_widget.py
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout
from .widget_base import NodeWidgetBase

class ComboWidget(NodeWidgetBase):
    """下拉选择Widget"""
    
    def __init__(self, definition, parent=None):
        super().__init__(definition, parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标签
        label = QLabel(self._definition.name)
        layout.addWidget(label)
        
        # 下拉框
        self._combo = QComboBox()
        values = self._definition.options.get("values", [])
        self._combo.addItems(values)
        if self._value and self._value in values:
            self._combo.setCurrentText(self._value)
        self._combo.currentTextChanged.connect(self._on_value_changed)
        layout.addWidget(self._combo)
    
    def get_value(self) -> str:
        return self._combo.currentText()
    
    def set_value(self, value: str):
        self._combo.setCurrentText(value)
    
    def _on_value_changed(self, value: str):
        self._value = value
        self.value_changed.emit(value)


# src/ui/components/node_editor/widgets/text_widget.py
from PySide6.QtWidgets import QLineEdit, QLabel, QVBoxLayout
from .widget_base import NodeWidgetBase

class TextWidget(NodeWidgetBase):
    """文本输入Widget"""
    
    def __init__(self, definition, parent=None):
        super().__init__(definition, parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标签
        label = QLabel(self._definition.name)
        layout.addWidget(label)
        
        # 文本输入框
        self._line_edit = QLineEdit()
        self._line_edit.setText(str(self._value or ""))
        self._line_edit.setPlaceholderText(f"输入{self._definition.name}...")
        self._line_edit.textChanged.connect(self._on_value_changed)
        layout.addWidget(self._line_edit)
    
    def get_value(self) -> str:
        return self._line_edit.text()
    
    def set_value(self, value: str):
        self._line_edit.setText(str(value))
    
    def _on_value_changed(self, value: str):
        self._value = value
        self.value_changed.emit(value)


# src/ui/components/node_editor/widgets/__init__.py
from .widget_base import NodeWidgetBase
from .number_widget import NumberWidget
from .combo_widget import ComboWidget
from .text_widget import TextWidget
from src.core.widget_types import WidgetType

def create_widget_for_definition(definition, parent=None) -> NodeWidgetBase:
    """根据Widget定义创建对应的Widget实例"""
    widgets = {
        WidgetType.NUMBER: NumberWidget,
        WidgetType.SLIDER: NumberWidget,  # Slider也用NumberWidget
        WidgetType.COMBO: ComboWidget,
        WidgetType.TEXT: TextWidget,
    }
    
    widget_class = widgets.get(definition.type)
    if widget_class:
        return widget_class(definition, parent)
    return None
```

##### 動態Widget嵌入到QGraphicsItem（可選）

如果需要将Widget直接嵌入到节点图元中，可以使用 `QGraphicsProxyWidget`:

```python
# src/ui/components/node_editor/items/widget_item.py
from PySide6.QtWidgets import QGraphicsProxyWidget
from PySide6.QtCore import QPointF
from ..widgets import create_widget_for_definition

class WidgetProxyItem(QGraphicsProxyWidget):
    """
    Widget代理图元 - 将QWidget嵌入到QGraphicsScene中
    """
    
    def __init__(self, widget_definition, parent_item, parent=None):
        super().__init__(parent)
        self._parent_item = parent_item
        self._widget = create_widget_for_definition(widget_definition)
        self.setWidget(self._widget)
        self.setParentItem(parent_item)
    
    def set_position(self, pos: QPointF):
        """设置位置"""
        self.setPos(pos)
```

---

## 4. 目录结构

> 遵循 Python 标准项目结构

```
 office/                         # 项目根目录
 ├── README.md                   # 项目说明
 ├── pyproject.toml              # 项目配置（依赖、元信息）
 │
 ├── src/                        # 源代码目录
 │   ├── assets/                 # 静态资源（图片、图标、QSS等）
 │   │   └── icon.png
 │   │
 │   ├── main.py                 # 应用入口
 │   │
 │   ├── core/                   # 核心模块
 │   │   ├── __init__.py
 │   │   ├── plugin_base.py      # 插件基类和工具定义
 │   │   ├── plugin_manager.py   # 插件管理器
 │   │   ├── node_base.py        # 自定义节点基类
 │   │   ├── node_engine.py      # 自研节点流引擎
 │   │   └── node_registry.py    # 节点注册中心
 │   │
 │   ├── agents/                 # AI Agent模块
 │   │   ├── __init__.py
 │   │   └── office_agent.py     # AgentScope Agent配置
 │   │
 │   ├── ui/                     # PySide6 UI组件
 │   │   ├── __init__.py
 │   │   ├── main_window.py      # 主窗口
 │   │   ├── state.py            # 应用状态管理
 │   │   ├── theme.py            # QSS主题样式表
 │   │   ├── components/         # UI子组件
 │   │   │   ├── chat_panel.py   # AI对话面板
 │   │   │   ├── navigation.py   # 导航栏
 │   │   │   └── node_editor.py  # 节点编辑器UI
 │   │
 │   ├── plugins/                # 插件目录
 │   │   ├── __init__.py
 │   │   ├── excel_tools/        # Excel工具插件
 │   │   │   └── __init__.py
 │   │   ├── table_tools/        # 表格处理插件
 │   │   │   └── __init__.py
 │   │   ├── wechat_tools/       # 微信工具插件
 │   │   │   └── __init__.py
 │   │
 │   ├── custom_nodes/           # 自定义节点
 │   └── config/                 # 配置文件
 │       └── settings.yaml
 │
 ├── storage/                    # 存储目录
 │   ├── data/                   # 持久化数据
 │   └── temp/                   # 临时文件
 │
 ├── docs/                       # 文档目录
 │   └── ARCHITECTURE.md         # 架构文档
 │
 ├── excel_compare.py            # 现有: Excel对比工具 (待迁移为插件)
 ├── table.py                    # 现有: 表格处理 (待迁移为插件)
 └── chat.py                     # 现有: 微信助手 (待迁移为插件)
 ```

### 运行命令

```bash
# 开发运行
uv run python src/main.py

# 或使用Python直接运行
python src/main.py

# 打包发布 (使用 PyInstaller)
pip install pyinstaller
pyinstaller --windowed --onefile --name="OfficeTools" src/main.py
```

---

## 5. 数据流

### 5.1 Qt信号槽数据流

```
用户操作 (Event)
     │
     ▼
触发 Qt Signal
     │
     ▼
更新 QObject 属性
     │
     ▼
发射变化 Signal (如 messages_changed)
     │
     ▼
连接的 Slot 被调用
     │
     ▼
UI组件更新（手动刷新或重新渲染）
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
          └─► 通过回调通知 UI 更新
```

---

### 5.4 Widget输入与连接输入的数据流

```
用户设置Widget值
      │
      ▼
Widget.value_changed 信号
      │
      ▼
更新 node.properties[property_name]
      │
      ├───────────────────────────────┐
      │                               │
      ▼                               ▼
连接输入 (来自上一节点)         Widget值 (用户输入)
      │                               │
      └───────────┬───────────────┘
                  │               │
                  ▼               ▼
            DualInput.get_value()
                  │               │
                  └───────────────┘
                          │
                          ▼
                  返回连接值 (如果有)
                          │
                          ▼ (如果没有连接)
                  返回Widget值
                          │
                          ▼ (如果没有Widget值)
                  返回默认值
```

**关键设计点**:
1. **Fallback机制**： 连接优先于Widget，Widget优先于默认值
2. **属性绑定**： Widget可以直接绑定到 `node.properties`，数据自动持久化
3. **运行时更新**： 连接断开时自动使用Widget值，连接建立时Widget值被忽略

---

## 6. 关键设计决策

---

## 6. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| **UI范式** | PySide6 + 信号槽 | Qt原生Python绑定，成熟稳定，QSS样式定制灵活 |
| **AI框架** | AgentScope | ReAct范式，Toolkit管理，支持MCP |
| **插件系统** | 自研 | 轻量、灵活、与AgentScope/NodeEngine深度集成 |
| **节点引擎** | 自研 | 无第三方依赖，便于QGraphicsView集成 |
| **Widget系统** | 参考LiteGraph | 双重输入机制，Widget可绑定属性， 支持动态UI组件 |
| **工具Schema** | ToolDefinition | 统一格式，同时生成OpenAI Schema和节点端口 |
| **主题设计** | QSS样式表 | 现代化扁平风格，统一色彩体系 |

---

## 7. 依赖清单

```toml
[project]
dependencies = [
    "PySide6>=6.6.0",          # Qt官方Python绑定 (UI框架)
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
| **Phase 2** | PySide6 UI组件 + AI对话 | 2周 |
| **Phase 3** | 节点编辑器UI (QGraphicsView) + 连线功能 | 2周 |
| **Phase 4** | 迁移现有工具为插件 | 1周 |
| **Phase 5** | 打磨优化 + 文档 | 1周 |

---

*文档版本: 6.0 | 最后更新: 2026-03-25 | PySide6 + AgentScope + 自研节点引擎 + LiteGraph风格Widget系统*
