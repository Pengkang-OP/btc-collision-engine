#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU监控模块

提供GPU使用率、显存使用等监控指标
"""

import os
import time
import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger("GPUMonitor")


class GPUMonitor:
    """GPU监控器"""

    def __init__(self) -> None:
        """初始化GPU监控器"""
        self.gpu_available = False
        self.gpu_info: Dict[str, Any] = {}
        self._last_check = 0.0
        self._cached_metrics: Dict[str, Any] = {}
        self._check_interval = 5.0  # 5秒检查一次

        # 尝试导入GPU相关库
        try:
            import pyopencl as cl

            self.cl = cl
            self.gpu_available = True
            logger.info("PyOpenCL可用，GPU监控已启用")
        except ImportError:
            logger.warning("PyOpenCL不可用，GPU监控已禁用")
            self.gpu_available = False

    def get_gpu_info(self) -> Dict[str, Any]:
        """
        获取GPU基本信息

        Returns:
            GPU信息字典
        """
        if not self.gpu_available:
            return {"available": False}

        try:
            platforms = self.cl.get_platforms()
            gpus = []

            for platform in platforms:
                devices = platform.get_devices(device_type=self.cl.device_type.GPU)
                for device in devices:
                    gpu_info = {
                        "name": device.name,
                        "vendor": device.vendor,
                        "max_compute_units": device.max_compute_units,
                        "global_memory_mb": device.global_mem_size / (1024 * 1024),
                        "max_clock_frequency": device.max_clock_frequency,
                        "available": True,
                    }
                    gpus.append(gpu_info)

            return {"available": True, "gpu_count": len(gpus), "gpus": gpus}
        except Exception as e:
            logger.error(f"获取GPU信息失败: {e}")
            return {"available": False, "error": str(e)}

    def get_gpu_metrics(self) -> Dict[str, Any]:
        """
        获取GPU性能指标（使用缓存）

        Returns:
            GPU性能指标字典
        """
        current_time = time.time()

        # 使用缓存避免频繁查询
        if current_time - self._last_check < self._check_interval:
            return self._cached_metrics

        if not self.gpu_available:
            return {
                "available": False,
                "gpu_usage": 0.0,
                "memory_used_mb": 0.0,
                "memory_total_mb": 0.0,
                "memory_usage_percent": 0.0,
            }

        try:
            # 注意：PyOpenCL不直接提供GPU使用率
            # 这里返回基本信息，实际使用率需要特定平台的API
            platforms = self.cl.get_platforms()
            total_memory = 0.0
            gpu_count = 0

            for platform in platforms:
                devices = platform.get_devices(device_type=self.cl.device_type.GPU)
                for device in devices:
                    total_memory += device.global_mem_size / (1024 * 1024)
                    gpu_count += 1

            metrics = {
                "available": True,
                "gpu_count": gpu_count,
                "total_memory_mb": total_memory,
                # 注意：这些是估算值，实际值需要特定GPU驱动API
                "memory_used_mb": 0.0,  # 需要运行时跟踪
                "memory_usage_percent": 0.0,
                "timestamp": current_time,
            }

            self._cached_metrics = metrics
            self._last_check = current_time

            return metrics
        except Exception as e:
            logger.error(f"获取GPU指标失败: {e}")
            return {"available": False, "error": str(e)}

    def track_memory_usage(self, allocated_bytes: int) -> None:
        """
        跟踪GPU显存使用

        Args:
            allocated_bytes: 已分配的字节数
        """
        if not self.gpu_available:
            return

        self._cached_metrics["memory_used_mb"] = allocated_bytes / (1024 * 1024)

        if self._cached_metrics.get("total_memory_mb", 0) > 0:
            self._cached_metrics["memory_usage_percent"] = (
                self._cached_metrics["memory_used_mb"]
                / self._cached_metrics["total_memory_mb"]
                * 100
            )

    def is_available(self) -> bool:
        """检查GPU是否可用"""
        return self.gpu_available


# 全局GPU监控器实例
_gpu_monitor = None


def get_gpu_monitor() -> GPUMonitor:
    """获取全局GPU监控器实例"""
    global _gpu_monitor
    if _gpu_monitor is None:
        _gpu_monitor = GPUMonitor()
    return _gpu_monitor


def collect_gpu_metrics() -> Dict[str, Any]:
    """
    收集GPU监控指标（便捷函数）

    Returns:
        GPU指标字典
    """
    monitor = get_gpu_monitor()
    return monitor.get_gpu_metrics()


if __name__ == "__main__":
    # 测试GPU监控
    logging.basicConfig(level=logging.INFO)

    monitor = GPUMonitor()
    print("GPU信息:", monitor.get_gpu_info())
    print("GPU指标:", monitor.get_gpu_metrics())
