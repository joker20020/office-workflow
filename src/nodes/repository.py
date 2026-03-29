# -*- coding: utf-8 -*-
"""
节点包存储库模块 (Node Package Repository Module)

提供节点包的数据库CRUD操作：
- 创建包记录
- 查询包信息
- 更新包信息
- 删除包记录
- 启用/禁用包

使用方式：
    from src.nodes.repository import NodePackageRepository

    repo = NodePackageRepository(database)

    # 创建包
    package = repo.create({
        "id": "com.example.text-tools",
        "name": "Text Tools",
        "version": "1.0.0",
        "repository_url": "https://github.com/example/text-tools"
    })

    # 获取包
    package = repo.get_by_id("com.example.text-tools")
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy import select, delete

from src.storage.database import Database
from src.storage.models import NodePackageRecord
from src.utils.logger import get_logger

_logger = get_logger(__name__)


def _record_to_dict(record: Optional[NodePackageRecord]) -> Optional[Dict[str, Any]]:
    """将ORM记录转换为字典（在session内调用）"""
    if record is None:
        return None
    return {
        "id": record.id,
        "name": record.name,
        "version": record.version,
        "author": record.author,
        "description": record.description,
        "repository_url": record.repository_url,
        "branch": record.branch,
        "local_path": record.local_path,
        "enabled": record.enabled,
        "installed_at": record.installed_at.isoformat() if record.installed_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


class NodePackageRepository:
    """
    节点包存储库

    提供节点包的数据库持久化操作：
    - create: 创建新包记录
    - get_by_id: 根据ID获取包
    - get_all: 获取所有包（可筛选）
    - update: 更新包信息
    - delete: 删除包记录
    - set_enabled: 设置启用状态
    - exists: 检查包是否存在
    - get_by_repository: 根据仓库URL获取包

    Example:
        >>> repo = NodePackageRepository(database)
        >>> package = repo.create({
        ...     "id": "com.example.text-tools",
        ...     "name": "Text Tools",
        ...     "version": "1.0.0",
        ...     "repository_url": "https://github.com/example/text-tools"
        ... })
    """

    def __init__(self, database: Database):
        self._database = database

    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        创建新的节点包记录

        Args:
            data: 包含包信息的字典，必须包含:
                - id: 包唯一标识
                - name: 显示名称
                - version: 版本号
                - repository_url: Git仓库地址
                可选字段:
                - author: 作者
                - description: 描述
                - branch: 分支（默认: main）
                - local_path: 本地路径
                - enabled: 是否启用（默认: True）

        Returns:
            创建的记录字典，失败返回None

        Example:
            >>> package = repo.create({
            ...     "id": "com.example.text-tools",
            ...     "name": "Text Tools",
            ...     "version": "1.0.0",
            ...     "repository_url": "https://github.com/example/text-tools"
            ... })
        """
        package_id = data["id"]
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord.id).where(NodePackageRecord.id == package_id)
                if session.execute(stmt).scalar_one_or_none() is not None:
                    _logger.warning(f"包已存在: {package_id}")
                    return None

                record = NodePackageRecord(
                    id=package_id,
                    name=data["name"],
                    version=data["version"],
                    author=data.get("author", ""),
                    description=data.get("description", ""),
                    repository_url=data["repository_url"],
                    branch=data.get("branch", "main"),
                    local_path=data.get("local_path"),
                    enabled=data.get("enabled", True),
                )
                session.add(record)
                session.flush()

                _logger.info(f"创建节点包记录: {record.id} v{record.version}")
                return _record_to_dict(record)

        except Exception as e:
            _logger.error(f"创建节点包记录失败: {e}", exc_info=True)
            return None

    def get_by_id(self, package_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取节点包

        Args:
            package_id: 包唯一标识

        Returns:
            包字典，不存在返回None

        Example:
            >>> package = repo.get_by_id("com.example.text-tools")
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord).where(NodePackageRecord.id == package_id)
                record = session.execute(stmt).scalar_one_or_none()
                return _record_to_dict(record)
        except Exception as e:
            _logger.error(f"获取节点包失败: {e}", exc_info=True)
            return None

    def get_all(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有节点包

        Args:
            enabled_only: 是否只获取已启用的包（默认: False）

        Returns:
            包字典列表

        Example:
            >>> packages = repo.get_all()
            >>> enabled = repo.get_all(enabled_only=True)
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord).order_by(NodePackageRecord.installed_at.desc())

                if enabled_only:
                    stmt = stmt.where(NodePackageRecord.enabled == True)

                records = session.execute(stmt).scalars().all()
                return [_record_to_dict(r) for r in records]
        except Exception as e:
            _logger.error(f"获取节点包列表失败: {e}", exc_info=True)
            return []

    def update(self, package_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新节点包信息

        Args:
            package_id: 包唯一标识
            updates: 要更新的字段字典
                可更新字段: name, version, author, description,
                           repository_url, branch, local_path, enabled

        Returns:
            是否更新成功

        Example:
            >>> repo.update("com.example.text-tools", {
            ...     "version": "2.0.0",
            ...     "description": "Updated description"
            ... })
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord).where(NodePackageRecord.id == package_id)
                record = session.execute(stmt).scalar_one_or_none()

                if not record:
                    _logger.warning(f"节点包不存在: {package_id}")
                    return False

                allowed_fields = {
                    "name",
                    "version",
                    "author",
                    "description",
                    "repository_url",
                    "branch",
                    "local_path",
                    "enabled",
                }

                for key, value in updates.items():
                    if key in allowed_fields and hasattr(record, key):
                        setattr(record, key, value)

                record.updated_at = datetime.now()

                _logger.info(f"更新节点包: {package_id}")
                return True

        except Exception as e:
            _logger.error(f"更新节点包失败: {e}", exc_info=True)
            return False

    def delete(self, package_id: str) -> bool:
        """
        删除节点包记录

        Args:
            package_id: 包唯一标识

        Returns:
            是否删除成功

        Example:
            >>> repo.delete("com.example.text-tools")
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord).where(NodePackageRecord.id == package_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record:
                    session.delete(record)
                    _logger.info(f"删除节点包记录: {package_id}")
                    return True
                else:
                    _logger.warning(f"节点包不存在，无法删除: {package_id}")
                    return False

        except Exception as e:
            _logger.error(f"删除节点包失败: {e}", exc_info=True)
            return False

    def set_enabled(self, package_id: str, enabled: bool) -> bool:
        """
        设置节点包启用状态

        Args:
            package_id: 包唯一标识
            enabled: 是否启用

        Returns:
            是否设置成功

        Example:
            >>> repo.set_enabled("com.example.text-tools", False)
        """
        return self.update(package_id, {"enabled": enabled})

    def exists(self, package_id: str) -> bool:
        """
        检查节点包是否存在

        Args:
            package_id: 包唯一标识

        Returns:
            是否存在

        Example:
            >>> repo.exists("com.example.text-tools")
            True
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord.id).where(NodePackageRecord.id == package_id)
                result = session.execute(stmt).scalar_one_or_none()
                return result is not None
        except Exception:
            return False

    def get_by_repository(self, repository_url: str) -> Optional[Dict[str, Any]]:
        """
        根据仓库URL获取节点包

        Args:
            repository_url: Git仓库URL

        Returns:
            包字典，不存在返回None

        Example:
            >>> pkg = repo.get_by_repository(
            ...     "https://github.com/example/text-tools"
            ... )
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord).where(
                    NodePackageRecord.repository_url == repository_url
                )
                record = session.execute(stmt).scalar_one_or_none()
                return _record_to_dict(record)
        except Exception as e:
            _logger.error(f"根据仓库URL获取节点包失败: {e}", exc_info=True)
            return None

    def get_by_local_path(self, local_path: str) -> Optional[Dict[str, Any]]:
        """
        根据本地路径获取节点包

        Args:
            local_path: 本地安装路径

        Returns:
            包字典，不存在返回None

        Example:
            >>> pkg = repo.get_by_local_path("/path/to/package")
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord).where(NodePackageRecord.local_path == local_path)
                record = session.execute(stmt).scalar_one_or_none()
                return _record_to_dict(record)
        except Exception as e:
            _logger.error(f"根据本地路径获取节点包失败: {e}", exc_info=True)
            return None

    def count(self, enabled_only: bool = False) -> int:
        """
        统计节点包数量

        Args:
            enabled_only: 是否只统计已启用的包

        Returns:
            包数量

        Example:
            >>> total = repo.count()
            >>> enabled = repo.count(enabled_only=True)
        """
        try:
            with self._database.session() as session:
                stmt = select(NodePackageRecord)
                if enabled_only:
                    stmt = stmt.where(NodePackageRecord.enabled == True)

                records = session.execute(stmt).scalars().all()
                return len(records)
        except Exception:
            return 0
