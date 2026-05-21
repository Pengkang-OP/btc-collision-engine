#!/usr/bin/env python3
"""
日志存储器

负责日志的持久化存储。
"""

import json
import os
import threading
from collections import deque
from typing import Any


class LogStorage:
    """日志存储器

    负责日志的持久化存储，支持：
    - 文件存储
    - 内存缓存
    - 轮转机制
    """

    def __init__(
        self,
        storage_dir: str = "logs",
        max_file_size: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        """初始化存储器

        Args:
            storage_dir: 存储目录
            max_file_size: 单个文件最大大小（字节）
            backup_count: 保留的备份文件数量
        """
        self.storage_dir = storage_dir
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self._lock = threading.Lock()
        self._memory_buffer: deque[dict[str, Any]] = deque(maxlen=10000)
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """确保存储目录存在"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

    def save(self, event_data: dict[str, Any]) -> bool:
        """保存日志

        Args:
            event_data: 日志数据

        Returns:
            是否保存成功
        """
        try:
            # 保存到内存（持锁，避免并发变形 deque 迭代器）
            with self._lock:
                self._memory_buffer.append(event_data)

            # 保存到文件
            self._save_to_file(event_data)

            return True
        except (OSError, RuntimeError):
            return False

    def _save_to_file(self, event_data: dict[str, Any]):
        """保存到文件"""
        log_file = os.path.join(self.storage_dir, "wizard.log")

        # 检查文件大小并轮转（持锁，消除 TOCTOU 竞态）
        with self._lock:
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                if file_size >= self.max_file_size:
                    self._rotate_file(log_file)

        # 文件写入在锁外执行，避免阻塞读操作
        # JSON 行写入是安全的（每行完整写入 + 换行）
        with open(log_file, "a", encoding="utf-8") as f:
            json.dump(event_data, f, ensure_ascii=False)
            f.write("\n")

    def _rotate_file(self, filepath: str):
        """轮转文件"""
        # 删除最旧的备份
        oldest_backup = f"{filepath}.{self.backup_count}"
        if os.path.exists(oldest_backup):
            os.remove(oldest_backup)

        # 轮转现有备份
        for i in range(self.backup_count - 1, 0, -1):
            src = f"{filepath}.{i}"
            dst = f"{filepath}.{i + 1}"
            if os.path.exists(src):
                os.rename(src, dst)

        # 重命名当前文件
        os.rename(filepath, f"{filepath}.1")

    def save_batch(self, events_data: list[dict[str, Any]]) -> int:
        """批量保存

        Args:
            events_data: 日志数据列表

        Returns:
            成功保存的数量
        """
        success_count = 0
        for event_data in events_data:
            if self.save(event_data):
                success_count += 1
        return success_count

    def get_recent(self, count: int = 100) -> list[dict[str, Any]]:
        """获取最近的日志

        Args:
            count: 获取数量

        Returns:
            日志列表
        """
        with self._lock:
            buffer_list = list(self._memory_buffer)
            return buffer_list[-count:]

    def get_by_type(self, event_type: str, limit: int = 100) -> list[dict[str, Any]]:
        """按类型获取日志

        Args:
            event_type: 事件类型
            limit: 限制数量

        Returns:
            符合条件的日志列表
        """
        results = []
        with self._lock:
            buffer_snapshot = list(self._memory_buffer)
        for event_data in reversed(buffer_snapshot):
            if event_data.get("type") == event_type:
                results.append(event_data)
                if len(results) >= limit:
                    break
        return results

    def get_by_timerange(self, start_time: float, end_time: float) -> list[dict[str, Any]]:
        """按时间范围获取日志

        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳

        Returns:
            符合条件的日志列表
        """
        results = []
        with self._lock:
            buffer_snapshot = list(self._memory_buffer)
        for event_data in buffer_snapshot:
            timestamp = event_data.get("timestamp", 0)
            if start_time <= timestamp <= end_time:
                results.append(event_data)
        return results

    def search(self, keyword: str, case_sensitive: bool = False) -> list[dict[str, Any]]:
        """搜索日志

        Args:
            keyword: 搜索关键词
            case_sensitive: 是否区分大小写

        Returns:
            符合条件的日志列表
        """
        results = []
        keyword_to_find = keyword if case_sensitive else keyword.lower()

        with self._lock:
            buffer_snapshot = list(self._memory_buffer)
        for event_data in buffer_snapshot:
            message = str(event_data.get("message", ""))
            search_in = message if case_sensitive else message.lower()

            if keyword_to_find in search_in:
                results.append(event_data)

        return results

    def clear(self):
        """清空内存缓存"""
        with self._lock:
            self._memory_buffer.clear()

    def get_stats(self) -> dict[str, Any]:
        """获取存储统计

        Returns:
            统计信息字典
        """
        type_counts: dict[str, int] = {}
        with self._lock:
            buffer_snapshot = list(self._memory_buffer)
        for event_data in buffer_snapshot:
            event_type = event_data.get("type", "unknown")
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

        log_file = os.path.join(self.storage_dir, "wizard.log")
        file_size = 0
        if os.path.exists(log_file):
            file_size = os.path.getsize(log_file)

        return {
            "total_count": len(buffer_snapshot),
            "type_counts": type_counts,
            "file_size": file_size,
            "storage_dir": self.storage_dir,
        }

    def export_to_json(self, filepath: str, recent_only: bool = False) -> bool:
        """导出到JSON文件

        Args:
            filepath: 导出文件路径
            recent_only: 是否只导出最近的日志

        Returns:
            是否导出成功
        """
        try:
            # 通过持锁 snapshot 或 get_recent() 获取线程安全的数据副本
            if not recent_only:
                with self._lock:
                    data = list(self._memory_buffer)
            else:
                data = self.get_recent()

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except (OSError, RuntimeError):
            return False
