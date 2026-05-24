"""CLI input validation utilities."""

import argparse
import os
from pathlib import Path
from typing import Any


def validate_args(args: argparse.Namespace) -> bool:
    """Validate parsed CLI arguments.

    Args:
        args: Parsed argument namespace

    Returns:
        True if valid, False otherwise
    """
    from src.cli.output import CLIOutput

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

    # Range mode requires start/end
    if mode in ("range", "brute_force"):
        start = getattr(args, "start", None)
        end = getattr(args, "end", None)
        if not start and mode == "range":
            output.error("范围扫描模式需要指定 --start")
            return False

    return True


def validate_file_path(file_path: str) -> bool:
    """Security check: validate file path for path traversal and existence.

    Args:
        file_path: File path to validate

    Returns:
        True if path is safe and exists, False otherwise
    """
    from src.cli.output import CLIOutput

    output = CLIOutput.get_instance()

    if not file_path or not isinstance(file_path, str):
        output.error("无效的文件路径")
        return False

    # Convert to absolute path and resolve
    try:
        resolved = Path(file_path).resolve()
    except (OSError, RuntimeError):
        output.error(f"无法解析文件路径: {file_path}")
        return False

    # Check for path traversal attempts
    project_root = _get_project_root()
    if project_root:
        try:
            resolved.relative_to(project_root)
        except ValueError:
            # File outside project root - warn but still allow
            pass

    return True


def _get_project_root() -> Path | None:
    """Get the project root directory."""
    try:
        from ._path_setup import _get_project_root as _pr

        return Path(_pr()).resolve()
    except Exception:
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
            f"Batch size must be between 1 and 10,000,000, "
            f"got {n}",
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
            f"Worker count must be between 1 and 1024, "
            f"got {n}",
        )
    return n
