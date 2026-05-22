#!/usr/bin/env python3
"""实时监控GPU碰撞引擎 - 持续监控模式"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_current_program_info():
    """获取当前运行程序的信息"""
    import json
    import subprocess

    try:
        # 获取最新启动的Python进程
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-Process python -ErrorAction SilentlyContinue | "
                "Sort-Object StartTime -Descending | "
                "Select-Object -First 1 | "
                "ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )

        if result.stdout.strip():
            proc = json.loads(result.stdout)
            return {
                "pid": proc.get("Id", "N/A"),
                "memory_mb": proc.get("WorkingSet", 0) / (1024 * 1024),
                "cpu_seconds": proc.get("CPU", 0),
                "start_time": proc.get("StartTime", "Unknown"),
            }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass

    return None


def check_recent_errors(log_file, since_time):
    """检查指定时间之后的错误"""
    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        errors_after = []
        for line in lines:
            if "ERROR" in line:
                # 提取时间戳
                try:
                    timestamp_str = line[:23]  # "2026-04-21 20:44:19,927"
                    line_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")

                    if line_time >= since_time:
                        errors_after.append(line.strip())
                except (ValueError, AttributeError):
                    pass

        return errors_after
    except OSError:
        return []


def check_gpu_status():
    """检查GPU状态"""
    import subprocess

    try:
        # 尝试使用pyopencl检查GPU
        result = subprocess.run(
            [
                "python",
                "-c",
                "import pyopencl as cl; "
                "platforms = cl.get_platforms(); "
                "devices = []; "
                "[devices.extend(p.get_devices(device_type=cl.device_type.GPU)) for p in platforms]; "
                "print(len(devices))",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        pass

    return None


def main():
    print("=" * 80)
    print("  GPU碰撞引擎 - 实时监控")
    print("=" * 80)
    print()

    log_file = Path("logs/collision.log")

    if not log_file.exists():
        print("[ERROR] 日志文件不存在")
        return

    # 获取程序启动时间
    print("正在检测程序运行状态...")
    print()

    proc_info = get_current_program_info()

    if proc_info:
        print("[PASS] 程序正在运行")
        print(f"  PID: {proc_info['pid']}")
        print(f"  内存: {proc_info['memory_mb']:.1f} MB")
        print(f"  CPU时间: {proc_info['cpu_seconds']:.1f}s")

        # 解析启动时间
        try:
            start_time = datetime.strptime(proc_info["start_time"].split(".")[0], "%Y-%m-%d %H:%M:%S")
            print(f"  启动时间: {proc_info['start_time']}")

            # 计算运行时间
            now = datetime.now()
            runtime = (now - start_time).total_seconds()
            print(f"  运行时长: {runtime:.0f} 秒 ({runtime / 60:.1f} 分钟)")
        except (ValueError, AttributeError):
            start_time = None
            print(f"  启动时间: {proc_info['start_time']}")
    else:
        print("[WARN] 未检测到Python进程")
        print("[INFO] 程序可能未启动或已退出")
        return

    print()

    # 检查最新错误
    print("=" * 80)
    print("  错误检查")
    print("=" * 80)
    print()

    if start_time:
        print(f"检查 {start_time.strftime('%Y-%m-%d %H:%M:%S')} 之后的错误...")
        errors = check_recent_errors(log_file, start_time)

        if errors:
            print(f"[WARN] 发现 {len(errors)} 个错误:")
            for error in errors[-5:]:
                print(f"  {error[:120]}")
        else:
            print("[PASS] 当前运行期间无错误!")
    else:
        print("[INFO] 无法确定启动时间,检查最近10分钟的错误")

    print()

    # 检查GPU
    print("=" * 80)
    print("  GPU状态")
    print("=" * 80)
    print()

    gpu_count = check_gpu_status()
    if gpu_count is not None:
        print(f"[PASS] 检测到 {gpu_count} 个GPU设备可用")
    else:
        print("[WARN] 无法检测GPU状态")

    print()

    # 持续监控
    print("=" * 80)
    print("  持续监控 (Ctrl+C停止)")
    print("=" * 80)
    print()

    print("每5秒刷新一次...")
    print()

    try:
        iteration = 0
        while True:
            time.sleep(5)
            iteration += 1

            # 获取最新的10行日志
            try:
                with open(log_file, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    recent = lines[-10:]

                print(f"--- 刷新 #{iteration} ({datetime.now().strftime('%H:%M:%S')}) ---")

                for line in recent:
                    line = line.strip()
                    if "ERROR" in line:
                        print(f"  [ERROR] {line[24:100]}")
                    elif "WARNING" in line or "WARN" in line:
                        print(f"  [WARN]  {line[24:100]}")
                    elif "INFO" in line and (
                        "吞吐量" in line or "throughput" in line.lower() or "keys/s" in line.lower()
                    ):
                        print(f"  [PERF]  {line[24:100]}")

                print()

            except Exception as e:
                print(f"[ERROR] 读取日志失败: {e}")

    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("  监控已停止")
        print("=" * 80)


if __name__ == "__main__":
    main()
