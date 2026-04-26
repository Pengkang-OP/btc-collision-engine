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
    MonitoringData
)
from .data_logger import DataLogger
from .enhanced_monitoring import EnhancedMonitoringSystem

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
    "EnhancedMonitoringSystem"
]
