"""GPU 同步回退执行和资源管理。

实现 AsyncGPUExecutor 的同步回退模式、异步模式恢复和资源清理逻辑。

v5.2.3: 从 async_executor.py 提取为独立模块（代码质量优化 #M4）。
"""

import logging
import time
from contextlib import suppress
from typing import Any, NoReturn

import numpy as np

from ...utils import get_configured_logger
from ..executor_types import (
    ASYNC_RECOVER_AFTER_SYNC_COUNT,
    MAX_CONSECUTIVE_SYNC_FALLBACKS,
    _SyncFallbackError,
)
from ..seed_utils import _seed_bytes_to_u32_be_array

logger = get_configured_logger("AsyncGPUExecutor.SyncFallback")


class _SyncFallbackMixin:
    """同步回退执行 Mixin。

    为 AsyncGPUExecutor 提供：
    - _run_batch_sync: 纯同步 GPU 执行（PRNG 模式）
    - 多种回退入口：_run_batch_sync_fallback, _run_batch_sync_fallback_and_return, _handle_sync_fallback
    - 异步模式恢复：_track_sync_fallback, _check_async_recovery, _on_async_success
    - 资源管理：cleanup, _finish_all_queues, _wait_pending_event, _release_buffer_*

    Note:
        所有 cleanup 路径中的日志使用 _log_cleanup 包装，
        避免解释器关闭时日志基础设施已销毁导致 "句柄无效"。

    """

    @staticmethod
    def _log_cleanup(level: int, msg: str, *args: Any) -> None:
        """Cleanup 安全日志：抑制因日志基础设施关闭导致的异常。"""
        try:
            logger.log(level, msg, *args)
        except (OSError, RuntimeError, AttributeError):
            pass

    # ------------------------------------------------------------------
    # 同步执行（回退模式，PRNG 模式）
    # ------------------------------------------------------------------

    def _run_batch_sync(
        self,
        seed: bytes,
        num_keys: int,
        program: Any,
        targets_buf: Any,
        num_targets: int,
    ) -> "tuple[list[tuple[bytes, list[dict]]], float]":
        """同步执行（回退模式，PRNG 模式）。

        当异步执行失败时使用。seed 替代 private_keys。

        Returns:
            [(seed, matches)] 格式，种子随匹配绑定，与异步路径一致。

        """
        import pyopencl as cl

        start_time = time.time()

        # 写入种子到 seed_buffer
        seed_array = _seed_bytes_to_u32_be_array(seed[:32])
        cl.enqueue_copy(self.device.queue, self.seed_buffer, seed_array)

        # 使用 buffer_a 作为临时缓冲（仅匹配结果）
        temp_buf = self.buffer_a if self.buffer_a.get("matches") is not None else self.buffer_b

        try:
            cl.enqueue_fill_buffer(
                self.device.queue,
                temp_buf["matches"],
                np.int32(0),
                0,
                num_keys * 4,
            )
        except (RuntimeError, MemoryError) as e:
            logger.warning(f"同步模式下清空缓冲区OpenCL错误: {type(e).__name__}: {e}")
            if not self._try_create_fallback_buffer(temp_buf, num_keys, start_time):
                return [], (time.time() - start_time) * 1000
        except Exception as e:
            logger.warning(f"同步模式下清空缓冲区失败: {type(e).__name__}: {e}")
            if not self._try_create_fallback_buffer(temp_buf, num_keys, start_time):
                return [], (time.time() - start_time) * 1000

        try:
            batch_kernel = getattr(self, "_cached_sync_kernel", None)
            if batch_kernel is None:
                batch_kernel = cl.Kernel(program, "batch_check")
                self._cached_sync_kernel = batch_kernel
        except Exception as e:
            logger.warning(f"同步模式下创建内核失败: {type(e).__name__}: {e}")
            return [], (time.time() - start_time) * 1000

        sync_local_ws = getattr(self, "_work_group_size", 256)
        sync_global_ws = ((num_keys + sync_local_ws - 1) // sync_local_ws) * sync_local_ws

        try:
            batch_kernel(
                self.device.queue,
                (sync_global_ws,),
                (sync_local_ws,),
                self.seed_buffer,
                np.uint32(num_keys),
                targets_buf,
                np.uint32(num_targets),
                temp_buf["matches"],
                np.uint32(getattr(self, "check_uncompressed", 0)),
                self.precomp_buffer,
            )
        except Exception as e:
            logger.warning(f"同步模式内核执行失败: {type(e).__name__}: {e}")
            return [], (time.time() - start_time) * 1000

        match_flags = np.zeros(num_keys, dtype=np.int32)

        try:
            cl.enqueue_copy(self.device.queue, match_flags, temp_buf["matches"])
            self.device.queue.finish()
        except Exception as e:
            logger.warning(f"同步模式结果回读失败: {type(e).__name__}: {e}")
            return [], (time.time() - start_time) * 1000

        matches_list: list[dict] = []
        for i in range(num_keys):
            if match_flags[i] > 0:
                matches_list.append({"key_index": i, "target_index": int(match_flags[i] - 1)})

        execution_time_ms = (time.time() - start_time) * 1000
        return [(seed, matches_list)], execution_time_ms

    # ------------------------------------------------------------------
    # 回退入口（抛出 _SyncFallbackError 携带同步结果）
    # ------------------------------------------------------------------

    def _run_batch_sync_fallback(
        self,
        seed: bytes,
        num_keys: int,
        program: Any,
        targets_buf: Any,
        num_targets: int,
    ) -> NoReturn:
        """回退到同步执行并抛出结果异常（供 _allocate_buffer 使用）。"""
        matches, exec_time = self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
        self.sync_fallbacks += 1
        self._track_sync_fallback()
        raise _SyncFallbackError(matches, exec_time)

    def _run_batch_sync_fallback_and_return(
        self,
        seed: bytes,
        num_keys: int,
        program: Any,
        targets_buf: Any,
        num_targets: int,
    ) -> NoReturn:
        """回退到同步执行并抛出结果异常（供 _transfer_seed / _clear_matches_buffer 使用）。"""
        matches, exec_time = self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
        self.sync_fallbacks += 1
        self._track_sync_fallback()
        raise _SyncFallbackError(matches, exec_time)

    # ------------------------------------------------------------------
    # 异步模式恢复
    # ------------------------------------------------------------------

    def _track_sync_fallback(self) -> None:
        """追踪连续同步回退，管理异步模式禁用。"""
        self._consecutive_sync_fallbacks += 1
        if (
            self._consecutive_sync_fallbacks >= MAX_CONSECUTIVE_SYNC_FALLBACKS
            and not self._async_mode_disabled
        ):
            self._async_mode_disabled = True
            logger.warning(
                f"连续同步回退({self._consecutive_sync_fallbacks}次)超过阈值"
                f"({MAX_CONSECUTIVE_SYNC_FALLBACKS})，已禁用异步模式",
            )

    def _check_async_recovery(self) -> None:
        """检查是否可以恢复异步模式。

        当连续同步执行次数足够低时，尝试恢复异步执行。
        """
        if not self._async_mode_disabled:
            self._consecutive_sync_fallbacks = 0
            return
        current_time = time.time()
        if (
            self._consecutive_sync_fallbacks > 0
            and self._consecutive_sync_fallbacks % ASYNC_RECOVER_AFTER_SYNC_COUNT == 0
            and current_time - self._last_async_attempt_time > 30
        ):
            self._async_mode_disabled = False
            self._last_async_attempt_time = current_time
            logger.info(f"尝试恢复异步模式 (连续同步次数: {self._consecutive_sync_fallbacks})")

    def _on_async_success(self) -> None:
        """异步执行成功后重置回退计数。"""
        self.async_executions += 1
        self._consecutive_sync_fallbacks = 0
        if self._async_mode_disabled:
            self._async_mode_disabled = False
            logger.info("异步模式已恢复")

    def _is_buffer_valid(self) -> bool:
        """检查缓冲区和传输队列的有效性。"""
        if self.seed_buffer is None:
            logger.warning("种子缓冲区已释放，回退到同步模式")
            return False
        if not hasattr(self.device, "transfer_queue") or self.device.transfer_queue is None:
            logger.warning("传输队列已不可用，回退到同步模式")
            return False
        return True

    def _handle_sync_fallback(
        self,
        error: Exception,
        seed: bytes,
        num_keys: int,
        program: Any,
        targets_buf: Any,
        num_targets: int,
    ) -> NoReturn:
        """统一处理同步回退逻辑。"""
        try:
            sync_matches, sync_time = self._run_batch_sync(
                seed, num_keys, program, targets_buf, num_targets,
            )
        except Exception as sync_e:
            logger.debug(f"同步回退也失败: {type(sync_e).__name__}: {sync_e}")
            sync_matches, sync_time = [], 0.0
        self.sync_fallbacks += 1
        self._track_sync_fallback()
        raise _SyncFallbackError(sync_matches, sync_time) from error

    # ------------------------------------------------------------------
    # 缓冲区调整（_clear_matches_buffer 内部使用）
    # ------------------------------------------------------------------

    def _resize_buffer_and_clear(
        self,
        current_buf: dict[str, Any],
        num_keys: int,
        seed: bytes,
        program: Any,
        targets_buf: Any,
        num_targets: int,
    ) -> None:
        """调整缓冲区大小并清空。"""
        import pyopencl as cl

        if current_buf["matches"] is not None:
            try:
                current_buf["matches"].release()
            except Exception as e:
                logger.warning(f"释放旧缓冲区异常: {type(e).__name__}: {e}")

        try:
            current_buf["matches"] = cl.Buffer(
                self.device.context,
                cl.mem_flags.READ_WRITE,
                size=num_keys * 4,
            )
            current_buf["match_flags"] = np.zeros(num_keys, dtype=np.int32)
            logger.debug("已动态调整缓冲区大小为: %s个元素", num_keys)
        except Exception as e:
            logger.warning(f"创建新缓冲区失败: {type(e).__name__}: {e}，回退到同步模式")
            self._handle_sync_fallback(e, seed, num_keys, program, targets_buf, num_targets)

    # ------------------------------------------------------------------
    # 资源清理
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """释放所有GPU缓冲区资源。

        按安全依赖顺序执行清理：
        0. 停止后台结果收集器线程
        1. 完成所有命令队列
        2. 清理所有待处理事件
        3. 释放种子缓冲区 (seed_buffer, 32字节 PRNG)
        4. 释放预计算表常量缓冲区 (precomp_buffer)
        5. 释放缓冲区池中的所有匹配结果缓冲区
        6. 清空待处理状态字段
        """
        self.stop_result_collector()

        self._finish_all_queues()
        with self._prefetch_lock:
            self._prefetch_events.clear()

        self._wait_pending_event()

        # 释放 seed_buffer 池
        for _, sbuf in enumerate(getattr(self, "_seed_buffer_pool", [])):
            if sbuf is not None:
                with suppress(Exception):
                    sbuf.release()
        self._seed_buffer_pool = []
        self.seed_buffer = None

        self._release_buffer_safe(
            "precomp_buffer",
            lambda: self.precomp_buffer,
            lambda v: setattr(self, "precomp_buffer", v),
        )
        self._release_buffer_pool()
        self._pending_buffer = None
        self._pending_num_keys = 0
        self._log_cleanup(logging.INFO, "异步GPU执行器资源已清理")

    def _finish_all_queues(self) -> None:
        """安全地完成所有命令队列。"""
        queues = [
            ("计算", getattr(self.device, "compute_queue", None)),
            ("传输", getattr(self.device, "transfer_queue", None)),
        ]
        for name, queue in queues:
            if queue:
                try:
                    queue.finish()
                    self._log_cleanup(logging.DEBUG, "%s队列已完成所有命令", name)
                except RuntimeError as e:
                    self._log_cleanup(logging.WARNING, "完成%s队列命令OpenCL错误: %s", name, e)
                except Exception as e:
                    self._log_cleanup(logging.WARNING, f"完成{name}队列命令失败: {type(e).__name__}: {e}")

    def _wait_pending_event(self) -> None:
        """安全地等待待处理事件完成。"""
        if self.pending_event:
            try:
                self.pending_event.wait()
                self._log_cleanup(logging.DEBUG, "已等待待处理事件完成")
            except RuntimeError as e:
                self._log_cleanup(logging.WARNING, "等待待处理事件OpenCL错误: %s", e)
            except Exception as e:
                self._log_cleanup(logging.WARNING, f"等待待处理事件完成失败: {type(e).__name__}: {e}")
            self.pending_event = None

    def _release_buffer_safe(self, name: str, getter, setter) -> None:
        """安全地释放缓冲区资源。"""
        buf = getter()
        if buf is not None:
            try:
                buf.release()
                self._log_cleanup(logging.DEBUG, "已释放 %s", name)
            except RuntimeError as e:
                self._log_cleanup(logging.WARNING, "释放 %s OpenCL错误: %s", name, e)
            except Exception as e:
                self._log_cleanup(logging.WARNING, f"释放 {name} 失败: {type(e).__name__}: {e}")
            setter(None)

    def _try_create_fallback_buffer(self, buf_dict: dict, num_keys: int, start_time: float) -> bool:
        """尝试创建临时回退缓冲区并清空。"""
        import pyopencl as cl

        try:
            # 安全释放旧缓冲区
            from ._error_utils import safe_release_buffer

            safe_release_buffer(buf_dict, "matches")
            buf_dict["matches"] = None
            buf_dict["matches"] = cl.Buffer(
                self.device.context,
                cl.mem_flags.READ_WRITE,
                size=num_keys * 4,
            )
            cl.enqueue_fill_buffer(
                self.device.queue,
                buf_dict["matches"],
                np.int32(0),
                0,
                num_keys * 4,
            )
            return True
        except Exception:
            self._log_cleanup(logging.WARNING, "创建临时缓冲区失败")
            return False

    def _release_buffer_pool(self) -> None:
        """释放缓冲区池中的所有缓冲区。"""
        buf_pool = getattr(self, "_buffer_pool", None)
        if buf_pool is not None:
            for idx, buf_dict in enumerate(buf_pool):
                self._release_buffer_safe(
                    f"_buffer_pool[{idx}]['matches']",
                    lambda d=buf_dict: d.get("matches"),
                    lambda v, d=buf_dict: d.__setitem__("matches", v),
                )
                buf_dict["match_flags"] = None
            self._buffer_pool = []
        else:
            for buf_name, buf_dict in [("buffer_a", self.buffer_a), ("buffer_b", self.buffer_b)]:
                self._release_buffer_safe(
                    f"{buf_name}['matches']",
                    lambda d=buf_dict: d.get("matches"),
                    lambda v, d=buf_dict: d.__setitem__("matches", v),
                )
                buf_dict["match_flags"] = None
