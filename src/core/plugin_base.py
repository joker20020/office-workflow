# -*- coding: utf-8 -*-
"""
插件基类模块

定义插件的基本接口和生命周期：
- PluginBase: 抽象基类，所有插件必须继承
- 插件元数据：name, version, description, author
- 权限声明：permissions
- 生命周期：on_load, on_unload

插件开发指南：
    from src.core.plugin_base import PluginBase, PermissionSet
    from src.core.permission_manager import Permission

    class MyPlugin(PluginBase):
        name = "my_plugin"
        version = "1.0.0"
        description = "我的插件"
        author = "Developer"

        permissions = PermissionSet.from_list([
            Permission.FILE_READ,
            Permission.EVENT_SUBSCRIBE,
        ])

        def on_load(self, context):
            # 插件加载时执行
            pass

        def on_unload(self):
            # 插件卸载时执行
            pass
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Union

from src.core.permission_manager import Permission, PermissionSet
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.app_context import AppContext
    from src.core.permission_proxy import PermissionProxy

    PluginContext = Union[AppContext, PermissionProxy]

# 模块日志记录器
_logger = get_logger(__name__)


class PluginBase(ABC):
    """
    插件抽象基类

    所有插件必须继承此类并实现抽象方法。

    Class Attributes:
        name: 插件唯一标识（必填）
        version: 插件版本号（必填）
        description: 插件描述（可选）
        author: 作者信息（可选）
        permissions: 所需权限集合（默认为空）

    Abstract Methods:
        on_load: 插件加载时调用
        on_unload: 插件卸载时调用

    Example:
        class MyPlugin(PluginBase):
            name = "my_plugin"
            version = "1.0.0"
            description = "示例插件"
            author = "Developer"

            permissions = PermissionSet.from_list([
                Permission.FILE_READ,
            ])

            def on_load(self, context: AppContext):
                context.event_bus.subscribe(
                    EventType.APP_STARTED,
                    self.on_app_started
                )

            def on_unload(self):
                # 清理资源
                pass

            def on_app_started(self, event):
                print("应用已启动")
    """

    # 插件元数据（子类必须覆盖）
    name: str = "unknown"
    version: str = "1.0.0"
    description: str = ""
    author: str = ""

    # 插件所需权限（默认为空）
    permissions: PermissionSet = PermissionSet.empty()

    # 插件实例状态
    _loaded: bool = False
    _context: Optional["AppContext"] = None

    @classmethod
    def get_required_permissions(cls) -> PermissionSet:
        """
        获取插件所需权限（类方法，加载前检查）

        Returns:
            插件声明的权限集合

        Note:
            此方法在插件加载前调用，用于权限检查。
            不应在此方法中执行任何初始化逻辑。
        """
        return cls.permissions

    @classmethod
    def get_metadata(cls) -> dict:
        """
        获取插件元数据

        Returns:
            包含 name, version, description, author 的字典
        """
        return {
            "name": cls.name,
            "version": cls.version,
            "description": cls.description,
            "author": cls.author,
            "permissions": [p.value for p in cls.permissions],
        }

    @abstractmethod
    def on_load(self, context: "PluginContext") -> None:
        """
        插件加载时调用

        Args:
            context: 应用上下文，提供访问程序功能的接口

        Note:
            - 此方法在插件加载时调用一次
            - 可以通过 context 访问已授权的功能
            - 应在此方法中完成插件的初始化工作

        Example:
            def on_load(self, context: AppContext):
                # 订阅事件
                context.event_bus.subscribe(
                    EventType.PLUGIN_LOADED,
                    self.on_other_plugin_loaded
                )

                # 注册工具
                if context.check_permission(Permission.AGENT_TOOL):
                    context.agent.register_tool("my_tool", self.my_func)
        """
        pass

    @abstractmethod
    def on_unload(self) -> None:
        """
        插件卸载时调用

        Note:
            - 此方法在插件卸载时调用一次
            - 应在此方法中清理所有资源
            - 取消所有事件订阅
            - 注销所有注册的工具

        Example:
            def on_unload(self):
                # 取消事件订阅
                if self._subscription_id:
                    self.context.event_bus.unsubscribe(self._subscription_id)

                # 注销工具
                # ...
        """
        pass

    @property
    def is_loaded(self) -> bool:
        """插件是否已加载"""
        return self._loaded

    @property
    def context(self) -> Optional["AppContext"]:
        """获取应用上下文"""
        return self._context

    def _set_loaded(self, loaded: bool, context: Optional["AppContext"] = None) -> None:
        """
        设置加载状态（内部方法，由PluginManager调用）

        Args:
            loaded: 是否已加载
            context: 应用上下文
        """
        self._loaded = loaded
        self._context = context

    def __repr__(self) -> str:
        """插件字符串表示"""
        return f"<Plugin {self.name} v{self.version}>"
