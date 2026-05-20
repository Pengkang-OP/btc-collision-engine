"""增量统计更新模块

通过增量更新机制减少锁竞争，提升并发性能。
"""

import threading
import time
from typing import Any, cast  # noqa: F811


class DeltaStats:
    """增量统计更新器

    使用批量更新策略减少锁竞争：
    - 多个线程可以并发写入增量队列
    - 定期批量刷新到主统计对象
    - 读操作直接读取主统计对象，不受写操作影响

    线程安全：
    - 增量队列为线程安全队列
    - 刷新操作使用独立锁
    """

    def __init__(self, flush_interval: float = 0.1) -> None:
        """
        Args:
            flush_interval: 自动刷新间隔（秒），默认0.1秒
        """
        # 停止标志（必须在启动线程前初始化）
        self._stop_event = threading.Event()

        # 主统计数据
        self._stats = {
            "total_checked": 0,
            "matches_found": 0,
            "gpu_errors": 0,
            "worker_errors": 0,
            "wif_encode_errors": 0,
            "resource_errors": 0,
            "elapsed_time": 0.0,
            "start_time": time.time(),
            "throughput": 0.0,
        }

        # 增量更新队列
        self._delta_queue: list[dict[str, Any]] = []
        self._delta_lock = threading.Lock()

        # 刷新线程
        self._flush_interval = flush_interval
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def queue_update(self, delta: dict[str, Any]) -> None:
        """将增量更新加入队列（非阻塞）"""
        with self._delta_lock:
            self._delta_queue.append(delta)

    def _flush_loop(self) -> None:
        """后台刷新循环"""
        while not self._stop_event.is_set():
            self._flush_updates()
            time.sleep(self._flush_interval)

    def _flush_updates(self) -> None:
        """批量刷新增量更新到主统计对象"""
        with self._delta_lock:
            updates = self._delta_queue
            self._delta_queue = []

        if not updates:
            return

        merged_delta: dict[str, int] = {}
        for update in updates:
            for key, value in update.items():
                merged_delta[key] = merged_delta.get(key, 0) + value

        with self._delta_lock:
            for key, value in merged_delta.items():
                if key in self._stats:
                    self._stats[key] += value

        self._update_derived_metrics()

    def _update_derived_metrics(self) -> None:
        """更新派生指标"""
        elapsed = time.time() - self._stats["start_time"]
        self._stats["elapsed_time"] = elapsed

        if elapsed > 0 and self._stats["total_checked"] > 0:
            self._stats["throughput"] = self._stats["total_checked"] / elapsed

    def get_stats(self) -> dict[str, Any]:
        """获取当前统计数据"""
        with self._delta_lock:
            return dict(self._stats)

    def reset(self) -> None:
        """重置统计数据"""
        with self._delta_lock:
            self._stats = {
                "total_checked": 0,
                "matches_found": 0,
                "gpu_errors": 0,
                "worker_errors": 0,
                "wif_encode_errors": 0,
                "resource_errors": 0,
                "elapsed_time": 0.0,
                "start_time": time.time(),
                "throughput": 0.0,
            }
            self._delta_queue = []

    def stop(self) -> None:
        """停止刷新线程"""
        self._stop_event.set()
        self._flush_thread.join(timeout=1.0)
        self._flush_updates()


class ThreadLocalDeltaStats:
    """线程本地增量统计器

    为每个线程维护独立的增量缓冲区，减少锁竞争。
    """

    def __init__(self) -> None:
        self._local = threading.local()
        self._global_stats = DeltaStats()

    def _get_thread_buffer(self) -> dict[str, int]:
        """获取当前线程的增量缓冲区"""
        if not hasattr(self._local, "buffer"):
            self._local.buffer = {
                "total_checked": 0,
                "matches_found": 0,
                "gpu_errors": 0,
                "worker_errors": 0,
            }
        return cast(dict[str, int], self._local.buffer)

    def add_check(self, count: int = 1) -> None:
        """记录检查数量（无锁操作）"""
        buffer = self._get_thread_buffer()
        buffer["total_checked"] += count

    def add_match(self) -> None:
        """记录匹配（无锁操作）"""
        buffer = self._get_thread_buffer()
        buffer["matches_found"] += 1

    def add_error(self, error_type: str) -> None:
        """记录错误（无锁操作）"""
        buffer = self._get_thread_buffer()
        if error_type in buffer:
            buffer[error_type] += 1

    def flush_to_global(self) -> None:
        """将线程缓冲区刷新到全局统计（需要锁）"""
        buffer = self._get_thread_buffer()
        if any(buffer.values()):
            self._global_stats.queue_update(dict(buffer))
            for key in buffer:
                buffer[key] = 0

    def get_global_stats(self) -> dict[str, Any]:
        """获取全局统计"""
        return self._global_stats.get_stats()

    def stop(self) -> None:
        """停止并刷新所有数据"""
        self._global_stats.stop()
