#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控系统模块
"""

from .monitoring_system import (
    MonitoringSystem,
    DataCollector,
    DataStorage,
    AnomalyDetector,
    MonitoringAlertAdapter,
    ReportGenerator,
    MonitoringData,
)
from .data_logger import DataLogger
from .enhanced_monitoring import EnhancedMonitoringSystem

# P2-7: 多渠道通知
from .notification_channels import (
    NotificationChannel,
    ConsoleNotification,
    LogFileNotification,
    CompositeNotification,
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
    # P2-7: 通知渠道
    "NotificationChannel",
    "ConsoleNotification",
    "LogFileNotification",
    "CompositeNotification",
]
