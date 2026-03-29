# -*- coding: utf-8 -*-
"""
插件管理器模块

负责插件的发现、加载和管理：
- 扫描插件目录
- 动态加载插件模块
- 验证插件类
- 管理插件生命周期

使用方式：
    from src.core.plugin_manager import PluginManager

    manager = PluginManager(Path("plugins"))

    # 发现插件
    plugins = manager.discover_plugins()

    # 加载插件
    instance = manager.load_plugin("my_plugin")

    # 卸载插件
    manager.unload_plugin("my_plugin")
"""

import importlib.util
import threading
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set, Type, cast

if TYPE_CHECKING:
    from src.core.app_context import AppContext

from src.core.event_bus import EventBus, EventType
from src.core.permission_manager import Permission, PermissionManager, PermissionSet
from src.core.plugin_base import PluginBase
from src.storage.repositories import PluginPermissionRepository, PluginRepository
from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)

_logger = get_logger(__name__)

# ================================================================
# Global singleton management for PluginManager
# ================================================================
_global_plugin_manager: Optional["PluginManager"] = None
_global_lock = threading.Lock()


def get_plugin_manager() -> "PluginManager":
    """Return the global PluginManager singleton.

    The singleton must be initialized via init_plugin_manager(...) first.
    This function will raise a RuntimeError if called before initialization.
    """
    with _global_lock:
        if _global_plugin_manager is None:
            raise RuntimeError(
                "PluginManager is not initialized. Call init_plugin_manager(...) to initialize the singleton before use."
            )
        return _global_plugin_manager


def init_plugin_manager(
    plugins_dir,
    event_bus: Optional[EventBus] = None,
    permission_manager: Optional[PermissionManager] = None,
    repository: Optional[PluginPermissionRepository] = None,
    plugin_repository: Optional[PluginRepository] = None,
) -> "PluginManager":
    """Initialize and return the global PluginManager singleton.

    This should be called once during application startup before any use of
    the singleton via get_plugin_manager(). Subsequent calls will re-create the
    singleton (with a warning).
    """
    global _global_plugin_manager

    with _global_lock:
        if _global_plugin_manager is not None:
            _logger.warning("PluginManager singleton is already initialized. Reinitializing...")

        _global_plugin_manager = PluginManager(
            plugins_dir=Path(plugins_dir),
            event_bus=event_bus,
            permission_manager=permission_manager,
            repository=repository,
            plugin_repository=plugin_repository,
        )

        _logger.info(f"PluginManager singleton initialized: {_global_plugin_manager.plugins_dir}")
        return _global_plugin_manager


def shutdown_plugin_manager() -> None:
    """Shut down (clear) the global PluginManager singleton."""
    global _global_plugin_manager
    with _global_lock:
        _global_plugin_manager = None
        _logger.info("PluginManager singleton has been shut down.")


def reset_plugin_manager_for_testing() -> None:
    """Reset the global PluginManager singleton for testing purposes."""
    with _global_lock:
        global _global_plugin_manager
        _global_plugin_manager = None
        _logger.info("PluginManager singleton reset for testing.")


@dataclass
class PluginInfo:
    """
    插件信息

    存储已发现插件的基本信息

    Attributes:
        name: 插件名称
        module_path: 模块路径
        plugin_class: 插件类（加载后）
        instance: 插件实例（加载后）
        loaded: 是否已加载
    """

    name: str
    module_path: Path
    plugin_class: Optional[Type[PluginBase]] = None
    instance: Optional[PluginBase] = None
    loaded: bool = False


class PluginLoadError(Exception):
    """插件加载错误"""

    pass


class PluginManager:
    """
    插件管理器

    管理插件的生命周期，包括：
    - 发现：扫描插件目录，识别有效的插件模块
    - 加载：动态导入模块，实例化插件类
    - 权限检查：验证插件所需权限是否已授权
    - 卸载：清理插件资源

    Example:
        manager = PluginManager(
            plugins_dir=Path("plugins"),
            event_bus=event_bus,
            permission_manager=permission_manager,
        )

        # 发现所有插件
        discovered = manager.discover_plugins()

        # 加载特定插件
        manager.load_plugin("my_plugin")

        # 获取插件实例
        plugin = manager.get_plugin("my_plugin")

        # 卸载插件
        manager.unload_plugin("my_plugin")
    """

    def __init__(
        self,
        plugins_dir: Path,
        event_bus: Optional[EventBus] = None,
        permission_manager: Optional[PermissionManager] = None,
        repository: Optional[PluginPermissionRepository] = None,
        plugin_repository: Optional[PluginRepository] = None,
    ):
        """Deprecated: Direct construction of PluginManager is discouraged.

        This constructor remains for backward compatibility, but the preferred
        workflow is to create a singleton via init_plugin_manager(...) and
        access it via get_plugin_manager().

        Args:
            plugins_dir: 插件目录路径
            event_bus: 事件总线（可选，用于发布插件事件）
            permission_manager: 权限管理器（可选，用于权限检查）
            repository: 持久化存储库（可选，用于持久化插件权限）
            plugin_repository: 持久化存储库（可选，用于持久化插件状态）
        """
        self.plugins_dir = Path(plugins_dir)
        self.event_bus = event_bus
        self.permission_manager = permission_manager
        self._repository = repository
        self._plugin_repository = plugin_repository
        self._context: Optional["AppContext"] = None

        # 已发现的插件:插件名 -> PluginInfo
        self._discovered: Dict[str, PluginInfo] = {}
        # 已加载的插件:插件名 -> 插件实例
        self._loaded: Dict[str, PluginBase] = {}

        # 确保插件目录存在
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        _logger.debug(f"插件管理器初始化: {self.plugins_dir}")

    def discover_plugins(self) -> List[str]:
        """
        发现插件目录中的所有插件

        扫描插件目录，查找包含 PluginBase 子类的模块

        Returns:
            发现的插件名称列表

        Note:
            - 扫描目录下的所有 Python 模块
            - 验证模块是否包含有效的插件类
            - 不会加载插件，仅记录信息
        """
        discovered_names: List[str] = []

        if not self.plugins_dir.exists():
            _logger.warning(f"插件目录不存在: {self.plugins_dir}")
            return discovered_names

        # 遍历插件目录
        for item in self.plugins_dir.iterdir():
            # 跳过非目录和隐藏目录
            if not item.is_dir() or item.name.startswith("_"):
                continue

            # 检查是否包含 __init__.py
            init_file = item / "__init__.py"
            if not init_file.exists():
                _logger.debug(f"跳过非插件目录: {item}")
                continue

            # 尝试发现插件类
            try:
                plugin_class = self._discover_plugin_class(item)
                if plugin_class is not None:
                    plugin_name = plugin_class.name

                    # 检查是否重复
                    if plugin_name in self._discovered:
                        _logger.warning(
                            f"插件名称冲突: '{plugin_name}' 已存在于 "
                            f"{self._discovered[plugin_name].module_path}"
                        )
                        continue

                    # 记录发现的插件
                    self._discovered[plugin_name] = PluginInfo(
                        name=plugin_name,
                        module_path=item,
                        plugin_class=plugin_class,
                    )
                    discovered_names.append(plugin_name)

                    _logger.info(f"发现插件: {plugin_name} v{plugin_class.version} ({item})")
            except Exception as e:
                _logger.error(f"发现插件失败: {item}, 错误: {e}", exc_info=True)

        return discovered_names

    def _discover_plugin_class(self, plugin_dir: Path) -> Optional[Type[PluginBase]]:
        """
        在插件目录中发现插件类

        Args:
            plugin_dir: 插件目录路径

        Returns:
            找到的插件类，如果没有则返回 None
        """
        init_file = plugin_dir / "__init__.py"

        # 动态导入模块
        spec = importlib.util.spec_from_file_location(
            f"plugins.{plugin_dir.name}",
            init_file,
        )
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            _logger.error(f"加载插件模块失败: {init_file}, 错误: {e}")
            return None

        # 查找 PluginBase 的子类
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            # 检查是否是类且是 PluginBase 的子类（但不是 PluginBase 本身）
            if isinstance(attr, type) and issubclass(attr, PluginBase) and attr is not PluginBase:
                return attr

        return None

    def load_plugin(
        self,
        name: str,
        context: Optional["AppContext"] = None,
    ) -> PluginBase:
        """
        加载插件

        Args:
            name: 插件名称
            context: 应用上下文（传递给插件的 on_load 方法）

        Returns:
            加载的插件实例

        Raises:
            PluginLoadError: 插件加载失败

        Note:
            - 如果插件未发现，会先调用 discover_plugins
            - 权限检查在插件 on_load 之前进行
        """
        # 检查是否已加载
        if name in self._loaded:
            _logger.debug(f"插件已加载: {name}")
            return self._loaded[name]

        # 获取插件信息
        info = self._discovered.get(name)
        if info is None:
            raise PluginLoadError(f"未找到插件: {name}")

        if info.plugin_class is None:
            raise PluginLoadError(f"插件类未加载: {name}")

        try:
            # 实例化插件
            instance = info.plugin_class()

            # 权限检查（如果提供了权限管理器）
            if self.permission_manager:
                required_perms = info.plugin_class.get_required_permissions()
                self._check_and_grant_permissions(name, required_perms)
                granted_permissions = self.permission_manager.get_granted_permissions(name)
            else:
                granted_permissions = set()

            # 设置加载状态
            instance._set_loaded(True, context)

            # 调用插件的 on_load 方法
            if context is not None:
                from src.core.permission_proxy import PermissionProxy

                proxy = PermissionProxy(
                    context=context,
                    plugin_name=name,
                    granted_permissions=granted_permissions,
                    config_repository=self._plugin_repository,
                )
                instance.on_load(proxy)
            else:
                # 没有上下文时直接调用（测试场景）
                instance.on_load(context)

            # 记录已加载
            self._loaded[name] = instance
            info.loaded = True
            info.instance = instance

            # 发布事件
            if self.event_bus:
                self.event_bus.publish(
                    EventType.PLUGIN_LOADED,
                    {"name": name},
                )

            _logger.info(f"插件加载成功: {name}")

            return instance

        except Exception as e:
            _logger.error(f"插件加载失败: {name}, 错误: {e}", exc_info=True)
            raise PluginLoadError(f"插件加载失败: {name}") from e

    def _check_and_grant_permissions(
        self,
        plugin_name: str,
        required_perms: PermissionSet,
    ) -> None:
        """
        检查并授权插件权限

        Args:
            plugin_name: 插件名称
            required_perms: 所需权限集合

        Note:
            Phase 1 简化实现：自动授权所有请求的权限
            Phase 4 将实现用户确认对话框
        """
        if self.permission_manager is None:
            _logger.warning("权限管理器未初始化，跳过权限检查")
            return

        # 获取已授权的权限
        granted = self.permission_manager.get_granted_permissions(plugin_name)

        # 计算需要新授权的权限
        new_perms = set(required_perms.permissions) - granted

        if new_perms:
            # Phase 1: 自动授权（Phase 4 将添加用户确认）
            self.permission_manager.grant_all(plugin_name, new_perms)

            perm_values = [p.value for p in new_perms]
            _logger.info(f"插件 '{plugin_name}' 获得权限: {perm_values}")

    def unload_plugin(self, name: str) -> bool:
        """
        卸载插件

        Args:
            name: 插件名称

        Returns:
            是否成功卸载
        """
        if name not in self._loaded:
            _logger.warning(f"插件未加载: {name}")
            return False

        instance = self._loaded[name]

        try:
            # 调用 on_unload
            instance.on_unload()

            # 清理状态
            instance._set_loaded(False, None)

            # 从已加载列表移除
            del self._loaded[name]

            # 更新发现信息
            if name in self._discovered:
                self._discovered[name].instance = None
                self._discovered[name].loaded = False

            _logger.info(f"插件卸载成功: {name}")

            # 发布事件
            if self.event_bus:
                self.event_bus.publish(
                    EventType.PLUGIN_UNLOADED,
                    {"name": name},
                )

            return True

        except Exception as e:
            _logger.error(f"插件卸载失败: {name}, 错误: {e}", exc_info=True)
            return False

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """
        获取已加载的插件实例

        Args:
            name: 插件名称

        Returns:
            插件实例，如果未加载则返回 None
        """
        return self._loaded.get(name)

    def get_loaded_plugins(self) -> Dict[str, PluginBase]:
        """
        获取所有已加载的插件

        Returns:
            插件名到实例的映射（副本）
        """
        return self._loaded.copy()

    def get_discovered_plugins(self) -> Dict[str, PluginInfo]:
        """
        获取所有已发现的插件信息

        Returns:
            插件名到信息的映射（副本）
        """
        return self._discovered.copy()

    def is_loaded(self, name: str) -> bool:
        """
        检查插件是否已加载

        Args:
            name: 插件名称

        Returns:
            是否已加载
        """
        return name in self._loaded

    def enable_plugin(self, name: str) -> bool:
        """
        启用插件

        Args:
            name: 插件名称

        Returns:
            是否成功启用
        """
        if name not in self._discovered:
            _logger.warning(f"插件未发现: {name}")
            return False

        # 先保存启用状态到数据库
        if self._repository:
            self._repository.set_plugin_enabled(name, True)

        if name in self._loaded:
            _logger.debug(f"插件已加载: {name}")
            return True

        try:
            self.load_plugin(name, self._context)
            _logger.info(f"插件已启用: {name}")
            return True
        except Exception as e:
            _logger.error(f"启用插件失败: {name}", exc_info=True)
            return False

    def disable_plugin(self, name: str) -> bool:
        """
        禁用插件

        Args:
            name: 插件名称

        Returns:
            是否成功禁用
        """
        # 先保存禁用状态到数据库
        if self._repository:
            self._repository.set_plugin_enabled(name, False)

        if name not in self._loaded:
            _logger.debug(f"插件未加载: {name}")
            return True

        try:
            self.unload_plugin(name)
            _logger.info(f"插件已禁用: {name}")
            return True
        except Exception as e:
            _logger.error(f"禁用插件失败: {name}", exc_info=True)
            return False

    def unload_all(self) -> None:
        """
        卸载所有插件

        用于应用关闭时清理资源
        """
        plugin_names = list(self._loaded.keys())

        for name in plugin_names:
            self.unload_plugin(name)

        _logger.info("所有插件已卸载")

    def check_permissions_needed(self, name: str) -> Optional[Set[Permission]]:
        """
        检查插件是否需要新的权限授权

        Args:
            name: 插件名称

        Returns:
            需要授权的权限集合，如果不需要或插件不存在则返回 None
        """
        if name not in self._discovered:
            return None

        info = self._discovered[name]
        if info.plugin_class is None:
            return None

        if self.permission_manager is None:
            return None

        required_perms = info.plugin_class.get_required_permissions()
        granted = self.permission_manager.get_granted_permissions(name)

        new_perms = set(required_perms.permissions) - granted

        return new_perms if new_perms else None

    def get_plugin_info_for_permission_dialog(self, name: str) -> Optional[dict]:
        """
        获取插件信息用于权限对话框显示

        Args:
            name: 插件名称

        Returns:
            插件信息字典，包含 version、description、author 等字段
        """
        if name not in self._discovered:
            return None

        info = self._discovered[name]
        if info.plugin_class is None:
            return None

        return {
            "version": info.plugin_class.version,
            "description": info.plugin_class.description,
            "author": info.plugin_class.author,
        }

    def get_plugin_required_permissions(self, name: str) -> Optional[Set[Permission]]:
        """
        获取插件所需的权限集合

        Args:
            name: 插件名称

        Returns:
            所需权限集合，如果插件不存在则返回 None
        """
        if name not in self._discovered:
            return None

        info = self._discovered[name]
        if info.plugin_class is None:
            return None

        return set(info.plugin_class.get_required_permissions().permissions)

    def load_enabled_plugins(
        self,
        context: Optional["AppContext"] = None,
        on_permission_request: Optional[Callable[[str, Set[Permission]], bool]] = None,
    ) -> Dict[str, bool]:
        """
        根据数据库中的启用状态加载插件

        Args:
            context: 应用上下文
            on_permission_request: 权限请求回调函数
                - 参数: plugin_name, required_permissions
                - 返回: True 表示授权，False 表示拒绝
                - 如果为 None，则自动授权所有权限

        Returns:
            插件名 -> 是否成功加载的映射

        Note:
            - 从数据库读取每个插件的启用状态
            - 只加载启用状态的插件
            - 对于需要新权限的插件，调用 on_permission_request 回调
        """
        results: Dict[str, bool] = {}

        if self._repository is None:
            _logger.warning("未设置 repository，无法读取启用状态")
            return results

        # 保存 context 供 enable_plugin 使用
        self._context = context

        for name, info in self._discovered.items():
            # 从数据库读取启用状态
            enabled = self._repository.get_plugin_enabled(name)

            if not enabled:
                _logger.debug(f"插件 '{name}' 未启用，跳过加载")
                results[name] = False
                continue

            # 检查是否需要新的权限授权
            needed_perms = self.check_permissions_needed(name)

            if needed_perms:
                # 需要新权限
                if on_permission_request is not None:
                    # 调用回调函数请求用户确认
                    granted = on_permission_request(name, needed_perms)

                    if not granted:
                        _logger.info(f"用户拒绝授权插件 '{name}' 的权限")
                        results[name] = False
                        continue
                else:
                    # 没有回调函数，自动授权
                    _logger.info(f"自动授权插件 '{name}' 的权限: {[p.value for p in needed_perms]}")

            # 加载插件
            try:
                self.load_plugin(name, context)
                results[name] = True
                _logger.info(f"插件 '{name}' 加载成功")
            except Exception as e:
                _logger.error(f"插件 '{name}' 加载失败: {e}", exc_info=True)
                results[name] = False

        return results

    # Alias for backward compatibility
    unload_all_plugins = unload_all
