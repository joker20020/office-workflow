# -*- coding: utf-8 -*-
"""
节点包管理模块 (Node Package Management Module)

提供基于Git的节点包管理功能：
- GitUtils: Git克隆/拉取操作
- NodePackageRepository: 数据库CRUD操作
- PackageLoader: 解析package.json，加载节点
- NodePackageManager: 核心管理逻辑

使用方式：
    from src.nodes import NodePackageManager, GitUtils

    # 克隆仓库
    result = GitUtils.clone(url, path)

    # 管理包
    manager = NodePackageManager(packages_dir, database, node_engine)
    manager.install(url, branch="main")
"""

# 延迟导入以避免循环依赖
__all__ = [
    "GitUtils",
    "GitResult",
    "NodePackageRepository",
    "PackageLoader",
    "PackageManifest",
    "NodePackageManager",
    "InstallResult",
    "UpdateResult",
]


def __getattr__(name: str):
    """延迟导入模块成员"""
    if name == "GitUtils":
        from src.nodes.git_utils import GitUtils

        return GitUtils
    elif name == "GitResult":
        from src.nodes.git_utils import GitResult

        return GitResult
    elif name == "NodePackageRepository":
        from src.nodes.repository import NodePackageRepository

        return NodePackageRepository
    elif name == "PackageLoader":
        from src.nodes.package_loader import PackageLoader

        return PackageLoader
    elif name == "PackageManifest":
        from src.nodes.package_loader import PackageManifest

        return PackageManifest
    elif name == "NodePackageManager":
        from src.nodes.package_manager import NodePackageManager

        return NodePackageManager
    elif name == "InstallResult":
        from src.nodes.package_manager import InstallResult

        return InstallResult
    elif name == "UpdateResult":
        from src.nodes.package_manager import UpdateResult

        return UpdateResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
