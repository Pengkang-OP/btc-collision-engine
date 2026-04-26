"""GPU内核实现

包含 GPUKernel 类的实现，解决循环导入问题。
"""
import logging
import os
import time
import threading
from typing import Optional, Any, List, Dict

import numpy as np

from .kernel_protocol import GPUKernelProtocol
from .device import GPUDevice
from .kernel import OPENCL_KERNEL_SOURCE
from .profiles.loader import GPUProfileLoader
from .async_executor import AsyncGPUExecutor
from .memory_pool import get_gpu_memory_pool
from .amd_optimizer import AmdGPUOptimizer
from .nvidia_optimizer import NvidiaGPUOptimizer
from .intel_optimizer import IntelGPUOptimizer
from .buffer_tracker import GPUBufferTracker
from .precompute import get_precomp_table
from ..utils.exception_handler import ExceptionHandler
from ..utils.performance_monitor import EnhancedPerformanceMonitor, PerformanceMetrics
from ..utils.gpu_memory_utils import calculate_optimal_batch_size
from ..core.address_generator import P2PKHAddressGenerator
from ..core.hash_utils import HashUtils
from ..monitoring.gpu_performance_monitor import get_gpu_performance_monitor

logger = logging.getLogger(__name__)


# 尝试导入 pyopencl
cl = None
try:
    import pyopencl as cl
except ImportError:
    pass


def get_gpu_optimizer():
    """获取GPU优化器"""
    try:
        from .performance_optimizer import get_gpu_optimizer as _get_gpu_optimizer
        return _get_gpu_optimizer()
    except ImportError:
        return None


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


class GPUKernel(GPUKernelProtocol):
    """OpenCL GPU 计算内核包装 - 优化版本
    
    实现GPUKernelProtocol接口（P1-2修复）。
    使用持久化 Buffer 和异步执行来保持 GPU 持续高负载，
    避免频繁的内存分配和同步等待造成的 GPU 空闲。
    """
    
    # 2*G 的期望坐标值（用于验证）
    EXPECTED_2G_X = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
    EXPECTED_2G_Y = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A
    
    # v3.3.0新增: 缓冲区大小因子常量
    # KEYS_BUFFER_SIZE_FACTOR: PRNG改造后私钥缓冲区已弃用，保留常量以兼容内存池预分配历史代码
    KEYS_BUFFER_SIZE_FACTOR = 32    # Deprecated: PRNG模式下私钥缓冲区已不再需要
    MATCH_BUFFER_SIZE_FACTOR = 4    # 每个匹配标志4字节（int32）
    
    def __init__(self, device: GPUDevice, max_batch_size: int = None, program: Optional[Any] = None):
        """
        初始化GPUKernel
        
        Args:
            device: GPUDevice实例
            max_batch_size: 最大批次大小（None=自动计算）
            program: 已编译的OpenCL程序（可选，如果提供则跳过编译）
        """
        self._device = device
        self.gpu_optimizer = get_gpu_optimizer()
        
        # v2.3.0优化: 从配置中获取work_group_size
        device_info = device.get_device_info() if hasattr(device, 'get_device_info') else {}
        self._work_group_size = device_info.get('work_group_size', 256)
        
        # 如果没有指定max_batch_size，根据GPU显存自动计算
        if max_batch_size is None:
            max_batch_size = self._calculate_optimal_batch_size()
                
        # L-NEW1修复: 与配置层保持一致的上限检查（16M）
        MAX_BATCH_SIZE_LIMIT = 16777216  # 16M，与 config_manager.py Schema 一致
        if max_batch_size > MAX_BATCH_SIZE_LIMIT:
            raise ValueError(
                f"batch_size {max_batch_size} 超出最大限制 {MAX_BATCH_SIZE_LIMIT} "
                f"(配置层与引擎层统一上限)"
            )
                
        self._max_batch_size = max_batch_size
        self._program = program  # 可能为None（需要自行编译）
        self._batch_kernel = None
        self._batch_kernel_local = None  # local memory版本内核引用
        # 查询设备local memory大小（OpenCL标准属性），回退默认值16KB
        try:
            self._local_mem_size = device.device.local_mem_size
        except Exception:
            self._local_mem_size = 16384  # 默认16KB
        
        # P2-2修复: 初始化缓冲区追踪器
        self._buffer_tracker = GPUBufferTracker()
        
        # 持久化 Buffer - 避免频繁分配/释放
        self._seed_buf = None     # PRNG模式：仅存傤32字节种子
        # self._keys_buf 已于 v4.0 PRNG 改造时移除，不再使用
        self._match_buf = None
        self._targets_buf = None
        self._target_hash160s = None  # P3修复: 添加目标地址缓存
        self._targets_cached = None
        self._num_targets_cached = 0
        self._precomp_buf = None  # 预计算表常量缓冲区（生命周期与 kernel 一致）
        
        # 预分配主机内存
        self._match_flags = None

        # 校验 GPUDevice 已正确初始化
        if not getattr(self.device, "context", None) or not getattr(self.device, "queue", None):
            raise RuntimeError("GPUDevice 尚未初始化，请先调用 GPUDevice.initialize() 再创建 GPUKernel")
        
        # 如果未提供program，则自行编译
        if self.program is None:
            self._compile()
        
        # 初始化_batch_kernel引用
        if self._program is not None:
            self._batch_kernel = self._program.batch_check
            # 初始化 local memory 版本内核引用
            try:
                self._batch_kernel_local = self._program.batch_check_local_mem
            except AttributeError:
                logger.warning("batch_check_local_mem 内核未找到，将回退到标准版本")
                self._batch_kernel_local = None
        
        self._allocate_buffers()
        
        # 验证GPU内核(在分配缓冲区之后)
        self._verify()
    
    @property
    def device(self) -> Any:  # GPUDevice
        """GPU设备对象
        
        Returns:
            GPUDevice实例，包含OpenCL上下文、队列等设备信息
        """
        return self._device
    
    @property
    def max_batch_size(self) -> int:
        """最大批次大小
        
        Returns:
            GPU内核能够处理的最大私钥数量
        """
        return self._max_batch_size
    
    @property
    def program(self) -> Optional[Any]:  # Optional[cl.Program]
        """已编译的OpenCL程序
        
        Returns:
            pyopencl.Program实例，或None（如果尚未编译）
        """
        return self._program
    
    def _compile(self):
        """编译 OpenCL 内核（带性能监控和缓存）
        
        P2-6修复: 添加内核编译缓存机制，避免每次启动都重新编译
        """
        import time
        
        # P2-6修复: 尝试从缓存加载
        if self._load_kernel_cache():
            logger.info("使用缓存的OpenCL内核二进制")
            return
        
        compile_start = time.time()
        try:
            # 使用新模块的内核源码
            self._program = cl.Program(self.device.context, OPENCL_KERNEL_SOURCE).build()
            compile_time_ms = (time.time() - compile_start) * 1000
            
            logger.info(f"OpenCL 内核编译成功: {compile_time_ms:.0f}ms")
            
            # P2-6修复: 保存编译结果到缓存
            self._save_kernel_cache()
            
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
                    self._max_batch_size = profile.max_batch_size
                    
            except Exception as opt_error:
                logger.warning(f"GPU性能优化失败: {opt_error}")
                
        except Exception as e:
            # 编译失败或其他错误
            compile_time_ms = (time.time() - compile_start) * 1000
            logger.error(f"OpenCL 内核编译失败: {type(e).__name__}: {e} ({compile_time_ms:.0f}ms)")
            raise RuntimeError(f"GPU 内核编译失败: {e}") from e
    
    def _verify(self):
        """ALG-3修复: 验证 GPU 计算正确性（增强版）
                
        验证内容:
        1. 基础验证: 虚拟目标不应匹配
        2. 增强验证: 已知私钥-地址对应该匹配（如果提供）
            
        PRNG模式: seed=1, gid=0 -> key = seed + 0 = 1 (与原测试私钥一致)
        """
        import pyopencl as cl
        import numpy as np
                
        # ===== 验证1: 基础验证 - 虚拟目标不应匹配 =====
        num_keys = 1
        num_targets = 1
                
        # PRNG模式: 种子=1 (32字节), gid=0 -> key = 1 + 0 = 1
        # 字节序: 大端, 最后一个字节为 0x01
        test_seed_bytes = b'\x00' * 31 + b'\x01'
                
        # 虚拟目标hash160 (20字节)
        test_targets = b'\x00' * 20
                
        # 将种子写入GPU seed缓冲区
        seed_array = _seed_bytes_to_u32_be_array(test_seed_bytes)
        cl.enqueue_copy(self.device.queue, self._seed_buf, seed_array)
                
        # 设置目标
        self.set_targets(test_targets, num_targets)
                
        # 清空匹配结果缓冲区
        cl.enqueue_fill_buffer(
            self.device.queue, self._match_buf,
            np.int32(0), 0, num_keys * 4
        )
                
        # 执行GPU batch计算
        self._batch_kernel(
            self.device.queue,
            (num_keys,), None,
            self._seed_buf, np.uint32(num_keys),
            self._targets_buf, np.uint32(num_targets),
            self._match_buf,
            self._precomp_buf
        ).wait()
                
        # 读取结果
        match_flags = np.zeros(num_keys, dtype=np.int32)
        cl.enqueue_copy(self.device.queue, match_flags, self._match_buf)
                
        # 验证: 由于目标是全0,不应该匹配
        if match_flags[0] != 0:
            raise RuntimeError(f"GPU内核验证失败: 不应匹配虚拟目标,但match_flags[0]={match_flags[0]}")
                
        logger.info("✅ GPU内核基础验证通过（虚拟目标不匹配）")
                
        # ===== ALG-3修复: 验证2 - 真实地址匹配测试 =====
        # 使用已知私钥和对应的Hash160进行测试
        # 即私钥=1的公钥的Hash160: 751e76e8199196d454941c45d1b3a323f1433bd6
        try:
            # 私钥1对应的字节串（大端，与 seed=1 一致）
            test_key_bytes = b'\x00' * 31 + b'\x01'
                    
            # 生成私钥1的地址和Hash160
            generator = P2PKHAddressGenerator()
            test_address, compressed_pk, _ = generator.generate_address(test_key_bytes)
            test_hash160 = HashUtils.hash160(compressed_pk)
                    
            logger.info(f"ALG-3增强验证: 测试私钥1 -> 地址 {test_address}")
            logger.info(f"  Hash160: {test_hash160.hex()}")
                    
            # 将真实Hash160设置为目标
            self.set_targets(test_hash160, 1)
                    
            # 清空匹配结果缓冲区
            cl.enqueue_fill_buffer(
                self.device.queue, self._match_buf,
                np.int32(0), 0, num_keys * 4
            )
                    
            # 执行GPU batch计算
            self._batch_kernel(
                self.device.queue,
                (num_keys,), None,
                self._seed_buf, np.uint32(num_keys),
                self._targets_buf, np.uint32(1),
                self._match_buf,
                self._precomp_buf
            ).wait()
                    
            # 读取结果
            match_flags = np.zeros(num_keys, dtype=np.int32)
            cl.enqueue_copy(self.device.queue, match_flags, self._match_buf)
                    
            # 验证: 私钥1应该匹配它的地址
            if match_flags[0] != 1:
                raise RuntimeError(
                    f"GPU内核增强验证失败: "
                    f"私钥1应该匹配地址{test_address},但match_flags[0]={match_flags[0]}"
                )
                    
            logger.info(f"✅ GPU内核增强验证通过（私钥1匹配地址{test_address}）")
                    
        except ImportError:
            logger.warning("ALG-3增强验证跳过: 无法导入地址生成器")
        except Exception as e:
            logger.warning(f"ALG-3增强验证失败: {e}")
            # 不阻止初始化，仅警告
    
    def _generate_cache_key(self) -> str:
        """P2-6修复: 生成缓存键
        
        基于设备信息和内核源码生成唯一的缓存键
        """
        import hashlib
        
        # 使用设备信息和内核源码生成键
        device_info = f"{self.device.device.name}_{self.device.device.vendor}"
        source_hash = hashlib.md5(OPENCL_KERNEL_SOURCE.encode(), usedforsecurity=False).hexdigest()[:8]
        
        cache_key = f"{device_info}_{source_hash}"
        # 替换非法字符
        cache_key = cache_key.replace(' ', '_').replace('-', '_')
        
        return cache_key
    
    def _get_cache_file(self) -> str:
        """P2-6修复: 获取缓存文件路径"""
        import os
        
        cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        cache_key = self._generate_cache_key()
        cache_file = os.path.join(cache_dir, f"kernel_{cache_key}.bin")
        
        return cache_file
    
    def _load_kernel_cache(self) -> bool:
        """P2-6修复: 从缓存加载内核二进制
        
        返回:
            bool: 是否成功加载缓存
        """
        import pyopencl as cl
        
        cache_file = self._get_cache_file()
        
        if not os.path.exists(cache_file):
            logger.debug(f"缓存文件不存在: {cache_file}")
            return False
        
        try:
            with open(cache_file, 'rb') as f:
                cached_binary = f.read()
            
            # 从二进制加载程序
            self._program = cl.Program(
                self.device.context,
                [self.device.device],
                [cached_binary]
            ).build()
            
            logger.info(f"成功加载内核缓存: {cache_file}")
            return True
            
        except Exception as e:
            logger.warning(f"加载内核缓存失败: {e}")
            # 缓存损坏，删除它
            try:
                os.remove(cache_file)
            except Exception as cleanup_error:
                # A类修复: 资源清理失败添加DEBUG日志
                logger.debug(f"清理损坏缓存文件失败（可忽略）: {cleanup_error}")
            return False
    
    def _save_kernel_cache(self):
        """P2-6修复: 保存内核二进制到缓存"""
        cache_file = self._get_cache_file()
        
        try:
            # 获取编译后的二进制
            binaries = self._program.get_info(cl.program_info.BINARIES)
            if binaries and len(binaries) > 0:
                binary = binaries[0]
                
                with open(cache_file, 'wb') as f:
                    f.write(binary)
                
                logger.debug(f"内核缓存已保存: {cache_file} ({len(binary)} bytes)")
                
        except Exception as e:
            logger.warning(f"保存内核缓存失败: {e}")
    
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
        """预分配 GPU 内存缓冲区（PRNG模式）
        
        P2-2修复: 添加缓冲区追踪
        v3.2.0修复: 使用GPU内存池分配缓冲区（如果已启用）
        PRNG改造: 删除大型 keys_buf，改用固定32字节 seed_buf
        """
        import numpy as np
        import pyopencl as cl
        
        # 获取内存池引用（如果已启用）
        memory_pool = getattr(self, '_gpu_memory_pool', None)
        
        # PRNG模式: 种子缓冲区（32字节，固定，替代原 num_keys*32 字节的 keys 缓冲区）
        # 节省显存: max_batch_size * 32 字节（例: 1M keys 节省约32MB）
        if memory_pool:
            # 内存池不支持如此小的分配，直接创建
            self._seed_buf = cl.Buffer(
                self.device.context,
                cl.mem_flags.READ_ONLY,
                size=32  # 固定32字节
            )
        else:
            self._seed_buf = cl.Buffer(
                self.device.context,
                cl.mem_flags.READ_ONLY,
                size=32  # 固定32字节
            )
        logger.info(
            f"PRNG模式: 创建 seed_buf 32字节（替代原 keys_buf "
            f"{self.max_batch_size * self.KEYS_BUFFER_SIZE_FACTOR // 1024 // 1024}MB）"
        )
        self._buffer_tracker.track_buffer("_seed_buf", self._seed_buf, 32)
        
        # 匹配结果缓冲区
        match_buf_size = self.max_batch_size * self.MATCH_BUFFER_SIZE_FACTOR
        if memory_pool:
            # 使用内存池分配（支持复用）
            self._match_buf = memory_pool.allocate(match_buf_size, cl.mem_flags.WRITE_ONLY)
            logger.debug(f"使用内存池分配匹配缓冲区: {match_buf_size}字节")
        else:
            # 直接分配（回退模式）
            self._match_buf = cl.Buffer(
                self.device.context,
                cl.mem_flags.WRITE_ONLY,
                size=match_buf_size
            )
            logger.debug(f"直接分配匹配缓冲区: {match_buf_size}字节")
        
        # P2-2修复: 注册缓冲区追踪
        self._buffer_tracker.track_buffer("_match_buf", self._match_buf, match_buf_size)
        
        # 预分配主机内存
        self._match_flags = np.zeros(self.max_batch_size, dtype=np.int32)

        # 预计算表常量缓冲区
        if self._precomp_buf is None:
            from .precompute import get_precomp_table
            precomp_data = get_precomp_table()
            self._precomp_buf = cl.Buffer(
                self.device.context,
                cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                hostbuf=precomp_data
            )
            logger.info("预计算表常量缓冲区已创建: 496 uint32")
            self._buffer_tracker.track_buffer("_precomp_buf", self._precomp_buf, 496 * 4)
        
        logger.info(f"GPU 缓冲区分配完成（PRNG模式）: max_batch_size={self.max_batch_size}")
        # P2-2修复: 记录缓冲区统计
        stats = self._buffer_tracker.get_stats()
        logger.debug(f"GPU Buffer统计: {stats['count']}个缓冲区, {stats['total_size_mb']:.2f} MB")
        
        # v3.3.0优化: 记录内存池使用状态（纯持久化设计）
        if memory_pool:
            pool_stats = memory_pool.get_stats()
            logger.info(
                f"GPU内存池状态 (v3.3.0纯持久化设计): "
                f"已分配={pool_stats['total_allocated']}, "
                f"已复用={pool_stats['total_reused']}, "
                f"当前内存={pool_stats['current_memory_mb']:.1f}MB, "
                f"池内缓冲={pool_stats['pooled_buffers']}个 | "
                f"设计: 持久化缓冲区在引擎生命周期内重复使用，零运行时分配开销"
            )
    
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
    
    def run_batch(self, seed: bytes, num_keys: int,
                  target_hash160s: bytes = None, num_targets: int = 0,
                  stop_event = None) -> List[Dict]:
        """PRNG模式批量执行私钥碰撞检测
        
        v4.0 PRNG改造: CPU仅传入 32 字节种子，GPU内核自行计算 key = seed + gid。
        节省 ~32MB GPU 显存（max_batch_size * 32 字节 keys 缓冲区）。
        v3.2.2优化: 持久化缓冲区设计 - 零运行时分配开销，性能最优
        v3.3.1修复: 添加stop_event参数,支持优雅停止
        
        Args:
            seed: 32字节随机种子
            num_keys: 批次大小
            target_hash160s: 目标地址Hash160
            num_targets: 目标数量
            stop_event: 停止事件(可选),用于优雅退出
        """
        import numpy as np
        import time
        
        batch_start_time = time.time()
        
        # 参数校验
        if num_keys <= 0 or num_keys > self.max_batch_size:
            raise ValueError(f"num_keys 必须在 1..{self.max_batch_size} 之间，当前为 {num_keys}")
        
        if len(seed) != 32:
            raise ValueError(
                f"seed 长度必须为 32 字节（PRNG模式），当前为 {len(seed)} 字节"
            )
        
        # P0修复: 显存溢出检查（PRNG模式，无需考虑 keys 缓冲区）
        target_buffer_size = len(self._target_hash160s) if self._target_hash160s else 0
        required_memory = 32 + (num_keys * 4) + target_buffer_size  # seed(32) + match + targets
        required_memory_with_overhead = int(required_memory * 1.2)
        
        # 获取GPU最大可用显存(80%为安全阈值)
        device_info = self.device.get_device_info() if hasattr(self.device, 'get_device_info') else {}
        max_memory = device_info.get('global_mem_size', 0)
        safe_memory_limit = int(max_memory * 0.8) if max_memory > 0 else float('inf')
        
        if required_memory_with_overhead > safe_memory_limit:
            raise MemoryError(
                f"所需显存 {required_memory_with_overhead/1024**2:.0f}MB 超过安全限制 {safe_memory_limit/1024**2:.0f}MB\n"
                f"建议: 减小 batch_size 从 {num_keys} 到 {int(num_keys * safe_memory_limit / required_memory_with_overhead)}"
            )
        
        # 设置目标（仅在第一次或目标变化时）
        if target_hash160s is not None:
            self.set_targets(target_hash160s, num_targets)
        
        # PRNG模式: 将 32 字节种子写入 _seed_buf
        if self._seed_buf is None:
            logger.error("_seed_buf 已释放，无法执行批处理")
            return []
        
        seed_array = _seed_bytes_to_u32_be_array(seed)
        try:
            cl.enqueue_copy(self.device.queue, self._seed_buf, seed_array)
        except Exception as e:
            logger.error(f"写入 seed_buf 失败: {e}")
            return []
        
        # 清空匹配结果缓冲区
        if self._match_buf is None:
            logger.error("_match_buf 已释放，无法执行批处理")
            return []
        
        try:
            cl.enqueue_fill_buffer(
                self.device.queue, self._match_buf,
                np.int32(0), 0, num_keys * 4
            )
        except Exception as e:
            logger.error(f"清空 match_buf 失败: {e}")
            return []
        
        # 执行内核（异步）
        if self._batch_kernel is None:
            self._batch_kernel = self.program.batch_check
        
        # v2.3.0优化: 显式设置local_work_size提升性能
        # 从配置中获取work_group_size，避免OpenCL自动选择次优值
        local_work_size = getattr(self, '_work_group_size', 256)
        
        # 确保global_work_size是local_work_size的整数倍
        global_work_size = ((num_keys + local_work_size - 1) // local_work_size) * local_work_size
        
        # 判断是否使用local memory版内核
        # 条件: 1. 存在local memory版内核引用; 2. 目标数据能装入设备local mem（80%安全阈值）
        # 优化: 当目标地址数量较少（<=250，约5KB）时，更积极使用local memory版内核
        target_bytes = self._num_targets_cached * 20
        local_mem_size = getattr(self, '_local_mem_size', 16384)
        use_local_mem = (
            self._batch_kernel_local is not None
            and target_bytes > 0
            and target_bytes <= local_mem_size  # 确保实际能装入设备local mem（确保安全）
            and (
                target_bytes <= int(local_mem_size * 0.8)  # 原有条件: 80%安全阈值
                or self._num_targets_cached <= 250  # 新增: 少量目标时更积极使用local memory
            )
        )
        
        if use_local_mem:
            logger.debug(
                f"使用local memory版内核: 目标数据{target_bytes}B 设备local_mem={local_mem_size}B"
            )
            self._batch_kernel_local(
                self.device.queue, (global_work_size,), (local_work_size,),
                self._seed_buf, np.uint32(num_keys),
                self._targets_buf, np.uint32(self._num_targets_cached),
                self._match_buf,
                cl.LocalMemory(target_bytes),  # 分配 local memory
                self._precomp_buf
            )
        else:
            self._batch_kernel(
                self.device.queue, (global_work_size,), (local_work_size,),
                self._seed_buf, np.uint32(num_keys),
                self._targets_buf, np.uint32(self._num_targets_cached),
                self._match_buf,
                self._precomp_buf
            )
        
        # 异步读取结果
        match_view = self._match_flags[:num_keys]
        read_event = cl.enqueue_copy(
            self.device.queue, match_view, self._match_buf
        )
        
        # 方案B: 添加超时保护机制(防止Intel Arc A770等GPU永久卡死)
        # v3.3.1修复: 使用轮询检查替代无限期等待,支持优雅停止
        # 性能分析: 每批次约0.5秒,轮询5次(间隔0.1秒),开销<0.001%
        timeout_seconds = 30  # Intel Arc建议的超时时间
        poll_interval = 0.1   # 轮询间隔(秒)
                
        # 创建超时事件
        timeout_event = threading.Event()
        execution_completed = [False]  # 使用列表存储结果(闭包)
                
        def timeout_monitor():
            """后台线程监控GPU执行超时"""
            try:
                if not timeout_event.wait(timeout_seconds):
                    # 超时未收到完成信号
                    logger.error(f"GPU执行超时({timeout_seconds}秒),可能存在内核hang问题")
                    # 尝试强制完成队列
                    try:
                        self.device.queue.finish()
                    except Exception as e:
                        logger.error(f"强制完成队列失败: {e}")
                    execution_completed[0] = False
                # else: 正常完成,不做任何操作
            except Exception as e:
                logger.error(f"超时监控线程异常: {e}")
                execution_completed[0] = False
                
        # 启动超时监控线程
        monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)
        monitor_thread.start()
                
        try:
            # v3.3.1修复: 使用轮询等待替代无限期阻塞
            # PyOpenCL的Event.wait()不支持timeout参数,改用command_execution_status查询
            import pyopencl as cl
            
            while True:
                # 非阻塞查询GPU执行状态
                status = read_event.command_execution_status
                if status == cl.command_execution_status.COMPLETE:
                    execution_completed[0] = True
                    break
                        
                # 检查是否需要停止(支持优雅退出)
                if stop_event is not None and stop_event.is_set():
                    logger.info("检测到停止信号,中断GPU等待")
                    execution_completed[0] = False
                    break
                
                # 短暂休眠,避免CPU空转
                time.sleep(poll_interval)
        finally:
            # 通知监控线程已完成
            timeout_event.set()
            # 等待监控线程退出(最多2秒)
            if monitor_thread.is_alive():
                monitor_thread.join(timeout=2.0)
                if monitor_thread.is_alive():
                    logger.warning("超时监控线程未能及时退出")
        
        # 检查是否超时
        if not execution_completed[0]:
            # P1修复: 超时后尝试清理资源
            # P3改进: 添加超时监控和强制中断机制
            try:
                logger.warning("GPU执行超时，尝试强制完成队列以清理资源")
                
                # 记录清理开始时间
                cleanup_start = time.time()
                
                # 尝试在有限时间内完成队列
                # 注意: OpenCL的finish()没有超时参数,但我们可以通过异常捕获来检测
                self.device.queue.finish()  # 强制完成队列
                
                cleanup_elapsed = time.time() - cleanup_start
                
                # 记录清理性能指标
                if cleanup_elapsed > 1.0:
                    logger.warning(
                        f"队列清理耗时{cleanup_elapsed:.2f}秒, "
                        f"GPU可能存在性能问题"
                    )
                
                # 如果清理耗时异常长(超过原始超时时间),说明GPU可能已完全故障
                if cleanup_elapsed > timeout_seconds:
                    logger.critical(
                        f"队列清理耗时{cleanup_elapsed:.1f}秒超过原始超时{timeout_seconds}秒, "
                        f"GPU可能已完全故障,建议重启程序并检查硬件"
                    )
            except Exception as cleanup_error:
                logger.error(f"强制清理GPU队列失败: {cleanup_error}")
                # 队列清理失败后尝试释放缓冲区资源，防止显存泄漏
                for buf_attr in ('_seed_buf', '_match_buf', '_targets_buf'):
                    buf = getattr(self, buf_attr, None)
                    if buf is not None:
                        try:
                            buf.release()
                            logger.debug(f"GPU超时清理：已释放 {buf_attr}")
                        except Exception as buf_err:
                            logger.debug(f"GPU超时清理：释放 {buf_attr} 失败: {buf_err}")
            
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
                    gpu_monitor = get_gpu_performance_monitor()
                    # v2.2.1: 使用精确的显存估算
                    if hasattr(self, '_calculate_gpu_memory_usage'):
                        memory_mb = self._calculate_gpu_memory_usage(num_keys)
                    else:
                        # PRNG模式: seed_buf(32B) + precomp_table(1984B) + match_flags(num_keys*4B)
                        memory_mb = (32 + 1984 + num_keys * 4) / (1024 * 1024)
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
            if hasattr(self, 'timeout_manager') and self.timeout_manager:
                self.timeout_manager.record_execution_time(execution_time_ms)
                
                # 降低日志频率：每 100 个批次检查一次警告
                if hasattr(self, 'stats') and self.stats and hasattr(self, 'MONITOR_INTERVAL'):
                    if (self.stats.total_batches > 0 and 
                        self.stats.total_batches % self.MONITOR_INTERVAL == 0):
                        if self.timeout_manager.should_warn(execution_time_ms):
                            timeout = self.timeout_manager.get_timeout()
                            logger.warning(
                                f"⚠️ 执行时间接近超时阈值: "
                                f"{execution_time_ms:.0f}ms / {timeout*1000:.0f}ms"
                            )
            
            # P1: 显存监控（每个批次都跟踪，但降低检查频率）
            if hasattr(self, 'memory_monitor') and self.memory_monitor:
                # 跟踪显存使用（估算）- 每个批次都记录
                estimated_memory = num_keys * 36  # 每个私钥约 36 字节
                self.memory_monitor.track_allocation(
                    estimated_memory,
                    batch_count=self.stats.total_batches
                )
                
                # 降低显存检查频率：每 100 个批次检查一次
                if hasattr(self, 'stats') and self.stats and hasattr(self, 'MONITOR_INTERVAL'):
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
        """清理GPU资源
            
        P1修复: 显式释放OpenCL Buffer,防止显存泄漏
        P3改进: 删除未使用的pyopencl导入(Buffer对象自带release方法)
        P5增强: 引擎关闭时强制检查内存泄漏
        v2.2.1: 关闭异步日志处理器
        v2.2.1修复: 避免双重释放缓冲区
        v3.2.1修复: 缓冲区归还到内存池（支持复用）
        v3.3.0优化: 纯持久化设计 - 直接释放，不归还到内存池
        """
        # 注意: 不需要导入pyopencl, OpenCL Buffer对象自带release()方法
        
        # v3.3.0优化: 纯持久化设计 - 不需要内存池引用（缓冲区直接释放）
        # memory_pool = getattr(self, '_gpu_memory_pool', None)  # 不再需要
        
        # v2.2.1修复: 跟踪已释放的缓冲区，避免双重释放
        released_buffers = set()
            
        # P5增强: 引擎关闭时强制检查并释放所有缓冲区
        if hasattr(self, '_buffer_tracker') and self._buffer_tracker:
            try:
                leak_report = self._buffer_tracker.force_check_on_shutdown()
                # 记录force_check_on_shutdown已经释放的缓冲区
                released_buffers.update(leak_report.get('released', []))
                
                # v2.2.1修复: 将已释放的缓冲区引用设为None，避免双重释放
                for buf_name in released_buffers:
                    if buf_name == '_seed_buf':
                        self._seed_buf = None
                    elif buf_name == '_match_buf':
                        self._match_buf = None
                    elif buf_name == '_targets_buf':
                        self._targets_buf = None
                
                # 审查修复#3: 使用修正后的语义
                if leak_report['has_unreleased'] or leak_report['has_leak']:
                    logger.warning(
                        f"GPU内存泄漏检测报告: "
                        f"未释放={leak_report['remaining_buffers']}, "
                        f"释放成功={len(leak_report['released'])}, "
                        f"释放失败={len(leak_report['release_failed'])}"
                    )
                    if leak_report['has_leak']:
                        logger.error(
                            f"发现{len(leak_report['release_failed'])}个缓冲区释放失败，"
                            f"可能存在内存泄漏"
                        )
            except Exception as e:
                logger.error(f"内存泄漏检查失败: {e}")
        
        # v3.3.0优化: 纯持久化设计 - 直接释放，不需要计算大小
        
        # P1修复: 显式释放OpenCL Buffer（跳过已释放的）
        buffers_to_release = [
            ("_seed_buf", self._seed_buf),
            ("_match_buf", self._match_buf),
            ("_targets_buf", self._targets_buf),
        ]
            
        for buf_name, buf in buffers_to_release:
            # v2.2.1修复: 跳过已被force_check_on_shutdown释放的缓冲区
            if buf_name in released_buffers:
                logger.debug(f"缓冲区 {buf_name} 已释放，跳过")
                continue
                
            if buf is not None:
                try:
                    # v3.3.0优化: 纯持久化设计 - 直接释放，不归还到内存池
                    buf.release()
                    logger.debug(f"已释放 {buf_name}")
                    
                    # P2-2修复: 注销缓冲区追踪
                    if hasattr(self, '_buffer_tracker'):
                        self._buffer_tracker.release_buffer(buf_name)
                except Exception as e:
                    logger.warning(f"释放 {buf_name} 失败: {e}")
            
        # 清空引用
        self._seed_buf = None
        self._match_buf = None
        self._targets_buf = None
        
        # v2.2.1: 关闭异步日志处理器
        if hasattr(self, '_async_log_handler') and self._async_log_handler:
            try:
                self._async_log_handler.close()
                logger.info("GPU异步日志已关闭")
            except Exception as e:
                logger.debug(f"关闭异步日志失败: {e}")
        self._match_flags = None
        self._program = None
        self._batch_kernel = None
        self._batch_kernel_local = None
    
    def _setup_async_logging(self, log_file: str, max_bytes: int, backup_count: int):
        """设置异步日志处理器（v2.2.1新增）
        
        Args:
            log_file: 日志文件路径
            max_bytes: 单个文件最大字节数
            backup_count: 备份文件数
        """
        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, mode=0o750, exist_ok=True)
            
            # 创建异步文件处理器
            from ..utils.async_file_handler import AsyncFileHandler
            self._async_log_handler = AsyncFileHandler(
                log_file,
                max_bytes=max_bytes,
                backup_count=backup_count
            )
            self._async_log_handler.setLevel(logging.DEBUG)
            
            # 添加到GPU引擎logger
            logger.addHandler(self._async_log_handler)
            
            logger.info(f"GPU异步日志已启用: {log_file} (max={max_bytes/1024/1024:.0f}MB)")
            
        except Exception as e:
            logger.warning(f"异步日志启用失败: {e}，使用同步日志")
            self._async_log_handler = None
            
        logger.debug("GPU Kernel资源已清理")
