"""比特币私钥对撞引擎"""

import concurrent.futures
import hashlib
import os
import signal
import threading
import time
from typing import Any, cast

import psutil

# v2.2.1迁移: 使用crypto_backend替代secp256k1.py（性能提升1000倍）
from ..core.crypto_backend import BackendType, crypto_manager
from ..core.optimized_address_generator import OptimizedP2PKHAddressGenerator
from ..core.secure_key_manager import SecureKeyManager

# 线程池配置校验
from ..core.thread_pool import _validate_worker_count

# WIF 编码（匹配结果导出）
from ..core.wif import WIF
from ..log_engine.log_processor import SensitiveDataFilter
from ..monitoring.data_logger import DataLogger
from ..monitoring.enhanced_monitoring import EnhancedMonitoringSystem
from ..utils import get_configured_logger
from ..utils.exception_handler import ExceptionHandler
from ..utils.logger import get_sampled_logger
from .base_engine import BaseCollisionEngine
from .checkpoint_manager import CheckpointManager
from .collision_stats import CollisionStats
from .deduplication_filter import DeduplicationFilter

# v3.2.0: 事件系统支持
from .event_bus import EventBus
from .events import (
    EngineCompleteEvent,
    EngineErrorEvent,
    EngineMatchEvent,
    EngineProgressEvent,
    EngineStartEvent,
    EngineStopEvent,
)
from .types import CompleteCallback, MatchCallback, ProgressCallback

# 日志系统由CLI/main.py入口统一初始化
# v2.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("KeyCollisionEngine", thread_safe=False)
sampled_logger = get_sampled_logger("KeyCollisionEngine.sampled", sample_rate=1000)

# 模块级常量配置
BATCH_SIZE = 1000  # 每批处理的私钥数量
PROGRESS_INTERVAL_SEC = 0.5  # 进度回调最小间隔（秒）
PROGRESS_INTERVAL_COUNT = 1000  # 每N次检测触发一次进度回调
DATA_LOG_SAVE_FREQUENCY = 3  # 每N次记录保存一次数据日志
ERROR_LOG_INTERVAL_SEC = 5.0  # 错误日志记录间隔（秒）
CPU_CACHE_INTERVAL_SEC = 1.0  # CPU使用率缓存更新间隔（秒）
MATCH_BATCH_FLUSH_THRESHOLD = 10  # P2-2修复: 匹配结果批量提交阈值


class KeyCollisionEngine(BaseCollisionEngine):
    """比特币私钥对撞引擎(CPU实现)

    继承BaseCollisionEngine,实现CPU碰撞引擎。
    """

    def __init__(
        self,
        targets: set[str],
        # v3.2.0: 统一类型提示
        on_progress: ProgressCallback | None = None,
        on_match: MatchCallback | None = None,
        on_complete: CompleteCallback | None = None,
        checkpoint_enabled: bool = False,
        dedup_enabled: bool = False,
        dedup_max_size: int = 1_000_000,
        checkpoint_interval: int = 30,
        max_workers: int | None = None,
        # v3.2.0: 事件总线支持
        event_bus: EventBus | None = None,
        data_logging_enabled: bool = True,
        data_logging_interval: int = 5,
        verbose_logging: bool = False,
        use_enhanced_monitoring: bool = True,  # 默认启用增强监控
        # 性能优化参数 (v2.2.0新增)
        use_performance_optimization: bool = True,
        precomputed_window_size: int = 8,
        use_simd_hash: bool = True,
        use_memory_pool: bool = True,
        # v2.2.1: crypto_backend支持
        crypto_backend_type: str | None = None,  # 'coincurve', 'openssl', 'ecdsa', 'pure_python'
        # 地址格式支持 (v3.2.1新增)
        check_uncompressed: bool | None = None,
    ) -> None:  # 是否同时检查非压缩格式地址, None表示自动检测
        """
        Args:
            targets: 目标地址集合 (set, O(1)查找)
            on_progress: 进度回调 fn(stats: CollisionStats)
            on_match: 匹配回调 fn(private_key: bytes, address: str, wif: str)
                ⚠️ 安全注意:
                - private_key是bytes副本，调用者负责安全处理
                - Python bytes 不可变，无法直接清零；如需安全清零请先转为 bytearray
                - 不要存储到日志或文件（除非加密）
                - 不要传递给不可信的函数
            on_complete: 完成回调 fn(stats: CollisionStats)
            checkpoint_enabled: 是否启用断点续传
            dedup_enabled: 是否启用去重过滤
            dedup_max_size: 去重过滤器最大容量
            checkpoint_interval: 断点自动保存间隔(秒)
            max_workers: 线程池最大工作线程数，None表示使用默认值
            event_bus: 事件总线实例（v3.2.0新增，None则自动创建）
            data_logging_enabled: 是否启用数据日志记录
            data_logging_interval: 数据日志记录间隔(秒)
            verbose_logging: 是否启用详细日志（生产环境建议False）
            use_enhanced_monitoring: 是否使用增强监控系统（默认True，包含异常检测和告警）

            # 性能优化参数 (v2.2.0新增)
            use_performance_optimization: 是否启用性能优化（默认True）
            precomputed_window_size: 预计算表窗口大小4-8（默认8）
            use_simd_hash: 是否使用SIMD哈希优化（默认True）
            use_memory_pool: 是否使用内存池（默认True）

            # v2.2.1: crypto_backend支持
            crypto_backend_type: 加密后端类型（默认自动选择最佳后端）

            # 地址格式支持 (v3.2.1新增)
            check_uncompressed: 是否同时检查非压缩格式地址
                              - True: 强制启用双格式检查
                              - False: 强制禁用，仅检查压缩格式
                              - None: 自动检测（默认，根据目标地址数量决定）

        安全特性:
            - 使用SecureKeyManager管理私钥生命周期
            - 未匹配的私钥在使用后自动清零
            - 匹配的私钥以副本形式传递给回调函数
            - 密码学库(cryptography/PyNaCl)确保安全清零
        """
        # 标准化目标地址为小写，确保大小写不敏感匹配
        self.targets = set(addr.lower() for addr in targets)

        # v4.3.1: 过滤非P2PKH目标地址（引擎仅生成P2PKH，其他格式必然无法匹配）
        p2pkh_targets = {a for a in self.targets if a.startswith("1")}
        filtered_count = len(self.targets) - len(p2pkh_targets)
        if filtered_count > 0:
            fmt_skipped: dict[str, int] = {}
            for a in self.targets:
                if not a.startswith("1"):
                    if a.startswith("bc1p"):
                        fmt_skipped["Taproot"] = fmt_skipped.get("Taproot", 0) + 1
                    elif a.startswith("bc1"):
                        fmt_skipped["Bech32"] = fmt_skipped.get("Bech32", 0) + 1
                    elif a.startswith("3"):
                        fmt_skipped["P2SH"] = fmt_skipped.get("P2SH", 0) + 1
                    else:
                        fmt_skipped["Unknown"] = fmt_skipped.get("Unknown", 0) + 1
            detail = ", ".join(f"{k}:{v}" for k, v in fmt_skipped.items())
            logger.warning(
                f"已过滤 {filtered_count} 个非P2PKH目标地址（引擎仅生成P2PKH，其他格式无法匹配）: {detail}"
            )
            self.targets = p2pkh_targets

        # v3.2.0: 事件总线初始化
        self.event_bus = event_bus or EventBus()

        # 向后兼容: 保留回调
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete

        # v3.2.1: 地址格式支持配置（智能检测）
        if check_uncompressed is None:
            self.check_uncompressed = self._auto_detect_compression_needed()
            logger.info(
                f"自动检测地址格式: {'启用双格式检查' if self.check_uncompressed else '仅检查压缩格式'}"
            )
        else:
            self.check_uncompressed = check_uncompressed

        # 性能优化: 选择优化版或标准版地址生成器 (v2.2.0)
        if use_performance_optimization:
            self.generator = OptimizedP2PKHAddressGenerator(
                use_precomputed_table=True,
                use_simd_hash=use_simd_hash,
                use_memory_pool=use_memory_pool,
                window_size=precomputed_window_size,
            )
            logger.info(
                "KeyCollisionEngine 使用优化版地址生成器: "
                f"window_size={precomputed_window_size}, "
                f"simd={use_simd_hash}, pool={use_memory_pool}"
            )
        else:
            self.generator = OptimizedP2PKHAddressGenerator(
                use_precomputed_table=False,
                use_simd_hash=False,
                use_memory_pool=False,
            )
            logger.info("KeyCollisionEngine 使用标准版地址生成器")
        # 存储内存池开关状态
        self.use_memory_pool = use_memory_pool
        self.stats = CollisionStats()
        self._stop_event = threading.Event()
        self._running = False
        self._engine_stop_reason: str = "normal"  # v3.5.2: 跟踪停止原因
        self._stop_reason_lock = threading.Lock()  # v4.2.3: 保护 _engine_stop_reason 竞态
        self._thread: threading.Thread | None = None
        self.progress_interval = PROGRESS_INTERVAL_COUNT  # 每N次检测触发一次进度回调

        # 日志记录
        logger.info(
            f"KeyCollisionEngine 初始化完成: P2PKH目标数={len(self.targets)}, "
            f"断点={checkpoint_enabled}, 去重={dedup_enabled}, "
            f"工作线程={max_workers or '默认'}"
        )
        # 断点管理器
        self.checkpoint_mgr = (
            CheckpointManager(auto_save_interval=checkpoint_interval)
            if checkpoint_enabled
            else None
        )
        # 去重过滤器
        self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size, enabled=dedup_enabled)
        # 线程池配置
        # 校验并记录最终使用的 max_workers
        self._cpu_count = os.cpu_count() or 4
        self.max_workers = _validate_worker_count(max_workers) if max_workers is not None else None
        if self.max_workers is not None:
            logger.info(
                f"KeyCollisionEngine 使用自定义线程数: max_workers={self.max_workers}, CPU核心数={self._cpu_count}"
            )
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        # 当前位置（用于断点保存）
        self._current_position = 0
        self._current_mode = ""
        self._range_start: int | None = None
        self._range_end: int | None = None

        # v2.2.1: 初始化crypto_backend
        self._init_crypto_backend(crypto_backend_type)
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
        # P3-9修复: 支持自动调整batch_size
        self._batch_size = BATCH_SIZE  # 每批处理的私鑰数量
        self._auto_tune_batch_size = True  # P3-9修复: 是否自动调整batch_size
        self._tune_batch_size()  # P3-9修复: 根据CPU核心数调整batch_size
        self._progress_interval_sec = PROGRESS_INTERVAL_SEC  # 进度回调最小间隔（秒）
        self._progress_interval_count = 1000  # P2-5修复: 进度回调计数控制(每N个batch)
        self._last_progress_time = 0.0
        self._batch_counter = 0  # P2-5修复: batch计数器

        # M13: 内存监控自动降级
        self._memory_high_threshold_mb = 2048  # 内存警报阈値 2GB
        self._memory_critical_threshold_mb = 3072  # 内存临界阈値 3GB
        self._last_memory_downgrade_time = 0.0  # 上次降级时间
        self._memory_downgrade_cooldown = 30.0  # 降级冷却时间（秒）

        # 数据日志系统
        # 设计说明：以下数据日志变量仅在主线程访问（通过_log_data_metrics方法），
        # 工作线程不直接访问这些变量，因此无需额外的锁保护。
        # 这种设计避免了锁竞争，提高了性能。
        self.data_logging_enabled = data_logging_enabled
        self.data_logging_interval = data_logging_interval
        self._last_data_log_time = 0.0
        self.data_logger: Any | None = None
        self.enhanced_monitoring: Any | None = None
        self._process = psutil.Process(os.getpid())

        # v3.2.0: 初始化数据日志系统（使用事件适配器）
        if data_logging_enabled:
            try:
                from src.monitoring.event_adapters import setup_data_logging

                if use_enhanced_monitoring:
                    # 使用增强监控系统（推荐）
                    self.enhanced_monitoring = EnhancedMonitoringSystem(
                        engine=self,
                        collection_interval=data_logging_interval,
                        enable_monitoring_data=False,  # 统一使用data_logs
                    )
                    self.data_logger = self.enhanced_monitoring.data_logger

                    # 订阅事件到增强监控
                    from src.monitoring.event_adapters import EnhancedMonitoringAdapter

                    monitoring_adapter = EnhancedMonitoringAdapter(self.enhanced_monitoring)
                    monitoring_adapter.subscribe_to(self.event_bus)

                    logger.info("增强监控系统已启用（事件驱动模式）")
                else:
                    # 使用传统DataLogger（向后兼容）
                    # 通过事件适配器解耦
                    self.data_logger_adapter = setup_data_logging(
                        event_bus=self.event_bus, data_logger=DataLogger()
                    )
                    self.data_logger = self.data_logger_adapter.data_logger
                    logger.info("数据日志系统已启用（事件驱动模式）")
            except (RuntimeError, OSError, ValueError) as e:
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

        # 私钥回调安全配置
        self._match_callback_timeout = 5  # 回调超时时间（秒）
        self._match_callback_audit_enabled = True  # 启用审计日志

    def _safe_invoke_match_callback(self, private_key: bytes, address: str, wif: str) -> bool:
        """安全调用匹配回调函数

        功能:
        - 超时控制（防止回调函数卡死）
        - 异常隔离（回调异常不影响引擎运行）
        - 审计日志（记录回调执行情况）

        参数:
            private_key: 私钥字节（32字节）
            address: 比特币地址
            wif: WIF格式私钥

        返回:
            bool: 回调是否成功执行
        """
        if not self.on_match:
            return True

        on_match = self.on_match

        key_hash = hashlib.blake2b(private_key, digest_size=8).hexdigest()

        if self._match_callback_audit_enabled:
            logger.debug(f"调用匹配回调: address={address}, key_hash={key_hash}")

        try:
            # Windows不支持SIGALRM，使用线程超时
            if os.name == "nt":
                result: list[Any | None] = [None]
                exception: list[Exception | None] = [None]

                def target() -> None:
                    try:
                        result[0] = on_match(private_key, address, wif)
                    except (RuntimeError, OSError, ValueError) as e:
                        exception[0] = e

                callback_thread = threading.Thread(target=target, daemon=True)
                callback_thread.start()
                callback_thread.join(timeout=self._match_callback_timeout)

                if callback_thread.is_alive():
                    logger.critical(
                        f"匹配回调执行超时 ({self._match_callback_timeout}秒)，强制跳过: "
                        f"address={address}, key_hash={key_hash}"
                    )
                    return False

                if exception[0]:
                    logger.error(f"匹配回调异常: {exception[0]}")
                    return False
            else:
                # Unix系统使用SIGALRM超时
                def timeout_handler(signum: int, frame: Any) -> None:
                    raise TimeoutError(f"匹配回调执行超时 ({self._match_callback_timeout}秒)")

                _sigalrm = signal.SIGALRM  # type: ignore[attr-defined] # noqa: E501 # signal.SIGALRM 仅 Unix 可用
                old_handler = signal.signal(_sigalrm, timeout_handler)  # noqa: E501
                _alarm = signal.alarm  # type: ignore[attr-defined] # signal.alarm 仅 Unix 可用
                _alarm(self._match_callback_timeout)

                try:
                    on_match(private_key, address, wif)
                except TimeoutError as e:
                    logger.critical(str(e))
                    return False
                except (RuntimeError, OSError, ValueError) as e:
                    logger.error(f"匹配回调异常: {e}")
                    return False
                finally:
                    _alarm(0)  # noqa: E501
                    signal.signal(_sigalrm, old_handler)

            if self._match_callback_audit_enabled:
                logger.debug(f"匹配回调执行成功: address={address}")

            # v4.3.1: 私钥安全说明
            # Python bytes 对象不可变，无法在内存中直接清零。bytearray(private_key)
            # 仅创建副本并清零副本，对原 bytes 无影响。此处的 private_key 是调用方
            # 传入的副本，原始密钥由 SecureKeyManager 在上下文退出时安全清零。
            # 本函数返回后，该 bytes 对象依赖 Python GC 回收内存。

            return True

        except (RuntimeError, OSError, ValueError) as e:
            logger.error(f"匹配回调调用失败: {e}")
            # v4.3.1: 异常路径同样依赖 SecureKeyManager 清零原始密钥，
            # 此处的 private_key 是调用方传入的 bytes 副本，函数返回后由 GC 回收。
            return False

    def _generate_and_check_secure(self) -> tuple[bytes, str] | None:
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
            k = int.from_bytes(private_key, "big")

            # 验证范围（使用crypto_backend的曲线参数）
            # Secp256k1.N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
            if k < 1 or k >= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141:
                return None

            # 生成地址
            address, _, _ = self.generator.generate_address(private_key)

            # 检查匹配（标准化为小写）
            if address.lower() in self.targets:
                # 找到匹配时，返回私钥的副本
                # 注意：调用者需要负责安全处理这个副本
                return (bytes(private_key), address)

            # 退出上下文时私钥自动清零
            return None

    def _save_checkpoint(self, count: int) -> None:
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
            matches_list = (
                [
                    {"private_key_hash": m["private_key_hash"], "address": m["address"]}
                    for m in self.stats.matches
                ]
                if hasattr(self.stats, "matches")
                else []
            )

            # random模式不保存位置（随机生成无位置概念）
            position = self._current_position if self._current_mode != "random" else 0

            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=position,
                total_checked=count,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end,
            )

    def _log_data_metrics(self, count: int, speed: float) -> None:
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
                self._cached_cpu_percent = self._process.cpu_percent(interval=0.1)
                self._last_cpu_check = current_time

            # 获取内存使用
            memory_info = self._process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # M13: 内存监控自动降级
            self._check_memory_and_downgrade(memory_mb, current_time)
            # P3-9修复: 记录batch_size调优信息
            if hasattr(self, "_auto_tune_batch_size") and self._auto_tune_batch_size:
                logger.debug(f"Batch size调优: {self._batch_size} (CPU: {self._cpu_count}核)")

            # 记录数据 - 使用DataLogger的正确方法
            if hasattr(self.data_logger, "log_performance"):
                # 增强监控系统的DataLogger
                self.data_logger.log_performance(
                    timestamp=current_time,
                    keys_checked=count,
                    speed=speed,
                    cpu_percent=self._cached_cpu_percent,
                    memory_mb=memory_mb,
                )
            elif hasattr(self.data_logger, "record_performance_data"):
                # 传统DataLogger
                self.data_logger.record_performance_data(
                    speed=speed,
                    total_checked=count,
                    matches_found=self.stats.matches_found,
                    cpu_usage=self._cached_cpu_percent,
                    memory_usage=memory_mb,
                )

            self._last_data_log_time = current_time

        except (RuntimeError, OSError, ValueError) as e:
            logger.error(f"记录数据指标失败: {e}")

    def _check_memory_and_downgrade(self, memory_mb: float, current_time: float) -> None:
        """M13: 内存监控自动降级

        当进程内存使用超过阈値时，自动降低 batch_size 和 max_workers
        以降低内存压力，防止程序 OOM 崩溃。

        参数:
            memory_mb: 当前进程占用内存（MB）
            current_time: 当前时间戳
        """
        # 冷却期内不重复降级
        if current_time - self._last_memory_downgrade_time < self._memory_downgrade_cooldown:
            return

        if memory_mb >= self._memory_critical_threshold_mb:
            # 临界状态：将 batch_size 减半（对当前运行立即生效）
            old_batch = self._batch_size
            new_batch = max(old_batch // 2, 256)
            self._batch_size = new_batch

            # 同时更新 max_workers 配置（边界校验，影响下次启动）
            if self.max_workers and self.max_workers > 1:
                old_workers = self.max_workers
                self.max_workers = _validate_worker_count(max(self.max_workers // 2, 1))
                logger.warning(
                    f"[M13 内存降级] 内存使用 {memory_mb:.0f}MB 达临界阈値 "
                    f"{self._memory_critical_threshold_mb}MB，"
                    f"本次运行已将 batch_size: {old_batch} -> {new_batch}，"
                    f"将下次启动的 max_workers 配置: {old_workers} -> {self.max_workers}"
                )
            else:
                logger.warning(
                    f"[M13 内存降级] 内存使用 {memory_mb:.0f}MB 达临界阈値 "
                    f"{self._memory_critical_threshold_mb}MB，"
                    f"本次运行已将 batch_size: {old_batch} -> {new_batch}"
                )
            self._last_memory_downgrade_time = current_time

        elif memory_mb >= self._memory_high_threshold_mb:
            # 警报状态：仅降低 batch_size
            old_batch = self._batch_size
            new_batch = max(old_batch * 3 // 4, 512)  # 降到 75%
            if new_batch < old_batch:
                self._batch_size = new_batch
                logger.warning(
                    f"[M13 内存降级] 内存使用 {memory_mb:.0f}MB 达高警阈値 "
                    f"{self._memory_high_threshold_mb}MB，"
                    f"batch_size: {old_batch} -> {new_batch}"
                )
                self._last_memory_downgrade_time = current_time

    def _tune_batch_size(self) -> None:
        """P3-9修复: 根据CPU核心数自动调整batch_size

        调优策略:
        - 1-2核: 500
        - 4核: 1000
        - 8核: 2000
        - 16核+: 4000

        目标: 平衡内存使用和并行效率
        """
        if not self._auto_tune_batch_size:
            return

        cpu_count = self._cpu_count

        if cpu_count <= 2:
            optimal_batch_size = 500
        elif cpu_count <= 4:
            optimal_batch_size = 1000
        elif cpu_count <= 8:
            optimal_batch_size = 2000
        else:
            optimal_batch_size = 4000

        old_batch_size = self._batch_size
        self._batch_size = optimal_batch_size

        if old_batch_size != optimal_batch_size:
            logger.info(
                f"P3-9 Batch size自动调整: {old_batch_size} -> {optimal_batch_size} (CPU: {cpu_count}核)"
            )

    def _auto_detect_compression_needed(self) -> bool:
        """智能检测是否需要检查非压缩格式地址

        检测策略:
        - 目标地址数量较少时（< 1000），启用双格式检查以确保不漏掉匹配
        - 目标地址数量较多时（>= 1000），仅检查压缩格式以优化性能

        返回:
            bool: 是否需要检查非压缩格式
        """
        target_count = len(self.targets)

        # 策略：少量目标时启用双格式检查，大量目标时性能优先
        if target_count < 1000:
            logger.debug(f"目标地址数={target_count} < 1000，启用双格式检查")
            return True
        else:
            logger.debug(f"目标地址数={target_count} >= 1000，仅检查压缩格式（性能优先）")
            return False

    def _init_crypto_backend(self, backend_type: str | None = None) -> None:
        """初始化加密后端（v2.2.1新增）

        Args:
            backend_type: 后端类型 ('coincurve', 'openssl', 'ecdsa', 'pure_python')
                         None表示自动选择最佳后端
        """
        try:
            if backend_type:
                # 用户指定后端
                backend_map = {
                    "coincurve": BackendType.COINCURVE,
                    "openssl": BackendType.OPENSSL,
                    "ecdsa": BackendType.ECDSA,
                    "pure_python": BackendType.PURE_PYTHON,
                }

                backend_enum = backend_map.get(backend_type.lower())
                if backend_enum:
                    success = crypto_manager.set_backend(backend_enum)
                    if success:
                        logger.info(f"加密后端已设置为: {backend_type}")
                    else:
                        logger.warning(f"加密后端设置失败: {backend_type}，使用默认后端")
                else:
                    logger.warning(f"未知的加密后端类型: {backend_type}，使用默认后端")

            # 获取当前后端信息
            backend = crypto_manager.current_backend
            logger.info(
                f"加密后端初始化完成: {backend.name}, 恒定时间={backend.is_constant_time()}"
            )

        except (RuntimeError, OSError, ValueError) as e:
            logger.error(f"加密后端初始化失败: {e}，使用默认后端")

    def _log_throttled_error(
        self, error_type: str, message: str, exception: Exception, worker_id: int
    ) -> None:
        """限频记录错误日志（线程安全）

        P1-1重构: 从 _random_search_worker 提取重复的错误日志限频逻辑。

        H-4修复: 添加敏感数据脱敏处理。

        敏感数据脱敏说明:
        1. 使用 SensitiveDataFilter 对错误消息进行脱敏处理
        2. 异常字符串中的敏感信息被替换为占位符
        3. 保留异常类型用于诊断和调试
        4. 避免私钥等敏感数据泄露到日志文件

        Args:
            error_type: 错误类型标识
            message: 错误描述
            exception: 异常对象
            worker_id: 工作线程ID
        """
        if not (self.data_logging_enabled and self.data_logger):
            return

        current_time = time.time()
        should_log = False

        with self._state_lock:
            if current_time - self._last_error_log_time >= self._error_log_interval:
                self._last_error_log_time = current_time
                should_log = True

        if should_log:
            # H-4修复: 脱敏处理 - 对消息和异常字符串进行敏感数据过滤，保留异常类型
            safe_message = SensitiveDataFilter.redact(message) if message else message
            safe_exception = exception
            if exception is not None:
                safe_exc_str = SensitiveDataFilter.redact(str(exception))
                if safe_exc_str != str(exception):
                    try:
                        safe_exception = type(exception)(safe_exc_str)
                    except (TypeError, ValueError):
                        safe_exception = RuntimeError(safe_exc_str)
            self.data_logger.record_error(
                error_type=error_type,
                message=safe_message,
                exception=safe_exception,
                context={"worker_id": worker_id},
            )

    def _process_key_match(
        self,
        private_key,
        matched_address: str,
        matched_compressed: bool,
        local_matches: list,
        worker_id: int,
    ) -> bool:
        """处理密钥匹配：WIF编码、记录匹配、触发回调

        P1-1重构: 从 _random_search_worker 提取匹配处理逻辑。

        Args:
            private_key: 匹配的私钥（bytes或memoryview）
            matched_address: 匹配的比特币地址
            matched_compressed: 是否为压缩格式地址
            local_matches: 本地匹配结果列表（可变）
            worker_id: 工作线程ID

        Returns:
            True 表示应继续运行，False 表示应停止引擎
        """
        try:
            pk_bytes = bytes(private_key) if not isinstance(private_key, bytes) else private_key
            wif = WIF.encode(pk_bytes, compressed=True)
            local_matches.append((pk_bytes, matched_address, wif))
        except (ValueError, TypeError, OverflowError) as e:
            logger.error(
                f"Random worker {worker_id}: WIF编码参数错误 addr={matched_address}: {type(e).__name__}"
            )
            # v3.5.2: 发布 ENGINE_ERROR 事件
            try:
                self.event_bus.publish(EngineErrorEvent(
                    error_type="wif_encode_error",
                    error_message=str(e),
                    exception=e,
                    context={"worker_id": worker_id, "address": matched_address},
                    recoverable=True,
                ))
            except (RuntimeError, OSError):
                pass
            return True  # 继续运行
        except (RuntimeError, OSError):
            logger.exception(f"Random worker {worker_id}: WIF编码未知错误 addr={matched_address}")
            return True  # 继续运行

        # 记录匹配发现
        format_type = "压缩" if matched_compressed else "非压缩"
        logger.info(f"🎯 发现匹配! 地址={matched_address} (格式: {format_type})")

        # H-5修复: 批量回调添加超时和批次数限制
        # 分批处理回调，避免长时间阻塞
        #
        # 批量回调设计目的:
        # 1. 防止回调函数卡死导致主线程阻塞
        # 2. 避免一次性处理大量匹配导致内存压力
        # 3. 每批之间可以处理其他任务，提高响应性
        #
        # 批处理参数:
        # - CALLBACK_BATCH_SIZE: 每批最多处理5个回调
        # - CALLBACK_TIMEOUT: 每批超时2秒
        CALLBACK_BATCH_SIZE = 5  # 每批最多5个回调
        CALLBACK_TIMEOUT = 2.0  # 每批超时2秒
        for i in range(0, len(local_matches), CALLBACK_BATCH_SIZE):
            batch = local_matches[i:i + CALLBACK_BATCH_SIZE]
            for pk, addr, wif_str in batch:
                self.stats.add_match(pk, addr)
            if self.on_match:
                for pk, addr, wif_str in batch:
                    self._safe_invoke_match_callback(pk, addr, wif_str)
            # v3.5.2: 发布 ENGINE_MATCH 事件（stats.add_match 之后，确保统计已更新）
            for _pk, addr, _wif in local_matches:
                try:
                    self.event_bus.publish(EngineMatchEvent(
                        private_key=b'',  # 安全: 事件不暴露原始私钥
                        address=addr,
                        wif=_wif,
                        target_address=addr,
                    ))
                except (RuntimeError, OSError, ValueError) as e:
                    logger.debug(f"发布 ENGINE_MATCH 事件失败（非致命）: {e}")
            local_matches.clear()

        # 如果没有on_match回调，找到匹配后停止
        if not self.on_match:
            logger.info("找到匹配且无回调，停止对撞")
            self._stop_event.set()
            return False  # 停止运行

        return True  # 继续运行

    def _random_search_worker(self, worker_id: int = 0) -> int:
        """
        随机碰撞模式的工作线程函数（安全增强版）

        使用SecureKeyManager确保每个私钥在使用后立即清零。

        P1-1重构: 提取 _log_throttled_error / _process_key_match，
        方法从 248 行缩减至 ~160 行。

        参数:
            worker_id: 工作线程标识符，用于日志区分，默认0

        返回:
            本线程处理的私钥总数
        """
        local_count = 0
        local_matches: list[tuple[bytes, str, str]] = []
        batch_start_time = time.time()

        # BL-4修复: 添加短期去重缓存，减少DeduplicationFilter的压力
        # M1优化: 使用list+set组合，避免频繁的list<->set转换
        # list保持添加顺序，set用于O(1)查找
        # 当容量超过阈值时，丢弃前半部分并重建set
        recent_keys_list: list = []  # 记录添加顺序
        recent_keys_set: set = set()  # 用于O(1)查找
        max_recent_size = 10000  # 缓存大小
        _half_size = max_recent_size // 2  # 预计算阈值

        logger.debug(f"工作线程 {worker_id} 启动，批量大小={self._batch_size}")

        while not self._stop_event.is_set():
            batch_count = 0
            batch_start = time.time()

            with SecureKeyManager() as key_mgr:
                for _ in range(self._batch_size):
                    if self._stop_event.is_set():
                        break

                    key_mgr.generate_key()
                    private_key = key_mgr.get_key()

                    k = int.from_bytes(private_key, "big")
                    if (
                        k < 1
                        or k >= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
                    ):
                        continue

                    # 短期缓存 + 去重检查（M1优化: 使用list+set组合）
                    key_fp = hashlib.sha256(private_key).digest()[:8]
                    if key_fp in recent_keys_set:
                        continue
                    if not self.dedup_filter.check_and_add(bytes(private_key)):
                        continue

                    # M1优化: 高效缓存管理
                    # 当缓存超过max_recent_size时，丢弃前半部分并重建set
                    # 这种方式比每次都转换更高效
                    recent_keys_list.append(key_fp)
                    recent_keys_set.add(key_fp)
                    if len(recent_keys_list) > max_recent_size:
                        # 丢弃前半部分，保留后半部分
                        recent_keys_list = recent_keys_list[_half_size:]
                        # 重建set以反映新的列表内容
                        recent_keys_set = set(recent_keys_list)

                    # 生成地址（错误日志通过 _log_throttled_error 统一处理）
                    try:
                        if self.check_uncompressed:
                            compressed_addr, _, _ = self.generator.generate_address(
                                private_key, compressed=True
                            )
                            uncompressed_addr, _, _ = self.generator.generate_address(
                                private_key, compressed=False
                            )
                        else:
                            compressed_addr, _, _ = self.generator.generate_address(
                                private_key, compressed=True
                            )
                            uncompressed_addr = None
                    except ValueError as e:
                        logger.warning(f"Random worker {worker_id}: 私钥无效，跳过: {e}")
                        self._log_throttled_error("invalid_key", "随机私钥无效", e, worker_id)
                        continue
                    except (RuntimeError, OSError, ValueError) as e:
                        logger.error(f"Random worker {worker_id}: 生成地址失败: {e}", exc_info=True)
                        self._log_throttled_error(
                            "address_generation_failed", "生成地址失败", e, worker_id
                        )
                        continue

                    local_count += 1
                    batch_count += 1

                    if local_count % 32 == 0:
                        with self._state_lock:
                            self._live_range_count += 32

                    # 检查匹配（匹配处理通过 _process_key_match 统一处理）
                    matched_address = None
                    matched_compressed = False
                    if compressed_addr.lower() in self.targets:
                        matched_address = compressed_addr
                        matched_compressed = True
                    elif (
                        self.check_uncompressed
                        and uncompressed_addr
                        and uncompressed_addr.lower() in self.targets
                    ):
                        matched_address = uncompressed_addr
                        matched_compressed = False

                    if matched_address:
                        if not self._process_key_match(
                            private_key,
                            matched_address,
                            matched_compressed,
                            local_matches,
                            worker_id,
                        ):
                            break

            # 批次结束：key_mgr实例退出with块，最后一次私钥清零

            # P1-5修复: 删除批次结束的 _live_range_count += batch_count
            # 原因：批内每32步已通过 L749-752 提交增量，此处重复提交导致双重计数
            # 正确公式: total_count(已完成worker的总数) + _live_range_count(运行中worker的32步增量)
            # 旧代码 self._live_range_count += batch_count 导致进度虚高约100%

            # 定期让出时间片，避免CPU占用过高
            if local_count % 100 == 0:
                time.sleep(0)

            # 每批处理完后记录性能
            batch_time = time.time() - batch_start
            if batch_count > 0:
                batch_speed = batch_count / batch_time if batch_time > 0 else 0
                if worker_id == 0 and local_count % 10000 == 0:
                    sampled_logger.info(
                        f"工作线程 {worker_id}: 批次处理 {batch_count} 个私钥，速度 {batch_speed:.2f} 次/秒"
                    )

            # 每批处理完后检查是否需要让出
            time.sleep(0)

        # 提交剩余的匹配结果
        if local_matches:
            for pk, addr, wif_str in local_matches:
                self.stats.add_match(pk, addr)
            if self.on_match:
                for pk, addr, wif_str in local_matches:
                    self._safe_invoke_match_callback(pk, addr, wif_str)
            # v3.5.2: 发布剩余匹配的 ENGINE_MATCH 事件
            for _pk, addr, _wif in local_matches:
                try:
                    self.event_bus.publish(EngineMatchEvent(
                        private_key=b'',  # 安全: 事件不暴露原始私钥
                        address=addr,
                        wif=_wif,
                        target_address=addr,
                    ))
                except (RuntimeError, OSError, ValueError) as e:
                    logger.debug(f"发布 ENGINE_MATCH 事件失败（非致命）: {e}")
            logger.debug(f"工作线程 {worker_id} 提交了 {len(local_matches)} 个匹配结果")

        # P1-5修复: worker退出时提交32步余数，修复精度丢失（最多31个计数）
        # 批内每32步提交一次 _live_range_count += 32
        # 如果 total 不是32的倍数，余数未被提交，导致最终统计偏低
        remainder = local_count % 32
        if remainder > 0:
            with self._state_lock:
                self._live_range_count += remainder

        worker_time = time.time() - batch_start_time
        worker_speed = local_count / worker_time if worker_time > 0 else 0
        logger.debug(
            f"工作线程 {worker_id} 结束，共处理 {local_count} 个私钥，平均速度 {worker_speed:.2f} 次/秒"
        )

        return local_count

    def random_search(self) -> None:
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

        # v3.5.2: 发布 ENGINE_START 事件
        try:
            self.event_bus.publish(EngineStartEvent(
                mode=self._current_mode,
                target_count=len(self.targets),
                batch_size=self._batch_size,
            ))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug(f"发布 ENGINE_START 事件失败（非致命）: {e}")

        # 启动时自适应调优内存池
        if self.use_memory_pool:
            try:
                from ..core.memory_pool import pool_manager

                was_tuned = pool_manager.auto_tune_all()
                if not was_tuned:
                    stats = pool_manager.get_all_stats()
                    logger.debug(
                        f"P3-7 内存池状态: total_est={stats['total_estimated_memory_mb']:.1f}MB"
                    )
            except (ImportError, RuntimeError) as e:
                logger.debug(f"P3-7 内存池调优跳过: {type(e).__name__}: {e}")

        # 记录引擎启动数据
        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=0,
            )
            # 系统数据只在第一次记录（避免重复）
            if self._last_data_log_time == 0.0:
                self.data_logger.record_system_data()

        # 确定工作线程数
        # 使用配置值或CPU核心数（上限1024，下限1）
        num_workers = (
            _validate_worker_count(self.max_workers)
            if self.max_workers is not None
            else self._cpu_count
        )
        # 内存降级时进一步减少线程
        available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)
        if available_memory_mb < 512:
            # 可用内存 < 512MB：限制线程数不超过2
            num_workers = min(num_workers, 2)
            logger.warning(
                f"可用内存不足 ({available_memory_mb:.0f}MB)，限制线程数为 {num_workers}"
            )
        logger.info(
            f"工作线程数: {num_workers} (CPU核心: {self._cpu_count}, 可用内存: {available_memory_mb:.0f}MB)"
        )

        # 创建线程池
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            self._executor = executor

            # 提交初始任务
            futures = {
                executor.submit(self._random_search_worker, i): i for i in range(num_workers)
            }

            while not self._stop_event.is_set() and futures:
                # 等待至少一个任务完成
                done, _ = concurrent.futures.wait(
                    futures, timeout=0.1, return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    worker_id = futures.pop(future)
                    try:
                        local_count = future.result()
                        with self._state_lock:
                            # P1-5修复: 已完成worker的live计数转移到total_count
                            # 原因：_live_range_count 中已完成worker的贡献必须扣除
                            # 否则 total_count + _live_range_count 会重复计入已完成work
                            # 使用 max(0, ...) 防止并发下的短暂不一致
                            self._live_range_count = max(0, self._live_range_count - local_count)
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
                    except (RuntimeError, OSError, ValueError) as e:
                        # 未知错误：使用统一异常处理器
                        ExceptionHandler.handle_engine_error(
                            "CPU", e, self.stats, f"工作线程{worker_id}执行"
                        )

                    # 如果未停止，提交新任务
                    if not self._stop_event.is_set():
                        new_future = executor.submit(self._random_search_worker, worker_id)
                        futures[new_future] = worker_id

                # P2-5修复: 基于时间和计数的双重进度回调控制
                current_time = time.time()
                should_report = False

                # 时间间隔控制
                if current_time - self._last_progress_time >= self._progress_interval_sec:
                    should_report = True

                # 计数控制(高速运行时更精确)
                self._batch_counter += 1
                if self._batch_counter >= self._progress_interval_count:
                    should_report = True
                    self._batch_counter = 0

                if should_report:
                    # P2-5修复: 使用实时计数器，而不是等待线程完成
                    # 这确保在工作线程持续运行时也能获取实时进度
                    with self._state_lock:
                        safe_count = total_count + self._live_range_count

                    self.stats.update(safe_count)
                    if self.on_progress:
                        self.on_progress(self.stats.snapshot())
                    self._save_checkpoint(safe_count)

                    # 记录数据日志
                    elapsed = current_time - self.stats.start_time
                    speed = safe_count / elapsed if elapsed > 0 else 0
                    self._log_data_metrics(safe_count, speed)

                    # M13: 内存监控自动降级（独立于数据日志，即使禁用日志也生效）
                    try:
                        mem_mb = self._process.memory_info().rss / 1024 / 1024
                        self._check_memory_and_downgrade(mem_mb, current_time)
                    except (AttributeError, OSError, RuntimeError) as e:
                        logger.debug(f"内存监控失败（不影响主逻辑）: {type(e).__name__}: {e}")

                    # v3.5.2: 发布 ENGINE_PROGRESS 事件
                    try:
                        self.event_bus.publish(EngineProgressEvent(
                            total_checked=safe_count,
                            speed=speed,
                            matches_found=self.stats.matches_found,
                            elapsed_time=elapsed,
                        ))
                    except (RuntimeError, OSError, ValueError) as e:
                        logger.debug(f"发布 ENGINE_PROGRESS 事件失败（非致命）: {e}")

                    self._last_progress_time = current_time

                    # 采样日志记录进度
                    sampled_logger.info(f"进度: {safe_count:,} 已检查, {speed:,.0f} 次/秒")

        # 确保线程安全地获取最终计数
        with self._state_lock:
            # P2-5修复: 包含实时计数器，确保最终统计准确
            final_count = total_count + self._live_range_count
            # 重置实时计数器（为下次运行做准备）
            self._live_range_count = 0

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
        logger.info(f"发现匹配: {self.stats.matches_found} 个")
        logger.info("=" * 60)

        # v3.5.2: 发布 ENGINE_COMPLETE 事件
        try:
            with self._stop_reason_lock:
                stop_reason = self._engine_stop_reason
                self._engine_stop_reason = "normal"  # 重置为默认值
            self.event_bus.publish(EngineCompleteEvent(
                total_checked=final_count,
                matches_found=self.stats.matches_found,
                elapsed_time=elapsed,
                avg_speed=speed,
                stop_reason=stop_reason,
            ))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug(f"发布 ENGINE_COMPLETE 事件失败（非致命）: {e}")

        # 记录引擎停止数据
        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=False,
                current_position=final_count,
            )
            # 生成报告
            try:
                self.data_logger.generate_report("daily")
                logger.info("数据日志报告已生成")
            except (RuntimeError, OSError, ValueError) as e:
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

                # 验证范围（使用crypto_backend的曲线参数）
                # Secp256k1.N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
                if k < 1 or k >= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141:
                    continue

                # 复用key_mgr生成新私钥（旧私钥自动清零）
                key_mgr.generate_key(k.to_bytes(32, "big"))
                private_key = key_mgr.get_key()

                # 将bytearray转换为bytes（coincurve等库需要bytes类型）
                private_key_bytes = bytes(private_key)

                try:
                    # 生成地址
                    if self.check_uncompressed:
                        # 同时生成压缩和非压缩格式地址
                        compressed_addr, compressed_pub, _ = self.generator.generate_address(
                            private_key_bytes, compressed=True
                        )
                        uncompressed_addr, uncompressed_pub, _ = self.generator.generate_address(
                            private_key_bytes, compressed=False
                        )
                    else:
                        # 仅生成压缩格式地址（默认）
                        compressed_addr, compressed_pub, _ = self.generator.generate_address(
                            private_key_bytes, compressed=True
                        )
                        uncompressed_addr = None
                except ValueError as e:
                    logger.warning(f"Worker {worker_id}: 私钥 k={k} 无效，跳过: {e}")
                    continue
                except (RuntimeError, OSError, ValueError) as e:
                    logger.error(f"Worker {worker_id}: 生成地址失败 k={k}: {e}", exc_info=True)
                    continue

                local_count += 1

                # M2修复: 统一提交阈值为32，与random_search保持一致
                # 原来范围扫描使用500，随机搜索使用32，现在统一为32
                # 更频繁的更新可以减少异常时丢失的计数
                if local_count % 32 == 0:
                    with self._state_lock:
                        self._live_range_count += 32

                # 检查匹配：先检查压缩格式，再检查非压缩格式（如果启用）
                matched_address = None
                matched_compressed: bool = False

                if compressed_addr.lower() in self.targets:
                    matched_address = compressed_addr
                    matched_compressed = True
                elif (
                    self.check_uncompressed
                    and uncompressed_addr
                    and uncompressed_addr.lower() in self.targets
                ):
                    matched_address = uncompressed_addr
                    matched_compressed = False

                if matched_address:
                    try:
                        # 将private_key转换为bytes（可能是memoryview）
                        pk_bytes = (
                            bytes(private_key)
                            if not isinstance(private_key, bytes)
                            else private_key
                        )
                        wif = WIF.encode(pk_bytes, compressed=True)
                        # 保存私钥副本（调用者负责安全处理）
                        pk_copy = bytes(private_key)
                        self.stats.add_match(pk_copy, matched_address)
                        if self.on_match:
                            self._safe_invoke_match_callback(pk_copy, matched_address, wif)
                        # 如果没有on_match回调，找到匹配后停止
                        else:
                            self._stop_event.set()

                        # 记录匹配发现
                        format_type = "压缩" if matched_compressed else "非压缩"
                        logger.info(f"🎯 发现匹配! 地址={matched_address} (格式: {format_type})")

                        # v3.5.2: 发布 ENGINE_MATCH 事件
                        try:
                            self.event_bus.publish(EngineMatchEvent(
                                private_key=b'',  # 安全: 事件不暴露原始私钥
                                address=matched_address,
                                wif=wif,
                                target_address=matched_address,
                            ))
                        except (RuntimeError, OSError, ValueError) as e:
                            logger.debug(f"发布 ENGINE_MATCH 事件失败（非致命）: {e}")

                    except (ValueError, TypeError, OverflowError) as e:
                        # WIF编码或回调参数错误
                        # MEDIUM-9修复: 拆分多行f-string提高可读性
                        err_type = type(e).__name__
                        logger.error(
                            f"Worker {worker_id}: 匹配处理参数错误 addr={matched_address}: {err_type}: {e}"
                        )
                        # v3.5.2: 发布 ENGINE_ERROR 事件
                        try:
                            self.event_bus.publish(EngineErrorEvent(
                                error_type="wif_encode_error",
                                error_message=str(e),
                                exception=e,
                                context={"worker_id": worker_id, "address": matched_address},
                                recoverable=True,
                            ))
                        except (RuntimeError, OSError):
                            pass
                    except (RuntimeError, OSError):
                        # 未知错误：记录完整堆栈
                        logger.exception(
                            f"Worker {worker_id}: 匹配处理未知错误 addr={matched_address}"
                        )

            # with块退出时私钥自动清零

        # P1-5修复: worker退出时提交余数，修复精度丢失（最多31个计数）
        # M2修复: 阈值从500改为32，与random_search保持一致
        remainder = local_count % 32
        if remainder > 0:
            with self._state_lock:
                self._live_range_count += remainder

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

        # v3.5.2: 发布 ENGINE_START 事件
        try:
            self.event_bus.publish(EngineStartEvent(
                mode=self._current_mode,
                target_count=len(self.targets),
                batch_size=self._batch_size,
            ))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug(f"发布 ENGINE_START 事件失败（非致命）: {e}")

        # 记录引擎启动数据
        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=start,
                additional_info={"range_start": start, "range_end": end},
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

                # M3修复: 添加边界检查，确保无重叠
                # 计算前一个worker的结束位置
                if i > 0:
                    prev_worker_end = start + i * chunk_size - 1
                    if worker_start <= prev_worker_end:
                        # 发现重叠，调整当前worker的开始位置为前一个worker结束+1
                        logger.warning(
                            f"RangeScan worker {i}: 检测到边界重叠，修正范围 "
                            f"[{worker_start}, {worker_end}] -> [{prev_worker_end + 1}, {worker_end}]"
                        )
                        worker_start = prev_worker_end + 1
                        if worker_start > worker_end:
                            # 如果修正后范围无效，跳过此worker
                            logger.warning(f"RangeScan worker {i}: 范围无效，跳过")
                            continue

                logger.debug(
                    f"RangeScan worker {i}: 分配范围 [{worker_start}, {worker_end}] "
                    f"(共{worker_end - worker_start + 1}个私钥)"
                )

                future = executor.submit(self._range_scan_worker, worker_start, worker_end, i)
                futures.append(future)

            # 基于时间的进度回调（不依赖 future 完成）
            pending = set(futures)
            while pending and not self._stop_event.is_set():
                done, pending = concurrent.futures.wait(
                    pending,
                    timeout=self._progress_interval_sec,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )

                # 收集已完成的 future
                for future in done:
                    try:
                        local_count = future.result()
                        with self._state_lock:
                            # P1-5修复: 已完成worker的live计数转移到total_count
                            # 防止 total_count + _live_range_count 重复计入
                            self._live_range_count = max(0, self._live_range_count - local_count)
                            total_count += local_count
                    except concurrent.futures.CancelledError:
                        # 线程被取消（正常停止）
                        logger.debug("工作线程被取消")
                    except KeyboardInterrupt:
                        # 用户中断程序，重新抛出让主线程处理
                        logger.info("工作线程被用户中断")
                        raise
                    except (RuntimeError, ValueError) as e:
                        # 使用统一异常处理器
                        ExceptionHandler.handle_engine_error(
                            "CPU", e, self.stats, "range_scan工作线程执行"
                        )
                    except (RuntimeError, OSError, ValueError) as e:
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

                # v3.5.2: 发布 ENGINE_PROGRESS 事件
                try:
                    self.event_bus.publish(EngineProgressEvent(
                        total_checked=display_count,
                        speed=speed,
                        matches_found=self.stats.matches_found,
                        elapsed_time=elapsed,
                    ))
                except (RuntimeError, OSError, ValueError) as e:
                    logger.debug(f"发布 ENGINE_PROGRESS 事件失败（非致命）: {e}")

        # P1-4修复: 停止时合并 _live_range_count，防止pending worker贡献丢失
        # 当stop()被调用时，while循环退出但pending workers可能已完成
        # 它们的贡献仍在 _live_range_count 中，需要合并到最终计数
        # pattern与 random_search (L976-981) 一致
        with self._state_lock:
            final_count = total_count + self._live_range_count
            logger.debug(
                f"P1-4: range_scan final: total={total_count}, live={self._live_range_count}, final={final_count}"
            )
            self._live_range_count = 0

        self._executor = None

        # 更新最终统计并设置事件
        self._stats_updated.clear()
        self.stats.update(final_count, total_range=total_range)
        self._stats_updated.set()

        self._running = False

        elapsed = time.time() - self.stats.start_time
        speed = final_count / elapsed if elapsed > 0 else 0

        # v3.5.2: 发布 ENGINE_COMPLETE 事件
        try:
            with self._stop_reason_lock:
                stop_reason = self._engine_stop_reason
                self._engine_stop_reason = "normal"  # 重置为默认值
            self.event_bus.publish(EngineCompleteEvent(
                total_checked=final_count,
                matches_found=self.stats.matches_found,
                elapsed_time=elapsed,
                avg_speed=speed,
                stop_reason=stop_reason,
            ))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug(f"发布 ENGINE_COMPLETE 事件失败（非致命）: {e}")

        # 记录引擎停止数据
        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=False,
                current_position=final_count,
            )
            # 生成报告
            try:
                self.data_logger.generate_report("daily")
                logger.info("数据日志报告已生成")
            except (RuntimeError, OSError, ValueError) as e:
                logger.error(f"生成数据日志报告失败: {e}")

        if self.on_complete:
            self.on_complete(self.stats)

    def _brute_force_worker(
        self, worker_id: int, batch_size: int = 5000, max_keys: int | None = None
    ) -> int:
        """
        暴力穷举模式的工作线程函数

        从指定起点开始顺序递增扫描私钥，使用原子操作获取当前位置。
        适用于从特定起点开始的系统性搜索。

        参数:
            worker_id: 工作线程标识符，用于日志区分
            batch_size: 每批获取的私钥数量，默认5000（减少锁竞争）
            max_keys: 最大扫描私钥数量，None表示无限制

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
            # 检查是否达到最大扫描数量
            if max_keys is not None and local_count >= max_keys:
                logger.info(f"BruteForce worker {worker_id}: 已达到最大扫描数量 {max_keys}")
                break

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

                    # 验证范围（使用crypto_backend的曲线参数）
                    # Secp256k1.N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141 # noqa: E501
                    if (
                        k < 1
                        or k >= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
                    ):
                        continue

                    # 复用key_mgr生成新私钥（旧私钥自动清零）
                    key_mgr.generate_key(k.to_bytes(32, "big"))
                    private_key = key_mgr.get_key()

                    # 将bytearray转换为bytes（coincurve等库需要bytes类型）
                    private_key_bytes = bytes(private_key)

                    try:
                        # 生成地址
                        address, compressed_pub, _ = self.generator.generate_address(
                            private_key_bytes
                        )
                    except ValueError as e:
                        logger.warning(f"BruteForce worker {worker_id}: 私钥 k={k} 无效，跳过: {e}")
                        continue
                    except (TypeError, OverflowError) as e:
                        # 私钥转换错误（这是关键错误，应该引起关注）
                        # 理论上不应该发生，如果发生说明有潜在的bug
                        logger.error(
                            f"BruteForce worker {worker_id}: 私钥转换错误 k={k}: {type(e).__name__}: {e}"
                        )
                        continue
                    except (RuntimeError, OSError):
                        # 未知错误：记录完整堆栈
                        logger.exception(f"BruteForce worker {worker_id}: 生成地址未知错误 k={k}")
                        continue

                    local_count += 1

                    # 检查匹配（标准化为小写）
                    if address.lower() in self.targets:
                        try:
                            # 将private_key转换为bytes（可能是memoryview）
                            pk_bytes = (
                                bytes(private_key)
                                if not isinstance(private_key, bytes)
                                else private_key
                            )
                            wif = WIF.encode(pk_bytes, compressed=True)
                            # 保存私钥副本（调用者负责安全处理）
                            pk_copy = bytes(private_key)
                            self.stats.add_match(pk_copy, address)
                            if self.on_match:
                                self._safe_invoke_match_callback(pk_copy, address, wif)
                            # 如果没有on_match回调，找到匹配后停止
                            else:
                                self._stop_event.set()

                            # v3.5.2: 发布 ENGINE_MATCH 事件
                            try:
                                self.event_bus.publish(EngineMatchEvent(
                                    private_key=b'',  # 安全: 事件不暴露原始私钥
                                    address=address,
                                    wif=wif,
                                    target_address=address,
                                ))
                            except (RuntimeError, OSError, ValueError) as e:
                                logger.debug(f"发布 ENGINE_MATCH 事件失败（非致命）: {e}")

                        except (ValueError, TypeError, OverflowError) as e:
                            # WIF编码或回调参数错误
                            # MEDIUM-9修复: 拆分多行f-string提高可读性
                            err_type = type(e).__name__
                            logger.error(
                                f"BruteForce worker {worker_id}: 匹配处理参数错误 addr={address}: {err_type}"
                            )
                            # v3.5.2: 发布 ENGINE_ERROR 事件
                            try:
                                self.event_bus.publish(EngineErrorEvent(
                                    error_type="wif_encode_error",
                                    error_message=str(e),
                                    exception=e,
                                    context={"worker_id": worker_id, "address": address},
                                    recoverable=True,
                                ))
                            except (RuntimeError, OSError):
                                pass
                        except (RuntimeError, OSError):
                            # 未知错误：记录完整堆栈
                            logger.exception(
                                f"BruteForce worker {worker_id}: 匹配处理未知错误 addr={address}"
                            )

                # with块退出时私钥自动清零

        return local_count

    def brute_force(self, start: int = 1, max_keys: int | None = None) -> None:
        """暴力穷举模式 - 使用线程池并行从指定起点开始顺序递增

        参数:
            start: 起始私钥值，默认1
            max_keys: 最大扫描私钥数量，None表示无限制（防止无限运行）

        注意:
            - 建议设置max_keys参数以避免无限运行
            - 例如：max_keys=1_000_000_000 限制扫描10亿个私钥
        """
        self._current_mode = "brute_force"
        self._range_start = start
        self._range_end = None
        self._current_position = start
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        total_count = 0
        self._running = True
        self._last_data_log_time = 0.0  # 重置数据日志时间

        # v3.5.2: 发布 ENGINE_START 事件
        try:
            self.event_bus.publish(EngineStartEvent(
                mode=self._current_mode,
                target_count=len(self.targets),
                batch_size=self._batch_size,
            ))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug(f"发布 ENGINE_START 事件失败（非致命）: {e}")

        # 警告：如果未设置max_keys
        if max_keys is None:
            logger.warning("⚠️ brute_force模式未设置max_keys限制，将无限运行直到手动停止或找到匹配")
            logger.warning("建议：使用 max_keys 参数限制扫描数量，例如 max_keys=1_000_000_000")

        # 记录引擎启动数据
        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=start,
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
                    logger.debug("BruteForce 工作线程被取消")
                except KeyboardInterrupt:
                    # 用户中断程序，重新抛出让主线程处理
                    logger.info("BruteForce 工作线程被用户中断")
                    raise
                except (RuntimeError, ValueError) as e:
                    # 使用统一异常处理器
                    ExceptionHandler.handle_engine_error(
                        "CPU", e, self.stats, "brute_force工作线程执行"
                    )
                except (RuntimeError, OSError, ValueError) as e:
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

                    # v3.5.2: 发布 ENGINE_PROGRESS 事件
                    try:
                        self.event_bus.publish(EngineProgressEvent(
                            total_checked=total_count,
                            speed=speed,
                            matches_found=self.stats.matches_found,
                            elapsed_time=elapsed,
                        ))
                    except (RuntimeError, OSError, ValueError) as e:
                        logger.debug(f"发布 ENGINE_PROGRESS 事件失败（非致命）: {e}")

        self._executor = None

        # 更新最终统计并设置事件
        self._stats_updated.clear()
        self.stats.update(total_count)
        self._stats_updated.set()

        self._running = False

        elapsed = time.time() - self.stats.start_time
        speed = total_count / elapsed if elapsed > 0 else 0

        # v3.5.2: 发布 ENGINE_COMPLETE 事件
        try:
            stop_reason = self._engine_stop_reason
            self._engine_stop_reason = "normal"  # 重置为默认值
            self.event_bus.publish(EngineCompleteEvent(
                total_checked=total_count,
                matches_found=self.stats.matches_found,
                elapsed_time=elapsed,
                avg_speed=speed,
                stop_reason=stop_reason,
            ))
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug(f"发布 ENGINE_COMPLETE 事件失败（非致命）: {e}")

        # 记录引擎停止数据
        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=False,
                current_position=total_count,
            )
            # 生成报告
            try:
                self.data_logger.generate_report("daily")
                logger.info("数据日志报告已生成")
            except (RuntimeError, OSError, ValueError) as e:
                logger.error(f"生成数据日志报告失败: {e}")

        # 最终断点保存
        if self.checkpoint_mgr:
            matches_list = (
                [
                    {"private_key_hash": m["private_key_hash"], "address": m["address"]}
                    for m in self.stats.matches
                ]
                if hasattr(self.stats, "matches")
                else []
            )
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=self._current_position,
                total_checked=self.stats.total_checked,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end,
            )
        if self.on_complete:
            self.on_complete(self.stats)

    def resume_from_checkpoint(self) -> dict | None:
        """从断点恢复，返回断点数据（包含mode等信息），无断点返回 None"""
        if not self.checkpoint_mgr or not self.checkpoint_mgr.exists():
            return None
        data = self.checkpoint_mgr.load()
        if not data:
            return None

        # 恢复统计数据
        self.stats.total_checked = data.get("total_checked", 0)
        self.stats.matches = data.get("matches", [])

        # 恢复目标（如果当前没有目标）
        if not self.targets and data.get("targets"):
            self.targets = set(data["targets"])

        return data

    def start_from_checkpoint(self, data: dict) -> None:
        """根据断点数据启动对撞"""
        mode = data.get("mode", "random")
        if mode == "range":
            self.start(
                mode="range",
                start=data.get("current_position", 1),
                end=data.get("range_end", 2**32),
            )
        elif mode == "brute_force":
            self.start(mode="brute_force", start=data.get("current_position", 1))
        elif mode == "random":
            self.start(mode="random")

    def start(self, mode: str = "random", resume: bool = False, **kwargs) -> None:
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
                if "start" not in kwargs or "end" not in kwargs:
                    raise ValueError("range模式需要提供 start 和 end 参数")
                if not isinstance(kwargs["start"], int) or not isinstance(kwargs["end"], int):
                    raise ValueError("start 和 end 参数必须是整数")
                if kwargs["start"] < 1 or kwargs["end"] < kwargs["start"]:
                    raise ValueError("start 必须大于0且小于等于 end")
            elif mode == "brute_force":
                if "start" in kwargs and not isinstance(kwargs["start"], int):
                    raise ValueError("start 参数必须是整数")
                if "start" in kwargs and kwargs["start"] < 1:
                    raise ValueError("start 必须大于0")

            if not self.targets:
                logger.warning("目标地址集合为空，对撞将无意义")

            logger.info(f"启动对撞引擎: 模式={mode}, 恢复={resume}, 目标数={len(self.targets)}")

            # 断点恢复逻辑
            if resume and self.checkpoint_mgr:
                try:
                    checkpoint = self.checkpoint_mgr.load()
                    if checkpoint:
                        logger.info(
                            f"从断点恢复: 模式={checkpoint.get('mode')}, 已检查={checkpoint.get('total_checked', 0)}"
                        )
                        # 恢复目标地址
                        if checkpoint.get("targets"):
                            self.targets = set(checkpoint["targets"])
                        # 根据断点中的 mode 字段恢复对应模式
                        checkpoint_mode = checkpoint.get("mode", mode)
                        if checkpoint_mode == "range":
                            # 从断点继续范围扫描
                            range_start = checkpoint.get("current_position", kwargs.get("start", 1))
                            range_end = checkpoint.get("range_end", kwargs.get("end", 2**32))
                            kwargs["start"] = range_start
                            kwargs["end"] = range_end
                            mode = "range"
                            logger.info(f"范围扫描从 {range_start} 继续到 {range_end}")
                        elif checkpoint_mode == "brute_force":
                            # 从断点继续暴力穷举
                            start_pos = checkpoint.get("current_position", kwargs.get("start", 1))
                            kwargs["start"] = start_pos
                            mode = "brute_force"
                            logger.info(f"暴力穷举从 {start_pos} 继续")
                        elif checkpoint_mode == "random":
                            # 随机模式直接启动，恢复统计数据
                            mode = "random"
                except (RuntimeError, OSError, ValueError) as e:
                    logger.error(f"从断点恢复失败: {e}")
                    # RL-1修复: 启动失败时清理已初始化的资源
                    self.checkpoint_mgr = None  # 清理可能损坏的checkpoint
                    # 继续使用原始参数启动

            self._stop_event.clear()
            self._running = True
            # 重置统计更新事件（确保每次启动都是新状态）
            self._stats_updated.set()  # 初始为已更新状态

            if mode == "random":
                target_fn = self.random_search
            elif mode == "range":

                def target_fn():
                    return self.range_scan(kwargs.get("start", 1), kwargs.get("end", 2**32))

            elif mode == "brute_force":

                def target_fn():
                    return self.brute_force(kwargs.get("start", 1), kwargs.get("max_keys"))

            logger.info(
                f"启动工作线程: {target_fn.__name__ if hasattr(target_fn, '__name__') else 'lambda'}"
            )
            self._thread = threading.Thread(target=target_fn, daemon=True)
            self._thread.start()
            logger.info("对撞引擎启动完成")
        except (RuntimeError, OSError, ValueError) as e:
            logger.error(f"启动对撞引擎失败: {e}")
            # RL-1修复: 启动失败时清理资源
            self._running = False
            self._stop_event.set()
            # 清理可能已初始化的资源
            if hasattr(self, "_executor") and self._executor:
                try:
                    self._executor.shutdown(wait=False)
                except Exception as cleanup_error:
                    # A类修复: 资源清理失败添加DEBUG日志
                    logger.debug(f"清理线程池失败（启动失败时）: {cleanup_error}")
            raise

    def stop(self, timeout: float | None = None) -> None:
        """停止对撞

        参数:
            timeout: 等待工作线程结束的超时时间（秒）
                    None时使用默认值（根据目标数动态计算，最少10秒）
        """
        logger.info("正在停止对撞引擎...")

        with self._stop_reason_lock:
            self._engine_stop_reason = "user_stopped"  # v3.5.2: 必须在下述信号前设置
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
            matches_list = (
                [
                    {"private_key_hash": m["private_key_hash"], "address": m["address"]}
                    for m in self.stats.matches
                ]
                if hasattr(self.stats, "matches")
                else []
            )
            try:
                self.checkpoint_mgr.save(
                    mode=self._current_mode,
                    targets=self.targets,
                    current_position=self._current_position,
                    total_checked=self.stats.total_checked,
                    matches=matches_list,
                    range_start=self._range_start,
                    range_end=self._range_end,
                )
                logger.info("断点保存成功")
            except (RuntimeError, OSError, ValueError) as e:
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
                except (RuntimeError, OSError, ValueError) as e:
                    logger.error(f"保存最终数据失败: {e}")

        # 清理去重过滤器（释放内存）
        if self.dedup_filter and self.dedup_filter.enabled:
            stats = self.dedup_filter.get_stats()
            logger.info(
                f"清理去重过滤器: 检查={stats['checks_total']}, 重复={stats['duplicates_found']}, "
                f"跟踪={stats['tracked_total']}"
            )
            self.dedup_filter.reset()
            logger.info("去重过滤器已清理")

        # 显式关闭线程池（如果还在运行）
        if self._executor:
            logger.info("关闭线程池...")
            self._executor.shutdown(wait=False)  # 不等待，立即关闭
            self._executor = None

        # 重置引擎状态（支持重启）
        was_thread_alive = self._thread is not None and self._thread.is_alive()
        with self._stop_reason_lock:
            self._engine_stop_reason = "user_stopped"  # v3.5.2: 标记用户主动停止
        self._stop_event.clear()
        self._running = False
        self._thread = None

        # v3.5.2: 发布 ENGINE_STOP 事件（仅当线程曾被中断时）
        if was_thread_alive:
            try:
                snap = self.stats.snapshot()
                self.event_bus.publish(EngineStopEvent(
                    reason="user_stopped",
                    total_checked=snap.total_checked,
                ))
            except (RuntimeError, OSError, ValueError) as e:
                logger.debug(f"发布 ENGINE_STOP 事件失败（非致命）: {e}")

        logger.info("对撞引擎已停止")

    def is_running(self) -> bool:
        """
        检查碰撞引擎是否正在运行

        返回:
            True 表示引擎正在运行（已启动且工作线程存活），
            False 表示引擎已停止或未启动
        """
        return cast(bool, self._running and self._thread and self._thread.is_alive())

    def __enter__(self) -> "KeyCollisionEngine":
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        self.stop()
        return

    def __del__(self) -> None:
        # H-2修复: 添加异常处理记录，避免静默吞掉异常
        #
        # 析构函数异常处理说明:
        # 1. 析构函数中的异常默认被忽略，可能导致问题被隐藏
        # 2. 使用 logging 模块记录异常，提高问题可追溯性
        # 3. 避免静默失败，确保清理过程中的问题被记录
        #
        # 注意:
        # - 记录警告级别日志，不抛出异常（析构函数不能抛出异常）
        # - 异常通常是资源清理问题，不影响主要功能
        # - 更好的做法是使用上下文管理器确保资源正确清理
        try:
            if self._running:
                self.stop()
        except (RuntimeError, OSError, ValueError) as e:
            # 记录析构函数中的异常，而不是静默忽略
            logger.warning(f'析构函数资源清理异常（非致命）: {type(e).__name__}: {e}')

    def get_stats(self) -> CollisionStats:
        """
        获取当前碰撞统计信息

        返回:
            CollisionStats 对象，包含总检查数、匹配数、运行时间等统计信息

        注意:
            返回的是原始 stats 对象的引用，外部修改会影响内部状态
            P2修复: 包含_live_range_count确保实时统计数据准确
            线程安全: 使用stats.update()确保正确的锁保护
        """
        if self.stats:
            with self._state_lock:
                live_count = self._live_range_count

            if live_count > 0:
                # 有实时计数：合并到 stats。
                # 注意：不重置 _live_range_count，它由主循环自行管理。
                # 将 live_count 直接作为近似总计数更新到 stats。
                # （主循环会定期调用 stats.update(safe_count)，其中 safe_count = total_count + _live_range_count） # noqa: E501
                self.stats.update(max(live_count, self.stats.total_checked))
            elif self.stats.start_time > 0 and self.stats.total_checked > 0:
                # 即使 live_range_count 为 0，也尝试刷新 elapsed 和 speed
                elapsed = time.time() - self.stats.start_time
                if elapsed > 0:
                    with self.stats._lock:
                        self.stats.elapsed = elapsed
                        self.stats.speed = self.stats.total_checked / elapsed

        return self.stats


# 注意: GPU加速功能已迁移到 gpu_collision_engine.py
# 使用方式:
# from src.collision import create_collision_engine
# engine = create_collision_engine(targets, mode='gpu') # 强制GPU
# engine = create_collision_engine(targets, mode='auto') # 自动选择
# 或直接导入:
# from src.collision.gpu_collision_engine import GPUCollisionEngine
