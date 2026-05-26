"""CLI input validation utilities."""

import argparse
from pathlib import Path

from ..utils import get_configured_logger
from .output import CLIOutput

logger = get_configured_logger(__name__)


def validate_args(args: argparse.Namespace) -> bool:  # noqa: C901
    """Validate parsed CLI arguments."""
    output = CLIOutput.get_instance()

    # Check: must have either -t or -f (unless it's a utility-only command)
    if not getattr(args, "targets", None) and not getattr(args, "file", None):
        output.error("必须指定目标地址 (-t) 或目标文件 (-f)")
        output.print("  示例: -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        output.print("  示例: -f targets.txt")
        return False

    # Validate mode
    mode = getattr(args, "mode", "random")
    if mode not in ("random", "range", "brute_force"):
        output.error(f"无效模式: {mode}，有效值: random, range, brute_force")
        return False

    # ── GPU 参数互斥校验 ────────────────────────────────────────────────
    # 注意: --use-gpu 与 --multi-gpu 已在 argparse 中通过
    # add_mutually_exclusive_group 保证互斥。
    # --gpu-count 与 --gpu-indices 无 argparse 级互斥，需手动校验。
    gpu_count = getattr(args, "gpu_count", -1)
    gpu_indices = getattr(args, "gpu_indices", None)
    if gpu_count != -1 and gpu_indices is not None:
        output.error("--gpu-count 与 --gpu-indices 不能同时使用")
        output.hint("--gpu-count: 自动选择前 N 个 GPU｜--gpu-indices: 手动指定 GPU 索引")
        return False

    # ── Duration validation (must be >= 0, 0 = indefinite) ──────────────────
    duration = getattr(args, "duration", 0)
    if duration is not None and duration < 0:
        output.error(f"--duration 必须 >= 0，当前值: {duration}")
        return False

    # ── Workers validation (must be >= 1 when specified) ────────────────────
    workers = getattr(args, "workers", None)
    if workers is not None and workers < 1:
        output.error(f"--workers 必须 >= 1，当前值: {workers}")
        return False

    # ── Checkpoint interval validation (range 5-3600) ───────────────────────
    cp_interval = getattr(args, "checkpoint_interval", None)
    if cp_interval is not None and not (5 <= cp_interval <= 3600):
        output.error(f"--checkpoint-interval 必须在 5-3600 之间，当前值: {cp_interval}")
        return False

    # ── Batch size validation (must be >= 1 when specified) ─────────────────
    batch_size = getattr(args, "batch_size", None)
    if batch_size is not None and batch_size < 1:
        output.error(f"--batch-size 必须 >= 1，当前值: {batch_size}")
        return False

    # ── Progress interval validation (must be > 0) ──────────────────────────
    prog_interval = getattr(args, "progress_interval", None)
    if prog_interval is not None and prog_interval <= 0:
        output.error(f"--progress-interval 必须 > 0，当前值: {prog_interval}")
        return False

    # ── Dedup max size validation (must be > 0) ─────────────────────────────
    dedup_max = getattr(args, "dedup_max_size", None)
    if dedup_max is not None and dedup_max < 1:
        output.error(f"--dedup-max-size 必须 >= 1，当前值: {dedup_max}")
        return False

    # Range/brute_force mode requires --start
    if mode in ("range", "brute_force"):
        start = getattr(args, "start", None)
        if not start:
            output.error(f"{mode} 模式需要指定 --start (十六进制起始私钥)")
            return False

        # --end only required for range mode
        end = getattr(args, "end", None)
        if mode == "range" and not end:
            output.error("range 模式需要指定 --end (十六进制结束私钥)")
            return False

        # Validate hex format
        try:
            start_int = int(start, 16)
        except (ValueError, TypeError):
            output.error(f"--start 值不是合法的十六进制: {start}")
            return False
        if start_int < 1:
            output.error(f"--start 必须 >= 1，当前值: {start_int}")
            return False
        if end:
            try:
                end_int = int(end, 16)
            except (ValueError, TypeError):
                output.error(f"--end 值不是合法的十六进制: {end}")
                return False
            if end_int <= start_int:
                output.error(f"--end ({end_int}) 必须大于 --start ({start_int})")
                return False

    return True


def validate_file_path(file_path: str) -> bool:
    """Validate file path format and accessibility (allowing arbitrary locations).

    Users may place target files anywhere on disk (Desktop, Downloads, etc.).
    Only blocks obviously malformed paths and warns about non-existent files.
    """
    output = CLIOutput.get_instance()

    if not file_path or not isinstance(file_path, str):
        output.error("Invalid file path")
        return False

    # Convert to absolute path and resolve (handles .. and symlinks)
    try:
        resolved = Path(file_path).resolve()
    except (OSError, RuntimeError):
        output.error("Cannot resolve file path: %s", file_path)
        return False

    # Warn but do NOT block if file doesn't exist (caller handles it separately)
    if not resolved.exists():
        output.warning("File not found: %s (will be checked by caller)", file_path)

    return True


def _get_project_root() -> Path | None:
    """Get the project root directory (reserved for future use)."""
    try:
        from ._path_setup import _get_project_root as _pr

        return Path(_pr()).resolve()
    except Exception as e:
        logger.debug("Failed to get project root: %s", e)
        return None


def validate_batch_size(value: str) -> int:
    """Validate and convert batch size argument.

    Args:
        value: Batch size string

    Returns:
        Validated batch size integer

    Raises:
        ValueError: If value is invalid

    """
    n = int(value)
    if not (1 <= n <= 10_000_000):
        raise ValueError(
            f"Batch size must be between 1 and 10,000,000, got {n}",
        )
    return n


def validate_worker_count(value: str) -> int:
    """Validate and convert worker count argument.

    Args:
        value: Worker count string

    Returns:
        Validated worker count

    Raises:
        ValueError: If value is invalid

    """
    n = int(value)
    if not (1 <= n <= 1024):
        raise ValueError(
            f"Worker count must be between 1 and 1024, got {n}",
        )
    return n
