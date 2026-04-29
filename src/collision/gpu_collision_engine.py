"""GPU加速的比特币私钥对撞引擎

基于 OpenCL 的 GPU 加速实现，利用 GPU 并行计算能力进行批量私钥碰撞检测。
"""

# ========== 标准库导入 ==========
import os
import sys
import json
import time
import signal
import threading
import secrets
import logging
from pathlib import Path
from typing import Set, Optional, Callable, Tuple, List, Dict, Any

# v2.2.1: 导入异步日志支持
try:
    from ..utils.logger import AsyncFileHandler
    ASYNC_LOG_AVAILABLE = True
except ImportError:
    ASYNC_LOG_AVAILABLE = False

# CODE-1修复: 导入GPU配置管理器（可选）
try:
    from .gpu_config_manager import GPUConfigManager
    GPU_CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    GPU_CONFIG_MANAGER_AVAILABLE = False
    GPUConfigManager = None

# P2-2: 导入GPU缓冲区追踪器（已迁移至独立模块）
from ..gpu.buffer_tracker import GPUBufferTracker

# Task#2: 导入搜索模式模块（已迁移至独立模块）
from ..gpu.search_modes import RandomSearchMode, BruteForceSearchMode, RangeScanSearchMode

# Task#3: 导入引擎监控模块（已迁移至独立模块）
from ..gpu.engine_monitor import GPUEngineMonitor

# 导入日志配置（修复：统一使用get_configured_logger）
from ..utils import get_configured_logger

# v2.2.1迁移: 移除未使用的secp256k1导入，使用crypto_backend
# from ..core.secp256k1 import Secp256k1  # 已删除，未使用

# 修复: 使用统一的logger获取方式
logger = get_configured_logger(__name__)

# ========== 常量定义 ==========
# P2-2: 魔法数字提取为常量
# GPU计算常量
INITIAL_BATCH_SIZE = 1_000_000  # 初始批次大小（100万）
ASYNC_KEY_GEN_TIMEOUT = 30.0  # 异步私钥生成超时（秒）
BATCH_LOG_FREQUENCY = 100  # 日志记录频率（每N个batch）
INITIAL_BATCHES_LOG = 3  # 初始批次日志数量

# P1-2修复: GPU内核 gid 为 ulong (64-bit), 但 num_keys 仍为 uint (32-bit)
# batch_size 必须 < 2^32 以防止 gid 溢出和安全参数截断
UINT32_MAX = 0xFFFFFFFF  # 4294967295
GPU_MAX_BATCH_SIZE = UINT32_MAX  # GPU内核 batch_size 上限 (匹配 num_keys 的 uint 类型)

# 线程等待超时
THREAD_JOIN_TIMEOUT = 5.0  # 默认线程join超时（秒）
MONITOR_THREAD_JOIN_TIMEOUT = 1.0  # 监控线程join超时（秒）

# 异常恢复
EXCEPTION_RECOVERY_DELAY = 0.1  # 异常恢复延迟（秒）

# ALG-1修复: 异步私钥生成超时计算常量
ASYNC_KEY_GEN_BASE_TIMEOUT = 5.0  # 基础超时（秒）
ASYNC_KEY_GEN_PER_KEY_TIME = 0.00001  # 每个私钥预计时间（10微秒）
ASYNC_KEY_GEN_SAFETY_FACTOR = 2.0  # 安全系数

# ========== 本地模块导入 ==========
# GPU设备与上下文
from ..gpu.device import GPUDevice, GPUDeviceDetector
from ..gpu.context import GPUContext
from ..gpu.device_helper import GPUDeviceHelper  # P1-2修复：从独立模块导入

# GPU内核与协议
from ..gpu.profiles.loader import GPUProfileLoader
from ..gpu.kernel import OPENCL_KERNEL_SOURCE
from ..gpu.kernel_protocol import GPUKernelProtocol, GPUKernelFactory  # P1-2修复
from ..gpu.kernel_impl import GPUKernel

# GPU性能优化
from ..gpu.performance_optimizer import get_gpu_optimizer, PerformanceMetrics
from ..gpu.auto_config import get_gpu_configurator, GPUAutoConfigurator
from ..gpu.intel_timeout_manager import AdaptiveTimeoutManager
from ..gpu.intel_memory_monitor import IntelMemoryMonitor
from ..gpu.benchmark_suite import GPUBenchmarkSuite
from ..gpu.auto_tuner import GPUAutoTuner
from ..gpu.performance_reporter import PerformanceReportGenerator, ReportConfig
from ..gpu.async_executor import AsyncGPUExecutor  # 异步优化
from ..utils.exception_handler import ExceptionHandler  # 统一异常处理器
from ..utils.performance_monitor import EnhancedPerformanceMonitor
# 提取的独立模块
from ..gpu.intel_optimizer import IntelGPUOptimizer
from ..gpu.memory_calculator import GPUMemoryCalculator
from ..gpu.optimization_pipeline import PerformanceOptimizationPipeline
from ..gpu.device_manager import GPUDeviceManager
from ..gpu.config_manager import GPUConfigManager
from ..gpu.search_mode_coordinator import SearchModeCoordinator

NEW_GPU_MODULE_AVAILABLE = True
logger.info("使用新的GPU模块: src.gpu.device")

# 尝试导入 pyopencl
try:
    import pyopencl as cl
    import numpy as np
    PYOPENCL_AVAILABLE = True
except ImportError:
    PYOPENCL_AVAILABLE = False


def _seed_bytes_to_u32_be_array(seed: bytes):
    """把 32 字节 seed 按 big-endian 拆成 8×uint32，再转成本机端序。

    GPU 内核 generate_private_key 假设 seed 按 big-endian uint32 排列，
    而 x86 上 np.frombuffer(dtype=np.uint32) 默认按 little-endian 解析。
    需要先按 big-endian 解析再转为本机端序传给 OpenCL。
    """
    if len(seed) != 32:
        raise ValueError(f"seed must be 32 bytes, got {len(seed)}")
    be_u32 = np.frombuffer(seed, dtype='>u4')  # big-endian uint32
    return be_u32.astype(np.uint32)  # 转为本机端序（little-endian on x86）

from ..core.address_generator import P2PKHAddressGenerator
from ..core.hash_utils import HashUtils
from ..core.secp256k1 import Secp256k1
from ..core.base58 import Base58
from ..core.wif import WIF  # P1修复: 提前导入,避免循环内重复导入
from .collision_stats import CollisionStats
from .checkpoint_manager import CheckpointManager
from .deduplication_filter import DeduplicationFilter
from .base_engine import BaseCollisionEngine
from ..monitoring.data_logger import DataLogger
from ..monitoring.enhanced_monitoring import EnhancedMonitoringSystem
from ..monitoring.gpu_performance_monitor import GPUPerformanceMonitor, get_gpu_performance_monitor

# v2.2.1: 预导入GPU监控器,避免重复import
_gpu_performance_monitor = None
def _get_gpu_monitor():
    """获取GPU性能监控器(懒加载)"""
    global _gpu_performance_monitor
    if _gpu_performance_monitor is None:
        _gpu_performance_monitor = get_gpu_performance_monitor()
    return _gpu_performance_monitor


# P1-2修复：GPUDeviceHelper已迁移到src.gpu.device_helper
# from ..gpu.device_helper import GPUDeviceHelper



class GPUCollisionEngine(BaseCollisionEngine):
    """GPU 加速的比特币私钥对撞引擎
    
    继承BaseCollisionEngine，实现GPU碰撞引擎。
    """
    
    # 监控配置
    MONITOR_INTERVAL = 100  # 每 100 个批次检查一次警告和建议
    
    def _apply_intel_specific_optimizations(self):
        """应用 Intel GPU 特定优化和验证
        
        委托给 IntelGPUOptimizer 处理，保持向后兼容。
        """
        if self._intel_optimizer is None:
            self._intel_optimizer = IntelGPUOptimizer(
                device=self._gpu_device,
                config=getattr(self, 'config', {}),
                engine_logger=logger,
            )
        self._intel_optimizer.apply_optimizations({
            'kernel_source': OPENCL_KERNEL_SOURCE,
            'engine': self,
        })
        # 将组件引用同步回引擎属性（保持现有代码兼容）
        self.timeout_manager = self._intel_optimizer.timeout_manager
        self.memory_monitor = self._intel_optimizer.memory_monitor
        self.benchmark_suite = self._intel_optimizer.benchmark_suite
        self.auto_tuner = self._intel_optimizer.auto_tuner
        self.performance_reporter = self._intel_optimizer.performance_reporter
        # 同步到性能优化管道
        self._perf_pipeline.benchmark_suite = self.benchmark_suite
        self._perf_pipeline.auto_tuner = self.auto_tuner
        self._perf_pipeline.performance_reporter = self.performance_reporter
    
    def _init_intel_monitoring_and_tuning(self):
        """初始化 Intel GPU 监控和调优组件（P1/P2）
        
        委托给 IntelGPUOptimizer 处理，保持向后兼容。
        """
        if self._intel_optimizer is None:
            self._intel_optimizer = IntelGPUOptimizer(
                device=self._gpu_device,
                config=getattr(self, 'config', {}),
                engine_logger=logger,
            )
        components = self._intel_optimizer.init_monitoring_and_tuning({
            'engine': self,
        })
        # 将组件引用同步回引擎属性（保持现有代码兼容）
        self.timeout_manager = components['timeout_manager']
        self.memory_monitor = components['memory_monitor']
        self.benchmark_suite = components['benchmark_suite']
        self.auto_tuner = components['auto_tuner']
        self.performance_reporter = components['performance_reporter']
        # 同步到性能优化管道
        self._perf_pipeline.benchmark_suite = self.benchmark_suite
        self._perf_pipeline.auto_tuner = self.auto_tuner
        self._perf_pipeline.performance_reporter = self.performance_reporter
    
    def _verify_uint32_workaround(self):
        """验证 uint32 workaround 是否正确应用
        
        委托给 IntelGPUOptimizer 处理，保持向后兼容。
        
        Returns:
            bool: 验证成功返回 True
        """
        if self._intel_optimizer is None:
            self._intel_optimizer = IntelGPUOptimizer(
                device=self._gpu_device,
                config=getattr(self, 'config', {}),
                engine_logger=logger,
            )
        return self._intel_optimizer._verify_uint32_workaround(OPENCL_KERNEL_SOURCE)
    
    def __init__(self, targets: Set[str],
                 device_index: int = 1,
                 batch_size: int = None,
                 on_progress: Optional[Callable] = None,
                 on_match: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None,
                 checkpoint_enabled: bool = False,
                 dedup_enabled: bool = False,
                 dedup_max_size: int = 1_000_000,
                 checkpoint_interval: int = 30,
                 data_logging_enabled: bool = True,
                 data_logging_interval: int = 5,
                 use_enhanced_monitoring: bool = True,
                 # 性能优化参数 (v2.2.0新增)
                 use_gpu_memory_pool: bool = True,
                 gpu_pool_max_buffers: int = 100,
                 gpu_pool_max_memory_mb: int = 512,
                 # v2.2.1: 异步日志支持
                 use_async_logging: bool = False,
                 async_log_file: str = "logs/gpu_async.log",
                 async_log_max_bytes: int = 10*1024*1024,
                 async_log_backup_count: int = 5,
                 # v4.0: 地址格式支持
                 check_uncompressed: Optional[bool] = None):  # 是否同时检查非压缩格式, None=自动检测
        """
        初始化 GPU 碰撞引擎
        
        Args:
            targets: 目标地址集合
            device_index: GPU 设备索引（默认1选择GPU 1，-1 自动选择）
            batch_size: 每批处理的私钥数量（None=根据GPU显存自动计算）
            on_progress: 进度回调
            on_match: 匹配回调
            on_complete: 完成回调
            checkpoint_enabled: 是否启用断点续传
            dedup_enabled: 是否启用去重过滤
            dedup_max_size: 去重过滤器最大容量
            checkpoint_interval: 断点自动保存间隔(秒)
            data_logging_enabled: 是否启用数据日志记录
            data_logging_interval: 数据日志记录间隔(秒)
            use_enhanced_monitoring: 是否使用增强监控系统（默认True）
            
            # 性能优化参数 (v2.2.0新增)
            use_gpu_memory_pool: 是否使用GPU内存池（默认True）
            gpu_pool_max_buffers: 内存池最大缓冲区数量（默认100）
            gpu_pool_max_memory_mb: 内存池最大内存MB（默认512）
            
            # v2.2.1: 异步日志支持
            use_async_logging: 是否启用异步日志（默认False）
            async_log_file: 异步日志文件路径
            async_log_max_bytes: 单个日志文件最大字节数（默认10MB）
            async_log_backup_count: 日志备份数量（默认5）
            
            # v4.0: 地址格式支持
            check_uncompressed: 是否同时检查非压缩格式地址
                              - True: 强制启用双格式检查
                              - False: 强制禁用, 仅检查压缩格式
                              - None: 自动检测（默认, 根据目标地址数量决定）
        """
        if not PYOPENCL_AVAILABLE:
            raise RuntimeError("pyopencl 不可用，无法使用 GPU 加速")
        
        # 基本属性
        self.targets = targets
        self.device_index = device_index
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete
        self._match_callback_timeout = 5.0  # 回调超时时间（秒）
        self.stats = CollisionStats()
        self._stop_event = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._dynamic_speed_benchmark = 500000  # 默认500K keys/s基准
        self._last_memory_check_time = time.time()  # 上次内存检查时间
        self._memory_check_interval = 60  # 内存检查间隔（秒）
        
        # v4.0: 地址格式支持配置（智能检测）
        if check_uncompressed is None:
            self._check_uncompressed = self._auto_detect_compression_needed_gpu()
            logger.info(f"GPU自动检测地址格式: {'启用双格式检查' if self._check_uncompressed else '仅检查压缩格式'}")
        else:
            self._check_uncompressed = 1 if check_uncompressed else 0
        
        # 控制参数
        self._batch_size = batch_size
        self._batch_size_lock = threading.Lock()  # 线程安全：batch_size保护锁
        
        # 错误处理参数
        self._max_gpu_error_retries = 100  # 最大连续错误次数
        self._consecutive_gpu_errors = 0  # 当前连续错误计数
        
        # 断点管理器
        self.checkpoint_mgr = CheckpointManager(auto_save_interval=checkpoint_interval) if checkpoint_enabled else None
        # 去重过滤器
        self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size, enabled=dedup_enabled)
        
        # 监控系统
        self.data_logging_enabled = data_logging_enabled
        self.data_logging_interval = data_logging_interval
        self.data_logger = None
        self.enhanced_monitoring = None
        
        # 异步日志支持
        self._async_log_handler = None
        if use_async_logging and ASYNC_LOG_AVAILABLE:
            self._setup_async_logging(async_log_file, async_log_max_bytes, async_log_backup_count)
        elif use_async_logging and not ASYNC_LOG_AVAILABLE:
            logger.warning("异步日志不可用（AsyncFileHandler导入失败），使用同步日志")
        
        # 初始化监控器
        self._engine_monitor = GPUEngineMonitor(engine=self)
        
        # 构建配置字典
        config = {
            'gpu': {
                'use_memory_pool': use_gpu_memory_pool,
                'pool_max_buffers': gpu_pool_max_buffers,
                'pool_max_memory_mb': gpu_pool_max_memory_mb
            }
        }
        
        # 初始化设备管理器
        self._device_manager = GPUDeviceManager(
            device_index=device_index,
            config=config,
            logger=logger
        )
        
        # 初始化GPU设备
        self._device_manager.initialize(targets, batch_size,
                                         check_uncompressed=self._check_uncompressed)
        
        # 获取设备实例（保持向后兼容）
        self._gpu_device = self._device_manager.device
        self._gpu_context = self._device_manager.context
        self._gpu_kernel = self._device_manager.kernel
        self._async_executor = self._device_manager.async_executor
        self._gpu_memory_pool = self._device_manager.memory_pool
        
        # 初始化搜索模式协调器
        self._search_coordinator = SearchModeCoordinator(self, logger)
        
        # 初始化监控系统
        if data_logging_enabled:
            try:
                if use_enhanced_monitoring:
                    self.enhanced_monitoring = EnhancedMonitoringSystem(
                        engine=self,
                        collection_interval=data_logging_interval,
                        enable_monitoring_data=False
                    )
                    self.data_logger = self.enhanced_monitoring.data_logger
                    logger.info("GPU引擎：增强监控系统已启用")
                else:
                    self.data_logger = DataLogger()
                    logger.info("GPU引擎：数据日志系统已启用（传统模式）")
            except Exception as e:
                logger.warning(f"GPU引擎：监控系统初始化失败: {e}")
                self.data_logging_enabled = False
        
        # 初始化其他属性（保持向后兼容）
        self._current_position = 0
        self._current_mode = ""
        self._range_start = None
        self._range_end = None
        self._last_progress_time = 0
        self._progress_interval_sec = 0.5
        
        # GPU性能监控器（v2.2.1新增）
        self.gpu_performance_monitor = None
        
        # 自适应批处理配置（v4.0新增）
        self._adaptive_batch_enabled = True
        self._adaptive_error_count = 0
        self._adaptive_batch_size = self._batch_size
        self._max_batch_size = min(self._batch_size * 2, GPU_MAX_BATCH_SIZE - 1) if self._batch_size else 2097152
        self._min_batch_size = self._batch_size // 4 if self._batch_size else 262144
        self._last_batch_adjust_time = time.time()
        self._batch_adjust_interval = 10.0  # 批次调整间隔（秒）
        
        # 计算动态性能基准
        self._calculate_dynamic_benchmark()
    
    @property
    def batch_size(self) -> int:
        """线程安全的batch_size读取
        
        Returns:
            当前批次大小
        """
        with self._batch_size_lock:
            return self._batch_size
    
    @batch_size.setter
    def batch_size(self, value: int):
        """线程安全的batch_size写入
        
        P1-2: batch_size >= UINT32_MAX 会导致 GPU 内核 gid 溢出
        
        Args:
            value: 新的批次大小
            
        Raises:
            ValueError: 如果 batch_size >= UINT32_MAX (2^32)
        """
        if value >= GPU_MAX_BATCH_SIZE:
            raise ValueError(
                f"P1-2: batch_size ({value:,}) >= UINT32_MAX ({GPU_MAX_BATCH_SIZE:,}) "
                f"会导致 GPU 内核 gid 溢出"
            )
        with self._batch_size_lock:
            self._batch_size = value
    
    def _merge_gpu_configs(self, auto_config: Dict, profile_config: Optional[Dict]) -> Dict:
        """合并AutoConfig和ProfileLoader的配置
        
        CODE-1修复: 优先使用GPUConfigManager，否则使用原有逻辑（向后兼容）
        
        优先级: ProfileLoader > AutoConfig
        
        Args:
            auto_config: GPUAutoConfigurator生成的配置
            profile_config: GPUProfileLoader加载的配置（可能为None）
            
        Returns:
            合并后的配置
        """
        # CODE-1修复: 使用GPUConfigManager（如果可用）
        if GPU_CONFIG_MANAGER_AVAILABLE and GPUConfigManager is not None:
            try:
                config_manager = GPUConfigManager()
                return config_manager.merge_gpu_configs(auto_config, profile_config)
            except Exception as e:
                logger.warning(f"GPUConfigManager合并失败，使用原有逻辑: {e}")
        
        # 原有逻辑（向后兼容）
        merged = auto_config.copy()
        
        if profile_config:
            # ProfileLoader的配置覆盖AutoConfig
            for key in ['batch_size', 'work_group_size', 'memory_usage_ratio',
                        'enable_async', 'use_uint32_workaround']:
                if key in profile_config:
                    value = profile_config[key]
                    # 验证值的有效性
                    if self._validate_config_value(key, value):
                        merged[key] = value
                        logger.debug(f"配置覆盖: {key} = {value}")
                    else:
                        logger.warning(f"配置值无效: {key}={value}，使用默认值")
        
        # 验证合并后的配置
        self._validate_merged_config(merged)
        
        # v3.3.0修复: 安全的日志格式化（保留千位分隔符和百分比）
        batch_size_val = merged.get('batch_size', 'N/A')
        batch_size_str = f"{batch_size_val:,}" if isinstance(batch_size_val, (int, float)) else batch_size_val
        
        mem_ratio_val = merged.get('memory_usage_ratio', 'N/A')
        mem_ratio_str = f"{mem_ratio_val:.0%}" if isinstance(mem_ratio_val, (int, float)) else mem_ratio_val
        
        logger.info(
            f"GPU配置合并完成: "
            f"batch_size={batch_size_str}, "
            f"work_group={merged.get('work_group_size', 'N/A')}, "
            f"mem_ratio={mem_ratio_str}"
        )
        return merged
    
    def _validate_config_value(self, key: str, value: Any) -> bool:
        """验证配置值的有效性
        
        Args:
            key: 配置项名称
            value: 配置值
            
        Returns:
            是否有效
        """
        if key == 'batch_size':
            return isinstance(value, int) and 1024 <= value < GPU_MAX_BATCH_SIZE
        elif key == 'work_group_size':
            return isinstance(value, int) and 64 <= value <= 1024
        elif key == 'memory_usage_ratio':
            return isinstance(value, (int, float)) and 0.1 <= value <= 0.9
        elif key in ['enable_async', 'use_uint32_workaround']:
            return isinstance(value, bool)
        return True
    
    def _validate_merged_config(self, config: Dict):
        """验证合并后的配置
        
        Args:
            config: 合并后的配置字典
        """
        if 'batch_size' in config:
            batch_size = config['batch_size']
            if batch_size < 1024:
                logger.warning(f"batch_size过小({batch_size})，可能导致性能差")
            elif batch_size > 16777216:
                logger.warning(f"batch_size过大({batch_size})，可能导致显存不足")
        
        if 'memory_usage_ratio' in config:
            ratio = config['memory_usage_ratio']
            if ratio > 0.85:
                logger.warning(f"显存使用率过高({ratio:.0%})，可能导致不稳定")
            elif ratio < 0.3:
                logger.warning(f"显存使用率过低({ratio:.0%})，性能可能不佳")
    
    def _resize_gpu_buffers(self, new_batch_size: int):
        """动态调整GPU缓冲区大小
        
        Args:
            new_batch_size: 新的批次大小
        """
        try:
            old_batch_size = self.batch_size
            logger.info(f"正在调整GPU缓冲区大小: {old_batch_size:,} -> {new_batch_size:,}")
            
            # 1. 释放旧缓冲区
            if self._gpu_kernel:
                # 优先使用GPUKernel的release_buffers方法（推荐）
                if hasattr(self._gpu_kernel, 'release_buffers'):
                    self._gpu_kernel.release_buffers()
                    logger.debug("使用release_buffers方法释放所有缓冲区")
                else:
                    logger.warning("GPUKernel没有release_buffers方法，尝试手动释放")
                    # 手动释放已知缓冲区
                    released_count = 0
                    failed_count = 0
                    
                    # 标准缓冲区（_keys_buf 已于 v4.0 移除）
                    for attr in ['_match_buf', '_targets_buf']:
                        buf = getattr(self._gpu_kernel, attr, None)
                        if buf is not None:
                            if hasattr(buf, 'release'):
                                try:
                                    buf.release()
                                    setattr(self._gpu_kernel, attr, None)
                                    released_count += 1
                                    logger.debug(f"释放缓冲区: {attr}")
                                except Exception as e:
                                    failed_count += 1
                                    logger.error(f"释放缓冲区失败 {attr}: {e}")
                            else:
                                logger.debug(f"缓冲区无release方法: {attr}")
                    
                    # 尝试释放其他可能的缓冲区（带_的缓冲区属性）
                    for attr_name in dir(self._gpu_kernel):
                        if attr_name.startswith('_') and 'buf' in attr_name.lower():
                            if attr_name not in ['_match_buf', '_targets_buf']:
                                buf = getattr(self._gpu_kernel, attr_name, None)
                                if buf is not None and hasattr(buf, 'release'):
                                    try:
                                        buf.release()
                                        setattr(self._gpu_kernel, attr_name, None)
                                        released_count += 1
                                        logger.debug(f"释放额外缓冲区: {attr_name}")
                                    except Exception as e:
                                        failed_count += 1
                                        logger.debug(f"释放额外缓冲区失败 {attr_name}: {e}")
                    
                    logger.info(f"手动释放完成: 成功{released_count}个, 失败{failed_count}个")
            
            # 2. 更新kernel的max_batch_size
            if self._gpu_kernel:
                self._gpu_kernel._max_batch_size = new_batch_size
            
            # 3. 重新分配缓冲区
            if self._gpu_kernel:
                if hasattr(self._gpu_kernel, '_allocate_buffers'):
                    self._gpu_kernel._allocate_buffers()
                    logger.debug("缓冲区重新分配完成")
            
            logger.info(f"GPU缓冲区调整完成: {new_batch_size:,}")
            
            # 4. 记录调整历史
            self._record_adjustment(old_batch_size, new_batch_size, "buffer_resize")
            
        except Exception as e:
            logger.error(f"GPU缓冲区调整失败: {e}")
            # 失败时保持原有batch_size
            if self._gpu_kernel:
                self.batch_size = self._gpu_kernel._max_batch_size
    
    def _record_adjustment(self, old_size: int, new_size: int, reason: str, details: str = ""):
        """记录调整历史 - 委托给 GPUEngineMonitor.record_adjustment()
        
        Args:
            old_size: 调整前的大小
            new_size: 调整后的大小
            reason: 调整原因
            details: 详细信息
        """
        self._engine_monitor.record_adjustment(
            old_size=old_size,
            new_size=new_size,
            reason=reason,
            details=details,
        )
    
    def get_adjustment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取调整历史 - 委托给 GPUEngineMonitor.get_adjustment_history()
        
        Args:
            limit: 返回的记录数量限制
            
        Returns:
            调整历史记录列表（最新的在前）
        """
        return self._engine_monitor.get_adjustment_history(limit=limit)
    
    def _auto_detect_compression_needed_gpu(self) -> int:
        """GPU路径智能检测是否需要检查非压缩格式地址
        
        与CPU路径策略一致：
        - 目标地址数量较少时（< 1000），启用双格式检查（返回1）
        - 目标地址数量较多时（>= 1000），仅检查压缩格式（返回0）
        
        返回:
            int: 0=仅压缩格式, 1=双格式检查
        """
        target_count = len(self.targets)
        
        if target_count < 1000:
            logger.debug(f"GPU: 目标地址数={target_count} < 1000，启用双格式检查")
            return 1
        else:
            logger.debug(f"GPU: 目标地址数={target_count} >= 1000，仅检查压缩格式（性能优先）")
            return 0
    

    def _prepare_targets(self):
        """将目标地址转换为 Hash160"""
        self._target_list = []
        hash160_list = []
        
        for address in sorted(self.targets):
            try:
                version, payload = Base58.check_decode(address)
                if version == 0x00 and len(payload) == 20:
                    self._target_list.append(address)
                    hash160_list.append(payload)
            except (ValueError, TypeError) as e:
                # 地址格式错误，跳过
                logger.debug(f"目标地址格式无效 [{address}]: {type(e).__name__}")
                continue
            except Exception as e:
                # 未知错误：记录日志
                logger.warning(f"目标地址解析失败 [{address}]: {type(e).__name__}")
                continue
        
        if not hash160_list:
            raise ValueError("没有有效的目标地址")
        
        self._target_hash160s = b''.join(hash160_list)
    
    def _calculate_gpu_memory_usage(self, num_keys: int) -> float:
        """
        计算GPU显存使用(MB)
            
        委托给 GPUMemoryCalculator.calculate_from_hash160_bytes 处理。
        保持向后兼容。
            
        Args:
            num_keys: 私鑰数量
                
        Returns:
            显存使用量(MB)
        """
        return GPUMemoryCalculator.calculate_from_hash160_bytes(
            num_keys=num_keys,
            hash160_bytes=self._target_hash160s,
        )
    
    def _calculate_dynamic_benchmark(self):
        """
        计算动态性能基准值
        
        通过运行简短的性能测试，获取实际GPU性能数据，
        并设置动态基准值，用于性能警告阈值计算。
        """
        import time
        
        # 运行简短的性能测试
        test_batch_size = 100000
        seed = os.urandom(32)
        
        try:
            start_time = time.time()
            # 运行测试批次
            self._gpu_kernel.run_batch(seed, test_batch_size)
            execution_time = time.time() - start_time
            
            # 计算实际性能
            actual_speed = test_batch_size / execution_time
            # 使用实际性能的80%作为基准
            self._dynamic_speed_benchmark = actual_speed * 0.8
            
            logger.info(f"动态性能基准计算完成: {self._dynamic_speed_benchmark:.0f} keys/s")
        except Exception as e:
            logger.warning(f"动态性能基准计算失败，使用默认值: {e}")
            # 保持默认值
            pass
    
    def _check_memory_leaks(self):
        """
        定期检查内存泄漏
        
        检查缓冲区追踪器中的未释放缓冲区，
        及时发现和处理内存泄漏问题。
        """
        current_time = time.time()
        if current_time - self._last_memory_check_time >= self._memory_check_interval:
            self._last_memory_check_time = current_time
            
            if hasattr(self._gpu_kernel, '_buffer_tracker') and self._gpu_kernel._buffer_tracker:
                try:
                    # 获取当前缓冲区状态
                    stats = self._gpu_kernel._buffer_tracker.get_stats()
                    logger.debug(f"内存检查: {stats['count']}个缓冲区, {stats['total_size_mb']:.2f} MB")
                    
                    # 只检查状态，不释放缓冲区
                    # 注意：force_check_on_shutdown() 会释放所有缓冲区，在运行时不应调用
                except Exception as e:
                    logger.error(f"内存泄漏检查失败: {e}")
    
    @staticmethod
    def is_gpu_available() -> bool:
        """检查 GPU 是否可用
        
        委托给GPUDeviceDetector进行实际检测，避免代码重复。
        
        Returns:
            bool: GPU可用返回True，否则返回False
        """
        return GPUDeviceDetector.is_gpu_available()
    
    def start(self, mode: str = "random", resume: bool = False, **kwargs):
        """启动对撞"""
        if self._running:
            return
        
        # P0-4修复: 重置错误计数器（引擎重启时清空历史状态）
        with self._batch_size_lock:
            self._consecutive_gpu_errors = 0
        
        self._stop_event.clear()
        self._running = True
        self.stats.start_time = time.time()
        
        # 委托给搜索模式协调器
        self._search_coordinator.start(mode, resume=resume, **kwargs)
    
    def _random_search(self):
        """随机碰撞模式 - 委托给 RandomSearchMode"""
        return self._random_search_mode.execute()
    
    def _start_range_scan(self):
        """启动范围扫描（命名函数替代lambda）
        
        这个函数是为了替代lambda: self._range_scan(self._range_start, self._range_end)
        使用命名函数可以提高代码可读性和调试友好性。
        """
        return self._range_scan(self._range_start, self._range_end)
    
    def _start_brute_force(self):
        """启动暴力穷举（命名函数替代lambda）
        
        这个函数是为了替代lambda: self._brute_force(self._range_start)
        使用命名函数可以提高代码可读性和调试友好性。
        """
        return self._brute_force(self._range_start)
    
    def _random_search_sync(self):
        """同步执行版本 - 委托给 RandomSearchMode._execute_sync()"""
        return self._random_search_mode._execute_sync()
    
    def _random_search_async(self):
        """异步执行版本(双缓冲优化) - 委托给 RandomSearchMode._execute_async()"""
        # 尝试使用异步模式，如果失败会自动回退到同步模式
        return self._random_search_mode._execute_async()
    
    # ========== P0-1重构：辅助方法 ==========
    
    def _calculate_key_gen_timeout(self, batch_size: int) -> float:
        """ALG-1修复: 委托给 RandomSearchMode._calculate_key_gen_timeout()"""
        return self._random_search_mode._calculate_key_gen_timeout(batch_size)
    
    def _start_async_key_generation(self, batch_size: int) -> Tuple[threading.Thread, List[Any]]:
        """启动异步私钥生成线程 - 委托给 RandomSearchMode._start_async_key_generation()"""
        return self._random_search_mode._start_async_key_generation(batch_size)
    
    def _wait_for_async_key_generation(
        self,
        gen_thread: threading.Thread,
        gen_result: List[Any],
        batch_num: int
    ) -> bytes:
        """等待异步私钥生成完成 - 委托给 RandomSearchMode._wait_for_async_key_generation()"""
        return self._random_search_mode._wait_for_async_key_generation(gen_thread, gen_result, batch_num)
    
    def _execute_gpu_batch(
        self,
        seed: bytes,
        batch_size: int,
        batch_num: int
    ) -> Tuple[List[Dict[str, int]], float]:
        """PERF-1修复: 执行GPU batch计算（带性能优化建议）

        PRNG模式: seed 为32字节随机种子, GPU内核自行计算 key = seed + gid。

        Args:
            seed: 32字节随机种子
            batch_size: 批次大小
            batch_num: 批次号

        Returns:
            (matches, execution_time_ms) 元组
        """
        if batch_num <= INITIAL_BATCHES_LOG or batch_num % BATCH_LOG_FREQUENCY == 0:
            logger.debug(
                f"GPU batch {batch_num}: 运行 run_batch (size={batch_size})..."
            )

        batch_start_time = time.time()
        
        # 检查是否有异步执行器可用
        if hasattr(self, '_async_executor') and self._async_executor is not None:
            try:
                # 使用异步执行
                matches: List[Dict[str, int]] = []
                if hasattr(self, '_gpu_kernel') and self._gpu_kernel is not None:
                    if hasattr(self._gpu_kernel, 'program') and hasattr(self._gpu_kernel, '_targets_buf'):
                        matches, execution_time_ms = self._async_executor.run_batch_async(
                            seed, batch_size, self._gpu_kernel.program,
                            self._gpu_kernel._targets_buf, len(self.targets)
                        )
                        logger.debug(f"GPU batch {batch_num}: 使用异步执行")
                    else:
                        # 回退到同步执行
                        matches = self._gpu_kernel.run_batch(
                            seed, batch_size, stop_event=self._stop_event
                        )
                        execution_time_ms = (time.time() - batch_start_time) * 1000
                else:
                    # 回退到同步执行
                    matches = self._gpu_kernel.run_batch(
                        seed, batch_size, stop_event=self._stop_event
                    )
                    execution_time_ms = (time.time() - batch_start_time) * 1000
            except Exception as e:
                logger.warning(f"异步执行失败，回退到同步模式: {e}")
                # 回退到同步执行
                matches = self._gpu_kernel.run_batch(
                    seed, batch_size, stop_event=self._stop_event
                )
                execution_time_ms = (time.time() - batch_start_time) * 1000
        else:
            # 同步执行
            matches = self._gpu_kernel.run_batch(
                seed, batch_size, stop_event=self._stop_event
            )
            execution_time_ms = (time.time() - batch_start_time) * 1000
        
        # PERF-1修复: 检测CPU-GPU同步瓶颈（动态阈值）
        # 基于批次大小和预期速度计算合理阈值
        # 动态基准值：使用历史性能数据或默认值
        expected_speed = getattr(self, '_dynamic_speed_benchmark', 500000)  # 默认500K keys/s基准
        expected_time_ms = (batch_size / expected_speed) * 1000
        threshold_ms = expected_time_ms * 1.5  # 1.5倍容差
        
        if execution_time_ms > threshold_ms:
            logger.warning(
                f"PERF-1警告: GPU batch {batch_num} 执行时间过长 "
                f"({execution_time_ms:.0f}ms > {threshold_ms:.0f}ms)\n"
                f"  可能原因: CPU-GPU同步等待、PCIe带宽瓶颈、GPU计算负载高\n"
                f"  建议: 启用异步执行模式(双缓冲)可提升30-50%吞吐量"
            )
        
        # 定期检查内存泄漏
        self._check_memory_leaks()
        
        if batch_num <= INITIAL_BATCHES_LOG or batch_num % BATCH_LOG_FREQUENCY == 0:
            logger.debug(f"GPU batch {batch_num}: 发现 {len(matches)} 个匹配")
        
        return matches, execution_time_ms
    
    def _safe_invoke_match_callback(self, private_key: bytes, address: str, wif: str) -> bool:
        """安全调用匹配回调函数，提供超时控制与异常隔离。

        Returns:
            bool: 回调是否成功执行
        """
        if not self.on_match:
            return True

        try:
            if os.name == 'nt':
                result = [None]
                exception = [None]

                def target():
                    try:
                        result[0] = self.on_match(private_key, address, wif)
                    except Exception as e:
                        exception[0] = e

                callback_thread = threading.Thread(target=target, daemon=True)
                callback_thread.start()
                callback_thread.join(timeout=self._match_callback_timeout)

                if callback_thread.is_alive():
                    logger.critical(
                        f"匹配回调执行超时 ({self._match_callback_timeout}秒)，强制跳过: "
                        f"address={address}"
                    )
                    return False

                if exception[0]:
                    logger.error(f"匹配回调异常: {exception[0]}")
                    return False
            else:
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"匹配回调执行超时 ({self._match_callback_timeout}秒)")

                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(self._match_callback_timeout))
                try:
                    self.on_match(private_key, address, wif)
                except TimeoutError as e:
                    logger.critical(str(e))
                    return False
                except Exception as e:
                    logger.error(f"匹配回调异常: {e}")
                    return False
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

            return True

        except Exception as e:
            logger.error(f"匹配回调调用失败: {e}")
            return False

    def _process_gpu_matches(self, private_keys: bytes, matches: List[Dict[str, int]]) -> None:
        """处理GPU匹配结果
        
        Args:
            private_keys: 私钥字节串
            matches: 匹配结果列表
        """
        for match in matches:
            key_idx = match["key_index"]
            private_key = private_keys[key_idx*32:(key_idx+1)*32]
            
            if not self.dedup_filter.check_and_add(private_key):
                continue
            
            target_idx = match["target_index"]
            address = self._target_list[target_idx]
            
            # P1修复: 使用顶部导入的WIF,避免循环内重复导入
            wif = WIF.encode(private_key, compressed=True)
            
            self.stats.add_match(private_key, address)
            if not self._safe_invoke_match_callback(private_key, address, wif):
                logger.warning(f"GPU匹配回调处理失败，跳过地址: {address}")
    
    def _process_gpu_matches_prng(self, seed: bytes, matches: List[Dict[str, int]]) -> None:
        """处理GPU匹配结果 (PRNG模式)

        PRNG模式下私钥通过 seed + key_index 重建，而非从预分配数组中切片。

        Args:
            seed: 32字节种子
            matches: 匹配结果列表 [{"key_index": int, "target_index": int}, ...]
        """
        seed_int = int.from_bytes(seed, 'big')
        for match in matches:
            key_idx = match["key_index"]
            key_int = (seed_int + key_idx) % (2 ** 256)
            private_key = key_int.to_bytes(32, 'big')

            if not self.dedup_filter.check_and_add(private_key):
                continue

            target_idx = match["target_index"]
            address = self._target_list[target_idx]
            wif = WIF.encode(private_key, compressed=True)

            self.stats.add_match(private_key, address)
            if not self._safe_invoke_match_callback(private_key, address, wif):
                logger.warning(f"GPU匹配回调处理失败，跳过地址: {address}")

    def _update_performance_metrics(
        self,
        batch_size: int,
        execution_time_ms: float
    ) -> None:
        """记录GPU性能指标
        
        Args:
            batch_size: 批次大小
            execution_time_ms: 执行时间（毫秒）
        """
        if not self.gpu_performance_monitor:
            return
        
        try:
            memory_mb = self._calculate_gpu_memory_usage(batch_size)
            self.gpu_performance_monitor.record_kernel_metrics(
                batch_size=batch_size,
                execution_time_ms=execution_time_ms,
                memory_allocated_mb=memory_mb
            )
        except Exception as e:
            logger.debug(f"记录GPU性能指标失败: {e}")
    
    def _maybe_adjust_batch_size(self) -> None:
        """根据运行时状态自适应调整 batch_size (v4.0新增)
        
        每隔 _batch_adjust_interval 秒评估一次：
        - 错误率 > _error_rate_threshold: 不断减batch_size，直到最小限制
        - GPU利用率 < 50%: 适当增大batch_size，最大至上限
        - 其他情况不调整
        """
        if not self._adaptive_batch_enabled:
            return
        
        current_time = time.monotonic()
        if current_time - self._last_batch_adjust_time < self._batch_adjust_interval:
            return  # 未到评估时间
        
        self._last_batch_adjust_time = current_time
        
        # 获取当前统计快照
        stats = self.get_stats()
        if stats is None:
            return
        
        total_checked = getattr(stats, 'total_checked', 0)
        gpu_errors = getattr(stats, 'gpu_errors', 0)
        
        # 计算错误率
        error_rate = gpu_errors / max(total_checked, 1)
        
        old_batch_size = self.batch_size
        
        if error_rate > self._error_rate_threshold:
            # 错误率过高：减batch_size以降低负荷
            new_size = max(self._min_batch_size, old_batch_size // 2)
            if new_size != old_batch_size:
                self.batch_size = new_size
                self._adaptive_error_count = 0
                logger.warning(
                    f"自适应调整: 错误率过高({error_rate:.2%})，"
                    f"降低batch_size: {old_batch_size:,} -> {new_size:,}"
                )
        else:
            # 检查GPU利用率（如果监控系统提供）
            gpu_utilization = None
            if hasattr(self, 'gpu_performance_monitor') and self.gpu_performance_monitor:
                try:
                    perf_stats = self.gpu_performance_monitor.get_stats()
                    gpu_utilization = perf_stats.get('avg_gpu_utilization')
                except Exception:
                    pass
            
            if gpu_utilization is not None and gpu_utilization < 0.5:
                # GPU利用率低：增大batch_size以提升吞吐量
                new_size = min(self._max_batch_size, int(old_batch_size * 1.5))
                if new_size != old_batch_size:
                    self.batch_size = new_size
                    logger.info(
                        f"自适应调整: GPU利用率低({gpu_utilization:.0%})，"
                        f"增大batch_size: {old_batch_size:,} -> {new_size:,}"
                    )
    
    def _check_and_report_progress(
        self,
        batch_count: int,
        current_batch_size: int
    ) -> None:
        """检查并报告进度
        
        Args:
            batch_count: 已处理的总批次数量
            current_batch_size: 当前批次大小
        """
        current_time = time.time()
        if current_time - self._last_progress_time < self._progress_interval_sec:
            return
        
        # 触发进度回调
        logger.debug(f"GPU 进度回调: batch_count={batch_count}")
        if self.on_progress:
            self.on_progress(self.stats.snapshot())  # P1-2修复: 使用线程安全快照
        self._save_checkpoint(batch_count)
        self._last_progress_time = current_time
        
        # 成功执行,重置连续错误计数（添加锁保护）
        with self._batch_size_lock:
            self._consecutive_gpu_errors = 0
                        
        # 自适应性能优化
        if not hasattr(self, '_gpu_kernel') or not self._gpu_kernel:
            return
        
        try:
            error_rate = self.stats.gpu_error_count / max(batch_count, 1)
            
            new_batch_size, adjustments = self._gpu_kernel.gpu_optimizer.analyze_and_adjust(
                current_batch_size=current_batch_size,
                error_rate=error_rate,
                engine=self,
            )
            
            if new_batch_size != current_batch_size and adjustments:
                reason = list(adjustments.keys())[0]
                logger.info(
                    f"自适应优化: batch_size {current_batch_size} -> {new_batch_size} "
                    f"({reason})"
                )
                current_batch_size = new_batch_size
                self.batch_size = new_batch_size
                
        except Exception as adjust_error:
            logger.debug(f"自适应调整失败: {adjust_error}")
        
        # v4.0: 运行时自适应批大小调整
        self._maybe_adjust_batch_size()
    
    def _range_scan(self, start: int, end: int):
        """范围扫描模式 - 委托给 RangeScanSearchMode.execute()"""
        return self._range_scan_mode.execute(start, end)
    
    def _execute_batch_loop(
        self,
        key_generator_fn: Callable[[], Tuple[bytes, int]],
        mode_name: str,
        stop_condition_fn: Optional[Callable[[], bool]] = None,
    ) -> int:
        """通用批处理执行循环 - 委托给 BaseSearchMode._execute_batch_loop()"""
        # 临时创建一个基础搜索模式实例执行循环
        # 如果直接使用 _brute_force_mode 或 _range_scan_mode 执行循环，則使用 brute_force_mode
        return self._brute_force_mode._execute_batch_loop(
            key_generator_fn=key_generator_fn,
            mode_name=mode_name,
            stop_condition_fn=stop_condition_fn,
        )

    def _brute_force(self, start: int):
        """暴力穷举模式 - 委托给 BruteForceSearchMode.execute()"""
        return self._brute_force_mode.execute(start)
    
    def _save_checkpoint(self, count: int):
        """保存断点"""
        if self.checkpoint_mgr and self.checkpoint_mgr.should_auto_save():
            matches_list = [
                {"private_key": m["private_key_hex"], "address": m["address"]}
                for m in self.stats.matches
            ]
            self.checkpoint_mgr.save(
                mode=self._current_mode,
                targets=self.targets,
                current_position=self._current_position,
                total_checked=count,
                matches=matches_list,
                range_start=self._range_start,
                range_end=self._range_end
            )
    
    def stop(self, timeout: Optional[float] = None):
        """停止对撞
        
        Args:
            timeout: 等待停止的超时时间(秒)，None表示使用默认值
        """
        # 停止搜索模式
        self._search_coordinator.stop()
        
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout or 5)
        
        # 保存最终断点
        if self.checkpoint_mgr:
            try:
                matches_list = [
                    {"private_key": m["private_key_hex"], "address": m["address"]}
                    for m in self.stats.matches
                ]
                self.checkpoint_mgr.save(
                    mode=self._current_mode,
                    targets=self.targets,
                    current_position=self._current_position,
                    total_checked=self.stats.total_checked,
                    matches=matches_list,
                    range_start=self._range_start,
                    range_end=self._range_end
                )
            except Exception as e:
                logger.error(f"保存最终断点失败: {e}")
                # 继续执行后续清理步骤，不因为断点保存失败而中断
        
        # 停止监控系统
        if self.enhanced_monitoring:
            try:
                self.enhanced_monitoring.stop()
                logger.info("GPU引擎：增强监控系统已停止")
            except Exception as e:
                logger.error(f"GPU引擎：停止监控系统失败: {e}")
        
        # v2.2.1: 停止GPU性能监控器
        if hasattr(self, 'gpu_performance_monitor') and self.gpu_performance_monitor:
            try:
                self.gpu_performance_monitor.stop()
                logger.info("GPU引擎：GPU性能监控器已停止")
            except Exception as e:
                logger.error(f"GPU引擎：停止GPU性能监控器失败: {e}")
        
        # 清理去重过滤器（释放内存）
        if self.dedup_filter and self.dedup_filter.enabled:
            stats = self.dedup_filter.get_stats()
            logger.info(f"GPU引擎：清理去重过滤器: 检查={stats['checks_total']}, "
                       f"重复={stats['duplicates_found']}, 跟踪={stats['tracked_total']}")
            self.dedup_filter.reset()
            logger.info("GPU引擎：去重过滤器已清理")
        
        # 刷写数据日志缓冲
        if hasattr(self, 'data_logger') and self.data_logger:
            try:
                self.data_logger.flush()
                logger.info("GPU引擎：数据日志缓冲已刷写")
            except Exception as e:
                logger.error(f"GPU引擎：刷写数据日志失败: {e}")
        
        import time
        
        # 停止缓冲区定期泄漏检查
        if hasattr(self, '_buffer_tracker') and self._buffer_tracker:
            try:
                self._buffer_tracker.stop_periodic_check()
                logger.debug("GPU引擎：缓冲区定期泄漏检查已停止")
            except Exception as e:
                logger.warning(f"GPU引擎：停止缓冲区定期检查失败: {e}")
        
        # 停止种子预生成线程（BUG-1: 防止线程泄漏）
        if hasattr(self, '_random_search_mode') and self._random_search_mode:
            try:
                start_time = time.time()
                self._random_search_mode.stop()
                elapsed = time.time() - start_time
                logger.info(f"GPU引擎：种子预生成线程已停止 (耗时: {elapsed:.2f}秒)")
            except Exception as e:
                logger.warning(f"GPU引擎：停止种子预生成线程失败: {e}")

        # 清理异步执行器资源（BUG-2: 防止 buffer_pool 中的 OpenCL Buffer 泄漏）
        if hasattr(self, '_async_executor') and self._async_executor:
            try:
                start_time = time.time()
                self._async_executor.cleanup()
                elapsed = time.time() - start_time
                logger.info(f"GPU引擎：异步执行器资源已清理 (耗时: {elapsed:.2f}秒)")
            except Exception as e:
                logger.error(f"GPU引擎：清理异步执行器失败: {e}")
            self._async_executor = None

        # 清理设备管理器资源
        if hasattr(self, '_device_manager') and self._device_manager:
            try:
                start_time = time.time()
                self._device_manager.cleanup()
                elapsed = time.time() - start_time
                logger.info(f"GPU引擎：设备管理器资源已清理 (耗时: {elapsed:.2f}秒)")
            except Exception as e:
                logger.error(f"GPU引擎：清理设备管理器失败: {e}")
        
        # 重置引擎状态（支持重启）
        self._stop_event.clear()
        self._running = False
        self._thread = None
        
        logger.info("GPU引擎：资源清理完成")
    
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running and self._thread and self._thread.is_alive()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器，释放资源"""
        self.stop()
        return False  # 不抑制异常
    
    def __del__(self):
        """析构函数，确保资源释放"""
        try:
            if self._running:
                self.stop()
        except Exception:
            pass

    def get_device_info(self) -> Dict[str, Any]:
        """获取GPU设备信息
        
        Returns:
            设备信息字典
        """
        if self._gpu_device:
            return {
                "type": "GPU",
                "name": getattr(self._gpu_device, 'name', 'Unknown'),
                "vendor": getattr(self._gpu_device, 'vendor', 'Unknown'),
                "device_index": self.device_index,
                "batch_size": self.batch_size
            }
        return {"type": "GPU", "status": "not_initialized"}
    
    def get_stats(self) -> CollisionStats:
        """获取统计信息"""
        return self.stats
    
    # ==================== P2 便捷方法 ====================
    
    def run_benchmark(self, iterations: int = 5, save_report: bool = True) -> Dict[str, Any]:
        """运行性能基准测试（P2）
        
        Args:
            iterations: 迭代次数
            save_report: 是否保存报告
        
        Returns:
            基准测试结果
        """
        # 委托给性能优化管道
        results = self._perf_pipeline.run_benchmark(iterations)
        
        # 保存报告（婉包装，保持向后兼容）
        if save_report and results:
            report_path = self.generate_performance_report(
                include_benchmarks=True,
                include_tuning=False,
                include_recommendations=True
            )
            logger.info(f"基准测试报告已保存: {report_path}")
        
        return results
    
    def start_auto_tuning(
        self, 
        max_iterations: int = 30, 
        save_report: bool = True,
        auto_apply: bool = False
    ) -> Dict[str, Any]:
        """启动自动调优（P2）
        
        Args:
            max_iterations: 最大迭代次数（建议 30-100）
            save_report: 是否保存报告
            auto_apply: 是否自动应用最优配置（默认 False，需要用户手动确认）
        
        Returns:
            调优结果
        """
        # 参数验证
        if max_iterations <= 0:
            raise ValueError(f"max_iterations 必须大于 0，当前值: {max_iterations}")
        if max_iterations > 1000:
            logger.warning(
                f"max_iterations={max_iterations} 过大，可能导致调优时间过长，"
                f"建议设置为 30-100"
            )
        
        # 调优回调：更新 batch_size（仅在 auto_apply=True 时）
        original_batch_size = self.batch_size
        logger.info(f"当前 batch_size: {original_batch_size:,}")
        
        def on_new_batch_size(new_size):
            if auto_apply:
                old_size = self.batch_size
                self.batch_size = new_size
                logger.info(f"自动更新 batch_size: {old_size:,} -> {new_size:,}")
            else:
                logger.info(f"建议 batch_size: {new_size:,} (当前: {self.batch_size:,})")
        
        # 委托给性能优化管道
        results = self._perf_pipeline.start_auto_tuning(
            max_iterations=max_iterations,
            on_new_batch_size=on_new_batch_size,
        )
        
        optimal_size = results.get('optimal_batch_size')
        if not auto_apply and optimal_size:
            logger.info(f"要应用此配置，请使用: engine.batch_size = {optimal_size:,}")
        
        # 保存报告（薄包装，保持向后兼容）
        if save_report and results:
            report_path = self.generate_performance_report(
                include_benchmarks=False,
                include_tuning=True,
                include_recommendations=True
            )
            logger.info(f"调优报告已保存: {report_path}")
        
        return results
    
    def generate_performance_report(
        self,
        include_benchmarks: bool = True,
        include_tuning: bool = True,
        include_history: bool = True,
        include_recommendations: bool = True,
        include_comparison: bool = False,
        output_dir: str = None
    ) -> str:
        """生成性能报告（P2）
        
        Args:
            include_benchmarks: 包含基准测试结果
            include_tuning: 包含调优结果
            include_history: 包含历史趋势
            include_recommendations: 包含优化建议
            include_comparison: 包含历史对比
            output_dir: 输出目录
        
        Returns:
            报告文件路径
        """
        # 委托给性能优化管道
        return self._perf_pipeline.generate_report(
            include_benchmarks=include_benchmarks,
            include_tuning=include_tuning,
            include_history=include_history,
            include_recommendations=include_recommendations,
            include_comparison=include_comparison,
            output_dir=output_dir,
        )
    
    def _setup_async_logging(self, log_file: str, max_bytes: int, backup_count: int):
        """设置异步日志处理器
        
        Args:
            log_file: 日志文件路径
            max_bytes: 单个文件最大字节数
            backup_count: 备份文件数
        """
        import os
        import logging
        
        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, mode=0o750, exist_ok=True)
            
            # 创建异步文件处理器
            from ..utils.logger import AsyncFileHandler
            self._async_log_handler = AsyncFileHandler(
                log_file,
                max_bytes=max_bytes,
                backup_count=backup_count
            )
            self._async_log_handler.setLevel(logging.DEBUG)
            
            # 修复: 使用模块级logger，不重复获取
            # logger = logging.getLogger(__name__)  # ← 已删除
            logger.addHandler(self._async_log_handler)
            
            logger.info(f"GPU异步日志已启用: {log_file} (max={max_bytes/1024/1024:.0f}MB)")
            
        except Exception as e:
            # 修复: 使用模块级logger，不重复获取
            # logger = logging.getLogger(__name__)  # ← 已删除
            logger.warning(f"异步日志启用失败: {e}，使用同步日志")
