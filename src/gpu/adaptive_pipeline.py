"""自适应流水线控制器 (Adaptive Pipeline Controller).

基于实时 GPU 性能反馈，动态调整三个核心参数：
1. queue_depth   — GPU 命令队列深度（缓冲数量）
2. batch_size    — 每批次计算量（数据大小）
3. seed_rate     — 后台种子生成速率（数据生成速度）

技术原理（参考 CUDA Streams / OpenCL OOO Queue / Micro-batching）：
- GPU 利用率 = GPU 执行时间 / (GPU 执行时间 + CPU 提交空隙)
- 保持 queue_depth 使 GPU 队列占用率在 60-80%，既充分利用又不溢出
- batch_size 使单次内核执行 20-80ms，摊平调度开销
- seed 生成速率匹配 GPU 消耗速率，避免主循环等待

设计模式：类 PID 反馈控制 + 冷却期 + 上下界限制
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("AdaptivePipeline")


@dataclass
class PipelineMetrics:
    """单次批次管道的监控指标."""

    batch_num: int
    batch_size: int
    submit_time_ms: float = 0.0  # CPU 提交耗时
    exec_time_ms: float = 0.0  # GPU 执行耗时（从 submit 到 collect）
    queue_occupancy: float = 0.0  # 提交时 _prefetch_events 占用率 (0-1)
    seed_queue_occupancy: float = 0.0  # 提交时 seed_queue 占用率 (0-1)
    timestamp: float = field(default_factory=time.time)


class AdaptivePipelineController:
    """自适应流水线控制器.

    实时监控 GPU 管道状态，通过反馈控制动态调整 queue_depth、batch_size
    和 seed 生成参数，目标是将 GPU 利用率曲线拉平。

    核心控制逻辑（每 N 批次评估一次）：
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │  采集指标       │ -> │  评估偏差        │ -> │  输出调整指令   │
    │ (submit/collect)│    │ (目标 vs 实际)   │    │ (Δdepth/size/rate)
    └─────────────────┘    └──────────────────┘    └─────────────────┘
    """

    __slots__ = (
        "_adjustment_count",
        "_batch_size",
        "_cooldown_remaining",
        "_metrics_lock",
        "_metrics_window",
        "_on_adjust_batch_size",
        "_on_adjust_queue_depth",
        "_on_adjust_seed_batch_size",
        "_queue_depth",
        "_seed_batch_size",
        "_seed_prefetch_size",
        "_start_time",
        "_window_size",
    )

    # ── 控制参数 ────────────────────────────────────────────────────
    EVAL_INTERVAL_BATCHES = 8  # 每 N 批次评估一次
    COOLDOWN_BATCHES = 4  # 调整后冷却期（避免震荡）

    # Queue depth 目标范围
    TARGET_QUEUE_OCCUPANCY_LOW = 0.55  # 低于此值 → 增加 depth
    TARGET_QUEUE_OCCUPANCY_HIGH = 0.85  # 高于此值 → 减少 depth
    QUEUE_DEPTH_MIN = 4
    QUEUE_DEPTH_MAX = 48
    QUEUE_DEPTH_STEP = 2

    # Batch size 目标：单次 GPU 执行 25-80ms
    TARGET_EXEC_TIME_MS_LOW = 15.0
    TARGET_EXEC_TIME_MS_HIGH = 80.0
    BATCH_SIZE_MIN = 65536
    BATCH_SIZE_MAX = 8388608
    BATCH_SIZE_SCALE_UP = 1.35
    BATCH_SIZE_SCALE_DOWN = 0.75

    # Seed queue 目标范围
    TARGET_SEED_OCCUPANCY_LOW = 0.25
    TARGET_SEED_OCCUPANCY_HIGH = 0.75
    SEED_BATCH_MIN = 8
    SEED_BATCH_MAX = 256
    SEED_BATCH_STEP = 8

    def __init__(
        self,
        initial_queue_depth: int = 8,
        initial_batch_size: int = 1_048_576,
        initial_seed_prefetch_size: int = 256,
        on_adjust_queue_depth: Callable[[int], None] | None = None,
        on_adjust_batch_size: Callable[[int], None] | None = None,
        on_adjust_seed_batch_size: Callable[[int], None] | None = None,
    ) -> None:
        """Initialize the adaptive pipeline.

        Args:
            initial_queue_depth: 初始队列深度
            initial_batch_size: 初始批次大小
            initial_seed_prefetch_size: 初始种子队列容量
            on_adjust_queue_depth: 队列深度调整回调(新值)
            on_adjust_batch_size: 批次大小调整回调(新值)
            on_adjust_seed_batch_size: 种子生成批量调整回调(新值)

        """
        self._queue_depth = initial_queue_depth
        self._batch_size = initial_batch_size
        self._seed_prefetch_size = initial_seed_prefetch_size

        self._on_adjust_queue_depth = on_adjust_queue_depth
        self._on_adjust_batch_size = on_adjust_batch_size
        self._on_adjust_seed_batch_size = on_adjust_seed_batch_size

        # 指标历史滑动窗口（最近 N 次）
        self._metrics_window: list[PipelineMetrics] = []
        self._window_size = self.EVAL_INTERVAL_BATCHES * 2
        self._metrics_lock = threading.Lock()

        # 调整冷却计数器
        self._cooldown_remaining = 0
        self._adjustment_count = 0

        # 当前 seed 生成批量
        self._seed_batch_size = 64

        # 启动时间
        self._start_time = time.time()

        logger.debug(
            "自适应流水线控制器已启动: queue=%d, batch=%s, seed=%d",
            self._queue_depth,
            f"{self._batch_size:,}",
            self._seed_batch_size,
        )

    # ------------------------------------------------------------------
    # 指标采集（由 AsyncGPUExecutor / RandomSearchMode 调用）
    # ------------------------------------------------------------------

    def record_batch_submit(
        self,
        batch_num: int,
        batch_size: int,
        queue_occupancy: float,
        seed_queue_occupancy: float = 0.0,
    ) -> None:
        """记录批次提交事件（主循环调用）."""
        with self._metrics_lock:
            # 查找或创建该 batch_num 的指标记录
            for m in self._metrics_window:
                if m.batch_num == batch_num:
                    m.batch_size = batch_size
                    m.queue_occupancy = queue_occupancy
                    m.seed_queue_occupancy = seed_queue_occupancy
                    m.submit_time_ms = time.time() * 1000
                    return
            self._metrics_window.append(
                PipelineMetrics(
                    batch_num=batch_num,
                    batch_size=batch_size,
                    queue_occupancy=queue_occupancy,
                    seed_queue_occupancy=seed_queue_occupancy,
                    submit_time_ms=time.time() * 1000,
                ),
            )
            self._trim_window()

    def record_batch_collect(
        self,
        batch_num: int,
        exec_time_ms: float,
    ) -> None:
        """记录批次收集事件（结果收集器调用）."""
        with self._metrics_lock:
            for m in self._metrics_window:
                if m.batch_num == batch_num:
                    m.exec_time_ms = exec_time_ms
                    return
            self._metrics_window.append(
                PipelineMetrics(
                    batch_num=batch_num,
                    batch_size=0,
                    exec_time_ms=exec_time_ms,
                ),
            )
            self._trim_window()

    def record_seed_queue_state(self, occupancy: float) -> None:
        """记录种子队列状态（RandomSearchMode 调用）.

        独立记录到最新的一条 metrics 中，或新建一条占位记录。
        """
        with self._metrics_lock:
            if self._metrics_window:
                self._metrics_window[-1].seed_queue_occupancy = occupancy
            else:
                self._metrics_window.append(
                    PipelineMetrics(
                        batch_num=0,
                        batch_size=0,
                        seed_queue_occupancy=occupancy,
                    ),
                )
            self._trim_window()

    def _trim_window(self) -> None:
        if len(self._metrics_window) > self._window_size:
            self._metrics_window = self._metrics_window[-self._window_size :]

    # ------------------------------------------------------------------
    # 自适应评估与调整（每 N 批次调用一次）
    # ------------------------------------------------------------------

    def evaluate_and_adjust(self) -> dict[str, Any]:  # noqa: C901
        """评估当前管道状态并输出调整指令.

        Returns:
            调整动作字典，如 {"queue_depth": 10, "batch_size": 1310720,
            "seed_batch": 72}

        """
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            return {}

        with self._metrics_lock:
            if len(self._metrics_window) < self.EVAL_INTERVAL_BATCHES:
                return {}  # 数据不足

            recent = self._metrics_window[-self.EVAL_INTERVAL_BATCHES :]

        adjustments: dict[str, Any] = {}

        # ── 1. Queue Depth 调整 ─────────────────────────────────────
        avg_queue_occ = sum(m.queue_occupancy for m in recent) / len(recent)
        if avg_queue_occ < self.TARGET_QUEUE_OCCUPANCY_LOW:
            new_depth = min(
                self._queue_depth + self.QUEUE_DEPTH_STEP,
                self.QUEUE_DEPTH_MAX,
            )
            if new_depth != self._queue_depth:
                adjustments["queue_depth"] = new_depth
                self._queue_depth = new_depth
                logger.debug(
                    "[自适应] queue_depth ↑ %d -> %d (队列占用率 %.1%% 过低)",
                    self._queue_depth - self.QUEUE_DEPTH_STEP,
                    new_depth,
                    avg_queue_occ * 100,
                )
        elif avg_queue_occ > self.TARGET_QUEUE_OCCUPANCY_HIGH:
            new_depth = max(
                self._queue_depth - self.QUEUE_DEPTH_STEP,
                self.QUEUE_DEPTH_MIN,
            )
            if new_depth != self._queue_depth:
                adjustments["queue_depth"] = new_depth
                self._queue_depth = new_depth
                logger.debug(
                    "[自适应] queue_depth ↓ %d -> %d (队列占用率 %.1%% 过高)",
                    self._queue_depth + self.QUEUE_DEPTH_STEP,
                    new_depth,
                    avg_queue_occ * 100,
                )

        # ── 2. Batch Size 调整 ──────────────────────────────────────
        exec_times = [m.exec_time_ms for m in recent if m.exec_time_ms > 0]
        if exec_times:
            avg_exec = sum(exec_times) / len(exec_times)
            current_bs = self._batch_size
            if avg_exec < self.TARGET_EXEC_TIME_MS_LOW:
                new_bs = min(
                    int(current_bs * self.BATCH_SIZE_SCALE_UP),
                    self.BATCH_SIZE_MAX,
                )
                if new_bs != current_bs:
                    adjustments["batch_size"] = new_bs
                    self._batch_size = new_bs
                    logger.debug(
                        "[自适应] batch_size ↑ %s -> %s (GPU执行 %.1fms 过短)",
                        f"{current_bs:,}",
                        f"{new_bs:,}",
                        avg_exec,
                    )
            elif avg_exec > self.TARGET_EXEC_TIME_MS_HIGH:
                new_bs = max(
                    int(current_bs * self.BATCH_SIZE_SCALE_DOWN),
                    self.BATCH_SIZE_MIN,
                )
                if new_bs != current_bs:
                    adjustments["batch_size"] = new_bs
                    self._batch_size = new_bs
                    logger.debug(
                        "[自适应] batch_size ↓ %s -> %s (GPU执行 %.1fms 过长)",
                        f"{current_bs:,}",
                        f"{new_bs:,}",
                        avg_exec,
                    )

        # ── 3. Seed 生成批量调整 ────────────────────────────────────
        seed_occs = [m.seed_queue_occupancy for m in recent if m.seed_queue_occupancy > 0]
        if seed_occs:
            avg_seed_occ = sum(seed_occs) / len(seed_occs)
            current_seed_batch = self._seed_batch_size
            if avg_seed_occ < self.TARGET_SEED_OCCUPANCY_LOW:
                new_sb = min(
                    current_seed_batch + self.SEED_BATCH_STEP,
                    self.SEED_BATCH_MAX,
                )
                if new_sb != current_seed_batch:
                    adjustments["seed_batch_size"] = new_sb
                    self._seed_batch_size = new_sb
                    logger.debug(
                        "[自适应] seed_batch ↑ %d -> %d (seed队列占用 %.1%% 过低)",
                        current_seed_batch,
                        new_sb,
                        avg_seed_occ * 100,
                    )
            elif avg_seed_occ > self.TARGET_SEED_OCCUPANCY_HIGH:
                new_sb = max(
                    current_seed_batch - self.SEED_BATCH_STEP,
                    self.SEED_BATCH_MIN,
                )
                if new_sb != current_seed_batch:
                    adjustments["seed_batch_size"] = new_sb
                    self._seed_batch_size = new_sb
                    logger.debug(
                        "[自适应] seed_batch ↓ %d -> %d (seed队列占用 %.1%% 过高)",
                        current_seed_batch,
                        new_sb,
                        avg_seed_occ * 100,
                    )

        # 触发回调
        if adjustments:
            self._cooldown_remaining = self.COOLDOWN_BATCHES
            self._adjustment_count += 1
            if "queue_depth" in adjustments and self._on_adjust_queue_depth:
                self._on_adjust_queue_depth(adjustments["queue_depth"])
            if "batch_size" in adjustments and self._on_adjust_batch_size:
                self._on_adjust_batch_size(adjustments["batch_size"])
            if "seed_batch_size" in adjustments and self._on_adjust_seed_batch_size:
                self._on_adjust_seed_batch_size(adjustments["seed_batch_size"])

        return adjustments

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    @property
    def queue_depth(self) -> int:
        """Get current queue depth."""
        return self._queue_depth

    @property
    def batch_size(self) -> int:
        """Get current batch size."""
        return self._batch_size

    @property
    def seed_batch_size(self) -> int:
        """Get current seed batch size."""
        return self._seed_batch_size

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline performance statistics."""
        with self._metrics_lock:
            recent = self._metrics_window[-self.EVAL_INTERVAL_BATCHES :]
            if recent:
                avg_queue = sum(m.queue_occupancy for m in recent) / len(recent)
            else:
                avg_queue = 0
            avg_exec = (
                (
                    sum(m.exec_time_ms for m in recent if m.exec_time_ms > 0)
                    / len([m for m in recent if m.exec_time_ms > 0])
                )
                if recent
                else 0
            )
            if recent:
                seed_vals = [m.seed_queue_occupancy for m in recent if m.seed_queue_occupancy > 0]
                avg_seed = sum(seed_vals) / len(seed_vals) if seed_vals else 0
            else:
                avg_seed = 0

        return {
            "queue_depth": self._queue_depth,
            "batch_size": self._batch_size,
            "seed_batch_size": self._seed_batch_size,
            "adjustment_count": self._adjustment_count,
            "cooldown_remaining": self._cooldown_remaining,
            "avg_queue_occupancy": round(avg_queue, 3),
            "avg_exec_time_ms": round(avg_exec, 2),
            "avg_seed_occupancy": round(avg_seed, 3),
            "metrics_window_size": len(self._metrics_window),
        }
