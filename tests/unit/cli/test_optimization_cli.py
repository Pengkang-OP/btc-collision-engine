"""optimization_cli.py 单元测试。.

覆盖范围：
- OptimizationCLI.add_arguments: 参数注册
- OptimizationCLI.auto_tune: 自动调优逻辑
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from src.cli.optimization_cli import OptimizationCLI

# ============================================================================
# OptimizationCLI.add_arguments
# ============================================================================


class TestOptimizationCLIAddArguments:
    """参数注册测试。."""

    def test_add_arguments_registers_auto_tune(self):
        """--auto-tune 参数被正确注册。."""
        parser = argparse.ArgumentParser()
        OptimizationCLI.add_arguments(parser)

        args = parser.parse_args(["--auto-tune"])
        assert args.auto_tune is True

    def test_add_arguments_registers_batch_size(self):
        """--batch-size 参数被正确注册并包含默认值。."""
        parser = argparse.ArgumentParser()
        OptimizationCLI.add_arguments(parser)

        args = parser.parse_args([])
        assert args.batch_size == 100000

    def test_add_arguments_batch_size_custom(self):
        """--batch-size 自定义值被正确解析。."""
        parser = argparse.ArgumentParser()
        OptimizationCLI.add_arguments(parser)

        args = parser.parse_args(["--batch-size", "50000"])
        assert args.batch_size == 50000

    def test_both_arguments_simultaneously(self):
        """两个参数同时指定。."""
        parser = argparse.ArgumentParser()
        OptimizationCLI.add_arguments(parser)

        args = parser.parse_args(["--auto-tune", "--batch-size", "250000"])
        assert args.auto_tune is True
        assert args.batch_size == 250000


# ============================================================================
# OptimizationCLI.auto_tune
# ============================================================================


class TestOptimizationCLIAutoTune:
    """自动调优测试。."""

    def test_auto_tune_returns_recommendations(self):
        """auto_tune 返回调优建议字典。."""
        args = MagicMock()
        args.workers = None  # 未指定
        args.batch_size = 100000

        result = OptimizationCLI.auto_tune(args)

        assert isinstance(result, dict)
        assert "batch_size" in result
        assert result["batch_size"] >= 100000

    def test_auto_tune_respects_explicit_workers(self):
        """如果已指定 workers，不在建议中覆盖。."""
        args = MagicMock()
        args.workers = 8  # 用户显式指定
        args.batch_size = 100000

        result = OptimizationCLI.auto_tune(args)

        assert "workers" not in result
        assert "batch_size" in result

    def test_auto_tune_sets_workers_when_not_specified(self):
        """未指定 workers 时自动推荐。."""
        args = MagicMock()
        args.workers = None
        args.batch_size = 50000

        result = OptimizationCLI.auto_tune(args)

        assert "workers" in result
        assert result["workers"] >= 2

    @patch("os.cpu_count", return_value=16)
    def test_auto_tune_scales_with_cpu_cores(self, mock_cpu):
        """batch_size 随 CPU 核心数缩放。."""
        args = MagicMock()
        args.workers = 4  # 已指定，不覆盖
        args.batch_size = 100000

        result = OptimizationCLI.auto_tune(args)

        # 16 核心 / 4 = 4x 缩放
        assert result["batch_size"] == 400000

    @patch("os.cpu_count", return_value=2)
    def test_auto_tune_minimum_cpu_cores(self, mock_cpu):
        """低核心数时至少 1x 缩放。."""
        args = MagicMock()
        args.workers = 4
        args.batch_size = 50000

        result = OptimizationCLI.auto_tune(args)

        # 2 核心 / 4 = 0.5, max(1, 0) = 1x
        assert result["batch_size"] == 50000

    @patch("os.cpu_count", return_value=None)
    def test_auto_tune_cpu_count_none(self, mock_cpu):
        """cpu_count 返回 None 时使用默认值 4。."""
        args = MagicMock()
        args.workers = None
        args.batch_size = 100000

        result = OptimizationCLI.auto_tune(args)

        # 默认 4 核心: workers = max(2, 2) = 2
        assert result["workers"] == 2
        assert result["batch_size"] == 100000  # 4/4 = 1x


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
