#!/usr/bin/env python3
"""性能衰减曲线监控脚本 - 长时间运行性能记录.

使用方法:
    python scripts/benchmarking/monitor_performance_decay.py --duration 3600 --interval 60

这将在 1 小时内每分钟记录一次性能数据，生成性能衰减曲线 CSV 文件。
"""

import argparse
import csv
import time
from datetime import UTC, datetime


def get_gpu_devices():
    """获取 GPU 设备信息."""
    try:
        import pyopencl as cl

        devices = []
        for platform in cl.get_platforms():
            for device in platform.get_devices():
                devices.append(
                    {
                        "name": device.name.strip(),
                        "platform": platform.name.strip(),
                    },
                )
        return devices
    except ImportError:
        return []


def get_performance(engine=None):
    """获取当前性能指标."""
    data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "speed_keys_per_sec": 0,
        "total_checked": 0,
        "matches": 0,
        "elapsed_seconds": 0,
        "memory_rss_mb": 0,
        "memory_vms_mb": 0,
        "cpu_percent": 0,
    }

    try:
        import psutil

        proc = psutil.Process()
        mem = proc.memory_info()
        data["memory_rss_mb"] = round(mem.rss / 1024 / 1024, 2)
        data["memory_vms_mb"] = round(mem.vms / 1024 / 1024, 2)
        data["cpu_percent"] = proc.cpu_percent(interval=0)
    except (ImportError, psutil.Error):
        pass

    if engine and hasattr(engine, "stats") and engine.stats:
        stats = engine.stats
        data["speed_keys_per_sec"] = getattr(stats, "speed", 0) or 0
        data["total_checked"] = getattr(stats, "total_checked", 0) or 0
        data["matches"] = len(getattr(stats, "matches", []) or [])
        data["elapsed_seconds"] = getattr(stats, "elapsed", 0) or 0

    return data


def main():
    parser = argparse.ArgumentParser(description="性能衰减曲线监控")
    parser.add_argument(
        "--duration", type=int, default=3600, help="监控持续时间（秒），默认 3600 (1 小时)",
    )
    parser.add_argument("--interval", type=int, default=60, help="采样间隔（秒），默认 60")
    parser.add_argument("--output", type=str, default=None, help="输出 CSV 文件路径")
    args = parser.parse_args()

    output_path = args.output or f"performance_decay_{int(time.time())}.csv"
    print("性能衰减曲线监控")
    print(f"   持续时间: {args.duration} 秒")
    print(f"   采样间隔: {args.interval} 秒")
    print(f"   预估采样数: {args.duration // args.interval}")
    print(f"   输出文件: {output_path}")

    devices = get_gpu_devices()
    if devices:
        print(f"   GPU 设备: {', '.join(d['name'] for d in devices)}")
    else:
        print("   GPU 设备: 未检测到")

    print()
    print("开始监控...")
    print(f"{'时间戳':<25} {'速度(keys/s)':<15} {'已检测':<15} {'RSS(MB)':<12} {'CPU%':<8}")
    print("-" * 80)

    fieldnames = [
        "timestamp",
        "speed_keys_per_sec",
        "total_checked",
        "matches",
        "elapsed_seconds",
        "memory_rss_mb",
        "memory_vms_mb",
        "cpu_percent",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        start_time = time.time()
        sample_count = 0

        while time.time() - start_time < args.duration:
            data = get_performance()
            writer.writerow(data)
            f.flush()

            sample_count += 1
            print(
                f"{data['timestamp']:<25} "
                f"{data['speed_keys_per_sec']:<15.0f} "
                f"{data['total_checked']:<15} "
                f"{data['memory_rss_mb']:<12.2f} "
                f"{data['cpu_percent']:<8.1f}",
            )

            # 等待下一个采样间隔
            time.sleep(args.interval)

    print("-" * 80)
    print(f"监控完成！共采集 {sample_count} 个样本")
    print(f"   数据已保存至: {output_path}")
    print()
    print("使用以下命令生成图表:")
    print(
        f'   python -c "import pandas as pd; import matplotlib.pyplot as plt; '
        f"df = pd.read_csv('{output_path}'); "
        f"df['elapsed'] = df['elapsed_seconds']; "
        f"plt.plot(df['elapsed'], df['speed_keys_per_sec']); "
        f"plt.xlabel('Time (s)'); plt.ylabel('Speed (keys/s)'); "
        f"plt.title('Performance Decay Curve'); plt.savefig('decay_curve.png')\"",
    )


if __name__ == "__main__":
    main()
