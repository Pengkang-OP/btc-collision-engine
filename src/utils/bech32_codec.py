# -*- coding: utf-8 -*-
"""Bech32 / Bech32m 统一编解码模块

基于 BIP-173 (Bech32) 和 BIP-350 (Bech32m) 规范实现。
提供编解码、校验和验证、SegWit 地址解析等全部功能。

本模块是项目中所有 Bech32 相关功能的权威实现，
替换了原有的 3 套独立实现:
- src/collision/targets/resolver.py (模块级函数)
- src/core/bitcoin_key_validator.py (静态方法)
- tools/btc_key_address_verifier.py (Bech32Codec 类)

参考规范:
- BIP-173: Bech32 地址格式
- BIP-350: Bech32m 地址格式 (Taproot)
- BIP-341: Taproot (P2TR)

优化特性:
- 内置 max_acc 溢出保护 (convertbits)
- 长度限制 90 字符 (BIP-173 要求)
- witness version 与编码一致性检查
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# ============================================================================
# 常量定义
# ============================================================================

BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CHARSET_MAP = {c: i for i, c in enumerate(BECH32_CHARSET)}

BECH32_CONST = 1           # bech32  校验常量 (BIP-173)
BECH32M_CONST = 0x2BC830A3  # bech32m 校验常量 (BIP-350)

# polymod 生成元 (BIP-173 规范)
_POLYMOD_GENERATOR = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]

# BIP-173 编码长度限制
MAX_BECH32_LENGTH = 90

# Witness program 长度约束 (BIP-141/BIP-341)
WP_MIN_LENGTH = 2
WP_MAX_LENGTH = 40


# ============================================================================
# 核心算法
# ============================================================================

def bech32_polymod(values: List[int]) -> int:
    """Bech32/Bech32m 多项式校验模运算

    Args:
        values: 5-bit 整数列表 (包含展开的 HRP + data + 校验位)

    Returns:
        32-bit 多项式的值
    """
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= _POLYMOD_GENERATOR[i] if ((top >> i) & 1) else 0
    return chk


def bech32_hrp_expand(hrp: str) -> List[int]:
    """扩展 HRP 为校验运算所需格式

    Args:
        hrp: 人类可读部分 (如 'bc', 'tb')

    Returns:
        扩展后的整数列表
    """
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def convertbits(
    data: bytes | List[int],
    from_bits: int,
    to_bits: int,
    pad: bool = True
) -> Optional[List[int]]:
    """5-bit <-> 8-bit 位转换 (BIP-173 convertbits)

    含 max_acc 溢出保护，防止长时间序列导致的累加器无界增长。

    Args:
        data: 输入数据 (8-bit bytes 或 5-bit int list)
        from_bits: 源位数
        to_bits: 目标位数
        pad: 是否填充末尾不足的位

    Returns:
        转换后的整数列表，失败返回 None
    """
    acc = 0
    bits = 0
    result: List[int] = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1

    for value in data:
        if value < 0 or (value >> from_bits):
            return None
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((acc >> bits) & maxv)

    if pad:
        if bits:
            result.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None

    return result


# ============================================================================
# 校验和
# ============================================================================

def bech32_verify_checksum(hrp: str, data: List[int]) -> Optional[int]:
    """验证 Bech32/Bech32m 校验和

    Args:
        hrp: 人类可读部分
        data: 完整 5-bit 数据 (包含校验和尾部)

    Returns:
        BECH32_CONST (1) 表示有效 bech32,
        BECH32M_CONST (0x2bc830a3) 表示有效 bech32m,
        None 表示校验和不匹配
    """
    const = bech32_polymod(bech32_hrp_expand(hrp) + data)
    if const == BECH32_CONST:
        return BECH32_CONST
    if const == BECH32M_CONST:
        return BECH32M_CONST
    return None


def bech32_create_checksum(hrp: str, data: List[int], spec: str = "bech32") -> List[int]:
    """创建 Bech32/Bech32m 校验和

    Args:
        hrp: 人类可读部分
        data: 5-bit 数据 (不含校验位)
        spec: "bech32" 或 "bech32m"

    Returns:
        6 个 5-bit 校验和值
    """
    values = bech32_hrp_expand(hrp) + data + [0, 0, 0, 0, 0, 0]

    # BIP-173: bech32 校验和常数 = 1
    # BIP-350: bech32m 校验和常数 = 0x2BC830A3
    if spec == "bech32m":
        polymod = bech32_polymod(values) ^ BECH32M_CONST
    else:
        polymod = bech32_polymod(values) ^ 1

    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


# ============================================================================
# 编解码
# ============================================================================

def bech32_encode(
    hrp: str,
    witver: int,
    witprog: bytes,
    spec: str = "bech32"
) -> str:
    """编码 Bech32/Bech32m 地址

    Args:
        hrp: 人类可读部分 ('bc'=主网, 'tb'=测试网)
        witver: Witness version (0-16)
        witprog: Witness program bytes (2-40 bytes)
        spec: "bech32" 或 "bech32m"

    Returns:
        编码后的地址字符串 (小写)

    Raises:
        ValueError: 参数不符合规范时
    """
    if witver < 0 or witver > 16:
        raise ValueError("Witness version must be 0-16")
    if len(witprog) < WP_MIN_LENGTH or len(witprog) > WP_MAX_LENGTH:
        raise ValueError(f"Witness program must be {WP_MIN_LENGTH}-{WP_MAX_LENGTH} bytes")
    if witver == 0 and len(witprog) not in (20, 32):
        raise ValueError("Witness version 0 requires 20 or 32 byte witness program")

    data = convertbits(witprog, 8, 5)
    if data is None:
        raise ValueError("Failed to convert witness program to 5-bit")

    combined = [witver] + data
    checksum = bech32_create_checksum(hrp, combined, spec)

    return hrp.lower() + "1" + "".join(BECH32_CHARSET[d] for d in combined + checksum)


def bech32_decode(bech: str) -> Tuple[Optional[str], Optional[List[int]], Optional[int]]:
    """解码 Bech32/Bech32m 字符串

    Args:
        bech: 要解码的字符串

    Returns:
        (hrp, data_5bit, encoding_const) 三元组，失败时返回 (None, None, None)
        encoding_const: 1=bech32, 0x2bc830a3=bech32m
    """
    # BIP-173: 禁止大小写混合
    if bech.lower() != bech and bech.upper() != bech:
        return None, None, None
    bech = bech.lower()

    # 最大长度限制
    if len(bech) > MAX_BECH32_LENGTH:
        return None, None, None

    # 找分隔符 '1'
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech):
        return None, None, None

    hrp = bech[:pos]
    data_part = bech[pos + 1:]

    # 验证字符集
    if not all(c in _BECH32_CHARSET_MAP for c in data_part):
        return None, None, None

    decoded = [_BECH32_CHARSET_MAP[c] for c in data_part]
    enc = bech32_verify_checksum(hrp, decoded)
    if enc is None:
        return None, None, None

    return hrp, decoded[:-6], enc


# ============================================================================
# SegWit 地址解析
# ============================================================================

def decode_segwit_address(hrp: str, addr: str) -> Tuple[Optional[int], Optional[bytes]]:
    """解码 SegWit 地址，提取 witness version 和 witness program

    支持:
    - P2WPKH: witness version=0, 20字节 witness program (bc1q)
    - P2WSH:  witness version=0, 32字节 witness program (bc1q)
    - P2TR:   witness version=1, 32字节 witness program (bc1p, Taproot)

    Args:
        hrp: 人类可读部分 ('bc'=主网, 'tb'=测试网)
        addr: 完整 bech32/bech32m 地址字符串

    Returns:
        (witness_version, witness_program_bytes), 失败返回 (None, None)
    """
    hrp_got, data, enc = bech32_decode(addr)
    if hrp_got is None or hrp_got != hrp.lower():
        return None, None
    if not data or len(data) < 1:
        return None, None

    witness_version = data[0]
    if witness_version > 16:
        return None, None

    # witness_version=0 必须使用 bech32，version>=1 必须使用 bech32m
    if witness_version == 0 and enc != BECH32_CONST:
        return None, None
    if witness_version != 0 and enc != BECH32M_CONST:
        return None, None

    witness_program = convertbits(data[1:], 5, 8, False)
    if witness_program is None:
        return None, None

    prog_len = len(witness_program)
    # P2WPKH=20, P2WSH=32, P2TR=32
    if witness_version == 0 and prog_len not in (20, 32):
        return None, None
    if witness_version == 1 and prog_len != 32:
        return None, None
    if prog_len < WP_MIN_LENGTH or prog_len > WP_MAX_LENGTH:
        return None, None

    return witness_version, bytes(witness_program)
