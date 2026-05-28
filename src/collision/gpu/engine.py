"""GPU碰撞引擎 - 协调器实现.

组合 Phase 1-5 建立的独立组件，作为统一的引擎协调器。

职责:
- 组件协调与依赖注入
- 引擎生命周期管理 (start/stop)
- 对外 API 统一接口
- 搜索模式执行桥接

组件:
- GPUDeviceManager (Phase 2): GPU设备/上下文/内核/异步管道
- PerformanceMonitoringPipeline (Phase 3): 性能监控/异常检测
- CollisionCore (Phase 4): 统计/断点/去重/搜索协调
- VendorOptimizationFactory (Phase 5): NVIDIA/AMD/Intel 策略

依赖注入:
- Phase 6.1: 添加可选依赖注入参数，支持自定义组件实现
- 通过 device_manager, search_coordinator 等参数传入自定义实现
- 如未传入，则使用默认实现

版本: v4.2.2 Phase 6.1
创建日期: 2026-04-30
更新日期: 2026-05-23
"""

import contextlib
import logging
import os
import pathlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

# 跨包依赖
from src.gpu.device import GPUDeviceDetector
from src.gpu.device_manager import GPUDeviceManager
from src.gpu.engine_monitor import GPUEngineMonitor
from src.gpu.search_mode_coordinator import SearchModeCoordinator
from src.monitoring.data_logger import DataLogger

# 其余依赖
from src.monitoring.enhanced_monitoring import EnhancedMonitoringSystem
from src.monitoring.event_adapters import (
    DataLoggerAdapter,
    EnhancedMonitoringAdapter,
)
from src.monitoring.gpu_performance_monitor import (
    GPUPerformanceMonitor,
    get_gpu_performance_monitor,
)
from src.monitoring.monitor_config import MonitorConfig
from src.utils import get_configured_logger
from src.utils.logging_config import LOG_DEFAULT_MAX_BYTES
from src.utils.timeout import invoke_with_timeout

from ..base_engine import BaseCollisionEngine

# 碰撞基础
from ..collision_stats import CollisionStats

# v3.2.0: 事件系统支持
from ..event_bus import EventBus
from ..events import (
    # EngineErrorEvent, # 暂未使用
    EngineCompleteEvent,
    EngineMatchEvent,
    EngineProgressEvent,
    EngineStartEvent,
    EngineStopEvent,
    EventType,
)

# 回调类型
from ..types import CompleteCallback, MatchCallback, ProgressCallback

# Phase 1-5 组件
from ._result_processor import GPUResultProcessor
from ._scheduler import GPUBatchScheduler
from .core import CollisionCore

# v3.2.1: 增强私钥生成器
from .key_generator import (
    KeyGenerationStrategy,
)
from .monitoring import (
    PerformanceMonitoringPipeline,
)

logger = get_configured_logger(__name__)

# GPU 常量（必须位于所有导入之后、类定义之前）
UINT32_MAX = 0xFFFFFFFF
GPU_MAX_BATCH_SIZE = UINT32_MAX
INITIAL_BATCH_SIZE = 1_000_000
ASYNC_KEY_GEN_TIMEOUT = 30.0
BATCH_LOG_FREQUENCY = 100
INITIAL_BATCHES_LOG = 3
THREAD_JOIN_TIMEOUT = 5.0
MONITOR_THREAD_JOIN_TIMEOUT = 1.0
EXCEPTION_RECOVERY_DELAY = 0.1
# P2-3.2修复: GPU批次执行瞬态错误重试常量
GPU_BATCH_MAX_RETRIES = 3
GPU_BATCH_RETRY_BASE_DELAY = 0.05  # 基础退避延迟(秒)
GPU_BATCH_RETRY_MAX_DELAY = 2.0
ASYNC_KEY_GEN_BASE_TIMEOUT = 5.0
ASYNC_KEY_GEN_PER_KEY_TIME = 0.00001
ASYNC_KEY_GEN_SAFETY_FACTOR = 2.0

from src.gpu._availability import PYOPENCL_AVAILABLE  # noqa: E402

if PYOPENCL_AVAILABLE:
    import pyopencl as cl
else:
    cl = None  # type: ignore[assignment]

# 预导入 GPU 监控器（模块级缓存）
# 线程安全说明：
# - 模块导入时单线程执行，GIL 保证 _gpu_performance_monitor 赋值安全
# - get_gpu_performance_monitor() 自身已有 _monitor_lock 保护
# - 此缓存仅存储引用，不涉及竞态条件，无需额外线程锁

__all__ = [
    "ASYNC_KEY_GEN_BASE_TIMEOUT",
    "ASYNC_KEY_GEN_PER_KEY_TIME",
    "ASYNC_KEY_GEN_SAFETY_FACTOR",
    "ASYNC_KEY_GEN_TIMEOUT",
    "BATCH_LOG_FREQUENCY",
    "EXCEPTION_RECOVERY_DELAY",
    "GPU_BATCH_MAX_RETRIES",
    "GPU_BATCH_RETRY_BASE_DELAY",
    "GPU_BATCH_RETRY_MAX_DELAY",
    "GPU_MAX_BATCH_SIZE",
    "INITIAL_BATCHES_LOG",
    "INITIAL_BATCH_SIZE",
    "MONITOR_THREAD_JOIN_TIMEOUT",
    "THREAD_JOIN_TIMEOUT",
    "UINT32_MAX",
    "GPUCollisionEngine",
    "GPUEngineConfig",
]

_gpu_performance_monitor = None


def _get_gpu_monitor() -> "GPUPerformanceMonitor":
    """获取 GPU 性能监控器(懒加载).

    线程安全：模块级缓存仅赋值一次，GIL 保护下安全。
    底层 get_gpu_performance_monitor() 已有 _monitor_lock 双重检查锁定。
    """
    global _gpu_performance_monitor
    if _gpu_performance_monitor is None:
        _gpu_performance_monitor = get_gpu_performance_monitor()
    return _gpu_performance_monitor


@dataclass
class GPUEngineConfig:
    """GPU 碰撞引擎配置 (v4.3.1 Phase 6.1).

    将所有配置参数封装为 dataclass，便于外部构造、序列化和验证。
    可通过 GPUCollisionEngine(targets, config=cfg) 传入。

    Phase 6.1 新增:
    - device_manager_class: 自定义GPUDeviceManager类
    - search_coordinator_class: 自定义SearchModeCoordinator类
    """

    targets: set[str] = field(default_factory=set)
    device_index: int = 1
    batch_size: int | None = None
    on_progress: ProgressCallback | None = None
    on_match: MatchCallback | None = None
    on_complete: CompleteCallback | None = None
    event_bus: EventBus | None = None
    checkpoint_enabled: bool = False
    dedup_enabled: bool = False
    dedup_max_size: int = 1_000_000
    checkpoint_interval: int = 30
    data_logging_enabled: bool = True
    data_logging_interval: int = 5
    use_enhanced_monitoring: bool = True
    use_gpu_memory_pool: bool = True
    gpu_pool_max_buffers: int = 100
    gpu_pool_max_memory_mb: int = 512
    use_async_logging: bool = False
    async_log_file: str = "logs/gpu_async.log"
    async_log_max_bytes: int = LOG_DEFAULT_MAX_BYTES
    async_log_backup_count: int = 5
    check_uncompressed: bool | None = None
    key_generation_strategy: KeyGenerationStrategy = field(
        default=KeyGenerationStrategy.PRNG_SEED,
    )
    # Phase 6.1: 依赖注入配置
    device_manager_class: Any | None = None  # 自定义GPUDeviceManager类
    search_coordinator_class: Any | None = None  # 自定义SearchModeCoordinator类

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "device_index": self.device_index,
            "batch_size": self.batch_size,
            "checkpoint_enabled": self.checkpoint_enabled,
            "dedup_enabled": self.dedup_enabled,
            "dedup_max_size": self.dedup_max_size,
            "checkpoint_interval": self.checkpoint_interval,
            "data_logging_enabled": self.data_logging_enabled,
            "data_logging_interval": self.data_logging_interval,
            "use_enhanced_monitoring": self.use_enhanced_monitoring,
            "use_gpu_memory_pool": self.use_gpu_memory_pool,
            "gpu_pool_max_buffers": self.gpu_pool_max_buffers,
            "gpu_pool_max_memory_mb": self.gpu_pool_max_memory_mb,
            "use_async_logging": self.use_async_logging,
            "async_log_file": self.async_log_file,
            "async_log_max_bytes": self.async_log_max_bytes,
            "async_log_backup_count": self.async_log_backup_count,
            "check_uncompressed": self.check_uncompressed,
            "key_generation_strategy": self.key_generation_strategy.value,
            # 枚举名，可通过 KeyGenerationStrategy[name] 反序列化
        }


class GPUCollisionEngine(BaseCollisionEngine):
    """GPU 加速的比特币私钥对撞引擎 - Phase 6 重构版.

    组合 GPUDeviceManager (Phase 2) + PerformanceMonitoringPipeline (Phase 3)
    + CollisionCore (Phase 4) + VendorOptimizationFactory (Phase 5),
    实现统一的引擎协调器。

    继承 BaseCollisionEngine，保持完整向后兼容。

    自 v4.3.1: 支持通过 GPUEngineConfig 配置对象简化参数传递。
    """

    MONITOR_INTERVAL = 100

    def __init__(
        self,
        targets: set[str],
        device_index: int = 1,
        batch_size: int | None = None,
        on_progress: ProgressCallback | None = None,
        on_match: MatchCallback | None = None,
        on_complete: CompleteCallback | None = None,
        checkpoint_enabled: bool = False,
        dedup_enabled: bool = False,
        dedup_max_size: int = 1_000_000,
        checkpoint_interval: int = 30,
        event_bus: EventBus | None = None,
        data_logging_enabled: bool = True,
        data_logging_interval: int = 5,
        use_enhanced_monitoring: bool = True,
        use_gpu_memory_pool: bool = True,
        gpu_pool_max_buffers: int = 100,
        gpu_pool_max_memory_mb: int = 512,
        use_async_logging: bool = False,
        async_log_file: str = "logs/gpu_async.log",
        async_log_max_bytes: int = LOG_DEFAULT_MAX_BYTES,
        async_log_backup_count: int = 5,
        check_uncompressed: bool | None = None,
        key_generation_strategy: KeyGenerationStrategy = (KeyGenerationStrategy.PRNG_SEED),
        config: "GPUEngineConfig | None" = None,
        gpu_config: dict[str, Any] | None = None,
        device_manager: Any | None = None,
        search_coordinator: Any | None = None,
    ) -> None:
        """初始化 GPU 碰撞引擎 (Phase 6.1 重构版).

        支持两种初始化方式:
        1. (推荐) 通过 GPUEngineConfig 对象: GPUCollisionEngine(targets, config=cfg)
        2. (兼容) 直接传参: GPUCollisionEngine(targets, device_index=1, ...)

        当 config 参数提供时，config 中的值覆盖对应的显式参数默认值。
        显式非默认参数值优先于 config 中的值。

        Phase 6.1 新增依赖注入:
        - device_manager: 可传入自定义的GPUDeviceManager实现（用于测试或特殊需求）
        - search_coordinator: 可传入自定义的SearchModeCoordinator实现
        如未传入，则使用默认实现。
        """
        # 合并配置并解决所有参数（config 对象提供默认值）
        params = self._resolve_config(
            config=config,
            batch_size=batch_size,
            check_uncompressed=check_uncompressed,
            device_index=device_index,
            checkpoint_enabled=checkpoint_enabled,
            dedup_enabled=dedup_enabled,
            dedup_max_size=dedup_max_size,
            checkpoint_interval=checkpoint_interval,
            data_logging_enabled=data_logging_enabled,
            data_logging_interval=data_logging_interval,
            use_enhanced_monitoring=use_enhanced_monitoring,
            use_gpu_memory_pool=use_gpu_memory_pool,
            gpu_pool_max_buffers=gpu_pool_max_buffers,
            gpu_pool_max_memory_mb=gpu_pool_max_memory_mb,
            use_async_logging=use_async_logging,
            async_log_file=async_log_file,
            async_log_max_bytes=async_log_max_bytes,
            async_log_backup_count=async_log_backup_count,
            key_generation_strategy=key_generation_strategy,
        )
        batch_size = params["batch_size"]
        check_uncompressed = params["check_uncompressed"]
        device_index = params["device_index"]
        checkpoint_enabled = params["checkpoint_enabled"]
        dedup_enabled = params["dedup_enabled"]
        dedup_max_size = params["dedup_max_size"]
        checkpoint_interval = params["checkpoint_interval"]
        data_logging_enabled = params["data_logging_enabled"]
        data_logging_interval = params["data_logging_interval"]
        use_enhanced_monitoring = params["use_enhanced_monitoring"]
        use_gpu_memory_pool = params["use_gpu_memory_pool"]
        gpu_pool_max_buffers = params["gpu_pool_max_buffers"]
        gpu_pool_max_memory_mb = params["gpu_pool_max_memory_mb"]
        use_async_logging = params["use_async_logging"]
        async_log_file = params["async_log_file"]
        async_log_max_bytes = params["async_log_max_bytes"]
        async_log_backup_count = params["async_log_backup_count"]
        key_generation_strategy = params["key_generation_strategy"]
        device_manager_class = params["device_manager_class"]
        search_coordinator_class = params["search_coordinator_class"]

        self._check_pyopencl()

        logger.debug(
            f"GPU引擎：私钥生成策略参数: {key_generation_strategy.value} (GPU路径不使用)",
        )

        # 初始化基类（提供 self.config, self._lock 等基础设施）
        super().__init__(
            config={
                "mode": "gpu",
                "device_index": device_index,
                "batch_size": batch_size,
                "checkpoint_enabled": checkpoint_enabled,
                "dedup_enabled": dedup_enabled,
            },
        )

        # 显式类型注解 — 因 check_untyped_defs=false，mypy 无法追踪 _init_* 内部对
        # self._core / self._random_search_mode 的赋值，加注解使其类型对 mypy 可见。
        self._core: CollisionCore
        self._random_search_mode: Any
        self._range_scan_mode: Any
        self._brute_force_mode: Any

        self.event_bus = event_bus or EventBus()
        self._init_basic_attrs(
            targets,
            device_index,
            on_progress,
            on_match,
            on_complete,
        )
        self._init_check_uncompressed(check_uncompressed)
        self._init_control_params(batch_size)
        self._init_collision_core(
            targets,
            checkpoint_enabled,
            dedup_enabled,
            dedup_max_size,
            checkpoint_interval,
            on_progress,
            on_match,
        )
        self._init_monitoring_system(
            data_logging_enabled,
            data_logging_interval,
            use_enhanced_monitoring,
            use_async_logging,
            async_log_file,
            async_log_max_bytes,
            async_log_backup_count,
        )
        self._init_gpu_device(
            use_gpu_memory_pool,
            gpu_pool_max_buffers,
            gpu_pool_max_memory_mb,
            gpu_config,
            batch_size,
            device_index,
            targets,
            device_manager,
            device_manager_class,
        )
        self._init_search_coordinator(
            search_coordinator,
            search_coordinator_class,
        )
        self._init_perf_pipeline_config(batch_size, device_index)
        self._init_position_tracking()
        self._init_adaptive_batch()
        self._init_benchmark()

    # ========== 初始化辅助方法 ==========

    @staticmethod
    def _resolve_config(
        config: "GPUEngineConfig | None",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """合并 GPUEngineConfig 与显式参数，返回解析后的参数字典.

        GPUEngineConfig 提供默认值，显式传入的非 None 参数优先。
        """
        if config is None:
            return {
                **kwargs,
                "device_manager_class": None,
                "search_coordinator_class": None,
            }
        cfg = config
        result = dict(kwargs)
        # None 值参数从 cfg 获取默认值
        none_keys = ["batch_size", "check_uncompressed"]
        for key in none_keys:
            if result.get(key) is None:
                result[key] = getattr(cfg, key)
        # 非 None 参数使用 cfg 默认值覆盖函数默认值
        override_keys = [
            "device_index",
            "checkpoint_enabled",
            "dedup_enabled",
            "dedup_max_size",
            "checkpoint_interval",
            "data_logging_enabled",
            "data_logging_interval",
            "use_enhanced_monitoring",
            "use_gpu_memory_pool",
            "gpu_pool_max_buffers",
            "gpu_pool_max_memory_mb",
            "use_async_logging",
            "async_log_file",
            "async_log_max_bytes",
            "async_log_backup_count",
            "key_generation_strategy",
        ]
        for key in override_keys:
            result[key] = getattr(cfg, key)
        result["device_manager_class"] = cfg.device_manager_class
        result["search_coordinator_class"] = cfg.search_coordinator_class
        return result

    @staticmethod
    def _check_pyopencl() -> None:
        """检查 PyOpenCL 可用性，不可用时抛出详细诊断异常."""
        if PYOPENCL_AVAILABLE:
            return
        diagnostic_msg = (
            "PyOpenCL 不可用，无法使用 GPU 加速。\n"
            "诊断步骤:\n"
            "  1. 安装 OpenCL 运行时:\n"
            "     - NVIDIA: conda install pyopencl"
            " nccl-cu* (或 pip install pyopencl)\n"
            "     - Intel: 下载 Intel OpenCL Runtime\n"
            "     - AMD: 安装 AMD APP SDK\n"
            "  2. 验证 GPU 驱动已正确安装\n"
            "  3. 设置 PYOPENCL_DEBUG=1 查看详细错误\n"
            "  4. 使用 CPU 模式作为替代:\n"
            "     python key_collision_cli.py -t <地址> -m random\n"
        )
        raise RuntimeError(diagnostic_msg)

    def _init_basic_attrs(
        self,
        targets: set[str],
        device_index: int,
        on_progress: ProgressCallback | None,
        on_match: MatchCallback | None,
        on_complete: CompleteCallback | None,
    ) -> None:
        """初始化基本属性和事件总线订阅."""
        self.targets = targets
        self.device_index = device_index
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete
        self._data_logger_adapter = None
        self._enhanced_monitoring_adapter = None
        if on_progress:
            self.event_bus.subscribe(
                EventType.ENGINE_PROGRESS,
                self._on_progress_callback,
            )
        if on_match:
            self.event_bus.subscribe(
                EventType.ENGINE_MATCH,
                self._on_match_callback,
            )
        if on_complete:
            self.event_bus.subscribe(
                EventType.ENGINE_COMPLETE,
                self._on_complete_callback,
            )
        self._match_callback_timeout = 5.0
        self._stop_event = threading.Event()
        self._running = False
        self._thread: threading.Thread | None = None
        self._dynamic_speed_benchmark: float = 500000.0
        self._last_memory_check_time = time.time()
        self._memory_check_interval = 60

    def _init_check_uncompressed(
        self,
        check_uncompressed: bool | None,
    ) -> None:
        """初始化压缩格式检测标志."""
        if check_uncompressed is None:
            self._check_uncompressed = self._auto_detect_compression_needed_gpu()
        else:
            self._check_uncompressed = 1 if check_uncompressed else 0

    def _init_control_params(self, batch_size: int | None) -> None:
        """初始化控制参数."""
        self._batch_size = batch_size if batch_size is not None else INITIAL_BATCH_SIZE
        self._batch_size_lock = threading.Lock()
        self._max_gpu_error_retries = 100
        self._consecutive_gpu_errors = 0

    def _init_collision_core(
        self,
        targets: set[str],
        checkpoint_enabled: bool,
        dedup_enabled: bool,
        dedup_max_size: int,
        checkpoint_interval: int,
        on_progress: ProgressCallback | None,
        on_match: MatchCallback | None,
    ) -> None:
        """初始化 CollisionCore（统计/断点/去重）."""
        self._core = CollisionCore(  # type: ignore[abstract]
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
        self.stats = self._core.stats
        self.checkpoint_mgr = self._core.checkpoint
        self.dedup_filter = self._core.dedup_filter

    def _init_monitoring_system(
        self,
        data_logging_enabled: bool,
        data_logging_interval: int,
        use_enhanced_monitoring: bool,
        use_async_logging: bool,
        async_log_file: str,
        async_log_max_bytes: int,
        async_log_backup_count: int,
    ) -> None:
        """初始化监控系统和异步日志."""
        self.data_logging_enabled = data_logging_enabled
        self.data_logging_interval = data_logging_interval
        self.data_logger = None
        self.enhanced_monitoring = None
        self._engine_monitor = GPUEngineMonitor(engine=self)  # type: ignore[arg-type]
        self._async_log_handler: Any | None = None
        if use_async_logging:
            self._setup_async_logging(
                async_log_file,
                async_log_max_bytes,
                async_log_backup_count,
            )

        if not data_logging_enabled:
            return
        try:
            if use_enhanced_monitoring:
                self.enhanced_monitoring = EnhancedMonitoringSystem(
                    config=MonitorConfig(
                        collection_interval=data_logging_interval,
                        enable_monitoring_data=False,
                    ),
                )
                self.data_logger = self.enhanced_monitoring.data_logger
                self._enhanced_monitoring_adapter = EnhancedMonitoringAdapter(  # type: ignore[assignment]
                    self.enhanced_monitoring,
                )
                self._enhanced_monitoring_adapter.subscribe_to(self.event_bus)  # type: ignore[attr-defined]
                self.enhanced_monitoring.start()
                logger.debug("GPU引擎：增强监控系统已启用并启动（事件适配器模式）")
            else:
                self.data_logger = DataLogger()
                self._data_logger_adapter = DataLoggerAdapter(self.data_logger)  # type: ignore[assignment]
                self._data_logger_adapter.subscribe_to(self.event_bus)  # type: ignore[attr-defined]
                logger.debug("GPU引擎：数据日志系统已启用（事件适配器模式）")
        except Exception as e:
            logger.warning("GPU引擎：监控系统初始化失败: %s", e, exc_info=True)
            self.data_logging_enabled = False

    def _init_gpu_device(
        self,
        use_gpu_memory_pool: bool,
        gpu_pool_max_buffers: int,
        gpu_pool_max_memory_mb: int,
        gpu_config: dict[str, Any] | None,
        batch_size: int | None,
        device_index: int,
        targets: set[str],
        device_manager: Any | None,
        device_manager_class: Any | None,
    ) -> None:
        """初始化 GPU 设备管理器."""
        _base_gpu_cfg: dict[str, Any] = {
            "use_memory_pool": use_gpu_memory_pool,
            "pool_max_buffers": gpu_pool_max_buffers,
            "pool_max_memory_mb": gpu_pool_max_memory_mb,
        }
        if gpu_config:
            _base_gpu_cfg.update(gpu_config)
        gpu_facade_config = {"gpu": _base_gpu_cfg, "batch_size": batch_size}

        if device_manager is not None:
            self._device_manager = device_manager
        elif device_manager_class is not None:
            self._device_manager = device_manager_class(
                device_index=device_index,
                config=gpu_facade_config,
                logger=logger,
            )
            self._device_manager.initialize(
                targets,
                batch_size,
                check_uncompressed=self._check_uncompressed,
            )
        else:
            self._device_manager = GPUDeviceManager(
                device_index=device_index,
                config=gpu_facade_config,
                logger=logger,
            )
            self._device_manager.initialize(
                targets,
                batch_size,
                check_uncompressed=self._check_uncompressed,
            )

        self._gpu_device = self._device_manager.device
        self._gpu_context = self._device_manager.context
        self._gpu_kernel = self._device_manager.kernel
        try:
            self._async_executor = self._device_manager.async_executor
        except RuntimeError:
            self._async_executor = None
        self._gpu_memory_pool = self._device_manager.memory_pool

    def _init_search_coordinator(
        self,
        search_coordinator: Any | None,
        search_coordinator_class: Any | None,
    ) -> None:
        """初始化搜索模式协调器."""
        if search_coordinator is not None:
            self._search_coordinator = search_coordinator
        elif search_coordinator_class is not None:
            self._search_coordinator = search_coordinator_class(self, logger)
        else:
            self._search_coordinator = SearchModeCoordinator(self, logger)  # type: ignore[arg-type]

        self._random_search_mode = self._search_coordinator.get_mode_instance("random")
        self._range_scan_mode = self._search_coordinator.get_mode_instance("range_scan")
        self._brute_force_mode = self._search_coordinator.get_mode_instance("brute_force")

    def _init_perf_pipeline_config(
        self,
        batch_size: int | None,
        device_index: int,
    ) -> None:
        """初始化性能监控管道配置（懒加载）."""
        self._perf_pipeline: PerformanceMonitoringPipeline | None = None
        self._perf_pipeline_config: dict[str, Any] = {
            "batch_size": batch_size,
            "device_index": device_index,
        }

    def _init_position_tracking(self) -> None:
        """初始化位置跟踪."""
        self._current_position = 0
        self._current_mode = ""
        self._range_start = None
        self._range_end = None
        self._last_progress_time = 0.0
        self._progress_interval_sec = 0.5
        self.gpu_performance_monitor = _get_gpu_monitor()

    def _init_adaptive_batch(self) -> None:
        """初始化自适应批处理参数."""
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

    def _init_benchmark(self) -> None:
        """初始化性能基准."""
        self._result_processor = GPUResultProcessor(engine=self)
        self._scheduler = GPUBatchScheduler(engine=self)
        self._scheduler.calculate_dynamic_benchmark()

    # ========== 属性 ==========

    @property
    def batch_size(self) -> int:
        """线程安全的 batch_size 读取."""
        with self._batch_size_lock:
            return int(self._batch_size)

    @batch_size.setter
    def batch_size(self, value: int) -> None:
        """线程安全的 batch_size 写入 (UINT32_MAX 溢出检查)."""
        if value >= GPU_MAX_BATCH_SIZE:
            raise ValueError(
                f"batch_size ({value:,}) >= UINT32_MAX "
                f"({GPU_MAX_BATCH_SIZE:,}) 会导致 GPU 内核 gid 溢出",
            )
        with self._batch_size_lock:
            self._batch_size = value

    # ========== 公共 API ==========

    @classmethod
    def from_config(cls, config: GPUEngineConfig) -> "GPUCollisionEngine":
        """从 GPUEngineConfig dataclass 创建引擎实例（v4.2.2 M8）.

        推荐使用此方法替代构造函数直接传参，享受类型安全和 IDE 补全。

        Args:
            config: GPUEngineConfig 配置对象

        Returns:
            已初始化（但未启动）的 GPUCollisionEngine 实例

        """
        return cls(
            targets=config.targets,
            device_index=config.device_index,
            batch_size=config.batch_size,
            on_progress=config.on_progress,
            on_match=config.on_match,
            on_complete=config.on_complete,
            checkpoint_enabled=config.checkpoint_enabled,
            dedup_enabled=config.dedup_enabled,
            dedup_max_size=config.dedup_max_size,
            checkpoint_interval=config.checkpoint_interval,
            event_bus=config.event_bus,
            data_logging_enabled=config.data_logging_enabled,
            data_logging_interval=config.data_logging_interval,
            use_enhanced_monitoring=config.use_enhanced_monitoring,
            use_gpu_memory_pool=config.use_gpu_memory_pool,
            gpu_pool_max_buffers=config.gpu_pool_max_buffers,
            gpu_pool_max_memory_mb=config.gpu_pool_max_memory_mb,
            use_async_logging=config.use_async_logging,
            async_log_file=config.async_log_file,
            async_log_max_bytes=config.async_log_max_bytes,
            async_log_backup_count=config.async_log_backup_count,
            check_uncompressed=config.check_uncompressed,
            key_generation_strategy=config.key_generation_strategy,
        )

    @staticmethod
    def is_gpu_available() -> bool:
        """检查 GPU 是否可用."""
        return GPUDeviceDetector.is_gpu_available()

    def start(  # type: ignore[no-untyped-def]
        self,
        mode: str = "random",
        resume: bool = False,
        **kwargs,
    ) -> None:
        """启动对撞."""
        if self._running:
            return
        with self._batch_size_lock:
            self._consecutive_gpu_errors = 0
        self._adaptive_error_count = 0
        self._stop_event.clear()
        self._running = True
        self._current_mode = mode

        # 每次 start 重新初始化 Core 组件（stats/checkpoint/dedup）
        self._core._init_stats()
        self.stats = self._core.stats
        if self.checkpoint_mgr is None and self._core.config.get("checkpoint_enabled", False):
            self._core._init_checkpoint()
            self.checkpoint_mgr = self._core.checkpoint
        if self.dedup_filter is None and self._core.config.get("dedup_enabled", False):
            self._core._init_dedup_filter()
            self.dedup_filter = self._core.dedup_filter

        if self.stats is None:
            raise RuntimeError(
                "GPUCollisionEngine.start(): self.stats is None, _core._init_stats() 可能未正确初始化",
            )
        self.stats.start_time = time.time()

        # v4.2.1: 发布引擎启动事件
        start_event = EngineStartEvent(
            mode=mode,
            target_count=len(self.targets),
            batch_size=self.batch_size,
            source="gpu_collision_engine",
        )
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

    def _save_checkpoint_on_stop(self) -> None:
        """保存最终断点（stop 时调用）。."""
        if not self.checkpoint_mgr:
            return
        try:
            matches_list = [
                {
                    "private_key_hash": m["private_key_hash"],
                    "address": m["address"],
                }
                for m in self.stats.matches
                if (isinstance(m, dict) and "private_key_hash" in m and "address" in m)
            ]
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
        except Exception as e:
            logger.error("保存最终断点失败: %s", e, exc_info=True)

    def _publish_stop_events(self) -> None:
        """发布引擎停止和完成事件。.

        调用方（stop()）保证 self.stats 非 None，此处不做重复检查。
        """
        if self.stats is None:
            raise RuntimeError("GPUCollisionEngine.stats is None when publishing stop events")
        # v5.2.2: 修复 — 填充 stats 和 total_checked 字段
        stop_event = EngineStopEvent(
            reason="user_request",
            source="gpu_collision_engine",
            stats=self.stats.to_dict(),
            total_checked=self.stats.total_checked,
        )
        self.event_bus.publish(stop_event)

        complete_event = EngineCompleteEvent(
            stats=self.stats.to_dict(),
            duration=time.time() - self.stats.start_time,
            source="gpu_collision_engine",
        )
        self.event_bus.publish(complete_event)

    @staticmethod
    def _safe_cleanup_component(
        component: Any,
        cleanup_attr: str,
        error_msg: str,
        log_level: str = "error",
        extra_cleanup: Callable[[], None] | None = None,
    ) -> None:
        """安全清理组件，捕获并记录异常.

        Args:
            component: 要清理的组件对象
            cleanup_attr: 调用的清理方法名
            error_msg: 失败时的错误日志信息
            log_level: 日志级别 ("error" 或 "warning")
            extra_cleanup: 额外清理回调（清理后执行）
        """
        if not component:
            return
        try:
            getattr(component, cleanup_attr)()
        except Exception as e:
            log_fn = logger.warning if log_level == "warning" else logger.error
            log_fn("%s: %s", error_msg, e, exc_info=True)
        if extra_cleanup:
            extra_cleanup()

    def _cleanup_stop_components(self) -> None:
        """停止后清理所有组件（监控、去重、日志、种子预生成、异步执行器等）。."""
        self._safe_cleanup_component(
            self.enhanced_monitoring,
            "stop",
            "停止监控系统失败",
        )
        self._safe_cleanup_component(
            self.gpu_performance_monitor,
            "stop",
            "停止GPU性能监控器失败",
        )
        self._safe_cleanup_component(
            self._perf_pipeline,
            "stop",
            "停止性能监控管道失败",
        )
        if self.dedup_filter and self.dedup_filter.enabled:
            self.dedup_filter.reset()
        self._safe_cleanup_component(
            self.data_logger,
            "flush",
            "刷写数据日志失败",
        )
        self._safe_cleanup_component(
            getattr(self, "_random_search_mode", None),
            "stop",
            "停止种子预生成线程失败",
            log_level="warning",
        )
        self._safe_cleanup_component(
            self._async_executor,
            "cleanup",
            "清理异步执行器失败",
            extra_cleanup=lambda: setattr(self, "_async_executor", None),
        )
        self._safe_cleanup_component(
            self._device_manager,
            "cleanup",
            "清理设备管理器失败",
        )

    def stop(self, timeout: float | None = None) -> None:
        """停止对撞（幂等，重复调用安全）。."""
        if self._stop_event.is_set():
            logger.debug("stop() 已执行过，跳过重复调用")
            return

        # 状态一致性守卫：stats 必须在后续步骤前可用
        if self.stats is None:
            logger.warning("stop() 跳过：引擎从未 start，stats 未初始化")
            self._stop_event.set()
            self._running = False
            return

        self._search_coordinator.stop()
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout if timeout is not None else 5)

        self._save_checkpoint_on_stop()
        self._publish_stop_events()
        self._cleanup_stop_components()

        self._thread = None
        logger.info("GPU引擎：资源清理完成")

    def is_running(self) -> bool:
        """是否正在运行."""
        return bool(self._running and self._thread and self._thread.is_alive())

    def get_device_info(self) -> dict[str, Any]:
        """获取 GPU 设备信息."""
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
        """获取统计信息."""
        if self.stats is None:
            raise RuntimeError(
                "GPUCollisionEngine.get_stats(): self.stats is None, 引擎未正确初始化",
            )
        return self.stats

    def get_adjustment_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取调整历史."""
        return self._engine_monitor.get_adjustment_history(limit=limit)

    # ========== 上下文管理器 ==========

    def __enter__(self) -> "GPUCollisionEngine":
        """进入上下文管理器."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文管理器，停止引擎."""
        self.stop()

    def __del__(self) -> None:
        """Q5修复: 析构函数只做最小化清理，避免死锁和竞态条件.

        不调用完整的 stop() 方法，因为：
        1. stop() 会尝试获取锁，在多线程环境中可能导致死锁
        2. 析构期间可能存在部分初始化的对象
        3. 守护线程会在进程退出时自动清理资源

        风险说明（评估为低风险，暂不修改）：
        - __del__ 中调用 checkpoint 保存涉及文件 I/O，在解释器关闭时可能失败
        - 但已有 try/except 包裹，异常被 contextlib.suppress 静默处理
        - 推荐使用上下文管理器（with 语句）确保资源正确释放
        """
        try:
            # 检查对象是否已完全初始化
            if not hasattr(self, "_stop_event"):
                return

            # Q7增强: 尽力保存断点（仅在引擎完全初始化且有数据时尝试）
            if (
                hasattr(self, "checkpoint_mgr")
                and self.checkpoint_mgr is not None
                and hasattr(self, "stats")
                and self.stats is not None
            ):
                with contextlib.suppress(Exception):
                    self._save_checkpoint_on_stop()

            # 只设置停止事件，不调用完整的 stop() 方法
            if not self._stop_event.is_set():
                self._stop_event.set()

            # 清理异步执行器（如果存在且已初始化）
            if hasattr(self, "_async_executor") and self._async_executor is not None:
                with contextlib.suppress(Exception):
                    self._async_executor.cleanup()
                self._async_executor = None

            # 清理设备管理器
            if hasattr(self, "_device_manager") and self._device_manager is not None:
                with contextlib.suppress(Exception):
                    self._device_manager.cleanup()
                self._device_manager = None
                self._gpu_memory_pool = None

            # GPU 内存池由 device_manager.cleanup() 统一清理，无需重复操作

            # 停止 enhanced_monitoring（修复: 防止异常路径绕过上下文管理器）
            if hasattr(self, "enhanced_monitoring") and self.enhanced_monitoring is not None:
                with contextlib.suppress(Exception):
                    self.enhanced_monitoring.stop()

            # 清理性能监控管道（修复: 资源泄漏）
            if hasattr(self, "_perf_pipeline") and self._perf_pipeline is not None:
                try:
                    if hasattr(self._perf_pipeline, "stop"):
                        self._perf_pipeline.stop()
                    elif hasattr(self._perf_pipeline, "cleanup"):
                        self._perf_pipeline.cleanup()
                except Exception as e:
                    logger.debug(f"GPU性能管道清理异常（非致命）: {type(e).__name__}: {e}")
                self._perf_pipeline = None
        except Exception as e:
            logger.debug(f"GPU引擎析构清理异常（非致命）: {type(e).__name__}: {e}")

    # ========== 厂商检测 ==========

    def _detect_vendor_from_device(self) -> str:
        """从 GPU 设备检测厂商."""
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
        """GPU 路径智能检测是否需要双格式检查.

        P2PKH地址无法从字符串区分压缩/非压缩来源，优先保证不漏匹配。
        仅在目标数 >= 50000 时自动切为仅压缩格式。
        """
        target_count = len(self.targets)
        compression_auto_threshold = 50000
        if target_count < compression_auto_threshold:
            return 1
        logger.warning(
            "GPU引擎: 目标地址数=%s >= %s，自动切换为仅检查压缩格式（性能优先）。"
            "注意：非压缩P2PKH地址将不会被匹配！如需确保匹配所有地址，"
            "请设置 check_uncompressed=True。",
            target_count,
            compression_auto_threshold,
        )
        return 0

    # ========== GPU 显存用量计算 ==========

    def _calculate_gpu_memory_usage(self, num_keys: int) -> float:
        """计算 GPU 显存使用(MB) [委托给 _scheduler]."""
        return self._scheduler.calculate_gpu_memory_usage(num_keys)

    # ========== 性能基准 ==========

    def _calculate_dynamic_benchmark(self) -> None:
        """计算动态性能基准值 [委托给 _scheduler]."""
        self._scheduler.calculate_dynamic_benchmark()

    def _check_memory_leaks(self) -> None:
        """定期检查内存泄漏 [委托给 _scheduler]."""
        self._scheduler.check_memory_leaks()

    # ========== GPU 批次执行 ==========

    def _execute_gpu_batch(
        self,
        seed: bytes,
        batch_size: int,
        batch_num: int,
    ) -> tuple[list[dict[str, int]], float]:
        """执行 GPU batch 计算 [委托给 _scheduler]."""
        return self._scheduler.execute_batch(seed, batch_size, batch_num)

    def _execute_gpu_batch_once(
        self,
        seed: bytes,
        batch_size: int,
        batch_num: int,
    ) -> tuple[list[dict[str, int]], float]:
        """单次 GPU batch 执行 [委托给 _scheduler]."""
        return self._scheduler.execute_batch_once(seed, batch_size, batch_num)

    # ========== 匹配回调 ==========

    def _safe_invoke_match_callback(
        self,
        private_key: bytes,
        address: str,
        wif: str,
    ) -> bool:
        """安全调用匹配回调函数 [委托给 _result_processor]."""
        return self._result_processor.safe_invoke_match_callback(
            private_key,
            address,
            wif,
        )

    # ========== 匹配处理 ==========

    def _process_gpu_matches(
        self,
        private_keys: bytes,
        matches: list[dict[str, int]],
    ) -> None:
        """处理 GPU 匹配结果 [委托给 _result_processor]."""
        self._result_processor.process_matches(private_keys, matches)

    def _process_gpu_matches_prng(
        self,
        seed: bytes,
        matches: list[dict[str, int]],
    ) -> None:
        """处理 GPU 匹配结果 (PRNG 模式) [委托给 _result_processor]."""
        self._result_processor.process_matches_prng(seed, matches)

    # ========== 性能指标 ==========

    def _update_performance_metrics(
        self,
        batch_size: int,
        execution_time_ms: float,
    ) -> None:
        """记录 GPU 性能指标 [委托给 _scheduler]."""
        self._scheduler.update_performance_metrics(
            batch_size,
            execution_time_ms,
        )

    def _record_adjustment(
        self,
        old_size: int,
        new_size: int,
        reason: str,
        details: str = "",
    ) -> None:
        """记录调整历史 [委托给 _scheduler]."""
        self._scheduler.record_adjustment(old_size, new_size, reason, details)

    # ========== 自适应批大小 ==========

    def _maybe_adjust_batch_size(self) -> None:
        """根据运行时状态自适应调整 batch_size [委托给 _scheduler]."""
        self._scheduler.maybe_adjust_batch_size()

    # ========== 进度与断点 ==========

    def _check_and_report_progress(
        self,
        batch_count: int,
        current_batch_size: int,
    ) -> None:
        """检查并报告进度 [委托给 _scheduler]."""
        self._scheduler.check_and_report_progress(
            batch_count,
            current_batch_size,
        )

    def _save_checkpoint(self, count: int) -> None:
        """保存断点 [委托给 _scheduler]."""
        self._scheduler.save_checkpoint(count)

    # ========== 搜索模式委托 ==========

    def _random_search(self) -> None:
        """随机碰撞模式."""
        if self._random_search_mode is None:
            raise RuntimeError("_random_search_mode not set")
        self._random_search_mode.execute()

    def _start_range_scan(self) -> None:
        """启动范围扫描."""
        if self._range_start is None:
            raise RuntimeError("_range_start not set")
        if self._range_end is None:
            raise RuntimeError("_range_end not set")
        self._range_scan(self._range_start, self._range_end)

    def _start_brute_force(self) -> None:
        """启动暴力穷举."""
        if self._range_start is None:
            raise RuntimeError("_range_start not set for brute_force")
        return self._brute_force(self._range_start)

    def _random_search_sync(self) -> None:
        """同步执行版本."""
        if self._random_search_mode is None:
            raise RuntimeError("_random_search_mode not set for sync")
        return self._random_search_mode._execute_sync()

    def _random_search_async(self) -> None:
        """异步执行版本(双缓冲优化)."""
        if self._random_search_mode is None:
            raise RuntimeError("_random_search_mode not set for async")
        return self._random_search_mode._execute_async()

    def _calculate_key_gen_timeout(self, batch_size: int) -> float:
        """异步私钥生成超时计算."""
        if self._random_search_mode is None:
            raise RuntimeError("_random_search_mode not set for key_gen_timeout")
        return cast(
            "float",
            self._random_search_mode._calculate_key_gen_timeout(
                batch_size,
            ),
        )

    def _start_async_key_generation(
        self,
        batch_size: int,
    ) -> tuple[threading.Thread, list[Any]]:
        """启动异步私钥生成线程."""
        if self._random_search_mode is None:
            raise RuntimeError("_random_search_mode not set for async_key_gen")
        return cast(
            "tuple[threading.Thread, list[Any]]",
            self._random_search_mode._start_async_key_generation(batch_size),
        )

    def _wait_for_async_key_generation(
        self,
        gen_thread: threading.Thread,
        gen_result: list[Any],
        batch_num: int,
    ) -> bytes:
        """等待异步私钥生成完成."""
        if self._random_search_mode is None:
            raise RuntimeError("_random_search_mode not set for wait_async")
        return cast(
            "bytes",
            self._random_search_mode._wait_for_async_key_generation(
                gen_thread,
                gen_result,
                batch_num,
            ),
        )

    def _range_scan(self, start: int, end: int) -> None:
        """范围扫描模式."""
        if self._range_scan_mode is None:
            raise RuntimeError("GPUCollisionEngine._range_scan_mode is None when calling _range_scan()")
        return self._range_scan_mode.execute(start, end)

    def _brute_force(self, start: int) -> None:
        """暴力穷举模式."""
        if self._brute_force_mode is None:
            raise RuntimeError("_brute_force_mode not set")
        return self._brute_force_mode.execute(start)

    def _execute_batch_loop(
        self,
        key_generator_fn: Callable[[], tuple[bytes, int]],
        mode_name: str,
        stop_condition_fn: Callable[[], bool] | None = None,
    ) -> int:
        """通用批处理执行循环."""
        if self._brute_force_mode is None:
            raise RuntimeError("_brute_force_mode not set for _execute_batch_loop")
        return cast(
            "int",
            self._brute_force_mode._execute_batch_loop(
                key_generator_fn=key_generator_fn,
                mode_name=mode_name,
                stop_condition_fn=stop_condition_fn,
            ),
        )

    # ========== 异步日志 ==========

    def _setup_async_logging(  # type: ignore[no-untyped-def]
        self,
        log_file: str,
        max_bytes: int,
        backup_count: int,
    ):
        """设置异步日志处理器."""
        try:
            log_dir = os.path.dirname(log_file)
            log_path = pathlib.Path(log_dir)
            if log_dir and not log_path.exists():
                log_path.mkdir(mode=0o750, exist_ok=True, parents=True)
            from src.utils.logger import AsyncFileHandler

            handler = AsyncFileHandler(
                log_file,
                max_bytes=max_bytes,
                backup_count=backup_count,
            )
            self._async_log_handler = handler
            handler.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            logger.info(
                "GPU异步日志已启用: %s (max=%.0fMB)",
                log_file,
                max_bytes / 1024 / 1024,
            )
        except Exception as e:
            logger.warning("异步日志启用失败: %s，使用同步日志", e)

    # ========== GPU 缓冲区调整 ==========

    def _resize_gpu_buffers(self, new_batch_size: int) -> None:
        """动态调整 GPU 缓冲区大小 [委托给 _scheduler]."""
        self._scheduler.resize_gpu_buffers(new_batch_size)

    # ========== P2 便捷方法 (向后兼容) ==========

    def _get_perf_pipeline(self) -> PerformanceMonitoringPipeline:
        """懒加载 PerformanceMonitoringPipeline."""
        if self._perf_pipeline is None:
            self._perf_pipeline = PerformanceMonitoringPipeline(
                engine=self,
                config=self._perf_pipeline_config,
            )
        return self._perf_pipeline

    def run_benchmark(
        self,
        iterations: int = 5,
        save_report: bool = True,
    ) -> dict[str, Any]:
        """运行性能基准测试 (P2)."""
        pipeline: Any = self._get_perf_pipeline()
        results = pipeline.run_benchmark(iterations)
        if save_report and results:
            report_path = self.generate_performance_report(
                include_benchmarks=True,
                include_tuning=False,
                include_recommendations=True,
            )
            logger.info("基准测试报告已保存: %s", report_path)
        return cast("dict[str, Any]", results)

    def start_auto_tuning(
        self,
        max_iterations: int = 30,
        save_report: bool = True,
        auto_apply: bool = False,
    ) -> dict[str, Any]:
        """启动自动调优 (P2)."""
        if max_iterations <= 0:
            raise ValueError(f"max_iterations 必须大于 0，当前值: {max_iterations}")
        if max_iterations > 1000:
            logger.warning("max_iterations=%s 过大，建议设置为 30-100", max_iterations)

        def on_new_batch_size(new_size: int) -> None:
            if auto_apply:
                old_size = self.batch_size
                self.batch_size = new_size
                logger.info(f"自动更新 batch_size: {old_size:,} -> {new_size:,}")
            else:
                logger.info(
                    "建议 batch_size: %s (当前: %s)",
                    f"{new_size:,}",
                    f"{self.batch_size:,}",
                )

        pipeline: Any = self._get_perf_pipeline()
        results = pipeline.start_auto_tuning(
            max_iterations=max_iterations,
            on_new_batch_size=on_new_batch_size,
        )
        optimal_size = results.get("optimal_batch_size")
        if not auto_apply and optimal_size:
            logger.info(f"要应用此配置，请使用: engine.batch_size = {optimal_size:,}")
        if save_report and results:
            report_path = self.generate_performance_report(
                include_benchmarks=False,
                include_tuning=True,
                include_recommendations=True,
            )
            logger.info("调优报告已保存: %s", report_path)
        return cast("dict[str, Any]", results)

    def generate_performance_report(
        self,
        include_benchmarks: bool = True,
        include_tuning: bool = True,
        include_history: bool = True,
        include_recommendations: bool = True,
        include_comparison: bool = False,
        output_dir: str | None = None,
    ) -> str:
        """生成性能报告 (P2)."""
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
        """应用 Intel GPU 特定优化 (Phase 6: 委托给 VendorOptimizationFactory)."""
        logger.debug("Intel优化已通过 VendorOptimizationFactory 处理")

    def _init_intel_monitoring_and_tuning(self) -> None:
        """初始化 Intel GPU 监控和调优组件."""
        logger.debug("Intel监控调优已通过 VendorOptimizationFactory 处理")

    def _verify_uint32_workaround(self) -> bool:
        """验证 uint32 workaround."""
        return True

    # ========== v4.2.1: 事件回调包装器 (向后兼容) ==========

    def _on_progress_callback(self, event: EngineProgressEvent) -> None:
        """处理进度事件 - 向后兼容包装器."""
        if self.on_progress:
            invoke_with_timeout(
                self.on_progress,
                args=(event,),
                timeout=5.0,
                callback_name="on_progress",
            )

    def _on_match_callback(self, event: EngineMatchEvent) -> None:
        """处理匹配事件 - 仅记录日志，不重复调用用户回调.

        BLOCK-2修复: safe_invoke_match_callback 已通过 _result_processor
        直接调用 self.on_match（传递原始私钥/WIF），此 EventBus 路径
        仅用于日志/监控，不应重复触发用户回调。
        """
        logger.info(
            "GPU引擎匹配事件: address=%s...%s",
            event.address[:4] if event.address else "?",
            event.address[-4:] if event.address else "?",
        )

    def _on_complete_callback(self, event: EngineCompleteEvent) -> None:
        """处理完成事件 - 向后兼容包装器."""
        if self.on_complete:
            invoke_with_timeout(
                self.on_complete,
                args=(event,),
                timeout=5.0,
                callback_name="on_complete",
            )
