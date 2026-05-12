"""Bloom Filter去重过滤器

使用Bloom Filter算法实现高效的私钥去重，
相比哈希集合可节省90%内存，支持更大容量。
"""

import hashlib
import math
import threading

from bitarray import bitarray

# 导入日志配置
from ..utils import get_configured_logger, init_logging

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("BloomDeduplicationFilter")


class BloomFilter:
    """Bloom Filter实现

    空间效率高的概率型数据结构，用于判断元素是否在集合中。
    - 可能误判（False Positive）：说在但实际不在
    - 不会漏判（False Negative）：说不在就一定不在
    """

    def __init__(self, max_elements: int, false_positive_rate: float = 0.01) -> None:
        """
        初始化Bloom Filter

        Args:
            max_elements: 预期最大元素数量
            false_positive_rate: 期望的误判率（0.01 = 1%）
        """
        if max_elements <= 0:
            raise ValueError("max_elements必须是正整数")
        if not (0 < false_positive_rate < 1):
            raise ValueError("false_positive_rate必须在(0, 1)范围内")

        self.max_elements = max_elements
        self.false_positive_rate = false_positive_rate

        # 计算最优位数组大小和哈希函数数量
        self.bit_size = self._optimal_bit_size(max_elements, false_positive_rate)
        self.hash_count = self._optimal_hash_count(self.bit_size, max_elements)

        # 初始化位数组
        self.bit_array = bitarray(self.bit_size)
        self.bit_array.setall(0)

        # 统计信息
        self.elements_added = 0

        logger.info(
            f"Bloom Filter初始化: 容量={max_elements}, "
            f"误判率={false_positive_rate * 100:.2f}%, "
            f"位数组大小={self.bit_size}, "
            f"哈希函数数量={self.hash_count}"
        )

    @staticmethod
    def _optimal_bit_size(n: int, p: float) -> int:
        """计算最优位数组大小

        公式: m = -n * ln(p) / (ln(2)^2)

        Args:
            n: 预期元素数量
            p: 期望误判率

        Returns:
            位数组大小（bit）
        """
        m = -n * math.log(p) / (math.log(2) ** 2)
        return int(math.ceil(m))

    @staticmethod
    def _optimal_hash_count(m: int, n: int) -> int:
        """计算最优哈希函数数量

        公式: k = (m/n) * ln(2)

        Args:
            m: 位数组大小
            n: 预期元素数量

        Returns:
            哈希函数数量
        """
        k = (m / n) * math.log(2)
        return int(math.ceil(k))

    def _hashes(self, item: bytes) -> list:
        """生成多个哈希值

        使用双重哈希技术：h(i) = h1(x) + i * h2(x)
        只需计算2个哈希函数即可模拟k个哈希函数

        Args:
            item: 要哈希的数据

        Returns:
            哈希值列表（位数组索引）
        """
        # 计算两个基础哈希(仅用于Bloom过滤器,不用于加密安全)
        h1 = int(hashlib.md5(item, usedforsecurity=False).hexdigest(), 16)  # nosec B324 - 仅用于Bloom过滤器性能优化
        h2 = int(hashlib.sha1(item).hexdigest(), 16)  # nosec B324 - 仅用于Bloom过滤器性能优化

        # 生成k个哈希值
        hashes = []
        for i in range(self.hash_count):
            hash_val = (h1 + i * h2) % self.bit_size
            hashes.append(hash_val)

        return hashes

    def add(self, item: bytes) -> None:
        """添加元素到Bloom Filter

        Args:
            item: 要添加的元素（bytes）
        """
        if not isinstance(item, bytes):
            raise TypeError("item必须是bytes类型")

        for hash_val in self._hashes(item):
            self.bit_array[hash_val] = 1

        self.elements_added += 1

    def check(self, item: bytes) -> bool:
        """检查元素是否可能在集合中

        Args:
            item: 要检查的元素（bytes）

        Returns:
            bool: True表示可能在（可能误判），False表示一定不在
        """
        if not isinstance(item, bytes):
            raise TypeError("item必须是bytes类型")

        return all(self.bit_array[hash_val] == 1 for hash_val in self._hashes(item))

    def get_current_false_positive_rate(self) -> float:
        """计算当前实际误判率

        公式: p = (1 - e^(-kn/m))^k

        Returns:
            当前误判率
        """
        if self.elements_added == 0:
            return 0.0

        n = self.elements_added
        m = self.bit_size
        k = self.hash_count

        # p = (1 - e^(-kn/m))^k
        exponent = -k * n / m
        p = (1 - math.exp(exponent)) ** k

        return p

    def get_fill_ratio(self) -> float:
        """获取位数组填充率

        Returns:
            填充率（0.0-1.0）
        """
        count = self.bit_array.count(1)
        return count / self.bit_size

    def get_stats(self) -> dict:
        """获取Bloom Filter统计信息

        Returns:
            统计信息字典
        """
        return {
            "max_elements": self.max_elements,
            "elements_added": self.elements_added,
            "bit_size": self.bit_size,
            "hash_count": self.hash_count,
            "fill_ratio": self.get_fill_ratio(),
            "current_false_positive_rate": self.get_current_false_positive_rate(),
            "target_false_positive_rate": self.false_positive_rate,
            "memory_usage_bytes": self.bit_size // 8,
        }

    def clear(self) -> None:
        """清空Bloom Filter"""
        self.bit_array.setall(0)
        self.elements_added = 0
        logger.info("Bloom Filter已清空")


class BloomDeduplicationFilter:
    """基于Bloom Filter的去重过滤器

    相比传统哈希集合：
    - 内存占用减少90%
    - 支持更大容量（1亿+元素）
    - 可配置误判率
    """

    def __init__(
        self, max_size: int = 10_000_000, false_positive_rate: float = 0.001, enabled: bool = True
    ) -> None:
        """
        初始化Bloom Filter去重过滤器

        Args:
            max_size: 预期最大元素数量（默认1000万）
            false_positive_rate: 误判率（默认0.1%）
            enabled: 是否启用去重
        """
        self.enabled = enabled
        self.max_size = max_size
        self.false_positive_rate = false_positive_rate

        # 创建Bloom Filter
        self.bloom = BloomFilter(max_size, false_positive_rate)

        # 统计信息
        self.duplicates_found = 0
        self.total_checks = 0

        # 线程锁
        self._lock = threading.Lock()

        logger.info(
            f"BloomDeduplicationFilter初始化: max_size={max_size}, false_positive_rate={false_positive_rate * 100:.3f}%"
        )

    def _fingerprint(self, private_key: bytes) -> bytes:
        """计算私钥指纹

        Args:
            private_key: 私钥字节

        Returns:
            指纹（SHA256哈希）
        """
        return hashlib.sha256(private_key).digest()

    def check_and_add(self, private_key: bytes) -> bool:
        """检查是否重复，不重复则添加

        Args:
            private_key: 私钥字节

        Returns:
            bool: True表示不重复（已添加），False表示可能重复
        """
        if not self.enabled:
            return True

        fp = self._fingerprint(private_key)

        with self._lock:
            self.total_checks += 1

            # 检查是否可能重复
            if self.bloom.check(fp):
                self.duplicates_found += 1
                return False  # 可能重复

            # 添加到Bloom Filter
            self.bloom.add(fp)
            return True  # 确定不重复

    def get_stats(self) -> dict:
        """获取去重统计信息

        Returns:
            统计信息字典
        """
        bloom_stats = self.bloom.get_stats()

        return {
            "enabled": self.enabled,
            "total_checks": self.total_checks,
            "duplicates_found": self.duplicates_found,
            "unique_elements": self.total_checks - self.duplicates_found,
            "duplicate_rate": (
                self.duplicates_found / self.total_checks * 100 if self.total_checks > 0 else 0
            ),
            "bloom_filter": bloom_stats,
        }

    def reset(self) -> None:
        """重置过滤器"""
        with self._lock:
            self.bloom.clear()
            self.duplicates_found = 0
            self.total_checks = 0
        logger.info("BloomDeduplicationFilter已重置")

    def should_auto_reset(self) -> bool:
        """检查是否应该自动重置

        当Bloom Filter填充率超过70%时建议重置，
        因为误判率会快速上升。

        Returns:
            bool: True表示建议重置
        """
        fill_ratio = self.bloom.get_fill_ratio()
        return fill_ratio > 0.7
