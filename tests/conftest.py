# -*- coding: utf-8 -*-
"""pytest配置 - 共享fixtures和hooks"""

import pytest
from pathlib import Path
import tempfile


@pytest.fixture(autouse=True)
def reset_all_singletons():
    """自动重置所有单例 - 确保测试隔离"""
    yield
    # 在每个测试后重置所有单例
    # Reset in reverse order of dependencies
    # 1. NodePackageManager (depends on NodeEngine)
    try:
        from src.nodes.package_manager import reset_package_manager_for_testing

        reset_package_manager_for_testing()
    except ImportError:
        pass

    # 2. PluginManager (independent)
    try:
        from src.core.plugin_manager import reset_plugin_manager_for_testing

        reset_plugin_manager_for_testing()
    except ImportError:
        pass

    # 3. NodeEngine (independent)
    try:
        from src.engine.node_engine import reset_node_engine_for_testing

        reset_node_engine_for_testing()
    except ImportError:
        pass

    # 4. Agent managers (ApiKey, Mcp, Skill)
    try:
        from src.agent.api_key_manager import reset_api_key_manager_for_testing

        reset_api_key_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.agent.mcp_server_manager import reset_mcp_server_manager_for_testing

        reset_mcp_server_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.agent.skill_manager import reset_skill_manager_for_testing

        reset_skill_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.agent.api_key_manager import reset_api_key_manager_for_testing

        reset_api_key_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.agent.mcp_server_manager import reset_mcp_server_manager_for_testing

        reset_mcp_server_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.agent.skill_manager import reset_skill_manager_for_testing

        reset_skill_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.nodes.package_manager import reset_package_manager_for_testing

        reset_package_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.core.plugin_manager import reset_plugin_manager_for_testing

        reset_plugin_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.core.config_manager import reset_config_manager_for_testing

        reset_config_manager_for_testing()
    except ImportError:
        pass

    try:
        from src.ui.theme_manager import reset_theme_manager_for_testing

        reset_theme_manager_for_testing()
    except ImportError:
        pass


@pytest.fixture
def tmp_path_fixture(tmp_path):
    """创建临时目录fixture"""
    temp_dir = Path(tmp_path)
    yield temp_dir


@pytest.fixture
def db_path(tmp_path):
    """创建临时数据库路径fixture"""
    db_file = tmp_path / "test.db"
    yield db_file
