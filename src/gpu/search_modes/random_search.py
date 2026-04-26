"""随机搜索模式 - RandomSearchMode

将 GPUCollisionEngine 中的随机搜索相关方法迁移至此独立模块，
包括同步模式（_random_search_sync）和异步双缓冲模式（_random_search_async）。

PRNG改造 (v4.0): CPU仅生成 32 字节种子，GPU内核自行计算 key = seed + gid。
消除大型私钥数组的内存分配和 CPU-GPU 传输开销。

CPU过载保护: 主循环内添加节流机制，防止 CPU 飞升。
"""

import logging
import os
import queue
import threading
import time
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from ...utils.exception_handler import ExceptionHandler
from .base_search import BaseSearchMode

if TYPE_CHECKING:
    from ...collision.gpu_collision_engine import GPUCollisionEngine

logger = logging.getLogger(__name__)

# 与 gpu_collision_engine 保持一致的常量
INITIAL_BATCH_SIZE = 1_000_000
EXCEPTION_RECOVERY_DELAY = 0.1

# CPU过载保护参数
CPU_OVERLOAD_THRESHOLD = 90.0    # CPU使用率超过该阈値时节流
CPU_THROTTLE_SLEEP = 0.02         # CPU过载时睡眠 20ms
MIN_BATCH_INTERVAL_SEC = 0.001    # 批次间最小间隔 1ms，防止空转
EXP_BACKOFF_BASE = 0.1            # 指数退避基础延迟(s)
EXP_BACKOFF_MAX = 30.0            # 指数退避最大延迟(s)

# 种子预生成参数
SEED_PREFETCH_SIZE = 5            # 种子缓存队列最大深度

# 已弃用常量（历史兼容保留，PRNG模式下不再需要）
ASYNC_KEY_GEN_BASE_TIMEOUT = 5.0
ASYNC_KEY_GEN_PER_KEY_TIME = 0.00001
ASYNC_KEY_GEN_SAFETY_FACTOR = 2.0


class RandomSearchMode(BaseSearchMode):
    """随机搜索模式

    对应原 GPUCollisionEngine 中的 _random_search_sync / _random_search_async 方法。
    通过 self.engine 访问所有引擎状态，不复制状态。

    v4.1 新增：后台种子预生成线程，维护 maxsize=5 的种子缓存队列，
    消除主循环中 os.urandom() 的阻塞等待，进一步平滑 GPU 利用率。
    """

    def __init__(self, engine, seed_prefetch_size: int = SEED_PREFETCH_SIZE) -> None:  # type: ignore[override]
        super().__init__(engine)
        # BUG-6: 支持从外部传入 seed_prefetch_size，不再硬编码 SEED_PREFETCH_SIZE
        self._seed_prefetch_size = seed_prefetch_size
        # 种子预生成队列与线程
        self._seed_queue: queue.Queue = queue.Queue(maxsize=seed_prefetch_size)
        self._seed_stop_event: threading.Event = threading.Event()
        self._seed_thread: Optional[threading.Thread] = None
        self._start_seed_prefetch_thread()

    def _start_seed_prefetch_thread(self) -> None:
        """启动后台种子预生成 daemon 线程"""
        self._seed_stop_event.clear()
        self._seed_thread = threading.Thread(
            target=self._seed_prefetch_worker,
            name="SeedPrefetch",
            daemon=True
        )
        self._seed_thread.start()
        logger.info(f"种子预生成线程已启动 (缓存深度={self._seed_prefetch_size})")

    def _seed_prefetch_worker(self) -> None:
        """后台线程：持续调用 os.urandom(32) 填充种子队列"""
        while not self._seed_stop_event.is_set():
            try:
                seed = os.urandom(32)
                # 阻塞等待直到队列有空位（最多等待 0.1s，超时后检查 stop_event）
                try:
                    self._seed_queue.put(seed, timeout=0.1)
                except queue.Full:
                    # 队列满则跳过，避免阻塞 stop_event 检查
                    pass
            except OSError as e:
                logger.warning(f"种子预生成失败: {e}")
                time.sleep(0.01)
            except Exception as e:
                logger.warning(f"种子预生成线程意外错误: {e}")
                time.sleep(0.01)
        logger.debug("种子预生成线程已退出")

    def stop(self) -> None:
        """停止种子预生成线程（cleanup 入口）"""
        self._seed_stop_event.set()
        if self._seed_thread is not None and self._seed_thread.is_alive():
            self._seed_thread.join(timeout=2.0)
            if self._seed_thread.is_alive():
                logger.warning("种子预生成线程未在 2s 内退出")
        self._seed_thread = None
        logger.info("种子预生成线程已停止")

    def execute(self) -> None:
        """执行随机搜索（入口，根据引擎配置选择同步或异步模式）"""
        engine = self.engine
        # 确保异步执行器存在且启用
        use_async = engine._gpu_device.enable_async_execution and engine._async_executor is not None
        if use_async:
            logger.info("✅ 使用GPU异步执行模式(双缓冲)")
            self._execute_async()
        else:
            logger.info("使用GPU同步执行模式")
            self._execute_sync()

    # ------------------------------------------------------------------
    # 同步执行模式
    # ------------------------------------------------------------------

    def _execute_sync(self) -> None:
        """同步执行版本 (PRNG + CPU过载保护)

        PRNG模式: CPU仅生成32字节种子, GPU内核自行计算 key = seed + gid。
        CPU过载保护: 批次间最小间隔 + psutil CPU使用率节流 + 指数退避。
        """
        import psutil

        engine = self.engine
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

                # PRNG: 仅生成32字节种子, GPU内核自行展开为 key = seed + gid
                seed = self._generate_seed()

                # 执行GPU batch计算
                matches, execution_time_ms = engine._execute_gpu_batch(
                    seed, current_batch_size, batch_num
                )

                # 重置连续错误计数
                consecutive_errors = 0

                # 根据 seed 和 key_index 重建私钥
                engine._process_gpu_matches_prng(seed, matches)

                # 更新统计数据
                batch_count += current_batch_size
                engine.stats.update(batch_count)

                # 记录性能指标
                engine._update_performance_metrics(current_batch_size, execution_time_ms)

                # 检查并报告进度
                engine._check_and_report_progress(batch_count, current_batch_size)

                # ------ CPU过载保护 ------
                # 1. 批次间最小间隔保护
                elapsed = time.monotonic() - batch_start_time
                if elapsed < MIN_BATCH_INTERVAL_SEC:
                    time.sleep(MIN_BATCH_INTERVAL_SEC - elapsed)

                # 2. CPU使用率节流
                try:
                    cpu_pct = psutil.cpu_percent(interval=None)
                    if cpu_pct > CPU_OVERLOAD_THRESHOLD:
                        logger.debug(
                            f"CPU使用率 {cpu_pct:.1f}% 超过阈值 "
                            f"{CPU_OVERLOAD_THRESHOLD}%, 节流 {CPU_THROTTLE_SLEEP}s"
                        )
                        time.sleep(CPU_THROTTLE_SLEEP)
                except OSError:
                    pass  # psutil 不可用时忽略

            except Exception as e:
                ExceptionHandler.handle_gpu_error("随机碰撞", e, engine.stats)

                consecutive_errors += 1
                backoff = min(
                    EXP_BACKOFF_BASE * (2 ** min(consecutive_errors - 1, 8)),
                    EXP_BACKOFF_MAX
                )
                logger.warning(
                    f"GPU batch {batch_num}: 异常 (连续第{consecutive_errors}次), "
                    f"退避 {backoff:.2f}s"
                )
                time.sleep(backoff)
                continue

        logger.info(f"GPU _random_search 结束: 共处理 {batch_count} 个私钥")
        engine._running = False
        engine.stats.update(batch_count)
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())

    # ------------------------------------------------------------------
    # 异步双缓冲执行模式
    # ------------------------------------------------------------------

    def _execute_async(self) -> None:
        """异步执行版本（双缓冲 + PRNG + CPU过载保护）"""
        import psutil
        from ...gpu.performance_optimizer import PerformanceMetrics

        engine = self.engine
        logger.info("GPU _random_search_async 启动 (PRNG + 异步双缓冲)")
        # 使用engine.targets作为目标地址列表
        target_list = list(engine.targets)
        num_targets = len(target_list)
        batch_count = 0
        batch_num = 0
        consecutive_errors = 0
        current_batch_size = engine.batch_size

        # BUG-4: 若 while 循环未执行（stop_event 提前 set），seed 需有初始值防止 NameError
        seed: Optional[bytes] = None

        # 确保current_batch_size不为None
        if current_batch_size is None:
            current_batch_size = 1000000  # 默认批次大小
        logger.info(f"初始批次大小: {current_batch_size:,}")

        while not engine._stop_event.is_set():
            batch_start_time = time.monotonic()

            try:
                batch_num += 1

                # PRNG: 仅生成32字节种子
                seed = self._generate_seed()

                # 使用异步执行器提交 seed
                matches, execution_time_ms = engine._async_executor.run_batch_async(
                    seed=seed,
                    num_keys=current_batch_size,
                    program=engine._gpu_context.program,
                    targets_buf=engine._gpu_kernel._targets_buf,
                    num_targets=num_targets
                )

                # 重置连续错误计数
                consecutive_errors = 0

                # 处理匹配：用 seed + key_index 重建私钥
                from ...core.wif import WIF
                seed_int = int.from_bytes(seed, 'big')
                for match in matches:
                    key_idx = match["key_index"]
                    key_int = (seed_int + key_idx) % (2 ** 256)
                    private_key = key_int.to_bytes(32, 'big')

                    if not engine.dedup_filter.check_and_add(private_key):
                        continue

                    target_idx = match["target_index"]
                    address = engine._target_list[target_idx]
                    wif = WIF.encode(private_key, compressed=True)

                    engine.stats.add_match(private_key, address)
                    if engine.on_match:
                        engine.on_match(private_key, address, wif)

                batch_count += current_batch_size
                engine.stats.update(batch_count)

                # 记录性能指标
                try:
                    memory_mb = engine._calculate_gpu_memory_usage(current_batch_size)

                    if engine.gpu_performance_monitor:
                        engine.gpu_performance_monitor.record_kernel_metrics(
                            batch_size=current_batch_size,
                            execution_time_ms=execution_time_ms,
                            memory_allocated_mb=memory_mb
                        )

                    if engine.performance_optimizer:
                        metrics = PerformanceMetrics(
                            batch_execution_time_ms=execution_time_ms,
                            keys_per_second=engine.stats.get_speed(),
                            memory_usage_mb=memory_mb,
                            error_count=0
                        )
                        engine.performance_optimizer.record_performance(metrics)

                    if batch_num % 10 == 0 and engine.performance_optimizer:
                        new_batch_size, adjustment_info = engine.performance_optimizer.analyze_and_adjust(
                            current_batch_size=engine.batch_size,
                            error_rate=0.0,
                            engine=engine,
                        )
                        if new_batch_size != engine.batch_size:
                            old_batch_size = engine.batch_size
                            logger.info(
                                f"🔧 动态调整batch_size: {old_batch_size:,} -> {new_batch_size:,} "
                                f"原因: {adjustment_info}"
                            )
                            engine.batch_size = new_batch_size
                            current_batch_size = new_batch_size
                            engine._resize_gpu_buffers(new_batch_size)
                            engine._record_adjustment(
                                old_batch_size, new_batch_size,
                                "performance_optimization",
                                str(adjustment_info)
                            )

                except Exception as e:
                    logger.debug(f"记录GPU性能指标失败: {e}")

                # 进度回调
                current_time = time.time()
                if current_time - engine._last_progress_time >= engine._progress_interval_sec:
                    if engine.on_progress:
                        engine.on_progress(engine.stats.snapshot())
                    engine._save_checkpoint(batch_count)
                    engine._last_progress_time = current_time

                # ------ CPU过载保护 ------
                elapsed = time.monotonic() - batch_start_time
                if elapsed < MIN_BATCH_INTERVAL_SEC:
                    time.sleep(MIN_BATCH_INTERVAL_SEC - elapsed)

                try:
                    cpu_pct = psutil.cpu_percent(interval=None)
                    if cpu_pct > CPU_OVERLOAD_THRESHOLD:
                        logger.debug(
                            f"CPU使用率 {cpu_pct:.1f}% 超过阈值 "
                            f"{CPU_OVERLOAD_THRESHOLD}%, 节流 {CPU_THROTTLE_SLEEP}s"
                        )
                        time.sleep(CPU_THROTTLE_SLEEP)
                except OSError:
                    pass

            except Exception as e:
                ExceptionHandler.handle_gpu_error("异步随机碰撞", e, engine.stats)

                with engine._batch_size_lock:
                    engine._consecutive_gpu_errors += 1
                    if engine._consecutive_gpu_errors >= engine._max_gpu_error_retries:
                        logger.critical(
                            f"GPU连续错误次数达到上限({engine._max_gpu_error_retries}), "
                            f"强制停止引擎以防止无限循环"
                        )
                        engine._running = False
                        break

                consecutive_errors += 1
                backoff = min(
                    EXP_BACKOFF_BASE * (2 ** min(consecutive_errors - 1, 8)),
                    EXP_BACKOFF_MAX
                )
                logger.warning(
                    f"异步GPU batch {batch_num}: 退避 {backoff:.2f}s "
                    f"(连续第{consecutive_errors}次)"
                )
                time.sleep(backoff)

        logger.info(f"GPU _random_search_async 结束: 共处理 {batch_count} 个私钥")

        # 收集最后一批异步结果
        if engine._async_executor is not None:
            try:
                # BUG-3: flush_pending 返回 List[Tuple[bytes, List[Dict]]]，
                # 每批次携带自己的 seed，必须按批次正确重建私钥，不得用最后一个 seed 处理所有结果
                pending_batches = engine._async_executor.flush_pending()
                if pending_batches:
                    from ...core.wif import WIF
                    for batch_seed, batch_matches in pending_batches:
                        if not batch_matches:
                            continue
                        # BUG-4: 跳过 seed 为 None 的批次（理论上不应出现，防御性处理）
                        if batch_seed is None:
                            logger.warning("flush_pending 返回了 seed=None 的批次，跳过")
                            continue
                        batch_seed_int = int.from_bytes(batch_seed, 'big')
                        for match in batch_matches:
                            key_idx = match["key_index"]
                            key_int = (batch_seed_int + key_idx) % (2 ** 256)
                            private_key = key_int.to_bytes(32, 'big')

                            if not engine.dedup_filter.check_and_add(private_key):
                                continue

                            target_idx = match["target_index"]
                            address = engine._target_list[target_idx]
                            wif = WIF.encode(private_key, compressed=True)

                            engine.stats.add_match(private_key, address)
                            if engine.on_match:
                                engine.on_match(private_key, address, wif)
            except Exception as e:
                logger.warning(f"收集最后一批异步结果失败: {e}")

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _generate_seed(self) -> bytes:
        """生成 32 字节随机种子（PRNG模式入口）

        优先从预生成缓存队列获取（get_nowait），队列为空时
        fallback 到即时调用 os.urandom(32)。

        Returns:
            32字节种子
        """
        try:
            seed = self._seed_queue.get_nowait()
            logger.debug("使用预生成种子（缓存命中）")
            return seed
        except queue.Empty:
            logger.debug("种子队列空，即时生成")
            return os.urandom(32)

    # DEPRECATED(v4.0): PRNG改造后不再需要批量生成私钥缓冲区。
    # GPU内核通过 seed+gid 自行推导私钥，无需主机侧传输大缓冲区。
    # 此方法无任何调用者，仅保留以避免破坏可能存在的外部脚本引用。
    def _generate_private_keys_batch(self, count: int) -> bytes:  # noqa: deprecated
        """[已弃用，v4.0 PRNG改造后无调用者]

        PRNG模式下 GPU 自行推导私钥，本方法不再被引擎使用。
        如需生成随机字节，请使用 _generate_seed() 代替。
        """
        import warnings
        warnings.warn(
            "_generate_private_keys_batch 已弃用（v4.0 PRNG改造），请使用 _generate_seed()",
            DeprecationWarning,
            stacklevel=2,
        )
        return os.urandom(count * 32)
