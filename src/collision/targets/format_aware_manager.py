"""格式感知的目标地址管理器

根据目标地址格式智能选择地址生成策略:
- 检测目标地址格式
- 为不同格式创建独立的目标集合
- 提供格式感知的地址匹配接口

示例:
    >>> manager = FormatAwareTargetManager()
    >>> manager.load_targets(['1A1z...', '3J98t...', 'bc1qw...'])
    >>> targets_by_format = manager.get_targets_by_format()
    >>> print(f"P2PKH: {len(targets_by_format['p2pkh'])}")
"""

import threading

from ...core.multi_format_generator import AddressFormat, MultiFormatAddressGenerator
from ...utils import get_configured_logger

logger = get_configured_logger("FormatAwareTargetManager")


class FormatAwareTargetManager:
    """
    格式感知的目标地址管理器

    自动检测目标地址格式，支持多格式目标混合匹配。
    为碰撞引擎提供智能的格式感知地址生成和匹配接口。

    属性:
        targets: 所有目标地址集合
        targets_by_format: 按格式分组的目标字典

    示例:
        >>> manager = FormatAwareTargetManager()
        >>> manager.add_target('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        >>> manager.add_target('3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy')
        >>> manager.get_format_stats()
        {'p2pkh': 1, 'p2sh': 1}
    """

    def __init__(self) -> None:
        """初始化格式感知目标管理器"""
        self._all_targets: set[str] = set()
        self._targets_by_format: dict[AddressFormat, set[str]] = {
            AddressFormat.P2PKH: set(),
            AddressFormat.P2SH: set(),
            AddressFormat.BECH32: set(),
            AddressFormat.TAPROOT: set(),
        }
        self._generator = MultiFormatAddressGenerator()
        self._lock = threading.RLock()

        logger.info("FormatAwareTargetManager初始化完成")

    def add_target(self, address: str) -> bool:
        """
        添加单个目标地址，自动检测格式

        参数:
            address: 比特币地址

        返回:
            是否添加成功
        """
        with self._lock:
            try:
                format_type = self._generator.detect_address_format(address)
                normalized = address.strip().lower()

                # 先检查是否已存在（统一小写去重）
                if normalized in self._all_targets:
                    # 检查是否已在正确的格式组中
                    if normalized not in self._targets_by_format[format_type]:
                        self._targets_by_format[format_type].add(normalized)
                        logger.debug(f"补充分类目标地址: {address[:6]}... (格式: {format_type.value})")
                    return False

                self._all_targets.add(normalized)
                self._targets_by_format[format_type].add(normalized)

                logger.debug(f"添加目标地址: {address[:6]}... (格式: {format_type.value})")
                return True

            except ValueError as e:
                logger.warning(f"无法添加目标地址: {address[:6]}... - {e}")
                return False

    def add_targets(self, addresses: list[str]) -> int:
        """
        批量添加目标地址

        参数:
            addresses: 地址列表

        返回:
            成功添加的数量
        """
        count = 0
        for address in addresses:
            if self.add_target(address):
                count += 1

        logger.info(f"批量添加目标: {count}/{len(addresses)} 成功")
        return count

    def load_from_file(self, filepath: str) -> int:
        """
        从文件加载目标地址

        参数:
            filepath: 文件路径

        返回:
            成功加载的数量
        """
        with self._lock:
            try:
                with open(filepath, encoding="utf-8") as f:
                    addresses = [
                        line.strip() for line in f
                        if line.strip() and not line.startswith("#")
                    ]

                count = self.add_targets(addresses)
                logger.info(f"从文件加载目标: {filepath}, {count}/{len(addresses)} 成功")
                return count

            except (OSError, ValueError, UnicodeDecodeError) as e:
                logger.error(f"从文件加载目标失败: {filepath} - {e}")
                return 0

    def get_targets_by_format(self) -> dict[AddressFormat, set[str]]:
        """
        获取按格式分组的目标地址

        返回:
            格式到地址集合的映射
        """
        with self._lock:
            return {fmt: targets.copy() for fmt, targets in self._targets_by_format.items()}

    def get_all_targets(self) -> set[str]:
        """
        获取所有目标地址

        返回:
            所有目标地址集合
        """
        with self._lock:
            return self._all_targets.copy()

    def get_format_stats(self) -> dict[str, int]:
        """
        获取格式统计信息

        返回:
            各格式目标数量统计
        """
        with self._lock:
            return {fmt.value: len(targets) for fmt, targets in self._targets_by_format.items()}

    def has_targets(self, format_type: AddressFormat | None = None) -> bool:
        """
        检查是否存在目标地址

        参数:
            format_type: 指定格式，为None则检查所有格式

        返回:
            是否存在目标
        """
        with self._lock:
            if format_type is None:
                return len(self._all_targets) > 0
            return len(self._targets_by_format.get(format_type, set())) > 0

    def get_target_count(self, format_type: AddressFormat | None = None) -> int:
        """
        获取目标地址数量

        参数:
            format_type: 指定格式，为None则返回总数

        返回:
            目标数量
        """
        with self._lock:
            if format_type is None:
                return len(self._all_targets)
            return len(self._targets_by_format.get(format_type, set()))

    def check_match(
        self, private_key: bytes
    ) -> tuple[bool, str | None, str | None]:
        """
        检查私钥是否匹配任何目标
        【说明】返回第一个匹配，如需所有匹配请用 check_match_all

        参数:
            private_key: 32字节私钥

        返回:
            (is_match, matched_address, matched_format) 元组
        """
        return self._generator.match_address(private_key, self._targets_by_format)

    def check_match_all(
        self, private_key: bytes
    ) -> tuple[bool, list[tuple[str, str]]]:
        """
        检查私钥是否匹配所有目标格式的地址
        【完整检查】遍历所有目标格式，返回所有匹配的地址

        参数:
            private_key: 32字节私钥

        返回:
            (is_match, list[tuple[address, format]]) 元组
            例如: (True, [("1xxx...", "p2pkh"), ("bc1q...", "bech32")])
        """
        with self._lock:
            return self._generator.match_all_formats(private_key, self._targets_by_format)

    def clear(self) -> None:
        """清空所有目标"""
        with self._lock:
            self._all_targets.clear()
            for fmt in self._targets_by_format:
                self._targets_by_format[fmt].clear()
            logger.info("所有目标已清空")

    def get_supported_formats(self) -> list[str]:
        """
        获取支持的目标格式列表

        返回:
            包含目标的格式列表
        """
        with self._lock:
            return [
                fmt.value
                for fmt, targets in self._targets_by_format.items()
                if len(targets) > 0
            ]

    def get_max_batch_size(self) -> int:
        """
        获取最大批量大小（基于格式数量）

        返回:
            批量大小
        """
        supported_count = len(self.get_supported_formats())
        if supported_count == 0:
            return 1
        return supported_count

    def __len__(self) -> int:
        """返回目标地址总数"""
        return self.get_target_count()

    def __contains__(self, address: str) -> bool:
        """支持 in 操作符（统一小写比较）"""
        return address.strip().lower() in self._all_targets

    def __repr__(self) -> str:
        stats = self.get_format_stats()
        return f"FormatAwareTargetManager({stats})"
