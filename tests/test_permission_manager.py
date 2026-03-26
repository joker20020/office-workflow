# -*- coding: utf-8 -*-
"""权限管理模块测试"""

import pytest

from src.core.permission_manager import (
    Permission,
    PermissionDeniedError,
    PermissionManager,
    PermissionSet,
)


class TestPermission:
    """测试 Permission 枚举"""

    def test_permission_values(self):
        """测试权限值"""
        assert Permission.FILE_READ.value == "file.read"
        assert Permission.FILE_WRITE.value == "file.write"
        assert Permission.NETWORK.value == "network"
        assert Permission.AGENT_TOOL.value == "agent.tool"
        assert Permission.EVENT_SUBSCRIBE.value == "event.subscribe"
        assert Permission.NODE_READ.value == "node.read"
        assert Permission.STORAGE_READ.value == "storage.read"

    def test_all_permissions_defined(self):
        """测试所有权限都已定义"""
        # 文件权限
        assert hasattr(Permission, "FILE_READ")
        assert hasattr(Permission, "FILE_WRITE")

        # 网络权限
        assert hasattr(Permission, "NETWORK")

        # Agent 权限
        assert hasattr(Permission, "AGENT_TOOL")
        assert hasattr(Permission, "AGENT_MCP")
        assert hasattr(Permission, "AGENT_SKILL")
        assert hasattr(Permission, "AGENT_CHAT")

        # 事件权限
        assert hasattr(Permission, "EVENT_SUBSCRIBE")
        assert hasattr(Permission, "EVENT_PUBLISH")

        # 节点权限
        assert hasattr(Permission, "NODE_READ")
        assert hasattr(Permission, "NODE_REGISTER")

        # 存储权限
        assert hasattr(Permission, "STORAGE_READ")
        assert hasattr(Permission, "STORAGE_WRITE")


class TestPermissionSet:
    """测试 PermissionSet 类"""

    def test_from_list_with_enums(self):
        """测试从枚举列表创建"""
        perms = PermissionSet.from_list(
            [
                Permission.FILE_READ,
                Permission.NETWORK,
            ]
        )

        assert perms.has(Permission.FILE_READ)
        assert perms.has(Permission.NETWORK)
        assert not perms.has(Permission.FILE_WRITE)

    def test_from_list_with_strings(self):
        """测试从字符串列表创建"""
        perms = PermissionSet.from_list(["file.read", "network"])

        assert perms.has(Permission.FILE_READ)
        assert perms.has(Permission.NETWORK)

    def test_from_list_mixed(self):
        """测试从混合列表创建"""
        perms = PermissionSet.from_list(
            [
                Permission.FILE_READ,
                "network",
            ]
        )

        assert perms.has(Permission.FILE_READ)
        assert perms.has(Permission.NETWORK)

    def test_empty(self):
        """测试创建空权限集合"""
        perms = PermissionSet.empty()
        assert len(perms) == 0

    def test_has(self):
        """测试 has 方法"""
        perms = PermissionSet.from_list([Permission.FILE_READ])

        assert perms.has(Permission.FILE_READ)
        assert not perms.has(Permission.FILE_WRITE)

    def test_has_all(self):
        """测试 has_all 方法"""
        perms = PermissionSet.from_list(
            [
                Permission.FILE_READ,
                Permission.FILE_WRITE,
                Permission.NETWORK,
            ]
        )

        assert perms.has_all({Permission.FILE_READ, Permission.FILE_WRITE})
        assert not perms.has_all({Permission.FILE_READ, Permission.AGENT_TOOL})

    def test_has_any(self):
        """测试 has_any 方法"""
        perms = PermissionSet.from_list([Permission.FILE_READ])

        assert perms.has_any({Permission.FILE_READ, Permission.FILE_WRITE})
        assert not perms.has_any({Permission.FILE_WRITE, Permission.NETWORK})

    def test_union(self):
        """测试并集操作"""
        perms1 = PermissionSet.from_list([Permission.FILE_READ])
        perms2 = PermissionSet.from_list([Permission.NETWORK])

        combined = perms1 | perms2

        assert combined.has(Permission.FILE_READ)
        assert combined.has(Permission.NETWORK)

    def test_intersection(self):
        """测试交集操作"""
        perms1 = PermissionSet.from_list([Permission.FILE_READ, Permission.NETWORK])
        perms2 = PermissionSet.from_list([Permission.FILE_READ, Permission.FILE_WRITE])

        intersection = perms1 & perms2

        assert intersection.has(Permission.FILE_READ)
        assert not intersection.has(Permission.NETWORK)
        assert not intersection.has(Permission.FILE_WRITE)

    def test_difference(self):
        """测试差集操作"""
        perms1 = PermissionSet.from_list([Permission.FILE_READ, Permission.NETWORK])
        perms2 = PermissionSet.from_list([Permission.FILE_READ])

        diff = perms1 - perms2

        assert not diff.has(Permission.FILE_READ)
        assert diff.has(Permission.NETWORK)

    def test_len(self):
        """测试长度"""
        perms = PermissionSet.from_list([Permission.FILE_READ, Permission.NETWORK])
        assert len(perms) == 2

    def test_contains(self):
        """测试 in 操作符"""
        perms = PermissionSet.from_list([Permission.FILE_READ])

        assert Permission.FILE_READ in perms
        assert Permission.FILE_WRITE not in perms

    def test_iter(self):
        """测试迭代"""
        perms = PermissionSet.from_list(
            [
                Permission.FILE_READ,
                Permission.NETWORK,
            ]
        )

        permissions = list(perms)
        assert Permission.FILE_READ in permissions
        assert Permission.NETWORK in permissions

    def test_frozen(self):
        """测试不可变"""
        perms = PermissionSet.from_list([Permission.FILE_READ])

        # PermissionSet 是 frozen 的，不能修改内部集合
        # 应该创建新的 PermissionSet 而不是修改现有的
        new_perms = perms | PermissionSet.from_list([Permission.NETWORK])

        # 原集合应该不变
        assert not perms.has(Permission.NETWORK)
        # 新集合应该包含 NETWORK
        assert new_perms.has(Permission.NETWORK)


class TestPermissionManager:
    """测试 PermissionManager 类"""

    def test_grant_permission(self):
        """测试授权权限"""
        pm = PermissionManager()

        pm.grant("test_plugin", Permission.FILE_READ)

        assert pm.check("test_plugin", Permission.FILE_READ)

    def test_grant_all(self):
        """测试批量授权"""
        pm = PermissionManager()

        pm.grant_all(
            "test_plugin",
            {
                Permission.FILE_READ,
                Permission.FILE_WRITE,
            },
        )

        assert pm.check("test_plugin", Permission.FILE_READ)
        assert pm.check("test_plugin", Permission.FILE_WRITE)

    def test_revoke_permission(self):
        """测试撤销权限"""
        pm = PermissionManager()

        pm.grant("test_plugin", Permission.FILE_READ)
        result = pm.revoke("test_plugin", Permission.FILE_READ)

        assert result is True
        assert not pm.check("test_plugin", Permission.FILE_READ)

    def test_revoke_nonexistent_returns_false(self):
        """测试撤销不存在的权限返回False"""
        pm = PermissionManager()

        result = pm.revoke("nonexistent_plugin", Permission.FILE_READ)
        assert result is False

    def test_revoke_all(self):
        """测试撤销所有权限"""
        pm = PermissionManager()

        pm.grant_all(
            "test_plugin",
            {
                Permission.FILE_READ,
                Permission.FILE_WRITE,
            },
        )
        pm.revoke_all("test_plugin")

        assert not pm.check("test_plugin", Permission.FILE_READ)
        assert not pm.check("test_plugin", Permission.FILE_WRITE)

    def test_check_all(self):
        """测试检查所有权限"""
        pm = PermissionManager()

        pm.grant_all(
            "test_plugin",
            {
                Permission.FILE_READ,
                Permission.FILE_WRITE,
            },
        )

        assert pm.check_all(
            "test_plugin",
            {
                Permission.FILE_READ,
                Permission.FILE_WRITE,
            },
        )
        assert not pm.check_all(
            "test_plugin",
            {
                Permission.FILE_READ,
                Permission.NETWORK,
            },
        )

    def test_get_granted_permissions(self):
        """测试获取已授权权限"""
        pm = PermissionManager()

        pm.grant_all(
            "test_plugin",
            {
                Permission.FILE_READ,
                Permission.FILE_WRITE,
            },
        )

        granted = pm.get_granted_permissions("test_plugin")

        assert Permission.FILE_READ in granted
        assert Permission.FILE_WRITE in granted
        assert Permission.NETWORK not in granted

    def test_get_granted_permissions_returns_copy(self):
        """测试获取的是副本"""
        pm = PermissionManager()

        pm.grant("test_plugin", Permission.FILE_READ)
        granted = pm.get_granted_permissions("test_plugin")

        # 修改副本不应影响原数据
        granted.add(Permission.NETWORK)

        assert not pm.check("test_plugin", Permission.NETWORK)

    def test_require_raises_on_missing_permission(self):
        """测试 require 在缺少权限时抛出异常"""
        pm = PermissionManager()

        with pytest.raises(PermissionDeniedError) as exc_info:
            pm.require("test_plugin", Permission.FILE_READ)

        assert exc_info.value.permission == Permission.FILE_READ

    def test_require_does_not_raise_with_permission(self):
        """测试 require 在有权限时不抛出异常"""
        pm = PermissionManager()

        pm.grant("test_plugin", Permission.FILE_READ)

        # 不应抛出异常
        pm.require("test_plugin", Permission.FILE_READ)


class TestPermissionDeniedError:
    """测试 PermissionDeniedError 异常"""

    def test_error_message(self):
        """测试错误消息"""
        error = PermissionDeniedError(Permission.FILE_READ)

        assert error.permission == Permission.FILE_READ
        assert "file.read" in error.message
        assert "file.read" in str(error)

    def test_custom_message(self):
        """测试自定义消息"""
        error = PermissionDeniedError(Permission.FILE_READ, "自定义错误消息")

        assert error.message == "自定义错误消息"
