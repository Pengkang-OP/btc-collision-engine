<<<<<<< Updated upstream
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

# ============================================================================
# 常量定义
# ============================================================================

BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CHARSET_MAP = {c: i for i, c in enumerate(BECH32_CHARSET)}

BECH32_CONST = 1  # bech32 校验常量 (BIP-173)
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


def bech32_polymod(values: list[int]) -> int:
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


def bech32_hrp_expand(hrp: str) -> list[int]:
    """扩展 HRP 为校验运算所需格式

    Args:
        hrp: 人类可读部分 (如 'bc', 'tb')

    Returns:
        扩展后的整数列表
    """
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def convertbits(
    data: bytes | list[int], from_bits: int, to_bits: int, pad: bool = True
) -> list[int] | None:
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
=======
"""Bech32/Bech32m 地址编解码器

纯 Python 实现，无外部依赖。
支持:
- bech32:  SegWit v0 地址 (BIP-0173)
- bech32m: SegWit v1+ 地址 (BIP-0350, Taproot 等)
"""

__all__ = ["bech32_encode", "decode_segwit_address"]

# Bech32 字符集 (5-bit 编码)
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

# Bech32m 校验常量 (BIP-0350)
_BECH32M_CONST = 0x2BC830A3


def _polymod(values: list[int]) -> int:
    """Bech32/Bech32m 多项式校验和计算"""
    generator = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= generator[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    """展开 HRP (Human-Readable Part) 用于校验和计算"""
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _create_checksum(hrp: str, data: list[int], encoding: str) -> list[int]:
    """创建校验和"""
    values = _hrp_expand(hrp) + data
    const = _BECH32M_CONST if encoding == "bech32m" else 1
    polymod = _polymod(values + [0, 0, 0, 0, 0, 0]) ^ const
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convert_bits(data: bytes, from_bits: int, to_bits: int, pad: bool = True) -> list[int] | None:
    """位宽转换 (如 8-bit → 5-bit)"""
>>>>>>> Stashed changes
    acc = 0
    bits = 0
    result: list[int] = []
    maxv = (1 << to_bits) - 1
<<<<<<< Updated upstream
    max_acc = (1 << (from_bits + to_bits - 1)) - 1

    for value in data:
        if value < 0 or (value >> from_bits):
            return None
        acc = ((acc << from_bits) | value) & max_acc
=======
    for value in data:
        if value < 0 or (value >> from_bits):
            return None
        acc = (acc << from_bits) | value
>>>>>>> Stashed changes
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((acc >> bits) & maxv)
<<<<<<< Updated upstream

    if pad:
        if bits:
            result.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None

    return result


# ============================================================================
# 校验和
# ============================================================================


def bech32_verify_checksum(hrp: str, data: list[int]) -> int | None:
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


def bech32_create_checksum(hrp: str, data: list[int], spec: str = "bech32") -> list[int]:
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
    polymod = bech32_polymod(values) ^ BECH32M_CONST if spec == "bech32m" else bech32_polymod(values) ^ 1

    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


# ============================================================================
# 编解码
# ============================================================================


def bech32_encode(hrp: str, witver: int, witprog: bytes, spec: str = "bech32") -> str:
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


def bech32_decode(bech: str) -> tuple[str | None, list[int] | None, int | None]:
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
    data_part = bech[pos + 1 :]

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


def decode_segwit_address(hrp: str, addr: str) -> tuple[int | None, bytes | None]:
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
=======
    if pad:
        if bits > 0:
            result.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None
    return result


def _verify_checksum(hrp: str, data: list[int]) -> str | None:
    """验证校验和并返回编码类型 ('bech32' / 'bech32m')"""
    const = _polymod(_hrp_expand(hrp) + data)
    if const == 1:
        return "bech32"
    if const == _BECH32M_CONST:
        return "bech32m"
    return None


def bech32_encode(hrp: str, witness_version: int, witness_program: bytes, encoding: str = "bech32") -> str:
    """将 witness program 编码为 Bech32/Bech32m 地址。

    参数:
        hrp: Human-Readable Part, 如 "bc" (主网), "tb" (测试网)
        witness_version: 见证版本号 (0=SegWit v0, 1=Taproot 等)
        witness_program: 见证程序字节
        encoding: "bech32" 或 "bech32m"

    返回:
        Bech32/Bech32m 格式地址字符串, 如 "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    """
    # v4.2.2 R7: 输入校验
    if not isinstance(witness_version, int) or not (0 <= witness_version <= 16):
        raise ValueError(f"witness_version 必须在 0..16 之间, 实际: {witness_version}")
    if encoding not in ("bech32", "bech32m"):
        raise ValueError(f"encoding 必须是 'bech32' 或 'bech32m', 实际: {encoding!r}")
    if not hrp or not all("a" <= c <= "z" for c in hrp):
        raise ValueError(f"hrp 必须是非空小写字母, 实际: {hrp!r}")
    if not witness_program:
        raise ValueError("witness_program 不能为空")

    # 将 8-bit witness_program 转换为 5-bit
    converted = _convert_bits(witness_program, 8, 5)
    if converted is None:
        raise ValueError("witness_program 转换失败")

    # 数据: [witness_version] + 5-bit program
    data = [witness_version] + converted

    # 计算校验和
    checksum = _create_checksum(hrp, data, encoding)

    # 编码为字符串
    combined = data + checksum
    return hrp + "1" + "".join(_CHARSET[d] for d in combined)


def decode_segwit_address(hrp: str, addr: str) -> tuple[int | None, bytes | None]:
    """解码 SegWit Bech32/Bech32m 地址。

    参数:
        hrp: 预期的 Human-Readable Part
        addr: 完整的 Bech32/Bech32m 地址字符串

    返回:
        (witness_version, witness_program) 元组。
        解码失败返回 (None, None)。
    """
    if not addr:
        return None, None

    # 检查大小写混合 (Bech32 规范: 必须全大写或全小写)
    if addr != addr.lower() and addr != addr.upper():
        return None, None

    addr = addr.lower()

    # 分割 HRP 和数据部分
    pos = addr.rfind("1")
    if pos == -1:
        return None, None

    if addr[:pos] != hrp:
        return None, None

    data_part = addr[pos + 1:]
    if len(data_part) < 6:
        return None, None

    # 解码字符
    data: list[int] = []
    for ch in data_part:
        idx = _CHARSET.find(ch)
        if idx == -1:
            return None, None
        data.append(idx)

    # 验证校验和
    encoding = _verify_checksum(hrp, data)
    if encoding is None:
        return None, None

    # 去除校验和 (最后 6 个字节)
    data = data[:-6]

    # 提取 witness_version (第一个 5-bit 值)
    if not data:
        return None, None
    witness_version = data[0]

    # 将 5-bit 数据转回 8-bit (去除 witness_version)
    witness_program_bytes = _convert_bits(bytes(data[1:]), 5, 8, pad=False)
    if witness_program_bytes is None:
        return None, None

    return witness_version, bytes(witness_program_bytes)
>>>>>>> Stashed changes
