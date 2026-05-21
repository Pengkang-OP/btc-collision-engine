#!/usr/bin/env python3
"""事件总线 (EventBus) 单元测试

覆盖：
- 同步/异步模式
- 订阅/取消订阅
- 发布事件分发
- 错误处理
- 统计/属性
- 全局单例
- 上下文管理器
"""

import threading
import time
from unittest.mock import Mock

import pytest

from src.collision.event_bus import EventBus, get_event_bus, reset_event_bus
from src.collision.events import (
    CollisionEvent,
    EngineCompleteEvent,
    EngineErrorEvent,
    EngineMatchEvent,
    EngineProgressEvent,
    EngineStartEvent,
    EngineStopEvent,
    EventType,
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
def sync_bus():
    """同步模式事件总线"""
    return EventBus(async_mode=False)


@pytest.fixture
def async_bus():
    """异步模式事件总线"""
    bus = EventBus(async_mode=True)
    yield bus
    bus.stop()


# ============================================================================
# 事件创建测试
# ============================================================================


@pytest.mark.unit
class TestEventCreation:
    """事件对象创建测试"""

    def test_engine_start_event(self):
        event = EngineStartEvent(mode="random", target_count=5, batch_size=65536)
        assert event.event_type == EventType.ENGINE_START
        assert event.mode == "random"
        assert event.target_count == 5
        assert event.batch_size == 65536
        # 验证 __post_init__ 正确写入 metadata
        assert event.metadata["mode"] == "random"
        assert event.metadata["target_count"] == 5
        assert event.metadata["batch_size"] == 65536

    def test_engine_progress_event(self):
        event = EngineProgressEvent(total_checked=100000, speed=500000.0, matches_found=2)
        assert event.event_type == EventType.ENGINE_PROGRESS
        assert event.total_checked == 100000
        assert event.speed == 500000.0

    def test_engine_match_event(self):
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="KxFAKE000000000000000000000000000000000000000000000",
            target_address="1TargetAddress",
        )
        assert event.event_type == EventType.ENGINE_MATCH
        assert event.address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        # 私钥和 WIF 不应出现在 metadata 中（安全检查）
        assert "private_key" not in event.metadata
        assert "wif" not in event.metadata

    def test_engine_match_event_to_dict(self):
        """EngineMatchEvent.to_dict 不泄露私钥和 WIF"""
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="KxFAKE000000000000000000000000000000000000000000000",
            target_address="1TargetAddress",
        )
        d = event.to_dict()
        assert d["event_type"] == "engine.match"
        assert d["metadata"]["address"] == "1A1zP1...vfNa"
        assert d["metadata"]["target_address"] == "1Targe...ress"
        # 安全：序列化后不包含私钥和 WIF
        assert "private_key" not in d
        assert "private_key" not in d["metadata"]
        assert "wif" not in d["metadata"]

    def test_engine_error_event(self):
        event = EngineErrorEvent(
            error_type="GPU_OOM", error_message="Out of memory", recoverable=True
        )
        assert event.event_type == EventType.ENGINE_ERROR
        assert event.error_type == "GPU_OOM"

    def test_engine_complete_event(self):
        event = EngineCompleteEvent(
            total_checked=1000000, matches_found=5, elapsed_time=3600.0, stop_reason="normal"
        )
        assert event.event_type == EventType.ENGINE_COMPLETE

    def test_engine_stop_event(self):
        event = EngineStopEvent(reason="user_request", total_checked=500000)
        assert event.event_type == EventType.ENGINE_STOP

    def test_event_to_dict(self):
        event = EngineStartEvent(mode="range", target_count=3, batch_size=32768)
        d = event.to_dict()
        assert d["event_type"] == "engine.start"
        assert d["source"] == "collision_engine"

    def test_collision_event_base_to_dict_none_type(self):
        """CollisionEvent(event_type=None) 的 to_dict 返回 event_type=None"""
        event = CollisionEvent(event_type=None, source="test_source")
        d = event.to_dict()
        assert d["event_type"] is None
        assert d["source"] == "test_source"
        assert "timestamp" in d
        assert "metadata" in d

    def test_collision_event_base_to_dict_with_type(self):
        """CollisionEvent 带 event_type 时正确序列化"""
        event = CollisionEvent(event_type=EventType.ENGINE_START, source="test")
        d = event.to_dict()
        assert d["event_type"] == "engine.start"

    def test_engine_error_event_with_exception(self):
        """EngineErrorEvent 正确存储 exception 参数"""
        exc = ValueError("test error")
        event = EngineErrorEvent(
            error_type="ValueError",
            error_message="test error",
            exception=exc,
        )
        assert event.exception is exc
        assert event.error_type == "ValueError"
        assert event.event_type == EventType.ENGINE_ERROR

    def test_engine_error_event_to_dict(self):
        """EngineErrorEvent.to_dict 生成正确字典"""
        event = EngineErrorEvent(
            error_type="GPU_OOM",
            error_message="Out of memory",
            recoverable=False,
        )
        d = event.to_dict()
        assert d["event_type"] == "engine.error"
        assert d["metadata"]["error_type"] == "GPU_OOM"
        assert d["metadata"]["error_message"] == "Out of memory"
        assert d["metadata"]["recoverable"] is False

    def test_engine_stop_event_to_dict(self):
        """EngineStopEvent.to_dict 生成正确字典"""
        event = EngineStopEvent(reason="completed", total_checked=1000000)
        d = event.to_dict()
        assert d["event_type"] == "engine.stop"
        assert d["source"] == "collision_engine"

    def test_engine_complete_event_to_dict(self):
        """EngineCompleteEvent.to_dict 生成正确字典"""
        event = EngineCompleteEvent(
            total_checked=2000000,
            matches_found=3,
            elapsed_time=7200.0,
            avg_speed=278.0,
            stop_reason="completed",
        )
        d = event.to_dict()
        assert d["event_type"] == "engine.complete"
        assert d["metadata"]["total_checked"] == 2000000
        assert d["metadata"]["matches_found"] == 3
        assert d["metadata"]["stop_reason"] == "completed"


# ============================================================================
# 同步模式测试
# ============================================================================


@pytest.mark.unit
class TestEventBusSync:
    """同步模式事件总线测试"""

    def test_initial_state(self, sync_bus):
        assert sync_bus.subscriber_count == 0
        assert sync_bus.published_count == 0
        assert sync_bus.error_count == 0

    def test_subscribe(self, sync_bus):
        handler = Mock(__name__="test_handler")
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, handler)
        assert sync_bus.subscriber_count == 1

    def test_subscribe_duplicate_handler(self, sync_bus):
        handler = Mock(__name__="test_handler")
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, handler)
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, handler)
        assert sync_bus.subscriber_count == 1  # 同 handler 不重复订阅

    def test_unsubscribe(self, sync_bus):
        handler = Mock(__name__="test_handler")
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, handler)
        sync_bus.unsubscribe(EventType.ENGINE_PROGRESS, handler)
        assert sync_bus.subscriber_count == 0

    def test_publish_dispatches_to_handler(self, sync_bus):
        handler = Mock(__name__="test_handler")
        sync_bus.subscribe(EventType.ENGINE_START, handler)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        sync_bus.publish(event)

        handler.assert_called_once_with(event)
        assert sync_bus.published_count == 1

    def test_publish_multiple_subscribers(self, sync_bus):
        h1, h2, h3 = Mock(__name__="h1"), Mock(__name__="h2"), Mock(__name__="h3")
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, h1)
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, h2)
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, h3)

        event = EngineProgressEvent(total_checked=1000, speed=50000.0)
        sync_bus.publish(event)

        h1.assert_called_once_with(event)
        h2.assert_called_once_with(event)
        h3.assert_called_once_with(event)

    def test_publish_no_subscribers(self, sync_bus):
        event = EngineProgressEvent(total_checked=1000)
        sync_bus.publish(event)  # 不应抛异常
        assert sync_bus.published_count == 1

    def test_publish_none_event(self, sync_bus):
        sync_bus.publish(None)  # 不应抛异常
        assert sync_bus.published_count == 0

    def test_publish_none_event_type(self, sync_bus):
        event = CollisionEvent(event_type=None)
        sync_bus.publish(event)  # 不应抛异常
        assert sync_bus.published_count == 0

    def test_subscribe_to_all(self, sync_bus):
        handler = Mock()
        sync_bus.subscribe_to_all(handler)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        sync_bus.publish(event)

        handler.assert_called_once()
        # handler 接收 (event_type, event) 两个参数
        args = handler.call_args[0]
        assert args[0] == EventType.ENGINE_START
        assert args[1] is event


@pytest.mark.unit
class TestEventBusSyncErrorHandling:
    """同步模式错误处理测试"""

    def test_handler_error_sets_error_count(self, sync_bus):
        handler = Mock(__name__="bad_handler", side_effect=RuntimeError("handler error"))
        sync_bus.subscribe(EventType.ENGINE_START, handler)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        sync_bus.publish(event)

        assert sync_bus.error_count == 1

    def test_global_error_handler(self, sync_bus):
        error_handler = Mock(__name__="error_handler")
        handler = Mock(__name__="bad_handler", side_effect=RuntimeError("test error"))
        sync_bus.subscribe(EventType.ENGINE_START, handler)
        sync_bus.set_error_handler(error_handler)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        sync_bus.publish(event)

        error_handler.assert_called_once()
        args = error_handler.call_args[0]
        assert args[0] is event
        assert isinstance(args[1], RuntimeError)

    def test_error_handler_exception_not_propagate(self, sync_bus):
        error_handler = Mock(
            __name__="err_handler", side_effect=RuntimeError("error in error handler")
        )
        handler = Mock(__name__="bad_handler", side_effect=RuntimeError("original error"))
        sync_bus.subscribe(EventType.ENGINE_START, handler)
        sync_bus.set_error_handler(error_handler)

        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        sync_bus.publish(event)  # 不应向外传播异常


@pytest.mark.unit
class TestEventBusSyncLifecycle:
    """同步模式生命周期测试"""

    def test_clear(self, sync_bus):
        h1, h2 = Mock(__name__="h1"), Mock(__name__="h2")
        sync_bus.subscribe(EventType.ENGINE_PROGRESS, h1)
        sync_bus.subscribe(EventType.ENGINE_MATCH, h2)
        assert sync_bus.subscriber_count == 2

        sync_bus.clear()
        assert sync_bus.subscriber_count == 0

    def test_get_stats(self, sync_bus):
        handler = Mock(__name__="handler")
        sync_bus.subscribe(EventType.ENGINE_START, handler)
        event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
        sync_bus.publish(event)

        stats = sync_bus.get_stats()
        assert stats["subscriber_count"] == 1
        assert stats["published_count"] == 1
        assert stats["error_count"] == 0
        assert stats["async_mode"] is False

    def test_context_manager(self):
        with EventBus(async_mode=False) as bus:
            assert bus.subscriber_count == 0
            handler = Mock(__name__="handler")
            bus.subscribe(EventType.ENGINE_START, handler)
            event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
            bus.publish(event)
            handler.assert_called_once()
        # 退出上下文后应正常关闭


# ============================================================================
# 异步模式测试
# ============================================================================


@pytest.mark.unit
class TestEventBusAsync:
    """异步模式事件总线测试"""

    def test_async_mode_initialization(self, async_bus):
        assert async_bus._async_mode is True
        assert async_bus._event_queue is not None
        assert async_bus._worker_thread is not None
        assert async_bus._worker_thread.is_alive()

    def test_async_publish(self, async_bus):
        handler = Mock(__name__="handler")
        async_bus.subscribe(EventType.ENGINE_PROGRESS, handler)

        event = EngineProgressEvent(total_checked=500, speed=10000.0)
        async_bus.publish(event)

        # 异步模式需要等待处理
        time.sleep(0.3)

        assert async_bus.published_count == 1
        handler.assert_called_once_with(event)

    def test_async_stop(self, async_bus):
        assert async_bus._running is True
        async_bus.stop()
        assert async_bus._running is False

    def test_async_shutdown(self, async_bus):
        async_bus.shutdown()
        assert async_bus._running is False

    def test_async_context_manager(self):
        with EventBus(async_mode=True) as bus:
            handler = Mock(__name__="handler")
            bus.subscribe(EventType.ENGINE_START, handler)
            event = EngineStartEvent(mode="random", target_count=1, batch_size=1024)
            bus.publish(event)
            time.sleep(0.3)
            handler.assert_called_once()
        # 退出上下文后应正常关闭


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

    def test_async_mode_only_first_call(self):
        bus1 = get_event_bus(async_mode=True)
        bus2 = get_event_bus(async_mode=False)
        # 第二次调用 async_mode 参数被忽略
        assert bus1._async_mode is True
        assert bus2._async_mode is True
        bus1.stop()


# ============================================================================
# 线程安全测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.thread_safety
class TestEventBusThreadSafety:
    """线程安全测试"""

    def test_concurrent_publish(self, sync_bus):
        """多线程同时发布不应损坏数据"""
        results = []

        def handler(e):  # noqa: E306
            return results.append(e.total_checked)

        sync_bus.subscribe(EventType.ENGINE_PROGRESS, handler)

        def publish_events(start, count):
            for i in range(start, start + count):
                event = EngineProgressEvent(total_checked=i, speed=10000.0)
                sync_bus.publish(event)

        threads = []
        for j in range(4):
            t = threading.Thread(target=publish_events, args=(j * 100, 50))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sync_bus.published_count == 200
        assert len(results) == 200

    def test_concurrent_subscribe_unsubscribe(self, sync_bus):
        """并发订阅取消不应导致数据竞争"""
        errors = []

        def subscribe_loop():
            try:
                for i in range(100):

                    def handler(e):
                        return None

                    sync_bus.subscribe(EventType.ENGINE_PROGRESS, handler)
                    sync_bus.unsubscribe(EventType.ENGINE_PROGRESS, handler)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=subscribe_loop) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
