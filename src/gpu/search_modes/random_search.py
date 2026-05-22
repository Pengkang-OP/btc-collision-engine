"""随机搜索模式 - RandomSearchMode

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
from ...utils import get_configured_logger
from ...utils.exception_handler import ExceptionHandler
from .base_search import BaseSearchMode

if TYPE_CHECKING:
    from ...collision.gpu.engine import GPUCollisionEngine

logger = get_configured_logger("RandomSearchMode")

# 与 gpu_collision_engine 保持一致的常量
INITIAL_BATCH_SIZE = 1_000_000
EXCEPTION_RECOVERY_DELAY = 0.1

# CPU过载保护参数
CPU_OVERLOAD_THRESHOLD = 95.0  # 提高阈值，减少不必要节流
CPU_THROTTLE_SLEEP = 0.01  # 减少节流时间
MIN_BATCH_INTERVAL_SEC = 0.0005  # 减少批次间隔
EXP_BACKOFF_BASE = 0.1  # 指数退避基础延迟(s)
EXP_BACKOFF_MAX = 30.0  # 指数退避最大延迟(s)

# 种子预生成参数 - v4.2.1优化：解决CPU-GPU同步瓶颈
SEED_PREFETCH_SIZE = 100  # 大幅增加缓存深度，匹配GPU队列深度32
SEED_BATCH_GENERATE_SIZE = 25  # 增加每次批量生成的种子数量
SEED_PREFILL_ON_START = True  # 启动时预填充队列
SEED_MIN_QUEUE_SIZE = 5  # 降低阈值，更早触发批量生成

# CPU过载保护参数

# v5.0.0: 移除已弃用的 ASYNC_KEY_GEN_* 常量（PRNG模式下不再需要）


class RandomSearchMode(BaseSearchMode):
    """随机搜索模式

    对应原 GPUCollisionEngine 中的 _random_search_sync / _random_search_async 方法。
    通过 self.engine 访问所有引擎状态，不复制状态。

    v4.2.1 新增：后台种子预生成线程，维护 maxsize=5 的种子缓存队列，
    消除主循环中 os.urandom() 的阻塞等待，进一步平滑 GPU 利用率。
    """

    def __init__(
        self, engine: "GPUCollisionEngine", seed_prefetch_size: int = SEED_PREFETCH_SIZE
    ) -> None:
        super().__init__(engine)
        self._seed_prefetch_size = seed_prefetch_size
        # 种子预生成队列与线程
        self._seed_queue: queue.Queue = queue.Queue(maxsize=seed_prefetch_size)
        self._seed_stop_event: threading.Event = threading.Event()
        self._seed_thread: threading.Thread | None = None

        # 种子统计信息
        self._seed_generated_count = 0
        self._seed_used_count = 0
        self._seed_generation_errors = 0

        # 启动时预填充队列
        if SEED_PREFILL_ON_START:
            self._prefill_seed_queue()

        self._start_seed_prefetch_thread()

        logger.info(f"随机搜索模式已初始化 (种子缓存深度={seed_prefetch_size})")

    def _start_seed_prefetch_thread(self) -> None:
        """启动后台种子预生成 daemon 线程"""
        self._seed_stop_event.clear()
        self._seed_thread = threading.Thread(
            target=self._seed_prefetch_worker, name="SeedPrefetch", daemon=True
        )
        self._seed_thread.start()
        logger.info(f"种子预生成线程已启动 (缓存深度={self._seed_prefetch_size})")

    def _prefill_seed_queue(self) -> None:
        """启动时预填充种子队列"""
        # M-3修复: 简化布尔逻辑，避免 bool AND int 的隐式转换
        base_count = SEED_MIN_QUEUE_SIZE if SEED_PREFILL_ON_START else 0
        prefill_count = min(base_count, self._seed_prefetch_size)
        if prefill_count <= 0:
            return

        logger.info(f"预填充种子队列: {prefill_count} 个种子")
        prefilled = 0

        try:
            # 批量生成种子
            while prefilled < prefill_count and not self._seed_stop_event.is_set():
                seeds = self._generate_seed_batch(SEED_BATCH_GENERATE_SIZE)
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

            logger.info(f"预填充完成: {prefilled}/{prefill_count}")
        except Exception as e:
            logger.warning(f"种子预填充失败: {e}")

    def _generate_seed_batch(self, count: int) -> list[bytes]:
        """批量生成种子（高效）"""
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
            logger.warning(f"批量种子生成失败: {e}")
            # 降级到逐个生成
            for _ in range(count):
                try:
                    seeds.append(secrets.token_bytes(32))
                except OSError:
                    break

        return seeds

    def _seed_prefetch_worker(self) -> None:
        """后台线程：持续调用 os.urandom(32) 填充种子队列 - v4.2.1优化版"""
        while not self._seed_stop_event.is_set():
            try:
                # v4.2.1优化：减少检查间隔，更快速响应
                current_size = self._seed_queue.qsize()

                if current_size < SEED_MIN_QUEUE_SIZE:
                    # v4.2.1优化：批量生成更多种子
                    needed = min(
                        SEED_BATCH_GENERATE_SIZE * 2,  # v4.2.1: 增加批量大小
                        self._seed_prefetch_size - current_size,
                    )

                    # 批量生成种子（高效）
                    seeds = self._generate_seed_batch(needed)

                    # 快速放入队列
                    for seed in seeds:
                        if self._seed_queue.full():
                            break
                        self._seed_queue.put_nowait(seed)
                        self._seed_generated_count += 1
                else:
                    # 队列充足，批量补充
                    batch_size = min(SEED_BATCH_GENERATE_SIZE, self._seed_prefetch_size - current_size)
                    if batch_size > 0:
                        seeds = self._generate_seed_batch(batch_size)
                        for seed in seeds:
                            if self._seed_queue.full():
                                break
                            self._seed_queue.put_nowait(seed)
                            self._seed_generated_count += 1
                    else:
                        time.sleep(0.001)  # v4.2.1: 减少等待时间

            except OSError as e:
                self._seed_generation_errors += 1
                logger.warning(f"种子预生成失败: {e}")
                time.sleep(0.01)
            except Exception as e:
                self._seed_generation_errors += 1
                logger.warning(f"种子预生成线程意外错误: {e}")
                time.sleep(0.01)
        logger.debug("种子预生成线程已退出")

    def _generate_seed(self) -> bytes:
        """获取一个预生成的种子（从队列）"""
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
        """获取种子生成统计信息"""
        return {
            "generated": self._seed_generated_count,
            "used": self._seed_used_count,
            "errors": self._seed_generation_errors,
            "queue_size": self._seed_queue.qsize(),
        }

    def stop(self) -> None:
        """停止种子预生成线程和执行循环（cleanup 入口）"""
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
        """执行随机搜索（入口，自动选择同步或异步模式）"""
        engine = self.engine

        # 检查异步执行器是否可用
        if hasattr(engine, "_async_executor") and engine._async_executor is not None:
            logger.info("使用GPU异步执行模式（双缓冲优化）")
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
        if engine.stats is None:
            raise RuntimeError(
                "RandomSearchMode._random_search(): engine.stats is None, 引擎未正确初始化"
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
                backoff = min(EXP_BACKOFF_BASE * (2 ** min(consecutive_errors - 1, 8)), EXP_BACKOFF_MAX)
                logger.warning(
                    f"GPU batch {batch_num}: 异常 (连续第{consecutive_errors}次), 退避 {backoff:.2f}s"
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

    # ========================================================================
    # 辅助函数 - 拆分自 _execute_async
    # ========================================================================

    def _detect_gpu_model(self, engine: Any) -> str:
        """检测GPU型号

        与 async_executor.py:AsyncGPUExecutor._detect_gpu_model() 保持统一。
        """
        gpu_model = "default"
        if hasattr(engine, "_gpu_device") and engine._gpu_device:
            device_info = engine._gpu_device.get_device_info()
            if device_info and "name" in device_info:
                device_name = device_info["name"].lower()
                if "1660" in device_name:
                    gpu_model = "1660"
                elif "rtx 40" in device_name or "rtx40" in device_name:
                    gpu_model = "rtx40"
                elif "rtx 30" in device_name or "rtx30" in device_name:
                    gpu_model = "rtx30"
                elif "rtx" in device_name:
                    gpu_model = "rtx30"  # 默认RTX系列使用rtx30配置
                elif (
                    "gtx 10" in device_name
                    or "1060" in device_name
                    or "1070" in device_name
                    or "1080" in device_name
                ):
                    gpu_model = "10"
                elif (
                    "gtx 9" in device_name
                    or "960" in device_name
                    or "970" in device_name
                    or "980" in device_name
                ):
                    gpu_model = "9"
                elif "rx 7" in device_name or "rx7" in device_name:
                    gpu_model = "amd7000"
                elif "rx 6" in device_name or "rx6" in device_name:
                    gpu_model = "amd6000"
                elif "amd" in device_name or "radeon" in device_name:
                    gpu_model = "amd6000"  # 默认AMD系列使用amd6000配置
                elif "intel" in device_name or "iris" in device_name or "arc" in device_name:
                    gpu_model = "intel"
        return gpu_model

    def _check_engine_availability(self, engine: Any) -> bool:
        """检查引擎组件是否可用"""
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
        self, engine: Any, seed: bytes, batch_size: int, batch_optimizer: Any, batch_num: int
    ) -> tuple[list, float]:
        """执行单个批次并返回结果"""
        matches, execution_time_ms = engine._async_executor.run_batch_async(
            seed,
            batch_size,
            engine._gpu_kernel.program,
            engine._gpu_kernel._targets_buf,
            len(engine.targets),
        )
        return matches, execution_time_ms

    def _record_performance_data(
        self, engine, batch_optimizer, batch_size, execution_time_ms, speed
    ) -> None:
        """记录性能数据"""
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

    def _handle_batch_error(
        self, e, engine, batch_num, consecutive_errors
    ) -> int:  # type: ignore[override]
        """处理批次执行错误"""
        if isinstance(e, KeyboardInterrupt):
            logger.info("用户中断，停止异步执行")
            return -1  # 表示中断
        ExceptionHandler.handle_gpu_error("随机碰撞(异步)", e, engine.stats)
        consecutive_errors += 1
        backoff = min(EXP_BACKOFF_BASE * (2 ** min(consecutive_errors - 1, 8)), EXP_BACKOFF_MAX)
        logger.warning(
            f"GPU batch {batch_num}: 异常 (连续第{consecutive_errors}次), 退避 {backoff:.2f}s"
        )
        time.sleep(backoff)
        return consecutive_errors

    # ── _execute_async 辅助方法（降低 C901） ──────────────────────

    def _setup_async_buffers(self, engine: Any, current_batch_size: int) -> tuple[dict, int, str]:
        """初始化双缓冲区和 GPU 型号检测。"""
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
                logger.warning(f"batch_size超过GPU缓冲区大小，使用缓冲区大小: {actual_batch_size}")
                current_batch_size = actual_batch_size

        buffer_data = {
            "A": {"seed": self._generate_seed(), "batch_size": current_batch_size},
            "B": {"seed": None, "batch_size": current_batch_size},
        }
        return buffer_data, current_batch_size, "A", batch_optimizer  # type: ignore[return-value]

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
        """执行一次异步批处理周期。

        Returns:
            (current_batch_size, current_buffer, batch_num,
             consecutive_errors, should_break, batch_size_used)
        """
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
            matches, execution_time_ms = self._handle_batch_execution(
                engine, seed, batch_size, batch_optimizer, batch_num
            )

            if engine._stop_event.is_set():
                return current_batch_size, current_buffer, batch_num, consecutive_errors, True, 0

            if matches:
                engine._process_gpu_matches_prng(seed, matches)

            if engine._stop_event.is_set():
                return current_batch_size, current_buffer, batch_num, consecutive_errors, True, 0

            effective_time_ms = max(execution_time_ms, 0.001)
            speed = batch_size / (effective_time_ms / 1000)
            if batch_num <= 5 or batch_num % 10 == 0:
                logger.debug(
                    f"GPU batch {batch_num}: {batch_size:,} keys, "
                    f"{execution_time_ms:.2f}ms, {speed:.0f} keys/s"
                )
            self._record_performance_data(engine, batch_optimizer, batch_size, execution_time_ms, speed)
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
        """异步执行版本（双缓冲 + PRNG + CPU过载保护）。"""
        engine = self.engine
        if engine.stats is None:
            raise RuntimeError(
                "RandomSearchMode._execute_async(): engine.stats is None, 引擎未正确初始化"
            )

        if not self._check_engine_availability(engine):
            logger.warning("异步执行器不可用，回退到同步模式")
            self._execute_sync()
            return

        logger.info("启动GPU异步执行模式（双缓冲优化）")
        current_batch_size = engine.batch_size or 1000000
        buffer_data, current_batch_size, current_buffer, batch_optimizer = self._setup_async_buffers(
            engine, current_batch_size
        )

        batch_count = 0
        batch_num = 0
        consecutive_errors = 0

        try:
            import psutil

            while not engine._stop_event.is_set():
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
                engine.stats.update(batch_count)

        except KeyboardInterrupt:
            logger.info("用户中断，停止异步执行")
        except Exception as e:
            logger.error(f"异步执行模式异常: {e}", exc_info=True)
        finally:
            self.stop()
            logger.info(f"智能批次优化器统计: {batch_optimizer.get_stats()}")

        logger.info(f"GPU异步执行结束: 共处理 {batch_count} 个私钥")
        engine._running = False
        engine.stats.update(batch_count)
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())

    def _process_matches(self, matches, seed, batch_size) -> None:
        """处理匹配结果

        注意: 此方法当前为死代码，无任何调用者。
        保留用于未来重构。
        """
        engine = self.engine
        if engine.stats is None:
            raise RuntimeError(
                "RandomSearchMode._process_matches(): engine.stats is None, 引擎未正确初始化"
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
                        logger.error(f"匹配回调异常: {e}")
