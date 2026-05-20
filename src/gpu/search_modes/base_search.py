"""基础搜索模式 - BaseSearchMode

定义所有搜索模式的基类，包含通用的 _execute_batch_loop 批处理循环。
搜索模式通过引擎引用（engine reference）访问引擎状态，不复制状态。
"""

import struct
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

# 统一日志获取 + 修复缺失导入
from ...utils import get_configured_logger
from ...utils.exception_handler import ExceptionHandler

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

    def _execute_batch_loop(
        self,
        key_generator_fn: Callable[[], tuple[bytes, int] | None],
        mode_name: str,
        stop_condition_fn: Callable[[], bool] | None = None,
        key_extractor_fn: Callable[[bytes, int], bytes] | None = None,
    ) -> int:
        """通用批处理执行循环

        消除 _brute_force / _range_scan 中约 100 行重复的批处理执行逻辑。

        Args:
            key_generator_fn:    无参可调用对象，每次调用返回 (data_bytes, actual_batch_size)。
                                 支持两种模式：
                                 - PRNG模式（random_search）：返回 32 字节种子（seed）和批次大小。
                                 - 序列模式（brute_force/range_scan）：返回完整私钥字节串和数量。
                                 返回 None 或空字节串时终止循环。
            mode_name:           搜索模式名称，用于异常日志（如"暴力穷举"、"范围扫描"）。
            stop_condition_fn:   可选的额外停止条件检查，返回 True 表示停止。
                                 若为 None，则仅依赖 _stop_event。
            key_extractor_fn:    可选的私钥提取函数，签名为 (batch_data, key_index) -> private_key_bytes。
                                 用于 PRNG 模式下从种子+索引重建私钥。
                                 若为 None，则假设 batch_data 包含完整私钥数组。

        Returns:
            本次循环共处理的私钥总数 (batch_count)
        """
        engine = self.engine
        assert engine.stats is not None
        batch_count = 0

        while not engine._stop_event.is_set():
            # 外部停止条件（如范围扫描边界）
            if stop_condition_fn and stop_condition_fn():
                break

            # 生成本批私钥
            gen_result = key_generator_fn()
            if gen_result is None:
                break
            batch_data, actual_batch_size = gen_result
            if not batch_data or actual_batch_size <= 0:
                break

            try:
                # 执行 GPU batch 计算（支持两种模式：seed 或完整私钥字节串）
                matches = engine._gpu_kernel.run_batch(batch_data, actual_batch_size)

                # 处理匹配结果
                for match in matches:
                    key_idx = match["key_index"]
                    if key_extractor_fn is not None:
                        private_key = key_extractor_fn(batch_data, key_idx)
                    else:
                        if (key_idx + 1) * 32 > len(batch_data):
                            logger.warning(
                                "key_index %d 超出 batch_data 范围 (data_len=%d, mode=%s) — "
                                "可能是PRNG种子模式，请传入 key_extractor_fn 参数",
                                key_idx, len(batch_data), mode_name
                            )
                            continue
                        private_key = batch_data[key_idx * 32 : (key_idx + 1) * 32]
                    target_idx = match["target_index"]
                    address = engine._target_list[target_idx]
                    from ...core.wif import WIF

                    wif = WIF.encode(private_key, compressed=True)
                    engine.stats.add_match(private_key, address)
                    if engine.on_match:
                        engine.on_match(private_key, address, wif)

                # 更新统计
                batch_count += actual_batch_size
                engine.stats.update(batch_count)

                # 成功后重置连续错误计数
                with engine._batch_size_lock:
                    engine._consecutive_gpu_errors = 0

                # 定时进度回调
                current_time = time.time()
                if current_time - engine._last_progress_time >= engine._progress_interval_sec:
                    if engine.on_progress:
                        engine.on_progress(engine.stats.snapshot())
                    engine._save_checkpoint(batch_count)
                    engine._last_progress_time = current_time

            except Exception as e:
                # 保持现有的 ExceptionHandler 调用
                ExceptionHandler.handle_gpu_error(mode_name, e, engine.stats)

                # 异常分类和恢复
                error_str = str(e).lower()

                if "out of memory" in error_str or "mem_object_allocation_failure" in error_str:
                    # OOM: 缩减 batch_size
                    logger.warning("GPU内存不足，尝试缩减batch_size")
                    with engine._batch_size_lock:
                        assert engine._batch_size is not None
                        new_size = max(engine._batch_size // 2, 1024)
                        engine._batch_size = new_size
                        logger.info(f"batch_size已缩减至 {new_size}")
                    continue

                elif "timeout" in error_str or "command_execution" in error_str:
                    # 超时: 记录但继续（连续错误计数会最终处理）
                    logger.warning(f"GPU执行超时: {e}")

                elif "device" in error_str and ("lost" in error_str or "not found" in error_str):
                    # 设备丢失: 尝试 recovery_manager 恢复
                    recovery_mgr = getattr(engine, "_recovery_manager", None) or getattr(
                        engine, "gpu_recovery_manager", None
                    )
                    if recovery_mgr is not None:
                        try:
                            gpu_id = getattr(engine, "device_index", 0)
                            recovered = recovery_mgr.handle_gpu_failure(gpu_id, e)
                            if recovered:
                                logger.info("GPU设备恢复成功")
                                continue
                        except Exception as recovery_err:
                            logger.error(f"GPU恢复失败: {recovery_err}")
                    # 恢复失败，停止引擎
                    engine._running = False
                    return batch_count

                # 保持现有的连续错误计数逻辑
                with engine._batch_size_lock:
                    engine._consecutive_gpu_errors += 1
                    if engine._consecutive_gpu_errors >= engine._max_gpu_error_retries:
                        logger.critical(
                            f"GPU连续错误次数达到上限({engine._max_gpu_error_retries}), 强制停止引擎以防止无限循环"
                        )
                        engine._running = False
                        return batch_count
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
        _MASK64 = 0xFFFFFFFFFFFFFFFF
        for _ in range(count):
            high = key_int >> 128
            low = key_int & ((1 << 128) - 1)
            struct.pack_into(
                ">QQQQ",
                keys_data,
                offset,
                high >> 64,
                high & _MASK64,
                low >> 64,
                low & _MASK64,
            )
            offset += 32
            key_int += 1
        return bytes(keys_data)
