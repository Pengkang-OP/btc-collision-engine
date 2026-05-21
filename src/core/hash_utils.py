"""哈希工具类"""

import hashlib


class HashUtils:
    """
    哈希工具类

    提供比特币中使用的各种哈希函数，包括SHA-256、RIPEMD-160和Hash160。
    """

    @staticmethod
    def sha256(data: bytes) -> bytes:
        """
        计算SHA-256哈希

        参数:
            data: 输入字节串

        返回:
            32字节SHA-256哈希值
        """
        return hashlib.sha256(data).digest()

    @staticmethod
    def ripemd160(data: bytes) -> bytes:
        """
        计算RIPEMD-160哈希

        参数:
            data: 输入字节串

        返回:
            20字节RIPEMD-160哈希值
        """
        return hashlib.new("ripemd160", data).digest()

    @staticmethod
    def hash160(data: bytes) -> bytes:
        """
        计算Hash160 = RIPEMD160(SHA256(data))

        参数:
            data: 输入字节串

        返回:
            20字节Hash160值
        """
        return HashUtils.ripemd160(HashUtils.sha256(data))

    @staticmethod
    def key_fingerprint(private_key: bytes, length: int = 16) -> str:
        """
        计算私钥的安全指纹（SHA256前N位hex）

        用于日志/验证输出中安全标识私钥而不暴露明文。
        统一避免多处重复 hashlib.sha256(key).hexdigest()[:16] 模式。

        参数:
            private_key: 32字节私钥
            length: 指纹长度（字符数），默认16

        返回:
            私钥SHA256指纹的前length个hex字符

        示例:
            >>> fp = HashUtils.key_fingerprint(b'\\x00' * 32)
            >>> len(fp)
            16
        """
        return hashlib.sha256(private_key).hexdigest()[:length]

    @staticmethod
    def double_sha256(data: bytes) -> bytes:
        """
        计算双SHA-256哈希

        参数:
            data: 输入字节串

        返回:
            32字节双SHA-256哈希值
        """
        return HashUtils.sha256(HashUtils.sha256(data))

    @staticmethod
    def hash160_to_address(hash160: bytes, version: int = 0x00) -> str:
        """
        将Hash160转换为P2PKH地址

        参数:
            hash160: 20字节Hash160值
            version: 版本字节，默认0x00 (P2PKH主网)

        返回:
            Base58Check编码的P2PKH地址

        # 使用 Bitcoin Wiki 标准测试向量（hash160 → 创世地址，私钥=1，公开已知）
        示例:
            >>> hash160 = bytes.fromhex('0000000000000000000000000000000000000000')
            >>> address = HashUtils.hash160_to_address(hash160)
            >>> print(address)
            1111111111111111111114oLvT2  # 全零 hash160 地址（仅格式验证用）
        """
        if len(hash160) != 20:
            raise ValueError(f"Hash160必须为20字节，当前为{len(hash160)}字节")

        # 延迟导入避免循环依赖
        from .base58 import Base58

        return Base58.check_encode(version, hash160)
