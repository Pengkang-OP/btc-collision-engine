#!/usr/bin/env python3
"""
引擎启动与主循环模块

提供碰撞引擎的启动、主进度循环逻辑，以及运行时控制台日志抑制功能。
"""

import argparse
import os
import signal
import sys
import threading
import time
from typing import Any

# v4.5.1: 确保项目根目录在 sys.path 中（使用共享模块）
from ._path_setup import ensure_project_root

ensure_project_root()

from src.cli.engine_builder import (  # noqa: E402 — 需 sys.path 前置
    EngineBuildError,
    GPUInitializationError,
    GPUNotAvailableError,
    build_engine,
)  # noqa: E402
from src.cli.output import CLIOutput  # noqa: E402
from src.cli.progress import format_progress  # noqa: E402
from src.cli.stats_reporter import _print_detailed_stats  # noqa: E402
from src.i18n import _t  # noqa: E402

# ── 运行时日志抑制 ───────────────────────────────────────────────────
_suppressed_handlers: list = []  # 保存被抑制的 (handler, original_level) 对


def _suppress_console_logging() -> None:
    """将所有终端 StreamHandler 日志级别提升到 CRITICAL，避免运行时刷屏。"""
    import logging as _logging

    root = _logging.getLogger()
    for h in root.handlers:
        if isinstance(h, _logging.StreamHandler) and not isinstance(h, _logging.FileHandler):
            _suppressed_handlers.append((h, h.level))
            h.setLevel(_logging.CRITICAL)


def _restore_console_logging() -> None:
    """恢复被抑制的终端 StreamHandler 的原始日志级别。"""
    for h, original_level in _suppressed_handlers:
        h.setLevel(original_level)
    _suppressed_handlers.clear()


def _setup_and_start_engine(
    args: argparse.Namespace,
    targets: set[str],
    config: dict | None,
    start_val: int | None,
    end_val: int | None,
) -> tuple[Any, str, Any, threading.Event]:
    """
    构建引擎、初始化告警系统、注册信号处理器并启动引擎。

    返回:
        (engine, engine_type, alert_system, stop_event) 四元组
    """
    import logging as _logging

    logger = _logging.getLogger("CLI")

    sensitive_mode = getattr(args, "sensitive_mode", "masked")

    try:
        engine, engine_type = build_engine(args, targets, sensitive_mode=sensitive_mode, config=config)
    except GPUNotAvailableError as e:
        logger.error(f"GPU不可用: {e.message}")
        print(f"{e.user_message}", file=sys.stderr)
        sys.exit(1)
    except GPUInitializationError as e:
        logger.error(f"GPU初始化失败: {e.message}")
        print(f"{e.user_message}", file=sys.stderr)
        sys.exit(1)
    except EngineBuildError as e:
        logger.error(f"引擎构建失败: {e.message}")
        print(f"{e.user_message}", file=sys.stderr)
        sys.exit(1)

    # ── 将告警系统集成到引擎主流程 ──────────────────────────────────
    # v4.2.2 M6: 统一使用 src-prefix 导入路径，移除重复 fallback
    alert_system = None
    try:
        from src.monitoring.alert_system import AlertSystem as _alert_class  # noqa: N813
    except ImportError:
        try:
            from ..monitoring.alert_system import AlertSystem as _alert_class  # noqa: N813
        except ImportError:
            _alert_class: Any = None  # type: ignore[no-redef]

    if _alert_class is not None:
        try:
            alert_system = _alert_class()
            alert_system.setup_default_rules()

            def _on_alert(alert_record: Any) -> None:
                level = getattr(alert_record.level, "value", str(alert_record.level)).upper()
                msg = getattr(alert_record, "message", str(alert_record))
                print("\n[WARN] [" + _t("common.warning") + f"/{level}] {msg}")

            alert_system.add_alert_callback(_on_alert)
            logger.info("告警系统已集成：%d 条规则", len(alert_system.rules))
        except Exception as exc:
            logger.warning("告警系统初始化失败，将以没有告警的方式运行: %s", exc)
            alert_system = None

    # 信号处理（Ctrl+C 优雅停止）
    stop_event = threading.Event()

    def handle_signal(sig: int, frame: Any) -> None:
        print("\n" + _t("cli.messages.stopping"))
        stop_event.set()
        engine.stop()

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    # 启动引擎
    print(_t("cli.main.collision_start") + "\n")

    if engine_type == "multi_gpu":
        # v4.2.2 L1修复: 多GPU引擎start返回值为统一格式
        ok = engine.start(
            targets=targets,
            mode=args.mode,
            range_start=start_val,
            range_end=end_val,
            match_callback=lambda dev_idx, m: print(
                "\n[GPU {}] 发现匹配: 地址={}...{}".format(
                    dev_idx,
                    str(m.get("address", "N/A"))[:6],
                    str(m.get("address", "N/A"))[-4:],
                )
            ),
        )
        if not ok:
            print(_t("cli.messages.start_failed", error="多GPU引擎启动失败"), file=sys.stderr)
            sys.exit(1)
    else:
        # 单GPU / CPU 引擎
        engine_kwargs = {}
        if args.mode in ("range", "brute_force"):
            engine_kwargs["start"] = start_val
        if args.mode == "range":
            engine_kwargs["end"] = end_val
        engine.start(mode=args.mode, **engine_kwargs)

    return engine, engine_type, alert_system, stop_event


# ── 键盘回调（拆分为模块级函数以降低 C901 圈复杂度）───────────────


def _handle_pause(engine: Any, output: Any, paused: list[bool], pause_start: list[float | None]) -> None:
    paused[0] = True
    pause_start[0] = time.time()
    output.print("[yellow]⏸ 已暂停 — 按 [R] 恢复 | [Q] 退出 | [S] 统计[/yellow]")
    if hasattr(engine, "pause"):
        engine.pause()


def _handle_resume(
    engine: Any,
    output: Any,
    paused: list[bool],
    pause_start: list[float | None],
    total_pause_time: list[float],
) -> None:
    if pause_start[0] is not None:
        total_pause_time[0] += time.time() - pause_start[0]
    paused[0] = False
    pause_start[0] = None
    output.print("[green]▶ 已恢复运行[/green]")
    if hasattr(engine, "resume"):
        engine.resume()


def _handle_stats_key(engine: Any, engine_type: str) -> None:
    """S键：打印详细统计信息。"""
    try:
        if engine_type == "multi_gpu":
            combined = engine.get_combined_stats()
            print("\n" + "=" * 52)
            print("  详细统计信息")
            print("-" * 52)
            print(f"  已检查:     {combined.get('total_keys_checked', 0):,}")
            print(f"  GPU数量:    {combined.get('device_count', 0)}")
            print(f"  发现匹配:   {combined.get('total_matches', 0)}")
            print("=" * 52 + "\n")
        else:
            _print_detailed_stats(engine.get_stats())
    except (AttributeError, RuntimeError, TypeError):
        pass


def _make_key_handler(
    engine: Any,
    engine_type: str,
    output: Any,
    stop_event: threading.Event,
    paused: list[bool],
    pause_start: list[float | None],
    total_pause_time: list[float],
) -> Any:
    """创建键盘回调函数，返回 on_key callable。"""

    def on_key(key: str) -> None:
        if key == "P" and not paused[0]:
            _handle_pause(engine, output, paused, pause_start)
        elif key == "R" and paused[0]:
            _handle_resume(engine, output, paused, pause_start, total_pause_time)
        elif key == "Q":
            output.print("[red]■ 正在停止..[/red]")
            stop_event.set()
            engine.stop()
        elif key == "S":
            _handle_stats_key(engine, engine_type)

    return on_key


# ── 进度/告警辅助函数 ───────────────────────────────────────────────


def _format_multi_gpu_status_line(engine: Any) -> str:
    """格式化 multi_gpu 引擎状态行。"""
    combined = engine.get_combined_stats()
    elapsed_sec = combined.get("elapsed_time", 0)
    total_checked = combined.get("total_keys_checked", 0)
    throughput = combined.get("combined_throughput", 0)
    matches = combined.get("total_matches", 0)
    device_count = combined.get("device_count", 0)
    h, rem = divmod(int(elapsed_sec), 3600)
    m_t, s = divmod(rem, 60)
    elapsed_fmt = f"{h:02d}:{m_t:02d}:{s:02d}"
    if throughput >= 1_000_000:
        speed_fmt = f"{throughput / 1_000_000:.2f}M/s"
    elif throughput >= 1_000:
        speed_fmt = f"{throughput / 1_000:.1f}K/s"
    else:
        speed_fmt = f"{throughput:.0f}/s"
    return (
        f"[{elapsed_fmt}] GPU x{device_count} | "
        + _t("cli.main.progress_checked", count=total_checked)
        + f" | {speed_fmt} | "
        + _t("cli.main.progress_matches", count=matches)
    )


def _check_alerts_in_loop(alert_system: Any, stats: Any) -> None:
    """检查告警系统指标。"""
    if alert_system is None:
        return
    try:
        elapsed_sec = stats.elapsed if stats.elapsed > 0 else 1
        throughput = stats.total_checked / elapsed_sec if elapsed_sec > 0 else 0
        metrics = {
            "throughput": throughput,
            "baseline_throughput": getattr(stats, "peak_speed", throughput * 1.2),
            "error_rate": 0.0,
        }
        alert_system.check_metrics(metrics)
    except (AttributeError, RuntimeError, TypeError):
        pass


def _display_progress(hotkey_visible: bool, status_line: str, hotkey_bar: str) -> None:
    """显示进度行和快捷键栏。"""
    if hotkey_visible:
        print(f"\r{status_line}\033[K", end="", flush=True)
        print(f"\n{hotkey_bar}\033[K", end="", flush=True)
        print("\033[1A", end="", flush=True)
    else:
        print(f"\r{status_line}\033[K", end="", flush=True)


def _init_hotkey_display(listener: Any, output: Any) -> bool:
    """初始化热键显示状态，返回是否可见。"""
    if listener._available:
        return True
    from src.cli.keyboard_listener import KeyboardListener

    reason = KeyboardListener.unavailable_reason()
    output.warning(f"键盘快捷键不可用（{reason}）")
    return False


# ── 主循环 ───────────────────────────────────────────────────────────


def _run_collision_loop(
    engine: Any,
    engine_type: str,
    args: argparse.Namespace,
    total_range: int | None,
    alert_system: Any,
    stop_event: threading.Event,
) -> None:
    """主循环：定期打印进度、检查运行时长限制和告警。支持键盘交互控制。"""
    from src.cli.keyboard_listener import KeyboardListener

    output = CLIOutput.get_instance()
    start_time = time.time()
    paused: list[bool] = [False]
    pause_start: list[float | None] = [None]
    total_pause_time: list[float] = [0.0]

    listener = KeyboardListener(
        _make_key_handler(engine, engine_type, output, stop_event, paused, pause_start, total_pause_time)
    )
    listener.start()
    _suppress_console_logging()

    hotkey_bar = "\033[36m快捷键: [P]暂停  [R]恢复  [Q]退出  [S]统计\033[0m"
    hotkey_visible = _init_hotkey_display(listener, output)

    try:
        while engine.is_running() and not stop_event.is_set():
            if paused[0]:
                time.sleep(0.2)
                continue

            sleep_interval = min(float(args.progress_interval), 1.0)
            time.sleep(sleep_interval)
            if stop_event.is_set():
                break

            if engine_type == "multi_gpu":
                status_line = _format_multi_gpu_status_line(engine)
            else:
                stats = engine.get_stats()
                status_line = format_progress(stats, args.mode, total_range).replace("\n", " ")

            _display_progress(hotkey_visible, status_line, hotkey_bar)

            if not hotkey_visible:
                if engine_type != "multi_gpu":
                    _check_alerts_in_loop(alert_system, stats)  # type: ignore[possibly-unbound]
                elif alert_system is not None:
                    _check_alerts_in_loop(alert_system, engine.get_stats())

            effective_elapsed = time.time() - start_time - total_pause_time[0]
            if args.duration > 0 and effective_elapsed >= args.duration:
                print()
                print(_t("cli.main.duration_reached", seconds=args.duration))
                engine.stop()
                stop_event.set()
                break
    except KeyboardInterrupt:
        engine.stop()
        raise
    finally:
        listener.stop()
        _restore_console_logging()
        print()


# ── 现有辅助函数（保持不变）──────────────────────────────────────────


def _compute_range(
    args: argparse.Namespace,
) -> "tuple[int | None, int | None, int | None]":
    """计算范围参数，返回 (start_val, end_val, total_range) 三元组。"""
    start_val: int | None = None
    end_val: int | None = None
    total_range: int | None = None
    if args.mode in ("range", "brute_force") and args.start:
        start_val = int(args.start, 16)
    if args.mode == "range" and args.end:
        end_val = int(args.end, 16)
        if start_val is not None and end_val >= start_val:
            total_range = end_val - start_val + 1
    return start_val, end_val, total_range


def _print_config_info(
    args: argparse.Namespace,
    targets: set[str],
    start_val: int | None,
    end_val: int | None,
    total_range: int | None,
) -> None:
    """打印碰撞配置信息（使用 Rich Panel + Table 展示参数摘要）。"""
    output = CLIOutput.get_instance()

    # 确定引擎模式
    use_multi_gpu = getattr(args, "multi_gpu", False)
    use_single_gpu = getattr(args, "use_gpu", False) and not use_multi_gpu
    use_cpu = not use_multi_gpu and not use_single_gpu

    # 构建配置字典
    config_items: dict = {}
    config_items["碰撞模式"] = args.mode
    config_items["目标地址数"] = str(len(targets))
    if start_val is not None:
        config_items["起始私鑅"] = f"0x{start_val:x}"
    if end_val is not None:
        config_items["结束私鑅"] = f"0x{end_val:x}"
        config_items["搜索范围"] = f"{total_range:,} 个私鑅"

    if use_multi_gpu:
        gpu_indices = getattr(args, "gpu_indices", None)
        gpu_count = getattr(args, "gpu_count", -1)
        config_items["加速模式"] = _t("gpu.multi_gpu.enabled")
        if gpu_indices:
            config_items["GPU 设备"] = f"指定索引 {gpu_indices}"
        elif gpu_count > 0:
            config_items["GPU 设备"] = _t("gpu.multi_gpu.device_count", count=gpu_count)
        else:
            config_items["GPU 设备"] = _t("gpu.multi_gpu.device_count", count=_t("common.all"))
    elif use_single_gpu:
        gpu_device = getattr(args, "gpu_device", -1)
        gpu_batch_size = getattr(args, "gpu_batch_size", None)
        config_items["加速模式"] = _t("collision.mode.gpu")
        config_items["GPU 设备索引"] = str(gpu_device) if gpu_device >= 0 else _t("common.auto")
        config_items["GPU 批次大小"] = str(gpu_batch_size) if gpu_batch_size else _t("common.auto")
    else:
        workers = args.workers or os.cpu_count() or 4
        config_items["加速模式"] = _t("collision.mode.cpu")
        config_items["工作线程数"] = str(workers)

    config_items["断点续传"] = _t("common.enabled") if args.checkpoint else _t("common.disabled")
    config_items["去重过滤"] = _t("common.enabled") if args.dedup else _t("common.disabled")
    duration_str = f"{args.duration}秒" if args.duration > 0 else "无限制（Ctrl+C 停止）"
    config_items["运行时长"] = duration_str

    if use_cpu:
        optimize_status = _t("common.disabled") if args.no_optimize else _t("common.enabled")
        config_items["性能优化"] = f"{optimize_status} (v4.2.2)"
        if not args.no_optimize:
            config_items["预计算表"] = f"window_size={args.window_size}"
            config_items["SIMD哈希"] = _t("common.disabled") if args.no_simd else _t("common.enabled")
            config_items["内存池"] = (
                _t("common.disabled") if args.no_memory_pool else _t("common.enabled")
            )

    output.startup_panel(config_items)
