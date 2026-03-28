# -*- coding: utf-8 -*-
"""Skill管理器 - 管理Agent技能包"""

import json
from pathlib import Path
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage.database import Database
from src.storage.models import SkillRecord
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class SkillManager:
    """
    Skill管理器

    负责管理AgentScope的Skill包:
    - 发现本地Skill目录
    - 数据库持久化存储
    - 启用/禁用Skill
    - 生成AgentScope配置
    """

    def __init__(self, db: Optional[Database] = None):
        if db is None:
            db_path = Path.home() / ".office_tools" / "data.db"
            db = Database(db_path)

        self._db = db
        self._db.create_tables()
        _logger.info("Skill管理器初始化完成")

    def add_skill(self, name: str, path: str, description: Optional[str] = None) -> None:
        """
        添加Skill到数据库

        Args:
            name: Skill名称
            path: Skill目录路径
            description: 描述（可选）
        """
        with Session(self._db.engine) as session:
            existing = session.execute(
                select(SkillRecord).where(SkillRecord.name == name)
            ).scalar_one_or_none()

            if existing:
                raise ValueError(f"Skill已存在: {name}")

            record = SkillRecord(
                name=name,
                path=path,
                description=description,
                enabled=True,
            )
            session.add(record)
            session.commit()
            _logger.info(f"添加Skill: {name}")

    def delete_skill(self, name: str) -> bool:
        """
        从数据库删除Skill

        Args:
            name: Skill名称

        Returns:
            是否成功删除
        """
        with Session(self._db.engine) as session:
            record = session.execute(
                select(SkillRecord).where(SkillRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到Skill: {name}")
                return False

            session.delete(record)
            session.commit()
            _logger.info(f"删除Skill: {name}")
            return True

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """
        启用/禁用Skill

        Args:
            name: Skill名称
            enabled: 是否启用

        Returns:
            是否成功设置
        """
        with Session(self._db.engine) as session:
            record = session.execute(
                select(SkillRecord).where(SkillRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到Skill: {name}")
                return False

            record.enabled = enabled
            session.commit()
            status = "启用" if enabled else "禁用"
            _logger.info(f"{status}Skill: {name}")
            return True

    def update_skill(
        self,
        name: str,
        path: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        更新Skill配置

        Args:
            name: Skill名称
            path: 新路径（可选）
            description: 新描述（可选）

        Returns:
            是否成功更新
        """
        with Session(self._db.engine) as session:
            record = session.execute(
                select(SkillRecord).where(SkillRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到Skill: {name}")
                return False

            if path is not None:
                record.path = path
            if description is not None:
                record.description = description

            session.commit()
            _logger.info(f"更新Skill: {name}")
            return True

    def list_skills(self) -> List[dict]:
        """
        列出所有已注册的Skill

        Returns:
            Skill配置列表
        """
        with Session(self._db.engine) as session:
            result = session.execute(select(SkillRecord))
            records = result.scalars().all()

            return [
                {
                    "name": record.name,
                    "path": record.path,
                    "description": record.description,
                    "enabled": record.enabled,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                }
                for record in records
            ]

    def get_skill(self, name: str) -> Optional[dict]:
        """
        获取指定Skill的配置

        Args:
            name: Skill名称

        Returns:
            Skill配置，如果不存在则返回None
        """
        with Session(self._db.engine) as session:
            record = session.execute(
                select(SkillRecord).where(SkillRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                return None

            return {
                "name": record.name,
                "path": record.path,
                "description": record.description,
                "enabled": record.enabled,
            }

    def get_enabled_skills(self) -> List[dict]:
        """
        获取所有已启用的Skill

        Returns:
            已启用的Skill列表
        """
        with Session(self._db.engine) as session:
            result = session.execute(select(SkillRecord).where(SkillRecord.enabled == True))
            records = result.scalars().all()

            return [
                {
                    "name": record.name,
                    "path": record.path,
                    "description": record.description,
                }
                for record in records
            ]

    def discover_skills(self, directory: Path) -> List[dict]:
        """
        扫描目录发现Skill包

        Args:
            directory: 要扫描的目录

        Returns:
            发现的Skill列表，每项包含 name, path, description
        """
        discovered = []

        if not directory.exists():
            _logger.warning(f"目录不存在: {directory}")
            return discovered

        for skill_dir in directory.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    try:
                        content = skill_md.read_text(encoding="utf-8")
                        name = skill_dir.name
                        description = self._extract_description(content)

                        discovered.append(
                            {
                                "name": name,
                                "path": str(skill_dir),
                                "description": description,
                            }
                        )
                        _logger.debug(f"发现Skill: {name}")
                    except Exception as e:
                        _logger.error(f"读取Skill失败 {skill_dir}: {e}")

        return discovered

    def discover_and_register(self, directory: Path) -> int:
        """
        扫描目录并自动注册发现的Skill

        Args:
            directory: 要扫描的目录

        Returns:
            新注册的Skill数量
        """
        discovered = self.discover_skills(directory)
        registered = 0

        for skill in discovered:
            try:
                self.add_skill(
                    name=skill["name"],
                    path=skill["path"],
                    description=skill.get("description"),
                )
                registered += 1
            except ValueError:
                pass  # 已存在，跳过

        _logger.info(f"从 {directory} 注册了 {registered} 个新Skill")
        return registered

    def _extract_description(self, content: str) -> str:
        """从SKILL.md提取description字段"""
        lines = content.split("\n")
        in_frontmatter = False
        description_lines = []

        for line in lines:
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter and line.startswith("description:"):
                desc = line[len("description:") :].strip()
                description_lines.append(desc)

        return " ".join(description_lines) if description_lines else ""
