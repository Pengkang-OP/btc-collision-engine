#!/usr/bin/env python3
"""GPU碰撞引擎监控面板 - 显示实时状态"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

def clear_screen():
    """清屏"""
    import subprocess

    subprocess.call("cls" if os.name == "nt" else "clear", shell=True)  # nosec B605


def analyze_current_run():
    """分析当前运行的程序"""
    log_file = Path("logs/collision.log")

    if not log_file.exists():
        return None

    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # 查找最近的启动记录
        start_info = None
        gpu_info = None
        error_count = 0
        warning_count = 0
        batch_info = None

        # 从后向前查找
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]

            # 查找启动时间
            if "GPU引擎初始化成功" in line and not start_info:
                try:
                    timestamp = line[:23]
                    start_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S,%f")
                    start_info = {"time": start_time, "timestamp": timestamp}
                except ValueError:
                    pass

            # 查找GPU信息
            if "Intel(R) Arc(TM) A770" in line and not gpu_info:
                gpu_info = "Intel Arc A770"
            elif "NVIDIA" in line and not gpu_info:
                gpu_info = "NVIDIA GPU"

            # 查找batch_size
            if "batch_size:" in line and not batch_info:
                try:
                    # 提取batch_size数值
                    import re

                    match = re.search(r"batch_size:\s*(\d+)", line)
                    if match:
                        batch_info = int(match.group(1))
                except (re.error, ValueError):
                    pass

            # 统计错误和警告(最近1000行)
            if i > len(lines) - 1000:
                if "ERROR" in line:
                    error_count += 1
                if "WARNING" in line or "WARN" in line:
                    warning_count += 1

        # 检查断点文件
        checkpoint_file = Path("src/collision/collision_checkpoint.json")
        checkpoint_info = None

        if checkpoint_file.exists():
            try:
                import json

                with open(checkpoint_file, encoding="utf-8") as f:
                    checkpoint = json.load(f)

                checkpoint_info = {
                    "checked": checkpoint.get("total_checked", 0),
                    "matches": checkpoint.get("match_count", 0),
                    "last_update": checkpoint.get("last_update", ""),
                }
            except (OSError, json.JSONDecodeError):
                pass

        return {
            "start_info": start_info,
            "gpu_info": gpu_info,
            "batch_size": batch_info,
            "error_count": error_count,
            "warning_count": warning_count,
            "checkpoint": checkpoint_info,
        }

    except Exception as e:
        print(f"[ERROR] 分析失败: {e}")
        return None


def display_dashboard():
    """显示监控面板"""
    clear_screen()

    print("=" * 80)
    print("  GPU碰撞引擎监控面板")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # 分析当前运行状态
    status = analyze_current_run()

    if not status:
        print("[ERROR] 无法获取运行状态")
        return

    # GPU信息
    print("GPU设备信息")
    print("-" * 80)
    print(f"  GPU: {status['gpu_info'] or 'Unknown'}")
    print(f"  Batch Size: {status['batch_size'] or 'Unknown':,}")
    print()

    # 运行状态
    print("运行状态")
    print("-" * 80)

    if status["start_info"]:
        start_time = status["start_info"]["time"]
        now = datetime.now()
        runtime = (now - start_time).total_seconds()

        print(f"  启动时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  运行时长: {runtime:.0f} 秒 ({runtime / 60:.1f} 分钟)")

        # 估算性能
        if status["checkpoint"] and status["checkpoint"]["checked"] > 0:
            checked = status["checkpoint"]["checked"]
            speed = checked / runtime if runtime > 0 else 0

            print(f"  已检查: {checked:,} 个密钥")
            print(f"  平均速度: {speed:,.0f} keys/s")
        else:
            print("  已检查: 计算中...")
    else:
        print("  状态: 未检测到运行记录")

    print()

    # 错误统计
    print("错误统计")
    print("-" * 80)

    if status["error_count"] == 0:
        print("  [PASS] 当前运行期间: 0 个错误")
    else:
        print(f"  [WARN] 当前运行期间: {status['error_count']} 个错误")

    if status["warning_count"] < 10:
        print(f"  [PASS] 警告数量: {status['warning_count']} (正常)")
    else:
        print(f"  [INFO] 警告数量: {status['warning_count']} (较多)")

    print()

    # 健康评估
    print("健康评估")
    print("-" * 80)

    health_score = 100

    if status["error_count"] > 0:
        health_score -= 20
        print("  [-20] 存在错误")

    if status["warning_count"] > 50:
        health_score -= 10
        print("  [-10] 警告过多")

    if status["start_info"]:
        print("  [+0] 程序正常运行")
    else:
        health_score -= 50
        print("  [-50] 未检测到运行")

    print()
    print(f"  健康评分: {health_score}/100")

    if health_score >= 80:
        print("  状态: [HEALTHY] 运行正常")
    elif health_score >= 60:
        print("  状态: [WARNING] 需要关注")
    else:
        print("  状态: [ERROR] 存在问题")

    print()
    print("=" * 80)


def main():
    """主循环"""
    print("启动监控面板...")
    print("按 Ctrl+C 停止")
    print()
    time.sleep(1)

    try:
        while True:
            display_dashboard()
            time.sleep(5)  # 每5秒刷新
    except KeyboardInterrupt:
        print()
        print("\n监控已停止")


if __name__ == "__main__":
    main()
