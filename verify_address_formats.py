#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地址格式解析功能验证脚本

测试所有支持的比特币地址格式的自动识别和转换功能。
包括：P2PKH、P2SH、Bech32、WIF、公钥、Hash160等。
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.collision.targets.resolver import TargetResolver
from src.utils import init_logging, get_configured_logger

# 初始化日志
init_logging()
logger = get_configured_logger("AddressFormatTest")


class TestColors:
    """终端颜色代码"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    # ASCII符号替代Unicode（Windows兼容）
    CHECK = '[OK]'
    CROSS = '[FAIL]'


def print_header(text):
    """打印测试标题"""
    print(f"\n{TestColors.CYAN}{'='*70}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.CYAN}{text}{TestColors.RESET}")
    print(f"{TestColors.CYAN}{'='*70}{TestColors.RESET}\n")


def print_result(test_name, success, details=""):
    """打印测试结果"""
    status = f"{TestColors.GREEN}{TestColors.CHECK}{TestColors.RESET}" if success else f"{TestColors.RED}{TestColors.CROSS}{TestColors.RESET}"
    print(f"  {test_name:40s} {status}")
    if details and not success:
        print(f"    {TestColors.YELLOW}详情: {details}{TestColors.RESET}")


def test_format_detection():
    """测试格式自动检测功能"""
    print_header("测试 1: 地址格式自动检测")
    
    test_cases = [
        # (输入, 期望格式, 描述)
        ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "address", "P2PKH地址"),
        ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "p2sh_address", "P2SH地址"),
        ("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "bech32_address", "Bech32地址(SegWit v0)"),
        ("bc1pw508d6qejxtdg4y5r3zarvary0c5dxwkd9k6a6w5pnl7nrt4jhe0cgp2x5", "taproot_address", "Taproot地址(bc1p)"),
        ("5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf", "wif", "WIF私钥(非压缩)"),
        ("KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn", "wif", "WIF私钥(压缩)"),
        ("L5oLkpV3aqBjhki6LmvChTCV73v9Pym6UqHYxkz8UwH7qJ8VqJgG", "wif", "WIF私钥(压缩，L开头)"),
        ("0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", "pubkey_compressed", "压缩公钥"),
        ("03fff97bd5755eeea420453a14355235d382f6472f8568a18b2f057a1460297556", "pubkey_compressed", "压缩公钥(03开头)"),
        ("0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8", "pubkey_uncompressed", "非压缩公钥"),
        ("751e76e8199196d454941c45d1b3a323f1433bd6", "hash160", "Hash160"),
        ("", "unknown", "空字符串"),
        ("invalid_address!!!", "unknown", "无效格式"),
    ]
    
    passed = 0
    failed = 0
    
    for input_str, expected_format, description in test_cases:
        actual_format = TargetResolver.detect_format(input_str)
        success = actual_format == expected_format
        
        if success:
            passed += 1
        else:
            failed += 1
        
        print_result(
            description,
            success,
            f"期望: {expected_format}, 实际: {actual_format}"
        )
    
    print(f"\n{TestColors.BOLD}格式检测统计:{TestColors.RESET}")
    print(f"  总计: {len(test_cases)} | {TestColors.GREEN}通过: {passed}{TestColors.RESET} | {TestColors.RED}失败: {failed}{TestColors.RESET}\n")
    
    return failed == 0


def test_address_resolution():
    """测试地址解析功能"""
    print_header("测试 2: 地址解析与转换")
    
    resolver = TargetResolver(enable_cache=False)
    
    test_cases = [
        # (输入, 期望输出类型, 描述)
        ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "success", "P2PKH地址(中本聪创世地址)"),
        ("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2", "success", "P2PKH地址(示例地址2)"),
        ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "success", "P2SH地址(应转换为P2PKH)"),
        ("5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf", "success", "WIF私钥(非压缩，私钥=1)"),
        ("KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn", "success", "WIF私钥(压缩，私钥=1)"),
        ("0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", "success", "压缩公钥(私钥=1)"),
        ("0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8", "success", "非压缩公钥(私钥=1)"),
        ("751e76e8199196d454941c45d1b3a323f1433bd6", "success", "Hash160(私钥=1的hash160)"),
        ("invalid_address", "fail", "无效地址"),
        ("", "fail", "空字符串"),
    ]
    
    passed = 0
    failed = 0
    
    for input_str, expected_type, description in test_cases:
        try:
            result = resolver.resolve(input_str)
            
            if expected_type == "success":
                if result is not None and result.startswith('1'):
                    passed += 1
                    print_result(description, True, f"→ {result[:20]}...")
                else:
                    failed += 1
                    print_result(description, False, f"解析失败或格式错误: {result}")
            else:  # expect fail
                if result is None:
                    passed += 1
                    print_result(description, True)
                else:
                    failed += 1
                    print_result(description, False, f"应返回None但返回: {result}")
        except Exception as e:
            failed += 1
            print_result(description, False, f"异常: {e}")
    
    print(f"\n{TestColors.BOLD}地址解析统计:{TestColors.RESET}")
    print(f"  总计: {len(test_cases)} | {TestColors.GREEN}通过: {passed}{TestColors.RESET} | {TestColors.RED}失败: {failed}{TestColors.RESET}\n")
    
    return failed == 0


def test_wif_to_address_consistency():
    """测试WIF私钥到地址的一致性"""
    print_header("测试 3: WIF私钥到地址的一致性验证")
    
    resolver = TargetResolver(enable_cache=False)
    
    # 已知私钥=1的各种格式
    test_data = {
        "WIF非压缩": "5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf",
        "WIF压缩": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn",
        "压缩公钥": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        "非压缩公钥": "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",
        "Hash160": "751e76e8199196d454941c45d1b3a323f1433bd6",
    }
        
    # 期望的P2PKH地址（私钥=1的非压缩地址）
    # 注意：WIF压缩、压缩公钥生成压缩地址，其他生成非压缩地址
    # Hash160 "751e76e8199196d454941c45d1b3a323f1433bd6" 是压缩公钥的hash160，所以会生成压缩地址
    expected_p2pkh_uncompressed = "1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm"
    expected_p2pkh_compressed = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        
    print(f"{TestColors.BOLD}已知参考地址:{TestColors.RESET}")
    print(f"  非压绽P2PKH: {expected_p2pkh_uncompressed}")
    print(f"  压绽P2PKH:   {expected_p2pkh_compressed}")
    print(f"  Hash160对应压绽地址: {expected_p2pkh_compressed} (因该hash160来自压缩公钥)\n")
        
    passed = 0
    failed = 0
        
    for format_name, input_str in test_data.items():
        result = resolver.resolve(input_str)
            
        if result:
            # WIF压缩、压缩公钥、Hash160都应该生成压缩地址
            # 因为Hash160 "751e76e8199196d454941c45d1b3a323f1433bd6" 是压缩公钥的hash160
            if format_name in ["WIF压缩", "压缩公钥", "Hash160"]:
                success = result == expected_p2pkh_compressed
                expected = expected_p2pkh_compressed
            else:
                # 其他格式生成非压缩地址
                success = result == expected_p2pkh_uncompressed
                expected = expected_p2pkh_uncompressed
                
            if success:
                passed += 1
                print_result(format_name, True, f"→ {result}")
            else:
                failed += 1
                print_result(format_name, False, f"期望: {expected}, 实际: {result}")
        else:
            failed += 1
            print_result(format_name, False, "解析返回None")
    
    print(f"\n{TestColors.BOLD}一致性验证统计:{TestColors.RESET}")
    print(f"  总计: {len(test_data)} | {TestColors.GREEN}通过: {passed}{TestColors.RESET} | {TestColors.RED}失败: {failed}{TestColors.RESET}\n")
    
    return failed == 0


def test_cache_functionality():
    """测试缓存功能"""
    print_header("测试 4: 解析缓存功能")
    
    resolver = TargetResolver(enable_cache=True, cache_max_size=100)
    
    test_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    
    # 第一次解析（缓存未命中）
    result1 = resolver.resolve(test_address)
    stats1 = resolver.get_cache_stats()
    
    # 第二次解析（应命中缓存）
    result2 = resolver.resolve(test_address)
    stats2 = resolver.get_cache_stats()
    
    passed = 0
    failed = 0
    
    # 测试结果一致性
    test1 = result1 == result2 == test_address
    if test1:
        passed += 1
        print_result("两次解析结果一致", True)
    else:
        failed += 1
        print_result("两次解析结果一致", False, f"结果1: {result1}, 结果2: {result2}")
    
    # 测试缓存命中
    test2 = stats2.get('hits', 0) >= 1
    if test2:
        passed += 1
        print_result("缓存命中统计", True, f"命中: {stats2.get('hits', 0)}, 未命中: {stats2.get('misses', 0)}")
    else:
        failed += 1
        print_result("缓存命中统计", False, f"统计: {stats2}")
    
    # 测试清空缓存
    resolver.clear_cache()
    stats3 = resolver.get_cache_stats()
    test3 = stats3.get('hits', 0) == 0 and stats3.get('misses', 0) == 0
    if test3:
        passed += 1
        print_result("清空缓存", True)
    else:
        failed += 1
        print_result("清空缓存", False, f"清空后统计: {stats3}")
    
    print(f"\n{TestColors.BOLD}缓存功能统计:{TestColors.RESET}")
    print(f"  总计: 3 | {TestColors.GREEN}通过: {passed}{TestColors.RESET} | {TestColors.RED}失败: {failed}{TestColors.RESET}\n")
    
    return failed == 0


def test_batch_resolution():
    """测试批量解析功能"""
    print_header("测试 5: 批量地址解析")
    
    resolver = TargetResolver(enable_cache=False)
    
    test_inputs = [
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 有效
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # 有效
        "invalid_address",                    # 无效
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH有效
        "",                                   # 空字符串
        "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",  # Bech32
    ]
    
    results = resolver.resolve_batch(test_inputs)
    
    passed = 0
    failed = 0
    
    # 验证有效地址数量
    valid_count = sum(1 for v in results.values() if v is not None)
    if valid_count == 4:  # 应该有4个有效地址
        passed += 1
        print_result(f"有效地址数量({valid_count}/4)", True)
    else:
        failed += 1
        print_result(f"有效地址数量({valid_count}/4)", False, f"实际: {valid_count}")
    
    # 验证具体地址
    test_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    if results.get(test_address) == test_address:
        passed += 1
        print_result("P2PKH地址解析", True)
    else:
        failed += 1
        print_result("P2PKH地址解析", False, f"结果: {results.get(test_address)}")
    
    # 验证无效地址返回None
    if results.get("invalid_address") is None:
        passed += 1
        print_result("无效地址过滤", True)
    else:
        failed += 1
        print_result("无效地址过滤", False, f"应返回None但返回: {results.get('invalid_address')}")
    
    print(f"\n{TestColors.BOLD}批量解析统计:{TestColors.RESET}")
    print(f"  输入: {len(test_inputs)} | 有效: {valid_count} | {TestColors.GREEN}通过: {passed}{TestColors.RESET} | {TestColors.RED}失败: {failed}{TestColors.RESET}\n")
    
    return failed == 0


def test_file_loading():
    """测试从文件加载地址"""
    print_header("测试 6: 从文件加载地址")
    
    import tempfile
    
    resolver = TargetResolver(enable_cache=False)
    
    # 创建临时测试文件
    test_content = """# 测试地址文件
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2

# 这是注释
invalid_address
3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_path = f.name
    
    try:
        addresses = resolver.load_from_file(temp_path)
        
        passed = 0
        failed = 0
        
        # 验证加载数量（应该3个有效地址）
        if len(addresses) == 3:
            passed += 1
            print_result(f"加载地址数量({len(addresses)}/3)", True)
        else:
            failed += 1
            print_result(f"加载地址数量({len(addresses)}/3)", False, f"实际: {len(addresses)}")
        
        # 验证特定地址
        if "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in addresses:
            passed += 1
            print_result("包含创世地址", True)
        else:
            failed += 1
            print_result("包含创世地址", False)
        
        # 验证无效地址被过滤
        if "invalid_address" not in addresses:
            passed += 1
            print_result("无效地址已过滤", True)
        else:
            failed += 1
            print_result("无效地址已过滤", False)
        
        print(f"\n{TestColors.BOLD}文件加载统计:{TestColors.RESET}")
        print(f"  加载地址: {len(addresses)} | {TestColors.GREEN}通过: {passed}{TestColors.RESET} | {TestColors.RED}失败: {failed}{TestColors.RESET}\n")
        
        return failed == 0
        
    finally:
        os.unlink(temp_path)


def test_security_checks():
    """测试安全检查"""
    print_header("测试 7: 安全验证（路径遍历防护）")
    
    resolver = TargetResolver(enable_cache=False)
    
    test_cases = [
        ("../etc/passwd", "基础路径遍历"),
        ("../../secret.txt", "双点遍历"),
        ("..\\..\\windows\\system32", "Windows遍历"),
        ("....//....//etc/passwd", "双点混淆"),
    ]
    
    passed = 0
    failed = 0
    
    for malicious_path, description in test_cases:
        result = resolver.load_from_file(malicious_path)
        if result == set():
            passed += 1
            print_result(description, True)
        else:
            failed += 1
            print_result(description, False, f"应返回空集合但返回: {result}")
    
    print(f"\n{TestColors.BOLD}安全检查统计:{TestColors.RESET}")
    print(f"  总计: {len(test_cases)} | {TestColors.GREEN}通过: {passed}{TestColors.RESET} | {TestColors.RED}失败: {failed}{TestColors.RESET}\n")
    
    return failed == 0


def main():
    """主测试函数"""
    print_header("[TEST] 比特币地址格式解析功能全面验证")
    
    print(f"{TestColors.BOLD}测试环境:{TestColors.RESET}")
    print(f"  Python版本: {sys.version}")
    print(f"  项目路径: {os.path.dirname(os.path.abspath(__file__))}\n")
    
    results = {}
    
    # 执行所有测试
    results["格式检测"] = test_format_detection()
    results["地址解析"] = test_address_resolution()
    results["WIF一致性"] = test_wif_to_address_consistency()
    results["缓存功能"] = test_cache_functionality()
    results["批量解析"] = test_batch_resolution()
    results["文件加载"] = test_file_loading()
    results["安全检查"] = test_security_checks()
    
    # 汇总统计
    print_header("[SUMMARY] 测试总结")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    failed_tests = total_tests - passed_tests
    
    print(f"{TestColors.BOLD}测试模块统计:{TestColors.RESET}\n")
    
    for test_name, success in results.items():
        status = f"{TestColors.GREEN}[PASS]{TestColors.RESET}" if success else f"{TestColors.RED}[FAIL]{TestColors.RESET}"
        print(f"  {test_name:20s} {status}")
    
    print(f"\n{TestColors.CYAN}{'='*70}{TestColors.RESET}")
    print(f"{TestColors.BOLD}总计: {total_tests} 个测试模块 | "
          f"{TestColors.GREEN}通过: {passed_tests}{TestColors.RESET} | "
          f"{TestColors.RED}失败: {failed_tests}{TestColors.RESET}")
    print(f"{TestColors.CYAN}{'='*70}{TestColors.RESET}\n")
    
    if failed_tests == 0:
        print(f"{TestColors.GREEN}{TestColors.BOLD}[PASS] 所有测试通过！地址格式解析功能正常。{TestColors.RESET}\n")
        return 0
    else:
        print(f"{TestColors.RED}{TestColors.BOLD}[FAIL] 有 {failed_tests} 个测试模块失败，请检查详情。{TestColors.RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
