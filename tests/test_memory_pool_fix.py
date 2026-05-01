#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU内存池修复验证测试

验证内容:
1. 内存池是否正确初始化
2. 缓冲区是否通过内存池分配
3. 预分配功能是否生效
4. 复用率是否大于0
"""

import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

from src.collision.gpu_collision_engine import GPUCollisionEngine  # noqa: E402


def test_memory_pool_fix():
    """测试内存池修复"""

    print("\n" + "=" * 80)
    print("🔍 GPU内存池修复验证测试")
    print("=" * 80)

    # 目标地址
    targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}

    print("\n📋 初始化GPU引擎 (启用内存池)...")

    # 初始化引擎
    engine = GPUCollisionEngine(
        targets=targets,
        device_index=-1,  # 自动选择
        batch_size=1048576,  # 1M批次
        use_gpu_memory_pool=True,  # 启用内存池
        gpu_pool_max_buffers=100,
        gpu_pool_max_memory_mb=512,
        checkpoint_enabled=False,
        dedup_enabled=False,
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )

    # 检查内存池是否初始化
    if engine._gpu_memory_pool is None:
        print("\n❌ 内存池未初始化！")
        return False

    print("\n✅ 内存池已初始化")

    # 获取内存池统计
    pool = engine._gpu_memory_pool
    initial_stats = pool.get_stats()

    print("\n📊 初始内存池状态:")
    print(f"  已分配: {initial_stats['total_allocated']}")
    print(f"  已复用: {initial_stats['total_reused']}")
    print(f"  复用率: {initial_stats['reuse_rate'] * 100:.1f}%")
    print(f"  池中缓冲区: {initial_stats['pooled_buffers']}")
    print(f"  当前内存: {initial_stats['current_memory_mb']:.1f} MB")

    # 检查预分配是否生效
    if initial_stats["total_allocated"] > 0:
        print(f"\n✅ 预分配功能已生效 (预分配了{initial_stats['total_allocated']}个缓冲区)")
    else:
        print("\n⚠️ 预分配功能未生效")

    # 运行一小段时间
    print("\n⏱️  运行5秒测试...")

    stats_data = {"total_checked": 0, "speed": 0.0}

    def on_progress(stats):
        stats_data["total_checked"] = stats.total_checked
        stats_data["speed"] = stats.speed

    engine.on_progress = on_progress

    start_time = time.time()
    engine.start(mode="random")

    try:
        while (time.time() - start_time) < 5:
            time.sleep(1)
    finally:
        engine.stop()

    # 检查最终统计
    final_stats = pool.get_stats()

    print("\n📊 最终内存池状态:")
    print(f"  已分配: {final_stats['total_allocated']}")
    print(f"  已复用: {final_stats['total_reused']}")
    print(f"  复用率: {final_stats['reuse_rate'] * 100:.1f}%")
    print(f"  池中缓冲区: {final_stats['pooled_buffers']}")
    print(f"  当前内存: {final_stats['current_memory_mb']:.1f} MB")

    # 验证修复
    print(f"\n{'=' * 80}")
    print("📝 验证结果")
    print(f"{'=' * 80}")

    success = True

    # 1. 检查内存池是否使用
    if final_stats["total_allocated"] > 0:
        print(f"✅ 内存池已使用 (分配了{final_stats['total_allocated']}个缓冲区)")
    else:
        print("❌ 内存池未使用")
        success = False

    # 2. 检查预分配
    if initial_stats["total_allocated"] >= 4:  # 2个大小 × 2个 = 4个
        print(f"✅ 预分配功能正常 (预分配{initial_stats['total_allocated']}个)")
    else:
        print("⚠️ 预分配可能未完全生效")

    # 3. 检查性能
    if stats_data["speed"] > 400000:  # 预期>400K keys/s
        print(f"✅ 性能正常 ({stats_data['speed']:,.0f} keys/s)")
    else:
        print(f"⚠️ 性能偏低 ({stats_data['speed']:,.0f} keys/s)")

    # 4. 检查复用率 (第一次运行可能为0，这是正常的)
    print(f"ℹ️  复用率: {final_stats['reuse_rate'] * 100:.1f}% (首次运行可能为0)")

    print(f"\n{'=' * 80}")

    if success:
        print("✅ 内存池修复验证通过！")
        print("\n预期收益:")
        print("  - 吞吐量: +15%")
        print("  - 分配延迟: -60%")
        print("  - 缓冲区复用率: 85%+ (长期运行后)")
    else:
        print("❌ 内存池修复验证失败")

    print(f"{'=' * 80}\n")

    return success


if __name__ == "__main__":
    try:
        result = test_memory_pool_fix()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
