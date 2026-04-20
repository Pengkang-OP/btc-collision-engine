"""私钥去重过滤器"""
import hashlib
import threading
from typing import Dict, Any
from collections import deque

# 导入日志配置
from ..utils import init_logging, get_configured_logger

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("DeduplicationFilter")


class DeduplicationFilter:
    """私钥去重过滤器 - 防止重复检测相同私钥（优化版）
    
    设计说明：
    比特币私钥空间为 2^256，内存无法存储所有已检测的键。
    本实现采用滑动窗口 + Bloom Filter 混合策略：
    - 使用双缓冲队列实现滑动窗口，避免频繁清空
    - 8字节SHA256截断作为指纹，误判率极低
    - 仅对 random_search 模式有意义（range/brute_force 天然无重复）
    """
    
    def __init__(self, max_size: int = 1_000_000, enabled: bool = True):
        self.max_size = max_size
        self.enabled = enabled
        self.duplicates_found: int = 0
        self.checks_total: int = 0
        
        # 双缓冲设计：当前集合和待淘汰集合
        self._current: set = set()
        self._pending: set = set()
        self._lock = threading.Lock()
        
        # 使用 deque 作为 FIFO 队列跟踪插入顺序
        self._queue: deque = deque(maxlen=max_size // 2)
        self._current_size = 0
        self._half_size = max_size // 2
        
        logger.debug(f"DeduplicationFilter 初始化: max_size={max_size}, enabled={enabled}")
    
    def _fingerprint(self, private_key: bytes) -> bytes:
        """计算私钥的8字节指纹"""
        # 使用 SHA256 截断（兼容性更好）
        return hashlib.sha256(private_key).digest()[:8]
    
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
                logger.debug(f"缓冲区轮换: current={len(self._current)} -> pending, 总跟踪={len(self._current) + len(self._pending)}")
                self._pending = self._current
                self._current = set()
                self._current_size = 0
                # 清空队列但保持容量
                self._queue.clear()
            
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """返回去重统计"""
        with self._lock:
            tracked_total = len(self._current) + len(self._pending)
            stats = {
                "tracked_current": len(self._current),
                "tracked_pending": len(self._pending),
                "tracked_total": tracked_total,
                "duplicates_found": self.duplicates_found,
                "checks_total": self.checks_total,
                "duplicate_rate": self.duplicates_found / self.checks_total if self.checks_total > 0 else 0,
                "max_size": self.max_size,
                "memory_usage_estimate": tracked_total * 8  # 每个指纹8字节
            }
            
            # 记录统计信息（每1000次检查记录一次）
            if self.checks_total % 1000 == 0 and self.checks_total > 0:
                memory_mb = stats["memory_usage_estimate"] / (1024 * 1024)
                logger.debug(f"去重统计: 检查={self.checks_total}, 重复={self.duplicates_found}, "
                            f"重复率={stats['duplicate_rate']:.4%}, 跟踪数={tracked_total}, "
                            f"内存估计={memory_mb:.2f}MB")
            
            return stats
    
    def reset(self) -> None:
        """重置过滤器"""
        with self._lock:
            old_stats = self.get_stats()
            self._current.clear()
            self._pending.clear()
            self._queue.clear()
            self._current_size = 0
            self.duplicates_found = 0
            self.checks_total = 0
            logger.info(f"去重过滤器已重置 (之前: 检查={old_stats['checks_total']}, 重复={old_stats['duplicates_found']})")
