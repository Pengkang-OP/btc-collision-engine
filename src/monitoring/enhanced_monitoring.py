"""Enhanced monitoring with advanced metrics tracking."""

import logging
import threading
from contextlib import suppress
from typing import Any

from src.monitoring.data_logger import DataLogger
from src.monitoring.monitor_config import MonitorConfig

logger = logging.getLogger(__name__)


class EnhancedMonitoringSystem:
    """Enhanced monitoring with detailed metrics tracking.

    Extends basic monitoring with throughput histograms, match rate
    analysis, and resource usage tracking.
    """

    def __init__(self, engine=None, config=None):
        self._engine = engine
        self._config = config if config is not None else MonitorConfig()
        self._lock = threading.Lock()
        self._metrics: dict[str, list[float]] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Extract config attributes for direct access
        # Support both MonitorConfig objects and dicts
        if isinstance(config, dict):
            self.collection_interval = config.get("collection_interval", 5)
            self.enable_monitoring_data = config.get("enable_monitoring_data", True)
            self.data_logging_enabled = config.get("data_logging_enabled", True)
        else:
            self.collection_interval = getattr(config, "collection_interval", 5)
            self.enable_monitoring_data = getattr(config, "enable_monitoring_data", True)
            self.data_logging_enabled = getattr(config, "data_logging_enabled", True)

        # Create data logger when data logging is enabled
        if self.data_logging_enabled:
            self.data_logger = DataLogger()
        else:
            self.data_logger = None

        # Monitoring data components (created when enable_monitoring_data=True)
        self.storage = None
        self.detector = None
        self.alert_system = None
        self.report_generator = None

        if self.enable_monitoring_data:
            self._init_monitoring_components()

        # Validate configuration
        self._validate_config()

        logger.info("增强版监控系统初始化完成")

    def _validate_config(self) -> bool:
        """Validate monitoring configuration.

        Returns:
            True if config is valid, False otherwise.

        """
        config = self._config
        valid = True

        if isinstance(config, MonitorConfig):
            # Validate alert_threshold range (0.0 - 1.0)
            if hasattr(config, "alert_threshold"):
                threshold = config.alert_threshold
                if not (0.0 <= threshold <= 1.0):
                    logger.warning(
                        "配置验证失败: alert_threshold=%s 超出范围 [0.0, 1.0]，使用默认值 0.8",
                        threshold,
                    )
                    valid = False

            # Validate collection_interval positive
            if hasattr(config, "collection_interval"):
                interval = config.collection_interval
                if interval <= 0:
                    logger.warning(
                        "配置验证失败: collection_interval=%s 必须为正数",
                        interval,
                    )
                    valid = False

        return valid

    def _init_monitoring_components(self):
        """Initialize monitoring data components."""
        self.storage = {}
        self.detector = {}
        self.alert_system = {}
        self.report_generator = {}

    @property
    def config(self):
        """Get the monitoring configuration."""
        return self._config

    @property
    def engine(self):
        """Get the engine instance."""
        return self._engine

    @engine.setter
    def engine(self, value):
        """Set the engine instance."""
        self._engine = value

    def is_running(self) -> bool:
        """Check if monitoring system is running."""
        return self._running

    def start(self) -> None:
        """Start the monitoring system.

        Launches a background thread that periodically collects
        performance, engine, and system data.
        """
        if self._running:
            logger.warning("监控系统已在运行中")
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._monitoring_loop,
            name="EnhancedMonitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("增强版监控系统已启动")

    def _monitoring_loop(self) -> None:
        """Background monitoring loop.

        Periodically collects performance data, engine state,
        and system information.
        """
        while not self._stop_event.is_set():
            try:
                self._collect_data()
            except Exception as e:
                logger.warning("监控数据采集异常: %s", e)

            self._stop_event.wait(timeout=self.collection_interval)

    def _collect_data(self) -> None:
        """Collect monitoring data from engine and system."""
        if not self.data_logger:
            return

        # Collect engine data
        engine = self._engine
        if engine is not None:
            try:
                stats = None
                if hasattr(engine, "get_stats"):
                    stats = engine.get_stats()

                if stats is not None:
                    speed = (
                        getattr(stats, "speed", 0)
                        if not isinstance(stats, dict)
                        else stats.get("speed", 0)
                    )
                    total_checked = (
                        getattr(stats, "total_checked", 0)
                        if not isinstance(stats, dict)
                        else stats.get("total_checked", 0)
                    )
                    matches = (
                        getattr(stats, "matches", [])
                        if not isinstance(stats, dict)
                        else stats.get("matches", [])
                    )

                    self.data_logger.record_performance_data(
                        speed=float(speed),
                        total_checked=int(total_checked),
                        matches_found=len(matches),
                    )

                mode = getattr(engine, "_current_mode", "")
                targets: set = getattr(engine, "targets", set())
                position = getattr(engine, "_current_position", 0)

                self.data_logger.record_engine_data(
                    mode=str(mode),
                    target_count=len(targets) if targets else 0,
                    is_running=engine.is_running() if hasattr(engine, "is_running") else False,
                    current_position=int(position),
                )
            except Exception as e:
                logger.debug("采集引擎数据异常: %s", e)

        # Collect system data
        try:
            self.data_logger.record_system_data()
        except Exception as e:
            logger.debug("采集系统数据异常: %s", e)

    def stop(self) -> None:
        """Stop the monitoring system and clean up resources.

        Safely shuts down the background thread and data logger.
        This method is idempotent - calling it multiple times is safe.
        """
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("监控线程未在 5s 内退出")
        self._thread = None

        with self._lock:
            with suppress(Exception):
                if self.data_logger is not None:
                    self.data_logger.stop()
            self._metrics.clear()

        logger.info("增强版监控系统已停止")

    def get_current_status(self) -> dict[str, Any]:
        """Get the current monitoring status.

        Returns:
            Dictionary with current status information.

        """
        status = {
            "running": self._running,
            "collection_interval": self.collection_interval,
            "data_logging": self.data_logger is not None,
            "monitoring_data": self.enable_monitoring_data,
        }

        if self.data_logger:
            try:
                stats = self.data_logger.get_statistics()
                status["stats"] = stats
            except Exception:
                pass

        return status

    def get_data_logger(self) -> DataLogger | None:
        """Get the data logger instance.

        Returns:
            DataLogger instance or None if not enabled.

        """
        return self.data_logger

    def record_metric(
        self,
        name: str,
        value: float,
    ) -> None:
        """Record a metric value.

        Args:
            name: Metric name
            value: Metric value

        """
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []
            self._metrics[name].append(value)
            if len(self._metrics[name]) > 10000:
                self._metrics[name] = self._metrics[name][-5000:]

    def get_average(
        self,
        name: str,
    ) -> float:
        """Get average value for a metric.

        Args:
            name: Metric name

        Returns:
            Average value or 0

        """
        with self._lock:
            values = self._metrics.get(name, [])
            if not values:
                return 0.0
            return sum(values) / len(values)
