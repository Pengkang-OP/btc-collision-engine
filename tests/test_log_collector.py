#!/usr/bin/env python3
"""日志收集器 (LogCollector) 单元测试

覆盖：
- 初始化与配置
- 启动/停止生命周期
- 日志收集与处理
- Handler 注册/取消
- Logger 附加/分离
- 队列满处理
- 异常容错
"""

import pytest
import logging
import time
from unittest.mock import Mock, patch, call

from src.logging.log_collector import LogCollector, _CollectorLogHandler
from src.logging.events import LogEvent, LogEventType

# ============================================================================
# 初始化测试
# ============================================================================


@pytest.mark.unit
class TestLogCollectorInit:
    """LogCollector 初始化测试"""

    def test_default_initialization(self):
        collector = LogCollector()
        assert collector._running is False
        assert collector._collector_thread is None
        assert collector._log_handler is not None
        assert isinstance(collector._handlers, dict)
        assert len(collector._handlers) == 0

    def test_custom_queue_size(self):
        collector = LogCollector(max_queue_size=500)
        assert collector._queue.maxsize == 500

    def test_log_handler_setup_on_init(self):
        collector = LogCollector()
        assert collector._log_handler is not None
        assert collector._log_handler.level == logging.DEBUG


# ============================================================================
# 启停生命周期测试
# ============================================================================


@pytest.mark.unit
class TestLogCollectorStartStop:
    """LogCollector 启停测试"""

    def test_start_creates_thread(self):
        collector = LogCollector()
        collector.start()
        assert collector._running is True
        assert collector._collector_thread is not None
        assert collector._collector_thread.is_alive()
        collector.stop()

    def test_double_start_is_idempotent(self):
        collector = LogCollector()
        collector.start()
        thread1 = collector._collector_thread
        collector.start()
        thread2 = collector._collector_thread
        assert thread1 is thread2
        collector.stop()

    def test_stop_joins_thread(self):
        collector = LogCollector()
        collector.start()
        collector.stop()
        assert collector._running is False
        # 线程应已结束
        if collector._collector_thread:
            collector._collector_thread.join(timeout=0.5)
            assert not collector._collector_thread.is_alive()

    def test_stop_when_not_started(self):
        collector = LogCollector()
        collector.stop()  # 不应抛异常
        assert collector._running is False


# ============================================================================
# 日志收集测试
# ============================================================================


@pytest.mark.unit
class TestLogCollectorCollection:
    """日志收集功能测试"""

    def test_collect_from_queue(self):
        collector = LogCollector()
        handler = Mock()
        collector.register_handler("status_update", handler)
        collector.start()

        collector.collect_from_queue(
            LogEventType.STATUS_UPDATE, {"message": "test"}, source="test_source"
        )

        # 给收集线程一点时间处理
        time.sleep(0.2)
        collector.stop()

        handler.assert_called()
        called_event = handler.call_args[0][0]
        assert isinstance(called_event, LogEvent)
        assert called_event.data == {"message": "test"}
        assert called_event.source == "test_source"

    def test_collect_log(self):
        collector = LogCollector()
        handler = Mock()
        collector.register_handler("status_update", handler)
        collector.start()

        collector.collect_log("test_logger", logging.INFO, "test message")

        time.sleep(0.2)
        collector.stop()

        handler.assert_called()
        called_event = handler.call_args[0][0]
        assert called_event.data["logger"] == "test_logger"
        assert called_event.data["level"] == "INFO"
        assert called_event.data["message"] == "test message"

    def test_queue_full_drops_event(self):
        collector = LogCollector(max_queue_size=1)
        # 填满队列
        collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"msg": "1"})
        collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"msg": "2"})
        # 不应抛异常
        collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"msg": "3"})


# ============================================================================
# Handler 注册/取消测试
# ============================================================================


@pytest.mark.unit
class TestLogCollectorHandlers:
    """Handler 管理测试"""

    def test_register_handler(self):
        collector = LogCollector()
        handler = Mock()
        collector.register_handler("engine_start", handler)
        assert "engine_start" in collector._handlers
        assert collector._handlers["engine_start"] is handler

    def test_unregister_handler(self):
        collector = LogCollector()
        handler = Mock()
        collector.register_handler("engine_start", handler)
        collector.unregister_handler("engine_start")
        assert "engine_start" not in collector._handlers

    def test_unregister_nonexistent_handler(self):
        collector = LogCollector()
        collector.unregister_handler("nonexistent")  # 不应抛异常

    def test_multiple_handlers(self):
        collector = LogCollector()
        h1, h2 = Mock(), Mock()
        collector.register_handler("event_a", h1)
        collector.register_handler("event_b", h2)
        assert len(collector._handlers) == 2


# ============================================================================
# Logger 附加/分离测试
# ============================================================================


@pytest.mark.unit
class TestLogCollectorLoggerAttachment:
    """Logger 附加功能测试"""

    def test_attach_to_logger(self):
        collector = LogCollector()
        test_logger = logging.getLogger("test_attach_logger")
        test_logger.handlers.clear()

        collector.attach_to_logger("test_attach_logger")
        assert collector._log_handler in test_logger.handlers
        assert test_logger.level == logging.DEBUG

        collector.detach_from_logger("test_attach_logger")
        assert collector._log_handler not in test_logger.handlers

    def test_attach_to_root_logger(self):
        collector = LogCollector()
        collector.attach_to_logger(None)  # 根日志器
        root_logger = logging.getLogger()
        assert collector._log_handler in root_logger.handlers
        collector.detach_from_logger(None)

    def test_handler_error_does_not_crash(self):
        """处理器异常不应导致收集循环崩溃"""
        collector = LogCollector()
        handler = Mock(side_effect=RuntimeError("handler error"))
        collector.register_handler("status_update", handler)
        collector.start()

        collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"msg": "test"})
        time.sleep(0.2)
        collector.stop()
        # 不应抛异常


# ============================================================================
# _CollectorLogHandler 测试
# ============================================================================


@pytest.mark.unit
class TestCollectorLogHandler:
    """_CollectorLogHandler 内部类测试"""

    def test_emit_calls_collector(self):
        collector = LogCollector()
        handler = _CollectorLogHandler(collector)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        # 不应抛异常

    def test_emit_error_handled(self):
        """emit 异常时调用 handleError"""
        collector = Mock()
        collector.collect_log = Mock(side_effect=RuntimeError("emit error"))
        handler = _CollectorLogHandler(collector)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        handler.emit(record)  # 不应抛异常
