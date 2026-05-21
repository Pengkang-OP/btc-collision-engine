"""GPU 性能报告生成器 (performance_reporter.py) 全覆盖测试

覆盖: ReportConfig, PerformanceReportGenerator 全部方法

注意: 绕过 src.gpu.__init__ 避免 kernel_impl → numpy 循环导入导致覆盖率失败
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# ---- 绕过 src.gpu.__init__ 导入链 (避免 numpy/pyopencl 重复加载) ----
# __init__ → context → kernel_impl → (numpy, pyopencl) 链
# 在 context 和 kernel_impl 的 sys.modules 中预置 mock，阻止真实导入
_mock_kernel_impl = MagicMock()
_mock_kernel_impl.compile_kernel_with_retry = MagicMock()
sys.modules["src.gpu.kernel_impl"] = _mock_kernel_impl

_mock_context = MagicMock()
_mock_context.GPUContext = MagicMock()
sys.modules["src.gpu.context"] = _mock_context

from src.gpu.performance_reporter import (  # noqa: E402
    PerformanceReportGenerator,
    ReportConfig,
)

# ===========================================================================
# Mock 工具函数
# ===========================================================================


def _make_mock_engine(device_info=None):
    """创建模拟 GPU 引擎"""
    engine = MagicMock()
    if device_info:
        device = MagicMock()
        device.device_info = device_info
        # 避免 getattr 返回 MagicMock: 显式设置属性为非 mock 值
        device.driver_version = device_info.get("driver_version", "Unknown")
        engine._gpu_device = device
    else:
        engine._gpu_device = None
    return engine


def _make_mock_benchmark(results=None):
    """创建模拟基准测试套件"""
    bm = MagicMock()
    bm.results = results or []
    bm.generate_report.return_value = "Benchmark Report Content"
    return bm


def _make_mock_autotuner(
    best_config=None,
    best_throughput=0,
    total_tuning_cycles=0,
    performance_history=None,
    tuning_report="Tuning Report Content",
):
    """创建模拟自动调优器"""
    tuner = MagicMock()
    tuner.best_config = best_config or {}
    tuner.best_throughput = best_throughput
    tuner.total_tuning_cycles = total_tuning_cycles
    tuner.performance_history = performance_history or []
    tuner.get_tuning_report.return_value = tuning_report
    return tuner


def _make_mock_history_record(
    timestamp=1234567890.0,
    batch_size=65536,
    throughput=500000.0,
    execution_time_ms=120.0,
):
    """创建模拟历史性能记录"""
    record = MagicMock()
    record.timestamp = timestamp
    record.batch_size = batch_size
    record.throughput = throughput
    record.execution_time_ms = execution_time_ms
    return record


# ===========================================================================
# Group 1: ReportConfig 测试
# ===========================================================================


class TestReportConfig:
    """测试 ReportConfig dataclass"""

    def test_default_values(self):
        """测试默认值"""
        config = ReportConfig()
        assert config.include_device_info is True
        assert config.include_benchmark_results is True
        assert config.include_tuning_results is True
        assert config.include_history is True
        assert config.include_recommendations is True
        assert config.include_comparison is False
        assert config.format == "markdown"
        assert config.output_dir == "./logs"

    def test_custom_values(self):
        """测试自定义配置"""
        config = ReportConfig(
            include_device_info=False,
            include_benchmark_results=False,
            include_comparison=True,
            format="json",
            output_dir="/custom/path",
        )
        assert config.include_device_info is False
        assert config.include_benchmark_results is False
        assert config.include_comparison is True
        assert config.format == "json"
        assert config.output_dir == "/custom/path"


# ===========================================================================
# Group 2: __init__ 测试
# ===========================================================================


class TestInit:
    """测试 PerformanceReportGenerator 初始化"""

    def test_init_with_engine_only(self):
        """仅提供 engine 初始化"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        assert gen.gpu_engine is engine
        assert gen.benchmark_suite is None
        assert gen.auto_tuner is None

    def test_init_with_all_deps(self):
        """提供所有依赖初始化"""
        engine = _make_mock_engine()
        bm = _make_mock_benchmark()
        tuner = _make_mock_autotuner()
        gen = PerformanceReportGenerator(engine, benchmark_suite=bm, auto_tuner=tuner)
        assert gen.gpu_engine is engine
        assert gen.benchmark_suite is bm
        assert gen.auto_tuner is tuner

    def test_init_logs_info(self):
        """初始化时记录 info 日志"""
        engine = _make_mock_engine()
        with patch("src.gpu.performance_reporter.logger") as mock_logger:
            PerformanceReportGenerator(engine)
            mock_logger.info.assert_called_once()


# ===========================================================================
# Group 3: generate_report 分发测试
# ===========================================================================


class TestGenerateReport:
    """测试 generate_report 格式分发"""

    def test_markdown_format_default(self):
        """默认生成 Markdown 报告"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        with patch.object(gen, "_generate_markdown_report", return_value="md_report") as mock_md:
            result = gen.generate_report()
            mock_md.assert_called_once()
            assert result == "md_report"

    def test_markdown_format_explicit(self):
        """显式指定 Markdown 格式"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        config = ReportConfig(format="markdown")
        with patch.object(gen, "_generate_markdown_report", return_value="md_report") as mock_md:
            result = gen.generate_report(config)
            mock_md.assert_called_once_with(config)
            assert result == "md_report"

    def test_json_format(self):
        """生成 JSON 报告"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        config = ReportConfig(format="json")
        with patch.object(gen, "_generate_json_report", return_value='{"key":"val"}') as mock_json:
            result = gen.generate_report(config)
            mock_json.assert_called_once_with(config)
            assert result == '{"key":"val"}'

    def test_invalid_format_raises_error(self):
        """不支持的格式抛出 ValueError"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        config = ReportConfig(format="html")
        with pytest.raises(ValueError, match="不支持的报告格式"):
            gen.generate_report(config)

    def test_none_config_uses_default(self):
        """config=None 时使用默认配置"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        with patch.object(gen, "_generate_markdown_report", return_value="report") as mock_md:
            gen.generate_report(None)
            args_config = mock_md.call_args[0][0]
            assert isinstance(args_config, ReportConfig)
            assert args_config.format == "markdown"


# ===========================================================================
# Group 4: _generate_markdown_report 测试
# ===========================================================================


class TestGenerateMarkdownReport:
    """测试 Markdown 报告生成"""

    def setup_method(self):
        self.engine = _make_mock_engine({"name": "Test GPU", "vendor": "NVIDIA"})
        self.gen = PerformanceReportGenerator(self.engine)

    def test_report_contains_header_and_footer(self):
        """报告包含标题和页脚"""
        with patch("src.gpu.performance_reporter.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 3, 12, 0, 0)
            report = self.gen._generate_markdown_report(ReportConfig())
        assert "# GPU 性能详细报告" in report
        assert "BTC Collision Engine 自动生成" in report
        assert "生成时间" in report

    def test_all_sections_included_by_default(self):
        """默认配置包含所有章节"""
        report = self.gen._generate_markdown_report(ReportConfig())
        assert "GPU 设备信息" in report
        assert "历史性能趋势" in report
        assert "优化建议" in report
        # benchmark 和 tuning 需要对应的 suite/tuner，否则显示暂无数据
        assert "暂无基准测试数据" not in report  # benchmark_suite is None, section skipped

    def test_sections_disabled_via_config(self):
        """通过配置禁用章节"""
        config = ReportConfig(
            include_device_info=False,
            include_history=False,
            include_recommendations=False,
        )
        report = self.gen._generate_markdown_report(config)
        assert "GPU 设备信息" not in report
        assert "历史性能趋势" not in report
        assert "优化建议" not in report

    def test_benchmark_section_with_suite(self):
        """有 benchmark_suite 时包含基准测试章节"""
        bm = _make_mock_benchmark()
        gen = PerformanceReportGenerator(self.engine, benchmark_suite=bm)
        report = gen._generate_markdown_report(ReportConfig())
        assert "基准测试结果" in report

    def test_tuning_section_with_tuner(self):
        """有 auto_tuner 时包含调优章节"""
        tuner = _make_mock_autotuner()
        gen = PerformanceReportGenerator(self.engine, auto_tuner=tuner)
        report = gen._generate_markdown_report(ReportConfig())
        assert "自动调优结果" in report

    def test_comparison_section_when_enabled(self):
        """启用 include_comparison 时包含对比章节"""
        config = ReportConfig(include_comparison=True)
        report = self.gen._generate_markdown_report(config)
        assert "性能对比" in report

    def test_comparison_section_when_disabled(self):
        """禁用 include_comparison 时不含对比章节"""
        report = self.gen._generate_markdown_report(ReportConfig(include_comparison=False))
        assert "性能对比" not in report


# ===========================================================================
# Group 5: _generate_device_info_section 测试
# ===========================================================================


class TestDeviceInfoSection:
    """测试设备信息章节"""

    def test_with_device_info(self):
        """有设备信息时生成表格"""
        engine = _make_mock_engine(
            {
                "name": "NVIDIA RTX 3080",
                "vendor": "NVIDIA Corporation",
                "platform": "OpenCL",
                "global_mem_size": 10 * 1024**3,
                "max_compute_units": 68,
                "driver_version": "535.129.03",
            }
        )
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_device_info_section()
        assert "GPU 设备信息" in section
        assert "NVIDIA RTX 3080" in section
        assert "NVIDIA Corporation" in section
        assert "10.0 GB" in section
        assert "68" in section

    def test_without_device_info(self):
        """无设备信息时返回空表格"""
        engine = _make_mock_engine(None)
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_device_info_section()
        assert "GPU 设备信息" in section
        # 设备信息为空字典，表格只有表头
        lines = section.strip().split("\n")
        assert len(lines) == 4  # header + separator + no data rows + empty

    def test_intel_device_opencl_version(self):
        """Intel 设备 OpenCL 版本为 3.0"""
        engine = _make_mock_engine(
            {
                "name": "Intel Arc A770",
                "vendor": "Intel Corporation",
                "platform": "OpenCL",
                "global_mem_size": 16 * 1024**3,
                "max_compute_units": 512,
            }
        )
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_device_info_section()
        assert "3.0" in section  # Intel 硬编码 OpenCL 3.0


# ===========================================================================
# Group 6: _generate_benchmark_section 测试
# ===========================================================================


class TestBenchmarkSection:
    """测试基准测试章节"""

    def test_with_results(self):
        """有基准测试结果"""
        engine = _make_mock_engine()
        bm = _make_mock_benchmark(results=[MagicMock()])
        gen = PerformanceReportGenerator(engine, benchmark_suite=bm)
        section = gen._generate_benchmark_section()
        assert "基准测试结果" in section
        assert "Benchmark Report Content" in section

    def test_without_suite(self):
        """无 benchmark_suite 时跳过"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_benchmark_section()
        assert "暂无基准测试数据" in section

    def test_with_suite_no_results(self):
        """有 suite 但无 results"""
        engine = _make_mock_engine()
        bm = MagicMock()
        bm.results = []
        gen = PerformanceReportGenerator(engine, benchmark_suite=bm)
        section = gen._generate_benchmark_section()
        assert "暂无基准测试数据" in section

    def test_with_suite_no_results_attr(self):
        """suite 无 results 属性"""
        engine = _make_mock_engine()
        bm = MagicMock(spec=[])
        gen = PerformanceReportGenerator(engine, benchmark_suite=bm)
        section = gen._generate_benchmark_section()
        assert "暂无基准测试数据" in section


# ===========================================================================
# Group 7: _generate_tuning_section 测试
# ===========================================================================


class TestTuningSection:
    """测试自动调优章节"""

    def test_with_tuner(self):
        """有 auto_tuner 时显示调优报告"""
        engine = _make_mock_engine()
        tuner = _make_mock_autotuner(tuning_report="Custom Tuning Report")
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        section = gen._generate_tuning_section()
        assert "自动调优结果" in section
        assert "Custom Tuning Report" in section

    def test_without_tuner(self):
        """无 auto_tuner 时显示暂无数据"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_tuning_section()
        assert "暂无调优数据" in section


# ===========================================================================
# Group 8: _generate_history_section 测试
# ===========================================================================


class TestHistorySection:
    """测试历史性能章节"""

    def test_with_history(self):
        """有历史记录时生成表格"""
        engine = _make_mock_engine()
        record = _make_mock_history_record()
        tuner = _make_mock_autotuner(performance_history=[record])
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        section = gen._generate_history_section()
        assert "历史性能趋势" in section
        assert "65,536" in section  # 千分位格式化
        assert "500,000" in section

    def test_with_multiple_records_shows_last_20(self):
        """多条记录时仅显示最近 20 条"""
        engine = _make_mock_engine()
        records = [
            _make_mock_history_record(timestamp=float(i), batch_size=100000 + i * 10000)
            for i in range(30)
        ]
        tuner = _make_mock_autotuner(performance_history=records)
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        section = gen._generate_history_section()
        # record[29] batch_size=390,000 → "390,000" 应该出现
        assert "390,000" in section
        # record[9] batch_size=190,000 → index 9 不在最近20条 (最近20条是 10-29)
        assert "190,000" not in section

    def test_without_tuner(self):
        """无 auto_tuner"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_history_section()
        assert "暂无历史数据" in section

    def test_tuner_without_history(self):
        """有 tuner 但无 performance_history"""
        engine = _make_mock_engine()
        tuner = MagicMock()
        tuner.performance_history = []
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        section = gen._generate_history_section()
        assert "暂无历史数据" in section


# ===========================================================================
# Group 9: _generate_recommendations_section 测试
# ===========================================================================


class TestRecommendationsSection:
    """测试优化建议章节"""

    def test_with_recommendations(self):
        """有建议时列出"""
        engine = _make_mock_engine(
            {"name": "Intel GPU", "vendor": "Intel", "global_mem_size": 8 * 1024**3}
        )
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_recommendations_section()
        assert "优化建议" in section
        assert "Intel Arc" in section  # Intel 特定建议

    def test_without_recommendations(self):
        """无建议时显示已优化"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        with patch.object(gen, "_generate_recommendations", return_value=[]):
            section = gen._generate_recommendations_section()
            assert "暂无额外建议" in section


# ===========================================================================
# Group 10: _generate_comparison_section 测试
# ===========================================================================


class TestComparisonSection:
    """测试对比分析章节"""

    def test_comparison_with_current_device(self):
        """包含当前设备与参考 GPU 对比"""
        engine = _make_mock_engine(
            {
                "name": "NVIDIA RTX 3080",
                "vendor": "NVIDIA",
                "platform": "OpenCL",
                "global_mem_size": 10 * 1024**3,
            }
        )
        tuner = _make_mock_autotuner(
            best_config={"throughput": 600000, "batch_size": 2097152},
            best_throughput=600000,
        )
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        section = gen._generate_comparison_section()
        assert "性能对比" in section
        assert "RTX 3060" in section
        assert "RTX 3080" in section
        assert "RX 6600" in section
        assert "Arc A750" in section
        assert "Arc A770" in section
        assert "← 当前" in section  # 设备名称匹配，标记当前设备

    def test_comparison_without_tuner(self):
        """无 tuner 时 throughput 为 0"""
        engine = _make_mock_engine(
            {
                "name": "Test GPU",
                "vendor": "Unknown",
                "platform": "OpenCL",
                "global_mem_size": 4 * 1024**3,
            }
        )
        gen = PerformanceReportGenerator(engine)
        section = gen._generate_comparison_section()
        assert "性能对比" in section
        # throughput 为 0，相对性能应为 0.0%
        assert "0.0%" in section


# ===========================================================================
# Group 11: _generate_json_report 测试
# ===========================================================================


class TestJSONReport:
    """测试 JSON 格式报告"""

    def setup_method(self):
        self.engine = _make_mock_engine(
            {"name": "Test GPU", "vendor": "NVIDIA", "global_mem_size": 8 * 1024**3}
        )
        self.gen = PerformanceReportGenerator(self.engine)

    def test_basic_json_structure(self):
        """基本 JSON 结构"""
        with patch("src.gpu.performance_reporter.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 3, 12, 0, 0)
            report = self.gen._generate_json_report(ReportConfig(format="json"))
        data = json.loads(report)
        assert "metadata" in data
        assert data["metadata"]["generator"] == "BTC Collision Engine Performance Reporter"
        assert data["metadata"]["version"] == "1.0"
        assert "device_info" in data
        assert data["device_info"]["设备名称"] == "Test GPU"

    def test_json_with_benchmark(self):
        """JSON 包含基准测试结果"""
        bm = _make_mock_benchmark()

        class MockResult:
            test_name = "throughput_test"
            test_type = MagicMock(value="THROUGHPUT")
            throughput = 500000.0
            duration_ms = 120.0
            parameters = {"batch_size": 65536}

        bm.results = [MockResult()]
        gen = PerformanceReportGenerator(self.engine, benchmark_suite=bm)
        report = gen._generate_json_report(ReportConfig(format="json"))
        data = json.loads(report)
        assert data["benchmark_results"] is not None
        assert len(data["benchmark_results"]) == 1
        assert data["benchmark_results"][0]["test_name"] == "throughput_test"
        assert data["benchmark_results"][0]["throughput"] == 500000.0

    def test_json_with_tuning(self):
        """JSON 包含调优结果"""
        tuner = _make_mock_autotuner(
            best_config={"batch_size": 131072},
            best_throughput=700000.0,
            total_tuning_cycles=5,
        )
        gen = PerformanceReportGenerator(self.engine, auto_tuner=tuner)
        report = gen._generate_json_report(ReportConfig(format="json"))
        data = json.loads(report)
        assert data["tuning_results"] is not None
        assert data["tuning_results"]["best_config"] == {"batch_size": 131072}
        assert data["tuning_results"]["best_throughput"] == 700000.0
        assert data["tuning_results"]["tuning_cycles"] == 5

    def test_json_with_history(self):
        """JSON 包含历史数据"""
        record = _make_mock_history_record()
        tuner = _make_mock_autotuner(performance_history=[record])
        gen = PerformanceReportGenerator(self.engine, auto_tuner=tuner)
        report = gen._generate_json_report(ReportConfig(format="json"))
        data = json.loads(report)
        assert data["performance_history"] is not None
        assert len(data["performance_history"]) == 1
        assert data["performance_history"][0]["batch_size"] == 65536

    def test_json_disabled_sections_are_none(self):
        """禁用章节时对应字段为 None"""
        config = ReportConfig(
            format="json",
            include_device_info=False,
            include_benchmark_results=False,
            include_tuning_results=False,
            include_history=False,
            include_recommendations=False,
        )
        report = self.gen._generate_json_report(config)
        data = json.loads(report)
        assert data["device_info"] is None
        assert data["benchmark_results"] is None
        assert data["tuning_results"] is None
        assert data["performance_history"] is None
        assert data["recommendations"] is None

    def test_json_history_capped_at_50(self):
        """JSON 历史数据限制最近 50 条"""
        records = [_make_mock_history_record(timestamp=float(i)) for i in range(60)]
        tuner = _make_mock_autotuner(performance_history=records)
        gen = PerformanceReportGenerator(self.engine, auto_tuner=tuner)
        report = gen._generate_json_report(ReportConfig(format="json"))
        data = json.loads(report)
        assert len(data["performance_history"]) == 50


# ===========================================================================
# Group 12: save_report 测试
# ===========================================================================


class TestSaveReport:
    """测试 save_report 方法"""

    def test_save_to_existing_dir(self):
        """保存到已存在的目录"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.md")
            gen.save_report("# Test Report", filepath)
            assert os.path.exists(filepath)
            with open(filepath, encoding="utf-8") as f:
                assert f.read() == "# Test Report"

    def test_save_creates_parent_dir(self):
        """自动创建不存在的父目录"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "sub", "nested", "report.md")
            gen.save_report("content", filepath)
            assert os.path.exists(filepath)

    def test_save_no_parent_dir(self):
        """文件路径无父目录（当前目录）"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                gen.save_report("content", "report_no_dir.md")
                assert os.path.exists(os.path.join(tmpdir, "report_no_dir.md"))
            finally:
                os.chdir(orig_cwd)

    def test_save_logs_info(self):
        """保存成功后记录日志"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.md")
            with patch("src.gpu.performance_reporter.logger") as mock_logger:
                gen.save_report("test", filepath)
                mock_logger.info.assert_called_once()
                assert "report.md" in mock_logger.info.call_args[0][0]


# ===========================================================================
# Group 13: _get_device_info 测试
# ===========================================================================


class TestGetDeviceInfo:
    """测试 _get_device_info"""

    def test_with_device(self):
        """有 GPU 设备时返回完整信息"""
        engine = _make_mock_engine(
            {
                "name": "RTX 3080",
                "vendor": "NVIDIA",
                "platform": "CUDA",
                "global_mem_size": 10 * 1024**3,
                "max_compute_units": 68,
                "driver_version": "535.129.03",
            }
        )
        gen = PerformanceReportGenerator(engine)
        info = gen._get_device_info()
        assert info["设备名称"] == "RTX 3080"
        assert info["厂商"] == "NVIDIA"
        assert "10.0 GB" in info["全局显存"]

    def test_without_device(self):
        """无 GPU 设备时返回空字典"""
        engine = _make_mock_engine(None)
        gen = PerformanceReportGenerator(engine)
        assert gen._get_device_info() == {}

    def test_device_without_device_info_keys(self):
        """device_info 缺少部分字段"""
        engine = _make_mock_engine({"name": "Basic GPU"})
        gen = PerformanceReportGenerator(engine)
        info = gen._get_device_info()
        assert info["设备名称"] == "Basic GPU"
        assert info["厂商"] == "Unknown"
        assert info["平台"] == "Unknown"


# ===========================================================================
# Group 14: _get_current_performance 测试
# ===========================================================================


class TestGetCurrentPerformance:
    """测试 _get_current_performance"""

    def test_with_tuner_best_config(self):
        """有调优器且有 best_config"""
        engine = _make_mock_engine()
        tuner = _make_mock_autotuner(best_config={"throughput": 500000, "batch_size": 131072})
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        perf = gen._get_current_performance()
        assert perf["throughput"] == 500000
        assert perf["batch_size"] == 131072

    def test_without_tuner(self):
        """无调优器"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        perf = gen._get_current_performance()
        assert perf["throughput"] == 0
        assert perf["batch_size"] == 0

    def test_tuner_without_best_config(self):
        """调优器无 best_config"""
        engine = _make_mock_engine()
        tuner = MagicMock()
        tuner.best_config = None
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        perf = gen._get_current_performance()
        assert perf["throughput"] == 0
        assert perf["batch_size"] == 0


# ===========================================================================
# Group 15: _generate_recommendations 测试
# ===========================================================================


class TestGenerateRecommendations:
    """测试 _generate_recommendations"""

    def test_intel_vendor_recommendations(self):
        """Intel 厂商包含特定建议"""
        engine = _make_mock_engine(
            {
                "name": "Intel Arc A770",
                "vendor": "Intel Corporation",
                "global_mem_size": 16 * 1024**3,
            }
        )
        tuner = _make_mock_autotuner(best_config={"throughput": 500000, "batch_size": 524288})
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        recs = gen._generate_recommendations()
        assert any("uint32 workaround" in r for r in recs)
        assert any("保守的 batch_size" in r for r in recs)
        assert any("驱动版本" in r for r in recs)

    def test_low_throughput_recommendation(self):
        """低吞吐量建议运行自动调优"""
        engine = _make_mock_engine(
            {
                "name": "GPU",
                "vendor": "Unknown",
                "global_mem_size": 8 * 1024**3,  # int, not str
            }
        )
        tuner = _make_mock_autotuner(best_config={"throughput": 50000, "batch_size": 32768})
        gen = PerformanceReportGenerator(engine, auto_tuner=tuner)
        recs = gen._generate_recommendations()
        assert any("吞吐量较低" in r for r in recs)

    def test_high_memory_recommendation(self):
        """大显存 (≥16GB) 建议"""
        engine = _make_mock_engine(
            {
                "name": "High Mem GPU",
                "vendor": "NVIDIA",
                "global_mem_size": 24 * 1024**3,
            }
        )
        gen = PerformanceReportGenerator(engine)
        recs = gen._generate_recommendations()
        assert any("显存充足" in r for r in recs)

    def test_low_memory_recommendation(self):
        """小显存 (<4GB) 建议"""
        engine = _make_mock_engine(
            {
                "name": "Low Mem GPU",
                "vendor": "AMD",
                "global_mem_size": 2 * 1024**3,
            }
        )
        gen = PerformanceReportGenerator(engine)
        recs = gen._generate_recommendations()
        assert any("显存较小" in r for r in recs)

    def test_always_includes_generic_recommendations(self):
        """始终包含通用建议"""
        engine = _make_mock_engine(
            {
                "name": "GPU",
                "vendor": "NVIDIA",
                "global_mem_size": 8 * 1024**3,  # int, not str
            }
        )
        gen = PerformanceReportGenerator(engine)
        recs = gen._generate_recommendations()
        assert any("定期运行基准测试" in r for r in recs)
        assert any("GPU 驱动为最新版本" in r for r in recs)

    def test_zero_memory_handled_gracefully(self):
        """显存为 0 时正确进入小显存建议分支，不崩溃"""
        engine = _make_mock_engine(
            {
                "name": "GPU",
                "vendor": "Unknown",
                "global_mem_size": 0,  # 格式化为 "0.0 GB"，触发 mem_gb < 4 → 小显存建议
            }
        )
        gen = PerformanceReportGenerator(engine)
        recs = gen._generate_recommendations()
        assert isinstance(recs, list)
        assert any("显存较小" in r for r in recs)  # 精准断言进入小显存分支
        assert len(recs) >= 2  # 仍包含通用建议

    def test_empty_device_info_no_crash(self):
        """空设备信息不崩溃"""
        engine = _make_mock_engine(None)
        gen = PerformanceReportGenerator(engine)
        recs = gen._generate_recommendations()
        assert isinstance(recs, list)
        # 仍包含通用建议
        assert len(recs) >= 2

    def test_memory_parse_exception_logged(self):
        """显存解析异常时记录 debug 日志 (lines 407-408)"""
        engine = _make_mock_engine()
        gen = PerformanceReportGenerator(engine)
        # 构造含 "GB" 但不可解析的显存字符串
        with patch.object(gen, "_get_device_info", return_value={"厂商": "", "全局显存": "GB"}):
            with patch("src.gpu.performance_reporter.logger") as mock_logger:
                recs = gen._generate_recommendations()
                assert isinstance(recs, list)
                mock_logger.debug.assert_called_once()
                assert "获取GPU显存信息失败" in mock_logger.debug.call_args[0][0]
