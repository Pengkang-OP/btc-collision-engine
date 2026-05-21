#!/usr/bin/env python3
"""
CLI进度格式化模块

包含:
- format_progress: 格式化进度信息（带可视化进度条）
"""

import logging
import time

from src.cli.constants import (
    ETA_HOUR_THRESHOLD,
    ETA_MINUTE_THRESHOLD,
    INIT_CHECK_THRESHOLD,
    PROGRESS_BAR_EMPTY,
    PROGRESS_BAR_FILLED,
    PROGRESS_BAR_LENGTH,
    UNIT_BILLION,
    UNIT_MILLION,
    UNIT_THOUSAND,
)
from src.collision import CollisionStats


def _format_checked_count(checked: int) -> str:
    """将已检查数格式化为缩写形式"""
    assert checked >= 0, f"checked 不能为负数: {checked}"
    if checked >= UNIT_BILLION:
        return f"{checked / UNIT_BILLION:.2f}B"
    elif checked >= UNIT_MILLION:
        return f"{checked / UNIT_MILLION:.2f}M"
    elif checked >= UNIT_THOUSAND:
        return f"{checked / UNIT_THOUSAND:.1f}K"
    else:
        return str(checked)


def _format_total_count(total: int) -> str:
    """将总范围数格式化为缩写形式"""
    if total >= UNIT_BILLION:
        return f"{total / UNIT_BILLION:.2f}B"
    elif total >= UNIT_MILLION:
        return f"{total / UNIT_MILLION:.2f}M"
    else:
        return f"{total:,}"


def _compute_eta(elapsed_sec: float, checked: int, total_range: int | None) -> str:
    """计算预计剩余时间"""
    if total_range is None or total_range <= 0 or checked <= 0:
        return "--"
    if elapsed_sec > 0:
        speed = checked / elapsed_sec
        remaining = total_range - checked
        if speed > 0 and remaining > 0:
            eta_sec = remaining / speed
            if eta_sec < ETA_MINUTE_THRESHOLD:
                return f"{eta_sec:.0f}s"
            elif eta_sec < ETA_HOUR_THRESHOLD:
                return f"{eta_sec / 60:.1f}m"
            else:
                return f"{eta_sec / 3600:.1f}h"
        elif remaining <= 0:
            return "[Done] 完成"
    return "--"


def _format_progress_bar(pct: float) -> str:
    """渲染Unicode进度条"""
    filled = int(PROGRESS_BAR_LENGTH * pct / 100)
    bar = PROGRESS_BAR_FILLED * filled + PROGRESS_BAR_EMPTY * (PROGRESS_BAR_LENGTH - filled)
    return f" {bar} {pct:5.1f}%"


# 有效的引擎类型白名单
VALID_ENGINE_TYPES = {"cpu", "gpu", "multi-gpu"}


def format_progress(
    stats: CollisionStats, mode: str, total_range: int | None = None, engine_type: str = "cpu"
) -> str:
    """格式化进度信息（带可视化进度条）

    Args:
        stats: 碰撞统计数据
        mode: 碰撞模式
        total_range: 总范围
        engine_type: 引擎类型 ('cpu', 'gpu', 'multi-gpu')
    """
    # 验证引擎类型，无效时降级为默认值
    if engine_type not in VALID_ENGINE_TYPES:
        logging.getLogger("CLI").warning("无效的 engine_type '%s'，已降级为 'cpu'", engine_type)
        engine_type = "cpu"

    elapsed = stats.format_elapsed()
    checked = stats.total_checked
    speed_str = stats.format_speed()
    matches = len(stats.matches)

    # 引擎初始化期间，显示友好提示
    elapsed_sec = (
        stats.elapsed
        if stats.elapsed > 0
        else (time.time() - stats.start_time if stats.start_time > 0 else 0)
    )
    if checked == 0 and elapsed_sec < INIT_CHECK_THRESHOLD:
        engine_tag = f"[{engine_type.upper()}]"
        return f"[{elapsed}] {engine_tag} [Initializing] 初始化中... | 速度: -- | 匹配: {matches} | ETA: --"

    # 计算进度百分比
    pct = min(100.0, checked / total_range * 100) if total_range and total_range > 0 else 0.0

    # 计算 ETA
    eta_str = _compute_eta(elapsed_sec, checked, total_range)

    # 生成可视化进度条
    pct_str = _format_progress_bar(pct) if total_range and total_range > 0 else ""

    # 格式化已检查数量
    checked_str = _format_checked_count(checked)

    # 总范围显示
    if total_range and total_range > 0:
        total_str = _format_total_count(total_range)
        range_info = f" | {checked_str}/{total_str}"
    else:
        range_info = f" | {checked_str}"

    # 引擎类型标签
    engine_tag = f"[{engine_type.upper()}]"

    _range = f" {range_info}" if range_info else ""
    _m = matches if matches else "0"
    return f"[{elapsed}] {engine_tag}{pct_str}{_range} | {speed_str} | ETA:{eta_str} | 匹配:{_m}"
