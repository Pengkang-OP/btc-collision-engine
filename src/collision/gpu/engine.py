"""GPU碰撞引擎 - 协调器实现

组合 Phase 1-5 建立的独立组件，作为统一的引擎协调器。

职责:
- 组件协调与依赖注入
- 引擎生命周期管理 (start/stop)
- 对外 API 统一接口
- 搜索模式执行桥接

组件:
- GPUEngineFacade (Phase 2): GPU设备/上下文/内核/异步管道
- PerformanceMonitoringPipeline (Phase 3): 性能监控/异常检测
- CollisionCore (Phase 4): 统计/断点/去重/搜索协调
- VendorOptimizationFactory (Phase 5): NVIDIA/AMD/Intel 策略

版本: v6.0.0 (Phase 6)
创建日期: 2026-04-30
"""

import os
import time
import signal
import threading
import logging
from typing import Set, Optional, Tuple, List, Dict, Any, Callable, cast

# Phase 1-5 组件
from .monitoring import PerformanceMonitoringPipeline
from .core import CollisionCore
from .vendor_strategy import VendorOptimizationFactory  # noqa: F401  # 保留供测试 patch 目标

# 回调类型
from ..types import ProgressCallback, MatchCallback, CompleteCallback

# GPU 常量
UINT32_MAX = 0xFFFFFFFF
GPU_MAX_BATCH_SIZE = UINT32_MAX
INITIAL_BATCH_SIZE = 1_000_000
ASYNC_KEY_GEN_TIMEOUT = 30.0
BATCH_LOG_FREQUENCY = 100
INITIAL_BATCHES_LOG = 3
THREAD_JOIN_TIMEOUT = 5.0
MONITOR_THREAD_JOIN_TIMEOUT = 1.0
EXCEPTION_RECOVERY_DELAY = 0.1
ASYNC_KEY_GEN_BASE_TIMEOUT = 5.0
ASYNC_KEY_GEN_PER_KEY_TIME = 0.00001
ASYNC_KEY_GEN_SAFETY_FACTOR = 2.0

# pyopencl 检测
try:
    import pyopencl as cl  # noqa: F401
    import numpy as np

    PYOPENCL_AVAILABLE = True
except ImportError:
    PYOPENCL_AVAILABLE = False

# 异步日志支持
try:
    pass

    ASYNC_LOG_AVAILABLE = True
except ImportError:
    ASYNC_LOG_AVAILABLE = False

# GPU 配置管理器 (已弃用: _merge_gpu_configs 已移除, 常量仅保留供外部导入兼容)
GPU_CONFIG_MANAGER_AVAILABLE = False  # 保留供外部导入兼容

# 基础依赖
from ...gpu.device import GPUDeviceDetector  # noqa: E402
from ...gpu.engine_monitor import GPUEngineMonitor  # noqa: E402
from ...gpu.search_mode_coordinator import SearchModeCoordinator  # noqa: E402
from ...gpu.device_manager import GPUDeviceManager  # noqa: E402
from ...gpu.memory_calculator import GPUMemoryCalculator  # noqa: E402

# 碰撞基础
from ..collision_stats import CollisionStats  # noqa: E402
from ..base_engine import BaseCollisionEngine  # noqa: E402

# 加密
from ...core.base58 import Base58  # noqa: E402
from ...core.wif import WIF  # noqa: E402

# 监控
from ...monitoring.data_logger import DataLogger  # noqa: E402
from ...monitoring.enhanced_monitoring import EnhancedMonitoringSystem  # noqa: E402
from ...monitoring.gpu_performance_monitor import (  # noqa: E402
    GPUPerformanceMonitor,
    get_gpu_performance_monitor,
)  # noqa: E402

# v3.2.0: 事件系统支持
from ..event_bus import EventBus  # noqa: E402
from ..events import (  # noqa: E402
    EngineStartEvent,
    EngineProgressEvent,
    EngineMatchEvent,
    # EngineErrorEvent,  # 暂未使用
    EngineCompleteEvent,
    EngineStopEvent,
    EventType,
)
from ...monitoring.event_adapters import (  # noqa: E402
    DataLoggerAdapter,
    EnhancedMonitoringAdapter,
)

# v3.2.1: 增强私钥生成器
from .key_generator import (  # noqa: E402
    KeyGenerator,
    KeyGenerationStrategy,
)

logger = logging.getLogger(__name__)

# 预导入 GPU 监控器
_gpu_performance_monitor = None


def _get_gpu_monitor() -> "GPUPerformanceMonitor":
    """获取 GPU 性能监控器(懒加载)"""
    global _gpu_performance_monitor
    if _gpu_performance_monitor is None:
        _gpu_performance_monitor = get_gpu_performance_monitor()
    return _gpu_performance_monitor


def _seed_bytes_to_u32_be_array(seed: bytes) -> "np.ndarray":
    """把 32 字节 seed 按 big-endian 拆成 8*uint32, 再转成本机端序。"""
    if len(seed) != 32:
        raise ValueError(f"seed must be 32 bytes, got {len(seed)}")
    be_u32 = np.frombuffer(seed, dtype=">u4")
    return be_u32.astype(np.uint32)


class GPUCollisionEngine(BaseCollisionEngine):
    """GPU 加速的比特币私钥对撞引擎 - Phase 6 重构版

    组合 GPUEngineFacade (Phase 2) + PerformanceMonitoringPipeline (Phase 3)
    + CollisionCore (Phase 4) + VendorOptimizationFactory (Phase 5),
    实现统一的引擎协调器。

    继承 BaseCollisionEngine，保持完整向后兼容。
    """

    MONITOR_INTERVAL = 100

    def __init__(
        self,
        targets: Set[str],
        device_index: int = 1,
        batch_size: Optional[int] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_match: Optional[MatchCallback] = None,
        on_complete: Optional[CompleteCallback] = None,
        checkpoint_enabled: bool = False,
        dedup_enabled: bool = False,
        dedup_max_size: int = 1_000_000,
        checkpoint_interval: int = 30,
        event_bus: Optional[EventBus] = None,  # v3.2.0: 事件总线支持
        data_logging_enabled: bool = True,
        data_logging_interval: int = 5,
        use_enhanced_monitoring: bool = True,
        use_gpu_memory_pool: bool = True,
        gpu_pool_max_buffers: int = 100,
        gpu_pool_max_memory_mb: int = 512,
        use_async_logging: bool = False,
        async_log_file: str = "logs/gpu_async.log",
        async_log_max_bytes: int = 10 * 1024 * 1024,
        async_log_backup_count: int = 5,
        check_uncompressed: Optional[bool] = None,
        key_generation_strategy: KeyGenerationStrategy = KeyGenerationStrategy.PRNG_SEED,  # v3.2.1: 私钥生成策略
    ) -> None:
        """初始化 GPU 碰撞引擎 (Phase 6 重构版)

        保持全部 17 个参数与原始 GPUCollisionEngine 完全兼容。
        """
        if not PYOPENCL_AVAILABLE:
            # L2修复: 提供详细诊断信息
            diagnostic_msg = (
                "PyOpenCL 不可用，无法使用 GPU 加速。\n"
                "诊断步骤:\n"
                "  1. 安装 OpenCL 运行时:\n"
                "     - NVIDIA: conda install pyopencl nccl-cu* (或 pip install pyopencl)\n"
                "     - Intel: 下载 Intel OpenCL Runtime\n"
                "     - AMD: 安装 AMD APP SDK\n"
                "  2. 验证 GPU 驱动已正确安装\n"
                "  3. 设置 PYOPENCL_DEBUG=1 查看详细错误\n"
                "  4. 使用 CPU 模式作为替代:\n"
                "     python key_collision_cli.py -t <地址> -m random\n"
            )
            raise RuntimeError(diagnostic_msg)

        # v3.2.1: 初始化私钥生成器
        self._key_generator = KeyGenerator(strategy=key_generation_strategy)
        logger.info(f"GPU引擎：使用私钥生成策略: {key_generation_strategy.value}")

        # v3.2.0: 事件总线初始化
        self.event_bus = event_bus or EventBus()

        # === 基本属性 ===
        self.targets = targets
        self.device_index = device_index
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete

        # v3.2.0: 向后兼容 - 回调包装器
        self._data_logger_adapter = None
        self._enhanced_monitoring_adapter = None
        if on_progress:
            self.event_bus.subscribe(EventType.ENGINE_PROGRESS, self._on_progress_callback)
        if on_match:
            self.event_bus.subscribe(EventType.ENGINE_MATCH, self._on_match_callback)
        if on_complete:
            self.event_bus.subscribe(EventType.ENGINE_COMPLETE, self._on_complete_callback)
        self._match_callback_timeout = 5.0
        self._stop_event = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._dynamic_speed_benchmark: float = 500000.0
        self._last_memory_check_time = time.time()
        self._memory_check_interval = 60

        # === 地址格式检测 ===
        if check_uncompressed is None:
            self._check_uncompressed = self._auto_detect_compression_needed_gpu()
        else:
            self._check_uncompressed = 1 if check_uncompressed else 0

        # === 控制参数 ===
        self._batch_size = batch_size if batch_size is not None else INITIAL_BATCH_SIZE
        self._batch_size_lock = threading.Lock()
        self._max_gpu_error_retries = 100
        self._consecutive_gpu_errors = 0

        # === Phase 4: CollisionCore (stats/checkpoint/dedup) ===
        self._core = CollisionCore(
            targets=targets,
            config={
                "checkpoint_enabled": checkpoint_enabled,
                "dedup_enabled": dedup_enabled,
                "dedup_max_size": dedup_max_size,
                "checkpoint_interval": checkpoint_interval,
            },
            on_progress=on_progress,
            on_match=on_match,
            engine=self,
        )

        # 直接暴露 Core 属性（向后兼容）
        self.stats = self._core.stats
        self.checkpoint_mgr = self._core.checkpoint
        self.dedup_filter = self._core.dedup_filter

        # === 监控系统 ===
        self.data_logging_enabled = data_logging_enabled
        self.data_logging_interval = data_logging_interval
        self.data_logger = None
        self.enhanced_monitoring = None
        self._engine_monitor = GPUEngineMonitor(engine=self)

        # 异步日志
        self._async_log_handler: Optional[Any] = None
        if use_async_logging and ASYNC_LOG_AVAILABLE:
            self._setup_async_logging(async_log_file, async_log_max_bytes, async_log_backup_count)
        elif use_async_logging and not ASYNC_LOG_AVAILABLE:
            logger.warning("异步日志不可用（AsyncFileHandler导入失败），使用同步日志")

        # === Phase 2: GPUEngineFacade ===
        config = {
            "gpu": {
                "use_memory_pool": use_gpu_memory_pool,
                "pool_max_buffers": gpu_pool_max_buffers,
                "pool_max_memory_mb": gpu_pool_max_memory_mb,
            },
            "batch_size": batch_size,
        }
        self._device_manager = GPUDeviceManager(
            device_index=device_index, config=config, logger=logger
        )
        self._device_manager.initialize(
            targets,
            batch_size,
            check_uncompressed=self._check_uncompressed,
        )

        # 暴露 GPU 对象（向后兼容）
        self._gpu_device = self._device_manager.device
        self._gpu_context = self._device_manager.context
        self._gpu_kernel = self._device_manager.kernel
        self._async_executor: Optional[Any] = self._device_manager.async_executor
        self._gpu_memory_pool = self._device_manager.memory_pool

        # Phase 5: VendorOptimizationFactory 策略创建保留供外部测试使用
        # 引擎内部不再持有 _vendor_strategy 引用 (scheduled removal)

        # === 搜索模式协调器 ===
        self._search_coordinator = SearchModeCoordinator(self, logger)

        # 将协调器内部模式同步到 engine 属性（向后兼容搜索模式委托方法）
        self._random_search_mode = self._search_coordinator.get_mode_instance("random")
        self._range_scan_mode = self._search_coordinator.get_mode_instance("range_scan")
        self._brute_force_mode = self._search_coordinator.get_mode_instance("brute_force")

        # === Phase 3: PerformanceMonitoringPipeline (懒加载) ===
        self._perf_pipeline: Optional[PerformanceMonitoringPipeline] = None
        self._perf_pipeline_config = {
            "batch_size": batch_size,
            "device_index": device_index,
        }
        if data_logging_enabled:
            try:
                if use_enhanced_monitoring:
                    # v3.2.0: 使用事件适配器模式
                    self.enhanced_monitoring = EnhancedMonitoringSystem(
                        collection_interval=data_logging_interval,
                        enable_monitoring_data=False,
                    )
                    self.data_logger = self.enhanced_monitoring.data_logger
                    self._enhanced_monitoring_adapter = EnhancedMonitoringAdapter(self.enhanced_monitoring)
                    self._enhanced_monitoring_adapter.subscribe_to(self.event_bus)
                    logger.info("GPU引擎：增强监控系统已启用（事件适配器模式）")
                else:
                    # v3.2.0: 使用数据日志事件适配器
                    self.data_logger = DataLogger()
                    self._data_logger_adapter = DataLoggerAdapter(self.data_logger)
                    self._data_logger_adapter.subscribe_to(self.event_bus)
                    logger.info("GPU引擎：数据日志系统已启用（事件适配器模式）")
            except Exception as e:
                logger.warning(f"GPU引擎：监控系统初始化失败: {e}")
                self.data_logging_enabled = False

        # === 位置跟踪 ===
        self._current_position = 0
        self._current_mode = ""
        self._range_start = None
        self._range_end = None
        self._last_progress_time = 0.0
        self._progress_interval_sec = 0.5

        # GPU 性能监控器
        self.gpu_performance_monitor = None

        # 自适应批处理
        self._adaptive_batch_enabled = True
        self._adaptive_error_count = 0
        self._adaptive_batch_size = self._batch_size
        self._max_batch_size = (
            min(self._batch_size * 2, GPU_MAX_BATCH_SIZE - 1) if self._batch_size else 2097152
        )
        self._min_batch_size = self._batch_size // 4 if self._batch_size else 262144
        self._last_batch_adjust_time = time.time()
        self._batch_adjust_interval = 10.0
        self._error_rate_threshold = 0.05

        # 性能基准
        self._calculate_dynamic_benchmark()

    # ========== 属性 ==========

    @property
    def batch_size(self) -> int:
        """线程安全的 batch_size 读取"""
        with self._batch_size_lock:
            return cast(int, self._batch_size)

    @batch_size.setter
    def batch_size(self, value: int) -> None:
        """线程安全的 batch_size 写入 (P1-2: UINT32_MAX 检查)"""
        if value >= GPU_MAX_BATCH_SIZE:
            raise ValueError(
                f"P1-2: batch_size ({value:,}) >= UINT32_MAX ({GPU_MAX_BATCH_SIZE:,}) "
                "会导致 GPU 内核 gid 溢出"
            )
        with self._batch_size_lock:
            self._batch_size = value

    # ========== 公共 API ==========

    @staticmethod
    def is_gpu_available() -> bool:
        """检查 GPU 是否可用"""
        return GPUDeviceDetector.is_gpu_available()

    def start(self, mode: str = "random", resume: bool = False, **kwargs) -> None:
        """启动对撞"""
        if self._running:
            return
        with self._batch_size_lock:
            self._consecutive_gpu_errors = 0
        self._stop_event.clear()
        self._running = True

        # 每次 start 重新初始化 Core 组件（stats/checkpoint/dedup）
        self._core._init_stats()
        self.stats = self._core.stats
        if self.checkpoint_mgr is None and self._core.config.get("checkpoint_enabled", False):
            self._core._init_checkpoint()
            self.checkpoint_mgr = self._core.checkpoint
        if self.dedup_filter is None and self._core.config.get("dedup_enabled", False):
            self._core._init_dedup_filter()
            self.dedup_filter = self._core.dedup_filter

        assert self.stats is not None
        self.stats.start_time = time.time()

        # v3.2.0: 发布引擎启动事件
        start_event = EngineStartEvent(
            mode=mode,
            target_count=len(self.targets),
            batch_size=self.batch_size,
        )
        start_event.source = "gpu_collision_engine"
        self.event_bus.publish(start_event)

        # 在后台线程中启动搜索（start() 非阻塞，stop() 负责终止）
        self._thread = threading.Thread(
            target=self._search_coordinator.start,
            args=(mode,),
            kwargs={"resume": resume, **kwargs},
            daemon=True,
            name="GPUCollisionEngine-search",
        )
        self._thread.start()

    def stop(self, timeout: Optional[float] = None) -> None:
        """停止对撞（幂等，重复调用安全）

        GPU-1修复: 使用 _stop_event 防止重复调用导致异常。
        当 _stop_event 已被设置时，说明 stop() 已执行过，直接返回。
        """
        # GPU-1: 防止重复调用 stop()
        if self._stop_event.is_set():
            logger.debug("stop() 已执行过，跳过重复调用")
            return

        self._search_coordinator.stop()
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout or 5)

        # 保存最终断点
        if self.checkpoint_mgr:
            try:
                # MEDIUM-3修复: 添加类型检查确保 matches 数据格式正确
                matches_list = []
                for m in self.stats.matches:
                    if isinstance(m, dict) and "private_key_hash" in m and "address" in m:
                        matches_list.append({
                            "private_key_hash": m["private_key_hash"],
                            "address": m["address"]
                        })
                self.checkpoint_mgr.save(
                    mode=self._current_mode,
                    targets=self.targets,
                    current_position=self._current_position,
                    total_checked=self.stats.total_checked,
                    matches=matches_list,
                    range_start=self._range_start,
                    range_end=self._range_end,
                )
            except Exception as e:
                logger.error(f"保存最终断点失败: {e}", exc_info=True)

        # v3.2.0: 发布引擎停止事件
        stop_event = EngineStopEvent(
            reason="user_request",
            total_checked=self.stats.total_checked,
        )
        stop_event.source = "gpu_collision_engine"
        self.event_bus.publish(stop_event)

        # v3.2.0: 发布引擎完成事件
        assert self.stats is not None
        complete_event = EngineCompleteEvent(
            total_checked=self.stats.total_checked,
            matches_found=self.stats.matches_found,
            elapsed_time=time.time() - self.stats.start_time,
            avg_speed=self.stats.avg_speed,
            stop_reason="user_request",
        )
        complete_event.source = "gpu_collision_engine"
        self.event_bus.publish(complete_event)

        # 停止监控
        if self.enhanced_monitoring:
            try:
                self.enhanced_monitoring.stop()
            except Exception as e:
                logger.error(f"停止监控系统失败: {e}", exc_info=True)

        if self.gpu_performance_monitor:
            try:
                self.gpu_performance_monitor.stop()
            except Exception as e:
                logger.error(f"停止GPU性能监控器失败: {e}", exc_info=True)

        # 清理去重过滤器
        if self.dedup_filter and self.dedup_filter.enabled:
            self.dedup_filter.reset()

        # 刷写日志
        if self.data_logger:
            try:
                self.data_logger.flush()
            except Exception as e:
                logger.error(f"刷写数据日志失败: {e}", exc_info=True)

        # 停止种子预生成
        if hasattr(self, "_random_search_mode") and self._random_search_mode:
            try:
                self._random_search_mode.stop()
            except Exception as e:
                logger.warning(f"停止种子预生成线程失败: {e}")

        # 清理异步执行器
        if self._async_executor:
            try:
                self._async_executor.cleanup()
            except Exception as e:
                logger.error(f"清理异步执行器失败: {e}", exc_info=True)
            self._async_executor = None  # cleanup重置

        # 清理设备管理器
        if self._device_manager:
            try:
                self._device_manager.cleanup()
            except Exception as e:
                logger.error(f"清理设备管理器失败: {e}", exc_info=True)

        self._thread = None
        logger.info("GPU引擎：资源清理完成")

    def is_running(self) -> bool:
        """是否正在运行"""
        return cast(bool, self._running and self._thread and self._thread.is_alive())

    def get_device_info(self) -> Dict[str, Any]:
        """获取 GPU 设备信息"""
        if self._gpu_device:
            return {
                "type": "GPU",
                "name": getattr(self._gpu_device, "name", "Unknown"),
                "vendor": getattr(self._gpu_device, "vendor", "Unknown"),
                "device_index": self.device_index,
                "batch_size": self.batch_size,
            }
        return {"type": "GPU", "status": "not_initialized"}

    def get_stats(self) -> CollisionStats:
        """获取统计信息"""
        assert self.stats is not None
        return self.stats

    def get_adjustment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取调整历史"""
        return self._engine_monitor.get_adjustment_history(limit=limit)

    # ========== 上下文管理器 ==========

    def __enter__(self) -> "GPUCollisionEngine":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def __del__(self) -> None:
        """Q5修复: 析构函数只做最小化清理，避免死锁和竞态条件

        不调用完整的 stop() 方法，因为：
        1. stop() 会尝试获取锁，在多线程环境中可能导致死锁
        2. 析构期间可能存在部分初始化的对象
        3. 守护线程会在进程退出时自动清理资源
        """
        try:
            # 检查对象是否已完全初始化
            if not hasattr(self, "_stop_event"):
                return

            # 只设置停止事件，不调用完整的 stop() 方法
            if not self._stop_event.is_set():
                self._stop_event.set()

            # 清理异步执行器（如果存在且已初始化）
            if hasattr(self, "_async_executor") and self._async_executor is not None:
                try:
                    self._async_executor.cleanup()
                except Exception:
                    pass
                self._async_executor = None

            # 清理设备管理器
            if hasattr(self, "_device_manager") and self._device_manager is not None:
                try:
                    self._device_manager.cleanup()
                except Exception:
                    pass
                self._device_manager = None
        except Exception:
            pass  # 析构函数中资源清理失败静默处理

    # ========== 厂商检测 ==========

    def _detect_vendor_from_device(self) -> str:
        """从 GPU 设备检测厂商"""
        if self._gpu_device:
            vendor = getattr(self._gpu_device, "vendor", "")
            if vendor:
                v_lower = str(vendor).lower()
                if "intel" in v_lower:
                    return "intel"
                if "nvidia" in v_lower:
                    return "nvidia"
                if "amd" in v_lower or "advanced" in v_lower:
                    return "amd"
        return "unknown"

    def _auto_detect_compression_needed_gpu(self) -> int:
        """GPU 路径智能检测是否需要双格式检查"""
        target_count = len(self.targets)
        if target_count < 1000:
            return 1
        return 0

    # ========== 目标地址处理 ==========

    def _prepare_targets(self) -> None:
        """将目标地址转换为 Hash160"""
        self._target_list = []
        hash160_list = []
        for address in sorted(self.targets):
            try:
                version, payload = Base58.check_decode(address)
                if version == 0x00 and len(payload) == 20:
                    self._target_list.append(address)
                    hash160_list.append(payload)
            except (ValueError, TypeError):
                continue
        if not hash160_list:
            raise ValueError("没有有效的目标地址")
        self._target_hash160s = b"".join(hash160_list)

    def _calculate_gpu_memory_usage(self, num_keys: int) -> float:
        """计算 GPU 显存使用(MB)"""
        return GPUMemoryCalculator.calculate_from_hash160_bytes(
            num_keys=num_keys,
            hash160_bytes=self._target_hash160s,
        )

    # ========== 性能基准 ==========

    def _calculate_dynamic_benchmark(self) -> None:
        """计算动态性能基准值"""
        try:
            test_batch_size = 100000
            seed = os.urandom(32)
            start_time = time.time()
            self._gpu_kernel.run_batch(seed, test_batch_size)
            execution_time = time.time() - start_time
            actual_speed = test_batch_size / execution_time
            self._dynamic_speed_benchmark = actual_speed * 0.8
            logger.info(f"动态性能基准计算完成: {self._dynamic_speed_benchmark:.0f} keys/s")
        except Exception as e:
            logger.warning(f"动态性能基准计算失败，使用默认值: {e}")

    def _check_memory_leaks(self) -> None:
        """定期检查内存泄漏"""
        current_time = time.time()
        if current_time - self._last_memory_check_time >= self._memory_check_interval:
            self._last_memory_check_time = current_time
            if hasattr(self._gpu_kernel, "_buffer_tracker") and self._gpu_kernel._buffer_tracker:
                try:
                    stats = self._gpu_kernel._buffer_tracker.get_stats()
                    logger.debug(
                        f"内存检查: {stats['count']}个缓冲区, {stats['total_size_mb']:.2f} MB"
                    )
                except Exception as e:
                    logger.error(f"内存泄漏检查失败: {e}", exc_info=True)

    # ========== GPU 批次执行 ==========

    def _execute_gpu_batch(
        self, seed: bytes, batch_size: int, batch_num: int
    ) -> Tuple[List[Dict[str, int]], float]:
        """执行 GPU batch 计算"""
        if batch_num <= INITIAL_BATCHES_LOG or batch_num % BATCH_LOG_FREQUENCY == 0:
            logger.debug(f"GPU batch {batch_num}: 运行 run_batch (size={batch_size})...")

        batch_start_time = time.time()

        if self._async_executor is not None:
            matches: List[Dict[str, int]] = []
            if self._gpu_kernel is not None:
                if hasattr(self._gpu_kernel, "program") and hasattr(
                    self._gpu_kernel, "_targets_buf"
                ):
                    try:
                        matches, execution_time_ms = self._async_executor.run_batch_async(
                            seed,
                            batch_size,
                            self._gpu_kernel.program,
                            self._gpu_kernel._targets_buf,
                            len(self.targets),
                        )
                    except Exception as e:
                        logger.warning(f"异步执行失败，回退到同步模式: {e}")
                        matches = self._gpu_kernel.run_batch(
                            seed, batch_size, stop_event=self._stop_event
                        )
                        execution_time_ms = (time.time() - batch_start_time) * 1000
                else:
                    matches = self._gpu_kernel.run_batch(
                        seed, batch_size, stop_event=self._stop_event
                    )
                    execution_time_ms = (time.time() - batch_start_time) * 1000
            else:
                raise RuntimeError("GPU内核不可用，无法执行批次")
        elif self._gpu_kernel is not None:
            matches = self._gpu_kernel.run_batch(seed, batch_size, stop_event=self._stop_event)
            execution_time_ms = (time.time() - batch_start_time) * 1000
        else:
            raise RuntimeError("GPU内核不可用，无法执行批次")

        # PERF-1: 检测 CPU-GPU 同步瓶颈
        expected_speed = getattr(self, "_dynamic_speed_benchmark", 500000)
        expected_time_ms = (batch_size / expected_speed) * 1000
        threshold_ms = expected_time_ms * 1.5
        if execution_time_ms > threshold_ms:
            logger.warning(
                f"PERF-1警告: GPU batch {batch_num} 执行时间过长 "
                f"({execution_time_ms:.0f}ms > {threshold_ms:.0f}ms)"
            )

        self._check_memory_leaks()

        if batch_num <= INITIAL_BATCHES_LOG or batch_num % BATCH_LOG_FREQUENCY == 0:
            logger.debug(f"GPU batch {batch_num}: 发现 {len(matches)} 个匹配")

        return matches, execution_time_ms

    # ========== 匹配回调 ==========

    def _safe_invoke_match_callback(self, private_key: bytes, address: str, wif: str) -> bool:
        """安全调用匹配回调函数，提供超时控制与异常隔离"""
        on_match = self.on_match
        if not on_match:
            return True
        try:
            if os.name == "nt":
                result: list[Optional[Any]] = [None]
                exception: list[Optional[BaseException]] = [None]

                def target() -> None:
                    try:
                        result[0] = on_match(private_key, address, wif)
                    except Exception as e:
                        exception[0] = e

                callback_thread = threading.Thread(target=target, daemon=True)
                callback_thread.start()
                callback_thread.join(timeout=self._match_callback_timeout)
                if callback_thread.is_alive():
                    logger.critical(f"匹配回调执行超时 ({self._match_callback_timeout}秒)")
                    return False
                if exception[0]:
                    logger.error(f"匹配回调异常: {exception[0]}")
                    return False
            else:
                # Q7修复: 添加信号 API 可用性检查，兼容 WSL 和其他 Unix-like 环境
                try:
                    _sigalrm = signal.SIGALRM  # Unix-only API
                except AttributeError:
                    # 信号 API 不可用，回退到无超时模式
                    logger.warning("SIGALRM 不可用，匹配回调将无超时保护")
                    try:
                        on_match(private_key, address, wif)
                    except Exception as e:
                        logger.error(f"匹配回调异常: {e}", exc_info=True)
                        return False
                    return True

                def timeout_handler(signum: int, frame: Any) -> None:
                    raise TimeoutError(f"匹配回调执行超时 ({self._match_callback_timeout}秒)")

                old_handler = signal.signal(_sigalrm, timeout_handler)  # noqa: E501
                _alarm = signal.alarm  # type: ignore[attr-defined]  # Unix-only API
                _alarm(int(self._match_callback_timeout))
                try:
                    on_match(private_key, address, wif)
                except TimeoutError as e:
                    logger.critical(str(e))
                    return False
                except Exception as e:
                    logger.error(f"匹配回调异常: {e}", exc_info=True)
                    return False
                finally:
                    _alarm(0)
                    signal.signal(_sigalrm, old_handler)
            return True
        except Exception as e:
            logger.error(f"匹配回调调用失败: {e}", exc_info=True)
            return False

    # ========== 匹配处理 ==========

    def _process_gpu_matches(self, private_keys: bytes, matches: List[Dict[str, int]]) -> None:
        """处理 GPU 匹配结果"""
        for match in matches:
            key_idx = match["key_index"]
            # S-2修复: 添加边界检查，防止越界访问
            if key_idx * 32 + 32 > len(private_keys):
                logger.warning(f"私钥索引越界: key_idx={key_idx}, private_keys长度={len(private_keys)}")
                continue
            private_key = private_keys[key_idx * 32 : (key_idx + 1) * 32]
            if self.dedup_filter is not None and not self.dedup_filter.check_and_add(private_key):
                continue
            target_idx = match["target_index"]
            address = self._target_list[target_idx]
            wif = WIF.encode(private_key, compressed=True)
            if self.stats is not None:
                self.stats.add_match(private_key, address)
            
            # v3.2.0: 发布匹配事件
            match_event = EngineMatchEvent(
                private_key=private_key,
                address=address,
                wif=wif,
                target_address=address,
            )
            match_event.source = "gpu_collision_engine"
            self.event_bus.publish(match_event)
            
            # 向后兼容: 调用传统回调
            if not self._safe_invoke_match_callback(private_key, address, wif):
                logger.warning(f"GPU匹配回调处理失败，跳过地址: {address[:6]}...{address[-4:]}")

    def _process_gpu_matches_prng(self, seed: bytes, matches: List[Dict[str, int]]) -> None:
        """处理 GPU 匹配结果 (PRNG 模式)
        
        G1修复: 添加索引越界检查，防止IndexError崩溃
        """
        seed_int = int.from_bytes(seed, "big")
        for match in matches:
            key_idx = match["key_index"]
            key_int = (seed_int + key_idx) % (2**256)
            private_key = key_int.to_bytes(32, "big")
            if self.dedup_filter is not None and not self.dedup_filter.check_and_add(private_key):
                continue
            target_idx = match["target_index"]
            # G1修复: 检查目标索引是否越界
            if target_idx >= len(self._target_list):
                logger.warning(f"目标索引越界: {target_idx} >= {len(self._target_list)}，跳过匹配")
                continue
            address = self._target_list[target_idx]
            wif = WIF.encode(private_key, compressed=True)
            if self.stats is not None:
                self.stats.add_match(private_key, address)
            
            # v3.2.0: 发布匹配事件
            match_event = EngineMatchEvent(
                private_key=private_key,
                address=address,
                wif=wif,
                target_address=address,
            )
            match_event.source = "gpu_collision_engine"
            self.event_bus.publish(match_event)
            
            # 向后兼容: 调用传统回调
            if not self._safe_invoke_match_callback(private_key, address, wif):
                logger.warning(f"GPU匹配回调处理失败，跳过地址: {address[:6]}...{address[-4:]}")

    # ========== 性能指标 ==========

    def _update_performance_metrics(self, batch_size: int, execution_time_ms: float) -> None:
        """记录 GPU 性能指标"""
        if not self.gpu_performance_monitor:
            return
        try:
            memory_mb = self._calculate_gpu_memory_usage(batch_size)
            self.gpu_performance_monitor.record_kernel_metrics(
                batch_size=batch_size,
                execution_time_ms=execution_time_ms,
                memory_allocated_mb=memory_mb,
            )
        except Exception as e:
            logger.debug(f"记录GPU性能指标失败: {e}")

    def _record_adjustment(
        self, old_size: int, new_size: int, reason: str, details: str = ""
    ) -> None:
        """记录调整历史"""
        self._engine_monitor.record_adjustment(
            old_size=old_size, new_size=new_size, reason=reason, details=details
        )

    # ========== 自适应批大小 ==========

    def _maybe_adjust_batch_size(self) -> None:
        """根据运行时状态自适应调整 batch_size"""
        if not self._adaptive_batch_enabled:
            return
        current_time = time.monotonic()
        if current_time - self._last_batch_adjust_time < self._batch_adjust_interval:
            return
        self._last_batch_adjust_time = current_time

        stats = self.get_stats()
        total_checked = getattr(stats, "total_checked", 0)
        gpu_errors = getattr(stats, "gpu_errors", 0)
        error_rate = gpu_errors / max(total_checked, 1)
        old_batch_size = self.batch_size

        if error_rate > self._error_rate_threshold:
            new_size = max(self._min_batch_size, old_batch_size // 2)
            if new_size != old_batch_size:
                self.batch_size = new_size
                self._adaptive_error_count = 0
                logger.warning(
                    f"自适应调整: 错误率过高({error_rate:.2%})，"
                    f"降低batch_size: {old_batch_size:,} -> {new_size:,}"
                )
        else:
            gpu_utilization = None
            if self.gpu_performance_monitor:
                try:
                    perf_stats = self.gpu_performance_monitor.get_stats()
                    gpu_utilization = perf_stats.get("avg_gpu_utilization")
                except Exception:
                    pass  # 无法获取GPU性能统计，跳过利用率自适应调整
            if gpu_utilization is not None and gpu_utilization < 0.5:
                new_size = min(self._max_batch_size, int(old_batch_size * 1.5))
                if new_size != old_batch_size:
                    self.batch_size = new_size
                    logger.info(
                        f"自适应调整: GPU利用率低({gpu_utilization:.0%})，"
                        f"增大batch_size: {old_batch_size:,} -> {new_size:,}"
                    )

    # ========== 进度与断点 ==========

    def _check_and_report_progress(self, batch_count: int, current_batch_size: int) -> None:
        """检查并报告进度"""
        current_time = time.time()
        if current_time - self._last_progress_time < self._progress_interval_sec:
            return
        logger.debug(f"GPU 进度回调: batch_count={batch_count}")
        
        assert self.stats is not None
        stats_snapshot = self.stats.snapshot()
        
        # v3.2.0: 发布进度事件
        progress_event = EngineProgressEvent(
            total_checked=stats_snapshot.total_checked,
            speed=stats_snapshot.speed,
            avg_speed=stats_snapshot.avg_speed,
            matches_found=stats_snapshot.matches_found,
            cpu_usage=0.0,  # GPU引擎暂不报告CPU使用
            memory_usage=0.0,
            thread_count=0,
            elapsed_time=time.time() - self.stats.start_time,
        )
        progress_event.source = "gpu_collision_engine"
        self.event_bus.publish(progress_event)
        
        # 向后兼容: 调用传统回调（从事件触发）
        if self.on_progress:
            self.on_progress(stats_snapshot)
        
        self._save_checkpoint(batch_count)
        self._last_progress_time = current_time

        with self._batch_size_lock:
            self._consecutive_gpu_errors = 0

        if not self._gpu_kernel:
            return

        try:
            error_rate = getattr(self.stats, "gpu_errors", 0) / max(batch_count, 1)
            if self._gpu_kernel and self._gpu_kernel.gpu_optimizer:
                new_batch_size, adjustments = self._gpu_kernel.gpu_optimizer.analyze_and_adjust(
                    current_batch_size=current_batch_size,
                    error_rate=error_rate,
                    engine=self,
                )
                if new_batch_size != current_batch_size and adjustments:
                    reason = list(adjustments.keys())[0]
                    logger.info(
                        f"自适应优化: batch_size {current_batch_size} -> {new_batch_size} ({reason})"
                    )
                    self.batch_size = new_batch_size
        except Exception as adjust_error:
            logger.debug(f"自适应调整失败: {adjust_error}")

        self._maybe_adjust_batch_size()

    def _save_checkpoint(self, count: int):
        """保存断点"""
        if self.checkpoint_mgr and self.checkpoint_mgr.should_auto_save():
            matches_list = [
                {"private_key_hash": m["private_key_hash"], "address": m["address"]}
                for m in self.stats.matches
            ]
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=self._current_position,
                total_checked=count,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end,
            )

    # ========== 搜索模式委托 ==========

    def _random_search(self) -> None:
        """随机碰撞模式"""
        assert self._random_search_mode is not None
        self._random_search_mode.execute()

    def _start_range_scan(self) -> None:
        """启动范围扫描"""
        assert self._range_start is not None
        assert self._range_end is not None
        self._range_scan(self._range_start, self._range_end)

    def _start_brute_force(self):
        """启动暴力穷举"""
        assert self._range_start is not None
        return self._brute_force(self._range_start)

    def _random_search_sync(self):
        """同步执行版本"""
        assert self._random_search_mode is not None
        return self._random_search_mode._execute_sync()

    def _random_search_async(self):
        """异步执行版本(双缓冲优化)"""
        assert self._random_search_mode is not None
        return self._random_search_mode._execute_async()

    def _calculate_key_gen_timeout(self, batch_size: int) -> float:
        """异步私钥生成超时计算"""
        assert self._random_search_mode is not None
        return cast(float, self._random_search_mode._calculate_key_gen_timeout(batch_size))

    def _start_async_key_generation(self, batch_size: int) -> Tuple[threading.Thread, List[Any]]:
        """启动异步私钥生成线程"""
        assert self._random_search_mode is not None
        return cast(
            Tuple[threading.Thread, List[Any]],
            self._random_search_mode._start_async_key_generation(batch_size),
        )

    def _wait_for_async_key_generation(
        self, gen_thread: threading.Thread, gen_result: List[Any], batch_num: int
    ) -> bytes:
        """等待异步私钥生成完成"""
        assert self._random_search_mode is not None
        return cast(
            bytes,
            self._random_search_mode._wait_for_async_key_generation(
                gen_thread, gen_result, batch_num
            ),
        )

    def _range_scan(self, start: int, end: int):
        """范围扫描模式"""
        assert self._range_scan_mode is not None
        return self._range_scan_mode.execute(start, end)

    def _brute_force(self, start: int):
        """暴力穷举模式"""
        assert self._brute_force_mode is not None
        return self._brute_force_mode.execute(start)

    def _execute_batch_loop(
        self,
        key_generator_fn: Callable[[], Tuple[bytes, int]],
        mode_name: str,
        stop_condition_fn: Optional[Callable[[], bool]] = None,
    ) -> int:
        """通用批处理执行循环"""
        assert self._brute_force_mode is not None
        return cast(
            int,
            self._brute_force_mode._execute_batch_loop(
                key_generator_fn=key_generator_fn,
                mode_name=mode_name,
                stop_condition_fn=stop_condition_fn,
            ),
        )

    # ========== 异步日志 ==========

    def _setup_async_logging(self, log_file: str, max_bytes: int, backup_count: int):
        """设置异步日志处理器"""
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, mode=0o750, exist_ok=True)
            from ...utils.logger import AsyncFileHandler

            handler = AsyncFileHandler(log_file, max_bytes=max_bytes, backup_count=backup_count)
            self._async_log_handler = handler
            handler.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            logger.info(f"GPU异步日志已启用: {log_file} (max={max_bytes / 1024 / 1024:.0f}MB)")
        except Exception as e:
            logger.warning(f"异步日志启用失败: {e}，使用同步日志")

    # ========== GPU 缓冲区调整 ==========

    def _resize_gpu_buffers(self, new_batch_size: int) -> None:
        """动态调整 GPU 缓冲区大小"""
        try:
            old_batch_size = self.batch_size
            logger.info(f"正在调整GPU缓冲区大小: {old_batch_size:,} -> {new_batch_size:,}")
            if self._gpu_kernel:
                if hasattr(self._gpu_kernel, "release_buffers"):
                    self._gpu_kernel.release_buffers()
                else:
                    for attr in ["_match_buf", "_targets_buf"]:
                        buf = getattr(self._gpu_kernel, attr, None)
                        if buf is not None and hasattr(buf, "release"):
                            try:
                                buf.release()
                                setattr(self._gpu_kernel, attr, None)
                            except Exception:
                                pass  # 缓冲区释放失败不影响主流程
                self._gpu_kernel._max_batch_size = new_batch_size
                if hasattr(self._gpu_kernel, "_allocate_buffers"):
                    self._gpu_kernel._allocate_buffers()
            logger.info(f"GPU缓冲区调整完成: {new_batch_size:,}")
            self._record_adjustment(old_batch_size, new_batch_size, "buffer_resize")
        except Exception as e:
            logger.error(f"GPU缓冲区调整失败: {e}", exc_info=True)
            if self._gpu_kernel:
                self.batch_size = self._gpu_kernel._max_batch_size

    # ========== 配置合并 (scheduled removal: _merge_gpu_configs 无调用者) ==========

    # ========== P2 便捷方法 (向后兼容) ==========

    def _get_perf_pipeline(self) -> PerformanceMonitoringPipeline:
        """懒加载 PerformanceMonitoringPipeline"""
        if self._perf_pipeline is None:
            self._perf_pipeline = PerformanceMonitoringPipeline(
                engine=self,
                config=self._perf_pipeline_config,
            )
        return self._perf_pipeline

    def run_benchmark(self, iterations: int = 5, save_report: bool = True) -> Dict[str, Any]:
        """运行性能基准测试 (P2)"""
        pipeline: Any = self._get_perf_pipeline()
        results = pipeline.run_benchmark(iterations)
        if save_report and results:
            report_path = self.generate_performance_report(
                include_benchmarks=True, include_tuning=False, include_recommendations=True
            )
            logger.info(f"基准测试报告已保存: {report_path}")
        return cast(Dict[str, Any], results)

    def start_auto_tuning(
        self, max_iterations: int = 30, save_report: bool = True, auto_apply: bool = False
    ) -> Dict[str, Any]:
        """启动自动调优 (P2)"""
        if max_iterations <= 0:
            raise ValueError(f"max_iterations 必须大于 0，当前值: {max_iterations}")
        if max_iterations > 1000:
            logger.warning(f"max_iterations={max_iterations} 过大，建议设置为 30-100")

        def on_new_batch_size(new_size: int) -> None:
            if auto_apply:
                old_size = self.batch_size
                self.batch_size = new_size
                logger.info(f"自动更新 batch_size: {old_size:,} -> {new_size:,}")
            else:
                logger.info(f"建议 batch_size: {new_size:,} (当前: {self.batch_size:,})")

        pipeline: Any = self._get_perf_pipeline()
        results = pipeline.start_auto_tuning(
            max_iterations=max_iterations, on_new_batch_size=on_new_batch_size
        )
        optimal_size = results.get("optimal_batch_size")
        if not auto_apply and optimal_size:
            logger.info(f"要应用此配置，请使用: engine.batch_size = {optimal_size:,}")
        if save_report and results:
            report_path = self.generate_performance_report(
                include_benchmarks=False, include_tuning=True, include_recommendations=True
            )
            logger.info(f"调优报告已保存: {report_path}")
        return cast(Dict[str, Any], results)

    def generate_performance_report(
        self,
        include_benchmarks: bool = True,
        include_tuning: bool = True,
        include_history: bool = True,
        include_recommendations: bool = True,
        include_comparison: bool = False,
        output_dir: Optional[str] = None,
    ) -> str:
        """生成性能报告 (P2)"""
        pipeline: Any = self._get_perf_pipeline()
        return pipeline.generate_report(
            include_benchmarks=include_benchmarks,
            include_tuning=include_tuning,
            include_history=include_history,
            include_recommendations=include_recommendations,
            include_comparison=include_comparison,
            output_dir=output_dir,
        )

    # ========== Intel 特定优化 (向后兼容存根) ==========

    def _apply_intel_specific_optimizations(self) -> None:
        """应用 Intel GPU 特定优化 (Phase 6: 委托给 VendorOptimizationFactory)"""
        logger.debug("Intel优化已通过 VendorOptimizationFactory 处理")

    def _init_intel_monitoring_and_tuning(self) -> None:
        """初始化 Intel GPU 监控和调优组件"""
        logger.debug("Intel监控调优已通过 VendorOptimizationFactory 处理")

    def _verify_uint32_workaround(self) -> bool:
        """验证 uint32 workaround"""
        return True

    # ========== v3.2.0: 事件回调包装器 (向后兼容) ==========

    def _on_progress_callback(self, event: EngineProgressEvent) -> None:
        """处理进度事件 - 向后兼容包装器"""
        if self.on_progress:
            self.on_progress(event)

    def _on_match_callback(self, event: EngineMatchEvent) -> None:
        """处理匹配事件 - 向后兼容包装器"""
        if self.on_match:
            self.on_match(event.private_key, event.address, event.wif)

    def _on_complete_callback(self, event: EngineCompleteEvent) -> None:
        """处理完成事件 - 向后兼容包装器"""
        if self.on_complete:
            self.on_complete(event)
