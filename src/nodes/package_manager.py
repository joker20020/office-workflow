# -*- coding: utf-8 -*-
"""
节点包管理器模块

提供节点包的中央管理功能：
- 从Git仓库安装包
- 更新已安装的包
- 启用/禁用包
- 删除包
- 向NodeEngine注册/注销节点

使用方式：
    from src.nodes.package_manager import NodePackageManager

    manager = NodePackageManager(
        packages_dir=Path("node_packages"),
        database=db,
        node_engine=engine,
        event_bus=event_bus
    )

    # 安装包
    result = manager.install(
        "https://github.com/example/text-tools",
        branch="main"
    )

    # 启用/禁用
    manager.enable("com.example.text-tools")
    manager.disable("com.example.text-tools")

    # 更新
    result = manager.update("com.example.text-tools")

    # 删除
    manager.delete("com.example.text-tools")
"""

import threading
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from src.core.event_bus import EventBus, EventType
from src.engine.node_engine import NodeEngine
from src.nodes.git_utils import GitUtils, GitResult
from src.nodes.package_loader import PackageLoader, PackageManifest
from src.nodes.repository import NodePackageRepository
from src.storage.database import Database
from src.utils.logger import get_logger

_logger = get_logger(__name__)


@dataclass
class InstallResult:
    """
    包安装结果

    Attributes:
        success: 是否安装成功
        message: 结果消息
        package_id: 安装的包ID（成功时填充）
        nodes_loaded: 加载的节点数量
    """

    success: bool
    message: str
    package_id: Optional[str] = None
    nodes_loaded: int = 0


@dataclass
class UpdateResult:
    """
    包更新结果

    Attributes:
        success: 是否操作成功
        message: 结果消息
        updated: 是否有实际更新（False表示已是最新）
        nodes_reloaded: 重新加载的节点数量
    """

    success: bool
    message: str
    updated: bool = False
    nodes_reloaded: int = 0


class NodePackageManager:
    """
    节点包管理器

    中央管理节点包的生命周期：
    - 安装：从Git仓库克隆、解析清单、注册节点
    - 更新：拉取最新更改、重新加载节点
    - 启用/禁用：切换包状态、注册/注销节点
    - 删除：从数据库和文件系统移除

    Example:
        >>> manager = NodePackageManager(
        ...     packages_dir=Path("node_packages"),
        ...     database=db,
        ...     node_engine=engine,
        ...     event_bus=event_bus
        ... )
        >>> result = manager.install("https://github.com/example/nodes")
        >>> if result.success:
        ...     print(f"已安装 {result.package_id}，加载 {result.nodes_loaded} 个节点")
    """

    def __init__(
        self,
        packages_dir: Path,
        database: Database,
        node_engine: NodeEngine,
        event_bus: Optional[EventBus] = None,
    ):
        """
        初始化包管理器

        Args:
            packages_dir: 包安装目录
            database: 数据库实例
            node_engine: 节点引擎（用于注册节点）
            event_bus: 事件总线（可选，用于发布事件）
        """
        self._packages_dir = packages_dir
        self._database = database
        self._node_engine = node_engine
        self._event_bus = event_bus
        self._repository = NodePackageRepository(database)

        # 已加载的包: package_id -> {manifest, node_types, path}
        self._loaded: Dict[str, Dict[str, Any]] = {}

        # 确保包目录存在
        self._packages_dir.mkdir(parents=True, exist_ok=True)
        _logger.info(f"节点包管理器初始化完成，包目录: {packages_dir}")

    # ==================== 包发现 ====================

    def discover_packages(self) -> List[Dict[str, Any]]:
        """
        发现所有已安装的包

        扫描包目录并返回包信息列表。
        同时会自动将文件系统中存在但数据库中未注册的包同步到数据库。

        Returns:
            包信息字典列表

        Example:
            >>> packages = manager.discover_packages()
            >>> for pkg in packages:
            ...     print(f"{pkg['name']} v{pkg['version']}")
        """
        packages: List[Dict[str, Any]] = []

        if not self._packages_dir.exists():
            return packages

        for pkg_dir in self._packages_dir.iterdir():
            if not pkg_dir.is_dir():
                continue

            if pkg_dir.name.startswith("."):
                continue

            manifest = PackageLoader.parse_manifest(pkg_dir)
            if manifest:
                db_record = self._repository.get_by_id(manifest.id)

                # 如果包在文件系统中存在但数据库中没有记录，自动注册
                if db_record is None:
                    self._repository.create(
                        {
                            "id": manifest.id,
                            "name": manifest.name,
                            "version": manifest.version,
                            "author": manifest.author,
                            "description": manifest.description,
                            "repository_url": manifest.repository,
                            "branch": manifest.branch,
                            "local_path": str(pkg_dir),
                            "enabled": True,
                        }
                    )
                    db_record = self._repository.get_by_id(manifest.id)
                    _logger.info(f"已将包 {manifest.id} 同步到数据库")

                package_info = {
                    "id": manifest.id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "author": manifest.author,
                    "description": manifest.description,
                    "repository": manifest.repository,
                    "branch": manifest.branch,
                    "local_path": str(pkg_dir),
                    "enabled": db_record.get("enabled", True) if db_record else True,
                    "installed": db_record is not None,
                    "nodes": manifest.nodes,
                }
                packages.append(package_info)

        _logger.debug(f"发现 {len(packages)} 个包")
        return packages

    def get_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取包信息

        Args:
            package_id: 包唯一标识

        Returns:
            包信息字典，不存在返回None

        Example:
            >>> pkg = manager.get_package("com.example.text-tools")
            >>> if pkg:
            ...     print(f"版本: {pkg['version']}")
        """
        db_record = self._repository.get_by_id(package_id)
        if not db_record:
            return None

        # 尝试从本地路径加载节点列表
        local_path = db_record.get("local_path")
        if local_path:
            manifest = PackageLoader.parse_manifest(Path(local_path))
            if manifest:
                db_record["nodes"] = manifest.nodes

        return db_record

    # ==================== 安装 ====================

    def install(
        self,
        repository_url: str,
        branch: str = "main",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> InstallResult:
        """
        从Git仓库安装包

        安装步骤：
        1. 克隆仓库
        2. 解析包清单
        3. 验证依赖
        4. 保存到数据库
        5. 加载节点
        6. 注册到NodeEngine
        7. 发布事件

        Args:
            repository_url: Git仓库URL
            branch: 要克隆的分支（默认: main）
            progress_callback: 可选的进度回调函数

        Returns:
            InstallResult 安装结果

        Example:
            >>> result = manager.install(
            ...     "https://github.com/example/text-tools",
            ...     branch="main"
            ... )
            >>> if result.success:
            ...     print(f"已安装 {result.package_id}")
        """
        # 通知进度
        if progress_callback:
            progress_callback(0, "开始克隆仓库...")

        # 检查是否已从该仓库安装
        existing = self._repository.get_by_repository(repository_url)
        if existing:
            return InstallResult(
                success=False,
                message=f"已从该仓库安装过包: {existing['id']}",
            )

        # 从URL提取包名
        package_name = repository_url.rstrip("/").split("/")[-1]
        if package_name.endswith(".git"):
            package_name = package_name[:-4]

        target_path = self._packages_dir / package_name

        # 检查目标目录是否存在
        if target_path.exists():
            return InstallResult(
                success=False,
                message=f"目标目录已存在: {target_path}",
            )

        # 克隆仓库
        if progress_callback:
            progress_callback(10, "正在克隆仓库...")

        clone_result = GitUtils.clone(
            url=repository_url,
            target_path=target_path,
            branch=branch,
        )

        if not clone_result.success:
            return InstallResult(
                success=False,
                message=f"克隆失败: {clone_result.message}",
            )

        # 解析包清单
        if progress_callback:
            progress_callback(40, "正在解析包清单...")

        manifest = PackageLoader.parse_manifest(target_path)
        if not manifest:
            # 解析失败，清理克隆的目录
            GitUtils.delete_repo(target_path)
            return InstallResult(
                success=False,
                message="解析 package.json 失败",
            )

        # 验证清单
        validation_errors = PackageLoader.validate_manifest(manifest)
        if validation_errors:
            # 验证失败，清理
            GitUtils.delete_repo(target_path)
            return InstallResult(
                success=False,
                message=f"清单验证失败: {'; '.join(validation_errors)}",
            )

        # 加载节点定义
        if progress_callback:
            progress_callback(50, "正在加载节点定义...")

        node_definitions = PackageLoader.load_nodes(target_path, manifest)

        # 保存到数据库
        if progress_callback:
            progress_callback(70, "正在保存包记录...")

        package_data = {
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "author": manifest.author,
            "description": manifest.description,
            "repository_url": repository_url,
            "branch": branch,
            "local_path": str(target_path),
            "enabled": True,
        }

        self._repository.create(package_data)

        # 注册节点
        if progress_callback:
            progress_callback(85, "正在注册节点...")

        nodes_registered = 0
        for node_def in node_definitions:
            try:
                self._node_engine.register_node_type(node_def)
                nodes_registered += 1
            except Exception as e:
                _logger.error(f"注册节点失败 {node_def.node_type}: {e}")

        # 记录已加载的包
        self._loaded[manifest.id] = {
            "manifest": manifest,
            "node_types": [d.node_type for d in node_definitions],
            "path": target_path,
        }

        if progress_callback:
            progress_callback(100, "安装完成")

        # 发布事件
        self._publish_event(
            EventType.PACKAGE_INSTALLED,
            {
                "package_id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "nodes_loaded": nodes_registered,
            },
        )

        _logger.info(
            f"包安装成功: {manifest.id} v{manifest.version} "
            f"({nodes_registered}/{len(node_definitions)} 个节点)"
        )

        return InstallResult(
            success=True,
            message=f"成功安装 {manifest.name} v{manifest.version}",
            package_id=manifest.id,
            nodes_loaded=nodes_registered,
        )

    # ==================== 更新 ====================

    def install_local(
        self,
        local_path: Path,
        copy: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> InstallResult:
        """
        从本地目录安装包

        安装步骤：
        1. 验证本地路径存在
        2. 解析包清单
        3. 验证依赖
        4. 保存到数据库
        5. 复制或链接到包目录
        6. 加载节点
        7. 注册到NodeEngine
        8. 发布事件

        Args:
            local_path: 本地包目录路径
            copy: 是否复制到包目录（True=复制，False=创建符号链接）
            progress_callback: 可选的进度回调函数

        Returns:
            InstallResult 安装结果

        Example:
            >>> result = manager.install_local(
            ...     Path("/path/to/local/package"),
            ...     copy=True
            ... )
            >>> if result.success:
            ...     print(f"已安装 {result.package_id}")
        """
        if progress_callback:
            progress_callback(0, "正在验证本地路径...")

        local_path = Path(local_path)
        if not local_path.exists():
            return InstallResult(
                success=False,
                message=f"本地路径不存在: {local_path}",
            )

        if not local_path.is_dir():
            return InstallResult(
                success=False,
                message=f"本地路径不是目录: {local_path}",
            )

        if progress_callback:
            progress_callback(10, "正在解析包清单...")

        manifest = PackageLoader.parse_manifest(local_path)
        if not manifest:
            return InstallResult(
                success=False,
                message="解析 package.json 失败",
            )

        validation_errors = PackageLoader.validate_manifest(manifest)
        if validation_errors:
            return InstallResult(
                success=False,
                message=f"清单验证失败: {'; '.join(validation_errors)}",
            )

        if progress_callback:
            progress_callback(30, "正在检查是否已安装...")

        existing = self._repository.get_by_id(manifest.id)
        if existing:
            return InstallResult(
                success=False,
                message=f"包已存在: {manifest.id}",
            )

        target_path = self._packages_dir / local_path.name

        if target_path.exists():
            if target_path.resolve() == local_path.resolve():
                pass
            else:
                return InstallResult(
                    success=False,
                    message=f"目标目录已存在: {target_path}",
                )

        if progress_callback:
            progress_callback(40, "正在复制/链接包...")

        try:
            if copy:
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(local_path, target_path)
                final_path = target_path
            else:
                if target_path.exists():
                    target_path.unlink()
                target_path.symlink_to(local_path)
                final_path = target_path
        except Exception as e:
            return InstallResult(
                success=False,
                message=f"复制/链接失败: {e}",
            )

        if progress_callback:
            progress_callback(60, "正在加载节点定义...")

        node_definitions = PackageLoader.load_nodes(final_path, manifest)

        if progress_callback:
            progress_callback(80, "正在保存包记录...")

        package_data = {
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "author": manifest.author,
            "description": manifest.description,
            "repository_url": f"local://{local_path}",
            "branch": "local",
            "local_path": str(final_path),
            "enabled": True,
            "is_local": True,
        }

        self._repository.create(package_data)

        if progress_callback:
            progress_callback(90, "正在注册节点...")

        nodes_registered = 0
        for node_def in node_definitions:
            try:
                self._node_engine.register_node_type(node_def)
                nodes_registered += 1
            except Exception as e:
                _logger.error(f"注册节点失败 {node_def.node_type}: {e}")

        self._loaded[manifest.id] = {
            "manifest": manifest,
            "node_types": [d.node_type for d in node_definitions],
            "path": final_path,
            "is_local": True,
        }

        if progress_callback:
            progress_callback(100, "安装完成")

        self._publish_event(
            EventType.PACKAGE_INSTALLED,
            {
                "package_id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "nodes_loaded": nodes_registered,
                "source": "local",
            },
        )

        _logger.info(
            f"本地包安装成功: {manifest.id} v{manifest.version} "
            f"({nodes_registered}/{len(node_definitions)} 个节点)"
        )

        return InstallResult(
            success=True,
            message=f"成功安装本地包 {manifest.name} v{manifest.version}",
            package_id=manifest.id,
            nodes_loaded=nodes_registered,
        )

    def update(
        self,
        package_id: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> UpdateResult:
        """
        从远程更新包

        更新步骤：
        1. 获取包信息
        2. 拉取最新更改
        3. 检查是否有更新
        4. 重新加载节点
        5. 更新数据库
        6. 发布事件

        Args:
            package_id: 包唯一标识
            progress_callback: 可选的进度回调函数

        Returns:
            UpdateResult 更新结果

        Example:
            >>> result = manager.update("com.example.text-tools")
            >>> if result.updated:
            ...     print(f"已更新，重新加载 {result.nodes_reloaded} 个节点")
        """
        if progress_callback:
            progress_callback(0, "正在获取包信息...")

        # 获取包记录
        db_record = self._repository.get_by_id(package_id)
        if not db_record:
            return UpdateResult(
                success=False,
                message=f"包不存在: {package_id}",
            )

        # 获取本地路径
        local_path = db_record.get("local_path")
        if not local_path:
            return UpdateResult(
                success=False,
                message="包没有本地路径",
            )

        repo_path = Path(local_path)
        if not repo_path.exists():
            return UpdateResult(
                success=False,
                message=f"包目录不存在: {repo_path}",
            )

        # 拉取更新
        if progress_callback:
            progress_callback(20, "正在拉取更新...")

        branch = db_record.get("branch", "main")
        pull_result = GitUtils.pull(repo_path, branch)

        if not pull_result.success:
            return UpdateResult(
                success=False,
                message=f"拉取失败: {pull_result.message}",
            )

        # 检查是否有变更
        if pull_result.changed_files == 0:
            return UpdateResult(
                success=True,
                message="已是最新版本",
                updated=False,
            )

        # 重新解析清单
        if progress_callback:
            progress_callback(50, "正在重新解析包清单...")

        manifest = PackageLoader.parse_manifest(repo_path)
        if not manifest:
            return UpdateResult(
                success=False,
                message="解析更新后的 package.json 失败",
            )

        # 重新加载节点
        if progress_callback:
            progress_callback(60, "正在重新加载节点...")

        # 先注销旧节点
        if package_id in self._loaded:
            old_node_types = self._loaded[package_id].get("node_types", [])
            for node_type in old_node_types:
                try:
                    self._node_engine.unregister_node_type(node_type)
                except Exception as e:
                    _logger.warning(f"注销节点失败 {node_type}: {e}")

        # 加载新节点
        node_definitions = PackageLoader.load_nodes(repo_path, manifest)

        if progress_callback:
            progress_callback(80, "正在注册节点...")

        # 注册新节点
        nodes_registered = 0
        for node_def in node_definitions:
            try:
                self._node_engine.register_node_type(node_def)
                nodes_registered += 1
            except Exception as e:
                _logger.error(f"注册节点失败 {node_def.node_type}: {e}")

        # 更新已加载记录
        self._loaded[package_id] = {
            "manifest": manifest,
            "node_types": [d.node_type for d in node_definitions],
            "path": repo_path,
        }

        # 更新数据库
        if progress_callback:
            progress_callback(90, "正在更新数据库...")

        self._repository.update(
            package_id,
            {
                "version": manifest.version,
                "name": manifest.name,
                "description": manifest.description,
                "author": manifest.author,
            },
        )

        if progress_callback:
            progress_callback(100, "更新完成")

        # 发布事件
        self._publish_event(
            EventType.PACKAGE_UPDATED,
            {
                "package_id": package_id,
                "version": manifest.version,
                "nodes_reloaded": nodes_registered,
            },
        )

        _logger.info(
            f"包更新成功: {package_id} v{manifest.version} "
            f"({nodes_registered}/{len(node_definitions)} 个节点)"
        )

        return UpdateResult(
            success=True,
            message=f"成功更新到 v{manifest.version}",
            updated=True,
            nodes_reloaded=nodes_registered,
        )

    def check_for_updates(self, package_id: str) -> bool:
        """
        检查是否有更新可用（不安装）

        执行 git fetch 检查是否有新提交。

        Args:
            package_id: 包唯一标识

        Returns:
            是否有更新可用

        Example:
            >>> if manager.check_for_updates("com.example.text-tools"):
            ...     print("有可用更新")
        """
        db_record = self._repository.get_by_id(package_id)
        if not db_record:
            return False

        local_path = db_record.get("local_path")
        if not local_path:
            return False

        repo_path = Path(local_path)
        if not repo_path.exists():
            return False

        try:
            from git import Repo

            repo = Repo(repo_path)
            origin = repo.remote(name="origin")
            if not origin:
                return False

            # 获取远程更新
            origin.fetch()

            # 比较本地和远程提交
            local_commit = repo.head.commit
            remote_commit = origin.refs[repo.active_branch.name].commit

            return local_commit != remote_commit
        except Exception as e:
            _logger.warning(f"检查更新失败: {e}")
            return False

    # ==================== 启用/禁用 ====================

    def enable(self, package_id: str) -> bool:
        """
        启用包

        启用步骤：
        1. 获取包信息
        2. 更新数据库
        3. 加载并注册节点
        4. 发布事件

        Args:
            package_id: 包唯一标识

        Returns:
            是否成功

        Example:
            >>> manager.enable("com.example.text-tools")
            True
        """
        db_record = self._repository.get_by_id(package_id)
        if not db_record:
            _logger.warning(f"包不存在: {package_id}")
            return False

        # 检查是否已启用
        if db_record.get("enabled", True):
            _logger.debug(f"包已启用: {package_id}")
            return True

        # 获取本地路径
        local_path = db_record.get("local_path")
        if not local_path:
            _logger.warning(f"包没有本地路径: {package_id}")
            return False

        repo_path = Path(local_path)

        # 解析清单
        manifest = PackageLoader.parse_manifest(repo_path)
        if not manifest:
            _logger.error(f"解析清单失败: {package_id}")
            return False

        # 加载节点
        node_definitions = PackageLoader.load_nodes(repo_path, manifest)

        # 注册节点
        nodes_registered = 0
        for node_def in node_definitions:
            try:
                self._node_engine.register_node_type(node_def)
                nodes_registered += 1
            except Exception as e:
                _logger.error(f"注册节点失败 {node_def.node_type}: {e}")

        # 更新已加载记录
        self._loaded[package_id] = {
            "manifest": manifest,
            "node_types": [d.node_type for d in node_definitions],
            "path": repo_path,
        }

        # 更新数据库
        self._repository.set_enabled(package_id, True)

        # 发布事件
        self._publish_event(
            EventType.PACKAGE_ENABLED,
            {
                "package_id": package_id,
                "nodes_loaded": nodes_registered,
            },
        )

        _logger.info(f"包已启用: {package_id} ({nodes_registered} 个节点)")
        return True

    def disable(self, package_id: str) -> bool:
        """
        禁用包

        禁用步骤：
        1. 获取包信息
        2. 注销节点
        3. 更新数据库
        4. 发布事件

        Args:
            package_id: 包唯一标识

        Returns:
            是否成功

        Example:
            >>> manager.disable("com.example.text-tools")
            True
        """
        db_record = self._repository.get_by_id(package_id)
        if not db_record:
            _logger.warning(f"包不存在: {package_id}")
            return False

        # 检查是否已禁用
        if not db_record.get("enabled", True):
            _logger.debug(f"包已禁用: {package_id}")
            return True

        # 注销节点
        if package_id in self._loaded:
            node_types = self._loaded[package_id].get("node_types", [])
            for node_type in node_types:
                try:
                    self._node_engine.unregister_node_type(node_type)
                except Exception as e:
                    _logger.warning(f"注销节点失败 {node_type}: {e}")

            # 从已加载列表移除
            del self._loaded[package_id]

        # 更新数据库
        self._repository.set_enabled(package_id, False)

        # 发布事件
        self._publish_event(
            EventType.PACKAGE_DISABLED,
            {
                "package_id": package_id,
            },
        )

        _logger.info(f"包已禁用: {package_id}")
        return True

    # ==================== 删除 ====================

    def delete(self, package_id: str) -> bool:
        """
        完全删除包

        删除步骤：
        1. 获取包信息
        2. 注销节点
        3. 从数据库删除
        4. 删除文件
        5. 发布事件

        Args:
            package_id: 包唯一标识

        Returns:
            是否成功

        Example:
            >>> manager.delete("com.example.text-tools")
            True
        """
        db_record = self._repository.get_by_id(package_id)
        if not db_record:
            _logger.warning(f"包不存在: {package_id}")
            return False

        # 注销节点
        if package_id in self._loaded:
            node_types = self._loaded[package_id].get("node_types", [])
            for node_type in node_types:
                try:
                    self._node_engine.unregister_node_type(node_type)
                except Exception as e:
                    _logger.warning(f"注销节点失败 {node_type}: {e}")

            # 从已加载列表移除
            del self._loaded[package_id]

        # 获取本地路径
        local_path = db_record.get("local_path")

        # 从数据库删除
        self._repository.delete(package_id)

        # 删除文件
        if local_path:
            GitUtils.delete_repo(Path(local_path))

        # 发布事件
        self._publish_event(
            EventType.PACKAGE_REMOVED,
            {
                "package_id": package_id,
            },
        )

        _logger.info(f"包已删除: {package_id}")
        return True

    # ==================== 生命周期 ====================

    def load_all_enabled(self) -> int:
        """
        启动时加载所有已启用的包

        Returns:
            成功加载的包数量

        Example:
            >>> count = manager.load_all_enabled()
            >>> print(f"已加载 {count} 个包")
        """
        enabled_packages = self._repository.get_all(enabled_only=True)
        loaded_count = 0

        for pkg in enabled_packages:
            package_id = pkg["id"]
            local_path = pkg.get("local_path")

            if not local_path:
                _logger.warning(f"包 {package_id} 没有本地路径，跳过")
                continue

            repo_path = Path(local_path)
            if not repo_path.exists():
                _logger.warning(f"包目录不存在: {repo_path}，跳过")
                continue

            # 解析清单
            manifest = PackageLoader.parse_manifest(repo_path)
            if not manifest:
                _logger.warning(f"解析 {package_id} 的清单失败，跳过")
                continue

            # 加载节点
            node_definitions = PackageLoader.load_nodes(repo_path, manifest)

            # 注册节点
            nodes_registered = 0
            for node_def in node_definitions:
                try:
                    self._node_engine.register_node_type(node_def)
                    nodes_registered += 1
                except Exception as e:
                    _logger.error(f"注册节点失败 {node_def.node_type}: {e}")

            # 记录已加载
            self._loaded[package_id] = {
                "manifest": manifest,
                "node_types": [d.node_type for d in node_definitions],
                "path": repo_path,
            }

            loaded_count += 1
            _logger.info(
                f"已加载包: {package_id} ({nodes_registered}/{len(node_definitions)} 个节点)"
            )

        _logger.info(f"已加载 {loaded_count}/{len(enabled_packages)} 个启用的包")
        return loaded_count

    def unload_all(self) -> None:
        """
        关闭时卸载所有包

        Example:
            >>> manager.unload_all()
        """
        for package_id, pkg_data in list(self._loaded.items()):
            node_types = pkg_data.get("node_types", [])
            for node_type in node_types:
                try:
                    self._node_engine.unregister_node_type(node_type)
                except Exception as e:
                    _logger.warning(f"注销节点失败 {node_type}: {e}")

        self._loaded.clear()
        _logger.info("所有包已卸载")

    # ==================== 内部方法 ====================

    def _publish_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """发布事件（如果事件总线可用）"""
        if self._event_bus:
            self._event_bus.publish(event_type, data)

    def get_loaded_packages(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已加载包的信息"""
        return dict(self._loaded)

    def is_loaded(self, package_id: str) -> bool:
        """检查包是否已加载到内存"""
        return package_id in self._loaded

    @property
    def packages_dir(self) -> Path:
        """获取包目录路径"""
        return self._packages_dir


# Singleton pattern implementation
_global_NodePackageManager_instance: Optional["NodePackageManager"] = None
_global_lock = threading.Lock()


def get_package_manager() -> "NodePackageManager":
    """Get the singleton NodePackageManager instance."""
    global _global_NodePackageManager_instance, _global_lock
    if _global_NodePackageManager_instance is None:
        raise RuntimeError("NodePackageManager not initialized")
    return _global_NodePackageManager_instance


def init_package_manager(
    packages_dir: Path,
    database: Database,
    node_engine: NodeEngine,
    event_bus: Optional[EventBus] = None,
) -> "NodePackageManager":
    """Initialize the singleton NodePackageManager with custom parameters."""
    global _global_NodePackageManager_instance, _global_lock
    with _global_lock:
        if _global_NodePackageManager_instance is not None:
            raise RuntimeError("NodePackageManager already initialized")
        _global_NodePackageManager_instance = NodePackageManager(
            packages_dir, database, node_engine, event_bus
        )
    return _global_NodePackageManager_instance


def shutdown_package_manager() -> None:
    """Shutdown the singleton NodePackageManager."""
    global _global_NodePackageManager_instance, _global_lock
    with _global_lock:
        _global_NodePackageManager_instance = None


def reset_package_manager_for_testing() -> None:
    """Reset the singleton for testing purposes."""
    shutdown_package_manager()
