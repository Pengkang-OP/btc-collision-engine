"""Engine runner with lifecycle functions for CLI main flow."""

import hashlib
import signal
import threading
import time
from typing import Any

from ..monitoring.alert_system import AlertSystem
from ..utils import get_configured_logger

logger = get_configured_logger("EngineRunner")


def _mask_private_key(key: str, mode: str = "masked") -> str:
    """根据 sensitive_mode 对私钥进行脱敏处理。.

    Args:
        key: 原始私钥十六进制字符串
        mode: full | masked | hash_only

    Returns:
        脱敏后的私钥字符串

    """
    if not key:
        return "(空)"
    if mode == "full":
        return key
    if mode == "hash_only":
        return hashlib.sha256(key.encode()).hexdigest()[:16] + "..."
    # masked (default): 显示首尾各4位，中间用 * 代替
    if len(key) <= 8:
        star_count = max(len(key) - 4, 1)
        return key[:2] + "*" * star_count + key[-2:]
    return key[:4] + "*" * min(len(key) - 8, 12) + key[-4:]


def _compute_range(args: Any) -> tuple[Any, ...]:
    """阶段4: 计算搜索范围参数。.

    Args:
        args: 解析后的命令行参数

    Returns:
        (start_val, end_val, total_range)

    """
    mode = getattr(args, "mode", "random")
    if mode == "random":
        return None, None, None
    start_val = getattr(args, "start", "0")
    end_val = getattr(args, "end", "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140")
    try:
        total_range = int(end_val, 16) - int(start_val, 16) + 1 if start_val and end_val else None
    except (ValueError, TypeError):
        total_range = None
    return start_val, end_val, total_range


def _print_config_info(
    args: Any,
    targets: set[str],
    start_val: str | None,
    end_val: str | None,
    total_range: int | None,
) -> None:
    """阶段5: 显示运行配置摘要。."""
    from ..cli.output import CLIOutput

    output = CLIOutput.get_instance()

    sensitive_mode = getattr(args, "sensitive_mode", "masked")
    use_gpu = getattr(args, "use_gpu", False) or getattr(args, "multi_gpu", False)
    is_multi = getattr(args, "multi_gpu", False)
    duration = getattr(args, "duration", None)

    mode = getattr(args, "mode", "random")
    engine_label = "Multi-GPU" if is_multi else ("GPU" if use_gpu else "CPU")
    mode_labels = {"random": "随机扫描", "range": "范围扫描", "sequential": "顺序扫描"}
    mode_display = mode_labels.get(mode, mode)

    rows = [
        ("引擎", f"[bold]{engine_label}[/bold]"),
        ("模式", mode_display),
        ("目标数", str(len(targets))),
        ("线程", str(getattr(args, "workers", None) or "auto")),
        (
            "私钥显示",
            {"full": "完整", "masked": "脱敏", "hash_only": "仅哈希"}.get(
                sensitive_mode,
                sensitive_mode,
            ),
        ),
    ]
    extras = []
    if getattr(args, "checkpoint", False):
        extras.append("断点续传")
    if getattr(args, "dedup", False):
        extras.append("去重")
    if extras:
        rows.append(("特性", ", ".join(extras)))
    if start_val and end_val:
        rows.append(("范围", f"{start_val} … {end_val}"))
    if duration:
        rows.append(("时限", f"{duration}s"))

    output.startup_panel("运行配置", rows)
    output.success("引擎准备就绪，即将开始碰撞...")


def _setup_and_start_engine(
    args: Any,
    targets: set[str],
    config: dict[str, Any],
    start_val: str | None,
    end_val: str | None,
) -> tuple[Any, ...]:
    """阶段6: 构建引擎、初始化告警、注册信号、启动引擎。.

    Returns:
        (engine, engine_type, alert_system, stop_event)

    """
    use_gpu = getattr(args, "use_gpu", False) or getattr(args, "multi_gpu", False)
    is_multi_gpu = getattr(args, "multi_gpu", False)

    if use_gpu:
        if is_multi_gpu:
            from ..gpu.multi_gpu_engine import MultiGPUCollisionEngine

            engine = MultiGPUCollisionEngine(config=config)
            gpu_count = getattr(args, "gpu_count", 2)
            gpu_indices = getattr(args, "gpu_indices", None)
            engine.initialize(device_count=gpu_count, device_indices=gpu_indices)
            # 通过公开方法设置目标地址
            if hasattr(engine, "set_targets"):
                engine.set_targets(list(targets))
            else:
                engine._targets = list(targets)  # type: ignore[assignment]
            engine_type = "MultiGPU"
        else:
            from ..gpu.facade import GPUFacade

            # v5.2.2: 补全所有 CLI 参数传递
            engine = GPUFacade(  # type: ignore[assignment]
                targets=list(targets),
                config=config,
                checkpoint_enabled=getattr(args, "checkpoint", False),
                dedup_enabled=getattr(args, "dedup", False),
                use_performance_optimization=not getattr(args, "no_optimize", False),
                precomputed_window_size=getattr(args, "window_size", 8),
                use_simd_hash=not getattr(args, "no_simd", False),
                use_memory_pool=not getattr(args, "no_memory_pool", False),
                max_workers=getattr(args, "workers", None),
                checkpoint_interval=getattr(args, "checkpoint_interval", 30),
                dedup_max_size=getattr(args, "dedup_max_size", 1_000_000),
            )
            engine_type = "GPU"
    else:
        from ..collision.key_collision_engine import KeyCollisionEngine

        # v5.2.2: 修复 — 补全所有 CLI 参数传递
        engine = KeyCollisionEngine(  # type: ignore[assignment]
            targets=targets,
            checkpoint_enabled=getattr(args, "checkpoint", False),
            dedup_enabled=getattr(args, "dedup", False),
            use_performance_optimization=not getattr(args, "no_optimize", False),
            precomputed_window_size=getattr(args, "window_size", 8),
            use_simd_hash=not getattr(args, "no_simd", False),
            use_memory_pool=not getattr(args, "no_memory_pool", False),
            max_workers=getattr(args, "workers", None),
            checkpoint_interval=getattr(args, "checkpoint_interval", 30),
            dedup_max_size=getattr(args, "dedup_max_size", 1_000_000),
        )
        engine_type = "CPU"

    # 初始化告警系统
    alert_system = AlertSystem()
    alert_system.setup_default_rules()

    # R3: 将 AlertSystem 通过事件适配器订阅到引擎 EventBus（事件驱动告警）
    if hasattr(engine, "event_bus") and engine.event_bus is not None:
        from ..monitoring.event_adapters import AlertSystemAdapter

        alert_adapter = AlertSystemAdapter(alert_system)
        alert_adapter.subscribe_to(engine.event_bus)
        logger.debug("AlertSystem 已通过 EventBus 事件适配器集成")

    # 停止事件：用于优雅停止的跨线程通信
    stop_event = threading.Event()

    def _sig_handler(signum: Any, frame: Any) -> None:
        logger.info("收到信号 %s，开始优雅停止", signum)
        stop_event.set()
        engine.stop()

    # signal.signal() 只能在主线程中调用；此处由 CLI 主流程保证在主线程执行
    import threading as _threading

    if _threading.current_thread() is _threading.main_thread():
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    else:
        logger.warning("非主线程中跳过信号注册（信号处理不可用）")

    # 启动引擎
    if is_multi_gpu:
        mode = getattr(args, "mode", "random")
        total_keys = getattr(args, "total_keys", None) or 2**31
        engine.start(targets=set(targets), mode=mode, total_keys=total_keys)
    else:
        engine.start()  # type: ignore[call-arg]
    logger.info("%s 引擎已启动", engine_type)

    return engine, engine_type, alert_system, stop_event


def _run_collision_loop(
    engine: Any,
    engine_type: str,
    args: Any,
    total_range: int | None,
    alert_system: AlertSystem,
    stop_event: threading.Event,
) -> None:
    """阶段7: 主运行循环，使用 Rich Live 动态显示实时进度。."""
    from ..cli.keyboard_listener import check_key
    from ..cli.output import CLIOutput
    from ..cli.progress import LiveStatsDisplay

    output = CLIOutput.get_instance()
    duration = getattr(args, "duration", None)
    start_time = time.time()
    last_key_hint = 0.0

    # 初始化 Rich Live 显示
    live_display = LiveStatsDisplay(
        engine_type=engine_type,
        description=f"{engine_type} 引擎运行中",
        refresh_rate=4,
    )

    try:
        live_display.start()

        while engine.is_running() and not stop_event.is_set():
            time.sleep(0.25)  # 250ms 轮询 (配合 4Hz Live 刷新)

            # ── 键盘检测：'q' 键退出 ─────────────────────────
            key = check_key()
            if key and key.lower() == "q":
                live_display.stop()
                print()
                output.warning("收到 'q' 键退出指令，正在优雅停止引擎...")
                stop_event.set()
                engine.stop()
                break

            # ── 超时检查 ─────────────────────────────────────
            if duration and (time.time() - start_time) >= duration:
                logger.info("运行时限 %s 秒已达，停止引擎", duration)
                stop_event.set()
                engine.stop()
                break

            # ── 更新 Live 进度显示 ──────────────────────────
            try:
                stats = engine.get_stats()
                if stats:
                    keys_checked = stats.get("total_checked", 0)
                    speed = stats.get("speed", 0)
                    matches = stats.get("matches_found", 0)
                    elapsed = time.time() - start_time
                    gpu_info = ""
                    if "gpu_temp" in stats and "gpu_util" in stats:
                        gpu_info = f"{stats['gpu_temp']}C {stats['gpu_util']}%"

                    live_display.update(
                        keys_checked=keys_checked,
                        speed=speed,
                        matches=matches,
                        elapsed=elapsed,
                        gpu_info=gpu_info,
                    )

                    # 每60秒提示一次键盘操作
                    now = time.time()
                    if now - last_key_hint >= 60:
                        last_key_hint = now

                    # ── 告警检查 ──────────────────────────────
                    try:
                        alert_metrics = {
                            "throughput": speed,
                            "error_rate": stats.get("error_rate", 0),
                            "memory_usage": stats.get("memory_usage", 0),
                            "gpu_temperature": stats.get("gpu_temp", 0),
                        }
                        triggered = alert_system.check_metrics(alert_metrics)
                        for alert in triggered:
                            logger.warning(
                                "告警触发 [%s] %s: %s",
                                alert.level.value,
                                alert.alert_type.value,
                                alert.message,
                            )
                    except Exception:
                        logger.debug("告警检查失败（非致命）", exc_info=True)

            except Exception:
                logger.debug("进度显示更新失败（非致命）", exc_info=True)

        live_display.stop()

    except KeyboardInterrupt:
        live_display.stop()
        logger.info("用户中断")
        stop_event.set()
        engine.stop()
    finally:
        print()  # 确保换行


def _format_match_detail(match: dict[str, Any], sensitive_mode: str) -> str:
    """格式化单条匹配结果，应用脱敏模式。.

    Args:
        match: 匹配结果字典，可能包含 address, private_key 等字段
        sensitive_mode: full | masked | hash_only

    Returns:
        格式化后的匹配详情字符串

    """
    addr = match.get("address", match.get("target", "N/A"))
    pk = match.get("private_key", match.get("key", ""))
    pk_display = _mask_private_key(pk, sensitive_mode) if pk else "N/A"

    lines = [f"  目标地址: {addr}"]
    if pk:
        if sensitive_mode == "full":
            lines.append(f"  [bold yellow]私钥: {pk}[/bold yellow]")
        else:
            lines.append(f"  私钥({sensitive_mode}): {pk_display}")
    # 其他字段
    for field in ("timestamp", "found_at", "method"):
        val = match.get(field)
        if val:
            lines.append(f"  {field}: {val}")
    return "\n".join(lines)
