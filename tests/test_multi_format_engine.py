#!/usr/bin/env python3
"""多格式比特币地址生成和匹配测试.

测试系统是否支持根据目标地址格式自动生成对应格式的地址。
"""

import secrets

from src.collision.targets.format_aware_manager import FormatAwareTargetManager
from src.core.multi_format_generator import AddressFormat, MultiFormatAddressGenerator

print("=" * 80)
print("Multi-Format Bitcoin Address Generation and Matching Test")
print("=" * 80)

# 1. 测试多格式地址生成器
print("\n[Test 1] MultiFormatAddressGenerator")
print("-" * 80)

gen = MultiFormatAddressGenerator()

# 生成测试私钥
test_key = secrets.token_bytes(32)
print(f"Test Private Key: {test_key.hex()[:32]}...")

# 生成所有格式
addresses = gen.generate_all_formats(test_key)
print("\nGenerated Addresses:")
for fmt, addr in addresses.items():
    if addr:
        print(f"  {fmt:10s}: {addr}")
    else:
        print(f"  {fmt:10s}: FAILED (not supported)")

# 验证格式
print("\nFormat Validation:")
for fmt, addr in addresses.items():
    if addr:
        detected_fmt = gen.detect_address_format(addr)
        expected_fmt = AddressFormat(fmt)
        match = detected_fmt == expected_fmt
        print(
            f"  {fmt:10s}: {'✓' if match else '✗'} (expected={expected_fmt.value}, detected={detected_fmt.value})",  # noqa: E501
        )

# 2. 测试格式检测
print("\n[Test 2] Address Format Detection")
print("-" * 80)

test_addresses = [
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", AddressFormat.P2PKH),
    ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", AddressFormat.P2SH),
    ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", AddressFormat.BECH32),
    ("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297", AddressFormat.TAPROOT),
]

print("\nKnown Address Format Detection:")
for addr, expected_fmt in test_addresses:
    try:
        detected_fmt = gen.detect_address_format(addr)
        match = detected_fmt == expected_fmt
        print(f"  {addr[:30]:30s} -> {detected_fmt.value:10s} {'✓' if match else '✗'}")
    except Exception as e:
        print(f"  {addr[:30]:30s} -> ERROR: {e}")

# 3. 测试格式感知目标管理器
print("\n[Test 3] FormatAwareTargetManager")
print("-" * 80)

manager = FormatAwareTargetManager()

# 添加多格式目标
target_addresses = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # P2PKH
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32
    "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297",  # Taproot
]

print(f"\nAdding {len(target_addresses)} targets:")
for addr in target_addresses:
    success = manager.add_target(addr)
    print(f"  {addr[:40]:40s} {'✓' if success else '✗'}")

# 统计
print("\nFormat Statistics:")
stats = manager.get_format_stats()
for fmt, count in stats.items():
    print(f"  {fmt:10s}: {count}")

print(f"\nTotal Targets: {len(manager)}")
print(f"Supported Formats: {manager.get_supported_formats()}")

# 4. 测试匹配功能
print("\n[Test 4] Multi-Format Matching")
print("-" * 80)

# 生成一个已知会匹配某目标地址的私钥
# 私钥=1 对应的P2PKH地址
private_key_1 = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000001")
p2pkh_addr = gen.generate_p2pkh_address(private_key_1)
p2sh_addr = gen.generate_p2sh_address(private_key_1)
bech32_addr = gen.generate_bech32_address(private_key_1)
taproot_addr = gen.generate_taproot_address(private_key_1)

print("\nKey=1 addresses:")
print(f"  P2PKH: {p2pkh_addr}")
print(f"  P2SH: {p2sh_addr}")
print(f"  Bech32: {bech32_addr}")
print(f"  Taproot: {taproot_addr}")

# 测试匹配
print("\nMatching Test:")
for fmt in ["p2pkh", "p2sh", "bech32", "taproot"]:
    manager_test = FormatAwareTargetManager()
    addr = locals().get(f"{fmt}_addr")
    if addr:
        manager_test.add_target(addr)
        is_match, matched_addr, matched_fmt = manager_test.check_match(private_key_1)
        print(
            f"  {fmt:10s}: {'✓ MATCHED' if is_match else '✗ NO MATCH'} - {matched_addr if is_match else ''}",  # noqa: E501
        )

# 5. 测试混合格式匹配
print("\n[Test 5] Mixed Format Matching")
print("-" * 80)

mixed_manager = FormatAwareTargetManager()

# 添加所有格式目标
for addr in target_addresses:
    mixed_manager.add_target(addr)

print(f"Total targets: {len(mixed_manager)}")
print(f"Format distribution: {mixed_manager.get_format_stats()}")

# 测试已知私钥
is_match, matched_addr, matched_fmt = mixed_manager.check_match(private_key_1)
print("\nKey=1 matching result:")
print(f"  Matched: {'✓ YES' if is_match else '✗ NO'}")
if is_match:
    print(f"  Address: {matched_addr}")
    print(f"  Format: {matched_fmt}")

# 6. 性能测试
print("\n[Test 6] Performance Test")
print("-" * 80)

import time  # noqa: E402

# 生成1000个地址
iterations = 1000
start = time.time()
for _ in range(iterations):
    key = secrets.token_bytes(32)
    addrs = gen.generate_all_formats(key)
elapsed = time.time() - start

print(f"Generated {iterations} multi-format address sets")
print(f"Time: {elapsed:.3f}s")
print(f"Rate: {iterations / elapsed:.1f} sets/s")

# 7. 格式支持状态
print("\n[Test 7] Format Support Status")
print("-" * 80)

support = gen.validate_format_support()
print("Format generation support:")
for fmt, supported in support.items():
    status = "✓" if supported else "✗"
    print(f"  {fmt:10s}: {status}")

print("\n" + "=" * 80)
print("Test Summary")
print("=" * 80)

test_results = {
    "Multi-format generation": all(addresses.values()),
    "Format detection": all(detected_fmt == expected_fmt for addr, expected_fmt in test_addresses),
    "Target management": len(manager) == len(target_addresses),
    "Multi-format matching": is_match,
    "Performance acceptable": elapsed < 5.0,
    "All formats supported": all(support.values()),
}

all_passed = all(test_results.values())

for test_name, result in test_results.items():
    status = "✓ PASS" if result else "✗ FAIL"
    print(f"  {status} {test_name}")

print("\n" + "=" * 80)
if all_passed:
    print("✓ ALL MULTI-FORMAT FEATURES WORKING CORRECTLY")
    print("\nNew Capabilities:")
    print("  • Generate addresses in all formats (P2PKH/P2SH/Bech32/Taproot)")
    print("  • Auto-detect address format")
    print("  • Match against multi-format targets")
    print("  • Format-aware target management")
else:
    print("✗ SOME FEATURES NOT WORKING")
print("=" * 80)
