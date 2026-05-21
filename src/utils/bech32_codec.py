"""Bech32/Bech32m 地址编解码器

纯 Python 实现，无外部依赖。
支持:
- bech32:  SegWit v0 地址 (BIP-0173)
- bech32m: SegWit v1+ 地址 (BIP-0350, Taproot 等)
"""

__all__ = [
    "bech32_encode",
    "bech32_decode",
    "decode_segwit_address",
    "convertbits",
    "BECH32_CONST",
    "BECH32M_CONST",
]

# Bech32 字符集 (5-bit 编码)
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

# Bech32 校验常量 (BIP-0173)
BECH32_CONST = 1

# Bech32m 校验常量 (BIP-0350)
BECH32M_CONST = 0x2BC830A3

# 内部别名
_BECH32M_CONST = BECH32M_CONST


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
    acc = 0
    bits = 0
    result: list[int] = []
    maxv = (1 << to_bits) - 1
    for value in data:
        if value < 0 or (value >> from_bits):
            return None
        acc = (acc << from_bits) | value
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((acc >> bits) & maxv)
    if pad:
        if bits > 0:
            result.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None
    return result


# 公开别名（保持与旧 bech32 库 API 兼容）
convertbits = _convert_bits


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


def bech32_decode(addr: str) -> tuple[str | None, list[int], str | None]:
    """解码 Bech32/Bech32m 地址，返回 (hrp, data, encoding)。

    与 bech32 库兼容的接口，用于链式调用验证代码。

    参数:
        addr: Bech32/Bech32m 地址字符串

    返回:
        (hrp, data, encoding) 元组。
        - hrp: Human-Readable Part，失败为 None
        - data: 5-bit 数据列表（含 witness_version，不含校验和）
        - encoding: 'bech32' / 'bech32m'，失败为 None
    """
    if not addr:
        return None, [], None

    addr = addr.lower()
    pos = addr.rfind("1")
    if pos == -1:
        return None, [], None

    hrp = addr[:pos]
    data_part = addr[pos + 1:]
    if len(data_part) < 6:
        return None, [], None

    data: list[int] = []
    for ch in data_part:
        idx = _CHARSET.find(ch)
        if idx == -1:
            return None, [], None
        data.append(idx)

    encoding = _verify_checksum(hrp, data)
    if encoding is None:
        return None, [], None

    # 去除校验和 (最后 6 个字节)
    return hrp, data[:-6], encoding


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
