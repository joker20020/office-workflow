# -*- coding: utf-8 -*-
"""MCP服务配置管理器

注意：该类的实例采用模块级单例模式访问。请使用以下函数获取单例：
- get_mcp_server_manager()
- init_mcp_server_manager(db=None)
- shutdown_mcp_server_manager()
- reset_mcp_server_manager_for_testing()
"""

import threading
import json
from typing import Optional, List

try:
    from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig
except ImportError:
    HttpMCPConfig = None
    MCPClient = None
    StdioMCPConfig = None

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.change_notifier import ChangeCallback, ChangeNotifier
from src.storage.database import Database
from src.storage.models import McpServerRecord
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class McpServerManager:
    """MCP服务配置管理器"""

    def __init__(self, db: Optional[Database] = None):
        """
        Initialize McpServerManager.

        Deprecated: This constructor is deprecated for direct usage. Use
        get_mcp_server_manager() or init_mcp_server_manager(db) to access the
        singleton instance instead.

        Args:
            db: Optional Database instance. If None, a per-user default database
                will be created.
        """
        if db is None:
            from pathlib import Path

            db_path = Path.home() / ".office_tools" / "data.db"
            db = Database(db_path)

        self._db = db
        self._change_notifier = ChangeNotifier("mcp")
        self._db.create_tables()
        _logger.info("MCP服务管理器初始化完成")

    def subscribe_changes(self, callback: ChangeCallback) -> int:
        return self._change_notifier.subscribe(callback)

    def unsubscribe_changes(self, token: int) -> None:
        self._change_notifier.unsubscribe(token)

    def add_stdio_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[dict] = None,
        timeout: int = 30,
    ) -> None:
        """添加stdio类型MCP服务器"""
        with Session(self._db.engine) as session:
            existing = session.execute(
                select(McpServerRecord).where(McpServerRecord.name == name)
            ).scalar_one_or_none()

            if existing:
                raise ValueError(f"MCP服务器已存在: {name}")

            record = McpServerRecord(
                name=name,
                server_type="stdio",
                command=command,
                args=json.dumps(args) if args else None,
                env=json.dumps(env) if env else None,
                timeout=timeout,
                enabled=True,
            )
            session.add(record)
            session.commit()
            _logger.info(f"添加stdio MCP服务器: {name}")
        self._change_notifier.notify(action="added", name=name)

    def add_http_server(
        self,
        name: str,
        url: str,
        transport: str = "streamable_http",
    ) -> None:
        """添加http类型MCP服务器"""
        with Session(self._db.engine) as session:
            existing = session.execute(
                select(McpServerRecord).where(McpServerRecord.name == name)
            ).scalar_one_or_none()

            if existing:
                raise ValueError(f"MCP服务器已存在: {name}")

            record = McpServerRecord(
                name=name,
                server_type="http",
                url=url,
                transport=transport,
                enabled=True,
            )
            session.add(record)
            session.commit()
            _logger.info(f"添加http MCP服务器: {name}")
        self._change_notifier.notify(action="added", name=name)

    def get_server(self, name: str) -> Optional[dict]:
        """获取MCP服务器配置"""
        with Session(self._db.engine) as session:
            record = session.execute(
                select(McpServerRecord).where(McpServerRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                return None

            return self._record_to_dict(record)

    def delete_server(self, name: str) -> bool:
        """删除MCP服务器"""
        with Session(self._db.engine) as session:
            record = session.execute(
                select(McpServerRecord).where(McpServerRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到MCP服务器: {name}")
                return False

            session.delete(record)
            session.commit()
            _logger.info(f"删除MCP服务器: {name}")
        self._change_notifier.notify(action="deleted", name=name)
        return True

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """启用/禁用MCP服务器"""
        with Session(self._db.engine) as session:
            record = session.execute(
                select(McpServerRecord).where(McpServerRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到MCP服务器: {name}")
                return False

            if record.enabled == enabled:
                return True

            record.enabled = enabled
            session.commit()
            status = "启用" if enabled else "禁用"
            _logger.info(f"{status}MCP服务器: {name}")
        self._change_notifier.notify(
            action="enabled" if enabled else "disabled", name=name
        )
        return True

    def update_stdio_server(
        self,
        name: str,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """更新stdio类型MCP服务器配置"""
        with Session(self._db.engine) as session:
            record = session.execute(
                select(McpServerRecord).where(McpServerRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到MCP服务器: {name}")
                return False

            if record.server_type != "stdio":
                _logger.warning(f"MCP服务器类型不是stdio: {name}")
                return False

            changed = False
            if command is not None:
                changed = changed or record.command != command
                record.command = command
            if args is not None:
                serialized_args = json.dumps(args)
                changed = changed or record.args != serialized_args
                record.args = serialized_args
            if env is not None:
                serialized_env = json.dumps(env)
                changed = changed or record.env != serialized_env
                record.env = serialized_env
            if timeout is not None:
                changed = changed or record.timeout != timeout
                record.timeout = timeout

            session.commit()
            _logger.info(f"更新stdio MCP服务器: {name}")
        if changed:
            self._change_notifier.notify(action="updated", name=name)
        return True

    def update_http_server(
        self,
        name: str,
        url: Optional[str] = None,
        transport: Optional[str] = None,
    ) -> bool:
        """更新http类型MCP服务器配置"""
        with Session(self._db.engine) as session:
            record = session.execute(
                select(McpServerRecord).where(McpServerRecord.name == name)
            ).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到MCP服务器: {name}")
                return False

            if record.server_type != "http":
                _logger.warning(f"MCP服务器类型不是http: {name}")
                return False

            changed = False
            if url is not None:
                changed = changed or record.url != url
                record.url = url
            if transport is not None:
                changed = changed or record.transport != transport
                record.transport = transport

            session.commit()
            _logger.info(f"更新http MCP服务器: {name}")
        if changed:
            self._change_notifier.notify(action="updated", name=name)
        return True

    def list_servers(self) -> List[dict]:
        """列出所有MCP服务器"""
        with Session(self._db.engine) as session:
            result = session.execute(select(McpServerRecord))
            records = result.scalars().all()
            return [self._record_to_dict(r) for r in records]

    def _record_to_dict(self, record: McpServerRecord) -> dict:
        """将记录转换为字典"""
        data = {
            "id": record.id,
            "name": record.name,
            "server_type": record.server_type,
            "timeout": record.timeout,
            "enabled": record.enabled,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

        if record.server_type == "stdio":
            data["command"] = record.command
            data["args"] = json.loads(record.args) if record.args else []
            data["env"] = json.loads(record.env) if record.env else {}
        else:
            data["url"] = record.url
            data["transport"] = record.transport

        return data

    def get_agentscope_config(self, name: str) -> Optional[dict]:
        """生成AgentScope MCP客户端配置"""
        server = self.get_server(name)
        if not server:
            return None

        if server["server_type"] == "stdio":
            return {
                "name": server["name"],
                "command": server["command"],
                "args": server.get("args", []),
                "env": server.get("env", {}),
                "timeout": server["timeout"],
            }
        else:
            return {
                "name": server["name"],
                "transport": server.get("transport", "streamable_http"),
                "url": server["url"],
            }

    def create_agentscope_client(self, name: str) -> "MCPClient | None":
        """Build an AgentScope 2 MCP client without connecting it."""
        server = self.get_server(name)
        if not server:
            return None

        if MCPClient is None:
            _logger.warning("AgentScope MCP integration is unavailable")
            return None

        timeout = float(server.get("timeout", 30))
        if server["server_type"] == "stdio":
            config = StdioMCPConfig(
                command=server["command"],
                args=server.get("args") or [],
                env=server.get("env") or {},
                cwd=server.get("cwd"),
            )
            is_stateful = True
        else:
            config = HttpMCPConfig(
                url=server["url"],
                headers=server.get("headers"),
                timeout=timeout,
            )
            is_stateful = False

        return MCPClient(
            name=server["name"],
            is_stateful=is_stateful,
            mcp_config=config,
            enable_tools=server.get("enable_tools"),
            disable_tools=server.get("disable_tools"),
            execution_timeout=timeout,
        )


# Singleton pattern implementation
_global_McpServerManager_instance: Optional["McpServerManager"] = None
_global_lock = threading.Lock()


def get_mcp_server_manager() -> "McpServerManager":
    """Get the singleton McpServerManager instance."""
    global _global_lock, _global_McpServerManager_instance
    if _global_McpServerManager_instance is None:
        with _global_lock:
            if _global_McpServerManager_instance is None:
                _global_McpServerManager_instance = McpServerManager()
    return _global_McpServerManager_instance


def init_mcp_server_manager(db: Optional[Database] = None) -> "McpServerManager":
    """Initialize the singleton McpServerManager with custom parameters."""
    global _global_lock, _global_McpServerManager_instance
    with _global_lock:
        if _global_McpServerManager_instance is not None:
            raise RuntimeError("McpServerManager already initialized")
        _global_McpServerManager_instance = McpServerManager(db=db)
    return _global_McpServerManager_instance


def shutdown_mcp_server_manager() -> None:
    """Shutdown the singleton McpServerManager."""
    global _global_lock, _global_McpServerManager_instance
    with _global_lock:
        _global_McpServerManager_instance = None


def reset_mcp_server_manager_for_testing() -> None:
    """Reset the singleton for testing purposes."""
    shutdown_mcp_server_manager()
