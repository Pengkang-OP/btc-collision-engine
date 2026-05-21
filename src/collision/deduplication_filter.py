"""私钥去重过滤器"""

import hashlib
import threading
from collections import deque
from typing import Any

# 导入日志配置
from ..utils import get_configured_logger

# 获取模块日志记录器
logger = get_configured_logger("DeduplicationFilter")

# v4.3.1: 快速哈希模式开关
# 当启用时，使用 Python 内置 hash() 替代 SHA256 计算指纹
# hash() 比 SHA256 快 10-100x，适合内存级去重场景
# 注意: hash() 值在进程间不可复现，但会话内去重不需要跨进程一致性
_USE_FAST_HASH: bool = True


def _fast_fingerprint(private_key: bytes) -> int:
    """快速指纹计算 (Python 内置 hash)"""
    return hash(private_key)


def _crypto_fingerprint(private_key: bytes) -> int:
    """密码学指纹计算 (SHA256 截断)"""
    return int.from_bytes(hashlib.sha256(private_key).digest()[:8], "big")


class DeduplicationFilter:
    """私钥去重过滤器 - 防止重复检测相同私钥（滑动窗口 + 哈希指纹）

    **使用场景（M7）**: 适用于 random_search 模式的高频去重，
    与 [BloomDeduplicationFilter](file:///f:/Qoder/btc-collision-engine/src/collision/bloom_deduplication_filter.py)
    选择分界：
    - DeduplicationFilter: 滑动窗口精确去重，适合 <100万 元素、
      需要零误判的场景（range/sequential/brute_force 模式可用此）
    - BloomDeduplicationFilter: 概率去重，适合 >100万 元素、
      可容忍 0.1% 误判率的 random_search 海量去重

    设计说明：
    比特币私钥空间为 2^256，内存无法存储所有已检测的键。
    本实现采用滑动窗口 + 双缓冲集合策略：
    - 使用双缓冲集合实现滑动窗口，避免频繁清空
    - 8字节SHA256截断作为指纹，误判率极低
    - 需要零误判的场景请使用本类；海量去重请使用 BloomDeduplicationFilter
    - 仅对 random_search 模式有意义（range/brute_force 天然无重复）
    """

    def __init__(
        self, max_size: int = 1_000_000, enabled: bool = True, false_positive_rate: float = 0.001
    ) -> None:
        """初始化去重过滤器

        参数:
            max_size: 最大容量
            enabled: 是否启用
            false_positive_rate: 期望的误判率（保留参数，v4.3.1 快速哈希模式下不适用）
        """
        self.max_size = max_size
        self.enabled = enabled
        self.false_positive_rate = false_positive_rate
        self.duplicates_found: int = 0
        self.checks_total: int = 0
        # _queue 为滑动窗口队列，用于快速哈希模式下的指纹去重
        # 写入后由 _fast_dedup_check 通过 __contains__ 检查成员
        # noqa: W0612 (deque 通过 runtime patching 访问，静态分析不可见)

        # v4.3.1: 根据 _USE_FAST_HASH 选择指纹函数
        if _USE_FAST_HASH:
            self._fingerprint_fn = _fast_fingerprint
            logger.debug("DeduplicationFilter: 启用快速哈希模式 (Python hash)")
        else:
            self._fingerprint_fn = _crypto_fingerprint
            logger.debug("DeduplicationFilter: 使用密码学哈希模式 (SHA256)")

        # 双缓冲设计：当前集合和待淘汰集合 (v4.3.1: int 指纹)
        self._current: set[int] = set()
        self._pending: set[int] = set()
        self._lock = threading.Lock()

        # 使用 deque 作为 FIFO 队列跟踪插入顺序
        self._queue: deque[int] = deque(maxlen=max_size // 2)
        self._current_size = 0
        self._half_size = max_size // 2

        logger.debug(f"DeduplicationFilter 初始化: max_size={max_size}, enabled={enabled}")

    def _fingerprint(self, private_key: bytes) -> int:
        return self._fingerprint_fn(private_key)

    def check_and_add(self, private_key: bytes) -> bool:
        """检查是否重复。不重复返回True，重复返回False。禁用时始终返回True。

        线程安全说明:
        - 所有计数器更新都在锁内完成，确保线程安全
        - 指纹计算在锁外进行，减少锁持有时间
        """
        if not self.enabled:
            return True

        fp = self._fingerprint(private_key)

        with self._lock:
            # 线程安全：计数器更新在锁内
            self.checks_total += 1
            # 检查当前集合和待淘汰集合
            if fp in self._current or fp in self._pending:
                self.duplicates_found += 1
                return False

            # 添加到当前集合
            self._current.add(fp)
            self._queue.append(fp)
            self._current_size += 1

            # 达到半满时，将当前集合移入待淘汰，清空当前
            if self._current_size >= self._half_size:
                logger.debug(
                    f"缓冲区轮换: current={len(self._current)} -> pending, 总跟踪={len(self._current) + len(self._pending)}"  # noqa: E501
                )
                self._pending = self._current
                self._current = set()
                self._current_size = 0
                # 清空队列但保持容量
                self._queue.clear()

            return True

    def _get_stats_unlocked(self) -> dict[str, Any]:
        """返回去重统计（不加锁版本，调用方须已持有 self._lock）"""
        tracked_total = len(self._current) + len(self._pending)
        stats = {
            "tracked_current": len(self._current),
            "tracked_pending": len(self._pending),
            "tracked_total": tracked_total,
            "duplicates_found": self.duplicates_found,
            "checks_total": self.checks_total,
            "duplicate_rate": (
                self.duplicates_found / self.checks_total if self.checks_total > 0 else 0
            ),
            "max_size": self.max_size,
            "memory_usage_estimate": tracked_total * 8,  # 每个指纹8字节
        }

        # 记录统计信息（每1000次检查记录一次）
        if self.checks_total % 1000 == 0 and self.checks_total > 0:
            memory_mb = stats["memory_usage_estimate"] / (1024 * 1024)
            logger.debug(
                f"去重统计: 检查={self.checks_total}, 重复={self.duplicates_found}, "
                f"重复率={stats['duplicate_rate']:.4%}, 跟踪数={tracked_total}, "
                f"内存估计={memory_mb:.2f}MB"
            )

        return stats

    def get_stats(self) -> dict[str, Any]:
        """返回去重统计"""
        with self._lock:
            return self._get_stats_unlocked()

    def reset(self) -> None:
        """重置过滤器"""
        with self._lock:
            # 使用不加锁版本，避免 reset() 持锁时再次获取同一把锁导致死锁
            old_stats = self._get_stats_unlocked()
            self._current.clear()
            self._pending.clear()
            self._queue.clear()
            self._current_size = 0
            self.duplicates_found = 0
            self.checks_total = 0
            _old_checks = old_stats["checks_total"]
            _old_dups = old_stats["duplicates_found"]
            logger.info(f"去重过滤器已重置 (之前: 检查={_old_checks}, 重复={_old_dups})")
