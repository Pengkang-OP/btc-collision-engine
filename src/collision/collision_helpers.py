#!/usr/bin/env python3
"""碰撞辅助函数"""

from typing import Any

from ..core.wif import WIF
from ..utils import get_configured_logger

logger = get_configured_logger("collision_helpers")


def encode_private_key_to_wif(private_key: bytes, compressed: bool = True) -> str:
    """将私钥编码为WIF格式
    
    Args:
        private_key: 32字节私钥
        compressed: 是否使用压缩格式
    
    Returns:
        WIF格式的私钥
    """
    return WIF.encode(private_key, compressed=compressed)


def safe_wif_encode(private_key: bytes, compressed: bool = True) -> str:
    """安全的WIF编码函数（不抛出异常）
    
    Args:
        private_key: 32字节私钥
        compressed: 是否使用压缩格式
    
    Returns:
        WIF格式的私钥，或空字符串如果编码失败
    """
    try:
        return encode_private_key_to_wif(private_key, compressed=compressed)
    except Exception:
        return ""


def format_match_result(match: dict[str, Any]) -> str:
    """格式化匹配结果为可读字符串
    
    Args:
        match: 匹配结果字典
    
    Returns:
        格式化的匹配结果字符串
    """
    return (
        f"地址: {match.get('address', '')}\n"
        f"WIF: {match.get('wif', '')}\n"
        f"目标地址: {match.get('target_address', '')}"
    )
