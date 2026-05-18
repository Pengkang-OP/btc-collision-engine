#!/usr/bin/env python3
"""
日志查询器

提供日志查询和检索功能。
"""

import json
import os
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any


class LogQuery:
    """日志查询器

    提供强大的日志查询和检索功能。
    """

    def __init__(self, storage_dir: str = "logs"):
        self.storage_dir = storage_dir
        self.log_file = os.path.join(storage_dir, "wizard.log")

    def query(
        self,
        event_type: str | None = None,
        source: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        keyword: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查询日志

        Args:
            event_type: 事件类型过滤
            source: 来源过滤
            start_time: 开始时间戳
            end_time: 结束时间戳
            keyword: 关键词搜索
            limit: 返回数量限制

        Returns:
            符合条件的日志列表
        """
        results: list[dict[str, Any]] = []

        if not os.path.exists(self.log_file):
            return results

        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                try:
                    event_data = json.loads(line.strip())

                    # 应用过滤条件
                    if event_type and event_data.get("type") != event_type:
                        continue

                    if source and event_data.get("source") != source:
                        continue

                    timestamp = event_data.get("timestamp", 0)
                    if start_time and timestamp < start_time:
                        continue
                    if end_time and timestamp > end_time:
                        continue

                    if keyword:
                        message = event_data.get("message", "").lower()
                        if keyword.lower() not in message:
                            continue

                    results.append(event_data)

                    if len(results) >= limit:
                        break

                except json.JSONDecodeError:
                    continue

        return results

    def get_recent(self, count: int = 50) -> list[dict[str, Any]]:
        """获取最近的日志

        Args:
            count: 数量

        Returns:
            日志列表
        """
        return self.query(limit=count)

    def get_by_type(self, event_type: str, limit: int = 100) -> list[dict[str, Any]]:
        """按类型获取日志

        Args:
            event_type: 事件类型
            limit: 限制数量

        Returns:
            日志列表
        """
        return self.query(event_type=event_type, limit=limit)

    def get_by_timerange(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """按时间范围获取

        Args:
            start: 开始时间
            end: 结束时间

        Returns:
            日志列表
        """
        return self.query(start_time=start.timestamp(), end_time=end.timestamp())

    def get_last_hour(self) -> list[dict[str, Any]]:
        """获取最近一小时的日志"""
        end = datetime.now()
        start = end - timedelta(hours=1)
        return self.get_by_timerange(start, end)

    def get_last_day(self) -> list[dict[str, Any]]:
        """获取最近一天的日志"""
        end = datetime.now()
        start = end - timedelta(days=1)
        return self.get_by_timerange(start, end)

    def search(
        self, keyword: str, case_sensitive: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        """搜索日志

        Args:
            keyword: 搜索关键词
            case_sensitive: 是否区分大小写
            limit: 限制数量

        Returns:
            符合条件的日志列表
        """
        return self.query(keyword=keyword, limit=limit)

    def count_by_type(self) -> dict[str, int]:
        """按类型统计数量

        Returns:
            类型计数字典
        """
        counts: defaultdict[str, int] = defaultdict(int)

        if not os.path.exists(self.log_file):
            return dict(counts)

        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                try:
                    event_data = json.loads(line.strip())
                    event_type = event_data.get("type", "unknown")
                    counts[event_type] += 1
                except json.JSONDecodeError:
                    continue

        return dict(counts)

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        counts = self.count_by_type()
        total = sum(counts.values())

        first_time = None
        last_time = None

        if os.path.exists(self.log_file):
            with open(self.log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        timestamp = event_data.get("timestamp")
                        if timestamp:
                            if first_time is None:
                                first_time = timestamp
                            last_time = timestamp
                    except json.JSONDecodeError:
                        continue

        return {
            "total_count": total,
            "type_counts": counts,
            "first_log_time": first_time,
            "last_log_time": last_time,
            "log_file": self.log_file,
            "log_file_exists": os.path.exists(self.log_file),
        }

    def tail(self, count: int = 10) -> list[dict[str, Any]]:
        """获取最后的日志（类似Unix tail）

        Args:
            count: 数量

        Returns:
            日志列表
        """
        return self.get_recent(count)

    def filter(
        self, predicate: Callable[[dict[str, Any]], bool], limit: int = 100
    ) -> list[dict[str, Any]]:
        """使用自定义函数过滤

        Args:
            predicate: 过滤函数
            limit: 限制数量

        Returns:
            符合条件的日志列表
        """
        results = []
        all_logs = self.get_recent(1000)

        for log in all_logs:
            if predicate(log):
                results.append(log)
                if len(results) >= limit:
                    break

        return results
