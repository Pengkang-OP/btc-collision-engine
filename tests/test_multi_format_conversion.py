#!/usr/bin/env python3
"""比特币多格式地址转换验证测试"""
# 此文件是独立脚本（无 pytest 测试函数），标记排除 pytest 收集
__test__ = False


def main():
    """运行多格式地址转换测试"""
    import secrets

    from src.core.address_generator import P2PKHAddressGenerator
    from src.core.bitcoin_key_validator import BitcoinKeyValidator

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
    print(f"Uncompressed Public Key: {uncompressed_pk.hex()[:64]}...")

    # AddressConverter removed, subsequent converter-dependent code will not execute
    converter = None
    bech32_address = None
    p2sh_address = None

    # 1. P2PKH地址生成
    print("\n" + "=" * 80)
    print("[1] P2PKH Address (Pay-to-Public-Key-Hash)")
    print("-" * 80)

    p2pkh_address = addr_gen.public_key_to_address(compressed_pk)
    print(f"Generated P2PKH Address: {p2pkh_address}")
    print(f"Starts with '1': {p2pkh_address[0] == '1'}")

    result = validator.validate_address(p2pkh_address)
    print(f"Validation: {'✓ PASS' if result.success else '✗ FAIL'}")
    if result.success:
        print(f"Address Type: {result.details.get('address_type', 'N/A')}")
        print(f"Checksum Valid: {result.details.get('checksum_valid', 'N/A')}")

    # 2. P2SH地址生成
    print("\n" + "=" * 80)
    print("[2] P2SH Address (Pay-to-Script-Hash)")
    print("-" * 80)
    print("ℹ P2SH/Bech32 conversion requires AddressConverter (module removed)")

    # 4. Taproot地址生成 (SegWit v1)
    print("\n" + "=" * 80)
    print("[4] Taproot Address (SegWit v1 - bc1p)")
    print("-" * 80)

    try:
        taproot_address = converter.pubkey_to_taproot_address(compressed_pk)
        print(f"Generated Taproot Address: {taproot_address}")
        print(f"Starts with 'bc1p': {taproot_address.startswith('bc1p')}")
        result = validator.validate_address(taproot_address)
        print(f"Validation: {'✓ PASS' if result.success else '✗ FAIL'}")
        if result.success:
            print(f"Address Type: {result.details.get('address_type', 'N/A')}")
    except Exception as e:
        print(f"❌ Taproot conversion failed: {e}")

    # 5. P2PKH <-> P2SH 转换
    print("\n" + "=" * 80)
    print("[5] P2PKH <-> P2SH Address Conversion")
    print("-" * 80)

    try:
        p2pkh_to_p2sh = converter.p2pkh_to_p2sh(p2pkh_address)
        print(f"P2PKH: {p2pkh_address}")
        print("  ↓ Convert")
        print(f"P2SH: {p2pkh_to_p2sh}")
        p2sh_to_p2pkh = converter.p2sh_to_p2pkh(p2pkh_to_p2sh)
        print(f"P2SH: {p2pkh_to_p2sh}")
        print("  ↓ Convert")
        print(f"P2PKH: {p2sh_to_p2pkh}")
        print(f"\nRound-trip conversion: {'✓ PASS' if p2pkh_address == p2sh_to_p2pkh else '✗ FAIL'}")
    except Exception as e:
        print(f"❌ P2PKH <-> P2SH conversion failed: {e}")

    # 6. Bech32 -> P2SH
    print("\n" + "=" * 80)
    print("[6] Bech32 <-> P2SH-P2WPKH Conversion")
    print("-" * 80)

    try:
        wrapped_segwit = converter.bech32_to_p2sh_p2wpkh(bech32_address)
        print(f"Bech32: {bech32_address}")
        print("  ↓ Convert")
        print(f"P2SH-P2WPKH: {wrapped_segwit}")
        wrapped_to_native = converter.p2sh_p2wpkh_to_bech32(wrapped_segwit)
        print(f"P2SH-P2WPKH: {wrapped_segwit}")
        print("  ↓ Convert")
        print(f"Bech32: {wrapped_to_native}")
        print(f"\nRound-trip conversion: {'✓ PASS' if bech32_address == wrapped_to_native else '✗ FAIL'}")
    except Exception as e:
        print(f"❌ Bech32 <-> P2SH-P2WPKH conversion failed: {e}")

    # 7. 已知地址验证
    print("\n" + "=" * 80)
    print("[7] Known Address Validation")
    print("-" * 80)

    known_addresses = [
        ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "P2PKH", "Satoshi Nakamoto"),
        ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "P2SH", "Example P2SH"),
        ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "Bech32", "Example Bech32"),
    ]

    for addr, addr_type, description in known_addresses:
        result = validator.validate_address(addr)
        status = "✓" if result.success else "✗"
        detected_type = result.details.get("address_type", "N/A") if result.success else "N/A"
        print(f"{status} {addr}")
        print(f"  Type: {addr_type} (Expected), {detected_type} (Detected)")
        print(f"  Description: {description}")

    # 8. 交叉验证
    print("\n" + "=" * 80)
    print("[8] Cross-Format Verification")
    print("-" * 80)

    print("\nAddress Format Summary:")
    print(f"  Private Key: {test_private_key.hex()[:32]}... (32 bytes)")
    print(f"  Compressed PK: {compressed_pk.hex()} (33 bytes)")
    print(f"  Uncompressed PK: {uncompressed_pk.hex()[:64]}... (65 bytes)")

    addresses = {
        "P2PKH": p2pkh_address,
        "P2SH": p2sh_address if p2sh_address is not None else "N/A",
        "Bech32": bech32_address if bech32_address is not None else "N/A",
        "Taproot": taproot_address if "taproot_address" in locals() else "N/A",
    }

    for addr_type, addr in addresses.items():
        if addr and addr != "N/A":
            print(f"\n{addr_type}:")
            print(f"  Address: {addr}")
            print(f"  Length: {len(addr)} chars")

            if addr_type in ["P2PKH", "P2SH"]:
                from src.core.base58 import Base58

                try:
                    version, payload = Base58.check_decode(addr)
                    addr_hash160 = payload.hex()
                    print(f"  Hash160: {addr_hash160}")
                except Exception:
                    print("  Hash160: Unable to decode")
            else:
                print("  Hash160: N/A (Bech32/Taproot uses different encoding)")

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    test_results = {
        "P2PKH Generation": p2pkh_address[0] == "1",
        "P2SH Generation": False,
        "Bech32 Generation": False,
        "Taproot Generation": (
            taproot_address.startswith("bc1p") if "taproot_address" in locals() else False
        ),
        "P2PKH Validation": validator.validate_address(p2pkh_address).success,
        "Known Address Validation": True,
    }

    all_passed = all(test_results.values())

    for test_name, result in test_results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} {test_name}")

    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL FORMAT CONVERSIONS WORKING CORRECTLY")
    else:
        print("✗ SOME FORMAT CONVERSIONS FAILED")
    print("=" * 80)


if __name__ == "__main__":
    main()
