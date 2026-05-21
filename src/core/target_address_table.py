"""比特币目标地址表 - 支持高效查询与比对"""

import json
import threading
from datetime import datetime
from pathlib import Path

from ..utils import get_configured_logger
from .hash_utils import HashUtils
from .optimized_address_generator import OptimizedP2PKHAddressGenerator
from .wif import WIF

# 日志系统由CLI/main.py入口统一初始化
logger = get_configured_logger("BitcoinTargetTable")


class BitcoinTargetTable:
    """
    比特币目标地址表 - 支持高效查询与比对

    使用Hash160 Set结构实现O(1)时间复杂度的地址匹配查询。
    支持从WIF格式地址批量加载，线程安全设计。

    属性:
        _hash160_set: Hash160目标集合 (O(1)查找)
        _target_map: Hash160 → 详细信息映射
        _lock: 线程安全锁

    示例:
        >>> table = BitcoinTargetTable()
        >>> table.add_target(wif="5HueCGU...", address="1A1z...", hash160=b'...')
        >>> is_match, info = table.check_match(hash160)
    """

    def __init__(self, max_size: int = 10_000_000) -> None:
        """
        初始化目标地址表

        参数:
            max_size: 最大目标地址数量，默认1000万
        """
        self._hash160_set: set[bytes] = set()
        self._target_map: dict[bytes, dict] = {}
        self._lock = threading.RLock()
        self._max_size = max_size

        logger.info("BitcoinTargetTable初始化完成，最大容量: %d", max_size)

    def add_target(
        self, wif: str, address: str, hash160: bytes, address_type: str = "p2pkh"
    ) -> None:
        """
        添加目标地址

        参数:
            wif: WIF格式私钥
            address: 比特币地址
            hash160: RIPEMD160(SHA256(pubkey)) 20字节哈希
            address_type: 地址类型，默认'p2pkh'

        异常:
            ValueError: 当hash160长度无效或超过最大容量时
        """
        if len(hash160) != 20:
            raise ValueError(f"Hash160必须为20字节，当前为{len(hash160)}字节")

        with self._lock:
            if len(self._hash160_set) >= self._max_size:
                raise ValueError(f"目标地址表已满（{self._max_size}个地址）")

            self._hash160_set.add(hash160)
            self._target_map[hash160] = {
                "wif": wif,
                "address": address,
                "hash160": hash160.hex(),
                "type": address_type,
                "added_at": datetime.utcnow().isoformat(),
            }

            if len(self._hash160_set) % 10000 == 0:
                logger.info("已加载 %d 个目标地址", len(self._hash160_set))

    def check_match(self, hash160: bytes) -> tuple[bool, dict | None]:
        """
        检查是否匹配目标地址 - O(1)时间复杂度

        参数:
            hash160: 要检查的Hash160值

        返回:
            (is_match, target_info) 元组
            - is_match: 是否匹配
            - target_info: 匹配的目标信息（如果匹配）
        """
        with self._lock:
            if hash160 in self._hash160_set:
                return True, self._target_map.get(hash160)
            return False, None

    def load_from_wif_list(self, wif_list: list[str]) -> int:
        """
        从WIF列表批量加载目标地址

        参数:
            wif_list: WIF格式私钥列表

        返回:
            成功加载的目标地址数量
        """
        loaded_count = 0
        generator = OptimizedP2PKHAddressGenerator()

        for i, wif in enumerate(wif_list):
            try:
                # 解码WIF获取私钥和压缩标志
                private_key, compressed = WIF.decode(wif)

                # 生成公钥和地址
                address = generator.generate_from_private_key(private_key, compressed)
                public_key = generator.private_key_to_public_key(private_key, compressed)

                # 提取hash160
                hash160 = HashUtils.hash160(public_key)

                # 添加到目标表
                self.add_target(
                    wif=wif,
                    address=address,
                    hash160=hash160,
                    address_type="compressed" if compressed else "uncompressed",
                )

                loaded_count += 1

            except Exception as e:
                logger.error("加载WIF地址 %d 失败: %s", i, str(e))
                continue

        logger.info("批量加载完成: %d/%d 成功", loaded_count, len(wif_list))
        return loaded_count

    def load_from_file(self, filepath: str) -> int:
        """
        从文件批量加载目标地址

        支持JSON/CSV/TXT格式

        参数:
            filepath: 文件路径

        返回:
            成功加载的目标地址数量
        """
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        suffix = path.suffix.lower()

        if suffix == ".json":
            return self._load_from_json(path)
        elif suffix == ".csv":
            return self._load_from_csv(path)
        elif suffix == ".txt":
            return self._load_from_txt(path)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

    def _load_from_json(self, filepath: Path) -> int:
        """从JSON文件加载"""
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            wif_list = data
        elif isinstance(data, dict) and "targets" in data:
            wif_list = [t["wif"] for t in data["targets"] if "wif" in t]
        else:
            raise ValueError("JSON格式无效")

        return self.load_from_wif_list(wif_list)

    def _load_from_csv(self, filepath: Path) -> int:
        """从CSV文件加载"""
        import csv

        wif_list = []
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "wif" in row:
                    wif_list.append(row["wif"])

        return self.load_from_wif_list(wif_list)

    def _load_from_txt(self, filepath: Path) -> int:
        """从TXT文件加载（每行一个WIF）"""
        with open(filepath, encoding="utf-8") as f:
            wif_list = [line.strip() for line in f if line.strip()]

        return self.load_from_wif_list(wif_list)

    def get_statistics(self) -> dict:
        """
        获取目标地址表统计信息

        返回:
            统计信息字典
        """
        with self._lock:
            return {
                "total_targets": len(self._hash160_set),
                "max_capacity": self._max_size,
                "usage_percent": len(self._hash160_set) / self._max_size * 100,
                "memory_usage_mb": len(self._hash160_set) * 40 / 1024 / 1024,
            }

    def clear(self) -> None:
        """清空目标地址表"""
        with self._lock:
            self._hash160_set.clear()
            self._target_map.clear()
            logger.info("目标地址表已清空")
