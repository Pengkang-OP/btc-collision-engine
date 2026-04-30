"""性能监控告警系统

实现GPU性能实时监控和异常自动告警功能。
支持多种告警规则和通知方式。
"""

import logging
import time
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
from src.utils.fast_json import fast_dump, fast_load
logger = logging.getLogger(__name__)

# 告警系统常量
MAX_ALERT_HISTORY = 1000  # 最大保存告警记录数
ALERT_DEDUP_LOOKBACK = 10  # 告警去重回溯数量


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"           # 信息
    WARNING = "warning"     # 警告
    CRITICAL = "critical"   # 严重
    EMERGENCY = "emergency" # 紧急


class AlertType(Enum):
    """告警类型"""
    PERFORMANCE_DEGRADATION = "performance_degradation"  # 性能退化
    MEMORY_OVERFLOW = "memory_overflow"                  # 内存溢出
    GPU_OVERHEAT = "gpu_overheat"                        # GPU过热
    ERROR_RATE_HIGH = "error_rate_high"                  # 错误率高
    THROUGHPUT_DROP = "throughput_drop"                  # 吞吐量下降
    SYSTEM_STABLE = "system_stable"                      # 系统稳定(恢复)


# 默认冷却时间配置(秒)
DEFAULT_COOLDOWNS = {
    AlertType.PERFORMANCE_DEGRADATION: 300,  # 5分钟
    AlertType.MEMORY_OVERFLOW: 600,          # 10分钟
    AlertType.GPU_OVERHEAT: 120,             # 2分钟(需要快速响应)
    AlertType.ERROR_RATE_HIGH: 300,          # 5分钟
    AlertType.THROUGHPUT_DROP: 300,          # 5分钟
    AlertType.SYSTEM_STABLE: 600,            # 10分钟
}


@dataclass
class AlertRule:
    """告警规则"""
    name: str                           # 规则名称
    alert_type: AlertType               # 告警类型
    level: AlertLevel                   # 告警级别
    condition: Callable[[Dict], bool]  # 条件函数
    message: str                        # 告警消息
    cooldown: Optional[int] = None      # 冷却时间(秒),None表示使用默认值
    enabled: bool = True                # 是否启用
    
    def get_cooldown(self) -> int:
        """获取冷却时间
        
        Returns:
            冷却时间(秒)
        """
        if self.cooldown is not None:
            return self.cooldown
        return DEFAULT_COOLDOWNS.get(self.alert_type, 300)


@dataclass
class AlertRecord:
    """告警记录"""
    timestamp: str                      # 时间戳
    alert_type: AlertType               # 告警类型
    level: AlertLevel                   # 告警级别
    message: str                        # 告警消息
    metrics: Dict[str, Any]             # 触发时的指标数据
    resolved: bool = False              # 是否已解决
    resolved_at: Optional[str] = None   # 解决时间


class AlertSystem:
    """性能监控告警系统
    
    功能:
    - 实时监控GPU性能指标
    - 自动检测异常情况
    - 触发告警通知
    - 记录告警历史
    - 支持告警恢复检测
    
    使用示例:
        alert_system = AlertSystem()
        alert_system.setup_default_rules()
        
        # 检查性能指标
        alert_system.check_metrics({
            'throughput': 1000000,
            'memory_usage': 0.75,
            'gpu_temperature': 80,
            'error_rate': 0.01
        })
    """
    
    def __init__(self, alert_log_file: Optional[str] = None) -> None:
        """初始化告警系统
        
        Args:
            alert_log_file: 告警日志文件路径
        """
        self.rules: List[AlertRule] = []
        self.alert_history: List[AlertRecord] = []
        self.last_alert_time: Dict[str, float] = {}  # 规则名称 -> 最后告警时间
        self.alert_callbacks: List[Callable] = []     # 告警回调函数
        
        # #11修复: 增强的速率限制
        self._global_rate_limit_max = 10  # 每分钟最多10条告警
        self._global_rate_limit_window = 60  # 时间窗口60秒
        self._recent_alerts: List[float] = []  # 最近的告警时间戳列表
        self._rate_limit_exceeded_count = 0  # 速率限制触发次数
        
        # 告警日志文件
        if alert_log_file is None:
            alert_log_file = "data_logs/alert_history.json"
        self.alert_log_file = Path(alert_log_file)
        self.alert_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载历史告警
        self._load_alert_history()
        
        logger.info(f"告警系统初始化完成: {len(self.rules)} 条规则")
    
    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则
        
        Args:
            rule: 告警规则对象
        """
        self.rules.append(rule)
        logger.info(f"添加告警规则: {rule.name} ({rule.level.value})")
    
    def remove_rule(self, rule_name: str) -> bool:
        """移除告警规则
        
        Args:
            rule_name: 规则名称
            
        Returns:
            是否成功移除
        """
        initial_count = len(self.rules)
        self.rules = [r for r in self.rules if r.name != rule_name]
        removed = len(self.rules) < initial_count
        
        if removed:
            logger.info(f"移除告警规则: {rule_name}")
        
        return removed
    
    def add_alert_callback(self, callback: Callable) -> None:
        """添加告警回调函数
        
        Args:
            callback: 回调函数,接收AlertRecord参数
        """
        self.alert_callbacks.append(callback)
        logger.info(f"添加告警回调函数")
    
    def setup_default_rules(self) -> None:
        """设置默认告警规则"""
        
        # 规则1: 性能退化>20%
        def check_performance_degradation(metrics: Dict) -> bool:
            if 'degradation_rate' not in metrics:
                return False
            return metrics['degradation_rate'] > 20.0  # type: ignore[no-any-return]
        
        self.add_rule(AlertRule(
            name="性能退化警告",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            condition=check_performance_degradation,
            message="GPU性能退化超过20%",
            cooldown=300
        ))
        
        # 规则2: 内存使用>80%
        def check_memory_usage(metrics: Dict) -> bool:
            if 'memory_usage_percent' not in metrics:
                return False
            return metrics['memory_usage_percent'] > 80.0  # type: ignore[no-any-return]
        
        self.add_rule(AlertRule(
            name="内存使用过高",
            alert_type=AlertType.MEMORY_OVERFLOW,
            level=AlertLevel.WARNING,
            condition=check_memory_usage,
            message="GPU内存使用超过80%",
            cooldown=600
        ))
        
        # 规则3: GPU温度>85°C
        def check_gpu_temperature(metrics: Dict) -> bool:
            if 'gpu_temperature' not in metrics:
                return False
            return metrics['gpu_temperature'] > 85.0  # type: ignore[no-any-return]
        
        self.add_rule(AlertRule(
            name="GPU温度过高",
            alert_type=AlertType.GPU_OVERHEAT,
            level=AlertLevel.CRITICAL,
            condition=check_gpu_temperature,
            message="GPU温度超过85°C",
            cooldown=120
        ))
        
        # 规则4: 错误率>5%
        def check_error_rate(metrics: Dict) -> bool:
            if 'error_rate' not in metrics:
                return False
            return metrics['error_rate'] > 0.05  # type: ignore[no-any-return]
        
        self.add_rule(AlertRule(
            name="错误率过高",
            alert_type=AlertType.ERROR_RATE_HIGH,
            level=AlertLevel.CRITICAL,
            condition=check_error_rate,
            message="错误率超过5%",
            cooldown=300
        ))
        
        # 规则5: 吞吐量下降>50%
        def check_throughput_drop(metrics: Dict) -> bool:
            if 'throughput' not in metrics or 'baseline_throughput' not in metrics:
                return False
            if metrics['baseline_throughput'] == 0:
                return False
            drop_rate = (metrics['baseline_throughput'] - metrics['throughput']) / metrics['baseline_throughput']
            return drop_rate > 0.5  # type: ignore[no-any-return]
        
        self.add_rule(AlertRule(
            name="吞吐量严重下降",
            alert_type=AlertType.THROUGHPUT_DROP,
            level=AlertLevel.CRITICAL,
            condition=check_throughput_drop,
            message="吞吐量下降超过50%",
            cooldown=300
        ))
        
        logger.info(f"默认告警规则设置完成: {len(self.rules)} 条规则")
    
    def check_metrics(self, metrics: Dict[str, Any]) -> List[AlertRecord]:
        """检查性能指标并触发告警
        
        Args:
            metrics: 性能指标字典
                - throughput: 当前吞吐量 (keys/s)
                - peak_throughput: 峰值吞吐量 (keys/s)
                - degradation_rate: 性能退化率 (%)
                - memory_usage_percent: 内存使用百分比 (%)
                - gpu_temperature: GPU温度 (°C)
                - error_rate: 错误率 (0-1)
                - baseline_throughput: 基准吞吐量 (keys/s)
        
        Returns:
            触发的告警记录列表
        """
        triggered_alerts: List[AlertRecord] = []
        current_time = time.time()
        
        # #11修复: 检查全局速率限制
        if not self._check_global_rate_limit(current_time):
            logger.warning(
                f"告警速率限制触发: 已发送{self._global_rate_limit_max}条告警，"
                f"将在{self._global_rate_limit_window}秒窗口后重置"
            )
            self._rate_limit_exceeded_count += 1
            return triggered_alerts
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            last_time = self.last_alert_time.get(rule.name, 0)
            cooldown = rule.get_cooldown()
            if current_time - last_time < cooldown:
                continue
            
            # 检查条件
            try:
                if rule.condition(metrics):
                    # 创建告警记录
                    alert = AlertRecord(
                        timestamp=datetime.now().isoformat(),
                        alert_type=rule.alert_type,
                        level=rule.level,
                        message=rule.message,
                        metrics=metrics.copy()
                    )
                    
                    # 检查是否是重复告警
                    if self._is_duplicate_alert(alert):
                        logger.debug(f"忽略重复告警: {rule.name}")
                        continue
                    
                    # 记录告警
                    self.alert_history.append(alert)
                    self.last_alert_time[rule.name] = current_time
                    
                    # #11修复: 记录到全局速率限制
                    self._recent_alerts.append(current_time)
                    
                    # 触发告警
                    self._trigger_alert(alert)
                    triggered_alerts.append(alert)
                    
                    logger.warning(f"⚠️ 告警触发 [{rule.level.value.upper()}]: {rule.message}")
                    
            except Exception as e:
                logger.error(f"检查告警规则 {rule.name} 时出错: {e}")
        
        return triggered_alerts
    
    def _check_global_rate_limit(self, current_time: float) -> bool:
        """检查全局速率限制（#11修复）
        
        防止告警泛滥，限制单位时间内的告警数量。
        
        Args:
            current_time: 当前时间戳
        
        Returns:
            True表示允许发送告警，False表示超过限制
        """
        # 清理过期的告警记录
        window_start = current_time - self._global_rate_limit_window
        self._recent_alerts = [
            t for t in self._recent_alerts if t > window_start
        ]
        
        # 检查是否超过限制
        return len(self._recent_alerts) < self._global_rate_limit_max
    
    def get_rate_limit_stats(self) -> dict:
        """获取速率限制统计"""
        current_time = time.time()
        window_start = current_time - self._global_rate_limit_window
        recent_count = len([t for t in self._recent_alerts if t > window_start])
        
        return {
            'recent_alerts': recent_count,
            'max_alerts_per_window': self._global_rate_limit_max,
            'window_seconds': self._global_rate_limit_window,
            'rate_limit_exceeded_count': self._rate_limit_exceeded_count,
            'can_send_more': recent_count < self._global_rate_limit_max
        }
    
    def _is_duplicate_alert(self, alert: AlertRecord, lookback: int = ALERT_DEDUP_LOOKBACK) -> bool:
        """检查是否是重复告警
        
        Args:
            alert: 当前告警
            lookback: 回溯检查的告警数量
            
        Returns:
            是否是重复告警
        """
        # 获取最近的告警
        recent_alerts = self.alert_history[-lookback:]
        
        for recent in recent_alerts:
            # 如果类型和消息相同,且未解决,则认为是重复
            if (recent.alert_type == alert.alert_type and 
                recent.message == alert.message and 
                not recent.resolved):
                return True
        
        return False
    
    def _trigger_alert(self, alert: AlertRecord):
        """触发告警
        
        Args:
            alert: 告警记录
        """
        # 调用所有回调函数
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"告警回调函数执行失败: {e}")
        
        # 保存告警历史
        self._save_alert_history()
    
    def resolve_alert(self, alert_index: int) -> None:
        """标记告警已解决
        
        Args:
            alert_index: 告警记录索引
        """
        if 0 <= alert_index < len(self.alert_history):
            alert = self.alert_history[alert_index]
            alert.resolved = True
            alert.resolved_at = datetime.now().isoformat()
            logger.info(f"告警已解决: {alert.message}")
            self._save_alert_history()
    
    def get_active_alerts(self) -> List[AlertRecord]:
        """获取未解决的告警
        
        Returns:
            未解决的告警记录列表
        """
        return [a for a in self.alert_history if not a.resolved]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """获取告警统计信息
        
        Returns:
            统计信息字典
        """
        stats: Dict[str, Any] = {
            'total_alerts': len(self.alert_history),
            'active_alerts': len(self.get_active_alerts()),
            'resolved_alerts': sum(1 for a in self.alert_history if a.resolved),
            'alerts_by_level': {},
            'alerts_by_type': {},
            'recent_alerts': []
        }
        
        # 按级别统计
        for alert in self.alert_history:
            level = alert.level.value
            stats['alerts_by_level'][level] = stats['alerts_by_level'].get(level, 0) + 1
            
            alert_type = alert.alert_type.value
            stats['alerts_by_type'][alert_type] = stats['alerts_by_type'].get(alert_type, 0) + 1
        
        # 最近10条告警
        stats['recent_alerts'] = [
            {
                'timestamp': a.timestamp,
                'level': a.level.value,
                'type': a.alert_type.value,
                'message': a.message,
                'resolved': a.resolved
            }
            for a in self.alert_history[-10:]
        ]
        
        return stats
    
    def _save_alert_history(self, max_records: int = MAX_ALERT_HISTORY):
        """保存告警历史到文件
        
        Args:
            max_records: 最大保存记录数,避免文件过大
        """
        try:
            # 只保存最近的记录,避免文件过大
            recent_history = self.alert_history[-max_records:]
            
            data = []
            for alert in recent_history:
                data.append({
                    'timestamp': alert.timestamp,
                    'alert_type': alert.alert_type.value,
                    'level': alert.level.value,
                    'message': alert.message,
                    'metrics': alert.metrics,
                    'resolved': alert.resolved,
                    'resolved_at': alert.resolved_at
                })
            
            with open(self.alert_log_file, 'w', encoding='utf-8') as f:
                fast_dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"保存告警历史失败: {e}")
    
    def _load_alert_history(self):
        """从文件加载告警历史"""
        if not self.alert_log_file.exists():
            return
        
        try:
            with open(self.alert_log_file, 'r', encoding='utf-8') as f:
                data = fast_load(f)
            
            for item in data:
                alert = AlertRecord(
                    timestamp=item['timestamp'],
                    alert_type=AlertType(item['alert_type']),
                    level=AlertLevel(item['level']),
                    message=item['message'],
                    metrics=item.get('metrics', {}),
                    resolved=item.get('resolved', False),
                    resolved_at=item.get('resolved_at')
                )
                self.alert_history.append(alert)
            
            logger.info(f"加载告警历史: {len(self.alert_history)} 条记录")
            
        except Exception as e:
            logger.error(f"加载告警历史失败: {e}")
    
    def clear_history(self) -> None:
        """清空告警历史"""
        self.alert_history.clear()
        self.last_alert_time.clear()
        self._save_alert_history()
        logger.info("告警历史已清空")


# 全局告警系统实例
_alert_system: Optional[AlertSystem] = None


def get_alert_system() -> AlertSystem:
    """获取全局告警系统实例
    
    Returns:
        AlertSystem实例
    """
    global _alert_system
    if _alert_system is None:
        _alert_system = AlertSystem()
        _alert_system.setup_default_rules()
    return _alert_system
