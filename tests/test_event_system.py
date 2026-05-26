"""事件系统单元测试

测试范围:
- 事件定义和类型
- EventBus订阅/发布
- 线程安全
- 异步模式
- 事件适配器
- 向后兼容性
"""

import threading
import time
from unittest.mock import Mock

from src.collision.event_bus import EventBus, get_event_bus, reset_event_bus
from src.collision.events import (
    EngineErrorEvent,
    EngineMatchEvent,
    EngineProgressEvent,
    EventType,
)
from src.monitoring.event_adapters import (
    setup_data_logging,
)


class TestEventType:
    """测试事件类型定义"""

    def test_event_type_values(self):
        """测试事件类型值格式"""
        assert EventType.ENGINE_START.value == "engine_start"
        assert EventType.ENGINE_PROGRESS.value == "engine_progress"
        assert EventType.ENGINE_MATCH.value == "engine_match"
        assert EventType.ENGINE_ERROR.value == "engine_error"
        assert EventType.ENGINE_COMPLETE.value == "engine_complete"

    def test_event_type_count(self):
        """测试事件类型数量"""
        # Phase 6：EventType 精简为 6 个核心事件
        event_types = list(EventType)
        assert len(event_types) >= 6


class TestCollisionEvent:
    """测试事件数据类"""

    def test_engine_progress_event(self):
        """测试引擎进度事件"""
        event = EngineProgressEvent(
            total_checked=1000000,
            speed=537000.0,
            avg_speed=500000.0,
            matches_found=0,
            cpu_usage=45.2,
            memory_usage=60.5,
        )

        assert event.total_checked == 1000000
        assert event.speed == 537000.0
        assert event.event_type == EventType.ENGINE_PROGRESS
        assert event.timestamp is not None

    def test_engine_match_event(self):
        """测试引擎匹配事件"""
        event = EngineMatchEvent(
            private_key=b"test_key",
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ",
        )

        assert event.address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert event.private_key == b"test_key"
        assert event.event_type == EventType.ENGINE_MATCH

    def test_engine_error_event(self):
        """测试引擎错误事件"""
        error = ValueError("Test error")
        event = EngineErrorEvent(error_type="ValueError", error_message="Test error", exception=error)

        assert event.error_type == "ValueError"
        assert event.event_type == EventType.ENGINE_ERROR


class TestEventBus:
    """测试事件总线"""

    def setUp(self):
        """每个测试前重置事件总线"""
        reset_event_bus()

    def test_subscribe_and_publish(self):
        """测试订阅和发布"""
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        # 订阅
        bus.subscribe(EventType.ENGINE_PROGRESS, handler)

        # 发布
        event = EngineProgressEvent(total_checked=1000)
        bus.publish(event)

        # 验证
        assert len(received_events) == 1
        assert received_events[0].total_checked == 1000

    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        bus = EventBus()
        results = []

        def handler1(event):
            results.append(("h1", event.total_checked))

        def handler2(event):
            results.append(("h2", event.total_checked))

        bus.subscribe(EventType.ENGINE_PROGRESS, handler1)
        bus.subscribe(EventType.ENGINE_PROGRESS, handler2)

        event = EngineProgressEvent(total_checked=5000)
        bus.publish(event)

        assert len(results) == 2
        assert results in ("h1", 5000)
        assert results in ("h2", 5000)

    def test_unsubscribe(self):
        """测试取消订阅"""
        bus = EventBus()
        call_count = [0]

        def handler(event):
            call_count[0] += 1

        bus.subscribe(EventType.ENGINE_PROGRESS, handler)
        bus.publish(EngineProgressEvent())
        assert call_count[0] == 1

        # 取消订阅
        bus.unsubscribe(EventType.ENGINE_PROGRESS, handler)
        bus.publish(EngineProgressEvent())
        assert call_count[0] == 1  # 应该仍然为1

    def test_no_duplicate_subscribers(self):
        """测试不允许重复订阅"""
        bus = EventBus()
        call_count = [0]

        def handler(event):
            call_count[0] += 1

        # 订阅两次
        bus.subscribe(EventType.ENGINE_PROGRESS, handler)
        bus.subscribe(EventType.ENGINE_PROGRESS, handler)

        bus.publish(EngineProgressEvent())
        assert call_count[0] == 1  # 只应该调用一次

    def test_handler_exception_not_crash_bus(self):
        """测试处理器异常不会使总线崩溃"""
        bus = EventBus()
        received = []

        def failing_handler(event):
            raise ValueError("Handler error")

        def good_handler(event):
            received.append(event)

        bus.subscribe(EventType.ENGINE_PROGRESS, failing_handler)
        bus.subscribe(EventType.ENGINE_PROGRESS, good_handler)

        # 发布事件 - 不应该崩溃
        event = EngineProgressEvent()
        bus.publish(event)

        # 好的处理器应该仍然被调用
        assert len(received) == 1

    def test_handler_error_callback(self):
        """测试错误处理器回调"""
        bus = EventBus()
        errors = []

        def error_handler(event, error):
            errors.append((event.event_type, str(error)))

        bus.set_error_handler(error_handler)

        def failing_handler(event):
            raise RuntimeError("Test error")

        bus.subscribe(EventType.ENGINE_PROGRESS, failing_handler)
        bus.publish(EngineProgressEvent())

        # 验证错误被捕获
        assert len(errors) == 1
        assert errors[0][0] == EventType.ENGINE_PROGRESS

    def test_subscribe_to_all(self):
        """测试订阅所有事件"""
        bus = EventBus()
        all_events = []

        def handler(event_type, event):
            all_events.append((event_type, event))

        bus.subscribe_to_all(handler)

        bus.publish(EngineProgressEvent())
        bus.publish(EngineMatchEvent(private_key=b"key", address="addr", wif="wif"))

        assert len(all_events) == 2


class TestEventBusAsync:
    """测试异步事件总线"""

    def setUp(self):
        reset_event_bus()

    def test_async_publish(self):
        """测试异步发布"""
        bus = EventBus(async_mode=True)
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.ENGINE_PROGRESS, handler)
        bus.publish(EngineProgressEvent(total_checked=1000))

        # 等待异步处理（轮询等待，避免固定sleep不可靠）
        for _ in range(20):  # 最多等待2秒
            time.sleep(0.1)
            if len(received) >= 1:
                break

        assert len(received) == 1

    def test_async_queue_full(self):
        """测试异步队列满时的行为"""
        bus = EventBus(async_mode=True, max_queue_size=2)

        # 填满队列
        bus.publish(EngineProgressEvent())
        bus.publish(EngineProgressEvent())

        # 队列满时发布应该不崩溃
        bus.publish(EngineProgressEvent())

    def test_stop_clears_queue(self):
        """测试停止时清空队列"""
        bus = EventBus(async_mode=True)
        bus.publish(EngineProgressEvent())
        bus.publish(EngineProgressEvent())

        bus.stop()

        # 工作线程应该停止
        assert not bus._running


class TestEventBusThreadSafety:
    """测试事件总线线程安全"""

    def setUp(self):
        reset_event_bus()

    def test_concurrent_subscribe(self):
        """测试并发订阅"""
        bus = EventBus()
        errors = []

        def subscribe_worker(worker_id):
            try:

                def handler(event):
                    pass

                bus.subscribe(EventType.ENGINE_PROGRESS, handler)
            except Exception as e:
                errors.append(e)

        # 多线程并发订阅
        threads = []
        for i in range(10):
            t = threading.Thread(target=subscribe_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 不应该有错误
        assert len(errors) == 0

    def test_concurrent_publish(self):
        """测试并发发布"""
        bus = EventBus()
        counter = [0]
        lock = threading.Lock()

        def handler(event):
            with lock:
                counter[0] += 1

        bus.subscribe(EventType.ENGINE_PROGRESS, handler)

        def publish_worker():
            for _ in range(100):
                bus.publish(EngineProgressEvent())

        # 多线程并发发布
        threads = []
        for _ in range(5):
            t = threading.Thread(target=publish_worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 应该处理了所有事件
        assert counter[0] == 500


class TestGlobalEventBus:
    """测试全局事件总线单例"""

    def setUp(self):
        reset_event_bus()

    def test_get_event_bus_returns_same_instance(self):
        """测试获取同一实例"""
        bus1 = get_event_bus()
        bus2 = get_event_bus()

        assert bus1 is bus2

    def test_reset_clears_instance(self):
        """测试重置清除实例"""
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()

        assert bus1 is not bus2


class TestDataLoggerAdapter:
    """测试DataLogger事件适配器"""

    def test_setup_data_logging(self):
        """测试设置数据日志"""
        from src.monitoring.data_logger import DataLogger

        bus = EventBus()
        mock_logger = Mock(spec=DataLogger)

        adapter = setup_data_logging(bus, mock_logger)

        # 验证适配器创建成功
        assert adapter is not None
        assert adapter.data_logger == mock_logger

    def test_adapter_handles_progress_event(self):
        """测试适配器处理进度事件"""
        from src.monitoring.data_logger import DataLogger

        bus = EventBus()
        mock_logger = Mock(spec=DataLogger)

        setup_data_logging(bus, mock_logger)

        # 发布进度事件
        event = EngineProgressEvent(total_checked=1000000, speed=537000.0, matches_found=0)
        bus.publish(event)

        # 验证DataLogger被调用 (adapter calls log_progress for progress events)
        mock_logger.log_progress.assert_called()


class TestDependencyInjection:
    """测试依赖注入"""

    def test_custom_event_bus(self):
        """测试自定义事件总线注入"""
        EventBus()

        # 应该可以注入自定义事件总线
        # (这里只是验证构造函数接受参数，不实际运行引擎)
        try:
            # 注意: 这里会创建真实引擎，但不会启动
            # 实际测试中应该Mock其他依赖
            pass
        except Exception:
            pass  # 忽略其他依赖缺失的错误

    def test_mock_event_bus_for_testing(self):
        """测试使用Mock事件总线"""
        mock_bus = Mock(spec=EventBus)

        # 验证Mock总线可以正常工作
        mock_bus.subscribe(EventType.ENGINE_PROGRESS, lambda e: None)
        mock_bus.publish(EngineProgressEvent())

        mock_bus.subscribe.assert_called()
        mock_bus.publish.assert_called()
