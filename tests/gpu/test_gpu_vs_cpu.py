#!/usr/bin/env python3
"""GPU vs CPU 性能对比测试脚本.

测试相同配置下GPU和CPU模式的性能差异
"""

import json
import os
import pathlib
import sys
import time

from src.collision.gpu.engine import GPUCollisionEngine
from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.targets.resolver import TargetResolver


def run_cpu_test(targets, duration=15):
    """运行CPU模式测试."""
    print("\n" + "=" * 70)
    print("[BLUE] 开始 CPU 模式测试")
    print("=" * 70)

    engine = KeyCollisionEngine(
        targets=targets,
        on_progress=lambda s: None,
        on_match=None,
        checkpoint_enabled=False,
        dedup_enabled=False,
        max_workers=None,  # 使用默认CPU核心数
        use_performance_optimization=True,
        precomputed_window_size=8,
        use_simd_hash=True,
        use_memory_pool=True,
    )

    print("启动CPU引擎...")
    engine.start(mode="random")
    start_time = time.time()

    # 运行指定时长
    time.sleep(duration)

    engine.stop()
    time.sleep(0.5)

    stats = engine.get_stats()
    elapsed = time.time() - start_time

    print("\nOK CPU测试完成:")
    print(f"  总检查数: {stats.total_checked:,}")
    print(f"  运行时间: {elapsed:.2f}秒")
    print(f"  平均速度: {stats.total_checked / elapsed:.2f} keys/s")

    return {
        "mode": "CPU",
        "total_checked": stats.total_checked,
        "elapsed": elapsed,
        "speed": stats.total_checked / elapsed,
        "workers": os.cpu_count() or 16,
    }


def run_gpu_test(targets, duration=15):
    """运行GPU模式测试."""
    print("\n" + "=" * 70)
    print("GREEN 开始 GPU 模式测试")
    print("=" * 70)

    try:
        engine = GPUCollisionEngine(
            targets=targets,
            on_progress=lambda s: None,
            on_match=None,
            checkpoint_enabled=False,
            dedup_enabled=False,
            device_index=-1,  # 自动选择GPU
            batch_size=None,  # 自动计算
            use_gpu_memory_pool=True,
        )

        print("启动GPU引擎...")
        engine.start(mode="random")
        start_time = time.time()

        # 运行指定时长
        time.sleep(duration)

        engine.stop()
        time.sleep(0.5)

        stats = engine.get_stats()
        elapsed = time.time() - start_time

        print("\nOK GPU测试完成:")
        print(f"  总检查数: {stats.total_checked:,}")
        print(f"  运行时间: {elapsed:.2f}秒")
        print(f"  平均速度: {stats.total_checked / elapsed:.2f} keys/s")

        return {
            "mode": "GPU",
            "total_checked": stats.total_checked,
            "elapsed": elapsed,
            "speed": stats.total_checked / elapsed,
            "device": "auto-detected",
        }
    except Exception as e:
        print(f"\nERR GPU测试失败: {e}")
        import traceback

        traceback.print_exc()
        return None


def compare_results(cpu_result, gpu_result):
    """对比CPU和GPU结果."""
    print("\n" + "=" * 70)
    print("STATS 性能对比分析")
    print("=" * 70)

    print(f"\n{'指标':<20} {'CPU模式':<20} {'GPU模式':<20}")
    print("-" * 70)
    print(
        f"{'总检查数':<20} {cpu_result['total_checked']:>15,}  {gpu_result['total_checked']:>15,}"
        if gpu_result
        else f"{'总检查数':<20} {cpu_result['total_checked']:>15,}  {'N/A':>20}",
    )
    print(
        f"{'运行时间(秒)':<18} {cpu_result['elapsed']:>15.2f}  {gpu_result['elapsed']:>15.2f}"
        if gpu_result
        else f"{'运行时间(秒)':<18} {cpu_result['elapsed']:>15.2f}  {'N/A':>20}",
    )
    print(
        f"{'平均速度(keys/s)':<18} {cpu_result['speed']:>15.2f}  {gpu_result['speed']:>15.2f}"
        if gpu_result
        else f"{'平均速度(keys/s)':<18} {cpu_result['speed']:>15.2f}  {'N/A':>20}",
    )

    if gpu_result:
        speedup = gpu_result["speed"] / cpu_result["speed"]
        print(f"\nFAST GPU加速比: {speedup:.2f}x")

        if speedup > 1:
            improvement = (speedup - 1) * 100
            print(f"OK GPU性能提升: {improvement:.1f}%")
        else:
            print("WARN  GPU性能未超越CPU")

    print("\n" + "=" * 70)


def main():
    """主函数."""
    print("=" * 70)
    print("  GPU vs CPU 性能对比测试")
    print("=" * 70)

    # 加载目标地址
    print("\n加载目标地址...")
    resolver = TargetResolver()
    targets = resolver.load_from_file("valid_addresses.txt")
    print(f"加载了 {len(targets)} 个目标地址")

    # 运行CPU测试
    cpu_result = run_cpu_test(targets, duration=15)

    # 运行GPU测试
    gpu_result = run_gpu_test(targets, duration=15)

    # 对比结果
    compare_results(cpu_result, gpu_result)

    # 保存测试结果
    results = {"cpu": cpu_result, "gpu": gpu_result, "timestamp": time.time()}

    output_file = "test_results/gpu_vs_cpu_comparison.json"
    pathlib.Path("test_results").mkdir(exist_ok=True, parents=True)
    with pathlib.Path(output_file).open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nNOTE 测试结果已保存: {output_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nERR 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
