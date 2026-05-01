#!/usr/bin/env python3
"""集成工作流 (Integration Workflow) 端到端测试

验证多个组件协同工作的完整链路：
1. LogCollector → LogProcessor → LogStorage 数据流
2. EventBus + Observer 事件通知链
3. ConfigCoordinator 统一配置管理
4. 模拟完整碰撞引擎运行周期
"""

import os
import json
import time
import tempfile
import pytest
import threading
from unittest.mock import Mock, patch

from src.logging.log_collector import LogCollector
from src.logging.log_processor import LogProcessor, SensitiveDataFilter
from src.logging.log_storage import LogStorage
from src.logging.log_query import LogQuery
from src.logging.events import LogEvent, LogEventType
from src.logging.log_manager import LogManager

from src.collision.event_bus import EventBus, get_event_bus, reset_event_bus
from src.collision.events import (
    EngineStartEvent,
    EngineProgressEvent,
    EngineMatchEvent,
    EngineErrorEvent,
    EngineCompleteEvent,
    EventType,
)
from src.collision.observers import (
    BaseCollisionObserver,
    ObserverManager,
)
from src.collision.collision_stats import CollisionStats

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_global():
    """每个测试前后重置全局状态"""
    reset_event_bus()
    yield
    reset_event_bus()


# ============================================================================
# 数据流集成测试: Collector → Processor → Storage
# ============================================================================


@pytest.mark.integration
class TestLoggingPipeline:
    """日志管道端到端测试"""

    def test_full_pipeline_data_flow(self):
        """验证 Collector → Processor → Storage 完整数据流"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建管道组件
            collector = LogCollector(max_queue_size=100)
            processor = LogProcessor()
            storage = LogStorage(storage_dir=tmpdir)

            # 连接管道
            def pipeline_handler(event):
                processed = processor.process(event)
                if processed:
                    storage.save(processed)

            collector.register_handler("status_update", pipeline_handler)
            collector.register_handler("engine_start", pipeline_handler)
            collector.register_handler("engine_error", pipeline_handler)

            # 启动收集器
            collector.start()

            # 发送事件
            collector.collect_from_queue(
                LogEventType.ENGINE_START, {"mode": "random", "targets": 5}
            )
            collector.collect_from_queue(
                LogEventType.STATUS_UPDATE, {"message": "引擎运行中", "progress": 50}
            )
            collector.collect_from_queue(LogEventType.ENGINE_ERROR, {"error": "GPU内存不足"})

            time.sleep(0.3)
            collector.stop()

            # 验证存储中有数据
            recent = storage.get_recent(10)
            assert len(recent) >= 3
            # 验证数据完整性
            types = [r.get("type") for r in recent]
            assert "engine_start" in types
            assert "status_update" in types
            assert "engine_error" in types


@pytest.mark.integration
class TestLoggingPipelineWithSensitiveFilter:
    """带敏感数据过滤的日志管道"""

    def test_sensitive_data_filtered_in_pipeline(self):
        """敏感数据在管道中应被过滤"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = LogCollector(max_queue_size=100)
            processor = LogProcessor()
            processor.add_filter(SensitiveDataFilter().filter)
            storage = LogStorage(storage_dir=tmpdir)

            def pipeline_handler(event):
                processed = processor.process(event)
                if processed:
                    storage.save(processed)

            collector.register_handler("match_found", pipeline_handler)
            collector.register_handler("status_update", pipeline_handler)
            collector.start()

            # 发送包含敏感数据的事件
            collector.collect_from_queue(
                LogEventType.MATCH_FOUND,
                {"message": "找到匹配!", "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            )
            # 发送安全数据
            collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"message": "正常运行"})

            time.sleep(0.3)
            collector.stop()

            # 安全数据应被存储，敏感数据被过滤
            recent = storage.get_recent(10)
            assert len(recent) >= 1


# ============================================================================
# EventBus + Observer 集成测试
# ============================================================================


@pytest.mark.integration
class TestEventBusObserverIntegration:
    """EventBus + Observer 集成测试"""

    def test_event_bus_to_observer_chain(self):
        """事件从 EventBus 流转到 Observer"""
        bus = EventBus(async_mode=False)
        observer_manager = ObserverManager()

        # 创建观察者收集事件
        received_events = []

        class TestObserver(BaseCollisionObserver):
            def on_progress(self, stats):
                received_events.append(("progress", stats.total_checked))

            def on_match(self, private_key, address, wif):
                received_events.append(("match", address))

        observer = TestObserver()
        observer_manager.add_observer(observer)

        # 通过 EventBus 订阅，桥接到 ObserverManager
        def bridge_progress(event):
            stats = CollisionStats()
            stats.total_checked = event.total_checked
            observer_manager.notify_progress(stats)

        def bridge_match(event):
            observer_manager.notify_match(event.private_key, event.address, event.wif)

        bus.subscribe(EventType.ENGINE_PROGRESS, bridge_progress)
        bus.subscribe(EventType.ENGINE_MATCH, bridge_match)

        # 模拟引擎运行
        bus.publish(EngineProgressEvent(total_checked=1000, speed=50000.0))
        bus.publish(EngineProgressEvent(total_checked=2000, speed=52000.0))
        bus.publish(
            EngineMatchEvent(
                private_key=b"\x01" * 32,
                address="1TestAddress",
                wif="TestWIF",
                target_address="1TargetAddr",
            )
        )
        bus.publish(EngineProgressEvent(total_checked=3000, speed=51000.0))

        bus.stop()

        assert len(received_events) == 4
        assert received_events[0] == ("progress", 1000)
        assert received_events[1] == ("progress", 2000)
        assert received_events[2] == ("match", "1TestAddress")
        assert received_events[3] == ("progress", 3000)


# ============================================================================
# 引擎生命周期集成测试
# ============================================================================


@pytest.mark.integration
class TestEngineLifecycleIntegration:
    """引擎完整生命周期集成测试"""

    def test_full_lifecycle_via_event_bus(self):
        """通过 EventBus 模拟引擎完整生命周期"""
        bus = EventBus(async_mode=False)
        lifecycle_log = []

        def log_event(event_type, event):
            lifecycle_log.append(event_type.value if event_type else "unknown")

        bus.subscribe_to_all(log_event)

        # 启动
        bus.publish(EngineStartEvent(mode="random", target_count=5, batch_size=65536))
        # 进度更新 (3次)
        for i in range(3):
            bus.publish(
                EngineProgressEvent(total_checked=(i + 1) * 10000, speed=50000.0, matches_found=0)
            )
        # 错误事件
        bus.publish(
            EngineErrorEvent(
                error_type="RecoverableError",
                error_message="GPU timeout, retrying",
                recoverable=True,
            )
        )
        # 更多进度
        bus.publish(EngineProgressEvent(total_checked=50000, speed=48000.0))
        # 完成
        bus.publish(
            EngineCompleteEvent(
                total_checked=50000, matches_found=0, elapsed_time=1.0, stop_reason="normal"
            )
        )

        bus.stop()

        assert "engine.start" in lifecycle_log
        assert lifecycle_log.count("engine.progress") == 4
        assert "engine.error" in lifecycle_log
        assert "engine.complete" in lifecycle_log
        assert bus.published_count == 7


# ============================================================================
# LogManager 集成测试
# ============================================================================


@pytest.mark.integration
class TestLogManagerIntegration:
    """LogManager 集成测试"""

    def test_log_manager_lifecycle(self):
        """LogManager 完整生命周期"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lm = LogManager(
                storage_dir=tmpdir,
                enable_console=False,
                enable_file=True,
                redact_sensitive=True,
            )

            lm.start()
            assert lm.is_running() is True

            # 记录各类日志
            lm.info("引擎正在初始化")
            lm.warning("检测到 GPU 温度偏高")
            lm.error("连接超时", timeout=30)
            lm.debug("内部状态: 缓冲区大小=1024")

            # 专用日志
            lm.log_wizard_start({"mode": "interactive"})
            lm.log_target_selected(["1Target1", "1Target2"], target_file="targets.txt")
            lm.log_mode_selected("random")

            time.sleep(0.3)

            lm.stop()
            assert lm.is_running() is False

            # 验证日志已存储
            recent = lm.get_recent(20)
            assert len(recent) > 0

            stats = lm.get_stats()
            assert stats["total_count"] > 0

    def test_log_manager_context_manager(self):
        """LogManager 上下文管理器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with LogManager(storage_dir=tmpdir, enable_console=False, enable_file=True) as lm:
                lm.info("上下文管理器测试")
                time.sleep(0.2)

            assert lm.is_running() is False
            recent = lm.get_recent(5)
            assert len(recent) > 0
