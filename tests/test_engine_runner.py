#!/usr/bin/env python3
"""引擎启动与主循环 (engine_runner) 单元测试

覆盖：
- _suppress_console_logging / _restore_console_logging 日志抑制
- _compute_range 范围计算
- _print_config_info 配置信息打印
"""

import sys
import logging
import argparse
import pytest
from unittest.mock import Mock, patch, MagicMock


# ============================================================================
# _suppress_console_logging / _restore_console_logging 测试
# ============================================================================

@pytest.mark.unit
class TestConsoleLogSuppression:
    """控制台日志抑制测试"""

    def test_suppress_raises_stream_handler_level(self):
        """抑制应将 StreamHandler 级别提升到 CRITICAL"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging
        import src.cli.engine_runner as er

        # 创建一个 StreamHandler 添加到 root logger
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            root.addHandler(handler)

            _suppress_console_logging()
            assert handler.level == logging.CRITICAL
            # _suppressed_handlers 应包含被抑制的处理器
            assert len(er._suppressed_handlers) >= 1
        finally:
            _restore_console_logging()
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_restore_recovers_original_level(self):
        """恢复应还原原始日志级别"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging

        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            root.addHandler(handler)

            _suppress_console_logging()
            _restore_console_logging()

            assert handler.level == logging.INFO
            from src.cli.engine_runner import _suppressed_handlers
            assert len(_suppressed_handlers) == 0
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_suppress_skips_file_handlers(self):
        """抑制应跳过 FileHandler"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging
        from logging import FileHandler

        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            # FileHandler 不应被抑制
            fh = FileHandler("nul")
            fh.setLevel(logging.DEBUG)
            root.addHandler(fh)

            _suppress_console_logging()
            # FileHandler 级别不应改变
            assert fh.level == logging.DEBUG
        finally:
            _restore_console_logging()
            fh.close()
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_double_suppress_is_safe(self):
        """重复抑制应安全"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging

        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            root.addHandler(handler)

            _suppress_console_logging()
            _suppress_console_logging()  # 重复调用

            # 应不崩溃
            assert handler.level == logging.CRITICAL
        finally:
            _restore_console_logging()
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)


# ============================================================================
# _compute_range 测试
# ============================================================================

@pytest.mark.unit
class TestComputeRange:
    """范围计算测试"""

    def test_range_mode_with_both_keys(self):
        from src.cli.engine_runner import _compute_range
        args = Mock()
        args.mode = "range"
        args.start = "1"
        args.end = "FF"
        start_val, end_val, total = _compute_range(args)
        assert start_val == 1
        assert end_val == 255
        assert total == 255

    def test_brute_force_mode_no_end(self):
        from src.cli.engine_runner import _compute_range
        args = Mock()
        args.mode = "brute_force"
        args.start = "A"
        args.end = None
        start_val, end_val, total = _compute_range(args)
        assert start_val == 10
        assert end_val is None
        assert total is None

    def test_random_mode_no_range(self):
        from src.cli.engine_runner import _compute_range
        args = Mock()
        args.mode = "random"
        args.start = None
        args.end = None
        start_val, end_val, total = _compute_range(args)
        assert start_val is None
        assert end_val is None
        assert total is None

    def test_range_mode_no_start(self):
        from src.cli.engine_runner import _compute_range
        args = Mock()
        args.mode = "range"
        args.start = None
        args.end = "FF"
        start_val, end_val, total = _compute_range(args)
        assert start_val is None
        assert end_val == 255
        assert total is None  # 没有 start 无法计算 total

    def test_large_hex_values(self):
        from src.cli.engine_runner import _compute_range
        args = Mock()
        args.mode = "range"
        args.start = "FFFFFFFF"
        args.end = "1FFFFFFFF"
        start_val, end_val, total = _compute_range(args)
        assert start_val == 0xFFFFFFFF
        assert end_val == 0x1FFFFFFFF
        assert total == 0x1FFFFFFFF - 0xFFFFFFFF + 1


# ============================================================================
# _print_config_info 测试
# ============================================================================

@pytest.mark.unit
class TestPrintConfigInfo:
    """配置信息打印测试"""

    def test_cpu_mode_output(self):
        from src.cli.engine_runner import _print_config_info
        args = Mock()
        args.mode = "random"
        args.multi_gpu = False
        args.use_gpu = False
        args.checkpoint = True
        args.dedup = False
        args.duration = 0
        args.workers = 4
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False

        with patch('src.cli.engine_runner.CLIOutput') as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1", "addr2"}, None, None, None)
            # startup_panel 应被调用
            mock_output.startup_panel.assert_called_once()

    def test_gpu_mode_output(self):
        from src.cli.engine_runner import _print_config_info
        args = Mock()
        args.mode = "random"
        args.multi_gpu = False
        args.use_gpu = True
        args.checkpoint = True
        args.dedup = True
        args.duration = 3600
        args.gpu_device = 0
        args.gpu_batch_size = 1000000

        with patch('src.cli.engine_runner.CLIOutput') as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1"}, None, None, None)
            mock_output.startup_panel.assert_called_once()
            # 验证 panel 内容包含 GPU
            call_args = mock_output.startup_panel.call_args[0][0]
            assert any("GPU" in str(v) for v in call_args.values())

    def test_multi_gpu_mode_output(self):
        from src.cli.engine_runner import _print_config_info
        args = Mock()
        args.mode = "range"
        args.multi_gpu = True
        args.use_gpu = False
        args.checkpoint = False
        args.dedup = False
        args.duration = 7200
        args.gpu_indices = "0 1"
        args.gpu_count = 2

        with patch('src.cli.engine_runner.CLIOutput') as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1"}, 1, 255, 255)
            mock_output.startup_panel.assert_called_once()

    def test_range_mode_config(self):
        from src.cli.engine_runner import _print_config_info
        args = Mock()
        args.mode = "range"
        args.multi_gpu = False
        args.use_gpu = False
        args.checkpoint = True
        args.dedup = True
        args.duration = 0
        args.workers = 8
        args.no_optimize = True
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False

        with patch('src.cli.engine_runner.CLIOutput') as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1"}, 0, 100, 101)
            mock_output.startup_panel.assert_called_once()
            # 验证 panel 包含范围信息
            call_args = mock_output.startup_panel.call_args[0][0]
            panel_text = str(call_args)
            assert "101" in panel_text
