"""高效地址匹配引擎

提供多种匹配策略优化地址匹配性能:
- Hash集合匹配(默认,O(1)查找)
- 布隆过滤器(大规模地址集,节省内存)
- 前缀树(支持地址模式匹配)

适用于不同规模的目标地址集合。
增强的策略回退和依赖兼容性。
"""

import threading
from typing import Any

# 导入日志配置
from ...utils import get_configured_logger

# v4.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("AddressMatcher", thread_safe=False)


class AddressMatcher:
    """高效地址匹配引擎

    根据目标地址集合的规模选择最优匹配策略。

    策略选择指南:
    - hash_set: 目标地址 < 10万(默认,O(1)查找)
    - bloom_filter: 目标地址 >= 10万(节省98%内存,极低误判率)
    - trie: 需要前缀匹配场景

    示例:
        >>> targets = {'1A1z...', '1B2x...'}
        >>> matcher = AddressMatcher(strategy='hash_set', targets=targets)
        >>> matcher.is_match('1A1z...')
        True
    """

    def __init__(
        self,
        strategy: str = "hash_set",
        targets: set[str] | None = None,
        bloom_capacity: int = 100000,
        bloom_error_rate: float = 0.001,
    ) -> None:
        """
        初始化地址匹配引擎

        参数:
            strategy: 匹配策略,可选 'hash_set', 'bloom_filter', 'trie'
            targets: 目标地址集合
            bloom_capacity: 布隆过滤器容量(仅bloom_filter策略)
            bloom_error_rate: 布隆过滤器误判率(仅bloom_filter策略)
        """
        self.strategy = strategy
        # 标准化目标地址为小写，确保大小写不敏感匹配
        self.targets = set(addr.lower() for addr in (targets or set()))

        # 线程安全
        self._lock = threading.RLock()

        # 根据策略初始化
        if strategy == "hash_set":
            self._init_hash_set()
        elif strategy == "bloom_filter":
            self._init_bloom_filter(bloom_capacity, bloom_error_rate)
        elif strategy == "trie":
            self._init_trie()
        else:
            raise ValueError(f"未知策略: {strategy}, 可选: hash_set, bloom_filter, trie")

        logger.info(f"AddressMatcher 初始化: 策略={strategy}, 目标数={len(self.targets)}")

    def _init_hash_set(self):
        """初始化Hash集合策略"""
        self._hash_set = set(self.targets)
        logger.debug(f"Hash集合初始化完成: {len(self._hash_set)} 个目标")

    def _init_bloom_filter(self, capacity: int, error_rate: float):
        """初始化布隆过滤器策略"""
        try:
            from pybloom_live import BloomFilter

            self._bloom = BloomFilter(capacity=capacity, error_rate=error_rate)
            for addr in self.targets:
                self._bloom.add(addr)
            logger.debug(
                f"布隆过滤器初始化成功: 容量={capacity}, 误判率={error_rate}, 目标数={len(self.targets)}"
            )
        except ImportError as e:
            logger.warning(f"pybloom-live 未安装,回退到 hash_set 策略 (原因: {e})")
            self.strategy = "hash_set"
            self._init_hash_set()
        except Exception as e:
            logger.error(f"布隆过滤器初始化失败: {e}, 回退到 hash_set 策略", exc_info=True)
            self.strategy = "hash_set"
            self._init_hash_set()

    def _init_trie(self):
        """初始化前缀树策略"""
        try:
            self._trie = {}
            for addr in self.targets:
                self._insert_trie(addr)
            logger.debug(f"前缀树初始化成功: {len(self.targets)} 个目标")
        except Exception as e:
            logger.error(f"前缀树初始化失败: {e}, 回退到 hash_set 策略", exc_info=True)
            self.strategy = "hash_set"
            self._init_hash_set()

    def _insert_trie(self, address: str):
        """插入地址到前缀树"""
        node = self._trie
        for char in address:
            if char not in node:
                node[char] = {}
            node = node[char]
        node["$"] = True  # 标记地址结束

    def is_match(self, address: str) -> bool:
        """
        检查地址是否匹配目标集

        参数:
            address: 待检查的地址

        返回:
            True表示匹配,False表示不匹配
        """
        # 输入验证
        if not isinstance(address, str):
            try:
                address = str(address)
            except Exception as e:
                logger.error(f"地址类型转换失败: {address}, 错误={e}")
                return False

        # 标准化地址为小写，确保大小写不敏感匹配
        normalized_address = address.lower()

        with self._lock:
            try:
                if self.strategy == "hash_set":
                    return normalized_address in self._hash_set
                elif self.strategy == "bloom_filter":
                    return normalized_address in self._bloom
                elif self.strategy == "trie":
                    return self._search_trie(normalized_address)
                else:
                    return False
            except Exception as e:
                logger.error(f"地址匹配异常: {address}, 策略={self.strategy}, 错误={e}")
                return False

    def _search_trie(self, address: str) -> bool:
        """在前缀树中搜索地址"""
        node = self._trie
        for char in address:
            if char not in node:
                return False
            node = node[char]
        return "$" in node

    def add_target(self, address: str) -> None:
        """
        添加单个目标地址

        参数:
            address: 目标地址
        """
        # 输入验证
        if not isinstance(address, str):
            try:
                address = str(address)
            except Exception as e:
                logger.error(f"地址类型转换失败: {address}, 错误={e}")
                return

        # 标准化地址为小写
        normalized_address = address.lower()

        with self._lock:
            try:
                self.targets.add(normalized_address)

                if self.strategy == "hash_set":
                    self._hash_set.add(normalized_address)
                elif self.strategy == "bloom_filter":
                    self._bloom.add(normalized_address)
                elif self.strategy == "trie":
                    self._insert_trie(normalized_address)
            except Exception as e:
                logger.error(f"添加目标地址失败: {address}, 错误={e}")

    def add_targets(self, addresses: set[str]) -> None:
        """
        批量添加目标地址

        参数:
            addresses: 目标地址集合
        """
        # 输入验证和转换
        valid_addresses = set()
        for addr in addresses:
            if isinstance(addr, str):
                # 标准化地址为小写
                valid_addresses.add(addr.lower())
            else:
                try:
                    # 标准化地址为小写
                    valid_addresses.add(str(addr).lower())
                except Exception as e:
                    logger.warning(f"地址类型转换失败,跳过: {addr}, 错误={e}")

        with self._lock:
            try:
                self.targets.update(valid_addresses)

                if self.strategy == "hash_set":
                    self._hash_set.update(valid_addresses)
                elif self.strategy == "bloom_filter":
                    for addr in valid_addresses:
                        self._bloom.add(addr)
                elif self.strategy == "trie":
                    for addr in valid_addresses:
                        self._insert_trie(addr)
            except Exception as e:
                logger.error(f"批量添加目标地址失败: 错误={e}")

    def remove_target(self, address: str) -> bool:
        """
        移除目标地址

        注意: 布隆过滤器不支持删除操作

        参数:
            address: 要移除的地址

        返回:
            True表示成功移除,False表示地址不存在
        """
        # 标准化地址为小写
        normalized_address = address.lower()

        with self._lock:
            if normalized_address not in self.targets:
                return False

            self.targets.discard(normalized_address)

            if self.strategy == "hash_set":
                self._hash_set.discard(normalized_address)
            elif self.strategy == "bloom_filter":
                logger.warning("布隆过滤器不支持删除操作")
                return False
            elif self.strategy == "trie":
                # 前缀树删除较复杂,这里简化处理
                logger.warning("前缀树删除操作未实现")
                return False

            return True

    def get_stats(self) -> dict[str, Any]:
        """
        获取匹配引擎统计信息

        返回:
            包含统计信息的字典
        """
        with self._lock:
            stats = {
                "strategy": self.strategy,
                "target_count": len(self.targets),
            }

            if self.strategy == "hash_set":
                stats["memory_estimate_bytes"] = len(self._hash_set) * 50  # 粗略估计
            elif self.strategy == "bloom_filter":
                stats["memory_estimate_bytes"] = len(self._bloom) // 8  # 位图估计
                stats["bloom_capacity"] = self._bloom.capacity

            return stats

    def clear(self) -> None:
        """清空所有目标地址"""
        with self._lock:
            self.targets.clear()

            if self.strategy == "hash_set":
                self._hash_set.clear()
            elif self.strategy == "bloom_filter":
                # 布隆过滤器需要重新创建
                self._init_bloom_filter(self._bloom.capacity, self._bloom.error_rate)
            elif self.strategy == "trie":
                self._trie.clear()

            logger.info("匹配引擎已清空")

    def __len__(self) -> int:
        """返回目标地址数量"""
        return len(self.targets)

    def __contains__(self, address: str) -> bool:
        """支持 in 操作符"""
        return self.is_match(address)

    def __repr__(self) -> str:
        return f"AddressMatcher(strategy={self.strategy}, targets={len(self.targets)})"
