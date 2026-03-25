# 办公工具集 - Flet 插件化桌面应用

## TL;DR

> **Quick Summary**: 创建基于 Flet 的桌面应用程序，采用插件化架构，支持自动发现和加载工具。首个集成工具为 Excel 文件对比分析器。
> 
> **Deliverables**: 
> - 可运行的桌面应用程序（main.py）
> - 插件管理核心框架（core/）
> - Excel 对比插件（plugins/excel_compare/）
> - 插件开发模板（plugins/template/）
> - 依赖配置（pyproject.toml 或 requirements.txt）
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 5 → Task 7 → F1-F4

---

## Context

### Original Request
用户希望创建一个办公工具集合程序，要求：
1. 使用 Flet (Flutter) 框架构建桌面应用
2. 采用插件模式，每个工具独立文件
3. 放入 plugins 目录自动加载
4. 方便扩展新工具

### Interview Summary
**Key Discussions**:
- 应用类型: 桌面应用（非 Web）
- GUI 框架: Flet (Flutter) - 现代化 UI，可同时生成 Web 和桌面
- 扩展方式: 插件模式 - 每个工具独立文件，放入 plugins 目录自动加载
- 现有代码: excel_compare.py 已存在，将作为首个插件集成

**Research Findings**:
- Flet 支持 Windows/Mac/Linux 桌面打包
- 使用 importlib.util 实现动态插件加载
- NavigationRail 适合侧边栏导航
- 需要处理插件加载失败的容错机制

### Metis Review
**Identified Gaps** (addressed):
- 后端模块处理: 保持不动，仅集成 excel_compare.py
- Excel 对比插件范围: 仅 GUI 功能，CLI 保持独立脚本
- 目标平台: Windows 优先
- 插件错误显示: Snackbar 通知 + 继续运行
- 空插件目录: 显示空状态 UI

---

## Work Objectives

### Core Objective
构建一个可扩展的办公工具桌面应用，核心框架提供插件管理和 UI 容器，工具作为插件动态加载。

### Concrete Deliverables
- `office_tools/main.py` - 应用启动入口
- `office_tools/core/app.py` - Flet 主应用
- `office_tools/core/plugin_manager.py` - 插件管理器
- `office_tools/core/base_plugin.py` - 插件基类
- `office_tools/plugins/excel_compare/` - Excel 对比插件
- `office_tools/plugins/template/` - 插件开发模板

### Definition of Done
- [ ] 运行 `python office_tools/main.py` 启动应用
- [ ] 应用窗口显示侧边栏导航
- [ ] Excel 对比插件可正常加载和使用
- [ ] 文件选择、对比、结果展示功能完整
- [ ] 插件加载失败时显示友好错误提示

### Must Have
- Flet 桌面应用框架
- 插件自动发现机制
- NavigationRail 侧边栏
- Excel 对比工具集成
- 中文 UI

### Must NOT Have (Guardrails)
- 不创建配置持久化系统
- 不添加 logging 框架
- 不构建测试框架（MVP 手动测试）
- 不迁移 backend/ 模块
- 不实现热重载
- 不过度抽象（无工厂模式、建造者模式）

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO
- **Automated tests**: None (MVP)
- **Framework**: N/A

### QA Policy
每个任务包含 agent-executed QA 场景。
证据保存到 `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`。

- **Desktop GUI**: 使用 Playwright (playwright skill) — 截图验证 UI 元素
- **File Operations**: 使用 Bash — 验证文件创建、内容正确性
- **Plugin Loading**: 使用 Bash (python -c) — 验证导入和实例化

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - all parallel):
├── Task 1: Add flet dependency [quick]
├── Task 2: Create base_plugin.py with PluginInterface [quick]
├── Task 3: Create plugin_manager.py [quick]
└── Task 4: Create main app shell with NavigationRail [quick]

Wave 2 (Plugin Integration - after Wave 1):
├── Task 5: Create excel_compare plugin [unspecified-high]
├── Task 6: Create plugin template [quick]
└── Task 7: Integrate plugin discovery into main app [quick]

Wave 3 (Polish - after Wave 2):
├── Task 8: Add error handling for plugin failures [quick]
└── Task 9: Create README with usage instructions [writing]

Wave FINAL (Verification - after ALL tasks):
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Real manual QA [unspecified-high]
└── Task F4: Scope fidelity check [deep]
-> Present results -> Get explicit user okay

Critical Path: T1 → T2 → T5 → T7 → T8 → F1-F4
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

- **1**: — — 7
- **2**: — — 5, 6
- **3**: — — 7
- **4**: — — 7
- **5**: 2 — 7
- **6**: 2 — 7
- **7**: 1, 3, 4, 5 — 8
- **8**: 7 — 9
- **9**: 8 — F1-F4

### Agent Dispatch Summary

- **Wave 1**: 4 tasks — T1-T4 → `quick`
- **Wave 2**: 3 tasks — T5 → `unspecified-high`, T6-T7 → `quick`
- **Wave 3**: 2 tasks — T8 → `quick`, T9 → `writing`
- **FINAL**: 4 tasks — F1 → `oracle`, F2-F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 1. Add flet dependency to pyproject.toml

  **What to do**:
  - 在项目根目录的 `pyproject.toml` 中添加 `flet` 依赖
  - 如果没有 pyproject.toml，创建一个简单的或使用 requirements.txt
  - 运行 `pip install flet` 确保依赖可用

  **Must NOT do**:
  - 不要添加其他不必要的依赖（如 logging, pytest 等）
  - 不要修改现有 backend/ 模块的依赖

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的依赖添加，单一明确目标
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:
  - `pyproject.toml` 或 `requirements.txt` - 添加依赖的位置
  - Flet 官方文档: `https://flet.dev/docs/` - 安装说明

  **Acceptance Criteria**:
  - [ ] flet 添加到依赖配置文件
  - [ ] `pip show flet` 返回版本信息
  - [ ] `python -c "import flet; print(flet.__version__)"` 成功执行

  **QA Scenarios**:
  ```
  Scenario: Verify flet installation
    Tool: Bash
    Steps:
      1. Run: pip show flet
      2. Assert: Output contains "Name: flet"
    Expected Result: Command exits with code 0, shows flet info
    Evidence: .sisyphus/evidence/task-01-flet-install.txt
  ```

  **Commit**: YES
  - Message: `build: add flet dependency to pyproject.toml`
  - Files: `pyproject.toml` 或 `requirements.txt`

- [ ] 2. Create base_plugin.py with PluginInterface

  **What to do**:
  - 创建 `office_tools/core/base_plugin.py`
  - 定义 `PluginMeta` dataclass 包含: name, version, description, author, icon, category
  - 定义 `BasePlugin` 抽象基类包含:
    - `_meta: PluginMeta` 属性
    - `meta` property getter
    - `build_ui(page: ft.Page) -> ft.Control` 抽象方法
    - `on_load(page: ft.Page)` 可选方法
    - `on_unload()` 可选方法
    - `get_menu_item() -> ft.NavigationDrawerDestination` 方法

  **Must NOT do**:
  - 不要添加不必要的抽象方法
  - 不要创建工厂类或注册器类
  - 不要添加配置系统

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 定义清晰的接口类，结构简单
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 5, 6
  - **Blocked By**: None

  **References**:
  - Python ABC 文档: `https://docs.python.org/3/library/abc.html`
  - Flet 控件文档: `https://flet.dev/docs/controls/`

  **Acceptance Criteria**:
  - [ ] 文件创建在正确位置
  - [ ] PluginMeta dataclass 包含所有必需字段
  - [ ] BasePlugin 是抽象类
  - [ ] build_ui 是抽象方法
  - [ ] 可成功导入: `from core.base_plugin import BasePlugin, PluginMeta`

  **QA Scenarios**:
  ```
  Scenario: Verify base plugin import
    Tool: Bash
    Steps:
      1. cd office_tools
      2. python -c "from core.base_plugin import BasePlugin, PluginMeta; print('OK')"
    Expected Result: Output "OK"
    Evidence: .sisyphus/evidence/task-02-base-plugin.txt
  ```

  **Commit**: YES
  - Message: `feat(core): create PluginInterface abstract base class`
  - Files: `office_tools/core/base_plugin.py`, `office_tools/core/__init__.py`

- [ ] 3. Create plugin_manager.py with discovery logic

  **What to do**:
  - 创建 `office_tools/core/plugin_manager.py`
  - 实现 `PluginManager` 类:
    - `__init__(plugins_dir: Path)` 初始化
    - `discover_plugins() -> List[str]` 发现所有插件
    - `_load_plugin_module(plugin_name, file_path) -> bool` 加载单个插件模块
    - `instantiate_plugin(plugin_name) -> Optional[BasePlugin]` 实例化插件
    - `get_plugin(plugin_name) -> Optional[BasePlugin]` 获取已实例化的插件
    - `get_all_plugins() -> Dict[str, BasePlugin]` 获取所有插件
    - `get_plugin_categories() -> Dict[str, List[str]]` 按分类获取插件
  - 使用 `importlib.util.spec_from_file_location` 动态加载
  - 处理加载失败的异常

  **Must NOT do**:
  - 不要添加插件热重载功能
  - 不要创建复杂的插件验证系统
  - 不要添加插件依赖管理

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 核心逻辑清晰，使用标准库
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:
  - importlib 文档: `https://docs.python.org/3/library/importlib.html`
  - 动态导入模式: `importlib.util.spec_from_file_location`

  **Acceptance Criteria**:
  - [ ] 文件创建在正确位置
  - [ ] discover_plugins 能发现 .py 文件和包目录
  - [ ] 加载失败时不会崩溃，返回 False
  - [ ] 可成功导入: `from core.plugin_manager import PluginManager`

  **QA Scenarios**:
  ```
  Scenario: Verify plugin manager import
    Tool: Bash
    Steps:
      1. cd office_tools
      2. python -c "from core.plugin_manager import PluginManager; print('OK')"
    Expected Result: Output "OK"
    Evidence: .sisyphus/evidence/task-03-plugin-manager.txt
  ```

  **Commit**: YES
  - Message: `feat(core): create PluginManager with discovery logic`
  - Files: `office_tools/core/plugin_manager.py`

- [ ] 4. Create main app shell with NavigationRail

  **What to do**:
  - 创建 `office_tools/main.py` 作为启动入口
  - 创建 `office_tools/core/app.py` 包含主应用类
  - 实现 `OfficeToolsApp` 类:
    - 使用 `ft.NavigationRail` 作为侧边栏
    - 主内容区域使用 `ft.Container` 或 `ft.Column`
    - `load_plugins()` 方法加载所有插件
    - `switch_plugin(plugin_name)` 切换显示的插件
  - 使用 `ft.AppView.DESKTOP` 模式
  - 窗口标题: "办公工具集"
  - 默认窗口大小: 1200x800

  **Must NOT do**:
  - 不要添加主题切换功能
  - 不要添加配置持久化
  - 不要实现热重载

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Flet 应用结构清晰，文档完善
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:
  - Flet NavigationRail: `https://flet.dev/docs/controls/navigationrail/`
  - Flet Desktop App: `https://flet.dev/docs/guides/python/packaging-desktop-app`

  **Acceptance Criteria**:
  - [ ] main.py 可启动 Flet 应用
  - [ ] 应用窗口显示 NavigationRail
  - [ ] 窗口标题和大小正确
  - [ ] 可成功运行: `python office_tools/main.py`

  **QA Scenarios**:
  ```
  Scenario: Verify app launches
    Tool: Bash
    Steps:
      1. cd office_tools
      2. timeout 5 python main.py || true
    Expected Result: No import errors, app attempts to start
    Evidence: .sisyphus/evidence/task-04-app-launch.txt
  ```

  **Commit**: YES
  - Message: `feat: create main Flet app with NavigationRail`
  - Files: `office_tools/main.py`, `office_tools/core/app.py`

- [ ] 5. Create excel_compare plugin

  **What to do**:
  - 创建 `office_tools/plugins/excel_compare/` 目录
  - 创建 `__init__.py` 导出插件类
  - 创建 `plugin.py` 实现 `ExcelComparePlugin` 类:
    - 继承 `BasePlugin`
    - 设置 `_meta` (name="Excel对比", icon="table_excel", category="数据处理")
    - 实现 `build_ui()` 返回 Flet UI 组件
    - UI 包含: 文件选择器、列选择下拉框、对比按钮、结果显示区域
  - 复用现有的 `ExcelComparator` 逻辑（从 excel_compare.py）
  - 使用 `ft.FilePicker` 选择文件
  - 使用 `ft.DataTable` 或 `ft.ListView` 显示结果

  **Must NOT do**:
  - 不要保留 CLI 交互代码（argparse, input()）
  - 不要修改原始 excel_compare.py（保留为独立脚本）
  - 不要添加 config 持久化

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要将 CLI 代码转换为 GUI，涉及 UI 设计和逻辑重构
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 2)
  - **Parallel Group**: Wave 2 (with Tasks 6, 7)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:
  - `excel_compare.py` - 现有的 Excel 对比逻辑
  - `office_tools/core/base_plugin.py` - 插件基类
  - Flet FilePicker: `https://flet.dev/docs/controls/filepicker/`

  **Acceptance Criteria**:
  - [ ] 插件目录结构正确
  - [ ] 可成功导入: `from plugins.excel_compare import ExcelComparePlugin`
  - [ ] 插件 UI 可正常渲染
  - [ ] 文件选择功能可用
  - [ ] 对比功能可用，结果正确显示

  **QA Scenarios**:
  ```
  Scenario: Verify plugin can be imported
    Tool: Bash
    Steps:
      1. cd office_tools
      2. python -c "from plugins.excel_compare import ExcelComparePlugin; print('OK')"
    Expected Result: Output "OK"
    Evidence: .sisyphus/evidence/task-05-plugin-import.txt

  Scenario: Verify plugin metadata
    Tool: Bash
    Steps:
      1. cd office_tools
      2. python -c "from plugins.excel_compare import ExcelComparePlugin; p = ExcelComparePlugin(); print(p.meta.name)"
    Expected Result: Output "Excel对比"
    Evidence: .sisyphus/evidence/task-05-plugin-meta.txt
  ```

  **Commit**: YES
  - Message: `feat(plugins): create excel_compare plugin`
  - Files: `office_tools/plugins/excel_compare/`

- [ ] 6. Create plugin development template

  **What to do**:
  - 创建 `office_tools/plugins/template/` 目录
  - 创建 `__init__.py` 导出模板插件
  - 创建 `plugin.py` 实现示例 `TemplatePlugin`:
    - 继承 `BasePlugin`
    - 设置 `_meta` (name="插件模板", icon="code", category="开发")
    - 实现 `build_ui()` 返回简单的说明页面
    - 包含详细注释说明如何开发新插件
  - 创建 `README.md` 说明插件开发步骤

  **Must NOT do**:
  - 不要添加复杂功能到模板
  - 保持模板简洁易懂

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的模板创建，主要是示例代码
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 2)
  - **Parallel Group**: Wave 2 (with Tasks 5, 7)
  - **Blocks**: Task 7
  - **Blocked By**: Task 2

  **References**:
  - `office_tools/core/base_plugin.py` - 插件基类
  - `office_tools/plugins/excel_compare/` - 已实现的插件示例

  **Acceptance Criteria**:
  - [ ] 模板目录结构正确
  - [ ] 可成功导入模板插件
  - [ ] README 包含开发步骤说明
  - [ ] 代码注释清晰

  **QA Scenarios**:
  ```
  Scenario: Verify template plugin
    Tool: Bash
    Steps:
      1. cd office_tools
      2. python -c "from plugins.template import TemplatePlugin; p = TemplatePlugin(); print(p.meta.name)"
    Expected Result: Output "插件模板"
    Evidence: .sisyphus/evidence/task-06-template.txt
  ```

  **Commit**: YES
  - Message: `feat(plugins): create plugin development template`
  - Files: `office_tools/plugins/template/`

- [ ] 7. Integrate plugin discovery into main app

  **What to do**:
  - 修改 `office_tools/core/app.py`:
    - 在 `__init__` 中创建 `PluginManager` 实例
    - 在 `page.on_load` 或初始化时调用 `discover_plugins()`
    - 为每个插件调用 `instantiate_plugin()`
    - 将插件添加到 NavigationRail destinations
    - 实现点击导航项时切换插件 UI
  - 处理插件加载失败情况（显示错误提示）
  - 如果没有插件，显示空状态提示

  **Must NOT do**:
  - 不要静默忽略插件加载失败
  - 不要让单个插件失败影响整个应用

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 集成已有组件，逻辑清晰
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (depends on 1, 3, 4, 5)
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 1, 3, 4, 5

  **References**:
  - `office_tools/core/plugin_manager.py` - 插件管理器
  - `office_tools/core/app.py` - 主应用
  - `office_tools/plugins/` - 插件目录

  **Acceptance Criteria**:
  - [ ] 应用启动时自动发现所有插件
  - [ ] NavigationRail 显示所有插件图标和名称
  - [ ] 点击导航项切换到对应插件 UI
  - [ ] 插件加载失败显示错误提示

  **QA Scenarios**:
  ```
  Scenario: Verify plugin discovery
    Tool: Bash
    Steps:
      1. cd office_tools
      2. python -c "from core.plugin_manager import PluginManager; from pathlib import Path; pm = PluginManager(Path('plugins')); plugins = pm.discover_plugins(); print(plugins)"
    Expected Result: Output contains "excel_compare" and "template"
    Evidence: .sisyphus/evidence/task-07-discovery.txt
  ```

  **Commit**: YES
  - Message: `feat: integrate plugin discovery into main app`
  - Files: `office_tools/core/app.py`, `office_tools/main.py`

- [ ] 8. Add error handling for plugin failures

  **What to do**:
  - 在 `PluginManager` 中添加更健壮的错误处理:
    - `_load_plugin_module` 捕获所有异常
    - 记录失败的插件和原因
  - 在主应用中:
    - 使用 `ft.SnackBar` 显示插件加载失败通知
    - 在 NavigationRail 中为失败插件显示禁用状态
    - 在主内容区域显示详细错误信息
  - 添加 `get_failed_plugins()` 方法返回失败列表

  **Must NOT do**:
  - 不要让错误导致应用崩溃
  - 不要使用 logging 模块（用 print）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准的错误处理添加
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (depends on Task 7)
  - **Blocks**: Task 9
  - **Blocked By**: Task 7

  **References**:
  - `office_tools/core/plugin_manager.py` - 添加错误处理
  - `office_tools/core/app.py` - 显示错误通知
  - Flet SnackBar: `https://flet.dev/docs/controls/snackbar/`

  **Acceptance Criteria**:
  - [ ] 插件加载失败不导致应用崩溃
  - [ ] 失败时显示 SnackBar 通知
  - [ ] 可通过 `get_failed_plugins()` 获取失败列表

  **QA Scenarios**:
  ```
  Scenario: Verify error handling
    Tool: Bash
    Steps:
      1. Create a broken plugin file in plugins/
      2. cd office_tools
      3. python -c "from core.plugin_manager import PluginManager; from pathlib import Path; pm = PluginManager(Path('plugins')); pm.discover_plugins(); print(pm.get_failed_plugins())"
      4. Remove broken plugin
    Expected Result: Returns list of failed plugins without crashing
    Evidence: .sisyphus/evidence/task-08-error-handling.txt
  ```

  **Commit**: YES
  - Message: `fix: add error handling for plugin failures`
  - Files: `office_tools/core/plugin_manager.py`, `office_tools/core/app.py`

- [ ] 9. Create README with usage instructions

  **What to do**:
  - 创建 `office_tools/README.md`
  - 包含以下内容:
    - 项目简介
    - 安装依赖 (`pip install flet pandas openpyxl`)
    - 运行方式 (`python main.py`)
    - 如何开发新插件（基于模板）
    - 插件目录结构说明
    - 已有插件列表

  **Must NOT do**:
  - 不要添加过多的安装方式（保持简单）
  - 不要添加贡献指南（MVP 不需要）

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 文档编写
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (depends on Task 8)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 8

  **References**:
  - `office_tools/` 目录结构
  - `office_tools/plugins/template/README.md` - 插件开发说明

  **Acceptance Criteria**:
  - [ ] README.md 存在
  - [ ] 包含安装、运行、开发插件说明
  - [ ] 格式清晰，易于阅读

  **QA Scenarios**:
  ```
  Scenario: Verify README exists and is complete
    Tool: Bash
    Steps:
      1. cat office_tools/README.md
    Expected Result: File contains "安装", "运行", "开发插件" sections
    Evidence: .sisyphus/evidence/task-09-readme.txt
  ```

  **Commit**: YES
  - Message: `docs: add README with usage instructions`
  - Files: `office_tools/README.md`

---

## Final Verification Wave (MANDATORY)

- [ ] F1. **Plan Compliance Audit** — `oracle`
  读取计划全文。验证每个 "Must Have" 是否实现，每个 "Must NOT Have" 是否不存在。
  Output: `Must Have [N/N] | Must NOT Have [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  检查所有新建文件：`as any`/`@ts-ignore` 等价物、空 catch、console.log、注释代码、未使用导入。
  Output: `Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  启动应用，执行每个 QA 场景，截图保存证据。
  Output: `Scenarios [N/N pass] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  对比每个任务的 "What to do" 与实际代码，验证 1:1 匹配。
  Output: `Tasks [N/N compliant] | VERDICT`

---

## Commit Strategy

- **1**: `build: add flet dependency to pyproject.toml`
- **2**: `feat(core): create PluginInterface abstract base class`
- **3**: `feat(core): create PluginManager with discovery logic`
- **4**: `feat: create main Flet app with NavigationRail`
- **5**: `feat(plugins): create excel_compare plugin`
- **6**: `feat(plugins): create plugin development template`
- **7**: `feat: integrate plugin discovery into main app`
- **8**: `fix: add error handling for plugin failures`
- **9**: `docs: add README with usage instructions`

---

## Success Criteria

### Verification Commands
```bash
# 1. 依赖安装成功
pip show flet
# Expected: Name: flet, Version: X.X.X

# 2. 应用启动成功
cd office_tools && python main.py
# Expected: Window opens with NavigationRail

# 3. 插件加载成功
python -c "from core.plugin_manager import PluginManager; pm = PluginManager(Path('plugins')); print(pm.discover_plugins())"
# Expected: ['excel_compare', 'template']

# 4. Excel 对比功能可用
# Manual: Select two Excel files, compare, view results
```

### Final Checklist
- [ ] 应用可正常启动
- [ ] 侧边栏显示所有已加载插件
- [ ] Excel 对比插件可完整使用
- [ ] 插件加载失败有友好提示
- [ ] 代码无过度抽象
- [ ] README 文档完整
