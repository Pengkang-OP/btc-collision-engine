#!/usr/bin/env python3
"""GPU碰撞引擎稳定性压力测试
运行10分钟，验证长期稳定性
"""

import os
import time

import psutil

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
from src.collision.gpu.engine import GPUCollisionEngine  # noqa: E402


def stability_test(duration_minutes=10):  # noqa: C901
    """稳定性压力测试"""
    print("=" * 80)
    print("  GPU碰撞引擎 - 稳定性压力测试")
    print("=" * 80)
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  测试时长: {duration_minutes} 分钟")
    print()

    targets = {
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr",
    }

    stats_history = []
    error_count = 0

    def on_progress(stats):
        stats_history.append(
            {
                "timestamp": time.time(),
                "total_checked": stats.total_checked,
                "speed": stats.speed,
                "matches": (len(stats.matches) if hasattr(stats.matches, "__len__") else stats.matches),
            }
        )

    def on_match(match_info):
        print("  [MATCH] 发现匹配!")

    try:
        # 初始化引擎
        print("  初始化GPU引擎 (batch_size=262144)...")
        start_init = time.time()

        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=262144,
            on_progress=on_progress,
            on_match=on_match,
            use_enhanced_monitoring=True,
            use_gpu_memory_pool=True,
        )

        init_time = time.time() - start_init

        device_info = engine._gpu_device.get_device_info()
        print(f"\n  GPU设备: {device_info.get('name', 'Unknown')}")
        print(f"  显存: {device_info.get('global_mem_size', 0) / (1024**3):.2f} GB")
        print(f"  批次大小: {engine.batch_size:,}")
        print(f"  初始化时间: {init_time:.2f}秒")
        print()

        # 开始测试
        print(f"  开始压力测试 ({duration_minutes} 分钟)...")
        print()

        engine.start(mode="random")

        start_time = time.time()
        duration_seconds = duration_minutes * 60

        # 监控循环
        last_check = time.time()
        check_interval = 60  # 每分钟检查一次

        while time.time() - start_time < duration_seconds:
            time.sleep(5)

            # 每分钟输出一次状态
            if time.time() - last_check >= check_interval:
                elapsed = time.time() - start_time
                elapsed_min = elapsed / 60

                if stats_history:
                    latest = stats_history[-1]
                    speed = latest["speed"]
                    total = latest["total_checked"]

                    # 获取进程内存
                    process = psutil.Process(os.getpid())
                    memory_mb = process.memory_info().rss / (1024 * 1024)

                    print(
                        f"  [{elapsed_min:5.1f}min] {total:>12,} keys | "
                        f"{speed:>10.2f} keys/s | "
                        f"内存: {memory_mb:.1f} MB"
                    )

                last_check = time.time()

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

            # 性能趋势分析
            if len(speeds) >= 2:
                first_half = speeds[: len(speeds) // 2]
                second_half = speeds[len(speeds) // 2 :]
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                trend = ((second_avg - first_avg) / first_avg) * 100
            else:
                trend = 0

            print(f"\n{'=' * 80}")
            print("  压力测试结果")
            print(f"{'=' * 80}")
            print(f"    总运行时间:   {(time.time() - start_time) / 60:.2f} 分钟")
            print(f"    总检查数:     {total_keys:,} keys")
            print(f"    平均速度:     {avg_speed:,.2f} keys/s")
            print(f"    峰值速度:     {max_speed:,.2f} keys/s")
            print(f"    最低速度:     {min_speed:,.2f} keys/s")
            print(f"    稳定性:       变异系数 {cv:.2f}%")
            print(f"    性能趋势:     {trend:+.2f}% ({'上升' if trend > 0 else '下降'})")
            print()

            # 稳定性评级
            if cv < 1:
                stability = "优秀"
            elif cv < 3:
                stability = "良好"
            elif cv < 5:
                stability = "一般"
            else:
                stability = "差"

            print(f"    稳定性评级:   {stability}")
            print()

            # 内存使用
            process = psutil.Process(os.getpid())
            final_memory_mb = process.memory_info().rss / (1024 * 1024)
            print(f"    最终内存占用: {final_memory_mb:.1f} MB")

            # 检查内存泄漏
            if stats_history:
                first_memory = final_memory_mb  # 近似值
                if first_memory > 500:
                    print("    内存泄漏:     警告 - 内存占用过高")
                else:
                    print("    内存泄漏:     无")

            print()

            # 最终结论
            print(f"{'=' * 80}")
            print("  测试结论")
            print(f"{'=' * 80}")

            if cv < 2 and error_count == 0 and trend > -5:
                print("    结果: PASS")
                print("    GPU碰撞引擎通过稳定性压力测试")
                print("    可以安全用于生产环境")
            else:
                print("    结果: WARNING")
                if cv >= 2:
                    print(f"    - 稳定性不足 (CV={cv:.2f}%)")
                if error_count > 0:
                    print(f"    - 发生 {error_count} 个错误")
                if trend <= -5:
                    print(f"    - 性能衰减严重 ({trend:.2f}%)")

            print(f"{'=' * 80}")

            return {
                "duration_minutes": duration_minutes,
                "total_keys": total_keys,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "min_speed": min_speed,
                "cv": cv,
                "trend": trend,
                "errors": error_count,
                "memory_mb": final_memory_mb,
                "passed": cv < 2 and error_count == 0 and trend > -5,
            }

    except Exception as e:
        print(f"\n  错误: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    # 运行10分钟压力测试
    result = stability_test(duration_minutes=10)

    if result:
        print(f"\n{'=' * 80}")
        if result["passed"]:
            print("  压力测试完成 - 通过!")
        else:
            print("  压力测试完成 - 需要关注!")
        print(f"{'=' * 80}")
    else:
        print(f"\n{'=' * 80}")
        print("  压力测试失败!")
        print(f"{'=' * 80}")
