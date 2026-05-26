#!/usr/bin/env python3
"""
测试262K批次大小性能（Intel Arc推荐值）
"""

import os
import time

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
from src.collision.gpu.engine import GPUCollisionEngine


def test_262k_batch():
    """测试262K批次大小"""
    print("=" * 80)
    print("  GPU碰撞引擎 - 262K批次大小测试")
    print("=" * 80)
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    targets = {
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr",
    }

    stats_history = []

    def on_progress(stats):
        stats_history.append(
            {
                "total_checked": stats.total_checked,
                "speed": stats.speed,
                "matches": (len(stats.matches) if hasattr(stats.matches, "__len__") else stats.matches),
            }
        )

    def on_match(match_info):
        print("  [MATCH] 发现匹配!")

    try:
        # 初始化引擎 - 使用262K批次
        print("  初始化GPU引擎 (batch_size=262144)...")
        start_init = time.time()

        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=262144,  # 262K批次
            on_progress=on_progress,
            on_match=on_match,
            use_enhanced_monitoring=True,
            use_gpu_memory_pool=True,
        )

        init_time = time.time() - start_init

        # 获取设备信息
        device_info = engine._gpu_device.get_device_info()
        memory_efficiency = getattr(engine._gpu_device, "memory_efficiency", 0.70)

        print("\n  GPU设备信息:")
        print(f"    名称: {device_info.get('name', 'Unknown')}")
        print(f"    显存: {device_info.get('global_mem_size', 0) / (1024**3):.2f} GB")
        print(f"    显存效率: {memory_efficiency * 100:.0f}%")
        print(f"    批次大小: {engine.batch_size:,}")
        print(f"    初始化时间: {init_time:.2f}秒")
        print()

        # 开始测试
        print("  开始测试 (运行60秒)...")
        print()

        engine.start(mode="random")

        start_time = time.time()
        test_duration = 60

        while time.time() - start_time < test_duration:
            time.sleep(5)
            if stats_history:
                latest = stats_history[-1]
                elapsed = time.time() - start_time
                print(
                    f"  [{elapsed:5.1f}s] {latest['total_checked']:>12,} keys | "
                    f"{latest['speed']:>10.2f} keys/s"
                )

        engine.stop()

        # 统计结果
        if stats_history:
            speeds = [s["speed"] for s in stats_history if s["speed"] > 0]
            total_keys = stats_history[-1]["total_checked"]
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            max_speed = max(speeds) if speeds else 0
            min_speed = min(speeds) if speeds else 0

            # 计算稳定性
            if avg_speed > 0:
                std_dev = (sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)) ** 0.5
                cv = (std_dev / avg_speed) * 100
            else:
                cv = 0

            print(f"\n{'=' * 80}")
            print("  测试结果")
            print(f"{'=' * 80}")
            print(f"    总运行时间: {time.time() - start_time:.2f}秒")
            print(f"    总检查数:   {total_keys:,} keys")
            print(f"    平均速度:   {avg_speed:,.2f} keys/s")
            print(f"    峰值速度:   {max_speed:,.2f} keys/s")
            print(f"    最低速度:   {min_speed:,.2f} keys/s")
            print(f"    稳定性:     变异系数 {cv:.2f}%")
            print()

            # 与之前配置对比
            print(f"{'=' * 80}")
            print("  性能对比")
            print(f"{'=' * 80}")
            print("    65K批次:    44,096 keys/s (基线)")
            print("    131K批次:   46,333 keys/s (+5.1%)")
            print(
                f"    262K批次:   {avg_speed:,.2f} keys/s ({((avg_speed - 44096) / 44096 * 100):+.1f}%)"
            )
            print()

            return {
                "batch_size": 262144,
                "total_keys": total_keys,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "min_speed": min_speed,
                "cv": cv,
            }

    except Exception as e:
        print(f"\n  错误: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = test_262k_batch()

    if result:
        print(f"\n{'=' * 80}")
        print("  测试完成!")
        print(f"{'=' * 80}")
    else:
        print(f"\n{'=' * 80}")
        print("  测试失败!")
        print(f"{'=' * 80}")
