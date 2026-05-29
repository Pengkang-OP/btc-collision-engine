"""GPU缓冲区追踪器模块.

提供 GPUBufferTracker 类，用于检测和管理 GPU 内存缓冲区泄漏。
"""

import threading
import time
from typing import Any

# 统一日志获取
from ..utils import get_configured_logger

__all__ = ["GPUBufferTracker"]


logger = get_configured_logger("GPUBufferTracker")


# ========== GPU缓冲区追踪器 ==========
class GPUBufferTracker:
    """P2-2修复: GPU缓冲区跟踪器,用于检测内存泄漏.

    追踪所有分配的GPU缓冲区,检测超时未释放的缓冲区。
    线程安全,支持多线程并发访问。

    增强功能:
    - 自动清理超时缓冲区
    - 引擎关闭时强制检查
    - 内存使用趋势监控
    - 更细粒度的缓冲区跟踪
    - 内存使用阈值自动清理
    - 缓冲区类型分类管理
    """

    __slots__ = (
        "_allocated_buffers",
        "_check_interval",
        "_cleanup_count",
        "_last_check_time",
        "_leak_detection_count",
        "_lock",
        "_memory_threshold",
        "_memory_usage_history",
        "_periodic_check_stop",
        "_periodic_check_thread",
        "_timeout",
    )

    # 类级别配置
    DEFAULT_TIMEOUT = 300  # 默认超时5分钟
    MAX_TRACKED_BUFFERS = 1000  # 最大追踪缓冲区数量
    MEMORY_USAGE_THRESHOLD = 1024 * 1024 * 1024  # 1GB内存使用阈值
    # P2-02修复: 提取魔法数字
    MAX_MEMORY_HISTORY = 100  # 内存使用历史最大记录数
    MEMORY_TREND_WINDOW = 5  # 内存趋势分析窗口大小
    MEMORY_GROWTH_WARNING_RATIO = 1.5  # 内存增长警告比例（增长超过50%）

    def __init__(self, timeout: int | None = None, memory_threshold: int | None = None) -> None:
        """初始化缓冲区追踪器。.

        Args:
            timeout: 缓冲区超时时间（秒）。
            memory_threshold: 内存阈值（MB）。
        """
        self._allocated_buffers: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._memory_threshold = memory_threshold or self.MEMORY_USAGE_THRESHOLD
        self._cleanup_count = 0
        self._leak_detection_count = 0
        self._memory_usage_history: list[dict[str, Any]] = []  # 内存使用历史
        self._last_check_time = time.time()

    def track_buffer(
        self,
        name: str,
        buffer: Any,
        size: int,
        buffer_type: str = "generic",
        context: str = "",
    ) -> None:
        """注册缓冲区.

        Args:
            name: 缓冲区名称
            buffer: OpenCL Buffer对象
            size: 缓冲区大小(字节)
            buffer_type: 缓冲区类型 (generic, seed, matches, targets, precomp)
            context: 分配上下文

        Raises:
            RuntimeError: 当追踪的缓冲区数量超过最大限制时

        """
        with self._lock:
            # P2-02修复: 使用 MAX_TRACKED_BUFFERS 防止无限制增长
            if len(self._allocated_buffers) >= self.MAX_TRACKED_BUFFERS:
                logger.warning(f"缓冲区追踪数量已达上限 ({self.MAX_TRACKED_BUFFERS})，触发自动清理")
                _ = self._cleanup_sync()
                if len(self._allocated_buffers) >= self.MAX_TRACKED_BUFFERS:
                    _cnt = len(self._allocated_buffers)
                    _max = self.MAX_TRACKED_BUFFERS
                    raise RuntimeError(
                        f"GPU缓冲区追踪溢出: {_cnt} >= {_max}"
                        f" (超时阈值: {self._timeout}s, 请检查是否有未释放的缓冲区)",
                    )

            self._allocated_buffers[name] = {
                "buffer": buffer,
                "size": size,
                "timestamp": time.time(),
                "allocated": True,
                "type": buffer_type,
                "context": context,
            }

            # 记录内存使用历史
            self._record_memory_usage()

            # 检查内存使用是否超过阈值
            total_size = sum(info["size"] for info in self._allocated_buffers.values())
            if total_size > self._memory_threshold:
                _used_mb = total_size / 1024 / 1024
                _threshold_mb = self._memory_threshold / 1024 / 1024
                logger.warning(f"GPU内存使用超过阈值: {_used_mb:.1f}MB > {_threshold_mb:.1f}MB")
                # 触发自动清理
                self.cleanup_timed_out_buffers()

        logger.debug(f"GPU Buffer追踪: 分配 {name} ({size / 1024:.1f} KB, 类型: {buffer_type})")

    def is_tracked(self, name: str) -> bool:
        """检查缓冲区是否已被追踪.

        Args:
            name: 缓冲区名称

        Returns:
            True 如果缓冲区已在追踪列表中

        """
        with self._lock:
            return name in self._allocated_buffers

    def release_buffer(self, name: str) -> None:
        """注销缓冲区.

        Args:
            name: 缓冲区名称

        """
        with self._lock:
            if name in self._allocated_buffers:
                # 尝试释放GPU资源
                try:
                    buffer = self._allocated_buffers[name].get("buffer")
                    if buffer is not None and hasattr(buffer, "release"):
                        buffer.release()
                        logger.debug("GPU Buffer追踪: 释放 %s", name)
                except Exception as e:
                    logger.error("释放缓冲区失败 %s: %s", name, e)
                finally:
                    del self._allocated_buffers[name]
                    # 记录内存使用历史
                    self._record_memory_usage()

    def get_leaked_buffers(self, timeout: int | None = None) -> list[str]:
        """检测超过timeout未释放的缓冲区.

        Args:
            timeout: 超时阈值(秒)，None则使用实例默认超时

        Returns:
            泄漏的缓冲区名称列表

        """
        current_time = time.time()
        leaked = []
        effective_timeout = timeout if timeout is not None else self._timeout

        with self._lock:
            for name, info in self._allocated_buffers.items():
                if current_time - info["timestamp"] > effective_timeout:
                    leaked.append(name)

        if leaked:
            logger.warning(f"检测到{len(leaked)}个可能的GPU Buffer泄漏: {', '.join(leaked)}")

        return leaked

    def get_stats(self) -> dict[str, Any]:
        """获取缓冲区统计信息.

        Returns:
            统计信息字典

        """
        with self._lock:
            total_size = sum(info["size"] for info in self._allocated_buffers.values())
            # 按类型统计
            type_stats = {}
            for info in self._allocated_buffers.values():
                buffer_type = info.get("type", "generic")
                if buffer_type not in type_stats:
                    type_stats[buffer_type] = {"count": 0, "size": 0}
                type_stats[buffer_type]["count"] += 1
                type_stats[buffer_type]["size"] += info["size"]

            return {
                "count": len(self._allocated_buffers),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / 1024 / 1024,
                "type_stats": type_stats,
                "buffers": list(self._allocated_buffers.keys()),
                "cleanup_count": self._cleanup_count,
                "leak_detection_count": self._leak_detection_count,
                "timeout_seconds": self._timeout,
                "memory_threshold_mb": self._memory_threshold / 1024 / 1024,
                # 最近趋势窗口记录
                "memory_usage_history": self._memory_usage_history[-self.MEMORY_TREND_WINDOW :],
                "last_check_time": self._last_check_time,
            }

    def cleanup_timed_out_buffers(self) -> list[str]:
        """自动清理超时的缓冲区.

        审查修复#2: 实际释放GPU资源，而不仅删除追踪记录。

        Returns:
            被清理的缓冲区名称列表

        """
        current_time = time.time()
        cleaned = []
        failed_to_release = []  # 记录释放失败的资源

        with self._lock:
            to_remove = []
            for name, info in self._allocated_buffers.items():
                if current_time - info["timestamp"] > self._timeout:
                    to_remove.append(name)

            for name in to_remove:
                info = self._allocated_buffers[name]
                # 审查修复#2: 尝试释放GPU资源
                try:
                    buffer = info.get("buffer")
                    if buffer is not None and hasattr(buffer, "release"):
                        buffer.release()
                        logger.debug(
                            f"自动清理超时缓冲区: {name} (类型: {info.get('type', 'generic')})",
                        )
                    else:
                        failed_to_release.append(name)
                        logger.warning("超时缓冲区无release方法: %s", name)
                except Exception as e:
                    failed_to_release.append(name)
                    logger.error("清理超时缓冲区失败 %s: %s", name, e)
                finally:
                    del self._allocated_buffers[name]
                    cleaned.append(name)
                    self._cleanup_count += 1

            # 记录内存使用历史
            if cleaned:
                self._record_memory_usage()

        if cleaned:
            msg = f"自动清理{len(cleaned)}个超时GPU缓冲区"
            if failed_to_release:
                msg += f"，{len(failed_to_release)}个释放失败"
            logger.warning(msg)

        return cleaned

    def _cleanup_sync(self) -> list[str]:
        """P2-02修复: 同步清理超时缓冲区（在锁内调用）.

        与 cleanup_timed_out_buffers 的区别：
        - 此方法假定调用者已持有 self._lock
        - 不重复获取锁，避免死锁

        Returns:
            被清理的缓冲区名称列表

        """
        current_time = time.time()
        cleaned: list[str] = []

        to_remove = []
        for name, info in self._allocated_buffers.items():
            if current_time - info["timestamp"] > self._timeout:
                to_remove.append(name)

        for name in to_remove:
            info = self._allocated_buffers[name]
            try:
                buffer = info.get("buffer")
                if buffer is not None and hasattr(buffer, "release"):
                    buffer.release()
            except (RuntimeError, OSError):
                logger.debug("_cleanup_sync: 释放缓冲区失败 %s，已移除追踪记录", name)
            finally:
                del self._allocated_buffers[name]
                cleaned.append(name)
                self._cleanup_count += 1

        if cleaned:
            logger.debug(f"_cleanup_sync: 同步清理了 {len(cleaned)} 个超时缓冲区")
            self._record_memory_usage()

        return cleaned

    def cleanup_by_type(self, buffer_type: str) -> list[str]:
        """按类型清理缓冲区.

        Args:
            buffer_type: 缓冲区类型

        Returns:
            被清理的缓冲区名称列表

        """
        cleaned = []
        failed_to_release = []

        with self._lock:
            to_remove = []
            for name, info in self._allocated_buffers.items():
                if info.get("type") == buffer_type:
                    to_remove.append(name)

            for name in to_remove:
                info = self._allocated_buffers[name]
                try:
                    buffer = info.get("buffer")
                    if buffer is not None and hasattr(buffer, "release"):
                        buffer.release()
                        logger.debug("按类型清理缓冲区: %s (类型: %s)", name, buffer_type)
                    else:
                        failed_to_release.append(name)
                        logger.warning("缓冲区无release方法: %s", name)
                except Exception as e:
                    failed_to_release.append(name)
                    logger.error("清理缓冲区失败 %s: %s", name, e)
                finally:
                    del self._allocated_buffers[name]
                    cleaned.append(name)
                    self._cleanup_count += 1

            # 记录内存使用历史
            if cleaned:
                self._record_memory_usage()

        if cleaned:
            msg = f"按类型清理{len(cleaned)}个GPU缓冲区 (类型: {buffer_type})"
            if failed_to_release:
                msg += f"，{len(failed_to_release)}个释放失败"
            logger.info(msg)

        return cleaned

    def start_periodic_check(self, interval: int = 300) -> None:
        """启动定期泄漏检查（默认每5分钟）."""
        self._check_interval = interval
        self._periodic_check_stop = threading.Event()
        self._periodic_check_thread = threading.Thread(
            target=self._periodic_check_loop,
            daemon=True,
            name="buffer-tracker-periodic",
        )
        self._periodic_check_thread.start()
        logger.info("GPU缓冲区追踪器：定期检查已启动，间隔 %s 秒", interval)

    def stop_periodic_check(self) -> None:
        """停止定期泄漏检查."""
        if hasattr(self, "_periodic_check_stop") and self._periodic_check_stop:
            self._periodic_check_stop.set()
            if hasattr(self, "_periodic_check_thread") and self._periodic_check_thread:
                self._periodic_check_thread.join(timeout=10)
            logger.info("GPU缓冲区追踪器：定期检查已停止")

    def _periodic_check_loop(self) -> None:
        """定期检查循环."""
        while not self._periodic_check_stop.is_set():
            self._periodic_check_stop.wait(timeout=self._check_interval)
            if self._periodic_check_stop.is_set():
                break
            try:
                # 检查泄漏
                leaked = self.get_leaked_buffers(timeout=self._timeout)
                if leaked:
                    stats = self.get_stats()
                    _count = stats["count"]
                    logger.warning(
                        f"GPU缓冲区泄漏: 泄漏={len(leaked)}, 追踪={_count}, 已泄漏={leaked}",
                    )
                    # 自动清理泄漏的缓冲区
                    self.cleanup_timed_out_buffers()

                # 检查内存使用趋势
                self._check_memory_trend()

                # 更新最后检查时间
                self._last_check_time = time.time()
            except Exception as e:
                logger.error("定期泄漏检查失败: %s", e)

    def _record_memory_usage(self) -> None:
        """记录内存使用情况."""
        total_size = sum(info["size"] for info in self._allocated_buffers.values())
        self._memory_usage_history.append(
            {
                "timestamp": time.time(),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / 1024 / 1024,
                "buffer_count": len(self._allocated_buffers),
            },
        )

        # 只保留最近记录
        if len(self._memory_usage_history) > self.MAX_MEMORY_HISTORY:
            self._memory_usage_history = self._memory_usage_history[-self.MAX_MEMORY_HISTORY :]

    def _check_memory_trend(self) -> None:
        """检查内存使用趋势."""
        if len(self._memory_usage_history) < self.MEMORY_TREND_WINDOW:
            return

        # 计算内存使用趋势
        recent = self._memory_usage_history[-self.MEMORY_TREND_WINDOW :]
        initial_size = recent[0]["total_size_bytes"]
        final_size = recent[-1]["total_size_bytes"]

        if final_size > initial_size * self.MEMORY_GROWTH_WARNING_RATIO:  # 内存使用增长超过阈值
            final_mb = final_size / 1024 / 1024
            initial_mb = initial_size / 1024 / 1024
            logger.warning(f"GPU内存使用持续增长: {initial_mb:.1f}MB -> {final_mb:.1f}MB")
            # 尝试清理所有超时缓冲区
            self.cleanup_timed_out_buffers()

    def force_check_on_shutdown(self) -> dict[str, Any]:
        """引擎关闭时强制检查内存泄漏.

        Returns:
            检查结果字典

        """
        self._leak_detection_count += 1

        with self._lock:
            remaining = len(self._allocated_buffers)
            total_size = sum(info["size"] for info in self._allocated_buffers.values())
            buffer_names = list(self._allocated_buffers.keys())

            # 按类型统计
            type_stats = {}
            for info in self._allocated_buffers.values():
                buffer_type = info.get("type", "generic")
                if buffer_type not in type_stats:
                    type_stats[buffer_type] = 0
                type_stats[buffer_type] += 1

            # 尝试释放所有剩余缓冲区
            released = []
            failed = []

            for name, info in self._allocated_buffers.items():
                try:
                    buffer = info.get("buffer")
                    if buffer is not None and hasattr(buffer, "release"):
                        buffer.release()
                        released.append(name)
                        logger.debug(
                            f"关闭时释放缓冲区: {name} (类型: {info.get('type', 'generic')})",
                        )
                except Exception as e:
                    failed.append(
                        {"name": name, "error": str(e), "type": info.get("type", "generic")},
                    )
                    logger.error("关闭时释放缓冲区失败 %s: %s", name, e)

            # 清空追踪记录
            self._allocated_buffers.clear()
            self._memory_usage_history.clear()

        # 审查修复#3: 修正语义准确性
        result = {
            "remaining_buffers": remaining,
            "total_size_bytes": total_size,
            "released": released,
            "release_failed": failed,
            "type_stats": type_stats,
            "has_unreleased": remaining > 0,  # 有未释放的缓冲区
            "has_leak": len(failed) > 0,  # 释放失败才算泄漏
            "all_released_successfully": len(failed) == 0,
        }

        # v4.2.1修复: 只在释放失败时输出CRITICAL警告
        if len(failed) > 0:
            logger.critical(
                f"GPU引擎关闭时{len(failed)}个缓冲区释放失败 (可能内存泄漏): "
                f"{', '.join([f['name'] for f in failed])}",
            )
        elif remaining > 0:
            logger.info(
                f"GPU引擎关闭时释放了{remaining}个缓冲区 "
                f"(总大小: {total_size / 1024:.1f}KB): {', '.join(buffer_names)}",
            )
        else:
            logger.info("GPU引擎关闭时所有缓冲区已正确释放")

        return result
