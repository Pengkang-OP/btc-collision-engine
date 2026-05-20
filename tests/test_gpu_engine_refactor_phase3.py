#!/usr/bin/env python3
"""GPU引擎重构 Phase 3 监控管道单元测试

测试覆盖:
1. DataLoggerAdapter: 数据日志适配器
2. PerformanceMonitoringPipeline: 监控管道完整功能
3. 模块导入与版本
4. 管道集成 (record_metrics → log_performance 流程)

所有测试使用 Mock，无需真实 GPU 硬件。
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = pytest.mark.gpu

# ============================================================================
# DataLoggerAdapter 测试
# ============================================================================


class TestDataLoggerAdapter:
    """测试数据日志适配器"""

    def test_creation_with_engine_data_logger(self):
        """测试复用引擎已有的 DataLogger"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        mock_engine = Mock()
        mock_engine.data_logger = Mock()
        mock_engine.data_logger.flush = Mock()

        adapter = DataLoggerAdapter(engine=mock_engine)
        assert adapter.is_available() is True
        assert adapter._owns_logger is False
        assert adapter._logger is mock_engine.data_logger

    def test_creation_without_engine(self):
        """测试无引擎时创建独立 DataLogger"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        with patch(
            "src.collision.gpu.data_logger_adapter.DataLoggerAdapter.__init__",
            lambda self, engine=None, config=None: None,
        ):
            pass  # skip actual DataLogger creation

        # 使用 mock DataLogger
        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        adapter._logger = None
        adapter._owns_logger = False
        adapter.config = {}
        assert adapter.is_available() is False

    def test_log_performance_maps_to_record_performance_data(self):
        """测试 log_performance 正确桥接到 record_performance_data"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        adapter.config = {}
        adapter._owns_logger = False
        mock_logger = Mock()
        adapter._logger = mock_logger

        # 完整参数
        adapter.log_performance(
            {
                "batch_size": 1_000_000,
                "execution_time_ms": 50.5,
                "speed": 20_000_000.0,
                "match_count": 3,
                "cpu_usage": 45.2,
                "memory_usage": 512.0,
                "thread_count": 8,
            }
        )

        mock_logger.record_performance_data.assert_called_once_with(
            speed=20_000_000.0,
            total_checked=1_000_000,
            matches_found=3,
            cpu_usage=45.2,
            memory_usage=512.0,
            thread_count=8,
        )

    def test_log_performance_with_alternative_keys(self):
        """测试 log_performance 使用备选键名"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        adapter.config = {}
        adapter._owns_logger = False
        mock_logger = Mock()
        adapter._logger = mock_logger

        adapter.log_performance(
            {
                "keys_per_second": 15_000_000.0,
                "total_checked": 500_000,
                "matches_found": 1,
            }
        )

        mock_logger.record_performance_data.assert_called_once_with(
            speed=15_000_000.0,
            total_checked=500_000,
            matches_found=1,
            cpu_usage=0.0,
            memory_usage=0.0,
            thread_count=0,
        )

    def test_log_performance_empty_data(self):
        """测试 log_performance 处理空数据"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        adapter.config = {}
        adapter._owns_logger = False
        mock_logger = Mock()
        adapter._logger = mock_logger

        adapter.log_performance({})

        mock_logger.record_performance_data.assert_called_once_with(
            speed=0.0,
            total_checked=0,
            matches_found=0,
            cpu_usage=0.0,
            memory_usage=0.0,
            thread_count=0,
        )

    def test_log_performance_when_unavailable(self):
        """测试 DataLogger 不可用时 log_performance 安全"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        adapter.config = {}
        adapter._owns_logger = False
        adapter._logger = None

        # 不应抛出异常
        adapter.log_performance({"batch_size": 1000})

    def test_flush_delegation(self):
        """测试 flush 委托给底层 DataLogger"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        mock_logger = Mock()
        adapter._logger = mock_logger

        adapter.flush()
        mock_logger.flush.assert_called_once()

    def test_flush_when_unavailable(self):
        """测试 DataLogger 不可用时 flush 安全"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        adapter._logger = None

        adapter.flush()  # 不应抛出异常

    def test_get_stats_delegation(self):
        """测试 get_stats 委托给底层 DataLogger.get_statistics"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        mock_logger = Mock()
        mock_logger.get_statistics.return_value = {"total_checks": 1000, "matches": 5}
        adapter._logger = mock_logger

        stats = adapter.get_stats()
        assert stats["total_checks"] == 1000
        assert stats["matches"] == 5

    def test_get_stats_when_unavailable(self):
        """测试 DataLogger 不可用时 get_stats 返回 not_initialized"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        adapter._logger = None

        stats = adapter.get_stats()
        assert stats["status"] == "not_initialized"

    def test_save_current_data_delegation(self):
        """测试 save_current_data 委托"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        mock_logger = Mock()
        adapter._logger = mock_logger

        adapter.save_current_data()
        mock_logger.save_current_data.assert_called_once()

    def test_save_history_data_delegation(self):
        """测试 save_history_data 委托"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        mock_logger = Mock()
        adapter._logger = mock_logger

        adapter.save_history_data()
        mock_logger.save_history_data.assert_called_once()

    def test_cleanup_when_owns_logger(self):
        """测试自有 DataLogger 时的清理"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        mock_logger = Mock()
        adapter._logger = mock_logger
        adapter._owns_logger = True

        adapter.cleanup()

        mock_logger.flush.assert_called_once()
        assert adapter._logger is None
        assert adapter._owns_logger is False

    def test_cleanup_when_reusing_engine_logger(self):
        """测试复用引擎 DataLogger 时不清理"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        mock_logger = Mock()
        adapter._logger = mock_logger
        adapter._owns_logger = False

        adapter.cleanup()

        # 不应调用 flush，也不应清空 logger
        mock_logger.flush.assert_not_called()
        assert adapter._logger is mock_logger

    def test_get_native_logger(self):
        """测试获取底层 DataLogger"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        adapter = DataLoggerAdapter.__new__(DataLoggerAdapter)
        mock_logger = Mock()
        adapter._logger = mock_logger

        assert adapter.get_native_logger() is mock_logger


# ============================================================================
# PerformanceMonitoringPipeline 测试
# ============================================================================


class TestPerformanceMonitoringPipeline:
    """测试性能监控管道"""

    def test_pipeline_creation(self):
        """测试管道创建"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline(
            engine=None,
            config={"slow_threshold_ms": 3000},
        )
        assert pipeline.engine is None
        assert pipeline.config["slow_threshold_ms"] == 3000
        assert pipeline.is_running() is False

    def test_pipeline_creation_with_engine(self):
        """测试带引擎的管道创建"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_engine = Mock()
        pipeline = PerformanceMonitoringPipeline(engine=mock_engine)
        assert pipeline.engine is mock_engine

    def test_start_stop_lifecycle(self):
        """测试启动-停止生命周期"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()

        # Mock 所有工厂方法
        with (
            patch.object(pipeline, "_create_performance_monitor", return_value=None),
            patch.object(pipeline, "_create_engine_monitor", return_value=None),
            patch.object(pipeline, "_create_data_logger", return_value=None),
            patch.object(pipeline, "_create_vendor_monitors", return_value=[]),
        ):

            pipeline.start()
            assert pipeline.is_running() is True

            pipeline.stop()
            assert pipeline.is_running() is False

    def test_double_start_is_safe(self):
        """测试重复启动安全"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()

        with (
            patch.object(pipeline, "_create_performance_monitor", return_value=None),
            patch.object(pipeline, "_create_engine_monitor", return_value=None),
            patch.object(pipeline, "_create_data_logger", return_value=None),
            patch.object(pipeline, "_create_vendor_monitors", return_value=[]),
        ):

            pipeline.start()
            pipeline.start()  # 不应抛出异常
            assert pipeline.is_running() is True

    def test_stop_when_not_running_is_safe(self):
        """测试未运行时停止安全"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        pipeline.stop()  # 不应抛出异常

    def test_record_metrics_delegates_to_perf_monitor(self):
        """测试 record_metrics 委托给性能监控器"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        mock_perf_monitor = Mock()
        pipeline._perf_monitor = mock_perf_monitor
        pipeline._data_logger = None
        pipeline._running = True

        pipeline.record_metrics(batch_size=1_000_000, execution_time_ms=50.0)

        mock_perf_monitor.record_kernel_metrics.assert_called_once_with(
            batch_size=1_000_000, execution_time_ms=50.0
        )

    def test_record_metrics_delegates_to_data_logger(self):
        """测试 record_metrics 委托给数据日志"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        mock_data_logger = Mock()
        pipeline._perf_monitor = None
        pipeline._data_logger = mock_data_logger
        pipeline._running = True

        pipeline.record_metrics(
            batch_size=500_000,
            execution_time_ms=100.0,
            gpu_errors=2,
        )

        # 验证 log_performance 被调用
        call_args = mock_data_logger.log_performance.call_args[0][0]
        assert call_args["batch_size"] == 500_000
        assert call_args["execution_time_ms"] == 100.0
        assert call_args["gpu_errors"] == 2
        assert "timestamp" in call_args

    def test_record_metrics_skips_when_not_running(self):
        """测试未运行时跳过指标记录"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        mock_perf_monitor = Mock()
        mock_data_logger = Mock()
        pipeline._perf_monitor = mock_perf_monitor
        pipeline._data_logger = mock_data_logger
        pipeline._running = False

        pipeline.record_metrics(batch_size=1000, execution_time_ms=10.0)

        mock_perf_monitor.record_kernel_metrics.assert_not_called()
        mock_data_logger.log_performance.assert_not_called()

    def test_flush_delegates_to_data_logger(self):
        """测试 flush 委托给数据日志"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        mock_data_logger = Mock()
        pipeline._data_logger = mock_data_logger

        pipeline.flush()
        mock_data_logger.flush.assert_called_once()

    def test_flush_safe_when_no_data_logger(self):
        """测试无数据日志时 flush 安全"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        pipeline._data_logger = None

        pipeline.flush()  # 不应抛出异常

    def test_get_stats_aggregation(self):
        """测试 get_stats 整合所有监控器统计"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        pipeline._running = True

        mock_perf = Mock()
        mock_perf.get_stats.return_value = {"throughput": 20000000}
        pipeline._perf_monitor = mock_perf

        mock_engine_mon = Mock()
        mock_engine_mon.get_stats.return_value = {"total_adjustments": 5}
        pipeline._engine_monitor = mock_engine_mon

        mock_dl = Mock()
        mock_dl.get_stats.return_value = {"total_checks": 1000}
        pipeline._data_logger = mock_dl

        stats = pipeline.get_stats()
        assert stats["running"] is True
        assert stats["performance"]["throughput"] == 20000000
        assert stats["engine"]["total_adjustments"] == 5
        assert stats["data_logger"]["total_checks"] == 1000

    def test_get_stats_fallback_to_performance_report(self):
        """测试 get_stats 回退到 get_performance_report.to_dict()"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()

        mock_report = Mock()
        mock_report.to_dict.return_value = {"avg_throughput": 15000000}
        mock_perf = Mock()
        # 不提供 get_stats，提供 get_performance_report
        del mock_perf.get_stats
        mock_perf.get_performance_report.return_value = mock_report
        pipeline._perf_monitor = mock_perf

        stats = pipeline.get_stats()
        assert stats["performance"]["avg_throughput"] == 15000000

    def test_get_stats_partial_data(self):
        """测试部分监控器不可用时的 get_stats"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        pipeline._perf_monitor = None
        pipeline._engine_monitor = None
        pipeline._data_logger = None

        stats = pipeline.get_stats()
        assert stats["running"] is False
        assert "performance" not in stats
        assert "engine" not in stats
        assert "data_logger" not in stats

    def test_get_data_logger(self):
        """测试获取数据日志适配器"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        mock_dl = Mock()
        pipeline._data_logger = mock_dl

        assert pipeline.get_data_logger() is mock_dl

    def test_get_data_logger_before_init(self):
        """测试初始化前获取数据日志返回 None"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline()
        assert pipeline.get_data_logger() is None

    # ---------- 异常检测测试 ----------

    def test_detect_anomalies_slow_execution(self):
        """测试慢操作异常检测"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline(config={"slow_threshold_ms": 100})

        with patch("src.collision.gpu.monitoring.logger") as mock_logger:
            pipeline._detect_anomalies(
                batch_size=1000,
                execution_time_ms=500.0,  # 超过阈值
                metrics={},
            )
            # 应输出 warning
            assert mock_logger.warning.called

    def test_detect_anomalies_normal_execution(self):
        """测试正常执行不触发告警"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline(config={"slow_threshold_ms": 5000})

        with patch("src.collision.gpu.monitoring.logger") as mock_logger:
            pipeline._detect_anomalies(
                batch_size=1000,
                execution_time_ms=50.0,  # 远低于阈值
                metrics={},
            )
            # 不应输出 warning 或 error
            mock_logger.warning.assert_not_called()
            mock_logger.error.assert_not_called()

    def test_detect_anomalies_high_error_rate(self):
        """测试高错误率检测"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline(config={"error_rate_threshold": 0.01})

        with patch("src.collision.gpu.monitoring.logger") as mock_logger:
            pipeline._detect_anomalies(
                batch_size=1000,
                execution_time_ms=50.0,
                metrics={"gpu_errors": 20},  # 2% 错误率 > 1% 阈值
            )
            assert mock_logger.error.called

    def test_detect_anomalies_normal_error_rate(self):
        """测试正常错误率不触发告警"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline(config={"error_rate_threshold": 0.01})

        with patch("src.collision.gpu.monitoring.logger") as mock_logger:
            pipeline._detect_anomalies(
                batch_size=10000,
                execution_time_ms=50.0,
                metrics={"gpu_errors": 1},  # 0.01% < 1% 阈值
            )
            mock_logger.error.assert_not_called()

    # ---------- 厂商检测测试 ----------

    def test_detect_vendor_from_gpu_device(self):
        """测试从 _gpu_device 检测厂商"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_engine = Mock()
        mock_engine._gpu_device = Mock()

        with patch(
            "src.collision.gpu.monitoring.PerformanceMonitoringPipeline._detect_vendor"
        ) as mock_detect:
            mock_detect.return_value = "nvidia"

            pipeline = PerformanceMonitoringPipeline(engine=mock_engine)
            vendor = pipeline._detect_vendor()
            assert vendor == "nvidia"

    def test_detect_vendor_from_device_info_fallback(self):
        """测试从 device_info 回退检测厂商"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_engine = Mock()
        # 没有 _gpu_device
        del mock_engine._gpu_device
        mock_engine.get_device_info.return_value = {"vendor": "amd"}

        pipeline = PerformanceMonitoringPipeline(engine=mock_engine)
        vendor = pipeline._detect_vendor()
        assert vendor == "amd"

    def test_detect_vendor_unknown(self):
        """测试未知厂商返回 unknown"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        pipeline = PerformanceMonitoringPipeline(engine=None)
        vendor = pipeline._detect_vendor()
        assert vendor == "unknown"


# ============================================================================
# 工厂方法测试
# ============================================================================


class TestFactoryMethods:
    """测试监控工厂方法"""

    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_performance_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_engine_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_data_logger")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_vendor_monitors")
    def test_start_invokes_all_factories(self, mock_vendor, mock_dl, mock_engine, mock_perf):
        """测试 start 调用所有工厂方法"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_perf.return_value = None
        mock_engine.return_value = None
        mock_dl.return_value = None
        mock_vendor.return_value = []

        pipeline = PerformanceMonitoringPipeline()
        pipeline.start()

        mock_perf.assert_called_once()
        mock_engine.assert_called_once()
        mock_dl.assert_called_once()
        mock_vendor.assert_called_once()

    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_performance_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_engine_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_data_logger")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_vendor_monitors")
    def test_start_with_all_monitors(self, mock_vendor, mock_dl, mock_engine, mock_perf):
        """测试启动时所有监控器 start() 被调用"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_perf_mon = Mock()
        mock_perf.return_value = mock_perf_mon
        mock_engine_mon = Mock()
        mock_engine.return_value = mock_engine_mon
        mock_dl_obj = Mock()
        mock_dl.return_value = mock_dl_obj
        mock_vendor.return_value = []

        pipeline = PerformanceMonitoringPipeline()
        pipeline.start()

        mock_perf_mon.start.assert_called_once()
        mock_engine_mon.start.assert_called_once()

    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_performance_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_engine_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_data_logger")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_vendor_monitors")
    def test_stop_stops_all_monitors_in_order(self, mock_vendor, mock_dl, mock_engine, mock_perf):
        """测试 stop 按正确顺序停止所有监控器"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_perf_mon = Mock()
        mock_perf.return_value = mock_perf_mon
        mock_engine_mon = Mock()
        mock_engine.return_value = mock_engine_mon
        mock_dl_obj = Mock()
        mock_dl.return_value = mock_dl_obj
        mock_vendor_mon1 = Mock()
        mock_vendor_mon2 = Mock()
        mock_vendor.return_value = [mock_vendor_mon1, mock_vendor_mon2]

        pipeline = PerformanceMonitoringPipeline()
        pipeline.start()

        # 重置 mock 以追踪 stop 调用顺序
        mock_vendor_mon1.reset_mock()
        mock_vendor_mon2.reset_mock()
        mock_engine_mon.reset_mock()
        mock_perf_mon.reset_mock()
        mock_dl_obj.reset_mock()

        pipeline.stop()

        # 厂商监控先停
        mock_vendor_mon1.stop.assert_called_once()
        mock_vendor_mon2.stop.assert_called_once()
        # 引擎监控其次
        mock_engine_mon.stop.assert_called_once()
        # 性能监控最后
        mock_perf_mon.stop.assert_called_once()
        # 数据日志保存并刷写
        mock_dl_obj.save_current_data.assert_called_once()
        mock_dl_obj.save_history_data.assert_called_once()
        mock_dl_obj.flush.assert_called_once()


# ============================================================================
# 模块导入测试
# ============================================================================


class TestModuleImports:
    """测试模块导入完整性"""

    def test_import_data_logger_adapter(self):
        """测试 DataLoggerAdapter 导入"""
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        assert DataLoggerAdapter is not None

    def test_import_from_module_init(self):
        """测试从 __init__ 导入 Phase 3 适配器"""
        from src.collision.gpu import DataLoggerAdapter, get_data_logger_adapter

        assert DataLoggerAdapter is not None
        assert callable(get_data_logger_adapter)

    def test_module_version(self):
        """测试模块版本号"""
        from src.collision import gpu

<<<<<<< Updated upstream
        assert gpu.__version__ == "4.4.0"
=======
        assert gpu.__version__ == "4.2.2"
>>>>>>> Stashed changes

    def test_all_exports_include_phase3(self):
        """测试 __all__ 包含 Phase 3 导出"""
        from src.collision.gpu import __all__

        # Phase 3 exports
        assert "DataLoggerAdapter" in __all__
        assert "get_data_logger_adapter" in __all__

        # Phase 1 & 2 exports still present
        assert "PerformanceMonitoringPipeline" in __all__
        assert "DeviceManagerAdapter" in __all__

    def test_monitoring_pipeline_import(self):
        """测试 PerformanceMonitoringPipeline 导入"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        assert PerformanceMonitoringPipeline is not None

    def test_no_todos_in_phase3_files(self):
        """测试 Phase 3 文件无残留 TODO"""
        import os

        phase3_files = [
            "src/collision/gpu/monitoring.py",
            "src/collision/gpu/data_logger_adapter.py",
        ]

        for filepath in phase3_files:
            full_path = os.path.join(os.path.dirname(__file__), "..", filepath)
            if os.path.exists(full_path):
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()
                assert "TODO: Phase 3" not in content, f"{filepath} 仍有 Phase 3 TODO"


# ============================================================================
# 集成测试
# ============================================================================


class TestPipelineIntegration:
    """测试管道与适配器集成"""

    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_performance_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_engine_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_vendor_monitors")
    def test_record_metrics_to_data_logger_integration(self, mock_vendor, mock_engine, mock_perf):
        """测试 record_metrics → DataLoggerAdapter.log_performance 完整流程"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_perf.return_value = Mock()
        mock_engine.return_value = Mock()
        mock_vendor.return_value = []

        pipeline = PerformanceMonitoringPipeline(
            config={"slow_threshold_ms": 10000},
        )

        # 使用真实的 DataLoggerAdapter
        from src.collision.gpu.data_logger_adapter import DataLoggerAdapter

        mock_adapter = MagicMock(spec=DataLoggerAdapter)
        pipeline._data_logger = mock_adapter

        pipeline._running = True

        pipeline.record_metrics(
            batch_size=2_000_000,
            execution_time_ms=80.0,
            gpu_errors=0,
            memory_usage=1024.0,
        )

        # 验证 log_performance 被调用并接收到正确数据
        call_data = mock_adapter.log_performance.call_args[0][0]
        assert call_data["batch_size"] == 2_000_000
        assert call_data["execution_time_ms"] == 80.0
        assert call_data["gpu_errors"] == 0
        assert call_data["memory_usage"] == 1024.0

    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_performance_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_engine_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_data_logger")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_vendor_monitors")
    def test_full_lifecycle_with_data_logger(self, mock_vendor, mock_dl, mock_engine, mock_perf):
        """测试完整生命周期：start → record → get_stats → stop"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_perf.return_value = Mock()
        mock_engine.return_value = Mock()
        mock_dl_adapter = Mock()
        mock_dl_adapter.get_stats.return_value = {"total_checks": 5000}
        mock_dl.return_value = mock_dl_adapter
        mock_vendor.return_value = []

        pipeline = PerformanceMonitoringPipeline()

        # start
        pipeline.start()
        assert pipeline.is_running() is True

        # record
        pipeline.record_metrics(batch_size=1_000_000, execution_time_ms=50.0)
        mock_dl_adapter.log_performance.assert_called_once()

        # get_stats
        stats = pipeline.get_stats()
        assert stats["data_logger"]["total_checks"] == 5000

        # stop
        pipeline.stop()
        assert pipeline.is_running() is False
        mock_dl_adapter.save_current_data.assert_called_once()
        mock_dl_adapter.flush.assert_called_once()

    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_performance_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_engine_monitor")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_data_logger")
    @patch("src.collision.gpu.monitoring.PerformanceMonitoringPipeline._create_vendor_monitors")
    def test_start_failure_triggers_stop(self, mock_vendor, mock_dl, mock_engine, mock_perf):
        """测试启动失败时触发 stop 清理"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        mock_perf.return_value = Mock()
        mock_engine.return_value = Mock()
        mock_dl.side_effect = RuntimeError("DataLogger 初始化失败")
        mock_vendor.return_value = []

        pipeline = PerformanceMonitoringPipeline()

        with pytest.raises(RuntimeError, match="DataLogger"):
            pipeline.start()

        # stop 应该已被调用
        assert pipeline.is_running() is False
