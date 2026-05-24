#!/usr/bin/env python3
"""并发与压力测试 (Concurrency & Stress Tests)

验证系统在高并发和极端条件下的稳定性。

覆盖：
- EventBus 多线程并发发布/订阅
- LogStorage 并发写入
- LogCollector 并发收集
- ObserverManager 并发通知
- 长时间运行稳定性
"""

import math
import tempfile
import threading
import time
from collections import Counter

import pytest

# ============================================================================
# EventBus 并发测试
# ============================================================================


@pytest.mark.thread_safety
class TestEventBusConcurrency:
    """EventBus 并发测试"""

    def test_concurrent_publish_no_data_race(self):
        """多线程并发发布不应有数据竞争"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EngineProgressEvent, EventType

        reset_event_bus()

        bus = EventBus(async_mode=False)
        received = []
        lock = threading.Lock()

        def handler(event):
            with lock:
                received.append(event.total_checked)

        bus.subscribe(EventType.ENGINE_PROGRESS, handler)

        errors_in_threads = []

        def publisher(start, count):
            try:
                for i in range(start, start + count):
                    bus.publish(EngineProgressEvent(total_checked=i, speed=1000.0))
            except Exception as e:
                errors_in_threads.append(e)

        thread_count = 8
        events_per_thread = 100
        threads = []
        for j in range(thread_count):
            t = threading.Thread(target=publisher, args=(j * events_per_thread, events_per_thread))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        bus.stop()

        assert len(errors_in_threads) == 0, f"线程错误: {errors_in_threads}"
        assert bus.published_count == thread_count * events_per_thread
        assert len(received) == thread_count * events_per_thread

    def test_concurrent_subscribe_unsubscribe(self):
        """并发订阅/取消订阅不应导致状态不一致"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EventType

        reset_event_bus()

        bus = EventBus(async_mode=False)
        errors = []

        def sub_unsub_loop():
            try:
                for _ in range(50):

                    def handler(e):
                        return None

                    bus.subscribe(EventType.ENGINE_PROGRESS, handler)
                    bus.unsubscribe(EventType.ENGINE_PROGRESS, handler)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=sub_unsub_loop) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        bus.stop()
        assert len(errors) == 0
        # 最终不应有残留订阅
        assert bus.subscriber_count == 0


# ============================================================================
# LogStorage 并发测试
# ============================================================================


@pytest.mark.thread_safety
class TestLogStorageConcurrency:
    """LogStorage 并发测试"""

    def test_concurrent_saves(self):
        """大量并发保存不应丢失数据"""
        from src.log_engine.log_storage import LogStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir)

            def writer(idx):
                for i in range(250):
                    s.save(
                        {
                            "timestamp": idx * 1000 + i,
                            "type": f"type_{idx}",
                            "message": f"message_{idx}_{i}",
                        },
                    )

            threads = [threading.Thread(target=writer, args=(j,)) for j in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # 验证数据完整性
            stats = s.get_stats()
            assert stats["total_count"] == 2000  # 8 * 250

    def test_concurrent_read_write(self):
        """并发读写不应导致数据损坏"""
        from src.log_engine.log_storage import LogStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir)
            for i in range(100):
                s.save({"timestamp": i, "type": "prefill", "message": f"msg_{i}"})

            errors = []
            results = []

            def writer():
                try:
                    for i in range(100, 200):
                        s.save({"timestamp": i, "type": "concurrent", "message": f"msg_{i}"})
                except Exception as e:
                    errors.append(("writer", e))

            def reader():
                try:
                    for _ in range(50):
                        r = s.get_recent(10)
                        results.append(len(r))
                except Exception as e:
                    errors.append(("reader", e))

            w = threading.Thread(target=writer)
            r1 = threading.Thread(target=reader)
            r2 = threading.Thread(target=reader)

            w.start()
            r1.start()
            r2.start()

            w.join()
            r1.join()
            r2.join()

            assert len(errors) == 0, f"并发读写错误: {errors}"


# ============================================================================
# LogCollector 并发测试
# ============================================================================


@pytest.mark.thread_safety
class TestLogCollectorConcurrency:
    """LogCollector 并发测试"""

    def test_concurrent_collection(self):
        """并发收集不应丢失事件"""
        from src.log_engine.events import LogEventType
        from src.log_engine.log_collector import LogCollector

        collector = LogCollector(max_queue_size=5000)
        received = Counter()
        lock = threading.Lock()

        def handler(event):
            with lock:
                received[event.data.get("thread_id", "unknown")] += 1

        collector.register_handler("status_update", handler)
        collector.start()

        def sender(thread_id):
            for _ in range(100):
                collector.collect_from_queue(
                    LogEventType.STATUS_UPDATE,
                    {"thread_id": thread_id, "msg": "test"},
                    source="test",
                )

        threads = [threading.Thread(target=sender, args=(f"t_{j}",)) for j in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(0.5)
        collector.stop()

        total = sum(received.values())
        assert total == 1000  # 10 threads * 100 events


# ============================================================================
# ObserverManager 并发测试
# ============================================================================


@pytest.mark.thread_safety
class TestObserverManagerConcurrency:
# Observers 模块已移除 — test_concurrent_notify 测试已删除

        threads = [threading.Thread(target=notifier) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发通知错误: {errors}"


# ============================================================================
# 压力测试
# ============================================================================


@pytest.mark.thread_safety
class TestStressTests:
    """压力测试"""

    def test_high_volume_events(self):
        """高容量事件处理压力测试"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EngineProgressEvent, EventType

        reset_event_bus()

        bus = EventBus(async_mode=False)
        count = 0

        def fast_handler(event):
            nonlocal count
            count += 1

        bus.subscribe(EventType.ENGINE_PROGRESS, fast_handler)

        # 快速发布大量事件
        start = time.perf_counter()
        for i in range(10000):
            bus.publish(EngineProgressEvent(total_checked=i, speed=float(i)))
        elapsed = time.perf_counter() - start

        bus.stop()

        # 验证所有事件都被处理
        assert count == 10000
        # 性能检查：10000 个事件应在合理时间内完成（< 2 秒）
        assert elapsed < 2.0, f"高容量事件处理过慢: {elapsed:.2f}s"
        print(f"\n[StressTest] 10000 事件处理耗时: {elapsed:.3f}s")

    def test_large_log_storage(self):
        """大量日志存储压力测试"""
        from src.log_engine.log_storage import LogStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir, max_file_size=10 * 1024 * 1024)

            # 写入 5000 条日志
            start = time.perf_counter()
            for i in range(5000):
                s.save(
                    {
                        "timestamp": i,
                        "type": "stress_test",
                        "message": f"message_{i}" + "x" * 50,
                        "data": {"index": i, "value": i * math.pi},
                    },
                )
            elapsed = time.perf_counter() - start

            stats = s.get_stats()
            assert stats["total_count"] == 5000
            assert elapsed < 5.0, f"大量日志存储过慢: {elapsed:.2f}s"
            print(f"\n[StressTest] 5000 日志存储耗时: {elapsed:.3f}s")

    def test_sustained_load(self):
        """持续负载测试 - 模拟长时间运行"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EngineProgressEvent, EventType

        reset_event_bus()

        bus = EventBus(async_mode=False)
        handler_call_count = 0

        def handler(event):
            nonlocal handler_call_count
            handler_call_count += 1

        bus.subscribe(EventType.ENGINE_PROGRESS, handler)

        # 模拟持续 2 秒的事件流
        duration = 2.0
        start = time.perf_counter()
        event_count = 0

        while time.perf_counter() - start < duration:
            bus.publish(EngineProgressEvent(total_checked=event_count, speed=10000.0))
            event_count += 1
            time.sleep(0.001)  # 模拟 1000 events/s

        bus.stop()

        # 验证处理了一切事件
        assert handler_call_count == event_count
        print(f"\n[StressTest] 持续 {duration}s 负载: {event_count} 个事件处理完成")
