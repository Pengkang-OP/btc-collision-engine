#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU碰撞引擎性能对比测试
测试不同配置下的性能差异

配置对比:
- A: 显存效率45% + batch_size=65536 (原始配置)
- B: 显存效率70% + batch_size=65536 (用户优化)
- C: 显存效率70% + batch_size=131072 (进一步优化)
"""

import sys
import os
import time
import json

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.collision.gpu_collision_engine import GPUCollisionEngine  # noqa: E402


def test_config(config_name, batch_size, test_duration=30):
    """测试特定配置"""
    print(f"\n{'=' * 80}")
    print(f"  配置测试: {config_name}")
    print(f"{'=' * 80}")

    targets = {
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr",
    }

    stats_history = []

    def on_progress(stats):
        stats_history.append(
            {
                "total_checked": stats.total_checked,
                "keys_per_second": stats.speed,  # 修复: 使用speed而非keys_per_second
                "matches": stats.matches,
            }
        )

    def on_match(match_info):
        print(f"  🎯 发现匹配! 私钥: {match_info.get('private_key', 'N/A')}")

    try:
        start_init = time.time()
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=batch_size,
            on_progress=on_progress,
            on_match=on_match,
            use_enhanced_monitoring=True,
            use_gpu_memory_pool=True,
        )
        init_time = time.time() - start_init

        engine._gpu_device.get_device_info()
        memory_efficiency = getattr(engine._gpu_device, "memory_efficiency", 0.45)

        print(f"  批次大小: {batch_size:,}")
        print(f"  显存效率: {memory_efficiency * 100:.0f}%")
        print(f"  初始化时间: {init_time:.2f}秒")
        print()

        # 开始测试
        engine.start(mode="random")

        print(f"  运行 {test_duration} 秒...")
        print()

        start_time = time.time()
        while time.time() - start_time < test_duration:
            time.sleep(5)
            if stats_history:
                latest = stats_history[-1]
                elapsed = time.time() - start_time
                print(
                    f"  [{elapsed:5.1f}s] {latest['total_checked']:>10,} keys | "
                    f"{latest['keys_per_second']:>10.2f} keys/s"
                )

        engine.stop()

        # 统计结果
        if stats_history:
            speeds = [s["keys_per_second"] for s in stats_history if s["keys_per_second"] > 0]
            total_keys = stats_history[-1]["total_checked"]
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            max_speed = max(speeds) if speeds else 0

            print("\n  结果:")
            print(f"    总检查数: {total_keys:,} keys")
            print(f"    平均速度: {avg_speed:,.2f} keys/s")
            print(f"    峰值速度: {max_speed:,.2f} keys/s")

            return {
                "config": config_name,
                "batch_size": batch_size,
                "memory_efficiency": memory_efficiency,
                "total_keys": total_keys,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "speeds": speeds,
            }

    except Exception as e:
        print(f"  错误: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("=" * 80)
    print("  GPU碰撞引擎性能对比测试")
    print("=" * 80)
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 测试配置
    configs = [
        ("A: 45%效率 + 65K批次", 65536),
        ("B: 70%效率 + 65K批次", 65536),
        ("C: 70%效率 + 131K批次", 131072),
    ]

    results = []

    for config_name, batch_size in configs:
        print(f"\n>>> 开始测试配置 {config_name}")

        # 注意：需要在测试前修改gpu_collision_engine.py中的memory_efficiency值
        # 这里我们假设已经修改，直接测试

        result = test_config(config_name, batch_size, test_duration=30)
        if result:
            results.append(result)

        print(f"\n>>> 配置 {config_name} 测试完成")
        time.sleep(2)  # 等待GPU资源释放

    # 生成对比报告
    if results:
        print(f"\n{'=' * 80}")
        print("  性能对比报告")
        print(f"{'=' * 80}")
        print()

        print(f"{'配置':<30} {'批次大小':>10} {'平均速度':>12} {'峰值速度':>12} {'提升':>8}")
        print("-" * 80)

        baseline = results[0]["avg_speed"]
        for r in results:
            improvement = ((r["avg_speed"] - baseline) / baseline * 100) if baseline > 0 else 0
            print(
                f"{r['config']:<30} {r['batch_size']:>10,} {r['avg_speed']:>10,.2f} "
                f"{r['max_speed']:>10,.2f} {improvement:>6.1f}%"
            )

        print()

        # 找出最佳配置
        best = max(results, key=lambda x: x["avg_speed"])
        print(f"  最佳配置: {best['config']}")
        print(f"  最佳速度: {best['avg_speed']:,.2f} keys/s")
        print(f"  相比基线提升: {((best['avg_speed'] - baseline) / baseline * 100):.1f}%")

        # 保存结果
        report = {
            "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "best_config": best["config"],
            "best_speed": best["avg_speed"],
        }

        report_file = os.path.join(project_root, "test_results", "gpu_performance_comparison.json")
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n  报告已保存: {report_file}")

    print(f"\n{'=' * 80}")
    print("  测试完成!")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
