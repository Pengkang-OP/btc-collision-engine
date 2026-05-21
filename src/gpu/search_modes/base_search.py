"""基础搜索模式 - BaseSearchMode

定义所有搜索模式的基类，包含通用的 _execute_batch_loop 批处理循环。
搜索模式通过引擎引用（engine reference）访问引擎状态，不复制状态。

v4.2.2: H5修复 - 设备丢失恢复失败时发布 ENGINE_ERROR 事件。
         S4改进 - WIF 导入提升到模块级别，避免循环内重复导入。
"""

import struct
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

# 统一日志获取 + 修复缺失导入
from ...utils import get_configured_logger
from ...utils.exception_handler import ExceptionHandler
from ...utils.timeout import invoke_with_timeout

# v4.2.2 S4: 将循环内 WIF 导入提升到模块级别
from ...core.wif import WIF

if TYPE_CHECKING:
    from ...collision.gpu_collision_engine import GPUCollisionEngine

logger = get_configured_logger("BaseSearchMode")


class BaseSearchMode:
    """所有搜索模式的基类

    构造函数接收引擎实例引用，通过 self.engine 访问所有引擎属性，
    避免在模块间复制状态。
    """

    def __init__(self, engine: "GPUCollisionEngine") -> None:
        """
        Args:
            engine: GPUCollisionEngine 实例引用
        """
        self.engine = engine

    # ------------------------------------------------------------------
    # 通用批处理执行循环（从 GPUCollisionEngine._execute_batch_loop 迁移）
    # ------------------------------------------------------------------

    # ── _execute_batch_loop 辅助方法（降低 C901） ────────────────

    def _process_batch_matches(
        self, matches: list, batch_data: bytes, key_extractor_fn, mode_name: str
    ) -> None:
        """处理一批 GPU 匹配结果：提取私钥、WIF 编码、触发回调。"""
        engine = self.engine
        for match in matches:
            key_idx = match["key_index"]
            if key_extractor_fn is not None:
                private_key = key_extractor_fn(batch_data, key_idx)
            else:
                if (key_idx + 1) * 32 > len(batch_data):
                    logger.warning(
                        "key_index %d 超出 batch_data 范围 (data_len=%d, mode=%s) — "
                        "可能是PRNG种子模式，请传入 key_extractor_fn 参数",
                        key_idx, len(batch_data), mode_name,
                    )
                    continue
                private_key = batch_data[key_idx * 32 : (key_idx + 1) * 32]
            target_idx = match["target_index"]
            address = engine._target_list[target_idx]
            wif = WIF.encode(private_key, compressed=True)
            engine.stats.add_match(private_key, address)
            if engine.on_match:
                timeout_val = (
                    engine._match_callback_timeout
                    if hasattr(engine, "_match_callback_timeout")
                    else 5.0
                )
                invoke_with_timeout(
                    engine.on_match,
                    args=(private_key, address, wif),
                    timeout=timeout_val,
                    callback_name="on_match",
                )

    def _handle_batch_error(
        self, error: Exception, mode_name: str
    ) -> int | None:
        """处理批量执行中的 GPU 异常，返回 batch_count 或 None（继续）。

        Returns:
            int: 应返回的 batch_count（发生致命错误时）。
            None: 应 continue 继续执行。
        """
        engine = self.engine
        ExceptionHandler.handle_gpu_error(mode_name, error, engine.stats)
        error_str = str(error).lower()

        if "out of memory" in error_str or "mem_object_allocation_failure" in error_str:
            logger.warning("GPU内存不足，尝试缩减batch_size")
            with engine._batch_size_lock:
                assert engine._batch_size is not None
                engine._batch_size = max(engine._batch_size // 2, 1024)
                logger.info(f"batch_size已缩减至 {engine._batch_size}")
            return None  # continue

        if "timeout" in error_str or "command_execution" in error_str:
            logger.warning(f"GPU执行超时: {error}")
            # fall through to error counting

        elif "device" in error_str and ("lost" in error_str or "not found" in error_str):
            recovery_mgr = (
                getattr(engine, "_recovery_manager", None)
                or getattr(engine, "gpu_recovery_manager", None)
            )
            if recovery_mgr is not None:
                try:
                    gpu_id = getattr(engine, "device_index", 0)
                    if recovery_mgr.handle_gpu_failure(gpu_id, error):
                        logger.info("GPU设备恢复成功")
                        return None  # continue
                except Exception as recovery_err:
                    logger.error(f"GPU恢复失败: {recovery_err}")
            # 恢复失败 → 停止引擎
            try:
                if hasattr(engine, "event_bus") and engine.event_bus:
                    from ...collision.events import EngineErrorEvent

                    engine.event_bus.publish(EngineErrorEvent(
                        error_type="gpu_device_lost_unrecoverable",
                        error_message=f"GPU设备丢失且恢复失败: {error}",
                        exception=error,
                        context={"gpu_id": getattr(engine, "device_index", 0)},
                        recoverable=False,
                    ))
            except (RuntimeError, AttributeError):
                logger.debug("发布 ENGINE_ERROR 事件失败（非致命）", exc_info=True)
            engine._running = False
            return engine.stats.total_checked if engine.stats else 0

        # 通用错误计数
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors += 1
            if engine._consecutive_gpu_errors >= engine._max_gpu_error_retries:
                _max_retry = engine._max_gpu_error_retries
                logger.critical(
                    f"GPU连续错误达上限({_max_retry}), 强制停止引擎防止无限循环"
                )
                engine._running = False
                return engine.stats.total_checked if engine.stats else 0
        return None  # continue

    def _execute_batch_loop(
        self,
        key_generator_fn: Callable[[], tuple[bytes, int] | None],
        mode_name: str,
        stop_condition_fn: Callable[[], bool] | None = None,
        key_extractor_fn: Callable[[bytes, int], bytes] | None = None,
    ) -> int:
        """通用批处理执行循环。"""
        engine = self.engine
        if engine.stats is None:
            raise RuntimeError("BaseSearchMode: engine.stats is None, 引擎未正确初始化")
        batch_count = 0

        while not engine._stop_event.is_set():
            if stop_condition_fn and stop_condition_fn():
                break

            gen_result = key_generator_fn()
            if gen_result is None:
                break
            batch_data, actual_batch_size = gen_result
            if not batch_data or actual_batch_size <= 0:
                break

            try:
                matches = engine._gpu_kernel.run_batch(batch_data, actual_batch_size)
                self._process_batch_matches(matches, batch_data, key_extractor_fn, mode_name)

                batch_count += actual_batch_size
                engine.stats.update(batch_count)

                with engine._batch_size_lock:
                    engine._consecutive_gpu_errors = 0

                current_time = time.time()
                if current_time - engine._last_progress_time >= engine._progress_interval_sec:
                    if engine.on_progress:
                        invoke_with_timeout(
                            engine.on_progress,
                            args=(engine.stats.snapshot(),),
                            timeout=5.0,
                            callback_name="on_progress",
                        )
                    engine._save_checkpoint(batch_count)
                    engine._last_progress_time = current_time

            except Exception as e:
                result = self._handle_batch_error(e, mode_name)
                if result is not None:
                    return result
                continue

        return batch_count

    # ------------------------------------------------------------------
    # 工具方法：高效连续私钥生成
    # ------------------------------------------------------------------

    def _generate_sequential_keys(self, start: int, count: int) -> bytes:
        """高效生成连续序列的私钥字节串

        使用预分配 bytearray + struct.pack_into 替代
        逐个 int.to_bytes() + b''.join()，减少中间列表/生成器的内存分配开销。

        Args:
            start: 起始私钥整数值
            count: 生成数量

        Returns:
            连续的私钥字节串（每个32字节，大端序），共 count * 32 字节
        """
        keys_data = bytearray(count * 32)
        offset = 0
        key_int = start
        _mask64 = 0xFFFFFFFFFFFFFFFF
        for _ in range(count):
            high = key_int >> 128
            low = key_int & ((1 << 128) - 1)
            struct.pack_into(
                ">QQQQ",
                keys_data,
                offset,
                high >> 64,
                high & _mask64,
                low >> 64,
                low & _mask64,
            )
            offset += 32
            key_int += 1
        return bytes(keys_data)
