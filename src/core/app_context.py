# -*- coding: utf-8 -*-
"""
应用上下文模块

提供应用程序的核心上下文，包括：
- EventBus: 事件系统
- PluginManager: 插件管理
- PermissionManager: 权限管理
- Database: 数据库连接
- Storage: 存储服务

上下文是插件访问程序功能的唯一入口。

使用方式：
    from src.core.app_context import AppContext

    # 创建上下文
    context = AppContext()
    context.initialize()

    # 使用上下文
    context.event_bus.publish(EventType.APP_STARTED, {})

    # 关闭
    context.shutdown()
"""

from pathlib import Path
from typing import Optional

from src.core.event_bus import EventBus, EventType
from src.core.permission_manager import Permission, PermissionManager, PermissionSet
from src.core.plugin_manager import PluginManager
from src.storage.database import Database
from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


class AppContext:
    """
    应用上下文

    作为应用程序的核心容器，提供：
    - 统一的服务访问入口
    - 服务初始化和关闭管理
    - 权限检查接口（供插件使用）

    Example:
        # 创建并初始化
        context = AppContext()
        context.initialize()

        # 访问服务
        bus = context.event_bus
        plugins = context.plugin_manager

        # 关闭
        context.shutdown()

    Note:
        - initialize() 必须在使用前调用
        - shutdown() 应在应用关闭时调用
    """

    # 默认配置
    DEFAULT_DATA_DIR = Path("data")
    DEFAULT_PLUGINS_DIR = Path("plugins")
    DEFAULT_DB_NAME = "app.db"

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        plugins_dir: Optional[Path] = None,
    ):
        """
        初始化应用上下文

        Args:
            data_dir: 数据目录，存储数据库等文件
            plugins_dir: 插件目录
        """
        # 目录配置
        self.data_dir = Path(data_dir) if data_dir else self.DEFAULT_DATA_DIR
        self.plugins_dir = Path(plugins_dir) if plugins_dir else self.DEFAULT_PLUGINS_DIR

        # 核心服务（延迟初始化）
        self._event_bus: Optional[EventBus] = None
        self._permission_manager: Optional[PermissionManager] = None
        self._plugin_manager: Optional[PluginManager] = None
        self._database: Optional[Database] = None

        # 状态
        self._initialized: bool = False

        _logger.debug(f"AppContext 创建: data_dir={self.data_dir}, plugins_dir={self.plugins_dir}")

    @property
    def event_bus(self) -> EventBus:
        """获取事件总线"""
        if self._event_bus is None:
            raise RuntimeError("AppContext 未初始化，请先调用 initialize()")
        return self._event_bus

    @property
    def permission_manager(self) -> PermissionManager:
        """获取权限管理器"""
        if self._permission_manager is None:
            raise RuntimeError("AppContext 未初始化，请先调用 initialize()")
        return self._permission_manager

    @property
    def plugin_manager(self) -> PluginManager:
        """获取插件管理器"""
        if self._plugin_manager is None:
            raise RuntimeError("AppContext 未初始化，请先调用 initialize()")
        return self._plugin_manager

    @property
    def database(self) -> Database:
        """获取数据库"""
        if self._database is None:
            raise RuntimeError("AppContext 未初始化，请先调用 initialize()")
        return self._database

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    def initialize(self) -> None:
        """
        初始化所有服务

        初始化顺序：
        1. 创建数据目录
        2. 初始化数据库
        3. 初始化事件总线
        4. 初始化权限管理器
        5. 初始化插件管理器
        6. 发布应用启动事件

        Raises:
            RuntimeError: 如果已初始化
        """
        if self._initialized:
            raise RuntimeError("AppContext 已初始化")

        _logger.info("开始初始化 AppContext...")

        # 1. 创建数据目录
        self.data_dir.mkdir(parents=True, exist_ok=True)
        _logger.debug(f"数据目录: {self.data_dir}")

        # 2. 初始化数据库
        db_path = self.data_dir / self.DEFAULT_DB_NAME
        self._database = Database(db_path)
        self._database.create_tables()
        _logger.info(f"数据库初始化完成: {db_path}")

        # 3. 初始化事件总线
        self._event_bus = EventBus()
        _logger.debug("事件总线初始化完成")

        # 4. 初始化权限管理器
        self._permission_manager = PermissionManager()
        _logger.debug("权限管理器初始化完成")

        # 5. 初始化插件管理器
        self._plugin_manager = PluginManager(
            plugins_dir=self.plugins_dir,
            event_bus=self._event_bus,
            permission_manager=self._permission_manager,
        )
        _logger.debug("插件管理器初始化完成")

        # 6. 标记为已初始化
        self._initialized = True

        # 7. 发布应用启动事件
        self._event_bus.publish(EventType.APP_STARTED, {})

        _logger.info("AppContext 初始化完成")

    def shutdown(self) -> None:
        """
        关闭所有服务

        关闭顺序：
        1. 卸载所有插件
        2. 发布应用关闭事件
        3. 关闭数据库

        Note:
            可以安全地多次调用
        """
        if not self._initialized:
            return

        _logger.info("开始关闭 AppContext...")

        # 1. 卸载所有插件
        if self._plugin_manager:
            self._plugin_manager.unload_all()

        # 2. 发布应用关闭事件
        if self._event_bus:
            self._event_bus.publish(EventType.APP_SHUTDOWN, {})
            self._event_bus.clear_all()

        # 3. 关闭数据库
        if self._database:
            self._database.close()

        # 清理状态
        self._plugin_manager = None
        self._database = None
        self._event_bus = None
        self._permission_manager = None
        self._initialized = False

        _logger.info("AppContext 关闭完成")

    # ============ 权限检查接口（供插件使用）============

    def check_permission(
        self,
        plugin_name: str,
        permission: Permission,
    ) -> bool:
        """
        检查插件是否拥有某权限

        Args:
            plugin_name: 插件名称
            permission: 要检查的权限

        Returns:
            是否拥有该权限
        """
        return self.permission_manager.check(plugin_name, permission)

    def require_permission(
        self,
        plugin_name: str,
        permission: Permission,
    ) -> None:
        """
        要求权限，无权限时抛出异常

        Args:
            plugin_name: 插件名称
            permission: 要求的权限

        Raises:
            PermissionDeniedError: 无权限时
        """
        self.permission_manager.require(plugin_name, permission)

    # ============ 上下文管理器支持 ============

    def __enter__(self) -> "AppContext":
        """上下文管理器入口"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.shutdown()


# 全局上下文实例（单例）
_global_context: Optional[AppContext] = None


def get_context() -> AppContext:
    """
    获取全局应用上下文

    Returns:
        全局 AppContext 实例

    Raises:
        RuntimeError: 如果上下文未初始化
    """
    global _global_context
    if _global_context is None:
        raise RuntimeError("全局上下文未初始化")
    return _global_context


def init_context(
    data_dir: Optional[Path] = None,
    plugins_dir: Optional[Path] = None,
) -> AppContext:
    """
    初始化全局应用上下文

    Args:
        data_dir: 数据目录
        plugins_dir: 插件目录

    Returns:
        初始化后的全局上下文

    Raises:
        RuntimeError: 如果上下文已初始化
    """
    global _global_context
    if _global_context is not None:
        raise RuntimeError("全局上下文已初始化")

    _global_context = AppContext(data_dir=data_dir, plugins_dir=plugins_dir)
    _global_context.initialize()
    return _global_context


def shutdown_context() -> None:
    """
    关闭全局应用上下文
    """
    global _global_context
    if _global_context is not None:
        _global_context.shutdown()
        _global_context = None
