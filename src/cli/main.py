#!/usr/bin/env python3
"""Bitcoin private key collision tool - CLI entry point.

Usage:
    python -m src.cli.main [选项]
    python key_collision_cli.py [选项]

Example:
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

# ── 模块级必需导入（仅保留被多处引用或模块级调用的轻量模块） ─────────────
from ..utils import get_configured_logger, init_logging  # noqa: E402 — 模块级使用
from .output import CLIOutput  # noqa: E402 — 被5个函数引用

# 初始化日志
init_logging()
logger = get_configured_logger("CLI")


def _apply_output_flags(args) -> None:
    """根据 --verbose / --quiet / --no-color 调整日志级别和输出行为."""
    import logging

    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)
    no_color = getattr(args, "no_color", False)

    # 遵循 https://no-color.org/ 标准：环境变量 NO_COLOR 也启用无颜色模式
    if not no_color and os.environ.get("NO_COLOR", "").strip():
        no_color = True

    # --no-color: 设置环境变量供 Rich 等库感知
    if no_color:
        os.environ["NO_COLOR"] = "1"

    # --quiet 与 --verbose 互斥：quiet 优先
    if quiet:
        # 仅显示 WARNING 及以上，屏蔽 INFO/DEBUG
        logging.getLogger().setLevel(logging.WARNING)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.WARNING)
    elif verbose >= 1:
        # -v/-vv/-vvv: DEBUG（vvv/vv 的区别在后续阶段区分）
        level_name = {1: "-v", 2: "-vv", 3: "-vvv"}.get(verbose, "-v")
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.DEBUG)
        if verbose >= 3:
            logger.debug("详细级别 %s：启用所有调试输出", level_name)
        elif verbose >= 2:
            logger.debug("详细级别 %s：启用调试输出（含配置详情）", level_name)
        else:
            logger.debug("详细级别 %s：启用调试输出", level_name)


def load_targets(args: Any) -> set[str]:
    """加载目标地址集合，显示详细的加载/丢弃统计。."""
    # 延迟导入 TargetResolver（属于重量级依赖链）
    from src.collision.targets.resolver import TargetResolver

    resolver = TargetResolver()
    quiet = getattr(args, "quiet", False)
    output = CLIOutput.get_instance()

    if args.file:
        from src.cli.validation import validate_file_path

        if not validate_file_path(args.file):
            output.error("文件路径验证失败")
            sys.exit(1)
        targets = resolver.load_from_file(args.file)
        # 获取不支持类型的丢弃统计
        dropped = resolver.get_unsupported_types()
        total_dropped = sum(dropped.values()) if dropped else 0

        if not targets:
            output.error(f"从文件 '{args.file}' 未加载到任何有效地址")
            if total_dropped > 0:
                _print_dropped_summary(output, dropped)
            sys.exit(1)
        if not quiet:
            _print_load_result(output, len(targets), total_dropped, dropped)
    else:
        # resolve_multiple returns dict[str,str] (input→resolved), extract values as set
        resolved = resolver.resolve_multiple(args.targets)  # type: ignore[arg-type]
        targets = {v for v in resolved.values() if v is not None}
        dropped_inputs = [k for k, v in resolved.items() if v is None]
        if not targets:
            output.error("未能解析任何有效的目标地址")
            if dropped_inputs:
                output.hint(f"已跳过 {len(dropped_inputs)} 条无法解析的输入")
            sys.exit(1)
        if not quiet and dropped_inputs:
            output.warning(f"已跳过 {len(dropped_inputs)} 条不兼容格式的输入")

    return targets


def _print_load_result(
    output: "CLIOutput",
    valid_count: int,
    dropped_count: int,
    dropped_detail: dict[str, int] | None,
) -> None:
    """打印文件加载结果摘要。."""
    output.success(f"已加载 {valid_count} 个有效目标地址")
    if dropped_count > 0 and dropped_detail:
        _print_dropped_summary(output, dropped_detail)


def _print_dropped_summary(
    output: "CLIOutput",
    dropped_detail: dict[str, int],
) -> None:
    """打印被丢弃的不兼容格式统计。."""
    total = sum(dropped_detail.values())
    type_names = {
        "p2sh_address": "P2SH (3...)",
        "p2wsh_address": "P2WSH (bc1q... 32B witness)",
        "taproot_address": "Taproot (bc1p...)",
    }
    output.warning(f"已跳过 {total} 条密码学上不兼容的输入格式:")
    for key, count in sorted(dropped_detail.items()):
        label = type_names.get(key, key)
        output.print(f"  - {label}: {count} 条")
    output.hint("提示: 仅 P2PKH (1...)、P2WPKH (bc1q... 20B)、WIF私钥、公钥格式可被碰撞匹配")


def _run_security_check(args) -> None:
    """在引擎启动前自动验证加密后端安全性（非阻塞模式）。.

    默认自动执行；使用 --skip-security-check 可跳过。
    通过时显示绿色成功信息；不通过时显示黄色警告但允许继续运行。
    """
    if getattr(args, "skip_security_check", False):
        logger.info("跳过安全加密后端检查（--skip-security-check）")
        return

    from src.core.crypto_backend import verify_production_ready

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
                Panel(warning_text, title="[bold yellow]安全检查[/bold yellow]", border_style="yellow"),
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
    """CLI 主逻辑（由 main() 包装异常处理）."""
    # 延迟导入：保留 ensure_project_root() 的调用顺序约束，同时避免模块级 E402
    from src.cli.arg_parser import parse_args
    from src.cli.commands import dispatch_utility_commands
    from src.cli.config_loader import load_config_with_validation
    from src.cli.stats_reporter import _print_final_summary
    from src.cli.validation import validate_args
    from src.i18n import _t, set_language

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
    if dispatch_utility_commands(args, _run_main):
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
        args,
        targets,
        config,
        start_val,
        end_val,
    )

    # 阶段7: 主循环
    _run_collision_loop(engine, engine_type, args, total_range, alert_system, stop_event)

    # 阶段8: 等待引擎完全停止（带超时轮询）
    if engine.is_running():
        engine.stop()
    try:
        engine.stop_event.wait(timeout=5.0)
    except AttributeError:
        # 回退到轮询方式（引擎可能没有 stop_event）
        logger.debug("引擎无 stop_event 属性，回退到轮询等待停止")
        for _ in range(50):  # 最多等待5秒
            if not engine.is_running():
                break
            time.sleep(0.1)

    # 阶段9: 最终统计
    _export_progress_data(engine, args)
    _print_final_summary(engine, engine_type, args)


def _export_progress_data(engine: Any, args: Any) -> None:
    """如果指定了 --export-progress，将进度数据导出为 JSON。."""
    export_path = getattr(args, "export_progress", None)
    if not export_path:
        return
    try:
        import json

        stats = {}
        if hasattr(engine, "get_stats"):
            stats = engine.get_stats() or {}
        elif hasattr(engine, "get_combined_stats"):
            stats = engine.get_combined_stats() or {}

        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, default=str, ensure_ascii=False)
        logger.info("进度数据已导出到: %s", export_path)
        CLIOutput.get_instance().success(f"进度数据已导出: {export_path}")
    except OSError as e:
        logger.warning("导出进度数据失败: %s", e)
        CLIOutput.get_instance().warning(f"导出失败: {e}")


def _handle_error(e: Exception) -> None:
    """统一错误处理 — 向用户显示友好消息并将完整堆栈写入日志.

    可在 CLIOutput 未初始化时安全调用（get_instance() 自动创建默认实例）。
    ROADMAP #11: 增强兜底逻辑，确保所有入口路径（key_collision_cli.py / -m / btc-collision）一致。
    """
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
        try:
            from src.i18n import _t

            output.print(_t("cli.entry.check_log"))
        except Exception:
            output.print("  详细日志: 请查看 logs/ 目录下的日志文件")

    # 记录完整堆栈到日志（不显示给用户）
    logger.exception("CLI 运行错误: %s", error_type)


def main() -> None:
    """CLI 主入口（单一真相源）.

    ROADMAP #11: 此函数是所有入口路径（key_collision_cli.py / -m / btc-collision）
    的单一实现。顶层异常处理已集成在此，代理文件无需重复。
    """
    # 确保 stdout/stderr 在非 UTF-8 环境下不会因无法编码字符而崩溃
    try:
        if hasattr(sys.stdout, "reconfigure"):
            cast("Any", sys.stdout).reconfigure(errors="replace")
            cast("Any", sys.stderr).reconfigure(errors="replace")
    except (OSError, AttributeError) as e:
        logger.debug("Failed to reconfigure stdout/stderr for UTF-8: %s", e)
    try:
        _run_main()
    except KeyboardInterrupt:
        print()
        try:
            from src.i18n import _t

            print(_t("cli.entry.keyboard_interrupt"))
        except Exception:
            pass
        sys.exit(130)
    except SystemExit:
        # argparse 的 --help/--version 以及主动调用 sys.exit() 均透传
        raise
    except Exception as e:
        # 最终兜底：确保 logging 已初始化（即使 _run_main 早期失败）
        import logging as _logging

        _logging.basicConfig(level=_logging.CRITICAL)
        _handle_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
