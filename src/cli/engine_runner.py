"""Engine runner with lifecycle functions for CLI main flow."""

import signal
import threading
import time
from typing import Any

from ..i18n import _t
from ..monitoring.alert_system import AlertSystem
from ..utils import get_configured_logger

logger = get_configured_logger("EngineRunner")


def _compute_range(args: Any) -> tuple:
    """阶段4: 计算搜索范围参数。

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
    """阶段5: 显示运行配置摘要。"""
    print(_t("cli.config_summary_header"))
    print(f"  模式: {getattr(args, 'mode', 'random')}")
    print(f"  目标地址数: {len(targets)}")
    print(f"  工作线程: {getattr(args, 'workers', 'auto')}")
    print(f"  GPU: {'是' if getattr(args, 'use_gpu', False) or getattr(args, 'multi_gpu', False) else '否'}")
    print(f"  断点续传: {'是' if getattr(args, 'checkpoint', False) else '否'}")
    print(f"  去重: {'是' if getattr(args, 'dedup', False) else '否'}")
    if start_val and end_val:
        print(f"  扫描范围: {start_val} ~ {end_val}")
        if total_range:
            print(f"  范围大小: {total_range:,}")
    duration = getattr(args, "duration", None)
    if duration:
        print(f"  运行时限: {duration}秒")
    print()


def _setup_and_start_engine(
    args: Any,
    targets: set[str],
    config: dict,
    start_val: str | None,
    end_val: str | None,
) -> tuple:
    """阶段6: 构建引擎、初始化告警、注册信号、启动引擎。

    Returns:
        (engine, engine_type, alert_system, stop_event)
    """
    use_gpu = getattr(args, "use_gpu", False) or getattr(args, "multi_gpu", False)
    is_multi_gpu = getattr(args, "multi_gpu", False)

    if use_gpu:
        if is_multi_gpu:
            from ..gpu.multi_gpu_engine import MultiGPUCollisionEngine

            engine = MultiGPUCollisionEngine(config=config)
            engine._targets = list(targets)
            # 从 args 获取多 GPU 配置
            gpu_count = getattr(args, "gpu_count", 2)
            gpu_indices = getattr(args, "gpu_indices", None)
            engine.initialize(device_count=gpu_count, device_indices=gpu_indices)
            engine_type = "MultiGPU"
        else:
            from ..gpu.facade import GPUFacade

            engine = GPUFacade(
                targets=list(targets),
                config=config,
                checkpoint_enabled=getattr(args, "checkpoint", False),
                dedup_enabled=getattr(args, "dedup", False),
            )
            engine_type = "GPU"
    else:
        from ..collision.key_collision_engine import KeyCollisionEngine

        engine = KeyCollisionEngine(
            targets=targets,
            checkpoint_enabled=getattr(args, "checkpoint", False),
            dedup_enabled=getattr(args, "dedup", False),
        )
        engine_type = "CPU"

    # 初始化告警系统
    alert_system = AlertSystem()
    alert_system.setup_default_rules()

    # 停止事件：用于优雅停止的跨线程通信
    stop_event = threading.Event()

    def _sig_handler(signum, frame):
        logger.info("收到信号 %s，开始优雅停止", signum)
        stop_event.set()
        engine.stop()

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # 启动引擎
    if is_multi_gpu:
        # v5.2.1: random 模式传大 total_keys 使 worker 持续运行
        mode = getattr(args, "mode", "random")
        total_keys = 2**31
        engine.start(targets=set(targets), mode=mode, total_keys=total_keys)
    else:
        engine.start()
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
    """阶段7: 主运行循环，显示实时进度。"""
    from ..cli.progress import format_progress

    duration = getattr(args, "duration", None)
    start_time = time.time()

    try:
        while engine.is_running() and not stop_event.is_set():
            time.sleep(1.0)

            # 超时检查
            if duration and (time.time() - start_time) >= duration:
                logger.info("运行时限 %s 秒已达，停止引擎", duration)
                stop_event.set()
                engine.stop()
                break

            # 进度输出
            try:
                stats = engine.get_stats()
                if stats:
                    keys_checked = stats.get("total_checked", 0)
                    speed = stats.get("speed", 0)
                    matches = stats.get("matches_found", 0)
                    elapsed = time.time() - start_time
                    progress_line = format_progress(keys_checked, speed, matches, elapsed)
                    if progress_line:
                        print(f"\r{progress_line}", end="", flush=True)
            except Exception:
                pass  # 进度显示非致命

    except KeyboardInterrupt:
        logger.info("用户中断")
        stop_event.set()
        engine.stop()
    finally:
        print()  # 换行
