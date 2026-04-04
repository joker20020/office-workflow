# -*- coding: utf-8 -*-
"""性能优化测试"""

import pytest
import time
from unittest.mock import Mock

from typing import Callable

from src.engine.node_engine import NodeEngine, ExecutionResult
from src.engine.node_graph import NodeGraph, Node
from src.engine.definitions import NodeDefinition, PortDefinition, PortType


