# -*- coding: utf-8 -*-
"""
插件系统测试模块
==================

测试插件系统的核心功能:
- PluginBase: 插件基类
- ToolDefinition: 工具定义
- PluginManager: 插件管理器
- PluginState: 插件状态
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from src.core.plugin_base import (
    PluginBase,
    ToolDefinition,
    PortDefinition,
    PortType,
)
from src.core.plugin_manager import (
    PluginInfo,
    PluginState,
    PluginManager,
)


# ==================== 测试工具定义 ====================


class TestToolDefinition:
    """测试ToolDefinition类"""

    def test_create_tool_definition(self):
        """测试创建工具定义"""

        def simple_execute(text: str) -> str:
            return text.upper()

        tool = ToolDefinition(
            name="test_tool",
            display_name="测试工具",
            description="一个简单的测试工具",
            category="测试",
            icon="🔧",
            inputs=[
                PortDefinition("text", PortType.STRING, "输入文本"),
            ],
            outputs=[
                PortDefinition("result", PortType.STRING, "输出结果"),
            ],
            execute=simple_execute,
        )

        assert tool.name == "test_tool"
        assert tool.display_name == "测试工具"
        assert tool.category == "测试"
        assert len(tool.inputs) == 1
        assert len(tool.outputs) == 1

    def test_get_json_schema(self):
        """测试生成JSON Schema"""
        tool = ToolDefinition(
            name="add_numbers",
            display_name="数字相加",
            description="将两个数字相加",
            inputs=[
                PortDefinition("a", PortType.INTEGER, "第一个数字"),
                PortDefinition("b", PortType.INTEGER, "第二个数字", default=0),
            ],
            outputs=[
                PortDefinition("sum", PortType.INTEGER, "和"),
            ],
            execute=lambda a, b: a + b,
        )

        schema = tool.get_json_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "add_numbers"
        assert "a" in schema["function"]["parameters"]["properties"]
        assert "b" in schema["function"]["parameters"]["properties"]
        # a是必需的，b有默认值但也是required=True
        assert "a" in schema["function"]["parameters"]["required"]

    def test_port_type_to_json(self):
        """测试端口类型转换"""
        # 测试各种类型转换
        assert ToolDefinition._port_type_to_json(PortType.STRING) == "string"
        assert ToolDefinition._port_type_to_json(PortType.INTEGER) == "integer"
        assert ToolDefinition._port_type_to_json(PortType.FLOAT) == "number"
        assert ToolDefinition._port_type_to_json(PortType.BOOLEAN) == "boolean"
        assert ToolDefinition._port_type_to_json(PortType.LIST) == "array"
        assert ToolDefinition._port_type_to_json(PortType.DICT) == "object"


# ==================== 测试插件状态 ====================


class TestPluginState:
    """测试PluginState类"""

    def test_register_tool(self):
        """测试注册工具"""
        state = PluginState()

        tool = ToolDefinition(
            name="test",
            display_name="测试",
            description="测试工具",
            execute=lambda: None,
        )

        state.register_tool(tool)
        assert "test" in state.tools
        assert state.tools["test"] == tool

    def test_unregister_tool(self):
        """测试注销工具"""
        state = PluginState()

        tool = ToolDefinition(
            name="test",
            display_name="测试",
            description="测试工具",
            execute=lambda: None,
        )

        state.register_tool(tool)
        assert "test" in state.tools

        state.unregister_tool("test")
        assert "test" not in state.tools


# ==================== 测试插件基类 ====================


class MockPlugin(PluginBase):
    """模拟插件用于测试"""

    name = "mock_plugin"
    version = "1.0.0"
    description = "测试用模拟插件"

    def __init__(self):
        self.loaded = False
        self.unloaded = False

    def get_tools(self):
        return [
            ToolDefinition(
                name="mock_tool",
                display_name="模拟工具",
                description="测试用模拟工具",
                execute=lambda x: x * 2,
            )
        ]

    def on_load(self):
        self.loaded = True

    def on_unload(self):
        self.unloaded = True


class TestPluginBase:
    """测试PluginBase类"""

    def test_plugin_metadata(self):
        """测试插件元信息"""
        plugin = MockPlugin()
        assert plugin.name == "mock_plugin"
        assert plugin.version == "1.0.0"
        assert plugin.description == "测试用模拟插件"

    def test_get_tools(self):
        """测试获取工具列表"""
        plugin = MockPlugin()
        tools = plugin.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "mock_tool"

    def test_lifecycle_hooks(self):
        """测试生命周期钩子"""
        plugin = MockPlugin()

        # 初始状态
        assert not plugin.loaded
        assert not plugin.unloaded

        # 调用加载钩子
        plugin.on_load()
        assert plugin.loaded

        # 调用卸载钩子
        plugin.on_unload()
        assert plugin.unloaded


# ==================== 测试插件管理器 ====================


class TestPluginManager:
    """测试PluginManager类"""

    def test_discover_plugins_empty_dir(self, tmp_path: Path):
        """测试在空目录中发现插件"""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        state = PluginState()
        manager = PluginManager(plugins_dir, state)

        discovered = manager.discover_plugins()
        assert discovered == []

    def test_discover_single_file_plugin(self, tmp_path: Path):
        """测试发现单文件插件"""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # 创建一个简单的插件文件
        plugin_code = """
from src.core.plugin_base import PluginBase, ToolDefinition, PortDefinition, PortType

class TestPlugin(PluginBase):
    name = "test_plugin"
    version = "1.0.0"
    description = "测试插件"
    
    def get_tools(self):
        return [
            ToolDefinition(
                name="hello",
                display_name="Hello",
                description="Say hello",
                execute=lambda: "Hello!",
            )
        ]
"""
        (plugins_dir / "test_plugin.py").write_text(plugin_code)

        state = PluginState()
        manager = PluginManager(plugins_dir, state)

        discovered = manager.discover_plugins()
        assert "test_plugin" in discovered

    def test_load_plugin(self, tmp_path: Path):
        """测试加载插件"""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # 创建插件文件
        plugin_code = """
from src.core.plugin_base import PluginBase, ToolDefinition

class LoadablePlugin(PluginBase):
    name = "loadable"
    version = "1.0.0"
    description = "可加载插件"
    
    def get_tools(self):
        return [
            ToolDefinition(
                name="echo",
                display_name="Echo",
                description="Echo input",
                execute=lambda x: x,
            )
        ]
"""
        (plugins_dir / "loadable.py").write_text(plugin_code)

        state = PluginState()
        manager = PluginManager(plugins_dir, state)

        # 加载插件
        success = manager.load_plugin("loadable")
        assert success
        assert "echo" in state.tools

    def test_get_tool(self, tmp_path: Path):
        """测试获取工具"""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = """
from src.core.plugin_base import PluginBase, ToolDefinition

class ToolPlugin(PluginBase):
    name = "tool_plugin"
    version = "1.0.0"
    
    def get_tools(self):
        return [
            ToolDefinition(
                name="my_tool",
                display_name="My Tool",
                description="A tool",
                execute=lambda: "result",
            )
        ]
"""
        (plugins_dir / "tool_plugin.py").write_text(plugin_code)

        state = PluginState()
        manager = PluginManager(plugins_dir, state)
        manager.load_plugin("tool_plugin")

        tool = manager.get_tool("my_tool")
        assert tool is not None
        assert tool.name == "my_tool"

        # 测试不存在的工具
        assert manager.get_tool("nonexistent") is None

    def test_get_all_tools(self, tmp_path: Path):
        """测试获取所有工具"""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = """
from src.core.plugin_base import PluginBase, ToolDefinition

class MultiToolPlugin(PluginBase):
    name = "multi_tool"
    version = "1.0.0"
    
    def get_tools(self):
        return [
            ToolDefinition(name="tool1", display_name="Tool 1", description="", execute=lambda: 1),
            ToolDefinition(name="tool2", display_name="Tool 2", description="", execute=lambda: 2),
        ]
"""
        (plugins_dir / "multi.py").write_text(plugin_code)

        state = PluginState()
        manager = PluginManager(plugins_dir, state)
        manager.load_plugin("multi")

        tools = manager.get_all_tools()
        assert len(tools) == 2
