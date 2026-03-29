# -*- coding: utf-8 -*-
"""
Git工具模块 (Git Utilities Module)

提供Git操作功能：
- 克隆仓库
- 拉取更新
- 获取提交信息
- 验证仓库

使用方式：
    from src.nodes.git_utils import GitUtils, GitResult

    # 克隆仓库
    result = GitUtils.clone(
        url="https://github.com/user/repo",
        target_path=Path("node_packages/my_package"),
        branch="main"
    )

    if result.success:
        print(f"克隆成功: {result.commit_hash}")

    # 拉取更新
    result = GitUtils.pull(Path("node_packages/my_package"))
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from git import Repo, GitCommandError, InvalidGitRepositoryError
from git.exc import NoSuchPathError

from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


@dataclass
class GitResult:
    """
    Git操作结果

    Attributes:
        success: 操作是否成功
        message: 结果消息或错误信息
        commit_hash: 当前提交哈希（短格式）
        changed_files: 变更的文件数量
    """

    success: bool
    message: str
    commit_hash: Optional[str] = None
    changed_files: int = 0


class GitUtils:
    """
    Git操作工具类

    提供静态方法进行Git操作：
    - clone: 克隆远程仓库
    - pull: 拉取最新更改
    - get_current_commit: 获取当前提交哈希
    - get_remote_url: 获取远程URL
    - get_branch: 获取当前分支名
    - is_valid_repo: 检查是否为有效仓库
    - delete_repo: 删除仓库目录

    Example:
        >>> result = GitUtils.clone(
        ...     "https://github.com/user/nodes",
        ...     Path("node_packages/nodes")
        ... )
        >>> print(result.success)
        True
    """

    @staticmethod
    def clone(
        url: str,
        target_path: Path,
        branch: str = "main",
        depth: int = 1,
        timeout: int = 300,
    ) -> GitResult:
        """
        克隆仓库到目标路径

        Args:
            url: Git仓库URL（支持HTTPS和SSH）
            target_path: 目标目录路径
            branch: 要克隆的分支（默认: main）
            depth: 浅克隆深度（默认: 1，仅最新提交）
            timeout: 超时时间（秒，默认: 300）

        Returns:
            GitResult: 克隆结果

        Example:
            >>> result = GitUtils.clone(
            ...     "https://github.com/user/nodes",
            ...     Path("node_packages/nodes"),
            ...     branch="develop"
            ... )
        """
        try:
            # 检查目标路径是否已存在
            if target_path.exists():
                return GitResult(
                    success=False,
                    message=f"目标路径已存在: {target_path}",
                )

            # 确保父目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            _logger.info(f"正在克隆仓库: {url} -> {target_path}")

            # 执行克隆操作
            repo = Repo.clone_from(
                url,
                target_path,
                branch=branch,
                depth=depth,
            )

            # 获取提交哈希
            commit_hash = repo.head.commit.hexsha[:8] if repo.head.commit else None

            _logger.info(f"克隆成功: {url} @ {commit_hash}")

            return GitResult(
                success=True,
                message=f"成功克隆 {url}",
                commit_hash=commit_hash,
            )

        except GitCommandError as e:
            # Git命令执行失败
            error_msg = f"Git命令失败: {e.stderr or str(e)}"
            _logger.error(f"克隆失败: {error_msg}")
            return GitResult(success=False, message=error_msg)

        except Exception as e:
            # 其他异常
            error_msg = f"克隆失败: {str(e)}"
            _logger.error(f"克隆失败: {error_msg}", exc_info=True)
            return GitResult(success=False, message=error_msg)

    @staticmethod
    def pull(repo_path: Path, branch: str = "main", timeout: int = 300) -> GitResult:
        """
        从远程拉取最新更改

        Args:
            repo_path: Git仓库路径
            branch: 要拉取的分支（默认: main）
            timeout: 超时时间（秒，默认: 300）

        Returns:
            GitResult: 拉取结果，包含变更信息

        Example:
            >>> result = GitUtils.pull(Path("node_packages/nodes"))
            >>> if result.changed_files > 0:
            ...     print(f"有 {result.changed_files} 个文件变更")
        """
        try:
            # 检查路径是否存在
            if not repo_path.exists():
                return GitResult(
                    success=False,
                    message=f"仓库路径不存在: {repo_path}",
                )

            # 打开仓库
            repo = Repo(repo_path)

            # 获取远程origin
            origin = repo.remote(name="origin")
            if not origin:
                return GitResult(
                    success=False,
                    message="未找到远程 'origin'",
                )

            _logger.info(f"正在拉取更新: {repo_path}")

            # 执行拉取
            fetch_info = origin.pull(branch)

            # 检查是否有更新
            if not fetch_info:
                return GitResult(
                    success=True,
                    message="拉取完成，无新提交",
                    changed_files=0,
                )

            # 获取提交哈希
            commit_hash = repo.head.commit.hexsha[:8] if repo.head.commit else None

            # 检查是否是最新的
            from git import RemoteProgress

            HEAD_UPTODATE = 64  # GitPython的标志常量
            flags = fetch_info[0].flags if fetch_info else 0

            if flags & HEAD_UPTODATE:
                return GitResult(
                    success=True,
                    message="已是最新版本",
                    commit_hash=commit_hash,
                    changed_files=0,
                )

            # 计算变更文件数量
            changed_files = 0
            if repo.head.commit.parents:
                changed_files = len(list(repo.head.commit.diff(repo.head.commit.parents[0])))

            _logger.info(f"拉取成功: {changed_files} 个文件变更")

            return GitResult(
                success=True,
                message="成功拉取更新",
                commit_hash=commit_hash,
                changed_files=changed_files,
            )

        except InvalidGitRepositoryError:
            return GitResult(
                success=False,
                message=f"不是有效的Git仓库: {repo_path}",
            )
        except GitCommandError as e:
            error_msg = f"Git命令失败: {e.stderr or str(e)}"
            _logger.error(f"拉取失败: {error_msg}")
            return GitResult(success=False, message=error_msg)
        except Exception as e:
            error_msg = f"拉取失败: {str(e)}"
            _logger.error(f"拉取失败: {error_msg}", exc_info=True)
            return GitResult(success=False, message=error_msg)

    @staticmethod
    def get_current_commit(repo_path: Path) -> Optional[str]:
        """
        获取当前提交哈希（短格式）

        Args:
            repo_path: Git仓库路径

        Returns:
            提交哈希（8字符）或None

        Example:
            >>> commit = GitUtils.get_current_commit(Path("node_packages/nodes"))
            >>> print(commit)
            'a1b2c3d4'
        """
        try:
            repo = Repo(repo_path)
            return repo.head.commit.hexsha[:8] if repo.head.commit else None
        except Exception as e:
            _logger.warning(f"获取提交哈希失败: {e}")
            return None

    @staticmethod
    def get_remote_url(repo_path: Path) -> Optional[str]:
        """
        获取远程origin的URL

        Args:
            repo_path: Git仓库路径

        Returns:
            远程URL或None

        Example:
            >>> url = GitUtils.get_remote_url(Path("node_packages/nodes"))
            >>> print(url)
            'https://github.com/user/nodes'
        """
        try:
            repo = Repo(repo_path)
            origin = repo.remote(name="origin")
            return origin.url if origin else None
        except Exception as e:
            _logger.warning(f"获取远程URL失败: {e}")
            return None

    @staticmethod
    def get_branch(repo_path: Path) -> Optional[str]:
        """
        获取当前分支名

        Args:
            repo_path: Git仓库路径

        Returns:
            分支名或None（如果是分离HEAD状态）

        Example:
            >>> branch = GitUtils.get_branch(Path("node_packages/nodes"))
            >>> print(branch)
            'main'
        """
        try:
            repo = Repo(repo_path)
            return repo.active_branch.name
        except Exception:
            # 分离HEAD状态会抛出异常
            return None

    @staticmethod
    def is_valid_repo(path: Path) -> bool:
        """
        检查路径是否为有效的Git仓库

        Args:
            path: 要检查的路径

        Returns:
            是否为有效Git仓库

        Example:
            >>> GitUtils.is_valid_repo(Path("node_packages/nodes"))
            True
        """
        try:
            Repo(path)
            return True
        except Exception:
            return False

    @staticmethod
    def delete_repo(path: Path) -> bool:
        """
        安全删除仓库目录

        删除整个目录，包括.git文件夹

        Args:
            path: 仓库根目录路径

        Returns:
            是否删除成功

        Example:
            >>> GitUtils.delete_repo(Path("node_packages/old_nodes"))
            True
        """
        try:
            if not path.exists():
                return True

            _logger.info(f"正在删除仓库: {path}")
            shutil.rmtree(path)
            _logger.info(f"仓库已删除: {path}")
            return True
        except Exception as e:
            _logger.error(f"删除仓库失败: {e}", exc_info=True)
            return False
