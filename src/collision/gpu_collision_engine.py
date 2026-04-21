"""GPU加速的比特币私钥对撞引擎

基于 OpenCL 的 GPU 加速实现，利用 GPU 并行计算能力进行批量私钥碰撞检测。
"""

# ========== 标准库导入 ==========
import os
import sys
import json
import time
import threading
import secrets
import logging
from pathlib import Path
from typing import Set, Optional, Callable, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# ========== 常量定义 ==========
# P2-2: 魔法数字提取为常量
# GPU计算常量
INITIAL_BATCH_SIZE = 1_000_000  # 初始批次大小（100万）
ASYNC_KEY_GEN_TIMEOUT = 30.0  # 异步私钥生成超时（秒）
BATCH_LOG_FREQUENCY = 100  # 日志记录频率（每N个batch）
INITIAL_BATCHES_LOG = 3  # 初始批次日志数量

# 线程等待超时
THREAD_JOIN_TIMEOUT = 5.0  # 默认线程join超时（秒）
MONITOR_THREAD_JOIN_TIMEOUT = 1.0  # 监控线程join超时（秒）

# 异常恢复
EXCEPTION_RECOVERY_DELAY = 0.1  # 异常恢复延迟（秒）

# ========== 本地模块导入 ==========
# GPU设备与上下文
from ..gpu.device import GPUDevice, GPUDeviceDetector
from ..gpu.context import GPUContext
from ..gpu.device_helper import GPUDeviceHelper  # P1-2修复：从独立模块导入

# GPU内核与协议
from ..gpu.profiles.loader import GPUProfileLoader
from ..gpu.kernel import OPENCL_KERNEL_SOURCE
from ..gpu.kernel_protocol import GPUKernelProtocol, GPUKernelFactory  # P1-2修复

# GPU性能优化
from ..gpu.performance_optimizer import get_gpu_optimizer, PerformanceMetrics
from ..gpu.intel_timeout_manager import AdaptiveTimeoutManager
from ..gpu.intel_memory_monitor import IntelMemoryMonitor
from ..gpu.benchmark_suite import GPUBenchmarkSuite
from ..gpu.auto_tuner import GPUAutoTuner
from ..gpu.performance_reporter import PerformanceReportGenerator, ReportConfig
from ..gpu.async_executor import AsyncGPUExecutor  # 异步优化
from ..utils.exception_handler import ExceptionHandler
from ..utils.performance_monitor import EnhancedPerformanceMonitor

NEW_GPU_MODULE_AVAILABLE = True
logger.info("使用新的GPU模块: src.gpu.device")

# 尝试导入 pyopencl
try:
    import pyopencl as cl
    import numpy as np
    PYOPENCL_AVAILABLE = True
except ImportError:
    PYOPENCL_AVAILABLE = False

from ..core.address_generator import P2PKHAddressGenerator
from ..core.secp256k1 import Secp256k1
from ..core.base58 import Base58
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


class GPUKernel(GPUKernelProtocol):
    """OpenCL GPU 计算内核包装 - 优化版本
    
    实现GPUKernelProtocol接口（P1-2修复）。
    使用持久化 Buffer 和异步执行来保持 GPU 持续高负载，
    避免频繁的内存分配和同步等待造成的 GPU 空闲。
    """
    
    # 2*G 的期望坐标值（用于验证）
    EXPECTED_2G_X = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
    EXPECTED_2G_Y = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A
    
    def __init__(self, device: GPUDevice, max_batch_size: int = None, program: Optional[Any] = None):
        """
        初始化GPUKernel
        
        Args:
            device: GPUDevice实例
            max_batch_size: 最大批次大小（None=自动计算）
            program: 已编译的OpenCL程序（可选，如果提供则跳过编译）
        """
        self.device = device
        self.gpu_optimizer = get_gpu_optimizer()
        
        # 如果没有指定max_batch_size，根据GPU显存自动计算
        if max_batch_size is None:
            max_batch_size = self._calculate_optimal_batch_size()
        
        self.max_batch_size = max_batch_size
        self.program = program  # 可能为None（需要自行编译）
        self._batch_kernel = None
        
        # 持久化 Buffer - 避免频繁分配/释放
        self._keys_buf = None
        self._match_buf = None
        self._targets_buf = None
        self._targets_cached = None
        self._num_targets_cached = 0
        
        # 预分配主机内存
        self._match_flags = None
        
        # 校验 GPUDevice 已正确初始化
        if not getattr(self.device, "context", None) or not getattr(self.device, "queue", None):
            raise RuntimeError("GPUDevice 尚未初始化，请先调用 GPUDevice.initialize() 再创建 GPUKernel")
        
        # 如果未提供program，则自行编译
        if self.program is None:
            self._compile()
        
        self._verify()
        self._allocate_buffers()
    
    def _compile(self):
        """编译 OpenCL 内核（带性能监控）"""
        import time
        
        compile_start = time.time()
        try:
            # 使用新模块的内核源码
            self.program = cl.Program(self.device.context, OPENCL_KERNEL_SOURCE).build()
            compile_time_ms = (time.time() - compile_start) * 1000
            
            logger.info(f"OpenCL 内核编译成功: {compile_time_ms:.0f}ms")
            
            # 记录编译性能
            try:
                # 获取设备信息
                device_name = self.device.device.name
                vendor_str = self.device.device.vendor
                global_mem = self.device.device.global_mem_size
                
                # 创建优化配置
                profile = self.gpu_optimizer.create_optimized_profile(
                    device_name=device_name,
                    vendor_str=vendor_str,
                    global_mem_size=global_mem,
                    compile_time_ms=compile_time_ms
                )
                
                # 如果配置文件指定了batch_size，更新
                if profile.max_batch_size != self.max_batch_size:
                    logger.info(
                        f"根据性能优化调整batch_size: "
                        f"{self.max_batch_size} -> {profile.max_batch_size}"
                    )
                    self.max_batch_size = profile.max_batch_size
                    
            except Exception as opt_error:
                logger.warning(f"GPU性能优化失败: {opt_error}")
                
        except Exception as e:
            # 编译失败或其他错误
            compile_time_ms = (time.time() - compile_start) * 1000
            logger.error(f"OpenCL 内核编译失败: {type(e).__name__}: {e} ({compile_time_ms:.0f}ms)")
            raise RuntimeError(f"GPU 内核编译失败: {e}") from e
    
    def _verify(self):
        """验证 GPU 计算正确性"""
        import numpy as np
        
        result_x = np.zeros(8, dtype=np.uint32)
        result_y = np.zeros(8, dtype=np.uint32)
        
        x_buf = cl.Buffer(self.device.context, cl.mem_flags.WRITE_ONLY, size=32)
        y_buf = cl.Buffer(self.device.context, cl.mem_flags.WRITE_ONLY, size=32)
        
        kernel = self.program.verify_arithmetic
        kernel(self.device.queue, (1,), None, x_buf, y_buf)
        self.device.queue.finish()
        
        cl.enqueue_copy(self.device.queue, result_x, x_buf)
        cl.enqueue_copy(self.device.queue, result_y, y_buf)
        
        computed_x = sum(int(result_x[i]) << (i * 32) for i in range(8))
        computed_y = sum(int(result_y[i]) << (i * 32) for i in range(8))
        
        if computed_x != self.EXPECTED_2G_X or computed_y != self.EXPECTED_2G_Y:
            raise RuntimeError("GPU 算术验证失败")
        
        logger.info("GPU 算术验证通过")
    
    def _calculate_optimal_batch_size(self) -> int:
        """根据GPU显存大小计算最优batch_size
        
        使用共享工具函数，考虑目标地址缓冲区占用。
        """
        # 导入共享工具函数
        from ..utils.gpu_memory_utils import calculate_optimal_batch_size
        
        # 计算目标地址缓冲区大小（如果已准备）
        target_buffer_size = 0
        if hasattr(self, '_target_hash160s') and self._target_hash160s:
            target_buffer_size = len(self._target_hash160s)
        
        # 调用共享函数
        return calculate_optimal_batch_size(
            device=self.device,
            target_buffer_size=target_buffer_size
        )
    
    def _allocate_buffers(self):
        """预分配 GPU 内存缓冲区"""
        import numpy as np
        
        # 私钥缓冲区 (最大批次大小)
        self._keys_buf = cl.Buffer(
            self.device.context,
            cl.mem_flags.READ_ONLY,
            size=self.max_batch_size * 32
        )
        
        # 匹配结果缓冲区
        self._match_buf = cl.Buffer(
            self.device.context,
            cl.mem_flags.WRITE_ONLY,
            size=self.max_batch_size * 4
        )
        
        # 预分配主机内存
        self._match_flags = np.zeros(self.max_batch_size, dtype=np.int32)
        
        logger.info(f"GPU 缓冲区分配完成: max_batch_size={self.max_batch_size}")
    
    def set_targets(self, target_hash160s: bytes, num_targets: int):
        """设置目标地址 Hash160 - 只需设置一次"""
        import numpy as np
        
        # 检查是否需要更新
        if (self._targets_cached == target_hash160s and 
            self._num_targets_cached == num_targets):
            return
        
        # 释放旧的缓冲区
        if self._targets_buf is not None:
            self._targets_buf = None
        
        # 创建新的目标缓冲区
        targets_array = np.frombuffer(target_hash160s, dtype=np.uint8)
        self._targets_buf = cl.Buffer(
            self.device.context,
            cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=targets_array
        )
        
        self._targets_cached = target_hash160s
        self._num_targets_cached = num_targets
        
        logger.info(f"GPU 目标地址设置完成: {num_targets} 个目标")
    
    def run_batch(self, private_keys: bytes, num_keys: int,
                  target_hash160s: bytes = None, num_targets: int = 0) -> List[Dict]:
        """批量执行私钥碰撞检测 - 优化版本
        
        使用异步数据传输和持久化缓冲区，保持 GPU 持续工作。
        修复：使用uint32替代uint8避免Intel Arc A770的global char* hang bug
        """
        import numpy as np
        import time
        
        batch_start_time = time.time()
        
        # 参数校验
        if num_keys <= 0 or num_keys > self.max_batch_size:
            raise ValueError(f"num_keys 必须在 1..{self.max_batch_size} 之间，当前为 {num_keys}")
        
        if len(private_keys) != num_keys * 32:
            raise ValueError(
                f"private_keys 长度与 num_keys 不匹配：len(private_keys)={len(private_keys)}, "
                f"但 num_keys={num_keys} 需要 {num_keys * 32} 字节"
            )
        
        # 设置目标（仅在第一次或目标变化时）
        if target_hash160s is not None:
            self.set_targets(target_hash160s, num_targets)
        
        # 修复：使用uint32替代uint8避免Intel Arc A770的global char* hang bug
        # 将32字节私钥重新解释为8个uint32（性能提升4倍）
        keys_array = np.frombuffer(private_keys[:num_keys * 32], dtype=np.uint32)
        cl.enqueue_copy(self.device.queue, self._keys_buf, keys_array)
        
        # 清空匹配结果缓冲区
        cl.enqueue_fill_buffer(
            self.device.queue, self._match_buf,
            np.int32(0), 0, num_keys * 4
        )
        
        # 执行内核（异步）
        if self._batch_kernel is None:
            self._batch_kernel = self.program.batch_check
        
        self._batch_kernel(
            self.device.queue, (num_keys,), None,
            self._keys_buf, np.uint32(num_keys),
            self._targets_buf, np.uint32(self._num_targets_cached),
            self._match_buf
        )
        
        # 异步读取结果
        match_view = self._match_flags[:num_keys]
        read_event = cl.enqueue_copy(
            self.device.queue, match_view, self._match_buf
        )
        
        # 方案B：添加超时保护机制（防止Intel Arc A770等GPU永久卡死）
        # 使用事件等待带超时，避免GUI永久阻塞
        timeout_seconds = 30  # Intel Arc建议的超时时间
        
        # 创建超时事件
        timeout_event = threading.Event()
        execution_completed = [False]  # 使用列表存储结果（闭包）
        
        def timeout_monitor():
            """后台线程监控GPU执行超时"""
            if not timeout_event.wait(timeout_seconds):
                # 超时未收到完成信号
                logger.error(f"GPU执行超时({timeout_seconds}秒)，可能存在内核hang问题")
                # 尝试强制完成队列
                try:
                    self.device.queue.finish()
                except Exception as e:
                    logger.error(f"强制完成队列失败: {e}")
                execution_completed[0] = False
            # else: 正常完成，不做任何操作
        
        # 启动超时监控线程
        monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)
        monitor_thread.start()
        
        try:
            # 等待当前批次完成（阻塞等待）
            read_event.wait()
            execution_completed[0] = True
        finally:
            # 通知监控线程已完成
            timeout_event.set()
            monitor_thread.join(timeout=1.0)
        
        # 检查是否超时
        if not execution_completed[0]:
            raise RuntimeError(f"GPU执行超时{timeout_seconds}秒，内核可能已hang")
        
        # 收集匹配结果
        matches = []
        for i in range(num_keys):
            if match_view[i] > 0:
                matches.append({
                    "key_index": i,
                    "target_index": int(match_view[i] - 1)
                })
        
        # 记录性能指标（用于自适应优化）
        try:
            execution_time_ms = (time.time() - batch_start_time) * 1000
            keys_per_second = (num_keys / execution_time_ms * 1000) if execution_time_ms > 0 else 0
            
            metrics = PerformanceMetrics(
                batch_execution_time_ms=execution_time_ms,
                keys_per_second=keys_per_second,
                error_count=0  # 本批次无错误
            )
            self.gpu_optimizer.record_performance(metrics)
            
            # v2.2.1: 记录到GPU性能监控器
            if hasattr(self, 'stats') and self.stats:
                try:
                    # 使用预导入的监控器,避免重复import
                    gpu_monitor = _get_gpu_monitor()
                    # v2.2.1: 使用精确的显存估算
                    if hasattr(self, '_calculate_gpu_memory_usage'):
                        memory_mb = self._calculate_gpu_memory_usage(num_keys)
                    else:
                        memory_mb = (num_keys * 36) / (1024 * 1024)
                    gpu_monitor.record_kernel_metrics(
                        batch_size=num_keys,
                        execution_time_ms=execution_time_ms,
                        memory_allocated_mb=memory_mb,
                        error_count=0,
                        match_count=len(matches)
                    )
                except Exception as monitor_error:
                    logger.debug(f"GPU性能监控记录失败: {monitor_error}")
            
            # P1: 记录到自适应超时管理器（每个批次都记录）
            if self.timeout_manager:
                self.timeout_manager.record_execution_time(execution_time_ms)
                
                # 降低日志频率：每 100 个批次检查一次警告
                if (self.stats.total_batches > 0 and 
                    self.stats.total_batches % self.MONITOR_INTERVAL == 0):
                    if self.timeout_manager.should_warn(execution_time_ms):
                        timeout = self.timeout_manager.get_timeout()
                        logger.warning(
                            f"⚠️ 执行时间接近超时阈值: "
                            f"{execution_time_ms:.0f}ms / {timeout*1000:.0f}ms"
                        )
            
            # P1: 显存监控（每个批次都跟踪，但降低检查频率）
            if self.memory_monitor:
                # 跟踪显存使用（估算）- 每个批次都记录
                estimated_memory = num_keys * 36  # 每个私钥约 36 字节
                self.memory_monitor.track_allocation(
                    estimated_memory,
                    batch_count=self.stats.total_batches
                )
                
                # 降低显存检查频率：每 100 个批次检查一次
                if (self.stats.total_batches > 0 and 
                    self.stats.total_batches % self.MONITOR_INTERVAL == 0):
                    # 检查显存警告
                    warnings = self.memory_monitor.check_warnings()
                    if warnings:
                        for warning in warnings:
                            logger.warning(warning)
                    
                    # 如果显存压力大，建议减小 batch_size
                    reduction = self.memory_monitor.get_recommended_batch_reduction()
                    if reduction > 0:
                        new_batch_size = int(num_keys * (1 - reduction))
                        logger.info(
                            f"💡 显存压力，建议减小 batch_size: "
                            f"{num_keys} -> {new_batch_size}"
                        )
        except Exception as perf_error:
            logger.debug(f"性能指标记录失败: {perf_error}")
        
        return matches
    
    def cleanup(self):
        """清理资源"""
        if self._keys_buf:
            self._keys_buf = None
        if self._match_buf:
            self._match_buf = None
        if self._targets_buf:
            self._targets_buf = None
        self._match_flags = None
        self.program = None
        self._batch_kernel = None


class GPUCollisionEngine(BaseCollisionEngine):
    """GPU 加速的比特币私钥对撞引擎
    
    继承BaseCollisionEngine，实现GPU碰撞引擎。
    """
    
    # 监控配置
    MONITOR_INTERVAL = 100  # 每 100 个批次检查一次警告和建议
    
    def _apply_intel_specific_optimizations(self):
        """应用 Intel GPU 特定优化和验证"""
        logger.info("="*60)
        logger.info("🔧 开始应用 Intel GPU 特殊优化")
        logger.info("="*60)
        
        # 1. 验证 uint32 workaround
        if not self._verify_uint32_workaround():
            logger.error("❌ Intel uint32 workaround 验证失败")
            raise RuntimeError("Intel GPU workaround 未正确应用，无法继续")
        
        # 2. 初始化 P1/P2 组件
        self._init_intel_monitoring_and_tuning()
        
        # 3. 设置保守的超时
        timeout = getattr(self._gpu_device, 'timeout_seconds', 30)
        logger.info(f"✅ Intel 超时保护: {timeout}秒")
        
        # 4. 异步执行(根据配置决定)
        if hasattr(self._gpu_device, 'enable_async'):
            # 不再强制禁用,尊重配置
            if self._gpu_device.enable_async_execution:
                logger.info("✅ Intel 异步执行: 已启用(双缓冲优化)")
            else:
                self._gpu_device.enable_async = False
                logger.info("✅ Intel 异步执行: 已禁用(传统模式)")
        
        # 5. 显存限制
        memory_efficiency = getattr(self._gpu_device, 'memory_efficiency', 0.45)
        logger.info(f"✅ Intel 显存效率: {memory_efficiency*100:.0f}%")
        
        # 6. 驱动版本检查
        if hasattr(self._gpu_device, 'driver_version') and self._gpu_device.driver_version:
            logger.info(f"✅ Intel 驱动版本: {self._gpu_device.driver_version}")
        else:
            logger.warning("⚠️ 无法检测 Intel 驱动版本")
        
        logger.info("="*60)
        logger.info("✅ Intel GPU 特殊优化应用完成")
        logger.info("="*60)
    
    def _init_intel_monitoring_and_tuning(self):
        """初始化 Intel GPU 监控和调优组件（P1/P2）
        
        采用防御性初始化策略：
        - 每个组件独立初始化
        - 失败不影响其他组件
        - 失败的组件设为 None
        - 记录详细的警告日志
        
        注意:
            所有监控组件都是可选的，初始化失败不会阻止引擎运行。
            引擎核心功能（碰撞检测）不受影响。
        """
        logger.info("\n📊 初始化 Intel GPU 监控和调优组件...")
        
        # 1. 自适应超时管理器（P1）
        try:
            self.timeout_manager = AdaptiveTimeoutManager(
                base_timeout=getattr(self._gpu_device, 'timeout_seconds', 30.0),
                history_size=50,
                safety_factor=3.0,
                min_timeout=10.0,
                max_timeout=120.0
            )
            logger.info("✅ 自适应超时管理器已初始化")
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(
                f"⚠️ 自适应超时管理器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                f"   超时管理功能将被禁用，使用固定超时保护",
                exc_info=True
            )
            self.timeout_manager = None
        
        # 2. 显存监控器（P1）
        try:
            # 防御性检查：确保 device_info 是字典
            device_info = self._gpu_device.device_info
            if not isinstance(device_info, dict):
                logger.warning(
                    f"⚠️ device_info 类型异常: {type(device_info).__name__}，跳过显存监控器初始化\n"
                    f"   显存监控功能将被禁用"
                )
                self.memory_monitor = None
            else:
                total_memory = device_info.get('global_mem_size', 0)
                
                if total_memory <= 0:
                    logger.warning(
                        "⚠️ 无法获取显存大小（global_mem_size=0），跳过显存监控器初始化\n"
                        "   显存监控功能将被禁用"
                    )
                    self.memory_monitor = None
                else:
                    self.memory_monitor = IntelMemoryMonitor(
                        total_memory_bytes=total_memory,
                        safe_usage_ratio=0.45  # Intel 保守策略
                    )
                    logger.info(
                        f"✅ 显存监控器已初始化 "
                        f"(总显存: {total_memory/1024**3:.1f}GB)"
                    )
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(
                f"⚠️ 显存监控器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                f"   显存监控功能将被禁用",
                exc_info=True
            )
            self.memory_monitor = None
        
        # 3. 基准测试套件（P2）
        try:
            self.benchmark_suite = GPUBenchmarkSuite(self)
            logger.info("✅ 基准测试套件已初始化")
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(
                f"⚠️ 基准测试套件初始化失败（非致命）: {type(e).__name__}: {e}\n"
                f"   基准测试功能将被禁用",
                exc_info=True
            )
            self.benchmark_suite = None
        
        # 4. 自动调优器（P2）
        try:
            self.auto_tuner = GPUAutoTuner(self)
            logger.info("✅ 自动调优器已初始化")
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(
                f"⚠️ 自动调优器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                f"   自动调优功能将被禁用",
                exc_info=True
            )
            self.auto_tuner = None
        
        # 5. 性能报告生成器（P2）
        try:
            self.performance_reporter = PerformanceReportGenerator(
                gpu_engine=self,
                benchmark_suite=self.benchmark_suite,
                auto_tuner=self.auto_tuner
            )
            logger.info("✅ 性能报告生成器已初始化")
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(
                f"⚠️ 性能报告生成器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                f"   性能报告功能将被禁用",
                exc_info=True
            )
            self.performance_reporter = None
        
        # 总结初始化结果
        initialized_count = sum([
            self.timeout_manager is not None,
            self.memory_monitor is not None,
            self.benchmark_suite is not None,
            self.auto_tuner is not None,
            self.performance_reporter is not None
        ])
        
        if initialized_count == 5:
            logger.info("✅ 所有 5 个监控和调优组件初始化成功\n")
        elif initialized_count > 0:
            logger.warning(
                f"⚠️ {initialized_count}/5 个组件初始化成功，"
                f"{5 - initialized_count} 个组件被禁用\n"
                f"   引擎仍可正常运行，但部分监控功能不可用\n"
            )
        else:
            logger.error(
                "❌ 所有监控和调优组件初始化失败\n"
                "   引擎将使用默认配置运行，无监控和调优功能\n"
            )
        
        logger.info("✅ Intel GPU 监控和调优组件初始化完成\n")
    
    def _verify_uint32_workaround(self):
        """验证 uint32 workaround 是否正确应用
        
        Returns:
            bool: 验证成功返回 True
        """
        try:
            # 检查内核源码
            kernel_source = OPENCL_KERNEL_SOURCE
            if '__global const uint *private_keys' not in kernel_source:
                logger.error("❌ 内核未使用 uint32 workaround")
                return False
            
            logger.info("✅ 内核源码使用 uint32 workaround")
            
            # 小规模测试（100个私钥）
            test_num_keys = 100
            test_keys = secrets.token_bytes(test_num_keys * 32)
            test_targets = b'\x00' * 20  # 虚拟目标
            
            logger.info(f"🧪 运行 Intel workaround 测试 (num_keys={test_num_keys})...")
            
            # 运行测试批次
            matches = self._gpu_kernel.run_batch(
                num_keys=test_num_keys,
                private_keys=test_keys,
                target_hash160s=test_targets,
                num_targets=1
            )
            
            # 验证结果
            if isinstance(matches, list):
                logger.info("✅ Intel uint32 workaround 测试通过")
                return True
            else:
                logger.error(f"❌ Intel workaround 测试返回异常结果: {type(matches)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Intel workaround 测试失败: {type(e).__name__}: {e}")
            return False
    
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
                 gpu_pool_max_memory_mb: int = 512):
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
        """
        if not PYOPENCL_AVAILABLE:
            raise RuntimeError("pyopencl 不可用，无法使用 GPU 加速")
        
        self.targets = targets
        self.device_index = device_index
        
        # 如果未指定batch_size，稍后在_init_gpu中由GPUKernel自动计算
        self.batch_size = batch_size
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete
        self.stats = CollisionStats()
        self._stop_event = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 断点管理器
        self.checkpoint_mgr = CheckpointManager(auto_save_interval=checkpoint_interval) if checkpoint_enabled else None
        # 去重过滤器
        self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size, enabled=dedup_enabled)
        
        # GPU 相关
        self._gpu_device = None
        self._gpu_context = None  # GPU上下文管理器
        self._gpu_kernel = None
        self._target_hash160s = None
        self._target_list = []
        self._last_progress_time = 0
        self._progress_interval_sec = 0.5
        
        # GPU内存池配置 (v2.2.0新增)
        self.use_gpu_memory_pool = use_gpu_memory_pool
        self.gpu_pool_max_buffers = gpu_pool_max_buffers
        self.gpu_pool_max_memory_mb = gpu_pool_max_memory_mb
        self._gpu_memory_pool = None  # 将在_init_gpu中初始化
        
        if use_gpu_memory_pool:
            logger.info(f"GPU内存池已启用: max_buffers={gpu_pool_max_buffers}, "
                       f"max_memory={gpu_pool_max_memory_mb}MB")
        else:
            logger.info("GPU内存池未启用,使用直接分配模式")
        
        # GPU型号配置加载器
        self._profile_loader = GPUProfileLoader()
        
        # 当前模式
        self._current_position = 0
        self._current_mode = ""
        self._range_start = None
        self._range_end = None
        
        # 监控系统（与CPU引擎保持一致）
        self.data_logging_enabled = data_logging_enabled
        self.data_logging_interval = data_logging_interval
        self.data_logger = None
        self.enhanced_monitoring = None
        
        # P1/P2 新增：Intel GPU 监控和调优组件
        self.timeout_manager: Optional['AdaptiveTimeoutManager'] = None  # 自适应超时管理
        self.memory_monitor: Optional['IntelMemoryMonitor'] = None       # 显存监控
        self.benchmark_suite: Optional['GPUBenchmarkSuite'] = None       # 基准测试套件
        self.auto_tuner: Optional['GPUAutoTuner'] = None                 # 自动调优器
        self.performance_reporter: Optional['PerformanceReportGenerator'] = None  # 性能报告生成器
        
        # v2.2.1 新增：GPU性能监控器
        self.gpu_performance_monitor: Optional['GPUPerformanceMonitor'] = None
        
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
        
        # 初始化 GPU
        self._init_gpu()
    
    def _init_gpu(self):
        """初始化 GPU 设备和内核（优化版本）
        
        优化点:
        1. 使用GPUContext管理厂商优化
        2. 使用GPUProfileLoader加载型号配置
        3. 自动计算最优batch_size
        4. 应用厂商特定编译选项
        5. Intel GPU特殊验证
        """
        with EnhancedPerformanceMonitor(logger, "GPU引擎初始化", level="INFO") as pm:
            try:
                if not GPUDeviceDetector.is_gpu_available():
                    raise RuntimeError("pyopencl 不可用")
                
                # 1. 初始化GPU设备
                with EnhancedPerformanceMonitor(logger, "GPU设备初始化", level="DEBUG"):
                    self._gpu_device = GPUDevice()
                    
                    # 启用异步执行(按优先级读取配置)
                    enable_async = False
                    config_source = "默认"
                    
                    # 优先级1: 构造函数传入的配置
                    if hasattr(self, 'config') and self.config:
                        gpu_config = self.config.get('gpu', {})
                        if 'async_execution' in gpu_config:
                            enable_async = gpu_config['async_execution']
                            config_source = "构造参数"
                            logger.debug(f"从构造参数读取异步设置: {enable_async}")
                    
                    # 优先级2: 自动读取配置文件(仅当构造参数未明确设置时)
                    if config_source == "默认":
                        project_root = Path(__file__).parent.parent.parent
                        config_files = [
                            project_root / 'config.intel_arc.json',
                            project_root / 'config.json',
                        ]
                        
                        for cfg_file in config_files:
                            if cfg_file.exists():
                                try:
                                    with open(cfg_file, 'r', encoding='utf-8') as f:
                                        cfg = json.load(f)
                                        if cfg.get('gpu', {}).get('async_execution', False):
                                            enable_async = True
                                            config_source = f"配置文件 {cfg_file.name}"
                                            logger.info(f"✅ 从{config_source}读取异步设置")
                                            break
                                except json.JSONDecodeError as e:
                                    logger.warning(f"配置文件 {cfg_file} JSON格式错误: {e}")
                                except PermissionError:
                                    logger.warning(f"无法读取 {cfg_file}: 权限不足")
                                except Exception as e:
                                    logger.debug(f"读取配置文件 {cfg_file} 失败(非关键): {e}")
                    
                    # 应用配置
                    if enable_async:
                        self._gpu_device.enable_async_execution = True
                        logger.info(f"✅ GPU异步执行已启用({config_source}) - 双缓冲优化")
                    else:
                        logger.info(f"GPU异步执行未启用({config_source}) - 使用同步模式")
                        logger.debug("提示: 在配置文件中设置 'gpu.async_execution': true 以启用异步优化")
                    
                    # 初始化设备(传入enable_async)
                    self._gpu_device.initialize(self.device_index, enable_async=enable_async)
                
                # 2. 加载GPU型号配置
                device_info = self._gpu_device.get_device_info()
                device_name = device_info.get('name', '')
                vendor = device_info.get('vendor', '')
                
                logger.info(f"检测到GPU设备: {device_name} ({vendor})")
                logger.info(
                    f"  - 显存: {device_info.get('global_mem_size', 0) / (1024**3):.1f} GB\n"
                    f"  - 计算单元: {device_info.get('max_compute_units', 'N/A')}\n"
                    f"  - 平台: {device_info.get('platform', 'Unknown')}"
                )
                
                # 3. 识别厂商并加载配置
                with EnhancedPerformanceMonitor(logger, "GPU型号配置加载", level="DEBUG"):
                    from ..gpu.device import identify_vendor
                    vendor_type = identify_vendor(device_name, vendor)
                    
                    if vendor_type != 'unknown':
                        profile = self._profile_loader.get_profile(vendor_type, device_name)
                        if profile:
                            logger.info(f"成功加载GPU型号配置: {vendor_type}/{device_name}")
                            # 将配置附加到GPUDevice
                            self._gpu_device.profile = profile
                        else:
                            logger.warning(f"未找到GPU型号配置，使用默认配置: {device_name}")
                    else:
                        logger.warning(f"未知GPU厂商，跳过型号配置加载: {vendor}")
                
                # 4. 创建GPU上下文（包含厂商优化器）
                self._gpu_context = GPUContext(self._gpu_device)
                
                # 7. 应用厂商优化
                with EnhancedPerformanceMonitor(logger, "GPU厂商优化应用", level="DEBUG"):
                    self._gpu_context.apply_optimizations()
                
                # 8. 计算最优batch_size（如果未指定）
                if self.batch_size is None:
                    self.batch_size = self._gpu_context.calculate_batch_size()
                    logger.info(
                        f"自动设置 batch_size: {self.batch_size} "
                        f"(基于GPU型号配置和显存计算)"
                    )
                else:
                    logger.debug(f"使用指定的 batch_size: {self.batch_size}")
                
                # 9. 使用GPUContext编译内核（应用厂商编译选项）
                with EnhancedPerformanceMonitor(logger, "OpenCL内核编译", level="INFO"):
                    self._gpu_context.compile_kernel(OPENCL_KERNEL_SOURCE)
                
                # 10. 创建GPUKernel（使用已编译的程序）
                with EnhancedPerformanceMonitor(logger, "GPUKernel创建", level="DEBUG"):
                    # 初始化GPU内存池 (v2.2.0新增)
                    if self.use_gpu_memory_pool:
                        from ..gpu.memory_pool import get_gpu_memory_pool
                        self._gpu_memory_pool = get_gpu_memory_pool(
                            self._gpu_device.context,
                            max_buffers=self.gpu_pool_max_buffers
                        )
                        logger.info(f"GPU内存池初始化完成: {self._gpu_memory_pool.get_stats()}")
                    
                    self._gpu_kernel = GPUKernel(
                        self._gpu_device, 
                        max_batch_size=self.batch_size,
                        program=self._gpu_context.program
                    )
                
                # 初始化异步执行器(如果启用了异步)
                if self._gpu_device.enable_async_execution:
                    logger.info("初始化GPU异步执行器...")
                    self._async_executor = AsyncGPUExecutor(
                        self._gpu_device,
                        max_batch_size=self.batch_size
                    )
                    # 初始化双缓冲
                    self._async_executor.initialize_buffers(
                        self._gpu_device.context,
                        num_keys=self.batch_size
                    )
                    logger.info("✅ GPU异步执行器已初始化(双缓冲)")
                else:
                    self._async_executor = None
                    logger.info("GPU异步执行器未初始化(使用同步模式)")
                
                # 11. 预转换目标地址为 Hash160
                with EnhancedPerformanceMonitor(logger, "目标地址转换", level="DEBUG"):
                    self._prepare_targets()
                
                # 12. 设置 GPU 目标地址缓冲区
                if self._target_hash160s:
                    self._gpu_kernel.set_targets(self._target_hash160s, len(self._target_list))
                
                # 13. Intel GPU特殊验证（必须在 GPUKernel 创建之后）
                if vendor.lower().startswith('intel'):
                    logger.info("🔧 检测到 Intel GPU，应用特殊优化")
                    self._apply_intel_specific_optimizations()
                
                # 14. 初始化GPU性能监控器 (v2.2.1新增)
                self.gpu_performance_monitor = get_gpu_performance_monitor(engine=self)
                self.gpu_performance_monitor.start()
                logger.info("✅ GPU性能监控器已启动")
                
                logger.info(
                    f"GPU 引擎初始化成功: {device_name} "
                    f"(厂商: {vendor}, batch_size: {self.batch_size})"
                )
                
                pm.add_metadata('device_name', device_name)
                pm.add_metadata('vendor', vendor)
                pm.add_metadata('batch_size', self.batch_size)
                
            except Exception as e:
                # 使用ExceptionHandler记录详细错误
                ExceptionHandler.handle_engine_error(
                    "GPU",
                    e,
                    stats=self.stats,
                    context="初始化"
                )
                raise RuntimeError(f"GPU 初始化失败: {e}") from e
    
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
        
        v2.2.1改进: 考虑所有缓冲区,更精确的估算
        
        Args:
            num_keys: 私钥数量
            
        Returns:
            显存使用量(MB)
        """
        # 1. 私钥缓冲区 (num_keys * 32字节)
        private_keys_mb = (num_keys * 32) / (1024 * 1024)
        
        # 2. 匹配结果缓冲区 (num_keys * 4字节)
        match_flags_mb = (num_keys * 4) / (1024 * 1024)
        
        # 3. 目标地址缓冲区 (固定大小)
        targets_mb = 0.0
        if self._target_hash160s:
            targets_mb = len(self._target_hash160s) / (1024 * 1024)
        
        # 4. 内核执行临时显存 (估算20% overhead)
        overhead_mb = (private_keys_mb + match_flags_mb) * 0.2
        
        total_mb = private_keys_mb + match_flags_mb + targets_mb + overhead_mb
        
        logger.debug(f"GPU显存估算: private_keys={private_keys_mb:.2f}MB, "
                    f"match_flags={match_flags_mb:.2f}MB, "
                    f"targets={targets_mb:.2f}MB, "
                    f"overhead={overhead_mb:.2f}MB, "
                    f"total={total_mb:.2f}MB")
        
        return total_mb
    
    @staticmethod
    def is_gpu_available() -> bool:
        """检查 GPU 是否可用
        
        委托给GPUDeviceDetector进行实际检测，避免代码重复。
        
        Returns:
            bool: GPU可用返回True，否则返回False
        """
        return GPUDeviceDetector.is_gpu_available()
    
    def get_device_info(self) -> Dict:
        """获取 GPU 设备信息"""
        if self._gpu_device:
            return self._gpu_device.get_device_info()
        return {}
    
    def start(self, mode: str = "random", resume: bool = False, **kwargs):
        """启动对撞"""
        if self._running:
            return
        
        # 断点恢复逻辑
        if resume and self.checkpoint_mgr:
            checkpoint = self.checkpoint_mgr.load()
            if checkpoint:
                if checkpoint.get("targets"):
                    self.targets = set(checkpoint["targets"])
                    self._prepare_targets()
                    # 同步更新 GPU 目标缓冲区（修复：断点恢复后必须更新 GPU 目标）
                    if self._gpu_kernel and self._target_hash160s:
                        self._gpu_kernel.set_targets(
                            self._target_hash160s,
                            len(self._target_list)
                        )
                checkpoint_mode = checkpoint.get("mode", mode)
                if checkpoint_mode == "range":
                    kwargs['start'] = checkpoint.get("current_position", kwargs.get('start', 1))
                    kwargs['end'] = checkpoint.get("range_end", kwargs.get('end', 2**32))
                    mode = "range"
                elif checkpoint_mode == "brute_force":
                    kwargs['start'] = checkpoint.get("current_position", kwargs.get('start', 1))
                    mode = "brute_force"
                self.stats.total_checked = checkpoint.get("total_checked", 0)
        
        self._current_mode = mode
        if mode == "range":
            self._range_start = kwargs.get('start', 1)
            self._range_end = kwargs.get('end', 2**32)
        elif mode == "brute_force":
            self._range_start = kwargs.get('start', 1)
            self._range_end = None
        
        self._stop_event.clear()
        self._running = True
        self.stats.start_time = time.time()
        
        if mode == "random":
            target_fn = self._random_search
        elif mode == "range":
            target_fn = lambda: self._range_scan(self._range_start, self._range_end)
        elif mode == "brute_force":
            target_fn = lambda: self._brute_force(self._range_start)
        else:
            raise ValueError(f"未知模式: {mode}")
        
        self._thread = threading.Thread(target=target_fn, daemon=True)
        self._thread.start()
    
    def _random_search(self):
        """随机碰撞模式 - 高性能优化版本
        
        优化策略：
        1. 增加初始批次到100万，提高GPU利用率
        2. 异步私钥生成，在GPU计算时并行准备下一批
        3. 减少等待时间，实现持续高吞吐量
        4. GPU异步执行(双缓冲),消除CPU-GPU等待
        """
        # 检查是否启用异步执行
        use_async = self._gpu_device.enable_async_execution and self._async_executor
        if use_async:
            logger.info("✅ 使用GPU异步执行模式(双缓冲)")
            return self._random_search_async()
        else:
            logger.info("使用GPU同步执行模式")
            return self._random_search_sync()
    
    def _random_search_sync(self):
        """同步执行版本 - 重构优化（P0-1修复）
        
        将原有的300+行巨型函数拆分为多个职责单一的子函数：
        1. _generate_private_keys_batch - 私钥批量生成
        2. _process_gpu_matches - GPU匹配结果处理
        3. _update_performance_metrics - 性能指标更新
        4. _check_and_report_progress - 进度检查与报告
        5. _wait_for_async_key_generation - 异步私钥生成等待
        """
        import threading
        
        logger.info("GPU _random_search 启动（高性能优化模式）")
        
        # 初始化状态
        batch_count = 0
        batch_num = 0
        target_hash160s = self._target_hash160s
        num_targets = len(self._target_list)
        
        # 优化1: 增加初始批次到100万（提高GPU利用率）
        current_batch_size = min(INITIAL_BATCH_SIZE, self.batch_size)
        
        logger.info(f"目标数量: {num_targets}, 初始批次大小: {current_batch_size:,}")
        
        # 预生成第一批私钥
        next_private_keys = self._generate_private_keys_batch(current_batch_size)
        
        # 启动第一个异步生成线程
        gen_thread, gen_result = self._start_async_key_generation(self.batch_size)
        
        # 主循环
        while not self._stop_event.is_set():
            # 使用预生成的私钥
            private_keys = next_private_keys
            actual_batch_size = len(private_keys) // 32
            
            try:
                batch_num += 1
                
                # 执行GPU batch计算
                matches, execution_time_ms = self._execute_gpu_batch(
                    private_keys, actual_batch_size, batch_num
                )
                
                # 等待异步私钥生成完成
                next_private_keys = self._wait_for_async_key_generation(
                    gen_thread, gen_result, batch_num
                )
                
                # 启动下一批异步生成
                gen_thread, gen_result = self._start_async_key_generation(self.batch_size)
                
                # 处理GPU匹配结果
                self._process_gpu_matches(private_keys, matches)
                
                # 更新统计数据
                batch_count += actual_batch_size
                self.stats.update(batch_count)
                
                # 记录性能指标
                self._update_performance_metrics(actual_batch_size, execution_time_ms)
                
                # 检查并报告进度
                self._check_and_report_progress(batch_count, current_batch_size)
                    
            except Exception as e:
                # 使用统一异常处理器处理GPU异常
                ExceptionHandler.handle_gpu_error("随机碰撞", e, self.stats)
                
                # 异常恢复：重新启动异步生成
                logger.warning(f"GPU batch {batch_num}: 异常恢复，重新启动异步私钥生成")
                gen_thread, gen_result = self._start_async_key_generation(self.batch_size)
                
                continue
        
        logger.info(f"GPU _random_search 结束: 共处理 {batch_count} 个私钥")
        self._running = False
        self.stats.update(batch_count)
        if self.on_complete:
            self.on_complete(self.stats)
    
    def _random_search_async(self):
        """异步执行版本(双缓冲优化)"""
        import threading
        
        logger.info("GPU _random_search_async 启动（异步双缓冲模式）")
        target_hash160s = self._target_hash160s
        num_targets = len(self._target_list)
        batch_count = 0
        batch_num = 0
        
        current_batch_size = min(1_000_000, self.batch_size)
        logger.info(f"初始批次大小: {current_batch_size:,}")
        
        # 预生成第一批私钥
        next_private_keys = b''.join(secrets.token_bytes(32) for _ in range(current_batch_size))
        
        # 异步私钥生成
        def generate_next_batch_async(batch_size: int):
            result = [None]
            def _generate():
                result[0] = b''.join(secrets.token_bytes(32) for _ in range(batch_size))
            thread = threading.Thread(target=_generate, daemon=True)
            thread.start()
            return thread, result
        
        gen_thread, gen_result = generate_next_batch_async(self.batch_size)
        
        while not self._stop_event.is_set():
            private_keys = next_private_keys
            actual_batch_size = len(private_keys) // 32
            
            try:
                batch_num += 1
                batch_start_time = time.time()
                
                # 使用异步执行器
                matches, execution_time_ms = self._async_executor.run_batch_async(
                    private_keys=private_keys,
                    num_keys=actual_batch_size,
                    program=self._gpu_context.program,
                    targets_buf=self._gpu_kernel._targets_buf,
                    num_targets=num_targets
                )
                
                # GPU计算完成后，等待异步生成完成
                if gen_thread.is_alive():
                    gen_thread.join(timeout=30.0)
                    if gen_thread.is_alive():
                        logger.error(f"异步私钥生成超时")
                        next_private_keys = b''.join(secrets.token_bytes(32) for _ in range(self.batch_size))
                    else:
                        next_private_keys = gen_result[0] if gen_result[0] else b''.join(secrets.token_bytes(32) for _ in range(self.batch_size))
                else:
                    next_private_keys = gen_result[0] if gen_result[0] else b''.join(secrets.token_bytes(32) for _ in range(self.batch_size))
                
                # 启动下一批生成
                gen_thread, gen_result = generate_next_batch_async(self.batch_size)
                
                # 处理匹配
                for match in matches:
                    key_idx = match["key_index"]
                    private_key = private_keys[key_idx*32:(key_idx+1)*32]
                    
                    if not self.dedup_filter.check_and_add(private_key):
                        continue
                    
                    target_idx = match["target_index"]
                    address = self._target_list[target_idx]
                    
                    from ..core.wif import WIF
                    wif = WIF.encode(private_key, compressed=True)
                    
                    self.stats.add_match(private_key, address)
                    if self.on_match:
                        self.on_match(private_key, address, wif)
                
                batch_count += actual_batch_size
                self.stats.update(batch_count)
                
                # 记录性能
                if self.gpu_performance_monitor:
                    try:
                        memory_mb = self._calculate_gpu_memory_usage(actual_batch_size)
                        self.gpu_performance_monitor.record_kernel_metrics(
                            batch_size=actual_batch_size,
                            execution_time_ms=execution_time_ms,
                            memory_allocated_mb=memory_mb
                        )
                    except Exception as e:
                        logger.debug(f"记录GPU性能指标失败: {e}")
                
                # 进度回调
                current_time = time.time()
                if current_time - self._last_progress_time >= self._progress_interval_sec:
                    if self.on_progress:
                        self.on_progress(self.stats)
                    self._save_checkpoint(batch_count)
                    self._last_progress_time = current_time
                    
            except Exception as e:
                ExceptionHandler.handle_gpu_error("异步随机碰撞", e, self.stats)
                time.sleep(EXCEPTION_RECOVERY_DELAY)
        
        logger.info(f"GPU _random_search_async 结束: 共处理 {batch_count} 个私钥")
    
    # ========== P0-1重构：辅助方法 ==========
    
    def _generate_private_keys_batch(self, count: int) -> bytes:
        """生成一批随机私钥
        
        Args:
            count: 私钥数量
            
        Returns:
            拼接的私钥字节串（每个32字节）
        """
        return b''.join(secrets.token_bytes(32) for _ in range(count))
    
    def _start_async_key_generation(self, batch_size: int) -> Tuple[threading.Thread, List[Any]]:
        """启动异步私钥生成线程
        
        Args:
            batch_size: 要生成的私钥数量
            
        Returns:
            (thread, result_list) 元组
        """
        result: List[Any] = [None]
        
        def _generate():
            result[0] = self._generate_private_keys_batch(batch_size)
        
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()
        return thread, result
    
    def _wait_for_async_key_generation(
        self,
        gen_thread: threading.Thread,
        gen_result: List[Any],
        batch_num: int
    ) -> bytes:
        """等待异步私钥生成完成并返回结果
        
        Args:
            gen_thread: 生成线程
            gen_result: 结果列表
            batch_num: 当前批次号
            
        Returns:
            生成的私钥字节串
        """
        if gen_thread.is_alive():
            # 使用超时保护
            gen_thread.join(timeout=ASYNC_KEY_GEN_TIMEOUT)
            
            if gen_thread.is_alive():
                logger.error(
                    f"GPU batch {batch_num}: 异步私钥生成超时（>{ASYNC_KEY_GEN_TIMEOUT}秒），强制继续"
                )
                return self._generate_private_keys_batch(self.batch_size)
        
        # 检查生成结果
        if gen_result[0] is None:
            logger.error(
                f"GPU batch {batch_num}: 异步私钥生成失败，结果为None"
            )
            return self._generate_private_keys_batch(self.batch_size)
        
        return gen_result[0]
    
    def _execute_gpu_batch(
        self,
        private_keys: bytes,
        batch_size: int,
        batch_num: int
    ) -> Tuple[List[Dict[str, int]], float]:
        """执行GPU batch计算
        
        Args:
            private_keys: 私钥字节串
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
        matches: List[Dict[str, int]] = self._gpu_kernel.run_batch(private_keys, batch_size)
        execution_time_ms = (time.time() - batch_start_time) * 1000
        
        if batch_num <= INITIAL_BATCHES_LOG or batch_num % BATCH_LOG_FREQUENCY == 0:
            logger.debug(f"GPU batch {batch_num}: 发现 {len(matches)} 个匹配")
        
        return matches, execution_time_ms
    
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
            
            from ..core.wif import WIF
            wif = WIF.encode(private_key, compressed=True)
            
            self.stats.add_match(private_key, address)
            if self.on_match:
                self.on_match(private_key, address, wif)
    
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
            self.on_progress(self.stats)
        self._save_checkpoint(batch_count)
        self._last_progress_time = current_time
        
        # 自适应性能优化
        if not hasattr(self, '_gpu_kernel') or not self._gpu_kernel:
            return
        
        try:
            error_rate = self.stats.gpu_error_count / max(batch_count, 1)
            
            new_batch_size, adjustments = self._gpu_kernel.gpu_optimizer.analyze_and_adjust(
                current_batch_size=current_batch_size,
                error_rate=error_rate
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
    
    def _range_scan(self, start: int, end: int):
        """范围扫描模式 - 流水线优化版本"""
        target_hash160s = self._target_hash160s
        num_targets = len(self._target_list)
        current = start
        batch_count = 0
        
        # 预生成第一批私钥
        batch_end = min(current + self.batch_size, end + 1)
        actual_batch_size = batch_end - current
        next_private_keys = b''.join(
            i.to_bytes(32, 'big') for i in range(current, batch_end)
        )
        next_batch_size = actual_batch_size
        
        while current <= end and not self._stop_event.is_set():
            # 使用预生成的私钥
            private_keys = next_private_keys
            actual_batch_size = next_batch_size
            
            # 更新当前位置
            current += actual_batch_size
            self._current_position = current
            
            # 预生成下一批（在 GPU 计算时进行）
            if current <= end:
                batch_end = min(current + self.batch_size, end + 1)
                next_batch_size = batch_end - current
                next_private_keys = b''.join(
                    i.to_bytes(32, 'big') for i in range(current, batch_end)
                )
            
            try:
                # 目标已在初始化时设置，无需重复传递
                matches = self._gpu_kernel.run_batch(private_keys, actual_batch_size)
                
                for match in matches:
                    key_idx = match["key_index"]
                    private_key = private_keys[key_idx*32:(key_idx+1)*32]
                    target_idx = match["target_index"]
                    address = self._target_list[target_idx]
                    
                    from ..core.wif import WIF
                    wif = WIF.encode(private_key, compressed=True)
                    
                    self.stats.add_match(private_key, address)
                    if self.on_match:
                        self.on_match(private_key, address, wif)
                
                # 只有 run_batch 成功后才递增计数
                batch_count += actual_batch_size
                self.stats.update(batch_count)
                
                current_time = time.time()
                if current_time - self._last_progress_time >= self._progress_interval_sec:
                    if self.on_progress:
                        self.stats._progress_percent = (current - start) / (end - start) * 100
                        self.on_progress(self.stats)
                    self._save_checkpoint(batch_count)
                    self._last_progress_time = current_time
                    
            except Exception as e:
                # 使用统一异常处理器处理GPU异常
                ExceptionHandler.handle_gpu_error("范围扫描", e, self.stats)
                continue
        
        self._running = False
        self.stats.update(batch_count)
        if self.on_complete:
            self.on_complete(self.stats)
    
    def _brute_force(self, start: int):
        """暴力穷举模式"""
        # 暴力穷举与范围扫描类似，只是结束条件不同
        self._range_start = start
        self._current_position = start
        
        target_hash160s = self._target_hash160s
        num_targets = len(self._target_list)
        current = start
        batch_count = 0
        
        while not self._stop_event.is_set():
            batch_end = current + self.batch_size
            
            private_keys = b''.join(
                i.to_bytes(32, 'big') for i in range(current, batch_end)
            )
            
            try:
                # 目标已在初始化时设置，无需重复传递
                matches = self._gpu_kernel.run_batch(private_keys, self.batch_size)
                
                for match in matches:
                    key_idx = match["key_index"]
                    private_key = private_keys[key_idx*32:(key_idx+1)*32]
                    target_idx = match["target_index"]
                    address = self._target_list[target_idx]
                    
                    from ..core.wif import WIF
                    wif = WIF.encode(private_key, compressed=True)
                    
                    self.stats.add_match(private_key, address)
                    if self.on_match:
                        self.on_match(private_key, address, wif)
                
                # 只有 run_batch 成功后才递增计数和更新位置
                batch_count += self.batch_size
                current = batch_end
                self._current_position = current
                
                self.stats.update(batch_count)
                
                current_time = time.time()
                if current_time - self._last_progress_time >= self._progress_interval_sec:
                    if self.on_progress:
                        self.on_progress(self.stats)
                    self._save_checkpoint(batch_count)
                    self._last_progress_time = current_time
                    
            except Exception as e:
                # 使用统一异常处理器处理GPU异常
                ExceptionHandler.handle_gpu_error("暴力穷举", e, self.stats)
                continue
        
        self._running = False
        self.stats.update(batch_count)
        if self.on_complete:
            self.on_complete(self.stats)
    
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
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout or 5)
        
        # 保存最终断点
        if self.checkpoint_mgr:
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
        
        # 停止监控系统
        if self.enhanced_monitoring:
            try:
                self.enhanced_monitoring.stop()
                logger.info("GPU引擎：增强监控系统已停止")
            except Exception as e:
                logger.error(f"GPU引擎：停止监控系统失败: {e}")
        
        # v2.2.1: 停止GPU性能监控器
        if self.gpu_performance_monitor:
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
        
        # 清理 GPU 资源
        if self._gpu_kernel:
            self._gpu_kernel.cleanup()
            self._gpu_kernel = None
        if self._gpu_context:
            self._gpu_context.cleanup()
            self._gpu_context = None
        if self._gpu_device:
            self._gpu_device.cleanup()
            self._gpu_device = None
        
        # 重置引擎状态（支持重启）
        self._stop_event.clear()
        self._running = False
        self._thread = None
        
        logger.info("GPU引擎：资源已清理")
    
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running and self._thread and self._thread.is_alive()
    
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
        if not self.benchmark_suite:
            logger.warning("基准测试套件未初始化")
            return {}
        
        logger.info("\n" + "="*60)
        logger.info("🚀 开始运行 GPU 性能基准测试")
        logger.info("="*60)
        
        results = self.benchmark_suite.run_all_benchmarks(iterations)
        
        # 显示结果
        summary = self.benchmark_suite.get_summary(results)
        logger.info("\n" + summary)
        
        # 保存报告
        if save_report:
            report_path = self.generate_performance_report(
                include_benchmarks=True,
                include_tuning=False,
                include_recommendations=True
            )
            logger.info(f"\n📄 基准测试报告已保存: {report_path}")
        
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
        
        if not self.auto_tuner:
            logger.warning("自动调优器未初始化")
            return {}
        
        # 保存原始 batch_size
        original_batch_size = self.batch_size
        logger.info(f"📌 当前 batch_size: {original_batch_size:,}")
        
        logger.info("\n" + "="*60)
        logger.info("🎯 开始自动调优")
        logger.info("="*60)
        
        # 调优回调：更新 batch_size（仅在 auto_apply=True 时）
        def on_new_batch_size(new_size):
            if auto_apply:
                old_size = self.batch_size
                self.batch_size = new_size
                logger.info(f"🔄 自动更新 batch_size: {old_size:,} -> {new_size:,}")
            else:
                logger.info(f"💡 建议 batch_size: {new_size:,} (当前: {self.batch_size:,})")
        
        results = self.auto_tuner.start_tuning(
            max_iterations=max_iterations,
            callback=on_new_batch_size
        )
        
        # 显示结果
        optimal_size = results.get('optimal_batch_size')
        logger.info(f"\n✅ 调优完成！")
        logger.info(f"   最优 batch_size: {optimal_size:,}")
        logger.info(f"   预期吞吐量: {results.get('expected_throughput', 0):,.0f} keys/s")
        logger.info(f"   调优周期: {results.get('tuning_cycles', 0)}")
        
        if not auto_apply and optimal_size:
            logger.info(f"   💡 要应用此配置，请使用: engine.batch_size = {optimal_size:,}")
        
        # 保存报告
        if save_report:
            report_path = self.generate_performance_report(
                include_benchmarks=False,
                include_tuning=True,
                include_recommendations=True
            )
            logger.info(f"\n📄 调优报告已保存: {report_path}")
        
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
        if not self.performance_reporter:
            logger.warning("性能报告生成器未初始化")
            return ""
        
        logger.info("\n" + "="*60)
        logger.info("📊 生成 GPU 性能报告")
        logger.info("="*60)
        
        report_path = self.performance_reporter.generate_report(
            config=ReportConfig(
                include_device_info=True,
                include_benchmark_results=include_benchmarks,
                include_tuning_results=include_tuning,
                include_history=include_history,
                include_recommendations=include_recommendations,
                include_comparison=include_comparison
            ),
            output_dir=output_dir
        )
        
        return report_path
