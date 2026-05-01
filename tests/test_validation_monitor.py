"""验证质量监控工具测试"""

import pytest
from datetime import datetime
from src.collision.targets.validator import AddressBatchValidator, ValidationResult
from src.collision.targets.monitor import (
    ValidationMonitor,
    ValidationThresholds,
    ValidationMetrics,
    create_monitor,
)


class TestValidationMetrics:
    """验证质量指标测试"""

    def test_metrics_creation(self):
        """测试指标创建"""
        metrics = ValidationMetrics(
            timestamp=datetime.now(),
            total=100,
            validated=90,
            unvalidated=10,
            coverage=90.0,
            valid=80,
            invalid=10,
            success_rate=88.9,
        )

        assert metrics.total == 100
        assert metrics.validated == 90
        assert metrics.unvalidated == 10
        assert metrics.coverage == 90.0

    def test_metrics_to_dict(self):
        """测试指标转换为字典"""
        metrics = ValidationMetrics(
            timestamp=datetime(2026, 4, 19, 10, 30, 0),
            total=100,
            validated=90,
            unvalidated=10,
            coverage=90.0,
            valid=80,
            invalid=10,
            success_rate=88.9,
        )

        d = metrics.to_dict()

        assert d["total"] == 100
        assert d["validated"] == 90
        assert d["coverage"] == 90.0
        assert "timestamp" in d


class TestValidationThresholds:
    """验证阈值配置测试"""

    def test_default_thresholds(self):
        """测试默认阈值"""
        thresholds = ValidationThresholds()

        assert thresholds.coverage_warning == 90.0
        assert thresholds.coverage_critical == 50.0
        assert thresholds.unvalidated_warning == 0.1
        assert thresholds.unvalidated_critical == 0.5

    def test_custom_thresholds(self):
        """测试自定义阈值"""
        thresholds = ValidationThresholds(coverage_warning=95.0, unvalidated_warning=0.05)

        assert thresholds.coverage_warning == 95.0
        assert thresholds.unvalidated_warning == 0.05


class TestValidationMonitor:
    """验证质量监控器测试"""

    def test_monitor_creation(self):
        """测试监控器创建"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        assert monitor.validator is validator
        assert monitor.total_checks == 0
        assert monitor.total_alerts == 0

    def test_check_and_report_good_quality(self):
        """测试高质量验证"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        # 模拟高质量结果
        results = {
            "1A1z...": ValidationResult(address="1A1z...", valid=True, validated=True),
            "1B2x...": ValidationResult(address="1B2x...", valid=True, validated=True),
        }

        metrics = monitor.check_and_report(results)

        assert metrics.total == 2
        assert metrics.validated == 2
        assert metrics.unvalidated == 0
        assert metrics.coverage == 100.0
        assert monitor.total_checks == 1
        assert monitor.total_alerts == 0  # 无告警

    def test_check_and_report_low_coverage(self):
        """测试低覆盖率告警"""
        validator = AddressBatchValidator()
        alerts_triggered = []

        def alert_callback(level, message, metrics):
            alerts_triggered.append({"level": level, "message": message, "metrics": metrics})

        monitor = ValidationMonitor(validator, alert_callback=alert_callback)

        # 模拟低覆盖率结果(40%覆盖率,应该触发critical)
        results = {
            "1A1z...": ValidationResult(address="1A1z...", valid=True, validated=True),
            "1B2x...": ValidationResult(address="1B2x...", valid=False, validated=False),
            "1C3y...": ValidationResult(address="1C3y...", valid=False, validated=False),
            "1D4z...": ValidationResult(address="1D4z...", valid=False, validated=False),
        }

        metrics = monitor.check_and_report(results)

        assert metrics.total == 4
        assert metrics.validated == 1
        assert metrics.unvalidated == 3
        assert metrics.coverage == 25.0  # 25% < 50% critical阈值
        assert len(alerts_triggered) == 1
        assert alerts_triggered[0]["level"] == "critical"
        assert monitor.total_alerts == 1

    def test_check_and_report_empty_results(self):
        """测试空结果"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        metrics = monitor.check_and_report({})

        assert metrics.total == 0
        assert metrics.coverage == 0.0

    def test_check_alerts_critical_coverage(self):
        """测试覆盖率严重告警"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        metrics = ValidationMetrics(
            timestamp=datetime.now(),
            total=100,
            validated=40,  # 40%覆盖率
            unvalidated=60,
            coverage=40.0,
            valid=30,
            invalid=10,
            success_rate=75.0,
        )

        alert_level = monitor._check_alerts(metrics)

        assert alert_level == "critical"

    def test_check_alerts_warning_coverage(self):
        """测试覆盖率警告"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        metrics = ValidationMetrics(
            timestamp=datetime.now(),
            total=100,
            validated=80,  # 80%覆盖率
            unvalidated=20,
            coverage=80.0,
            valid=70,
            invalid=10,
            success_rate=87.5,
        )

        alert_level = monitor._check_alerts(metrics)

        assert alert_level == "warning"

    def test_check_alerts_no_alert(self):
        """测试无告警"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        metrics = ValidationMetrics(
            timestamp=datetime.now(),
            total=100,
            validated=95,  # 95%覆盖率
            unvalidated=5,
            coverage=95.0,
            valid=90,
            invalid=5,
            success_rate=94.7,
        )

        alert_level = monitor._check_alerts(metrics)

        assert alert_level is None

    def test_statistics(self):
        """测试统计信息"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        # 执行几次检查
        results1 = {"1A1z...": ValidationResult(address="1A1z...", valid=True, validated=True)}
        results2 = {"1B2x...": ValidationResult(address="1B2x...", valid=False, validated=False)}

        monitor.check_and_report(results1)
        monitor.check_and_report(results2)

        stats = monitor.get_statistics()

        assert stats["total_checks"] == 2
        assert stats["total_alerts"] >= 0

    def test_reset_statistics(self):
        """测试重置统计"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        results = {"1A1z...": ValidationResult(address="1A1z...", valid=True, validated=True)}
        monitor.check_and_report(results)

        assert monitor.total_checks == 1

        monitor.reset_statistics()

        assert monitor.total_checks == 0
        assert monitor.total_alerts == 0
        assert len(monitor.alert_history) == 0

    def test_alert_history_size_limit(self):
        """测试告警历史记录大小限制"""
        validator = AddressBatchValidator()
        monitor = ValidationMonitor(validator)

        # 模拟大量告警(超过MAX_HISTORY_SIZE)
        # 为了测试,临时降低阈值
        monitor.thresholds.coverage_warning = 99.0  # 几乎每次都会告警

        for i in range(1100):  # 超过MAX_HISTORY_SIZE(1000)
            results = {
                f"addr{i}": ValidationResult(
                    address=f"addr{i}", valid=False, validated=False  # 未验证,触发告警
                )
            }
            monitor.check_and_report(results)

        # 验证历史记录被限制在合理范围
        # 注意: 清理只在超过MAX_HISTORY_SIZE时触发一次
        # 第1001次告警触发清理,保留500条
        # 之后继续添加99条(1002-1100),最终599条
        assert len(monitor.alert_history) <= monitor.MAX_HISTORY_SIZE
        assert len(monitor.alert_history) == 599  # 500 + 99 = 599

        # 验证保留的是最近的记录
        assert monitor.total_alerts == 1100

        # 增强验证: 确认保留的是最新的记录
        # 最后一次告警(第1100次,索引1099)
        last_alert = monitor.alert_history[-1]
        assert last_alert["level"] == "critical"
        assert last_alert["metrics"]["total"] == 1
        assert last_alert["metrics"]["valid"] == 0
        assert last_alert["metrics"]["validated"] == 0

        # 第一条记录应该是清理后的第一条
        # 当长度达到1001时触发清理,保留最后500条
        # 所以保留的是索引501-1000(第502-1001次告警)
        first_alert = monitor.alert_history[0]
        assert first_alert["level"] == "critical"
        assert first_alert["metrics"]["total"] == 1

        # 验证记录数量不超过MAX_HISTORY_SIZE
        assert len(monitor.alert_history) <= monitor.MAX_HISTORY_SIZE
        assert len(monitor.alert_history) == 599

        # 额外验证: 确认是最近的记录,而不是旧的
        # 倒数第二条也应该存在
        second_last_alert = monitor.alert_history[-2]
        assert second_last_alert["level"] == "critical"
        assert second_last_alert["metrics"]["total"] == 1


class TestCreateMonitor:
    """便捷函数测试"""

    def test_create_monitor_default(self):
        """测试使用默认配置创建"""
        validator = AddressBatchValidator()
        monitor = create_monitor(validator)

        assert monitor.validator is validator
        assert monitor.thresholds.coverage_warning == 90.0

    def test_create_monitor_custom(self):
        """测试使用自定义配置创建"""
        validator = AddressBatchValidator()
        monitor = create_monitor(validator, coverage_warning=95.0, unvalidated_warning=0.05)

        assert monitor.thresholds.coverage_warning == 95.0
        assert monitor.thresholds.unvalidated_warning == 0.05


class TestIntegration:
    """集成测试"""

    def test_monitor_with_strict_mode(self):
        """测试监控严格模式验证"""
        validator = AddressBatchValidator(max_workers=2)
        monitor = create_monitor(validator, coverage_warning=90.0, unvalidated_warning=0.1)

        # 严格模式: 包含非字符串类型
        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            12345,  # 非字符串,导致中止
        ]

        results = validator.validate_batch(addresses, strict_mode=True)
        metrics = monitor.check_and_report(results, batch_id="test-001")

        # 验证指标计算正确
        assert metrics.total == 3
        assert metrics.validated == 1
        assert metrics.unvalidated == 2
        assert metrics.coverage == pytest.approx(33.33, rel=0.1)

        # 应该触发严重告警(覆盖率33% < 50%)
        assert monitor.total_alerts == 1

    def test_monitor_with_skip_strategy(self):
        """测试监控skip策略"""
        validator = AddressBatchValidator(max_workers=2)
        monitor = create_monitor(validator)

        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            12345,  # 非字符串,被跳过
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        ]

        results = validator.validate_batch(addresses, strict_mode=True, on_type_error="skip")
        metrics = monitor.check_and_report(results)

        # 使用skip策略,所有字符串地址都验证了
        assert metrics.total == 2
        assert metrics.validated == 2
        assert metrics.unvalidated == 0
        assert metrics.coverage == 100.0

        # 应该无告警
        assert monitor.total_alerts == 0
