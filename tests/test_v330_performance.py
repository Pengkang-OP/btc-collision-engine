#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.3.0性能优化测试

测试内容:
1. 内存标志优化效果
2. 批次大小优化（1M vs 1.5M vs 2M）
3. 预期突破600K keys/s

作者: AI Assistant
日期: 2026-04-24
版本: v3.3.0
"""

import sys
import time
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.collision.gpu_collision_engine import GPUCollisionEngine  # noqa: E402


def test_performance_optimization(batch_size: int, test_duration: int = 30):
    """测试特定批次大小的性能"""

    print(f"\n{'=' * 80}")
    print(f"测试批次大小: {batch_size:,} ({batch_size / 1024 / 1024:.2f}M)")
    print(f"测试时长: {test_duration}秒")
    print(f"{'=' * 80}")

    # 目标地址
    targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}

    # 初始化引擎
    print("\n[1/4] 初始化GPU引擎...")
    engine = GPUCollisionEngine(
        targets=targets,
        device_index=-1,
        batch_size=batch_size,
        use_gpu_memory_pool=True,
        gpu_pool_max_buffers=100,
        gpu_pool_max_memory_mb=512,
        checkpoint_enabled=False,
        dedup_enabled=False,
        data_logging_enabled=False,
        use_enhanced_monitoring=False,
    )

    # 检查内存池
    if engine._gpu_memory_pool is None:
        print("❌ 内存池未初始化！")
        return None

    pool = engine._gpu_memory_pool
    initial_stats = pool.get_stats()
    print(
        f"  初始内存池状态: 已分配={initial_stats['total_allocated']}, "
        f"池中={initial_stats['pooled_buffers']}"
    )

    # 启动引擎
    print(f"\n[2/4] 启动引擎（运行{test_duration}秒）...")
    engine.start(mode="random")

    # 监控性能
    start_time = time.time()
    speeds = []

    try:
        while time.time() - start_time < test_duration:
            time.sleep(5)
            stats = engine.get_stats()
            if stats:
                # CollisionStats对象有gpu_speed属性
                if hasattr(stats, "gpu_speed"):
                    speed = stats.gpu_speed
                elif hasattr(stats, "total_keys"):
                    speed = stats.total_keys / max(time.time() - start_time, 1)
                else:
                    speed = 0

                if speed > 0:
                    speeds.append(speed)
                    elapsed = time.time() - start_time
                    print(f"  [{elapsed:.0f}s] 速度: {speed:,.0f} keys/s")
    except KeyboardInterrupt:
        print("\n  测试中断")
    finally:
        engine.stop()

    # 统计结果
    print("\n[3/4] 统计结果...")
    if speeds:
        avg_speed = sum(speeds) / len(speeds)
        max_speed = max(speeds)
        min_speed = min(speeds)

        print(f"  平均速度: {avg_speed:,.0f} keys/s")
        print(f"  最高速度: {max_speed:,.0f} keys/s")
        print(f"  最低速度: {min_speed:,.0f} keys/s")
        print(f"  采样次数: {len(speeds)}")
    else:
        avg_speed = 0
        print("  ❌ 未收集到速度数据")

    # 检查内存池状态
    final_stats = pool.get_stats()
    print("\n  最终内存池状态:")
    print(f"    已分配: {final_stats['total_allocated']}")
    print(f"    已复用: {final_stats['total_reused']}")
    print(f"    复用率: {final_stats['reuse_rate'] * 100:.1f}%")
    print(f"    池中缓冲区: {final_stats['pooled_buffers']}")
    print(f"    当前内存: {final_stats['current_memory_mb']:.1f} MB")

    print("\n[4/4] 清理资源...")
    engine.cleanup()
    print("  ✅ 资源已清理")

    return {
        "batch_size": batch_size,
        "avg_speed": avg_speed,
        "max_speed": max(speeds) if speeds else 0,
        "min_speed": min(speeds) if speeds else 0,
        "reuse_rate": final_stats["reuse_rate"],
        "pooled_buffers": final_stats["pooled_buffers"],
        "memory_mb": final_stats["current_memory_mb"],
    }


def main():
    """主测试流程"""

    print("=" * 80)
    print("GPU性能优化测试 - v3.3.0")
    print("目标: 突破600K keys/s")
    print("=" * 80)

    # 测试不同批次大小
    batch_sizes = [
        1048576,  # 1M (基线)
        1572864,  # 1.5M (优化目标)
        # 2097152,  # 2M (可选)
    ]

    results = []
    test_duration = 30  # 每个测试30秒

    for batch_size in batch_sizes:
        result = test_performance_optimization(batch_size, test_duration)
        if result:
            results.append(result)

        # 等待一下
        time.sleep(2)

    # 总结
    print(f"\n{'=' * 80}")
    print("性能测试结果总结")
    print(f"{'=' * 80}")

    print(f"\n{'批次大小':<15} {'平均速度':<15} {'最高速度':<15} {'复用率':<10} {'显存':<10}")
    print("-" * 80)

    for r in results:
        print(
            f"{r['batch_size'] / 1024 / 1024:>8.2f}M  "
            f"{r['avg_speed']:>12,.0f}  "
            f"{r['max_speed']:>12,.0f}  "
            f"{r['reuse_rate'] * 100:>8.1f}%  "
            f"{r['memory_mb']:>8.1f}MB"
        )

    # 找到最佳结果
    if results:
        best = max(results, key=lambda x: x["avg_speed"])
        print(f"\n🏆 最佳配置: {best['batch_size'] / 1024 / 1024:.2f}M批次")
        print(f"   平均速度: {best['avg_speed']:,.0f} keys/s")

        if best["avg_speed"] > 600000:
            print(f"   ✅ 突破600K目标！超出{(best['avg_speed'] - 600000) / 600000 * 100:.1f}%")
        else:
            gap = 600000 - best["avg_speed"]
            print(f"   ⚠️ 距离600K目标还差{gap:,.0f} keys/s ({gap / 600000 * 100:.1f}%)")

    print(f"\n{'=' * 80}")
    print("测试完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
