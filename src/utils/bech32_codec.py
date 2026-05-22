"""Bech32 and Bech32m codec for Bitcoin addresses.

Implements the Bech32 and Bech32m encoding schemes as defined in
BIP-0173 and BIP-0350.
"""

import logging

logger = logging.getLogger(__name__)

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def bech32_polymod(values: list[int]) -> int:
    """Compute Bech32 checksum."""
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA,
           0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if (b >> i) & 1 else 0
    return chk


def bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def bech32_verify_checksum(hrp: str, data: list[int], spec: str) -> bool:
    const = 1 if spec == "bech32" else 0x2BC830A3
    return bech32_polymod(bech32_hrp_expand(hrp) + data) == const


def bech32_create_checksum(hrp: str, data: list[int], spec: str) -> list[int]:
    const = 1 if spec == "bech32" else 0x2BC830A3
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ const
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(data: list[int], frombits: int, tobits: int) -> list[int] | None:
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for v in data:
        if v < 0 or (v >> frombits):
            return None
        acc = (acc << frombits) | v
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def bech32_encode(hrp: str, witver: int, witprog: bytes, spec: str = "bech32") -> str:
    data = [witver] + _convertbits(list(witprog), 8, 5)
    if data is None:
        raise ValueError("Witness program conversion failed")
    checksum = bech32_create_checksum(hrp, data, spec)
    combined = data + checksum
    return hrp + "1" + "".join(CHARSET[d] for d in combined)


def decode_segwit_address(address: str) -> tuple[str | None, int, bytes]:
    """Decode a segwit address to HRP, witness version, and program."""
    hrp, data, spec = bech32_decode(address)
    if hrp is None or not data:
        return None, 0, b""
    witver = data[0]
    prog_bytes = _convertbits(data[1:], 5, 8)
    if prog_bytes is None:
        return None, 0, b""
    return hrp, witver, bytes(prog_bytes)


def bech32_decode(address: str) -> tuple[str | None, list[int], str]:
    """Decode a Bech32 or Bech32m address."""
    pos = address.rfind("1")
    if pos < 1 or pos + 7 > len(address) or len(address) > 90:
        return None, [], ""
    hrp = address[:pos].lower()
    data_str = address[pos + 1:]
    data = [CHARSET.find(c.lower()) for c in data_str]
    if any(d < 0 for d in data):
        return None, [], ""
    spec = "bech32"
    if bech32_verify_checksum(hrp, data, "bech32m"):
        spec = "bech32m"
    elif not bech32_verify_checksum(hrp, data, "bech32"):
        return None, [], ""
    return hrp, data[1:], spec
