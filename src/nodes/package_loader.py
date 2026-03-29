# -*- coding: utf-8 -*-
"""
Package Loader Module (包加载器模块)

Parses package.json and dynamically loads node definitions from packages.

Structure:
    node_packages/
    └── package_a/
        ├── package.json      # Package manifest
        ├── nodes/
        │   ├── __init__.py
        │   └── node_1.py
        └── requirements.txt   # Optional dependencies
"""

import importlib.util
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.engine.definitions import NodeDefinition
from src.utils.logger import get_logger

_logger = get_logger(__name__)


@dataclass
class PackageManifest:
    """
    Package manifest from package.json

    Attributes:
        id: Package unique identifier (e.g., "com.example.text-tools")
        name: Display name
        version: Version string (semver)
        author: Author name
        description: Package description
        repository: Git repository URL
        branch: Git branch
        nodes: List of node type identifiers
    """

    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    repository: str = ""
    branch: str = "main"
    nodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "repository": self.repository,
            "branch": self.branch,
            "nodes": self.nodes,
        }


class PackageLoader:
    """
    Package loader for parsing manifests and loading nodes

    Responsibilities:
    - Parse package.json files
    - Validate manifest fields
    - Dynamically load node definitions from Python modules
    - Create NodeDefinition instances from loaded modules

    Example:
        >>> manifest = PackageLoader.parse_manifest(Path("node_packages/my_package"))
        >>> nodes = PackageLoader.load_nodes(Path("node_packages/my_package"), manifest)
    """

    @staticmethod
    def parse_manifest(package_path: Path) -> Optional[PackageManifest]:
        """
        Parse package.json from package directory

        Args:
            package_path: Path to package root directory

        Returns:
            PackageManifest if valid, None if invalid
        """
        manifest_path = package_path / "package.json"

        if not manifest_path.exists():
            _logger.error(f"package.json not found: {manifest_path}")
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            required_fields = ["id", "name", "version"]
            for field_name in required_fields:
                if field_name not in data:
                    _logger.error(f"Missing required field in package.json: {field_name}")
                    return None

            manifest = PackageManifest(
                id=data["id"],
                name=data["name"],
                version=data["version"],
                author=data.get("author", ""),
                description=data.get("description", ""),
                repository=data.get("repository", ""),
                branch=data.get("branch", "main"),
                nodes=data.get("nodes", []),
            )

            _logger.info(f"解析包清单成功: {manifest.id} v{manifest.version}")
            return manifest

        except json.JSONDecodeError as e:
            _logger.error(f"Invalid JSON in package.json: {e}")
            return None
        except Exception as e:
            _logger.error(f"解析包清单失败: {e}", exc_info=True)
            return None

    @staticmethod
    def validate_manifest(manifest: PackageManifest) -> List[str]:
        """
        Validate manifest fields

        Args:
            manifest: Package manifest to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not manifest.id:
            errors.append("Package ID is required")
        elif not _is_valid_package_id(manifest.id):
            errors.append(f"Invalid package ID format: {manifest.id}")

        if not manifest.name:
            errors.append("Package name is required")

        if not manifest.version:
            errors.append("Package version is required")
        elif not _is_valid_version(manifest.version):
            errors.append(f"Invalid version format: {manifest.version}")

        if manifest.repository and not _is_valid_url(manifest.repository):
            errors.append(f"Invalid repository URL: {manifest.repository}")

        return errors

    @staticmethod
    def load_nodes(
        package_path: Path,
        manifest: PackageManifest,
    ) -> List[NodeDefinition]:
        """
        Load node definitions from package

        Dynamically imports Python modules from the nodes/ directory
        and collects NodeDefinition instances.

        Args:
            package_path: Path to package root directory
            manifest: Package manifest

        Returns:
            List of loaded NodeDefinition instances
        """
        nodes_dir = package_path / "nodes"

        if not nodes_dir.exists():
            _logger.warning(f"Nodes directory not found: {nodes_dir}")
            return []

        definitions: List[NodeDefinition] = []

        init_file = nodes_dir / "__init__.py"
        if not init_file.exists():
            _logger.warning(f"__init__.py not found in nodes directory: {nodes_dir}")
            return []

        module_prefix = _sanitize_module_name(manifest.id)

        try:
            # Register parent module in sys.modules for relative imports to work
            if module_prefix not in sys.modules:
                parent_module = types.ModuleType(module_prefix)
                parent_module.__file__ = None
                parent_module.__path__ = [str(nodes_dir.parent)]
                sys.modules[module_prefix] = parent_module

            spec = importlib.util.spec_from_file_location(
                f"{module_prefix}._nodes_init",
                init_file,
            )
            if spec is None or spec.loader is None:
                return []

            init_module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = init_module
            spec.loader.exec_module(init_module)

            for attr_name in dir(init_module):
                if attr_name.startswith("_"):
                    continue

                attr = getattr(init_module, attr_name)

                if isinstance(attr, NodeDefinition):
                    definitions.append(attr)
                    _logger.debug(f"从 __init__.py 加载节点定义: {attr.node_type}")

        except Exception as e:
            _logger.error(f"加载 __init__.py 失败: {e}", exc_info=True)

        for py_file in nodes_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"{module_prefix}.nodes.{py_file.stem}"

            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for attr_name in dir(module):
                    if attr_name.startswith("_"):
                        continue

                    attr = getattr(module, attr_name)

                    if isinstance(attr, NodeDefinition):
                        definitions.append(attr)
                        _logger.debug(f"从 {py_file.name} 加载节点定义: {attr.node_type}")

            except Exception as e:
                _logger.error(f"加载节点模块失败 {py_file}: {e}", exc_info=True)

        _logger.info(f"从包 {manifest.id} 加载了 {len(definitions)} 个节点定义")
        return definitions

    @staticmethod
    def check_requirements(package_path: Path) -> Optional[List[str]]:
        """
        Check requirements.txt for dependencies

        Args:
            package_path: Path to package root directory

        Returns:
            List of requirements (lines), None if no requirements.txt
        """
        req_path = package_path / "requirements.txt"

        if not req_path.exists():
            return None

        try:
            with open(req_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            _logger.debug(f"Found {len(lines)} requirements in {req_path}")
            return lines
        except Exception as e:
            _logger.error(f"Failed to read requirements.txt: {e}")
            return None


def _sanitize_module_name(package_id: str) -> str:
    """
    Convert package ID to a valid Python module name.

    Reverse domain notation (e.g., "com.example.data-helpers") contains
    dots and hyphens which are invalid in module names. This function
    converts them to underscores.

    Args:
        package_id: Package ID to sanitize

    Returns:
        Sanitized module name (e.g., "com_example_data_helpers")
    """
    return package_id.replace(".", "_").replace("-", "_")


def _is_valid_package_id(package_id: str) -> bool:
    """Check if package ID is valid (reverse domain notation)"""
    if not package_id:
        return False

    parts = package_id.split(".")
    if len(parts) < 2:
        return False

    for part in parts:
        if not part or not part.isalnum():
            return False

    return True


def _is_valid_version(version: str) -> bool:
    """Check if version string is valid semver"""
    if not version:
        return False

    parts = version.split(".")
    if len(parts) < 1 or len(parts) > 3:
        return False

    for part in parts:
        try:
            int(part)
        except ValueError:
            return False

    return True


def _is_valid_url(url: str) -> bool:
    """Check if URL is valid"""
    return url.startswith("http://") or url.startswith("https://") or url.startswith("git@")
