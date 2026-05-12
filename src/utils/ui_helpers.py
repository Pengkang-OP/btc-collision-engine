#!/usr/bin/env python3
"""
UI工具函数模块

提供GUI界面常用的工具函数，包括时间格式化、文本处理、数字格式化等。
"""

import math
import re
from datetime import datetime


def format_timestamp(timestamp: str, format_str: str = "%m-%d %H:%M") -> str | None:
    """
    格式化时间戳字符串

    Args:
        timestamp: ISO格式的时间戳字符串
        format_str: 输出格式字符串，默认为 "%m-%d %H:%M"

    Returns:
        格式化后的时间字符串，如果解析失败返回None
    """
    if not timestamp:
        return None

    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime(format_str)
    except (ValueError, TypeError):
        return None


def format_mode_name(mode: str) -> str:
    """
    将引擎模式名称转换为中文显示

    Args:
        mode: 引擎模式名称（random/range/brute_force/gpu）

    Returns:
        中文模式名称
    """
    mode_map = {"random": "随机", "range": "范围", "brute_force": "穷举", "gpu": "GPU"}
    return mode_map.get(mode, mode)


def format_number_with_commas(number: int | float) -> str:
    """
    格式化数字，添加千位分隔符

    Args:
        number: 要格式化的数字

    Returns:
        格式化后的数字字符串
    """
    if isinstance(number, float):
        return f"{number:,.2f}"
    return f"{number:,}"


def format_speed(speed: float) -> str:
    """
    格式化速度显示

    Args:
        speed: 速度值（keys/s）

    Returns:
        格式化后的速度字符串
    """
    # 处理负数、NaN和inf
    if speed < 0 or math.isnan(speed) or math.isinf(speed):
        return "0/s"

    if speed < 1000:
        return f"{speed:.0f}/s"
    elif speed < 1000000:
        return f"{speed / 1000:.2f}K/s"
    elif speed < 1000000000:
        return f"{speed / 1000000:.2f}M/s"
    else:
        return f"{speed / 1000000000:.2f}B/s"


def format_elapsed_time(seconds: float) -> str:
    """
    格式化运行时间

    Args:
        seconds: 秒数

    Returns:
        格式化后的时间字符串 (HH:MM:SS)
    """
    if seconds < 0:
        return "00:00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_eta(seconds: float) -> str:
    """
    格式化预计剩余时间

    Args:
        seconds: 秒数

    Returns:
        格式化后的ETA字符串
    """
    if seconds < 0 or seconds == float("inf"):
        return "-"

    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        return f"{seconds / 86400:.1f}d"


def truncate_address(address: str, max_length: int = 20) -> str:
    """
    截断地址显示

    Args:
        address: 完整地址
        max_length: 最大显示长度

    Returns:
        截断后的地址字符串
    """
    # 处理无效的max_length
    if max_length <= 0:
        return "..."

    if len(address) <= max_length:
        return address
    return f"{address[:max_length]}..."


def validate_address_format(address: str) -> bool:
    """
    验证地址格式

    支持以下格式：
    - P2PKH 地址（以 1 开头）
    - P2SH 地址（以 3 开头）
    - Bech32 地址（以 bc1 开头）
    - WIF 私钥（以 5/K/L 开头）
    - 压缩公钥（66 位十六进制，02/03/04 开头）
    - 非压缩公钥（130 位十六进制，04 开头）

    Args:
        address: 要验证的地址

    Returns:
        是否为有效格式
    """
    if not address or not isinstance(address, str):
        return False

    address = address.strip()

    if not address:
        return False

    # P2PKH 地址 (以 1 开头，25-34 字符)
    if re.match(r"^1[a-km-zA-HJ-NP-Z1-9]{25,34}$", address):
        return True

    # P2SH 地址 (以 3 开头，25-34 字符)
    if re.match(r"^3[a-km-zA-HJ-NP-Z1-9]{25,34}$", address):
        return True

    # Bech32 地址 (以 bc1 开头，25-39 字符小写)
    if re.match(r"^bc1[a-z0-9]{25,39}$", address):
        return True

    # WIF 私钥 (以 5/K/L 开头，51-52 字符)
    if re.match(r"^[5KL][a-km-zA-HJ-NP-Z1-9]{50,51}$", address):
        return True

    # 压缩公钥 (33 字节 = 66 字符，02/03 开头)
    if re.match(r"^(02|03)[0-9a-fA-F]{64}$", address):
        return True

    # 非压缩公钥 (65 字节 = 130 字符，04 开头)
    if re.match(r"^04[0-9a-fA-F]{128}$", address):
        return True

    return False


def validate_hex_string(hex_str: str, allow_prefix: bool = True) -> bool:
    """
    验证十六进制字符串

    Args:
        hex_str: 要验证的字符串
        allow_prefix: 是否允许 0x 前缀

    Returns:
        是否为有效的十六进制字符串
    """
    if not hex_str or not isinstance(hex_str, str):
        return False

    hex_str = hex_str.strip()

    if allow_prefix and hex_str.startswith(("0x", "0X")):
        hex_str = hex_str[2:]

    if not hex_str:
        return False

    try:
        int(hex_str, 16)
        return True
    except ValueError:
        return False


def format_bytes(bytes_value: int) -> str:
    """
    格式化字节数显示

    Args:
        bytes_value: 字节数

    Returns:
        格式化后的字节字符串
    """
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024**2:
        return f"{bytes_value / 1024:.2f} KB"
    elif bytes_value < 1024**3:
        return f"{bytes_value / 1024**2:.2f} MB"
    elif bytes_value < 1024**4:
        return f"{bytes_value / 1024**3:.2f} GB"
    else:
        return f"{bytes_value / 1024**4:.2f} TB"


def sanitize_display_text(text: str) -> str:
    """
    清理显示文本，移除不可见字符

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""

    # 移除控制字符（保留换行和制表符）
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 移除多余空白
    cleaned = cleaned.strip()

    return cleaned
