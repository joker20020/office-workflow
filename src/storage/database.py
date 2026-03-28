# -*- coding: utf-8 -*-
"""
数据库模块

提供SQLite数据库连接和管理功能：
- Database: 数据库连接管理类
- 支持同步操作
- 自动创建数据库文件
- 连接池管理

使用方式：
    from src.storage.database import Database

    # 创建数据库实例
    db = Database(Path("data/app.db"))

    # 创建表
    db.create_tables()

    # 获取会话
    session = db.get_session()
    session.query(PluginRecord).all()
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import Engine

from src.storage.models import Base
from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


class Database:
    """
    数据库管理类

    管理SQLite数据库连接，支持：
    - 自动创建数据库文件
    - 会话管理
    - 连接池

    Example:
        db = Database(Path("data/app.db"))
        db.create_tables()

        with db.session() as session:
            records = session.query(PluginRecord).all()
    """

    def __init__(self, db_path: Path):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

        # 确保父目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        _logger.debug(f"数据库初始化: {self.db_path}")

    @property
    def engine(self) -> Engine:
        """获取数据库引擎（懒加载）"""
        if self._engine is None:
            # 创建SQLite引擎
            # check_same_thread=False 允许多线程访问
            self._engine = create_engine(
                f"sqlite:///{self.db_path}",
                echo=False,  # 设为True可输出SQL语句
                pool_pre_ping=True,  # 连接前检查可用性
            )

            # 配置SQLite启用外键约束
            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            _logger.info(f"数据库引擎创建: {self.db_path}")

        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """获取会话工厂（懒加载）"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    def create_tables(self) -> None:
        """
        创建所有表

        如果表已存在则不会重新创建
        """
        Base.metadata.create_all(self.engine)
        self._run_migrations()
        _logger.info(f"数据库表创建完成: {self.db_path}")

    def _run_migrations(self) -> None:
        """
        运行数据库迁移

        处理现有表的schema更新
        """
        with self.engine.connect() as conn:
            self._migrate_add_config_json_column(conn)

    def _migrate_add_config_json_column(self, conn) -> None:
        """
        迁移: 为 plugins 表添加 config_json 列

        Args:
            conn: 数据库连接
        """
        from sqlalchemy.exc import OperationalError

        try:
            conn.execute(text("SELECT config_json FROM plugins LIMIT 1"))
        except OperationalError:
            _logger.info("迁移: 为 plugins 表添加 config_json 列")
            conn.execute(
                text("ALTER TABLE plugins ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}'")
            )
            conn.commit()
            _logger.info("迁移完成: config_json 列已添加")

    def drop_tables(self) -> None:
        """
        删除所有表

        警告: 此操作不可逆！
        """
        Base.metadata.drop_all(self.engine)
        _logger.warning(f"数据库表已删除: {self.db_path}")

    def get_session(self) -> Session:
        """
        获取数据库会话

        Returns:
            新的数据库会话

        Note:
            调用者负责关闭会话

        Example:
            session = db.get_session()
            try:
                records = session.query(PluginRecord).all()
            finally:
                session.close()
        """
        return self.session_factory()

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        上下文管理器方式的会话

        自动提交和关闭会话

        Yields:
            数据库会话

        Example:
            with db.session() as session:
                record = PluginRecord(name="test")
                session.add(record)
                # 自动提交
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        """关闭数据库连接"""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            _logger.info(f"数据库连接已关闭: {self.db_path}")

    def __enter__(self) -> "Database":
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.close()
