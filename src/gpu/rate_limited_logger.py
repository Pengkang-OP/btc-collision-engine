"""频率限制日志记录器 (Task 8/11 refactor: 从 3 个文件中提取)

避免在高频循环中产生大量重复日志，每条消息在冷却期内只记录一次。

由 nvidia_optimizer.py、amd_optimizer.py、vendors/intel.py 共享使用。
"""

import os
import time
from typing import Any

_ENV_RATE_LIMIT_SEC = "GPU_LOG_RATE_LIMIT_SEC"
# backward compat: also check Intel-specific env var
_ENV_RATE_LIMIT_SEC_LEGACY = "INTEL_LOG_RATE_LIMIT_SEC"


class RateLimitedLogger:
    """频率限制日志记录器

    Attributes:
        base_logger: 基础 logger 实例
        min_interval: 相同消息的最小输出间隔（秒）

    """

    @staticmethod
    def _get_default_min_interval() -> float:
        """从环境变量读取默认限流间隔，异常时安全回退"""
        for env_var in (_ENV_RATE_LIMIT_SEC, _ENV_RATE_LIMIT_SEC_LEGACY):
            try:
                val = os.environ.get(env_var)
                if val is not None:
                    return float(val)
            except (ValueError, TypeError):
                continue
        return 60.0

    def __init__(
        self,
        base_logger: Any,
        min_interval: float | None = None,
    ) -> None:
        """Args:
        base_logger: 基础 logger 实例
        min_interval: 相同消息的最小输出间隔（秒），
                      默认从环境变量 GPU_LOG_RATE_LIMIT_SEC 读取，回退至 60s

        """
        self._logger = base_logger
        self._min_interval = (
            min_interval if min_interval is not None else self._get_default_min_interval()
        )
        self._last_logged: dict[str, float] = {}

    def _should_log(self, key: str) -> bool:
        now = time.monotonic()
        last = self._last_logged.get(key, 0.0)
        if now - last >= self._min_interval:
            self._last_logged[key] = now
            return True
        return False

    def warning(self, msg: str, key: str | None = None) -> None:
        """限频 warning 日志"""
        k = key or msg[:80]
        if self._should_log(k):
            self._logger.warning(msg)

    def info(self, msg: str, key: str | None = None) -> None:
        """限频 info 日志"""
        k = key or msg[:80]
        if self._should_log(k):
            self._logger.info(msg)

    def error(self, msg: str, key: str | None = None) -> None:
        """Error 级别不限流，始终输出"""
        self._logger.error(msg)

    def debug(self, msg: str) -> None:
        """Debug 级别不限流，始终输出"""
        self._logger.debug(msg)
