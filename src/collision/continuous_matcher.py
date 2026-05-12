"""持续比对系统 - 大规模地址库快速比对"""

import threading
from datetime import datetime
from typing import Any

from ..utils import get_configured_logger, init_logging

# 初始化日志系统
init_logging()
logger = get_configured_logger("ContinuousMatcher")


class ContinuousMatcher:
    """
    持续比对系统 - 大规模地址库快速比对

    使用Hash160 Set实现O(1)时间复杂度的地址匹配，
    支持批量处理和高效统计。

    属性:
        target_table: 目标地址表引用
        match_count: 匹配计数
        total_checked: 总检查数
        _lock: 线程安全锁

    示例:
        >>> matcher = ContinuousMatcher(target_table)
        >>> matches = matcher.check_address_batch(addresses)
        >>> stats = matcher.get_statistics()
    """

    def __init__(self, target_table: Any) -> None:
        """
        初始化比对系统

        参数:
            target_table: BitcoinTargetTable实例
        """
        self.target_table = target_table
        self.match_count = 0
        self.total_checked = 0
        self._lock = threading.Lock()
        self._start_time = datetime.utcnow()

        logger.info("ContinuousMatcher初始化完成")

    def check_address_batch(self, addresses: list[dict]) -> list[dict]:
        """
        批量检查地址匹配 - 高效准确

        参数:
            addresses: 地址信息列表
                每个字典包含:
                - hash160: Hash160值（字节串）
                - address: 比特币地址
                - private_key: 私钥（字节串）
                - wif: WIF格式私钥
                - 其他生成信息

        返回:
            匹配的地址列表
        """
        matches = []
        batch_start = datetime.utcnow()

        for addr_info in addresses:
            hash160 = addr_info.get("hash160")

            if hash160 is None:
                logger.warning("地址信息缺少hash160字段")
                continue

            with self._lock:
                self.total_checked += 1

            # O(1)哈希表查找
            is_match, target_info = self.target_table.check_match(hash160)

            if is_match:
                with self._lock:
                    self.match_count += 1

                match_record = {
                    "found_at": datetime.utcnow().isoformat(),
                    "hash160": hash160.hex() if isinstance(hash160, bytes) else hash160,
                    "target": target_info,
                    "generated": addr_info,
                }

                matches.append(match_record)

                logger.critical(
                    "🎯 MATCH FOUND! Address: %s, Hash160: %s",
                    target_info.get("address", "unknown"),
                    hash160.hex() if isinstance(hash160, bytes) else hash160,
                )

        # 批量处理完成日志
        elapsed = (datetime.utcnow() - batch_start).total_seconds()
        logger.debug(
            "批量比对完成: %d addresses, %d matches, %.3fs", len(addresses), len(matches), elapsed
        )

        return matches

    def check_single_address(self, addr_info: dict) -> tuple[bool, dict | None]:
        """
        检查单个地址匹配

        参数:
            addr_info: 地址信息字典

        返回:
            (is_match, match_record) 元组
        """
        hash160 = addr_info.get("hash160")

        if hash160 is None:
            return False, None

        self.total_checked += 1

        is_match, target_info = self.target_table.check_match(hash160)

        if is_match:
            self.match_count += 1

            match_record = {
                "found_at": datetime.utcnow().isoformat(),
                "hash160": hash160.hex() if isinstance(hash160, bytes) else hash160,
                "target": target_info,
                "generated": addr_info,
            }

            return True, match_record

        return False, None

    def get_statistics(self) -> dict:
        """
        获取比对统计

        返回:
            统计信息字典
        """
        with self._lock:
            elapsed = (datetime.utcnow() - self._start_time).total_seconds()
            match_rate = self.match_count / max(self.total_checked, 1)

            return {
                "total_checked": self.total_checked,
                "matches_found": self.match_count,
                "match_rate": match_rate,
                "elapsed_seconds": elapsed,
                "check_rate": self.total_checked / elapsed if elapsed > 0 else 0,
                "efficiency": "O(1) per address",
            }

    def reset_statistics(self) -> None:
        """重置统计信息"""
        with self._lock:
            self.match_count = 0
            self.total_checked = 0
            self._start_time = datetime.utcnow()
            logger.info("比对统计已重置")
