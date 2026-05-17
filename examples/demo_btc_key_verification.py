# -*- coding: utf-8 -*-
"""
比特币密钥派生及地址生成验证示例
===================================

本文件展示如何使用 BTCKeyAddressVerifier 工具进行比特币密钥派生
及地址生成的验证。

使用方法:
    python examples/demo_btc_key_verification.py
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.btc_key_address_verifier import BTCKeyAddressVerifier, AddressFormat


def example_basic_verification():
    """基本验证示例"""
    print("=" * 70)
    print("示例1: 基本验证 - 使用已知私钥")
    print("=" * 70)

    verifier = BTCKeyAddressVerifier(verbose=True)

    # 已知私钥 (Bitcoin wiki 标准测试向量)
    private_key = "0000000000000000000000000000000000000000000000000000000000000001"

    # 已知目标地址
    targets = {
        "p2pkh": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "p2sh": "3LRW7jeCvQCRdPF8S3yUCfRAx4eqXFmdcr",
        "bech32": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    }

    report = verifier.verify_private_key(private_key, targets)

    print("\n验证摘要:")
    print("-" * 40)
    print(f"压缩公钥: {report.public_key_compressed}")
    print(f"公钥X坐标: {report.public_key_x}")
    print(f"公钥Y坐标: {report.public_key_y}")
    print(f"在曲线上: {'是' if report.is_public_key_on_curve else '否'}")

    for fmt in AddressFormat:
        result = report.address_results.get(fmt)
        if result:
            status = "[OK]" if result.is_match else "[FAIL]"
            print(f"{fmt.value:8s}: {result.generated_address} {status}")


def example_address_mismatch():
    """地址不匹配示例"""
    print("\n" + "=" * 70)
    print("示例2: 地址不匹配检测")
    print("=" * 70)

    verifier = BTCKeyAddressVerifier(verbose=True)

    private_key = "0000000000000000000000000000000000000000000000000000000000000001"

    # 故意提供错误的地址
    wrong_targets = {
        "p2pkh": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMX",  # 最后一个字符错误
    }

    report = verifier.verify_private_key(private_key, wrong_targets)

    p2pkh_result = report.address_results[AddressFormat.P2PKH]
    print("\n不匹配详情:")
    print(f"  生成地址: {p2pkh_result.generated_address}")
    print(f"  目标地址: {p2pkh_result.target_address}")
    print(f"  匹配状态: {p2pkh_result.match_status}")
    print(f"  不一致环节: {p2pkh_result.mismatch_step or 'N/A'}")


def example_random_key_verification():
    """随机私钥验证示例"""
    print("\n" + "=" * 70)
    print("示例3: 随机私钥验证")
    print("=" * 70)

    verifier = BTCKeyAddressVerifier(verbose=False)
    report = verifier.generate_random_verification()

    print(f"压缩公钥: {report.public_key_compressed}")
    print(f"P2PKH地址: {report.address_results[AddressFormat.P2PKH].generated_address}")
    print(f"P2SH地址: {report.address_results[AddressFormat.P2SH].generated_address}")
    print(f"Bech32地址: {report.address_results[AddressFormat.BECH32].generated_address}")
    print(f"Bech32m地址: {report.address_results[AddressFormat.BECH32M].generated_address}")


def example_batch_verification():
    """批量验证示例"""
    print("\n" + "=" * 70)
    print("示例4: 批量验证多个地址")
    print("=" * 70)

    verifier = BTCKeyAddressVerifier(verbose=False)

    # 测试用例数据
    test_cases = [
        {
            "private_key": "0000000000000000000000000000000000000000000000000000000000000001",
            "targets": {
                "p2pkh": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
                "p2sh": "3LRW7jeCvQCRdPF8S3yUCfRAx4eqXFmdcr",
                "bech32": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
            }
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试用例 #{i}:")
        results = verifier.batch_verify_addresses(
            case["private_key"],
            case["targets"]
        )

        print(f"  私钥哈希: {results['private_key_hash']}")
        for fmt, result in results["verification_results"].items():
            if result["match"] is True:
                match_status = "[OK]"
            elif result["match"] is False:
                match_status = "[FAIL]"
            else:
                match_status = "(no target)"
            print(f"  {fmt:8s}: {result['generated']} {match_status}")


def example_json_output():
    """JSON输出示例"""
    print("\n" + "=" * 70)
    print("示例5: JSON格式输出")
    print("=" * 70)

    import json

    verifier = BTCKeyAddressVerifier(verbose=False)
    report = verifier.generate_random_verification()

    # 转换为字典格式
    report_dict = report.to_dict()

    print("\nJSON输出摘要:")
    print("-" * 40)
    print(f"私钥 (哈希): {report_dict['private_key']['hex'][:16]}...")
    print(f"压缩公钥: {report_dict['public_key']['compressed'][:40]}...")
    print(f"公钥坐标: ({report_dict['public_key']['x'][:16]}..., {report_dict['public_key']['y'][:16]}...)")
    print(f"在曲线上: {report_dict['public_key']['on_curve']}")

    print("\n生成地址:")
    for fmt, addr_data in report_dict["addresses"].items():
        print(f"  {fmt}: {addr_data['generated']}")
        if addr_data.get("target"):
            print(f"    目标: {addr_data['target']}")
            print(f"    匹配: {addr_data['match']}")


def example_taproot_verification():
    """Taproot地址验证示例"""
    print("\n" + "=" * 70)
    print("示例6: Taproot (Bech32m) 地址验证")
    print("=" * 70)

    verifier = BTCKeyAddressVerifier(verbose=True)

    private_key = "0000000000000000000000000000000000000000000000000000000000000001"
    report = verifier.verify_private_key(private_key)

    taproot_result = report.address_results[AddressFormat.BECH32M]
    print(f"\nTaproot地址: {taproot_result.generated_address}")
    print(f"地址格式有效: {taproot_result.is_valid_format}")
    print(f"起始字符验证: {'bc1p' if taproot_result.generated_address.startswith('bc1p') else 'INVALID'}")

    # 显示转换步骤
    print("\n转换步骤:")
    for step in taproot_result.steps:
        print(f"  {step.name}:")
        print(f"    输入: {step.input_data[:60]}..." if len(step.input_data) > 60 else f"    输入: {step.input_data}")
        print(f"    输出: {step.output_data[:60]}..." if len(step.output_data) > 60 else f"    输出: {step.output_data}")


def main():
    """运行所有示例"""
    print("\n" + "#" * 70)
    print("# 比特币密钥派生及地址生成验证 - 示例")
    print("#" * 70)

    try:
        example_basic_verification()
        example_address_mismatch()
        example_random_key_verification()
        example_batch_verification()
        example_json_output()
        example_taproot_verification()

        print("\n" + "#" * 70)
        print("# 所有示例运行完成!")
        print("#" * 70)

    except (ValueError, TypeError, RuntimeError, ImportError) as e:
        # 演示脚本顶层兜底: 捕获常见异常类型, 打印完整堆栈便于诊断
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
