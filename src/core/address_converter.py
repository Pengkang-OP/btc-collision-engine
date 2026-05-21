"""地址转换工具 - 私钥到地址和WIF的完整转换"""

from typing import Any

from ..utils import get_configured_logger
from .base58 import Base58
from .hash_utils import HashUtils
from .secp256k1 import EllipticCurve
from .wif import WIF

# 日志系统由CLI/main.py入口统一初始化
logger = get_configured_logger("AddressConverter")


class AddressConverter:
    """
    地址转换工具

    实现私钥到公钥地址的转换，以及公钥地址到WIF格式的转换，
    严格遵循Bitcoin Core规范。

    示例:
        >>> converter = AddressConverter()
        >>> result = converter.private_key_to_all(private_key)
    """

    def __init__(self) -> None:
        """初始化地址转换器"""
        self.ec = EllipticCurve()
        logger.info("AddressConverter初始化完成")

    def private_key_to_address(self, private_key: bytes, compressed: bool = True) -> dict[str, Any]:
        """
        私钥 → 比特币地址 (严格遵循Bitcoin Core规范)

        6步推导流程:
        1. 椭圆曲线标量乘法 (私钥 → 公钥)
        2. SHA-256哈希
        3. RIPEMD-160哈希 (得到Hash160)
        4. 添加版本字节 (0x00 = Mainnet P2PKH)
        5. 计算校验和 (双重SHA-256)
        6. Base58Check编码

        参数:
            private_key: 32字节私钥
            compressed: 是否使用压缩公钥

        返回:
            包含所有转换结果的字典
        """
        if len(private_key) != 32:
            raise ValueError("私钥必须为32字节")

        # Step 1: 椭圆曲线标量乘法 (私钥 → 公钥)
        public_key = self.ec.generate_public_key(private_key, compressed)

        # Step 2-3: Hash160 = RIPEMD160(SHA256(public_key))
        hash160 = HashUtils.hash160(public_key)

        # Step 4-6: Base58Check编码生成地址
        address = Base58.check_encode(0x00, hash160)

        return {
            "private_key": private_key,
            "public_key": public_key,
            "hash160": hash160,
            "address": address,
            "compressed": compressed,
        }

    def private_key_to_wif(
        self, private_key: bytes, compressed: bool = True, mainnet: bool = True
    ) -> str:
        """
        私钥 → WIF格式 (Wallet Import Format)

        参数:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式
            mainnet: 是否为主网（False为测试网）

        返回:
            WIF格式字符串
        """
        return WIF.encode(private_key, compressed)

    def private_key_to_all(self, private_key: bytes) -> dict[str, Any]:
        """
        私钥 → 所有格式的完整转换

        参数:
            private_key: 32字节私钥

        返回:
            包含所有格式转换结果的字典
        """
        if len(private_key) != 32:
            raise ValueError("私钥必须为32字节")

        # 生成压缩格式
        compressed_result = self.private_key_to_address(private_key, compressed=True)

        # 生成非压缩格式
        uncompressed_result = self.private_key_to_address(private_key, compressed=False)

        # 生成WIF格式
        wif_compressed = self.private_key_to_wif(private_key, compressed=True)
        wif_uncompressed = self.private_key_to_wif(private_key, compressed=False)

        return {
            "private_key": private_key,
            # 压缩格式
            "public_key_compressed": compressed_result["public_key"],
            "hash160_compressed": compressed_result["hash160"],
            "address_compressed": compressed_result["address"],
            "wif_compressed": wif_compressed,
            # 非压缩格式
            "public_key_uncompressed": uncompressed_result["public_key"],
            "hash160_uncompressed": uncompressed_result["hash160"],
            "address_uncompressed": uncompressed_result["address"],
            "wif_uncompressed": wif_uncompressed,
        }

    def wif_to_address(self, wif: str) -> dict[str, Any]:
        """
        WIF → 私钥 → 地址

        参数:
            wif: WIF格式私钥

        返回:
            转换结果字典
        """
        # 解码WIF
        private_key, compressed = WIF.decode(wif)

        # 生成地址
        return self.private_key_to_address(private_key, compressed)

    def validate_conversion(
        self, private_key: bytes, expected_address: str | None = None
    ) -> tuple[bool, str]:
        """
        验证转换正确性

        参数:
            private_key: 私钥
            expected_address: 期望的地址（可选）

        返回:
            (是否有效, 错误信息)
        """
        try:
            # 生成地址
            result = self.private_key_to_all(private_key)

            # 验证WIF可解码
            decoded_key, _ = WIF.decode(result["wif_compressed"])
            if decoded_key != private_key:
                return False, "WIF解码后私钥不匹配"

            # 验证地址格式
            if not result["address_compressed"].startswith("1"):
                return False, "地址格式无效"

            # 验证期望地址
            if expected_address and result["address_compressed"] != expected_address:
                return False, "地址不匹配"

            return True, "验证通过"

        except (ValueError, KeyError, TypeError) as e:
            return False, str(e)
