"""GPU P2 优化功能单元测试

测试 P2 优先级的三个新功能：
1. 性能基准测试套件
2. 自动调优机制
3. 详细性能报告生成
"""

import json
import time
from unittest.mock import Mock

import pytest

from src.gpu.auto_tuner import GPUAutoTuner, TuningConfig, TuningPhase

# 导入被测试模块
from src.gpu.benchmark_suite import BenchmarkResult, BenchmarkType, GPUBenchmarkSuite
from src.gpu.performance_reporter import PerformanceReportGenerator, ReportConfig

pytestmark = pytest.mark.gpu


class TestGPUBenchmarkSuite:
    """测试 GPU 基准测试套件"""

    def setup_method(self):
        """设置测试环境"""
        # 创建模拟的 GPU 引擎
        self.mock_engine = Mock()
        self.mock_kernel = Mock()
        self.mock_engine._gpu_kernel = self.mock_kernel

        # 模拟设备
        self.mock_device = Mock()
        self.mock_device.device_info = {
            "name": "Test GPU",
            "vendor": "Test Vendor",
            "global_mem_size": 8 * 1024**3,
        }
        self.mock_engine._gpu_device = self.mock_device

        self.suite = GPUBenchmarkSuite(self.mock_engine)

    def test_initialization(self):
        """测试初始化"""
        assert self.suite.gpu_engine == self.mock_engine
        assert self.suite.results == []

    def test_run_all_benchmarks(self):
        """测试运行所有基准测试"""
        # 模拟 run_batch 返回（加延迟确保 benchmark 记录有效结果）
        self.mock_kernel.run_batch = Mock(side_effect=lambda *args, **kwargs: (time.sleep(0.001), [])[1])

        # 运行测试（减少迭代次数以加快速度）
        results = self.suite.run_all_benchmarks(iterations=2)

        assert isinstance(results, list)
        assert len(results) > 0

        # 验证结果类型
        for result in results:
            assert isinstance(result, BenchmarkResult)
            assert result.device_name == "Test GPU"
            assert result.vendor == "Test Vendor"

    def test_benchmark_kernel_compile(self):
        """测试内核编译基准"""
        # 模拟编译
        self.mock_kernel._compile = Mock()

        results = self.suite.benchmark_kernel_compile(iterations=2)

        assert isinstance(results, list)
        if results:
            result = results[0]
            assert result.test_type == BenchmarkType.COMPILE
            assert result.mean_ms >= 0

    def test_benchmark_batch_execution(self):
        """测试批次执行基准"""
        # 添加微小延迟确保 execution time > 0，避免被 valid_times 过滤
        self.mock_kernel.run_batch = Mock(side_effect=lambda *args, **kwargs: (time.sleep(0.001), [])[1])

        results = self.suite.benchmark_batch_execution(iterations=2)

        assert isinstance(results, list)
        assert len(results) > 0

        # 验证不同 batch_size 的测试结果
        batch_sizes = [r.parameters.get("batch_size") for r in results]
        assert 10000 in batch_sizes
        assert 50000 in batch_sizes
        assert 100000 in batch_sizes

    def test_generate_report(self):
        """测试生成报告"""
        # 创建模拟结果
        result = BenchmarkResult(
            test_name="test",
            test_type=BenchmarkType.BATCH_EXECUTION,
            device_name="Test GPU",
            vendor="Test Vendor",
            duration_ms=100.0,
            throughput=1000000.0,
            mean_ms=100.0,
            min_ms=90.0,
            max_ms=110.0,
            parameters={"batch_size": 100000},
        )
        self.suite.results = [result]

        report = self.suite.generate_report()

        assert isinstance(report, str)
        assert "GPU 性能基准测试报告" in report
        assert "Test GPU" in report


class TestGPUAutoTuner:
    """测试 GPU 自动调优器"""

    def setup_method(self):
        """设置测试环境"""
        self.mock_engine = Mock()
        self.mock_kernel = Mock()
        self.mock_engine._gpu_kernel = self.mock_kernel
        self.mock_kernel.run_batch = Mock(return_value=[])

        config = TuningConfig(exploration_iterations=2, exploration_batch_sizes=[10000, 50000, 100000])

        self.tuner = GPUAutoTuner(self.mock_engine, config)

    def test_initialization(self):
        """测试初始化"""
        assert self.tuner.gpu_engine == self.mock_engine
        assert self.tuner.phase == TuningPhase.EXPLORATION
        assert self.tuner.is_tuning is False

    def test_start_tuning(self):
        """测试开始调优"""
        optimal = self.tuner.start_tuning()

        assert isinstance(optimal, dict)
        assert "batch_size" in optimal
        assert optimal["batch_size"] in [10000, 50000, 100000]

    def test_get_optimal_config(self):
        """测试获取最优配置"""
        # 先调优
        optimal = self.tuner.start_tuning()

        # 获取配置
        config = self.tuner.get_optimal_config()

        assert config == optimal
        assert "batch_size" in config

    def test_should_re_tune(self):
        """测试是否应该重新调优"""
        # 初始状态不应该重新调优
        assert self.tuner.should_re_tune() is False

        # 设置上次调优时间为很久以前
        self.tuner.last_tuning_time = time.time() - 7200  # 2 小时前
        self.tuner.config.re_tuning_interval_sec = 3600  # 1 小时

        # 模拟性能退化
        self.tuner.best_throughput = 500000
        self.tuner.performance_history = []

        # 添加性能下降的历史记录
        from src.gpu.auto_tuner import PerformanceRecord

        for i in range(5):
            self.tuner.performance_history.append(
                PerformanceRecord(
                    batch_size=100000,
                    throughput=400000,  # 比最优低 20%
                    execution_time_ms=250,
                    timestamp=time.time(),
                )
            )

        # 现在应该重新调优
        assert self.tuner.should_re_tune() is True

    def test_monitor_performance(self):
        """测试性能监控"""
        result = self.tuner.monitor_performance()

        assert isinstance(result, dict)
        assert "status" in result

    def test_performance_history(self):
        """测试性能历史记录"""
        # 运行调优
        self.tuner.start_tuning()

        # 检查历史记录
        assert len(self.tuner.performance_history) > 0

        # 验证记录格式
        for record in self.tuner.performance_history:
            assert hasattr(record, "batch_size")
            assert hasattr(record, "throughput")
            assert hasattr(record, "timestamp")

    def test_get_tuning_report(self):
        """测试生成调优报告"""
        self.tuner.start_tuning()

        report = self.tuner.get_tuning_report()

        assert isinstance(report, str)
        assert "GPU 自动调优报告" in report

    def test_reset(self):
        """测试重置"""
        self.tuner.start_tuning()
        self.tuner.reset()

        assert self.tuner.performance_history == []
        assert self.tuner.best_config is None
        assert self.tuner.best_throughput == 0.0


class TestPerformanceReportGenerator:
    """测试性能报告生成器"""

    def setup_method(self):
        """设置测试环境"""
        self.mock_engine = Mock()
        self.mock_device = Mock()
        self.mock_device.device_info = {
            "name": "Test GPU",
            "vendor": "Test Vendor",
            "global_mem_size": 8 * 1024**3,
            "max_compute_units": 20,
        }
        self.mock_device.driver_version = "31.0.101.4500"
        self.mock_engine._gpu_device = self.mock_device

        self.mock_benchmark = Mock()
        self.mock_benchmark.results = []

        self.mock_tuner = Mock()
        self.mock_tuner.best_config = {
            "batch_size": 100000,
            "throughput": 500000,
            "avg_time_ms": 200,
        }
        self.mock_tuner.best_throughput = 500000
        self.mock_tuner.performance_history = []
        self.mock_tuner.total_tuning_cycles = 1
        self.mock_tuner.get_tuning_report = Mock(return_value="# 调优报告\n\n测试数据")

        self.generator = PerformanceReportGenerator(
            self.mock_engine, self.mock_benchmark, self.mock_tuner
        )

    def test_initialization(self):
        """测试初始化"""
        assert self.generator.gpu_engine == self.mock_engine
        assert self.generator.benchmark_suite == self.mock_benchmark
        assert self.generator.auto_tuner == self.mock_tuner

    def test_generate_markdown_report(self):
        """测试生成 Markdown 报告"""
        config = ReportConfig(
            include_device_info=True, include_benchmark_results=True, include_tuning_results=True
        )

        report = self.generator.generate_report(config)

        assert isinstance(report, str)
        assert "GPU 性能详细报告" in report
        assert "GPU 设备信息" in report

    def test_generate_json_report(self):
        """测试生成 JSON 报告"""
        config = ReportConfig(format="json")

        report = self.generator.generate_report(config)

        # 验证 JSON 格式
        data = json.loads(report)

        assert isinstance(data, dict)
        assert "metadata" in data
        assert "device_info" in data

    def test_generate_device_info_section(self):
        """测试生成设备信息章节"""
        section = self.generator._generate_device_info_section()

        assert isinstance(section, str)
        assert "GPU 设备信息" in section
        assert "Test GPU" in section

    def test_generate_recommendations(self):
        """测试生成优化建议"""
        recommendations = self.generator._generate_recommendations()

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # 应该包含 Intel 相关建议（如果是 Intel GPU）
        # 或其他通用建议

    def test_save_report(self, tmp_path):
        """测试保存报告"""
        report = "# Test Report"
        filepath = str(tmp_path / "test_report.md")

        self.generator.save_report(report, filepath)

        # 验证文件存在
        import os

        assert os.path.exists(filepath)

        # 验证内容
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
            assert content == report


class TestIntegration:
    """测试 P2 功能集成"""

    def test_full_workflow(self):
        """测试完整工作流"""
        # 创建模拟引擎
        mock_engine = Mock()
        mock_kernel = Mock()
        mock_engine._gpu_kernel = mock_kernel
        # 添加延迟确保 benchmark 能记录有效结果
        mock_kernel.run_batch = Mock(side_effect=lambda *args, **kwargs: (time.sleep(0.001), [])[1])

        mock_device = Mock()
        mock_device.device_info = {
            "name": "Integration Test GPU",
            "vendor": "Test Vendor",
            "global_mem_size": 8 * 1024**3,
        }
        mock_engine._gpu_device = mock_device

        # 1. 运行基准测试
        benchmark = GPUBenchmarkSuite(mock_engine)
        benchmark_results = benchmark.run_all_benchmarks(iterations=2)

        assert len(benchmark_results) > 0

        # 2. 自动调优
        tuner = GPUAutoTuner(mock_engine)
        optimal_config = tuner.start_tuning()

        assert "batch_size" in optimal_config

        # 3. 生成报告
        generator = PerformanceReportGenerator(mock_engine, benchmark, tuner)
        report = generator.generate_report()

        assert "GPU 性能详细报告" in report
        assert "Integration Test GPU" in report

    def test_benchmark_and_tune_integration(self):
        """测试基准测试和调优集成"""
        mock_engine = Mock()
        mock_kernel = Mock()
        mock_engine._gpu_kernel = mock_kernel
        mock_kernel.run_batch = Mock(side_effect=lambda *args, **kwargs: (time.sleep(0.001), [])[1])

        # 基准测试
        benchmark = GPUBenchmarkSuite(mock_engine)
        results = benchmark.benchmark_batch_execution(iterations=2)  # noqa: F841

        # 使用基准测试结果指导调优
        tuner = GPUAutoTuner(mock_engine)
        tuner.start_tuning()

        # 验证性能记录
        assert len(tuner.performance_history) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
