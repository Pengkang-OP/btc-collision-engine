"""日志监控集成模块

将新开发的日志监控系统与现有监控框架集成，实现数据共享和统一管理。
"""

import logging
import threading
import time
from typing import Any

# 导入现有监控系统
from src.monitoring.data_logger import DataLogger
from src.monitoring.monitoring_system import MonitoringSystem

# 导入新开发的日志监控系统
from src.utils.log_collection_rules import get_matching_rules, get_rule_manager
from src.utils.log_dependency_manager import check_dependencies
from src.utils.log_performance_optimizer import get_log_stats, get_performance_optimizer
from src.utils.log_platform_adapter import get_platform_info


class LogMonitoringIntegrator:
    """日志监控集成器"""

    def __init__(self, storage_dir: str | None = None) -> None:
        """
        初始化日志监控集成器

        Args:
            storage_dir: 数据存储目录
        """
        # 初始化现有监控系统
        self.data_logger = DataLogger(storage_dir)

        # 初始化新的日志监控系统组件
        self.rule_manager = get_rule_manager()
        self.performance_optimizer = get_performance_optimizer()

        # 日志记录器
        self.logger = logging.getLogger("LogMonitoringIntegrator")

        # 数据共享缓冲区
        self._log_buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()

        # 集成状态
        self._initialized = False

    def initialize(self) -> None:
        """初始化集成器"""
        if not self._initialized:
            # 检查依赖
            dependencies = check_dependencies()
            self.logger.info(f"依赖状态: {dependencies}")

            # 获取平台信息
            platform_info = get_platform_info()
            self.logger.info(f"平台信息: {platform_info}")

            # 初始化完成
            self._initialized = True
            self.logger.info("日志监控集成器初始化完成")

    def log(self, module: str, level: str, message: str, **kwargs) -> None:
        """
        统一日志接口

        Args:
            module: 模块名称
            level: 日志级别
            message: 日志消息
            **kwargs: 额外信息
        """
        # 获取匹配的日志规则
        rules = get_matching_rules(module, level, message)

        # 应用日志规则
        for rule in rules:
            # 检查采样率
            if hasattr(rule, "sample_rate") and rule.sample_rate > 1:
                # 简单的采样逻辑（统计采样，非加密用途）
                import random

                if random.randint(1, rule.sample_rate) != 1:  # nosec B311
                    continue

            # 记录日志
            self._record_log(module, level, message, rule, **kwargs)

    def _record_log(self, module: str, level: str, message: str, rule: Any, **kwargs):
        """
        记录日志到各个系统

        Args:
            module: 模块名称
            level: 日志级别
            message: 日志消息
            rule: 日志规则
            **kwargs: 额外信息
        """
        # 记录到标准日志
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, f"[{module}] {message}")

        # 记录到数据日志系统
        if level.upper() in ["ERROR", "CRITICAL"]:
            self.data_logger.record_error(
                error_type=level.upper(),
                message=message,
                context={"module": module, "rule": rule.name, **kwargs},
            )
        elif level.upper() in ["INFO", "DEBUG"] and (
            "speed" in kwargs or "performance" in message.lower()
        ):
            # 记录性能数据（如果包含性能信息）
            speed = kwargs.get("speed", 0.0)
            total_checked = kwargs.get("total_checked", 0)
            matches_found = kwargs.get("matches_found", 0)
            cpu_usage = kwargs.get("cpu_usage", 0.0)
            memory_usage = kwargs.get("memory_usage", 0.0)
            thread_count = kwargs.get("thread_count", 0)

            self.data_logger.record_performance_data(
                speed=speed,
                total_checked=total_checked,
                matches_found=matches_found,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                thread_count=thread_count,
            )

        # 记录到共享缓冲区
        with self._lock:
            self._log_buffer.append(
                {
                    "timestamp": time.time(),
                    "module": module,
                    "level": level,
                    "message": message,
                    "rule": rule.name,
                    "context": kwargs,
                }
            )

            # 限制缓冲区大小
            if len(self._log_buffer) > 1000:
                self._log_buffer = self._log_buffer[-1000:]

    def get_log_stats(self) -> dict[str, Any]:
        """
        获取日志统计信息

        Returns:
            统计信息字典
        """
        # 获取性能优化器统计信息
        optimizer_stats = get_log_stats()

        # 获取规则管理器统计信息
        rule_stats = {
            "rule_count": len(self.rule_manager.get_rules()),
            "enabled_rules": len([r for r in self.rule_manager.get_rules() if r.enabled]),
        }

        # 获取缓冲区统计信息
        with self._lock:
            buffer_stats = {"buffer_size": len(self._log_buffer), "buffer_max_size": 1000}

        return {"optimizer": optimizer_stats, "rules": rule_stats, "buffer": buffer_stats}

    def get_recent_logs(self, count: int = 50) -> list[dict[str, Any]]:
        """
        获取最近的日志

        Args:
            count: 日志数量

        Returns:
            日志列表
        """
        with self._lock:
            return self._log_buffer[-count:]

    def flush(self) -> None:
        """
        刷新所有缓冲数据
        """
        # 刷新数据日志系统
        self.data_logger.flush()

        # 清空日志缓冲区
        with self._lock:
            self._log_buffer.clear()

        self.logger.info("日志监控集成器数据已刷新")

    def stop(self) -> None:
        """
        停止集成器
        """
        # 刷新数据
        self.flush()

        # 停止数据日志系统
        self.data_logger.stop()

        self.logger.info("日志监控集成器已停止")

    def integrate_with_monitoring_system(self, monitoring_system: MonitoringSystem) -> None:
        """
        与监控系统集成

        Args:
            monitoring_system: 监控系统实例
        """
        # 注册为监控系统的组件
        if hasattr(monitoring_system, "register_component"):
            monitoring_system.register_component("log_monitoring", self)

        # 定期同步日志数据到监控系统
        def sync_log_data() -> None:
            while True:
                try:
                    # 获取最近的日志
                    recent_logs = self.get_recent_logs(100)
                    if recent_logs:
                        # 同步到监控系统
                        for log in recent_logs:
                            if log["level"] in ["ERROR", "CRITICAL"]:
                                # 记录为错误
                                monitoring_system.storage.save_error(
                                    {
                                        "type": "log_error",
                                        "level": log["level"],
                                        "message": log["message"],
                                        "module": log["module"],
                                        "context": log["context"],
                                    }
                                )
                    time.sleep(10)  # 每10秒同步一次
                except Exception as e:
                    self.logger.error(f"同步日志数据失败: {e}")
                    time.sleep(30)  # 出错后等待更长时间

        # 启动同步线程
        sync_thread = threading.Thread(target=sync_log_data, daemon=True, name="LogSyncThread")
        sync_thread.start()

        self.logger.info("日志监控集成器已与监控系统集成")


# 全局集成器实例
_integrator: LogMonitoringIntegrator | None = None


def get_log_monitoring_integrator(storage_dir: str | None = None) -> LogMonitoringIntegrator:
    """
    获取日志监控集成器实例

    Args:
        storage_dir: 数据存储目录

    Returns:
        日志监控集成器实例
    """
    global _integrator
    if _integrator is None:
        _integrator = LogMonitoringIntegrator(storage_dir)
        _integrator.initialize()
    return _integrator


def init_log_monitoring_integration(storage_dir: str | None = None) -> None:
    """
    初始化日志监控集成

    Args:
        storage_dir: 数据存储目录
    """
    integrator = get_log_monitoring_integrator(storage_dir)
    integrator.initialize()


def log(module: str, level: str, message: str, **kwargs) -> None:
    """
    统一日志接口

    Args:
        module: 模块名称
        level: 日志级别
        message: 日志消息
        **kwargs: 额外信息
    """
    integrator = get_log_monitoring_integrator()
    integrator.log(module, level, message, **kwargs)


def get_integration_stats() -> dict[str, Any]:
    """
    获取集成统计信息

    Returns:
        统计信息字典
    """
    integrator = get_log_monitoring_integrator()
    return integrator.get_log_stats()


def flush_logs() -> None:
    """
    刷新日志数据
    """
    integrator = get_log_monitoring_integrator()
    integrator.flush()


def stop_log_monitoring() -> None:
    """
    停止日志监控
    """
    integrator = get_log_monitoring_integrator()
    integrator.stop()
