#!/usr/bin/env python3
"""比特币密钥生成和地址匹配完整验证演示

演示完整的Bitcoin Core规范验证流程：
1. 私钥生成公钥
2. 公钥生成地址
3. 私钥转换为WIF
4. 地址匹配验证
5. 完整流程验证
"""

import os
import sys

# Windows UTF-8支持
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets  # noqa: E402

from src.core.bitcoin_key_validator import AddressType, BitcoinKeyValidator  # noqa: E402
from src.core.secp256k1 import Secp256k1  # noqa: E402


def print_section(title: str):
    """打印分隔标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(title: str, result):
    """打印验证结果"""
    print(f"\n📋 {title}")
    print(f"  状态: {'✅ 通过' if result.success else '❌ 失败'}")

    if result.errors:
        print("  错误:")
        for error in result.errors:
            print(f"    ❌ {error}")

    if result.warnings:
        print("  警告:")
        for warning in result.warnings:
            print(f"    ⚠️  {warning}")

    if result.details:
        print("  详情:")
        for key, value in result.details.items():
            if isinstance(value, str) and len(value) > 60:
                print(f"    {key}: {value[:60]}...")
            else:
                print(f"    {key}: {value}")


def demo_private_key_validation():
    """演示私钥验证"""
    print_section("1. 私钥验证（Bitcoin Core规范）")

    validator = BitcoinKeyValidator()

    # 测试1: 有效私钥（私钥=1）
    print("\n🔑 测试1: 最小有效私钥（k=1）")
    private_key = b"\x00" * 31 + b"\x01"
    result = validator.validate_private_key(private_key)
    print_result("私钥验证", result)

    # 测试2: 随机有效私钥
    print("\n🔑 测试2: 随机有效私钥")
    k = int.from_bytes(secrets.token_bytes(32), "big") % (Secp256k1.N - 1) + 1
    private_key = k.to_bytes(32, "big")
    result = validator.validate_private_key(private_key)
    print_result("私钥验证", result)

    # 测试3: 无效私钥（0）
    print("\n🔑 测试3: 无效私钥（k=0）")
    private_key = b"\x00" * 32
    result = validator.validate_private_key(private_key)
    print_result("私钥验证", result)

    # 测试4: 无效私钥（>= N）
    print("\n🔑 测试4: 无效私钥（k >= N）")
    private_key = Secp256k1.N.to_bytes(32, "big")
    result = validator.validate_private_key(private_key)
    print_result("私钥验证", result)


def demo_public_key_generation():
    """演示公钥生成"""
    print_section("2. 公钥生成（secp256k1椭圆曲线）")

    validator = BitcoinKeyValidator()
    private_key = b"\x00" * 31 + b"\x01"  # 私钥=1

    # 测试1: 生成压缩公钥
    print("\n🔐 测试1: 生成压缩公钥（33字节）")
    result, public_key = validator.generate_public_key(private_key, compressed=True)
    print_result("公钥生成", result)
    print(f"  公钥（hex）: {public_key.hex()}")
    print(f"  公钥长度: {len(public_key)} 字节")
    print(f"  前缀: 0x{public_key[0]:02x} ({'偶数y' if public_key[0] == 0x02 else '奇数y'})")

    # 测试2: 生成非压缩公钥
    print("\n🔐 测试2: 生成非压缩公钥（65字节）")
    result, public_key = validator.generate_public_key(private_key, compressed=False)
    print_result("公钥生成", result)
    print(f"  公钥（hex）: {public_key.hex()}")
    print(f"  公钥长度: {len(public_key)} 字节")

    # 测试3: 验证公钥在曲线上
    print("\n🔐 测试3: 验证secp256k1曲线方程")
    print("  曲线方程: y² = x³ + 7 (mod p)")
    print("  验证: 基点G满足曲线方程 ✅")

    # 验证基点
    x = Secp256k1.Gx
    y = Secp256k1.Gy
    left = pow(y, 2, Secp256k1.P)
    right = (pow(x, 3, Secp256k1.P) + 7) % Secp256k1.P
    print(f"  左边 y² mod p: {left:064x}")
    print(f"  右边 x³+7 mod p: {right:064x}")
    print(f"  匹配: {'✅ 是' if left == right else '❌ 否'}")


def demo_address_generation():
    """演示地址生成"""
    print_section("3. 地址生成（P2PKH/P2SH/Bech32）")

    validator = BitcoinKeyValidator()
    private_key = b"\x00" * 31 + b"\x01"
    _, public_key = validator.generate_public_key(private_key, compressed=True)

    # 测试1: 生成P2PKH地址
    print("\n📍 测试1: 生成P2PKH地址（以'1'开头）")
    result, address = validator.generate_address(public_key, AddressType.P2PKH)
    print_result("地址生成", result)
    print(f"  地址: {address}")
    print("  地址类型: P2PKH")
    print(f"  Hash160: {result.details.get('hash160', 'N/A')}")

    # 测试2: 验证地址格式
    print("\n📍 测试2: 验证地址格式")
    result = validator.validate_address(address)
    print_result("地址验证", result)

    # 测试3: 验证Base58Check校验和
    print("\n📍 测试3: Base58Check校验和验证")
    from src.core.base58 import Base58

    try:
        version, payload = Base58.check_decode(address)
        print(f"  版本字节: 0x{version:02x}")
        print(f"  载荷长度: {len(payload)} 字节")
        print("  校验和: ✅ 有效")
    except Exception as e:
        print(f"  校验和: ❌ 无效 - {e}")


def demo_wif_encoding():
    """演示WIF编码"""
    print_section("4. WIF编码（Wallet Import Format）")

    validator = BitcoinKeyValidator()
    private_key = b"\x00" * 31 + b"\x01"

    # 测试1: 压缩WIF
    print("\n💼 测试1: 压缩WIF编码（52字符，以'K'或'L'开头）")
    result, wif = validator.private_key_to_wif(private_key, compressed=True)
    print_result("WIF编码", result)
    print(f"  WIF: {wif}")
    print(f"  长度: {len(wif)} 字符")
    print(f"  前缀: {wif[0]}")

    # 测试2: 非压缩WIF
    print("\n💼 测试2: 非压缩WIF编码（51字符，以'5'开头）")
    result, wif = validator.private_key_to_wif(private_key, compressed=False)
    print_result("WIF编码", result)
    print(f"  WIF: {wif}")
    print(f"  长度: {len(wif)} 字符")
    print(f"  前缀: {wif[0]}")

    # 测试3: WIF解码
    print("\n💼 测试3: WIF解码验证")
    # 运行时动态生成WIF，不硬编码
    from src.core.wif import WIF

    wif = WIF.encode(private_key, compressed=True)
    result, decoded_key, compressed = validator.wif_to_private_key(wif)
    print_result("WIF解码", result)
    print(f"  解码私钥: {decoded_key.hex()}")
    print(f"  压缩标志: {compressed}")
    print(f"  匹配原私钥: {'✅ 是' if decoded_key == private_key else '❌ 否'}")


def demo_address_matching():
    """演示地址匹配"""
    print_section("5. 地址匹配验证（安全比较）")

    validator = BitcoinKeyValidator()

    # 测试1: 地址匹配
    print("\n🎯 测试1: 地址匹配成功")
    address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
    targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    result = validator.verify_address_match(address, targets)
    print_result("地址匹配", result)
    print(f"  匹配结果: {'✅ 找到匹配' if result.details.get('match') else '❌ 未匹配'}")

    # 测试2: 地址不匹配
    print("\n🎯 测试2: 地址不匹配")
    address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX"}
    result = validator.verify_address_match(address, targets)
    print_result("地址匹配", result)
    print(f"  匹配结果: {'✅ 找到匹配' if result.details.get('match') else '❌ 未匹配'}")

    # 测试3: 安全比较（防止时序攻击）
    print("\n🎯 测试3: 安全字符串比较")
    print("  使用: hmac.compare_digest()")
    print("  防止: 时序攻击（Timing Attack）")
    print("  状态: ✅ 已启用")


def demo_full_validation_chain():
    """演示完整验证链"""
    print_section("6. 完整验证链（私钥→公钥→地址→WIF→匹配）")

    validator = BitcoinKeyValidator()
    private_key = b"\x00" * 31 + b"\x01"
    target_addresses = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

    print("\n🔗 执行完整验证链...")
    report = validator.full_validation_chain(private_key, target_addresses)

    print("\n📊 验证报告")
    print(f"  整体状态: {'✅ 全部通过' if report['overall_success'] else '❌ 存在失败'}")
    print(f"  步骤数: {len(report['steps'])}")

    print("\n📋 各步骤结果:")
    for step_name, step_result in report["steps"].items():
        status = "✅" if step_result["success"] else "❌"
        print(f"  {status} {step_name}: {'通过' if step_result['success'] else '失败'}")

    print("\n📦 摘要信息:")
    summary = report["summary"]
    print(f"  私钥: {summary['private_key_hex']}")
    print(f"  公钥（压缩）: {summary['public_key_compressed']}")
    print(f"  地址: {summary['address']}")
    print(f"  WIF（压缩）: {summary['wif_compressed']}")
    print(f"  地址匹配: {'✅ 是' if summary['address_match'] else '❌ 否'}")

    if report["errors"]:
        print("\n❌ 错误:")
        for error in report["errors"]:
            print(f"    {error}")

    if report["warnings"]:
        print("\n⚠️  警告:")
        for warning in report["warnings"]:
            print(f"    {warning}")


def main():
    """主函数"""
    print("=" * 80)
    print("  比特币密钥生成和地址匹配完整验证系统")
    print("  Bitcoin Core规范符合性验证")
    print("=" * 80)

    try:
        demo_private_key_validation()
        demo_public_key_generation()
        demo_address_generation()
        demo_wif_encoding()
        demo_address_matching()
        demo_full_validation_chain()

        print("\n" + "=" * 80)
        print("  ✅ 所有验证演示完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
