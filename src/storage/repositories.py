# -*- coding: utf-8 -*-
"""
存储库模块

提供数据持久化操作：
- WorkflowRepository: 工作流CRUD操作

使用方式：
    from src.storage.repositories import WorkflowRepository

    repo = WorkflowRepository(database)
    repo.save(graph)
    graph = repo.load(graph_id)
"""

from datetime import datetime
from typing import List, Optional
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.engine.node_graph import NodeGraph
from src.engine.serialization import deserialize_graph, serialize_graph
from src.storage.database import Database
from src.storage.models import WorkflowRecord
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class WorkflowRepository:
    """
    工作流存储库

    提供工作流的CRUD操作：
    - save: 保存工作流
    - load: 加载工作流
    - delete: 删除工作流
    - list_all: 列出所有工作流

    Example:
        >>> repo = WorkflowRepository(database)
        >>> repo.save(graph)
        >>> loaded = repo.load(graph.id)
    """

    def __init__(self, database: Database):
        """
        初始化存储库

        Args:
            database: 数据库实例
        """
        self._database = database

    def save(self, graph: NodeGraph) -> bool:
        """
        保存工作流

        如果工作流已存在则更新，否则创建新记录。

        Args:
            graph: 要保存的工作流图

        Returns:
            是否保存成功

        Example:
            >>> repo.save(graph)
            True
        """
        try:
            with self._database.session() as session:
                # 检查是否已存在
                stmt = select(WorkflowRecord).where(WorkflowRecord.id == graph.id)
                existing = session.execute(stmt).scalar_one_or_none()

                # 序列化图
                graph_json = serialize_graph(graph)

                if existing:
                    # 更新
                    existing.name = graph.name
                    existing.graph_json = graph_json
                    existing.updated_at = datetime.now()
                    _logger.info(f"更新工作流: {graph.name} [{graph.id[:8]}...]")
                else:
                    # 创建
                    record = WorkflowRecord(
                        id=graph.id,
                        name=graph.name,
                        graph_json=graph_json,
                    )
                    session.add(record)
                    _logger.info(f"保存新工作流: {graph.name} [{graph.id[:8]}...]")

                return True

        except Exception as e:
            _logger.error(f"保存工作流失败: {e}", exc_info=True)
            return False

    def load(self, graph_id: str) -> Optional[NodeGraph]:
        """
        加载工作流

        Args:
            graph_id: 工作流ID

        Returns:
            工作流图，如果不存在则返回 None

        Example:
            >>> graph = repo.load("graph-uuid")
            >>> graph.name
            '我的工作流'
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord).where(WorkflowRecord.id == graph_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record is None:
                    _logger.warning(f"工作流不存在: {graph_id[:8]}...")
                    return None

                # 反序列化
                graph = deserialize_graph(record.graph_json)
                _logger.info(f"加载工作流: {graph.name} [{graph_id[:8]}...]")
                return graph

        except Exception as e:
            _logger.error(f"加载工作流失败: {e}", exc_info=True)
            return None

    def delete(self, graph_id: str) -> bool:
        """
        删除工作流

        Args:
            graph_id: 工作流ID

        Returns:
            是否删除成功

        Example:
            >>> repo.delete("graph-uuid")
            True
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord).where(WorkflowRecord.id == graph_id)
                record = session.execute(stmt).scalar_one_or_none()

                if record:
                    session.delete(record)
                    _logger.info(f"删除工作流: {graph_id[:8]}...")
                    return True
                else:
                    _logger.warning(f"工作流不存在，无法删除: {graph_id[:8]}...")
                    return False

        except Exception as e:
            _logger.error(f"删除工作流失败: {e}", exc_info=True)
            return False

    def list_all(self) -> List[dict]:
        """
        列出所有工作流（仅元信息）

        Returns:
            工作流元信息列表，每项包含 id, name, created_at, updated_at

        Example:
            >>> workflows = repo.list_all()
            >>> len(workflows)
            5
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord).order_by(WorkflowRecord.updated_at.desc())
                records = session.execute(stmt).scalars().all()

                result = [
                    {
                        "id": r.id,
                        "name": r.name,
                        "created_at": r.created_at.isoformat(),
                        "updated_at": r.updated_at.isoformat(),
                    }
                    for r in records
                ]

                _logger.debug(f"列出工作流: {len(result)} 个")
                return result

        except Exception as e:
            _logger.error(f"列出工作流失败: {e}", exc_info=True)
            return []

    def exists(self, graph_id: str) -> bool:
        """
        检查工作流是否存在

        Args:
            graph_id: 工作流ID

        Returns:
            是否存在
        """
        try:
            with self._database.session() as session:
                stmt = select(WorkflowRecord.id).where(WorkflowRecord.id == graph_id)
                result = session.execute(stmt).scalar_one_or_none()
                return result is not None
        except Exception:
            return False
