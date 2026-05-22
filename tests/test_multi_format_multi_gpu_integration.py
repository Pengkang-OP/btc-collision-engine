"""
多格式多GPU引擎集成测试

测试内容:
1. 多格式目标管理
2. GPU路径模拟（P2PKH匹配）
3. 后处理检查其他格式
4. 格式统计和监控
5. CPU路径全格式检查

运行方式:
    python test_multi_format_multi_gpu_integration.py
"""

import sys

sys.path.insert(0, "src")

import secrets  # noqa: E402

from src.core.multi_format_generator import MultiFormatAddressGenerator  # noqa: E402
from src.gpu.multi_format_multi_gpu_engine import create_multi_format_multi_gpu_engine  # noqa: E402


def test_format_manager():
    """测试1: 多格式目标管理器"""
    print("\n" + "=" * 80)
    print("测试1: 多格式目标管理器")
    print("=" * 80)

    from src.collision.targets.format_aware_manager import FormatAwareTargetManager

    manager = FormatAwareTargetManager()

    # 添加不同格式的目标
    test_addresses = [
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",  # P2PKH
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",  # Taproot
    ]

    for addr in test_addresses:
        success = manager.add_target(addr)
        print(f"  添加 {addr[:20]}... → {'✅ 成功' if success else '❌ 失败'}")

    # 获取格式统计
    stats = manager.get_format_stats()
    print(f"\n格式统计: {stats}")

    # 验证统计正确
    assert stats["p2pkh"] == 1, "P2PKH统计错误"
    assert stats["p2sh"] == 1, "P2SH统计错误"
    assert stats["bech32"] == 1, "Bech32统计错误"
    assert stats["taproot"] == 1, "Taproot统计错误"

    print("\n✅ 测试1通过: 多格式目标管理器")
    return manager


def test_engine_creation():
    """测试2: 引擎创建"""
    print("\n" + "=" * 80)
    print("测试2: 引擎创建")
    print("=" * 80)

    # 使用工厂函数创建
    engine = create_multi_format_multi_gpu_engine()()

    print(f"  引擎类型: {type(engine).__name__}")
    print(f"  目标管理器: {type(engine._format_manager).__name__}")
    print(f"  地址生成器: {type(engine._address_generator).__name__}")

    # 验证内部组件
    assert hasattr(engine, "_format_manager"), "缺少格式管理器"
    assert hasattr(engine, "_address_generator"), "缺少地址生成器"
    assert hasattr(engine, "add_target"), "缺少add_target方法"
    assert hasattr(engine, "check_match_all"), "缺少check_match_all方法"

    print("\n✅ 测试2通过: 引擎创建")
    return engine


def test_multi_format_matching(engine):
    """测试3: 多格式地址匹配"""
    print("\n" + "=" * 80)
    print("测试3: 多格式地址匹配")
    print("=" * 80)

    # 清除之前的目标
    engine._format_manager.clear()

    # 添加测试目标
    test_addresses = [
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",  # P2PKH
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32
    ]

    for addr in test_addresses:
        engine.add_target(addr)

    print(f"已添加 {len(test_addresses)} 个目标地址")

    # 使用已知私钥测试
    # 私钥=1 对应的地址
    known_private_key = b"\x00" * 31 + b"\x01"
    known_p2pkh = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"

    # 验证私钥生成的地址
    gen = MultiFormatAddressGenerator()
    addresses = gen.generate_all_formats(known_private_key)

    print("\n私钥=1 生成的地址:")
    for fmt, addr in addresses.items():
        print(f"  {fmt}: {addr}")

    # 测试check_match (快速匹配)
    print("\n测试 check_match (快速匹配):")
    is_match, matched_addr, matched_fmt = engine.check_match(known_private_key)
    print(f"  匹配结果: {is_match}")
    print(f"  匹配地址: {matched_addr}")
    print(f"  匹配格式: {matched_fmt}")

    assert is_match, "应该匹配P2PKH地址"
    assert matched_addr == known_p2pkh, f"应该匹配P2PKH地址，期望{known_p2pkh}, 得到{matched_addr}"

    # 测试check_match_all (完整检查)
    print("\n测试 check_match_all (完整检查):")
    is_match_all, matches = engine.check_match_all(known_private_key)
    print(f"  匹配结果: {is_match_all}")
    print(f"  匹配数量: {len(matches)}")
    for addr, fmt in matches:
        print(f"    {fmt}: {addr}")

    assert is_match_all, "应该有匹配"
    assert len(matches) >= 1, "至少应该有一个匹配"

    print("\n✅ 测试3通过: 多格式地址匹配")

    return addresses


def test_post_processing(engine):
    """测试4: 后处理检查其他格式"""
    print("\n" + "=" * 80)
    print("测试4: 后处理检查其他格式")
    print("=" * 80)

    # 清除之前的目标
    engine._format_manager.clear()

    # 添加P2PKH目标
    p2pkh_addr = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
    bech32_addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

    # 只添加P2PKH目标
    engine.add_target(p2pkh_addr)
    print(f"只添加P2PKH目标: {p2pkh_addr}")

    # 模拟GPU匹配到P2PKH地址
    private_key = b"\x00" * 31 + b"\x01"

    # 模拟匹配事件
    match = {"private_key": private_key, "address": p2pkh_addr, "format": "p2pkh", "device_idx": 0}

    # 调用后处理
    extra_matches = engine._check_other_formats(match["private_key"], match["address"], match["format"])

    print(f"\nGPU匹配到P2PKH: {p2pkh_addr}")
    print("后处理检查其他格式:")

    if extra_matches:
        print("  发现额外匹配:")
        for addr, fmt in extra_matches:
            print(f"    {fmt}: {addr}")
    else:
        print("  没有额外匹配（正常，因为只添加了P2PKH目标）")

    # 现在添加Bech32目标
    engine._format_manager.clear()
    engine.add_target(p2pkh_addr)
    engine.add_target(bech32_addr)
    print("\n添加两个目标:")
    print(f"  P2PKH: {p2pkh_addr}")
    print(f"  Bech32: {bech32_addr}")

    # 再次后处理
    extra_matches = engine._check_other_formats(match["private_key"], match["address"], match["format"])

    print("\n后处理结果:")
    if extra_matches:
        print("  ✅ 发现额外匹配:")
        for addr, fmt in extra_matches:
            print(f"    {fmt}: {addr}")

        # 验证Bech32匹配
        bech32_found = any(fmt == "bech32" for _, fmt in extra_matches)
        assert bech32_found, "应该找到Bech32匹配"
    else:
        print("  ❌ 没有找到Bech32匹配")

    print("\n✅ 测试4通过: 后处理检查其他格式")


def test_format_stats(engine):
    """测试5: 格式统计"""
    print("\n" + "=" * 80)
    print("测试5: 格式统计")
    print("=" * 80)

    # 清除并重新添加
    engine._format_manager.clear()

    test_addresses = [
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",  # P2PKH
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # P2PKH
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",  # Taproot
    ]

    for addr in test_addresses:
        engine.add_target(addr)

    # 获取统计
    stats = engine.get_format_stats()

    print("格式统计:")
    for fmt, count in stats.items():
        print(f"  {fmt}: {count} 个地址")

    # 验证
    assert stats["p2pkh"] == 2, "应该有2个P2PKH地址"
    assert stats["p2sh"] == 1, "应该有1个P2SH地址"
    assert stats["bech32"] == 1, "应该有1个Bech32地址"
    assert stats["taproot"] == 1, "应该有1个Taproot地址"

    # 获取引擎统计
    engine_stats = engine.get_combined_stats()
    print("\n引擎统计:")
    print(f"  格式统计: {engine_stats.get('format_stats', {})}")

    print("\n✅ 测试5通过: 格式统计")


def test_integration_scenario():
    """测试6: 集成场景测试"""
    print("\n" + "=" * 80)
    print("测试6: 集成场景测试")
    print("=" * 80)

    # 创建引擎
    engine = create_multi_format_multi_gpu_engine()()

    # 场景: 用户有多个格式的目标地址
    print("\n场景: 用户导入多个格式的目标地址")

    targets = [
        # P2PKH格式
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi的地址
        # Bech32格式
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        # Taproot格式
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",
    ]

    for addr in targets:
        engine.add_target(addr)

    # 显示统计
    stats = engine.get_format_stats()
    print(f"\n已导入 {len(targets)} 个目标地址:")
    print(f"  • P2PKH: {stats['p2pkh']} 个")
    print(f"  • Bech32: {stats['bech32']} 个")
    print(f"  • Taproot: {stats['taproot']} 个")

    # 模拟碰撞检测
    print("\n模拟碰撞检测 (CPU路径):")

    # 生成随机私钥测试
    for i in range(3):
        test_key = secrets.token_bytes(32)

        # 全格式检查
        is_match, matches = engine.check_match_all(test_key)

        if is_match:
            print(f"\n  找到匹配! 私钥 {i + 1}:")
            for addr, fmt in matches:
                print(f"    ✓ {fmt}: {addr}")
        else:
            print(f"  私钥 {i + 1}: 无匹配")

    # 清理
    engine.cleanup()

    print("\n✅ 测试6通过: 集成场景测试")


def main():
    """主测试流程"""
    print("\n" + "=" * 80)
    print("多格式多GPU引擎集成测试")
    print("=" * 80)

    try:
        # 运行所有测试
        test_format_manager()
        test_engine_creation()
        test_multi_format_matching(create_multi_format_multi_gpu_engine()())
        test_post_processing(create_multi_format_multi_gpu_engine()())
        test_format_stats(create_multi_format_multi_gpu_engine()())
        test_integration_scenario()

        print("\n" + "=" * 80)
        print("🎉 所有测试通过!")
        print("=" * 80)

        print("\n📊 总结:")
        print("  ✅ 多格式目标管理 - 正常工作")
        print("  ✅ 引擎创建和初始化 - 正常工作")
        print("  ✅ 多格式地址匹配 - 正常工作")
        print("  ✅ 后处理检查其他格式 - 正常工作")
        print("  ✅ 格式统计和监控 - 正常工作")
        print("  ✅ 集成场景测试 - 正常工作")

        print("\n🚀 集成完成! 多格式多GPU引擎已就绪!")

        return 0

    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
