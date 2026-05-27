"""后台 GPU 结果收集器。.

实现异步流水线中的结果收集机制：
- 后台 daemon 线程持续轮询 GPU 已完成批次的匹配结果
- 主循环通过 drain_results() 非阻塞获取已收集结果
- flush_pending() 确保程序退出前无结果丢失

v5.2.3: 从 async_executor.py 提取为独立模块（代码质量优化 #M3）。
v5.2.4: 新增 _CollectorHost(Protocol) 接口，替换 36 处 # type: ignore[attr-defined]。
"""

import threading
import time
from typing import Any, Protocol, runtime_checkable

from src.utils import get_configured_logger

from ..executor_types import _PendingBatch

logger = get_configured_logger("AsyncGPUExecutor.Collector")


@runtime_checkable
class _CollectorHost(Protocol):
    """Mixin 宿主需要满足的接口协议。

    声明 _ResultCollectorMixin 通过 self 访问的所有属性，
    使 mypy 能正确推断类型，无需 type: ignore。
    """

    _collector_running: bool
    _collector_thread: threading.Thread | None
    _collector_cycles: int
    _prefetch_events: list[_PendingBatch]
    _prefetch_lock: threading.Lock
    _completed_results: list[tuple[bytes, list[dict]]]
    _completed_results_lock: threading.Lock
    _adaptive_controller: Any  # AdaptiveController 实例
    queue_depth_hits: int
    pending_event: Any | None
    _pending_buffer: Any | None
    _pending_num_keys: int


class _ResultCollectorMixin:
    """后台 GPU 结果收集器 Mixin。.

    为 AsyncGPUExecutor 提供：
    - start_result_collector / stop_result_collector
    - _result_collector_worker（后台 daemon 线程）
    - drain_results（主循环非阻塞排空）
    - flush_pending（退出时收集所有剩余）
    - _collect_oldest_batch_results_from（单批次结果收集）

    Note:
        Mixin 方法通过 self 访问 AsyncGPUExecutor 实例属性，
        如 self._prefetch_events, self._prefetch_lock, self._completed_results 等。
        所有 self 参数已标注为 _CollectorHost 协议，mypy 可正确推断类型。

    """

    def start_result_collector(self: _CollectorHost) -> None:
        """启动后台结果收集线程。.

        该线程持续主动收集 GPU 已完成的批次结果，放入 _completed_results。
        主提交循环通过 drain_results() 获取已收集结果，不再阻塞等待 GPU。
        实现效果：CPU 可以持续提交新批次，GPU 永远有工作可做（三重缓冲）。
        """
        if self._collector_running:
            return
        self._collector_running = True
        self._collector_thread = threading.Thread(
            target=self._result_collector_worker,
            name="GPUResultCollector",
            daemon=True,
        )
        self._collector_thread.start()
        logger.debug("GPU后台结果收集器已启动（主动收集）")

    def stop_result_collector(self: _CollectorHost) -> None:
        """停止后台结果收集线程并收集所有剩余结果。."""
        self._collector_running = False
        if (
            self._collector_thread is not None
            and self._collector_thread.is_alive()
            and self._collector_thread is not threading.current_thread()
        ):
            self._collector_thread.join(timeout=3.0)
            if self._collector_thread.is_alive():
                logger.warning("GPU结果收集器线程未在 3s 内退出")
        self._collector_thread = None
        logger.info(
            "GPU后台结果收集器已停止 (运行周期: %s, 待收集: %s)",
            self._collector_cycles,
            len(self._prefetch_events),
        )

    def _result_collector_worker(self: _CollectorHost) -> None:
        """后台 daemon 线程：持续主动收集 GPU 已完成的批次结果。.

        使用 get_info(COMMAND_EXECUTION_STATUS) 轮询替代阻塞 wait()，
        兼容 pyopencl 2026.1.2 中 Event.wait() 不再支持 timeout 参数的变化。
        """
        import pyopencl as cl

        while self._collector_running:
            try:
                self._collector_cycles += 1
                oldest: _PendingBatch | None = None

                with self._prefetch_lock:
                    if self._prefetch_events:
                        oldest = self._prefetch_events[0]

                if oldest is None:
                    time.sleep(0.001)
                    continue

                # 轮询事件状态（兼容 pyopencl 2026.1.2）
                try:
                    status = oldest.read_event.get_info(cl.event_info.COMMAND_EXECUTION_STATUS)
                    if status != 0:  # CL_COMPLETE = 0
                        time.sleep(0.001)
                        continue
                except TypeError:
                    oldest.read_event.wait()
                except Exception as e:
                    logger.warning("结果收集器轮询事件异常: %s", e)
                    time.sleep(0.001)
                    continue

                # GPU 已完成！收集结果
                matches: list[dict] = []
                try:
                    for i in range(oldest.num_keys):
                        if oldest.buf and oldest.buf["match_flags"][i] > 0:
                            matches.append(
                                {
                                    "key_index": i,
                                    "target_index": int(oldest.buf["match_flags"][i] - 1),
                                },
                            )
                except Exception as e:
                    logger.warning("收集批次结果异常: %s", e)

                batch_seed = getattr(oldest, "seed", None) or b""

                # 记录收集指标（用于自适应控制器）
                batch_num = getattr(oldest, "batch_num", 0)
                if batch_num > 0:
                    self._adaptive_controller.record_batch_collect(
                        batch_num=batch_num,
                        exec_time_ms=oldest.num_keys / 1000.0,
                    )

                # 从预取队列移除
                with self._prefetch_lock:
                    if self._prefetch_events and self._prefetch_events[0] is oldest:
                        self._prefetch_events.pop(0)

                # 放入已完成结果队列
                with self._completed_results_lock:
                    self._completed_results.append((batch_seed, matches))

                self.queue_depth_hits += 1

            except Exception as e:
                logger.warning("结果收集器异常: %s", e, exc_info=True)
                time.sleep(0.001)

    def drain_results(self: _CollectorHost) -> "list[tuple[bytes, list[dict]]]":
        """排空后台收集器已完成的结果。.

        Returns:
            所有已收集的 (seed, matches) 对列表。
            调用方必须使用每对中自己的 seed 重建私钥。

        """
        combined: list[tuple[bytes, list[dict]]] = []
        with self._completed_results_lock:
            if not self._completed_results:
                return combined
            combined.extend(self._completed_results)
            self._completed_results.clear()
        return combined

    def flush_pending(self: _CollectorHost) -> "list[tuple[bytes, list[dict]]]":
        """收集所有尚未取回的异步执行结果。.

        在主循环结束后调用，确保 _prefetch_events 队列中所有已提交的 GPU 批次结果不丢失。

        Returns:
            List[Tuple[bytes, List[Dict]]]：每个元素为 (seed, matches_for_that_batch)。
            调用方必须使用每批次自己的 seed 重建私钥。

        """
        batch_results: list[tuple[bytes, list[dict]]] = []

        while True:
            with self._prefetch_lock:
                if not self._prefetch_events:
                    break
                oldest = self._prefetch_events.pop(0)

            try:
                try:
                    oldest.read_event.wait(timeout=30)
                except TypeError:
                    oldest.read_event.wait()
            except RuntimeError as e:
                logger.warning("等待最后一批结果OpenCL错误: %s", e)
                continue
            except Exception as e:
                logger.warning(f"等待最后一批结果失败: {type(e).__name__}: {e}")
                continue

            if oldest.buf is not None:
                batch_matches: list[dict] = []
                for i in range(oldest.num_keys):
                    if oldest.buf["match_flags"][i] > 0:
                        batch_matches.append(
                            {"key_index": i, "target_index": int(oldest.buf["match_flags"][i] - 1)},
                        )
                batch_results.append((oldest.seed, batch_matches))

        # 清除历史兼容字段
        self.pending_event = None
        self._pending_buffer = None
        self._pending_num_keys = 0
        return batch_results

    def _collect_oldest_batch_results_from(
        self: _CollectorHost,
        batch: _PendingBatch,
    ) -> "list[tuple[bytes, list[dict]]]":
        """等待并收集批次结果（种子随匹配绑定返回）。.

        Args:
            batch: 已从 _prefetch_events 弹出的 _PendingBatch

        Returns:
            list[(seed, matches)] — 包含该批次的种子和匹配列表

        """
        prev_matches: list[tuple[bytes, list[dict]]] = []
        oldest = batch
        batch_seed = getattr(oldest, "seed", None) or b""
        timeout_seconds = 5
        try:
            completed = oldest.read_event.wait(timeout=timeout_seconds)
            if not completed:
                logger.warning("异步执行超时(%s秒)", timeout_seconds)
                raise RuntimeError(f"异步执行超时({timeout_seconds}秒)")
        except TypeError:
            logger.debug("wait()不支持timeout参数，使用无参wait()")
            oldest.read_event.wait()
        except (RuntimeError, TimeoutError):
            raise
        except Exception as wait_err:
            logger.exception(f"等待批次完成时未知异常: {type(wait_err).__name__}: {wait_err}")
            raise RuntimeError(f"异步执行失败: {wait_err}") from wait_err

        try:
            batch_matches: list[dict] = []
            for i in range(oldest.num_keys):
                if oldest.buf["match_flags"][i] > 0:
                    batch_matches.append(
                        {"key_index": i, "target_index": int(oldest.buf["match_flags"][i] - 1)},
                    )
        except (IndexError, ValueError, AttributeError) as e:
            logger.warning(f"收集批次结果数据异常: {type(e).__name__}: {e}")
        except Exception as e:
            logger.warning(f"收集批次结果失败: {type(e).__name__}: {e}")
        self.queue_depth_hits += 1
        if batch_matches:
            prev_matches.append((batch_seed, batch_matches))
        return prev_matches
