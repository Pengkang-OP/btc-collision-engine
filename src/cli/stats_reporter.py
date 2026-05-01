#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计信息格式化与输出模块

提供碰撞引擎运行期间和结束后的统计数据格式化、显示功能。
"""

import argparse
import os
import sys
from typing import Any, Optional

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.i18n import _t
from src.cli.advanced_features import export_progress_data, export_matches
from src.cli.constants import SEPARATOR_EQUAL, SEPARATOR_DASHED
from src.cli.output import CLIOutput


def _print_detailed_stats(stats: Any) -> None:
    """按 S 键时显示详细统计信息。"""
    output = CLIOutput.get_instance()
    rows = []
    try:
        checked = getattr(stats, "total_checked", 0)
        matches_val = (
            len(stats.matches) if hasattr(stats, "matches") else getattr(stats, "matches", 0)
        )
        elapsed_str = (
            stats.format_elapsed()
            if hasattr(stats, "format_elapsed")
            else str(getattr(stats, "elapsed", "--"))
        )
        speed_str = stats.format_speed() if hasattr(stats, "format_speed") else "--"
        rows.append(("已检查", f"{checked:,}"))
        rows.append(("运行时间", elapsed_str))
        rows.append(("平均速度", speed_str))
        rows.append(("发现匹配", str(matches_val)))
        gpu_info = getattr(stats, "gpu_info", None)
        if gpu_info:
            rows.append(("GPU设备", str(gpu_info)))
    except Exception:
        rows.append(("状态", "统计信息暂不可用"))
    output.stats_panel("详细统计", rows)


def _print_final_summary(engine: Any, engine_type: str, args: argparse.Namespace) -> None:
    """打印最终统计报告（使用 Rich Panel + Table）。"""
    output = CLIOutput.get_instance()
    stats_dict: dict = {}

    if engine_type == "multi_gpu":
        combined = engine.get_combined_stats()
        elapsed_sec = combined.get("elapsed_time", 0)
        total_checked = combined.get("total_keys_checked", 0)
        throughput = combined.get("combined_throughput", 0)
        matches_count = combined.get("total_matches", 0)
        device_count = combined.get("device_count", 0)
        h, rem = divmod(int(elapsed_sec), 3600)
        m_t, s = divmod(rem, 60)
        elapsed_fmt = f"{h:02d}:{m_t:02d}:{s:02d}"
        speed_fmt = (
            f"{throughput/1_000_000:.2f}M/s"
            if throughput >= 1_000_000
            else f"{throughput/1_000:.1f}K/s" if throughput >= 1_000 else f"{throughput:.0f}/s"
        )
        stats_dict[_t("cli.main.accel_mode")] = f"多GPU ({device_count} 个设备)"
        stats_dict[_t("cli.main.total_checked")] = f"{total_checked:,}"
        stats_dict[_t("cli.main.elapsed_time")] = elapsed_fmt
        stats_dict[_t("cli.main.avg_speed")] = speed_fmt
        stats_dict[_t("cli.main.matches_found")] = f"{matches_count} 个"

        per_device = combined.get("per_device", {})
        if per_device:
            for dev_idx, dev_stats in sorted(per_device.items()):
                dev_keys = dev_stats.get("keys_checked", 0)
                dev_tp = dev_stats.get("throughput", 0)
                dev_speed_fmt = (
                    f"{dev_tp/1_000_000:.2f}M/s"
                    if dev_tp >= 1_000_000
                    else f"{dev_tp/1_000:.1f}K/s" if dev_tp >= 1_000 else f"{dev_tp:.0f}/s"
                )
                stats_dict[f"GPU {dev_idx}"] = (
                    _t("cli.main.gpu_checked", count=dev_keys)
                    + f" | "
                    + _t("cli.main.gpu_speed", speed=dev_speed_fmt)
                )
        engine.cleanup()
    else:
        stats = engine.get_stats()
        mode_label = _t("collision.mode.gpu") if engine_type == "gpu" else _t("collision.mode.cpu")
        stats_dict[_t("cli.main.accel_mode")] = mode_label
        stats_dict[_t("cli.main.total_checked")] = f"{stats.total_checked:,}"
        stats_dict[_t("cli.main.elapsed_time")] = stats.format_elapsed()
        stats_dict[_t("cli.main.avg_speed")] = stats.format_speed()
        stats_dict[_t("cli.main.matches_found")] = f"{len(stats.matches)} 个"
        if stats.matches:
            # 导入分页功能
            from src.cli.pagination import display_paginated_results

            display_paginated_results(stats.matches, "匹配结果")

    output.final_summary(_t("cli.main.final_summary"), stats_dict)

    # 导出数据（如果指定了导出路径）
    export_progress_file = getattr(args, "export_progress", None)
    if export_progress_file:
        try:
            stats = engine.get_stats() if hasattr(engine, "get_stats") else {}
            # 修正: 参数顺序 mode, engine_type (之前 engine_type 被错误传给 mode)
            mode = getattr(args, "mode", "unknown")
            export_progress_data(stats, mode, engine_type, export_progress_file)
            print(_t("export.completed", path=export_progress_file))
        except Exception as e:
            print(_t("export.failed", error=str(e)))

    export_matches_file = getattr(args, "export_matches", None)
    if export_matches_file:
        try:
            stats = engine.get_stats() if hasattr(engine, "get_stats") else {}
            matches = stats.get("matches", []) if isinstance(stats, dict) else []
            export_matches(matches, export_matches_file)
            print(_t("export.completed", path=export_matches_file))
        except Exception as e:
            print(_t("export.failed", error=str(e)))
