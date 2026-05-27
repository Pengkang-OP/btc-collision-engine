"""集成测试: 验证优化模块在主引擎中的效果
测试KeyCollisionEngine使用优化版地址生成器的性能.
"""

import io
import sys

# 修复Windows编码（Python 3.7+: reconfigure 安全无副作用）
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", closefd=False)

import secrets
import time

from src.collision.key_collision_engine import KeyCollisionEngine


def test_optimized_engine():
    """测试优化版碰撞引擎."""
    print("=" * 80)
    print("集成测试: 优化版 KeyCollisionEngine")
    print("=" * 80)

    # 创建测试目标地址
    test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}  # 中本聪地址

    # 测试1: 使用优化版引擎(默认)
    print("\n[测试1] 优化版引擎 (默认配置)")
    print("-" * 80)

    start = time.perf_counter()
    engine_opt = KeyCollisionEngine(
        targets=test_targets,
        use_performance_optimization=True,
        precomputed_window_size=8,
        use_simd_hash=True,
        use_memory_pool=True,
    )
    elapsed_init = time.perf_counter() - start

    print(f"  初始化时间: {elapsed_init * 1000:.2f}ms")
    print(f"  生成器类型: {type(engine_opt.generator).__name__}")
    print(f"  目标地址数: {len(engine_opt.targets)}")

    # 测试2: 使用标准版引擎
    print("\n[测试2] 标准版引擎 (禁用优化)")
    print("-" * 80)

    start = time.perf_counter()
    engine_std = KeyCollisionEngine(targets=test_targets, use_performance_optimization=False)
    elapsed_init_std = time.perf_counter() - start

    print(f"  初始化时间: {elapsed_init_std * 1000:.2f}ms")
    print(f"  生成器类型: {type(engine_std.generator).__name__}")
    print(f"  目标地址数: {len(engine_std.targets)}")

    # 测试3: 性能对比 - 生成100个地址
    print("\n[测试3] 性能对比: 生成100个地址")
    print("-" * 80)

    test_keys = [secrets.token_bytes(32) for _ in range(100)]

    # 优化版
    start = time.perf_counter()
    for pk in test_keys:
        engine_opt.generator.generate_from_private_key(pk)
    elapsed_opt = time.perf_counter() - start

    # 标准版
    start = time.perf_counter()
    for pk in test_keys:
        engine_std.generator.generate_address(pk)
    elapsed_std = time.perf_counter() - start

    speedup = elapsed_std / elapsed_opt

    print(f"  优化版: {elapsed_opt:.4f}s ({elapsed_opt / 100 * 1000:.2f}ms/地址)")
    print(f"  标准版: {elapsed_std:.4f}s ({elapsed_std / 100 * 1000:.2f}ms/地址)")
    print(f"  性能提升: {speedup:.2f}x")
    print(f"  速度: {100 / elapsed_opt:.0f} 地址/秒")

    # 测试4: 不同配置对比
    print("\n[测试4] 不同优化配置对比")
    print("-" * 80)

    configs = [
        ("全优化", True, 8, True, True),
        ("仅预计算表", True, 8, False, False),
        ("小窗口(w=6)", True, 6, True, True),
        ("禁用优化", False, 8, True, True),
    ]

    for name, use_opt, window, simd, pool in configs:
        engine = KeyCollisionEngine(
            targets=test_targets,
            use_performance_optimization=use_opt,
            precomputed_window_size=window,
            use_simd_hash=simd,
            use_memory_pool=pool,
        )

        start = time.perf_counter()
        for pk in test_keys[:20]:  # 测试20个
            if use_opt:
                engine.generator.generate_from_private_key(pk)
            else:
                engine.generator.generate_address(pk)
        elapsed = time.perf_counter() - start

        print(f"  {name:15s}: {elapsed:.4f}s ({elapsed / 20 * 1000:.2f}ms/地址)")

    print("\n" + "=" * 80)
    print("集成测试完成!")
    print("=" * 80)

    return speedup


if __name__ == "__main__":
    try:
        speedup = test_optimized_engine()
        print(f"\n✅ 测试通过! 性能提升: {speedup:.2f}x")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
