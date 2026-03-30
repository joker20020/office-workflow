# 插件和节点包开发指南

本文档介绍如何为办公小工具整合平台开发插件和节点包。

---

## 目录

- [概述](#概述)
- [第一部分：插件开发](#第一部分插件开发)
- [第二部分：节点包开发](#第二部分节点包开发)
- [第三部分：API 参考](#第三部分api-参考)
- [第四部分：最佳实践](#第四部分最佳实践)
- [第五部分：常见问题](#第五部分常见问题)

---

## 概述

### 插件 vs 节点包

| 特性 | 插件 (Plugin) | 节点包 (Node Package) |
|------|---------------|----------------------|
| **用途** | 扩展程序功能 | 添加新的节点类型 |
| **入口** | `PluginBase` 子类 | `NodeDefinition` 定义 |
| **通信方式** | 事件系统、Agent API | 节点执行函数 |
| **权限** | 需要声明权限 | 无需权限声明 |
| **目录** | `plugins/` | `node_packages/` |
| **分发** | 本地安装 | Git 仓库 |

简单来说：
- **插件** 用于扩展程序本身的能力（如添加 Agent 工具、订阅事件、扩展 UI）
- **节点包** 用于添加可在工作流中使用的节点（如文本处理、数据转换）

---

## 第一部分：插件开发

### 1.1 插件是什么

插件是扩展程序功能的模块，通过事件系统与程序或其他插件通信。插件**不提供节点**（节点通过节点包管理）。

插件可以：
- 订阅和发布事件
- 访问 AgentScope 的 tool/mcp/skill 管理接口
- 扩展程序 UI
- 添加自定义功能

### 1.2 插件生命周期

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
| **发现** | 扫描 `plugins/` 目录，识别插件模块 |
| **权限检查** | 读取插件声明的 `permissions`，检查是否已授权 |
| **用户确认** | 未授权权限弹窗请求用户确认（首次加载） |
| **加载** | 调用 `on_enable(context)` 方法 |
| **活跃** | 在已授权权限范围内响应事件、使用接口 |
| **卸载** | 调用 `on_disable()` 方法，清理资源 |

### 1.3 权限系统

插件必须显式声明所需权限，遵循最低权限原则。

#### 可用权限

| 权限 | 说明 |
|------|------|
| `FILE_READ` | 读取文件 |
| `FILE_WRITE` | 写入文件 |
| `NETWORK` | 网络访问 |
| `AGENT_TOOL` | 注册/注销 Agent 工具 |
| `AGENT_MCP` | 配置 MCP 服务 |
| `AGENT_SKILL` | 加载/卸载 Skill |
| `AGENT_CHAT` | 调用 Agent 对话 |
| `EVENT_SUBSCRIBE` | 订阅事件 |
| `EVENT_PUBLISH` | 发布事件 |
| `NODE_READ` | 读取节点信息 |
| `NODE_REGISTER` | 注册节点 |
| `STORAGE_READ` | 读取持久化数据 |
| `STORAGE_WRITE` | 写入持久化数据 |

### 1.4 创建插件

#### 步骤 1：创建目录结构

```
plugins/
└── my_plugin/
    └── __init__.py    # 插件入口文件
```

#### 步骤 2：编写插件类

```python
# plugins/my_plugin/__init__.py
# -*- coding: utf-8 -*-
"""
我的自定义插件
"""

from src.core.plugin_base import PluginBase
from src.core.permission_manager import Permission, PermissionSet


class MyPlugin(PluginBase):
    """示例插件 - 演示插件开发流程"""
    
    # 插件元数据（必填）
    name = "my_plugin"
    version = "1.0.0"
    description = "我的自定义插件，演示插件开发"
    author = "Your Name"
    
    # 声明所需权限（最低权限原则）
    permissions = PermissionSet.from_list([
        Permission.EVENT_SUBSCRIBE,   # 订阅事件
        Permission.AGENT_TOOL,        # 注册 Agent 工具
    ])
    
    def on_enable(self, context):
        """
        插件启用时调用
        
        Args:
            context: AppContext 实例，提供程序功能访问
        """
        # 1. 订阅事件（需要 EVENT_SUBSCRIBE 权限）
        context.event_bus.subscribe(
            "node.executed",
            self._on_node_executed
        )
        
        # 2. 注册 Agent 工具（需要 AGENT_TOOL 权限）
        context.agent.register_tool(
            name="my_custom_tool",
            description="自定义工具：处理输入文本",
            func=self._my_tool_func,
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要处理的文本"
                    }
                },
                "required": ["text"]
            }
        )
        
        print(f"[{self.name}] 插件已启用")
    
    def on_disable(self):
        """插件禁用时调用，清理资源"""
        # 清理注册的资源
        print(f"[{self.name}] 插件已禁用")
    
    def _on_node_executed(self, event_data):
        """节点执行完成事件处理器"""
        node_type = event_data.get("node_type")
        result = event_data.get("result")
        print(f"[{self.name}] 节点 {node_type} 执行完成")
    
    def _my_tool_func(self, text: str) -> dict:
        """自定义工具实现"""
        return {
            "result": f"处理后的文本: {text}",
            "length": len(text)
        }


# 导出插件类（必须）
plugin_class = MyPlugin
```

### 1.5 完整插件示例

以下是一个功能完整的插件示例，展示了常用功能：

```python
# plugins/workflow_logger/__init__.py
# -*- coding: utf-8 -*-
"""
工作流日志插件

功能：
- 记录所有节点执行结果
- 订阅工作流事件
- 提供 Agent 工具查询执行历史
"""

from datetime import datetime
from typing import Dict, Any, List

from src.core.plugin_base import PluginBase
from src.core.permission_manager import Permission, PermissionSet


class WorkflowLoggerPlugin(PluginBase):
    """工作流日志插件"""
    
    name = "workflow_logger"
    version = "1.0.0"
    description = "记录工作流执行历史，提供查询接口"
    author = "OfficeTools"
    
    permissions = PermissionSet.from_list([
        Permission.EVENT_SUBSCRIBE,
        Permission.EVENT_PUBLISH,
        Permission.AGENT_TOOL,
        Permission.STORAGE_WRITE,
        Permission.STORAGE_READ,
    ])
    
    # 内部状态
    _execution_history: List[Dict[str, Any]] = []
    
    def on_enable(self, context):
        """插件启用"""
        self._context = context
        
        # 订阅节点执行事件
        context.event_bus.subscribe("node.executed", self._on_node_executed)
        context.event_bus.subscribe("workflow.started", self._on_workflow_started)
        context.event_bus.subscribe("workflow.completed", self._on_workflow_completed)
        
        # 注册 Agent 工具
        context.agent.register_tool(
            name="get_execution_history",
            description="获取节点执行历史记录",
            func=self._get_history_tool,
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大记录数"
                    }
                }
            }
        )
        
        context.agent.register_tool(
            name="clear_execution_history",
            description="清空执行历史记录",
            func=self._clear_history_tool,
            parameters={"type": "object", "properties": {}}
        )
        
        self._log("工作流日志插件已启用")
    
    def on_disable(self):
        """插件禁用"""
        self._execution_history.clear()
        self._log("工作流日志插件已禁用")
    
    def _on_node_executed(self, event_data: Dict[str, Any]):
        """记录节点执行"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "event": "node_executed",
            "node_id": event_data.get("node_id"),
            "node_type": event_data.get("node_type"),
            "success": event_data.get("success", False),
            "result": event_data.get("result"),
            "error": event_data.get("error"),
        }
        self._execution_history.append(record)
        
        # 限制历史记录数量
        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-500:]
    
    def _on_workflow_started(self, event_data: Dict[str, Any]):
        """工作流开始"""
        self._log(f"工作流开始: {event_data.get('workflow_name', 'Unknown')}")
    
    def _on_workflow_completed(self, event_data: Dict[str, Any]):
        """工作流完成"""
        success = event_data.get("success", False)
        self._log(f"工作流完成: {'成功' if success else '失败'}")
    
    def _get_history_tool(self, limit: int = 10) -> dict:
        """Agent 工具：获取执行历史"""
        history = self._execution_history[-limit:] if limit else self._execution_history
        return {
            "count": len(history),
            "records": history
        }
    
    def _clear_history_tool(self) -> dict:
        """Agent 工具：清空历史"""
        count = len(self._execution_history)
        self._execution_history.clear()
        return {
            "success": True,
            "cleared_count": count
        }
    
    def _log(self, message: str):
        """日志输出"""
        print(f"[{self.name}] {message}")


# 导出插件类
plugin_class = WorkflowLoggerPlugin
```

---

## 第二部分：节点包开发

### 2.1 节点包是什么

节点包是一组相关节点的集合，可以从 Git 仓库安装。每个节点包包含：

- `package.json` - 包元信息
- `nodes/` - 节点定义目录
- `requirements.txt` - Python 依赖（可选）

### 2.2 目录结构

```
node_packages/
└── my_nodes/                    # 节点包目录
    ├── package.json             # 包元信息（必须）
    ├── requirements.txt         # Python 依赖（可选）
    └── nodes/                   # 节点目录（必须）
        ├── __init__.py          # 导出节点定义
        ├── text_nodes.py        # 文本处理节点
        └── data_nodes.py        # 数据处理节点
```

### 2.3 package.json 格式

```json
{
    "id": "com.example.myNodes",          // 唯一标识（必须）
    "name": "我的节点包",                  // 显示名称（必须）
    "version": "1.0.0",                   // 版本号（必须）
    "author": "Your Name",                // 作者（必须）
    "description": "节点包描述",           // 描述（必须）
    "repository": "https://github.com/...", // Git 仓库地址（推荐）
    "branch": "main",                     // 分支（默认 main）
    "nodes": ["text.join", "text.split"]  // 提供的节点类型列表
}
```

### 2.4 定义节点

#### 节点定义结构

```python
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# 执行函数
def _my_execute(text: str, count: int = 1) -> dict:
    """节点执行逻辑"""
    result = text * count
    return {"output": result}


# 节点定义
my_node = NodeDefinition(
    node_type="my.repeat",           # 节点类型标识（唯一）
    display_name="文本重复",          # 显示名称
    description="将文本重复指定次数",  # 描述（Agent 可用此理解节点功能）
    category="text",                 # 分类
    icon="🔁",                       # 图标（emoji）
    inputs=[                         # 输入端口
        PortDefinition("text", PortType.STRING, "要重复的文本"),
        PortDefinition("count", PortType.INTEGER, "重复次数", default=1, required=False),
    ],
    outputs=[                        # 输出端口
        PortDefinition("output", PortType.STRING, "重复后的文本"),
    ],
    execute=_my_execute,             # 执行函数
)
```

#### 执行函数规范

```python
def execute(**inputs) -> dict:
    """
    节点执行函数
    
    Args:
        **inputs: 输入端口名称到值的映射
        
    Returns:
        输出端口名称到值的映射
        
    Raises:
        Exception: 执行失败时抛出异常
    """
    # inputs 参数名必须与 PortDefinition.name 匹配
    text = inputs["text"]
    count = inputs.get("count", 1)  # 使用 get() 获取可选参数
    
    # 执行逻辑
    result = text * count
    
    # 返回值必须与 output PortDefinition.name 匹配
    return {"output": result}
```

### 2.5 端口类型

#### 预定义类型

| 类型 | 常量 | 说明 | 颜色 |
|------|------|------|------|
| 任意 | `PortType.ANY` | 兼容所有类型 | 灰色 |
| 字符串 | `PortType.STRING` | 文本数据 | 绿色 |
| 整数 | `PortType.INTEGER` | 整数 | 蓝色 |
| 浮点数 | `PortType.FLOAT` | 小数 | 紫色 |
| 布尔值 | `PortType.BOOLEAN` | True/False | 橙色 |
| 数据框 | `PortType.DATAFRAME` | Pandas DataFrame | 红色 |
| 文件 | `PortType.FILE` | 文件路径 | 黄色 |
| 列表 | `PortType.LIST` | 列表 | 青色 |
| 字典 | `PortType.DICT` | 字典 | 粉色 |
| 图片 | `PortType.IMAGE` | 图片数据 | 浅绿 |
| 音频 | `PortType.AUDIO` | 音频数据 | 深紫 |
| 视频 | `PortType.VIDEO` | 视频数据 | 深橙 |

#### 自定义类型

```python
# 使用字符串创建自定义类型
custom_type = PortType("my.custom.type")

# 自定义类型兼容性：只有完全相同的类型才能连接
```

### 2.6 端口定义详解

```python
PortDefinition(
    name="text",                     # 端口名称（必须）
    type=PortType.STRING,            # 端口类型（默认 ANY）
    description="输入文本",           # 描述
    required=True,                   # 是否必需（默认 True）
    default=None,                    # 默认值
    widget_type="line_edit",         # 内联控件类型
    show_preview=False,              # 是否显示预览（仅输出端口）
)
```

#### widget_type 选项

| 控件类型 | 适用类型 | 说明 |
|----------|----------|------|
| `line_edit` | STRING | 单行文本输入 |
| `text_edit` | STRING | 多行文本输入 |
| `spin_box` | INTEGER | 整数输入框 |
| `double_spin_box` | FLOAT | 浮点数输入框 |
| `combo_box` | STRING | 下拉选择框 |
| `check_box` | BOOLEAN | 复选框 |
| `file_picker` | FILE | 文件选择器 |

### 2.7 完整节点包示例

#### package.json

```json
{
    "id": "com.example.textUtils",
    "name": "文本工具集",
    "version": "1.0.0",
    "author": "Developer",
    "description": "常用文本处理工具，包含拼接、分割、替换等节点",
    "repository": "https://github.com/example/text-utils",
    "branch": "main",
    "nodes": ["text.join", "text.split", "text.replace", "text.length"]
}
```

#### nodes/__init__.py

```python
# -*- coding: utf-8 -*-
"""
文本工具节点包

导出所有节点定义
"""

from .text_nodes import (
    text_join,
    text_split,
    text_replace,
    text_length,
)

# 节点定义列表（必须）
node_definitions = [
    text_join,
    text_split,
    text_replace,
    text_length,
]
```

#### nodes/text_nodes.py

```python
# -*- coding: utf-8 -*-
"""
文本处理节点定义
"""

from typing import Dict, Any
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ==================== 文本拼接节点 ====================

def _join_text(text1: str, text2: str, separator: str = " ") -> dict:
    """拼接两个文本"""
    result = f"{text1}{separator}{text2}"
    return {"result": result}


text_join = NodeDefinition(
    node_type="text.join",
    display_name="文本拼接",
    description="将两个文本按指定分隔符拼接",
    category="text",
    icon="🔗",
    inputs=[
        PortDefinition("text1", PortType.STRING, "第一个文本", widget_type="line_edit"),
        PortDefinition("text2", PortType.STRING, "第二个文本", widget_type="line_edit"),
        PortDefinition("separator", PortType.STRING, "分隔符", default=" ", required=False, widget_type="line_edit"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "拼接结果", show_preview=True),
    ],
    execute=_join_text,
)


# ==================== 文本分割节点 ====================

def _split_text(text: str, separator: str = " ") -> dict:
    """按分隔符分割文本"""
    parts = text.split(separator)
    return {
        "parts": parts,
        "count": len(parts),
    }


text_split = NodeDefinition(
    node_type="text.split",
    display_name="文本分割",
    description="按分隔符将文本分割成列表",
    category="text",
    icon="✂️",
    inputs=[
        PortDefinition("text", PortType.STRING, "要分割的文本", widget_type="text_edit"),
        PortDefinition("separator", PortType.STRING, "分隔符", default=" ", required=False, widget_type="line_edit"),
    ],
    outputs=[
        PortDefinition("parts", PortType.LIST, "分割后的列表"),
        PortDefinition("count", PortType.INTEGER, "分割后的数量"),
    ],
    execute=_split_text,
)


# ==================== 文本替换节点 ====================

def _replace_text(text: str, old: str, new: str) -> dict:
    """替换文本中的内容"""
    result = text.replace(old, new)
    count = text.count(old)
    return {
        "result": result,
        "replaced_count": count,
    }


text_replace = NodeDefinition(
    node_type="text.replace",
    display_name="文本替换",
    description="将文本中的指定内容替换为新内容",
    category="text",
    icon="🔄",
    inputs=[
        PortDefinition("text", PortType.STRING, "原始文本", widget_type="text_edit"),
        PortDefinition("old", PortType.STRING, "要替换的内容", widget_type="line_edit"),
        PortDefinition("new", PortType.STRING, "替换为", widget_type="line_edit"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "替换结果", show_preview=True),
        PortDefinition("replaced_count", PortType.INTEGER, "替换次数"),
    ],
    execute=_replace_text,
)


# ==================== 文本长度节点 ====================

def _text_length(text: str) -> dict:
    """计算文本长度"""
    return {
        "length": len(text),
        "char_count": len(text),
        "byte_count": len(text.encode("utf-8")),
    }


text_length = NodeDefinition(
    node_type="text.length",
    display_name="文本长度",
    description="计算文本的字符数和字节数",
    category="text",
    icon="📏",
    inputs=[
        PortDefinition("text", PortType.STRING, "输入文本", widget_type="text_edit"),
    ],
    outputs=[
        PortDefinition("length", PortType.INTEGER, "字符数"),
        PortDefinition("char_count", PortType.INTEGER, "字符计数"),
        PortDefinition("byte_count", PortType.INTEGER, "字节数"),
    ],
    execute=_text_length,
)
```

### 2.8 发布节点包

1. **创建 Git 仓库**

```bash
mkdir my-node-package
cd my-node-package
git init

# 创建目录结构
mkdir nodes
touch package.json
touch requirements.txt  # 可选
touch nodes/__init__.py
touch nodes/my_nodes.py
```

2. **推送到远程仓库**

```bash
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/my-node-package.git
git push -u origin main
```

3. **在平台中安装**

在节点包管理器中输入 Git 仓库 URL，点击安装即可。

---

## 第三部分：API 参考

### 3.1 PluginBase

插件基类，所有插件必须继承此类。

```python
from src.core.plugin_base import PluginBase


class MyPlugin(PluginBase):
    """插件类"""
    
    # ===== 类属性（子类必须覆盖）=====
    
    name: str           # 插件唯一标识（必须）
    version: str        # 插件版本号（必须）
    description: str    # 插件描述（可选）
    author: str         # 作者信息（可选）
    
    # 所需权限集合
    permissions: PermissionSet = PermissionSet.empty()
    
    # ===== 生命周期方法 =====
    
    def on_enable(self, context: "AppContext") -> None:
        """
        插件启用时调用（主生命周期入口）
        
        Args:
            context: 应用上下文，提供程序功能访问
        """
        pass
    
    def on_disable(self) -> None:
        """插件禁用时调用，清理资源"""
        pass
    
    # ===== 类方法 =====
    
    @classmethod
    def get_required_permissions(cls) -> PermissionSet:
        """获取插件所需权限（类方法，加载前检查）"""
        return cls.permissions
    
    @classmethod
    def get_metadata(cls) -> dict:
        """获取插件元数据"""
        return {
            "name": cls.name,
            "version": cls.version,
            "description": cls.description,
            "author": cls.author,
            "permissions": [p.value for p in cls.permissions],
        }
```

### 3.2 Permission / PermissionSet

#### Permission 枚举

```python
from src.core.permission_manager import Permission


class Permission(Enum):
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
```

#### PermissionSet 类

```python
from src.core.permission_manager import PermissionSet


# 从列表创建
permissions = PermissionSet.from_list([
    Permission.FILE_READ,
    Permission.EVENT_SUBSCRIBE,
])

# 也可以使用字符串
permissions = PermissionSet.from_list([
    "file.read",
    "event.subscribe",
])

# 创建空权限集合
empty = PermissionSet.empty()

# 检查权限
permissions.has(Permission.FILE_READ)      # True
permissions.has(Permission.FILE_WRITE)     # False

# 检查多个权限
permissions.has_all({Permission.FILE_READ, Permission.EVENT_SUBSCRIBE})  # True

# 权限集合运算
other = PermissionSet.from_list([Permission.FILE_WRITE])
combined = permissions | other   # 并集
common = permissions & other     # 交集
diff = permissions - other       # 差集
```

### 3.3 NodeDefinition

节点定义类，定义节点的输入输出和执行逻辑。

```python
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


@dataclass
class NodeDefinition:
    """节点定义"""
    
    # ===== 元数据 =====
    
    node_type: str          # 节点类型标识（唯一）
    display_name: str       # 显示名称
    description: str = ""   # 描述（Agent可用此理解节点功能）
    category: str = "general"  # 分类
    icon: str = "🔧"        # 图标（emoji）
    
    # ===== 端口定义 =====
    
    inputs: List[PortDefinition] = field(default_factory=list)
    outputs: List[PortDefinition] = field(default_factory=list)
    
    # ===== 执行函数 =====
    
    execute: Optional[Callable[..., Dict[str, Any]]] = field(default=None)
    
    # ===== 方法 =====
    
    def get_input_port(self, name: str) -> Optional[PortDefinition]:
        """获取指定名称的输入端口"""
        pass
    
    def get_output_port(self, name: str) -> Optional[PortDefinition]:
        """获取指定名称的输出端口"""
        pass
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> List[str]:
        """验证输入值，返回错误消息列表"""
        pass
    
    def get_default_inputs(self) -> Dict[str, Any]:
        """获取所有输入端口的默认值"""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化和Agent理解）"""
        pass
```

### 3.4 PortDefinition

端口定义类，定义节点的输入输出端口。

```python
@dataclass
class PortDefinition:
    """端口定义"""
    
    name: str                       # 端口名称
    type: PortType = PortType.ANY   # 端口类型
    description: str = ""           # 描述
    required: bool = True           # 是否必需
    default: Any = None             # 默认值
    widget_type: str = ""           # 内联控件类型
    show_preview: bool = False      # 是否显示预览（仅输出端口）
```

### 3.5 PortType

端口数据类型。

```python
class PortType:
    """端口数据类型"""
    
    # 预定义类型
    ANY = "any"
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    DATAFRAME = "dataframe"
    FILE = "file"
    LIST = "list"
    DICT = "dict"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    
    def __init__(self, value: str = "any"):
        """初始化端口类型"""
        pass
    
    @property
    def value(self) -> str:
        """获取类型值"""
        pass
    
    @property
    def color(self) -> str:
        """获取端口类型的显示颜色"""
        pass
    
    def is_compatible_with(self, other: "PortType") -> bool:
        """
        检查类型兼容性
        
        两个端口可以连接的条件：
        1. 任一端口类型为 ANY
        2. 两个端口类型完全相同
        """
        pass
```

### 3.6 AppContext 接口

应用上下文，暴露给插件使用的程序功能。

```python
class AppContext:
    """应用上下文"""
    
    # ===== 核心组件 =====
    
    event_bus: EventBus           # 事件总线
    plugin_manager: PluginManager # 插件管理器
    node_engine: NodeEngine       # 节点引擎
    storage: StorageService       # 存储服务
    
    # ===== AgentScope 管理接口 =====
    
    agent: AgentScopeInterface    # Agent 管理接口
    
    # ===== 权限检查 =====
    
    def check_permission(self, permission: Permission) -> bool:
        """检查当前插件是否拥有指定权限"""
        pass
    
    def require_permission(self, permission: Permission) -> None:
        """要求权限，无权限时抛出 PermissionDeniedError"""
        pass
```

---

## 第四部分：最佳实践

### 4.1 插件最佳实践

1. **遵循最低权限原则**
   - 只声明真正需要的权限
   - 不要为了方便而请求所有权限

2. **正确处理生命周期**
   ```python
   def on_enable(self, context):
       # 保存 context 引用
       self._context = context
       # 注册资源
       self._subscription_id = context.event_bus.subscribe(...)
   
   def on_disable(self):
       # 清理注册的资源
       if self._subscription_id:
           self._context.event_bus.unsubscribe(self._subscription_id)
   ```

3. **使用日志记录**
   ```python
   from src.utils.logger import get_logger
   
   _logger = get_logger(__name__)
   
   def on_enable(self, context):
       _logger.info(f"[{self.name}] 插件已启用")
   ```

4. **异常处理**
   ```python
   def _my_handler(self, event_data):
       try:
           # 处理逻辑
           pass
       except Exception as e:
           _logger.error(f"[{self.name}] 处理事件失败: {e}", exc_info=True)
   ```

### 4.2 节点包最佳实践

1. **命名规范**
   - 节点类型：`category.action`（如 `text.join`、`data.filter`）
   - 显示名称：简洁明了的中文

2. **描述清晰**
   ```python
   NodeDefinition(
       node_type="text.join",
       display_name="文本拼接",
       description="将两个文本按指定分隔符拼接，支持自定义分隔符",
       ...
   )
   ```

3. **合理的默认值**
   ```python
   PortDefinition(
       "separator",
       PortType.STRING,
       "分隔符",
       default=" ",           # 合理的默认值
       required=False,        # 可选参数
   )
   ```

4. **输入验证**
   ```python
   def _my_execute(text: str, count: int) -> dict:
       if count < 0:
           raise ValueError("count 必须为非负数")
       if not text:
           return {"result": ""}
       return {"result": text * count}
   ```

### 4.3 错误处理

1. **节点执行错误**
   ```python
   def _execute(**inputs) -> dict:
       try:
           # 执行逻辑
           result = process(inputs["data"])
           return {"result": result}
       except FileNotFoundError as e:
           raise FileNotFoundError(f"文件不存在: {e.filename}")
       except Exception as e:
           raise RuntimeError(f"执行失败: {e}")
   ```

2. **插件权限错误**
   ```python
   def on_enable(self, context):
       try:
           context.agent.register_tool(...)
       except PermissionDeniedError as e:
           _logger.error(f"权限不足: {e}")
           raise
   ```

---

## 第五部分：常见问题

### 5.1 插件常见问题

**Q: 插件没有被加载？**

A: 检查以下几点：
1. 插件目录是否在 `plugins/` 下
2. 是否有 `__init__.py` 文件
3. 是否定义了 `plugin_class` 变量
4. 类名是否继承自 `PluginBase`

**Q: 权限被拒绝？**

A: 确保插件正确声明了所需权限：
```python
permissions = PermissionSet.from_list([
    Permission.FILE_READ,  # 不是 "file.read" 字符串
])
```

**Q: 如何访问 AppContext？**

A: 在 `on_enable` 方法中保存 context 引用：
```python
def on_enable(self, context):
    self._context = context
    # 后续使用 self._context
```

### 5.2 节点包常见问题

**Q: 节点不显示在节点面板中？**

A: 检查以下几点：
1. `nodes/__init__.py` 是否导出了 `node_definitions` 列表
2. 节点包是否已启用
3. `node_definitions` 列表中的节点定义是否正确

**Q: 端口类型不匹配？**

A: 检查连接的端口类型：
- `ANY` 类型可以连接任何类型
- 其他类型必须完全匹配才能连接

**Q: 节点执行失败？**

A: 检查：
1. 执行函数的参数名是否与输入端口名称匹配
2. 返回值的键名是否与输出端口名称匹配
3. 是否有必需的输入没有提供值

```python
# 正确的参数名匹配
inputs=[PortDefinition("text", ...)]  # 端口名是 "text"
def _execute(text: str): ...          # 参数名也是 "text"

# 正确的返回值匹配
outputs=[PortDefinition("result", ...)]  # 端口名是 "result"
return {"result": ...}                   # 返回键名也是 "result"
```

---

## 更多资源

- [架构设计文档](ARCHITECTURE.md) - 详细的系统架构说明
- [AgentScope 文档](https://github.com/alibaba/AgentScope) - AI Agent 框架
