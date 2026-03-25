# Flet 使用指南

> 面向Python初学者的GUI框架入门教程

## 1. Flet 简介

### 1.1 什么是 Flet？

Flet 是一个Python GUI框架，让你用**纯Python**构建跨平台应用（桌面、Web、移动端）。

**核心特点**：
- 🚀 **零前端知识** - 不需要HTML/CSS/JavaScript
- 🎯 **跨平台** - Windows、macOS、Linux、Web、Android、iOS
- ⚡ **即时预览** - 修改代码立即看到效果
- 🎨 **Flutter引擎** - 使用Google Flutter渲染，UI现代化

### 1.2 安装

```bash
uv add 'flet[all]'
```

### 1.3 第一个应用

```python
import flet as ft

def main(page: ft.Page):
    page.title = "我的第一个应用"
    page.add(ft.Text("你好，Flet！"))

ft.run(main)
```

运行：
```bash
python app.py
```

---

## 2. 核心概念

### 2.1 Page - 页面容器

每个Flet应用都有一个`Page`对象，是所有UI元素的根容器。

```python
def main(page: ft.Page):
    page.title = "页面标题"        # 设置标题
    page.theme_mode = ft.ThemeMode.LIGHT  # 设置主题（LIGHT/DARK/SYSTEM）
    page.window_width = 400       # 窗口宽度
    page.window_height = 300      # 窗口高度
```

### 2.2 Controls - 控件

控件是UI的基本元素（按钮、文本、输入框等）。

**常用控件**：

| 控件 | 用途 |
|------|------|
| `ft.Text` | 显示文本 |
| `ft.TextField` | 输入框 |
| `ft.Button` | 按钮 |
| `ft.IconButton` | 图标按钮 |
| `ft.Checkbox` | 复选框 |
| `ft.Dropdown` | 下拉选择 |
| `ft.Switch` | 开关 |
| `ft.Slider` | 滑块 |
| `ft.Image` | 图片 |
| `ft.Container` | 容器（用于样式） |

---

## 3. 布局系统

### 3.1 Row - 水平布局

```python
ft.Row(
    controls=[
        ft.Text("A"),
        ft.Text("B"),
        ft.Text("C"),
    ],
    alignment=ft.MainAxisAlignment.CENTER,  # 对齐方式
    spacing=10,  # 间距
)
```

### 3.2 Column - 垂直布局

```python
ft.Column(
    controls=[
        ft.Text("第一行"),
        ft.Text("第二行"),
        ft.Text("第三行"),
    ],
    spacing=20,
    scroll=ft.ScrollMode.AUTO,  # 可滚动
)
```

### 3.3 常用布局属性

| 属性 | 说明 |
|------|------|
| `alignment` | 主轴对齐（START/CENTER/END/SPACE_BETWEEN/SPACE_AROUND） |
| `horizontal_alignment` | 水平对齐 |
| `vertical_alignment` | 垂直对齐 |
| `spacing` | 子元素间距 |
| `expand` | 是否填充剩余空间（True/数字/loose） |
| `width` / `height` | 固定尺寸 |
| `padding` | 内边距 |
| `bgcolor` | 背景色 |

---

## 4. 事件处理

### 4.1 基本事件

```python
def button_clicked(e):
    print(f"按钮被点击了！")

ft.Button("点击我", on_click=button_clicked)
```

### 4.2 获取输入值

```python
def text_changed(e):
    print(f"输入内容: {e.control.value}")

ft.TextField(
    label="请输入",
    on_change=text_changed,  # 内容变化时
    on_submit=lambda e: print(f"回车提交: {e.control.value}"),  # 回车时
)
```

### 4.3 常用事件

| 事件 | 触发时机 |
|------|----------|
| `on_click` | 点击 |
| `on_change` | 值变化 |
| `on_submit` | 回车提交（TextField） |
| `on_focus` / `on_blur` | 获得/失去焦点 |
| `on_hover` / `on_dismiss` | 鼠标悬停/离开 |
| `on_scroll` | 滚动 |

---

## 5. 状态管理

### 5.1 基本方式 - update()

```python
import flet as ft

def main(page: ft.Page):
    count = 0
    text = ft.Text(f"计数: {count}")
    
    def increment(e):
        nonlocal count
        count += 1
        text.value = f"计数: {count}"
        page.update()  # 刷新页面
    
    page.add(
        text,
        ft.Button("增加", on_click=increment),
    )

ft.run(main)
```

### 5.2 声明式组件 - @ft.component

```python
import flet as ft

@ft.component
def Counter():
    count, set_count = ft.use_state(0)
    
    return ft.Column([
        ft.Text(f"计数: {count}"),
        ft.Button("增加", on_click=lambda _: set_count(count + 1)),
        ft.Button("减少", on_click=lambda _: set_count(count - 1)),
    ])

def main(page: ft.Page):
    page.add(Counter())

ft.run(main)
```

### 5.3 use_state Hook

| Hook | 用途 |
|------|------|
| `ft.use_state(default)` | 状态变量，返回 (value, setter) |
| `ft.use_effect(func, deps)` | 副作用（类似React） |
| `ft.use_ref(default)` | 引用（不触发重渲染） |

---

## 6. 常用组件示例（声明式）

### 6.1 表单示例

```python
import flet as ft
from dataclasses import dataclass, field


@ft.observable
@dataclass
class FormState:
    """表单状态 - 响应式"""
    name: str = ""
    email: str = ""
    submitted: bool = False
    
    def submit(self):
        if self.name and self.email:
            self.submitted = True


@ft.component
def FormExample() -> ft.Control:
    """声明式表单组件"""
    state, _ = ft.use_state(FormState())
    
    if state.submitted:
        return ft.Column([
            ft.Text("提交成功！", size=24, color=ft.Colors.GREEN),
            ft.Text(f"姓名: {state.name}"),
            ft.Text(f"邮箱: {state.email}"),
            ft.TextButton("重新填写", on_click=lambda: setattr(state, 'submitted', False)),
        ])
    
    return ft.Column([
        ft.TextField(
            label="姓名",
            value=state.name,
            on_change=lambda e: setattr(state, 'name', e.control.value),
        ),
        ft.TextField(
            label="邮箱",
            value=state.email,
            on_change=lambda e: setattr(state, 'email', e.control.value),
        ),
        ft.ElevatedButton(
            "提交",
            on_click=lambda _: state.submit(),
            disabled=not (state.name and state.email),
        ),
    ], spacing=10)


ft.run(lambda page: page.render(FormExample))
```

### 6.2 列表示例

```python
import flet as ft
from dataclasses import dataclass, field
from typing import List


@ft.observable
@dataclass
class TodoState:
    """待办状态 - 响应式"""
    tasks: List[str] = field(default_factory=list)
    new_task: str = ""
    
    def add_task(self):
        if self.new_task.strip():
            self.tasks.append(self.new_task.strip())
            self.new_task = ""
    
    def remove_task(self, task: str):
        if task in self.tasks:
            self.tasks.remove(task)


@ft.component
def TodoList() -> ft.Control:
    """声明式待办列表"""
    state, _ = ft.use_state(TodoState(tasks=["学习Flet", "写代码", "部署应用"]))
    
    return ft.Column([
        # 输入区域
        ft.Row([
            ft.TextField(
                value=state.new_task,
                on_change=lambda e: setattr(state, 'new_task', e.control.value),
                hint_text="添加新任务...",
                expand=True,
            ),
            ft.IconButton(
                icon=ft.Icons.ADD,
                on_click=lambda _: state.add_task(),
            ),
        ]),
        
        # 任务列表（条件渲染）
        ft.Column([
            ft.ListTile(
                title=ft.Text(task),
                trailing=ft.IconButton(
                    icon=ft.Icons.DELETE,
                    on_click=lambda e, t=task: state.remove_task(t),
                ),
            )
            for task in state.tasks
        ]) if state.tasks else ft.Text("暂无任务", color=ft.Colors.GREY),
    ], spacing=10)


ft.run(lambda page: page.render(TodoList))
```

### 6.2 列表示例

```python
import flet as ft

def main(page: ft.Page):
    tasks = ["学习Flet", "写代码", "部署应用"]
    
    def delete_task(e):
        tasks.remove(e.control.data)
        render_list()
    
    def render_list():
        lv.controls.clear()
        for task in tasks:
            lv.controls.append(
                ft.ListTile(
                    title=task,
                    trailing=ft.IconButton(
                        icon=ft.icons.DELETE,
                        on_click=delete_task,
                        data=task,
                    ),
                )
            )
        page.update()
    
    lv = ft.ListView(expand=True)
    render_list()
    page.add(lv)

ft.run(main)
```

### 6.3 对话框

```python
import flet as ft

def main(page: ft.Page):
    def open_dialog(e):
        dlg = ft.AlertDialog(
            title=ft.Text("确认"),
            content=ft.Text("确定要删除吗？"),
            actions=[
                ft.TextButton("取消", on_click=lambda _: page.close_dialog()),
                ft.TextButton("确定", on_click=lambda _: page.close_dialog()),
            ],
        )
        page.open_dialog(dlg)
    
    page.add(ft.Button("删除", on_click=open_dialog))

ft.run(main)
```

---

## 7. 导航与路由

### 7.1 多页面应用

```python
import flet as ft

def main(page: ft.Page):
    def route_change(e):
        page.views.clear()
        
        if page.route == "/":
            page.views.append(home_view())
        elif page.route == "/settings":
            page.views.append(settings_view())
        
        page.update()
    
    def home_view():
        return ft.View(
            "/",
            controls=[
                ft.AppBar(title="首页"),
                ft.Text("欢迎！"),
                ft.Button("设置", on_click=lambda _: page.go("/settings")),
            ],
        )
    
    def settings_view():
        return ft.View(
            "/settings",
            controls=[
                ft.AppBar(title="设置"),
                ft.Text("设置页面"),
                ft.Button("返回", on_click=lambda _: page.go("/")),
            ],
        )
    
    page.on_route_change = route_change
    page.go("/")

ft.run(main)
```

### 7.2 路由方法

| 方法 | 说明 |
|------|------|
| `page.go(route)` | 导航到指定路由 |
| `page.go_back()` | 返回上一页 |
| `page.route` | 当前路由 |

---

## 8. 样式与主题

### 8.1 颜色

```python
ft.Text("文本", color=ft.Colors.RED)  # 预设颜色
ft.Text("文本", color="blue")            # 字符串颜色
ft.Container(bgcolor=ft.Colors.GREY_100)  # 背景色
```

**预设颜色**： `RED`, `GREEN`, `BLUE`, `YELLOW`, `ORANGE`, `PURPLE`, `BLACK`, `WHITE`, `GREY_*`

### 8.2 字体

```python
ft.Text("标题", size=24, weight=ft.FontWeight.BOLD)
ft.Text("正文", size=14, weight=ft.FontWeight.NORMAL)
```

### 8.3 内边距与外边距

```python
ft.Container(
    padding=20,           # 四边
    padding=ft.padding.all(10, 20, 10, 20),  # 上右下左
    margin=10,
)
```

---

## 9. 运行与部署

### 9.1 运行方式

```bash
# 桌面应用
flet run app.py

# Web应用
flet run --web app.py

# 指定端口
flet run --port 8080 app.py
```

### 9.2 打包发布

```bash
# 打包为桌面应用
flet build windows app.py
flet build macos app.py
flet build linux app.py

# 打包为Web应用
flet build web app.py
```

---

## 10. 快速参考

### 10.1 常用布局组合

```python
# 卡片布局
ft.Container(
    padding=15,
    border_radius=10,
    bgcolor=ft.Colors.WHITE,
    shadow=ft.BoxShadow(5, 5, 15, ft.Colors.GREY_400),
    content=ft.Column([
        ft.Text("标题", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("描述内容", color=ft.Colors.GREY_700),
    ]),
)

# 两栏布局
ft.Row([
    ft.Container(expand=1, bgcolor=ft.Colors.BLUE_100),
    ft.Container(expand=2, bgcolor=ft.Colors.RED_100),
], expand=True)
```

### 10.2 项目结构（Flet标准）

```bash
# 创建新项目
uv run flet create my_app
```

```
my_app/                      # Flet标准项目结构
├── README.md                # 项目说明
├── pyproject.toml           # 项目配置（依赖、元信息）
├── src/                     # 源代码目录
│   ├── assets/              # 静态资源（图片、图标等）
│   │   └── icon.png
│   ├── main.py              # 应用入口
│   ├── views/               # 页面视图
│   │   ├── __init__.py
│   │   ├── home.py
│   │   └── settings.py
│   └── components/          # 可复用组件
│       ├── __init__.py
│       ├── header.py
│       └── footer.py
└── storage/                 # 存储目录
    ├── data/                # 持久化数据
    └── temp/                # 临时文件
```

**运行命令**：
```bash
# 开发运行
uv run flet run src/main.py

# Web模式
uv run flet run --web src/main.py

# 打包发布
uv run flet build windows src/main.py
```

---

## 11. 常见问题

### Q: 如何更新页面？
```python
page.update()  # 刷新整个页面
page.update(text)  # 只刷新特定控件
```

### Q: 如何传递数据？
```python
# 方式1: 函数参数
def MyComponent(title):
    return ft.Text(title)

# 方式2: 控件的data属性
btn = ft.Button("删除", data=item_id, on_click=handle_delete)
# 在事件中获取: e.control.data
```

### Q: 如何处理异步操作？
```python
import asyncio

async def fetch_data():
    await asyncio.sleep(1)
    return "数据"

async def on_click(e):
    data = await fetch_data()
    text.value = data
    page.update()
```

---

*更多资源*：
- 官方文档：https://flet.dev/docs/
- GitHub示例：https://github.com/flet-dev/flet/tree/main/sdk/python/examples
