"""随机搜索模式 - RandomSearchMode.

将 GPUCollisionEngine 中的随机搜索相关方法迁移至此独立模块，
包括同步模式（_execute_sync）和异步双缓冲模式（_execute_async）。

架构演变:
- v4.2.1: PRNG改造 — CPU仅生成32字节种子，GPU内核自行计算 key = seed + gid
  消除大型私钥数组的内存分配和 CPU-GPU 传输开销。
- v4.2.2: CPU过载保护 — 主循环内添加节流机制，防止 CPU 飞升。
- v4.5.0: 代码注释优化，文档标准化。

设计原则:
- 通过 self.engine 访问所有引擎状态，不复制状态
- 自动选择同步或异步执行模式
- 后台种子预生成线程消除 CPU-GPU 同步瓶颈
"""

import hashlib
import queue
import secrets
import threading
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

# 统一日志获取 + 修复缺失导入
from src.utils import get_configured_logger
from src.utils.exception_handler import ExceptionHandler

from .base_search import BaseSearchMode

if TYPE_CHECKING:
    # ROADMAP #13: 使用协议接口替代直接引用，消除反向依赖
    from src.gpu._engine_protocol import GPUEngineProtocol as GPUCollisionEngine

logger = get_configured_logger("RandomSearchMode")

# 与 gpu_collision_engine 保持一致的常量
INITIAL_BATCH_SIZE = 1_000_000
EXCEPTION_RECOVERY_DELAY = 0.1

# CPU过载保护参数
CPU_OVERLOAD_THRESHOLD = 95.0  # 提高阈值，减少不必要节流
CPU_THROTTLE_SLEEP = 0.01  # 减少节流时间
MIN_BATCH_INTERVAL_SEC = 0.0005  # 减少批次间隔
PSUTIL_CHECK_INTERVAL = 200  # v5.2.1: 每N批次检查一次CPU使用率（减少系统调用开销）
EXP_BACKOFF_BASE = 0.1  # 指数退避基础延迟(s)
EXP_BACKOFF_MAX = 30.0  # 指数退避最大延迟(s)

# 种子预生成参数 - v5.1优化：大幅提升以匹配高 GPU 队列深度
SEED_PREFETCH_SIZE = 256  # 增大缓存深度，匹配 GPU queue_depth=32+
SEED_BATCH_GENERATE_SIZE = 64  # 每次批量生成更多种子
SEED_PREFILL_ON_START = True  # 启动时预填充队列
SEED_MIN_QUEUE_SIZE = 48  # v5.2.0: 提高阈值 (原20)，匹配高 GPU queue_depth (Intel Arc=32/64)

# CPU过载保护参数

# 已弃用常量（历史兼容保留，PRNG模式下不再需要）

__all__ = [
    "ASYNC_KEY_GEN_BASE_TIMEOUT",
    "ASYNC_KEY_GEN_PER_KEY_TIME",
    "ASYNC_KEY_GEN_SAFETY_FACTOR",
    "CPU_OVERLOAD_THRESHOLD",
    "CPU_THROTTLE_SLEEP",
    "EXCEPTION_RECOVERY_DELAY",
    "EXP_BACKOFF_BASE",
    "EXP_BACKOFF_MAX",
    "INITIAL_BATCH_SIZE",
    "MIN_BATCH_INTERVAL_SEC",
    "PSUTIL_CHECK_INTERVAL",
    "SEED_BATCH_GENERATE_SIZE",
    "SEED_MIN_QUEUE_SIZE",
    "SEED_PREFETCH_SIZE",
    "SEED_PREFILL_ON_START",
    "RandomSearchMode",
]

ASYNC_KEY_GEN_BASE_TIMEOUT = 5.0
ASYNC_KEY_GEN_PER_KEY_TIME = 0.00001
ASYNC_KEY_GEN_SAFETY_FACTOR = 2.0


class RandomSearchMode(BaseSearchMode):
    """随机搜索模式.

    对应原 GPUCollisionEngine 中的 _random_search_sync / _random_search_async 方法。
    通过 self.engine 访问所有引擎状态，不复制状态。

    v4.2.1 新增：后台种子预生成线程，维护 maxsize=5 的种子缓存队列，
    消除主循环中 os.urandom() 的阻塞等待，进一步平滑 GPU 利用率。
    """

    __slots__ = (
        "_adaptive_controller",
        "_seed_generated_count",
        "_seed_generation_errors",
        "_seed_prefetch_size",
        "_seed_queue",
        "_seed_stop_event",
        "_seed_thread",
        "_seed_used_count",
    )

    def __init__(
        self,
        engine: "GPUCollisionEngine",
        seed_prefetch_size: int = SEED_PREFETCH_SIZE,
        adaptive_controller: Any = None,
    ) -> None:
        """初始化随机搜索模式。."""
        super().__init__(engine)
        self._seed_prefetch_size = seed_prefetch_size
        self._adaptive_controller = adaptive_controller
        # 种子预生成队列与线程
        self._seed_queue: queue.Queue = queue.Queue(maxsize=seed_prefetch_size)
        self._seed_stop_event: threading.Event = threading.Event()
        self._seed_thread: threading.Thread | None = None

        # 种子统计信息
        self._seed_generated_count = 0
        self._seed_used_count = 0
        self._seed_generation_errors = 0

        # 启动时预填充队列（同步，不涉及线程）
        if SEED_PREFILL_ON_START:
            self._prefill_seed_queue()

        # 线程延迟启动：在 execute() 中按需启动，避免测试中创建实例就产生线程
        # self._start_seed_prefetch_thread()  # 移到 _ensure_seed_thread_running()

        ctrl_info = ", 自适应控制=启用" if adaptive_controller else ""
        logger.debug("随机搜索模式已初始化 (种子深度=%s%s)", seed_prefetch_size, ctrl_info)

    def _start_seed_prefetch_thread(self) -> None:
        """启动后台种子预生成 daemon 线程（幂等：已启动则跳过）."""
        if self._seed_thread is not None and self._seed_thread.is_alive():
            return
        self._seed_stop_event.clear()
        self._seed_thread = threading.Thread(
            target=self._seed_prefetch_worker,
            name="SeedPrefetch",
            daemon=True,
        )
        self._seed_thread.start()
        logger.debug("种子预生成线程已启动 (缓存深度=%d)", self._seed_prefetch_size)

    def _ensure_seed_thread_running(self) -> None:
        """确保种子预生成线程在运行（在 execute() 入口调用）."""
        if self._seed_thread is None or not self._seed_thread.is_alive():
            self._start_seed_prefetch_thread()

    def _prefill_seed_queue(self) -> None:
        """启动时预填充种子队列.

        v5.1: 预填充更大比例（1/4 队列），确保启动后 GPU 不被种子等待阻塞。
        """
        if not SEED_PREFILL_ON_START:
            return
        # 预填充 1/4 队列或 SEED_MIN_QUEUE_SIZE*4，取较大值
        prefill_count = max(SEED_MIN_QUEUE_SIZE * 4, self._seed_prefetch_size // 4)
        prefill_count = min(prefill_count, self._seed_prefetch_size)
        if prefill_count <= 0:
            return

        logger.debug("预填充种子队列: %d 个种子", prefill_count)
        prefilled = 0

        try:
            # 批量生成种子，精确控制数量
            while prefilled < prefill_count and not self._seed_stop_event.is_set():
                remaining = prefill_count - prefilled
                batch = min(SEED_BATCH_GENERATE_SIZE, remaining)
                seeds = self._generate_seed_batch(batch)
                for seed in seeds:
                    if self._seed_queue.full():
                        break
                    # MEDIUM-4修复: 使用非阻塞put_nowait保持与_seed_prefetch_worker一致
                    try:
                        self._seed_queue.put_nowait(seed)
                    except queue.Full:
                        break
                    prefilled += 1
                    self._seed_generated_count += 1

            logger.info("预填充完成: %s/%s", prefilled, prefill_count)
        except Exception as e:
            logger.warning("种子预填充失败: %s", e)

    def _generate_seed_batch(self, count: int) -> list[bytes]:
        """批量生成种子（高效）."""
        seeds = []
        try:
            # 一次性读取大块随机数据，然后分割
            total_bytes = count * 32
            random_data = secrets.token_bytes(total_bytes)

            for i in range(count):
                start = i * 32
                end = start + 32
                seeds.append(random_data[start:end])
        except OSError as e:
            logger.warning("批量种子生成失败: %s", e)
            # 降级到逐个生成
            for _ in range(count):
                try:
                    seeds.append(secrets.token_bytes(32))
                except OSError:
                    break

        return seeds

    def _seed_prefetch_worker(self) -> None:
        """后台线程：持续填充种子队列 - v5.1.2 自适应速率版."""
        while not self._seed_stop_event.is_set():
            try:
                current_size = self._seed_queue.qsize()

                # v5.2.3: 防御性检查 — 当 qsize() 返回 MagicMock（测试环境）时跳过
                if not isinstance(current_size, int):
                    current_size = SEED_MIN_QUEUE_SIZE

                # v5.1.2: 使用自适应控制器推荐的批量大小
                dynamic_batch = SEED_BATCH_GENERATE_SIZE
                if self._adaptive_controller is not None:
                    dynamic_batch = self._adaptive_controller.seed_batch_size

                if current_size < SEED_MIN_QUEUE_SIZE:
                    needed = min(
                        dynamic_batch * 2,
                        self._seed_prefetch_size - current_size,
                    )
                    seeds = self._generate_seed_batch(needed)
                    for seed in seeds:
                        if self._seed_queue.full():
                            break
                        self._seed_queue.put_nowait(seed)
                        self._seed_generated_count += 1
                else:
                    batch_size = min(dynamic_batch, self._seed_prefetch_size - current_size)
                    if batch_size > 0:
                        seeds = self._generate_seed_batch(batch_size)
                        for seed in seeds:
                            if self._seed_queue.full():
                                break
                            self._seed_queue.put_nowait(seed)
                            self._seed_generated_count += 1
                    else:
                        time.sleep(0.001)

            except OSError as e:
                self._seed_generation_errors += 1
                logger.warning("种子预生成失败: %s", e)
                time.sleep(0.01)
            except Exception as e:
                self._seed_generation_errors += 1
                logger.warning("种子预生成线程意外错误: %s", e)
                time.sleep(0.01)
        logger.debug("种子预生成线程已退出")

    def _generate_seed(self) -> bytes:
        """获取一个预生成的种子（从队列）."""
        while not self.engine._stop_event.is_set():
            try:
                seed = self._seed_queue.get(timeout=1.0)
                self._seed_used_count += 1
                return seed
            except queue.Empty:
                logger.debug("种子队列为空，等待补充...")
                continue

        raise RuntimeError("种子生成被中断")

    def get_seed_stats(self) -> dict[str, int]:
        """获取种子生成统计信息."""
        return {
            "generated": self._seed_generated_count,
            "used": self._seed_used_count,
            "errors": self._seed_generation_errors,
            "queue_size": self._seed_queue.qsize(),
        }

    def stop(self) -> None:
        """停止种子预生成线程和执行循环（cleanup 入口）."""
        # 停止种子预生成线程
        self._seed_stop_event.set()
        if self._seed_thread is not None and self._seed_thread.is_alive():
            self._seed_thread.join(timeout=2.0)
            if self._seed_thread.is_alive():
                logger.warning("种子预生成线程未在 2s 内退出")
        self._seed_thread = None
        logger.info("种子预生成线程已停止")

        # 确保引擎的停止事件被设置，停止执行循环
        if hasattr(self.engine, "_stop_event"):
            self.engine._stop_event.set()
        if hasattr(self.engine, "_running"):
            self.engine._running = False

    def execute(self) -> None:
        """执行随机搜索（入口，自动选择同步或异步模式）."""
        engine = self.engine

        # 确保种子预生成线程已启动（延迟初始化）
        self._ensure_seed_thread_running()

        # 检查异步执行器是否可用
        if hasattr(engine, "_async_executor") and engine._async_executor is not None:
            logger.debug("使用GPU异步执行模式（双缓冲优化）")
            self._execute_async()
        else:
            logger.debug("使用GPU同步执行模式")
            self._execute_sync()

    # ------------------------------------------------------------------
    # 同步执行模式
    # ------------------------------------------------------------------

    def _execute_sync(self) -> None:
        """同步执行版本 (PRNG + CPU过载保护).

        PRNG模式: CPU仅生成32字节种子, GPU内核自行计算 key = seed + gid。
        CPU过载保护: 批次间最小间隔 + psutil CPU使用率节流 + 指数退避。
        """
        import psutil

        engine = self.engine
        if engine.stats is None:
            raise RuntimeError(
                "RandomSearchMode._random_search(): engine.stats is None, 引擎未正确初始化",
            )
        logger.info("GPU _random_search 启动 (PRNG + CPU过载保护模式)")

        batch_count = 0
        batch_num = 0
        consecutive_errors = 0
        # 使用engine.targets作为目标地址列表
        target_list = list(engine.targets)
        num_targets = len(target_list)
        current_batch_size = engine.batch_size

        # 确保current_batch_size不为None
        if current_batch_size is None:
            current_batch_size = 1000000  # 默认批次大小
        logger.info(f"目标数量: {num_targets}, 初始批次大小: {current_batch_size:,}")

        while not engine._stop_event.is_set():
            batch_start_time = time.monotonic()

            try:
                batch_num += 1
                engine.stats.set_total_batches(batch_num)

                # 检查停止信号，避免在资源已释放后执行批处理
                if engine._stop_event.is_set():
                    break

                # PRNG: 仅生成32字节种子, GPU内核自行展开为 key = seed + gid
                seed = self._generate_seed()

                # 再次检查停止信号
                if engine._stop_event.is_set():
                    break

                # 执行GPU batch计算
                matches, execution_time_ms = engine._execute_gpu_batch(
                    seed,
                    current_batch_size,
                    batch_num,
                )

                # 重置连续错误计数
                consecutive_errors = 0

                # 根据 seed 和 key_index 重建私钥
                engine._process_gpu_matches_prng(seed, matches)

                # 更新统计数据
                batch_count += current_batch_size
                engine.stats.update(batch_count)
                engine._current_position = batch_count

                # 记录性能指标
                engine._update_performance_metrics(current_batch_size, execution_time_ms)

                # 检查并报告进度
                engine._check_and_report_progress(batch_count, current_batch_size)

                # ------ CPU过载保护 ------
                # 1. 批次间最小间隔保护
                elapsed = time.monotonic() - batch_start_time
                if elapsed < MIN_BATCH_INTERVAL_SEC:
                    time.sleep(MIN_BATCH_INTERVAL_SEC - elapsed)

                # 2. CPU使用率节流 (v5.2.1: 每 N 批次检查一次，减少系统调用开销)
                try:
                    if batch_num % PSUTIL_CHECK_INTERVAL == 0:
                        cpu_pct = psutil.cpu_percent(interval=None)
                        if cpu_pct > CPU_OVERLOAD_THRESHOLD:
                            logger.debug(
                                f"CPU使用率 {cpu_pct:.1f}% 超过阈值 "
                                f"{CPU_OVERLOAD_THRESHOLD}%, 节流 {CPU_THROTTLE_SLEEP}s",
                            )
                            time.sleep(CPU_THROTTLE_SLEEP)
                except OSError:
                    pass  # psutil 不可用时忽略

            except Exception as e:
                ExceptionHandler.handle_gpu_error("随机碰撞", e, engine.stats)

                consecutive_errors += 1
                backoff = min(EXP_BACKOFF_BASE * (2 ** min(consecutive_errors - 1, 8)), EXP_BACKOFF_MAX)
                logger.warning(
                    f"GPU batch {batch_num}: 异常 (连续第{consecutive_errors}次), 退避 {backoff:.2f}s",
                )
                time.sleep(backoff)
                continue

        logger.info("GPU _random_search 结束: 共处理 %s 个私钥", batch_count)
        engine._running = False
        engine.stats.update(batch_count)
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())

    # ------------------------------------------------------------------
    # 异步双缓冲执行模式
    # ------------------------------------------------------------------

    # ========================================================================
    # 辅助函数 - 拆分自 _execute_async
    # ========================================================================

    def _detect_gpu_model(self, engine: Any) -> str:
        """检测GPU型号（v5.2.0: 委托给 AsyncGPUExecutor，消除 ~50 行重复检测逻辑）."""
        if hasattr(engine, "_async_executor") and engine._async_executor:
            executor = engine._async_executor
            if hasattr(executor, "_detect_gpu_model"):
                return executor._detect_gpu_model()
        return "default"

    def _check_engine_availability(self, engine: Any) -> bool:
        """检查引擎组件是否可用."""
        if not hasattr(engine, "_async_executor") or engine._async_executor is None:
            logger.warning("异步执行器不可用")
            return False
        if not hasattr(engine, "_gpu_kernel") or engine._gpu_kernel is None:
            logger.warning("GPU内核不可用")
            return False
        if not hasattr(engine._gpu_kernel, "_targets_buf") or engine._gpu_kernel._targets_buf is None:
            logger.warning("目标缓冲区不可用")
            return False
        return True

    def _handle_batch_execution(
        self,
        engine: Any,
        seed: bytes,
        batch_size: int,
        batch_optimizer: Any,
        batch_num: int,
    ) -> "tuple[list[tuple[bytes, list[dict]]], float]":
        """执行单个批次并返回结果（v5.2.0: 每批次种子随匹配绑定）.

        Returns:
            (batch_results, execution_time_ms)
            batch_results: list of (seed, matches) pairs from previously collected batches

        """
        batch_results: list[tuple[bytes, list[dict]]]
        batch_results, execution_time_ms = engine._async_executor.run_batch_async(
            seed,
            batch_size,
            engine._gpu_kernel.program,
            engine._gpu_kernel._targets_buf,
            len(engine.targets),
        )
        return batch_results, execution_time_ms

    def _record_performance_data(
        self,
        engine: Any,
        batch_optimizer: Any,
        batch_size: int,
        execution_time_ms: float,
        speed: float,
    ) -> None:
        """记录性能数据."""
        # 内存使用
        if hasattr(engine, "_gpu_device") and engine._gpu_device:
            device_info = engine._gpu_device.get_device_info()
            if "global_mem_size" in device_info:
                total_memory_mb = device_info["global_mem_size"] / (1024 * 1024)
                batch_optimizer.record_memory_usage(total_memory_mb * 0.7, total_memory_mb)
        # 系统负载
        with suppress(OSError):
            import psutil

            cpu_load = psutil.cpu_percent(interval=None) / 100.0
            gpu_load = min(speed / 1000000, 1.0)
            batch_optimizer.record_system_load(cpu_load, gpu_load)
        # 性能记录
        batch_optimizer.record_performance(batch_size, execution_time_ms, speed)

    def _handle_batch_error(  # type: ignore[override]
        self,
        e,
        engine,
        batch_num,
        consecutive_errors,
    ) -> int:
        """处理批次执行错误."""
        if isinstance(e, KeyboardInterrupt):
            logger.info("用户中断，停止异步执行")
            return -1  # 表示中断
        ExceptionHandler.handle_gpu_error("随机碰撞(异步)", e, engine.stats)
        consecutive_errors += 1
        backoff = min(EXP_BACKOFF_BASE * (2 ** min(consecutive_errors - 1, 8)), EXP_BACKOFF_MAX)
        logger.warning(
            f"GPU batch {batch_num}: 异常 (连续第{consecutive_errors}次), 退避 {backoff:.2f}s",
        )
        time.sleep(backoff)
        return consecutive_errors

    # ── _execute_async 辅助方法（降低 C901） ──────────────────────

    # v5.2.4: 修正返回类型注解 tuple[dict, int, str, Any]（原本漏掉 batch_optimizer 的第4个返回值）
    def _setup_async_buffers(self, engine: Any, current_batch_size: int) -> tuple[dict, int, str, Any]:
        """初始化双缓冲区和 GPU 型号检测。."""
        gpu_model = self._detect_gpu_model(engine)
        from ..batch_size_optimizer import get_batch_size_optimizer

        batch_optimizer = get_batch_size_optimizer(engine.batch_size or 1048576, gpu_model=gpu_model)

        if hasattr(engine, "_async_executor") and engine._async_executor:
            actual_batch_size = engine._async_executor.get_actual_batch_size()
            if (
                isinstance(current_batch_size, int)
                and isinstance(actual_batch_size, int)
                and current_batch_size > actual_batch_size
            ):
                logger.warning("batch_size超过GPU缓冲区大小，使用缓冲区大小: %s", actual_batch_size)
                current_batch_size = actual_batch_size

        buffer_data = {
            "A": {"seed": self._generate_seed(), "batch_size": current_batch_size},
            "B": {"seed": None, "batch_size": current_batch_size},
        }
        return buffer_data, current_batch_size, "A", batch_optimizer

    def _run_async_batch_cycle(
        self,
        engine: Any,
        batch_optimizer: Any,
        buffer_data: dict,
        current_buffer: str,
        current_batch_size: int,
        batch_num: int,
        consecutive_errors: int,
    ) -> tuple[int, str, int, int, bool, int]:
        """执行一次异步批处理周期。.

        Returns:
            (current_batch_size, current_buffer, batch_num,
             consecutive_errors, should_break, batch_size_used)

        """
        batch_size = 0  # 默认，防止 try 内异常导致 UnboundLocalError
        try:
            next_buffer = "B" if current_buffer == "A" else "A"
            buffer_data[next_buffer]["seed"] = self._generate_seed()
            buffer_data[next_buffer]["batch_size"] = current_batch_size
            batch_num += 1
            engine.stats.set_total_batches(batch_num)

            if batch_num % 10 == 0:
                current_batch_size = batch_optimizer.get_optimal_batch_size()

            seed = buffer_data[current_buffer]["seed"]
            batch_size = buffer_data[current_buffer]["batch_size"]

            # v5.1.2: 向自适应控制器报告 seed 队列状态
            if self._adaptive_controller is not None:
                seed_occ = self._seed_queue.qsize() / max(self._seed_prefetch_size, 1)
                self._adaptive_controller.record_seed_queue_state(seed_occ)

            batch_results, execution_time_ms = self._handle_batch_execution(
                engine,
                seed,
                batch_size,
                batch_optimizer,
                batch_num,
            )

            if engine._stop_event.is_set():
                return current_batch_size, current_buffer, batch_num, consecutive_errors, True, 0

            # v5.2.0 FIX: 每批次的种子与匹配结果绑定返回，
            # 使用每批次自己的 seed 重建私钥，而不是外层的当前 seed。
            if batch_results:
                for batch_seed, batch_matches in batch_results:
                    if batch_matches:
                        engine._process_gpu_matches_prng(batch_seed, batch_matches)

            if engine._stop_event.is_set():
                return current_batch_size, current_buffer, batch_num, consecutive_errors, True, 0

            effective_time_ms = max(execution_time_ms, 0.001)
            speed = batch_size / (effective_time_ms / 1000)
            # v5.1: 日志和性能记录降频，减少主循环开销
            if batch_num <= 5 or batch_num % 50 == 0:
                logger.debug(
                    f"GPU batch {batch_num}: {batch_size:,} keys, "
                    f"{execution_time_ms:.2f}ms, {speed:.0f} keys/s",
                )
            if batch_num % 10 == 0:
                self._record_performance_data(
                    engine,
                    batch_optimizer,
                    batch_size,
                    execution_time_ms,
                    speed,
                )
            consecutive_errors = 0
            current_buffer = next_buffer

        except Exception as e:
            result = self._handle_batch_error(e, engine, batch_num, consecutive_errors)
            if result == -1:
                return current_batch_size, current_buffer, batch_num, consecutive_errors, True, 0
            consecutive_errors = result
            if engine._stop_event.is_set():
                return current_batch_size, current_buffer, batch_num, consecutive_errors, True, 0

        return current_batch_size, current_buffer, batch_num, consecutive_errors, False, batch_size

    def _execute_async(self) -> None:
        """异步执行版本（v5.1 流水线并行 + PRNG + CPU过载保护）。.

        v5.1 优化:
        - 后台结果收集器持续主动收集 GPU 完成批次（消除主循环阻塞）
        - CPU过载检测降频到每10批次（减少 psutil 开销）
        - stats 更新降频到每批次累计（减少属性访问开销）
        """
        engine = self.engine
        if engine.stats is None:
            raise RuntimeError(
                "RandomSearchMode._execute_async(): engine.stats is None, 引擎未正确初始化",
            )

        if not self._check_engine_availability(engine):
            logger.warning("异步执行器不可用，回退到同步模式")
            self._execute_sync()
            return

        logger.debug("启动GPU异步执行模式 (v5.1 流水线并行 + 后台收集器)")
        current_batch_size = engine.batch_size or 1000000
        buffer_data, current_batch_size, current_buffer, batch_optimizer = self._setup_async_buffers(
            engine,
            current_batch_size,
        )

        batch_count = 0
        batch_num = 0
        consecutive_errors = 0

        try:
            import psutil

            while not engine._stop_event.is_set():
                # v5.1: CPU过载检测降频到每10批次，减少 psutil 开销
                if batch_num % 10 == 0:
                    with suppress(OSError):
                        cpu_pct = psutil.cpu_percent(interval=None)
                        if cpu_pct > CPU_OVERLOAD_THRESHOLD:
                            logger.debug(f"CPU使用率 {cpu_pct:.1f}% 超过阈值，节流")
                            current_batch_size = max(current_batch_size // 2, 10000)
                            time.sleep(CPU_THROTTLE_SLEEP)

                if not self._check_engine_availability(engine):
                    self.stop()
                    self._execute_sync()
                    return

                (
                    current_batch_size,
                    current_buffer,
                    batch_num,
                    consecutive_errors,
                    should_break,
                    batch_size_used,
                ) = self._run_async_batch_cycle(
                    engine,
                    batch_optimizer,
                    buffer_data,
                    current_buffer,
                    current_batch_size,
                    batch_num,
                    consecutive_errors,
                )
                if should_break:
                    break
                batch_count += batch_size_used

                # v5.1: stats 更新降频，减少属性访问开销
                if batch_num % 5 == 0:
                    engine.stats.update(batch_count)
                engine._current_position = batch_count

        except KeyboardInterrupt:
            logger.info("用户中断，停止异步执行")
        except Exception as e:
            logger.error("异步执行模式异常: %s", e, exc_info=True)
        finally:
            self.stop()
            logger.info(f"智能批次优化器统计: {batch_optimizer.get_stats()}")

        logger.info("GPU异步执行结束: 共处理 %s 个私钥", batch_count)
        engine._running = False
        engine.stats.update(batch_count)
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())

    def _process_matches(self, matches: list[dict[str, int]], seed: bytes, batch_size: int) -> None:
        """处理匹配结果.

        注意: 此方法当前为死代码，无任何调用者。
        保留用于未来重构。
        """
        engine = self.engine
        if engine.stats is None:
            raise RuntimeError(
                "RandomSearchMode._process_matches(): engine.stats is None, 引擎未正确初始化",
            )
        for match in matches:
            private_key = match.get("private_key")
            address = match.get("address")

            if private_key and address:
                # 构造匹配结果
                result = {
                    "private_key": private_key,
                    "private_key_hash": hashlib.sha256(str(private_key).encode()).hexdigest(),
                    "address": address,
                    "seed": seed,
                    "batch_size": batch_size,
                    "timestamp": time.time(),
                }

                # 报告匹配结果
                if hasattr(engine, "_on_match_found"):
                    engine._on_match_found(result)

                # 记录统计信息
                if hasattr(engine, "stats") and hasattr(engine.stats, "add_match"):
                    engine.stats.add_match(private_key, address)

                # 触发回调
                if hasattr(engine, "on_match") and engine.on_match:
                    try:
                        engine.on_match(result)
                    except Exception as e:
                        logger.error("匹配回调异常: %s", e)
