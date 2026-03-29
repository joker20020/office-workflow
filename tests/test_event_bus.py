# -*- coding: utf-8 -*-
"""EventBus 模块测试"""

import pytest

from src.core.event_bus import EventBus, Event, EventType, get_event_bus


class TestEventType:
    """测试 EventType 枚举"""

    def test_event_type_values(self):
        """测试事件类型值"""
        assert EventType.PLUGIN_LOADED.value == "plugin.loaded"
        assert EventType.PLUGIN_UNLOADED.value == "plugin.unloaded"
        assert EventType.NODE_EXECUTED.value == "node.executed"
        assert EventType.APP_STARTED.value == "app.started"

    def test_all_event_types_defined(self):
        """测试所有事件类型都已定义"""
        # 插件事件
        assert hasattr(EventType, "PLUGIN_LOADED")
        assert hasattr(EventType, "PLUGIN_UNLOADED")

        # 节点事件
        assert hasattr(EventType, "NODE_REGISTERED")
        assert hasattr(EventType, "NODE_EXECUTED")

        # 工作流事件
        assert hasattr(EventType, "WORKFLOW_SAVED")
        assert hasattr(EventType, "WORKFLOW_STARTED")

        # 系统事件
        assert hasattr(EventType, "APP_STARTED")
        assert hasattr(EventType, "APP_SHUTDOWN")


class TestEvent:
    """测试 Event 数据类"""

    def test_event_creation(self):
        """测试事件创建"""
        event = Event(
            event_type=EventType.PLUGIN_LOADED,
            data={"name": "test"},
        )

        assert event.event_type == EventType.PLUGIN_LOADED
        assert event.data == {"name": "test"}
        assert event.timestamp is not None

    def test_event_with_explicit_timestamp(self):
        """测试带显式时间戳的事件"""
        from datetime import datetime

        ts = datetime(2024, 1, 1, 12, 0, 0)
        event = Event(
            event_type=EventType.APP_STARTED,
            data=None,
            timestamp=ts,
        )

        assert event.timestamp == ts


class TestEventBus:
    """测试 EventBus 类"""

    def test_subscribe_returns_subscription_id(self):
        """测试订阅返回订阅ID"""
        bus = EventBus()
        sub_id = bus.subscribe(EventType.PLUGIN_LOADED, lambda e: None)

        assert sub_id is not None
        assert isinstance(sub_id, str)

    def test_publish_calls_handler(self):
        """测试发布事件调用处理器"""
        bus = EventBus()
        called_events: list[Event] = []

        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: called_events.append(e))
        bus.publish(EventType.PLUGIN_LOADED, {"name": "test"})

        assert len(called_events) == 1
        assert called_events[0].data == {"name": "test"}

    def test_unsubscribe_removes_handler(self):
        """测试取消订阅移除处理器"""
        bus = EventBus()
        called_count = [0]

        sub_id = bus.subscribe(
            EventType.PLUGIN_LOADED, lambda e: called_count.__setitem__(0, called_count[0] + 1)
        )

        # 发布一次
        bus.publish(EventType.PLUGIN_LOADED, {})
        assert called_count[0] == 1

        # 取消订阅
        bus.unsubscribe(sub_id)

        # 再发布一次
        bus.publish(EventType.PLUGIN_LOADED, {})
        assert called_count[0] == 1  # 没有增加

    def test_multiple_handlers_same_event(self):
        """测试同一事件的多个处理器"""
        bus = EventBus()
        results: list[int] = []

        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: results.append(1))
        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: results.append(2))

        bus.publish(EventType.PLUGIN_LOADED, {})

        assert sorted(results) == [1, 2]

    def test_handler_exception_is_caught(self):
        """测试处理器异常被捕获"""
        bus = EventBus()
        results: list[int] = []

        # 第一个处理器抛出异常
        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: 1 / 0)
        # 第二个处理器正常执行
        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: results.append(1))

        # 发布事件，第二个处理器仍应执行
        bus.publish(EventType.PLUGIN_LOADED, {})

        assert results == [1]

    def test_get_subscribers_count(self):
        """测试获取订阅者数量"""
        bus = EventBus()

        assert bus.get_subscribers_count(EventType.PLUGIN_LOADED) == 0

        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: None)
        assert bus.get_subscribers_count(EventType.PLUGIN_LOADED) == 1

        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: None)
        assert bus.get_subscribers_count(EventType.PLUGIN_LOADED) == 2

    def test_clear_all(self):
        """测试清除所有订阅"""
        bus = EventBus()

        bus.subscribe(EventType.PLUGIN_LOADED, lambda e: None)
        bus.subscribe(EventType.PLUGIN_UNLOADED, lambda e: None)

        bus.clear_all()

        assert bus.get_subscribers_count(EventType.PLUGIN_LOADED) == 0
        assert bus.get_subscribers_count(EventType.PLUGIN_UNLOADED) == 0

    def test_unsubscribe_nonexistent_returns_false(self):
        """测试取消不存在的订阅返回False"""
        bus = EventBus()
        result = bus.unsubscribe("nonexistent-id")
        assert result is False
