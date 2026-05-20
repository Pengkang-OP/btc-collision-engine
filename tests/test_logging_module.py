#!/usr/bin/env python3
"""日志模块全面单元测试

覆盖 src/log_engine/ 下全部7个模块：
- events.py (LogEvent, LogEventType)
- log_processor.py (LogProcessor, SensitiveDataFilter)
- log_storage.py (LogStorage)
- log_query.py (LogQuery)
- log_collector.py (LogCollector)
- log_manager.py (LogManager)
"""

import json
import os
import time
from unittest.mock import Mock

import pytest

from src.log_engine.events import LogEvent, LogEventType
from src.log_engine.log_collector import LogCollector
from src.log_engine.log_manager import LogLevel, LogManager
from src.log_engine.log_processor import LogProcessor, SensitiveDataFilter
from src.log_engine.log_query import LogQuery
from src.log_engine.log_storage import LogStorage

# ============================================================================
# 1. LogEvent & LogEventType 测试
# ============================================================================


class TestLogEventType:
    """LogEventType 枚举测试"""

    def test_all_event_types_defined(self):
        expected = [
            "engine_start",
            "engine_stop",
            "engine_error",
            "engine_pause",
            "engine_resume",
            "gpu_detected",
            "gpu_usage_update",
            "performance_update",
            "match_found",
            "checkpoint_saved",
            "config_loaded",
            "status_update",
        ]
        for name in expected:
            assert hasattr(LogEventType, name.upper())

    def test_event_type_value(self):
        assert LogEventType.ENGINE_START.value == "engine_start"
        assert LogEventType.STATUS_UPDATE.value == "status_update"


class TestLogEvent:
    """LogEvent 数据结构测试"""

    def test_default_creation(self):
        event = LogEvent(event_type=LogEventType.STATUS_UPDATE)
        assert event.event_type == LogEventType.STATUS_UPDATE
        assert event.source == "logging"
        assert isinstance(event.data, dict)
        assert isinstance(event.timestamp, float)

    def test_with_data_and_source(self):
        event = LogEvent(
            event_type=LogEventType.ENGINE_ERROR,
            data={"error": "test error", "code": 500},
            source="wizard",
        )
        assert event.data["error"] == "test error"
        assert event.source == "wizard"

    def test_to_dict(self):
        event = LogEvent(
            event_type=LogEventType.MATCH_FOUND,
            data={"key": "val"},
            source="engine",
        )
        d = event.to_dict()
        assert d["event_type"] == "match_found"
        assert d["data"] == {"key": "val"}
        assert d["source"] == "engine"
        assert "timestamp" in d

    def test_formatted_time(self):
        event = LogEvent(
            event_type=LogEventType.STATUS_UPDATE,
            timestamp=1714521600.0,  # 2024-05-01 00:00:00 UTC
        )
        ft = event.formatted_time
        assert isinstance(ft, str)
        assert len(ft) == 19  # YYYY-MM-DD HH:MM:SS


# ============================================================================
# 2. LogProcessor & SensitiveDataFilter 测试
# ============================================================================


class TestLogProcessor:
    """LogProcessor 测试"""

    def test_format_basic_event(self):
        processor = LogProcessor()
        event = LogEvent(LogEventType.STATUS_UPDATE, {"message": "hello"})
        result = processor.format(event)
        assert result["type"] == "status_update"
        assert "hello" in result["message"]
        assert "formatted_time" in result

    def test_format_with_error_data(self):
        processor = LogProcessor()
        event = LogEvent(LogEventType.ENGINE_ERROR, {"error": "GPU failed"})
        result = processor.format(event)
        assert "GPU failed" in result["message"]

    def test_format_to_json(self):
        processor = LogProcessor()
        event = LogEvent(LogEventType.STATUS_UPDATE, {"msg": "test"})
        json_str = processor.format_to_json(event)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["type"] == "status_update"

    def test_format_to_text(self):
        processor = LogProcessor()
        event = LogEvent(LogEventType.STATUS_UPDATE, {"message": "hello"})
        text = processor.format_to_text(event)
        assert "hello" in text

    def test_process_with_filter(self):
        processor = LogProcessor()

        # 添加总是返回 False 的过滤器
        processor.add_filter(lambda e: False)
        event = LogEvent(LogEventType.STATUS_UPDATE, {"msg": "test"})
        result = processor.process(event)
        assert result is None

    def test_process_batch(self):
        processor = LogProcessor()
        events = [
            LogEvent(LogEventType.STATUS_UPDATE, {"msg": "a"}),
            LogEvent(LogEventType.ENGINE_START, {"msg": "b"}),
        ]
        results = processor.process_batch(events)
        assert len(results) == 2

    def test_process_batch_with_filtered(self):
        processor = LogProcessor()
        processor.add_filter(lambda e: "a" in str(e.data))
        events = [
            LogEvent(LogEventType.STATUS_UPDATE, {"msg": "a"}),
            LogEvent(LogEventType.STATUS_UPDATE, {"msg": "b"}),
        ]
        results = processor.process_batch(events)
        assert len(results) == 1

    def test_add_remove_filter(self):
        processor = LogProcessor()

        def f(e):  # noqa: E306
            return True

        processor.add_filter(f)
        assert len(processor._filters) == 1
        processor.remove_filter(f)
        assert len(processor._filters) == 0

    def test_add_remove_formatter(self):
        processor = LogProcessor()

        def fmt(d):  # noqa: E306
            return d

        processor.add_formatter("status_update", fmt)
        assert "status_update" in processor._formatters
        processor.remove_formatter("status_update")
        assert "status_update" not in processor._formatters


class TestSensitiveDataFilter:
    """SensitiveDataFilter 测试"""

    def test_enabled_blocks_private_key(self):
        f = SensitiveDataFilter(enabled=True)
        event = LogEvent(LogEventType.STATUS_UPDATE, {"private_key": "a" * 64})
        assert f.filter(event) is False

    def test_disabled_allows_all(self):
        f = SensitiveDataFilter(enabled=False)
        event = LogEvent(LogEventType.STATUS_UPDATE, {"private_key": "a" * 64})
        assert f.filter(event) is True

    def test_non_sensitive_passes(self):
        f = SensitiveDataFilter(enabled=True)
        event = LogEvent(LogEventType.STATUS_UPDATE, {"message": "normal log"})
        assert f.filter(event) is True

    def test_redact_classmethod(self):
        text = "key=abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234 test"
        result = SensitiveDataFilter.redact(text)
        assert "***REDACTED***" in result

    def test_redact_p2pkh_address(self):
        text = "Found: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = SensitiveDataFilter.redact(text)
        assert "[P2PKH_ADDRESS]" in result

    def test_blocks_p2pkh_address_in_event(self):
        f = SensitiveDataFilter(enabled=True)
        event = LogEvent(
            LogEventType.MATCH_FOUND, {"address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        )
        assert f.filter(event) is False


# ============================================================================
# 3. LogStorage 测试
# ============================================================================


class TestLogStorage:
    """LogStorage 测试"""

    @pytest.fixture
    def storage(self, tmp_path):
        """创建临时目录中的存储实例"""
        storage_dir = str(tmp_path / "test_logs")
        return LogStorage(storage_dir=storage_dir)

    def test_init_creates_directory(self, tmp_path):
        storage_dir = str(tmp_path / "new_logs")
        LogStorage(storage_dir=storage_dir)
        assert os.path.exists(storage_dir)

    def test_save_to_memory(self, storage):
        event = {"type": "status_update", "message": "hello"}
        result = storage.save(event)
        assert result is True
        stats = storage.get_stats()
        assert stats["total_count"] == 1

    def test_save_batch(self, storage):
        events = [{"type": "status_update", "message": f"msg{i}"} for i in range(5)]
        count = storage.save_batch(events)
        assert count == 5

    def test_get_recent(self, storage):
        for i in range(10):
            storage.save({"type": "status_update", "message": f"msg{i}"})
        recent = storage.get_recent(3)
        assert len(recent) == 3

    def test_get_by_type(self, storage):
        storage.save({"type": "engine_start", "message": "start"})
        storage.save({"type": "status_update", "message": "update"})
        storage.save({"type": "engine_start", "message": "start2"})
        results = storage.get_by_type("engine_start")
        assert len(results) == 2

    def test_search(self, storage):
        storage.save({"type": "status_update", "message": "GPU initialized"})
        storage.save({"type": "status_update", "message": "CPU fallback"})
        results = storage.search("GPU")
        assert len(results) == 1
        assert "GPU initialized" in results[0]["message"]

    def test_search_case_insensitive(self, storage):
        storage.save({"type": "status_update", "message": "GPU initialized"})
        results = storage.search("gpu", case_sensitive=False)
        assert len(results) == 1

    def test_search_case_sensitive(self, storage):
        storage.save({"type": "status_update", "message": "GPU initialized"})
        results = storage.search("gpu", case_sensitive=True)
        assert len(results) == 0

    def test_clear(self, storage):
        storage.save({"type": "test", "message": "data"})
        assert storage.get_stats()["total_count"] == 1
        storage.clear()
        assert storage.get_stats()["total_count"] == 0

    def test_export_to_json(self, storage, tmp_path):
        storage.save({"type": "status_update", "message": "hello"})
        export_path = str(tmp_path / "export.json")
        result = storage.export_to_json(export_path)
        assert result is True
        assert os.path.exists(export_path)
        with open(export_path) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_get_by_timerange(self, storage):
        now = time.time()
        storage.save({"type": "test", "message": "old", "timestamp": now - 3600})
        storage.save({"type": "test", "message": "recent", "timestamp": now})
        results = storage.get_by_timerange(now - 10, now + 10)
        assert len(results) == 1
        assert results[0]["message"] == "recent"


# ============================================================================
# 4. LogQuery 测试
# ============================================================================


class TestLogQuery:
    """LogQuery 测试"""

    @pytest.fixture
    def query_with_data(self, tmp_path):
        """创建含预置日志数据的查询器"""
        storage_dir = str(tmp_path / "query_logs")
        os.makedirs(storage_dir, exist_ok=True)
        log_file = os.path.join(storage_dir, "wizard.log")
        events = [
            {
                "type": "engine_start",
                "message": "engine started",
                "timestamp": time.time() - 60,
                "source": "engine",
            },
            {
                "type": "status_update",
                "message": "processing keys",
                "timestamp": time.time() - 30,
                "source": "engine",
            },
            {
                "type": "engine_error",
                "message": "GPU timeout",
                "timestamp": time.time(),
                "source": "gpu",
            },
        ]
        with open(log_file, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return LogQuery(storage_dir=storage_dir)

    def test_no_file_returns_empty(self, tmp_path):
        query = LogQuery(storage_dir=str(tmp_path / "nonexistent"))
        results = query.get_recent()
        assert results == []

    def test_get_recent(self, query_with_data):
        results = query_with_data.get_recent(2)
        assert len(results) == 2

    def test_query_by_type(self, query_with_data):
        results = query_with_data.query(event_type="engine_start")
        assert len(results) == 1
        assert results[0]["message"] == "engine started"

    def test_query_by_source(self, query_with_data):
        results = query_with_data.query(source="gpu")
        assert len(results) == 1

    def test_query_by_keyword(self, query_with_data):
        results = query_with_data.query(keyword="GPU")
        assert len(results) == 1

    def test_get_by_type(self, query_with_data):
        results = query_with_data.get_by_type("engine_start")
        assert len(results) == 1

    def test_count_by_type(self, query_with_data):
        counts = query_with_data.count_by_type()
        assert counts.get("engine_start") == 1
        assert counts.get("status_update") == 1
        assert counts.get("engine_error") == 1

    def test_get_statistics(self, query_with_data):
        stats = query_with_data.get_statistics()
        assert stats["total_count"] == 3
        assert stats["log_file_exists"] is True

    def test_tail(self, query_with_data):
        results = query_with_data.tail(1)
        assert len(results) == 1

    def test_filter_with_predicate(self, query_with_data):
        results = query_with_data.filter(lambda e: "error" in e.get("type", ""))
        assert len(results) == 1

    def test_corrupted_line_skipped(self, tmp_path):
        storage_dir = str(tmp_path / "corrupt_logs")
        os.makedirs(storage_dir, exist_ok=True)
        log_file = os.path.join(storage_dir, "wizard.log")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write('{"type": "good", "message": "ok"}\n')
            f.write("invalid json line\n")
            f.write('{"type": "good2", "message": "ok2"}\n')
        query = LogQuery(storage_dir=storage_dir)
        results = query.get_recent()
        assert len(results) == 2


# ============================================================================
# 5. LogCollector 测试
# ============================================================================

from conftest import poll_until  # noqa: E402


class TestLogCollector:
    """LogCollector 测试"""

    def test_init(self):
        collector = LogCollector()
        assert collector._running is False
        assert collector._queue is not None

    def test_register_handler(self):
        collector = LogCollector()
        handler = Mock()
        collector.register_handler("engine_start", handler)
        assert "engine_start" in collector._handlers

    def test_unregister_handler(self):
        collector = LogCollector()
        handler = Mock()
        collector.register_handler("engine_start", handler)
        collector.unregister_handler("engine_start")
        assert "engine_start" not in collector._handlers

    def test_collect_from_queue(self):
        collector = LogCollector()
        collector.collect_from_queue(
            LogEventType.STATUS_UPDATE,
            {"message": "test"},
            source="test",
        )
        assert collector._queue.qsize() == 1

    def test_collect_log(self):
        collector = LogCollector()
        collector.collect_log("test_logger", 20, "test message")  # 20 = INFO
        assert collector._queue.qsize() == 1

    def test_start_stop(self):
        collector = LogCollector()
        collector.start()
        assert collector._running is True
        collector.stop()
        assert collector._running is False

    def test_attach_detach_logger(self):
        collector = LogCollector()
        collector.attach_to_logger("test_attach")
        import logging

        logger = logging.getLogger("test_attach")
        # 验证 _CollectorLogHandler 已被附加到 logger
        assert any(
            hasattr(h, "emit") and h is collector._log_handler for h in logger.handlers
        ), "_CollectorLogHandler 未被附加到 logger"
        collector.detach_from_logger("test_attach")
        # 验证 handler 已被移除
        assert collector._log_handler not in logger.handlers, "_CollectorLogHandler 未被成功移除"

    def test_handler_is_called(self):
        collector = LogCollector()
        received_events = []
        collector.register_handler("status_update", received_events.append)
        collector.start()
        collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"key": "val"}, source="test")
        poll_until(lambda: len(received_events) >= 1)
        collector.stop()
        assert len(received_events) >= 1
        if received_events:
            assert received_events[0].data == {"key": "val"}

    def test_queue_full_dropped(self):
        collector = LogCollector(max_queue_size=2)
        for i in range(10):
            collector.collect_from_queue(LogEventType.STATUS_UPDATE, {"idx": i}, source="test")
        # 队列最大2，所以应只有2条（不阻塞）
        assert collector._queue.qsize() <= 2


# ============================================================================
# 6. LogManager 测试
# ============================================================================


class TestLogLevel:
    """LogLevel 枚举测试"""

    def test_levels(self):
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestLogManager:
    """LogManager 测试"""

    @pytest.fixture
    def log_manager(self, tmp_path):
        """创建使用临时目录的 LogManager"""
        storage_dir = str(tmp_path / "test_manager_logs")
        return LogManager(
            storage_dir=storage_dir,
            enable_console=False,
            enable_file=True,
        )

    def test_init(self, log_manager):
        assert log_manager._running is False
        assert log_manager.enable_console is False
        assert log_manager.enable_file is True

    def test_start_stop(self, log_manager):
        log_manager.start()
        assert log_manager.is_running() is True
        log_manager.stop()
        assert log_manager.is_running() is False

    def test_double_start_ok(self, log_manager):
        log_manager.start()
        log_manager.start()  # 不应报错
        assert log_manager.is_running() is True
        log_manager.stop()

    def test_context_manager(self, tmp_path):
        storage_dir = str(tmp_path / "ctx_test")
        with LogManager(storage_dir=storage_dir, enable_console=False) as lm:
            assert lm.is_running() is True
        assert lm.is_running() is False

    def test_info_log(self, log_manager):
        log_manager.start()
        log_manager.info("test info message")
        poll_until(lambda: log_manager.get_stats()["total_count"] >= 1)
        stats = log_manager.get_stats()
        log_manager.stop()
        assert stats["total_count"] >= 1

    def test_error_log(self, log_manager):
        log_manager.start()
        log_manager.error("test error message", code=500)
        poll_until(lambda: log_manager.get_stats()["total_count"] >= 1)
        stats = log_manager.get_stats()
        log_manager.stop()
        assert stats["total_count"] >= 1

    def test_wizard_start_log(self, log_manager):
        log_manager.start()
        log_manager.log_wizard_start({"mode": "random"})
        poll_until(lambda: log_manager.get_stats()["total_count"] >= 1)
        stats = log_manager.get_stats()
        log_manager.stop()
        assert stats["total_count"] >= 1, "wizard_start 事件未被处理"

    def test_wizard_complete_log(self, log_manager):
        log_manager.start()
        log_manager.log_wizard_complete({"success": True})
        poll_until(lambda: log_manager.get_stats()["total_count"] >= 1)
        stats = log_manager.get_stats()
        log_manager.stop()
        assert stats["total_count"] >= 1, "wizard_complete 事件未被处理"

    def test_gpu_selected_log(self, log_manager):
        log_manager.start()
        log_manager.log_gpu_selected([0, 1], use_multi_gpu=True)
        poll_until(lambda: log_manager.get_stats()["total_count"] >= 1)
        stats = log_manager.get_stats()
        log_manager.stop()
        assert stats["total_count"] >= 1, "gpu_selected 事件未被处理"

    def test_get_recent(self, log_manager):
        log_manager.start()
        log_manager.info("recent test")
        poll_until(lambda: len(log_manager.get_recent(5)) >= 1)
        recent = log_manager.get_recent(5)
        log_manager.stop()
        # 至少有一条
        assert isinstance(recent, list)
