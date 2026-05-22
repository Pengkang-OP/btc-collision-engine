"""测试告警系统集成到GPU性能监控"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.alert_system import AlertLevel, AlertType  # noqa: E402
from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor  # noqa: E402


class TestAlertSystemIntegration:
    """测试告警系统集成"""

    def setup_method(self):
        """测试前准备"""
        # 重置全局告警系统
        import src.monitoring.alert_system as alert_module

        alert_module._alert_system = None

        # 创建监控器(无引擎)
        self.monitor = GPUPerformanceMonitor(
            engine=None, check_interval=1.0, degradation_threshold=0.75, history_size=100
        )

    def test_performance_degradation_triggers_alert(self, tmp_path):
        """测试性能退化触发告警"""
        log_file = tmp_path / "test_alerts.json"

        # 创建告警系统
        from src.monitoring.alert_system import AlertSystem

        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 替换全局实例
        import src.monitoring.alert_system as alert_module

        alert_module._alert_system = alert_system

        # Task 2 引入了预热机制: _warmup_batches=10
        # 预热期内不触发退化告警，需要先记录超过10批高性能数据度过预热期
        warmup_count = self.monitor._warmup_batches + 1  # 超过预热批次数
        for _ in range(warmup_count):
            self.monitor.record_kernel_metrics(
                batch_size=1000000,
                execution_time_ms=500.0,  # 500ms, 高性能基准
                memory_allocated_mb=256.0,
                error_count=0,
            )

        # 预热完成后记录低性能数据(2500ms, 吞吐量降低5倍,应该触发告警)
        self.monitor.record_kernel_metrics(
            batch_size=1000000,
            execution_time_ms=2500.0,  # 2500ms (退化80%)
            memory_allocated_mb=256.0,
            error_count=0,
        )

        # 检查告警历史
        alerts = alert_system.get_active_alerts()

        # 应该至少有一个性能退化告警
        performance_alerts = [a for a in alerts if a.alert_type == AlertType.PERFORMANCE_DEGRADATION]
        assert len(performance_alerts) > 0, "应该触发性能退化告警"

        # 检查告警级别
        assert performance_alerts[0].level == AlertLevel.WARNING

    def test_high_error_rate_triggers_alert(self, tmp_path):
        """测试高错误率触发告警"""
        log_file = tmp_path / "test_alerts.json"

        # 创建告警系统
        from src.monitoring.alert_system import AlertSystem

        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 替换全局实例
        import src.monitoring.alert_system as alert_module

        alert_module._alert_system = alert_system

        # 记录10个批次,其中8个错误(错误率80%)
        for i in range(10):
            self.monitor.record_kernel_metrics(
                batch_size=100000,
                execution_time_ms=100.0,
                memory_allocated_mb=128.0,
                error_count=1 if i < 8 else 0,  # 80%错误率
            )
            time.sleep(0.05)  # 避免时间戳重复

        # 触发错误率检查
        self.monitor._check_error_rate()

        # 检查告警历史
        alerts = alert_system.get_active_alerts()

        # 应该有一个错误率告警
        error_alerts = [a for a in alerts if a.alert_type == AlertType.ERROR_RATE_HIGH]
        assert len(error_alerts) > 0, "应该触发错误率告警"

        # 检查告警级别
        assert error_alerts[0].level == AlertLevel.CRITICAL

    def test_alert_integration_does_not_break_monitor(self):
        """测试告警集成不影响监控器正常工作"""
        # 即使告警系统失败,监控器也应正常工作

        # 记录多个指标
        for i in range(10):
            self.monitor.record_kernel_metrics(
                batch_size=100000,
                execution_time_ms=100.0 + i,
                memory_allocated_mb=128.0,
                error_count=0,
            )

        # 监控器应该正常记录数据
        assert len(self.monitor._kernel_metrics) == 10

        # 峰值吞吐量应该正确 (第一批最快)
        assert self.monitor._peak_throughput > 0

    def test_alert_system_import_fallback(self):
        """测试告警系统导入失败时的降级处理"""
        # 模拟告警系统不可用的情况
        import src.monitoring.alert_system as alert_module

        original_get = alert_module.get_alert_system

        # 临时替换为抛出异常
        def mock_get():
            raise ImportError("告警系统不可用")

        alert_module.get_alert_system = mock_get

        try:
            # 记录高性能数据
            self.monitor.record_kernel_metrics(
                batch_size=1000000,
                execution_time_ms=500.0,
                memory_allocated_mb=256.0,
                error_count=0,
            )

            # 再次记录低性能数据
            self.monitor.record_kernel_metrics(
                batch_size=1000000,
                execution_time_ms=2500.0,
                memory_allocated_mb=256.0,
                error_count=0,
            )

            # 应该不抛出异常
            assert self.monitor._peak_throughput > 0

        finally:
            # 恢复原始函数
            alert_module.get_alert_system = original_get

    def test_cooldown_mechanism_in_integration(self, tmp_path):
        """测试集成场景下的冷却机制"""
        log_file = tmp_path / "test_alerts.json"

        # 创建告警系统
        from src.monitoring.alert_system import AlertSystem

        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 替换全局实例
        import src.monitoring.alert_system as alert_module

        alert_module._alert_system = alert_system

        # 第一次触发告警
        self.monitor.record_kernel_metrics(
            batch_size=1000000, execution_time_ms=500.0, memory_allocated_mb=256.0, error_count=0
        )

        self.monitor.record_kernel_metrics(
            batch_size=1000000, execution_time_ms=2500.0, memory_allocated_mb=256.0, error_count=0
        )

        alerts_after_first = len(alert_system.get_active_alerts())

        # 立即再次触发(应该在冷却期内)
        self.monitor.record_kernel_metrics(
            batch_size=1000000, execution_time_ms=3000.0, memory_allocated_mb=256.0, error_count=0
        )

        alerts_after_second = len(alert_system.get_active_alerts())

        # 告警数量不应该增加(冷却机制生效)
        assert alerts_after_second == alerts_after_first


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
