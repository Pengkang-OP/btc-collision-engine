#!/usr/bin/env python3
"""
比特币私钥对撞工具 - 命令行界面入口

用法:
    python -m src.cli.main [选项]
    python key_collision_cli.py [选项]

示例:
    # 随机碰撞（无限运行）
    python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf -m random

    # 从文件加载目标，范围扫描
    python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFF

    # 启用断点续传和去重，运行60秒
    python key_collision_cli.py -t 1A1z... -m random --checkpoint --dedup --duration 60
"""

import os
import sys
import time
from typing import Any, cast

# v4.5.1: 确保项目根目录在 sys.path 中（使用共享模块）
from ._path_setup import ensure_project_root

ensure_project_root()

# ── 仅导入轻量级模块（--help/--version 等命令不触发重量级导入） ─────────────
from src.cli.arg_parser import parse_args  # noqa: E402
from src.cli.commands import _dispatch_utility_commands  # noqa: E402
from src.cli.config_loader import load_config_with_validation  # noqa: E402
from src.cli.output import CLIOutput  # noqa: E402
from src.cli.progress import (  # noqa: E402, F401
    format_progress,
)  # re-export for backward compat
from src.cli.stats_reporter import _print_final_summary  # noqa: E402
from src.cli.validation import validate_args, validate_file_path  # noqa: E402
from src.core.crypto_backend import verify_production_ready  # noqa: E402
from src.i18n import _t, set_language  # noqa: E402
from src.utils import get_configured_logger, init_logging  # noqa: E402

# 初始化日志
init_logging()
logger = get_configured_logger("CLI")


def _apply_output_flags(args) -> None:
    """根据 --verbose / --quiet / --no-color 调整日志级别和输出行为"""
    import logging

    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)
    no_color = getattr(args, "no_color", False)

    # --no-color: 设置环境变量供 Rich 等库感知
    if no_color:
        os.environ["NO_COLOR"] = "1"

    # --quiet 与 --verbose 互斥：quiet 优先
    if quiet:
        # 仅显示 WARNING 及以上，屏蔽 INFO/DEBUG
        logging.getLogger().setLevel(logging.WARNING)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.WARNING)
    elif verbose >= 3:
        # -vvv: 全部调试信息（DEBUG）
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.DEBUG)
        logger.debug("详细级别 -vvv：启用所有调试输出")
    elif verbose >= 2:
        # -vv: DEBUG + 稍后在配置信息阶段额外打印
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.DEBUG)
        logger.debug("详细级别 -vv：启用调试输出（含配置详情）")
    elif verbose >= 1:
        # -v: DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.DEBUG)
        logger.debug("详细级别 -v：启用调试输出")


def load_targets(args: Any) -> set[str]:
    """加载目标地址集合"""
    # 延迟导入 TargetResolver（属于重量级依赖链）
    from src.collision import TargetResolver

    resolver = TargetResolver()
    quiet = getattr(args, "quiet", False)
    if args.file:
        if not validate_file_path(args.file):
            print("[Error] 文件路径验证失败", file=sys.stderr)
            sys.exit(1)
        targets = resolver.load_from_file(args.file)
        if not targets:
            print(
                _t("address.load_failed", error=f"从文件 '{args.file}' 未加载到任何有效地址"),
                file=sys.stderr,
            )
            sys.exit(1)
        if not quiet:
            print(_t("address.loaded", count=len(targets)))
    else:
        targets = cast(set[str], resolver.resolve_multiple(args.targets))
        if not targets:
            print(_t("address.load_failed", error="未能解析任何有效的目标地址"), file=sys.stderr)
            sys.exit(1)
        if not quiet:
            print(_t("address.loaded", count=len(targets)))

    # v4.3.1: 分析目标格式并给出兼容性警告（始终执行分析，输出模式由 quiet 控制）
    fmt_counts = TargetResolver.analyze_target_formats(targets)
    if not quiet:
        _print_format_summary(fmt_counts)
    else:
        incompatible = (
            fmt_counts.get("p2sh", 0) + fmt_counts.get("bech32", 0) + fmt_counts.get("taproot", 0)
        )
        if incompatible > 0:
            logger.warning(_t("targets.incompatible_warning", count=incompatible))

    return targets


def _print_format_summary(fmt_counts: dict[str, int]) -> None:
    """打印目标格式统计及不兼容格式警告"""
    total = sum(fmt_counts.values())
    if total == 0:
        return

    # 格式统计
    parts = []
    if fmt_counts.get("p2pkh", 0) > 0:
        parts.append(f"P2PKH: {fmt_counts['p2pkh']}")
    if fmt_counts.get("p2sh", 0) > 0:
        parts.append(f"P2SH: {fmt_counts['p2sh']}")
    if fmt_counts.get("bech32", 0) > 0:
        parts.append(f"Bech32: {fmt_counts['bech32']}")
    if fmt_counts.get("taproot", 0) > 0:
        parts.append(f"Taproot: {fmt_counts['taproot']}")
    if fmt_counts.get("unknown", 0) > 0:
        parts.append(f"Unknown: {fmt_counts['unknown']}")
    print(_t("targets.format_breakdown", breakdown=", ".join(parts)))

    # 不兼容格式警告
    incompatible = (
        fmt_counts.get("p2sh", 0) + fmt_counts.get("bech32", 0) + fmt_counts.get("taproot", 0)
    )
    if incompatible > 0:
        # 使用 Rich Panel 输出醒目警告
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text

            console = Console()
            warning_text = Text()
            warning_text.append(
                _t("targets.incompatible_warning", count=incompatible),
                style="bold yellow",
            )
            warning_text.append("\n\n")
            warning_text.append(_t("targets.incompatible_detail"))
            warning_text.append("\n")
            warning_text.append(_t("targets.incompatible_suggestion"))
            console.print(Panel(warning_text, title=_t("common.warning"), border_style="yellow"))
        except (RuntimeError, OSError, ValueError):
            logger.debug("Rich Panel 渲染失败，降级纯文本警告", exc_info=True)
            print(_t("targets.incompatible_warning", count=incompatible))
            print(_t("targets.incompatible_detail"))
            print(_t("targets.incompatible_suggestion"))


def _run_security_check(args) -> None:
    """在引擎启动前自动验证加密后端安全性（非阻塞模式）。

    默认自动执行；使用 --skip-security-check 可跳过。
    通过时显示绿色成功信息；不通过时显示黄色警告但允许继续运行。
    """
    if getattr(args, "skip_security_check", False):
        logger.info("跳过安全加密后端检查（--skip-security-check）")
        return

    is_ready, message = verify_production_ready()
    output = CLIOutput.get_instance()

    if is_ready:
        output.success("生产环境安全检查通过 — 加密后端安全可用")
        logger.info("安全检查通过")
    else:
        # 非阻塞模式：使用 Rich Panel 显示醒目警告，但允许继续运行
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text

            console = Console(stderr=True)
            warning_text = Text()
            warning_text.append("生产环境安全检查未通过\n\n", style="bold yellow")
            warning_text.append(
                "当前加密后端安全级别不足，建议安装更安全的加密库后再运行。\n\n",
                style="yellow",
            )
            warning_text.append("  pip install coincurve     # 推荐，最安全\n", style="white")
            warning_text.append("  pip install cryptography  # 备选\n\n", style="white")
            warning_text.append("使用 --skip-security-check 跳过此检查", style="dim")
            console.print(
                Panel(
                    warning_text, title="[bold yellow]安全检查[/bold yellow]", border_style="yellow"
                )
            )
        except (RuntimeError, OSError, ValueError):
            # Rich Panel 渲染失败时降级为纯文本警告
            output.warning(
                "生产环境安全检查未通过 — 当前加密后端安全级别不足",
                details="建议: pip install coincurve  # 推荐，最安全",
            )
            output.print_always("[dim]使用 --skip-security-check 跳过此检查[/dim]")

        logger.warning("安全检查未通过，但允许继续运行")


def _run_main() -> None:
    """CLI 主逻辑（由 main() 包装异常处理）"""
    args = parse_args()

    # 语言设置（优先级：命令行 > 环境变量 > 系统语言）
    if getattr(args, "language", None):
        set_language(args.language)

    # 初始化统一输出管理器（单例，后续模块通过 CLIOutput.get_instance() 获取）
    CLIOutput.init(
        no_color=getattr(args, "no_color", False),
        quiet=getattr(args, "quiet", False),
    )

    # 应用输出标志（--verbose/--quiet/--no-color）
    _apply_output_flags(args)

    # 阶段1: 工具命令分发（提前处理，不需要 -t/-f，不触发重量级导入）
    if _dispatch_utility_commands(args, _run_main):
        return  # 工具命令已处理，不再进行后续流程

    # 安全检查: 在碰撞引擎启动前自动验证加密后端安全性（非阻塞）
    _run_security_check(args)

    # 阶段2: 参数验证
    if not validate_args(args):
        sys.exit(1)

    # 阶段3: 配置和目标加载
    config = load_config_with_validation(config_file=args.config)
    if config is None:
        logger.warning(_t("config.using_default"))
        config = {}
    targets = load_targets(args)
    if not targets:
        print(_t("address.load_failed", error="解析后无有效目标地址"), file=sys.stderr)
        sys.exit(1)

    # ── 以下阶段才延迟导入重量级模块 ────────────────────────────────────────
    from src.cli.engine_runner import (
        _compute_range,
        _print_config_info,
        _run_collision_loop,
        _setup_and_start_engine,
    )

    # 阶段4: 计算范围参数
    start_val, end_val, total_range = _compute_range(args)

    # 阶段5: 显示配置信息（--quiet 时跳过）
    quiet = getattr(args, "quiet", False)
    verbose = getattr(args, "verbose", 0)
    if not quiet:
        _print_config_info(args, targets, start_val, end_val, total_range)
        # -vv 额外打印配置详情
        if verbose >= 2 and config:
            import json

            print("\n[详细] 当前 config.json 配置:")
            print(json.dumps(config, ensure_ascii=False, indent=2))

    # 阶段6: 构建引擎、初始化告警、注册信号、启动
    engine, engine_type, alert_system, stop_event = _setup_and_start_engine(
        args, targets, config, start_val, end_val
    )

    # 阶段7: 主循环
    _run_collision_loop(engine, engine_type, args, total_range, alert_system, stop_event)

    # 阶段8: 等待引擎完全停止（带超时轮询）
    if engine.is_running():
        engine.stop()
    for _ in range(50):  # 最多等待5秒
        if not engine.is_running():
            break
        time.sleep(0.1)

    # 阶段9: 最终统计
    _print_final_summary(engine, engine_type, args)


def _handle_error(e: Exception) -> None:
    """统一错误处理 — 向用户显示友好消息并将完整堆栈写入日志"""
    output = CLIOutput.get_instance()
    error_type = type(e).__name__

    if isinstance(e, FileNotFoundError):
        output.error(f"文件未找到: {e}")
        output.print("  提示: 检查文件路径是否正确")
    elif isinstance(e, PermissionError):
        output.error(f"权限不足: {e}")
        output.print("  提示: 检查文件/目录的读写权限")
    elif isinstance(e, MemoryError):
        output.error("内存不足")
        output.print("  提示: 减小 --gpu-batch-size 或关闭其他程序")
    elif isinstance(e, ImportError):
        output.error(f"缺少依赖: {e}")
        output.print("  提示: 运行 pip install -r requirements.txt 安装依赖")
    elif isinstance(e, (ValueError, TypeError)):
        output.error(f"参数错误: {e}")
        output.print("  提示: 运行 --help 查看参数说明")
    elif isinstance(e, OSError):
        output.error(f"系统错误: {e}")
        output.print("  提示: 检查文件/目录权限或磁盘空间")
    else:
        output.error(f"运行时错误 ({error_type}): {e}")
        output.print("  详细日志: logs/collision.log")

    # 记录完整堆栈到日志（不显示给用户）
    logger.exception(f"CLI 运行错误: {error_type}")


def main() -> None:
    """CLI 主入口"""
    # 确保 stdout/stderr 在非 UTF-8 环境下不会因无法编码字符而崩溃
    try:
        if hasattr(sys.stdout, "reconfigure"):
            cast(Any, sys.stdout).reconfigure(errors="replace")
            cast(Any, sys.stderr).reconfigure(errors="replace")
    except (OSError, AttributeError):
        pass
    try:
        _run_main()
    except KeyboardInterrupt:
        print()  # 换行，避免 ^C 粘连
        sys.exit(130)
    except SystemExit:
        # argparse 的 --help/--version 以及主动调用 sys.exit() 均透传
        raise
    except Exception as e:
        _handle_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
