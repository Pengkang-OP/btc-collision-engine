#!/usr/bin/env python3
"""
CLI参数验证模块

包含:
- validate_args: 验证命令行参数合法性
- validate_file_path: 验证文件路径有效性
"""

import argparse
import logging
import os

from src.cli.constants import (
    DEFAULT_CHECKPOINT_INTERVAL,
    DEFAULT_DEDUP_MAX_SIZE,
)
from src.i18n import _t

# 运行时长上限阈值（7天，超过给出警告）
_DURATION_WARN_THRESHOLD = 604800
# checkpoint-interval 合法范围
_CHECKPOINT_INTERVAL_MIN = 5
_CHECKPOINT_INTERVAL_MAX = 3600
# 文件大小警告阈值（100 MB）
_FILE_SIZE_WARN_BYTES = 100 * 1024 * 1024


def validate_args(args: argparse.Namespace) -> bool:
    """验证参数合法性，返回 True 表示合法"""
    output = _get_output()

    # 如果没有 -t/-f，且不是实用工具命令，则报错
    is_util_cmd = (
        getattr(args, "health_check", False)
        or getattr(args, "platform_check", False)
        or getattr(args, "cleanup", False)
        or getattr(args, "validate_addresses", None) is not None
        or getattr(args, "examples", False)
        or getattr(args, "config_check", False)
        or getattr(args, "quick_start", False)
    )
    if not is_util_cmd and not args.targets and not args.file:
        output.error(_t("cli.validation.need_target"))
        output.print("  提示: 使用 -t <地址> 指定目标，或 --quick-start 启动引导")
        return False

    # -f 文件路径验证
    if args.file and not validate_file_path(args.file):
        return False

    if args.mode in ("range", "brute_force"):
        if args.start is None:
            output.error(_t("cli.validation.start_required", mode=args.mode))
            output.print("  提示: 添加 --start <十六进制私钥>，例如 --start 1")
            return False
        try:
            int(args.start, 16)
        except ValueError:
            output.error(_t("cli.validation.start_invalid", value=args.start))
            output.print("  提示: --start 必须为十六进制数字，例如 --start 1A2B3C")
            return False

    if args.mode == "range":
        if args.end is None:
            output.error(_t("cli.validation.end_required"))
            output.print("  提示: 添加 --end <十六进制私钥>，例如 --end FFFFFFFF")
            return False
        try:
            int(args.end, 16)
        except ValueError:
            output.error(_t("cli.validation.end_invalid", value=args.end))
            output.print("  提示: --end 必须为十六进制数字，例如 --end FFFFFFFF")
            return False

        start_val = int(args.start, 16)
        end_val = int(args.end, 16)
        if start_val >= end_val:
            output.error(_t("cli.validation.range_order", start=args.start, end=args.end))
            output.print("  提示: --start 值必须小于 --end 值")
            return False
        if start_val < 1:
            output.error(_t("cli.validation.start_min"))
            output.print("  提示: --start 最小值为 1 (0x1)")
            return False

        # 范围过大警告（2^64约需数百年才能穷举）
        # 使用安全计算避免溢出
        if end_val > (2**64) + start_val:
            total_range = end_val - start_val + 1
            hours = total_range / 1e9 / 3600  # 假设 1B keys/sec
            output.warning(_t("cli.validation.range_too_large", total=f"{total_range:,}"))
            output.warning(f"  预计耗时约 {hours:,.0f} 小时，建议缩小扫描范围")

    # --duration 超过 7 天给出警告（不阻止运行）
    duration = getattr(args, "duration", 0)
    if duration > _DURATION_WARN_THRESHOLD:
        days = duration / 86400
        output.warning(f"--duration {duration} 超过 7 天（{days:.1f} 天），程序将持续运行")

    # --checkpoint-interval 范围检查
    checkpoint_interval = getattr(args, "checkpoint_interval", DEFAULT_CHECKPOINT_INTERVAL)
    if (
        checkpoint_interval < _CHECKPOINT_INTERVAL_MIN
        or checkpoint_interval > _CHECKPOINT_INTERVAL_MAX
    ):
        output.error(f"--checkpoint-interval {checkpoint_interval} 超出合法范围")
        output.print(f"  提示: 有效范围为 {_CHECKPOINT_INTERVAL_MIN}-{_CHECKPOINT_INTERVAL_MAX} 秒")
        return False

    # GPU模式下CPU专用参数警告
    # 注意: --use-gpu 与 --multi-gpu 互斥性已由 argparse 的 mutually_exclusive_group 自动处理
    is_gpu_mode = getattr(args, "use_gpu", False) or getattr(args, "multi_gpu", False)
    if is_gpu_mode:
        cpu_only_warnings = []
        if getattr(args, "no_optimize", False):
            cpu_only_warnings.append("--no-optimize")
        if getattr(args, "window_size", 8) != 8:
            cpu_only_warnings.append(f"--window-size {args.window_size}")
        if getattr(args, "no_simd", False):
            cpu_only_warnings.append("--no-simd")
        if getattr(args, "no_memory_pool", False):
            cpu_only_warnings.append("--no-memory-pool")

        if cpu_only_warnings:
            logger = logging.getLogger(__name__)
            params_str = ", ".join(cpu_only_warnings)
            logger.warning(
                f"GPU mode active: the following CPU-only parameters will be ignored: {params_str}"
            )

    # checkpoint-interval 依赖性检查（自动启用 --checkpoint）
    if checkpoint_interval != DEFAULT_CHECKPOINT_INTERVAL and not getattr(
        args, "checkpoint", False
    ):
        output.print("  提示: 已自动启用 --checkpoint（因为指定了 --checkpoint-interval）")
        args.checkpoint = True

    # dedup-max-size 依赖性检查（自动启用 --dedup）
    if getattr(
        args, "dedup_max_size", DEFAULT_DEDUP_MAX_SIZE
    ) != DEFAULT_DEDUP_MAX_SIZE and not getattr(args, "dedup", False):
        output.print("  提示: 已自动启用 --dedup（因为指定了 --dedup-max-size）")
        args.dedup = True

    # window-size 范围验证
    window_size = getattr(args, "window_size", 8)
    if window_size < 4 or window_size > 8:
        output.error(_t("cli.validation.window_size_range", value=window_size))
        output.print("  提示: --window-size 有效范围为 4-8")
        return False

    if args.workers is not None and args.workers < 1:
        output.error(f"--workers 值无效: {args.workers}")
        output.print("  提示: --workers 必须 >= 1")
        return False

    if args.duration < 0:
        output.error(f"--duration 值无效: {args.duration}")
        output.print("  提示: --duration 必须 >= 0（0 表示无限运行）")
        return False

    return True


def _get_output():
    """获取 CLIOutput 单例（延迟导入避免循环依赖）"""
    from src.cli.output import CLIOutput

    return CLIOutput.get_instance()


def validate_file_path(file_path: str) -> bool:
    """
    验证文件路径有效性：存在性、类型、读权限、文件大小。

    允许任意位置的文件路径。大文件（>100MB）给出警告但不阻止运行。

    Args:
        file_path: 待验证的文件路径

    Returns:
        True 如果路径有效，False 如果路径无效
    """
    from pathlib import Path

    output = _get_output()
    resolved = Path(file_path).resolve()

    if not resolved.exists():
        output.error(f"文件不存在: {file_path}")
        output.print("  提示: 确认路径是否正确，或使用 -t <地址> 直接指定目标")
        return False

    if not resolved.is_file():
        output.error(f"路径不是文件: {file_path}")
        output.print("  提示: 请指定一个有效的文件路径，而非目录")
        return False

    if not os.access(resolved, os.R_OK):
        output.error(f"文件无读取权限: {file_path}")
        output.print("  提示: 检查文件权限，确保当前用户可以读取该文件")
        return False

    # 大文件警告（不阻止运行）
    try:
        size = resolved.stat().st_size
        if size > _FILE_SIZE_WARN_BYTES:
            size_mb = size / (1024 * 1024)
            output.warning(f"文件较大 ({size_mb:.0f} MB): {file_path}，加载可能需要较长时间")
    except OSError:
        pass  # 无法获取大小时忽略

    return True
