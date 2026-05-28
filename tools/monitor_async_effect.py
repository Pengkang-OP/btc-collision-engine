#!/usr/bin/env python3
"""监控GPU异步优化重启效果."""

import sys
import time
from datetime import datetime
from pathlib import Path


def check_async_enabled():
    """检查异步是否启用."""
    log_file = Path("logs/collision.log")

    if not log_file.exists():
        return False, "日志文件不存在"

    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # 查找最近的启动记录(最后200行)
        recent_lines = lines[-200:]
        recent_content = "".join(recent_lines)

        # 检查异步相关日志
        checks = {
            "异步配置": "GPU异步执行已启用" in recent_content,
            "双队列": "创建双队列" in recent_content,
            "异步执行器": "异步执行器已初始化" in recent_content,
            "异步模式": "使用GPU异步执行模式" in recent_content,
        }

        all_enabled = all(checks.values())

        return all_enabled, checks

    except Exception as e:
        return False, f"检查失败: {e}"


def get_recent_performance():
    """获取最近的性能数据."""
    log_file = Path("logs/collision.log")

    if not log_file.exists():
        return None

    try:
        import re

        with open(log_file, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # 查找最近的启动时间
        start_matches = list(
            re.finditer(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*?GPU引擎初始化成功", content),
        )

        if not start_matches:
            return None

        # 获取最后一次启动
        last_start = start_matches[-1]
        start_time_str = last_start.group(1)
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S,%f")

        # 计算运行时长
        now = datetime.now()
        runtime = (now - start_time).total_seconds()

        # 查找错误
        after_start = content[last_start.start() :]
        error_count = after_start.count("ERROR")
        warning_count = after_start.count("WARNING")

        return {
            "start_time": start_time,
            "runtime_seconds": runtime,
            "error_count": error_count,
            "warning_count": warning_count,
        }

    except Exception:
        return None


def monitor_async_stats():
    """持续监控异步执行统计."""
    print("=" * 80)
    print("  GPU异步优化效果监控")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # 1. 检查异步启用状态
    print("[1/4] 检查异步启用状态")
    print("-" * 80)

    enabled, result = check_async_enabled()

    if isinstance(result, dict):
        for check_name, status in result.items():
            if status:
                print(f"  [PASS] {check_name}")
            else:
                print(f"  [FAIL] {check_name}")

        if enabled:
            print("\n  [SUCCESS] 异步优化已完全启用!")
        else:
            print("\n  [WARN] 异步优化未完全启用")
    else:
        print(f"  [ERROR] {result}")

    print()

    # 2. 检查运行状态
    print("[2/4] 检查运行状态")
    print("-" * 80)

    perf_data = get_recent_performance()

    if perf_data:
        runtime = perf_data["runtime_seconds"]
        print(f"  启动时间: {perf_data['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  运行时长: {runtime:.0f} 秒 ({runtime / 60:.1f} 分钟)")
        print(f"  错误数量: {perf_data['error_count']}")
        print(f"  警告数量: {perf_data['warning_count']}")

        if perf_data["error_count"] == 0:
            print("  错误状态: [PASS] 无错误")
        else:
            print(f"  错误状态: [WARN] 发现{perf_data['error_count']}个错误")
    else:
        print("  [WARN] 未检测到新的运行记录")
        print("  [INFO] 请确认已重启程序")

    print()

    # 3. 检查日志关键字
    print("[3/4] 检查关键日志")
    print("-" * 80)

    log_file = Path("logs/collision.log")
    if log_file.exists():
        try:
            with open(log_file, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            recent = lines[-50:]

            # 查找关键信息
            keywords = {
                "Intel Arc": False,
                "batch_size": False,
                "双缓冲": False,
                "异步": False,
                "吞吐量": False,
            }

            for line in recent:
                for keyword in keywords:
                    if keyword in line:
                        keywords[keyword] = True

            for keyword, found in keywords.items():
                if found:
                    print(f"  [PASS] 日志包含: {keyword}")
                else:
                    print(f"  [INFO] 日志未包含: {keyword}")

        except Exception as e:
            print(f"  [ERROR] 读取日志失败: {e}")
    else:
        print("  [ERROR] 日志文件不存在")

    print()

    # 4. 健康评估
    print("[4/4] 健康评估")
    print("-" * 80)

    health_score = 100

    if enabled:
        print("  [+0] 异步已启用")
    else:
        health_score -= 30
        print("  [-30] 异步未启用")

    if perf_data and perf_data["error_count"] == 0:
        print("  [+0] 无错误")
    else:
        health_score -= 20
        print("  [-20] 存在错误")

    if perf_data and perf_data["runtime_seconds"] > 60:
        print("  [+0] 运行稳定(>1分钟)")
    elif perf_data:
        health_score -= 10
        print("  [-10] 运行时间短(<1分钟)")
    else:
        health_score -= 40
        print("  [-40] 未检测到运行")

    print()
    print(f"  健康评分: {health_score}/100")

    if health_score >= 80:
        print("  状态: [HEALTHY] 异步优化运行正常!")
    elif health_score >= 60:
        print("  状态: [WARNING] 需要关注")
    else:
        print("  状态: [ERROR] 存在问题")

    print()
    print("=" * 80)

    return health_score


def continuous_monitor(interval=10):
    """持续监控."""
    print("启动持续监控模式...")
    print(f"每{interval}秒刷新一次")
    print("按 Ctrl+C 停止")
    print()

    try:
        iteration = 0
        while True:
            iteration += 1
            health = monitor_async_stats()

            if health >= 80:
                print("OK 异步优化运行正常,继续监控...")
            else:
                print("WARN 检测到问题,请检查日志")

            print()
            time.sleep(interval)

    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("  监控已停止")
        print("=" * 80)


def main():
    """主函数."""
    if "--continuous" in sys.argv or "-c" in sys.argv:
        # 持续监控模式
        continuous_monitor()
    else:
        # 单次检查模式
        monitor_async_stats()


if __name__ == "__main__":
    main()
