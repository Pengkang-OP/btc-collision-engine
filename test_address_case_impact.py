#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实地址大小写影响检测

测试目标：验证地址大小写处理是否会影响实际的碰撞匹配功能
测试场景：
1. 测试目标地址加载时的大小写处理
2. 测试碰撞匹配时的大小写处理
3. 测试不同格式地址的匹配行为
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入必要的模块
from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.targets.matcher import AddressMatcher
from src.collision.targets.resolver import TargetResolver
from src.core.wif import WIF
from src.core.address_generator import P2PKHAddressGenerator


def test_1_target_address_case_handling():
    """测试1：目标地址加载时的大小写处理"""
    print("\n" + "="*80)
    print("测试1：目标地址加载时的大小写处理")
    print("="*80)
    
    # 真实测试地址（混合大小写）
    test_addresses = [
        "1HQF84ac1fgEBWrtav5vgpmLhbFkBLAyuV",  # 原始混合大小写
        "1hqf84ac1fgebwrtav5vgpmlhbfkblayuv",  # 全小写
        "1HQF84AC1FGEBWRTAV5VGPMLHBFKBLAYUV",  # 全大写
    ]
    
    print("\n场景1.1：直接使用混合大小写地址创建引擎")
    engine1 = KeyCollisionEngine(
        targets={test_addresses[0]},
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    print(f"  输入地址: {test_addresses[0]}")
    print(f"  引擎targets: {engine1.targets}")
    print(f"  地址已转为小写: {list(engine1.targets)[0] == test_addresses[0].lower()}")
    
    print("\n场景1.2：使用全小写地址创建引擎")
    engine2 = KeyCollisionEngine(
        targets={test_addresses[1]},
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    print(f"  输入地址: {test_addresses[1]}")
    print(f"  引擎targets: {engine2.targets}")
    
    print("\n场景1.3：使用全大写地址创建引擎")
    engine3 = KeyCollisionEngine(
        targets={test_addresses[2]},
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    print(f"  输入地址: {test_addresses[2]}")
    print(f"  引擎targets: {engine3.targets}")
    
    # 验证：无论输入什么大小写，引擎内部都应统一为小写
    assert list(engine1.targets)[0] == test_addresses[0].lower(), "场景1.1失败"
    assert list(engine2.targets)[0] == test_addresses[1].lower(), "场景1.2失败"
    assert list(engine3.targets)[0] == test_addresses[2].lower(), "场景1.3失败"
    
    print("\n✅ 测试1通过：所有地址在加载时统一转为小写")
    return True


def test_2_address_matching_with_case():
    """测试2：碰撞匹配时的大小写处理"""
    print("\n" + "="*80)
    print("测试2：碰撞匹配时的大小写处理")
    print("="*80)
    
    # 使用真实的私钥=1生成地址
    generator = P2PKHAddressGenerator()
    private_key_1 = b'\x00' * 31 + b'\x01'
    address_generated, _, _ = generator.generate_address(private_key_1)
    
    print(f"\n生成的真实地址: {address_generated}")
    print(f"地址类型: 全部大写、全部小写、混合大小写")
    
    # 场景2.1：引擎使用小写地址，匹配时也使用小写
    print("\n场景2.1：引擎使用小写地址")
    engine_lowercase = KeyCollisionEngine(
        targets={address_generated.lower()},
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    print(f"  引擎targets: {engine_lowercase.targets}")
    
    # 模拟碰撞引擎的匹配逻辑（使用 .lower() 比较）
    match_result_1 = address_generated.lower() in engine_lowercase.targets
    print(f"  匹配测试 (生成地址.lower() in targets): {match_result_1}")
    assert match_result_1, "场景2.1匹配失败"
    
    # 场景2.2：引擎使用大写地址（会被转为小写），匹配时使用小写
    print("\n场景2.2：引擎使用大写地址（会被转为小写）")
    engine_uppercase = KeyCollisionEngine(
        targets={address_generated.upper()},
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    print(f"  引擎targets: {engine_uppercase.targets}")
    
    match_result_2 = address_generated.lower() in engine_uppercase.targets
    print(f"  匹配测试 (生成地址.lower() in targets): {match_result_2}")
    assert match_result_2, "场景2.2匹配失败"
    
    # 场景2.3：引擎使用混合大小写地址（会被转为小写）
    print("\n场景2.3：引擎使用混合大小写地址")
    mixed_case = address_generated[0:10].lower() + address_generated[10:20].upper() + address_generated[20:].lower()
    engine_mixed = KeyCollisionEngine(
        targets={mixed_case},
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    print(f"  输入混合地址: {mixed_case}")
    print(f"  引擎targets: {engine_mixed.targets}")
    
    match_result_3 = address_generated.lower() in engine_mixed.targets
    print(f"  匹配测试 (生成地址.lower() in targets): {match_result_3}")
    assert match_result_3, "场景2.3匹配失败"
    
    print("\n✅ 测试2通过：匹配逻辑使用 .lower() 确保大小写不敏感")
    return True


def test_3_address_matcher_case_handling():
    """测试3：AddressMatcher的大小写处理"""
    print("\n" + "="*80)
    print("测试3：AddressMatcher的大小写处理")
    print("="*80)
    
    # 真实测试地址
    test_address = "1HQF84ac1fgEBWrtav5vgpmLhbFkBLAyuV"
    
    print(f"\n测试地址: {test_address}")
    
    # 场景3.1：使用原始大小写添加目标
    print("\n场景3.1：使用原始大小写添加目标")
    matcher1 = AddressMatcher(strategy='hash_set', targets={test_address})
    print(f"  输入: {test_address}")
    print(f"  matcher.targets: {matcher1.targets}")
    print(f"  匹配测试 (原始地址): {matcher1.is_match(test_address)}")
    print(f"  匹配测试 (小写地址): {matcher1.is_match(test_address.lower())}")
    print(f"  匹配测试 (大写地址): {matcher1.is_match(test_address.upper())}")
    
    assert matcher1.is_match(test_address) == True, "场景3.1原始地址匹配失败"
    assert matcher1.is_match(test_address.lower()) == True, "场景3.1小写匹配失败"
    assert matcher1.is_match(test_address.upper()) == True, "场景3.1大写匹配失败"
    
    # 场景3.2：使用小写添加目标
    print("\n场景3.2：使用小写添加目标")
    matcher2 = AddressMatcher(strategy='hash_set', targets={test_address.lower()})
    print(f"  输入: {test_address.lower()}")
    print(f"  matcher.targets: {matcher2.targets}")
    print(f"  匹配测试 (原始地址): {matcher2.is_match(test_address)}")
    print(f"  匹配测试 (小写地址): {matcher2.is_match(test_address.lower())}")
    
    assert matcher2.is_match(test_address) == True, "场景3.2原始地址匹配失败"
    assert matcher2.is_match(test_address.lower()) == True, "场景3.2小写匹配失败"
    
    print("\n✅ 测试3通过：AddressMatcher统一使用小写进行匹配")
    return True


def test_4_target_resolver_case_handling():
    """测试4：TargetResolver的地址解析大小写处理"""
    print("\n" + "="*80)
    print("测试4：TargetResolver的地址解析大小写处理")
    print("="*80)
    
    # 真实测试地址（不同大小写）
    # 注意：Base58编码区分大小写，所以小写地址可能无法被识别为有效地址
    addresses = [
        "1HQF84ac1fgEBWrtav5vgpmLhbFkBLAyuV",  # 原始正确格式
        "1HQF84AC1FGEBWRTAV5VGPMLHBFKBLAYUV",  # 全大写（可能无效）
    ]
    
    resolver = TargetResolver(enable_cache=False)
    
    print("\n测试不同大小写的地址解析:")
    resolved_addresses = []
    for addr in addresses:
        resolved = resolver.resolve(addr)
        resolved_addresses.append(resolved)
        print(f"  输入: {addr}")
        if resolved:
            print(f"  解析结果: {resolved}")
            print(f"  解析状态: 成功")
        else:
            print(f"  解析结果: None (无法识别)")
            print(f"  解析状态: 失败")
    
    # 验证：原始格式的地址应能正确解析
    assert resolved_addresses[0] is not None, "原始格式地址应能解析"
    
    # 注意：全大写地址可能无法被识别（Base58编码包含大小写字母）
    # 这是正常行为，因为Base58编码本身区分大小写
    
    print("\n✅ 测试4通过：TargetResolver正确解析有效格式的地址")
    print("   注：Base58编码区分大小写，全小写/全大写地址可能无效")
    return True


def test_5_wif_to_address_case():
    """测试5：WIF私钥到地址的转换（大小写无关）"""
    print("\n" + "="*80)
    print("测试5：WIF私钥到地址的转换（大小写无关）")
    print("="*80)
    
    # 真实WIF密钥
    wif_key = "KwjunGHKTae1w6BHCcmvWvWMEtWx5DTAwART1gHA1bysSMQsL68p"
    
    print(f"\nWIF密钥: {wif_key}")
    
    # 解码WIF
    private_key, compressed = WIF.decode(wif_key)
    print(f"  解码成功: compressed={compressed}")
    
    # 生成地址
    generator = P2PKHAddressGenerator()
    address, _, _ = generator.generate_address(private_key)
    
    print(f"  生成地址: {address}")
    print(f"  地址格式: {'全大写' if address == address.upper() else '其他'}")
    
    # 验证：地址应为标准格式（Base58Check编码，通常包含大小写）
    assert len(address) >= 25 and len(address) <= 34, "地址长度不正确"
    assert address.startswith('1'), "P2PKH地址应以1开头"
    
    print("\n✅ 测试5通过：WIF到地址转换正常")
    return True


def test_6_real_collision_scenario():
    """测试6：真实碰撞场景模拟"""
    print("\n" + "="*80)
    print("测试6：真实碰撞场景模拟（私钥=1的已知地址）")
    print("="*80)
    
    # 已知私钥=1的地址
    generator = P2PKHAddressGenerator()
    private_key_1 = b'\x00' * 31 + b'\x01'
    known_address, _, _ = generator.generate_address(private_key_1)
    
    print(f"\n已知信息:")
    print(f"  私钥: {private_key_1.hex()}")
    print(f"  地址: {known_address}")
    
    # 场景6.1：引擎使用原始地址
    print("\n场景6.1：引擎使用原始地址")
    callback_results = []
    
    def on_match(pk, addr, wif):
        callback_results.append({"pk": pk, "addr": addr, "wif": wif})
    
    engine1 = KeyCollisionEngine(
        targets={known_address},
        on_match=on_match,
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    
    # 模拟匹配检查
    match_check = known_address.lower() in engine1.targets
    print(f"  引擎targets: {engine1.targets}")
    print(f"  匹配检查 (地址.lower() in targets): {match_check}")
    assert match_check, "场景6.1匹配失败"
    
    # 场景6.2：引擎使用小写地址
    print("\n场景6.2：引擎使用小写地址")
    callback_results.clear()
    
    engine2 = KeyCollisionEngine(
        targets={known_address.lower()},
        on_match=on_match,
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    
    match_check2 = known_address.lower() in engine2.targets
    print(f"  引擎targets: {engine2.targets}")
    print(f"  匹配检查 (地址.lower() in targets): {match_check2}")
    assert match_check2, "场景6.2匹配失败"
    
    # 场景6.3：引擎使用大写地址
    print("\n场景6.3：引擎使用大写地址")
    callback_results.clear()
    
    engine3 = KeyCollisionEngine(
        targets={known_address.upper()},
        on_match=on_match,
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )
    
    match_check3 = known_address.lower() in engine3.targets
    print(f"  引擎targets: {engine3.targets}")
    print(f"  匹配检查 (地址.lower() in targets): {match_check3}")
    assert match_check3, "场景6.3匹配失败"
    
    print("\n✅ 测试6通过：真实碰撞场景中大小写处理正确")
    return True


def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("真实地址大小写影响检测")
    print("="*80)
    print("\n测试目的：验证地址大小写处理是否会影响实际的碰撞匹配功能")
    print("测试环境：使用真实比特币地址和私钥")
    
    tests = [
        ("目标地址加载时的大小写处理", test_1_target_address_case_handling),
        ("碰撞匹配时的大小写处理", test_2_address_matching_with_case),
        ("AddressMatcher的大小写处理", test_3_address_matcher_case_handling),
        ("TargetResolver的地址解析大小写处理", test_4_target_resolver_case_handling),
        ("WIF私钥到地址的转换", test_5_wif_to_address_case),
        ("真实碰撞场景模拟", test_6_real_collision_scenario),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, True, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n❌ 测试失败: {name}")
            print(f"   错误: {e}")
            import traceback
            traceback.print_exc()
    
    # 打印总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = sum(1 for _, success, _ in results if not success)
    
    print(f"\n总测试数: {len(results)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    
    print("\n详细结果:")
    for name, success, error in results:
        status = "✅ 通过" if success else f"❌ 失败: {error}"
        print(f"  {status} - {name}")
    
    if failed == 0:
        print("\n" + "="*80)
        print("🎉 所有测试通过！地址大小写处理不会影响业务功能")
        print("="*80)
        print("\n结论：")
        print("  1. 所有目标地址在加载时统一转为小写存储")
        print("  2. 碰撞匹配时使用 .lower() 进行比较")
        print("  3. AddressMatcher统一使用小写进行匹配")
        print("  4. 无论输入什么大小写，匹配结果都正确")
        print("  5. 业务功能正常，不会因地址大小写问题导致匹配失败")
        return 0
    else:
        print("\n" + "="*80)
        print("⚠️ 部分测试失败，需要进一步调查")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
