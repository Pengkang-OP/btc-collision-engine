"""GPU内核实现.

包含:
- compile_kernel_with_retry: 共享的内核编译重试函数 (DEF-2修复)，支持4种降级编译策略
- GPUKernel: OpenCL GPU计算内核包装类，实现GPUKernelProtocol接口
  - 持久化Buffer和异步执行，保持GPU持续高负载
  - 2*G自检验证、批量密钥碰撞、目标地址管理
  - 预计算表(Precomputed Table)常量缓冲区管理

v4.2.2 M5: _seed_bytes_to_u32_be_array 统一至 gpu/seed_utils.py 导入。
"""

import logging
import os
import pathlib
import threading
import time
from contextlib import suppress
from typing import Any, cast

import numpy as np

from ..core.address_generator import P2PKHAddressGenerator
from ..core.hash_utils import HashUtils
from ..monitoring.gpu_performance_monitor import get_gpu_performance_monitor
from ..utils import get_configured_logger
from ._availability import PYOPENCL_AVAILABLE
from .buffer_tracker import GPUBufferTracker
from .device import GPUDevice, _assert_opencl_available
from .kernel import OPENCL_KERNEL_SOURCE
from .kernel_protocol import GPUKernelProtocol
from .performance_optimizer import PerformanceMetrics
from .secure_buffer import secure_clear_gpu_buffer
from .seed_utils import _seed_bytes_to_u32_be_array

cl: Any
if PYOPENCL_AVAILABLE:
    import pyopencl as _cl
    cl = _cl
else:
    cl = cast(Any, None)

_assert_opencl_available()

logger = get_configured_logger("GPUKernel")

__all__ = [
    "COMPILE_STRATEGIES",
    "ENV_LOCAL_MEM_THRESHOLD",
    "ENV_WORK_GROUP_SIZE",
    "GPU_KERNEL_COMPILE_MAX_RETRIES",
    "GPU_KERNEL_COMPILE_RETRY_DELAY_BASE",
    "GPUKernel",
    "compile_kernel_with_retry",
    "get_gpu_optimizer",
]

# ============================================================================
# OPT-3: 可调参数 - 允许高级用户根据硬件和负载特征调整内核执行参数
# ============================================================================

# 环境变量: 覆盖 work_group_size
# 用法: set BTC_GPU_WORK_GROUP_SIZE=256   (Windows)
#       export BTC_GPU_WORK_GROUP_SIZE=256 (Linux)
# 合法值: 64~1024，且必须为 2 的幂（或至少为 32 的倍数以确保合并内存访问）
# 为 0 或未设置时使用自动检测
ENV_WORK_GROUP_SIZE = "BTC_GPU_WORK_GROUP_SIZE"

# 环境变量: local memory 阈值比例
# 控制何时使用 local memory 版内核 (batch_check_local_mem)
# 默认 0.8 意味着：目标数据占用 local memory 80% 以下时使用 local memory 内核
# 降低此值（如 0.6）可减少 local memory 使用，为寄存器溢出留更多空间
# 提高此值（如 0.95）可更大胆地使用 local memory（但可能因资源不足导致 occupancy 下降）
# 用法: set BTC_GPU_LOCAL_MEM_THRESHOLD=0.6
ENV_LOCAL_MEM_THRESHOLD = "BTC_GPU_LOCAL_MEM_THRESHOLD"

# 厂商推荐 work_group_size 默认值（在 auto_config 未提供时回退使用）
# NVIDIA: Warp=32, 256 是 SM 内多 warp 调度的甜点值
# AMD (GCN): Wavefront=64, 256 = 4 wavefronts, 可隐藏内存延迟
# AMD (RDNA): Wavefront=32, 256 = 8 wavefronts
# Intel Arc: EU=32-wide SIMD, 512 可同时利用多个 EU 的 SIMD 通道
# 通用: 256 是大多数 GPU 的安全甜点值
_VENDOR_WORK_GROUP_DEFAULTS: dict[str, int] = {
    "nvidia": 256,
    "amd": 256,
    "intel": 512,
}
_DEFAULT_WORK_GROUP_SIZE = 256

# DEF-2修复: 内核编译重试配置
GPU_KERNEL_COMPILE_MAX_RETRIES = 4  # v4.2.1: 4 策略（含 Intel Arc 优化）
GPU_KERNEL_COMPILE_RETRY_DELAY_BASE = 2.0  # 基础延迟(秒), 指数退避: 2s(第1次失败后), 4s(第2次失败后)

# DEF-2修复: 渐进编译策略 — 每次重试尝试不同的编译选项
# v4.2.1: 新增 Intel Arc 优化策略（无符号零+乘加融合，安全于加密运算）
COMPILE_STRATEGIES = (
    ("标准编译", ()),
    ("CL2.0标准编译", ("-cl-std=CL2.0",)),
    ("Intel Arc CL2.0 优化编译", ("-cl-std=CL2.0", "-cl-no-signed-zeros", "-cl-mad-enable")),
    ("降级CL1.2编译", ("-cl-std=CL1.2", "-cl-mad-enable", "-cl-no-signed-zeros")),
)


def compile_kernel_with_retry(
    ctx,  # OpenCL context
    source: str,
    strategies: list | None = None,
    max_retries: int = GPU_KERNEL_COMPILE_MAX_RETRIES,
    retry_delay_base: float = GPU_KERNEL_COMPILE_RETRY_DELAY_BASE,
    log=None,
):
    """共享的GPU内核编译重试函数 (DEF-2修复).

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
                    f"{compile_time_ms:.0f}ms (累计{compile_time_total:.0f}ms)",
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
                    f"{delay:.0f}s后重试...",
                )
                time.sleep(delay)
            else:
                log.error(
                    f"OpenCL 内核编译彻底失败 (已重试{max_retries}次): "
                    f"{type(e).__name__}: {e} (累计{compile_time_total:.0f}ms)",
                )

    raise RuntimeError(f"GPU 内核编译失败 (已重试{max_retries}次): {last_error}") from last_error


def get_gpu_optimizer() -> Any | None:
    """获取GPU优化器."""
    try:
        from .performance_optimizer import get_gpu_optimizer as _get_gpu_optimizer

        return _get_gpu_optimizer()
    except ImportError:
        return None


class GPUKernel(GPUKernelProtocol):
    """OpenCL GPU 计算内核包装 - 优化版本.

    实现GPUKernelProtocol接口（P1-2修复）。
    使用持久化 Buffer 和异步执行来保持 GPU 持续高负载，
    避免频繁的内存分配和同步等待造成的 GPU 空闲。

    v4.2.2: mod_inverse Binary GCD 2^256溢出修复；
    _seed_bytes_to_u32_be_array 统一至 gpu/seed_utils.py 导入。
    """

    __slots__ = (
        # === 设备 / 优化器 ===
        "_device",
        "gpu_optimizer",
        # === 内核参数 ===
        "_work_group_size",
        "_max_batch_size",
        "_local_mem_size",
        # === 内核引用 / 编译 ===
        "_program",
        "_batch_kernel",
        "_batch_kernel_local",
        # === 缓冲区 ===
        "_buffer_tracker",
        "_seed_buf",
        "_match_buf",
        "_targets_buf",
        "_precomp_buf",
        "_match_flags",
        # === 目标缓存 ===
        "_target_hash160s",
        "_targets_cached",
        "_num_targets_cached",
        "_check_uncompressed",
        # === 日志 ===
        "_async_log_handler",
    )

    # 2*G 的期望坐标值（用于验证）
    EXPECTED_2G_X = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
    EXPECTED_2G_Y = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A

    # v4.2.1新增: 缓冲区大小因子常量
    # KEYS_BUFFER_SIZE_FACTOR: PRNG改造后私钥缓冲区已弃用，保留以兼容日志中的历史大小引用
    KEYS_BUFFER_SIZE_FACTOR = 32  # 历史: PRNG模式下私钥缓冲区已不再需要，仅用于日志大小参考
    MATCH_BUFFER_SIZE_FACTOR = 4  # 每个匹配标志4字节（int32）

    def __init__(
        self,
        device: GPUDevice,
        max_batch_size: int | None = None,
        program: Any | None = None,
    ) -> None:
        """初始化GPUKernel.

        Args:
            device: GPUDevice实例
            max_batch_size: 最大批次大小（None=自动计算）
            program: 已编译的OpenCL程序（可选，如果提供则跳过编译）

        """
        self._device = device
        self.gpu_optimizer = get_gpu_optimizer()

        # v4.2.1优化: 从配置中获取work_group_size
        device_info = device.get_device_info() if hasattr(device, "get_device_info") else {}
        self._work_group_size = device_info.get("work_group_size", 256)

        # 如果没有指定max_batch_size，根据GPU显存自动计算
        if max_batch_size is None:
            max_batch_size = self._calculate_optimal_batch_size()

        # L-NEW1修复: 与配置层保持一致的上限检查（16M）
        _max_batch_size_limit = 16777216  # 16M，与 config_manager.py Schema 一致
        if max_batch_size > _max_batch_size_limit:
            raise ValueError(
                f"batch_size {max_batch_size} 超限 {_max_batch_size_limit} (配置层与引擎层统一)",
            )

        self._max_batch_size = max_batch_size
        self._program = program  # 可能为None（需要自行编译）
        self._batch_kernel: Any | None = None
        self._batch_kernel_local: Any | None = None  # local memory版本内核引用
        # 查询设备local memory大小（OpenCL标准属性），回退默认值16KB
        try:
            self._local_mem_size = device.device.local_mem_size
        except (AttributeError, RuntimeError, TypeError):
            self._local_mem_size = 16384  # 默认16KB

        # P2-2修复: 初始化缓冲区追踪器
        self._buffer_tracker = GPUBufferTracker()

        # 持久化 Buffer - 避免频繁分配/释放（PyOpenCL C扩展类型，无stubs故用Any）
        self._seed_buf = None  # PRNG模式：仅存傤32字节种子
        # self._keys_buf 已于 v4.2.1 PRNG 改造时移除，不再使用
        self._match_buf = None
        self._targets_buf = None
        self._target_hash160s: bytes | None = None  # 添加目标地址缓存
        self._targets_cached: bytes | None = None
        self._num_targets_cached = 0
        self._check_uncompressed = 0  # v4.2.1: 0=仅压缩, 1=也检查非压缩
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

        # v4.2.2 P1修复: try/finally 保护，防止 _verify() 异常导致 GPU Buffer 泄漏
        try:
            self._allocate_buffers()

            # 验证GPU内核(在分配缓冲区之后)
            self._verify()
        except Exception:
            self._release_buffers_on_error()
            raise

    @property
    def device(self) -> Any:  # GPUDevice
        """GPU设备对象.

        Returns:
            GPUDevice实例，包含OpenCL上下文、队列等设备信息

        """
        return self._device

    @property
    def max_batch_size(self) -> int:
        """最大批次大小.

        Returns:
            GPU内核能够处理的最大私钥数量

        """
        return self._max_batch_size

    @property
    def program(self) -> Any | None:  # Optional[cl.Program]
        """已编译的OpenCL程序.

        Returns:
            pyopencl.Program实例，或None（如果尚未编译）

        """
        return self._program

    def _compile(self) -> None:
        """编译 OpenCL 内核（带性能监控、缓存和重试机制）.

        P2-6修复: 添加内核编译缓存机制，避免每次启动都重新编译
        DEF-2修复: 编译失败时自动重试（最多4次，渐进策略+指数退避）
            第1次: 标准编译
            第2次: CL2.0标准编译 (延迟2s)
            第3次: Intel Arc CL2.0 优化编译 (延迟4s, -cl-no-signed-zeros -cl-mad-enable)
            第4次: 降级CL1.2编译 (延迟8s, -cl-std=CL1.2 -cl-mad-enable -cl-no-signed-zeros)
        COMP-2: 根据设备 OpenCL 版本自动跳过不兼容的策略
        """
        import time

        # P2-6修复: 尝试从缓存加载（标准编译的缓存）
        if self._load_kernel_cache():
            logger.info("使用缓存的OpenCL内核二进制")
            return

        compile_start_total = time.time()

        try:
            # COMP-2: 根据设备 OpenCL 版本选择编译策略
            device_ocl = getattr(self.device, "opencl_version", 1.2)
            if not isinstance(device_ocl, (int, float)):
                device_ocl = 1.2

            if device_ocl >= 2.0:
                strategies = COMPILE_STRATEGIES
                logger.debug(
                    f"COMP-2: OpenCL {device_ocl:.1f} >= 2.0, 使用完整{len(strategies)}级编译策略",
                )
            else:
                strategies = [
                    ("标准编译", []),
                    ("降级CL1.2编译", ["-cl-std=CL1.2", "-cl-mad-enable", "-cl-no-signed-zeros"]),
                ]
                logger.debug(
                    f"COMP-2: OpenCL {device_ocl:.1f} < 2.0, "
                    f"跳过 CL2.0 策略, 使用{len(strategies)}级编译策略",
                )

            # DEF-2修复: 使用共享重试编译函数
            self._program, strategy_idx = compile_kernel_with_retry(
                ctx=self.device.context,
                source=OPENCL_KERNEL_SOURCE,
                strategies=strategies,
                max_retries=len(strategies),
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
                    f"内核使用降级策略({strategies[strategy_idx][0]})编译成功，不缓存以避免锁定降级性能",
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
                        _old = self.max_batch_size
                        logger.info(f"根据性能优化调整batch_size: {_old} -> {profile.max_batch_size}")
                        self._max_batch_size = profile.max_batch_size
                else:
                    logger.debug("GPU优化器不可用，跳过性能配置创建")

            except Exception as opt_error:
                logger.warning("GPU性能优化失败: %s", opt_error)

        except RuntimeError:
            # compile_kernel_with_retry 已经记录了详细日志，直接向上传播
            raise

    def _verify(self):
        """ALG-3修复: 验证 GPU 计算正确性（增强版）.

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
            raise RuntimeError(f"GPU内核验证失败: 不应匹配虚拟目标,但match_flags[0]={match_flags[0]}")

        logger.info("[OK] GPU内核基础验证通过（虚拟目标不匹配）")

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

            logger.info(f"ALG-3增强验证: 测试私钥1 -> 地址 {test_address[:6]}...{test_address[-4:]}")
            logger.info(f"  Hash160: {test_hash160.hex()[:8]}...")

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
                _flag = match_flags[0]
                raise RuntimeError(
                    f"GPU内核增强验证失败: 私钥1应匹配{test_address},但match_flags[0]={_flag}",
                )

            logger.info("[OK] GPU内核增强验证通过（私钥1匹配地址%s）", test_address)

        except ImportError:
            logger.warning("ALG-3增强验证跳过: 无法导入地址生成器")
        except Exception as e:
            logger.error("ALG-3增强验证失败: %s，GPU内核可能产生错误结果", e, exc_info=True)
            raise RuntimeError(f"GPU内核增强验证失败: {e}") from e

    # P2-06修复: 内核缓存版本号。当内核算法或编译策略变更时递增此版本号，
    # 确保旧缓存自动失效并重新编译。
    KERNEL_CACHE_VERSION = 1

    def _generate_cache_key(self) -> str:
        """P2-6修复: 生成缓存键.

        基于设备信息、内核源码和缓存版本生成唯一的缓存键。
        P2-06增强: 纳入缓存版本号，保证版本升级后自动失效。
        """
        import hashlib

        # 使用设备信息、缓存版本和内核源码生成键
        device_info = f"{self.device.device.name}_{self.device.device.vendor}"
        source_fingerprint = (
            f"v{self.KERNEL_CACHE_VERSION}_"
            f"{OPENCL_KERNEL_SOURCE[:100]}"  # 取前100字符加速哈希
        )
        source_hash = hashlib.md5(source_fingerprint.encode(), usedforsecurity=False).hexdigest()[:8]

        cache_key = f"{device_info}_{source_hash}"
        # 替换非法字符
        cache_key = cache_key.replace(" ", "_").replace("-", "_")

        return cache_key

    def _get_cache_file(self) -> str:
        """P2-6修复: 获取缓存文件路径."""
        import os

        cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "cache")
        pathlib.Path(cache_dir).mkdir(exist_ok=True, parents=True)

        cache_key = self._generate_cache_key()
        cache_file = os.path.join(cache_dir, f"kernel_{cache_key}.bin")

        return cache_file

    def _load_kernel_cache(self) -> bool:
        """P2-6修复: 从缓存加载内核二进制.

        Returns:
            bool: 是否成功加载缓存

        """
        import pyopencl as cl

        cache_file = self._get_cache_file()

        if not pathlib.Path(cache_file).exists():
            logger.debug("缓存文件不存在: %s", cache_file)
            return False

        try:
            cached_binary = pathlib.Path(cache_file).read_bytes()

            # 从二进制加载程序
            self._program = cl.Program(
                self.device.context,
                [self.device.device],
                [cached_binary],
            ).build()

            logger.info("成功加载内核缓存: %s", cache_file)
            return True

        except (OSError, EOFError, ValueError) as e:
            logger.warning("加载内核缓存失败: %s", e)
            # 缓存损坏，删除它
            try:
                pathlib.Path(cache_file).unlink()
            except OSError as cleanup_error:
                # A类修复: 资源清理失败添加DEBUG日志
                logger.debug("清理损坏缓存文件失败（可忽略）: %s", cleanup_error)
            return False
        except Exception as e:
            logger.warning(f"加载内核缓存异常: {type(e).__name__}: {e}", exc_info=True)
            # CR审查修复: 未知异常也删除缓存，防止 pyopencl 异常导致损坏缓存永久残留
            with suppress(OSError):
                if pathlib.Path(cache_file).exists():
                    pathlib.Path(cache_file).unlink()
            return False

    def _save_kernel_cache(self) -> None:
        """P2-6修复 + DEF-2审查: 原子写入内核二进制到缓存.

        使用 tmp + os.replace 原子写入，防止并发写入导致缓存损坏。
        P2-06增强: 保存后自动清理旧版本缓存文件。
        """
        cache_file = self._get_cache_file()
        tmp_file = cache_file + ".tmp"

        try:
            # 获取编译后的二进制
            if self._program is None:
                raise RuntimeError("_save_kernel_cache should be called after successful compilation")
            binaries = self._program.get_info(cl.program_info.BINARIES)
            if binaries and len(binaries) > 0:
                binary = binaries[0]

                # 原子写入: 先写临时文件，再原子替换
                pathlib.Path(tmp_file).write_bytes(binary)
                pathlib.Path(tmp_file).replace(cache_file)  # 原子操作（Windows上也基本原子）

                logger.debug(f"内核缓存已保存: {cache_file} ({len(binary)} bytes)")

                # P2-06增强: 清理同一设备但不同版本的旧缓存
                self._cleanup_old_cache_versions()

        except (OSError, RuntimeError) as e:
            logger.warning("保存内核缓存失败: %s", e)
        except Exception as e:
            logger.warning(f"保存内核缓存异常: {type(e).__name__}: {e}", exc_info=True)
        else:
            return  # 成功时跳过清理
        # CR审查修复: 统一临时文件清理（消除重复代码）
        with suppress(OSError):
            if pathlib.Path(tmp_file).exists():
                pathlib.Path(tmp_file).unlink()

    def _cleanup_old_cache_versions(self):
        """P2-06增强: 清理同一设备但不同版本的旧缓存文件.

        扫描缓存目录，删除与当前设备匹配但版本号不同的旧缓存。
        防止多次升级后磁盘空间累积。
        """
        cache_file = self._get_cache_file()
        cache_dir = os.path.dirname(cache_file)
        current_base = os.path.basename(cache_file)

        if not pathlib.Path(cache_dir).is_dir():
            return

        try:
            # 从当前缓存文件名提取设备标识前缀 (格式: kernel_{device}_{vendor}_{hash}.bin)
            # 匹配同一设备但不同 hash 的旧缓存
            prefix_parts = current_base.rsplit("_", 1)  # 分离 hash 部分
            if len(prefix_parts) >= 2:
                device_prefix = prefix_parts[0]  # 不含 hash 的公共前缀
                # 提取更宽泛的标识: 设备名_厂商名
                parts = device_prefix.split("_", 2)  # kernel_{device}_{vendor}
                if len(parts) >= 3:
                    broad_prefix = "_".join(parts[:3])  # kernel_{device}_{vendor}

                    for entry in os.listdir(cache_dir):
                        if entry == current_base:
                            continue
                        if entry.startswith(broad_prefix) and entry.endswith(".bin"):
                            old_file = os.path.join(cache_dir, entry)
                            try:
                                pathlib.Path(old_file).unlink()
                                logger.debug("清理旧版本缓存: %s", entry)
                            except OSError:
                                pass
        except (OSError, RuntimeError):
            pass  # 清理失败不影响主流程

    def _calculate_optimal_batch_size(self) -> int:
        """根据GPU显存大小计算最优batch_size.

        使用共享工具函数，考虑目标地址缓冲区占用。
        """
        # 导入共享工具函数
        from ..utils.gpu_memory_utils import calculate_optimal_batch_size

        # 计算目标地址缓冲区大小（如果已准备）
        target_buffer_size = 0
        if hasattr(self, "_target_hash160s") and self._target_hash160s:
            target_buffer_size = len(self._target_hash160s)

        # 调用共享函数
        return calculate_optimal_batch_size(device=self.device, target_buffer_size=target_buffer_size)

    def _allocate_buffers(self):
        """预分配 GPU 内存缓冲区（PRNG模式）.

        P2-2修复: 添加缓冲区追踪
        v4.2.1修复: 使用GPU内存池分配缓冲区（如果已启用）
        PRNG改造: 删除大型 keys_buf，改用固定32字节 seed_buf
        OPT-3优化: match_buf 对齐到 64 字节边界，确保合并内存访问

        内存访问模式分析:
        - seed_buf (32B, READ_ONLY): 所有 work-item 读取相同值 -> __constant 缓存友好
        - match_buf (num_keys*4B, WRITE_ONLY): 每个 work-item 写 match_flags[gid]
          -> 连续 gid 写相邻内存地址 -> 完美合并写入，无 bank conflict
        - targets_buf (num_targets*20B, READ_ONLY): 每个 work-item 扫描全部目标
          -> 不同 work-item 读取相同数据 -> 缓存友好（L2 cache 命中率高）
        - precomp_buf (496*4B, READ_ONLY): 所有 work-item 读取相同表 -> __constant 缓存
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
            f"{self.max_batch_size * self.KEYS_BUFFER_SIZE_FACTOR // 1024 // 1024}MB）",
        )
        self._buffer_tracker.track_buffer("_seed_buf", self._seed_buf, 32)

        # 匹配结果缓冲区
        # OPT-3: 每个匹配标志4字节（int32），连续 gid 写入连续地址
        # 写入模式: match_flags[gid] = match_value
        # -> work-item N 写 offset = N*4, work-item N+1 写 offset = (N+1)*4
        # -> 完美合并写入: 32 work-items 写 128 字节连续块，1次内存事务
        # 注意: 4字节对齐天然满足（int32），无需额外 padding
        match_buf_size = self.max_batch_size * self.MATCH_BUFFER_SIZE_FACTOR
        if memory_pool:
            # 使用内存池分配（支持复用）
            self._match_buf = memory_pool.allocate(match_buf_size, cl.mem_flags.WRITE_ONLY)
            logger.debug("使用内存池分配匹配缓冲区: %s字节", match_buf_size)
        else:
            # 直接分配（回退模式）
            self._match_buf = cl.Buffer(
                self.device.context,
                cl.mem_flags.WRITE_ONLY,
                size=match_buf_size,
            )
            logger.debug("直接分配匹配缓冲区: %s字节", match_buf_size)

        # P2-2修复: 注册缓冲区追踪
        self._buffer_tracker.track_buffer("_match_buf", self._match_buf, match_buf_size)

        # 预分配主机内存
        self._match_flags = np.zeros(self.max_batch_size, dtype=np.int32)

        # 预计算表常量缓冲区（双重检查：属性 + tracker，防竞态重复分配）
        if self._precomp_buf is None and not self._buffer_tracker.is_tracked("_precomp_buf"):
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

        # v4.2.1优化: 记录内存池使用状态（纯持久化设计）
        if memory_pool:
            pool_stats = memory_pool.get_stats()
            logger.info(
                "GPU内存池状态 (v4.2.1纯持久化设计): "
                f"已分配={pool_stats['total_allocated']}, "
                f"已复用={pool_stats['total_reused']}, "
                f"当前内存={pool_stats['current_memory_mb']:.1f}MB, "
                f"池内缓冲={pool_stats['pooled_buffers']}个 | "
                "设计: 持久化缓冲区在引擎生命周期内重复使用，零运行时分配开销",
            )

    def set_targets(self, target_hash160s: bytes, num_targets: int, check_uncompressed: int = 0) -> None:
        """设置目标地址 Hash160 - 只需设置一次.

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
                logger.warning("释放旧 targets_buf 失败: %s", e)
            self._targets_buf = None

        # 创建新的目标缓冲区
        targets_array = np.frombuffer(target_hash160s, dtype=np.uint8)
        self._targets_buf = cl.Buffer(
            self.device.context,
            cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=targets_array,
        )

        # 注册到缓冲区追踪器
        if hasattr(self, "_buffer_tracker") and self._buffer_tracker:
            self._buffer_tracker.track_buffer("_targets_buf", self._targets_buf, len(target_hash160s))

        self._targets_cached = target_hash160s
        self._num_targets_cached = num_targets

        logger.info("GPU 目标地址设置完成: %s 个目标", num_targets)

    # ========================================================================
    # 辅助函数 - 拆分自 run_batch
    # ========================================================================

    def _validate_batch_params(self, num_keys: int, seed: bytes) -> None:
        """验证批次参数."""
        if num_keys <= 0 or num_keys > self.max_batch_size:
            raise ValueError(f"num_keys 必须在 1..{self.max_batch_size} 之间，当前为 {num_keys}")
        if len(seed) != 32:
            raise ValueError(f"seed 长度必须为 32 字节（PRNG模式），当前为 {len(seed)} 字节")

    def _check_memory_limit(self, num_keys: int) -> None:
        """检查GPU显存限制."""
        target_buffer_size = len(self._target_hash160s) if self._target_hash160s else 0
        required_memory = 32 + (num_keys * 4) + target_buffer_size
        required_memory_with_overhead = int(required_memory * 1.2)
        device_info = self.device.get_device_info() if hasattr(self.device, "get_device_info") else {}
        max_memory = device_info.get("global_mem_size", 0)
        safe_memory_limit = int(max_memory * 0.8) if max_memory > 0 else float("inf")
        if required_memory_with_overhead > safe_memory_limit:
            raise MemoryError(
                f"所需显存 {required_memory_with_overhead / 1024**2:.0f}MB "
                f"超过安全限制 {safe_memory_limit / 1024**2:.0f}MB",
            )

    def _write_seed_buffer(self, seed: bytes) -> None:
        """写入种子缓冲区."""
        if self._seed_buf is None:
            logger.error("_seed_buf 已释放，无法执行批处理")
            raise RuntimeError("_seed_buf 已释放")
        seed_array = _seed_bytes_to_u32_be_array(seed)
        try:
            cl.enqueue_copy(self.device.queue, self._seed_buf, seed_array)
        except Exception as e:
            # SUGGESTION-7: 添加exc_info保留完整堆栈信息
            logger.error("写入 seed_buf 失败: %s", e, exc_info=True)
            raise

    def _clear_match_buffer(self, num_keys: int) -> None:
        """清空匹配结果缓冲区."""
        import numpy as np

        if self._match_buf is None:
            logger.error("_match_buf 已释放，无法执行批处理")
            raise RuntimeError("_match_buf 已释放")
        try:
            cl.enqueue_fill_buffer(self.device.queue, self._match_buf, np.int32(0), 0, num_keys * 4)
        except Exception as e:
            logger.error("清空 match_buf 失败: %s", e, exc_info=True)
            raise

    def _execute_kernel(self, num_keys: int, local_work_size: int) -> tuple:
        """执行GPU内核（OPT-3 优化）.

        内核执行策略:
        1. 计算 global_work_size: 向上取整到 local_work_size 的整数倍
           - 确保所有 work-item 都属于完整 work-group，避免部分填充的 group
           - 多余 work-item 由内核内的 gid >= num_keys 检查跳过
        2. 选择内核版本: 根据 local memory 阈值决定使用 local 还是 global 版本
           - local memory 版: 带宽更高（~TB/s vs ~GB/s），但消耗共享内存配额
           - global memory 版: 不消耗 local memory，允许更多 work-group 并发

        OPT-3 优化说明:
        - local_work_size 由 self._work_group_size（智能检测）决定
        - local memory 阈值由 self._local_mem_threshold（可调参数）决定
        - local memory 大小查询设备属性，回退到保守值 16KB

        Args:
            num_keys: 本批次私钥数量
            local_work_size: 工作组大小 (work_group_size)

        Returns:
            cl.enqueue_copy 返回的读事件，用于等待完成

        """
        # OPT-3: global_work_size 计算
        # 向上取整到 local_work_size 倍数，确保 GPU 调度器可以高效分配 work-group
        # 多余 work-item 在内核开头被 if (gid >= num_keys) return; 跳过
        global_work_size = ((num_keys + local_work_size - 1) // local_work_size) * local_work_size

        target_bytes = self._num_targets_cached * 20
        local_mem_size = getattr(self, "_local_mem_size", 16384)

        # OPT-3: 使用可配置的 local memory 阈值
        # 条件1: local 版内核存在
        # 条件2: 目标数据非空
        # 条件3: 目标数据不超过 local memory 总大小
        # 条件4: 目标数据占比不超过阈值（默认80%），或目标数 <= 250（小数据集场景）
        #   阈值可通过 BTC_GPU_LOCAL_MEM_THRESHOLD 环境变量调整
        local_threshold = getattr(self, "_local_mem_threshold", 0.8)
        use_local_mem = (
            self._batch_kernel_local is not None
            and target_bytes > 0
            and target_bytes <= local_mem_size
            and (
                target_bytes <= int(local_mem_size * local_threshold) or self._num_targets_cached <= 250
            )
        )

        if use_local_mem:
            logger.debug(
                f"OPT-3: 使用 local memory 版内核: "
                f"target_bytes={target_bytes}B, "
                f"local_mem={local_mem_size}B, "
                f"ratio={target_bytes / local_mem_size:.1%}, "
                f"threshold={local_threshold:.0%}, "
                f"global_ws={global_work_size}, local_ws={local_work_size}",
            )
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
            logger.debug(
                f"OPT-3: 使用 global memory 版内核: "
                f"global_ws={global_work_size}, local_ws={local_work_size}, "
                f"num_keys={num_keys}, num_targets={self._num_targets_cached}",
            )
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

        # OPT-3: 异步读取匹配结果（非阻塞，通过返回的 event 同步）
        # 使用 match_flags[:num_keys] 视图而非整个数组，减少主机内存拷贝
        return cl.enqueue_copy(
            self.device.queue,
            self._match_flags[:num_keys],
            self._match_buf,
        )

    def _wait_for_completion(self, read_event, timeout_seconds: float = 30) -> bool:
        """等待GPU执行完成."""
        import time

        timeout_event = threading.Event()
        execution_completed = [False]

        def timeout_monitor():
            try:
                if not timeout_event.wait(timeout_seconds):
                    logger.error("GPU执行超时(%s秒)", timeout_seconds)
                    execution_completed[0] = False
            except Exception as e:
                logger.error("超时监控线程异常: %s", e, exc_info=True)
                execution_completed[0] = False

        # v5.2.1: 5ms polling interval — eliminates ~100ms dead time per batch on fast GPUs
        _poll_interval = 0.005  # 5ms (was 100ms)
        monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)
        monitor_thread.start()
        try:
            max_iterations = int(timeout_seconds / _poll_interval) + 50
            for _ in range(max_iterations):
                try:
                    status = read_event.command_execution_status
                    if status == cl.command_execution_status.COMPLETE:
                        execution_completed[0] = True
                        break
                except cl.Error:
                    execution_completed[0] = False
                    break
                time.sleep(_poll_interval)
        finally:
            timeout_event.set()
            monitor_thread.join(timeout=2.0)
        return execution_completed[0]

    def _release_buffers_on_error(self) -> None:
        """错误时释放缓冲区."""
        # 敏感缓冲区: 释放前尝试安全清除
        sensitive_bufs = {"_seed_buf", "_match_buf", "_targets_buf"}
        for buf_attr in ("_seed_buf", "_match_buf", "_targets_buf", "_precomp_buf"):
            buf = getattr(self, buf_attr, None)
            if buf is None:
                continue
            # P1安全修复: 错误路径也尝试清除敏感数据
            if buf_attr in sensitive_bufs and hasattr(buf, "size"):
                with suppress(Exception):
                    secure_clear_gpu_buffer(self.device.queue, buf, buf.size)
            released = False
            with suppress(Exception):
                if hasattr(self, "_buffer_tracker") and self._buffer_tracker:
                    self._buffer_tracker.release_buffer(buf_attr)
                    released = True
            if not released:
                with suppress(Exception):
                    buf.release()
            setattr(self, buf_attr, None)

    def _collect_matches(self, match_view, num_keys: int) -> list:
        """收集匹配结果."""
        matches = []
        for i in range(num_keys):
            if match_view[i] > 0:
                matches.append({"key_index": i, "target_index": int(match_view[i] - 1)})
        return matches

    def _record_performance(self, num_keys: int, batch_start_time: float, match_count: int) -> None:
        """记录性能指标."""
        import time

        with suppress(Exception):
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
                with suppress(Exception):
                    gpu_monitor = get_gpu_performance_monitor()
                    memory_mb = (32 + 1984 + num_keys * 4) / (1024 * 1024)
                    gpu_monitor.record_kernel_metrics(
                        batch_size=num_keys,
                        execution_time_ms=execution_time_ms,
                        memory_allocated_mb=memory_mb,
                        error_count=0,
                        match_count=match_count,
                    )
            if hasattr(self, "timeout_manager") and self.timeout_manager:
                self.timeout_manager.record_execution_time(execution_time_ms)
            if hasattr(self, "memory_monitor") and self.memory_monitor:
                self.memory_monitor.track_allocation(num_keys * 36)

    def run_batch(
        self,
        seed: bytes,
        num_keys: int,
        target_hash160s: bytes | None = None,
        num_targets: int = 0,
        stop_event: Any | None = None,
    ) -> list[dict]:
        """PRNG模式批量执行私钥碰撞检测."""
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
            self._batch_kernel = cast("cl.Program", self.program).batch_check

        # OPT-3: 使用智能检测的 work_group_size（而非硬编码 256）
        local_work_size = getattr(self, "_work_group_size", _DEFAULT_WORK_GROUP_SIZE)
        try:
            read_event = self._execute_kernel(num_keys, local_work_size)
        except Exception as e:
            logger.error("内核执行失败: %s", e, exc_info=True)
            raise RuntimeError(f"GPU内核执行失败: {e}") from e

        # 6. 等待完成
        if not self._wait_for_completion(read_event):
            self._release_buffers_on_error()
            raise RuntimeError("GPU执行超时，内核可能已hang")

        # 7. 收集结果
        matches = self._collect_matches(self._match_flags[:num_keys], num_keys)

        # 8. 记录性能
        self._record_performance(num_keys, batch_start_time, len(matches))

        return matches

    def _check_memory_leaks_on_shutdown(self, released_buffers: set[str]) -> None:
        """引擎关闭时强制检查并释放所有缓冲区。."""
        if not hasattr(self, "_buffer_tracker") or not self._buffer_tracker:
            return
        try:
            leak_report = self._buffer_tracker.force_check_on_shutdown()
            released_buffers.update(leak_report.get("released", []))

            for buf_name in released_buffers:
                if buf_name == "_seed_buf":
                    self._seed_buf = None
                elif buf_name == "_match_buf":
                    self._match_buf = None
                elif buf_name == "_targets_buf":
                    self._targets_buf = None
                elif buf_name == "_precomp_buf":
                    self._precomp_buf = None

            if leak_report["has_unreleased"] or leak_report["has_leak"]:
                logger.warning(
                    "GPU内存泄漏检测报告: "
                    f"未释放={leak_report['remaining_buffers']}, "
                    f"释放成功={len(leak_report['released'])}, "
                    f"释放失败={len(leak_report['release_failed'])}",
                )
                if leak_report["has_leak"]:
                    logger.error(f"发现{len(leak_report['release_failed'])}个缓冲区释放失败")
        except Exception as e:
            logger.error("内存泄漏检查失败: %s", e, exc_info=True)

    def _release_gpu_buffers(self, released_buffers: set[str]) -> None:
        """显式释放所有 OpenCL Buffer。."""
        # 敏感缓冲区列表: (名称, 缓冲区, 是否清除)
        buffers_to_release = [
            ("_seed_buf", self._seed_buf, True),
            ("_match_buf", self._match_buf, True),
            ("_targets_buf", self._targets_buf, True),
            ("_precomp_buf", self._precomp_buf, False),
        ]
        for buf_name, buf, needs_clear in buffers_to_release:
            if buf_name in released_buffers:
                logger.debug("缓冲区 %s 已释放，跳过", buf_name)
                continue
            if buf is not None:
                try:
                    # P1安全修复: 释放前用零覆盖敏感数据
                    if needs_clear and hasattr(buf, "size"):
                        secure_clear_gpu_buffer(self.device.queue, buf, buf.size)
                    buf.release()
                    logger.debug("已释放 %s", buf_name)
                    if hasattr(self, "_buffer_tracker"):
                        self._buffer_tracker.release_buffer(buf_name)
                except Exception as e:
                    logger.warning("释放 %s 失败: %s", buf_name, e)

        self._seed_buf = None
        self._match_buf = None
        self._targets_buf = None
        self._precomp_buf = None

    def _close_async_logging(self) -> None:
        """关闭异步日志处理器。."""
        if hasattr(self, "_async_log_handler") and self._async_log_handler:
            try:
                self._async_log_handler.close()
                logger.info("GPU异步日志已关闭")
            except Exception as e:
                logger.debug("关闭异步日志失败: %s", e)

    def cleanup(self) -> None:
        """清理GPU资源.

        P1修复: 显式释放OpenCL Buffer,防止显存泄漏
        改进: 删除未使用的pyopencl导入(Buffer对象自带release方法)
        P5增强: 引擎关闭时强制检查内存泄漏
        v4.2.1: 关闭异步日志处理器
        v4.2.1修复: 避免双重释放缓冲区
        v4.2.1修复: 缓冲区归还到内存池（支持复用）
        v4.2.1优化: 纯持久化设计 - 直接释放，不归还到内存池
        """
        # 注意: 不需要导入pyopencl, OpenCL Buffer对象自带release()方法

        # v4.2.1优化: 纯持久化设计 - 不需要内存池引用（缓冲区直接释放）
        # memory_pool = getattr(self, '_gpu_memory_pool', None)  # 不再需要

        # v4.2.1修复: 跟踪已释放的缓冲区，避免双重释放
        released_buffers: set[str] = set()

        self._check_memory_leaks_on_shutdown(released_buffers)
        self._release_gpu_buffers(released_buffers)
        self._close_async_logging()
        self._match_flags = None
        self._program = None
        self._batch_kernel = None
        self._batch_kernel_local = None

    def _setup_async_logging(self, log_file: str, max_bytes: int, backup_count: int) -> None:
        """设置异步日志处理器（v4.2.1新增）.

        Args:
            log_file: 日志文件路径
            max_bytes: 单个文件最大字节数
            backup_count: 备份文件数

        """
        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not pathlib.Path(log_dir).exists():
                pathlib.Path(log_dir).mkdir(mode=0o750, exist_ok=True, parents=True)

            # 创建异步文件处理器
            from ..utils.logger import AsyncFileHandler

            self._async_log_handler = AsyncFileHandler(
                log_file,
                max_bytes=max_bytes,
                backup_count=backup_count,
            )
            self._async_log_handler.setLevel(logging.DEBUG)

            # 添加到GPU引擎logger
            logger.addHandler(self._async_log_handler)

            logger.info(f"GPU异步日志已启用: {log_file} (max={max_bytes / 1024 / 1024:.0f}MB)")

        except Exception as e:
            logger.warning("异步日志启用失败: %s，使用同步日志", e)
            self._async_log_handler = None
