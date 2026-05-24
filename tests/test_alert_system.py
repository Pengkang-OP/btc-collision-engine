"""测试性能监控告警系统"""

import time

import pytest

from src.monitoring.alert_system import (
    AlertLevel,
    AlertRule,
    AlertSystem,
    AlertType,
    get_alert_system,
)


class TestAlertSystem:
    """测试告警系统"""

    def _create_alert_system(self, tmp_path):
        """创建独立的告警系统实例,避免测试间干扰"""
        log_file = tmp_path / f"test_alerts_{id(tmp_path)}.json"
        return AlertSystem(alert_log_file=str(log_file))

    def test_initialization(self, tmp_path):
        """测试初始化"""
        log_file = tmp_path / "test_alerts.json"
        alert_system = AlertSystem(alert_log_file=str(log_file))
        assert len(alert_system.rules) == 0
        assert len(alert_system.alert_history) == 0
        assert len(alert_system.alert_callbacks) == 0

    def test_setup_default_rules(self, tmp_path):
        """测试设置默认规则"""
        log_file = tmp_path / "test_alerts.json"
        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 应该有5条默认规则
        assert len(alert_system.rules) == 5

        # 检查规则名称
        rule_names = [r.name for r in alert_system.rules]
        assert "性能退化警告" in rule_names
        assert "内存使用过高" in rule_names
        assert "GPU温度过高" in rule_names
        assert "错误率过高" in rule_names
        assert "吞吐量严重下降" in rule_names

    def test_add_rule(self, tmp_path):
        """测试添加规则"""
        log_file = tmp_path / "test_alerts.json"
        alert_system = AlertSystem(alert_log_file=str(log_file))

        rule = AlertRule(
            name="测试规则",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            condition=lambda m: m.get("value", 0) > 100,
            message="测试告警",
        )

        alert_system.add_rule(rule)
        assert len(alert_system.rules) == 1
        assert alert_system.rules[0].name == "测试规则"

    def test_remove_rule(self, tmp_path):
        """测试删除规则"""
        alert_system = self._create_alert_system(tmp_path)

        rule = AlertRule(
            name="测试规则",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            condition=lambda m: True,
            message="测试告警",
        )

        alert_system.add_rule(rule)
        assert len(alert_system.rules) == 1

        # 移除规则
        result = alert_system.remove_rule("测试规则")
        assert result is True
        assert len(alert_system.rules) == 0

        # 移除不存在的规则
        result = alert_system.remove_rule("不存在的规则")
        assert result is False

    def test_check_metrics_performance_degradation(self, tmp_path):
        """测试性能退化告警"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        # 正常情况(退化率10%)
        metrics = {"degradation_rate": 10.0}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 0

        # 异常情况(退化率25%)
        metrics = {"degradation_rate": 25.0}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.PERFORMANCE_DEGRADATION
        assert alerts[0].level == AlertLevel.WARNING

    def test_check_metrics_memory_overflow(self, tmp_path):
        """测试内存溢出告警"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        # 正常情况(70%)
        metrics = {"memory_usage_percent": 70.0}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 0

        # 异常情况(85%)
        metrics = {"memory_usage_percent": 85.0}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.MEMORY_OVERFLOW
        assert alerts[0].level == AlertLevel.WARNING

    def test_check_metrics_gpu_overheat(self, tmp_path):
        """测试GPU过热告警"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        # 正常情况(75°C)
        metrics = {"gpu_temperature": 75.0}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 0

        # 异常情况(90°C)
        metrics = {"gpu_temperature": 90.0}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.GPU_OVERHEAT
        assert alerts[0].level == AlertLevel.CRITICAL

    def test_check_metrics_error_rate(self, tmp_path):
        """测试错误率告警"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        # 正常情况(2%)
        metrics = {"error_rate": 0.02}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 0

        # 异常情况(8%)
        metrics = {"error_rate": 0.08}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.ERROR_RATE_HIGH
        assert alerts[0].level == AlertLevel.CRITICAL

    def test_check_metrics_throughput_drop(self, tmp_path):
        """测试吞吐量下降告警"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        # 正常情况(下降30%)
        metrics = {"throughput": 700000, "baseline_throughput": 1000000}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 0

        # 异常情况(下降60%)
        metrics = {"throughput": 400000, "baseline_throughput": 1000000}
        alerts = alert_system.check_metrics(metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.THROUGHPUT_DROP
        assert alerts[0].level == AlertLevel.CRITICAL

    def test_cooldown_mechanism(self, tmp_path):
        """测试冷却机制"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        # 第一次触发
        metrics = {"degradation_rate": 25.0}
        alerts1 = alert_system.check_metrics(metrics)
        assert len(alerts1) == 1

        # 立即再次检查(应该在冷却期内)
        alerts2 = alert_system.check_metrics(metrics)
        assert len(alerts2) == 0

    def test_alert_callback(self, tmp_path):
        """测试告警回调"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        callback_triggered = []

        def test_callback(alert):
            callback_triggered.append(alert)

        alert_system.add_alert_callback(test_callback)

        # 触发告警
        metrics = {"degradation_rate": 25.0}
        alerts = alert_system.check_metrics(metrics)

        assert len(alerts) == 1
        assert len(callback_triggered) == 1
        assert callback_triggered[0] == alerts[0]

    def test_alert_history(self, tmp_path):
        """测试告警历史"""
        log_file = tmp_path / "test_alerts.json"
        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 触发多个告警
        alert_system.check_metrics({"degradation_rate": 25.0})
        time.sleep(0.1)  # 避免冷却期
        alert_system.check_metrics({"gpu_temperature": 90.0})

        # 检查历史
        assert len(alert_system.alert_history) == 2

        # 检查统计
        stats = alert_system.get_alert_statistics()
        assert stats["total_alerts"] == 2
        assert stats["active_alerts"] == 2
        assert stats["resolved_alerts"] == 0

    def test_resolve_alert(self, tmp_path):
        """测试解决告警"""
        log_file = tmp_path / "test_alerts.json"
        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 触发告警
        alert_system.check_metrics({"degradation_rate": 25.0})

        # 解决告警
        alert_system.resolve_alert(0)

        # 检查状态
        alert = alert_system.alert_history[0]
        assert alert.resolved is True
        assert alert.resolved_at is not None

        # 检查统计
        stats = alert_system.get_alert_statistics()
        assert stats["active_alerts"] == 0
        assert stats["resolved_alerts"] == 1

    def test_get_active_alerts(self, tmp_path):
        """测试获取活动告警"""
        log_file = tmp_path / "test_alerts.json"
        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 触发多个告警
        alert_system.check_metrics({"degradation_rate": 25.0})
        time.sleep(0.1)  # 避免冷却期
        alert_system.check_metrics({"gpu_temperature": 90.0})

        # 解决一个
        alert_system.resolve_alert(0)

        # 检查活动告警
        active = alert_system.get_active_alerts()
        assert len(active) == 1
        assert active[0].alert_type == AlertType.GPU_OVERHEAT

    def test_save_and_load_history(self, tmp_path):
        """测试保存和加载历史"""
        log_file = tmp_path / "test_alerts.json"

        # 创建告警系统并触发告警
        alert_system1 = AlertSystem(alert_log_file=str(log_file))
        alert_system1.setup_default_rules()
        alert_system1.check_metrics({"degradation_rate": 25.0})

        # 保存历史
        alert_system1._save_alert_history()
        assert log_file.exists()

        # 创建新的告警系统并加载历史
        alert_system2 = AlertSystem(alert_log_file=str(log_file))
        assert len(alert_system2.alert_history) == 1
        assert alert_system2.alert_history[0].alert_type == AlertType.PERFORMANCE_DEGRADATION

    def test_clear_history(self, tmp_path):
        """测试清空历史"""
        log_file = tmp_path / "test_alerts.json"
        alert_system = AlertSystem(alert_log_file=str(log_file))
        alert_system.setup_default_rules()

        # 触发告警
        alert_system.check_metrics({"degradation_rate": 25.0})
        assert len(alert_system.alert_history) == 1

        # 清空历史
        alert_system.clear_history()
        assert len(alert_system.alert_history) == 0

    def test_get_alert_system_singleton(self):
        """测试全局单例"""
        system1 = get_alert_system()
        system2 = get_alert_system()

        assert system1 is system2

    def test_multiple_alerts_no_cooldown(self, tmp_path):
        """测试多个不同规则同时触发"""
        alert_system = self._create_alert_system(tmp_path)
        alert_system.setup_default_rules()

        # 同时触发多个告警
        metrics = {"degradation_rate": 25.0, "gpu_temperature": 90.0, "error_rate": 0.08}
        alerts = alert_system.check_metrics(metrics)

        # 应该触发3个告警
        assert len(alerts) == 3

        # 检查告警类型
        alert_types = [a.alert_type for a in alerts]
        assert AlertType.PERFORMANCE_DEGRADATION in alert_types
        assert AlertType.GPU_OVERHEAT in alert_types
        assert AlertType.ERROR_RATE_HIGH in alert_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
