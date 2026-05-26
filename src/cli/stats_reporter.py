"""Statistics reporting utilities for CLI.

Provides final summary display with sensitive information masking
based on --sensitive-mode (full|masked|hash_only).
"""

import hashlib
import json
import os
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("StatsReporter")


def _mask_value(value: str, mode: str = "masked") -> str:
    """对敏感值进行脱敏处理。

    Args:
        value: 原始值（如私钥十六进制字符串）
        mode: full | masked | hash_only

    Returns:
        脱敏后的字符串
    """
    if not value:
        return "(空)"
    if mode == "full":
        return value
    if mode == "hash_only":
        return hashlib.sha256(str(value).encode()).hexdigest()[:16] + "..."
    # masked: 首尾各4位中间脱敏
    s = str(value)
    if len(s) <= 8:
        star_count = max(len(s) - 4, 1)
        return s[:2] + "*" * star_count + s[-2:]
    return s[:4] + "*" * min(len(s) - 8, 12) + s[-4:]


def _print_final_summary(engine: Any, engine_type: str, args: Any) -> None:
    """Print final collision statistics summary after engine stops.

    Args:
        engine: The collision engine instance
        engine_type: Engine type label (e.g. 'GPU', 'CPU')
        args: Parsed CLI arguments
    """
    from ..cli.output import CLIOutput

    output = CLIOutput.get_instance()
    sensitive_mode = getattr(args, "sensitive_mode", "masked")

    output.print()
    output.rule(f"BTC Collision Engine - 运行结束 ({engine_type})", style="bold cyan")

    # ── 统计信息 ──────────────────────────────────────────
    try:
        if engine_type == "MultiGPU" and hasattr(engine, "get_combined_stats"):
            stats = engine.get_combined_stats()
            if stats:
                rows = _build_stats_rows(stats, multi_gpu=True)
                output.stats_panel("运行统计", rows)
            else:
                output.warning("无法获取统计信息")
        else:
            stats = engine.get_stats()
            if stats:
                rows = _build_stats_rows(stats, multi_gpu=False)
                output.stats_panel("运行统计", rows)
            else:
                output.warning("无法获取统计信息")
    except Exception as e:
        logger.debug("Failed to get final stats: %s", e)
        output.warning("统计信息获取失败")

    # ── 匹配结果 ──────────────────────────────────────────
    matches = _get_matches(engine, engine_type)
    if matches:
        output.print()
        count_str = f"  {len(matches)} 条匹配" if len(matches) <= 20 else f"  {len(matches)} 条匹配 (显示前20条)"
        output.rule(f"匹配结果 — {count_str}", style="bold yellow")
        mode_labels = {"full": "完整显示", "masked": "部分脱敏", "hash_only": "仅哈希"}
        mode_label = mode_labels.get(sensitive_mode, sensitive_mode)
        output.hint(f"私钥显示: {mode_label}")
        output.print()

        for i, match in enumerate(matches[:20], 1):
            _print_single_match(output, match, i, sensitive_mode)
            if i < min(len(matches), 20):
                output.print()

        if len(matches) > 20:
            output.hint(f"（另有 {len(matches) - 20} 条未显示，使用 --export-matches 导出完整结果）")
        output.print()

        _export_matches_if_requested(args, matches)
    else:
        output.print()
        output.hint("本次运行未发现匹配的私钥")

    output.rule(style="dim")


def _build_stats_rows(stats: dict, multi_gpu: bool = False) -> list:
    """构建统计行数据。"""
    if multi_gpu:
        return [
            ("总检查私钥", f"{stats.get('total_keys_checked', 0):,}"),
            ("总吞吐量", f"{stats.get('combined_throughput', 0):,.0f} keys/s"),
            ("命中次数", str(stats.get("total_matches", 0))),
            ("GPU 数量", str(stats.get("device_count", 0))),
            ("运行时长", f"{stats.get('elapsed_time', 0):.1f}s"),
        ]
    return [
        ("总检查私钥", f"{stats.get('total_checked', 0):,}"),
        ("平均速度", f"{stats.get('avg_speed', stats.get('speed', 0)):,.0f} keys/s"),
        ("命中次数", str(stats.get("matches_found", 0))),
        ("运行时长", f"{stats.get('elapsed', 0):.1f}s"),
    ]


def _get_matches(engine: Any, engine_type: str) -> list[dict]:
    """安全获取匹配结果列表。"""
    try:
        if engine_type == "MultiGPU" and hasattr(engine, "get_matches"):
            return engine.get_matches() or []
        if hasattr(engine, "matches"):
            matches = engine.matches
            return list(matches) if matches else []
        if hasattr(engine, "get_matches"):
            return engine.get_matches() or []
    except Exception as e:
        logger.debug("获取匹配结果失败: %s", e, exc_info=True)
    return []


def _print_single_match(
    output: Any,
    match: dict,
    index: int,
    sensitive_mode: str,
) -> None:
    """打印单条匹配结果，应用脱敏模式 (Rich 格式化)。"""
    addr = match.get("address", match.get("target", "N/A"))
    pk = match.get("private_key", match.get("key", ""))

    output.print(f"[bold white]#{index}[/bold white]  [bold cyan]{addr}[/bold cyan]")
    if pk:
        pk_display = _mask_value(pk, sensitive_mode)
        if sensitive_mode == "full":
            output.print(f"    [bold yellow]私钥:[/bold yellow] {pk_display}")
        else:
            output.print(f"    [dim]私钥:[/dim] {pk_display}")

    for field in ("timestamp", "found_at", "method"):
        val = match.get(field)
        if val:
            output.print(f"    [dim]{field}:[/dim] {val}")


def _export_matches_if_requested(args: Any, matches: list[dict]) -> None:
    """如果指定了 --export-matches，导出为 JSON 文件。"""
    export_path = getattr(args, "export_matches", None)
    if not export_path:
        return

    sensitive_mode = getattr(args, "sensitive_mode", "masked")
    try:
        # 导出版本默认脱敏处理
        export_data = []
        for m in matches:
            item = dict(m)
            if "private_key" in item and sensitive_mode != "full":
                item["private_key"] = _mask_value(item["private_key"], sensitive_mode)
            if "key" in item and sensitive_mode != "full":
                item["key"] = _mask_value(item["key"], sensitive_mode)
            export_data.append(item)

        export_dir = os.path.dirname(os.path.abspath(export_path))
        if export_dir:
            os.makedirs(export_dir, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)
        logger.info("匹配结果已导出到: %s (%d 条)", export_path, len(export_data))
        from ..cli.output import CLIOutput

        CLIOutput.get_instance().success(f"匹配结果已导出: {export_path} ({len(export_data)} 条)")
    except OSError as e:
        logger.warning("导出匹配结果失败: %s", e)
        from ..cli.output import CLIOutput

        CLIOutput.get_instance().warning(f"导出失败: {e}")


class StatsReporter:
    """Formats and outputs collision engine statistics."""

    @staticmethod
    def format_summary(stats: dict) -> str:
        """Format a human-readable summary.

        Args:
            stats: Statistics dictionary

        Returns:
            Formatted summary string
        """
        lines = [
            "=== Collision Detection Summary ===",
            f"Keys checked: {stats.get('total_keys_checked', 0):,}",
            f"Matches found: {stats.get('total_matches', 0)}",
            f"Elapsed time: {stats.get('elapsed_seconds', 0):.1f}s",
            f"Throughput: {stats.get('throughput', 0):.0f} keys/s",
        ]
        return "\n".join(lines)

    @staticmethod
    def format_json(stats: dict) -> str:
        """Format as JSON.

        Args:
            stats: Statistics dictionary

        Returns:
            JSON string
        """
        return json.dumps(stats, indent=2, default=str)
