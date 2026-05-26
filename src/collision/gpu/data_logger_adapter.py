"""数据日志适配器

将现有 DataLogger 适配为 IMonitoringPipeline 期望的接口，
桥接 `log_performance()` / `flush()` / `get_stats()` 到
DataLogger 的实际 API (`record_performance_data()` 等)。

版本: v4.2.2 (Phase 3)
创建日期: 2026-04-30
"""

from contextlib import suppress
from typing import Any

from ...utils import get_configured_logger

logger = get_configured_logger(__name__)


class DataLoggerAdapter:
    """数据日志适配器

    将 DataLogger 的 record_performance_data() 接口适配为
    PerformanceMonitoringPipeline 期望的 log_performance() 接口。

    职责:
    - API 桥接: log_performance(dict) → record_performance_data(**kwargs)
    - 透传: flush(), get_statistics()
    - 无引擎时的独立 DataLogger 创建

    使用示例:
        >>> adapter = DataLoggerAdapter()
        >>> adapter.log_performance({"batch_size": 1000000, "execution_time_ms": 50.0})
        >>> adapter.flush()
        >>> stats = adapter.get_stats()
    """

    def __init__(
        self,
        engine: Any = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """初始化数据日志适配器

        Args:
            engine: 引擎实例。若引擎有 data_logger 属性则复用；
                    否则创建独立的 DataLogger。
            config: 配置字典

        """
        self.config = config or {}
        self._logger: Any = None
        self._owns_logger = False

        # 优先使用引擎已有的 DataLogger
        if engine and hasattr(engine, "data_logger") and engine.data_logger is not None:
            self._logger = engine.data_logger
            logger.debug("DataLoggerAdapter: 复用引擎的 DataLogger")
        else:
            # 创建独立的 DataLogger
            try:
                from ...monitoring.data_logger import DataLogger

                self._logger = DataLogger(storage_dir="data_logs")
                self._owns_logger = True
                logger.debug("DataLoggerAdapter: 创建独立 DataLogger")
            except Exception as e:
                logger.warning("创建 DataLogger 失败: %s", e)

    def log_performance(self, data: dict[str, Any]) -> None:
        """记录性能数据（桥接方法）

        将 dict 形式的性能数据映射到 DataLogger.record_performance_data()
        的参数签名。

        Args:
            data: 性能数据字典，支持以下键：
                - batch_size (int): 映射到 total_checked
                - execution_time_ms (float)
                - speed / keys_per_second (float): 映射到 speed
                - match_count / matches (int): 映射到 matches_found
                - gpu_errors (int)
                - timestamp (float)

        """
        if not self._logger:
            return

        try:
            # 将通用 dict 映射到 record_performance_data 签名
            speed = data.get("speed", data.get("keys_per_second", 0.0))
            total_checked = data.get("total_checked", data.get("batch_size", 0))
            matches_found = data.get(
                "match_count",
                data.get("matches_found", data.get("matches", 0)),
            )
            cpu_usage = data.get("cpu_usage", 0.0)
            memory_usage = data.get("memory_usage", 0.0)
            thread_count = data.get("thread_count", 0)

            self._logger.record_performance_data(
                speed=float(speed),
                total_checked=int(total_checked),
                matches_found=int(matches_found),
                cpu_usage=float(cpu_usage),
                memory_usage=float(memory_usage),
                thread_count=int(thread_count),
            )

            logger.debug(
                f"性能数据已记录: speed={speed:.0f}/s, checked={total_checked}, matches={matches_found}",
            )

        except Exception as e:
            logger.error("记录性能数据失败: %s", e)

    def flush(self) -> None:
        """刷写缓冲数据到磁盘"""
        if self._logger and hasattr(self._logger, "flush"):
            try:
                self._logger.flush()
                logger.debug("数据日志缓冲已刷写")
            except Exception as e:
                logger.error("刷写数据日志失败: %s", e)

    def get_stats(self) -> dict[str, Any]:
        """获取数据日志统计

        Returns:
            统计信息字典

        """
        if not self._logger:
            return {"status": "not_initialized"}

        try:
            if hasattr(self._logger, "get_statistics"):
                return self._logger.get_statistics()
            return {"status": "no_stats_method"}
        except Exception as e:
            logger.error("获取数据日志统计失败: %s", e)
            return {"status": "error", "message": str(e)}

    def save_current_data(self) -> None:
        """持久化当前数据到磁盘"""
        if self._logger and hasattr(self._logger, "save_current_data"):
            try:
                self._logger.save_current_data()
            except Exception as e:
                logger.error("保存当前数据失败: %s", e)

    def save_history_data(self) -> None:
        """持久化历史数据到磁盘"""
        if self._logger and hasattr(self._logger, "save_history_data"):
            try:
                self._logger.save_history_data()
            except Exception as e:
                logger.error("保存历史数据失败: %s", e)

    def cleanup(self) -> None:
        """清理资源

        仅当适配器自己创建了 DataLogger 时才清理。
        """
        if self._owns_logger and self._logger:
            with suppress(Exception):
                self._logger.flush()
            self._logger = None
            self._owns_logger = False
            logger.debug("DataLoggerAdapter: 独立 DataLogger 已清理")

    def is_available(self) -> bool:
        """检查数据日志是否可用

        Returns:
            DataLogger 已初始化时返回 True

        """
        return self._logger is not None

    def get_native_logger(self) -> Any:
        """获取底层 DataLogger 实例

        Returns:
            底层 DataLogger 实例，或 None

        """
        return self._logger
