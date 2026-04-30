#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版监控系统

集成数据日志系统的监控系统，提供更全面的数据记录和监控功能。

P1-2修复: 使用MonitorConfig配置对象，解耦配置循环引用
"""

import os
import sys
import time
import threading
import logging
import json
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import psutil

# 导入现有模块
from src.utils import get_configured_logger
from src.monitoring.monitoring_system import (
    MonitoringSystem,
    DataCollector,
    DataStorage,
    AnomalyDetector,
    MonitoringAlertAdapter,
    ReportGenerator,
    MonitoringData,
)
from src.monitoring.data_logger import DataLogger

# P1-2修复：导入配置对象
from src.monitoring.monitor_config import MonitorConfig, DEFAULT_CONFIG


class EnhancedMonitoringSystem:
    """增强版监控系统 - 统一数据管理平台

    整合MonitoringSystem和DataLogger，提供：
    - 实时监控和异常检测
    - 数据持久化和报告生成
    - 统一的数据接口

    P1-2修复: 使用MonitorConfig配置对象，解耦配置循环引用

    Attributes:
        config: 监控配置对象
        engine: 对撞引擎实例
        data_logger: 数据日志记录器(可能为None)
        collection_interval: 数据采集间隔(秒)
        enable_monitoring_data: 是否启用监控数据采集
    """

    # 类属性类型提示
    config: MonitorConfig
    data_logger: Optional[Any]

    def __init__(
        self,
        engine: Optional[Any] = None,
        config: Optional[MonitorConfig] = None,
        collection_interval: Optional[float] = None,  # 已弃用，使用config
        enable_monitoring_data: Optional[bool] = None,  # 已弃用，使用config
    ) -> None:
        """
        初始化增强版监控系统

        Args:
            engine: 对撞引擎实例
            config: 监控配置对象（推荐）
            collection_interval: 数据采集间隔（秒）- 已弃用
            enable_monitoring_data: 是否同时保存到monitoring_data - 已弃用

        Example:
            >>> # 推荐方式：使用配置对象
            >>> from src.monitoring.monitor_config import MonitorConfig
            >>> config = MonitorConfig(
            ...     data_logging_enabled=True,
            ...     collection_interval=5.0
            ... )
            >>> monitoring = EnhancedMonitoringSystem(engine, config=config)
            >>>
            >>> # 兼容方式：使用旧参数
            >>> monitoring = EnhancedMonitoringSystem(
            ...     engine,
            ...     collection_interval=5,
            ...     enable_monitoring_data=False
            ... )
        """
        self.logger = get_configured_logger("EnhancedMonitoringSystem")
        self.engine = engine

        # P1-2修复：处理配置
        if config is not None:
            # 使用配置对象
            self.config = config
        else:
            # 兼容旧API：从参数构建配置
            self.config = MonitorConfig()

            if collection_interval is not None:
                self.config.collection_interval = float(collection_interval)

            if enable_monitoring_data is not None:
                self.config.enable_monitoring_data = enable_monitoring_data

        # 验证配置（添加异常处理）
        try:
            self.config.validate()
        except ValueError as e:
            self.logger.warning(f"配置验证失败: {e}, 使用默认配置")
            self.config = MonitorConfig()  # 回退到默认配置

        # 使用配置初始化
        self.collection_interval = self.config.collection_interval
        self.enable_monitoring_data = self.config.enable_monitoring_data

        # 数据日志系统（主数据源）
        if self.config.data_logging_enabled:
            # P1-2修复：DataLogger只接受storage_dir参数
            # config配置通过MonitorConfig管理，不直接传递给DataLogger
            self.data_logger = DataLogger(storage_dir="data_logs")
        else:
            self.data_logger = None

        # 可选：原始监控系统组件（用于实时监控和告警）
        self.storage: Optional[DataStorage] = None
        self.detector: Optional[AnomalyDetector] = None
        self.alert_system: Optional[MonitoringAlertAdapter] = None
        self.report_generator: Optional[ReportGenerator] = None
        self._collector: Optional[DataCollector] = None
        if self.config.enable_monitoring_data:
            self.storage = DataStorage()
            self.detector = AnomalyDetector(self.storage)
            self.alert_system = MonitoringAlertAdapter(self.storage)
            self.report_generator = ReportGenerator(self.storage, self.detector)
            # 创建长生命周期的 DataCollector，避免每轮循环重复创建导致线程泄漏
            self._collector = DataCollector(self.engine)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 报告生成控制（从配置读取）
        self._last_report_time: float = 0.0
        self._report_interval = self.config.report_interval

        self.logger.info(
            f"增强版监控系统初始化完成 "
            f"(monitoring_data={self.config.enable_monitoring_data}, "
            f"config={type(self.config).__name__})"
        )

    def start(self) -> None:
        """启动监控系统"""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        self.logger.info("增强版监控系统已启动")

    def stop(self) -> None:
        """停止监控系统"""
        if not self._running:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        # 清理 DataCollector，停止其后台 CPU 采样线程
        if hasattr(self, "_collector") and self._collector:
            try:
                self._collector.stop()
            except (TypeError, ValueError, KeyError) as e:
                self.logger.debug(f"DataCollector停止异常（可忽略）: {e}")
        self.logger.info("增强版监控系统已停止")

    def _monitoring_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                # 收集数据（从引擎直接获取）
                if self.data_logger and self.engine and hasattr(self.engine, "get_stats"):
                    stats = self.engine.get_stats()
                    if stats:
                        # 记录性能数据
                        self.data_logger.record_performance_data(
                            speed=stats.speed if hasattr(stats, "speed") else 0,
                            total_checked=(
                                stats.total_checked if hasattr(stats, "total_checked") else 0
                            ),
                            matches_found=len(stats.matches) if hasattr(stats, "matches") else 0,
                            cpu_usage=self._get_cpu_usage(),
                            memory_usage=self._get_memory_usage(),
                            thread_count=self._get_thread_count(),
                        )

                # 记录引擎数据
                if self.data_logger and self.engine:
                    self.data_logger.record_engine_data(
                        mode=getattr(self.engine, "_current_mode", ""),
                        target_count=len(getattr(self.engine, "targets", [])),
                        is_running=(
                            self.engine.is_running()
                            if hasattr(self.engine, "is_running")
                            else False
                        ),
                        current_position=getattr(self.engine, "_current_position", 0),
                    )

                # 记录系统数据
                if self.data_logger:
                    self.data_logger.record_system_data()

                # 如果使用monitoring_data，同时保存
                if self.enable_monitoring_data and self.storage and self._collector:
                    data = self._collector.collect_all_data()
                    self.storage.save_current_data(data)
                    self.storage.save_history_data(data)

                    # 检测异常
                    anomalies = self.detector.detect_anomalies(data)
                    if anomalies:
                        self.alert_system.process_anomalies(anomalies)

                # 控制报告生成频率（每小时最多一次）
                current_time = time.time()
                if current_time - self._last_report_time >= self._report_interval:
                    self._generate_reports()
                    self._last_report_time = current_time

                # 定期保存数据
                if self.data_logger:
                    self.data_logger.save_current_data()
                    self.data_logger.save_history_data()

            except OSError as e:
                # 文件系统相关错误（日志写入、数据保存等）
                self.logger.warning(f"监控系统文件系统错误: {e}")
                error_info = {"type": "monitoring", "message": f"监控系统文件系统错误: {str(e)}"}
                if self.enable_monitoring_data and self.storage:
                    try:
                        self.storage.save_error(error_info)
                    except OSError:
                        self.logger.debug("保存错误信息到存储失败（文件系统不可用）")
            except (TypeError, ValueError) as e:
                # 数据格式问题，通常是引擎返回数据结构变化
                self.logger.debug(f"监控系统数据格式异常（可忽略）: {e}")
            except Exception as e:
                error_info = {"type": "monitoring", "message": f"监控系统错误: {str(e)}"}

                # 保存到error_log
                if self.enable_monitoring_data and self.storage:
                    self.storage.save_error(error_info)

                # 同时记录到数据日志系统
                if self.data_logger:
                    self.data_logger.record_error(
                        error_type="monitoring_error",
                        message=f"监控系统错误: {str(e)}",
                        exception=e,
                    )
                self.logger.error(f"监控系统错误: {e}")

            # 等待下一次采集（可被 stop() 立即中断）
            self._stop_event.wait(self.collection_interval)

    def _save_to_data_logger(self, data: MonitoringData):
        """将数据保存到数据日志系统（已弃用，保留向后兼容）"""
        self.logger.warning("_save_to_data_logger已弃用，使用直接记录方式")
        if not self.data_logger:
            return

        try:
            # 记录性能数据
            perf = data.performance
            self.data_logger.record_performance_data(
                speed=perf.get("speed", 0),
                total_checked=perf.get("total_checked", 0),
                matches_found=perf.get("matches_found", 0),
                cpu_usage=perf.get("cpu_usage", 0),
                memory_usage=perf.get("memory_usage", 0),
                thread_count=perf.get("thread_count", 0),
            )

            # 记录系统数据
            sys_data = data.system
            self.data_logger.record_system_data(
                os_name=sys_data.get("os", ""),
                python_version=sys_data.get("python_version", ""),
                pid=sys_data.get("pid", 0),
                uptime=sys_data.get("uptime", 0),
            )

            # 记录引擎数据
            eng_data = data.engine
            self.data_logger.record_engine_data(
                mode=eng_data.get("mode", ""),
                target_count=eng_data.get("target_count", 0),
                is_running=eng_data.get("is_running", False),
                current_position=eng_data.get("current_position", 0),
            )

        except Exception as e:
            self.logger.error(f"保存到数据日志系统失败: {e}")

    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            process = psutil.Process(os.getpid())
            return process.cpu_percent(interval=0.1)  # type: ignore[no-any-return]
        except (TypeError, ValueError, KeyError):
            return 0.0

    def _get_memory_usage(self) -> float:
        """获取内存使用量(MB)"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # type: ignore[no-any-return]
        except (TypeError, ValueError, KeyError):
            return 0.0

    def _get_thread_count(self) -> int:
        """获取线程数"""
        try:
            process = psutil.Process(os.getpid())
            return len(process.threads())
        except (TypeError, ValueError, KeyError):
            return 0

    def _generate_reports(self):
        """生成报告（控制频率）"""
        try:
            # 生成数据日志报告
            if self.data_logger:
                self.data_logger.generate_report("daily")
                self.logger.info("每日报告已生成")

            # 如果启用monitoring_data，也生成原始报告
            if self.enable_monitoring_data and self.report_generator:
                self.report_generator.generate_daily_report()
                self.logger.info("监控系统报告已生成")
        except Exception as e:
            self.logger.error(f"生成报告失败: {e}")

    def is_running(self) -> bool:
        """检查监控系统是否运行"""
        return self._running

    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        if self.storage is None:
            return {"message": "监控数据未启用 (enable_monitoring_data=False)"}

        current_data = self.storage.get_current_data()
        if not current_data:
            return {"message": "暂无数据"}

        # 分析趋势
        history_data = self.storage.get_history_data()
        trends = self.detector.analyze_trends(history_data) if self.detector is not None else []

        # 获取告警历史
        alerts = self.alert_system.get_alert_history() if self.alert_system is not None else []

        # 获取数据日志统计
        data_stats = self.data_logger.get_statistics() if self.data_logger else {}

        return {
            "current_data": current_data,
            "trends": trends,
            "recent_alerts": alerts[-5:] if alerts else [],  # 最近5个告警
            "data_stats": data_stats,
        }

    def generate_report(self) -> Dict[str, Any]:
        """生成报告"""
        # 生成原始报告
        original_report = self.report_generator.generate_daily_report() if self.report_generator is not None else {}

        # 生成数据日志报告
        data_report = self.data_logger.generate_report("daily") if self.data_logger else {}

        return {"original_report": original_report, "data_report": data_report}

    def get_data_logger(self) -> DataLogger:
        """获取数据日志记录器"""
        return self.data_logger  # type: ignore[return-value]
