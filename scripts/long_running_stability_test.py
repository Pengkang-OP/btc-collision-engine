#!/usr/bin/env python3
"""长时间运行稳定性测试脚本

用于验证引擎长时间运行的稳定性和性能衰减情况。

使用方法:
    # 运行 1 小时稳定性测试
    python scripts/long_running_stability_test.py --duration 3600

    # 运行 8 小时长时间测试
    python scripts/long_running_stability_test.py --duration 28800
"""

import time
import json
import sys
import os
import argparse
from datetime import datetime, timezone

# 设置 stdout 编码
if sys.stdout.encoding.lower() in ('gbk', 'gb2312', 'cp936'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def get_memory_mb():
    """获取当前进程内存使用 (MB)"""
    try:
        import psutil
        proc = psutil.Process()
        return round(proc.memory_info().rss / 1024 / 1024, 2)
    except ImportError:
        return 0.0


def main():
    parser = argparse.ArgumentParser(description="长时间运行稳定性测试")
    parser.add_argument("--duration", type=int, default=300,
                        help="测试持续时间（秒），默认 300 (5分钟)")
    parser.add_argument("--interval", type=int, default=30,
                        help="采样间隔（秒），默认 30")
    parser.add_argument("--output", type=str, default=None,
                        help="输出文件路径")
    args = parser.parse_args()

    output_path = args.output or f"test_results/long_running_test_{int(time.time())}.json"
    os.makedirs("test_results", exist_ok=True)

    print("=" * 60)
    print("长时间运行稳定性测试")
    print("=" * 60)
    print(f"  测试持续时间: {args.duration} 秒 ({args.duration / 3600:.1f} 小时)")
    print(f"  采样间隔: {args.interval} 秒")
    print(f"  预估采样数: {args.duration // args.interval}")
    print(f"  输出文件: {output_path}")
    print()

    try:
        import pyopencl as cl
        devices = [d.name.strip() for p in cl.get_platforms() for d in p.get_devices()]
        print(f"  GPU 设备: {', '.join(devices)}")
    except ImportError:
        devices = []

    # 内存基准
    initial_mem = get_memory_mb()
    print(f"  初始内存: {initial_mem:.1f} MB")
    print()

    # 运行测试
    from src.collision.gpu.engine import GPUCollisionEngine
    import warnings
    warnings.filterwarnings("ignore")

    target_idx = 1 if len(devices) > 1 else 0
    engine = GPUCollisionEngine(
        targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
        device_index=target_idx,
        batch_size=1048576,
    )

    samples = []
    start_time = time.time()
    engine.start()

    print("开始采样...")
    print(f"{'时间(s)':<10} {'速度(keys/s)':<15} {'已检测':<15} {'内存(MB)':<12}")
    print("-" * 55)

    sample_count = 0
    while time.time() - start_time < args.duration:
        time.sleep(args.interval)
        sample_count += 1
        elapsed = time.time() - start_time
        stats = getattr(engine, 'stats', None)
        speed = getattr(stats, 'speed', 0) if stats else 0
        total = getattr(stats, 'total_checked', 0) if stats else 0
        mem = get_memory_mb()

        sample = {
            "elapsed_seconds": round(elapsed, 1),
            "speed_keys_per_sec": speed,
            "total_checked": total,
            "memory_mb": mem,
        }
        samples.append(sample)
        print(f"{elapsed:<10.1f} {speed:<15,.0f} {total:<15,} {mem:<12.1f}")

    engine.stop()
    time.sleep(2)

    # 分析结果
    final_mem = get_memory_mb()
    speeds = [s["speed_keys_per_sec"] for s in samples if s["speed_keys_per_sec"] > 0]
    # memories = [s["memory_mb"] for s in samples]

    result = {
        "test_type": "long_running_stability_test",
        "duration_seconds": args.duration,
        "sample_count": sample_count,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "gpu_devices": devices,
        "initial_memory_mb": initial_mem,
        "final_memory_mb": final_mem,
        "memory_growth_mb": round(final_mem - initial_mem, 2),
        "avg_speed_keys_per_sec": round(sum(speeds) / len(speeds)) if speeds else 0,
        "min_speed_keys_per_sec": min(speeds) if speeds else 0,
        "max_speed_keys_per_sec": max(speeds) if speeds else 0,
        "samples": samples,
    }

    print("-" * 55)
    print("\n测试完成!")
    print(f"  采样数: {sample_count}")
    print(f"  平均速度: {result['avg_speed_keys_per_sec']:,} keys/s")
    print(f"  最低速度: {result['min_speed_keys_per_sec']:,} keys/s")
    print(f"  最高速度: {result['max_speed_keys_per_sec']:,} keys/s")
    print(f"  内存增长: {result['memory_growth_mb']:+.1f} MB")

    if result['memory_growth_mb'] > 50:
        print("  警告: 内存增长超过 50MB，可能存在内存泄漏!")
    else:
        print("  内存稳定，无泄漏迹象")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n结果保存至: {output_path}")


if __name__ == "__main__":
    main()
