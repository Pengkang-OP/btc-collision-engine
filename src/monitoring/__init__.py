#!/usr/bin/env python3
"""
监控系统模块
"""

from .data_logger import DataLogger
from .enhanced_monitoring import EnhancedMonitoringSystem
from .monitoring_system import (
    AnomalyDetector,
    DataCollector,
    DataStorage,
    MonitoringAlertAdapter,
    MonitoringData,
    MonitoringSystem,
    ReportGenerator,
)

# 多渠道通知
from .notification_channels import (
    CompositeNotification,
    ConsoleNotification,
    LogFileNotification,
    NotificationChannel,
)

# 向后兼容别名：MonitoringAlertAdapter 取代原本地 AlertSystem
AlertSystem = MonitoringAlertAdapter

__all__ = [
    "MonitoringSystem",
    "DataCollector",
    "DataStorage",
    "AnomalyDetector",
    "MonitoringAlertAdapter",
    "AlertSystem",  # 向后兼容别名
    "ReportGenerator",
    "MonitoringData",
    "DataLogger",
    "EnhancedMonitoringSystem",
    # 通知渠道
    "NotificationChannel",
    "ConsoleNotification",
    "LogFileNotification",
    "CompositeNotification",
]
