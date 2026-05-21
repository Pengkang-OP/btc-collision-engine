"""多格式比特币地址生成器

支持从单个私钥生成多种格式的比特币地址:
- P2PKH (Pay-to-Public-Key-Hash) - 以'1'开头
- P2SH (Pay-to-Script-Hash) - 以'3'开头
- Bech32 (SegWit v0) - 以'bc1q'开头
- Taproot (SegWit v1) - 以'bc1p'开头

示例:
    >>> generator = MultiFormatAddressGenerator()
    >>> private_key = secrets.token_bytes(32)
    >>> addresses = generator.generate_all_formats(private_key)
    >>> print(addresses['p2pkh'], addresses['p2sh'], addresses['bech32'])
"""

import secrets
from enum import Enum

from ..utils import get_configured_logger
from ..utils.bech32_codec import bech32_encode
from .bitcoin_key_validator import BitcoinKeyValidator

logger = get_configured_logger("MultiFormatAddressGenerator")


class AddressFormat(Enum):
    """比特币地址格式枚举"""

    P2PKH = "p2pkh"
    P2SH = "p2sh"
    BECH32 = "bech32"
    TAPROOT = "taproot"


class MultiFormatAddressGenerator:
    """
    多格式比特币地址生成器

    从单个私钥生成所有支持的地址格式，支持智能格式检测和按需生成。

    属性:
        auto_detect: 是否自动检测支持的格式
        prefer_compressed: 是否优先使用压缩公钥

    示例:
        >>> gen = MultiFormatAddressGenerator()
        >>> key = secrets.token_bytes(32)
        >>> all_addrs = gen.generate_all_formats(key)
        >>> p2pkh_only = gen.generate_address(key, AddressFormat.P2PKH)
    """

    def __init__(self, auto_detect: bool = True, prefer_compressed: bool = True) -> None:
        """
        初始化多格式地址生成器

        参数:
            auto_detect: 是否自动检测支持的格式，默认True
            prefer_compressed: 是否优先使用压缩公钥，默认True
        """
        self.auto_detect = auto_detect
        self.prefer_compressed = prefer_compressed
        self._public_key_cache: bytes | None = None
        logger.info(
            f"MultiFormatAddressGenerator初始化: auto_detect={auto_detect}, "
            f"prefer_compressed={prefer_compressed}"
        )

    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        """
        从私钥生成公钥

        参数:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式

        返回:
            公钥字节串 (33字节压缩 / 65字节非压缩)
        """
        from .address_generator import P2PKHAddressGenerator

        generator = P2PKHAddressGenerator()
        return generator.private_key_to_public_key(private_key, compressed)

    def generate_p2pkh_address(self, private_key: bytes) -> str:
        """
        生成P2PKH地址 (Pay-to-Public-Key-Hash)

        格式: 以'1'开头，Base58Check编码

        参数:
            private_key: 32字节私钥

        返回:
            P2PKH地址字符串
        """
        public_key = self.generate_public_key(private_key, self.prefer_compressed)
        from .address_generator import P2PKHAddressGenerator

        generator = P2PKHAddressGenerator()
        return generator.public_key_to_address(public_key)

    def generate_p2sh_address(self, private_key: bytes) -> str:
        """
        生成P2SH地址 (Pay-to-Script-Hash)

        格式: 以'3'开头，Base58Check编码

        参数:
            private_key: 32字节私钥

        返回:
            P2SH地址字符串
        """
        public_key = self.generate_public_key(private_key, compressed=True)
        return BitcoinKeyValidator.generate_p2sh_address(public_key)

    def generate_bech32_address(self, private_key: bytes, hrp: str = "bc") -> str:
        """
        生成Bech32地址 (SegWit v0 - P2WPKH)

        格式: 以'bc1q'开头，Bech32编码

        参数:
            private_key: 32字节私钥
            hrp: 人类可读部分 (mainnet='bc', testnet='tb')

        返回:
            Bech32地址字符串
        """
        public_key = self.generate_public_key(private_key, compressed=True)
        return BitcoinKeyValidator.generate_bech32_address(public_key, hrp)

    def generate_taproot_address(self, private_key: bytes, hrp: str = "bc") -> str:
        """
        生成Taproot地址 (SegWit v1 - P2TR)

        格式: 以'bc1p'开头，Bech32m编码

        注意: Taproot使用xonly公钥 (32字节，仅x坐标)

        参数:
            private_key: 32字节私钥
            hrp: 人类可读部分 (mainnet='bc', testnet='tb')

        返回:
            Taproot地址字符串
        """
        try:
            import coincurve

            priv_key = coincurve.PrivateKey(private_key)
            pub_key = priv_key.public_key
            xonly_pubkey = pub_key.format(compressed=True)[1:33]
            return bech32_encode(hrp, 1, xonly_pubkey, "bech32m")
        except ImportError:
            logger.warning("coincurve不可用，无法生成Taproot地址")
            raise ValueError(
                "coincurve 不可用，无法生成 Taproot 地址。请安装 coincurve: pip install coincurve"
            )
        except Exception as e:
            logger.error(f"Taproot地址生成失败: {e}")
            raise ValueError(f"Taproot地址生成失败: {e}") from e

    def generate_address(
        self, private_key: bytes, format_type: AddressFormat = AddressFormat.P2PKH
    ) -> str:
        """
        生成指定格式的比特币地址

        参数:
            private_key: 32字节私钥
            format_type: 地址格式类型

        返回:
            对应格式的比特币地址

        异常:
            ValueError: 当私钥长度无效或格式不支持时
        """
        if len(private_key) != 32:
            raise ValueError(f"私钥必须为32字节，当前为{len(private_key)}字节")

        if format_type == AddressFormat.P2PKH:
            return self.generate_p2pkh_address(private_key)
        elif format_type == AddressFormat.P2SH:
            return self.generate_p2sh_address(private_key)
        elif format_type == AddressFormat.BECH32:
            return self.generate_bech32_address(private_key)
        elif format_type == AddressFormat.TAPROOT:
            return self.generate_taproot_address(private_key)
        else:
            raise ValueError(f"不支持的地址格式: {format_type}")

    def generate_all_formats(self, private_key: bytes, hrp: str = "bc") -> dict[str, str]:
        """
        生成所有支持的地址格式

        参数:
            private_key: 32字节私钥
            hrp: 人类可读部分 (mainnet='bc', testnet='tb')

        返回:
            包含所有格式地址的字典
            {
                'p2pkh': '1xxx...',
                'p2sh': '3xxx...',
                'bech32': 'bc1qxxx...',
                'taproot': 'bc1pxxx...'
            }
        """
        if len(private_key) != 32:
            raise ValueError(f"私钥必须为32字节，当前为{len(private_key)}字节")

        result = {}

        try:
            result["p2pkh"] = self.generate_p2pkh_address(private_key)
        except Exception as e:
            logger.error(f"P2PKH地址生成失败: {e}")
            result["p2pkh"] = ""

        try:
            result["p2sh"] = self.generate_p2sh_address(private_key)
        except Exception as e:
            logger.error(f"P2SH地址生成失败: {e}")
            result["p2sh"] = ""

        try:
            result["bech32"] = self.generate_bech32_address(private_key, hrp)
        except Exception as e:
            logger.error(f"Bech32地址生成失败: {e}")
            result["bech32"] = ""

        try:
            result["taproot"] = self.generate_taproot_address(private_key, hrp)
        except Exception as e:
            logger.error(f"Taproot地址生成失败: {e}")
            result["taproot"] = ""

        return result

    def detect_address_format(self, address: str) -> AddressFormat:
        """
        检测比特币地址格式

        参数:
            address: 比特币地址字符串

        返回:
            地址格式枚举

        异常:
            ValueError: 当地址格式无法识别时
        """
        if not address:
            raise ValueError("地址不能为空")

        address = address.strip().lower()

        if address.startswith("1"):
            return AddressFormat.P2PKH
        elif address.startswith("3"):
            return AddressFormat.P2SH
        elif address.startswith("bc1p"):
            return AddressFormat.TAPROOT
        elif address.startswith("bc1"):
            return AddressFormat.BECH32
        else:
            raise ValueError(f"无法识别的地址格式: {address[:20]}...")

    def get_targets_by_format(self, targets: set[str]) -> dict[AddressFormat, set[str]]:
        """
        按格式分类目标地址

        参数:
            targets: 目标地址集合

        返回:
            按格式分组的地址字典
        """
        result: dict[AddressFormat, set[str]] = {
            AddressFormat.P2PKH: set(),
            AddressFormat.P2SH: set(),
            AddressFormat.BECH32: set(),
            AddressFormat.TAPROOT: set(),
        }

        for address in targets:
            try:
                fmt = self.detect_address_format(address)
                result[fmt].add(address.lower())
            except ValueError as e:
                logger.warning(f"无法识别地址格式: {address[:20]}... - {e}")

        return result

    def match_address(
        self, private_key: bytes, targets: dict[AddressFormat, set[str]]
    ) -> tuple[bool, str | None, str | None]:
        """
        检查私钥生成的地址是否匹配任何格式的目标
        【优化】只生成目标格式对应的地址，提升性能
        【说明】返回第一个匹配，如需所有匹配请用 match_all_formats

        参数:
            private_key: 32字节私钥
            targets: 按格式分组的目标地址字典

        返回:
            (is_match, matched_address, matched_format) 元组
        """
        for fmt, target_set in targets.items():
            if len(target_set) == 0:
                continue

            try:
                if fmt == AddressFormat.P2PKH:
                    address = self.generate_p2pkh_address(private_key)
                elif fmt == AddressFormat.P2SH:
                    address = self.generate_p2sh_address(private_key)
                elif fmt == AddressFormat.BECH32:
                    address = self.generate_bech32_address(private_key)
                elif fmt == AddressFormat.TAPROOT:
                    address = self.generate_taproot_address(private_key)
                else:
                    continue

                if address and address.lower() in target_set:
                    return True, address, fmt.value

            except Exception as e:
                logger.warning(f"生成{fmt.value}地址失败: {e}")
                continue

        return False, None, None

    def match_all_formats(
        self, private_key: bytes, targets: dict[AddressFormat, set[str]]
    ) -> tuple[bool, list[tuple[str, str]]]:
        """
        检查私钥生成的地址是否匹配所有目标格式的地址
        【完整检查】遍历所有目标格式，返回所有匹配的地址

        参数:
            private_key: 32字节私钥
            targets: 按格式分组的目标地址字典

        返回:
            (is_match, list[tuple[address, format]]) 元组
            例如: (True, [("1xxx...", "p2pkh"), ("bc1q...", "bech32")])
        """
        matches = []
        for fmt, target_set in targets.items():
            if len(target_set) == 0:
                continue

            try:
                if fmt == AddressFormat.P2PKH:
                    address = self.generate_p2pkh_address(private_key)
                elif fmt == AddressFormat.P2SH:
                    address = self.generate_p2sh_address(private_key)
                elif fmt == AddressFormat.BECH32:
                    address = self.generate_bech32_address(private_key)
                elif fmt == AddressFormat.TAPROOT:
                    address = self.generate_taproot_address(private_key)
                else:
                    continue

                if address and address.lower() in target_set:
                    matches.append((address, fmt.value))

            except Exception as e:
                logger.warning(f"生成{fmt.value}地址失败: {e}")
                continue

        return len(matches) > 0, matches

    def validate_format_support(self) -> dict[str, bool]:
        """
        验证各格式的生成支持状态

        返回:
            格式支持状态字典
        """
        test_key = secrets.token_bytes(32)

        return {
            "p2pkh": bool(self.generate_p2pkh_address(test_key)),
            "p2sh": bool(self.generate_p2sh_address(test_key)),
            "bech32": bool(self.generate_bech32_address(test_key)),
            "taproot": bool(self.generate_taproot_address(test_key)),
        }
