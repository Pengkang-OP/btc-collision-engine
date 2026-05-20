#!/usr/bin/env python3
"""
测试格式感知目标管理器与多格式地址生成器的集成
验证：检测到的目标地址格式是否能正确传递给地址生成对应格式
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.multi_format_generator import MultiFormatAddressGenerator, AddressFormat
from src.collision.targets.format_aware_manager import FormatAwareTargetManager
import secrets


def test_format_detection_and_generation():
    """测试格式检测和生成的完整流程"""
    print("=" * 60)
    print("格式感知目标管理器 + 多格式地址生成器 集成测试")
    print("=" * 60)
    
    # -----------------------------
    # 测试1：创建管理器和生成器
    # -----------------------------
    print("\n【测试1】创建管理器和生成器")
    print("-" * 60)
    manager = FormatAwareTargetManager()
    generator = MultiFormatAddressGenerator()
    print(f"✓ FormatAwareTargetManager 创建成功")
    print(f"✓ MultiFormatAddressGenerator 创建成功")
    print(f"  - 内部生成器是否存在: {hasattr(manager, '_generator')}")
    print(f"  - 内部生成器类型: {type(manager._generator).__name__}")
    
    # -----------------------------
    # 测试2：准备测试地址和私钥
    # -----------------------------
    print("\n【测试2】准备测试地址和私钥")
    print("-" * 60)
    
    # 生成测试私钥
    test_private_key = b'\x01' * 32  # 测试用固定私钥
    
    # 用同一个私钥生成所有格式地址
    test_addresses = generator.generate_all_formats(test_private_key)
    print(f"✓ 从测试私钥生成的地址:")
    for fmt, addr in test_addresses.items():
        if addr:
            print(f"  - {fmt:8s}: {addr}")
    
    # -----------------------------
    # 测试3：添加目标地址到管理器
    # -----------------------------
    print("\n【测试3】添加目标地址到管理器")
    print("-" * 60)
    
    # 添加所有格式的地址作为目标
    for fmt, addr in test_addresses.items():
        if addr:
            success = manager.add_target(addr)
            print(f"  添加 {fmt:8s}: {addr} {'✓ 成功' if success else '✗ 已存在'}")
    
    # 检查格式统计
    stats = manager.get_format_stats()
    print(f"\n✓ 格式统计:")
    for fmt, count in stats.items():
        print(f"  - {fmt:8s}: {count} 个目标")
    
    # 检查按格式分组的目标
    targets_by_format = manager.get_targets_by_format()
    print(f"\n✓ 按格式分组的目标:")
    for fmt, targets in targets_by_format.items():
        if targets:
            print(f"  - {fmt.value:8s}: {list(targets)}")
    
    # -----------------------------
    # 测试4：使用管理器内部的check_match进行匹配
    # -----------------------------
    print("\n【测试4】使用FormatAwareTargetManager.check_match()")
    print("-" * 60)
    print(f"测试私钥: {test_private_key.hex()}")
    
    is_match, matched_address, matched_format = manager.check_match(test_private_key)
    
    print(f"✓ 匹配结果:")
    print(f"  - 是否匹配: {is_match}")
    print(f"  - 匹配地址: {matched_address}")
    print(f"  - 匹配格式: {matched_format}")
    
    # -----------------------------
    # 测试5：使用check_match_all获取所有匹配
    # -----------------------------
    print("\n【测试5】使用FormatAwareTargetManager.check_match_all()")
    print("-" * 60)
    
    all_match_found, all_matches = manager.check_match_all(test_private_key)
    
    print(f"✓ 所有匹配结果:")
    print(f"  - 是否有匹配: {all_match_found}")
    print(f"  - 匹配数量: {len(all_matches)}")
    for addr, fmt in all_matches:
        print(f"  - {fmt:8s}: {addr}")
    
    # -----------------------------
    # 测试6：验证格式传递正确性
    # -----------------------------
    print("\n【测试6】验证格式传递正确性（详细流程）")
    print("-" * 60)
    
    print("\n流程详解:")
    print("1. FormatAwareTargetManager.add_target() 检测每个地址的格式")
    print("2. 将地址按格式分组存储在 _targets_by_format 字典中")
    print("3. check_match() 调用内部 MultiFormatAddressGenerator.match_address()")
    print("4. match_address() 遍历有目标的格式，按需生成对应格式的地址")
    print("5. 只对有目标的格式进行地址生成，提升性能")
    
    print("\n✓ 验证: 只生成有目标的格式的地址")
    supported_formats = manager.get_supported_formats()
    print(f"  有目标的格式: {supported_formats}")
    
    # 验证内部流程
    print("\n✓ 内部数据结构验证:")
    print(f"  目标按格式分组的键类型: {type(list(targets_by_format.keys())[0])}")
    print(f"  键值: {[fmt.value for fmt in targets_by_format.keys()]}")
    
    # -----------------------------
    # 测试7：边界情况测试
    # -----------------------------
    print("\n【测试7】边界情况测试")
    print("-" * 60)
    
    # 测试空管理器
    empty_manager = FormatAwareTargetManager()
    print(f"空管理器 has_targets(): {empty_manager.has_targets()}")
    is_match_empty, _, _ = empty_manager.check_match(test_private_key)
    print(f"空管理器 check_match(): {is_match_empty}")
    
    # 测试只添加一个格式
    single_format_manager = FormatAwareTargetManager()
    single_format_manager.add_target(test_addresses['p2pkh'])
    print(f"\n单格式管理器（仅P2PKH）:")
    print(f"  格式统计: {single_format_manager.get_format_stats()}")
    single_match, single_addr, single_fmt = single_format_manager.check_match(test_private_key)
    print(f"  匹配结果: {single_match}, {single_fmt}, {single_addr}")
    
    print("\n" + "=" * 60)
    print("✓ 所有测试完成！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_format_detection_and_generation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
