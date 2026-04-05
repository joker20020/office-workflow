# OfficeFlow

基于 PySide6 的桌面办公自动化平台，通过可视化节点编辑器构建工作流，配合 AI 助手让办公自动化变得简单直观。

## 功能特性

- **可视化节点编辑器** — 拖拽节点、连线即可创建工作流，支持分支、循环、并行执行
- **节点包管理** — 内置 70+ 节点，支持从 Git 仓库安装第三方节点包
- **AI 助手** — 对话式工作流设计，AI 读取节点列表辅助构建流程
- **插件系统** — 通过事件总线扩展程序功能，支持权限管理
- **本地存储** — SQLite 持久化，数据不出本机

## 内置节点包

| 节点包 | 节点数 | 说明 |
|--------|--------|------|
| **数学工具** | 37 | 四则运算、比较、三角函数、聚合、随机数等 |
| **数据助手** | 18 | 数据输入（字符串/数字/布尔/列表/字典/文件）、类型转换、列表/字典操作 |
| **预览工具** | 10 | 文本/数字/图片/音频/视频/列表/字典/文件/数据表预览 |
| **Excel 工具** | 2 | Excel 文件对比与预览 |
| **流程控制** | 2 | 条件分支（True/False）与分支合并 |

## 工作流能力

```
线性链：  A → B → C → 结果
分支：    A → [条件] → True 分支 → D
                    → False 分支 → E
循环：    A → [条件] → True → 回到 A（累加计数器等）
并行：    A → B ┐
                ├→ D（B、C 并行执行后汇合）
           A → C ┘
```

## 技术栈

| 层次 | 技术 |
|------|------|
| UI | PySide6 (Qt 6) |
| 节点画布 | QGraphicsView / QGraphicsScene |
| AI | AgentScope |
| 存储 | SQLite + SQLAlchemy |
| 包管理 | GitPython |
| 构建工具 | uv + hatchling |

## 快速开始

### 环境要求

- Python 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装与运行

```bash
git clone <repository-url>
cd office

# 安装依赖
uv sync

# 启动应用
uv run office
```

### 基本使用

**节点编辑器：**
1. 从左侧节点面板拖拽节点到画布
2. 从输出端口拖线到输入端口，建立数据连接
3. 在节点内联控件中输入参数值（有连接时控件自动锁定）
4. 点击运行按钮执行工作流
5. Ctrl+S 保存工作流

**AI 对话：**
- 切换到 AI 对话页面，用自然语言描述需求
- AI 读取已注册节点列表，辅助设计和推荐工作流

**节点包管理：**
- 在节点包管理页面输入 Git 仓库地址安装新节点包
- 支持更新、启用/禁用、删除操作

## 项目结构

```
office/
├── src/
│   ├── core/               # 核心模块
│   │   ├── app_context.py   # 应用上下文（中枢）
│   │   ├── event_bus.py     # 事件总线（发布/订阅）
│   │   ├── plugin_base.py   # 插件基类
│   │   ├── plugin_manager.py# 插件管理器
│   │   └── permission_manager.py # 权限系统
│   ├── engine/              # 节点引擎
│   │   ├── definitions.py   # NodeDefinition / PortDefinition / PortType
│   │   ├── node_engine.py   # 执行引擎（注册、执行、分支、循环）
│   │   ├── node_graph.py    # 图数据结构（Node / Connection / NodeGraph）
│   │   └── serialization.py # 工作流 JSON 序列化
│   ├── ui/                  # 用户界面
│   │   ├── main_window.py   # 主窗口
│   │   ├── navigation_rail.py # 侧边导航
│   │   ├── node_editor/     # 节点编辑器
│   │   │   ├── scene.py     #   场景管理
│   │   │   ├── view.py      #   视图交互
│   │   │   ├── node_item.py #   节点图元
│   │   │   ├── port_item.py #   端口图元
│   │   │   ├── connection_item.py # 连接图元
│   │   │   ├── panel.py     #   节点面板
│   │   │   └── widgets.py   #   内联控件
│   │   ├── chat/            # AI 对话
│   │   ├── packages/        # 节点包管理
│   │   ├── plugins/         # 插件管理
│   │   └── settings/        # 设置
│   ├── agent/               # AI Agent 集成
│   │   ├── agent_integration.py # AgentScope 集成
│   │   └── workflow_tools.py    # 工作流操作工具
│   ├── nodes/               # 节点包管理
│   │   ├── package_manager.py    # 节点包生命周期
│   │   └── package_loader.py     # 动态加载
│   └── storage/             # 数据持久化
│       ├── database.py      # SQLite 连接
│       └── models.py        # 数据模型
├── node_packages/           # 内置节点包
├── plugins/                 # 内置插件
├── examples/                # 示例工作流
├── workflows/               # 用户工作流
├── tests/                   # 测试
└── docs/                    # 文档
```

## 文档

- [插件与节点开发指南](DEVELOPMENT.md) — 如何创建自定义节点包和插件

## 许可证

MIT License
