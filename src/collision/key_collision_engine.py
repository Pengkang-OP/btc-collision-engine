"""Bitcoin private key collision engine.

Detects Bitcoin address collisions by generating private keys and
matching against target addresses using CPU and GPU acceleration.
"""

import concurrent.futures
import hashlib
import os
import threading
import time
from typing import Any, cast

import psutil

# v4.2.1迁移: 使用crypto_backend替代secp256k1.py（性能提升1000倍）
from ..core.base58 import Base58
from ..core.crypto_backend import BackendType, crypto_manager
from ..core.optimized_address_generator import OptimizedP2PKHAddressGenerator
from ..core.secp256k1 import Secp256k1
from ..core.secure_key_manager import SecureKeyManager

# 线程池配置校验
from ..core.thread_pool import _validate_worker_count

# WIF 编码（匹配结果导出）
from ..core.wif import WIF
from ..i18n import _t
from ..log_engine.log_processor import SensitiveDataFilter
from ..monitoring.data_logger import DataLogger
from ..monitoring.enhanced_monitoring import EnhancedMonitoringSystem
from ..utils import get_configured_logger
from ..utils.exception_handler import ExceptionHandler
from ..utils.logger import get_sampled_logger
from ..utils.timeout import invoke_with_timeout
from .base_engine import BaseCollisionEngine
from .checkpoint_manager import CheckpointManager
from .collision_stats import CollisionStats
from .deduplication_filter import DeduplicationFilter

# v4.2.1: 事件系统支持
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

from ._engine_constants import (
    BATCH_SIZE,
    BATCH_TUNE_1_2_CORE,
    BATCH_TUNE_4_CORE,
    BATCH_TUNE_8_CORE,
    BATCH_TUNE_16_CORE,
    BATCH_TUNE_32_CORE,
    BATCH_TUNE_64_PLUS_CORE,
    COMPRESSION_AUTO_THRESHOLD,
    CPU_CACHE_INTERVAL_SEC,
    ERROR_LOG_INTERVAL_SEC,
    MATCH_BATCH_FLUSH_THRESHOLD,
    MEMORY_CRITICAL_THRESHOLD_MB,
    MEMORY_DOWNGRADE_COOLDOWN_SEC,
    MEMORY_HIGH_THRESHOLD_MB,
    PROGRESS_INTERVAL_COUNT,
    PROGRESS_INTERVAL_COUNT_DEFAULT,
    PROGRESS_INTERVAL_SEC,
)

# 获取模块日志记录器
# v4.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
logger = get_configured_logger("KeyCollisionEngine")
sampled_logger = get_sampled_logger("KeyCollisionEngine.sampled", sample_rate=1000)


class KeyCollisionEngine(BaseCollisionEngine):
    """Bitcoin private key collision engine (CPU implementation).

    Inherits BaseCollisionEngine, implements a complete CPU collision
    engine supporting:
    - 三种搜索模式: 随机碰撞、范围扫描、暴力穷举
    - 多线程并行处理 (ThreadPoolExecutor)
    - 断点续传 (CheckpointManager)
    - 去重过滤 (DeduplicationFilter)
    - 事件驱动架构 (EventBus, v3.2.0)
    - 增强监控系统 (EnhancedMonitoringSystem)
    - 性能优化预计算表 (v2.2.0)
    - crypto_backend多后端支持 (v2.2.1)
    - 内存监控自动降级 (M13)
    - 地址双格式检查 (v3.2.1)
    - P2PKH目标地址过滤 (v4.3.1)

    安全特性:
    - SecureKeyManager 私钥生命周期管理
    - 匹配回调超时控制与异常隔离
    - 审计日志记录
    """

    def __init__(
        self,
        targets: set[str],
        # v4.2.1: 统一类型提示
        on_progress: ProgressCallback | None = None,
        on_match: MatchCallback | None = None,
        on_complete: CompleteCallback | None = None,
        checkpoint_enabled: bool = False,
        dedup_enabled: bool = False,
        dedup_max_size: int = 1_000_000,
        checkpoint_interval: int = 30,
        max_workers: int | None = None,
        # v4.2.1: 事件总线支持
        event_bus: EventBus | None = None,
        data_logging_enabled: bool = True,
        data_logging_interval: int = 5,
        verbose_logging: bool = False,
        use_enhanced_monitoring: bool = True,  # 默认启用增强监控
        # 性能优化参数 (v4.2.1新增)
        use_performance_optimization: bool = True,
        precomputed_window_size: int = 8,
        use_simd_hash: bool = True,
        use_memory_pool: bool = True,
        # v4.2.1: crypto_backend支持
        crypto_backend_type: str | None = None,  # 'coincurve', 'openssl', 'ecdsa', 'pure_python'
        # 地址格式支持 (v4.2.1新增)
        check_uncompressed: bool | None = None,
    ) -> None:  # 是否同时检查非压缩格式地址, None表示自动检测
        """Args:
            targets: 目标地址集合 (set, O(1)查找)
            on_progress: 进度回调 fn(stats: CollisionStats)
            on_match: 匹配回调 fn(private_key: bytes, address: str, wif: str)
                [WARN] 安全注意:
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
            event_bus: 事件总线实例（v4.2.1新增，None则自动创建）
            data_logging_enabled: 是否启用数据日志记录
            data_logging_interval: 数据日志记录间隔(秒)
            verbose_logging: 是否启用详细日志（生产环境建议False）
            use_enhanced_monitoring: 是否使用增强监控系统（默认True，包含异常检测和告警）

            # 性能优化参数 (v4.2.1新增)
            use_performance_optimization: 是否启用性能优化（默认True）
            precomputed_window_size: 预计算表窗口大小4-8（默认8）
            use_simd_hash: 是否使用SIMD哈希优化（默认True）
            use_memory_pool: 是否使用内存池（默认True）

            # v4.2.1: crypto_backend支持
            crypto_backend_type: 加密后端类型（默认自动选择最佳后端）

            # 地址格式支持 (v4.2.1新增)
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
        # 使用 TargetResolver 解析并标准化所有目标地址
        # 将 Bech32/Bech32m 地址转换为 P2PKH 格式，确保匹配正确
        from .targets import TargetResolver

        resolver = TargetResolver(enable_cache=True)
        resolved_targets = set()
        self.target_hash160s: set[bytes] = set()
        self._hash160_to_target: dict[bytes, str] = {}
        for addr in targets:
            resolved = resolver.resolve(addr)
            if resolved:
                resolved_targets.add(resolved.lower())
                if resolved.lower() != addr.lower():
                    logger.debug("目标地址转换: %s -> %s", addr, resolved)
                # v4.2.1: 从原始解析地址提取 Hash160（大小写敏感的 Base58 解码）
                try:
                    _, payload = Base58.check_decode(resolved)
                    self.target_hash160s.add(payload)
                    self._hash160_to_target[payload] = resolved  # Hash160→目标地址映射
                except (ValueError, TypeError):
                    logger.warning(f"目标地址 Base58 解码失败，将从对撞目标中移除: {resolved[:20]}...")
                    resolved_targets.discard(resolved.lower())  # C1修复: 移除无法提取Hash160的目标地址
        self.targets = resolved_targets
        if len(self.targets) != len(targets):
            logger.warning(f"目标地址解析后数量变化: 输入={len(targets)}, 有效={len(self.targets)}")

        # v4.2.1: 事件总线初始化
        self.event_bus = event_bus or EventBus()

        # 向后兼容: 保留回调
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete

        # v4.2.1: 地址格式支持配置（智能检测）
        if check_uncompressed is None:
            self.check_uncompressed = self._auto_detect_compression_needed()
            logger.info(
                f"自动检测地址格式: {'启用双格式检查' if self.check_uncompressed else '仅检查压缩格式'}",
            )
        else:
            self.check_uncompressed = check_uncompressed

        # 性能优化: 选择优化版或标准版地址生成器 (v4.2.1)
        if use_performance_optimization:
            self.generator = OptimizedP2PKHAddressGenerator(
                use_precomputed_table=True,
                use_simd_hash=use_simd_hash,
                use_memory_pool=use_memory_pool,
                window_size=precomputed_window_size,
            )
            logger.info(
                "KeyCollisionEngine 使用优化版地址生成器: window_size=%s, simd=%s, pool=%s",
                precomputed_window_size,
                use_simd_hash,
                use_memory_pool,
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
        # v4.2.1: 跟踪停止原因
        # 线程安全说明: 主线程 (stop()) 写入, 后台工作线程读取后重置。
        # 依靠 _stop_event.set() 的 happens-before 保证 + CPython GIL 实现安全。
        self._engine_stop_reason: str = "normal"
        self._thread: threading.Thread | None = None
        self.progress_interval = PROGRESS_INTERVAL_COUNT  # 每N次检测触发一次进度回调

        # 日志记录
        logger.info(
            f"KeyCollisionEngine 初始化完成: P2PKH目标数={len(self.targets)}, "
            f"断点={checkpoint_enabled}, 去重={dedup_enabled}, "
            f"工作线程={max_workers or '默认'}",
        )
        # 断点管理器
        self.checkpoint_mgr = (
            CheckpointManager(auto_save_interval=checkpoint_interval) if checkpoint_enabled else None
        )
        # 去重过滤器
        self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size, enabled=dedup_enabled)
        # 线程池配置
        # 校验并记录最终使用的 max_workers
        self._cpu_count = os.cpu_count() or 4
        self.max_workers = _validate_worker_count(max_workers) if max_workers is not None else None
        if self.max_workers is not None:
            logger.info(
                f"KeyCollisionEngine 自定义线程: max_workers={self.max_workers}, "
                f"CPU={self._cpu_count}核",
            )
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        # 当前位置（用于断点保存）
        self._current_position = 0
        self._current_mode = ""
        self._range_start: int | None = None
        self._range_end: int | None = None

        # v4.2.1: 初始化crypto_backend
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
        self._progress_interval_count = PROGRESS_INTERVAL_COUNT_DEFAULT
        self._last_progress_time = 0.0
        self._batch_counter = 0  # P2-5修复: batch计数器

        # M13: 内存监控自动降级
        self._memory_high_threshold_mb = MEMORY_HIGH_THRESHOLD_MB
        self._memory_critical_threshold_mb = MEMORY_CRITICAL_THRESHOLD_MB
        self._last_memory_downgrade_time = 0.0  # 上次降级时间
        self._memory_downgrade_cooldown = MEMORY_DOWNGRADE_COOLDOWN_SEC

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

        # v4.2.1: 初始化数据日志系统（使用事件适配器）
        self._init_monitoring(data_logging_enabled, data_logging_interval, use_enhanced_monitoring)

        # CPU使用率缓存（避免频繁阻塞）
        # 线程安全：仅在主线程的_log_data_metrics中访问
        self._cached_cpu_percent = 0.0
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

        # 初始化状态标记（用于验收测试生命周期验证）
        self._initialized = True

        # 测试模式：最大处理私钥数（None=无限）
        self._max_keys: int | None = None

    def _safe_invoke_match_callback(
        self,
        private_key: bytes,
        address: str,
        wif: str,
    ) -> bool:
        """安全调用匹配回调，带超时和异常隔离。

        Args:
            private_key: 私钥
            address: 匹配到的地址
            wif: WIF格式私钥

        Returns:
            True if callback was invoked, False otherwise

        """
        if not self.on_match:
            return True
        try:
            invoke_with_timeout(
                self.on_match,
                args=(private_key, address, wif),
                timeout=self._match_callback_timeout,
            )
            return True
        except Exception:
            logger.exception("匹配回调执行异常（已隔离）")
            return False

    def _init_monitoring(
        self,
        data_logging_enabled: bool,
        data_logging_interval: int,
        use_enhanced_monitoring: bool,
    ) -> None:
        """初始化数据日志和监控系统

        v4.2.2 H6重构: 从 __init__ 提取监控初始化代码（~35行），减少 __init__ 复杂度。

        Args:
            data_logging_enabled: 是否启用数据日志
            data_logging_interval: 数据记录间隔（秒）
            use_enhanced_monitoring: 是否使用增强监控系统

        """
        if not data_logging_enabled:
            return

        try:
            from src.monitoring.event_adapters import setup_data_logging
            from src.monitoring.monitor_config import MonitorConfig

            if use_enhanced_monitoring:
                # 使用增强监控系统（推荐）
                self.enhanced_monitoring = EnhancedMonitoringSystem(
                    engine=self,
                    config=MonitorConfig(
                        collection_interval=data_logging_interval,
                        enable_monitoring_data=False,
                    ),
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
                    event_bus=self.event_bus,
                    data_logger=DataLogger(),
                )
                self.data_logger = self.data_logger_adapter.data_logger
                logger.info("数据日志系统已启用（事件驱动模式）")
        except Exception as e:
            logger.warning("数据日志系统初始化失败，已禁用: %s", e, exc_info=True)
            self.data_logging_enabled = False
            self.data_logger = None
            self.enhanced_monitoring = None

    def _generate_and_check_secure(self) -> tuple[bytes, str] | None:
        """使用安全密钥管理器生成私钥并检查匹配。

        使用SecureKeyManager确保私钥在使用后立即清零，
        防止私钥在内存中残留。

        同时检查压缩和非压缩格式地址，与主热路径 _worker_process_key 保持一致。

        Returns:
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

            # 验证范围: 私钥必须在 [1, Secp256k1.N) 范围内
            if k < 1 or k >= Secp256k1.N:
                return None

            # 生成地址
            address, compressed_pk, uncompressed_pk = self.generator.generate_address(private_key)

            # 检查匹配（v4.2.1 O1: Hash160 二进制比较）
            # 先检查压缩格式
            compressed_hash160 = self.generator.public_key_to_hash160(compressed_pk)
            if compressed_hash160 in self.target_hash160s:
                # 找到匹配时，返回私钥的副本
                # 注意：调用者需要负责安全处理这个副本
                return (bytes(private_key), address)

            # 再检查非压缩格式（与主热路径一致，确保不遗漏非压缩地址目标）
            if self.check_uncompressed:
                uncompressed_hash160 = self.generator.public_key_to_hash160(uncompressed_pk)
                if uncompressed_hash160 in self.target_hash160s:
                    uncompressed_addr = self.generator.public_key_to_address(uncompressed_pk)
                    return (bytes(private_key), uncompressed_addr)

            # 退出上下文时私钥自动清零
            return None

    def _save_checkpoint(self, count: int) -> None:
        """保存当前进度到断点文件

        将当前碰撞进度保存到 JSON 格式的断点文件中，支持断点续传功能。
        仅在启用了断点管理且满足自动保存间隔条件时执行实际保存操作。

        Args:
            count: 当前已检查的私钥数量

        注意:
            - 仅在 checkpoint_enabled=True 且满足保存间隔时执行
            - 使用 CheckpointManager 的线程安全方法
            - 保存的信息包括：模式、目标、位置、已检查数、匹配结果
            - random模式不保存当前位置（因为是随机生成）
        """
        if self.checkpoint_mgr and self.checkpoint_mgr.should_auto_save:
            # 通过 snapshot() 获取线程安全的匹配列表快照，避免无锁迭代 self.stats.matches
            snap = self.stats.snapshot()
            matches_list = (
                [
                    {"private_key_hash": m["private_key_hash"], "address": m["address"]}
                    for m in snap.matches
                ]
                if hasattr(snap, "matches") and snap.matches
                else []
            )

            # random模式不保存位置（随机生成无位置概念）
            position = self._current_position if self._current_mode != "random" else 0

            self.checkpoint_mgr.save(
                {
                    "mode": self._current_mode,
                    "targets": list(self.targets),
                    "current_position": position,
                    "total_checked": count,
                    "matches": matches_list,
                    "range_start": self._range_start,
                    "range_end": self._range_end,
                },
            )

    def _log_data_metrics(self, count: int, speed: float) -> None:
        """记录数据日志指标

        线程安全说明：
            此方法仅在主线程调用（通过进度更新循环），
            工作线程不直接调用此方法，因此无需额外的锁保护。

        在满足间隔条件时记录性能、系统和引擎数据到数据日志系统。

        Args:
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
            logger.warning("记录数据指标失败: %s", e, exc_info=True)

    def _check_memory_and_downgrade(self, memory_mb: float, current_time: float) -> None:
        """M13: 内存监控自动降级

        当进程内存使用超过阈値时，自动降低 batch_size 和 max_workers
        以降低内存压力，防止程序 OOM 崩溃。

        Args:
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
                    f"将下次启动的 max_workers 配置: {old_workers} -> {self.max_workers}",
                )
            else:
                logger.warning(
                    f"[M13 内存降级] 内存使用 {memory_mb:.0f}MB 达临界阈値 "
                    f"{self._memory_critical_threshold_mb}MB，"
                    f"本次运行已将 batch_size: {old_batch} -> {new_batch}",
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
                    f"batch_size: {old_batch} -> {new_batch}",
                )
                self._last_memory_downgrade_time = current_time

    def _tune_batch_size(self) -> None:
        """P3-9修复: 根据CPU核心数自动调整batch_size

        v4.2.2 S2: 扩展自适应范围，支持 64 核 → 8000。

        调优策略:
        - 1-2核: 500
        - 4核: 1000
        - 8核: 2000
        - 16核: 4000
        - 32核: 6000
        - 64核+: 8000

        目标: 平衡内存使用和并行效率
        """
        if not self._auto_tune_batch_size:
            return

        cpu_count = self._cpu_count

        if cpu_count <= 2:
            optimal_batch_size = BATCH_TUNE_1_2_CORE
        elif cpu_count <= 4:
            optimal_batch_size = BATCH_TUNE_4_CORE
        elif cpu_count <= 8:
            optimal_batch_size = BATCH_TUNE_8_CORE
        elif cpu_count <= 16:
            optimal_batch_size = BATCH_TUNE_16_CORE
        elif cpu_count <= 32:
            optimal_batch_size = BATCH_TUNE_32_CORE
        else:
            optimal_batch_size = BATCH_TUNE_64_PLUS_CORE

        old_batch_size = self._batch_size
        self._batch_size = optimal_batch_size

        if old_batch_size != optimal_batch_size:
            logger.info(
                "P3-9 Batch自动调整: %s->%s (CPU=%s核)",
                old_batch_size,
                optimal_batch_size,
                cpu_count,
            )

    def _auto_detect_compression_needed(self) -> bool:
        """智能检测是否需要检查非压缩格式地址

        检测策略:
        - 压缩和非压缩公钥的 Hash160 不同，生成的 P2PKH 地址也不同；
          仅从地址字符串无法判断原始钱包使用的公钥格式，故需双格式检查
        - 默认始终启用双格式检查以确保不漏掉非压缩地址的匹配
        - 仅在目标数 >= COMPRESSION_AUTO_THRESHOLD 时自动切为仅压缩格式（性能优先）
        - 用户可通过 check_uncompressed 参数显式覆盖此行为

        Returns:
            bool: 是否需要检查非压缩格式
        """
        target_count = len(self.targets)

        # P2PKH 地址无法区分压缩/非压缩来源（Hash160(compressed_pk) ≠ Hash160(uncompressed_pk)），
        # 优先保证不漏匹配；大规模目标集时性能优先切为仅压缩
        # v4.2.1.1: 从50000降至10000，减少大规模场景下的漏匹配风险
        if target_count < COMPRESSION_AUTO_THRESHOLD:
            logger.debug("目标地址数=%s < %s，启用双格式检查", target_count, COMPRESSION_AUTO_THRESHOLD)
            return True
        logger.warning(
            "目标地址数=%s >= %s，自动切换为仅检查压缩格式（性能优先）。"
            "注意：非压缩P2PKH地址将不会被匹配！"
            "如需确保匹配所有地址，请设置 check_uncompressed=True 或减少目标地址数量。",
            target_count,
            COMPRESSION_AUTO_THRESHOLD,
        )
        return False

    def _init_crypto_backend(self, backend_type: str | None = None) -> None:
        """初始化加密后端（v4.2.1新增）

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
                        logger.info("加密后端已设置为: %s", backend_type)
                    else:
                        logger.warning("加密后端设置失败: %s，使用默认后端", backend_type)
                else:
                    logger.warning("未知的加密后端类型: %s，使用默认后端", backend_type)

            # 获取当前后端信息
            backend = crypto_manager.current_backend
            logger.info(f"加密后端初始化完成: {backend.name}, 恒定时间={backend.is_constant_time()}")

        except (RuntimeError, OSError, ValueError) as e:
            logger.error("加密后端初始化失败: %s", e, exc_info=True)
            raise

    def _log_throttled_error(
        self,
        error_type: str,
        message: str,
        exception: Exception,
        worker_id: int,
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
            try:
                self.data_logger.record_error(
                    error_type=error_type,
                    message=safe_message,
                    exception=safe_exception,
                    context={"worker_id": worker_id},
                )
            except (RuntimeError, OSError, AttributeError) as e:
                logger.debug("记录错误到data_logger失败（非致命）: %s", e)

    def _resolve_target_address(self, matched_address: str, hash160: bytes | None = None) -> str:
        """从引擎生成的 P2PKH 地址反查 self.targets 中的原始目标地址

        M3优化: 若调用方已持有 Hash160，直接查映射避免重复 Base58 解码。

        Args:
            matched_address: 引擎生成的 P2PKH 地址
            hash160: 该地址的 Hash160（可选，传入则跳过 Base58 解码）

        Returns:
            self.targets 中对应的原始目标地址，查找失败时返回匹配地址本身

        """
        if hash160 is not None:
            return self._hash160_to_target.get(hash160, matched_address)
        try:
            _, payload = Base58.check_decode(matched_address)
            return self._hash160_to_target.get(payload, matched_address)
        except (ValueError, TypeError):
            return matched_address

    def _process_key_match(
        self,
        private_key,
        matched_address: str,
        matched_compressed: bool,
        local_matches: list,
        worker_id: int,
        matched_hash160: bytes | None = None,
    ) -> bool:
        """处理密钥匹配：WIF编码、记录匹配、触发回调

        P1-1重构: 从 _random_search_worker 提取匹配处理逻辑。

        Args:
            private_key: 匹配的私钥（bytes或memoryview）
            matched_address: 匹配的比特币地址
            matched_compressed: 是否为压缩格式地址
            local_matches: 本地匹配结果列表（可变）
            worker_id: 工作线程ID
            matched_hash160: 匹配地址的 Hash160（可选，M3优化: 避免批量flush时重复Base58解码）

        Returns:
            True 表示应继续运行，False 表示应停止引擎

        """
        try:
            pk_bytes = bytes(private_key) if not isinstance(private_key, bytes) else private_key
            # v4.2.2 H4修复: 根据匹配地址类型决定WIF压缩标志
            wif = WIF.encode(pk_bytes, compressed=matched_compressed)
            local_matches.append((pk_bytes, matched_address, wif, matched_hash160))
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(
                f"Random worker {worker_id}: WIF编码错误 addr={matched_address}: {type(e).__name__}",
            )
            # v4.2.1: 发布 ENGINE_ERROR 事件
            try:
                self.event_bus.publish(
                    EngineErrorEvent(
                        error_type="wif_encode_error",
                        error_message=str(e),
                        exception=e,
                        context={"worker_id": worker_id, "address": matched_address},
                        recoverable=True,
                    ),
                )
            except (AttributeError, RuntimeError, TypeError) as e:
                logger.debug(
                    "Random worker %s: EventBus publish 失败（非致命）: %s",
                    worker_id,
                    e,
                    exc_info=True,
                )
            return True  # 继续运行
        except (MemoryError, RuntimeError) as e:
            logger.exception(
                "Random worker %s: WIF编码未知错误 addr=%s: %s",
                worker_id,
                matched_address,
                e,
            )
            return True  # 继续运行

        # 记录匹配发现
        format_type = "压缩" if matched_compressed else "非压缩"
        logger.info("🎯 发现匹配! 地址=%s (格式: %s)", matched_address, format_type)

        # 批量提交匹配结果（v4.2.2 H6重构: 提取到 _flush_match_batch）
        should_continue, stop_flag = self._flush_match_batch(local_matches, force=not self.on_match)
        if stop_flag:
            self._stop_event.set()
            return False
        return should_continue

    def _flush_match_batch(self, local_matches: list, force: bool = False) -> tuple[bool, bool]:
        """批量提交匹配结果（v4.2.2 H6重构: 从 _process_key_match 和 worker 末尾提取公共逻辑）

        将匹配结果批量提交到 CollisionStats、匹配回调和 EventBus。
        当 local_matches 达到 MATCH_BATCH_FLUSH_THRESHOLD 或 force=True 时触发。

        Args:
            local_matches: 本地匹配结果列表，提交后会被清空
            force: 强制提交（即使未达到批量阈值），用于 worker 退出时

        Returns:
            (should_continue, stop_flag) 元组
            - should_continue: False 表示应停止引擎（无 on_match 回调时的行为）
            - stop_flag: True 表示需要调用者设置 _stop_event

        """
        if not local_matches:
            return True, False

        if not force and len(local_matches) < MATCH_BATCH_FLUSH_THRESHOLD:
            return True, False

        # 提交到统计
        for pk, addr, _wif_str, _h160 in local_matches:
            self.stats.add_match(pk, addr)

        # 触发匹配回调
        if self.on_match:
            for pk, addr, wif_str, _h160 in local_matches:
                self._safe_invoke_match_callback(pk, addr, wif_str)

        # 发布 ENGINE_MATCH 事件（stats.add_match 之后，确保统计已更新）
        for _pk, addr, _wif, h160 in local_matches:
            try:
                self.event_bus.publish(
                    EngineMatchEvent(
                        private_key=b"",  # 安全: 不暴露私钥
                        address=addr,
                        wif="",  # 安全: WIF即私钥，不通过EventBus传递
                        target_address=self._resolve_target_address(addr, h160),
                    ),
                )
            except (AttributeError, RuntimeError, TypeError) as e:
                logger.warning("发布 ENGINE_MATCH 事件失败（非致命）: %s", e)

        local_matches.clear()

        # 如果没有 on_match 回调，找到匹配后应停止
        if not self.on_match:
            logger.info("找到匹配且无回调，停止对撞")
            return False, True

        return True, False

    def _worker_process_key(
        self,
        private_key: bytes,
        worker_id: int,
        local_matches: list[tuple[bytes, str, str, bytes | None]],
        recent_keys_list: list[bytes],
        recent_keys_set: set[bytes],
        max_recent_size: int,
        _half_size: int,
        local_count: int,
        batch_count: int,
    ) -> tuple[int, int, list[bytes], set[bytes], bool]:
        """处理单个私钥：验证、去重、生成地址、匹配检查。"""
        k = int.from_bytes(private_key, "big")
        if k < 1 or k >= Secp256k1.N:
            return (
                local_count,
                batch_count,
                recent_keys_list,
                recent_keys_set,
                True,
            )

        # 短期缓存 + 去重检查（M1优化: 使用list+set组合）
        key_fp = hashlib.sha256(private_key).digest()[:8]
        if key_fp in recent_keys_set:
            return (
                local_count,
                batch_count,
                recent_keys_list,
                recent_keys_set,
                True,
            )

        if not self.dedup_filter.check_and_add(bytes(private_key)):
            return (
                local_count,
                batch_count,
                recent_keys_list,
                recent_keys_set,
                True,
            )

        # M1优化: 高效缓存管理
        recent_keys_list.append(key_fp)
        recent_keys_set.add(key_fp)
        if len(recent_keys_list) > max_recent_size:
            recent_keys_list = recent_keys_list[_half_size:]
            recent_keys_set = set(recent_keys_list)

        # 生成地址
        try:
            if self.check_uncompressed:
                compressed_addr, compressed_pk, _ = self.generator.generate_address(
                    private_key,
                    compressed=True,
                )
                uncompressed_pk = self.generator.private_key_to_public_key(private_key, compressed=False)
                uncompressed_addr = self.generator.public_key_to_address(uncompressed_pk)
            else:
                compressed_addr, compressed_pk, _ = self.generator.generate_address(
                    private_key,
                    compressed=True,
                )
                uncompressed_pk = None
                uncompressed_addr = None
        except ValueError as e:
            logger.warning("Random worker %s: 私钥无效，跳过: %s", worker_id, e)
            self._log_throttled_error("invalid_key", "随机私钥无效", e, worker_id)
            return (
                local_count,
                batch_count,
                recent_keys_list,
                recent_keys_set,
                True,
            )

        except Exception as e:
            logger.error("Random worker %s: 生成地址失败: %s", worker_id, e, exc_info=True)
            self._log_throttled_error("address_generation_failed", "生成地址失败", e, worker_id)
            return (
                local_count,
                batch_count,
                recent_keys_list,
                recent_keys_set,
                True,
            )

        local_count += 1
        batch_count += 1

        if local_count % 32 == 0:
            with self._state_lock:
                self._live_range_count += 32

        # Hash160 匹配检查
        matched_address = None
        matched_compressed = False
        matched_hash160: bytes | None = None
        compressed_hash160 = self.generator.public_key_to_hash160(compressed_pk)
        if compressed_hash160 in self.target_hash160s:
            matched_address = compressed_addr
            matched_compressed = True
            matched_hash160 = compressed_hash160
        elif self.check_uncompressed and uncompressed_pk:
            uncompressed_hash160 = self.generator.public_key_to_hash160(uncompressed_pk)
            if uncompressed_hash160 in self.target_hash160s:
                matched_address = uncompressed_addr
                matched_compressed = False
                matched_hash160 = uncompressed_hash160

        should_continue = True
        if matched_address:
            should_continue = self._process_key_match(
                private_key,
                matched_address,
                matched_compressed,
                local_matches,
                worker_id,
                matched_hash160,
            )

        return (
            local_count,
            batch_count,
            recent_keys_list,
            recent_keys_set,
            should_continue,
        )

    @staticmethod
    def _log_worker_batch_speed(
        worker_id: int,
        batch_count: int,
        batch_start: float,
        local_count: int,
    ) -> None:
        """记录工作线程批次速度日志（仅 worker 0 且达阈值时）。"""
        if batch_count <= 0:
            return
        batch_time = time.time() - batch_start
        batch_speed = batch_count / batch_time if batch_time > 0 else 0
        if worker_id == 0 and local_count % 10000 == 0:
            sampled_logger.info(
                f"工作线程 {worker_id}: 批次 {batch_count} 私钥, 速度 {batch_speed:.2f}/s",
            )

    def _random_search_worker(self, worker_id: int = 0) -> int:
        """随机碰撞模式的工作线程函数（安全增强版）

        使用SecureKeyManager确保每个私钥在使用后立即清零。

        P1-1重构: 提取 _log_throttled_error / _process_key_match，
        方法从 248 行缩减至 ~160 行。

        Args:
            worker_id: 工作线程标识符，用于日志区分，默认0

        Returns:
            本线程处理的私钥总数
        """
        local_count = 0
        local_matches: list[tuple[bytes, str, str, bytes | None]] = []
        batch_start_time = time.time()

        recent_keys_list: list = []
        recent_keys_set: set = set()
        max_recent_size = 10000
        _half_size = max_recent_size // 2

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

                    (
                        local_count,
                        batch_count,
                        recent_keys_list,
                        recent_keys_set,
                        should_continue,
                    ) = self._worker_process_key(
                        private_key,
                        worker_id,
                        local_matches,
                        recent_keys_list,
                        recent_keys_set,
                        max_recent_size,
                        _half_size,
                        local_count,
                        batch_count,
                    )
                    if not should_continue:
                        break

            if local_count % 100 == 0:
                time.sleep(0.001)

            self._log_worker_batch_speed(worker_id, batch_count, batch_start, local_count)
            time.sleep(0.001)

        self._flush_match_batch(local_matches, force=True)
        if local_matches:
            logger.debug(f"工作线程 {worker_id} 提交了 {len(local_matches)} 个匹配结果")

        remainder = local_count % 32
        if remainder > 0:
            with self._state_lock:
                self._live_range_count += remainder

        worker_time = time.time() - batch_start_time
        worker_speed = local_count / worker_time if worker_time > 0 else 0
        logger.debug(f"工作线程 {worker_id} 结束, 共 {local_count} 私钥, 平均 {worker_speed:.2f}/s")

        return local_count

    def _random_search_setup(self) -> None:
        """随机搜索模式：初始化状态、发布 ENGINE_START、调优内存池、记录数据"""
        logger.info("=" * 60)
        logger.info("启动随机碰撞模式")
        logger.info(f"目标地址数: {len(self.targets)}")

        self._current_mode = "random"
        self._current_position = 0
        self._range_start = None
        self._range_end = None
        self._live_range_count = 0  # 为实时进度显示初始化
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        self._running = True
        self._last_data_log_time = 0.0

        try:
            self.event_bus.publish(
                EngineStartEvent(
                    mode=self._current_mode,
                    target_count=len(self.targets),
                    batch_size=self._batch_size,
                ),
            )
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("发布 ENGINE_START 事件失败（非致命）: %s", e)

    def random_search(self) -> None:
        """随机碰撞模式 - 使用线程池并行生成私钥并比对（优化版）"""
        self._random_search_setup()
        total_count = 0
        num_workers = self._random_search_determine_workers()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            self._executor = executor
            futures = {executor.submit(self._random_search_worker, i): i for i in range(num_workers)}

            while not self._stop_event.is_set() and futures:
                done, _ = concurrent.futures.wait(
                    futures,
                    timeout=0.1,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )

                for future in done:
                    total_count = self._random_search_handle_done(future, futures, total_count, executor)

                # 基于时间和计数的双重进度回调控制
                current_time = time.time()
                should_report = False
                if current_time - self._last_progress_time >= self._progress_interval_sec:
                    should_report = True
                self._batch_counter += 1
                if self._batch_counter >= self._progress_interval_count:
                    should_report = True
                    self._batch_counter = 0

                if should_report:
                    self._random_search_report_progress(total_count, current_time)
                    # 测试模式：达到 max_keys 自动停止
                    if self._max_keys is not None and total_count >= self._max_keys:
                        logger.info("达到最大处理数 %s，自动停止随机搜索", self._max_keys)
                        self._stop_event.set()

        self._random_search_finalize(total_count)

    def _random_search_determine_workers(self) -> int:
        """确定随机搜索的工作线程数。"""
        return self.max_workers or 4

    def _random_search_handle_done(
        self,
        future: concurrent.futures.Future,
        futures: dict,
        total_count: int,
        executor: concurrent.futures.ThreadPoolExecutor,
    ) -> int:
        """处理完成的随机搜索线程，更新计数并提交新线程。"""
        worker_id = futures.get(future)
        try:
            local_count = future.result()
            total_count += local_count
        except concurrent.futures.CancelledError:
            logger.debug("随机搜索线程被取消")
        except KeyboardInterrupt:
            logger.warning("工作线程收到 KeyboardInterrupt，标记为取消")
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("随机搜索线程异常: %s", e)

        # 移除已完成的任务
        futures.pop(future, None)

        # 重新提交失败或取消的 worker，保持 worker 数量稳定
        if worker_id is not None and not self._stop_event.is_set():
            try:
                new_future = executor.submit(self._random_search_worker, worker_id)
                futures[new_future] = worker_id
            except (RuntimeError, OSError) as e:
                logger.error("重新提交工作线程 %s 失败: %s", worker_id, e)

        # 更新实时计数，使 engine_runner 轮询能读取到进度
        with self._state_lock:
            self._live_range_count = total_count

        return total_count

    def _random_search_report_progress(self, total_count: int, current_time: float) -> None:
        """随机搜索进度回调：更新统计、日志。"""
        elapsed = current_time - self.stats.start_time
        speed = total_count / elapsed if elapsed > 0 else 0

        self.stats.update(total_count)
        if self.on_progress:
            invoke_with_timeout(
                self.on_progress,
                args=(self.stats,),
                timeout=5.0,
                callback_name="on_progress",
            )
        self._save_checkpoint(total_count)
        self._log_data_metrics(total_count, speed)

        try:
            self.event_bus.publish(
                EngineProgressEvent(
                    total_checked=total_count,
                    speed=speed,
                    matches_found=self.stats.matches_found,
                    elapsed_time=elapsed,
                ),
            )
        except Exception as e:
            logger.debug("发布 ENGINE_PROGRESS 事件失败（非致命）: %s", e)

        self._last_progress_time = current_time

    def _publish_engine_complete(self, total_count: int) -> None:
        """发布 ENGINE_COMPLETE 事件、记录引擎数据、触发 on_complete 回调。

        CODE-2重构: 从三个 finalize 方法提取公共逻辑，消除重复。
        """
        elapsed = time.time() - self.stats.start_time
        speed = total_count / elapsed if elapsed > 0 else 0

        try:
            stop_reason = self._engine_stop_reason
            self._engine_stop_reason = "normal"
            self.event_bus.publish(
                EngineCompleteEvent(
                    total_checked=total_count,
                    matches_found=self.stats.matches_found,
                    elapsed_time=elapsed,
                    avg_speed=speed,
                    stop_reason=stop_reason,
                ),
            )
        except Exception as e:
            logger.debug("发布 ENGINE_COMPLETE 事件失败（非致命）: %s", e)

        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=False,
                current_position=total_count,
            )

        if self.on_complete:
            invoke_with_timeout(
                self.on_complete,
                args=(self.stats,),
                timeout=5.0,
                callback_name="on_complete",
            )

    def _random_search_finalize(self, total_count: int) -> None:
        """随机搜索结束：更新统计、发布 COMPLETE。"""
        # 合并 live 计数并重置
        with self._state_lock:
            final_count = max(total_count, self._live_range_count)
            self._live_range_count = 0

        self._executor = None
        self._stats_updated.clear()
        self.stats.update(final_count)
        self._stats_updated.set()
        self._running = False

        self._publish_engine_complete(final_count)

    def _worker_generate_addresses(
        self,
        private_key_bytes: bytes,
        worker_id: int,
    ) -> tuple[str, bytes, str | None, bytes | None] | None:
        """为工作线程生成压缩和（可选）未压缩地址。
        返回 (c_addr, c_pub, uc_addr, uc_pk) 或 None 表示跳过。
        """
        try:
            if self.check_uncompressed:
                compressed_addr, compressed_pub, _ = self.generator.generate_address(
                    private_key_bytes,
                    compressed=True,
                )
                uncompressed_pk = self.generator.private_key_to_public_key(
                    private_key_bytes,
                    compressed=False,
                )
                uncompressed_addr = self.generator.public_key_to_address(uncompressed_pk)
            else:
                compressed_addr, compressed_pub, _ = self.generator.generate_address(
                    private_key_bytes,
                    compressed=True,
                )
                uncompressed_addr = None
                uncompressed_pk = None
            return (compressed_addr, compressed_pub, uncompressed_addr, uncompressed_pk)
        except ValueError as e:
            logger.warning("Worker %s: 私钥无效，跳过: %s", worker_id, e)
            return None
        except (RuntimeError, OSError) as e:
            logger.error("Worker %s: 生成地址失败: %s", worker_id, e, exc_info=True)
            return None

    def _worker_check_and_handle_match(
        self,
        private_key,
        matched_address: str,
        matched_compressed: bool,
        matched_hash160: bytes | None,
        worker_id: int,
    ) -> None:
        """处理匹配结果：WIF编码、回调、事件发布、停止信号。"""
        try:
            pk_bytes = bytes(private_key) if not isinstance(private_key, bytes) else private_key
            wif = WIF.encode(pk_bytes, compressed=matched_compressed)
            pk_copy = bytes(private_key)
            self.stats.add_match(pk_copy, matched_address)
            if self.on_match:
                self._safe_invoke_match_callback(pk_copy, matched_address, wif)
            else:
                self._stop_event.set()

            format_type = "压缩" if matched_compressed else "非压缩"
            logger.info("🎯 发现匹配! 地址=%s (格式: %s)", matched_address, format_type)

            try:
                self.event_bus.publish(
                    EngineMatchEvent(
                        # 安全: 不通过 EventBus 传递私钥/WIF（EventBus 为广播机制）
                        # 匹配数据通过 on_match 回调安全传递
                        private_key=b"",
                        address=matched_address,
                        wif="",
                        target_address=self._resolve_target_address(matched_address, matched_hash160),
                    ),
                )
            except Exception as e:
                logger.debug("发布 ENGINE_MATCH 事件失败（非致命）: %s", e)

        except (ValueError, TypeError, OverflowError) as e:
            err_type = type(e).__name__
            logger.error(
                "Worker %s: 匹配参数错 addr=%s: %s: %s",
                worker_id,
                matched_address,
                err_type,
                e,
            )
            try:
                self.event_bus.publish(
                    EngineErrorEvent(
                        error_type="wif_encode_error",
                        error_message=str(e),
                        exception=e,
                        context={"worker_id": worker_id, "address": matched_address},
                        recoverable=True,
                    ),
                )
            except (AttributeError, RuntimeError, TypeError) as e:
                logger.debug(
                    "Worker %s: EventBus publish 失败（非致命）: %s",
                    worker_id,
                    e,
                    exc_info=True,
                )
        except (MemoryError, RuntimeError) as e:
            logger.exception("Worker %s: 匹配处理未知错误 addr=%s: %s", worker_id, matched_address, e)

    def _range_scan_worker(self, worker_start: int, worker_end: int, worker_id: int) -> int:
        """范围扫描模式的工作线程函数"""
        local_count = 0

        with SecureKeyManager() as key_mgr:
            for k in range(worker_start, worker_end + 1):
                if self._stop_event.is_set():
                    break

                if k < 1 or k >= Secp256k1.N:
                    continue

                key_mgr.generate_key(k.to_bytes(32, "big"))
                private_key = key_mgr.get_key()
                private_key_bytes = bytes(private_key)

                result = self._worker_generate_addresses(private_key_bytes, worker_id)
                if result is None:
                    continue
                compressed_addr, compressed_pub, uncompressed_addr, uncompressed_pk = result

                local_count += 1

                if local_count % 32 == 0:
                    with self._state_lock:
                        self._live_range_count += 32

                # Hash160 匹配检查
                matched_address = None
                matched_compressed = False
                matched_hash160: bytes | None = None

                compressed_hash160 = self.generator.public_key_to_hash160(compressed_pub)
                if compressed_hash160 in self.target_hash160s:
                    matched_address = compressed_addr
                    matched_compressed = True
                    matched_hash160 = compressed_hash160
                elif self.check_uncompressed and uncompressed_pk:
                    uncompressed_hash160 = self.generator.public_key_to_hash160(uncompressed_pk)
                    if uncompressed_hash160 in self.target_hash160s:
                        matched_address = uncompressed_addr
                        matched_compressed = False
                        matched_hash160 = uncompressed_hash160

                if matched_address:
                    self._worker_check_and_handle_match(
                        private_key,
                        matched_address,
                        matched_compressed,
                        matched_hash160,
                        worker_id,
                    )

        remainder = local_count % 32
        if remainder > 0:
            with self._state_lock:
                self._live_range_count += remainder

        return local_count

    def _range_scan_setup(self, start: int, end: int) -> int:
        """range_scan 初始化状态、发布 ENGINE_START、返回 total_range。"""
        self._current_mode = "range"
        self._range_start = start
        self._range_end = end
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        total_range = end - start + 1
        self._live_range_count = 0
        self._running = True
        self._last_data_log_time = 0.0

        try:
            self.event_bus.publish(
                EngineStartEvent(
                    mode=self._current_mode,
                    target_count=len(self.targets),
                    batch_size=self._batch_size,
                ),
            )
        except Exception as e:
            logger.warning("发布 ENGINE_START 事件失败（非致命）: %s", e)

        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=start,
                additional_info={"range_start": start, "range_end": end},
            )
            if self._last_data_log_time == 0.0:
                self.data_logger.record_system_data()

        return total_range

    @staticmethod
    def _range_scan_compute_ranges(
        start: int,
        end: int,
        total_range: int,
        num_workers: int,
    ) -> list[tuple[int, int, int]]:
        """计算各 worker 的范围，含边界重叠修正。
        返回 [(worker_id, worker_start, worker_end), ...] 列表。
        """
        chunk_size = total_range // num_workers
        ranges = []
        for i in range(num_workers):
            worker_start = start + i * chunk_size
            worker_end = start + (i + 1) * chunk_size - 1
            if i == num_workers - 1:
                worker_end = end

            if i > 0:
                prev_worker_end = start + i * chunk_size - 1
                if worker_start <= prev_worker_end:
                    logger.warning(
                        f"RangeScan worker {i}: 边界重叠修正 "
                        f"[{worker_start},{worker_end}]->[{prev_worker_end + 1},{worker_end}]",
                    )
                    worker_start = prev_worker_end + 1
                    if worker_start > worker_end:
                        logger.warning("RangeScan worker %s: 范围无效，跳过", i)
                        continue

            logger.debug(
                f"RangeScan worker {i}: 分配范围 [{worker_start}, {worker_end}] "
                f"(共{worker_end - worker_start + 1}个私钥)",
            )
            ranges.append((i, worker_start, worker_end))
        return ranges

    def _range_scan_report_progress(self, total_count: int, total_range: int) -> None:
        """range_scan 进度回调：读取 live 计数、更新统计、记日志。"""
        safe_count = total_count
        with self._state_lock:
            live_count = self._live_range_count
        display_count = max(safe_count, live_count)

        self.stats.update(display_count, total_range=total_range)
        if self.on_progress:
            self.stats._progress_percent = display_count / total_range * 100
            invoke_with_timeout(
                self.on_progress,
                args=(self.stats,),
                timeout=5.0,
                callback_name="on_progress",
            )
        self._save_checkpoint(display_count)

        elapsed = time.time() - self.stats.start_time
        speed = display_count / elapsed if elapsed > 0 else 0
        self._log_data_metrics(display_count, speed)

        try:
            self.event_bus.publish(
                EngineProgressEvent(
                    total_checked=display_count,
                    speed=speed,
                    matches_found=self.stats.matches_found,
                    elapsed_time=elapsed,
                ),
            )
        except Exception as e:
            logger.debug("发布 ENGINE_PROGRESS 事件失败（非致命）: %s", e)

    def _range_scan_finalize(self, total_count: int, total_range: int) -> None:
        """range_scan 结束：合并 live 计数、更新统计、发布 COMPLETE。"""
        with self._state_lock:
            final_count = total_count + self._live_range_count
            self._live_range_count = 0

        self._executor = None
        self._stats_updated.clear()
        self.stats.update(final_count, total_range=total_range)
        self._stats_updated.set()
        self._running = False

        self._publish_engine_complete(final_count)

        if self.data_logging_enabled and self.data_logger:
            try:
                self.data_logger.generate_report("daily")
                logger.info("数据日志报告已生成")
            except (RuntimeError, OSError, ValueError) as e:
                logger.error("生成数据日志报告失败: %s", e)

    def range_scan(self, start: int, end: int) -> None:
        """范围扫描模式 - 使用线程池并行扫描指定私鑰范围"""
        total_range = self._range_scan_setup(start, end)
        total_count = 0

        num_workers = self.max_workers or 4
        chunk_size = total_range // num_workers
        if chunk_size == 0:
            total_count = self._range_scan_worker(start, end, 0)
            # 单worker回退：worker已将计数写入_live_range_count，
            # 需扣除以避免_range_scan_finalize双重计数
            with self._state_lock:
                self._live_range_count = max(0, self._live_range_count - total_count)
            self._range_scan_finalize(total_count, total_range)
            return

        worker_ranges = self._range_scan_compute_ranges(start, end, total_range, num_workers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            self._executor = executor

            futures = {
                executor.submit(self._range_scan_worker, ws, we, wid): wid
                for wid, ws, we in worker_ranges
            }

            pending = set(futures.keys())
            while pending and not self._stop_event.is_set():
                done, pending = concurrent.futures.wait(
                    pending,
                    timeout=self._progress_interval_sec,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )

                for future in done:
                    try:
                        local_count = future.result()
                        with self._state_lock:
                            self._live_range_count = max(0, self._live_range_count - local_count)
                            total_count += local_count
                    except concurrent.futures.CancelledError:
                        logger.debug("工作线程被取消")
                    except KeyboardInterrupt:
                        logger.info("工作线程被用户中断")
                        raise
                    except (RuntimeError, OSError, ValueError) as e:
                        ExceptionHandler.handle_engine_error(
                            "CPU",
                            e,
                            self.stats,
                            "range_scan工作线程执行",
                        )

                self._range_scan_report_progress(total_count, total_range)
                # 测试模式：达到 max_keys 自动停止
                if self._max_keys is not None and total_count >= self._max_keys:
                    logger.info("达到最大处理数 %s，自动停止范围扫描", self._max_keys)
                    self._stop_event.set()

        self._range_scan_finalize(total_count, total_range)

    def _brute_force_worker(
        self,
        worker_id: int,
        batch_size: int = 5000,
        max_keys: int | None = None,
    ) -> int:
        """暴力穷举模式的工作线程函数。"""
        local_count = 0

        while not self._stop_event.is_set():
            if max_keys is not None and local_count >= max_keys:
                logger.info("BruteForce worker %s: 已达到最大扫描数量 %s", worker_id, max_keys)
                break

            with self._state_lock:
                batch_start = self._current_position
                self._current_position += batch_size

            with SecureKeyManager() as key_mgr:
                for k in range(batch_start, batch_start + batch_size):
                    if self._stop_event.is_set():
                        break

                    if k < 1 or k >= Secp256k1.N:
                        continue

                    key_mgr.generate_key(k.to_bytes(32, "big"))
                    private_key = key_mgr.get_key()
                    private_key_bytes = bytes(private_key)

                    result = self._worker_generate_addresses(private_key_bytes, worker_id)
                    if result is None:
                        continue
                    address, compressed_pub, uncompressed_addr, uncompressed_pk = result

                    local_count += 1
                    if local_count % 32 == 0:
                        with self._state_lock:
                            self._live_range_count += 32

                    # Hash160 匹配检查
                    matched_address = None
                    matched_compressed = False
                    matched_hash160: bytes | None = None

                    compressed_hash160 = self.generator.public_key_to_hash160(compressed_pub)
                    if compressed_hash160 in self.target_hash160s:
                        matched_address = address
                        matched_compressed = True
                        matched_hash160 = compressed_hash160
                    elif self.check_uncompressed and uncompressed_pk:
                        uncompressed_hash160 = self.generator.public_key_to_hash160(uncompressed_pk)
                        if uncompressed_hash160 in self.target_hash160s:
                            matched_address = uncompressed_addr
                            matched_compressed = False
                            matched_hash160 = uncompressed_hash160

                    if matched_address:
                        self._worker_check_and_handle_match(
                            private_key,
                            matched_address,
                            matched_compressed,
                            matched_hash160,
                            worker_id,
                        )

        return local_count

    def _brute_force_setup(self, start: int, max_keys: int | None) -> None:
        """brute_force 模式初始化状态、发布 ENGINE_START、记录日志。"""
        self._current_mode = "brute_force"
        self._range_start = start
        self._range_end = None
        self._current_position = start
        self.stats = CollisionStats()
        self.stats.start_time = time.time()
        self._running = True
        self._last_data_log_time = 0.0

        try:
            self.event_bus.publish(
                EngineStartEvent(
                    mode=self._current_mode,
                    target_count=len(self.targets),
                    batch_size=self._batch_size,
                ),
            )
        except Exception as e:
            logger.debug("发布 ENGINE_START 事件失败（非致命）: %s", e)

        if max_keys is None:
            logger.warning("[WARN] brute_force模式未设置max_keys限制，将无限运行直到手动停止或找到匹配")
            logger.warning("建议：使用 max_keys 参数限制扫描数量，例如 max_keys=1_000_000_000")

        if self.data_logging_enabled and self.data_logger:
            self.data_logger.record_engine_data(
                mode=self._current_mode,
                target_count=len(self.targets),
                is_running=True,
                current_position=start,
            )
            if self._last_data_log_time == 0.0:
                self.data_logger.record_system_data()

    def _brute_force_report_progress(self, total_count: int) -> None:
        """进度回调：更新统计、调用 on_progress、保存断点、记录日志。"""
        if total_count % self.progress_interval != 0:
            return
        self.stats.update(total_count)
        if self.on_progress:
            invoke_with_timeout(
                self.on_progress,
                args=(self.stats,),
                timeout=5.0,
                callback_name="on_progress",
            )
        self._save_checkpoint(total_count)

        elapsed = time.time() - self.stats.start_time
        speed = total_count / elapsed if elapsed > 0 else 0
        self._log_data_metrics(total_count, speed)

        try:
            self.event_bus.publish(
                EngineProgressEvent(
                    total_checked=total_count,
                    speed=speed,
                    matches_found=self.stats.matches_found,
                    elapsed_time=elapsed,
                ),
            )
        except Exception as e:
            logger.debug("发布 ENGINE_PROGRESS 事件失败（非致命）: %s", e)

    def _brute_force_finalize(self, total_count: int) -> None:
        """brute_force 结束：更新统计、发布 COMPLETE、记录日志、保存断点。"""
        self._executor = None
        # 合并 _live_range_count 确保计数准确（与 _range_scan_finalize 一致）
        with self._state_lock:
            final_count = total_count + self._live_range_count
            self._live_range_count = 0
        self._stats_updated.clear()
        self.stats.update(final_count)
        self._stats_updated.set()
        self._running = False

        self._publish_engine_complete(final_count)

        if self.data_logging_enabled and self.data_logger:
            try:
                self.data_logger.generate_report("daily")
                logger.info("数据日志报告已生成")
            except (RuntimeError, OSError, ValueError) as e:
                logger.error("生成数据日志报告失败: %s", e)

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
                {
                    "mode": self._current_mode,
                    "targets": list(self.targets),
                    "current_position": self._current_position,
                    "total_checked": self.stats.total_checked,
                    "matches": matches_list,
                    "range_start": self._range_start,
                    "range_end": self._range_end,
                },
            )
        # _publish_engine_complete already invokes on_complete; avoid duplicate call

    def brute_force(self, start: int = 1, max_keys: int | None = None) -> None:
        """暴力穷举模式 - 使用线程池并行从指定起点开始顺序递增"""
        self._brute_force_setup(start, max_keys)
        total_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            self._executor = executor

            futures = []
            num_workers = self.max_workers or 4
            for i in range(num_workers):
                future = executor.submit(self._brute_force_worker, i, max_keys=max_keys)
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                try:
                    local_count = future.result()
                    with self._state_lock:
                        total_count += local_count
                except concurrent.futures.CancelledError:
                    logger.debug("BruteForce 工作线程被取消")
                except KeyboardInterrupt:
                    logger.info("BruteForce 工作线程被用户中断")
                    raise
                except (RuntimeError, OSError, ValueError) as e:
                    ExceptionHandler.handle_engine_error("CPU", e, self.stats, "brute_force工作线程执行")

                self._brute_force_report_progress(total_count)

        self._brute_force_finalize(total_count)

    def resume_from_checkpoint(self) -> dict | None:
        """从断点恢复，返回断点数据（包含mode等信息），无断点返回 None"""
        if not self.checkpoint_mgr or not self.checkpoint_mgr.exists:
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

    def _validate_start_mode(self, mode: str, kwargs: dict) -> None:
        """验证 start() 参数的有效性。"""
        valid_modes = ["random", "range", "brute_force"]
        if mode not in valid_modes:
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

    def _handle_checkpoint_resume(self, mode: str, kwargs: dict) -> str:
        """处理断点恢复逻辑，返回更新后的 mode。

        如果恢复失败，返回原始 mode。
        """
        if not self.checkpoint_mgr:
            return mode

        try:
            checkpoint = self.checkpoint_mgr.load()
            if not checkpoint:
                return mode

            _mode = checkpoint.get("mode")
            _checked = checkpoint.get("total_checked", 0)
            logger.info("从断点恢复: 模式=%s, 已检查=%s", _mode, _checked)

            if checkpoint.get("targets"):
                self.targets = set(checkpoint["targets"])

            checkpoint_mode = checkpoint.get("mode", mode)
            if checkpoint_mode == "range":
                kwargs["start"] = checkpoint.get("current_position", kwargs.get("start", 1))
                kwargs["end"] = checkpoint.get("range_end", kwargs.get("end", 2**32))
                logger.info(f"范围扫描从 {kwargs['start']} 继续到 {kwargs['end']}")
                return "range"
            if checkpoint_mode == "brute_force":
                kwargs["start"] = checkpoint.get("current_position", kwargs.get("start", 1))
                logger.info(f"暴力穷举从 {kwargs['start']} 继续")
                return "brute_force"
            return "random"
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("从断点恢复失败: %s", e)
            self.checkpoint_mgr = None
            return mode

    def _create_and_start_thread(self, mode: str, kwargs: dict) -> None:
        """根据模式创建并启动工作线程。"""
        if mode == "random":
            target_fn = self.random_search
        elif mode == "range":

            def target_fn():
                return self.range_scan(kwargs.get("start", 1), kwargs.get("end", 2**32))

        else:  # brute_force

            def target_fn():
                return self.brute_force(kwargs.get("start", 1), self._max_keys)

        _name = target_fn.__name__ if hasattr(target_fn, "__name__") else "lambda"
        logger.info("启动工作线程: %s", _name)
        self._thread = threading.Thread(target=target_fn, daemon=True)
        self._thread.start()

    def start(  # noqa: E501
        self, mode: str = "random", resume: bool = False, max_keys: int | None = None, **kwargs
    ) -> None:
        """在后台线程启动对撞
        Args:
            mode: "random", "range", "brute_force"
            resume: 是否从断点恢复
            max_keys: 最大处理私钥数量（None=无限），用于测试环境自然终止
            kwargs: range模式需要 start, end; brute_force需要 start

        Raises:
            ValueError: 当参数无效时
            Exception: 当启动失败时
        """
        try:
            if self._running:
                logger.warning("对撞引擎已在运行中，忽略启动请求")
                return

            if self.enhanced_monitoring and not self.enhanced_monitoring.is_running():
                self.enhanced_monitoring.start()
                logger.info("增强监控系统已启动")

            self._validate_start_mode(mode, kwargs)

            if not self.targets:
                logger.warning("目标地址集合为空，对撞将无意义")

            logger.info(
                _t("engine.start", mode=mode, resume=str(resume), target_count=len(self.targets))
            )

            if resume:
                mode = self._handle_checkpoint_resume(mode, kwargs)

            self._stop_event.clear()
            self._engine_stop_reason = "normal"  # L2修复: 重置停止原因，避免重启后语义漂移
            self._running = True
            self._stats_updated.set()
            self._max_keys = max_keys  # 测试模式：限制最大处理数

            self._create_and_start_thread(mode, kwargs)
            logger.info(_t("engine.start_complete"))
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("启动对撞引擎失败: %s", e)
            self._running = False
            self._stop_event.set()
            if hasattr(self, "_executor") and self._executor:
                try:
                    self._executor.shutdown(wait=False)
                except Exception as cleanup_error:
                    logger.debug("清理线程池失败（启动失败时）: %s", cleanup_error)
            raise

    def _stop_send_signals(self) -> None:
        """发送停止信号"""
        self._engine_stop_reason = "user_stopped"
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        if hasattr(self, "_running"):
            self._running = False

    def _stop_join_workers(self, timeout: float | None) -> None:
        """等待工作线程结束"""
        if not (hasattr(self, "_thread") and self._thread):
            return
        if timeout is None and hasattr(self, "targets"):
            timeout = max(10.0, len(self.targets) * 0.001)
        logger.debug(f"等待工作线程结束 (超时{timeout:.1f}秒)...")
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            logger.warning(f"工作线程未在{timeout:.1f}秒内结束，可能存在未提交的匹配数据")
        else:
            logger.debug("工作线程已结束")

    def _stop_save_checkpoint(self) -> None:
        """保存最终断点"""
        if not (hasattr(self, "checkpoint_mgr") and self.checkpoint_mgr and hasattr(self, "stats")):
            return
        logger.info(f"保存最终断点: 已检查={self.stats.total_checked}")
        matches_list: list[dict[str, str]] = []
        if hasattr(self.stats, "matches"):
            matches_list = [
                {"private_key_hash": m["private_key_hash"], "address": m["address"]}
                for m in self.stats.matches
            ]
        try:
            self.checkpoint_mgr.save(
                {
                    "mode": self._current_mode if hasattr(self, "_current_mode") else "",
                    "targets": list(self.targets) if hasattr(self, "targets") else [],
                    "current_position": (
                        self._current_position if hasattr(self, "_current_position") else 0
                    ),
                    "total_checked": self.stats.total_checked,
                    "matches": matches_list,
                    "range_start": self._range_start if hasattr(self, "_range_start") else None,
                    "range_end": self._range_end if hasattr(self, "_range_end") else None,
                },
            )
            logger.info("断点保存成功")
        except (RuntimeError, OSError, ValueError) as e:
            logger.error("断点保存失败: %s", e)

    def _stop_cleanup_resources(self) -> None:
        """清理增强监控、去重过滤器、线程池"""
        if (
            hasattr(self, "enhanced_monitoring")
            and self.enhanced_monitoring
            and self.enhanced_monitoring.is_running()
        ):
            logger.info("正在停止增强监控系统...")
            self.enhanced_monitoring.stop()
            if hasattr(self, "data_logger") and self.data_logger:
                try:
                    self.data_logger.save_current_data()
                    self.data_logger.save_history_data()
                    logger.info("最终数据已保存")
                except (RuntimeError, OSError, ValueError) as e:
                    logger.error("保存最终数据失败: %s", e)

        if hasattr(self, "dedup_filter") and self.dedup_filter and self.dedup_filter.enabled:
            stats = self.dedup_filter.get_stats()
            logger.info(
                f"清理去重过滤器: 检查={stats['checks_total']}, 重复={stats['duplicates_found']}, "
                f"唯一={stats['unique_keys']}",
            )
            self.dedup_filter.reset()
            logger.info("去重过滤器已清理")

        if hasattr(self, "_executor") and self._executor:
            logger.info("关闭线程池...")
            self._executor.shutdown(wait=False)
            self._executor = None

    def _stop_reset_and_publish(self) -> None:
        """重置引擎状态并发布 ENGINE_STOP 事件"""
        self._engine_stop_reason = "user_stopped"
        if hasattr(self, "_stop_event"):
            self._stop_event.clear()
        if hasattr(self, "_running"):
            self._running = False
        if hasattr(self, "_thread"):
            self._thread = None

        # 不再检查 was_thread_alive，统一发布 ENGINE_STOP
        try:
            if hasattr(self, "stats") and hasattr(self, "event_bus"):
                snap = self.stats.snapshot()
                self.event_bus.publish(
                    EngineStopEvent(
                        reason="user_stopped",
                        total_checked=snap.total_checked,
                    ),
                )
        except (RuntimeError, OSError, ValueError) as e:
            logger.debug("发布 ENGINE_STOP 事件失败（非致命）: %s", e)

    def stop(self, timeout: float | None = None) -> None:
        """停止对撞

        Args:
            timeout: 等待工作线程结束的超时时间（秒）
                    None时使用默认值（根据目标数动态计算，最少10秒）
        """
        logger.info(_t("engine.stop"))

        # C2修复: 在信号设置前捕获运行状态，避免竞态遗漏 EngineStopEvent
        was_running = self._running

        self._stop_send_signals()
        self._stop_join_workers(timeout)

        # 保存最终断点
        self._stop_save_checkpoint()

        # 清理资源（监控、去重、线程池）
        self._stop_cleanup_resources()

        # 发布 ENGINE_STOP 事件
        if was_running:
            try:
                snap = self.stats.snapshot() if hasattr(self, "stats") else None
                if snap and hasattr(self, "event_bus"):
                    self.event_bus.publish(
                        EngineStopEvent(
                            reason="user_stopped",
                            total_checked=snap.total_checked,
                        ),
                    )
            except Exception as e:
                logger.debug("发布 ENGINE_STOP 事件失败（非致命）: %s", e)

        logger.info(_t("engine.stopped"))

    def is_running(self) -> bool:
        """检查碰撞引擎是否正在运行

        Returns:
            True 表示引擎正在运行（已启动且工作线程存活），
            False 表示引擎已停止或未启动
        """
        return cast(
            "bool",
            hasattr(self, "_running")
            and self._running
            and hasattr(self, "_thread")
            and self._thread
            and self._thread.is_alive(),
        )

    def __enter__(self) -> "KeyCollisionEngine":
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any | None) -> None:
        self.stop()

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
        #
        # 风险评估（低风险，暂不修改）：
        # - self.stop() 内部可能获取锁，在解释器关闭时存在潜在死锁风险
        # - 但已有 try/except 包裹，异常被 logger.debug 记录后静默处理
        # - 守护线程在进程退出时会自动清理，不依赖 __del__ 的完整执行
        try:
            if hasattr(self, "_running") and self._running and hasattr(self, "stop"):
                self.stop()
        except Exception as e:
            logger.debug("析构 KeyCollisionEngine 时发生异常: %s", e)

    def get_stats(self) -> CollisionStats:
        """获取当前碰撞统计信息

        Returns:
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
                # 有实时计数：合并到 stats
                self.stats.update(max(live_count, self.stats.total_checked))
            else:
                # 始终调用 update() 刷新 elapsed/speed，确保轮询循环能正常工作
                self.stats.update(self.stats.total_checked)

        return self.stats


# 注意: GPU加速功能已迁移到 gpu_collision_engine.py
# 使用方式:
# from src.collision import create_collision_engine
# engine = create_collision_engine(targets, mode='gpu') # 强制GPU
# engine = create_collision_engine(targets, mode='auto') # 自动选择
# 或直接导入:
# from src.collision.gpu_collision_engine import GPUCollisionEngine
