# -*- coding: utf-8 -*-
"""
GitUtils测试模块

测试Git操作功能：
- 克隆仓库
- 拉取更新
- 获取提交信息
- 验证仓库
"""

import shutil
from pathlib import Path
from unittest import mock

import pytest
from git import Repo

from src.nodes.git_utils import GitUtils, GitResult


class TestGitUtilsClone:
    """克隆操作测试"""

    def test_clone_success(self, tmp_path: Path):
        """测试成功克隆"""
        # 创建一个本地测试仓库
        source_repo_path = tmp_path / "source"
        source_repo_path.mkdir()
        Repo.init(source_repo_path)

        # 添加一个文件
        test_file = source_repo_path / "test.txt"
        test_file.write_text("test content")

        repo = Repo(source_repo_path)
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")

        # 克隆到目标路径
        target_path = tmp_path / "target"
        result = GitUtils.clone(str(source_repo_path), target_path)

        assert result.success is True
        assert "成功" in result.message
        assert result.commit_hash is not None
        assert target_path.exists()
        assert (target_path / "test.txt").exists()

    def test_clone_to_existing_path_fails(self, tmp_path: Path):
        """测试克隆到已存在的路径失败"""
        existing_path = tmp_path / "existing"
        existing_path.mkdir()

        result = GitUtils.clone("https://github.com/nonexistent/repo", existing_path)

        assert result.success is False
        assert "已存在" in result.message

    def test_clone_invalid_url_fails(self, tmp_path: Path):
        """测试克隆无效URL失败"""
        target_path = tmp_path / "target"

        result = GitUtils.clone("https://github.com/nonexistent/repo", target_path)

        assert result.success is False
        assert result.message != ""

    def test_clone_with_custom_branch(self, tmp_path: Path):
        """测试克隆指定分支"""
        source_repo_path = tmp_path / "source"
        source_repo_path.mkdir()
        repo = Repo.init(source_repo_path)

        # 创建main分支并提交
        test_file = source_repo_path / "test.txt"
        test_file.write_text("main content")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")

        # 克隆
        target_path = tmp_path / "target"
        result = GitUtils.clone(str(source_repo_path), target_path, branch="main")

        assert result.success is True


class TestGitUtilsPull:
    """拉取操作测试"""

    def test_pull_success(self, tmp_path: Path):
        """测试成功拉取"""
        # 创建源仓库
        source_repo_path = tmp_path / "source"
        source_repo_path.mkdir()
        source_repo = Repo.init(source_repo_path)

        # 初始提交
        test_file = source_repo_path / "test.txt"
        test_file.write_text("initial")
        source_repo.index.add(["test.txt"])
        source_repo.index.commit("Initial commit")

        # 克隆
        target_path = tmp_path / "target"
        GitUtils.clone(str(source_repo_path), target_path)

        # 在源仓库添加新提交
        test_file.write_text("updated")
        source_repo.index.add(["test.txt"])
        source_repo.index.commit("Update")

        # 拉取
        result = GitUtils.pull(target_path)

        assert result.success is True

    def test_pull_nonexistent_path_fails(self, tmp_path: Path):
        """测试拉取不存在的路径失败"""
        result = GitUtils.pull(tmp_path / "nonexistent")

        assert result.success is False
        assert "不存在" in result.message

    def test_pull_non_git_path_fails(self, tmp_path: Path):
        """测试拉取非Git目录失败"""
        non_git_path = tmp_path / "not_git"
        non_git_path.mkdir()

        result = GitUtils.pull(non_git_path)

        assert result.success is False
        assert "不是有效的Git仓库" in result.message


class TestGitUtilsGetCurrentCommit:
    """获取当前提交测试"""

    def test_get_current_commit_success(self, tmp_path: Path):
        """测试获取当前提交成功"""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        repo = Repo.init(repo_path)

        test_file = repo_path / "test.txt"
        test_file.write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")

        commit_hash = GitUtils.get_current_commit(repo_path)

        assert commit_hash is not None
        assert len(commit_hash) == 8

    def test_get_current_commit_empty_repo(self, tmp_path: Path):
        """测试空仓库返回None"""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        Repo.init(repo_path)

        commit_hash = GitUtils.get_current_commit(repo_path)

        # 空仓库没有HEAD提交
        assert commit_hash is None

    def test_get_current_commit_non_git(self, tmp_path: Path):
        """测试非Git路径返回None"""
        non_git_path = tmp_path / "not_git"
        non_git_path.mkdir()

        commit_hash = GitUtils.get_current_commit(non_git_path)

        assert commit_hash is None


class TestGitUtilsGetRemoteUrl:
    """获取远程URL测试"""

    def test_get_remote_url_success(self, tmp_path: Path):
        """测试获取远程URL成功"""
        source_path = tmp_path / "source"
        source_path.mkdir()
        source_repo = Repo.init(source_path)

        test_file = source_path / "test.txt"
        test_file.write_text("test")
        source_repo.index.add(["test.txt"])
        source_repo.index.commit("Initial commit")

        target_path = tmp_path / "target"
        GitUtils.clone(str(source_path), target_path)

        url = GitUtils.get_remote_url(target_path)

        assert url is not None
        assert str(source_path) in url

    def test_get_remote_url_no_remote(self, tmp_path: Path):
        """测试没有远程时返回None"""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        Repo.init(repo_path)

        url = GitUtils.get_remote_url(repo_path)

        assert url is None


class TestGitUtilsGetBranch:
    """获取分支名测试"""

    def test_get_branch_success(self, tmp_path: Path):
        """测试获取分支名成功"""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        repo = Repo.init(repo_path)

        test_file = repo_path / "test.txt"
        test_file.write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")

        branch = GitUtils.get_branch(repo_path)

        assert branch is not None

    def test_get_branch_non_git(self, tmp_path: Path):
        """测试非Git路径返回None"""
        non_git_path = tmp_path / "not_git"
        non_git_path.mkdir()

        branch = GitUtils.get_branch(non_git_path)

        assert branch is None


class TestGitUtilsIsValidRepo:
    """验证仓库测试"""

    def test_is_valid_repo_true(self, tmp_path: Path):
        """测试有效仓库返回True"""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        Repo.init(repo_path)

        assert GitUtils.is_valid_repo(repo_path) is True

    def test_is_valid_repo_false(self, tmp_path: Path):
        """测试非Git目录返回False"""
        non_git_path = tmp_path / "not_git"
        non_git_path.mkdir()

        assert GitUtils.is_valid_repo(non_git_path) is False

    def test_is_valid_repo_nonexistent(self, tmp_path: Path):
        """测试不存在的路径返回False"""
        assert GitUtils.is_valid_repo(tmp_path / "nonexistent") is False


class TestGitUtilsDeleteRepo:
    """删除仓库测试"""

    def test_delete_repo_success(self, tmp_path: Path):
        """测试成功删除仓库"""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        Repo.init(repo_path)

        # 添加文件
        test_file = repo_path / "test.txt"
        test_file.write_text("test")

        assert repo_path.exists()

        result = GitUtils.delete_repo(repo_path)

        assert result is True
        assert not repo_path.exists()

    def test_delete_repo_nonexistent(self, tmp_path: Path):
        """测试删除不存在的路径返回True"""
        nonexistent = tmp_path / "nonexistent"

        result = GitUtils.delete_repo(nonexistent)

        assert result is True


class TestGitResult:
    """GitResult数据类测试"""

    def test_git_result_defaults(self):
        """测试默认值"""
        result = GitResult(success=True, message="Test")

        assert result.success is True
        assert result.message == "Test"
        assert result.commit_hash is None
        assert result.changed_files == 0

    def test_git_result_all_fields(self):
        """测试所有字段"""
        result = GitResult(success=True, message="Success", commit_hash="abcd1234", changed_files=5)

        assert result.success is True
        assert result.message == "Success"
        assert result.commit_hash == "abcd1234"
        assert result.changed_files == 5
