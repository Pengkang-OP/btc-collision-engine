#!/usr/bin/env python3
"""
CLI引擎构建模块

包含:
- build_engine: 根据CLI参数构建引擎实例
- on_match_callback: 匹配回调函数
- 异常类: EngineBuildError, GPUNotAvailableError, GPUInitializationError
"""

import argparse
import hashlib
import logging
import sys
from typing import Any, cast

# 统一回调类型别名
from src.collision.types import MatchCallback, ProgressCallback

logger = logging.getLogger(__name__)

from src.cli.constants import SEPARATOR_EQUAL  # noqa: E402
from src.collision import KeyCollisionEngine  # noqa: E402
from src.i18n import _t  # noqa: E402

# 密钥审计模块
from src.utils.key_audit import log_key_display  # noqa: E402


class EngineBuildError(Exception):
    """引擎构建基础异常

    所有引擎构建相关的异常都继承此类。

    Attributes:
        message: 技术错误消息（用于日志）
        user_message: 用户友好的错误消息（用于显示）
        engine_type: 相关的引擎类型（'cpu', 'gpu', 'multi_gpu'）
    """

    def __init__(
        self,
        message: str,
        user_message: str | None = None,
        engine_type: str | None = None,
    ) -> None:
        self.message = message
        self.user_message = user_message or message
        self.engine_type = engine_type
        super().__init__(message)


class GPUNotAvailableError(EngineBuildError):
    """GPU不可用异常

    当请求GPU模式但GPU环境不可用时抛出。
    例如：OpenCL未安装、GPU驱动缺失等。
    """

    def __init__(
        self,
        message: str = "GPU not available",
        user_message: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            user_message=user_message,
            engine_type="gpu",
        )


class GPUInitializationError(EngineBuildError):
    """GPU初始化失败异常

    当GPU环境可用但初始化过程中发生错误时抛出。
    例如：GPU内存不足、设备初始化失败等。
    """

    def __init__(
        self,
        message: str = "GPU initialization failed",
        user_message: str | None = None,
        engine_type: str = "gpu",
    ) -> None:
        super().__init__(
            message=message,
            user_message=user_message,
            engine_type=engine_type,
        )


try:
    import pyopencl  # noqa: F401

    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False


def on_match_callback(sensitive_mode: str = "masked") -> MatchCallback:
    """匹配回调工厂函数（高亮显示，支持脱敏模式）

    安全说明: 非交互式终端 (non-TTY) 环境下自动降级为 hash_only 模式，
    防止 stdout 重定向导致的私钥泄露。

    审计功能: 所有密钥显示操作都会被记录到审计日志。

    full 模式二次确认: 显式选择 full 模式时发出安全警告。
    """
    # 二次确认: full 模式显式选择时发出安全警告
    if sensitive_mode == "full":
        logger.warning(
            "⚠️ 已启用 full 敏感模式 — 完整私钥将显示在终端输出中。"
            "请确保当前环境安全，避免屏幕录制或日志泄露。"
        )
        if sys.stdout.isatty():
            print(
                "\n⚠️  安全警告: 已启用完整私钥输出模式 (--sensitive-mode full)。"
                "请确认终端环境安全。\n",
                file=sys.stderr,
            )

    def _callback(private_key: bytes, address: str, wif: str) -> None:
        pk_hex = private_key.hex()

        effective_mode = sensitive_mode
        if not sys.stdout.isatty():
            effective_mode = "hash_only"

        if effective_mode == "masked":
            pk_display = pk_hex[:8] + "*" * (len(pk_hex) - 16) + pk_hex[-8:]
            wif_display = wif[:4] + "*" * (len(wif) - 8) + wif[-4:]
        elif effective_mode == "hash_only":
            pk_display = "[SHA256:" + hashlib.sha256(private_key).hexdigest()[:16] + "...]"
            wif_display = "[已隐藏]"
        else:
            pk_display = pk_hex
            wif_display = wif

        # 记录密钥显示审计（不影响主流程）
        try:
            log_key_display(
                address=address,
                private_key=private_key,
                display_mode=effective_mode,
            )
        except Exception as audit_error:
            # 审计失败不应影响主流程
            logger.debug(f"密钥审计记录失败: {audit_error}")

        print("\n" + SEPARATOR_EQUAL)
        print("🎯 " + _t("cli.engine.match_found"))
        print("  " + _t("cli.engine.match_address") + f" : {address}")
        print("  " + _t("cli.engine.match_privkey") + f" : {pk_display}")
        print("  " + _t("cli.engine.match_wif") + f"      : {wif_display}")
        print(SEPARATOR_EQUAL + "\n")

    return _callback


def _create_cpu_engine(
    args: argparse.Namespace,
    targets: set[str],
    on_progress: ProgressCallback | None,
    on_match: MatchCallback | None,
    sensitive_mode: str,
) -> KeyCollisionEngine:
    """创建CPU碰撞引擎（公共函数，消除代码重复）

    提取公共逻辑，避免在多处重复相同的引擎初始化代码。

    参数:
        args: CLI参数
        targets: 目标地址集合
        on_progress: 进度回调
        on_match: 匹配回调
        sensitive_mode: 敏感模式

    返回:
        KeyCollisionEngine实例
    """
    match_cb = on_match if on_match else on_match_callback(sensitive_mode=sensitive_mode)
    progress_cb = on_progress if on_progress else lambda s: None

    return KeyCollisionEngine(
        targets=targets,
        on_progress=progress_cb,
        on_match=match_cb,
        checkpoint_enabled=args.checkpoint,
        checkpoint_interval=args.checkpoint_interval,
        dedup_enabled=args.dedup,
        dedup_max_size=args.dedup_max_size,
        max_workers=args.workers,
        use_performance_optimization=not args.no_optimize,
        precomputed_window_size=args.window_size,
        use_simd_hash=not args.no_simd,
        use_memory_pool=not args.no_memory_pool,
    )


def build_engine(
    args: argparse.Namespace,
    targets: set[str],
    on_progress: ProgressCallback | None = None,
    on_match: MatchCallback | None = None,
    sensitive_mode: str = "masked",
    config: dict | None = None,
) -> tuple[Any, str]:
    """引擎工厂：根据 CLI 参数分路 CPU / 单GPU / 多GPU 三种引擎

    Raises:
        GPUNotAvailableError: 当请求GPU模式但GPU环境不可用时
        GPUInitializationError: 当GPU初始化失败时
        EngineBuildError: 当引擎构建失败时

    Returns:
        (engine, engine_type) 元组
        engine_type: 'cpu' | 'gpu' | 'multi_gpu'
    """
    engine: Any = None

    if getattr(args, "multi_gpu", False):
        if not GPU_AVAILABLE:
            raise GPUNotAvailableError(
                message="Multi-GPU mode requires OpenCL",
                user_message=_t("cli.engine.multi_gpu_requires_opencl"),
            )
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine as _MEngine
        try:
            engine = _MEngine()
            device_indices = getattr(args, "gpu_indices", None)
            gpu_count = getattr(args, "gpu_count", -1)
            ok = engine.initialize(
                device_indices=device_indices,
                device_count=gpu_count,
                strategy="performance",
            )
            if not ok:
                raise GPUInitializationError(
                    message="Multi-GPU initialization returned False",
                    user_message=_t("cli.engine.multi_gpu_init_failed"),
                    engine_type="multi_gpu",
                )
            return engine, "multi_gpu"
        except GPUInitializationError:
            raise
        except Exception as e:
            logger.error(f"Multi-GPU initialization failed: {e}")
            raise GPUInitializationError(
                message=f"Multi-GPU initialization failed: {e}",
                user_message=f"[ERROR] Multi-GPU initialization failed: {e}\n  Check GPU drivers and OpenCL environment.",
                engine_type="multi_gpu",
            ) from e

    if getattr(args, "use_gpu", False):
        if not GPU_AVAILABLE:
            raise GPUNotAvailableError(
                message="GPU mode requires OpenCL",
                user_message=_t("cli.engine.gpu_requires_opencl"),
            )
        from src.collision.gpu_collision_engine import GPUCollisionEngine as _GEngine
        match_cb = on_match if on_match else on_match_callback(sensitive_mode=sensitive_mode)
        try:
            engine = _GEngine(
                targets=targets,
                device_index=getattr(args, "gpu_device", -1),
                batch_size=cast(int, getattr(args, "gpu_batch_size", None)),
                on_progress=on_progress if on_progress else lambda s: None,
                on_match=match_cb,
                checkpoint_enabled=args.checkpoint,
                checkpoint_interval=args.checkpoint_interval,
                dedup_enabled=args.dedup,
                dedup_max_size=args.dedup_max_size,
                use_gpu_memory_pool=True,
                use_async_logging=True,
            )
            if config:
                engine.config = config
            return engine, "gpu"
        except RuntimeError as e:
            error_msg = str(e)
            logger.warning(f"GPU initialization failed, fallback to CPU: {error_msg}")
            print("\n[WARN] GPU initialization failed, fallback to CPU mode", file=sys.stderr)
            print(f"  GPU Error: {error_msg[:200]}...", file=sys.stderr)
            engine = _create_cpu_engine(args, targets, on_progress, on_match, sensitive_mode)
            return engine, "cpu"
        except Exception as e:
            logger.error(f"GPU initialization error: {e}")
            raise GPUInitializationError(
                message=f"GPU initialization error: {e}",
                user_message=f"[ERROR] GPU initialization error: {e}\n  Try CPU mode instead.",
            ) from e

    engine = _create_cpu_engine(args, targets, on_progress, on_match, sensitive_mode)
    return engine, "cpu"
