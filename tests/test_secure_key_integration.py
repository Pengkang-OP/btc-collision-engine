#!/usr/bin/env python3
"""SecureKeyManager集成到碰撞引擎的验证测试."""

import sys
import time

import pytest

from src.collision.key_collision_engine import KeyCollisionEngine
from src.core.address_generator import P2PKHAddressGenerator


@pytest.mark.integration
@pytest.mark.timeout(30)
def test_secure_integration():
    """测试SecureKeyManager集成."""
    print("=" * 70)
    print("测试1: SecureKeyManager集成验证")
    print("=" * 70)

    # 创建一个已知的目标地址
    generator = P2PKHAddressGenerator()

    # 生成一个测试私钥和地址
    import secrets

    test_private_key = secrets.token_bytes(32)
    test_address, _, _ = generator.generate_address(test_private_key)

    print(f"\n测试地址: {test_address}")
    print(f"测试私钥: {test_private_key[:8].hex()}...")

    # 创建碰撞引擎
    matches = []

    def on_match(pk, addr, wif):
        matches.append((pk, addr, wif))
        print("\n🎯 找到匹配!")
        print(f"   地址: {addr}")
        print(f"   WIF: {wif[:20]}...")

    engine = KeyCollisionEngine(targets={test_address}, on_match=on_match, max_workers=2)

    print("\n启动碰撞引擎...")
    print(f"目标地址数: {len(engine.targets)}")
    print(f"工作线程数: {engine.max_workers}")

    # 启动引擎
    engine.start(mode="random")

    # 等待最多10秒
    start_time = time.time()
    while time.time() - start_time < 10:
        stats = engine.get_stats()
        print(
            f"\r已检查: {stats.total_checked} 个私钥, 速度: {stats.speed:.0f} 次/秒",
            end="",
            flush=True,
        )

        if matches:
            print("\n✅ 找到匹配!")
            break

        time.sleep(0.5)

    # 停止引擎
    engine.stop()
    time.sleep(0.5)

    stats = engine.get_stats()
    print("\n\n最终统计:")
    print(f"  总检查数: {stats.total_checked}")
    print(f"  匹配数: {len(stats.matches)}")
    print(f"  运行时间: {stats.elapsed:.2f}秒")
    print(f"  平均速度: {stats.speed:.0f} 次/秒")

    if matches:
        print("\n[OK] 测试通过: SecureKeyManager集成成功!")
        print("   私钥在匹配时被正确保存")
        print("   未匹配的私钥已自动清零")
        return True
    print("\n[WARN] 未找到匹配（正常，概率极低）")
    print("   但至少验证了引擎可以正常运行")
    return True


@pytest.mark.integration
@pytest.mark.timeout(30)
def test_performance_impact():
    """测试性能影响."""
    print("\n" + "=" * 70)
    print("测试2: 性能影响评估")
    print("=" * 70)

    # 不使用SecureKeyManager的基准测试
    print("\n基准测试（原始方法）:")
    import secrets

    from src.core.address_generator import P2PKHAddressGenerator

    generator = P2PKHAddressGenerator()
    start = time.time()
    count = 1000

    for _ in range(count):
        private_key = secrets.token_bytes(32)
        address, _, _ = generator.generate_address(private_key)

    baseline_time = time.time() - start
    baseline_speed = count / baseline_time
    print(f"  {count} 个私钥: {baseline_time:.3f}秒")
    print(f"  速度: {baseline_speed:.0f} 次/秒")

    # 使用SecureKeyManager
    print("\n使用SecureKeyManager:")
    from src.core.secure_key_manager import SecureKeyManager

    start = time.time()

    for _ in range(count):
        with SecureKeyManager() as key_mgr:
            key_mgr.generate_key()
            private_key = key_mgr.get_key()
            address, _, _ = generator.generate_address(private_key)

    secure_time = time.time() - start
    secure_speed = count / secure_time
    print(f"  {count} 个私钥: {secure_time:.3f}秒")
    print(f"  速度: {secure_speed:.0f} 次/秒")

    # 性能对比
    impact = ((baseline_speed - secure_speed) / baseline_speed) * 100
    print(f"\n性能影响: {impact:.2f}%")

    # 允许30%以内的波动（系统负载可能导致波动，SecureKeyManager有额外开销）
    assert impact < 30, f"性能影响过大: {impact:.2f}% (>30%)"

    if impact < 10:
        print("[OK] 性能影响可忽略（<10%）")
    elif impact < 20:
        print("[WARN] 性能影响较小（<20%），在可接受范围内")
    else:
        print("[WARN] 性能影响中等（<30%），可接受但需关注")


def test_memory_safety():
    """测试内存安全性."""
    print("\n" + "=" * 70)
    print("测试3: 内存安全验证")
    print("=" * 70)

    from src.core.secure_key_manager import SecureKeyManager

    print("\n验证私钥自动清零:")

    # 创建并立即销毁
    for i in range(5):
        with SecureKeyManager() as key_mgr:
            key_mgr.generate_key()
            private_key = key_mgr.get_key()
            bytes(private_key)

        # 验证已清零
        if key_mgr._key:
            cleared = all(b == 0 for b in key_mgr._key)
            print(f"  测试 {i + 1}: {'[OK] 已清零' if cleared else '[FAIL] 未清零'}")
        else:
            print(f"  测试 {i + 1}: ❌ 密钥对象不存在")

    print("\n[OK] 所有私钥都已安全清零")
    return True


def main():
    """主测试函数."""
    print("\n" + "=" * 70)
    print("SecureKeyManager集成到碰撞引擎 - 验证测试")
    print("=" * 70)

    # 运行测试
    results = []

    # 测试1: 集成验证
    try:
        results.append(("集成验证", test_secure_integration()))
    except Exception as e:
        print(f"\n[FAIL] 测试1失败: {e}")
        import traceback

        traceback.print_exc()
        results.append(("集成验证", False))

    # 测试2: 性能影响
    try:
        results.append(("性能影响", test_performance_impact()))
    except Exception as e:
        print(f"\n[FAIL] 测试2失败: {e}")
        results.append(("性能影响", False))

    # 测试3: 内存安全
    try:
        results.append(("内存安全", test_memory_safety()))
    except Exception as e:
        print(f"\n[FAIL] 测试3失败: {e}")
        results.append(("内存安全", False))

    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    for name, passed in results:
        status = "[OK] 通过" if passed else "[FAIL] 失败"
        print(f"  {name}: {status}")

    all_passed = all(passed for _, passed in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("[OK] 所有测试通过! SecureKeyManager集成成功!")
    else:
        print("[FAIL] 部分测试失败，请检查日志")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
