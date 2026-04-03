# -*- coding: utf-8 -*-
"""
事件总线模块

提供发布-订阅模式的事件系统，用于：
- 组件间解耦通信
- 插件与主程序通信
- 系统事件广播

使用方式：
    from src.core.event_bus import EventBus, EventType

    bus = EventBus()

    # 订阅事件
    sub_id = bus.subscribe(EventType.PLUGIN_LOADED, self.on_plugin_loaded)

    # 发布事件
    bus.publish(EventType.PLUGIN_LOADED, {"name": "my_plugin"})

    # 取消订阅
    bus.unsubscribe(sub_id)
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.utils.logger import get_logger

# 模块日志记录器
_logger = get_logger(__name__)


import threading


from typing import Any, Callable, Dict, List, Optional


_global_EventBus_instance: Optional["EventBus"] = None
_global_lock = threading.Lock()


def get_event_bus() -> "EventBus":
    global _global_lock, _global_EventBus_instance
    if _global_EventBus_instance is None:
        with _global_lock:
            if _global_EventBus_instance is None:
                _global_EventBus_instance = EventBus()
    return _global_EventBus_instance


def init_event_bus() -> "EventBus":
    global _global_lock, _global_EventBus_instance
    with _global_lock:
        if _global_EventBus_instance is not None:
            raise RuntimeError("EventBus already initialized")
        _global_EventBus_instance = EventBus()
    return _global_EventBus_instance


def shutdown_event_bus() -> None:
    global _global_lock, _global_EventBus_instance
    with _global_lock:
        _global_EventBus_instance = None


def reset_event_bus_for_testing() -> None:
    shutdown_event_bus()


class EventType(Enum):
    """
    事件类型枚举

    定义系统中所有可用的事件类型，按功能分组：
    - 插件事件：插件生命周期相关
    - 节点事件：节点和工作流相关
    - Agent事件：AI助手相关
    - 系统事件：应用程序生命周期相关
    """

    # 插件事件
    PLUGIN_LOADED = "plugin.loaded"  # 插件加载完成
    PLUGIN_UNLOADED = "plugin.unloaded"  # 插件卸载完成
    PLUGIN_PERMISSION_REQUEST = "plugin.permission_request"  # 插件权限请求

    # 节点事件
    NODE_REGISTERED = "node.registered"  # 节点注册
    NODE_UNREGISTERED = "node.unregistered"  # 节点注销
    NODE_STARTED = "node.started"  # 节点开始执行
    NODE_EXECUTED = "node.executed"  # 节点执行完成

    # 工作流事件
    WORKFLOW_SAVED = "workflow.saved"  # 工作流保存
    WORKFLOW_LOADED = "workflow.loaded"  # 工作流加载
    WORKFLOW_STARTED = "workflow.started"  # 工作流开始执行
    WORKFLOW_COMPLETED = "workflow.completed"  # 工作流执行完成

    # Agent事件
    AGENT_MESSAGE = "agent.message"  # Agent消息
    AGENT_TOOL_CALLED = "agent.tool_called"  # Agent工具调用

    # 节点包事件
    PACKAGE_INSTALLED = "package.installed"  # 节点包安装
    PACKAGE_UPDATED = "package.updated"  # 节点包更新
    PACKAGE_REMOVED = "package.removed"  # 节点包删除
    PACKAGE_ENABLED = "package.enabled"  # 节点包启用
    PACKAGE_DISABLED = "package.disabled"  # 节点包禁用

    # 系统事件
    APP_STARTED = "app.started"  # 应用启动
    APP_SHUTDOWN = "app.shutdown"  # 应用关闭


@dataclass
class Event:
    """
    事件数据类

    封装事件的所有信息，包括事件类型、数据和时间戳

    Attributes:
        event_type: 事件类型
        data: 事件携带的数据
        timestamp: 事件发生时间
    """

    event_type: EventType
    data: Any
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """初始化时间戳"""
        if self.timestamp is None:
            self.timestamp = datetime.now()


# 处理器类型别名
Handler = Callable[[Event], None]


class EventBus:
    """
    事件总线

    实现发布-订阅模式，支持：
    - 订阅/取消订阅事件
    - 发布事件
    - 一对多事件分发

    Example:
        bus = EventBus()

        def on_plugin_loaded(event: Event):
            print(f"插件加载: {event.data}")

        # 订阅
        sub_id = bus.subscribe(EventType.PLUGIN_LOADED, on_plugin_loaded)

        # 发布
        bus.publish(EventType.PLUGIN_LOADED, {"name": "test"})

        # 取消订阅
        bus.unsubscribe(sub_id)
    """

    def __init__(self):
        """初始化事件总线"""
        # 订阅映射：事件类型 -> [(订阅ID, 处理器)]
        self._subscriptions: Dict[EventType, List[tuple[str, Handler]]] = {}
        # 订阅ID到事件类型的映射（用于快速取消订阅）
        self._subscription_types: Dict[str, EventType] = {}

        _logger.debug("事件总线初始化完成")

    def subscribe(self, event_type: EventType, handler: Handler) -> str:
        """
        订阅事件

        Args:
            event_type: 要订阅的事件类型
            handler: 事件处理函数，接收 Event 参数

        Returns:
            订阅ID，用于后续取消订阅

        Example:
            def my_handler(event: Event):
                print(event.data)

            sub_id = bus.subscribe(EventType.PLUGIN_LOADED, my_handler)
        """
        # 生成唯一订阅ID
        subscription_id = str(uuid.uuid4())

        # 初始化该事件类型的订阅列表
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []

        # 添加订阅
        self._subscriptions[event_type].append((subscription_id, handler))
        self._subscription_types[subscription_id] = event_type

        _logger.debug(f"订阅事件: {event_type.value}, 订阅ID: {subscription_id[:8]}...")

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        取消订阅

        Args:
            subscription_id: 订阅时返回的订阅ID

        Returns:
            是否成功取消（如果订阅ID不存在则返回False）

        Example:
            bus.unsubscribe(sub_id)
        """
        # 查找订阅对应的事件类型
        event_type = self._subscription_types.get(subscription_id)
        if event_type is None:
            _logger.warning(f"取消订阅失败: 未找到订阅ID {subscription_id[:8]}...")
            return False

        # 从订阅列表中移除
        if event_type in self._subscriptions:
            self._subscriptions[event_type] = [
                (sid, handler)
                for sid, handler in self._subscriptions[event_type]
                if sid != subscription_id
            ]

        # 从类型映射中移除
        del self._subscription_types[subscription_id]

        _logger.debug(f"取消订阅: {event_type.value}, 订阅ID: {subscription_id[:8]}...")

        return True

    def publish(self, event_type: EventType, data: Any = None) -> None:
        """
        发布事件

        将事件分发给所有订阅了该事件类型的处理器

        Args:
            event_type: 要发布的事件类型
            data: 事件携带的数据（可选）

        Example:
            bus.publish(EventType.PLUGIN_LOADED, {"name": "my_plugin"})
        """
        # 创建事件对象
        event = Event(event_type=event_type, data=data)

        # 获取该事件类型的所有订阅
        handlers = self._subscriptions.get(event_type, [])

        if not handlers:
            _logger.debug(f"发布事件: {event_type.value}, 无订阅者")
            return

        _logger.debug(f"发布事件: {event_type.value}, 订阅者数量: {len(handlers)}")

        # 分发事件给所有处理器
        for subscription_id, handler in handlers:
            try:
                handler(event)
            except Exception as e:
                _logger.error(
                    f"事件处理器执行失败: {event_type.value}, "
                    f"订阅ID: {subscription_id[:8]}..., 错误: {e}",
                    exc_info=True,
                )

    def get_subscribers_count(self, event_type: EventType) -> int:
        """
        获取某事件类型的订阅者数量

        Args:
            event_type: 事件类型

        Returns:
            订阅者数量
        """
        return len(self._subscriptions.get(event_type, []))

    def clear_all(self) -> None:
        """
        清除所有订阅

        用于应用关闭时清理资源
        """
        self._subscriptions.clear()
        self._subscription_types.clear()
        _logger.info("已清除所有事件订阅")
