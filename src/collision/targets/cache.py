"""地址缓存管理器.

提供多层缓存策略优化地址解析性能:
- LRU缓存: 最近使用的地址解析结果
- TTL缓存: 带过期时间的缓存
- 缓存统计和监控
- 增强的线程安全和跨平台兼容性
"""

import threading
from typing import TYPE_CHECKING, Any

# 导入日志配置
from src.utils import get_configured_logger

if TYPE_CHECKING:
    from cachetools import LRUCache, TTLCache  # noqa: F401

# 可选依赖: cachetools 提供 LRU/TTL 缓存，未安装时降级为 dict
try:
    from cachetools import LRUCache as _LRUCache
    from cachetools import TTLCache as _TTLCache
except ImportError:
    _LRUCache = dict  # type: ignore[assignment,misc]  # p: cachetools 可选依赖回退
    _TTLCache = dict  # type: ignore[assignment,misc]  # p: cachetools 可选依赖回退

# v4.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("AddressCache")


class AddressCache:
    """地址解析缓存管理器.

    提供多层缓存策略以优化地址解析性能。
    适用于频繁解析相同地址或WIF私钥的场景。

    Attributes:
        lru_cache: LRU缓存，存储最近使用的解析结果
        ttl_cache: TTL缓存，存储带过期时间的临时数据
        hits: 缓存命中次数
        misses: 缓存未命中次数

    Example:
        >>> cache = AddressCache(lru_size=10000, ttl_seconds=3600)
        >>> cache.put('5KJvs...', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        >>> address = cache.get('5KJvs...')

    """

    def __init__(
        self,
        lru_size: int = 10000,
        ttl_seconds: int = 3600,
        enable_stats: bool = True,
    ) -> None:
        """初始化地址缓存.

        Args:
            lru_size: LRU缓存最大容量，默认10000条目
            ttl_seconds: TTL缓存过期时间(秒)，默认3600秒(1小时)
            enable_stats: 是否启用缓存统计，默认True

        """
        # 内存LRU缓存 - 用于持久化常用地址
        self.lru_cache: Any = _LRUCache(maxsize=lru_size) if _LRUCache is not dict else {}  # type: ignore[comparison-overlap]

        # TTL缓存 - 用于临时数据，自动过期
        self.ttl_cache: Any = _TTLCache(maxsize=5000, ttl=ttl_seconds) if _TTLCache is not dict else {}  # type: ignore[comparison-overlap]

        # 缓存统计
        self.enable_stats = enable_stats
        self.hits = 0
        self.misses = 0

        # 线程安全
        self._lock = threading.RLock()

        # 保存配置参数
        self.lru_size = lru_size
        self.ttl_seconds = ttl_seconds

        logger.info("AddressCache 初始化: LRU大小=%s, TTL=%s秒", lru_size, ttl_seconds)

    def get(self, key: str, use_ttl: bool = False) -> str | None:
        """获取缓存的地址解析结果.

        Args:
            key: 缓存键(原始输入字符串)
            use_ttl: 是否使用TTL缓存，默认False(使用LRU缓存)

        Returns:
            缓存的地址，未命中返回None

        """
        # 输入验证
        if not isinstance(key, str):
            try:
                key = str(key)
            except Exception as e:
                logger.error("缓存键类型转换失败: %s, 错误=%s", key, e)
                return None

        with self._lock:
            try:
                value = self.ttl_cache.get(key) if use_ttl else self.lru_cache.get(key)

                if value is not None:
                    if self.enable_stats:
                        self.hits += 1
                    logger.debug(f"缓存命中: {key[:10]}...")
                    return value  # type: ignore[no-any-return]
                if self.enable_stats:
                    self.misses += 1
                logger.debug(f"缓存未命中: {key[:10]}...")
                return None
            except Exception as e:
                logger.error("缓存获取异常: %s, 错误=%s", key, e)
                return None

    def put(self, key: str, value: str, use_ttl: bool = False) -> None:
        """存入缓存.

        Args:
            key: 缓存键(原始输入字符串)
            value: 缓存值(解析后的地址)
            use_ttl: 是否使用TTL缓存，默认False(使用LRU缓存)

        """
        # 输入验证
        if not value:
            return

        if not isinstance(key, str):
            try:
                key = str(key)
            except Exception as e:
                logger.error("缓存键类型转换失败: %s, 错误=%s", key, e)
                return

        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception as e:
                logger.error("缓存值类型转换失败: %s, 错误=%s", value, e)
                return

        with self._lock:
            try:
                if use_ttl:
                    self.ttl_cache[key] = value
                else:
                    self.lru_cache[key] = value

                logger.debug(f"缓存存入: {key[:10]}... -> {value[:10]}...")
            except Exception as e:
                logger.error("缓存存入异常: %s, 错误=%s", key, e)

    def clear(self) -> None:
        """清空所有缓存."""
        with self._lock:
            try:
                self.lru_cache.clear()
                self.ttl_cache.clear()
                old_hits = self.hits
                old_misses = self.misses
                self.hits = 0
                self.misses = 0
                logger.info("缓存已清空 (之前: 命中=%s, 未命中=%s)", old_hits, old_misses)
            except Exception as e:
                logger.error("缓存清空异常: %s", e)

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息.

        Returns:
            包含缓存统计信息的字典

        """
        with self._lock:
            try:
                total = self.hits + self.misses
                hit_rate = self.hits / total if total > 0 else 0.0

                return {
                    "lru_size": len(self.lru_cache),
                    "lru_max_size": self.lru_cache.maxsize,
                    "ttl_size": len(self.ttl_cache),
                    "hits": self.hits,
                    "misses": self.misses,
                    "total_requests": total,
                    "hit_rate": hit_rate,
                    "memory_estimate_bytes": len(self.lru_cache) * 100,  # 粗略估计
                }
            except (ZeroDivisionError, AttributeError) as e:
                # 只捕获预期的异常类型
                logger.warning("缓存统计计算异常: %s", e)
                return self._default_stats()
            except Exception as e:
                # 其他异常向上抛出
                logger.error("缓存统计未知异常: %s", e)
                raise

    def _default_stats(self) -> dict[str, Any]:
        """返回默认统计信息."""
        return {
            "lru_size": 0,
            "lru_max_size": self.lru_size,
            "ttl_size": 0,
            "hits": 0,
            "misses": 0,
            "total_requests": 0,
            "hit_rate": 0.0,
            "memory_estimate_bytes": 0,
        }

    def reset_stats(self) -> None:
        """重置统计信息."""
        with self._lock:
            self.hits = 0
            self.misses = 0

    def __contains__(self, key: str) -> bool:
        """检查键是否在缓存中."""
        if not isinstance(key, str):
            try:
                key = str(key)
            except (TypeError, ValueError) as e:
                # C类修复: 使用具体异常类型代替裸异常捕获
                logger.debug("缓存键转换失败: %s", e)
                return False

        with self._lock:
            try:
                return key in self.lru_cache or key in self.ttl_cache
            except Exception as e:
                logger.error("缓存包含检查异常: %s, 错误=%s", key, e)
                return False

    def __len__(self) -> int:
        """返回缓存中的条目数."""
        with self._lock:
            try:
                return len(self.lru_cache) + len(self.ttl_cache)
            except Exception as e:
                logger.error("缓存长度获取异常: %s", e)
                return 0

    def __bool__(self) -> bool:
        """缓存对象始终为True(即使为空)."""
        return True

    def __repr__(self) -> str:
        """返回缓存对象的字符串表示。."""
        try:
            stats = self.get_stats()
            return (
                f"AddressCache(hit_rate={stats['hit_rate']:.2%}, "
                f"lru_size={stats['lru_size']}, "
                f"ttl_size={stats['ttl_size']})"
            )
        except Exception as e:
            return f"AddressCache(error={e!s})"
