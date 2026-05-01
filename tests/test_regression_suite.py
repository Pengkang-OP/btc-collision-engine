#!/usr/bin/env python3
"""回归测试套件 (Regression Test Suite)

集中验证历史修复问题不会回退，确保已知 Bug 不会再次出现。

覆盖：
- P0-P3 级别关键修复验证
- 边界条件回归
- 数据完整性回归
- 安全性回归
- API 兼容性回归
"""

import pytest
import json
import tempfile
import os
import time
from unittest.mock import Mock, patch

# ============================================================================
# P0 安全相关修复回归
# ============================================================================


@pytest.mark.regression
class TestP0SecurityRegression:
    """P0 安全修复回归测试"""

    def test_sensitive_data_not_leaked_in_logs(self):
        """确保私钥不会泄露到日志中"""
        from src.logging.log_processor import SensitiveDataFilter

        sf = SensitiveDataFilter()

        # 私有密钥模式
        private_key_hex = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        assert sf.filter(Mock(data={"key": private_key_hex})) is False

        # WIF格式不应被特殊处理(但包含在data中被str()检查)
        text_with_key = f"PrivateKey={private_key_hex}"
        redacted = SensitiveDataFilter.redact(text_with_key)
        assert "***REDACTED***" in redacted

    def test_address_not_exposed_in_unfiltered_logs(self):
        """确保地址在过滤时不会被日志泄露"""
        from src.logging.log_processor import SensitiveDataFilter

        sf = SensitiveDataFilter()

        # P2PKH地址
        test_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = SensitiveDataFilter.redact(f"Found match: {test_addr}")
        assert test_addr not in result
        assert "[P2PKH_ADDRESS]" in result

    def test_event_bus_null_safety(self):
        """None 事件和 None event_type 应被安全处理"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import CollisionEvent

        reset_event_bus()

        bus = EventBus(async_mode=False)

        # publish None
        bus.publish(None)
        assert bus.published_count == 0

        # publish event with None event_type
        bus.publish(CollisionEvent(event_type=None))
        assert bus.published_count == 0

        bus.stop()


# ============================================================================
# P1 数据完整性回归
# ============================================================================


@pytest.mark.regression
class TestP1DataIntegrityRegression:
    """P1 数据完整性回归测试"""

    def test_collision_stats_thread_safety(self):
        """CollisionStats 线程安全快照不被并发修改破坏"""
        import threading
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.start_time = time.time()
        stats.update(1000)

        snapshots = []

        def modifier():
            for i in range(100):
                stats.update(i * 100)
                stats.add_match(bytes(32), f"addr_{i}")

        def reader():
            for _ in range(100):
                snap = stats.snapshot()
                snapshots.append(snap)

        threads = [threading.Thread(target=modifier), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有快照应有效
        for snap in snapshots:
            assert snap.total_checked >= 0
            assert snap.speed >= 0

    def test_event_bus_handler_exception_isolation(self):
        """一个 handler 异常不影响其他 handler"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EngineStartEvent, EventType

        reset_event_bus()

        bus = EventBus(async_mode=False)
        good_called = False

        def bad_handler(event):
            raise RuntimeError("handler crash")

        def good_handler(event):
            nonlocal good_called
            good_called = True

        bus.subscribe(EventType.ENGINE_START, bad_handler)
        bus.subscribe(EventType.ENGINE_START, good_handler)

        bus.publish(EngineStartEvent(mode="test", target_count=1, batch_size=1024))

        assert good_called is True, "Good handler 未被执行"
        assert bus.error_count == 1
        bus.stop()

    def test_log_collector_queue_full_no_crash(self):
        """队列满时不应崩溃"""
        from src.logging.log_collector import LogCollector
        from src.logging.events import LogEventType

        collector = LogCollector(max_queue_size=2)
        for i in range(20):
            collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"msg": f"test_{i}"})
        # 不应抛异常


# ============================================================================
# P2 边界条件回归
# ============================================================================


@pytest.mark.regression
class TestP2BoundaryRegression:
    """P2 边界条件回归测试"""

    def test_empty_data_handling(self):
        """空数据处理"""
        from src.logging.log_processor import LogProcessor, SensitiveDataFilter
        from src.logging.events import LogEvent, LogEventType

        processor = LogProcessor()
        event = LogEvent(LogEventType.STATUS_UPDATE, data={})
        result = processor.process(event)
        assert result is not None
        assert result["data"] == {}

        sf = SensitiveDataFilter()
        event_empty = LogEvent(LogEventType.STATUS_UPDATE, data={})
        assert sf.filter(event_empty) is True

    def test_base58_empty_string(self):
        """Base58 空字符串编解码"""
        from src.core.base58 import Base58

        result = Base58.decode("")
        assert result == b""

    def test_log_storage_empty_queries(self):
        """空存储查询返回空"""
        from src.logging.log_storage import LogStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir)
            assert s.get_recent() == []
            assert s.get_by_type("any") == []
            assert s.search("anything") == []
            assert s.get_stats()["total_count"] == 0

    def test_event_bus_clear_then_publish(self):
        """清空后重新发布"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EngineStartEvent, EventType

        reset_event_bus()

        bus = EventBus(async_mode=False)
        handler = Mock(__name__="test_handler")
        bus.subscribe(EventType.ENGINE_START, handler)
        bus.clear()

        bus.publish(EngineStartEvent(mode="test", target_count=1, batch_size=1024))
        handler.assert_not_called()
        bus.stop()


# ============================================================================
# P3 API兼容性回归
# ============================================================================


@pytest.mark.regression
class TestP3APICompatibility:
    """P3 API兼容性回归测试"""

    def test_event_bus_context_manager(self):
        """验证上下文管理器 API 正常工作"""
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EngineStartEvent, EventType

        reset_event_bus()

        with EventBus(async_mode=False) as bus:
            handler = Mock(__name__="test_handler")
            bus.subscribe(EventType.ENGINE_START, handler)
            bus.publish(EngineStartEvent(mode="test", target_count=1, batch_size=1024))
            handler.assert_called_once()

    def test_collision_stats_reset(self):
        """CollisionStats.reset() API 兼容性"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.update(1000)
        stats.add_match(bytes(32), "addr1")

        stats.reset()
        assert stats.total_checked == 0
        assert stats.speed == 0.0
        assert len(stats.matches) == 0
        assert stats.gpu_errors == 0

    def test_collision_stats_error_tracking(self):
        """错误追踪 API 兼容性"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.record_gpu_error(is_resource_error=True)
        stats.record_worker_error()
        stats.record_wif_encode_error()

        assert stats.gpu_errors == 1
        assert stats.worker_errors == 1
        assert stats.wif_encode_errors == 1
        assert stats.resource_errors == 1

        summary = stats.error_summary()
        assert "GPU=1" in summary
        assert "Worker=1" in summary


# ============================================================================
# 安全性回归测试
# ============================================================================


@pytest.mark.regression
class TestSecurityRegression:
    """安全性回归测试"""

    def test_private_key_not_in_event_metadata(self):
        """EngineMatchEvent 元数据不应包含私钥"""
        from src.collision.events import EngineMatchEvent

        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1TestAddress",
            wif="TestWIF",
            target_address="1Target",
        )
        assert "private_key" not in event.metadata
        assert "wif" not in event.metadata

    def test_sensitive_filter_covers_all_address_types(self):
        """敏感数据过滤器覆盖所有地址类型"""
        from src.logging.log_processor import SensitiveDataFilter

        patterns = SensitiveDataFilter.SENSITIVE_PATTERNS
        assert len(patterns) >= 6  # 私钥 + PrivateKey + 4种地址类型

        # 验证每种地址类型都能被匹配
        test_addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # P2PKH
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32
            "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2ys4tqmpyuf4v",  # Bech32m
        ]
        for addr in test_addresses:
            redacted = SensitiveDataFilter.redact(addr)
            assert addr not in redacted, f"地址 {addr[:20]}... 未被脱敏"
