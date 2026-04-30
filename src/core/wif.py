# -*- coding: utf-8 -*-
"""WIF (Wallet Import Format) 编解码工具"""

from typing import Tuple
from .base58 import Base58
from ..utils import init_logging, get_configured_logger

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("WIF")


class WIF:
    """
    WIF (Wallet Import Format) 编解码工具

    用于比特币私钥的编码和解码，支持压缩和非压缩格式。
    压缩格式以'K'或'L'开头，非压缩格式以'5'开头。
    """

    @staticmethod
    def encode(private_key: bytes, compressed: bool = True) -> str:
        """
        将私钥编码为WIF格式

        参数:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式，默认True

        返回:
            WIF编码的字符串
            - 压缩格式: 以 'K' 或 'L' 开头 (52字符)
            - 非压缩格式: 以 '5' 开头 (51字符)

        异常:
            ValueError: 当私钥长度无效时
        """
        try:
            if not isinstance(private_key, bytes):
                raise ValueError("私钥必须是字节串")
            if len(private_key) != 32:
                raise ValueError("私钥长度必须为32字节")

            # 构建payload: 私钥 + [压缩标志]
            # 注意: check_encode 会自动添加版本字节和校验和
            if compressed:
                payload = private_key + b"\x01"
            else:
                payload = private_key

            # Base58Check编码: 版本字节(0x80) + payload + 4字节校验和
            return Base58.check_encode(0x80, payload)
        except ValueError:
            # 预期内的验证错误，直接重新抛出，不记录日志
            # ValueError通常包含输入验证信息（如私钥长度），不应记录
            raise
        except Exception as e:
            # 意外错误：仅记录异常类型，不记录任何用户输入
            # 私钥信息绝对不能记录到日志
            logger.error("编码WIF时发生未预期错误: %s", type(e).__name__)
            raise ValueError("WIF编码失败")

    @staticmethod
    def decode(wif: str) -> Tuple[bytes, bool]:
        """
        解码WIF格式私钥

        参数:
            wif: WIF编码的字符串

        返回:
            (private_key, is_compressed) 元组

        异常:
            ValueError: 当WIF格式无效时
        """
        try:
            if not isinstance(wif, str):
                raise ValueError("WIF必须是字符串")

            # 解码Base58Check
            version, data = Base58.check_decode(wif)

            # 验证版本字节
            if version != 0x80:
                raise ValueError("WIF版本字节无效")

            # 检查是否为压缩格式（最后一个字节为0x01）
            if len(data) == 33 and data[-1] == 0x01:
                return data[:32], True
            elif len(data) == 32:
                return data, False
            else:
                raise ValueError("WIF数据长度无效")
        except ValueError:
            # 预期内的验证错误，直接重新抛出，不记录日志
            raise
        except Exception as e:
            # 意外错误：仅记录异常类型，不记录任何用户输入
            # WIF字符串本身包含私钥信息，绝对不能记录
            logger.error("解码WIF时发生未预期错误: %s", type(e).__name__)
            raise ValueError("WIF格式无效")
