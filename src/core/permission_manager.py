# -*- coding: utf-8 -*-
"""
权限管理模块

提供插件权限管理功能，包括：
- 权限定义（Permission枚举）
- 权限集合（PermissionSet）
- 权限管理器（PermissionManager）

权限类型：
- 文件系统权限：FILE_READ, FILE_WRITE
- 网络权限：NETWORK
- Agent权限：AGENT_TOOL, AGENT_MCP, AGENT_SKILL, AGENT_CHAT
- 事件权限：EVENT_SUBSCRIBE, EVENT_PUBLISH
- 节点权限：NODE_READ, NODE_REGISTER
- 存储权限：STORAGE_READ, STORAGE_WRITE
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Set, Union

from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


class Permission(Enum):
    """
    权限枚举

    定义插件可能需要的所有权限类型，遵循最小权限原则

    Categories:
        文件系统: FILE_READ, FILE_WRITE
        网络: NETWORK
        Agent: AGENT_TOOL, AGENT_MCP, AGENT_SKILL, AGENT_CHAT
        事件: EVENT_SUBSCRIBE, EVENT_PUBLISH
        节点: NODE_READ, NODE_REGISTER
        存储: STORAGE_READ, STORAGE_WRITE
    """

    # 文件系统权限
    FILE_READ = "file.read"  # 读取文件
    FILE_WRITE = "file.write"  # 写入文件

    # 网络权限
    NETWORK = "network"  # 网络访问

    # Agent相关权限
    AGENT_TOOL = "agent.tool"  # 注册/注销Agent工具
    AGENT_MCP = "agent.mcp"  # 配置MCP服务
    AGENT_SKILL = "agent.skill"  # 加载/卸载Skill
    AGENT_CHAT = "agent.chat"  # 调用Agent对话

    # 事件系统权限
    EVENT_SUBSCRIBE = "event.subscribe"  # 订阅事件
    EVENT_PUBLISH = "event.publish"  # 发布事件

    # 节点权限
    NODE_READ = "node.read"  # 读取节点信息
    NODE_REGISTER = "node.register"  # 注册节点

    # 存储权限
    STORAGE_READ = "storage.read"  # 读取持久化数据
    STORAGE_WRITE = "storage.write"  # 写入持久化数据


@dataclass(frozen=True)
class PermissionSet:
    """
    权限集合

    用于声明和检查插件所需的权限集合。
    使用 frozen=True 确保权限集合不可变。

    Attributes:
        permissions: 权限集合

    Example:
        # 从列表创建权限集合
        perms = PermissionSet.from_list([
            Permission.FILE_READ,
            Permission.NETWORK
        ])

        # 检查是否包含某权限
        if perms.has(Permission.FILE_READ):
            print("有文件读取权限")

        # 合并两个权限集合
        combined = perms | other_perms
    """

    permissions: Set[Permission] = field(default_factory=set)

    @classmethod
    def from_list(cls, perms: list[Union[Permission, str]]) -> "PermissionSet":
        """
        从列表创建权限集合

        Args:
            perms: 权限列表，可以是 Permission 枚举或字符串

        Returns:
            新的 PermissionSet 实例

        Example:
            perms = PermissionSet.from_list([
                Permission.FILE_READ,
                "network"  # 也可以使用字符串
            ])
        """
        return cls(permissions={Permission(p) if isinstance(p, str) else p for p in perms})

    @classmethod
    def empty(cls) -> "PermissionSet":
        """
        创建空权限集合

        Returns:
            空的 PermissionSet 实例
        """
        return cls(permissions=set())

    def has(self, permission: Permission) -> bool:
        """
        检查是否包含某权限

        Args:
            permission: 要检查的权限

        Returns:
            是否包含该权限
        """
        return permission in self.permissions

    def has_all(self, permissions: Set[Permission]) -> bool:
        """
        检查是否包含所有指定权限

        Args:
            permissions: 要检查的权限集合

        Returns:
            是否包含所有权限
        """
        return permissions.issubset(self.permissions)

    def has_any(self, permissions: Set[Permission]) -> bool:
        """
        检查是否包含任一指定权限

        Args:
            permissions: 要检查的权限集合

        Returns:
            是否包含任一权限
        """
        return bool(self.permissions & permissions)

    def __or__(self, other: "PermissionSet") -> "PermissionSet":
        """
        权限集合并集

        Args:
            other: 另一个权限集合

        Returns:
            合并后的新权限集合
        """
        return PermissionSet(self.permissions | other.permissions)

    def __and__(self, other: "PermissionSet") -> "PermissionSet":
        """
        权限集合交集

        Args:
            other: 另一个权限集合

        Returns:
            交集权限集合
        """
        return PermissionSet(self.permissions & other.permissions)

    def __sub__(self, other: "PermissionSet") -> "PermissionSet":
        """
        权限集合差集

        Args:
            other: 另一个权限集合

        Returns:
            差集权限集合
        """
        return PermissionSet(self.permissions - other.permissions)

    def __len__(self) -> int:
        """返回权限数量"""
        return len(self.permissions)

    def __contains__(self, permission: Permission) -> bool:
        """支持 in 操作符"""
        return self.has(permission)

    def __iter__(self):
        """支持迭代"""
        return iter(self.permissions)


class PermissionDeniedError(Exception):
    """
    权限拒绝异常

    当插件尝试执行未授权的操作时抛出

    Attributes:
        permission: 被拒绝的权限
        message: 错误消息
    """

    def __init__(self, permission: Permission, message: str = "") -> None:
        self.permission = permission
        self.message = message or f"缺少权限: {permission.value}"
        super().__init__(self.message)


class PermissionManager:
    """
    权限管理器

    管理插件的权限授权，支持：
    - 授权/撤销权限
    - 检查权限
    - 持久化权限记录（需要配合StorageService使用）

    Example:
        pm = PermissionManager()

        # 授权
        pm.grant("my_plugin", Permission.FILE_READ)

        # 检查
        if pm.check("my_plugin", Permission.FILE_READ):
            print("有权限")

        # 撤销
        pm.revoke("my_plugin", Permission.FILE_READ)
    """

    def __init__(self):
        """初始化权限管理器"""
        # 插件权限映射：插件名 -> 权限集合
        self._granted: Dict[str, Set[Permission]] = {}

        _logger.debug("权限管理器初始化完成")

    def grant(self, plugin_name: str, permission: Permission) -> None:
        """
        授权给插件

        Args:
            plugin_name: 插件名称
            permission: 要授权的权限

        Example:
            pm.grant("my_plugin", Permission.FILE_READ)
        """
        if plugin_name not in self._granted:
            self._granted[plugin_name] = set()

        self._granted[plugin_name].add(permission)

        _logger.info(f"授权: 插件 '{plugin_name}' 获得权限 '{permission.value}'")

    def grant_all(self, plugin_name: str, permissions: Set[Permission]) -> None:
        """
        批量授权给插件

        Args:
            plugin_name: 插件名称
            permissions: 要授权的权限集合
        """
        if plugin_name not in self._granted:
            self._granted[plugin_name] = set()

        self._granted[plugin_name].update(permissions)

        perm_values = [p.value for p in permissions]
        _logger.info(f"批量授权: 插件 '{plugin_name}' 获得权限: {perm_values}")

    def revoke(self, plugin_name: str, permission: Permission) -> bool:
        """
        撤销插件权限

        Args:
            plugin_name: 插件名称
            permission: 要撤销的权限

        Returns:
            是否成功撤销（如果插件没有该权限则返回False）
        """
        if plugin_name not in self._granted:
            return False

        if permission in self._granted[plugin_name]:
            self._granted[plugin_name].remove(permission)
            _logger.info(f"撤销: 插件 '{plugin_name}' 失去权限 '{permission.value}'")
            return True

        return False

    def revoke_all(self, plugin_name: str) -> None:
        """
        撤销插件所有权限

        Args:
            plugin_name: 插件名称
        """
        if plugin_name in self._granted:
            del self._granted[plugin_name]
            _logger.info(f"撤销: 插件 '{plugin_name}' 的所有权限")

    def check(self, plugin_name: str, permission: Permission) -> bool:
        """
        检查插件是否拥有某权限

        Args:
            plugin_name: 插件名称
            permission: 要检查的权限

        Returns:
            是否拥有该权限
        """
        granted = self._granted.get(plugin_name, set())
        return permission in granted

    def check_all(self, plugin_name: str, permissions: Set[Permission]) -> bool:
        """
        检查插件是否拥有所有指定权限

        Args:
            plugin_name: 插件名称
            permissions: 要检查的权限集合

        Returns:
            是否拥有所有权限
        """
        granted = self._granted.get(plugin_name, set())
        return permissions.issubset(granted)

    def get_granted_permissions(self, plugin_name: str) -> Set[Permission]:
        """
        获取插件已授权的所有权限

        Args:
            plugin_name: 插件名称

        Returns:
            已授权的权限集合（副本）
        """
        return self._granted.get(plugin_name, set()).copy()

    def get_all_plugin_permissions(self) -> Dict[str, Set[Permission]]:
        """
        获取所有插件的权限配置

        Returns:
            插件名到权限集合的映射（副本）
        """
        return {name: perms.copy() for name, perms in self._granted.items()}

    def require(self, plugin_name: str, permission: Permission) -> None:
        """
        要求权限，无权限时抛出异常

        Args:
            plugin_name: 插件名称
            permission: 要求的权限

        Raises:
            PermissionDeniedError: 当插件没有该权限时
        """
        if not self.check(plugin_name, permission):
            raise PermissionDeniedError(
                permission, f"插件 '{plugin_name}' 需要权限 '{permission.value}'"
            )
