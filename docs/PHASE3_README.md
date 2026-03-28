# Phase 3: Agent集成

## 概述

Phase 3 实现了AI助手功能,集成AgentScope框架,允许用户通过自然语言对话来设计和操作节点工作流。

## 已实现的功能

### 1. 核心组件

- **ApiKeyManager** (`src/agent/api_key_manager.py`)
  - API密钥加密存储和管理
  - 增删改查API密钥
  - 匉provider分类管理密钥

- **NodeFormatter** (`src/agent/node_formatter.py`)
  - 节点定义格式化为Agent可读文本
  - 生成Agent系统提示词
  - 格式化单个/所有节点信息

- **ChatHistory** (`src/agent/chat_history.py`)
  - 对话历史管理(内存存储)
  - 支持最大消息数限制
  - 线程安全

- **WorkflowTools** (`src/agent/workflow_tools.py`)
  - Agent操作节点编辑器的工具集
  - 节点管理工具(create/delete/list)
  - 连接管理工具(connect/disconnect)
  - 工作流操作工具(execute/clear)
  - 节点配置工具(set_node_value)

- **AgentIntegration** (`src/agent/agent_integration.py`)
  - AgentScope框架集成层
  - ReActAgent生命周期管理
  - 工具注册和配置
  - 对话处理

### 2. UI组件

- **ChatPanel** (`src/ui/chat/chat_panel.py`)
  - 对话UI面板
  - 消息显示区域
  - 输入框和发送按钮
  - Agent状态显示
  - 与AgentIntegration集成

- **MessageWidget** (`src/ui/chat/chat_widget.py`)
  - 单条消息显示组件
  - 支持user/assistant角色
  - 自动换行和样式

- **ChatStyle** (`src/ui/chat/chat_style.py`)
  - 对话UI样式定义
  - 暗色主题适配

### 3. 集成

- **MainWindow集成** (`src/ui/main_window.py`)
  - 替换Agent占位页面为ChatPanel
  - 连接ChatPanel和 NodeEditorPanel
  - 集成AgentIntegration

## 特殊设计决策

1. **不使用数据库管理工作流**
   - 工作流完全在内存中管理
   - Agent通过工具直接操作NodeGraph
   - 简化架构,提高响应速度

2. **Agent通过工具操作节点编辑器**
   - Agent不直接管理持久化
   - 所有操作通过WorkflowTools
   - 清晰的职责分离

3. **中文注释**
   - 所有公共API包含中文注释
   - 复杂逻辑有详细说明
   - 示例代码帮助理解

## 使用方式

### 1. 配置API密钥

```python
from src.agent import ApiKeyManager

manager = ApiKeyManager()
manager.store_key("dashscope", "your-api-key")
```

### 2. 使用Agent

```python
from src.agent import AgentIntegration
from src.engine import NodeEngine

engine = NodeEngine()
agent = AgentIntegration(manager, engine)
agent.initialize("dashscope")

response = agent.chat("帮我创建一个文本处理工作流")
print(response)
```

### 3. 在UI中使用

```python
from src.ui.chat import ChatPanel

chat_panel = ChatPanel(agent)
chat_panel.show()  # 显示对话面板
```

## 测试

所有测试文件位于 `tests/` 目录:
- `test_api_key_manager.py` - API密钥管理器测试
- `test_node_formatter.py` - 节点格式化器测试
- `test_end_to_end.py` - 端到端集成测试

运行测试:
```bash
uv run pytest tests/test_api_key_manager.py -v
uv run pytest tests/test_node_formatter.py -v
uv run pytest tests/test_end_to_end.py -v
```

## 依赖

- **AgentScope** >=1.0.17 - AI Agent框架
- **PySide6** >=6.6.0 - UI框架
- **cryptography** >=41.0 - 加密工具
- **SQLAlchemy** >=2.0 - ORM

## 下一步

Phase 4将实现:
- 插件系统完善
- 权限管理
- 节点包管理
