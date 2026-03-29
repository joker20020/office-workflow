# -*- coding: utf-8 -*-
"""
PackageLoader 测试模块

测试包清单解析和节点加载功能：
- parse_manifest: 解析 package.json
- validate_manifest: 验证清单字段
- load_nodes: 动态加载节点定义
- check_requirements: 检查依赖
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.nodes.package_loader import (
    PackageLoader,
    PackageManifest,
    _is_valid_package_id,
    _is_valid_version,
    _is_valid_url,
)


class TestPackageManifest:
    """PackageManifest 数据类测试"""

    def test_manifest_creation(self):
        """测试创建清单对象"""
        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
            author="Test Author",
            description="Test description",
            repository="https://github.com/example/test",
            branch="main",
            nodes=["node1", "node2"],
        )

        assert manifest.id == "com.example.test"
        assert manifest.name == "Test Package"
        assert manifest.version == "1.0.0"
        assert manifest.author == "Test Author"
        assert manifest.description == "Test description"
        assert manifest.repository == "https://github.com/example/test"
        assert manifest.branch == "main"
        assert manifest.nodes == ["node1", "node2"]

    def test_manifest_default_values(self):
        """测试清单默认值"""
        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
        )

        assert manifest.author == ""
        assert manifest.description == ""
        assert manifest.repository == ""
        assert manifest.branch == "main"
        assert manifest.nodes == []

    def test_manifest_to_dict(self):
        """测试转换为字典"""
        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
            author="Test Author",
            nodes=["node1"],
        )

        result = manifest.to_dict()

        assert result["id"] == "com.example.test"
        assert result["name"] == "Test Package"
        assert result["version"] == "1.0.0"
        assert result["author"] == "Test Author"
        assert result["nodes"] == ["node1"]


class TestParseManifest:
    """parse_manifest 方法测试"""

    def test_parse_valid_manifest(self, tmp_path: Path):
        """测试解析有效的清单文件"""
        pkg_dir = tmp_path / "test_package"
        pkg_dir.mkdir()

        manifest_data = {
            "id": "com.example.test",
            "name": "Test Package",
            "version": "1.0.0",
            "author": "Test Author",
            "description": "Test description",
            "repository": "https://github.com/example/test",
            "branch": "develop",
            "nodes": ["node1", "node2"],
        }

        manifest_path = pkg_dir / "package.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        manifest = PackageLoader.parse_manifest(pkg_dir)

        assert manifest is not None
        assert manifest.id == "com.example.test"
        assert manifest.name == "Test Package"
        assert manifest.version == "1.0.0"
        assert manifest.author == "Test Author"
        assert manifest.description == "Test description"
        assert manifest.repository == "https://github.com/example/test"
        assert manifest.branch == "develop"
        assert manifest.nodes == ["node1", "node2"]

    def test_parse_manifest_with_fixture(self):
        """测试使用现有测试 fixture 解析清单"""
        fixture_path = Path(__file__).parent / "fixtures" / "mock_package"

        manifest = PackageLoader.parse_manifest(fixture_path)

        assert manifest is not None
        assert manifest.id == "com.test.mock-nodes"
        assert manifest.name == "Mock Test Nodes"
        assert manifest.version == "1.0.0"
        assert manifest.author == "Test Author"
        assert "mock.process" in manifest.nodes
        assert "mock.transform" in manifest.nodes

    def test_parse_missing_manifest(self, tmp_path: Path):
        """测试清单文件不存在"""
        pkg_dir = tmp_path / "no_manifest"
        pkg_dir.mkdir()

        manifest = PackageLoader.parse_manifest(pkg_dir)

        assert manifest is None

    def test_parse_invalid_json(self, tmp_path: Path):
        """测试无效的 JSON 格式"""
        pkg_dir = tmp_path / "invalid_json"
        pkg_dir.mkdir()

        manifest_path = pkg_dir / "package.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")

        manifest = PackageLoader.parse_manifest(pkg_dir)

        assert manifest is None

    def test_parse_missing_required_field(self, tmp_path: Path):
        """测试缺少必需字段"""
        pkg_dir = tmp_path / "missing_field"
        pkg_dir.mkdir()

        # 缺少 name 字段
        manifest_data = {
            "id": "com.example.test",
            "version": "1.0.0",
        }

        manifest_path = pkg_dir / "package.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        manifest = PackageLoader.parse_manifest(pkg_dir)

        assert manifest is None

    def test_parse_minimal_manifest(self, tmp_path: Path):
        """测试最小化的清单文件"""
        pkg_dir = tmp_path / "minimal"
        pkg_dir.mkdir()

        manifest_data = {
            "id": "com.example.minimal",
            "name": "Minimal",
            "version": "0.1.0",
        }

        manifest_path = pkg_dir / "package.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        manifest = PackageLoader.parse_manifest(pkg_dir)

        assert manifest is not None
        assert manifest.id == "com.example.minimal"
        assert manifest.author == ""
        assert manifest.nodes == []


class TestValidateManifest:
    """validate_manifest 方法测试"""

    def test_validate_valid_manifest(self):
        """测试验证有效的清单"""
        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
            repository="https://github.com/example/test",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert errors == []

    def test_validate_invalid_package_id_single_part(self):
        """测试无效的包 ID（只有一部分）"""
        manifest = PackageManifest(
            id="invalid",
            name="Test Package",
            version="1.0.0",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) == 1
        assert "Invalid package ID" in errors[0]

    def test_validate_invalid_package_id_empty_part(self):
        """测试无效的包 ID（包含空部分）"""
        manifest = PackageManifest(
            id="com..test",
            name="Test Package",
            version="1.0.0",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) == 1

    def test_validate_empty_package_id(self):
        """测试空的包 ID"""
        manifest = PackageManifest(
            id="",
            name="Test Package",
            version="1.0.0",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) >= 1
        assert any("Package ID" in e for e in errors)

    def test_validate_empty_name(self):
        """测试空的包名"""
        manifest = PackageManifest(
            id="com.example.test",
            name="",
            version="1.0.0",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) == 1
        assert "name is required" in errors[0]

    def test_validate_invalid_version_format(self):
        """测试无效的版本格式"""
        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="v1.0.0",  # 不应该有 'v' 前缀
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) == 1
        assert "Invalid version" in errors[0]

    def test_validate_empty_version(self):
        """测试空的版本号"""
        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) >= 1

    def test_validate_invalid_repository_url(self):
        """测试无效的仓库 URL"""
        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
            repository="not-a-url",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) == 1
        assert "Invalid repository URL" in errors[0]

    def test_validate_multiple_errors(self):
        """测试多个验证错误"""
        manifest = PackageManifest(
            id="invalid",
            name="",
            version="bad",
            repository="not-url",
        )

        errors = PackageLoader.validate_manifest(manifest)

        assert len(errors) >= 3


class TestLoadNodes:
    """load_nodes 方法测试"""

    def test_load_nodes_from_fixture(self):
        """测试从现有 fixture 加载节点"""
        fixture_path = Path(__file__).parent / "fixtures" / "mock_package"

        manifest = PackageManifest(
            id="com.test.mock-nodes",
            name="Mock Test Nodes",
            version="1.0.0",
        )

        nodes = PackageLoader.load_nodes(fixture_path, manifest)

        assert len(nodes) == 2
        node_types = [n.node_type for n in nodes]
        assert "mock.process" in node_types
        assert "mock.transform" in node_types

    def test_load_nodes_missing_nodes_dir(self, tmp_path: Path):
        """测试节点目录不存在"""
        pkg_dir = tmp_path / "no_nodes"
        pkg_dir.mkdir()

        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
        )

        nodes = PackageLoader.load_nodes(pkg_dir, manifest)

        assert nodes == []

    def test_load_nodes_missing_init(self, tmp_path: Path):
        """测试 __init__.py 不存在"""
        pkg_dir = tmp_path / "no_init"
        nodes_dir = pkg_dir / "nodes"
        nodes_dir.mkdir(parents=True)

        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
        )

        nodes = PackageLoader.load_nodes(pkg_dir, manifest)

        assert nodes == []

    def test_load_nodes_with_valid_module(self, tmp_path: Path):
        """测试加载有效的节点模块"""
        pkg_dir = tmp_path / "valid_module"
        nodes_dir = pkg_dir / "nodes"
        nodes_dir.mkdir(parents=True)

        # 创建 __init__.py
        init_content = """
from src.engine.definitions import NodeDefinition, PortDefinition, PortType

test_node = NodeDefinition(
    node_type="test.custom",
    display_name="Custom Test Node",
    description="A custom test node",
    category="test",
    icon="🔬",
    inputs=[],
    outputs=[],
    execute=lambda: {},
)
"""
        init_path = nodes_dir / "__init__.py"
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)

        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
        )

        nodes = PackageLoader.load_nodes(pkg_dir, manifest)

        assert len(nodes) == 1
        assert nodes[0].node_type == "test.custom"

    def test_load_nodes_skips_private_attributes(self, tmp_path: Path):
        """测试跳过私有属性"""
        pkg_dir = tmp_path / "private_attrs"
        nodes_dir = pkg_dir / "nodes"
        nodes_dir.mkdir(parents=True)

        init_content = """
from src.engine.definitions import NodeDefinition

_public_node = NodeDefinition(
    node_type="test.public",
    display_name="Public",
    execute=lambda: {},
)

__private_node = NodeDefinition(
    node_type="test.private",
    display_name="Private",
    execute=lambda: {},
)
"""
        init_path = nodes_dir / "__init__.py"
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)

        manifest = PackageManifest(
            id="com.example.test",
            name="Test Package",
            version="1.0.0",
        )

        nodes = PackageLoader.load_nodes(pkg_dir, manifest)

        # 应该只加载非下划线开头的属性
        node_types = [n.node_type for n in nodes]
        assert "test.public" not in node_types  # _public_node 被跳过
        assert "test.private" not in node_types  # __private_node 被跳过


class TestCheckRequirements:
    """check_requirements 方法测试"""

    def test_check_requirements_exists(self, tmp_path: Path):
        """测试检查存在的依赖文件"""
        pkg_dir = tmp_path / "with_reqs"
        pkg_dir.mkdir()

        req_content = """requests>=2.0.0
numpy>=1.0.0
# 这是一个注释
pandas>=2.0.0
"""
        req_path = pkg_dir / "requirements.txt"
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(req_content)

        reqs = PackageLoader.check_requirements(pkg_dir)

        assert reqs is not None
        assert len(reqs) == 3  # 注释行被跳过
        assert "requests>=2.0.0" in reqs
        assert "numpy>=1.0.0" in reqs
        assert "pandas>=2.0.0" in reqs

    def test_check_requirements_missing(self, tmp_path: Path):
        """测试依赖文件不存在"""
        pkg_dir = tmp_path / "no_reqs"
        pkg_dir.mkdir()

        reqs = PackageLoader.check_requirements(pkg_dir)

        assert reqs is None

    def test_check_requirements_empty_lines(self, tmp_path: Path):
        """测试包含空行的依赖文件"""
        pkg_dir = tmp_path / "empty_lines"
        pkg_dir.mkdir()

        req_content = """requests>=2.0.0

numpy>=1.0.0

"""
        req_path = pkg_dir / "requirements.txt"
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(req_content)

        reqs = PackageLoader.check_requirements(pkg_dir)

        assert reqs is not None
        assert len(reqs) == 2

    def test_check_requirements_only_comments(self, tmp_path: Path):
        """测试只有注释的依赖文件"""
        pkg_dir = tmp_path / "only_comments"
        pkg_dir.mkdir()

        req_content = """# Comment 1
# Comment 2
"""
        req_path = pkg_dir / "requirements.txt"
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(req_content)

        reqs = PackageLoader.check_requirements(pkg_dir)

        assert reqs is not None
        assert len(reqs) == 0


class TestValidationHelpers:
    """验证辅助函数测试"""

    def test_is_valid_package_id(self):
        """测试包 ID 验证"""
        # 有效的包 ID
        assert _is_valid_package_id("com.example.test") is True
        assert _is_valid_package_id("org.company.package") is True
        assert _is_valid_package_id("a.b") is True
        assert _is_valid_package_id("com.test123.nodes") is True

        # 无效的包 ID
        assert _is_valid_package_id("single") is False
        assert _is_valid_package_id("") is False
        assert _is_valid_package_id("com..test") is False
        assert _is_valid_package_id("com.test.") is False
        assert _is_valid_package_id(".com.test") is False
        assert _is_valid_package_id("com.test-with-dash") is False

    def test_is_valid_version(self):
        """测试版本号验证"""
        # 有效的版本号
        assert _is_valid_version("1.0.0") is True
        assert _is_valid_version("2.0") is True
        assert _is_valid_version("1") is True
        assert _is_valid_version("0.0.1") is True
        assert _is_valid_version("10.20.30") is True

        # 无效的版本号
        assert _is_valid_version("") is False
        assert _is_valid_version("1.0.0.0") is False  # 超过3部分
        assert _is_valid_version("v1.0.0") is False  # 有前缀
        assert _is_valid_version("1.0.0-beta") is False  # 有后缀
        assert _is_valid_version("1.x.0") is False  # 非数字

    def test_is_valid_url(self):
        """测试 URL 验证"""
        # 有效的 URL
        assert _is_valid_url("https://github.com/example/repo") is True
        assert _is_valid_url("http://example.com/repo") is True
        assert _is_valid_url("git@github.com:example/repo.git") is True
        assert _is_valid_url("https://gitlab.com/user/project") is True

        # 无效的 URL
        assert _is_valid_url("not-a-url") is False
        assert _is_valid_url("ftp://example.com") is False
        assert _is_valid_url("") is False
        assert _is_valid_url("github.com/example") is False  # 缺少协议
