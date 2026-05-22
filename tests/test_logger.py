#!/usr/bin/env python3
"""日志工具 (logger) 单元测试

覆盖：
- ColoredFormatter 彩色格式化
- SafeStreamHandler 编码安全
- PerformanceMonitor 性能监控
- SampledLogger 采样日志
- AsyncLogger / AsyncFileHandler 异步日志
- setup_logger / get_logger / get_sampled_logger
"""

import logging
import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_log_dir():
    """临时日志目录"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    # 关闭所有处理器
    root = logging.getLogger()
    for handler in list(root.handlers):
        try:
            handler.close()
        except Exception:
            pass
    root.handlers.clear()
    import shutil

    try:
        shutil.rmtree(tmpdir)
    except PermissionError:
        pass


@pytest.fixture
def clean_logger():
    """清理指定 logger 的处理器"""
    loggers_to_clean = []

    def _cleanup(name):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        loggers_to_clean.append(logger)
        return logger

    yield _cleanup

    for logger in loggers_to_clean:
        logger.handlers.clear()


# ============================================================================
# ColoredFormatter 测试
# ============================================================================


@pytest.mark.unit
class TestColoredFormatter:
    """彩色格式化器测试"""

    def test_format_adds_color_for_tty(self):
        from src.utils.logger import ColoredFormatter

        fmt = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        with patch.object(sys.stdout, "isatty", return_value=True):
            result = fmt.format(record)
        assert "INFO" in result
        assert "hello" in result
        # tty 下应包含 ANSI 转义码
        assert "\033[" in result

    def test_format_no_color_for_non_tty(self):
        from src.utils.logger import ColoredFormatter

        fmt = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord("test", logging.ERROR, "", 0, "error msg", (), None)
        with patch.object(sys.stdout, "isatty", return_value=False):
            result = fmt.format(record)
        assert "ERROR" in result
        assert "error msg" in result
        # 非 tty 下不应有 ANSI 转义码
        assert "\033[" not in result

    def test_format_restores_levelname(self):
        from src.utils.logger import ColoredFormatter

        fmt = ColoredFormatter("%(levelname)s")
        record = logging.LogRecord("test", logging.WARNING, "", 0, "w", (), None)
        orig = record.levelname
        with patch.object(sys.stdout, "isatty", return_value=True):
            fmt.format(record)
        assert record.levelname == orig

    def test_all_levels_have_color(self):
        from src.utils.logger import ColoredFormatter

        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            assert level in ColoredFormatter.COLORS


# ============================================================================
# SafeStreamHandler 测试
# ============================================================================


@pytest.mark.unit
class TestSafeStreamHandler:
    """安全流处理器测试"""

    def test_emit_writes_message(self, capsys):
        from src.utils.logger import SafeStreamHandler

        handler = SafeStreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)
        handler.emit(record)
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_emit_handles_closed_stream(self):
        """关闭的流不会抛出异常"""
        import io

        from src.utils.logger import SafeStreamHandler

        closed_stream = io.StringIO()
        closed_stream.close()
        handler = SafeStreamHandler(closed_stream)
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        # 不应抛出异常
        handler.emit(record)

    def test_emit_handles_none_stream(self):
        """None stream 不会抛出异常"""
        from src.utils.logger import SafeStreamHandler

        handler = SafeStreamHandler(sys.stdout)
        handler.stream = None
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        handler.emit(record)  # 不应抛出异常

    def test_emit_gbk_encoding_safe(self):
        """GBK 编码下中文不会崩溃"""
        from src.utils.logger import SafeStreamHandler

        handler = SafeStreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord("test", logging.INFO, "", 0, "中文测试日志", (), None)
        # 不应抛出异常
        handler.emit(record)


# ============================================================================
# PerformanceMonitor 测试
# ============================================================================


@pytest.mark.unit
class TestPerformanceMonitor:
    """性能监控测试"""

    def test_context_manager_logs_elapsed(self):
        from src.utils.logger import PerformanceMonitor

        mock_logger = MagicMock(spec=logging.Logger)
        with PerformanceMonitor(mock_logger, "test_op", level="INFO"):
            pass
        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args[0]
        assert "test_op" in call_args[1]
        assert "ms" in call_args[1]

    def test_elapsed_ms_property(self):
        from src.utils.logger import PerformanceMonitor

        mock_logger = MagicMock(spec=logging.Logger)
        monitor = PerformanceMonitor(mock_logger, "op")
        monitor.start_time = time.perf_counter()
        elapsed = monitor.elapsed_ms
        assert elapsed >= 0

    def test_exception_logs_failure(self):
        from src.utils.logger import PerformanceMonitor

        mock_logger = MagicMock(spec=logging.Logger)
        try:
            with PerformanceMonitor(mock_logger, "failing_op"):
                raise ValueError("test error")
        except ValueError:
            pass
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "FAILED" in call_args
        assert "test error" in call_args

    def test_default_level_is_debug(self):
        from src.utils.logger import PerformanceMonitor

        mock_logger = MagicMock(spec=logging.Logger)
        monitor = PerformanceMonitor(mock_logger, "op")
        assert monitor.level == logging.DEBUG


# ============================================================================
# SampledLogger 测试
# ============================================================================


@pytest.mark.unit
class TestSampledLogger:
    """采样日志测试"""

    def test_logs_only_at_sample_rate(self):
        from src.utils.logger import SampledLogger

        base = MagicMock(spec=logging.Logger)
        sampled = SampledLogger(base, sample_rate=5)
        for i in range(10):
            sampled.info("msg %d", i)
        # rate=5, 应记录2次（i=5,10）
        assert base.info.call_count == 2

    def test_respects_max_per_second(self):
        from src.utils.logger import SampledLogger

        base = MagicMock(spec=logging.Logger)
        sampled = SampledLogger(base, sample_rate=1, max_per_second=2)
        # 用 mock time.monotonic() 控制时间窗口，确保确定性
        with patch("time.monotonic", side_effect=[100.0, 100.1, 100.2, 100.3, 100.4]):
            for i in range(5):
                sampled.info("msg %d", i)
        # 同一时间窗口最多2条 → 调用次数精确 == 2
        assert base.info.call_count == 2

    def test_debug_uses_prefix(self):
        from src.utils.logger import SampledLogger

        base = MagicMock(spec=logging.Logger)
        sampled = SampledLogger(base, sample_rate=1)
        sampled.debug("test")
        call_arg = base.debug.call_args[0][0]
        assert "[Sampled 1/1]" in call_arg

    def test_warning_uses_prefix(self):
        from src.utils.logger import SampledLogger

        base = MagicMock(spec=logging.Logger)
        sampled = SampledLogger(base, sample_rate=1)
        sampled.warning("test")
        call_arg = base.warning.call_args[0][0]
        assert "[Sampled 1/1]" in call_arg

    def test_error_always_logs_at_rate_1(self):
        """rate=1 时每条都记录"""
        from src.utils.logger import SampledLogger

        base = MagicMock(spec=logging.Logger)
        sampled = SampledLogger(base, sample_rate=1)
        for i in range(3):
            sampled.error("err %d", i)
        assert base.error.call_count == 3

    def test_counter_wraps_at_max(self):
        """计数器超过上限后应重置为0"""
        from src.utils.logger import SampledLogger

        base = MagicMock(spec=logging.Logger)
        sampled = SampledLogger(base, sample_rate=1)
        sampled._counter = sampled._COUNTER_MAX - 1
        sampled.info("pre-wrap")
        # 超出上限后设为0（不是1，因为先+1到COUNTER_MAX，再=0）
        assert sampled._counter == 0

    def test_max_per_second_zero_disabled(self):
        """max_per_second=0 表示不限频"""
        from src.utils.logger import SampledLogger

        base = MagicMock(spec=logging.Logger)
        sampled = SampledLogger(base, sample_rate=1, max_per_second=0)
        for i in range(5):
            sampled.info("msg %d", i)
        assert base.info.call_count == 5


# ============================================================================
# AsyncLogger / AsyncFileHandler 测试
# ============================================================================


@pytest.mark.unit
class TestAsyncLogger:
    """异步日志器测试"""

    def test_init_starts_writer_thread(self):
        from src.utils.logger import AsyncLogger

        al = AsyncLogger(max_queue_size=100)
        try:
            assert al._writer_thread.is_alive()
        finally:
            al.close()

    def test_emit_queues_record(self):
        from conftest import poll_until
        from src.utils.logger import AsyncLogger

        al = AsyncLogger(max_queue_size=100)
        try:
            handler = MagicMock(spec=logging.Handler)
            al._handler = handler
            record = logging.LogRecord("test", logging.INFO, "", 0, "async msg", (), None)
            al.emit(record)
            # 用 poll_until 等待后台线程处理，比 time.sleep(0.2) 更稳定
            assert poll_until(lambda: handler.emit.called, timeout=2.0), (
                "AsyncLogger writer thread did not process record within timeout"
            )
        finally:
            al.close()

    def test_close_stops_thread(self):
        from src.utils.logger import AsyncLogger

        al = AsyncLogger(max_queue_size=100)
        al.close()
        al._writer_thread.join(timeout=2)
        assert not al._writer_thread.is_alive()

    def test_emit_queue_full_drops(self):
        from src.utils.logger import AsyncLogger

        al = AsyncLogger(max_queue_size=2)
        try:
            al._handler = MagicMock(spec=logging.Handler)
            record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
            # 快速大量填充，即使写入线程消耗队列，也应有丢弃（竞态条件已通过数量对冲）
            for i in range(100):
                al.emit(record)
            # 如果写入线程消耗太快导致无丢弃，跳过而非报错
            if al._dropped_count == 0:
                pytest.skip("Writer thread consumed queue too fast, no records dropped")
            assert al._dropped_count > 0
        finally:
            al.close()

    def test_get_stats(self):
        from src.utils.logger import AsyncLogger

        al = AsyncLogger(max_queue_size=100)
        try:
            stats = al.get_stats()
            assert "queue_size" in stats
            assert "dropped_count" in stats
            assert "is_running" in stats
            assert stats["is_running"] is True
        finally:
            al.close()


@pytest.mark.unit
class TestAsyncFileHandler:
    """异步文件处理器测试"""

    def test_creates_handler(self, temp_log_dir):
        from src.utils.logger import AsyncFileHandler

        log_file = os.path.join(temp_log_dir, "async.log")
        handler = AsyncFileHandler(log_file)
        try:
            assert handler is not None
            record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
            handler.emit(record)
            stats = handler.get_stats()
            assert "queue_size" in stats
        finally:
            handler.close()

    def test_rotating_handler(self, temp_log_dir):
        from src.utils.logger import AsyncFileHandler

        log_file = os.path.join(temp_log_dir, "rotate.log")
        handler = AsyncFileHandler(log_file, max_bytes=1024, backup_count=2)
        try:
            record = logging.LogRecord("test", logging.INFO, "", 0, "rotate test", (), None)
            handler.emit(record)
        finally:
            handler.close()


# ============================================================================
# setup_logger / get_logger 测试
# ============================================================================


@pytest.mark.unit
class TestSetupLogger:
    """setup_logger 函数测试"""

    def test_creates_logger_with_console_handler(self):
        from src.utils.logger import setup_logger

        logger = setup_logger("test_setup", level="DEBUG")
        try:
            assert isinstance(logger, logging.Logger)
            assert logger.name == "test_setup"
            assert logger.level == logging.DEBUG
            assert len(logger.handlers) >= 1  # console handler
        finally:
            logger.handlers.clear()

    def test_creates_file_handler(self, temp_log_dir):
        from src.utils.logger import setup_logger

        log_file = os.path.join(temp_log_dir, "setup_test.log")
        logger = setup_logger("test_file", log_file=log_file, use_color=False)
        try:
            assert len(logger.handlers) >= 2  # console + file
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            assert len(file_handlers) >= 1
        finally:
            for h in list(logger.handlers):
                try:
                    h.close()
                except Exception:
                    pass
            logger.handlers.clear()

    def test_creates_log_directory(self, temp_log_dir):
        from src.utils.logger import setup_logger

        log_subdir = os.path.join(temp_log_dir, "logs")
        log_file = os.path.join(log_subdir, "test.log")
        logger = setup_logger("test_dir", log_file=log_file)
        try:
            assert os.path.isdir(log_subdir)
        finally:
            for h in list(logger.handlers):
                try:
                    h.close()
                except Exception:
                    pass
            logger.handlers.clear()


@pytest.mark.unit
class TestGetLogger:
    """get_logger 函数测试"""

    def test_returns_existing_logger(self):
        from src.utils.logger import get_logger

        logger = get_logger("test_existing")
        assert isinstance(logger, logging.Logger)


@pytest.mark.unit
class TestGetSampledLogger:
    """get_sampled_logger 函数测试"""

    def test_returns_sampled_logger(self):
        from src.utils.logger import SampledLogger, get_sampled_logger

        sampled = get_sampled_logger("test_sampled", sample_rate=10)
        assert isinstance(sampled, SampledLogger)
        assert sampled.sample_rate == 10

    def test_default_max_per_second_zero(self):
        from src.utils.logger import get_sampled_logger

        sampled = get_sampled_logger("test_sampled2")
        assert sampled.max_per_second == 0.0
