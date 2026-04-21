"""比特币私钥对撞引擎"""
import os
import time
import threading
import secrets
import concurrent.futures
import psutil
from typing import Set, Optional, Callable, Tuple, List, Dict, Any
from ..core.address_generator import P2PKHAddressGenerator
from ..core.secp256k1 import Secp256k1
from ..core.secure_key_manager import SecureKeyManager
from .collision_stats import CollisionStats
from .checkpoint_manager import CheckpointManager
from .deduplication_filter import DeduplicationFilter
from .base_engine import BaseCollisionEngine
from ..utils import init_logging, get_configured_logger
from ..utils.logger import get_sampled_logger, PerformanceMonitor
from ..utils.exception_handler import ExceptionHandler
from ..monitoring.data_logger import DataLogger
from ..monitoring.enhanced_monitoring import EnhancedMonitoringSystem

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("KeyCollisionEngine", thread_safe=True)
sampled_logger = get_sampled_logger("KeyCollisionEngine.sampled", sample_rate=1000)

# 模块级常量配置
BATCH_SIZE = 1000  # 每批处理的私钥数量
PROGRESS_INTERVAL_SEC = 0.5  # 进度回调最小间隔（秒）
PROGRESS_INTERVAL_COUNT = 1000  # 每N次检测触发一次进度回调
DATA_LOG_SAVE_FREQUENCY = 3  # 每N次记录保存一次数据日志
ERROR_LOG_INTERVAL_SEC = 5.0  # 错误日志记录间隔（秒）
CPU_CACHE_INTERVAL_SEC = 1.0  # CPU使用率缓存更新间隔（秒）


class KeyCollisionEngine(BaseCollisionEngine):
    """比特币私钥对撞引擎(CPU实现)
    
    继承BaseCollisionEngine,实现CPU碰撞引擎。
    """

    def __init__(self, targets: Set[str],
                 on_progress: Optional[Callable[[Any], None]] = None,
                 on_match: Optional[Callable[[bytes, str, str], None]] = None,
                 on_complete: Optional[Callable[[Any], None]] = None,
                 checkpoint_enabled: bool = False,
                 dedup_enabled: bool = False,
                 dedup_max_size: int = 1_000_000,
                 checkpoint_interval: int = 30,
                 max_workers: Optional[int] = None,
                 data_logging_enabled: bool = True,
                 data_logging_interval: int = 5,
                 verbose_logging: bool = False,
                 use_enhanced_monitoring: bool = True):  # 默认启用增强监控
        """
        Args:
            targets: 目标地址集合 (set, O(1)查找)
            on_progress: 进度回调 fn(stats: CollisionStats)
            on_match: 匹配回调 fn(private_key: bytes, address: str, wif: str)
                ⚠️ 安全注意:
                - private_key是bytes副本，调用者负责安全处理
                - 建议在使用后立即清零（如使用secure_clear_bytearray）
                - 不要存储到日志或文件（除非加密）
                - 不要传递给不可信的函数
            on_complete: 完成回调 fn(stats: CollisionStats)
            checkpoint_enabled: 是否启用断点续传
            dedup_enabled: 是否启用去重过滤
            dedup_max_size: 去重过滤器最大容量
            checkpoint_interval: 断点自动保存间隔(秒)
            max_workers: 线程池最大工作线程数，None表示使用默认值
            data_logging_enabled: 是否启用数据日志记录
            data_logging_interval: 数据日志记录间隔(秒)
            verbose_logging: 是否启用详细日志（生产环境建议False）
            use_enhanced_monitoring: 是否使用增强监控系统（默认True，包含异常检测和告警）
        
        安全特性:
            - 使用SecureKeyManager管理私钥生命周期
            - 未匹配的私钥在使用后自动清零
            - 匹配的私钥以副本形式传递给回调函数
            - 密码学库(cryptography/PyNaCl)确保安全清零
        """
        self.targets = targets
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete
        self.generator = P2PKHAddressGenerator()
        self.stats = CollisionStats()
        self._stop_event = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.progress_interval = PROGRESS_INTERVAL_COUNT  # 每N次检测触发一次进度回调

        # 日志记录
        logger.info(f"KeyCollisionEngine 初始化完成: 目标数={len(targets)}, "
                   f"断点={checkpoint_enabled}, 去重={dedup_enabled}, "
                   f"工作线程={max_workers or '默认'}")
        # 断点管理器
        self.checkpoint_mgr = CheckpointManager(auto_save_interval=checkpoint_interval) if checkpoint_enabled else None
        # 去重过滤器
        self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size, enabled=dedup_enabled)
        # 线程池
        self.max_workers = max_workers
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        # 当前位置（用于断点保存）
        self._current_position = 0
        self._current_mode = ""
        self._range_start = None
        self._range_end = None
        # 线程安全的计数器
        # 注意：已简化为单锁设计，避免多锁导致的死锁风险
        # _count_lock 保护所有共享状态（计数器、位置、模式等）
        self._state_lock = threading.Lock()
        self._live_range_count = 0  # range_scan 工作线程实时计数器
        # 统计更新完成事件（用于解决竞态条件）
        self._stats_updated = threading.Event()
        self._stats_updated.set()  # 初始状态为已更新
        
        # 日志控制
        self.verbose_logging = verbose_logging  # 生产环境建议False
        # 性能优化：批量处理和进度控制
        self._batch_size = BATCH_SIZE  # 每批处理的私鑰数量
        self._progress_interval_sec = PROGRESS_INTERVAL_SEC  # 进度回调最小间隔（秒）
        self._last_progress_time = 0.0
        
        # 数据日志系统
        # 设计说明：以下数据日志变量仅在主线程访问（通过_log_data_metrics方法），
        # 工作线程不直接访问这些变量，因此无需额外的锁保护。
        # 这种设计避免了锁竞争，提高了性能。
        self.data_logging_enabled = data_logging_enabled
        self.data_logging_interval = data_logging_interval
        self._last_data_log_time = 0.0
        self.data_logger = None
        self.enhanced_monitoring = None
        self._process = psutil.Process(os.getpid())
        
        # 初始化数据日志器（带错误处理）
        if data_logging_enabled:
            try:
                if use_enhanced_monitoring:
                    # 使用增强监控系统（推荐）
                    self.enhanced_monitoring = EnhancedMonitoringSystem(
                        engine=self,
                        collection_interval=data_logging_interval,
                        enable_monitoring_data=False  # 统一使用data_logs
                    )
                    self.data_logger = self.enhanced_monitoring.data_logger
                    logger.info("增强监控系统已启用（统一数据源）")
                else:
                    # 使用传统DataLogger（向后兼容）
                    self.data_logger = DataLogger()
                    logger.info("数据日志系统已启用（传统模式）")
            except Exception as e:
                logger.warning(f"数据日志系统初始化失败，已禁用: {e}")
                self.data_logging_enabled = False
                self.data_logger = None
                self.enhanced_monitoring = None
        
        # CPU使用率缓存（避免频繁阻塞）
        # 线程安全：仅在主线程的_log_data_metrics中访问
        self._cached_cpu_usage = 0.0
        self._last_cpu_check = 0.0
        
        # 数据保存计数器（降低保存频率：每3次记录保存1次）
        # 线程安全：仅在主线程的_log_data_metrics中访问
        self._data_log_save_counter = 0
        
        # 错误记录限频（避免高频写入：每5秒最多记录1个错误）
        # 线程安全：仅在主线程的_log_data_metrics中访问
        self._last_error_log_time = 0.0
        self._error_log_interval = ERROR_LOG_INTERVAL_SEC  # 每5秒最多记录1个错误
    
    def _generate_and_check_secure(self) -> Optional[Tuple[bytes, str]]:
        """使用安全密钥管理器生成私钥并检查匹配。
        
        使用SecureKeyManager确保私钥在使用后立即清零，
        防止私钥在内存中残留。
        
        返回:
            (private_key, address) 如果匹配，否则 None
            注意：返回的private_key是副本，调用者负责清零
        """
        # 使用安全密钥管理器
        with SecureKeyManager() as key_mgr:
            # 生成私钥
            key_mgr.generate_key()
            private_key = key_mgr.get_key()
            
            # 转换为整数验证范围
            k = int.from_bytes(private_key, 'big')
            
            # 验证范围
            if k < 1 or k >= Secp256k1.N:
                return None
            
            # 生成地址
            address, _, _ = self.generator.generate_address(private_key)
            
            # 检查匹配
            if address in self.targets:
                # 找到匹配时，返回私钥的副本
                # 注意：调用者需要负责安全处理这个副本
                return (bytes(private_key), address)
            
            # 退出上下文时私钥自动清零
            return None
    
    def _save_checkpoint(self, count: int):
        """
        保存当前进度到断点文件
        
        将当前碰撞进度保存到 JSON 格式的断点文件中，支持断点续传功能。
        仅在启用了断点管理且满足自动保存间隔条件时执行实际保存操作。
        
        参数:
            count: 当前已检查的私钥数量
            
        注意:
            - 仅在 checkpoint_enabled=True 且满足保存间隔时执行
            - 使用 CheckpointManager 的线程安全方法
            - 保存的信息包括：模式、目标、位置、已检查数、匹配结果
            - random模式不保存当前位置（因为是随机生成）
        """
        if self.checkpoint_mgr and self.checkpoint_mgr.should_auto_save():
            matches_list = [
                {"private_key": m["private_key_hex"], "address": m["address"]}
                for m in self.stats.matches
            ] if hasattr(self.stats, 'matches') else []
            
            # random模式不保存位置（随机生成无位置概念）
            position = self._current_position if self._current_mode != "random" else 0
            
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=position,
                total_checked=count,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end
            )
    
    def _log_data_metrics(self, count: int, speed: float):
        """
        记录数据日志指标
        
        线程安全说明：
            此方法仅在主线程调用（通过进度更新循环），
            工作线程不直接调用此方法，因此无需额外的锁保护。
        
        在满足间隔条件时记录性能、系统和引擎数据到数据日志系统。
        
        参数:
            count: 当前已检查的私钥数量
            speed: 当前检测速度（次/秒）
        """
        if not self.data_logging_enabled or not self.data_logger:
            return
        
        current_time = time.time()
        # 检查是否满足记录间隔
        if current_time - self._last_data_log_time < self.data_logging_interval:
            return
        
        try:
            # 获取CPU使用率（使用缓存避免频繁阻塞）
            if current_time - self._last_cpu_check >= CPU_CACHE_INTERVAL_SEC:  # 每秒更新一次
                self._cached_cpu_usage = self._process.cpu_percent(interval=0.1)
                self._last_cpu_check = current_time
            cpu_usage = self._cached_cpu_usage
            
            # 获取内存和线程信息（非阻塞）
            memory_info = self._process.memory_info()
            memory_usage = memory_info.rss / (1024 * 1024)  # 转换为MB
            thread_count = len(self._process.threads())
            
            # 记录性能数据
            self.data_logger.record_performance_data(
                speed=speed,
                total_checked=count,
                matches_found=len(getattr(self.stats, 'matches', [])),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                thread_count=thread_count
            )
            
            # 记录引擎数据
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=self._running,
                current_position=self._current_position,
                additional_info={
                    "batch_size": self._batch_size,
                    "max_workers": self.max_workers,
                    "dedup_enabled": getattr(self.dedup_filter, 'enabled', False),
                    "checkpoint_enabled": self.checkpoint_mgr is not None
                }
            )
            
            # 更新最后记录时间
            self._last_data_log_time = current_time
            
            # 降低保存频率：每N次记录保存一次（减少I/O）
            self._data_log_save_counter += 1
            if self._data_log_save_counter % DATA_LOG_SAVE_FREQUENCY == 0:
                self.data_logger.save_current_data()
                self.data_logger.save_history_data()
            
        except (IOError, OSError) as e:
            # 文件系统错误：记录日志但不影响主流程
            logger.error(f"记录数据日志失败（I/O错误）: {e}")
        except (AttributeError, TypeError) as e:
            # 数据 logger 状态错误
            logger.error(f"记录数据日志失败（状态错误）: {type(e).__name__}")
        except Exception as e:
            # 未知错误：记录完整堆栈
            logger.exception(f"记录数据日志失败（未知错误）")
    
    def _random_search_worker(self, worker_id: int = 0) -> int:
        """
        随机碰撞模式的工作线程函数（安全增强版）
            
        使用SecureKeyManager确保每个私钥在使用后立即清零。
            
        参数:
            worker_id: 工作线程标识符，用于日志区分，默认0
                
        返回:
            本线程处理的私钥总数
        """
        local_count = 0
        local_matches = []
        batch_start_time = time.time()
            
        logger.debug(f"工作线程 {worker_id} 启动，批量大小={self._batch_size}")
            
        while not self._stop_event.is_set():
            # 批量生成和检查
            batch_count = 0
            batch_start = time.time()
            
            # 优化：批内复用SecureKeyManager实例（减少对象创建开销）
            with SecureKeyManager() as key_mgr:
                for _ in range(self._batch_size):
                    if self._stop_event.is_set():
                        break
                        
                    # 生成新私钥（复用key_mgr实例，清零后重新生成）
                    key_mgr.generate_key()
                    private_key = key_mgr.get_key()
                                    
                    # 转换为整数验证范围
                    k = int.from_bytes(private_key, 'big')
                    if k < 1 or k >= Secp256k1.N:
                        continue  # with块会正确执行__exit__清零私钥
                                    
                    # 去重检查（DeduplicationFilter内部已有锁保护）
                    if not self.dedup_filter.check_and_add(bytes(private_key)):
                        continue  # with块会正确执行__exit__清零私钥
                                    
                    # 生成地址
                    try:
                        address, compressed_pub, _ = self.generator.generate_address(private_key)
                    except ValueError as e:
                        logger.warning(f"Random worker {worker_id}: 私钥无效，跳过: {e}")
                        if self.data_logging_enabled:
                            current_time = time.time()
                            should_log = False
                            
                            # 使用锁保护限频检查和更新（避免竞态条件）
                            with self._state_lock:
                                if current_time - self._last_error_log_time >= self._error_log_interval:
                                    self._last_error_log_time = current_time
                                    should_log = True
                            
                            # 在锁外执行I/O操作
                            if should_log:
                                self.data_logger.record_error(
                                    error_type="invalid_key",
                                    message=f"随机私钥无效",
                                    exception=e,
                                    context={"worker_id": worker_id}
                                )
                        continue  # with块会正确执行__exit__清零私钥
                    except Exception as e:
                        logger.error(f"Random worker {worker_id}: 生成地址失败: {e}", exc_info=True)
                        if self.data_logging_enabled:
                            current_time = time.time()
                            should_log = False
                            
                            # 使用锁保护限频检查和更新（避免竞态条件）
                            with self._state_lock:
                                if current_time - self._last_error_log_time >= self._error_log_interval:
                                    self._last_error_log_time = current_time
                                    should_log = True
                            
                            # 在锁外执行I/O操作
                            if should_log:
                                self.data_logger.record_error(
                                    error_type="address_generation_failed",
                                    message=f"生成地址失败",
                                    exception=e,
                                    context={"worker_id": worker_id}
                                )
                        continue  # with块会正确执行__exit__清零私钥
                                    
                    local_count += 1
                    batch_count += 1
                                    
                    # 检查匹配
                    if address in self.targets:
                        try:
                            from ..core.wif import WIF
                            # 将private_key转换为bytes（可能是memoryview）
                            pk_bytes = bytes(private_key) if not isinstance(private_key, bytes) else private_key
                            # 在with块内编码WIF（私钥还未清零）
                            wif = WIF.encode(pk_bytes, compressed=True)
                            # 保存私钥的副本（调用者负责安全处理）
                            # ⚠️ 注意：local_matches中的private_key是bytes副本
                            #    回调函数on_match接收后需要负责安全处理
                            local_matches.append((bytes(private_key), address, wif))
                        except (ValueError, TypeError, OverflowError) as e:
                            # WIF编码参数错误
                            logger.error(f"Random worker {worker_id}: WIF编码参数错误 addr={address}: {type(e).__name__}")
                            continue  # with块会正确执行__exit__清零私钥
                        except Exception as e:
                            # 未知错误：记录完整堆栈
                            logger.exception(f"Random worker {worker_id}: WIF编码未知错误 addr={address}")
                            continue  # with块会正确执行__exit__清零私钥
                                        
                        # 记录匹配发现
                        logger.info(f"🎯 发现匹配! 地址={address}")
                                        
                        # 批量提交匹配结果
                        if len(local_matches) >= 10:
                            for pk, addr, wif_str in local_matches:
                                self.stats.add_match(pk, addr)
                            if self.on_match:
                                for pk, addr, wif_str in local_matches:
                                    self.on_match(pk, addr, wif_str)
                            local_matches.clear()
                                        
                        # 如果没有on_match回调，找到匹配后停止
                        if not self.on_match:
                            logger.info("找到匹配且无回调，停止对撞")
                            self._stop_event.set()
                            break
                                    
                    # 退出with语句时private_key自动清零
            
            # 批次结束：key_mgr实例退出with块，最后一次私钥清零
            
            # 定期让出时间片，避免CPU占用过高
            if local_count % 100 == 0:
                time.sleep(0)
            
            # 每批处理完后记录性能
            batch_time = time.time() - batch_start
            if batch_count > 0:
                batch_speed = batch_count / batch_time if batch_time > 0 else 0
                if worker_id == 0 and local_count % 10000 == 0:
                    sampled_logger.info(f"工作线程 {worker_id}: 批次处理 {batch_count} 个私钥，速度 {batch_speed:.2f} 次/秒")
            
            # 每批处理完后检查是否需要让出
            time.sleep(0)
        
        # 提交剩余的匹配结果
        if local_matches:
            for pk, addr, wif_str in local_matches:
                self.stats.add_match(pk, addr)
            if self.on_match:
                for pk, addr, wif_str in local_matches:
                    self.on_match(pk, addr, wif_str)
            logger.debug(f"工作线程 {worker_id} 提交了 {len(local_matches)} 个匹配结果")
        
        worker_time = time.time() - batch_start_time
        worker_speed = local_count / worker_time if worker_time > 0 else 0
        logger.debug(f"工作线程 {worker_id} 结束，共处理 {local_count} 个私钥，平均速度 {worker_speed:.2f} 次/秒")
        
        return local_count
    
    def random_search(self):
        """随机碰撞模式 - 使用线程池并行生成私钥并比对（优化版）"""
        logger.info("=" * 60)
        logger.info("启动随机碰撞模式")
        logger.info(f"目标地址数: {len(self.targets)}")
        
        self._current_mode = "random"
        self._current_position = 0
        self._range_start = None
        self._range_end = None
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        total_count = 0
        self._running = True
        self._last_data_log_time = 0.0  # 重置数据日志时间
        
        # 记录引擎启动数据
        if self.data_logging_enabled:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=0
            )
            # 系统数据只在第一次记录（避免重复）
            if self._last_data_log_time == 0.0:
                self.data_logger.record_system_data()
        
        # 确定工作线程数
        num_workers = self.max_workers or (os.cpu_count() or 4)
        logger.info(f"工作线程数: {num_workers}")
        
        # 创建线程池
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            self._executor = executor
            
            # 提交初始任务
            futures = {executor.submit(self._random_search_worker, i): i 
                      for i in range(num_workers)}
            
            while not self._stop_event.is_set() and futures:
                # 等待至少一个任务完成
                done, _ = concurrent.futures.wait(
                    futures, 
                    timeout=0.1,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )
                
                for future in done:
                    worker_id = futures.pop(future)
                    try:
                        local_count = future.result()
                        with self._state_lock:
                            total_count += local_count
                    except concurrent.futures.CancelledError:
                        # 线程被取消（正常停止）
                        # 这通常发生在调用stop()时，是预期内的行为
                        logger.debug(f"工作线程 {worker_id} 被取消")
                    except KeyboardInterrupt:
                        # 用户中断程序（Ctrl+C），重新抛出让主线程处理
                        # 这会让程序优雅退出，而不是强制终止
                        logger.info(f"工作线程 {worker_id} 被用户中断")
                        raise
                    except (RuntimeError, ValueError) as e:
                        # 使用统一异常处理器
                        ExceptionHandler.handle_engine_error(
                            "CPU", e, self.stats, f"工作线程{worker_id}执行"
                        )
                    except Exception as e:
                        # 未知错误：使用统一异常处理器
                        ExceptionHandler.handle_engine_error(
                            "CPU", e, self.stats, f"工作线程{worker_id}执行"
                        )
                    
                    # 如果未停止，提交新任务
                    if not self._stop_event.is_set():
                        new_future = executor.submit(self._random_search_worker, worker_id)
                        futures[new_future] = worker_id
                
                # 基于时间的进度回调
                current_time = time.time()
                if current_time - self._last_progress_time >= self._progress_interval_sec:
                    # 线程安全：在锁内读取 total_count
                    with self._state_lock:
                        safe_count = total_count
                    
                    self.stats.update(safe_count)
                    if self.on_progress:
                        self.on_progress(self.stats.snapshot())
                    self._save_checkpoint(safe_count)
                    
                    # 记录数据日志
                    elapsed = current_time - self.stats.start_time
                    speed = safe_count / elapsed if elapsed > 0 else 0
                    self._log_data_metrics(safe_count, speed)
                    
                    self._last_progress_time = current_time
                    
                    # 采样日志记录进度
                    sampled_logger.info(f"进度: {safe_count:,} 已检查, {speed:,.0f} 次/秒")
        
        # 确保线程安全地获取最终计数
        with self._state_lock:
            final_count = total_count
        
        self._executor = None
        
        # 更新最终统计并设置事件
        self._stats_updated.clear()  # 清除事件
        self.stats.update(final_count)
        self._stats_updated.set()  # 设置事件，通知更新完成
        
        self._running = False
        
        elapsed = time.time() - self.stats.start_time
        speed = final_count / elapsed if elapsed > 0 else 0
        logger.info("=" * 60)
        logger.info("随机碰撞模式结束")
        logger.info(f"总检查数: {final_count:,}")
        logger.info(f"运行时间: {elapsed:.2f}秒")
        logger.info(f"平均速度: {speed:,.0f} 次/秒")
        logger.info(f"发现匹配: {len(self.stats.matches)} 个")
        logger.info("=" * 60)
        
        # 记录引擎停止数据
        if self.data_logging_enabled:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=False,
                current_position=final_count
            )
            # 生成报告
            try:
                report = self.data_logger.generate_report("daily")
                logger.info(f"数据日志报告已生成")
            except Exception as e:
                logger.error(f"生成数据日志报告失败: {e}")
        
        if self.on_complete:
            self.on_complete(self.stats)
    
    def _range_scan_worker(self, worker_start: int, worker_end: int, worker_id: int) -> int:
        """
        范围扫描模式的工作线程函数
        
        在指定范围内顺序扫描私钥，检查是否匹配目标地址。
        适用于已知目标私钥在特定范围内的场景。
        
        参数:
            worker_start: 本线程扫描范围的起始值（包含）
            worker_end: 本线程扫描范围的结束值（包含）
            worker_id: 工作线程标识符，用于日志区分
            
        返回:
            本线程处理的私钥总数
            
        注意:
            - 范围是闭区间 [worker_start, worker_end]
            - 私钥值必须满足 1 <= k < Secp256k1.N
            - 支持通过 _stop_event 优雅停止
            - 使用SecureKeyManager确保私钥在使用后立即清零
        """
        local_count = 0
        
        # 批内复用SecureKeyManager（减少对象创建开销，提升性能2-5%）
        # 每次generate_key()会自动清零旧私钥，保证安全性
        with SecureKeyManager() as key_mgr:
            for k in range(worker_start, worker_end + 1):
                if self._stop_event.is_set():
                    break
                        
                # 验证范围
                if k < 1 or k >= Secp256k1.N:
                    continue
                        
                # 复用key_mgr生成新私钥（旧私钥自动清零）
                key_mgr.generate_key(k.to_bytes(32, 'big'))
                private_key = key_mgr.get_key()
                
                # 将bytearray转换为bytes（coincurve等库需要bytes类型）
                private_key_bytes = bytes(private_key)
                                
                try:
                    # 生成地址
                    address, compressed_pub, _ = self.generator.generate_address(private_key_bytes)
                except ValueError as e:
                    logger.warning(f"Worker {worker_id}: 私钥 k={k} 无效，跳过: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Worker {worker_id}: 生成地址失败 k={k}: {e}", exc_info=True)
                    continue
                        
                local_count += 1
                
                # 实时更新共享计数器（每 500 次更新一次，减少锁争用）
                if local_count % 500 == 0:
                    with self._state_lock:
                        self._live_range_count += 500
                        
                # 检查匹配
                if address in self.targets:
                    try:
                        from ..core.wif import WIF
                        # 将private_key转换为bytes（可能是memoryview）
                        pk_bytes = bytes(private_key) if not isinstance(private_key, bytes) else private_key
                        wif = WIF.encode(pk_bytes, compressed=True)
                        # 保存私钥副本（调用者负责安全处理）
                        pk_copy = bytes(private_key)
                        self.stats.add_match(pk_copy, address)
                        if self.on_match:
                            self.on_match(pk_copy, address, wif)
                        # 如果没有on_match回调，找到匹配后停止
                        else:
                            self._stop_event.set()
                    except (ValueError, TypeError, OverflowError) as e:
                        # WIF编码或回调参数错误
                        logger.error(f"Worker {worker_id}: 匹配处理参数错误 addr={address}: {type(e).__name__}: {e}")
                    except Exception as e:
                        # 未知错误：记录完整堆栈
                        logger.exception(f"Worker {worker_id}: 匹配处理未知错误 addr={address}")
                
            # with块退出时私钥自动清零
                
        return local_count
    
    def range_scan(self, start: int, end: int) -> None:
        """范围扫描模式 - 使用线程池并行扫描指定私鑰范围"""
        self._current_mode = "range"
        self._range_start = start
        self._range_end = end
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        total_count = 0
        total_range = end - start + 1
        self._live_range_count = 0  # 重置实时计数器
        self._running = True
        self._last_data_log_time = 0.0  # 重置数据日志时间
        
        # 记录引擎启动数据
        if self.data_logging_enabled:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=start,
                additional_info={"range_start": start, "range_end": end}
            )
            # 系统数据只在第一次记录（避免重复）
            if self._last_data_log_time == 0.0:
                self.data_logger.record_system_data()
            
        # 计算线程数和每个线程的任务范围
        num_workers = self.max_workers or 4
        chunk_size = total_range // num_workers
        if chunk_size == 0:
            # 范围太小，使用单线程
            self._range_scan_worker(start, end, 0)
            return
            
        # 创建线程池
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            self._executor = executor
                
            # 提交任务
            futures = []
            for i in range(num_workers):
                worker_start = start + i * chunk_size
                worker_end = start + (i + 1) * chunk_size - 1
                if i == num_workers - 1:
                    worker_end = end  # 最后一个线程处理剩余部分
                future = executor.submit(self._range_scan_worker, worker_start, worker_end, i)
                futures.append(future)
                
            # 基于时间的进度回调（不依赖 future 完成）
            pending = set(futures)
            while pending and not self._stop_event.is_set():
                done, pending = concurrent.futures.wait(
                    pending,
                    timeout=self._progress_interval_sec,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )
                    
                # 收集已完成的 future
                for future in done:
                    try:
                        local_count = future.result()
                        with self._state_lock:
                            total_count += local_count
                    except concurrent.futures.CancelledError:
                        # 线程被取消（正常停止）
                        logger.debug(f"工作线程被取消")
                    except KeyboardInterrupt:
                        # 用户中断程序，重新抛出让主线程处理
                        logger.info(f"工作线程被用户中断")
                        raise
                    except (RuntimeError, ValueError) as e:
                        # 使用统一异常处理器
                        ExceptionHandler.handle_engine_error(
                            "CPU", e, self.stats, "range_scan工作线程执行"
                        )
                    except Exception as e:
                        # 未知错误：使用统一异常处理器
                        ExceptionHandler.handle_engine_error(
                            "CPU", e, self.stats, "range_scan工作线程执行"
                        )
                    
                # 定期进度回调（无论是否有 future 完成）
                with self._state_lock:
                    safe_count = total_count
                # 从工作线程读取当前进度（通过共享计数器）
                with self._state_lock:
                    live_count = self._live_range_count
                display_count = max(safe_count, live_count)
                    
                self.stats.update(display_count, total_range=total_range)
                if self.on_progress:
                    self.stats._progress_percent = display_count / total_range * 100
                    self.on_progress(self.stats.snapshot())
                self._save_checkpoint(display_count)
                
                # 记录数据日志
                elapsed = time.time() - self.stats.start_time
                speed = display_count / elapsed if elapsed > 0 else 0
                self._log_data_metrics(display_count, speed)
            
        self._executor = None
        
        # 更新最终统计并设置事件
        self._stats_updated.clear()
        self.stats.update(total_count, total_range=total_range)
        self._stats_updated.set()
        
        self._running = False
        
        # 记录引擎停止数据
        if self.data_logging_enabled:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=False,
                current_position=total_count
            )
            # 生成报告
            try:
                report = self.data_logger.generate_report("daily")
                logger.info(f"数据日志报告已生成")
            except Exception as e:
                logger.error(f"生成数据日志报告失败: {e}")
        
        if self.on_complete:
            self.on_complete(self.stats)
    
    def _brute_force_worker(self, worker_id: int, batch_size: int = 5000) -> int:
        """
        暴力穷举模式的工作线程函数
        
        从指定起点开始顺序递增扫描私钥，使用原子操作获取当前位置。
        适用于从特定起点开始的系统性搜索。
        
        参数:
            worker_id: 工作线程标识符，用于日志区分
            batch_size: 每批获取的私钥数量，默认5000（减少锁竞争）
            
        返回:
            本线程处理的私钥总数
            
        实现细节:
            - 使用 _state_lock 保护 _current_position 的原子更新
            - 批量获取位置，减少锁竞争
            - 支持通过 _stop_event 优雅停止
            - 使用SecureKeyManager确保私钥在使用后立即清零
        """
        local_count = 0
        
        while not self._stop_event.is_set():
            # 原子地获取当前批次起始位置
            with self._state_lock:
                batch_start = self._current_position
                self._current_position += batch_size
            
            # 批内复用SecureKeyManager（减少对象创建开销，提升性能1-3%）
            # 每次generate_key()会自动清零旧私钥，保证安全性
            with SecureKeyManager() as key_mgr:
                # 处理当前批次
                for k in range(batch_start, batch_start + batch_size):
                    if self._stop_event.is_set():
                        break
                    
                    # 验证范围
                    if k < 1 or k >= Secp256k1.N:
                        continue
                    
                    # 复用key_mgr生成新私钥（旧私钥自动清零）
                    key_mgr.generate_key(k.to_bytes(32, 'big'))
                    private_key = key_mgr.get_key()
                    
                    # 将bytearray转换为bytes（coincurve等库需要bytes类型）
                    private_key_bytes = bytes(private_key)
                                    
                    try:
                        # 生成地址
                        address, compressed_pub, _ = self.generator.generate_address(private_key_bytes)
                    except ValueError as e:
                        logger.warning(f"BruteForce worker {worker_id}: 私钥 k={k} 无效，跳过: {e}")
                        continue
                    except (TypeError, OverflowError) as e:
                        # 私钥转换错误（这是关键错误，应该引起关注）
                        # 理论上不应该发生，如果发生说明有潜在的bug
                        logger.error(f"BruteForce worker {worker_id}: 私钥转换错误 k={k}: {type(e).__name__}: {e}")
                        continue
                    except Exception as e:
                        # 未知错误：记录完整堆栈
                        logger.exception(f"BruteForce worker {worker_id}: 生成地址未知错误 k={k}")
                        continue
                                    
                    local_count += 1
                                    
                    # 检查匹配
                    if address in self.targets:
                        try:
                            from ..core.wif import WIF
                            # 将private_key转换为bytes（可能是memoryview）
                            pk_bytes = bytes(private_key) if not isinstance(private_key, bytes) else private_key
                            wif = WIF.encode(pk_bytes, compressed=True)
                            # 保存私钥副本（调用者负责安全处理）
                            pk_copy = bytes(private_key)
                            self.stats.add_match(pk_copy, address)
                            if self.on_match:
                                self.on_match(pk_copy, address, wif)
                            # 如果没有on_match回调，找到匹配后停止
                            else:
                                self._stop_event.set()
                        except (ValueError, TypeError, OverflowError) as e:
                            # WIF编码或回调参数错误
                            logger.error(f"BruteForce worker {worker_id}: 匹配处理参数错误 addr={address}: {type(e).__name__}")
                        except Exception as e:
                            # 未知错误：记录完整堆栈
                            logger.exception(f"BruteForce worker {worker_id}: 匹配处理未知错误 addr={address}")
                    
                # with块退出时私钥自动清零
        
        return local_count
    def brute_force(self, start: int = 1) -> None:
        """暴力穷举模式 - 使用线程池并行从指定起点开始顺序递增"""
        self._current_mode = "brute_force"
        self._range_start = start
        self._range_end = None
        self._current_position = start
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        total_count = 0
        self._running = True
        self._last_data_log_time = 0.0  # 重置数据日志时间
        
        # 记录引擎启动数据
        if self.data_logging_enabled:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=start
            )
            # 系统数据只在第一次记录（避免重复）
            if self._last_data_log_time == 0.0:
                self.data_logger.record_system_data()
        
        # 创建线程池
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            self._executor = executor
            
            # 提交多个任务
            futures = []
            num_workers = self.max_workers or 4
            for i in range(num_workers):
                future = executor.submit(self._brute_force_worker, i)
                futures.append(future)
            
            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                try:
                    local_count = future.result()
                    with self._state_lock:
                        total_count += local_count
                except concurrent.futures.CancelledError:
                    # 线程被取消（正常停止）
                    logger.debug(f"BruteForce 工作线程被取消")
                except KeyboardInterrupt:
                    # 用户中断程序，重新抛出让主线程处理
                    logger.info(f"BruteForce 工作线程被用户中断")
                    raise
                except (RuntimeError, ValueError) as e:
                    # 使用统一异常处理器
                    ExceptionHandler.handle_engine_error(
                        "CPU", e, self.stats, "brute_force工作线程执行"
                    )
                except Exception as e:
                    # 未知错误：使用统一异常处理器
                    ExceptionHandler.handle_engine_error(
                        "CPU", e, self.stats, "brute_force工作线程执行"
                    )
                
                # 进度回调
                if total_count % self.progress_interval == 0:
                    self.stats.update(total_count)
                    if self.on_progress:
                        self.on_progress(self.stats.snapshot())
                    # 断点自动保存
                    self._save_checkpoint(total_count)
                    
                    # 记录数据日志
                    elapsed = time.time() - self.stats.start_time
                    speed = total_count / elapsed if elapsed > 0 else 0
                    self._log_data_metrics(total_count, speed)
        
        self._executor = None
        
        # 更新最终统计并设置事件
        self._stats_updated.clear()
        self.stats.update(total_count)
        self._stats_updated.set()
        
        self._running = False
        
        # 记录引擎停止数据
        if self.data_logging_enabled:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=False,
                current_position=total_count
            )
            # 生成报告
            try:
                report = self.data_logger.generate_report("daily")
                logger.info(f"数据日志报告已生成")
            except Exception as e:
                logger.error(f"生成数据日志报告失败: {e}")
        
        # 最终断点保存
        if self.checkpoint_mgr:
            matches_list = [
                {"private_key": m["private_key_hex"], "address": m["address"]}
                for m in self.stats.matches
            ] if hasattr(self.stats, 'matches') else []
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=self._current_position,
                total_checked=self.stats.total_checked,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end
            )
        if self.on_complete:
            self.on_complete(self.stats)
    
    def resume_from_checkpoint(self) -> Optional[Dict]:
        """从断点恢复，返回断点数据（包含mode等信息），无断点返回 None"""
        if not self.checkpoint_mgr or not self.checkpoint_mgr.exists():
            return None
        data = self.checkpoint_mgr.load()
        if not data:
            return None
        
        # 恢复统计数据
        self.stats.total_checked = data.get('total_checked', 0)
        self.stats.matches = data.get('matches', [])
        
        # 恢复目标（如果当前没有目标）
        if not self.targets and data.get('targets'):
            self.targets = set(data['targets'])
        
        return data
    
    def start_from_checkpoint(self, data: Dict):
        """根据断点数据启动对撞"""
        mode = data.get('mode', 'random')
        if mode == 'range':
            self.start(mode='range', 
                      start=data.get('current_position', 1),
                      end=data.get('range_end', 2**32))
        elif mode == 'brute_force':
            self.start(mode='brute_force',
                      start=data.get('current_position', 1))
        elif mode == 'random':
            self.start(mode='random')
    
    def start(self, mode: str = "random", resume: bool = False, **kwargs):
        """在后台线程启动对撞
        Args:
            mode: "random", "range", "brute_force"
            resume: 是否从断点恢复
            kwargs: range模式需要 start, end; brute_force需要 start
        
        异常:
            ValueError: 当参数无效时
            Exception: 当启动失败时
        """
        try:
            if self._running:
                logger.warning("对撞引擎已在运行中，忽略启动请求")
                return
            
            # 启动增强监控系统（如果启用）
            if self.enhanced_monitoring and not self.enhanced_monitoring.is_running():
                self.enhanced_monitoring.start()
                logger.info("增强监控系统已启动")
            
            # 参数验证
            if mode not in ["random", "range", "brute_force"]:
                raise ValueError(f"未知的对撞模式: {mode}")
            
            if mode == "range":
                if 'start' not in kwargs or 'end' not in kwargs:
                    raise ValueError("range模式需要提供 start 和 end 参数")
                if not isinstance(kwargs['start'], int) or not isinstance(kwargs['end'], int):
                    raise ValueError("start 和 end 参数必须是整数")
                if kwargs['start'] < 1 or kwargs['end'] < kwargs['start']:
                    raise ValueError("start 必须大于0且小于等于 end")
            elif mode == "brute_force":
                if 'start' in kwargs and not isinstance(kwargs['start'], int):
                    raise ValueError("start 参数必须是整数")
                if 'start' in kwargs and kwargs['start'] < 1:
                    raise ValueError("start 必须大于0")
            
            if not self.targets:
                logger.warning("目标地址集合为空，对撞将无意义")
            
            logger.info(f"启动对撞引擎: 模式={mode}, 恢复={resume}, 目标数={len(self.targets)}")
            
            # 断点恢复逻辑
            if resume and self.checkpoint_mgr:
                try:
                    checkpoint = self.checkpoint_mgr.load()
                    if checkpoint:
                        logger.info(f"从断点恢复: 模式={checkpoint.get('mode')}, "
                                   f"已检查={checkpoint.get('total_checked', 0)}")
                        # 恢复目标地址
                        if checkpoint.get("targets"):
                            self.targets = set(checkpoint["targets"])
                        # 根据断点中的 mode 字段恢复对应模式
                        checkpoint_mode = checkpoint.get("mode", mode)
                        if checkpoint_mode == "range":
                            # 从断点继续范围扫描
                            range_start = checkpoint.get("current_position", kwargs.get('start', 1))
                            range_end = checkpoint.get("range_end", kwargs.get('end', 2**32))
                            kwargs['start'] = range_start
                            kwargs['end'] = range_end
                            mode = "range"
                            logger.info(f"范围扫描从 {range_start} 继续到 {range_end}")
                        elif checkpoint_mode == "brute_force":
                            # 从断点继续暴力穷举
                            start_pos = checkpoint.get("current_position", kwargs.get('start', 1))
                            kwargs['start'] = start_pos
                            mode = "brute_force"
                            logger.info(f"暴力穷举从 {start_pos} 继续")
                        elif checkpoint_mode == "random":
                            # 随机模式直接启动，恢复统计数据
                            mode = "random"
                except Exception as e:
                    logger.error(f"从断点恢复失败: {e}")
                    # 继续使用原始参数启动
            
            self._stop_event.clear()
            self._running = True
            # 重置统计更新事件（确保每次启动都是新状态）
            self._stats_updated.set()  # 初始为已更新状态
            
            if mode == "random":
                target_fn = self.random_search
            elif mode == "range":
                target_fn = lambda: self.range_scan(kwargs.get('start', 1), kwargs.get('end', 2**32))
            elif mode == "brute_force":
                target_fn = lambda: self.brute_force(kwargs.get('start', 1))
            
            logger.info(f"启动工作线程: {target_fn.__name__ if hasattr(target_fn, '__name__') else 'lambda'}")
            self._thread = threading.Thread(target=target_fn, daemon=True)
            self._thread.start()
            logger.info("对撞引擎启动完成")
        except Exception as e:
            logger.error(f"启动对撞引擎失败: {e}")
            self._running = False
            raise
    
    def stop(self, timeout: Optional[float] = None) -> None:
        """停止对撞
        
        参数:
            timeout: 等待工作线程结束的超时时间（秒）
                    None时使用默认值（根据目标数动态计算，最少10秒）
        """
        logger.info("正在停止对撞引擎...")

        self._stop_event.set()
        self._running = False

        if self._thread:
            # 动态计算超时时间：最少10秒，每1000个目标增加1秒
            if timeout is None:
                timeout = max(10.0, len(self.targets) * 0.001)
            
            logger.debug(f"等待工作线程结束 (超时{timeout:.1f}秒)...")
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(f"工作线程未在{timeout:.1f}秒内结束，可能存在未提交的匹配数据")
            else:
                logger.debug("工作线程已结束")
        
        # 等待统计信息更新完成（使用事件机制，最多等待5秒）
        # 优化：从2秒增加到5秒，降低竞态条件失败率（目标：从0.9%降到<0.5%）
        if not self._stats_updated.wait(timeout=5.0):
            logger.warning("统计信息更新超时，可能存在竞态条件")
        else:
            logger.debug("统计信息更新完成")
        
        # 保存最终断点
        if self.checkpoint_mgr:
            logger.info(f"保存最终断点: 已检查={self.stats.total_checked}")
            matches_list = [
                {"private_key": m["private_key_hex"], "address": m["address"]}
                for m in self.stats.matches
            ] if hasattr(self.stats, 'matches') else []
            try:
                self.checkpoint_mgr.save(
                    mode=self._current_mode,
                    targets=self.targets,
                    current_position=self._current_position,
                    total_checked=self.stats.total_checked,
                    matches=matches_list,
                    range_start=self._range_start,
                    range_end=self._range_end
                )
                logger.info("断点保存成功")
            except Exception as e:
                logger.error(f"断点保存失败: {e}")
        
        # 停止增强监控系统
        if self.enhanced_monitoring and self.enhanced_monitoring.is_running():
            logger.info("正在停止增强监控系统...")
            self.enhanced_monitoring.stop()
            # 保存最终数据
            if self.data_logger:
                try:
                    self.data_logger.save_current_data()
                    self.data_logger.save_history_data()
                    logger.info("最终数据已保存")
                except Exception as e:
                    logger.error(f"保存最终数据失败: {e}")
        
        # 清理去重过滤器（释放内存）
        if self.dedup_filter and self.dedup_filter.enabled:
            stats = self.dedup_filter.get_stats()
            logger.info(f"清理去重过滤器: 检查={stats['checks_total']}, 重复={stats['duplicates_found']}, "
                       f"跟踪={stats['tracked_total']}")
            self.dedup_filter.reset()
            logger.info("去重过滤器已清理")
        
        # 显式关闭线程池（如果还在运行）
        if self._executor:
            logger.info("关闭线程池...")
            self._executor.shutdown(wait=False)  # 不等待，立即关闭
            self._executor = None
        
        # 重置引擎状态（支持重启）
        self._stop_event.clear()
        self._running = False
        self._thread = None
        
        logger.info("对撞引擎已停止")
    
    def is_running(self) -> bool:
        """
        检查碰撞引擎是否正在运行
        
        返回:
            True 表示引擎正在运行（已启动且工作线程存活），
            False 表示引擎已停止或未启动
        """
        return self._running and self._thread and self._thread.is_alive()
    
    def get_stats(self) -> CollisionStats:
        """
        获取当前碰撞统计信息
        
        返回:
            CollisionStats 对象，包含总检查数、匹配数、运行时间等统计信息
            
        注意:
            返回的是原始 stats 对象的引用，外部修改会影响内部状态
        """
        return self.stats


# 注意: GPU加速功能已迁移到 gpu_collision_engine.py
# 使用方式:
#   from src.collision import create_collision_engine
#   engine = create_collision_engine(targets, mode='gpu')  # 强制GPU
#   engine = create_collision_engine(targets, mode='auto')  # 自动选择
# 或直接导入:
#   from src.collision.gpu_collision_engine import GPUCollisionEngine

