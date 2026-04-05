# 插件与节点开发指南

本文档介绍如何为 OfficeFlow 开发自定义节点包和插件。

---

## 目录

- [概述](#概述)
- [第一部分：节点包开发](#第一部分节点包开发)
- [第二部分：流程控制节点](#第二部分流程控制节点)
- [第三部分：插件开发](#第三部分插件开发)
- [第四部分：API 参考](#第四部分api-参考)

---

## 概述

### 节点包 vs 插件

| 特性 | 节点包 (Node Package) | 插件 (Plugin) |
|------|----------------------|---------------|
| **用途** | 在工作流中添加新节点类型 | 扩展程序本身的能力 |
| **入口** | `NodeDefinition` 定义 | `PluginBase` 子类 |
| **通信** | 节点执行函数 | 事件系统、Agent API |
| **权限** | 无需声明 | 需显式声明 |
| **目录** | `node_packages/` | `plugins/` |
| **分发** | Git 仓库 | 本地安装 |

---

## 第一部分：节点包开发

### 1.1 目录结构

每个节点包必须遵循以下结构：

```
node_packages/
└── my-package/
    ├── package.json       # 包元信息（必须）
    ├── requirements.txt   # Python 依赖（可选）
    └── nodes/
        ├── __init__.py    # 导出所有 NodeDefinition 实例
        └── my_nodes.py    # 节点实现
```

### 1.2 package.json

```json
{
    "id": "com.example.myPackage",
    "name": "我的节点包",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "节点包功能描述",
    "repository": "https://github.com/...",
    "branch": "main",
    "nodes": ["my.node1", "my.node2"]
}
```

| 字段 | 必须 | 说明 |
|------|------|------|
| `id` | 是 | 唯一标识，推荐反向域名格式 |
| `name` | 是 | 显示名称 |
| `version` | 是 | 语义化版本号 |
| `author` | 是 | 作者 |
| `description` | 是 | 功能描述 |
| `repository` | 否 | Git 仓库地址（用于远程安装） |
| `branch` | 否 | Git 分支，默认 `main` |
| `nodes` | 是 | 提供的节点类型列表 |

### 1.3 定义节点

一个节点由三部分组成：**元数据**、**端口定义**、**执行函数**。

```python
# -*- coding: utf-8 -*-
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


# ---------- 执行函数 ----------
# 参数名必须与 inputs 中的 PortDefinition.name 一一对应
# 返回字典的键名必须与 outputs 中的 PortDefinition.name 一一对应
def _text_repeat(text: str, count: int = 1) -> dict:
    if count < 0:
        raise ValueError("count 必须为非负数")
    result = text * count
    return {
        "result": result,
        "length": len(result),
    }


# ---------- 节点定义 ----------
text_repeat = NodeDefinition(
    node_type="text.repeat",          # 唯一类型标识
    display_name="文本重复",           # UI 显示名
    description="将文本重复指定次数",   # AI 可读描述
    category="text",                  # 面板分类
    icon="🔁",                        # 图标（emoji）
    inputs=[
        PortDefinition("text", PortType.STRING, "要重复的文本"),
        PortDefinition("count", PortType.INTEGER, "重复次数",
                        default=1, required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "重复结果", show_preview=True),
        PortDefinition("length", PortType.INTEGER, "结果长度"),
    ],
    execute=_text_repeat,
)
```

### 1.4 导出节点

在 `nodes/__init__.py` 中导出所有节点定义：

```python
# -*- coding: utf-8 -*-
from .my_nodes import text_repeat, text_join

# 导出所有 NodeDefinition 实例
__all__ = ["text_repeat", "text_join"]
```

系统会自动扫描模块中所有 `NodeDefinition` 实例并注册。

### 1.5 端口类型

#### 预定义类型

| 类型 | 常量 | 颜色 |
|------|------|------|
| 任意 | `PortType.ANY` | 灰色 |
| 字符串 | `PortType.STRING` | 绿色 |
| 整数 | `PortType.INTEGER` | 蓝色 |
| 浮点数 | `PortType.FLOAT` | 紫色 |
| 布尔值 | `PortType.BOOLEAN` | 橙色 |
| 数据表 | `PortType.DATAFRAME` | 红色 |
| 文件 | `PortType.FILE` | 黄色 |
| 列表 | `PortType.LIST` | 青色 |
| 字典 | `PortType.DICT` | 粉色 |
| 图像 | `PortType.IMAGE` | 浅绿 |
| 音频 | `PortType.AUDIO` | 深紫 |
| 视频 | `PortType.VIDEO` | 深橙 |

#### 自定义类型

```python
# 自定义类型会根据类型字符串自动生成一致的颜色（基于哈希）
my_type = PortType("my.custom.type")
```

**类型兼容规则：**
- `ANY` 可与任何类型连接
- 相同类型可连接
- 不同类型不可连接（除非其中一个是 `ANY`）

### 1.6 端口定义参数

```python
PortDefinition(
    name="text",                     # 端口名称（必须）
    type=PortType.STRING,            # 数据类型，默认 ANY
    description="输入文本",           # 描述
    required=True,                   # 是否必需，默认 True
    default=None,                    # 默认值
    widget_type="line_edit",         # 内联控件类型（仅输入端口）
    show_preview=False,              # 是否显示输出预览（仅输出端口）
    role=None,                       # 端口角色（流程控制用）
)
```

#### widget_type 可选值

| 控件类型 | 适用类型 | 说明 |
|----------|----------|------|
| `"line_edit"` | STRING | 单行文本 |
| `"text_edit"` | STRING | 多行文本 |
| `"spin_box"` | INTEGER | 整数输入 |
| `"double_spin_box"` | FLOAT | 浮点数输入 |
| `"check_box"` | BOOLEAN | 复选框 |
| `"file_picker"` | FILE | 文件选择器 |

#### 输入优先级

当输入端口同时有连接和内联控件时，系统按以下优先级取值：

```
连接值 > 控件值 (widget_values) > 默认值 (default) > None
```

连接建立时控件自动锁定（禁用），断开连接时自动解锁。

### 1.7 执行函数规范

```python
def execute(**inputs) -> dict:
    """
    Args:
        **inputs: 输入端口名 → 值的映射。参数名必须与 PortDefinition.name 匹配。

    Returns:
        dict: 输出端口名 → 值的映射。键名必须与 PortDefinition.name 匹配。

    Raises:
        Exception: 执行失败时抛出异常，引擎会捕获并标记节点为 ERROR。
    """
```

要点：
- **必需参数**直接用位置参数或关键字参数接收
- **可选参数**（`required=False`）如果没有值会传入 `None`
- **返回值**的键必须与 `outputs` 端口名完全匹配
- 抛出异常会被引擎捕获，节点状态变为 `ERROR`

### 1.8 完整示例

以下是一个功能完整的节点包：

**package.json**

```json
{
    "id": "com.example.textUtils",
    "name": "文本工具集",
    "version": "1.0.0",
    "author": "Developer",
    "description": "文本处理工具：拼接、分割、替换、长度计算",
    "nodes": ["text.join", "text.split", "text.replace", "text.length"]
}
```

**nodes/text_nodes.py**

```python
# -*- coding: utf-8 -*-
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


def _join_text(text1: str, text2: str, separator: str = " ") -> dict:
    return {"result": f"{text1}{separator}{text2}"}


text_join = NodeDefinition(
    node_type="text.join",
    display_name="文本拼接",
    description="将两个文本按分隔符拼接",
    category="text",
    icon="🔗",
    inputs=[
        PortDefinition("text1", PortType.STRING, "第一个文本"),
        PortDefinition("text2", PortType.STRING, "第二个文本"),
        PortDefinition("separator", PortType.STRING, "分隔符",
                        default=" ", required=False),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "拼接结果", show_preview=True),
    ],
    execute=_join_text,
)


def _split_text(text: str, separator: str = " ") -> dict:
    parts = text.split(separator)
    return {"parts": parts, "count": len(parts)}


text_split = NodeDefinition(
    node_type="text.split",
    display_name="文本分割",
    description="按分隔符分割文本为列表",
    category="text",
    icon="✂️",
    inputs=[
        PortDefinition("text", PortType.STRING, "要分割的文本"),
        PortDefinition("separator", PortType.STRING, "分隔符",
                        default=" ", required=False),
    ],
    outputs=[
        PortDefinition("parts", PortType.LIST, "分割结果"),
        PortDefinition("count", PortType.INTEGER, "分割数量"),
    ],
    execute=_split_text,
)


def _replace_text(text: str, old: str, new: str) -> dict:
    result = text.replace(old, new)
    return {"result": result, "replaced_count": text.count(old)}


text_replace = NodeDefinition(
    node_type="text.replace",
    display_name="文本替换",
    description="替换文本中的指定内容",
    category="text",
    icon="🔄",
    inputs=[
        PortDefinition("text", PortType.STRING, "原始文本"),
        PortDefinition("old", PortType.STRING, "要替换的内容"),
        PortDefinition("new", PortType.STRING, "替换为"),
    ],
    outputs=[
        PortDefinition("result", PortType.STRING, "替换结果", show_preview=True),
        PortDefinition("replaced_count", PortType.INTEGER, "替换次数"),
    ],
    execute=_replace_text,
)


def _text_length(text: str) -> dict:
    return {
        "length": len(text),
        "byte_count": len(text.encode("utf-8")),
    }


text_length = NodeDefinition(
    node_type="text.length",
    display_name="文本长度",
    description="计算文本字符数和字节数",
    category="text",
    icon="📏",
    inputs=[
        PortDefinition("text", PortType.STRING, "输入文本"),
    ],
    outputs=[
        PortDefinition("length", PortType.INTEGER, "字符数"),
        PortDefinition("byte_count", PortType.INTEGER, "字节数"),
    ],
    execute=_text_length,
)
```

**nodes/__init__.py**

```python
# -*- coding: utf-8 -*-
from .text_nodes import text_join, text_split, text_replace, text_length

__all__ = ["text_join", "text_split", "text_replace", "text_length"]
```

### 1.9 发布节点包

将节点包推送到 Git 仓库后，用户可在节点包管理器中输入仓库 URL 安装。

```bash
mkdir my-node-package && cd my-node-package
git init
mkdir nodes
# 创建 package.json、nodes/__init__.py、nodes/my_nodes.py
git add . && git commit -m "Initial commit"
git remote add origin https://github.com/you/my-node-package.git
git push -u origin main
```

---

## 第二部分：流程控制节点

引擎原生支持**分支**和**循环**，通过特殊的端口角色（`role`）实现。

### 2.1 条件分支（flow.condition）

条件节点的输出端口有特殊角色标记：

```python
outputs=[
    PortDefinition("true_out", PortType.ANY, "True 分支", role="branch_true"),
    PortDefinition("false_out", PortType.ANY, "False 分支", role="branch_false"),
    PortDefinition("result", PortType.BOOLEAN, "条件值"),
]
```

- 当 `condition=True` 时：`true_out` 输出值，`false_out` 输出 `None`
- 当 `condition=False` 时：`false_out` 输出值，`true_out` 输出 `None`
- 引擎自动跳过非活跃分支的所有下游节点

### 2.2 循环（回边连接）

循环通过**回边连接**（back edge）实现。在连接上标记 `is_back_edge: true`：

```json
{
    "id": "conn-feedback",
    "source_node": "node-condition",
    "source_port": "true_out",
    "target_node": "node-start",
    "target_port": "value",
    "is_back_edge": true
}
```

**回边的作用：**
- 当源节点执行完成且该输出端口有值（活跃分支）时，重置目标节点状态并入队重新执行
- 如果该端口输出 `None`（非活跃分支），回边不触发，循环退出

**示例流程（累加计数器）：**

```
[输入: counter=0] → [加法: counter+step] → [比较: counter < limit]
                                              ↓
                                        [条件判断] ──→ false_out → [预览结果]
                                              ↓
                                         true_out（回边）→ [输入: counter]
```

每轮循环：加法节点将 `counter + step`，条件节点判断是否继续。当 `counter >= limit` 时走 `false_out` 退出。

### 2.3 分支合并（flow.merge）

用于将两条分支汇合：

```python
inputs=[
    PortDefinition("true_in", PortType.ANY, "True 分支数据", required=False),
    PortDefinition("false_in", PortType.ANY, "False 分支数据", required=False),
]
```

输出非 `None` 的那个输入值。

### 2.4 引擎执行流程

```
1. 发现入口节点（优先 flow.start，否则无入边节点）
2. 动态步进循环：
   a. 从队列取出所有输入就绪的节点 → 并行执行
   b. 每个节点完成后：
      - 普通连接 → 目标入队
      - 回边连接 → 重置目标状态并入队
      - 分支连接 → 只入队活跃分支下游，非活跃分支标记 SKIPPED
   c. 超过最大迭代次数（1000）则报错退出
3. 标记未执行节点为 SKIPPED
```

---

## 第三部分：插件开发

### 3.1 插件结构

```
plugins/
└── my_plugin/
    └── __init__.py    # 插件入口
```

### 3.2 最小插件

```python
# plugins/my_plugin/__init__.py
# -*- coding: utf-8 -*-
from src.core.plugin_base import PluginBase
from src.core.permission_manager import Permission, PermissionSet


class MyPlugin(PluginBase):
    name = "my_plugin"
    version = "1.0.0"
    description = "我的插件"
    author = "Author"

    permissions = PermissionSet.from_list([
        Permission.EVENT_SUBSCRIBE,
    ])

    def on_enable(self, context):
        self._context = context
        context.event_bus.subscribe("node.executed", self._on_node_done)

    def on_disable(self):
        pass

    def _on_node_done(self, data):
        print(f"节点完成: {data.get('node_type')}")


# 必须导出 plugin_class
plugin_class = MyPlugin
```

### 3.3 生命周期

```
发现 → 权限检查 → [用户确认] → on_enable(context) → 活跃 → on_disable()
```

### 3.4 权限

插件必须显式声明所需权限：

| 权限 | 说明 |
|------|------|
| `FILE_READ` / `FILE_WRITE` | 文件读写 |
| `NETWORK` | 网络访问 |
| `AGENT_TOOL` | 注册 Agent 工具 |
| `AGENT_MCP` | 配置 MCP 服务 |
| `AGENT_SKILL` | 加载 Skill |
| `AGENT_CHAT` | 调用 Agent 对话 |
| `EVENT_SUBSCRIBE` / `EVENT_PUBLISH` | 事件订阅/发布 |
| `NODE_READ` / `NODE_REGISTER` | 节点读取/注册 |
| `STORAGE_READ` / `STORAGE_WRITE` | 存储读写 |

```python
permissions = PermissionSet.from_list([
    Permission.EVENT_SUBSCRIBE,
    Permission.AGENT_TOOL,
])
```

### 3.5 事件类型

| 事件 | 说明 |
|------|------|
| `PLUGIN_LOADED` / `PLUGIN_UNLOADED` | 插件加载/卸载 |
| `NODE_REGISTERED` / `NODE_UNREGISTERED` | 节点注册/注销 |
| `NODE_STARTED` / `NODE_EXECUTED` | 节点开始/完成执行 |
| `WORKFLOW_STARTED` / `WORKFLOW_COMPLETED` | 工作流开始/完成 |
| `WORKFLOW_SAVED` / `WORKFLOW_LOADED` | 工作流保存/加载 |
| `AGENT_MESSAGE` / `AGENT_TOOL_CALLED` | Agent 消息/工具调用 |
| `PACKAGE_INSTALLED` / `PACKAGE_UPDATED` / `PACKAGE_REMOVED` | 节点包管理 |
| `PACKAGE_ENABLED` / `PACKAGE_DISABLED` | 节点包启用/禁用 |

### 3.6 完整插件示例

```python
# plugins/workflow_logger/__init__.py
# -*- coding: utf-8 -*-
from datetime import datetime
from src.core.plugin_base import PluginBase
from src.core.permission_manager import Permission, PermissionSet


class WorkflowLoggerPlugin(PluginBase):
    name = "workflow_logger"
    version = "1.0.0"
    description = "记录工作流执行历史"
    author = "OfficeTools"

    permissions = PermissionSet.from_list([
        Permission.EVENT_SUBSCRIBE,
        Permission.AGENT_TOOL,
        Permission.STORAGE_WRITE,
        Permission.STORAGE_READ,
    ])

    _history: list = []

    def on_enable(self, context):
        self._context = context
        context.event_bus.subscribe("node.executed", self._on_node_executed)
        context.event_bus.subscribe("workflow.completed", self._on_workflow_done)

        context.agent.register_tool(
            name="get_execution_history",
            description="获取节点执行历史",
            func=self._get_history,
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "最大记录数"}
                }
            },
        )

    def on_disable(self):
        self._history.clear()

    def _on_node_executed(self, data):
        self._history.append({
            "time": datetime.now().isoformat(),
            "node_type": data.get("node_type"),
            "success": data.get("success", False),
        })
        if len(self._history) > 1000:
            self._history = self._history[-500:]

    def _on_workflow_done(self, data):
        success = data.get("success", False)
        total = sum(1 for r in self._history if r.get("success"))
        print(f"工作流完成: {total} 个节点成功")

    def _get_history(self, limit: int = 10) -> dict:
        return {"records": self._history[-limit:]}


plugin_class = WorkflowLoggerPlugin
```

---

## 第四部分：API 参考

### NodeDefinition

```python
@dataclass
class NodeDefinition:
    node_type: str                          # 唯一类型标识
    display_name: str                       # 显示名称
    description: str = ""                   # 描述（AI 可读）
    category: str = "general"              # 分类
    icon: str = "🔧"                        # 图标

    inputs: List[PortDefinition] = []       # 输入端口列表
    outputs: List[PortDefinition] = []      # 输出端口列表

    execute: Optional[Callable] = None      # 执行函数

    # 方法
    def get_input_port(name) -> Optional[PortDefinition]
    def get_output_port(name) -> Optional[PortDefinition]
    def validate_inputs(inputs) -> List[str]    # 返回错误列表
    def get_default_inputs() -> Dict[str, Any]
    def to_dict() -> Dict[str, Any]             # 序列化
```

### PortDefinition

```python
@dataclass
class PortDefinition:
    name: str                               # 端口名称
    type: PortType = PortType.ANY           # 数据类型
    description: str = ""                   # 描述
    required: bool = True                   # 是否必需
    default: Any = None                     # 默认值
    widget_type: Optional[str] = None       # 内联控件类型
    show_preview: bool = False              # 显示输出预览
    role: Optional[str] = None              # 端口角色
    # role 取值: "branch_true", "branch_false", "feedback", None
```

### PortType

```python
class PortType:
    # 预定义类型（类属性）
    ANY, STRING, INTEGER, FLOAT, BOOLEAN,
    DATAFRAME, FILE, LIST, DICT,
    IMAGE, AUDIO, VIDEO

    def __init__(value: str = "any")        # 也支持自定义字符串
    @property value -> str                  # 类型字符串
    @property color -> str                  # 显示颜色（十六进制）
    @property display_name -> str           # 友好名称
    def is_compatible_with(other) -> bool   # 类型兼容检查
```

### PluginBase

```python
class PluginBase(ABC):
    name: str                               # 插件标识
    version: str                            # 版本号
    description: str                        # 描述
    author: str                             # 作者
    permissions: PermissionSet              # 所需权限

    def on_enable(context: AppContext)       # 启用回调
    def on_disable()                        # 禁用回调
```

### Permission / PermissionSet

```python
class Permission(Enum):
    FILE_READ, FILE_WRITE, NETWORK,
    AGENT_TOOL, AGENT_MCP, AGENT_SKILL, AGENT_CHAT,
    EVENT_SUBSCRIBE, EVENT_PUBLISH,
    NODE_READ, NODE_REGISTER,
    STORAGE_READ, STORAGE_WRITE

class PermissionSet:
    @classmethod from_list(perms) -> PermissionSet
    def has(permission) -> bool
    def has_all({permissions}) -> bool
    def __or__ / __and__ / __sub__          # 集合运算
```

---

## 常见问题

**Q: 节点不显示在面板中？**

检查：`nodes/__init__.py` 是否导出了 `NodeDefinition` 实例；节点包是否启用。

**Q: 节点执行失败？**

检查：执行函数参数名是否与输入端口名一致；返回值键名是否与输出端口名一致。

```python
# 错误：参数名不匹配
inputs=[PortDefinition("text", ...)]     # 端口名 "text"
def _execute(input_text: str): ...       # 参数名 "input_text" ✗

# 正确
inputs=[PortDefinition("text", ...)]
def _execute(text: str): ...             # 参数名 "text" ✓
```

**Q: 插件没有被加载？**

检查：是否在 `plugins/` 目录下；`__init__.py` 是否定义了 `plugin_class`；类是否继承 `PluginBase`。

**Q: 如何创建循环工作流？**

在连接 JSON 中设置 `"is_back_edge": true`，将条件节点的活跃分支输出口连回循环体的起始节点。参见 `examples/03_loop_back_edge.json`。

**Q: 自定义类型怎么显示颜色？**

自定义类型自动通过 MD5 哈希生成一致的颜色，无需手动配置。相同类型字符串始终显示相同颜色。
