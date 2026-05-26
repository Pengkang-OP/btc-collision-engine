#!/usr/bin/env python3
"""BTC 碰撞引擎 — 模拟运行 + 实时监测

在可控时长内启动引擎（默认 CPU 随机模式），并轮询 data_logs/current_data.json
输出吞吐量、引擎状态与系统指标。

用法:
    python scripts/benchmarking/simulate_run_monitor.py
    python scripts/benchmarking/simulate_run_monitor.py --duration 30
    python scripts/benchmarking/simulate_run_monitor.py --use-gpu --duration 60
    python scripts/benchmarking/simulate_run_monitor.py --monitor-only   # 仅读取已有监控数据
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_ENTRY = PROJECT_ROOT / "key_collision_cli.py"
DATA_FILE = PROJECT_ROOT / "data_logs" / "current_data.json"
LOG_FILE = PROJECT_ROOT / "logs" / "collision.log"
DEFAULT_TARGET = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


def _load_metrics() -> dict[str, Any] | None:
    if not DATA_FILE.exists():
        return None
    try:
        with DATA_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[WARN] 无法读取 {DATA_FILE}: {e}")
        return None


def _extract_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """从 data_logs/current_data.json 提取可读的监测快照。"""
    perf = data.get("performance") or {}
    engine = data.get("engine") or {}
    system = data.get("system") or {}

    speed = perf.get("speed") or perf.get("keys_per_second") or 0
    total = perf.get("total_checked") or data.get("total_checked") or 0
    matches = perf.get("matches_found") or data.get("match_count") or 0

    return {
        "saved_at": data.get("saved_at", perf.get("datetime", "—")),
        "uptime": data.get("uptime", perf.get("elapsed_time", 0)),
        "speed": float(speed),
        "total_checked": int(total),
        "matches": int(matches),
        "mode": engine.get("mode", "—"),
        "is_running": engine.get("is_running", data.get("running_status")),
        "target_count": engine.get("target_count", 0),
        "cpu_usage": perf.get("cpu_usage"),
        "memory_usage": perf.get("memory_usage"),
        "gpu_utilization": perf.get("gpu_utilization"),
        "pid": system.get("pid"),
    }


def print_snapshot(snap: dict[str, Any], label: str = "") -> None:
    prefix = f"[{label}] " if label else ""
    running = snap.get("is_running")
    run_txt = "运行中" if running is True else ("已停止" if running is False else "未知")
    print(
        f"{prefix}"
        f"状态={run_txt} | 模式={snap.get('mode')} | "
        f"已检={snap.get('total_checked'):,} | "
        f"速度={snap.get('speed'):,.1f} keys/s | "
        f"匹配={snap.get('matches')} | "
        f"运行={float(snap.get('uptime') or 0):.1f}s"
    )
    if snap.get("cpu_usage") is not None:
        print(
            f"      CPU={snap.get('cpu_usage'):.1f}% "
            f"MEM={snap.get('memory_usage') or 0:.1f}% "
            f"GPU={snap.get('gpu_utilization') or 0:.1f}% "
            f"PID={snap.get('pid', '—')}"
        )


def poll_while_running(
    proc: subprocess.Popen[str],
    interval: float,
    stop_when_done: bool = True,
) -> list[dict[str, Any]]:
    """在子进程运行期间轮询监控文件。"""
    history: list[dict[str, Any]] = []
    print("\n── 实时监测 (data_logs/current_data.json) ──")
    while True:
        if stop_when_done and proc.poll() is not None:
            break
        data = _load_metrics()
        if data:
            snap = _extract_snapshot(data)
            history.append(snap)
            ts = datetime.now().strftime("%H:%M:%S")
            print_snapshot(snap, label=ts)
        else:
            print(f"[{datetime.now():%H:%M:%S}] 等待监控数据写入…")
        if proc.poll() is not None:
            break
        time.sleep(interval)
    return history


def run_engine(
    duration: int,
    use_gpu: bool,
    target: str,
    quiet: bool,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(CLI_ENTRY),
        "-t",
        target,
        "-m",
        "random",
        "--duration",
        str(duration),
        "--no-color",
        "--skip-security-check",
    ]
    if use_gpu:
        cmd.append("--use-gpu")
    if quiet:
        cmd.append("-q")

    print("── 模拟运行 ──")
    print(f"命令: {' '.join(cmd)}")
    print(f"目标: {target} | 时长: {duration}s | GPU: {'是' if use_gpu else '否'}")
    print()

    return subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=not quiet,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def print_final_report(result: subprocess.CompletedProcess[str] | None) -> None:
    print("\n── 最终监测报告 ──")
    data = _load_metrics()
    if data:
        snap = _extract_snapshot(data)
        print_snapshot(snap, label="最终")
    else:
        print("[WARN] 未找到 data_logs/current_data.json")

    if LOG_FILE.exists():
        try:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
            err = sum(1 for ln in lines if " ERROR " in ln or "ERROR -" in ln)
            warn = sum(1 for ln in lines if " WARNING " in ln or "WARNING -" in ln)
            print(f"日志 {LOG_FILE.name}: 共 {len(lines)} 行 | ERROR={err} | WARNING={warn}")
            if lines:
                print("最近 3 行:")
                for ln in lines[-3:]:
                    print(f"  {ln[:120]}")
        except OSError as e:
            print(f"[WARN] 读取日志失败: {e}")

    if result is not None:
        status = "成功" if result.returncode == 0 else f"退出码 {result.returncode}"
        print(f"\n引擎进程: {status}")
        if result.stdout and result.stdout.strip():
            tail = result.stdout.strip().splitlines()[-8:]
            print("CLI 输出末尾:")
            for ln in tail:
                print(f"  {ln}")


def monitor_only(interval: float, count: int) -> None:
    print("── 仅监测模式 (不启动引擎) ──")
    for i in range(count):
        data = _load_metrics()
        if data:
            print_snapshot(_extract_snapshot(data), label=f"#{i + 1}")
        else:
            print(f"[#{i + 1}] 无监控数据")
        if i < count - 1:
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="BTC 碰撞引擎模拟运行与实时监测")
    parser.add_argument(
        "--duration",
        type=int,
        default=20,
        help="运行秒数 (默认 20)",
    )
    parser.add_argument("--use-gpu", action="store_true", help="启用 GPU（需 pyopencl）")
    parser.add_argument("-t", "--target", default=DEFAULT_TARGET, help="目标地址")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="监测轮询间隔秒 (默认 2)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="静默 CLI，仅显示监测")
    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="不启动引擎，仅轮询现有 data_logs",
    )
    parser.add_argument(
        "--monitor-count",
        type=int,
        default=5,
        help="--monitor-only 时轮询次数 (默认 5)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  BTC 碰撞引擎 — 模拟运行 + 监测")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"监控文件  : {DATA_FILE}")
    print()

    if args.monitor_only:
        monitor_only(args.poll_interval, args.monitor_count)
        return 0

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(CLI_ENTRY),
        "-t",
        args.target,
        "-m",
        "random",
        "--duration",
        str(args.duration),
        "--no-color",
        "--skip-security-check",
    ]
    if args.use_gpu:
        cmd.append("--use-gpu")
    if args.quiet:
        cmd.append("-q")

    print("── 模拟运行 ──")
    print(f"命令: {' '.join(cmd)}")
    print()

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE if args.quiet else None,
        stderr=subprocess.PIPE if args.quiet else None,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    poll_while_running(proc, args.poll_interval)

    stdout, stderr = "", ""
    if args.quiet and proc.stdout and proc.stderr:
        stdout, stderr = proc.communicate()
    else:
        proc.wait()

    result = subprocess.CompletedProcess(
        cmd,
        proc.returncode or 0,
        stdout,
        stderr,
    )
    print_final_report(result)
    print("=" * 60)
    return 0 if (proc.returncode or 0) == 0 else proc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
