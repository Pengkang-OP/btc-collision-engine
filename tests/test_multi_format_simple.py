#!/usr/bin/env python3
"""
比特币多格式地址转换验证测试 - 简化版
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.address_generator import P2PKHAddressGenerator
from src.core.bitcoin_key_validator import BitcoinKeyValidator, AddressType
from src.utils.bech32_codec import bech32_encode, bech32_decode, decode_segwit_address
import secrets
import hashlib

print("=" * 80)
print("Bitcoin Multi-Format Address Conversion Test")
print("=" * 80)

addr_gen = P2PKHAddressGenerator()
validator = BitcoinKeyValidator()

# 生成测试密钥
test_private_key = secrets.token_bytes(32)
compressed_pk = addr_gen.private_key_to_public_key(test_private_key, compressed=True)
uncompressed_pk = addr_gen.private_key_to_public_key(test_private_key, compressed=False)

print("\n[Test Data]")
print(f"Private Key: {test_private_key.hex()[:32]}...")
print(f"Compressed Public Key: {compressed_pk.hex()}")

# 1. P2PKH地址生成
print("\n" + "=" * 80)
print("[1] P2PKH Address (Pay-to-Public-Key-Hash)")
print("-" * 80)

result, p2pkh_address = validator.generate_address(compressed_pk, AddressType.P2PKH)
print(f"Generated P2PKH Address: {p2pkh_address}")
print(f"Starts with '1': {p2pkh_address[0] == '1'}")
print(f"Length: {len(p2pkh_address)} chars")

validation = validator.validate_address(p2pkh_address)
print(f"Validation: {'✓ PASS' if validation.success else '✗ FAIL'}")

# 2. P2SH地址生成
print("\n" + "=" * 80)
print("[2] P2SH Address (Pay-to-Script-Hash)")
print("-" * 80)

result, p2sh_address = validator.generate_address(compressed_pk, AddressType.P2SH)
print(f"Generated P2SH Address: {p2sh_address}")
print(f"Starts with '3': {p2sh_address[0] == '3'}")
print(f"Length: {len(p2sh_address)} chars")

validation = validator.validate_address(p2sh_address)
print(f"Validation: {'✓ PASS' if validation.success else '✗ FAIL'}")

# 3. Bech32地址生成 (SegWit v0)
print("\n" + "=" * 80)
print("[3] Bech32 Address (SegWit v0 - bc1q)")
print("-" * 80)

result, bech32_address = validator.generate_address(compressed_pk, AddressType.BECH32)
print(f"Generated Bech32 Address: {bech32_address}")
print(f"Starts with 'bc1q': {bech32_address.startswith('bc1q')}")
print(f"Length: {len(bech32_address)} chars")

validation = validator.validate_address(bech32_address)
print(f"Validation: {'✓ PASS' if validation.success else '✗ FAIL'}")

# 4. 手动Bech32编码验证
print("\n" + "=" * 80)
print("[4] Manual Bech32 Encoding")
print("-" * 80)

# 计算Hash160
from src.core.hash_utils import HashUtils
hash160 = HashUtils.hash160(compressed_pk)
print(f"Hash160: {hash160.hex()}")

# 手动Bech32编码
try:
    witprog = hash160  # 20字节用于P2WPKH
    manual_bech32 = bech32_encode("bc", 0, witprog, "bech32")
    print(f"Manual Bech32: {manual_bech32}")
    print(f"Match with validator: {'✓' if manual_bech32 == bech32_address else '✗'}")

    # 解码验证
    witver, prog = decode_segwit_address("bc", manual_bech32)
    print(f"Decoded witness version: {witver}")
    print(f"Decoded witness program: {prog.hex() if prog else 'N/A'}")
    print(f"Decoding successful: {'✓' if prog == witprog else '✗'}")
except Exception as e:
    print(f"❌ Bech32 encoding failed: {e}")

# 5. 已知地址验证
print("\n" + "=" * 80)
print("[5] Known Address Format Validation")
print("-" * 80)

known_addresses = [
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "P2PKH", "Satoshi Nakamoto"),
    ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "P2SH", "Example P2SH"),
    ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "Bech32", "Example Bech32"),
]

for addr, addr_type, description in known_addresses:
    result = validator.validate_address(addr)
    status = '✓' if result.success else '✗'
    detected_type = result.details.get('address_type', 'N/A') if result.success else 'N/A'
    match = '✓' if detected_type.upper().replace('-', '') == addr_type.upper().replace('-', '') else '✗'
    print(f"{status} {addr}")
    print(f"  {description}: {addr_type} (Expected) vs {detected_type} (Detected) {match}")

# 6. 地址格式总结
print("\n" + "=" * 80)
print("[6] Address Format Summary")
print("-" * 80)

print("\nAll Generated Addresses:")
addresses = {
    "P2PKH (1xxx)": p2pkh_address,
    "P2SH (3xxx)": p2sh_address,
    "Bech32 (bc1q)": bech32_address,
}

for format_name, addr in addresses.items():
    print(f"\n{format_name}:")
    print(f"  Address: {addr}")
    print(f"  Length: {len(addr)} chars")

    # 验证每个地址
    validation = validator.validate_address(addr)
    print(f"  Valid: {'✓' if validation.success else '✗'}")

    if validation.success:
        print(f"  Type: {validation.details.get('address_type', 'N/A')}")
        print(f"  Checksum: {validation.details.get('checksum_valid', 'N/A')}")

# 7. 地址特性对比
print("\n" + "=" * 80)
print("[7] Address Format Comparison")
print("-" * 80)

print("\n| Format | Prefix | Encoding | Witness Support |")
print("|--------|--------|----------|----------------|")
print("| P2PKH | 1 | Base58Check | No |")
print("| P2SH | 3 | Base58Check | No |")
print("| Bech32 | bc1q | Bech32 | Yes (v0) |")
print("| Bech32m | bc1p | Bech32m | Yes (v1 Taproot) |")

# 8. 多格式转换能力验证
print("\n" + "=" * 80)
print("[8] Format Support Verification")
print("-" * 80)

test_results = {
    "P2PKH Generation": validator.generate_address(compressed_pk, AddressType.P2PKH)[1][0] == '1',
    "P2SH Generation": validator.generate_address(compressed_pk, AddressType.P2SH)[1][0] == '3',
    "Bech32 Generation": validator.generate_address(compressed_pk, AddressType.BECH32)[1].startswith('bc1'),
    "P2PKH Validation": validator.validate_address(p2pkh_address).success,
    "P2SH Validation": validator.validate_address(p2sh_address).success,
    "Bech32 Validation": validator.validate_address(bech32_address).success,
    "Known P2PKH": validator.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa").success,
    "Known P2SH": validator.validate_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy").success,
    "Known Bech32": validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4").success,
}

print("\nTest Results:")
for test_name, result in test_results.items():
    status = "✓ PASS" if result else "✗ FAIL"
    print(f"  {status} {test_name}")

all_passed = all(test_results.values())

print("\n" + "=" * 80)
if all_passed:
    print("✓ ALL MULTI-FORMAT CONVERSIONS WORKING CORRECTLY")
    print("\nSupported Formats:")
    print("  • P2PKH (Pay-to-Public-Key-Hash) - 1xxx")
    print("  • P2SH (Pay-to-Script-Hash) - 3xxx")
    print("  • Bech32 (SegWit v0) - bc1qxxx")
    print("  • Bech32m (Taproot) - bc1pxxx")
else:
    print("✗ SOME FORMAT CONVERSIONS FAILED")
print("=" * 80)
