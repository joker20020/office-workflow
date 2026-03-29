# -*- coding: utf-8 -*-
"""
NodePackageManager 测试模块

测试节点包管理器的核心功能：
- install: 从 Git 仓库安装包
- update: 更新已安装的包
- enable/disable: 启用/禁用包
- delete: 删除包
- load_all_enabled/unload_all: 生命周期管理
"""

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from src.core.event_bus import EventBus, EventType
from src.engine.node_engine import NodeEngine
from src.nodes.git_utils import GitResult
from src.nodes.package_loader import PackageManifest
from src.nodes.package_manager import (
    NodePackageManager,
    InstallResult,
    UpdateResult,
)
from src.storage.database import Database


# ==================== Fixtures ====================


@pytest.fixture
def mock_database():
    """创建模拟数据库"""
    db = Mock(spec=Database)
    db.session = MagicMock()
    return db


@pytest.fixture
def mock_node_engine():
    """创建模拟节点引擎"""
    engine = Mock(spec=NodeEngine)
    engine.register_node_type = Mock()
    engine.unregister_node_type = Mock()
    return engine


@pytest.fixture
def mock_event_bus():
    """创建模拟事件总线"""
    return Mock(spec=EventBus)


@pytest.fixture
def packages_dir(tmp_path: Path) -> Path:
    """创建包目录"""
    return tmp_path / "node_packages"


@pytest.fixture
def manager(
    packages_dir: Path,
    mock_database: Mock,
    mock_node_engine: Mock,
    mock_event_bus: Mock,
) -> NodePackageManager:
    """创建包管理器实例"""
    return NodePackageManager(
        packages_dir=packages_dir,
        database=mock_database,
        node_engine=mock_node_engine,
        event_bus=mock_event_bus,
    )


@pytest.fixture
def manager_no_event_bus(
    packages_dir: Path,
    mock_database: Mock,
    mock_node_engine: Mock,
) -> NodePackageManager:
    """创建没有事件总线的包管理器"""
    return NodePackageManager(
        packages_dir=packages_dir,
        database=mock_database,
        node_engine=mock_node_engine,
        event_bus=None,
    )


# ==================== Install Tests ====================


class TestNodePackageManagerInstall:
    """install 方法测试"""

    @patch("src.nodes.package_manager.GitUtils")
    @patch("src.nodes.package_manager.PackageLoader")
    def test_install_success(
        self,
        mock_loader: Mock,
        mock_git: Mock,
        manager: NodePackageManager,
    ):
        """测试成功安装包"""
        mock_git.clone.return_value = GitResult(
            success=True,
            message="克隆成功",
            commit_hash="abc123",
        )

        mock_manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
            author="Test Author",
            description="Test description",
        )
        mock_loader.parse_manifest.return_value = mock_manifest
        mock_loader.validate_manifest.return_value = []
        mock_loader.load_nodes.return_value = []

        mock_repo = Mock()
        mock_repo.create.return_value = {"id": "com.example.test"}
        mock_repo.get_by_repository.return_value = None
        manager._repository = mock_repo

        progress_calls = []
        result = manager.install(
            "https://github.com/example/test",
            branch="main",
            progress_callback=lambda p, m: progress_calls.append((p, m)),
        )

        assert result.success is True
        assert result.package_id == "com.example.test"
        assert "成功" in result.message

        mock_git.clone.assert_called_once()
        mock_repo.create.assert_called_once()

        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == 100

    @patch("src.nodes.package_manager.GitUtils")
    def test_install_clone_failure(
        self,
        mock_git: Mock,
        manager: NodePackageManager,
    ):
        """测试克隆失败"""
        mock_git.clone.return_value = GitResult(
            success=False,
            message="网络错误",
        )

        mock_repo = Mock()
        mock_repo.get_by_repository.return_value = None
        manager._repository = mock_repo

        result = manager.install("https://github.com/example/test")

        assert result.success is False
        assert "网络错误" in result.message
        assert result.package_id is None

    @patch("src.nodes.package_manager.GitUtils")
    @patch("src.nodes.package_manager.PackageLoader")
    def test_install_invalid_manifest(
        self,
        mock_loader: Mock,
        mock_git: Mock,
        manager: NodePackageManager,
    ):
        """测试无效的包清单"""
        mock_git.clone.return_value = GitResult(
            success=True,
            message="克隆成功",
        )

        mock_loader.parse_manifest.return_value = None

        mock_repo = Mock()
        mock_repo.get_by_repository.return_value = None
        manager._repository = mock_repo

        result = manager.install("https://github.com/example/test")

        assert result.success is False
        assert "package.json" in result.message.lower()
        mock_git.delete_repo.assert_called_once()

    @patch("src.nodes.package_manager.GitUtils")
    @patch("src.nodes.package_manager.PackageLoader")
    def test_install_validation_errors(
        self,
        mock_loader: Mock,
        mock_git: Mock,
        manager: NodePackageManager,
    ):
        """测试清单验证失败"""
        mock_git.clone.return_value = GitResult(
            success=True,
            message="克隆成功",
        )

        mock_manifest = PackageManifest(
            id="invalid",
            name="Test",
            version="1.0.0",
        )
        mock_loader.parse_manifest.return_value = mock_manifest
        mock_loader.validate_manifest.return_value = ["Invalid package ID"]

        mock_repo = Mock()
        mock_repo.get_by_repository.return_value = None
        manager._repository = mock_repo

        result = manager.install("https://github.com/example/test")

        assert result.success is False
        assert "Invalid package ID" in result.message
        mock_git.delete_repo.assert_called_once()

    def test_install_already_exists_by_repository(
        self,
        manager: NodePackageManager,
    ):
        """测试从同一仓库已安装"""
        mock_repo = Mock()
        mock_repo.get_by_repository.return_value = {
            "id": "com.example.existing",
            "name": "Existing",
        }
        manager._repository = mock_repo

        result = manager.install("https://github.com/example/test")

        assert result.success is False
        assert "already installed" in result.message.lower() or "已" in result.message

    @patch("src.nodes.package_manager.GitUtils")
    @patch("src.nodes.package_manager.PackageLoader")
    def test_install_with_nodes(
        self,
        mock_loader: Mock,
        mock_git: Mock,
        manager: NodePackageManager,
    ):
        """测试安装包含节点的包"""
        mock_git.clone.return_value = GitResult(
            success=True,
            message="克隆成功",
        )

        mock_manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
        )
        mock_loader.parse_manifest.return_value = mock_manifest
        mock_loader.validate_manifest.return_value = []

        mock_node1 = Mock()
        mock_node1.node_type = "test.node1"
        mock_node2 = Mock()
        mock_node2.node_type = "test.node2"
        mock_loader.load_nodes.return_value = [mock_node1, mock_node2]

        mock_repo = Mock()
        mock_repo.create.return_value = {"id": "com.example.test"}
        mock_repo.get_by_repository.return_value = None
        manager._repository = mock_repo

        result = manager.install("https://github.com/example/test")

        assert result.success is True
        assert result.nodes_loaded == 2
        assert manager._node_engine.register_node_type.call_count == 2

    def test_install_event_published(
        self,
        manager: NodePackageManager,
    ):
        """测试安装时发布事件"""
        with (
            patch("src.nodes.package_manager.GitUtils") as mock_git,
            patch("src.nodes.package_manager.PackageLoader") as mock_loader,
        ):
            mock_git.clone.return_value = GitResult(success=True, message="OK")
            mock_manifest = PackageManifest(
                id="com.example.test",
                name="Test",
                version="1.0.0",
            )
            mock_loader.parse_manifest.return_value = mock_manifest
            mock_loader.validate_manifest.return_value = []
            mock_loader.load_nodes.return_value = []

            mock_repo = Mock()
            mock_repo.create.return_value = {"id": "com.example.test"}
            mock_repo.get_by_repository.return_value = None
            manager._repository = mock_repo

            manager.install("https://github.com/example/test")

            manager._event_bus.publish.assert_called()
            call_args = manager._event_bus.publish.call_args
            assert call_args[0][0] == EventType.PACKAGE_INSTALLED
            assert call_args[0][1]["package_id"] == "com.example.test"


# ==================== Update Tests ====================


class TestNodePackageManagerUpdate:
    """update 方法测试"""

    def test_update_success_with_changes(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试成功更新（有变更）"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "name": "Test Package",
            "version": "1.0.0",
            "local_path": str(pkg_dir),
            "branch": "main",
        }
        manager._repository = mock_repo

        with (
            patch("src.nodes.package_manager.GitUtils") as mock_git,
            patch("src.nodes.package_manager.PackageLoader") as mock_loader,
        ):
            mock_git.pull.return_value = GitResult(
                success=True,
                message="拉取成功",
                changed_files=5,
                commit_hash="def456",
            )

            mock_manifest = PackageManifest(
                id="com.example.test",
                name="Test Package Updated",
                version="2.0.0",
            )
            mock_loader.parse_manifest.return_value = mock_manifest
            mock_loader.load_nodes.return_value = []

            result = manager.update("com.example.test")

            assert result.success is True
            assert result.updated is True
            assert "2.0.0" in result.message

    def test_update_no_changes(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试更新（无变更）"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "local_path": str(pkg_dir),
            "branch": "main",
        }
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.GitUtils") as mock_git:
            mock_git.pull.return_value = GitResult(
                success=True,
                message="已是最新",
                changed_files=0,
            )

            result = manager.update("com.example.test")

            assert result.success is True
            assert result.updated is False

    def test_update_package_not_found(
        self,
        manager: NodePackageManager,
    ):
        """测试更新不存在的包"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        manager._repository = mock_repo

        result = manager.update("com.example.nonexistent")

        assert result.success is False
        assert "not found" in result.message.lower() or "不存在" in result.message

    def test_update_pull_failure(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试拉取失败"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "local_path": str(pkg_dir),
            "branch": "main",
        }
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.GitUtils") as mock_git:
            mock_git.pull.return_value = GitResult(
                success=False,
                message="网络错误",
            )

            result = manager.update("com.example.test")

            assert result.success is False
            assert "网络错误" in result.message

    def test_update_unregisters_old_nodes(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试更新时注销旧节点"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        manager._loaded["com.example.test"] = {
            "node_types": ["old.node1", "old.node2"],
            "path": pkg_dir,
        }

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "local_path": str(pkg_dir),
            "branch": "main",
        }
        manager._repository = mock_repo

        with (
            patch("src.nodes.package_manager.GitUtils") as mock_git,
            patch("src.nodes.package_manager.PackageLoader") as mock_loader,
        ):
            mock_git.pull.return_value = GitResult(
                success=True,
                message="拉取成功",
                changed_files=1,
            )

            mock_manifest = PackageManifest(
                id="com.example.test",
                name="Test",
                version="2.0.0",
            )
            mock_loader.parse_manifest.return_value = mock_manifest
            mock_loader.load_nodes.return_value = []

            result = manager.update("com.example.test")

            assert result.success is True
            assert manager._node_engine.unregister_node_type.call_count == 2


# ==================== Enable/Disable Tests ====================


class TestNodePackageManagerEnableDisable:
    """enable 和 disable 方法测试"""

    def test_enable_success(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试成功启用包"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "name": "Test Package",
            "version": "1.0.0",
            "local_path": str(pkg_dir),
            "enabled": False,
        }
        mock_repo.set_enabled.return_value = True
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.PackageLoader") as mock_loader:
            mock_manifest = PackageManifest(
                id="com.example.test",
                name="Test Package",
                version="1.0.0",
            )
            mock_loader.parse_manifest.return_value = mock_manifest
            mock_loader.load_nodes.return_value = []

            result = manager.enable("com.example.test")

            assert result is True
            mock_repo.set_enabled.assert_called_once_with("com.example.test", True)

    def test_enable_already_enabled(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试启用已启用的包"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "local_path": str(pkg_dir),
            "enabled": True,
        }
        manager._repository = mock_repo

        result = manager.enable("com.example.test")

        assert result is True

    def test_enable_package_not_found(
        self,
        manager: NodePackageManager,
    ):
        """测试启用不存在的包"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        manager._repository = mock_repo

        result = manager.enable("com.example.nonexistent")

        assert result is False

    def test_disable_success(
        self,
        manager: NodePackageManager,
    ):
        """测试成功禁用包"""
        manager._loaded["com.example.test"] = {
            "node_types": ["test.node1", "test.node2"],
        }

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "enabled": True,
        }
        mock_repo.set_enabled.return_value = True
        manager._repository = mock_repo

        result = manager.disable("com.example.test")

        assert result is True
        mock_repo.set_enabled.assert_called_once_with("com.example.test", False)
        assert manager._node_engine.unregister_node_type.call_count == 2
        assert "com.example.test" not in manager._loaded

    def test_disable_already_disabled(
        self,
        manager: NodePackageManager,
    ):
        """测试禁用已禁用的包"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "enabled": False,
        }
        manager._repository = mock_repo

        result = manager.disable("com.example.test")

        assert result is True

    def test_disable_package_not_found(
        self,
        manager: NodePackageManager,
    ):
        """测试禁用不存在的包"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        manager._repository = mock_repo

        result = manager.disable("com.example.nonexistent")

        assert result is False


# ==================== Delete Tests ====================


class TestNodePackageManagerDelete:
    """delete 方法测试"""

    def test_delete_success(
        self,
        manager: NodePackageManager,
    ):
        """测试成功删除包"""
        manager._loaded["com.example.test"] = {
            "node_types": ["test.node1"],
        }

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "local_path": "/path/to/package",
        }
        mock_repo.delete.return_value = True
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.GitUtils") as mock_git:
            mock_git.delete_repo.return_value = True

            result = manager.delete("com.example.test")

            assert result is True
            mock_repo.delete.assert_called_once_with("com.example.test")
            mock_git.delete_repo.assert_called_once()
            assert "com.example.test" not in manager._loaded

    def test_delete_package_not_found(
        self,
        manager: NodePackageManager,
    ):
        """测试删除不存在的包"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        manager._repository = mock_repo

        result = manager.delete("com.example.nonexistent")

        assert result is False

    def test_delete_unregisters_nodes(
        self,
        manager: NodePackageManager,
    ):
        """测试删除时注销节点"""
        manager._loaded["com.example.test"] = {
            "node_types": ["test.node1", "test.node2", "test.node3"],
        }

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "local_path": "/path/to/package",
        }
        mock_repo.delete.return_value = True
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.GitUtils"):
            result = manager.delete("com.example.test")

            assert result is True
            assert manager._node_engine.unregister_node_type.call_count == 3

    def test_delete_event_published(
        self,
        manager: NodePackageManager,
    ):
        """测试删除时发布事件"""
        manager._loaded["com.example.test"] = {"node_types": []}

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "local_path": "/path/to/package",
        }
        mock_repo.delete.return_value = True
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.GitUtils"):
            manager.delete("com.example.test")

            call_args = manager._event_bus.publish.call_args
            assert call_args[0][0] == EventType.PACKAGE_REMOVED
            assert call_args[0][1]["package_id"] == "com.example.test"


# ==================== Lifecycle Tests ====================


class TestNodePackageManagerLifecycle:
    """load_all_enabled 和 unload_all 方法测试"""

    def test_load_all_enabled_success(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试成功加载所有启用的包"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_all.return_value = [
            {
                "id": "com.example.test1",
                "name": "Test 1",
                "version": "1.0.0",
                "local_path": str(pkg_dir),
                "enabled": True,
            }
        ]
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.PackageLoader") as mock_loader:
            mock_manifest = PackageManifest(
                id="com.example.test1",
                name="Test 1",
                version="1.0.0",
            )
            mock_loader.parse_manifest.return_value = mock_manifest
            mock_loader.load_nodes.return_value = []

            count = manager.load_all_enabled()

            assert count == 1
            assert "com.example.test1" in manager._loaded

    def test_load_all_enabled_skips_missing_path(
        self,
        manager: NodePackageManager,
    ):
        """测试跳过没有本地路径的包"""
        mock_repo = Mock()
        mock_repo.get_all.return_value = [
            {
                "id": "com.example.test",
                "name": "Test",
                "version": "1.0.0",
                "local_path": None,
                "enabled": True,
            }
        ]
        manager._repository = mock_repo

        count = manager.load_all_enabled()

        assert count == 0
        assert len(manager._loaded) == 0

    def test_load_all_enabled_skips_nonexistent_path(
        self,
        manager: NodePackageManager,
    ):
        """测试跳过路径不存在的包"""
        mock_repo = Mock()
        mock_repo.get_all.return_value = [
            {
                "id": "com.example.test",
                "name": "Test",
                "version": "1.0.0",
                "local_path": "/nonexistent/path",
                "enabled": True,
            }
        ]
        manager._repository = mock_repo

        count = manager.load_all_enabled()

        assert count == 0

    def test_load_all_enabled_skips_invalid_manifest(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试跳过无效清单的包"""
        pkg_dir = tmp_path / "node_packages" / "test-package"
        pkg_dir.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_all.return_value = [
            {
                "id": "com.example.test",
                "local_path": str(pkg_dir),
                "enabled": True,
            }
        ]
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.PackageLoader") as mock_loader:
            mock_loader.parse_manifest.return_value = None

            count = manager.load_all_enabled()

            assert count == 0

    def test_load_all_enabled_multiple_packages(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试加载多个包"""
        pkg_dir1 = tmp_path / "node_packages" / "pkg1"
        pkg_dir2 = tmp_path / "node_packages" / "pkg2"
        pkg_dir1.mkdir(parents=True)
        pkg_dir2.mkdir(parents=True)

        mock_repo = Mock()
        mock_repo.get_all.return_value = [
            {
                "id": "com.example.test1",
                "local_path": str(pkg_dir1),
                "enabled": True,
            },
            {
                "id": "com.example.test2",
                "local_path": str(pkg_dir2),
                "enabled": True,
            },
        ]
        manager._repository = mock_repo

        with patch("src.nodes.package_manager.PackageLoader") as mock_loader:

            def create_manifest(pkg_id):
                return PackageManifest(
                    id=pkg_id,
                    name=f"Test {pkg_id}",
                    version="1.0.0",
                )

            mock_loader.parse_manifest.side_effect = lambda p: create_manifest(
                "com.example.test1" if "pkg1" in str(p) else "com.example.test2"
            )
            mock_loader.load_nodes.return_value = []

            count = manager.load_all_enabled()

            assert count == 2
            assert "com.example.test1" in manager._loaded
            assert "com.example.test2" in manager._loaded

    def test_unload_all(
        self,
        manager: NodePackageManager,
    ):
        """测试卸载所有包"""
        manager._loaded["com.example.test1"] = {
            "node_types": ["node1", "node2"],
        }
        manager._loaded["com.example.test2"] = {
            "node_types": ["node3"],
        }

        manager.unload_all()

        assert len(manager._loaded) == 0
        assert manager._node_engine.unregister_node_type.call_count == 3


# ==================== Discovery Tests ====================


class TestNodePackageManagerDiscovery:
    """discover_packages 和 get_package 方法测试"""

    def test_discover_packages_empty(
        self,
        manager: NodePackageManager,
    ):
        """测试发现空目录"""
        packages = manager.discover_packages()

        assert packages == []

    def test_discover_packages_with_packages(
        self,
        manager: NodePackageManager,
        tmp_path: Path,
    ):
        """测试发现已安装的包"""
        pkg_dir = manager._packages_dir / "test-package"
        pkg_dir.mkdir(parents=True)

        import json

        manifest_data = {
            "id": "com.example.test",
            "name": "Test Package",
            "version": "1.0.0",
        }
        with open(pkg_dir / "package.json", "w") as f:
            json.dump(manifest_data, f)

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "enabled": True,
        }
        manager._repository = mock_repo

        packages = manager.discover_packages()

        assert len(packages) == 1
        assert packages[0]["id"] == "com.example.test"

    def test_get_package_existing(
        self,
        manager: NodePackageManager,
    ):
        """测试获取存在的包"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "name": "Test Package",
            "version": "1.0.0",
        }
        manager._repository = mock_repo

        pkg = manager.get_package("com.example.test")

        assert pkg is not None
        assert pkg["id"] == "com.example.test"

    def test_get_package_nonexistent(
        self,
        manager: NodePackageManager,
    ):
        """测试获取不存在的包"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        manager._repository = mock_repo

        pkg = manager.get_package("com.example.nonexistent")

        assert pkg is None


# ==================== Helper Method Tests ====================


class TestNodePackageManagerHelpers:
    """辅助方法测试"""

    def test_is_loaded(
        self,
        manager: NodePackageManager,
    ):
        """测试 is_loaded 方法"""
        assert manager.is_loaded("com.example.test") is False

        manager._loaded["com.example.test"] = {"node_types": []}

        assert manager.is_loaded("com.example.test") is True

    def test_get_loaded_packages(
        self,
        manager: NodePackageManager,
    ):
        """测试 get_loaded_packages 方法"""
        manager._loaded["com.example.test"] = {"node_types": ["node1"]}

        loaded = manager.get_loaded_packages()

        assert "com.example.test" in loaded
        assert loaded["com.example.test"]["node_types"] == ["node1"]

    def test_packages_dir_property(
        self,
        manager: NodePackageManager,
        packages_dir: Path,
    ):
        """测试 packages_dir 属性"""
        assert manager.packages_dir == packages_dir

    def test_no_event_bus_no_crash(
        self,
        manager_no_event_bus: NodePackageManager,
    ):
        """测试没有事件总线时不会崩溃"""
        manager_no_event_bus._loaded["com.example.test"] = {"node_types": []}

        mock_repo = Mock()
        mock_repo.get_by_id.return_value = {
            "id": "com.example.test",
            "enabled": True,
        }
        mock_repo.set_enabled.return_value = True
        manager_no_event_bus._repository = mock_repo

        result = manager_no_event_bus.disable("com.example.test")
        assert result is True
