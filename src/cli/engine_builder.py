#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI引擎构建模块

包含:
- build_engine: 根据CLI参数构建引擎实例
- on_match_callback: 匹配回调函数
"""

import argparse
import hashlib
import logging
import sys
from typing import Any, Optional, Set, Tuple

# P3-3: 统一回调类型别名
from src.collision.types import ProgressCallback, MatchCallback

logger = logging.getLogger(__name__)

from src.collision import KeyCollisionEngine
from src.cli.constants import SEPARATOR_EQUAL
from src.i18n import _t

# GPU 引擎延迟导入（pyopencl 可选依赖）
try:
    from src.collision.gpu_collision_engine import GPUCollisionEngine
    from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False


def on_match_callback(sensitive_mode: str = "full") -> MatchCallback:
    """匹配回调工厂函数（高亮显示，支持脱敏模式）"""
    def _callback(private_key: bytes, address: str, wif: str) -> None:
        pk_hex = private_key.hex()

        # 根据安全模式决定私钥显示方式
        if sensitive_mode == "masked":
            pk_display = pk_hex[:8] + "*" * (len(pk_hex) - 16) + pk_hex[-8:]
            wif_display = wif[:4] + "*" * (len(wif) - 8) + wif[-4:]
        elif sensitive_mode == "hash_only":
            pk_display = "[SHA256:" + hashlib.sha256(private_key).hexdigest()[:16] + "...]"
            wif_display = "[已隐藏]"
        else:  # "full" - 默认，向后兼容
            pk_display = pk_hex
            wif_display = wif

        print("\n" + SEPARATOR_EQUAL)
        print("🎯 " + _t("cli.engine.match_found"))
        print(f"  " + _t("cli.engine.match_address") + f" : {address}")
        print(f"  " + _t("cli.engine.match_privkey") + f" : {pk_display}")
        print(f"  " + _t("cli.engine.match_wif") + f"      : {wif_display}")
        print(SEPARATOR_EQUAL + "\n")

    return _callback


def build_engine(args: argparse.Namespace, targets: Set[str], on_progress: Optional[ProgressCallback] = None, on_match: Optional[MatchCallback] = None, sensitive_mode: str = "full") -> Tuple[Any, str]:
    """引擎工厂：根据 CLI 参数分路 CPU / 单GPU / 多GPU 三种引擎

    Returns:
        (engine, engine_type) 元组
        engine_type: 'cpu' | 'gpu' | 'multi_gpu'
    """
    # ── 多GPU 模式 ──────────────────────────────────────────────
    if getattr(args, 'multi_gpu', False):
        if not GPU_AVAILABLE:
            print(_t("cli.engine.multi_gpu_requires_opencl"), file=sys.stderr)
            sys.exit(1)
        try:
            engine = MultiGPUCollisionEngine()
            device_indices = getattr(args, 'gpu_indices', None)
            gpu_count = getattr(args, 'gpu_count', -1)
            ok = engine.initialize(
                device_indices=device_indices,
                device_count=gpu_count,
                strategy='performance',
            )
            if not ok:
                print(_t("cli.engine.multi_gpu_init_failed"), file=sys.stderr)
                sys.exit(1)
            return engine, 'multi_gpu'
        except Exception as e:
            logger.error(f"Multi-GPU initialization failed: {e}")
            print(f"\n[ERROR] Multi-GPU initialization failed: {e}", file=sys.stderr)
            print(f"  Check GPU drivers and OpenCL environment.", file=sys.stderr)
            sys.exit(1)

    # ── 单GPU 模式 ──────────────────────────────────────────────
    if getattr(args, 'use_gpu', False):
        if not GPU_AVAILABLE:
            print(_t("cli.engine.gpu_requires_opencl"), file=sys.stderr)
            sys.exit(1)
        match_cb = on_match if on_match else on_match_callback(sensitive_mode=sensitive_mode)
        try:
            engine = GPUCollisionEngine(
                targets=targets,
                device_index=getattr(args, 'gpu_device', -1),
                batch_size=getattr(args, 'gpu_batch_size', None),
                on_progress=on_progress if on_progress else lambda s: None,
                on_match=match_cb,
                checkpoint_enabled=args.checkpoint,
                checkpoint_interval=args.checkpoint_interval,
                dedup_enabled=args.dedup,
                dedup_max_size=args.dedup_max_size,
                use_gpu_memory_pool=True,
                use_async_logging=True,
            )
            return engine, 'gpu'
        except RuntimeError as e:
            error_msg = str(e)
            print(f"\n[ERROR] GPU initialization failed", file=sys.stderr)
            print(f"  {error_msg}", file=sys.stderr)
            print(f"\nSuggestions:", file=sys.stderr)
            print(f"  1. Check GPU driver installation", file=sys.stderr)
            print(f"  2. Verify PyOpenCL environment", file=sys.stderr)
            print(f"  3. Try CPU mode: python key_collision_cli.py -t <address> -m random", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            logger.error(f"GPU initialization error: {e}")
            print(f"\n[ERROR] GPU initialization error: {e}", file=sys.stderr)
            print(f"  Try CPU mode instead.", file=sys.stderr)
            sys.exit(1)

    # ── CPU 模式（默认）────────────────────────────────────────
    match_cb_cpu = on_match if on_match else on_match_callback(sensitive_mode=sensitive_mode)
    engine = KeyCollisionEngine(
        targets=targets,
        on_progress=on_progress if on_progress else lambda s: None,
        on_match=match_cb_cpu,
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
    return engine, 'cpu'
