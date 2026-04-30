"""Intel GPU 自适应超时管理器

根据历史执行时间动态调整超时阈值，避免：
1. 固定超时导致的误判（正常执行被中断）
2. 过短超时的频繁触发
3. 过长超时的资源浪费

核心策略：
- 基于最近 N 次执行时间的统计
- 使用 3 倍标准差作为安全边际
- 设置上下限防止极端值
"""

import time
import logging
from ..utils import init_logging, get_configured_logger
import statistics
from typing import List, Optional, Dict, Any
from collections import deque

logger = get_configured_logger("IntelTimeoutManager")


class AdaptiveTimeoutManager:
    """自适应超时管理器
    
    根据 GPU 执行历史动态计算最优超时阈值。
    
    使用示例:
        >>> timeout_mgr = AdaptiveTimeoutManager(base_timeout=30)
        >>> # 记录执行时间
        >>> timeout_mgr.record_execution_time(150.5)
        >>> # 获取动态超时
        >>> timeout = timeout_mgr.get_timeout()
        >>> print(f"建议超时: {timeout:.1f}秒")
    """
    
    def __init__(
        self,
        base_timeout: float = 30.0,
        history_size: int = 50,
        safety_factor: float = 3.0,
        min_timeout: float = 10.0,
        max_timeout: float = 120.0
    ) -> None:
        """初始化自适应超时管理器
        
        Args:
            base_timeout: 基础超时时间（秒），用于数据不足时
            history_size: 历史记录保留数量
            safety_factor: 安全因子（标准差的倍数）
            min_timeout: 最小超时（秒）
            max_timeout: 最大超时（秒）
        """
        self.base_timeout = base_timeout
        self.history_size = history_size
        self.safety_factor = safety_factor
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout
        
        # 执行时间历史记录（毫秒）
        self._execution_times: deque[float] = deque(maxlen=history_size)
        
        # 统计信息
        self._total_records = 0
        self._timeout_adjustments = 0
        self._last_timeout = base_timeout
        
        logger.info(
            f"自适应超时管理器已初始化: "
            f"base={base_timeout}s, history={history_size}, "
            f"safety={safety_factor}x, range=[{min_timeout}s, {max_timeout}s]"
        )
    
    def record_execution_time(self, time_ms: float) -> None:
        """记录执行时间
        
        Args:
            time_ms: 执行时间（毫秒）
        """
        if time_ms < 0:
            logger.warning(f"忽略负的执行时间: {time_ms}")
            return
        
        if time_ms > 600000:  # 10 分钟
            logger.warning(f"执行时间异常长: {time_ms:.0f}ms，可能是 hang")
        
        self._execution_times.append(time_ms)
        self._total_records += 1
        
        logger.debug(
            f"记录执行时间: {time_ms:.0f}ms "
            f"(历史记录: {len(self._execution_times)})"
        )
    
    def get_timeout(self) -> float:
        """获取动态超时阈值
        
        计算策略:
        1. 数据不足（< 3 条）: 返回 base_timeout
        2. 数据充足: mean + safety_factor * std_dev
        3. 限制在 [min_timeout, max_timeout] 范围内
        
        Returns:
            超时时间（秒）
        """
        if len(self._execution_times) < 3:
            logger.debug(
                f"历史数据不足 ({len(self._execution_times)} < 3)，"
                f"使用基础超时: {self.base_timeout}s"
            )
            return self.base_timeout
        
        # 计算统计值
        times_list = list(self._execution_times)
        mean_time = statistics.mean(times_list)
        
        # 如果数据量足够，计算标准差
        if len(times_list) >= 10:
            std_dev = statistics.stdev(times_list)
        else:
            std_dev = statistics.pstdev(times_list)
        
        # 计算动态超时（mean + safety_factor * std_dev）
        dynamic_timeout_ms = mean_time + (self.safety_factor * std_dev)
        dynamic_timeout_sec = dynamic_timeout_ms / 1000.0
        
        # 限制在合理范围内
        final_timeout = float(max(self.min_timeout, min(dynamic_timeout_sec, self.max_timeout)))
        
        # 检查是否需要调整
        if abs(final_timeout - self._last_timeout) > 1.0:  # 变化超过 1 秒
            self._timeout_adjustments += 1
            logger.info(
                f"超时调整: {self._last_timeout:.1f}s -> {final_timeout:.1f}s "
                f"(mean={mean_time:.0f}ms, std={std_dev:.0f}ms, "
                f"n={len(times_list)})"
            )
            self._last_timeout = final_timeout
        
        return final_timeout
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            包含统计信息的字典
        """
        if not self._execution_times:
            return {
                "status": "no_data",
                "base_timeout": self.base_timeout,
                "current_timeout": self._last_timeout
            }
        
        times_list = list(self._execution_times)
        
        stats = {
            "status": "active",
            "total_records": self._total_records,
            "history_size": len(times_list),
            "base_timeout": self.base_timeout,
            "current_timeout": self._last_timeout,
            "mean_ms": statistics.mean(times_list),
            "median_ms": statistics.median(times_list),
            "min_ms": min(times_list),
            "max_ms": max(times_list),
            "std_dev_ms": statistics.stdev(times_list) if len(times_list) >= 10 else 0,
            "timeout_adjustments": self._timeout_adjustments
        }
        
        # 计算百分位数
        if len(times_list) >= 10:
            sorted_times = sorted(times_list)
            stats["p50_ms"] = sorted_times[int(len(sorted_times) * 0.5)]
            stats["p90_ms"] = sorted_times[int(len(sorted_times) * 0.9)]
            stats["p95_ms"] = sorted_times[int(len(sorted_times) * 0.95)]
            stats["p99_ms"] = sorted_times[int(len(sorted_times) * 0.99)]
        
        return stats
    
    def reset(self) -> None:
        """重置管理器状态"""
        self._execution_times.clear()
        self._total_records = 0
        self._timeout_adjustments = 0
        self._last_timeout = self.base_timeout
        logger.info("自适应超时管理器已重置")
    
    def should_warn(self, execution_time_ms: float) -> bool:
        """判断是否应该发出警告
        
        Args:
            execution_time_ms: 执行时间（毫秒）
            
        Returns:
            如果执行时间超过阈值返回 True
        """
        timeout_ms = self.get_timeout() * 1000
        return execution_time_ms > timeout_ms * 0.8  # 超过 80% 就警告
