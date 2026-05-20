"""Bitcoin Core规范合规性验证"""

from ..utils import get_configured_logger
<<<<<<< Updated upstream
from .secp256k1 import Secp256k1

# 日志系统由CLI/main.py入口统一初始化
=======
logger = get_configured_logger("BitcoinComplianceValidator")


class BitcoinComplianceValidator:
    """
    Bitcoin Core规范合规性验证器

    验证生成的密钥对和地址是否符合Bitcoin Core技术规范，
    确保完全兼容标准比特币网络。

    示例:
        >>> validator = BitcoinComplianceValidator()
        >>> is_valid, issues = validator.validate(data)
    """

    def __init__(self) -> None:
        """初始化验证器"""
        logger.info("BitcoinComplianceValidator初始化完成")

    def validate(self, data: dict) -> tuple[bool, list[str]]:
        """
        验证比特币规范合规性

        参数:
            data: 要验证的数据字典
                应包含:
                - private_key: 私钥（字节串）
                - public_key: 公钥（字节串）
                - address: 比特币地址
                - wif: WIF格式私钥
                - hash160: Hash160值
                - compressed: 是否压缩格式

        返回:
            (是否合规, 问题列表)
        """
        issues = []

        # 1. 私钥格式验证
        issues.extend(self._validate_private_key(data))

        # 2. 公钥格式验证
        issues.extend(self._validate_public_key(data))

        # 3. 地址格式验证
        issues.extend(self._validate_address(data))

        # 4. WIF格式验证
        issues.extend(self._validate_wif(data))

        # 5. Hash160验证
        issues.extend(self._validate_hash160(data))

        is_valid = len(issues) == 0

        if is_valid:
            logger.debug("合规性验证通过")
        else:
            logger.warning("合规性验证失败: %d 个问题", len(issues))

        return is_valid, issues

    def _validate_private_key(self, data: dict) -> list[str]:
        """验证私钥格式"""
        issues = []

        private_key = data.get("private_key")

        if private_key is None:
            issues.append("缺少私钥")
            return issues

        if not isinstance(private_key, (bytes, bytearray)):
            issues.append("私钥必须是字节串")
            return issues

        if len(private_key) != 32:
            issues.append(f"私钥长度必须为32字节，当前为{len(private_key)}字节")

        # 验证私钥范围 (1 <= k < n)
        key_int = int.from_bytes(private_key, "big")
<<<<<<< Updated upstream
        if key_int >= Secp256k1.N:
=======
        from .secp256k1 import Secp256k1
        SECP256K1_ORDER = Secp256k1.N

        if key_int < 1:
            issues.append("私钥必须大于0")

        if key_int >= SECP256K1_ORDER:
            issues.append("私钥必须小于secp256k1曲线阶")

        return issues

    def _validate_public_key(self, data: dict) -> list[str]:
        """验证公钥格式"""
        issues = []

        public_key = data.get("public_key")
        compressed = data.get("compressed", True)

        if public_key is None:
            issues.append("缺少公钥")
            return issues

        if not isinstance(public_key, (bytes, bytearray)):
            issues.append("公钥必须是字节串")
            return issues

        if compressed:
            # 压缩公钥: 33字节，前缀0x02或0x03
            if len(public_key) != 33:
                issues.append(f"压缩公钥长度必须为33字节，当前为{len(public_key)}字节")

            if public_key[0] not in [0x02, 0x03]:
                issues.append(f"压缩公钥前缀必须为0x02或0x03，当前为0x{public_key[0]:02x}")
        else:
            # 非压缩公钥: 65字节，前缀0x04
            if len(public_key) != 65:
                issues.append(f"非压缩公钥长度必须为65字节，当前为{len(public_key)}字节")

            if public_key[0] != 0x04:
                issues.append(f"非压缩公钥前缀必须为0x04，当前为0x{public_key[0]:02x}")

        return issues

    def _validate_address(self, data: dict) -> list[str]:
        """验证地址格式"""
        issues = []

        address = data.get("address")

        if address is None:
            issues.append("缺少地址")
            return issues

        if not isinstance(address, str):
            issues.append("地址必须是字符串")
            return issues

        # P2PKH地址以'1'开头
        if not address.startswith("1"):
            issues.append(f"P2PKH地址必须以'1'开头，当前为'{address[0]}'")

        # P2PKH地址长度33-34字符
        if len(address) not in [33, 34]:
            issues.append(f"P2PKH地址长度必须为33或34字符，当前为{len(address)}字符")

        # 验证Base58字符集
        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not all(c in base58_chars for c in address):
            issues.append("地址包含无效的Base58字符")

        return issues

    def _validate_wif(self, data: dict) -> list[str]:
        """验证WIF格式"""
        issues = []

        wif = data.get("wif")

        if wif is None:
            issues.append("缺少WIF")
            return issues

        if not isinstance(wif, str):
            issues.append("WIF必须是字符串")
            return issues

        # WIF必须以5、K或L开头
        if not wif.startswith(("5", "K", "L")):
            issues.append(f"WIF必须以5、K或L开头，当前为'{wif[0]}'")

        # 非压缩WIF: 51字符
        # 压缩WIF: 52字符
        if wif.startswith("5"):
            if len(wif) != 51:
                issues.append(f"非压缩WIF长度必须为51字符，当前为{len(wif)}字符")
        else:
            if len(wif) != 52:
                issues.append(f"压缩WIF长度必须为52字符，当前为{len(wif)}字符")

        # 验证Base58字符集
        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not all(c in base58_chars for c in wif):
            issues.append("WIF包含无效的Base58字符")

        return issues

    def _validate_hash160(self, data: dict) -> list[str]:
        """验证Hash160"""
        issues = []

        hash160 = data.get("hash160")

        if hash160 is None:
            issues.append("缺少Hash160")
            return issues

        if isinstance(hash160, bytes):
            if len(hash160) != 20:
                issues.append(f"Hash160必须为20字节，当前为{len(hash160)}字节")
        elif isinstance(hash160, str):
            if len(hash160) != 40:
                issues.append(f"Hash160十六进制字符串必须为40字符，当前为{len(hash160)}字符")
        else:
            issues.append("Hash160必须是字节串或十六进制字符串")

        return issues

    def validate_batch(self, data_list: list[dict]) -> list[tuple[bool, list[str]]]:
        """
        批量验证

        参数:
            data_list: 数据列表

        返回:
            验证结果列表
        """
        results = []

        for _i, data in enumerate(data_list):
            is_valid, issues = self.validate(data)
            results.append((is_valid, issues))

        valid_count = sum(1 for is_valid, _ in results if is_valid)

        logger.info("批量验证完成: %d/%d 通过", valid_count, len(data_list))

        return results
