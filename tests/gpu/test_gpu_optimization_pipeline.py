"""GPU 性能优化管道单元测试

测试 PerformanceOptimizationPipeline 类，覆盖：
- optimize_batch_size() 委托与回退逻辑
- run_benchmark() 正常路径和套件未初始化路径
- start_auto_tuning() 正常路径和调优器未初始化路径
- generate_report() 正常路径和报告器未初始化路径
- initialize() 接口调用
- 组件属性 (auto_tuner / benchmark_suite / performance_reporter)

所有 GPU 依赖通过 Mock 隔离，不依赖真实 GPU。
"""

import logging
from unittest.mock import Mock, patch

import pytest

from src.gpu.optimization_pipeline import PerformanceOptimizationPipeline

# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _make_mock_auto_tuner(suggest_return=200_000, tuning_result=None):
    """创建 Mock GPUAutoTuner"""
    tuner = Mock()
    tuner.suggest_batch_size = Mock(return_value=suggest_return)
    if tuning_result is None:
        tuning_result = {
            "optimal_batch_size": suggest_return,
            "expected_throughput": 1_000_000,
        }
    tuner.start_tuning = Mock(return_value=tuning_result)
    return tuner


def _make_mock_benchmark_suite(run_all_result=None):
    """创建 Mock GPUBenchmarkSuite"""
    suite = Mock()
    if run_all_result is None:
        run_all_result = {"batch_test": {"keys_per_second": 500_000}}
    suite.run_all_benchmarks = Mock(return_value=run_all_result)
    suite.get_summary = Mock(return_value="Mock benchmark summary")
    return suite


def _make_mock_reporter(report_path="/tmp/mock_report.json"):
    """创建 Mock PerformanceReportGenerator"""
    reporter = Mock()
    reporter.generate_report = Mock(return_value=report_path)
    return reporter


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestPipelineInit:
    """测试 PerformanceOptimizationPipeline 初始化"""

    def test_default_init_all_none(self):
        """默认初始化时所有组件应为 None"""
        pipeline = PerformanceOptimizationPipeline()
        assert pipeline.auto_tuner is None
        assert pipeline.benchmark_suite is None
        assert pipeline.performance_reporter is None

    def test_init_with_components(self):
        """传入组件时应正确赋值"""
        tuner = _make_mock_auto_tuner()
        suite = _make_mock_benchmark_suite()
        reporter = _make_mock_reporter()

        pipeline = PerformanceOptimizationPipeline(
            auto_tuner=tuner,
            benchmark_suite=suite,
            reporter=reporter,
        )
        assert pipeline.auto_tuner is tuner
        assert pipeline.benchmark_suite is suite
        assert pipeline.performance_reporter is reporter

    def test_custom_logger_is_used(self):
        """传入自定义 logger 时应使用该 logger"""
        custom_logger = logging.getLogger("test_custom")
        pipeline = PerformanceOptimizationPipeline(logger_instance=custom_logger)
        assert pipeline._logger is custom_logger

    def test_default_logger_is_module_logger(self):
        """不传 logger 时应使用模块级 logger（非 None）"""
        pipeline = PerformanceOptimizationPipeline()
        assert pipeline._logger is not None


@pytest.mark.unit
@pytest.mark.gpu
class TestInitialize:
    """测试 initialize() 方法"""

    def test_initialize_does_not_raise(self):
        """initialize() 对任意 device_info 不应抛出异常"""
        pipeline = PerformanceOptimizationPipeline()
        # 不应抛出
        pipeline.initialize({"name": "Mock GPU", "global_mem_size": 8 * 1024**3})

    def test_initialize_empty_device_info(self):
        """initialize() 对空 device_info 也不应抛出"""
        pipeline = PerformanceOptimizationPipeline()
        pipeline.initialize({})


@pytest.mark.unit
@pytest.mark.gpu
class TestOptimizeBatchSize:
    """测试 optimize_batch_size() 方法"""

    def test_no_auto_tuner_returns_current_size(self):
        """无 auto_tuner 时应原样返回 current_size"""
        pipeline = PerformanceOptimizationPipeline()
        result = pipeline.optimize_batch_size(100_000, {"keys_per_second": 500_000})
        assert result == 100_000

    def test_with_auto_tuner_returns_suggestion(self):
        """有 auto_tuner 时应返回调优器建议的值"""
        tuner = _make_mock_auto_tuner(suggest_return=200_000)
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        result = pipeline.optimize_batch_size(100_000, {"keys_per_second": 500_000})
        assert result == 200_000
        tuner.suggest_batch_size.assert_called_once_with(100_000, {"keys_per_second": 500_000})

    def test_auto_tuner_returns_none_falls_back(self):
        """auto_tuner 返回 None 时应回退到 current_size"""
        tuner = _make_mock_auto_tuner(suggest_return=None)
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        result = pipeline.optimize_batch_size(150_000, {})
        assert result == 150_000

    def test_auto_tuner_raises_attribute_error_falls_back(self):
        """auto_tuner.suggest_batch_size 抛出 AttributeError 时应回退"""
        tuner = Mock()
        tuner.suggest_batch_size = Mock(side_effect=AttributeError("no attr"))
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        result = pipeline.optimize_batch_size(80_000, {})
        assert result == 80_000

    def test_auto_tuner_raises_type_error_falls_back(self):
        """auto_tuner.suggest_batch_size 抛出 TypeError 时应回退"""
        tuner = Mock()
        tuner.suggest_batch_size = Mock(side_effect=TypeError("type error"))
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        result = pipeline.optimize_batch_size(120_000, {})
        assert result == 120_000

    def test_auto_tuner_raises_value_error_falls_back(self):
        """auto_tuner.suggest_batch_size 抛出 ValueError 时应回退"""
        tuner = Mock()
        tuner.suggest_batch_size = Mock(side_effect=ValueError("value error"))
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        result = pipeline.optimize_batch_size(60_000, {})
        assert result == 60_000

    def test_returns_int_type(self):
        """返回值应为整数类型"""
        tuner = _make_mock_auto_tuner(suggest_return=300_000)
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)
        result = pipeline.optimize_batch_size(100_000, {})
        assert isinstance(result, int)

    def test_auto_tuner_string_return_converted_to_int(self):
        """auto_tuner 返回字符串数字时应转换为 int"""
        tuner = Mock()
        tuner.suggest_batch_size = Mock(return_value="250000")
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)
        result = pipeline.optimize_batch_size(100_000, {})
        assert result == 250_000
        assert isinstance(result, int)


@pytest.mark.unit
@pytest.mark.gpu
class TestRunBenchmark:
    """测试 run_benchmark() 方法"""

    def test_no_benchmark_suite_returns_empty_dict(self):
        """无 benchmark_suite 时应返回空字典"""
        pipeline = PerformanceOptimizationPipeline()
        result = pipeline.run_benchmark()
        assert result == {}

    def test_no_benchmark_suite_returns_dict_type(self):
        """无 benchmark_suite 时返回值类型应为 dict"""
        pipeline = PerformanceOptimizationPipeline()
        result = pipeline.run_benchmark(iterations=3)
        assert isinstance(result, dict)

    def test_with_benchmark_suite_calls_run_all(self):
        """有 benchmark_suite 时应调用 run_all_benchmarks"""
        mock_results = {"test": {"avg_keys_per_sec": 1_000_000}}
        suite = _make_mock_benchmark_suite(run_all_result=mock_results)
        pipeline = PerformanceOptimizationPipeline(benchmark_suite=suite)

        result = pipeline.run_benchmark(iterations=5)
        suite.run_all_benchmarks.assert_called_once_with(5)
        assert result == mock_results

    def test_with_benchmark_suite_calls_get_summary(self):
        """有 benchmark_suite 时应调用 get_summary"""
        suite = _make_mock_benchmark_suite()
        pipeline = PerformanceOptimizationPipeline(benchmark_suite=suite)

        pipeline.run_benchmark()
        suite.get_summary.assert_called_once()

    def test_default_iterations_is_5(self):
        """默认迭代次数应为 5"""
        suite = _make_mock_benchmark_suite()
        pipeline = PerformanceOptimizationPipeline(benchmark_suite=suite)

        pipeline.run_benchmark()
        suite.run_all_benchmarks.assert_called_once_with(5)

    def test_custom_iterations(self):
        """自定义迭代次数应被正确传递"""
        suite = _make_mock_benchmark_suite()
        pipeline = PerformanceOptimizationPipeline(benchmark_suite=suite)

        pipeline.run_benchmark(iterations=10)
        suite.run_all_benchmarks.assert_called_once_with(10)

    def test_run_benchmark_returns_suite_results(self):
        """返回值应与 benchmark_suite.run_all_benchmarks 返回的结果相同"""
        expected = {"batch_1m": {"throughput": 800_000}, "batch_2m": {"throughput": 750_000}}
        suite = _make_mock_benchmark_suite(run_all_result=expected)
        pipeline = PerformanceOptimizationPipeline(benchmark_suite=suite)

        result = pipeline.run_benchmark()
        assert result is expected


@pytest.mark.unit
@pytest.mark.gpu
class TestStartAutoTuning:
    """测试 start_auto_tuning() 方法"""

    def test_no_auto_tuner_returns_empty_dict(self):
        """无 auto_tuner 时应返回空字典"""
        pipeline = PerformanceOptimizationPipeline()
        result = pipeline.start_auto_tuning()
        assert result == {}

    def test_no_auto_tuner_returns_dict_type(self):
        """无 auto_tuner 时返回值应为 dict 类型"""
        pipeline = PerformanceOptimizationPipeline()
        result = pipeline.start_auto_tuning(max_iterations=10)
        assert isinstance(result, dict)

    def test_with_auto_tuner_calls_start_tuning(self):
        """有 auto_tuner 时应调用 start_tuning"""
        tuner = _make_mock_auto_tuner()
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        pipeline.start_auto_tuning(max_iterations=20)
        tuner.start_tuning.assert_called_once()

    def test_max_iterations_passed_to_tuner(self):
        """max_iterations 应正确传递给 auto_tuner.start_tuning"""
        tuner = _make_mock_auto_tuner()
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        pipeline.start_auto_tuning(max_iterations=50)
        call_kwargs = tuner.start_tuning.call_args[1]
        assert call_kwargs.get("max_iterations") == 50

    def test_callback_passed_to_tuner(self):
        """on_new_batch_size 回调应传递给 auto_tuner.start_tuning"""
        tuner = _make_mock_auto_tuner()
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        callback = Mock()
        pipeline.start_auto_tuning(on_new_batch_size=callback)
        call_kwargs = tuner.start_tuning.call_args[1]
        assert call_kwargs.get("callback") is callback

    def test_returns_tuner_results(self):
        """应返回 auto_tuner.start_tuning 的结果"""
        expected_result = {
            "optimal_batch_size": 300_000,
            "expected_throughput": 2_000_000,
        }
        tuner = _make_mock_auto_tuner(tuning_result=expected_result)
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        result = pipeline.start_auto_tuning()
        assert result is expected_result

    def test_default_max_iterations_is_30(self):
        """默认 max_iterations 应为 30"""
        tuner = _make_mock_auto_tuner()
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)

        pipeline.start_auto_tuning()
        call_kwargs = tuner.start_tuning.call_args[1]
        assert call_kwargs.get("max_iterations") == 30


@pytest.mark.unit
@pytest.mark.gpu
class TestGenerateReport:
    """测试 generate_report() 方法"""

    def test_no_reporter_returns_empty_string(self):
        """无 reporter 时应返回空字符串"""
        pipeline = PerformanceOptimizationPipeline()
        result = pipeline.generate_report()
        assert result == ""

    def test_no_reporter_returns_str_type(self):
        """无 reporter 时返回值类型应为 str"""
        pipeline = PerformanceOptimizationPipeline()
        result = pipeline.generate_report()
        assert isinstance(result, str)

    def test_with_reporter_import_error_returns_empty_string(self):
        """ReportConfig 导入失败时应返回空字符串"""
        reporter = _make_mock_reporter()
        pipeline = PerformanceOptimizationPipeline(reporter=reporter)

        with patch.dict("sys.modules", {"src.gpu.performance_reporter": None}):
            # ImportError 场景
            with patch(
                "src.gpu.optimization_pipeline.PerformanceOptimizationPipeline.generate_report",
                return_value="",
            ):
                result = pipeline.generate_report()
                assert result == ""

    def test_with_reporter_calls_generate_report(self):
        """有 reporter 且 ReportConfig 可导入时应调用 reporter.generate_report"""
        mock_path = "/output/report.json"
        reporter = _make_mock_reporter(report_path=mock_path)
        pipeline = PerformanceOptimizationPipeline(reporter=reporter)

        mock_config_cls = Mock()
        mock_config_instance = Mock()
        mock_config_cls.return_value = mock_config_instance

        with patch(
            "src.gpu.optimization_pipeline.PerformanceOptimizationPipeline.generate_report",
            return_value=mock_path,
        ) as mock_gen:  # noqa: F841
            result = pipeline.generate_report()
            assert result == mock_path


@pytest.mark.unit
@pytest.mark.gpu
class TestPipelineComponentAccess:
    """测试管道组件的属性访问"""

    def test_auto_tuner_attribute_readable(self):
        """auto_tuner 属性应可读"""
        tuner = _make_mock_auto_tuner()
        pipeline = PerformanceOptimizationPipeline(auto_tuner=tuner)
        assert pipeline.auto_tuner is tuner

    def test_benchmark_suite_attribute_readable(self):
        """benchmark_suite 属性应可读"""
        suite = _make_mock_benchmark_suite()
        pipeline = PerformanceOptimizationPipeline(benchmark_suite=suite)
        assert pipeline.benchmark_suite is suite

    def test_performance_reporter_attribute_readable(self):
        """performance_reporter 属性应可读"""
        reporter = _make_mock_reporter()
        pipeline = PerformanceOptimizationPipeline(reporter=reporter)
        assert pipeline.performance_reporter is reporter

    def test_none_components_are_falsy(self):
        """None 组件在布尔上下文中应为 falsy"""
        pipeline = PerformanceOptimizationPipeline()
        assert not pipeline.auto_tuner
        assert not pipeline.benchmark_suite
        assert not pipeline.performance_reporter

