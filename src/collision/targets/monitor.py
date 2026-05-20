"""验证质量监控工具

提供验证质量的实时监控和告警功能,
替代基于日志级别的脆弱监控方式。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# 导入日志配置
from ...utils import get_configured_logger

# 日志系统由CLI/main.py入口统一初始化
logger = get_configured_logger("ValidationMonitor", thread_safe=False)


@dataclass
class ValidationThresholds:
    """验证质量阈值配置"""

    # 覆盖率阈值(%)
    coverage_critical: float = 50.0  # 严重告警阈值
    coverage_warning: float = 90.0  # 警告阈值

    # 未验证比例阈值
    unvalidated_critical: float = 0.5  # 严重告警阈值(50%)
    unvalidated_warning: float = 0.1  # 警告阈值(10%)

    # 成功率阈值(%)
    success_rate_critical: float = 50.0
    success_rate_warning: float = 80.0

    # 频率阈值(每小时)
    abort_critical: int = 50  # 严重告警: 每小时超过50次中止
    abort_warning: int = 10  # 警告: 每小时超过10次中止


@dataclass
class ValidationMetrics:
    """验证质量指标"""

    timestamp: datetime
    total: int
    validated: int
    unvalidated: int
    coverage: float
    valid: int
    invalid: int
    success_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total": self.total,
            "validated": self.validated,
            "unvalidated": self.unvalidated,
            "coverage": self.coverage,
            "valid": self.valid,
            "invalid": self.invalid,
            "success_rate": self.success_rate,
        }


class ValidationMonitor:
    """验证质量监控器

    提供基于业务指标的验证质量监控,
    替代基于日志级别的脆弱监控方式。

    示例:
        >>> validator = AddressBatchValidator(max_workers=4)
        >>> monitor = ValidationMonitor(validator)
        >>>
        >>> results = validator.validate_batch(addresses, strict_mode=True)
        >>> metrics = monitor.check_and_report(results)
        >>>
        >>> if metrics.alert_level:
        ...     print(f"告警级别: {metrics.alert_level}")
    """

    # 告警历史记录大小限制
    MAX_HISTORY_SIZE = 1000  # 最多保留1000条记录
    HISTORY_TRIM_SIZE = 500  # 触发清理时保留最近500条

    def __init__(
        self,
        validator: Any = None,
        thresholds: ValidationThresholds | None = None,
        alert_callback: Callable | None = None,
    ) -> None:
        """
        初始化验证质量监控器

        参数:
            validator: AddressBatchValidator实例(可选)
            thresholds: 阈值配置,使用默认值如果为None
            alert_callback: 告警回调函数,签名为 callback(level, message, metrics)
        """
        self.validator = validator
        self.thresholds = thresholds or ValidationThresholds()
        self.alert_callback = alert_callback or self._default_alert_callback

        # 统计信息
        self.total_checks = 0
        self.total_alerts = 0
        self.alert_history: list[dict[str, Any]] = []

        logger.info(
            "ValidationMonitor 初始化: "
            f"coverage_warning={self.thresholds.coverage_warning}%, "
            f"unvalidated_warning={self.thresholds.unvalidated_warning:.0%}, "
            f"max_history_size={self.MAX_HISTORY_SIZE}"
        )

    def check_and_report(
        self, results: dict, batch_id: str | None = None, data_source: str | None = None
    ) -> ValidationMetrics:
        """
        检查验证质量并生成报告

        参数:
            results: validate_batch返回的结果字典
            batch_id: 批次ID(可选,用于日志追踪)
            data_source: 数据源(可选,用于日志追踪)

        返回:
            ValidationMetrics: 验证质量指标
        """
        if not results:
            logger.debug("空结果,跳过检查")
            return ValidationMetrics(
                timestamp=datetime.now(),
                total=0,
                validated=0,
                unvalidated=0,
                coverage=0.0,
                valid=0,
                invalid=0,
                success_rate=0.0,
            )

        # 计算指标
        metrics = self._calculate_metrics(results)

        # 更新统计
        self.total_checks += 1

        # 检查告警
        alert_level = self._check_alerts(metrics)

        # 记录日志
        self._log_metrics(metrics, alert_level, batch_id, data_source)

        # 触发告警
        if alert_level:
            self.total_alerts += 1

            # 添加告警历史记录(带大小限制)
            self.alert_history.append(
                {
                    "level": alert_level,
                    "timestamp": metrics.timestamp,
                    "metrics": metrics.to_dict(),
                }
            )

            # 自动清理: 超过最大大小时保留最近HISTORY_TRIM_SIZE条
            if len(self.alert_history) > self.MAX_HISTORY_SIZE:
                self.alert_history = self.alert_history[-self.HISTORY_TRIM_SIZE :]
                logger.debug(f"告警历史记录已清理: 保留最近{self.HISTORY_TRIM_SIZE}条记录")

            self.alert_callback(
                alert_level, self._format_alert_message(alert_level, metrics, batch_id), metrics
            )

        return metrics

    def _calculate_metrics(self, results: dict) -> ValidationMetrics:
        """计算验证质量指标"""
        if not self.validator:
            # 如果没有validator实例,手动计算
            total = len(results)
            validated = sum(1 for r in results.values() if getattr(r, "validated", True))
            unvalidated = total - validated
            valid = sum(1 for r in results.values() if getattr(r, "valid", False))
            invalid = validated - valid
            coverage = (validated / total * 100) if total > 0 else 0.0
            success_rate = (valid / validated * 100) if validated > 0 else 0.0
        else:
            # 使用validator的方法
            coverage_stats = self.validator.get_validation_coverage(results)
            total = coverage_stats["total"]
            validated = coverage_stats["validated"]
            unvalidated = coverage_stats["unvalidated"]
            valid = coverage_stats["valid"]
            invalid = coverage_stats["invalid"]
            coverage = coverage_stats["coverage"]
            success_rate = (valid / validated * 100) if validated > 0 else 0.0

        return ValidationMetrics(
            timestamp=datetime.now(),
            total=total,
            validated=validated,
            unvalidated=unvalidated,
            coverage=coverage,
            valid=valid,
            invalid=invalid,
            success_rate=success_rate,
        )

    def _check_alerts(self, metrics: ValidationMetrics) -> str | None:
        """
        检查是否需要告警

        返回:
            'critical' | 'warning' | None
        """
        # 检查覆盖率
        if metrics.coverage < self.thresholds.coverage_critical:
            return "critical"
        elif metrics.coverage < self.thresholds.coverage_warning:
            return "warning"

        # 检查未验证比例
        if metrics.total > 0:
            unvalidated_ratio = metrics.unvalidated / metrics.total
            if unvalidated_ratio > self.thresholds.unvalidated_critical:
                return "critical"
            elif unvalidated_ratio > self.thresholds.unvalidated_warning:
                return "warning"

        # 检查成功率
        if metrics.success_rate < self.thresholds.success_rate_critical:
            return "critical"
        elif metrics.success_rate < self.thresholds.success_rate_warning:
            return "warning"

        return None

    def _log_metrics(
        self,
        metrics: ValidationMetrics,
        alert_level: str | None,
        batch_id: str | None,
        data_source: str | None,
    ):
        """记录验证指标日志"""
        context = []
        if batch_id:
            context.append(f"批次ID: {batch_id}")
        if data_source:
            context.append(f"数据源: {data_source}")

        context_str = f" [{', '.join(context)}]" if context else ""

        if alert_level == "critical":
            logger.error(
                f"验证质量严重告警{context_str}: "
                f"覆盖率={metrics.coverage:.1f}%, "
                f"未验证={metrics.unvalidated}/{metrics.total} "
                f"({metrics.unvalidated / metrics.total:.0%}"
                if metrics.total > 0
                else f"(0%)), 成功率={metrics.success_rate:.1f}%"
            )
        elif alert_level == "warning":
            logger.warning(
                f"验证质量警告{context_str}: "
                f"覆盖率={metrics.coverage:.1f}%, "
                f"未验证={metrics.unvalidated}/{metrics.total} "
                f"({metrics.unvalidated / metrics.total:.0%}"
                if metrics.total > 0
                else f"(0%)), 成功率={metrics.success_rate:.1f}%"
            )
        else:
            logger.debug(
                f"验证质量正常{context_str}: "
                f"覆盖率={metrics.coverage:.1f}%, "
                f"未验证={metrics.unvalidated}/{metrics.total}, "
                f"成功率={metrics.success_rate:.1f}%"
            )

    def _format_alert_message(self, level: str, metrics: ValidationMetrics, batch_id: str | None) -> str:
        """格式化告警消息"""
        severity = "严重" if level == "critical" else "警告"

        message = (
            f"验证质量{severity}告警:\n"
            f"  验证覆盖率: {metrics.coverage:.1f}%\n"
            f"  已验证地址: {metrics.validated}/{metrics.total}\n"
            f"  未验证地址: {metrics.unvalidated}\n"
            f"  验证成功率: {metrics.success_rate:.1f}%\n"
        )

        if batch_id:
            message += f"  批次ID: {batch_id}\n"

        message += f"  时间: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        return message

    def _default_alert_callback(self, level: str, message: str, metrics: ValidationMetrics):
        """默认告警回调(记录日志)"""
        # 这里可以集成实际的告警系统:
        # - Webhook通知
        # - 邮件通知
        # - Slack/钉钉通知
        # - Prometheus指标上报

        logger.info(f"告警触发 [{level}]: {message}")

    def get_statistics(self) -> dict[str, Any]:
        """获取监控统计信息"""
        return {
            "total_checks": self.total_checks,
            "total_alerts": self.total_alerts,
            "alert_rate": (
                (self.total_alerts / self.total_checks * 100) if self.total_checks > 0 else 0.0
            ),
            "recent_alerts": self.alert_history[-10:],  # 最近10次告警
        }

    def reset_statistics(self) -> None:
        """重置统计信息"""
        self.total_checks = 0
        self.total_alerts = 0
        self.alert_history.clear()
        logger.info("监控统计已重置")


# 便捷函数
def create_monitor(
    validator: Any = None,
    coverage_warning: float = 90.0,
    unvalidated_warning: float = 0.1,
    alert_callback: Callable | None = None,
) -> ValidationMonitor:
    """
    快速创建验证质量监控器

    参数:
        validator: AddressBatchValidator实例
        coverage_warning: 覆盖率警告阈值(%)
        unvalidated_warning: 未验证比例警告阈值
        alert_callback: 告警回调函数

    返回:
        ValidationMonitor实例
    """
    thresholds = ValidationThresholds(
        coverage_warning=coverage_warning, unvalidated_warning=unvalidated_warning
    )

    return ValidationMonitor(validator=validator, thresholds=thresholds, alert_callback=alert_callback)
