"""趋势分析共享工具

从 monitoring_system.py 和 data_logger.py 中提取的重复趋势计算逻辑，
提供统一的线性回归趋势分析函数。

原位置:
- monitoring_system.py: MonitoringSystem._calculate_trend() (static method)
- data_logger.py: DataLogger._analyze_trends() 内的 calculate_trend() (inner function)

提取原因: 两处实现完全相同（线性回归 + 2% 阈值），违反 DRY 原则。
"""

import logging
import statistics
from typing import Any

logger = logging.getLogger(__name__)

# 趋势判断的归一化斜率阈值 (2%)
_TREND_SLOPE_THRESHOLD = 0.02


def calculate_trend(values: list[float]) -> str:
    """使用线性回归计算趋势方向（共享工具函数）

    使用归一化斜率与 2% 阈值比较来判断趋势。
    需要至少 3 个数据点才能进行有效的线性回归。

    Args:
        values: 数值列表（时间序列）

    Returns:
        趋势字符串："increasing", "decreasing", 或 "stable"
    """
    if len(values) < 3:
        return "stable"

    try:
        # 简单线性回归: y = mx + b
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * v for i, v in enumerate(values))
        x2_sum = sum(i * i for i in range(n))

        # 计算斜率
        denominator = n * x2_sum - x_sum * x_sum
        if denominator == 0:
            return "stable"

        slope = (n * xy_sum - x_sum * y_sum) / denominator
        avg = y_sum / n

        # 避免除零
        if avg == 0:
            return "stable"

        # 归一化斜率（相对变化率）
        normalized_slope = slope / abs(avg)

        if normalized_slope > _TREND_SLOPE_THRESHOLD:
            return "increasing"
        elif normalized_slope < -_TREND_SLOPE_THRESHOLD:
            return "decreasing"
        else:
            return "stable"

    except (TypeError, OverflowError) as e:
        # 如果输入数据异常或数值溢出，降级为简单比较
        logger.debug(f"线性回归计算失败，使用简单比较: {e}")
        if len(values) < 2:
            return "stable"

        first_half_avg = statistics.mean(values[: len(values) // 2])
        second_half_avg = statistics.mean(values[len(values) // 2 :])

        if second_half_avg > first_half_avg * 1.05:
            return "increasing"
        elif second_half_avg < first_half_avg * 0.95:
            return "decreasing"
        else:
            return "stable"


def extract_metrics(data: list[dict[str, Any]]) -> tuple[list[float], list[float], list[float]]:
    """从监控数据中一次遍历提取 speed/cpu/memory 指标（共享工具函数）

    原 data_logger.py 和 monitoring_system.py 中有重复的"单次遍历提取字段"逻辑。

    Args:
        data: 监控数据列表，每项包含 "speed"/"cpu_usage"/"memory_usage" 字段

    Returns:
        (speeds, cpu_usages, memory_usages) 三元组
    """
    speeds: list[float] = []
    cpu_usages: list[float] = []
    memory_usages: list[float] = []

    for d in data:
        speeds.append(float(d.get("speed", 0)))
        cpu_usages.append(float(d.get("cpu_usage", 0)))
        memory_usages.append(float(d.get("memory_usage", 0)))

    return speeds, cpu_usages, memory_usages
