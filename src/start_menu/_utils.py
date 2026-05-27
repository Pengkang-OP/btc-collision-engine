"""启动菜单工具函数 — 清屏、等待按键、终端宽度、GPU 检测、统计收集."""

from typing import Any

import concurrent.futures
import os
import platform
from pathlib import Path

from ._shared import (
    _has_rich,
    _PROJECT_ROOT,
    _console,
)


def _clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[H\033[J", end="")


def _wait_key() -> None:
    if os.name == "nt":
        os.system("pause >nul")
    else:
        input("")


def _term_width() -> int:
    if _has_rich and _console is not None:
        w = _console.width
        return max(52, min(w - 4, 100))
    return 62


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _detect_gpu_quick() -> str | None:
    def _probe():
        try:
            from src.gpu.device import GPUDeviceDetector

            devs = GPUDeviceDetector.detect_devices()
            if devs:
                names = [d.get("name", "GPU") for d in devs[:3]]
                mems = []
                for d in devs[:3]:
                    m = d.get("global_mem_size", 0)
                    if m:
                        gb = m / (1024**3)
                        mems.append(f"{gb:.0f}G" if gb >= 1 else f"{m / (1024**2):.0f}M")
                parts = []
                for i, n in enumerate(names):
                    s = n
                    if i < len(mems):
                        s += f" ({mems[i]})"
                    parts.append(s)
                label = ", ".join(parts)
                if len(devs) > 3:
                    label += f" +{len(devs) - 3}"
                return label
        except Exception:
            pass
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_probe)
            return fut.result(timeout=2.0)
    except concurrent.futures.TimeoutError:
        return None


def _collect_dynamic_stats() -> dict[str, Any]:
    stats: dict[str, Any] = {}
    targets_file = os.path.join(_PROJECT_ROOT, "targets.txt")
    alt_targets = os.path.join(_PROJECT_ROOT, "btc_addresses_sorted.txt")
    tf = (
        targets_file
        if os.path.isfile(targets_file)
        else (alt_targets if os.path.isfile(alt_targets) else None)
    )
    if tf:
        try:
            size = os.path.getsize(tf)
            stats["target_file"] = os.path.basename(tf)
            stats["target_size"] = _format_size(size)
            count = 0
            enc = "utf-8-sig"
            try:
                with open(tf, encoding=enc, errors="ignore") as f:
                    for line in f:
                        s = line.strip()
                        if s and not s.startswith("#"):
                            count += 1
                            if count >= 100000:
                                break
            except Exception:
                pass
            stats["target_count"] = f"{count:,}" if count < 100000 else f"{count:,}+"
        except OSError:
            pass
    log_dir = os.path.join(_PROJECT_ROOT, "logs")
    if os.path.isdir(log_dir):
        try:
            log_files = sum(1 for _ in Path(log_dir).rglob("*.log") if _.is_file())
            if log_files > 0:
                stats["log_files"] = str(log_files)
        except OSError:
            pass
    stats["python"] = f"{platform.python_version()} ({platform.machine()})"
    try:
        gpu_info = _detect_gpu_quick()
        if gpu_info:
            stats["gpu"] = gpu_info
    except Exception:
        pass
    return stats
