"""GPU加速的比特币私钥对撞引擎

基于 OpenCL 的 GPU 加速实现，利用 GPU 并行计算能力进行批量私钥碰撞检测。
"""

import os
import sys
import time
import threading
import secrets
import logging
from typing import Set, Optional, Callable, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# 导入新GPU模块
from ..gpu.device import GPUDevice, GPUDeviceDetector
from ..gpu.context import GPUContext
from ..gpu.profiles.loader import GPUProfileLoader
from ..gpu.kernel import OPENCL_KERNEL_SOURCE
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


class GPUDeviceHelper:
    """GPU设备辅助类 - 提供静态方法供GPUKernel使用"""
    
    @staticmethod
    def handle_gpu_batch_error(mode: str, e: Exception, stats=None):
        """统一处理GPU计算批次异常
        
        Args:
            mode: 计算模式（随机碰撞/范围扫描/暴力穷举）
            e: 捕获的异常
            stats: 统计对象（可选）
            
        Returns:
            bool: 是否应该继续执行（总是返回True）
        """
        if isinstance(e, (RuntimeError, ValueError)):
            # OpenCL运行时错误或数据验证错误
            # 这些是可恢复的错误，跳过当前批次继续执行
            # 常见原因：GPU内存不足、内核参数错误、目标地址格式错误
            error_msg = str(e).lower()
            # 扩展资源不足关键词匹配，覆盖不同OpenCL实现的错误消息
            resource_keywords = [
                "out of resources", "memory", "out of memory", 
                "allocation failed", "insufficient", "resource exhausted",
                "cl_out_of_resources", "cl_mem_object_allocation_failure"
            ]
            is_resource_error = any(keyword in error_msg for keyword in resource_keywords)
            if is_resource_error:
                logger.error(f"GPU {mode}失败（资源不足）: {type(e).__name__}: {e}")
                if stats:
                    stats.record_gpu_error(is_resource_error=True)
            else:
                logger.error(f"GPU {mode}失败（运行时错误）: {type(e).__name__}: {e}")
                if stats:
                    stats.record_gpu_error(is_resource_error=False)
        elif isinstance(e, (TypeError, OverflowError)):
            # WIF编码或数据处理错误
            logger.error(f"GPU {mode}失败（数据错误）: {type(e).__name__}: {e}")
            if stats:
                stats.record_gpu_error(is_resource_error=False)
                stats.record_wif_encode_error()
        else:
            # 未知错误：记录完整堆栈
            logger.exception(f"GPU {mode}失败（未知错误）")
            if stats:
                stats.record_gpu_error(is_resource_error=False)
        return True  # 总是继续执行


class GPUKernel:
    """OpenCL GPU 计算内核包装 - 优化版本
    
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
        """编译 OpenCL 内核"""
        try:
            # 使用新模块的内核源码
            self.program = cl.Program(self.device.context, OPENCL_KERNEL_SOURCE).build()
            logger.info("OpenCL 内核编译成功")
        except Exception as e:
            # 编译失败或其他错误
            logger.error(f"OpenCL 内核编译失败: {type(e).__name__}: {e}")
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
                 use_enhanced_monitoring: bool = True):
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
        """
        with EnhancedPerformanceMonitor(logger, "GPU引擎初始化", level="INFO") as pm:
            try:
                if not GPUDevice.is_available():
                    raise RuntimeError("pyopencl 不可用")
                
                # 1. 初始化GPU设备
                with EnhancedPerformanceMonitor(logger, "GPU设备初始化", level="DEBUG"):
                    self._gpu_device = GPUDevice()
                    self._gpu_device.initialize(self.device_index)
                
                # 2. 加载GPU型号配置
                device_info = self._gpu_device.get_device_info()
                device_name = device_info.get('name', '')
                vendor = device_info.get('vendor', '')
                
                logger.info(f"检测到GPU设备: {device_name} ({vendor})")
                
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
                
                # 5. 应用厂商优化
                with EnhancedPerformanceMonitor(logger, "GPU厂商优化应用", level="DEBUG"):
                    self._gpu_context.apply_optimizations()
                
                # 6. 计算最优batch_size（如果未指定）
                if self.batch_size is None:
                    self.batch_size = self._gpu_context.calculate_batch_size()
                    logger.info(
                        f"自动设置 batch_size: {self.batch_size} "
                        f"(基于GPU型号配置和显存计算)"
                    )
                else:
                    logger.debug(f"使用指定的 batch_size: {self.batch_size}")
                
                # 7. 使用GPUContext编译内核（应用厂商编译选项）
                with EnhancedPerformanceMonitor(logger, "OpenCL内核编译", level="INFO"):
                    self._gpu_context.compile_kernel(OPENCL_KERNEL_SOURCE)
                
                # 8. 创建GPUKernel（使用已编译的程序）
                with EnhancedPerformanceMonitor(logger, "GPUKernel创建", level="DEBUG"):
                    self._gpu_kernel = GPUKernel(
                        self._gpu_device, 
                        max_batch_size=self.batch_size,
                        program=self._gpu_context.program
                    )
                
                # 9. 预转换目标地址为 Hash160
                with EnhancedPerformanceMonitor(logger, "目标地址转换", level="DEBUG"):
                    self._prepare_targets()
                
                # 10. 设置 GPU 目标地址缓冲区
                if self._target_hash160s:
                    self._gpu_kernel.set_targets(self._target_hash160s, len(self._target_list))
                
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
    
    @staticmethod
    def is_gpu_available() -> bool:
        """检查 GPU 是否可用"""
        if not PYOPENCL_AVAILABLE:
            return False
        try:
            devices = GPUDevice.detect_devices()
            return len(devices) > 0
        except (ImportError, RuntimeError, OSError) as e:
            # 预期的设备检测异常
            logger.debug(f"GPU检测失败: {type(e).__name__}: {e}")
            return False
        except Exception as e:
            # 未知错误：记录日志
            logger.warning(f"GPU检测未知错误: {type(e).__name__}: {e}")
            return False
    
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
        """
        import threading
        
        logger.info("GPU _random_search 启动（高性能模式）")
        target_hash160s = self._target_hash160s
        num_targets = len(self._target_list)
        batch_count = 0
        batch_num = 0
        
        logger.info(f"目标数量: {num_targets}, batch_size: {self.batch_size}")
        
        # 优化1: 增加初始批次到100万（提高GPU利用率）
        INITIAL_BATCH_SIZE = 1_000_000  # 100万（原10万）
        current_batch_size = min(INITIAL_BATCH_SIZE, self.batch_size)
        
        logger.info(f"初始批次大小: {current_batch_size:,}")
        
        # 预生成第一批私钥
        logger.debug(f"生成初始批次 {current_batch_size:,} 个私钥...")
        next_private_keys = b''.join(secrets.token_bytes(32) for _ in range(current_batch_size))
        
        # 优化2: 异步私钥生成函数
        def generate_next_batch_async(batch_size: int) -> threading.Thread:
            """在后台线程生成下一批私钥"""
            result = [None]  # 使用列表存储结果（闭包）
            
            def _generate():
                result[0] = b''.join(secrets.token_bytes(32) for _ in range(batch_size))
            
            thread = threading.Thread(target=_generate, daemon=True)
            thread.start()
            return thread, result
        
        # 启动第一个异步生成线程（生成完整batch_size）
        gen_thread, gen_result = generate_next_batch_async(self.batch_size)
        logger.debug(f"启动异步私钥生成线程（目标: {self.batch_size:,} 个）")
        
        while not self._stop_event.is_set():
            # 使用预生成的私钥
            private_keys = next_private_keys
            actual_batch_size = len(private_keys) // 32
            
            try:
                batch_num += 1
                if batch_num <= 3 or batch_num % 100 == 0:
                    logger.debug(f"GPU batch {batch_num}: 运行 run_batch (size={actual_batch_size})...")
                
                # 目标已在初始化时设置，无需重复传递
                matches = self._gpu_kernel.run_batch(private_keys, actual_batch_size)
                
                # GPU计算完成后，等待异步生成完成并获取下一批
                if gen_thread.is_alive():
                    # 使用超时保护（生成838万私钥最多需要30秒）
                    gen_thread.join(timeout=30.0)
                    
                    if gen_thread.is_alive():
                        logger.error(f"GPU batch {batch_num}: 异步私钥生成超时（>30秒），强制继续")
                        # 重新同步生成作为fallback
                        next_private_keys = b''.join(secrets.token_bytes(32) for _ in range(self.batch_size))
                    else:
                        # 检查生成结果是否有效
                        if gen_result[0] is None:
                            logger.error(f"GPU batch {batch_num}: 异步私钥生成失败，结果为None")
                            # 重新同步生成
                            next_private_keys = b''.join(secrets.token_bytes(32) for _ in range(self.batch_size))
                        else:
                            next_private_keys = gen_result[0]
                else:
                    # 线程已结束，检查结果
                    if gen_result[0] is None:
                        logger.error(f"GPU batch {batch_num}: 异步私钥生成失败，结果为None")
                        next_private_keys = b''.join(secrets.token_bytes(32) for _ in range(self.batch_size))
                    else:
                        next_private_keys = gen_result[0]
                
                # 立即启动下一批的异步生成
                gen_thread, gen_result = generate_next_batch_async(self.batch_size)
                
                if batch_num <= 3 or batch_num % 100 == 0:
                    logger.debug(f"GPU batch {batch_num}: 发现 {len(matches)} 个匹配")
                
                # 处理匹配结果
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
                
                # 只有 run_batch 成功后才递增计数
                batch_count += actual_batch_size
                self.stats.update(batch_count)
                
                # 进度回调
                current_time = time.time()
                if current_time - self._last_progress_time >= self._progress_interval_sec:
                    logger.debug(f"GPU 进度回调: batch_count={batch_count}")
                    if self.on_progress:
                        self.on_progress(self.stats)
                    self._save_checkpoint(batch_count)
                    self._last_progress_time = current_time
                    
            except Exception as e:
                # 使用统一异常处理器处理GPU异常
                ExceptionHandler.handle_gpu_error("随机碰撞", e, self.stats)
                
                # 异常恢复：重新启动异步生成，避免使用旧的/可能损坏的结果
                logger.warning(f"GPU batch {batch_num}: 异常恢复，重新启动异步私钥生成")
                gen_thread, gen_result = generate_next_batch_async(self.batch_size)
                
                continue
        
        logger.info(f"GPU _random_search 结束: 共处理 {batch_count} 个私钥")
        self._running = False
        self.stats.update(batch_count)
        if self.on_complete:
            self.on_complete(self.stats)
    
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
                logger.info("GPU引擎：监控系统已停止")
            except Exception as e:
                logger.error(f"GPU引擎：停止监控系统失败: {e}")
        
        # 清理 GPU 资源
        if self._gpu_kernel:
            self._gpu_kernel.cleanup()
        if self._gpu_context:
            self._gpu_context.cleanup()
        if self._gpu_device:
            self._gpu_device.cleanup()
        
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
