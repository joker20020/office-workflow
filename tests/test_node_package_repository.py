# -*- coding: utf-8 -*-
"""
NodePackageRepository测试模块

测试节点包存储库功能：
- 创建包记录
- 查询包信息
- 更新包信息
- 删除包记录
- 启用/禁用包
"""

from pathlib import Path
from datetime import datetime

import pytest

from src.storage.database import Database
from src.nodes.repository import NodePackageRepository


@pytest.fixture
def database(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.create_tables()
    yield db
    db.close()


@pytest.fixture
def repository(database: Database):
    return NodePackageRepository(database)


@pytest.fixture
def sample_package_data():
    return {
        "id": "com.example.text-tools",
        "name": "Text Tools",
        "version": "1.0.0",
        "author": "Test Author",
        "description": "Text processing nodes",
        "repository_url": "https://github.com/example/text-tools",
        "branch": "main",
        "local_path": "/path/to/text-tools",
        "enabled": True,
    }


class TestNodePackageRepositoryCreate:
    def test_create_success(self, repository: NodePackageRepository, sample_package_data: dict):
        result = repository.create(sample_package_data)

        assert result is not None
        assert result["id"] == "com.example.text-tools"
        assert result["name"] == "Text Tools"
        assert result["version"] == "1.0.0"
        assert result["author"] == "Test Author"
        assert result["enabled"] is True

    def test_create_minimal_data(self, repository: NodePackageRepository):
        minimal_data = {
            "id": "com.example.minimal",
            "name": "Minimal",
            "version": "0.1.0",
            "repository_url": "https://github.com/example/minimal",
        }

        result = repository.create(minimal_data)

        assert result is not None
        assert result["author"] == ""
        assert result["description"] == ""
        assert result["branch"] == "main"
        assert result["enabled"] is True

    def test_create_duplicate_id_fails(
        self, repository: NodePackageRepository, sample_package_data: dict
    ):
        repository.create(sample_package_data)

        duplicate_data = sample_package_data.copy()
        duplicate_data["name"] = "Different Name"

        result = repository.create(duplicate_data)

        assert result is None


class TestNodePackageRepositoryGetById:
    def test_get_by_id_exists(self, repository: NodePackageRepository, sample_package_data: dict):
        repository.create(sample_package_data)

        result = repository.get_by_id("com.example.text-tools")

        assert result is not None
        assert result["id"] == "com.example.text-tools"
        assert result["name"] == "Text Tools"

    def test_get_by_id_not_exists(self, repository: NodePackageRepository):
        result = repository.get_by_id("com.example.nonexistent")

        assert result is None


class TestNodePackageRepositoryGetAll:
    def test_get_all_empty(self, repository: NodePackageRepository):
        result = repository.get_all()

        assert result == []

    def test_get_all_multiple(self, repository: NodePackageRepository):
        packages = [
            {
                "id": "com.example.alpha",
                "name": "Alpha",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/alpha",
                "enabled": True,
            },
            {
                "id": "com.example.beta",
                "name": "Beta",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/beta",
                "enabled": False,
            },
            {
                "id": "com.example.gamma",
                "name": "Gamma",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/gamma",
                "enabled": True,
            },
        ]

        for pkg in packages:
            repository.create(pkg)

        result = repository.get_all()

        assert len(result) == 3

    def test_get_all_enabled_only(self, repository: NodePackageRepository):
        packages = [
            {
                "id": "com.example.enabled1",
                "name": "Enabled1",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/enabled1",
                "enabled": True,
            },
            {
                "id": "com.example.disabled",
                "name": "Disabled",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/disabled",
                "enabled": False,
            },
            {
                "id": "com.example.enabled2",
                "name": "Enabled2",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/enabled2",
                "enabled": True,
            },
        ]

        for pkg in packages:
            repository.create(pkg)

        result = repository.get_all(enabled_only=True)

        assert len(result) == 2
        for pkg in result:
            assert pkg["enabled"] is True


class TestNodePackageRepositoryUpdate:
    def test_update_version(self, repository: NodePackageRepository, sample_package_data: dict):
        repository.create(sample_package_data)

        result = repository.update("com.example.text-tools", {"version": "2.0.0"})

        assert result is True
        updated = repository.get_by_id("com.example.text-tools")
        assert updated["version"] == "2.0.0"

    def test_update_multiple_fields(
        self, repository: NodePackageRepository, sample_package_data: dict
    ):
        repository.create(sample_package_data)

        result = repository.update(
            "com.example.text-tools",
            {
                "version": "2.0.0",
                "description": "Updated description",
                "author": "New Author",
            },
        )

        assert result is True
        updated = repository.get_by_id("com.example.text-tools")
        assert updated["version"] == "2.0.0"
        assert updated["description"] == "Updated description"
        assert updated["author"] == "New Author"

    def test_update_nonexistent_package(self, repository: NodePackageRepository):
        result = repository.update("com.example.nonexistent", {"version": "2.0.0"})

        assert result is False

    def test_update_updates_timestamp(
        self, repository: NodePackageRepository, sample_package_data: dict
    ):
        repository.create(sample_package_data)
        original = repository.get_by_id("com.example.text-tools")
        original_updated_at = original["updated_at"]

        import time

        time.sleep(0.01)

        repository.update("com.example.text-tools", {"version": "2.0.0"})

        updated = repository.get_by_id("com.example.text-tools")
        assert updated["updated_at"] >= original_updated_at


class TestNodePackageRepositoryDelete:
    def test_delete_success(self, repository: NodePackageRepository, sample_package_data: dict):
        repository.create(sample_package_data)

        result = repository.delete("com.example.text-tools")

        assert result is True
        assert repository.get_by_id("com.example.text-tools") is None

    def test_delete_nonexistent(self, repository: NodePackageRepository):
        result = repository.delete("com.example.nonexistent")

        assert result is False


class TestNodePackageRepositorySetEnabled:
    def test_set_enabled_true(self, repository: NodePackageRepository, sample_package_data: dict):
        sample_package_data["enabled"] = False
        repository.create(sample_package_data)

        result = repository.set_enabled("com.example.text-tools", True)

        assert result is True
        pkg = repository.get_by_id("com.example.text-tools")
        assert pkg["enabled"] is True

    def test_set_enabled_false(self, repository: NodePackageRepository, sample_package_data: dict):
        repository.create(sample_package_data)

        result = repository.set_enabled("com.example.text-tools", False)

        assert result is True
        pkg = repository.get_by_id("com.example.text-tools")
        assert pkg["enabled"] is False


class TestNodePackageRepositoryExists:
    def test_exists_true(self, repository: NodePackageRepository, sample_package_data: dict):
        repository.create(sample_package_data)

        result = repository.exists("com.example.text-tools")

        assert result is True

    def test_exists_false(self, repository: NodePackageRepository):
        result = repository.exists("com.example.nonexistent")

        assert result is False


class TestNodePackageRepositoryGetByRepository:
    def test_get_by_repository_found(
        self, repository: NodePackageRepository, sample_package_data: dict
    ):
        repository.create(sample_package_data)

        result = repository.get_by_repository("https://github.com/example/text-tools")

        assert result is not None
        assert result["id"] == "com.example.text-tools"

    def test_get_by_repository_not_found(self, repository: NodePackageRepository):
        result = repository.get_by_repository("https://github.com/example/nonexistent")

        assert result is None


class TestNodePackageRepositoryCount:
    def test_count_empty(self, repository: NodePackageRepository):
        result = repository.count()

        assert result == 0

    def test_count_with_packages(self, repository: NodePackageRepository):
        packages = [
            {
                "id": "com.example.pkg1",
                "name": "Package 1",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/pkg1",
                "enabled": True,
            },
            {
                "id": "com.example.pkg2",
                "name": "Package 2",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/pkg2",
                "enabled": False,
            },
            {
                "id": "com.example.pkg3",
                "name": "Package 3",
                "version": "1.0.0",
                "repository_url": "https://github.com/example/pkg3",
                "enabled": True,
            },
        ]

        for pkg in packages:
            repository.create(pkg)

        assert repository.count() == 3
        assert repository.count(enabled_only=True) == 2
