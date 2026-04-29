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
        if hasattr(self.engine, '_stop_event'):
            self.engine._stop_event.set()
        if hasattr(self.engine, '_running'):
            self.engine._running = False

    def execute(self) -> None:
        """执行随机搜索（入口，自动选择同步或异步模式）"""
        engine = self.engine
        
        # 检查异步执行器是否可用
        if hasattr(engine, '_async_executor') and engine._async_executor is not None:
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
        engine = self.engine
        
        # 检查异步执行器是否可用
        if not hasattr(engine, '_async_executor') or engine._async_executor is None:
            logger.warning("异步执行器不可用，回退到同步模式")
            self._execute_sync()
            return
        
        if not hasattr(engine, '_gpu_kernel') or engine._gpu_kernel is None:
            logger.warning("GPU内核不可用，回退到同步模式")
            self._execute_sync()
            return
        
        logger.info("启动GPU异步执行模式（双缓冲优化）")
        
        consecutive_errors = 0
        batch_num = 0
        batch_count = 0
        start_time = time.time()
        
        # 双缓冲机制：一个缓冲区用于GPU计算，一个用于CPU准备
        current_buffer = 'A'
        buffer_data = {
            'A': {'seed': None, 'batch_size': 0},
            'B': {'seed': None, 'batch_size': 0}
        }
        
        # 智能批次大小优化器
        from ..batch_size_optimizer import get_batch_size_optimizer
        
        # 检测GPU型号
        gpu_model = 'default'
        if hasattr(engine, '_gpu_device') and engine._gpu_device:
            device_info = engine._gpu_device.get_device_info()
            if device_info and 'name' in device_info:
                device_name = device_info['name'].lower()
                if '1660' in device_name:
                    gpu_model = '1660'
                elif 'rtx' in device_name:
                    gpu_model = 'rtx'
                elif 'amd' in device_name or 'radeon' in device_name:
                    gpu_model = 'amd'
        
        batch_optimizer = get_batch_size_optimizer(engine.batch_size or 1048576, gpu_model=gpu_model)
        
        try:
            current_batch_size = engine.batch_size
            if current_batch_size is None:
                current_batch_size = 1000000  # 默认批次大小
            
            import psutil
            
            # 预生成第一个种子
            buffer_data['A']['seed'] = self._generate_seed()
            buffer_data['A']['batch_size'] = current_batch_size
            
            while not engine._stop_event.is_set():
                batch_num += 1
                
                # 检查CPU过载
                try:
                    cpu_pct = psutil.cpu_percent(interval=None)
                    if cpu_pct > CPU_OVERLOAD_THRESHOLD:
                        logger.debug(f"CPU使用率 {cpu_pct:.1f}% 超过阈值 {CPU_OVERLOAD_THRESHOLD}%, 节流 {CPU_THROTTLE_SLEEP}s")
                        current_batch_size = max(current_batch_size // 2, 10000)
                        time.sleep(CPU_THROTTLE_SLEEP)
                except OSError:
                    pass  # psutil 不可用时忽略
                
                try:
                    # 检查异步执行器是否仍然可用
                    if not hasattr(engine, '_async_executor') or engine._async_executor is None:
                        logger.warning("异步执行器已不可用，切换到同步模式")
                        # 先停止种子预生成线程
                        self.stop()
                        # 然后切换到同步模式
                        self._execute_sync()
                        return
                    
                    # 检查GPU内核是否仍然可用
                    if not hasattr(engine, '_gpu_kernel') or engine._gpu_kernel is None:
                        logger.warning("GPU内核已不可用，停止执行")
                        break
                    
                    # 检查目标缓冲区是否仍然可用
                    if not hasattr(engine._gpu_kernel, '_targets_buf') or engine._gpu_kernel._targets_buf is None:
                        logger.warning("目标缓冲区已不可用，停止执行")
                        break
                    
                    # 获取当前缓冲区的种子和批次大小
                    seed = buffer_data[current_buffer]['seed']
                    batch_size = buffer_data[current_buffer]['batch_size']
                    
                    # 预生成下一个缓冲区的种子（双缓冲关键）
                    next_buffer = 'B' if current_buffer == 'A' else 'A'
                    buffer_data[next_buffer]['seed'] = self._generate_seed()
                    
                    # 智能批次大小调整
                    if batch_num % 10 == 0:
                        current_batch_size = batch_optimizer.get_optimal_batch_size()
                    buffer_data[next_buffer]['batch_size'] = current_batch_size
                    
                    # 检查停止信号
                    if engine._stop_event.is_set():
                        break
                    
                    # 执行GPU异步批处理
                    matches, execution_time_ms = engine._async_executor.run_batch_async(
                        seed, batch_size, engine._gpu_kernel.program,
                        engine._gpu_kernel._targets_buf, len(engine.targets)
                    )
                    
                    # 检查停止信号
                    if engine._stop_event.is_set():
                        break
                    
                    batch_count += batch_size
                    
                    # 更新统计数据（与同步模式保持一致）
                    engine.stats.update(batch_count)
                    
                    # 处理匹配结果（与同步模式保持一致，使用 engine._process_gpu_matches_prng）
                    if matches:
                        engine._process_gpu_matches_prng(seed, matches)
                    
                    # 检查停止信号
                    if engine._stop_event.is_set():
                        break
                    
                    # 性能监控
                    # v4.0 修复: 异步模式下 execution_time_ms 可能为 0
                    # (GPU快到submit+return耗时小于1ms时钟精度)
                    effective_time_ms = max(execution_time_ms, 0.001)
                    speed = batch_size / (effective_time_ms / 1000)
                    if batch_num <= 5 or batch_num % 10 == 0:
                        logger.info(f"GPU batch {batch_num}: {batch_size:,} keys, {execution_time_ms:.2f}ms, {speed:.0f} keys/s")
                    
                    # 记录性能数据
                    batch_optimizer.record_performance(batch_size, execution_time_ms, speed)
                    
                    # 记录内存使用
                    if hasattr(engine, '_gpu_device') and engine._gpu_device:
                        device_info = engine._gpu_device.get_device_info()
                        if 'global_mem_size' in device_info:
                            total_memory_mb = device_info['global_mem_size'] / (1024 * 1024)
                            # 估算已使用内存
                            used_memory_mb = total_memory_mb * 0.7  # 估算值
                            batch_optimizer.record_memory_usage(used_memory_mb, total_memory_mb)
                    
                    # 记录系统负载
                    try:
                        cpu_load = psutil.cpu_percent(interval=None) / 100.0
                        # 估算GPU负载
                        gpu_load = min(speed / 1000000, 1.0)  # 估算值
                        batch_optimizer.record_system_load(cpu_load, gpu_load)
                    except OSError:
                        pass
                    
                    # 重置错误计数
                    consecutive_errors = 0
                    
                    # 切换缓冲区
                    current_buffer = next_buffer
                    
                except Exception as e:
                    # 检查是否是用户中断
                    if isinstance(e, KeyboardInterrupt):
                        logger.info("用户中断，停止异步执行")
                        break
                    
                    ExceptionHandler.handle_gpu_error("随机碰撞(异步)", e, engine.stats)
                    
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
                    
                    # 检查停止信号
                    if engine._stop_event.is_set():
                        break
                    
                    continue
                    
        except KeyboardInterrupt:
            logger.info("用户中断，停止异步执行")
        except Exception as e:
            logger.error(f"异步执行模式异常: {e}", exc_info=True)
        finally:
            # 确保停止种子预生成线程
            self.stop()
            # 打印优化器统计信息
            stats = batch_optimizer.get_stats()
            logger.info(f"智能批次大小优化器统计: {stats}")
        
        logger.info(f"GPU异步执行结束: 共处理 {batch_count} 个私钥")
        engine._running = False
        engine.stats.update(batch_count)
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())

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
    
    def _process_matches(self, matches, seed, batch_size):
        """处理匹配结果"""
        engine = self.engine
        for match in matches:
            private_key = match.get('private_key')
            address = match.get('address')
            
            if private_key and address:
                # 构造匹配结果
                result = {
                    'private_key': private_key,
                    'address': address,
                    'seed': seed,
                    'batch_size': batch_size,
                    'timestamp': time.time()
                }
                
                # 报告匹配结果
                if hasattr(engine, '_on_match_found'):
                    engine._on_match_found(result)
                
                # 记录统计信息
                if hasattr(engine, 'stats') and hasattr(engine.stats, 'add_match'):
                    engine.stats.add_match()
                
                # 触发回调
                if hasattr(engine, 'on_match') and engine.on_match:
                    try:
                        engine.on_match(result)
                    except Exception as e:
                        logger.error(f"匹配回调异常: {e}")
