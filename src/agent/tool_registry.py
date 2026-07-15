# -*- coding: utf-8 -*-
"""Registry for callable tools exposed to the main AgentScope agent."""

import threading
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from src.core.change_notifier import ChangeCallback, ChangeNotifier
from src.utils.logger import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ToolGroupSnapshot:
    """Immutable view of one registered tool group."""

    group_name: str
    owner_name: str | None
    tools: tuple[Callable, ...]


class AgentToolRegistry:
    """Singleton registry populated by application plugins."""

    _instance: Optional["AgentToolRegistry"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._tools: dict[str, list[Callable]] = {}
        self._owners: Dict[str, str | None] = {}
        self._registry_lock = threading.RLock()
        self._change_notifier = ChangeNotifier("tools")

    @classmethod
    def instance(cls) -> "AgentToolRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def subscribe_changes(self, callback: ChangeCallback) -> int:
        return self._change_notifier.subscribe(callback)

    def unsubscribe_changes(self, token: int) -> None:
        self._change_notifier.unsubscribe(token)

    def register(
        self,
        group_name: str,
        tools: list[Callable],
        *,
        owner_name: str | None = None,
    ) -> None:
        """Register or atomically replace a group while preserving its position."""
        with self._registry_lock:
            overwriting = group_name in self._tools
            self._tools[group_name] = list(tools)
            self._owners[group_name] = owner_name
        if overwriting:
            _logger.warning("工具组 '%s' 已存在，将被覆盖", group_name)
        _logger.info("注册工具组 '%s': %s 个工具", group_name, len(tools))
        self._change_notifier.notify(action="registered", name=group_name)

    def unregister(self, group_name: str) -> None:
        with self._registry_lock:
            removed = self._tools.pop(group_name, None)
            if removed is not None:
                self._owners.pop(group_name, None)
        if removed is None:
            _logger.debug("工具组 '%s' 不存在，跳过注销", group_name)
            return
        _logger.info("注销工具组 '%s': %s 个工具", group_name, len(removed))
        self._change_notifier.notify(action="unregistered", name=group_name)

    def get_group_snapshots(self) -> list[ToolGroupSnapshot]:
        with self._registry_lock:
            return [
                ToolGroupSnapshot(name, self._owners.get(name), tuple(tools))
                for name, tools in self._tools.items()
            ]

    def get_all_tools(self) -> List[Callable]:
        all_tools: List[Callable] = []
        for group in self.get_group_snapshots():
            all_tools.extend(group.tools)
        return all_tools

    def get_group_names(self) -> List[str]:
        with self._registry_lock:
            return list(self._tools.keys())

    def has_group(self, group_name: str) -> bool:
        with self._registry_lock:
            return group_name in self._tools

    @classmethod
    def _reset_for_testing(cls) -> None:
        cls._instance = None
