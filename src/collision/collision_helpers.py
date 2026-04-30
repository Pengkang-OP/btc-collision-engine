# -*- coding: utf-8 -*-
"""碰撞引擎辅助工具函数

提供碰撞引擎中常用的辅助函数，避免代码重复。
"""

from typing import Tuple, Optional
from ..core import WIF


def encode_private_key_to_wif(private_key: bytes, compressed: bool = True) -> str:
    """将私钥编码为WIF格式（统一封装函数）

    这是一个统一封装函数，用于在碰撞引擎中编码私钥为WIF格式。
    所有需要WIF编码的地方都应该使用此函数，而不是直接调用WIF.encode。

    参数:
        private_key: 32字节私钥
        compressed: 是否使用压缩格式，默认True（比特币标准）

    返回:
        WIF编码的字符串

    异常:
        ValueError: 当私钥无效时

    示例:
        >>> private_key = secrets.token_bytes(32)
        >>> wif = encode_private_key_to_wif(private_key)
        >>> print(wif[:10])  # 显示前10个字符
    """
    return WIF.encode(private_key, compressed)


def format_match_result(
    private_key: bytes, address: str, compressed: bool = True
) -> Tuple[bytes, str, str]:
    """格式化匹配结果，返回私钥、地址和WIF

    统一处理碰撞匹配结果的格式化，避免在各处重复编码WIF。

    参数:
        private_key: 32字节私钥
        address: 比特币地址
        compressed: 是否使用压缩格式，默认True

    返回:
        (private_key, address, wif) 元组

    示例:
        >>> pk, addr, wif = format_match_result(private_key, "1ABC...")
        >>> print(f"地址: {addr}")
        >>> print(f"WIF: {wif}")
    """
    wif = encode_private_key_to_wif(private_key, compressed)
    return (private_key, address, wif)


def safe_wif_encode(private_key: bytes, compressed: bool = True) -> Optional[str]:
    """安全地编码私钥为WIF，失败时返回None而不是抛出异常

    用于回调函数等场景，避免异常中断流程。

    参数:
        private_key: 32字节私钥
        compressed: 是否使用压缩格式，默认True

    返回:
        WIF字符串，失败时返回None
    """
    try:
        return encode_private_key_to_wif(private_key, compressed)
    except (ValueError, Exception):
        return None
