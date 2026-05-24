"""GPU 批次调度与性能管理器

从 GPUCollisionEngine 中提取 GPU 批次执行、自适应调整、
进度报告和性能监控逻辑。

职责:
- GPU 批次执行（含瞬态错误重试）
- 动态性能基准计算
- 内存泄漏检测
- 自适应批次大小调整
- 进度报告与断点保存
- GPU 缓冲区动态调整
- 性能指标记录

版本: v1.1.0 Phase 6.1
创建日期: 2026-05-20
更新日期: 2026-05-23
"""

import logging
import secrets
import time
from typing import TYPE_CHECKING

from ...gpu.memory_calculator import GPUMemoryCalculator
from ...utils.error_recovery import (
    classify_recoverable_error,
    get_default_recovery_manager,
)
from ...utils.timeout import invoke_with_timeout

if TYPE_CHECKING:
    from .engine import GPUCollisionEngine

from ..events import EngineProgressEvent

logger = logging.getLogger(__name__)

# 常量
GPU_MAX_BATCH_SIZE = 0xFFFFFFFF
INITIAL_BATCH_SIZE = 1_000_000
BATCH_LOG_FREQUENCY = 100
INITIAL_BATCHES_LOG = 3
GPU_BATCH_MAX_RETRIES = 3
GPU_BATCH_RETRY_BASE_DELAY = 0.05
GPU_BATCH_RETRY_MAX_DELAY = 2.0


class GPUBatchScheduler:
    """GPU 批次调度器

    封装 GPU 批次执行、性能监控和自适应调整逻辑。
    通过 engine 引用访问所有引擎状态，不复制状态。
    """

    def __init__(self, engine: "GPUCollisionEngine") -> None:
        """初始化批次调度器

        Args:
            engine: GPUCollisionEngine 实例引用

        """
        self._engine = engine

    # ========== GPU 显存用量计算 ==========

    def calculate_gpu_memory_usage(self, num_keys: int) -> float:
        """计算 GPU 显存使用(MB)"""
        engine = self._engine
        return GPUMemoryCalculator.calculate_from_hash160_bytes(
            num_keys=num_keys,
            hash160_bytes=engine._device_manager.target_hash160s,
        )

    # ========== 性能基准 ==========

    def calculate_dynamic_benchmark(self) -> None:
        """计算动态性能基准值

        运行一个小型测试批次，测量实际 GPU 吞吐量，
        基于实测性能的80%设置动态基准值。
        """
        engine = self._engine
        try:
            test_batch_size = 100000
            seed = secrets.token_bytes(32)
            start_time = time.time()
            engine._gpu_kernel.run_batch(seed, test_batch_size)
            execution_time = time.time() - start_time
            # 防止除零：在 Mock/极速环境下 execution_time 可能为 0
            if execution_time <= 0:
                raise ZeroDivisionError(
                    f"execution_time 为 {execution_time}，疑似 Mock 或无实际计算",
                )
            actual_speed = test_batch_size / execution_time
            engine._dynamic_speed_benchmark = actual_speed * 0.8
            logger.info(f"动态性能基准计算完成: {engine._dynamic_speed_benchmark:.0f} keys/s")
        except Exception as e:
            logger.warning("动态性能基准计算失败，使用默认值: %s", e)

    # ========== 内存泄漏检查 ==========

    def check_memory_leaks(self) -> None:
        """定期检查内存泄漏"""
        engine = self._engine
        current_time = time.time()
        if current_time - engine._last_memory_check_time >= engine._memory_check_interval:
            engine._last_memory_check_time = current_time
            if hasattr(engine._gpu_kernel, "_buffer_tracker") and engine._gpu_kernel._buffer_tracker:
                try:
                    stats = engine._gpu_kernel._buffer_tracker.get_stats()
                    logger.debug(f"内存检查: {stats['count']}个缓冲区, {stats['total_size_mb']:.2f} MB")
                except Exception as e:
                    logger.error("内存泄漏检查失败: %s", e, exc_info=True)

    # ========== GPU 批次执行 ==========

    def execute_batch(
        self, seed: bytes, batch_size: int, batch_num: int,
    ) -> tuple[list[dict[str, int]], float]:
        """执行 GPU batch 计算

        P2-3.2修复: 对瞬态 OpenCL 错误（资源不足、超时）进行本地指数退避重试，
        避免瞬态错误传递到搜索模式层的高开销退避逻辑。

        Args:
            seed: 32 字节随机种子
            batch_size: 批次大小
            batch_num: 批次序号

        Returns:
            (matches, execution_time_ms) 元组

        """
        if batch_num <= INITIAL_BATCHES_LOG or batch_num % BATCH_LOG_FREQUENCY == 0:
            logger.debug("GPU batch %s: 运行 run_batch (size=%s)...", batch_num, batch_size)

        # P2-3.2修复: 瞬态错误重试循环（DEF-2增强: 集成ErrorRecoveryManager追踪）
        # W1重构: 合并RuntimeError/MemoryError与通用Exception的重试逻辑
        recovery_mgr = get_default_recovery_manager()
        last_error: Exception | None = None

        _transient_keywords = (
            "out of resources",
            "out of memory",
            "memoryerror",
            "timeout",
            "device removed",
            "cl_out_of_resources",
            "cl_mem_object_allocation_failure",
            "resource exhausted",
            "insufficient",
        )

        for retry in range(GPU_BATCH_MAX_RETRIES):
            try:
                return self.execute_batch_once(seed, batch_size, batch_num)
            except Exception as e:
                last_error = e

                if isinstance(e, (SystemExit, KeyboardInterrupt)):
                    raise

                error_msg = str(e).lower()
                error_category = classify_recoverable_error(e)
                is_transient = any(kw in error_msg for kw in _transient_keywords)

                if not is_transient or retry >= GPU_BATCH_MAX_RETRIES - 1:
                    if error_category is not None:
                        recovery_mgr.record_retry(error_category, e, retry + 1, False)
                    raise

                if error_category is not None:
                    recovery_mgr.record_retry(error_category, e, retry + 1, False)

                backoff = min(
                    GPU_BATCH_RETRY_BASE_DELAY * (2**retry),
                    GPU_BATCH_RETRY_MAX_DELAY,
                )
                logger.warning(
                    f"GPU batch {batch_num}: 瞬态错误重试 "
                    f"{retry + 1}/{GPU_BATCH_MAX_RETRIES}, "
                    f"退避 {backoff:.3f}s: {type(e).__name__}: {e}",
                )
                time.sleep(backoff)

        # 理论上不可达（for 循环总会 raise 或 return）
        raise RuntimeError("BUG: execute_batch retry loop exhausted without result") from last_error

    def execute_batch_once(
        self, seed: bytes, batch_size: int, batch_num: int,
    ) -> tuple[list[dict[str, int]], float]:
        """单次 GPU batch 执行（由 execute_batch 调用）

        Args:
            seed: 32 字节随机种子
            batch_size: 批次大小
            batch_num: 批次序号

        Returns:
            (matches, execution_time_ms) 元组

        """
        engine = self._engine
        batch_start_time = time.time()

        if engine._async_executor is not None:
            matches: list[dict[str, int]] = []
            if engine._gpu_kernel is not None:
                if hasattr(engine._gpu_kernel, "program") and hasattr(
                    engine._gpu_kernel, "_targets_buf",
                ):
                    try:
                        matches, execution_time_ms = engine._async_executor.run_batch_async(
                            seed,
                            batch_size,
                            engine._gpu_kernel.program,
                            engine._gpu_kernel._targets_buf,
                            len(engine.targets),
                        )
                    except Exception as e:
                        logger.warning("异步执行失败，回退到同步模式: %s", e)
                        matches = engine._gpu_kernel.run_batch(
                            seed, batch_size, stop_event=engine._stop_event,
                        )
                        execution_time_ms = (time.time() - batch_start_time) * 1000
                else:
                    matches = engine._gpu_kernel.run_batch(
                        seed, batch_size, stop_event=engine._stop_event,
                    )
                    execution_time_ms = (time.time() - batch_start_time) * 1000
            else:
                raise RuntimeError("GPU内核不可用，无法执行批次")
        elif engine._gpu_kernel is not None:
            matches = engine._gpu_kernel.run_batch(seed, batch_size, stop_event=engine._stop_event)
            execution_time_ms = (time.time() - batch_start_time) * 1000
        else:
            raise RuntimeError("GPU内核不可用，无法执行批次")

        # PERF-1: 检测 CPU-GPU 同步瓶颈
        expected_speed = getattr(engine, "_dynamic_speed_benchmark", 500000)
        expected_time_ms = (batch_size / expected_speed) * 1000
        threshold_ms = expected_time_ms * 1.5
        if execution_time_ms > threshold_ms:
            logger.warning(
                f"PERF-1警告: GPU batch {batch_num} 执行时间过长 "
                f"({execution_time_ms:.0f}ms > {threshold_ms:.0f}ms)",
            )

        self.check_memory_leaks()

        if batch_num <= INITIAL_BATCHES_LOG or batch_num % BATCH_LOG_FREQUENCY == 0:
            logger.debug(f"GPU batch {batch_num}: 发现 {len(matches)} 个匹配")

        return matches, execution_time_ms

    # ========== 性能指标 ==========

    def update_performance_metrics(self, batch_size: int, execution_time_ms: float) -> None:
        """记录 GPU 性能指标"""
        engine = self._engine
        if not engine.gpu_performance_monitor:
            return
        try:
            memory_mb = self.calculate_gpu_memory_usage(batch_size)
            engine.gpu_performance_monitor.record_kernel_metrics(
                batch_size=batch_size,
                execution_time_ms=execution_time_ms,
                memory_allocated_mb=memory_mb,
            )
        except Exception as e:
            logger.debug("记录GPU性能指标失败: %s", e)

    def record_adjustment(self, old_size: int, new_size: int, reason: str, details: str = "") -> None:
        """记录调整历史"""
        engine = self._engine
        engine._engine_monitor.record_adjustment(
            old_size=old_size, new_size=new_size, reason=reason, details=details,
        )

    # ========== 自适应批大小 ==========

    def maybe_adjust_batch_size(self) -> None:
        """根据运行时状态自适应调整 batch_size"""
        engine = self._engine
        if not engine._adaptive_batch_enabled:
            return
        current_time = time.monotonic()
        if current_time - engine._last_batch_adjust_time < engine._batch_adjust_interval:
            return
        engine._last_batch_adjust_time = current_time

        stats = engine.get_stats()
        total_checked = getattr(stats, "total_checked", 0)
        gpu_errors = getattr(stats, "gpu_errors", 0)
        error_rate = gpu_errors / max(total_checked, 1)
        old_batch_size = engine.batch_size

        if error_rate > engine._error_rate_threshold:
            new_size = max(engine._min_batch_size, old_batch_size // 2)
            if new_size != old_batch_size:
                engine.batch_size = new_size
                engine._adaptive_error_count = 0
                logger.warning(
                    f"自适应调整: 错误率过高({error_rate:.2%})，"
                    f"降低batch_size: {old_batch_size:,} -> {new_size:,}",
                )
        else:
            gpu_utilization = None
            if engine.gpu_performance_monitor:
                try:
                    perf_stats = engine.gpu_performance_monitor.get_stats()
                    gpu_utilization = perf_stats.get("avg_gpu_utilization")
                except (AttributeError, RuntimeError, TypeError):
                    pass  # 无法获取GPU性能统计，跳过利用率自适应调整
            if gpu_utilization is not None and 0 < gpu_utilization < 0.5:
                new_size = min(engine._max_batch_size, int(old_batch_size * 1.5))
                if new_size != old_batch_size:
                    engine.batch_size = new_size
                    logger.info(
                        f"自适应调整: GPU利用率低({gpu_utilization:.0%})，"
                        f"增大batch_size: {old_batch_size:,} -> {new_size:,}",
                    )

    # ========== 进度与断点 ==========

    def check_and_report_progress(self, batch_count: int, current_batch_size: int) -> None:
        """检查并报告进度"""
        engine = self._engine
        current_time = time.time()
        if current_time - engine._last_progress_time < engine._progress_interval_sec:
            return
        logger.debug("GPU 进度回调: batch_count=%s", batch_count)

        assert engine.stats is not None
        stats_snapshot = engine.stats.snapshot()

        # v3.2.0: 发布进度事件
        progress_event = EngineProgressEvent(
            keys_checked=stats_snapshot["total_keys_checked"],
            elapsed_seconds=stats_snapshot["elapsed_seconds"],
            throughput=stats_snapshot["throughput"],
            matches_found=stats_snapshot["total_matches"],
        )
        progress_event.source = "gpu_collision_engine"
        engine.event_bus.publish(progress_event)

        # 向后兼容: 调用传统回调（CALL-1: 超时保护）
        if engine.on_progress:
            invoke_with_timeout(
                engine.on_progress,
                args=(stats_snapshot,),
                timeout=5.0,
                callback_name="on_progress",
            )

        self.save_checkpoint(batch_count)
        engine._last_progress_time = current_time

        with engine._batch_size_lock:
            engine._consecutive_gpu_errors = 0

        if not engine._gpu_kernel:
            return

        try:
            error_rate = getattr(engine.stats, "gpu_errors", 0) / max(batch_count, 1)
            if engine._gpu_kernel and engine._gpu_kernel.gpu_optimizer:
                new_batch_size, adjustments = engine._gpu_kernel.gpu_optimizer.analyze_and_adjust(
                    current_batch_size=current_batch_size,
                    error_rate=error_rate,
                    engine=engine,
                )
                if new_batch_size != current_batch_size and adjustments:
                    reason = list(adjustments.keys())[0]
                    logger.info(
                        "自适应优化: batch_size %s -> %s (%s)",
                        current_batch_size, new_batch_size, reason,
                    )
                    engine.batch_size = new_batch_size
        except Exception as adjust_error:
            logger.debug("自适应调整失败: %s", adjust_error)

        self.maybe_adjust_batch_size()

    def save_checkpoint(self, count: int) -> None:
        """保存断点"""
        engine = self._engine
        if engine.checkpoint_mgr and engine.checkpoint_mgr.should_auto_save:
            matches_list = [
                {
                    "private_key_hash": m["private_key_hash"],
                    "address": m["address"],
                }
                for m in engine.stats.matches
            ]
            engine.checkpoint_mgr.save({
                "mode": engine._current_mode,
                "targets": list(engine.targets),
                "current_position": engine._current_position,
                "total_checked": count,
                "matches": matches_list,
                "range_start": engine._range_start,
                "range_end": engine._range_end,
            })

    # ========== GPU 缓冲区调整 ==========

    def resize_gpu_buffers(self, new_batch_size: int) -> None:
        """动态调整 GPU 缓冲区大小

        注意: 缓冲区生命周期管理分布于两处:
        - 本方法: 运行时 resize (mid-operation)
        - device_manager.cleanup(): 关闭时释放 (shutdown)
        两处通过 kernel.release_buffers() / kernel.cleanup() 协作，
        本方法在释放后将缓冲区属性置 None，避免 cleanup 时 double-free。
        """
        engine = self._engine
        try:
            old_batch_size = engine.batch_size
            logger.info(f"正在调整GPU缓冲区大小: {old_batch_size:,} -> {new_batch_size:,}")
            if engine._gpu_kernel:
                if hasattr(engine._gpu_kernel, "release_buffers"):
                    engine._gpu_kernel.release_buffers()
                else:
                    for attr in ["_match_buf", "_targets_buf"]:
                        buf = getattr(engine._gpu_kernel, attr, None)
                        if buf is not None and hasattr(buf, "release"):
                            try:
                                buf.release()
                                setattr(engine._gpu_kernel, attr, None)
                            except Exception as e:
                                logger.warning(f"释放GPU缓冲区失败 [{attr}]: {type(e).__name__}: {e}")
                engine._gpu_kernel._max_batch_size = new_batch_size
                if hasattr(engine._gpu_kernel, "_allocate_buffers"):
                    engine._gpu_kernel._allocate_buffers()
            logger.info(f"GPU缓冲区调整完成: {new_batch_size:,}")
            self.record_adjustment(old_batch_size, new_batch_size, "buffer_resize")
        except Exception as e:
            logger.error("GPU缓冲区调整失败: %s", e, exc_info=True)
            if engine._gpu_kernel:
                engine.batch_size = engine._gpu_kernel._max_batch_size
