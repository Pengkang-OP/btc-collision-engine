"""GPU async execution optimization module.

Implements double-buffered async execution to improve GPU utilization:
1. 双OpenCL队列(计算+传输)
2. 双缓冲机制(消除CPU-GPU等待)
3. 安全保护(超时+回退)
"""

import threading
import time
from contextlib import suppress
from typing import Any, Callable

import numpy as np

# 统一日志获取 + 修复缺失导入
from ..utils import get_configured_logger

logger = get_configured_logger("AsyncGPUExecutor")


# v4.2.2 M5: 统一端序转换 → 从 gpu/seed_utils.py 导入单一权威实现
from .seed_utils import _seed_bytes_to_u32_be_array  # noqa: E402

# 队列深度管理常量
DEFAULT_QUEUE_DEPTH = 4  # GPU 队列中保持的预提交批次数量

# GPU型号特定配置
GPU_SPECIFIC_CONFIG = {
    # NVIDIA GTX 1660 系列优化配置
    "1660": {
        "queue_depth": 10,  # 增加队列深度，提高GPU利用率
        "initial_batch_size": 131072,  # 增加初始批次大小，提高吞吐量
        "max_batch_size": 524288,  # 增加最大批次大小，提高内存利用率
        "memory_factor": 0.75,  # 增加内存使用因子，提高内存利用率
    },
    # NVIDIA RTX 30系列
    "rtx30": {
        "queue_depth": 8,
        "initial_batch_size": 262144,
        "max_batch_size": 1048576,
        "memory_factor": 0.85,
    },
    # NVIDIA RTX 40系列
    "rtx40": {
        "queue_depth": 12,
        "initial_batch_size": 524288,
        "max_batch_size": 2097152,
        "memory_factor": 0.9,
    },
    # NVIDIA GTX 10系列
    "10": {
        "queue_depth": 6,
        "initial_batch_size": 131072,
        "max_batch_size": 524288,
        "memory_factor": 0.65,
    },
    # NVIDIA GTX 9系列
    "9": {
        "queue_depth": 4,
        "initial_batch_size": 65536,
        "max_batch_size": 262144,
        "memory_factor": 0.55,
    },
    # AMD Radeon RX 6000系列
    "amd6000": {
        "queue_depth": 7,
        "initial_batch_size": 262144,
        "max_batch_size": 1048576,
        "memory_factor": 0.8,
    },
    # AMD Radeon RX 7000系列
    "amd7000": {
        "queue_depth": 9,
        "initial_batch_size": 524288,
        "max_batch_size": 2097152,
        "memory_factor": 0.85,
    },
    # Intel Arc系列 - v4.2.1 极致性能配置
    "intel": {
        "queue_depth": 32,  # Arc A770最大队列深度，消除GPU等待
        "initial_batch_size": 4194304,  # 提高初始批次大小到400万
        "max_batch_size": 16777216,  # 匹配gpu_profiles.json的配置（1600万）
        "memory_factor": 0.90,  # 充分利用16GB显存
    },
    # 默认配置
    "default": {
        "queue_depth": 4,
        "initial_batch_size": 65536,
        "max_batch_size": 262144,
        "memory_factor": 0.6,
    },
}


class _PendingBatch:
    """队列深度管理中，单个已提交到 GPU 但尚未取回结果的批次描述符。

    Attributes:
        read_event: OpenCL 事件，结果回读完成后触发
        buf: 对应的缓冲区字典，包含 'matches' 和 'match_flags'
        num_keys: 当前批次的密钥数量
        seed: 当前批次对应的 32 字节种子，用于 seed+gid 还原私钥
    """

    __slots__ = ("read_event", "buf", "num_keys", "seed")

    def __init__(self, read_event: Any, buf: Any, num_keys: int, seed: bytes) -> None:
        self.read_event = read_event  # cl.Event: 结果回读完成事件
        self.buf = buf  # 对应的缓冲区字典 {matches, match_flags}
        self.num_keys = num_keys
        self.seed = seed  # 供上层用 seed+gid 还原私钥


class _SyncFallbackError(Exception):
    """异步执行回退信号：已通过同步路径完成执行，携带结果。

    用于在 _allocate_buffer / _transfer_seed / _clear_matches_buffer 中
    当异步预处理失败时，已完成同步执行并把结果带回外层，避免二次执行和结果丢失。
    """

    __slots__ = ("matches", "execution_time_ms")

    def __init__(self, matches: list[dict], execution_time_ms: float) -> None:
        super().__init__(f"Async fallback complete: {len(matches)} matches, {execution_time_ms:.1f}ms")
        self.matches = [dict(m) for m in matches]
        self.execution_time_ms = execution_time_ms


# 异步模式恢复常量
ASYNC_RECOVER_AFTER_SYNC_COUNT = 10  # 连续同步回退低于此阈值时，尝试恢复异步模式
MAX_CONSECUTIVE_SYNC_FALLBACKS = 50  # 超过此阈值停止尝试恢复异步


class AsyncGPUExecutor:
    """异步GPU执行器

    使用双缓冲和双队列实现异步执行，提升GPU利用率到90%+。

    核心机制:
    - 双OpenCL队列（计算队列 + 传输队列），独立工作，重叠执行
    - 双缓冲机制（buffer_a / buffer_b），消除CPU-GPU等待
    - PRNG模式：CPU仅生成32字节种子，GPU内核自行计算 key = seed + gid
    - 队列深度优化：预提交批次 FIFO 队列，保持 GPU 始终满载
    - 自动回退：异步失败时自动切换到同步模式

    优化历史:
    - v4.2.1: 预取队列、智能缓冲切换、queue_depth 预提交
    - v4.2.2: M5 种子端序转换统一、P0 批次注册修复
    - v4.5.0: 文档和注释优化

    Attributes:
        device: GPUDevice实例
        max_batch_size: 最大批次大小
        queue_depth: GPU命令队列深度
        initial_batch_size: 初始批次大小
    """

    def __init__(
        self, gpu_device: Any, max_batch_size: int, queue_depth: int = DEFAULT_QUEUE_DEPTH
    ) -> None:
        """
        初始化异步执行器

        Args:
            gpu_device: GPUDevice实例
            max_batch_size: 最大批次大小
            queue_depth: GPU 命令队列深度，默认 4（GPU 中同时保持的预提交批次数）
        """
        self.device = gpu_device

        # 根据GPU型号选择合适的配置
        gpu_model = self._detect_gpu_model()
        gpu_config = self._get_gpu_config(gpu_model)

        # 使用GPU特定配置或默认值
        # queue_depth: 构造参数显式传入优先，GPU型号配置仅作推荐
        self.max_batch_size = gpu_config.get("max_batch_size", max_batch_size)
        self.queue_depth = max(1, queue_depth)
        self.initial_batch_size = gpu_config.get("initial_batch_size", 65536)

        # 预计算表缓冲区（常量，生命周期与 executor 一致）
        self.precomp_buffer: Any | None = None

        # 种子缓冲区（32字节 = 8 uint32，替代大型 keys 缓冲区）
        self.seed_buffer: Any | None = None

        # 双缓冲（匹配结果，不再需要 keys 缓冲区）
        self.buffer_a: dict[str, Any] = {"matches": None, "match_flags": None}
        self.buffer_b: dict[str, Any] = {"matches": None, "match_flags": None}

        # 异步状态
        self.current_buffer = "A"
        self.pending_event: Any | None = None
        self.is_async_ready = False

        # 异步流水线状态 延迟结果等待
        self._pending_buffer: Any | None = None  # 待处理的缓冲区引用
        self._pending_num_keys = 0  # 待处理的批次大小
        self.check_uncompressed = 0  # v4.2.1: 由 GPUDeviceManager.initialize() 覆写

        # v4.2.1: 显式 work_group_size（内核启动必须指定，避免 OpenCL 自动选择次优值）
        # 从设备信息获取最优 work_group_size，Intel Arc 建议 256，NVIDIA/AMD 建议 256-512
        self._work_group_size = self._detect_optimal_work_group_size(gpu_config)
        self._align_global_size = True  # 是否对齐 global_work_size 到 local_work_size 的整数倍

        # 预取队列优化v4.2.1
        self._prefetch_enabled = True
        self._next_batch_ready = threading.Event()
        self._next_batch_data: bytes | None = None
        self._next_batch_size = 0

        # 队列深度优化 v4.2.1：预提交批次 FIFO 队列
        # 每个元素是 _PendingBatch，记录已提交但尚未取回结果的批次
        self._prefetch_events: list[_PendingBatch] = []
        self._prefetch_lock = threading.Lock()  # 保护 _prefetch_events 的线程安全

        # S2修复: 添加缓冲区池操作锁，保护 _pool_index 等状态的线程安全
        self._pool_lock = threading.Lock()

        # 统计
        self.async_executions = 0
        self.sync_fallbacks = 0
        self.prefetch_hits = 0  # 预取命中次数
        self.prefetch_misses = 0  # 预取未命中次数
        self.queue_depth_hits = 0  # 队列深度优化命中（GPU 不等待 CPU）

        # 异步模式恢复：连续同步回退追踪
        self._consecutive_sync_fallbacks = 0  # 连续同步回退计数器
        self._async_mode_disabled = False  # 异步模式是否被禁用
        self._last_async_attempt_time = 0.0  # 上次尝试异步的时间戳

        logger.info(
            "异步GPU执行器已初始化: "
            f"GPU型号={gpu_model}, "
            f"max_batch={self.max_batch_size}, "
            f"initial_batch={self.initial_batch_size}, "
            f"预取=启用, queue_depth={self.queue_depth}"
        )

    def _detect_gpu_model(self) -> str:
        """检测GPU型号并返回配置标识

        通过设备信息中的 name 字段检测具体 GPU 型号，
        返回与 GPU_SPECIFIC_CONFIG 中对应的配置键名。

        检测优先级:
        1. 具体型号匹配 (如 "1660", "rtx40")
        2. 系列匹配 (如 "rtx30", "amd6000")
        3. 厂商匹配 (如 "intel", "amd")
        4. 回退到 "default"

        Returns:
            GPU型号标识，如 "1660", "rtx40", "intel", "default" 等
        """
        if hasattr(self.device, "device_info") and self.device.device_info:
            device_name = self.device.device_info.get("name", "").lower()
            if "1660" in device_name:
                return "1660"
            elif "rtx 40" in device_name or "rtx40" in device_name:
                return "rtx40"
            elif "rtx 30" in device_name or "rtx30" in device_name:
                return "rtx30"
            elif "rtx" in device_name:
                return "rtx30"  # 默认RTX系列使用rtx30配置
            elif (
                "gtx 10" in device_name
                or "1060" in device_name
                or "1070" in device_name
                or "1080" in device_name
            ):
                return "10"
            elif (
                "gtx 9" in device_name
                or "960" in device_name
                or "970" in device_name
                or "980" in device_name
            ):
                return "9"
            elif "rx 7" in device_name or "rx7" in device_name:
                return "amd7000"
            elif "rx 6" in device_name or "rx6" in device_name:
                return "amd6000"
            elif "amd" in device_name or "radeon" in device_name:
                return "amd6000"  # 默认AMD系列使用amd6000配置
            elif "intel" in device_name or "iris" in device_name or "arc" in device_name:
                return "intel"
        return "default"

    def _get_gpu_config(self, gpu_model: str) -> dict:
        """
        获取GPU特定配置

        Args:
            gpu_model: GPU型号标识

        Returns:
            GPU配置字典
        """
        return GPU_SPECIFIC_CONFIG.get(gpu_model, GPU_SPECIFIC_CONFIG.get("default", {}))

    def _detect_optimal_work_group_size(self, gpu_config: dict) -> int:
        """检测最优 work_group_size

        v4.2.1: 从 GPU 设备信息和型号配置推断最优 work_group_size。
        显式设置 work_group_size 可避免 OpenCL 运行时自动选择次优值，
        在 Intel Arc GPU 上提升尤为显著（从自动 ~64 到显式 256）。

        Args:
            gpu_config: GPU 型号特定配置字典

        Returns:
            最优 work_group_size (64-1024)
        """
        # 优先从 GPU 设备信息获取（如果设备已初始化）
        device_ws = None
        with suppress(AttributeError):
            if hasattr(self.device, "device_info") and self.device.device_info:
                device_ws = self.device.device_info.get("work_group_size")

        if device_ws and isinstance(device_ws, int) and 64 <= device_ws <= 1024:
            return device_ws

        # 从 GPU 型号配置获取默认值
        model_ws_map = {
            "1660": 256,  # GTX 1660: 256 最优
            "rtx30": 256,  # RTX 30: 256 最优
            "rtx40": 512,  # RTX 40: 512 更大工作组提升吞吐
            "10": 256,  # GTX 10: 256
            "9": 256,  # GTX 9: 256
            "amd6000": 256,  # RX 6000: 256
            "amd7000": 256,  # RX 7000: 256
            "intel": 256,  # Intel Arc: 256 (A770 验证最优)
            "default": 256,
        }

        # S4修复: 直接调用 _detect_gpu_model() 方法，而非使用 getattr
        gpu_model = self._detect_gpu_model()
        return model_ws_map.get(gpu_model, 256)

    def initialize_buffers(self, context: Any, num_keys: int) -> None:
        """初始化缓冲区池（PRNG模式：seed缓冲区替代keys缓冲区）

        队列深度优化 v4.2.1：
        - 分配 queue_depth 个匹配结果缓冲区，支持多批次同时在 GPU 中执行
        - buffer_a / buffer_b 作为历史兼容引用，指向缓冲区池的头两个

        PRNG 模式优势:
        - 种子缓冲区仅 32 字节（替代原 num_keys*32 字节的 keys 缓冲区）
        - 大幅减少 CPU-GPU 传输量
        - 支持更大批次大小

        Args:
            context: OpenCL上下文
            num_keys: 每个缓冲的密钥数量
        """
        import numpy as np
        import pyopencl as cl

        # 确保缓冲区大小不超过max_batch_size
        if num_keys > self.max_batch_size:
            logger.warning(
                f"请求的缓冲区大小({num_keys})超过GPU配置的最大批次大小({self.max_batch_size})，"
                f"将自动调整为 {self.max_batch_size}"
            )
            num_keys = self.max_batch_size

        # 更新内部max_batch_size以匹配实际分配的缓冲区大小
        self._actual_batch_size = num_keys

        logger.info(f"创建缓冲区池（PRNG模式）: num_keys={num_keys}, queue_depth={self.queue_depth}")

        # 预计算表 GPU 常量缓冲区（如果尚未初始化）
        if self.precomp_buffer is None:
            from .precompute import get_precomp_table

            precomp_data = get_precomp_table()
            self.precomp_buffer = cl.Buffer(
                context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=precomp_data
            )
            logger.info("预计算表缓冲区已创建: shape=(496,), dtype=uint32")

        # 种子缓冲区（固定32字节，替代原 num_keys*32 字节的 keys 缓冲区）
        if self.seed_buffer is None:
            self.seed_buffer = cl.Buffer(
                context,
                cl.mem_flags.READ_ONLY,
                size=32,  # 固兵2字节 = 8 uint32
            )
            logger.info(f"种子缓冲区已创建: 32字节（PRNG模式，节省约{num_keys * 32 / 1024 / 1024}MB)")

        # 创建 queue_depth 个缓冲区构成缓冲区池
        self._buffer_pool: list[dict] = []
        for _i in range(self.queue_depth):
            buf = {
                "matches": cl.Buffer(context, cl.mem_flags.READ_WRITE, size=num_keys * 4),
                "match_flags": np.zeros(num_keys, dtype=np.int32),
            }
            self._buffer_pool.append(buf)

        # 将 buffer_a / buffer_b 指向池的头两个（历史兼容 + 回退模式使用）
        self.buffer_a = self._buffer_pool[0]
        self.buffer_b = self._buffer_pool[1] if len(self._buffer_pool) > 1 else self._buffer_pool[0]

        # 缓冲区池头指针
        self._pool_index = 0

        logger.info(
            f"缓冲区池创建完成（PRNG模式）: {self.queue_depth} 个缓冲区，"
            f"总显存消耗约 {self.queue_depth * num_keys * 4 / 1024 / 1024:.1f} MB"
        )

    def get_actual_batch_size(self) -> int:
        """获取实际分配的缓冲区大小"""
        return getattr(self, "_actual_batch_size", self.max_batch_size)

    def prefetch_next_batch(self, seed: bytes, num_keys: int) -> None:
        """预存下一批种子（PRNG模式：仅缓存32字节种子，v4.2.1）

        Args:
            seed: 32字节随机种子
            num_keys: 密钥数量（保留参数，用于兼容调用方）
        """
        if not self._prefetch_enabled:
            return

        try:
            # 保存预取种子（仅32字节）
            self._next_batch_data = seed
            self._next_batch_size = num_keys
            self._next_batch_ready.set()

            logger.debug(f"预取下一批种子: {num_keys} keys")
        except (ValueError, TypeError) as e:
            logger.warning(f"预取种子数据无效: {type(e).__name__}: {e}")
            self._next_batch_ready.clear()
        except Exception as e:
            logger.warning(f"预取失败: {type(e).__name__}: {e}")
            self._next_batch_ready.clear()

    def run_batch_async(
        self, seed: bytes, num_keys: int, program: Any, targets_buf: Any, num_targets: int
    ) -> tuple[list[dict], float]:
        """
        异步执行批次（PRNG模式：seed替代private_keys）

        v4.2.1 队列深度优化：
        - GPU 队列中始终保持多个待执行批次（最多 queue_depth 个）
        - 当队列没满时，直接提交新批次并立即返回（GPU 不等待 CPU）
        - 当队列已满时，取回最老的一个批次结果，再提交新批次
        - PRNG改造: CPU只传32字节种子，GPU内核自行生成 key = seed + gid。

        Args:
            seed: 32字节随机种子（替代原 private_keys 大缓冲区）
            num_keys: 密鑰数量
            program: OpenCL程序
            targets_buf: 目标地址缓冲区
            num_targets: 目标数量

        Returns:
            (matches, execution_time_ms)
        """
        start_time = time.time()

        # 检查是否支持异步（含异步模式恢复检查）
        self._check_async_recovery()
        if (
            not self.device.enable_async_execution
            or not self.device.compute_queue
            or self._async_mode_disabled
        ):
            return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)

        try:
            # === 队列深度优化核心逻辑 ===
            #
            # 修复竞争条件（race condition）：
            # 原实现先分配缓冲区再等待旧批次，导致 round-robin 分配到的缓冲区
            # 可能仍被 GPU 使用（旧批次未完成），新数据写入会覆盖旧缓冲区数据。
            #
            # 正确顺序：步骤0 先回收 → 步骤1 再分配 → 步骤2-6 正常执行
            # 这样可以保证 round-robin 分配到的缓冲区已被 GPU 安全释放。

            # 步骤 0（关键修复）：队列已满时，先回收最老批次，确保缓冲区安全可用
            prev_matches: list[dict] = []
            oldest_batch: _PendingBatch | None = None
            with self._prefetch_lock:
                if len(self._prefetch_events) >= self.queue_depth:
                    oldest_batch = self._prefetch_events.pop(0)
            if oldest_batch is not None:
                prev_matches = self._collect_oldest_batch_results_from(oldest_batch)

            # 步骤 1：现在可以安全分配缓冲区（oldest 已完成，round-robin 的 buf 确保空闲）
            current_buf = self._allocate_buffer(seed, num_keys, program, targets_buf, num_targets)

            # 步骤 2. 把本次种子写入 seed_buffer（传输队列，非阻塞）
            transfer_event = self._transfer_seed(seed, num_keys, program, targets_buf, num_targets)

            # 步骤 3. 清空当前缓冲的匹配结果（计算队列）
            if not self._clear_matches_buffer(
                current_buf, num_keys, seed, program, targets_buf, num_targets
            ):
                return [], 0.0

            # 步骤 4-6. 执行内核并注册结果
            kernel_event, read_event = self._execute_and_register(
                current_buf, num_keys, seed, program, targets_buf, num_targets, transfer_event
            )
            if kernel_event is None or read_event is None:
                return [], 0.0

            # v4.2.2 P0修复: 将批次注册到预提交队列，确保异步结果可被收集
            self._prefetch_events.append(
                _PendingBatch(
                    read_event=read_event,
                    buf=current_buf,
                    num_keys=num_keys,
                    seed=seed,
                )
            )

            execution_time_ms = (time.time() - start_time) * 1000

            # 异步执行成功，重置回退计数
            self._on_async_success()

            return prev_matches, execution_time_ms

        except _SyncFallbackError as sf:
            # 异步预处理（缓冲区分配/传输/清理）失败，已通过同步路径完成执行
            # 直接返回同步路径的结果，避免二次执行
            logger.debug(
                f"异步预处理回退到同步模式: {len(sf.matches)} matches, {sf.execution_time_ms:.1f}ms"
            )
            return sf.matches, sf.execution_time_ms
        except (RuntimeError, MemoryError) as e:
            logger.warning(f"异步执行OpenCL错误,回退到同步模式: {type(e).__name__}: {e}")
            self.sync_fallbacks += 1
            self._track_sync_fallback()
            return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
        except Exception as e:
            logger.warning(f"异步执行失败,回退到同步模式: {type(e).__name__}: {e}")
            self.sync_fallbacks += 1
            self._track_sync_fallback()
            return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)

    def flush_pending(self) -> list[tuple[bytes, list[dict]]]:
        """收集所有尚未取回的异步执行结果

        在主循环结束后调用，确保 _prefetch_events 队列中所有已提交的 GPU 批次结果不丢失。

        Returns:
            List[Tuple[bytes, List[Dict]]]：每个元素为 (seed, matches_for_that_batch)，
            其中 seed 是该批次对应的 32 字节种子，matches_for_that_batch 是该批次的匹配列表。
            调用方必须使用每批次自己的 seed 重建私钥，而不能用同一个 seed 处理所有匹配。
        """
        batch_results: list[tuple[bytes, list[dict]]] = []

        # 处理所有预提交队列中的待处理批次
        while True:
            with self._prefetch_lock:
                if not self._prefetch_events:
                    break
                oldest = self._prefetch_events.pop(0)
            try:
                try:
                    oldest.read_event.wait(timeout=30)
                except TypeError:
                    oldest.read_event.wait()
            except RuntimeError as e:
                logger.warning(f"等待最后一批结果OpenCL错误: {e}")
                continue
            except Exception as e:
                logger.warning(f"等待最后一批结果失败: {type(e).__name__}: {e}")
                continue

            if oldest.buf is not None:
                batch_matches: list[dict] = []
                for i in range(oldest.num_keys):
                    if oldest.buf["match_flags"][i] > 0:
                        batch_matches.append(
                            {"key_index": i, "target_index": int(oldest.buf["match_flags"][i] - 1)}
                        )
                # 每批次携带自身的 seed，确保上层能用正确 seed 重建私钥
                batch_results.append((oldest.seed, batch_matches))

        # 清除历史兼容字段
        self.pending_event = None
        self._pending_buffer = None
        self._pending_num_keys = 0
        return batch_results

    def _is_buffer_valid(self) -> bool:
        """检查缓冲区和传输队列的有效性

        Returns:
            bool: 如果所有必要的缓冲区和队列都有效返回True，否则返回False
        """
        # 检查seed_buffer是否仍然有效
        if self.seed_buffer is None:
            logger.warning("种子缓冲区已释放，回退到同步模式")
            return False

        # 检查transfer_queue是否仍然可用
        if not hasattr(self.device, "transfer_queue") or self.device.transfer_queue is None:
            logger.warning("传输队列已不可用，回退到同步模式")
            return False

        return True

    def _collect_oldest_batch_results_from(self, batch: _PendingBatch) -> list[dict]:
        """等待并收集批次结果

        Args:
            batch: 已从 _prefetch_events 弹出的 _PendingBatch（调用方已持有锁完成 pop）
        """
        prev_matches: list[dict] = []
        oldest = batch
        timeout_seconds = 30
        try:
            completed = oldest.read_event.wait(timeout=timeout_seconds)  # PyOpenCL使用秒作为浮点数
            if not completed:
                logger.warning(f"异步执行超时({timeout_seconds}秒)")
                raise RuntimeError(f"异步执行超时({timeout_seconds}秒)")
        except TypeError as te:
            error_msg = str(te).lower()
            if "timeout" in error_msg or "parameter" in error_msg:
                logger.debug("wait()不支持timeout参数，使用无参版本")
                oldest.read_event.wait()
            else:
                logger.warning(f"等待批次时TypeError（非timeout相关）: {te}")
                raise
        except (RuntimeError, TimeoutError):
            raise
        except Exception as wait_err:
            logger.exception(f"等待批次完成时未知异常: {type(wait_err).__name__}: {wait_err}")
            raise RuntimeError(f"异步执行失败: {wait_err}") from wait_err

        try:
            for i in range(oldest.num_keys):
                if oldest.buf["match_flags"][i] > 0:
                    prev_matches.append(
                        {
                            "key_index": i,
                            "target_index": int(oldest.buf["match_flags"][i] - 1),
                        }
                    )
        except (IndexError, ValueError, AttributeError) as e:
            logger.warning(f"收集批次结果数据异常: {type(e).__name__}: {e}")
        except Exception as e:
            logger.warning(f"收集批次结果失败: {type(e).__name__}: {e}")
        self.queue_depth_hits += 1
        return prev_matches

    def _allocate_buffer(self, seed, num_keys, program, targets_buf, num_targets):
        """步骤1: 分配工作缓冲区"""
        buf_pool = getattr(self, "_buffer_pool", None)
        if buf_pool is not None:
            with self._pool_lock:
                pool_idx = getattr(self, "_pool_index", 0)
                try:
                    current_buf = buf_pool[pool_idx % len(buf_pool)]
                    self._pool_index = (pool_idx + 1) % len(buf_pool)
                    return current_buf
                except (IndexError, ValueError) as e:
                    logger.warning(f"缓冲区池索引异常: {type(e).__name__}: {e}，回退到同步模式")
                    return self._run_batch_sync_fallback(
                        seed, num_keys, program, targets_buf, num_targets
                    )
                except Exception as e:
                    logger.warning(f"分配缓冲区失败: {type(e).__name__}: {e}，回退到同步模式")
                    return self._run_batch_sync_fallback(
                        seed, num_keys, program, targets_buf, num_targets
                    )
        else:
            try:
                current_buf = self.buffer_a if self.current_buffer == "A" else self.buffer_b
                self.current_buffer = "B" if self.current_buffer == "A" else "A"
                return current_buf
            except (AttributeError, KeyError) as e:
                logger.warning(f"获取双缓冲区属性异常: {type(e).__name__}: {e}，回退到同步模式")
                return self._run_batch_sync_fallback(seed, num_keys, program, targets_buf, num_targets)
            except Exception as e:
                logger.warning(f"获取双缓冲区失败: {type(e).__name__}: {e}，回退到同步模式")
                return self._run_batch_sync_fallback(seed, num_keys, program, targets_buf, num_targets)

    def _run_batch_sync_fallback(self, seed, num_keys, program, targets_buf, num_targets):
        """回退到同步执行并抛出结果异常（供 _allocate_buffer 使用）"""
        matches, exec_time = self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
        self.sync_fallbacks += 1
        self._track_sync_fallback()
        raise _SyncFallbackError(matches, exec_time)

    def _track_sync_fallback(self) -> None:
        """追踪连续同步回退，管理异步模式恢复"""
        self._consecutive_sync_fallbacks += 1
        if (
            self._consecutive_sync_fallbacks >= MAX_CONSECUTIVE_SYNC_FALLBACKS
            and not self._async_mode_disabled
        ):
            self._async_mode_disabled = True
            logger.warning(
                f"连续同步回退({self._consecutive_sync_fallbacks}次)超过阈值"
                f"({MAX_CONSECUTIVE_SYNC_FALLBACKS})，已禁用异步模式"
            )

    def _check_async_recovery(self) -> None:
        """检查是否可以恢复异步模式

        当连续同步执行次数足够低时，尝试恢复异步执行。
        """
        if not self._async_mode_disabled:
            self._consecutive_sync_fallbacks = 0  # 异步正常运行，重置计数器
            return
        current_time = time.time()
        # 每隔 ASYNC_RECOVER_AFTER_SYNC_COUNT 次同步回退，尝试恢复一次
        if (
            self._consecutive_sync_fallbacks > 0
            and self._consecutive_sync_fallbacks % ASYNC_RECOVER_AFTER_SYNC_COUNT == 0
            and current_time - self._last_async_attempt_time > 30
        ):
            self._async_mode_disabled = False
            self._last_async_attempt_time = current_time
            logger.info(f"尝试恢复异步模式 (连续同步次数: {self._consecutive_sync_fallbacks})")

    def _on_async_success(self) -> None:
        """异步执行成功后重置回退计数"""
        self._consecutive_sync_fallbacks = 0
        if self._async_mode_disabled:
            self._async_mode_disabled = False
            logger.info("异步模式已恢复")

    def _transfer_seed(self, seed, num_keys, program, targets_buf, num_targets):
        """步骤2: 传输种子到设备"""
        try:
            seed_array = _seed_bytes_to_u32_be_array(seed[:32])
        except (ValueError, TypeError) as e:
            logger.warning(f"准备种子数据格式错误: {type(e).__name__}: {e}，回退到同步模式")
            return self._run_batch_sync_fallback_and_return(
                seed, num_keys, program, targets_buf, num_targets
            )
        except Exception as e:
            logger.warning(f"准备种子数据失败: {type(e).__name__}: {e}，回退到同步模式")
            return self._run_batch_sync_fallback_and_return(
                seed, num_keys, program, targets_buf, num_targets
            )

        if not self._is_buffer_valid():
            return self._run_batch_sync_fallback_and_return(
                seed, num_keys, program, targets_buf, num_targets
            )

        try:
            import pyopencl as cl

            return cl.enqueue_copy(
                self.device.transfer_queue,
                self.seed_buffer,
                seed_array,
                is_blocking=False,
            )
        except TypeError as e:
            if "host-to-host transfers" in str(e):
                logger.warning("主机到主机传输错误，回退到同步模式")
                return self._run_batch_sync_fallback_and_return(
                    seed, num_keys, program, targets_buf, num_targets
                )
            raise
        except (RuntimeError, MemoryError) as e:
            logger.warning(f"写入种子缓冲区OpenCL错误: {type(e).__name__}: {e}，回退到同步模式")
            return self._run_batch_sync_fallback_and_return(
                seed, num_keys, program, targets_buf, num_targets
            )
        except Exception as e:
            logger.warning(f"写入种子缓冲区失败: {type(e).__name__}: {e}，回退到同步模式")
            return self._run_batch_sync_fallback_and_return(
                seed, num_keys, program, targets_buf, num_targets
            )

    def _run_batch_sync_fallback_and_return(self, seed, num_keys, program, targets_buf, num_targets):
        """回退到同步执行并抛出结果异常（供 _transfer_seed / _clear_matches_buffer 使用）"""
        matches, exec_time = self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
        self.sync_fallbacks += 1
        self._track_sync_fallback()
        raise _SyncFallbackError(matches, exec_time)

    def _clear_matches_buffer(self, current_buf, num_keys, seed, program, targets_buf, num_targets):
        """步骤3: 清空匹配结果缓冲区"""
        try:
            buffer_size = current_buf["match_flags"].size
            if buffer_size < num_keys:
                logger.warning(f"缓冲区大小不足: 需要{num_keys}个元素, 实际{buffer_size}个元素")
                self._resize_buffer_and_clear(
                    current_buf, num_keys, seed, program, targets_buf, num_targets
                )

            import pyopencl as cl

            cl.enqueue_fill_buffer(
                self.device.compute_queue,
                current_buf["matches"],
                np.int32(0),
                0,
                num_keys * 4,
            )
            return True
        except (RuntimeError, MemoryError, Exception) as e:
            self._handle_sync_fallback(e, seed, num_keys, program, targets_buf, num_targets)

    def _resize_buffer_and_clear(self, current_buf, num_keys, seed, program, targets_buf, num_targets):
        """调整缓冲区大小并清空（提取公共逻辑，消除代码重复）"""
        import pyopencl as cl

        if current_buf["matches"] is not None:
            try:
                current_buf["matches"].release()
            except (RuntimeError, Exception) as e:
                logger.warning(f"释放旧缓冲区异常: {type(e).__name__}: {e}")

        try:
            current_buf["matches"] = cl.Buffer(
                self.device.context, cl.mem_flags.READ_WRITE, size=num_keys * 4
            )
            current_buf["match_flags"] = np.zeros(num_keys, dtype=np.int32)
            logger.info(f"已动态调整缓冲区大小为: {num_keys}个元素")
        except (RuntimeError, MemoryError, Exception) as e:
            logger.warning(f"创建新缓冲区失败: {type(e).__name__}: {e}，回退到同步模式")
            self._handle_sync_fallback(e, seed, num_keys, program, targets_buf, num_targets)

    def _handle_sync_fallback(self, error, seed, num_keys, program, targets_buf, num_targets):
        """统一处理同步回退逻辑（提取公共异常处理，消除代码重复）"""
        try:
            sync_matches, sync_time = self._run_batch_sync(
                seed, num_keys, program, targets_buf, num_targets
            )
        except Exception as sync_e:
            logger.debug(f"同步回退也失败: {type(sync_e).__name__}: {sync_e}")
            sync_matches, sync_time = [], 0.0
        self.sync_fallbacks += 1
        self._track_sync_fallback()
        raise _SyncFallbackError(sync_matches, sync_time) from error

    def _execute_and_register(
        self, current_buf, num_keys, seed, program, targets_buf, num_targets, transfer_event
    ):
        """步骤4-6: 执行内核、注册批次结果"""
        import pyopencl as cl

        batch_kernel = getattr(self, "_cached_kernel", None)
        if batch_kernel is None:
            try:
                batch_kernel = cl.Kernel(program, "batch_check")
                self._cached_kernel = batch_kernel
            except (RuntimeError, ValueError) as e:
                logger.warning(f"创建内核OpenCL错误: {type(e).__name__}: {e}，回退到同步模式")
                sync_matches, sync_time = self._run_batch_sync(
                    seed, num_keys, program, targets_buf, num_targets
                )
                self.sync_fallbacks += 1
                self._track_sync_fallback()
                raise _SyncFallbackError(sync_matches, sync_time) from e
            except Exception as e:
                logger.warning(f"创建内核失败: {type(e).__name__}: {e}，回退到同步模式")
                sync_matches, sync_time = self._run_batch_sync(
                    seed, num_keys, program, targets_buf, num_targets
                )
                self.sync_fallbacks += 1
                self._track_sync_fallback()
                raise _SyncFallbackError(sync_matches, sync_time) from e

        local_ws = getattr(self, "_work_group_size", 256)
        global_ws = ((num_keys + local_ws - 1) // local_ws) * local_ws

        kernel_event = self._execute_kernel(
            batch_kernel,
            local_ws,
            global_ws,
            current_buf,
            num_keys,
            targets_buf,
            num_targets,
            transfer_event,
        )
        if kernel_event is None:
            return None, None

        read_event = self._enqueue_result_read(
            current_buf, num_keys, seed, program, targets_buf, num_targets
        )
        if read_event is None:
            return None, None

        self._update_compat_fields(read_event, current_buf, num_keys)
        return kernel_event, read_event

    def _execute_kernel(
        self,
        batch_kernel,
        local_ws,
        global_ws,
        current_buf,
        num_keys,
        targets_buf,
        num_targets,
        transfer_event,
    ):
        """执行GPU内核"""
        try:
            return batch_kernel(
                self.device.compute_queue,
                (global_ws,),
                (local_ws,),
                self.seed_buffer,
                np.uint32(num_keys),
                targets_buf,
                np.uint32(num_targets),
                current_buf["matches"],
                np.uint32(getattr(self, "check_uncompressed", 0)),
                self.precomp_buffer,
                wait_for=[transfer_event],
            )
        except TypeError:
            try:
                transfer_event.wait()
                return batch_kernel(
                    self.device.compute_queue,
                    (global_ws,),
                    (local_ws,),
                    self.seed_buffer,
                    np.uint32(num_keys),
                    targets_buf,
                    np.uint32(num_targets),
                    current_buf["matches"],
                    np.uint32(getattr(self, "check_uncompressed", 0)),
                    self.precomp_buffer,
                )
            except (RuntimeError, MemoryError) as e:
                logger.warning(f"执行内核OpenCL错误: {type(e).__name__}: {e}，回退到同步模式")
                return None
            except Exception as e:
                logger.warning(f"执行内核失败: {type(e).__name__}: {e}，回退到同步模式")
                return None
        except (RuntimeError, MemoryError) as e:
            logger.warning(f"执行内核OpenCL错误: {type(e).__name__}: {e}，回退到同步模式")
            return None
        except Exception as e:
            logger.warning(f"执行内核失败: {type(e).__name__}: {e}，回退到同步模式")
            return None

    def _enqueue_result_read(self, current_buf, num_keys, seed, program, targets_buf, num_targets):
        """步骤5: 非阻塞回读结果"""
        import pyopencl as cl

        try:
            return cl.enqueue_copy(
                self.device.compute_queue,
                current_buf["match_flags"],
                current_buf["matches"],
                is_blocking=False,
            )
        except (RuntimeError, MemoryError) as e:
            logger.warning(f"设置回读操作OpenCL错误: {type(e).__name__}: {e}，回退到同步模式")
            sync_matches, sync_time = self._run_batch_sync(
                seed, num_keys, program, targets_buf, num_targets
            )
            self.sync_fallbacks += 1
            self._track_sync_fallback()
            raise _SyncFallbackError(sync_matches, sync_time) from e
        except Exception as e:
            logger.warning(f"设置回读操作失败: {type(e).__name__}: {e}，回退到同步模式")
            sync_matches, sync_time = self._run_batch_sync(
                seed, num_keys, program, targets_buf, num_targets
            )
            self.sync_fallbacks += 1
            self._track_sync_fallback()
            raise _SyncFallbackError(sync_matches, sync_time) from e

    def _update_compat_fields(self, read_event, current_buf, num_keys):
        """步骤7: 更新历史兼容字段"""
        try:
            self.pending_event = read_event
            self._pending_buffer = current_buf
            self._pending_num_keys = num_keys
        except (AttributeError, TypeError) as e:
            logger.debug(f"更新历史兼容字段属性异常: {type(e).__name__}: {e}")
        except Exception as e:
            logger.debug(f"更新历史兼容字段失败: {type(e).__name__}: {e}")

    def _run_batch_sync(
        self, seed: bytes, num_keys: int, program, targets_buf, num_targets
    ) -> tuple[list[dict], float]:
        """
        同步执行(回退模式，PRNG模式)

        当异步执行失败时使用。seed替代private_keys。
        """
        import numpy as np
        import pyopencl as cl

        start_time = time.time()

        # 写入种子到 seed_buffer
        seed_array = _seed_bytes_to_u32_be_array(seed[:32])
        cl.enqueue_copy(self.device.queue, self.seed_buffer, seed_array)  # type: ignore[arg-type]

        # 使用buffer_a作为临时缓冲（仅匹配结果）
        # S-3修复: 正确检查 matches 是否存在，字典布尔值始终为True
        temp_buf = self.buffer_a if self.buffer_a.get("matches") is not None else self.buffer_b

        try:
            cl.enqueue_fill_buffer(
                self.device.queue,
                temp_buf["matches"],
                np.int32(0),  # type: ignore[arg-type]
                0,
                num_keys * 4,  # type: ignore[arg-type]
            )
        except (RuntimeError, MemoryError) as e:
            logger.warning(f"同步模式下清空缓冲区OpenCL错误: {type(e).__name__}: {e}")
            if not self._try_create_fallback_buffer(temp_buf, num_keys, start_time):
                return [], (time.time() - start_time) * 1000
        except Exception as e:
            logger.warning(f"同步模式下清空缓冲区失败: {type(e).__name__}: {e}")
            if not self._try_create_fallback_buffer(temp_buf, num_keys, start_time):
                return [], (time.time() - start_time) * 1000

        batch_kernel = getattr(self, "_cached_sync_kernel", None)
        if batch_kernel is None:
            batch_kernel = cl.Kernel(program, "batch_check")
            self._cached_sync_kernel = batch_kernel
        # v4.2.1: 显式设置 local_work_size，对齐异步路径
        sync_local_ws = getattr(self, "_work_group_size", 256)
        sync_global_ws = ((num_keys + sync_local_ws - 1) // sync_local_ws) * sync_local_ws
        batch_kernel(
            self.device.queue,
            (sync_global_ws,),
            (sync_local_ws,),
            self.seed_buffer,
            np.uint32(num_keys),
            targets_buf,
            np.uint32(num_targets),
            temp_buf["matches"],
            np.uint32(getattr(self, "check_uncompressed", 0)),
            self.precomp_buffer,
        )

        match_flags = np.zeros(num_keys, dtype=np.int32)
        cl.enqueue_copy(self.device.queue, match_flags, temp_buf["matches"])
        self.device.queue.finish()

        matches = []
        for i in range(num_keys):
            if match_flags[i] > 0:
                matches.append({"key_index": i, "target_index": int(match_flags[i] - 1)})

        execution_time_ms = (time.time() - start_time) * 1000
        return matches, execution_time_ms

    def cleanup(self) -> None:
        """释放所有GPU缓冲区资源

        按安全依赖顺序执行清理，确保无资源泄漏:

        1. 完成所有命令队列中的命令 (compute_queue, transfer_queue)
        2. 清理所有待处理事件 (_prefetch_events, pending_event)
        3. 释放种子缓冲区 (seed_buffer，32字节PRNG)
        4. 释放预计算表常量缓冲区 (precomp_buffer)
        5. 释放缓冲区池中的所有匹配结果缓冲区
        6. 清空待处理状态字段

        v4.2.1 变化:
        - 不再引用 buffer_a['keys'] / buffer_b['keys']
        - PRNG 改造后已移除大型私钥缓冲区
        """
        self._finish_all_queues()
        with self._prefetch_lock:
            self._prefetch_events.clear()
        self._wait_pending_event()
        self._release_buffer_safe(
            "seed_buffer", lambda: self.seed_buffer, lambda v: setattr(self, "seed_buffer", v)
        )
        self._release_buffer_safe(
            "precomp_buffer",
            lambda: self.precomp_buffer,
            lambda v: setattr(self, "precomp_buffer", v),
        )
        self._release_buffer_pool()
        self._pending_buffer = None
        self._pending_num_keys = 0
        logger.info("异步GPU执行器资源已清理")

    def _finish_all_queues(self) -> None:
        """安全地完成所有命令队列"""
        queues = [
            ("计算", getattr(self.device, "compute_queue", None)),
            ("传输", getattr(self.device, "transfer_queue", None)),
        ]
        for name, queue in queues:
            if queue:
                try:
                    queue.finish()
                    logger.debug(f"{name}队列已完成所有命令")
                except RuntimeError as e:
                    logger.warning(f"完成{name}队列命令OpenCL错误: {e}")
                except Exception as e:
                    logger.warning(f"完成{name}队列命令失败: {type(e).__name__}: {e}")

    def _wait_pending_event(self) -> None:
        """安全地等待待处理事件完成"""
        if self.pending_event:
            try:
                self.pending_event.wait()
                logger.debug("已等待待处理事件完成")
            except RuntimeError as e:
                logger.warning(f"等待待处理事件OpenCL错误: {e}")
            except Exception as e:
                logger.warning(f"等待待处理事件完成失败: {type(e).__name__}: {e}")
            self.pending_event = None

    def _release_buffer_safe(self, name: str, getter: Callable, setter: Callable) -> None:
        """安全地释放缓冲区资源"""
        buf = getter()
        if buf is not None:
            try:
                buf.release()
                logger.debug(f"已释放 {name}")
            except RuntimeError as e:
                logger.warning(f"释放 {name} OpenCL错误: {e}")
            except Exception as e:
                logger.warning(f"释放 {name} 失败: {type(e).__name__}: {e}")
            setter(None)

    @staticmethod
    def _safe_release_buffer(buf_dict: dict, key: str) -> None:
        """安全释放缓冲区字典中的单个 OpenCL buffer（防止孤儿泄漏）"""
        buf = buf_dict.get(key)
        if buf is not None:
            with suppress(Exception):
                buf.release()

    def _try_create_fallback_buffer(self, buf_dict: dict, num_keys: int, start_time: float) -> bool:
        """尝试创建临时回退缓冲区并清空

        L-1: 从 _run_batch_sync 的重复错误处理中提取，消除代码重复。
        """
        import numpy as np
        import pyopencl as cl

        try:
            self._safe_release_buffer(buf_dict, "matches")
            buf_dict["matches"] = None  # 明确置空，避免悬空引用
            buf_dict["matches"] = cl.Buffer(
                self.device.context, cl.mem_flags.READ_WRITE, size=num_keys * 4
            )
            cl.enqueue_fill_buffer(
                self.device.queue,
                buf_dict["matches"],
                np.int32(0),  # type: ignore[arg-type]
                0,
                num_keys * 4,
            )
            return True
        except (RuntimeError, MemoryError) as create_err:
            logger.warning(f"创建临时缓冲区OpenCL错误: {create_err}")
            return False
        except Exception as create_err:
            logger.warning(f"创建临时缓冲区失败: {type(create_err).__name__}: {create_err}")
            return False

    def _release_buffer_pool(self) -> None:
        """释放缓冲区池中的所有缓冲区"""
        buf_pool = getattr(self, "_buffer_pool", None)
        if buf_pool is not None:
            for idx, buf_dict in enumerate(buf_pool):
                self._release_buffer_safe(
                    f"_buffer_pool[{idx}]['matches']",
                    lambda d=buf_dict: d.get("matches"),
                    lambda v, d=buf_dict: d.__setitem__("matches", v),
                )
                buf_dict["match_flags"] = None
            self._buffer_pool = []
        else:
            for buf_name, buf_dict in [("buffer_a", self.buffer_a), ("buffer_b", self.buffer_b)]:
                self._release_buffer_safe(
                    f"{buf_name}['matches']",
                    lambda d=buf_dict: d.get("matches"),
                    lambda v, d=buf_dict: d.__setitem__("matches", v),
                )
                buf_dict["match_flags"] = None

    def get_stats(self) -> dict:
        """获取执行统计"""
        total = self.async_executions + self.sync_fallbacks
        async_rate = (self.async_executions / total * 100) if total > 0 else 0
        prefetch_total = self.prefetch_hits + self.prefetch_misses
        prefetch_rate = (self.prefetch_hits / prefetch_total * 100) if prefetch_total > 0 else 0

        return {
            "async_executions": self.async_executions,
            "sync_fallbacks": self.sync_fallbacks,
            "total_executions": total,
            "async_rate_percent": async_rate,
            "prefetch_hits": self.prefetch_hits,
            "prefetch_misses": self.prefetch_misses,
            "prefetch_rate_percent": prefetch_rate,
            "queue_depth": self.queue_depth,
            "queue_depth_hits": self.queue_depth_hits,
            "current_queue_depth": len(self._prefetch_events),
        }
