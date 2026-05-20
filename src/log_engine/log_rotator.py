#!/usr/bin/env python3
"""
日志轮转器

提供基于时间和数量的日志轮转功能，自动清理过期和超量记录。
"""

import time
from typing import Any


class LogRotator:
    """日志轮转器

    提供通用的日志记录轮转/过期机制：
    - 按时间过期：移除超过 N 天的记录
    - 按数量限制：保留最近 N 条记录
    - 自动清理：在写入时自动检查并清理过期记录

    使用示例：
        rotator = LogRotator(max_age_days=7, max_count=1000)
        cleaned = rotator.rotate(existing_records)
    """

    def __init__(self, max_age_days: int = 7, max_count: int = 1000):
        self.max_age_days = max_age_days
        self.max_count = max_count

    def rotate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """对记录列表执行轮转清理

        先按时间过滤过期记录，再按数量截断保留最新记录。

        Args:
            records: 原始记录列表，每条记录需包含 'timestamp' 字段

        Returns:
            清理后的记录列表
        """
        if not records:
            return records

        result = self._filter_by_age(records)
        result = self._filter_by_count(result)
        return result

    def _filter_by_age(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按时间过滤：移除超过 max_age_days 天的记录"""
        if self.max_age_days <= 0:
            return records

        cutoff = time.time() - (self.max_age_days * 86400)
        return [r for r in records if self._get_timestamp(r) >= cutoff]

    def _filter_by_count(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按数量限制：保留最近 max_count 条记录"""
        if self.max_count <= 0 or len(records) <= self.max_count:
            return records

        return records[-self.max_count :]

    @staticmethod
    def _get_timestamp(record: dict[str, Any]) -> float:
        """从记录中提取时间戳

        支持 float 和 ISO 字符串两种格式。
        """
        ts = record.get("timestamp", 0)
        if isinstance(ts, (int, float)):
            return float(ts)
        if isinstance(ts, str):
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(ts)
                return dt.timestamp()
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    def get_rotation_stats(
        self, before: list[dict[str, Any]], after: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """获取轮转统计信息

        Args:
            before: 轮转前记录列表
            after: 轮转后记录列表

        Returns:
            统计信息字典
        """
        removed = len(before) - len(after)
        return {
            "before_count": len(before),
            "after_count": len(after),
            "removed_count": removed,
            "max_age_days": self.max_age_days,
            "max_count": self.max_count,
        }
