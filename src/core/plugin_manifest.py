# -*- coding: utf-8 -*-
"""
插件清单解析模块

解析 plugin.json 文件，在加载插件前获取元数据和权限声明，
无需执行插件代码即可了解插件信息。

使用方式：
    from src.core.plugin_manifest import PluginManifest

    manifest = PluginManifest.from_file(plugin_dir / "plugin.json")
    if manifest:
        print(manifest.name, manifest.version, manifest.permissions)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.core.permission_manager import Permission, PermissionSet
from src.utils.logger import get_logger

_logger = get_logger(__name__)

MANIFEST_FILENAME = "plugin.json"


@dataclass
class PluginManifest:
    """插件清单

    从 plugin.json 文件解析的插件元数据。

    Attributes:
        name: 插件唯一标识
        version: 版本号
        description: 描述
        author: 作者
        permissions: 声明的权限列表（字符串形式）
        entry: 入口类路径，格式 "module:ClassName" 或 "ClassName"
    """

    name: str = ""
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    permissions: List[str] = field(default_factory=list)
    entry: str = ""

    @classmethod
    def from_file(cls, path: Path) -> Optional["PluginManifest"]:
        """从 plugin.json 文件解析清单

        Args:
            path: plugin.json 文件路径

        Returns:
            PluginManifest 实例，解析失败返回 None
        """
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            _logger.error(f"插件清单 JSON 解析失败 ({path}): {e}")
            return None
        except Exception as e:
            _logger.error(f"读取插件清单失败 ({path}): {e}")
            return None

    @classmethod
    def from_dir(cls, plugin_dir: Path) -> Optional["PluginManifest"]:
        """从插件目录查找并解析 plugin.json

        Args:
            plugin_dir: 插件目录路径

        Returns:
            PluginManifest 实例，无清单文件返回 None
        """
        manifest_path = plugin_dir / MANIFEST_FILENAME
        return cls.from_file(manifest_path)

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        """从字典创建清单

        Args:
            data: 清单数据字典

        Returns:
            PluginManifest 实例
        """
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            permissions=data.get("permissions", []),
            entry=data.get("entry", ""),
        )

    def get_permission_set(self) -> PermissionSet:
        """将声明的权限字符串列表转换为 PermissionSet

        Returns:
            PermissionSet 实例
        """
        perms = []
        for perm_str in self.permissions:
            try:
                perms.append(Permission(perm_str))
            except ValueError:
                _logger.warning(f"未知的权限标识: {perm_str}")
        return PermissionSet.from_list(perms)

    def get_entry_class_name(self) -> str:
        """获取入口类名

        entry 格式支持：
        - "ClassName" — 直接类名
        - "module:ClassName" — 模块:类名（取类名部分）

        Returns:
            类名字符串
        """
        if ":" in self.entry:
            return self.entry.split(":")[-1]
        return self.entry

    def validate(self) -> List[str]:
        """验证清单完整性

        Returns:
            错误列表，空列表表示通过验证
        """
        errors = []
        if not self.name:
            errors.append("缺少必填字段: name")
        if not self.version:
            errors.append("缺少必填字段: version")
        if self.name and not self.name.replace("_", "").replace("-", "").isalnum():
            errors.append(f"name 包含非法字符: {self.name}")
        return errors

    def to_display_dict(self) -> dict:
        """转换为用于显示的字典"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "permissions": self.permissions,
            "entry": self.entry,
        }
