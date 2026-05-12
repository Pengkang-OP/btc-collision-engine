"""分布式统计聚合器

支持大规模多GPU场景下的统计数据聚合。
"""

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class WorkerStats:
    """工作器统计数据"""

    keys_checked: int = 0
    matches_found: int = 0
    throughput: float = 0.0
    elapsed_time: float = 0.0
    error_count: int = 0
    status: str = "idle"


class DistributedStatsAggregator:
    """分布式统计聚合器

    为每个GPU工作器维护独立的统计对象，支持动态注册和聚合。

    特性：
    - 支持任意数量GPU工作器的动态注册
    - 实时聚合所有工作器的统计数据
    - 支持按设备维度查询统计
    - 内置负载均衡感知
    """

    def __init__(self) -> None:
        # 停止标志（必须在启动线程前初始化）
        self._stop_event = threading.Event()

        # 工作器统计字典 {device_idx: WorkerStats}
        self._workers: dict[int, WorkerStats] = {}
        self._workers_lock = threading.RLock()

        # 聚合统计缓存
        self._aggregated_stats: dict[str, Any] = {}
        self._cache_valid = False
        self._cache_lock = threading.Lock()

        # 聚合线程
        self._aggregation_interval = 0.1
        self._aggregation_thread = threading.Thread(target=self._aggregation_loop, daemon=True)
        self._aggregation_thread.start()

    def register_worker(self, device_idx: int) -> None:
        """注册GPU工作器"""
        with self._workers_lock:
            if device_idx not in self._workers:
                self._workers[device_idx] = WorkerStats()
                self._cache_valid = False

    def unregister_worker(self, device_idx: int) -> None:
        """注销GPU工作器"""
        with self._workers_lock:
            if device_idx in self._workers:
                del self._workers[device_idx]
                self._cache_valid = False

    def update_worker_stats(self, device_idx: int, stats: dict[str, Any]) -> None:
        """更新工作器统计数据"""
        with self._workers_lock:
            if device_idx in self._workers:
                worker = self._workers[device_idx]
                if "keys_checked" in stats:
                    worker.keys_checked = stats["keys_checked"]
                if "matches_found" in stats:
                    worker.matches_found = stats["matches_found"]
                if "throughput" in stats:
                    worker.throughput = stats["throughput"]
                if "elapsed_time" in stats:
                    worker.elapsed_time = stats["elapsed_time"]
                if "error_count" in stats:
                    worker.error_count = stats["error_count"]
                if "status" in stats:
                    worker.status = stats["status"]
                self._cache_valid = False

    def _aggregation_loop(self) -> None:
        """后台聚合循环"""
        while not self._stop_event.is_set():
            self._aggregate_stats()
            time.sleep(self._aggregation_interval)

    def _aggregate_stats(self) -> None:
        """执行统计聚合"""
        with self._workers_lock:
            workers = dict(self._workers)

        if not workers:
            return

        total_keys = 0
        total_matches = 0
        total_throughput = 0.0
        total_errors = 0
        active_workers = 0

        for device_idx, worker in workers.items():
            total_keys += worker.keys_checked
            total_matches += worker.matches_found
            total_throughput += worker.throughput
            total_errors += worker.error_count
            if worker.status == "running":
                active_workers += 1

        avg_throughput = total_throughput / len(workers) if workers else 0.0

        with self._cache_lock:
            self._aggregated_stats = {
                "device_count": len(workers),
                "active_device_count": active_workers,
                "total_keys_checked": total_keys,
                "total_matches": total_matches,
                "combined_throughput": total_throughput,
                "average_throughput": avg_throughput,
                "total_errors": total_errors,
                "per_device": {
                    idx: {
                        "keys_checked": w.keys_checked,
                        "matches_found": w.matches_found,
                        "throughput": w.throughput,
                        "elapsed_time": w.elapsed_time,
                        "error_count": w.error_count,
                        "status": w.status,
                    }
                    for idx, w in workers.items()
                },
            }
            self._cache_valid = True

    def get_combined_stats(self) -> dict[str, Any]:
        """获取聚合统计数据"""
        if not self._cache_valid:
            self._aggregate_stats()

        with self._cache_lock:
            return dict(self._aggregated_stats)

    def get_device_stats(self, device_idx: int) -> dict[str, Any] | None:
        """获取指定设备的统计数据"""
        with self._workers_lock:
            worker = self._workers.get(device_idx)
            if worker:
                return {
                    "keys_checked": worker.keys_checked,
                    "matches_found": worker.matches_found,
                    "throughput": worker.throughput,
                    "elapsed_time": worker.elapsed_time,
                    "error_count": worker.error_count,
                    "status": worker.status,
                }
            return None

    def get_load_balance_info(self) -> dict[str, Any]:
        """获取负载均衡信息"""
        combined = self.get_combined_stats()
        per_device = combined.get("per_device", {})

        if not per_device:
            return {"balanced": True, "devices": []}

        avg_keys = (
            combined["total_keys_checked"] / len(per_device)
            if combined["total_keys_checked"] > 0
            else 0
        )
        max_deviation = 0

        devices_info = []
        for idx, stats in per_device.items():
            deviation = abs(stats["keys_checked"] - avg_keys) / max(avg_keys, 1) * 100
            max_deviation = max(max_deviation, deviation)
            devices_info.append(
                {
                    "device_idx": idx,
                    "keys_checked": stats["keys_checked"],
                    "deviation_percent": deviation,
                }
            )

        return {
            "balanced": max_deviation < 10,
            "max_deviation_percent": max_deviation,
            "average_keys": avg_keys,
            "devices": devices_info,
        }

    def reset(self) -> None:
        """重置所有统计数据"""
        with self._workers_lock:
            for worker in self._workers.values():
                worker.keys_checked = 0
                worker.matches_found = 0
                worker.throughput = 0.0
                worker.elapsed_time = 0.0
                worker.error_count = 0
                worker.status = "idle"
            self._cache_valid = False

    def stop(self) -> None:
        """停止聚合器"""
        self._stop_event.set()
        self._aggregation_thread.join(timeout=1.0)
