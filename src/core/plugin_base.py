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

    生命周期设计：
      - on_enable / on_disable：插件启用与禁用的核心生命周期方法（为未来的统一入口，向后兼容其他接口）
      - on_load / on_unload：向后兼容的加载/卸载接口，内部会调用 on_enable / on_disable 以保持兼容性

    All plugins must inherit from this class and implement the abstract methods.

    Class Attributes:
        name: 插件唯一标识（必填）
        version: 插件版本号（必填）
        description: 插件描述（可选）
        author: 作者信息（可选）
        permissions: 所需权限集合（默认为空）

    Abstract Methods:
        on_enable: 插件启用时调用（主生命周期入口）
        on_disable: 插件禁用时调用

    Backward-compatibility:
        on_load: 已废弃的加载入口，默认实现会调用 on_enable 以保持向后兼容
        on_unload: 已废弃的卸载入口，默认实现会调用 on_disable 以保持向后兼容

    Example:
        class MyPlugin(PluginBase):
            name = "my_plugin"
            version = "1.0.0"
            description = "示例插件"
            author = "Developer"

            permissions = PermissionSet.from_list([
                Permission.FILE_READ,
            ])

            def on_enable(self, context: AppContext) -> None:
                # 插件启用时执行
                pass

            def on_disable(self) -> None:
                # 插件禁用时执行
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
    def on_enable(self, context: "PluginContext") -> None:
        """
        Called when the plugin is enabled.

        Args:
            context: Plugin context (PermissionProxy or None), provides restricted access to app resources.
        """
        pass

    @abstractmethod
    def on_disable(self, context: Optional["PluginContext"] = None) -> None:
        """
        Called when the plugin is disabled.

        Args:
            context: Plugin context (PermissionProxy or None), provides restricted access to app resources.
        """
        pass

    # 兼容旧接口：加载时调用，内部会委托到 on_enable 以保持向后兼容
    def on_load(self, context: "PluginContext") -> None:
        """Deprecated: Use on_enable instead. Calls on_enable for backward compatibility."""
        self.on_enable(context)

    # 兼容旧接口：卸载时调用，内部会委托到 on_disable 以保持向后兼容
    def on_unload(self, context: Optional["PluginContext"] = None) -> None:
        """Deprecated: Use on_disable instead. Calls on_disable for backward compatibility."""
        self.on_disable(context)

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
