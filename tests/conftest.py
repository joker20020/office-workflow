# -*- coding: utf-8 -*-
"""pytest配置 - 共享fixtures和hooks"""

import pytest
from pathlib import Path
import tempfile


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
