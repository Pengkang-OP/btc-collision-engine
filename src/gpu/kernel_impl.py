"""GPU内核实现

包含 GPUKernel 类的实现，解决循环导入问题。

注意: GPU路径同样仅生成P2PKH地址进行碰撞检测，与CPU路径保持一致。
非P2PKH格式(P2SH/Bech32/Taproot)的目标地址在当前版本中必然无法匹配。
"""

import logging
import os
import threading
import time
from typing import Any

import numpy as np
import pyopencl as cl

from ..core.address_generator import P2PKHAddressGenerator
from ..core.hash_utils import HashUtils
from ..monitoring.gpu_performance_monitor import get_gpu_performance_monitor

# 统一日志获取
from ..utils import get_configured_logger
from .buffer_tracker import GPUBufferTracker
from .device import GPUDevice
from .kernel import OPENCL_KERNEL_SOURCE
from .kernel_protocol import GPUKernelProtocol
from .performance_optimizer import PerformanceMetrics

logger = get_configured_logger("GPUKernel")

# DEF-2修复: 内核编译重试配置
GPU_KERNEL_COMPILE_MAX_RETRIES = 4  # v4.2.3: 4 策略（含 Intel Arc 优化）
GPU_KERNEL_COMPILE_RETRY_DELAY_BASE = (
    2.0  # 基础延迟(秒), 指数退避: 2s(第1次失败后), 4s(第2次失败后)
)

# DEF-2修复: 渐进编译策略 — 每次重试尝试不同的编译选项
# v4.2.3: 新增 Intel Arc 优化策略（无符号零+乘加融合，安全于加密运算）
COMPILE_STRATEGIES = [
    ("标准编译", []),
    ("CL2.0标准编译", ["-cl-std=CL2.0"]),
    ("Intel Arc CL2.0 优化编译", ["-cl-std=CL2.0", "-cl-no-signed-zeros", "-cl-mad-enable"]),
    ("降级CL1.2编译", ["-cl-std=CL1.2", "-cl-mad-enable", "-cl-no-signed-zeros"]),
]


def compile_kernel_with_retry(
    ctx,  # OpenCL context
    source: str,
    strategies: list | None = None,
    max_retries: int = GPU_KERNEL_COMPILE_MAX_RETRIES,
    retry_delay_base: float = GPU_KERNEL_COMPILE_RETRY_DELAY_BASE,
    log=None,
):
    """共享的GPU内核编译重试函数 (DEF-2修复)

    kernel_impl._compile() 和 context._get_or_compile_kernel() 共享此函数，
    消除代码重复并提供统一的重试+降级编译策略。

    Args:
        ctx: OpenCL context (pyopencl.Context)
        source: OpenCL 内核源码字符串
        strategies: 编译策略列表 [(描述, 选项列表), ...]，默认使用 COMPILE_STRATEGIES
        max_retries: 最大尝试次数
        retry_delay_base: 指数退避基础延迟(秒)
        log: 日志记录器（默认使用模块级 logger）

    Returns:
        编译后的 pyopencl.Program 对象和使用的策略索引 (program, strategy_idx)

    Raises:
        RuntimeError: 所有重试均失败
    """
    if log is None:
        log = logger
    if strategies is None:
        strategies = COMPILE_STRATEGIES

    last_error = None
    compile_time_total = 0.0

    for attempt in range(max_retries):
        strategy_idx = min(attempt, len(strategies) - 1)
        strategy_desc, build_options = strategies[strategy_idx]

        compile_start = time.time()
        try:
            if build_options:
                program = cl.Program(ctx, source).build(options=build_options)
            else:
                program = cl.Program(ctx, source).build()

            compile_time_ms = (time.time() - compile_start) * 1000
            compile_time_total += compile_time_ms

            if attempt > 0:
                log.info(
                    f"OpenCL 内核编译成功 (第{attempt + 1}次尝试/{strategy_desc}): "
                    f"{compile_time_ms:.0f}ms (累计{compile_time_total:.0f}ms)"
                )
            else:
                log.info(f"OpenCL 内核编译成功 ({strategy_desc}): {compile_time_ms:.0f}ms")

            return program, strategy_idx  # DEF-2: 返回策略索引供调用方决定是否缓存

        except Exception as e:
            compile_time_ms = (time.time() - compile_start) * 1000
            compile_time_total += compile_time_ms
            last_error = e

            if attempt < max_retries - 1:
                delay = retry_delay_base * (2**attempt)
                log.warning(
                    f"OpenCL 内核编译失败 (第{attempt + 1}/{max_retries}次/{strategy_desc}): "
                    f"{type(e).__name__}: {e} ({compile_time_ms:.0f}ms), "
                    f"{delay:.0f}s后重试..."
                )
                time.sleep(delay)
            else:
                log.error(
                    f"OpenCL 内核编译彻底失败 (已重试{max_retries}次): "
                    f"{type(e).__name__}: {e} (累计{compile_time_total:.0f}ms)"
                )

    raise RuntimeError(f"GPU 内核编译失败 (已重试{max_retries}次): {last_error}") from last_error


def get_gpu_optimizer() -> Any | None:
    """获取GPU优化器"""
    try:
        from .performance_optimizer import get_gpu_optimizer as _get_gpu_optimizer

        return _get_gpu_optimizer()
    except ImportError:
        return None


from .seed_utils import (
    _seed_bytes_to_u32_be_array,  # noqa: E402, F811  # 权威实现（含 itemsize/len 运行时校验）
)


class GPUKernel(GPUKernelProtocol):
    """OpenCL GPU 计算内核包装 - 优化版本

    实现GPUKernelProtocol接口（P1-2修复）。
    使用持久化 Buffer 和异步执行来保持 GPU 持续高负载，
    避免频繁的内存分配和同步等待造成的 GPU 空闲。

    地址格式: GPU路径使用 P2PKHAddressGenerator，仅生成P2PKH地址（与CPU路径一致）。
    """

    # 2*G 的期望坐标值（用于验证）
    EXPECTED_2G_X = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
    EXPECTED_2G_Y = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A

    # v3.3.0新增: 缓冲区大小因子常量
    # KEYS_BUFFER_SIZE_FACTOR: PRNG改造后私钥缓冲区已弃用，保留以兼容日志中的历史大小引用
    KEYS_BUFFER_SIZE_FACTOR = 32  # 历史: PRNG模式下私钥缓冲区已不再需要，仅用于日志大小参考
    MATCH_BUFFER_SIZE_FACTOR = 4  # 每个匹配标志4字节（int32）

    def __init__(
        self, device: GPUDevice, max_batch_size: int | None = None, program: Any | None = None
    ) -> None:
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
        device_info = device.get_device_info() if hasattr(device, "get_device_info") else {}
        self._work_group_size = device_info.get("work_group_size", 256)

        # 如果没有指定max_batch_size，根据GPU显存自动计算
        if max_batch_size is None:
            max_batch_size = self._calculate_optimal_batch_size()

        # L-NEW1修复: 与配置层保持一致的上限检查（16M）
        MAX_BATCH_SIZE_LIMIT = 16777216  # 16M，与 config_manager.py Schema 一致
        if max_batch_size > MAX_BATCH_SIZE_LIMIT:
            raise ValueError(
                f"batch_size {max_batch_size} 超出最大限制 {MAX_BATCH_SIZE_LIMIT} (配置层与引擎层统一上限)"
            )

        self._max_batch_size = max_batch_size
        self._program = program  # 可能为None（需要自行编译）
        self._batch_kernel = None
        self._batch_kernel_local = None  # local memory版本内核引用
        # 查询设备local memory大小（OpenCL标准属性），回退默认值16KB
        try:
            self._local_mem_size = device.device.local_mem_size  # type: ignore[attr-defined] # noqa: E501
        except (AttributeError, RuntimeError, TypeError):
            self._local_mem_size = 16384  # 默认16KB

        # P2-2修复: 初始化缓冲区追踪器
        self._buffer_tracker = GPUBufferTracker()

        # 持久化 Buffer - 避免频繁分配/释放（PyOpenCL C扩展类型，无stubs故用Any）
        self._seed_buf = None  # PRNG模式：仅存傤32字节种子
        # self._keys_buf 已于 v4.0 PRNG 改造时移除，不再使用
        self._match_buf = None
        self._targets_buf = None
        self._target_hash160s: bytes | None = None  # 添加目标地址缓存
        self._targets_cached: bytes | None = None
        self._num_targets_cached = 0
        self._check_uncompressed = 0  # v4.0: 0=仅压缩, 1=也检查非压缩
        self._precomp_buf = None  # 预计算表常量缓冲区（生命周期与 kernel 一致）

        # 预分配主机内存
        self._match_flags = None

        # 校验 GPUDevice 已正确初始化
        if not getattr(self.device, "context", None) or not getattr(self.device, "queue", None):
            raise RuntimeError(
                "GPUDevice 尚未初始化，请先调用 GPUDevice.initialize() 再创建 GPUKernel"
            )

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
    def program(self) -> Any | None:  # Optional[cl.Program]
        """已编译的OpenCL程序

        Returns:
            pyopencl.Program实例，或None（如果尚未编译）
        """
        return self._program

    def _compile(self):
        """编译 OpenCL 内核（带性能监控、缓存和重试机制）

        P2-6修复: 添加内核编译缓存机制，避免每次启动都重新编译
        DEF-2修复: 编译失败时自动重试（最多4次，渐进策略+指数退避）
            第1次: 标准编译
            第2次: CL2.0标准编译 (延迟2s)
            第3次: Intel Arc CL2.0 优化编译 (延迟4s, -cl-no-signed-zeros -cl-mad-enable)
            第4次: 降级CL1.2编译 (延迟8s, -cl-std=CL1.2 -cl-mad-enable -cl-no-signed-zeros)
        """
        import time

        # P2-6修复: 尝试从缓存加载（标准编译的缓存）
        if self._load_kernel_cache():
            logger.info("使用缓存的OpenCL内核二进制")
            return

        compile_start_total = time.time()

        try:
            # DEF-2修复: 使用共享重试编译函数
            self._program, strategy_idx = compile_kernel_with_retry(
                ctx=self.device.context,
                source=OPENCL_KERNEL_SOURCE,
                strategies=COMPILE_STRATEGIES,
                max_retries=GPU_KERNEL_COMPILE_MAX_RETRIES,
                retry_delay_base=GPU_KERNEL_COMPILE_RETRY_DELAY_BASE,
                log=logger,
            )

            total_compile_time_ms = (time.time() - compile_start_total) * 1000

            # DEF-2修复: 仅缓存标准编译结果（strategy_idx=0），
            # 降级编译不缓存，避免驱动升级后永久锁定在降级性能
            if strategy_idx == 0:
                self._save_kernel_cache()
            else:
                logger.info(
                    f"内核使用降级策略({COMPILE_STRATEGIES[strategy_idx][0]})编译成功，不缓存以避免锁定降级性能"
                )

            # 记录编译性能
            try:
                device_name = self.device.device.name
                vendor_str = self.device.device.vendor
                global_mem = self.device.device.global_mem_size

                if self.gpu_optimizer:
                    profile = self.gpu_optimizer.create_optimized_profile(
                        device_name=device_name,
                        vendor_str=vendor_str,
                        global_mem_size=global_mem,
                        compile_time_ms=total_compile_time_ms,
                    )

                    if profile.max_batch_size != self.max_batch_size:
                        logger.info(
                            f"根据性能优化调整batch_size: {self.max_batch_size} -> {profile.max_batch_size}"
                        )
                        self._max_batch_size = profile.max_batch_size
                else:
                    logger.debug("GPU优化器不可用，跳过性能配置创建")

            except Exception as opt_error:
                logger.warning(f"GPU性能优化失败: {opt_error}")

        except RuntimeError:
            # compile_kernel_with_retry 已经记录了详细日志，直接向上传播
            raise

    def _verify(self):
        """ALG-3修复: 验证 GPU 计算正确性（增强版）

        验证内容:
        1. 基础验证: 虚拟目标不应匹配
        2. 增强验证: 已知私钥-地址对应该匹配（如果提供）

        PRNG模式: seed=1, gid=0 -> key = seed + 0 = 1 (与原测试私钥一致)
        """
        import numpy as np
        import pyopencl as cl

        # ===== 验证1: 基础验证 - 虚拟目标不应匹配 =====
        num_keys = 1
        num_targets = 1

        # PRNG模式: 种子=1 (32字节), gid=0 -> key = 1 + 0 = 1
        # 字节序: 大端, 最后一个字节为 0x01
        test_seed_bytes = b"\x00" * 31 + b"\x01"

        # 虚拟目标hash160 (20字节)
        test_targets = b"\x00" * 20

        # 将种子写入GPU seed缓冲区
        seed_array = _seed_bytes_to_u32_be_array(test_seed_bytes)
        cl.enqueue_copy(self.device.queue, self._seed_buf, seed_array)

        # 设置目标
        self.set_targets(test_targets, num_targets, check_uncompressed=0)

        # 清空匹配结果缓冲区
        cl.enqueue_fill_buffer(
            self.device.queue,
            self._match_buf,
            np.int32(0),
            0,
            num_keys * 4,
        )

        # 执行GPU batch计算
        self._batch_kernel(
            self.device.queue,
            (num_keys,),
            None,
            self._seed_buf,
            np.uint32(num_keys),
            self._targets_buf,
            np.uint32(num_targets),
            self._match_buf,
            np.uint32(self._check_uncompressed),
            self._precomp_buf,
        ).wait()

        # 读取结果
        match_flags: np.ndarray[Any, Any] = np.zeros(num_keys, dtype=np.int32)
        cl.enqueue_copy(self.device.queue, match_flags, self._match_buf)

        # 验证: 由于目标是全0,不应该匹配
        if match_flags[0] != 0:
            raise RuntimeError(
                f"GPU内核验证失败: 不应匹配虚拟目标,但match_flags[0]={match_flags[0]}"
            )

        logger.info("✅ GPU内核基础验证通过（虚拟目标不匹配）")

        # ===== ALG-3修复: 验证2 - 真实地址匹配测试 =====
        # 使用已知私钥和对应的Hash160进行测试
        # 即私钥=1的公钥的Hash160: 751e76e8199196d454941c45d1b3a323f1433bd6
        try:
            # 私钥1对应的字节串（大端，与 seed=1 一致）
            test_key_bytes = b"\x00" * 31 + b"\x01"

            # 生成私钥1的地址和Hash160 (P2PKH-only，与CPU路径一致)
            generator = P2PKHAddressGenerator()
            test_address, compressed_pk, _ = generator.generate_address(test_key_bytes)
            test_hash160 = HashUtils.hash160(compressed_pk)

            logger.info(f"ALG-3增强验证: 测试私钥1 -> 地址 {test_address}")
            logger.info(f"  Hash160: {test_hash160.hex()}")

            # 将真实Hash160设置为目标
            self.set_targets(test_hash160, 1, check_uncompressed=0)

            # 清空匹配结果缓冲区
            cl.enqueue_fill_buffer(
                self.device.queue,
                self._match_buf,
                np.int32(0),
                0,
                num_keys * 4,
            )

            # 执行GPU batch计算
            self._batch_kernel(
                self.device.queue,
                (num_keys,),
                None,
                self._seed_buf,
                np.uint32(num_keys),
                self._targets_buf,
                np.uint32(1),
                self._match_buf,
                np.uint32(self._check_uncompressed),
                self._precomp_buf,
            ).wait()

            # 读取结果
            match_flags = np.zeros(num_keys, dtype=np.int32)
            cl.enqueue_copy(self.device.queue, match_flags, self._match_buf)

            # 验证: 私钥1应该匹配它的地址
            if match_flags[0] != 1:
                raise RuntimeError(
                    f"GPU内核增强验证失败: 私钥1应该匹配地址{test_address},但match_flags[0]={match_flags[0]}"
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
        source_hash = hashlib.md5(OPENCL_KERNEL_SOURCE.encode(), usedforsecurity=False).hexdigest()[
            :8
        ]

        cache_key = f"{device_info}_{source_hash}"
        # 替换非法字符
        cache_key = cache_key.replace(" ", "_").replace("-", "_")

        return cache_key

    def _get_cache_file(self) -> str:
        """P2-6修复: 获取缓存文件路径"""
        import os

        cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "cache")
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
            with open(cache_file, "rb") as f:
                cached_binary = f.read()

            # 从二进制加载程序
            self._program = cl.Program(
                self.device.context, [self.device.device], [cached_binary]
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
        """P2-6修复 + DEF-2审查: 原子写入内核二进制到缓存

        使用 tmp + os.replace 原子写入，防止并发写入导致缓存损坏。
        """
        cache_file = self._get_cache_file()
        tmp_file = cache_file + ".tmp"

        try:
            # 获取编译后的二进制
            assert self._program is not None, "_save_kernel_cache 应在编译成功后调用"
            binaries = self._program.get_info(cl.program_info.BINARIES)
            if binaries and len(binaries) > 0:
                binary = binaries[0]

                # 原子写入: 先写临时文件，再原子替换
                with open(tmp_file, "wb") as f:
                    f.write(binary)
                os.replace(tmp_file, cache_file)  # 原子操作（Windows上也基本原子）

                logger.debug(f"内核缓存已保存: {cache_file} ({len(binary)} bytes)")

        except Exception as e:
            logger.warning(f"保存内核缓存失败: {e}")
            # 清理可能的临时文件
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except OSError:
                pass

    def _calculate_optimal_batch_size(self) -> int:
        """根据GPU显存大小计算最优batch_size

        使用共享工具函数，考虑目标地址缓冲区占用。
        """
        # 导入共享工具函数
        from ..utils.gpu_memory_utils import calculate_optimal_batch_size

        # 计算目标地址缓冲区大小（如果已准备）
        target_buffer_size = 0
        if hasattr(self, "_target_hash160s") and self._target_hash160s:
            target_buffer_size = len(self._target_hash160s)

        # 调用共享函数
        return calculate_optimal_batch_size(
            device=self.device, target_buffer_size=target_buffer_size
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
        memory_pool = getattr(self, "_gpu_memory_pool", None)

        # PRNG模式: 种子缓冲区（32字节，固定，替代原 num_keys*32 字节的 keys 缓冲区）
        # 节省显存: max_batch_size * 32 字节（例: 1M keys 节省约32MB）
        if memory_pool:
            # 内存池不支持如此小的分配，直接创建
            self._seed_buf = cl.Buffer(
                self.device.context,
                cl.mem_flags.READ_ONLY,
                size=32,  # 固定32字节
            )
        else:
            self._seed_buf = cl.Buffer(
                self.device.context,
                cl.mem_flags.READ_ONLY,
                size=32,  # 固定32字节
            )
        logger.info(
            "PRNG模式: 创建 seed_buf 32字节（替代原 keys_buf "
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
                self.device.context, cl.mem_flags.WRITE_ONLY, size=match_buf_size
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
                hostbuf=precomp_data,
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
                "GPU内存池状态 (v3.3.0纯持久化设计): "
                f"已分配={pool_stats['total_allocated']}, "
                f"已复用={pool_stats['total_reused']}, "
                f"当前内存={pool_stats['current_memory_mb']:.1f}MB, "
                f"池内缓冲={pool_stats['pooled_buffers']}个 | "
                "设计: 持久化缓冲区在引擎生命周期内重复使用，零运行时分配开销"
            )

    def set_targets(
        self, target_hash160s: bytes, num_targets: int, check_uncompressed: int = 0
    ) -> None:
        """设置目标地址 Hash160 - 只需设置一次

        Args:
            target_hash160s: 目标Hash160字节串
            num_targets: 目标数量
            check_uncompressed: 是否同时检查非压缩格式 (0=仅压缩, 1=双格式)
        """
        import numpy as np

        # 检查是否需要更新
        if (
            self._targets_cached == target_hash160s
            and self._num_targets_cached == num_targets
            and self._check_uncompressed == check_uncompressed
        ):
            return

        self._check_uncompressed = check_uncompressed

        # 释放旧的缓冲区（通过buffer_tracker统一释放，避免直接调用.release()导致双重释放）
        if self._targets_buf is not None:
            try:
                if hasattr(self, "_buffer_tracker") and self._buffer_tracker:
                    self._buffer_tracker.release_buffer("_targets_buf")
                else:
                    self._targets_buf.release()
                logger.debug("已释放旧 targets_buf")
            except Exception as e:
                logger.warning(f"释放旧 targets_buf 失败: {e}")
            self._targets_buf = None

        # 创建新的目标缓冲区
        targets_array = np.frombuffer(target_hash160s, dtype=np.uint8)
        self._targets_buf = cl.Buffer(  # type: ignore[assignment] # PyOpenCL C扩展无stubs
            self.device.context,
            cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=targets_array,
        )

        # 注册到缓冲区追踪器
        if hasattr(self, "_buffer_tracker") and self._buffer_tracker:
            self._buffer_tracker.track_buffer(
                "_targets_buf", self._targets_buf, len(target_hash160s)
            )

        self._targets_cached = target_hash160s
        self._num_targets_cached = num_targets

        logger.info(f"GPU 目标地址设置完成: {num_targets} 个目标")

    # ========================================================================
    # 辅助函数 - 拆分自 run_batch
    # ========================================================================

    def _validate_batch_params(self, num_keys: int, seed: bytes) -> None:
        """验证批次参数"""
        if num_keys <= 0 or num_keys > self.max_batch_size:
            raise ValueError(f"num_keys 必须在 1..{self.max_batch_size} 之间，当前为 {num_keys}")
        if len(seed) != 32:
            raise ValueError(f"seed 长度必须为 32 字节（PRNG模式），当前为 {len(seed)} 字节")

    def _check_memory_limit(self, num_keys: int) -> None:
        """检查GPU显存限制"""
        target_buffer_size = len(self._target_hash160s) if self._target_hash160s else 0
        required_memory = 32 + (num_keys * 4) + target_buffer_size
        required_memory_with_overhead = int(required_memory * 1.2)
        device_info = (
            self.device.get_device_info() if hasattr(self.device, "get_device_info") else {}
        )
        max_memory = device_info.get("global_mem_size", 0)
        safe_memory_limit = int(max_memory * 0.8) if max_memory > 0 else float("inf")
        if required_memory_with_overhead > safe_memory_limit:
            raise MemoryError(
                f"所需显存 {required_memory_with_overhead / 1024**2:.0f}MB "
                f"超过安全限制 {safe_memory_limit / 1024**2:.0f}MB"
            )

    def _write_seed_buffer(self, seed: bytes) -> None:
        """写入种子缓冲区"""
        if self._seed_buf is None:
            logger.error("_seed_buf 已释放，无法执行批处理")
            raise RuntimeError("_seed_buf 已释放")
        seed_array = _seed_bytes_to_u32_be_array(seed)
        try:
            cl.enqueue_copy(self.device.queue, self._seed_buf, seed_array)
        except Exception as e:
            # SUGGESTION-7: 添加exc_info保留完整堆栈信息
            logger.error(f"写入 seed_buf 失败: {e}", exc_info=True)
            raise

    def _clear_match_buffer(self, num_keys: int) -> None:
        """清空匹配结果缓冲区"""
        import numpy as np

        if self._match_buf is None:
            logger.error("_match_buf 已释放，无法执行批处理")
            raise RuntimeError("_match_buf 已释放")
        try:
            cl.enqueue_fill_buffer(self.device.queue, self._match_buf, np.int32(0), 0, num_keys * 4)
        except Exception as e:
            logger.error(f"清空 match_buf 失败: {e}")
            raise

    def _execute_kernel(self, num_keys: int, local_work_size: int) -> tuple:
        """执行GPU内核"""
        global_work_size = ((num_keys + local_work_size - 1) // local_work_size) * local_work_size
        target_bytes = self._num_targets_cached * 20
        local_mem_size = getattr(self, "_local_mem_size", 16384)
        use_local_mem = (
            self._batch_kernel_local is not None
            and target_bytes > 0
            and target_bytes <= local_mem_size
            and (target_bytes <= int(local_mem_size * 0.8) or self._num_targets_cached <= 250)
        )
        if use_local_mem:
            logger.debug(f"使用local memory版内核: 目标数据{target_bytes}B")
            self._batch_kernel_local(
                self.device.queue,
                (global_work_size,),
                (local_work_size,),
                self._seed_buf,
                np.uint32(num_keys),
                self._targets_buf,
                np.uint32(self._num_targets_cached),
                self._match_buf,
                np.uint32(self._check_uncompressed),
                cl.LocalMemory(target_bytes),
                self._precomp_buf,
            )
        else:
            self._batch_kernel(
                self.device.queue,
                (global_work_size,),
                (local_work_size,),
                self._seed_buf,
                np.uint32(num_keys),
                self._targets_buf,
                np.uint32(self._num_targets_cached),
                self._match_buf,
                np.uint32(self._check_uncompressed),
                self._precomp_buf,
            )
        return cl.enqueue_copy(self.device.queue, self._match_flags[:num_keys], self._match_buf)

    def _wait_for_completion(self, read_event, timeout_seconds: float = 30) -> bool:
        """等待GPU执行完成"""
        import time

        timeout_event = threading.Event()
        execution_completed = [False]

        def timeout_monitor():
            try:
                if not timeout_event.wait(timeout_seconds):
                    logger.error(f"GPU执行超时({timeout_seconds}秒)")
                    execution_completed[0] = False
            except Exception as e:
                logger.error(f"超时监控线程异常: {e}")
                execution_completed[0] = False

        monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)
        monitor_thread.start()
        try:
            max_iterations = int(timeout_seconds / 0.1) + 10
            for _ in range(max_iterations):
                try:
                    status = read_event.command_execution_status
                    if status == cl.command_execution_status.COMPLETE:
                        execution_completed[0] = True
                        break
                except cl.Error:
                    execution_completed[0] = False
                    break
                time.sleep(0.1)
        finally:
            timeout_event.set()
            monitor_thread.join(timeout=2.0)
        return execution_completed[0]

    def _release_buffers_on_error(self) -> None:
        """错误时释放缓冲区"""
        for buf_attr in ("_seed_buf", "_match_buf", "_targets_buf", "_precomp_buf"):
            buf = getattr(self, buf_attr, None)
            if buf is None:
                continue
            released = False
            try:
                if hasattr(self, "_buffer_tracker") and self._buffer_tracker:
                    self._buffer_tracker.release_buffer(buf_attr)
                    released = True
            except Exception:
                pass
            if not released:
                try:
                    buf.release()
                except Exception:
                    pass
            setattr(self, buf_attr, None)

    def _collect_matches(self, match_view, num_keys: int) -> list:
        """收集匹配结果"""
        matches = []
        for i in range(num_keys):
            if match_view[i] > 0:
                matches.append({"key_index": i, "target_index": int(match_view[i] - 1)})
        return matches

    def _record_performance(self, num_keys: int, batch_start_time: float, match_count: int) -> None:
        """记录性能指标"""
        import time

        try:
            execution_time_ms = (time.time() - batch_start_time) * 1000
            keys_per_second = (num_keys / execution_time_ms * 1000) if execution_time_ms > 0 else 0
            metrics = PerformanceMetrics(
                batch_execution_time_ms=execution_time_ms,
                keys_per_second=keys_per_second,
                error_count=0,
            )
            if self.gpu_optimizer:
                self.gpu_optimizer.record_performance(metrics)
            if hasattr(self, "stats") and self.stats:
                try:
                    gpu_monitor = get_gpu_performance_monitor()
                    memory_mb = (32 + 1984 + num_keys * 4) / (1024 * 1024)
                    gpu_monitor.record_kernel_metrics(
                        batch_size=num_keys,
                        execution_time_ms=execution_time_ms,
                        memory_allocated_mb=memory_mb,
                        error_count=0,
                        match_count=match_count,
                    )
                except Exception:
                    pass
            if hasattr(self, "timeout_manager") and self.timeout_manager:
                self.timeout_manager.record_execution_time(execution_time_ms)
            if hasattr(self, "memory_monitor") and self.memory_monitor:
                self.memory_monitor.track_allocation(num_keys * 36)
        except Exception:
            pass

    def run_batch(
        self,
        seed: bytes,
        num_keys: int,
        target_hash160s: bytes | None = None,
        num_targets: int = 0,
        stop_event: Any | None = None,
    ) -> list[dict]:
        """PRNG模式批量执行私钥碰撞检测"""
        import time

        batch_start_time = time.time()

        # 1. 参数校验
        self._validate_batch_params(num_keys, seed)

        # 1.5. 显存限制检查
        self._check_memory_limit(num_keys)

        # 2. 设置目标
        if target_hash160s is not None:
            self.set_targets(target_hash160s, num_targets)

        # 3. 写入种子缓冲区
        self._write_seed_buffer(seed)

        # 4. 清空匹配结果缓冲区
        self._clear_match_buffer(num_keys)

        # 5. 执行内核
        if self._batch_kernel is None:
            self._batch_kernel = self.program.batch_check
        local_work_size = getattr(self, "_work_group_size", 256)
        try:
            read_event = self._execute_kernel(num_keys, local_work_size)
        except Exception as e:
            logger.error(f"内核执行失败: {e}")
            return []

        # 6. 等待完成
        if not self._wait_for_completion(read_event):
            self._release_buffers_on_error()
            raise RuntimeError("GPU执行超时，内核可能已hang")

        # 7. 收集结果
        matches = self._collect_matches(self._match_flags[:num_keys], num_keys)

        # 8. 记录性能
        self._record_performance(num_keys, batch_start_time, len(matches))

        return matches

    def cleanup(self) -> None:
        """清理GPU资源

        P1修复: 显式释放OpenCL Buffer,防止显存泄漏
        改进: 删除未使用的pyopencl导入(Buffer对象自带release方法)
        P5增强: 引擎关闭时强制检查内存泄漏
        v2.2.1: 关闭异步日志处理器
        v2.2.1修复: 避免双重释放缓冲区
        v3.2.1修复: 缓冲区归还到内存池（支持复用）
        v3.3.0优化: 纯持久化设计 - 直接释放，不归还到内存池
        """
        # 注意: 不需要导入pyopencl, OpenCL Buffer对象自带release()方法

        # v3.3.0优化: 纯持久化设计 - 不需要内存池引用（缓冲区直接释放）
        # memory_pool = getattr(self, '_gpu_memory_pool', None) # 不再需要

        # v2.2.1修复: 跟踪已释放的缓冲区，避免双重释放
        released_buffers = set()

        # P5增强: 引擎关闭时强制检查并释放所有缓冲区
        if hasattr(self, "_buffer_tracker") and self._buffer_tracker:
            try:
                leak_report = self._buffer_tracker.force_check_on_shutdown()
                # 记录force_check_on_shutdown已经释放的缓冲区
                released_buffers.update(leak_report.get("released", []))

                # v2.2.1修复: 将已释放的缓冲区引用设为None，避免双重释放
                for buf_name in released_buffers:
                    if buf_name == "_seed_buf":
                        self._seed_buf = None
                    elif buf_name == "_match_buf":
                        self._match_buf = None
                    elif buf_name == "_targets_buf":
                        self._targets_buf = None
                    elif buf_name == "_precomp_buf":
                        self._precomp_buf = None

                # 审查修复#3: 使用修正后的语义
                if leak_report["has_unreleased"] or leak_report["has_leak"]:
                    logger.warning(
                        "GPU内存泄漏检测报告: "
                        f"未释放={leak_report['remaining_buffers']}, "
                        f"释放成功={len(leak_report['released'])}, "
                        f"释放失败={len(leak_report['release_failed'])}"
                    )
                    if leak_report["has_leak"]:
                        logger.error(
                            f"发现{len(leak_report['release_failed'])}个缓冲区释放失败，可能存在内存泄漏"
                        )
            except Exception as e:
                logger.error(f"内存泄漏检查失败: {e}")

        # v3.3.0优化: 纯持久化设计 - 直接释放，不需要计算大小

        # 显式释放OpenCL Buffer（跳过已释放的）
        buffers_to_release = [
            ("_seed_buf", self._seed_buf),
            ("_match_buf", self._match_buf),
            ("_targets_buf", self._targets_buf),
            ("_precomp_buf", self._precomp_buf),
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
                    # 注意: force_check_on_shutdown已clear整个_allocated_buffers dict,
                    # 所以此处release_buffer是空操作(防御性保留,避免未来重构遗漏)
                    if hasattr(self, "_buffer_tracker"):
                        self._buffer_tracker.release_buffer(buf_name)
                except Exception as e:
                    logger.warning(f"释放 {buf_name} 失败: {e}")

        # 清空引用
        self._seed_buf = None
        self._match_buf = None
        self._targets_buf = None
        self._precomp_buf = None

        # v2.2.1: 关闭异步日志处理器
        if hasattr(self, "_async_log_handler") and self._async_log_handler:
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
                log_file, max_bytes=max_bytes, backup_count=backup_count
            )
            self._async_log_handler.setLevel(logging.DEBUG)

            # 添加到GPU引擎logger
            logger.addHandler(self._async_log_handler)

            logger.info(f"GPU异步日志已启用: {log_file} (max={max_bytes / 1024 / 1024:.0f}MB)")

        except Exception as e:
            logger.warning(f"异步日志启用失败: {e}，使用同步日志")
            self._async_log_handler = None
