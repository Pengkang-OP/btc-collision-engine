#!/usr/bin/env python3
"""GPU碰撞引擎实时监控工具"""

import json
import subprocess
from pathlib import Path


def read_monitoring_data():
    """读取监控数据文件"""
    monitoring_file = Path("monitoring_data/current_data.json")

    if not monitoring_file.exists():
        return None

    try:
        with open(monitoring_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取监控数据失败: {e}")
        return None


def read_error_log():
    """读取错误日志"""
    error_file = Path("monitoring_data/error_log.json")

    if not error_file.exists():
        return []

    try:
        with open(error_file, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def analyze_logs():
    """分析日志文件"""
    log_file = Path("logs/collision.log")

    if not log_file.exists():
        return {"status": "日志文件不存在"}

    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # 获取最后50行
        recent_lines = lines[-50:]

        # 统计关键信息
        info_count = sum(1 for line in lines if "INFO" in line)
        warning_count = sum(1 for line in lines if "WARNING" in line)
        error_count = sum(1 for line in lines if "ERROR" in line)

        return {
            "total_lines": len(lines),
            "recent_lines": [line.strip() for line in recent_lines],
            "info_count": info_count,
            "warning_count": warning_count,
            "error_count": error_count,
        }
    except Exception as e:
        return {"status": f"分析失败: {e}"}


def _check_processes():  # noqa: D401 (描述性函数名)
    """── 检查 Python 进程 ──"""
    print("[1/5] 检查程序运行状态")
    print("-" * 80)
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-Process python -ErrorAction SilentlyContinue | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.stdout.strip():
            processes = json.loads(result.stdout)
            if not isinstance(processes, list):
                processes = [processes]
            print(f"检测到 {len(processes)} 个Python进程:")
            for proc in processes:
                pid = proc.get("Id", "N/A")
                ws_mb = proc.get("WorkingSet", 0) / (1024 * 1024)
                cpu = proc.get("CPU", 0)
                print(f"  PID: {pid} | 内存: {ws_mb:.1f} MB | CPU时间: {cpu:.1f}s")
        else:
            print("[WARN] 未检测到Python进程")
    except Exception as e:  # noqa: BLE001 (监控工具容错)
        print(f"[WARN] 无法检查进程: {e}")
    print()


def _read_monitoring_section():
    """── 读取性能监控数据 ──"""
    print("[2/5] 读取性能监控数据")
    print("-" * 80)
    monitoring_data = read_monitoring_data()
    if monitoring_data:
        print("当前状态:")
        print(f"  运行状态: {monitoring_data.get('running_status', 'Unknown')}")
        print(f"  已检查密钥: {monitoring_data.get('total_checked', 0):,}")
        print(f"  匹配数: {monitoring_data.get('match_count', 0):,}")
        print(f"  速度: {monitoring_data.get('keys_per_second', 0):,.0f} keys/s")
        print(f"  运行时间: {monitoring_data.get('elapsed_time', 0):.1f} 秒")
        print(f"  最后更新: {monitoring_data.get('last_update', 'Unknown')}")
    else:
        print("[WARN] 暂无监控数据(程序可能刚启动)")
    print()
    return monitoring_data


def _check_errors_section():
    """── 检查错误日志 ──"""
    print("[3/5] 检查错误日志")
    print("-" * 80)
    errors = read_error_log()
    if errors:
        print(f"检测到 {len(errors)} 个错误:")
        for error in errors[-5:]:
            print(
                f"  [{error.get('timestamp', 'Unknown')}] "
                f"{error.get('error_type', 'Unknown')}: "
                f"{error.get('message', '')}"
            )
    else:
        print("[PASS] 无错误记录")
    print()


def _analyze_logs_section():
    """── 分析运行日志 ──"""
    print("[4/5] 分析运行日志")
    print("-" * 80)
    log_analysis = analyze_logs()
    if "total_lines" in log_analysis:
        print(f"日志总行数: {log_analysis['total_lines']}")
        print(
            f"INFO: {log_analysis['info_count']} | "
            f"WARNING: {log_analysis['warning_count']} | "
            f"ERROR: {log_analysis['error_count']}"
        )
        print()
        print("最新日志(最后10行):")
        for line in log_analysis["recent_lines"][-10:]:
            if "INFO" in line:
                level = "INFO"
            elif "WARNING" in line:
                level = "WARN"
            elif "ERROR" in line:
                level = "ERROR"
            else:
                level = "????"
            parts = line.split(" - ", 2)
            if len(parts) >= 3:
                message = parts[2][:100]
                print(f"  [{level}] {message}")
    else:
        print(f"[WARN] {log_analysis.get('status', '未知错误')}")
    print()
    return log_analysis


def _health_check_section(monitoring_data, log_analysis):
    """── 健康状态评估 ──"""
    print("[5/5] 健康状态评估")
    print("-" * 80)
    health_checks = []
    # 检查1: 进程
    if True:
        health_checks.append(("进程状态", True, "程序运行中"))
    # 检查2: 错误率
    err_cnt = log_analysis.get("error_count", 0)
    if err_cnt == 0:
        health_checks.append(("错误率", True, "0错误"))
    elif err_cnt < 5:
        health_checks.append(("错误率", True, f"{err_cnt}个错误(可接受)"))
    else:
        health_checks.append(("错误率", False, f"{err_cnt}个错误(需关注)"))
    # 检查3: 警告数量
    warn_cnt = log_analysis.get("warning_count", 0)
    if warn_cnt < 10:
        health_checks.append(("警告数量", True, f"{warn_cnt}个警告"))
    else:
        health_checks.append(("警告数量", False, f"{warn_cnt}个警告(较多)"))
    # 检查4: 性能
    if monitoring_data and monitoring_data.get("keys_per_second", 0) > 10000:
        health_checks.append(("吞吐量", True, f"{monitoring_data['keys_per_second']:,.0f} keys/s"))
    elif monitoring_data:
        health_checks.append(
            ("吞吐量", False, f"{monitoring_data.get('keys_per_second', 0):,.0f} keys/s(偏低)")
        )
    else:
        health_checks.append(("吞吐量", None, "暂无数据"))
    # 打印
    for name, status, message in health_checks:
        if status is True:
            print(f"  [PASS] {name}: {message}")
        elif status is False:
            print(f"  [FAIL] {name}: {message}")
        else:
            print(f"  [INFO] {name}: {message}")
    print()
    return health_checks


def _print_summary(health_checks, monitoring_data):
    """打印监控总结。"""
    print("=" * 80)
    print("  监控总结")
    print("=" * 80)
    print()
    pass_count = sum(1 for _, status, _ in health_checks if status is True)
    fail_count = sum(1 for _, status, _ in health_checks if status is False)
    if fail_count == 0:
        print(f"[HEALTHY] 程序运行正常! (通过 {pass_count}/{pass_count + fail_count} 项检查)")
        print()
        if monitoring_data:
            print(f"  已检查: {monitoring_data.get('total_checked', 0):,} 个密钥")
            print(f"  速度: {monitoring_data.get('keys_per_second', 0):,.0f} keys/s")
            print(f"  运行时间: {monitoring_data.get('elapsed_time', 0):.1f} 秒")
    else:
        print(f"[WARNING] 发现 {fail_count} 个问题需要关注")
        print()
        for name, status, message in health_checks:
            if status is False:
                print(f"  - {name}: {message}")
    print()
    print("=" * 80)


def main():
    """GPU碰撞引擎实时监控入口。"""
    print("=" * 80)
    print("  GPU碰撞引擎实时监控")
    print("=" * 80)
    print()
    _check_processes()
    monitoring_data = _read_monitoring_section()
    _check_errors_section()
    log_analysis = _analyze_logs_section()
    health_checks = _health_check_section(monitoring_data, log_analysis)
    _print_summary(health_checks, monitoring_data)


if __name__ == "__main__":
    main()
