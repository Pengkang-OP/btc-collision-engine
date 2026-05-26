#!/usr/bin/env python3
"""EventBus 单元测试

覆盖当前简化版 EventBus API：
- 订阅/取消订阅
- 发布事件分发
- 错误处理
- 全局单例
- 线程安全
"""

import threading
from unittest.mock import Mock

import pytest

from src.collision.event_bus import EventBus, get_event_bus, reset_event_bus
from src.collision.events import (
    EngineCompleteEvent,
    EngineErrorEvent,
    EngineMatchEvent,
    EngineProgressEvent,
    EngineStartEvent,
    EngineStopEvent,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_global_bus():
    """每个测试前后重置全局事件总线"""
    reset_event_bus()
    yield
    reset_event_bus()


@pytest.fixture
def bus():
    """新的事件总线实例"""
    return EventBus()


# ============================================================================
# 事件创建测试
# ============================================================================


@pytest.mark.unit
class TestEventCreation:
    """事件对象创建测试"""

    def test_engine_start_event(self):
        event = EngineStartEvent(mode="random", target_count=5, batch_size=65536)
        assert event.mode == "random"
        assert event.target_count == 5
        assert event.batch_size == 65536

    def test_engine_progress_event(self):
        event = EngineProgressEvent(total_checked=100000, speed=500000.0, matches_found=2)
        assert event.total_checked == 100000
        assert event.speed == 500000.0

    def test_engine_match_event(self):
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="KxFAKE000000000000000000000000000000000000000000000",
            target_address="1TargetAddress",
        )
        assert event.address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        # WIF 应被自动掩码 (安全检查)
        assert "..." in event.wif
        assert len(event.wif) < len("KxFAKE000000000000000000000000000000000000000000000")

    def test_engine_match_event_wif_masking(self):
        """EngineMatchEvent.__post_init__ 自动掩码 WIF"""
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="KxFAKE000000000000000000000000000000000000000000000",
            target_address="1TargetAddress",
        )
        # 公开 wif 已被掩码
        assert event.wif.startswith("KxFAKE")
        assert event.wif.endswith("0000")
        # 原始 WIF 保存在 _raw_wif
        assert event._raw_wif == "KxFAKE000000000000000000000000000000000000000000000"

    def test_engine_match_event_metadata(self):
        """EngineMatchEvent.metadata 不泄露私钥和 WIF"""
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="KxFAKE000000000000000000000000000000000000000000000",
            target_address="1TargetAddress",
        )
        meta = event.metadata
        assert "private_key" not in meta
        assert "wif" not in meta
        assert meta["address"] == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert meta["target_address"] == "1TargetAddress"

    def test_engine_error_event(self):
        event = EngineErrorEvent(error_type="GPU_OOM", error_message="Out of memory", recoverable=True)
        assert event.error_type == "GPU_OOM"
        assert event.recoverable is True

    def test_engine_complete_event(self):
        event = EngineCompleteEvent(
            total_checked=1000000,
            matches_found=5,
            elapsed_time=3600.0,
            stop_reason="normal",
        )
        assert event.total_checked == 1000000
        assert event.matches_found == 5

    def test_engine_stop_event(self):
        event = EngineStopEvent(reason="user_request", total_checked=500000)
        assert event.reason == "user_request"
        assert event.total_checked == 500000


# ============================================================================
# 订阅/取消订阅/发布测试
# ============================================================================


@pytest.mark.unit
class TestEventBusSubscribe:
    """订阅与取消订阅测试"""

    def test_subscribe(self, bus):
        handler = Mock(__name__="test_handler")
        bus.subscribe(EngineStartEvent, handler)
        assert len(bus._subscribers) == 1
        assert EngineStartEvent in bus._subscribers

    def test_subscribe_multiple_handlers_same_event(self, bus):
        h1 = Mock(__name__="h1")
        h2 = Mock(__name__="h2")
        bus.subscribe(EngineStartEvent, h1)
        bus.subscribe(EngineStartEvent, h2)
        assert len(bus._subscribers[EngineStartEvent]) == 2

    def test_unsubscribe(self, bus):
        handler = Mock(__name__="test_handler")
        bus.subscribe(EngineStartEvent, handler)
        bus.unsubscribe(EngineStartEvent, handler)
        assert len(bus._subscribers[EngineStartEvent]) == 0

    def test_unsubscribe_nonexistent_handler(self, bus):
        """取消未订阅的 handler 不抛异常"""
        handler = Mock(__name__="ghost")
        bus.unsubscribe(EngineStartEvent, handler)  # 不应抛异常

    def test_unsubscribe_nonexistent_event_type(self, bus):
        """取消未订阅的事件类型不抛异常"""
        handler = Mock(__name__="handler")
        bus.unsubscribe(EngineStartEvent, handler)  # 不应抛异常


@pytest.mark.unit
class TestEventBusPublish:
    """发布事件测试"""

    def test_publish_dispatches_to_handler(self, bus):
        handler = Mock(__name__="test_handler")
        bus.subscribe(EngineStartEvent, handler)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        bus.publish(event)

        handler.assert_called_once_with(event)

    def test_publish_multiple_subscribers(self, bus):
        h1, h2, h3 = Mock(__name__="h1"), Mock(__name__="h2"), Mock(__name__="h3")
        bus.subscribe(EngineProgressEvent, h1)
        bus.subscribe(EngineProgressEvent, h2)
        bus.subscribe(EngineProgressEvent, h3)

        event = EngineProgressEvent(total_checked=1000, speed=50000.0)
        bus.publish(event)

        h1.assert_called_once_with(event)
        h2.assert_called_once_with(event)
        h3.assert_called_once_with(event)

    def test_publish_no_subscribers(self, bus):
        """无订阅者时发布不抛异常"""
        event = EngineProgressEvent(total_checked=1000)
        bus.publish(event)  # 不应抛异常

    def test_publish_different_event_types(self, bus):
        """只有匹配的事件类型才触发 handler"""
        h_start = Mock(__name__="h_start")
        h_progress = Mock(__name__="h_progress")
        bus.subscribe(EngineStartEvent, h_start)
        bus.subscribe(EngineProgressEvent, h_progress)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        bus.publish(event)

        h_start.assert_called_once()
        h_progress.assert_not_called()

    def test_publish_handler_receives_correct_event(self, bus):
        """Handler 接收到正确的事件实例"""
        received = []

        def handler(e):
            received.append(e)

        bus.subscribe(EngineCompleteEvent, handler)

        event = EngineCompleteEvent(total_checked=5000, matches_found=3)
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event
        assert received[0].total_checked == 5000


@pytest.mark.unit
class TestEventBusErrorHandling:
    """错误处理测试"""

    def test_handler_error_is_logged_not_propagated(self, bus):
        """Handler 抛异常时不向外传播"""
        bad_handler = Mock(__name__="bad_handler", side_effect=RuntimeError("handler error"))
        good_handler = Mock(__name__="good_handler")

        bus.subscribe(EngineStartEvent, bad_handler)
        bus.subscribe(EngineStartEvent, good_handler)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        bus.publish(event)  # 不应向外传播异常

        # good_handler 仍然被调用
        good_handler.assert_called_once_with(event)


# ============================================================================
# 生命周期测试
# ============================================================================


@pytest.mark.unit
class TestEventBusLifecycle:
    """生命周期测试"""

    def test_clear(self, bus):
        h1, h2 = Mock(__name__="h1"), Mock(__name__="h2")
        bus.subscribe(EngineProgressEvent, h1)
        bus.subscribe(EngineMatchEvent, h2)
        assert len(bus._subscribers) == 2

        bus.clear()
        assert len(bus._subscribers) == 0

    def test_clear_then_resubscribe(self, bus):
        """Clear 后可以重新订阅"""
        handler = Mock(__name__="handler")
        bus.subscribe(EngineStartEvent, handler)
        bus.clear()

        new_handler = Mock(__name__="new_handler")
        bus.subscribe(EngineStartEvent, new_handler)
        assert len(bus._subscribers) == 1

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        bus.publish(event)
        new_handler.assert_called_once_with(event)


# ============================================================================
# 全局单例测试
# ============================================================================


@pytest.mark.unit
class TestEventBusGlobal:
    """全局单例测试"""

    def test_get_event_bus_returns_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_event_bus(self):
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2

    def test_get_event_bus_is_event_bus_instance(self):
        bus = get_event_bus()
        assert isinstance(bus, EventBus)


# ============================================================================
# 线程安全测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.thread_safety
class TestEventBusThreadSafety:
    """线程安全测试"""

    def test_concurrent_publish(self, bus):
        """多线程同时发布不应损坏数据"""
        results = []

        def handler(e):
            results.append(e.total_checked)

        bus.subscribe(EngineProgressEvent, handler)

        def publish_events(start, count):
            for i in range(start, start + count):
                event = EngineProgressEvent(total_checked=i, speed=10000.0)
                bus.publish(event)

        threads = []
        for j in range(4):
            t = threading.Thread(target=publish_events, args=(j * 100, 50))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 200

    def test_concurrent_subscribe_unsubscribe(self, bus):
        """并发订阅取消不应导致数据竞争"""
        errors = []

        def subscribe_loop():
            try:
                for _i in range(100):

                    def handler(e):
                        return None

                    bus.subscribe(EngineProgressEvent, handler)
                    bus.unsubscribe(EngineProgressEvent, handler)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=subscribe_loop) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
