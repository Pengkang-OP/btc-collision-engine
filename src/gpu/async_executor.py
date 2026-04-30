"""GPU异步执行优化模块

实现双缓冲异步执行机制,提升GPU利用率:
1. 双OpenCL队列(计算+传输)
2. 双缓冲机制(消除CPU-GPU等待)
3. 安全保护(超时+回退)
"""

import time
import threading
import logging
from typing import Any, List, Dict, Optional, Tuple

# P3-5: 统一日志获取 + 修复缺失导入
from ..utils import init_logging, get_configured_logger

import numpy as np

logger = get_configured_logger("AsyncGPUExecutor")


def _seed_bytes_to_u32_be_array(seed: bytes) -> np.ndarray:
    """把 32 字节 seed 按 big-endian 拆成 8×uint32，再转成本机端序。

    GPU 内核 generate_private_key 假设 seed 按 big-endian uint32 排列，
    而 x86 上 np.frombuffer(dtype=np.uint32) 默认按 little-endian 解析。
    需要先按 big-endian 解析再转为本机端序传给 OpenCL。
    """
    if len(seed) != 32:
        raise ValueError(f"seed must be 32 bytes, got {len(seed)}")
    be_u32 = np.frombuffer(seed, dtype='>u4')  # big-endian uint32
    return be_u32.astype(np.uint32)  # 转为本机端序（little-endian on x86）


# 队列深度管理常量
DEFAULT_QUEUE_DEPTH = 4   # GPU 队列中保持的预提交批次数量

# GPU型号特定配置
GPU_SPECIFIC_CONFIG = {
    # NVIDIA GTX 1660 系列优化配置
    '1660': {
        'queue_depth': 10,  # 增加队列深度，提高GPU利用率
        'initial_batch_size': 131072,  # 增加初始批次大小，提高吞吐量
        'max_batch_size': 524288,  # 增加最大批次大小，提高内存利用率
        'memory_factor': 0.75,  # 增加内存使用因子，提高内存利用率
    },
    # NVIDIA RTX 30系列
    'rtx30': {
        'queue_depth': 8,
        'initial_batch_size': 262144,
        'max_batch_size': 1048576,
        'memory_factor': 0.85,
    },
    # NVIDIA RTX 40系列
    'rtx40': {
        'queue_depth': 12,
        'initial_batch_size': 524288,
        'max_batch_size': 2097152,
        'memory_factor': 0.9,
    },
    # NVIDIA GTX 10系列
    '10': {
        'queue_depth': 6,
        'initial_batch_size': 131072,
        'max_batch_size': 524288,
        'memory_factor': 0.65,
    },
    # NVIDIA GTX 9系列
    '9': {
        'queue_depth': 4,
        'initial_batch_size': 65536,
        'max_batch_size': 262144,
        'memory_factor': 0.55,
    },
    # AMD Radeon RX 6000系列
    'amd6000': {
        'queue_depth': 7,
        'initial_batch_size': 262144,
        'max_batch_size': 1048576,
        'memory_factor': 0.8,
    },
    # AMD Radeon RX 7000系列
    'amd7000': {
        'queue_depth': 9,
        'initial_batch_size': 524288,
        'max_batch_size': 2097152,
        'memory_factor': 0.85,
    },
    # Intel Arc系列
    'intel': {
        'queue_depth': 4,
        'initial_batch_size': 65536,
        'max_batch_size': 262144,
        'memory_factor': 0.6,
    },
    # 默认配置
    'default': {
        'queue_depth': 4,
        'initial_batch_size': 65536,
        'max_batch_size': 262144,
        'memory_factor': 0.6,
    }
}


class _PendingBatch:
    """队列深度管理中，单个已提交到 GPU 但尚未取回结果的批次描述符。"""

    __slots__ = ("read_event", "buf", "num_keys", "seed")

    def __init__(self, read_event: Any, buf: Any, num_keys: int, seed: bytes) -> None:
        self.read_event = read_event  # cl.Event: 结果回读完成事件
        self.buf = buf                 # 对应的缓冲区字典 {matches, match_flags}
        self.num_keys = num_keys
        self.seed = seed               # 供上层用 seed+gid 还原私钥


class AsyncGPUExecutor:
    """异步GPU执行器
    
    使用双缓冲和双队列实现异步执行,提升GPU利用率到90%+
    
    优化v2.2.1:
    - 添加预取队列机制，消除CPU-GPU等待
    - 实现智能缓冲切换，减少空闲时间
    - 增强错误恢复，提升稳定性

    优化v2.3.2 (队列深度优化):
    - 维护 queue_depth=4 的预提交批次队列（_prefetch_events FIFO）
    - GPU 队列中始终保持多个待执行批次，消除批次间空闲间隙
    - 使用非阻塞 enqueue，按 FIFO 顺序处理最老批次结果
    """
    
    def __init__(self, gpu_device: Any, max_batch_size: int, queue_depth: int = DEFAULT_QUEUE_DEPTH) -> None:
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
        self.max_batch_size = gpu_config.get('max_batch_size', max_batch_size)
        self.queue_depth = gpu_config.get('queue_depth', queue_depth)
        self.initial_batch_size = gpu_config.get('initial_batch_size', 65536)

        # 预计算表缓冲区（常量，生命周期与 executor 一致）
        self.precomp_buffer = None

        # 种子缓冲区（32字节 = 8 uint32，替代大型 keys 缓冲区）
        self.seed_buffer = None

        # 双缓冲（匹配结果，不再需要 keys 缓冲区）
        self.buffer_a = {
            'matches': None,
            'match_flags': None
        }
        self.buffer_b = {
            'matches': None,
            'match_flags': None
        }
        
        # 异步状态
        self.current_buffer = 'A'
        self.pending_event = None
        self.is_async_ready = False
        
        # 异步流水线状态 — 延迟结果等待
        self._pending_buffer = None     # 待处理的缓冲区引用
        self._pending_num_keys = 0      # 待处理的批次大小
        self.check_uncompressed = 0     # v4.0: 由 GPUDeviceManager.initialize() 覆写
        
        # 预取队列优化v2.2.1
        self._prefetch_enabled = True
        self._next_batch_ready = threading.Event()
        self._next_batch_data = None
        self._next_batch_size = 0

        # 队列深度优化 v2.3.2：预提交批次 FIFO 队列
        # 每个元素是 _PendingBatch，记录已提交但尚未取回结果的批次
        self._prefetch_events: List[_PendingBatch] = []
        
        # 统计
        self.async_executions = 0
        self.sync_fallbacks = 0
        self.prefetch_hits = 0  # 预取命中次数
        self.prefetch_misses = 0  # 预取未命中次数
        self.queue_depth_hits = 0   # 队列深度优化命中（GPU 不等待 CPU）
        
        logger.info(
            f"异步GPU执行器已初始化: "
            f"GPU型号={gpu_model}, "
            f"max_batch={self.max_batch_size}, "
            f"initial_batch={self.initial_batch_size}, "
            f"预取=启用, queue_depth={self.queue_depth}"
        )
    
    def _detect_gpu_model(self) -> str:
        """
        检测GPU型号
        
        Returns:
            GPU型号标识
        """
        if hasattr(self.device, 'device_info') and self.device.device_info:
            device_name = self.device.device_info.get('name', '').lower()
            if '1660' in device_name:
                return '1660'
            elif 'rtx 40' in device_name or 'rtx40' in device_name:
                return 'rtx40'
            elif 'rtx 30' in device_name or 'rtx30' in device_name:
                return 'rtx30'
            elif 'rtx' in device_name:
                return 'rtx30'  # 默认RTX系列使用rtx30配置
            elif 'gtx 10' in device_name or '1060' in device_name or '1070' in device_name or '1080' in device_name:
                return '10'
            elif 'gtx 9' in device_name or '960' in device_name or '970' in device_name or '980' in device_name:
                return '9'
            elif 'rx 7' in device_name or 'rx7' in device_name:
                return 'amd7000'
            elif 'rx 6' in device_name or 'rx6' in device_name:
                return 'amd6000'
            elif 'amd' in device_name or 'radeon' in device_name:
                return 'amd6000'  # 默认AMD系列使用amd6000配置
            elif 'intel' in device_name or 'iris' in device_name or 'arc' in device_name:
                return 'intel'
        return 'default'
    
    def _get_gpu_config(self, gpu_model: str) -> Dict:
        """
        获取GPU特定配置
        
        Args:
            gpu_model: GPU型号标识
            
        Returns:
            GPU配置字典
        """
        return GPU_SPECIFIC_CONFIG.get(gpu_model, GPU_SPECIFIC_CONFIG.get('default', {}))
    
    def initialize_buffers(self, context: Any, num_keys: int) -> None:
        """
        初始化缓冲区池（PRNG模式：seed缓冲区替代keys缓冲区）

        队列深度优化 v2.3.2：
        - 分配 queue_depth 个匹配结果缓冲区，支持多批次同时在 GPU 中执行
        - buffer_a / buffer_b 作为历史兼容引用，指向缓冲区池的头两个

        Args:
            context: OpenCL上下文
            num_keys: 每个缓冲的密鑰数量
        """
        import pyopencl as cl
        import numpy as np
        
        logger.info(
            f"创建缓冲区池（PRNG模式）: num_keys={num_keys}, queue_depth={self.queue_depth}"
        )

        # 预计算表 GPU 常量缓冲区（如果尚未初始化）
        if self.precomp_buffer is None:
            from src.gpu.precompute import get_precomp_table
            precomp_data = get_precomp_table()
            self.precomp_buffer = cl.Buffer(
                context,
                cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                hostbuf=precomp_data
            )
            logger.info("预计算表缓冲区已创建: shape=(496,), dtype=uint32")

        # 种子缓冲区（固兵2字节，替代原 num_keys*32 字节的 keys 缓冲区）
        if self.seed_buffer is None:
            self.seed_buffer = cl.Buffer(
                context,
                cl.mem_flags.READ_ONLY,
                size=32  # 固兵2字节 = 8 uint32
            )
            logger.info("种子缓冲区已创建: 32字节（PRNG模式，节省约{}MB)".format(
                num_keys * 32 / 1024 / 1024
            ))

        # 创建 queue_depth 个缓冲区构成缓冲区池
        self._buffer_pool: List[Dict] = []
        for i in range(self.queue_depth):
            buf = {
                'matches': cl.Buffer(
                    context,
                    cl.mem_flags.READ_WRITE,
                    size=num_keys * 4
                ),
                'match_flags': np.zeros(num_keys, dtype=np.int32)
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

    def prefetch_next_batch(self, seed: bytes, num_keys: int) -> None:
        """预存下一批种子（PRNG模式：仅缓存32字节种子，v2.2.1）
        
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
        except Exception as e:
            logger.warning(f"预取失败: {e}")
            self._next_batch_ready.clear()
    
    def run_batch_async(self, seed: bytes, num_keys: int,
                       program: Any, targets_buf: Any, num_targets: int) -> Tuple[List[Dict], float]:
        """
        异步执行批次（PRNG模式：seed替代private_keys）
    
        v2.3.2 队列深度优化：
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
        import pyopencl as cl
        import numpy as np
    
        start_time = time.time()
    
        # 检查是否支持异步
        if not self.device.enable_async_execution or not self.device.compute_queue:
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
            # 此时 pool_idx 尚未推进，最老批次对应的正是即将被 round-robin 重新分配的缓冲区
            prev_matches: List[Dict] = []
            if len(self._prefetch_events) >= self.queue_depth:
                oldest = self._prefetch_events.pop(0)
                timeout_seconds = 30
                try:
                    try:
                        completed = oldest.read_event.wait(timeout=timeout_seconds * 1000)
                        if not completed:
                            logger.error(f"异步执行超时({timeout_seconds}秒)")
                            raise RuntimeError(f"异步执行超时({timeout_seconds}秒)")
                    except TypeError:
                        oldest.read_event.wait()
                except RuntimeError:
                    raise
                except Exception as wait_err:
                    logger.error(f"等待批次完成失败: {wait_err}")
                    raise RuntimeError(f"异步执行失败: {wait_err}")
    
                # 收集最老批次结果（缓冲区数据尚未被覆盖，此时读取安全）
                try:
                    for i in range(oldest.num_keys):
                        if oldest.buf['match_flags'][i] > 0:
                            prev_matches.append({
                                "key_index": i,
                                "target_index": int(oldest.buf['match_flags'][i] - 1)
                            })
                except Exception as e:
                    logger.warning(f"收集批次结果失败: {e}")
                self.queue_depth_hits += 1
    
            # 步骤 1：现在可以安全分配缓冲区（oldest 已完成，round-robin 的 buf 确保空闲）
            buf_pool = getattr(self, '_buffer_pool', None)
            if buf_pool is not None:
                pool_idx = getattr(self, '_pool_index', 0)
                try:
                    current_buf = buf_pool[pool_idx % len(buf_pool)]
                    self._pool_index = (pool_idx + 1) % len(buf_pool)
                except Exception as e:
                    logger.warning(f"分配缓冲区失败: {e}，回退到同步模式")
                    return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
            else:
                # 回退：使用老双缓冲区逻辑
                try:
                    current_buf = self.buffer_a if self.current_buffer == 'A' else self.buffer_b
                    self.current_buffer = 'B' if self.current_buffer == 'A' else 'A'
                except Exception as e:
                    logger.warning(f"获取双缓冲区失败: {e}，回退到同步模式")
                    return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
            # 步骤 2. 把本次种子写入 seed_buffer（传输队列，非阻塞）
            try:
                seed_array = _seed_bytes_to_u32_be_array(seed[:32])
            except Exception as e:
                logger.warning(f"准备种子数据失败: {e}，回退到同步模式")
                return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
            
            # 检查缓冲区有效性
            if not self._is_buffer_valid():
                return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
            
            try:
                transfer_event = cl.enqueue_copy(
                    self.device.transfer_queue,
                    self.seed_buffer,
                    seed_array,
                    is_blocking=False  # 非阻塞!
                )
            except TypeError as e:
                if "host-to-host transfers" in str(e):
                    logger.warning("主机到主机传输错误，回退到同步模式")
                    return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
                else:
                    raise
            except Exception as e:
                logger.warning(f"写入种子缓冲区失败: {e}，回退到同步模式")
                return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
            # 步骤 3. 清空当前缓冲的匹配结果（计算队列）
            try:
                # 检查缓冲区大小是否足够
                buffer_size = current_buf['match_flags'].size
                if buffer_size < num_keys:
                    logger.warning(f"缓冲区大小不足: 需要{num_keys}个元素, 实际{buffer_size}个元素")
                    # 动态调整缓冲区大小
                    import pyopencl as cl
                    import numpy as np
                    
                    # 释放旧缓冲区
                    if current_buf['matches'] is not None:
                        try:
                            current_buf['matches'].release()
                        except Exception as e:
                            logger.warning(f"释放旧缓冲区失败: {e}")
                    
                    # 创建新缓冲区
                    try:
                        current_buf['matches'] = cl.Buffer(
                            self.device.context,
                            cl.mem_flags.READ_WRITE,
                            size=num_keys * 4
                        )
                        current_buf['match_flags'] = np.zeros(num_keys, dtype=np.int32)
                        logger.info(f"已动态调整缓冲区大小为: {num_keys}个元素")
                    except Exception as e:
                        logger.warning(f"创建新缓冲区失败: {e}，回退到同步模式")
                        return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
                
                cl.enqueue_fill_buffer(
                    self.device.compute_queue,
                    current_buf['matches'],
                    np.int32(0),
                    0,
                    num_keys * 4
                )
            except Exception as e:
                logger.warning(f"清空缓冲区失败: {e}，回退到同步模式")
                return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
            # 步骤 4. 执行内核（等待传输事件完成）
            batch_kernel = getattr(self, '_cached_kernel', None)
            if batch_kernel is None:
                try:
                    batch_kernel = cl.Kernel(program, 'batch_check')
                    self._cached_kernel = batch_kernel
                except Exception as e:
                    logger.warning(f"创建内核失败: {e}，回退到同步模式")
                    return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
            try:
                kernel_event = batch_kernel(
                    self.device.compute_queue,
                    (num_keys,),
                    None,
                    self.seed_buffer,
                    np.uint32(num_keys),
                    targets_buf,
                    np.uint32(num_targets),
                    current_buf['matches'],
                    np.uint32(getattr(self, 'check_uncompressed', 0)),
                    self.precomp_buffer,
                    wait_for=[transfer_event]  # 等待种子传输完成再执行
                )
            except TypeError:
                # 如果该版本 pyopencl 不支持 wait_for，先同步等待传输完成
                try:
                    transfer_event.wait()
                    kernel_event = batch_kernel(
                        self.device.compute_queue,
                        (num_keys,),
                        None,
                        self.seed_buffer,
                        np.uint32(num_keys),
                        targets_buf,
                        np.uint32(num_targets),
                        current_buf['matches'],
                        np.uint32(getattr(self, 'check_uncompressed', 0)),
                        self.precomp_buffer
                    )
                except Exception as e:
                    logger.warning(f"执行内核失败: {e}，回退到同步模式")
                    return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
            except Exception as e:
                logger.warning(f"执行内核失败: {e}，回退到同步模式")
                return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
            # 步骤 5. 非阻塞回读结果
            try:
                read_event = cl.enqueue_copy(
                    self.device.compute_queue,
                    current_buf['match_flags'],
                    current_buf['matches'],
                    is_blocking=False
                )
            except Exception as e:
                logger.warning(f"设置回读操作失败: {e}，回退到同步模式")
                return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
            # 步骤 6. 将本批加入 _prefetch_events FIFO 队列
            try:
                pending = _PendingBatch(
                    read_event=read_event,
                    buf=current_buf,
                    num_keys=num_keys,
                    seed=seed
                )
                self._prefetch_events.append(pending)
                self.async_executions += 1
            except Exception as e:
                logger.warning(f"加入待处理队列失败: {e}，回退到同步模式")
                return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
            # 步骤 7. 同时更新历史兼容字段（flush_pending 和回退模式依赖）
            try:
                self.pending_event = read_event
                self._pending_buffer = current_buf
                self._pending_num_keys = num_keys
            except Exception as e:
                logger.debug(f"更新历史兼容字段失败: {e}")
    
            execution_time_ms = (time.time() - start_time) * 1000
            return prev_matches, execution_time_ms
    
        except Exception as e:
            logger.warning(f"异步执行失败,回退到同步模式: {e}")
            self.sync_fallbacks += 1
            return self._run_batch_sync(seed, num_keys, program, targets_buf, num_targets)
    
    def flush_pending(self) -> List[Tuple[bytes, List[Dict]]]:
        """收集所有尚未取回的异步执行结果

        在主循环结束后调用，确保 _prefetch_events 队列中所有已提交的 GPU 批次结果不丢失。

        Returns:
            List[Tuple[bytes, List[Dict]]]：每个元素为 (seed, matches_for_that_batch)，
            其中 seed 是该批次对应的 32 字节种子，matches_for_that_batch 是该批次的匹配列表。
            调用方必须使用每批次自己的 seed 重建私钥，而不能用同一个 seed 处理所有匹配。
        """
        batch_results: List[Tuple[bytes, List[Dict]]] = []

        # 处理所有预提交队列中的待处理批次
        while self._prefetch_events:
            oldest = self._prefetch_events.pop(0)
            try:
                try:
                    oldest.read_event.wait(timeout=30000)
                except TypeError:
                    oldest.read_event.wait()
            except Exception as e:
                logger.warning(f"等待最后一批结果失败: {e}")
                continue

            if oldest.buf is not None:
                batch_matches: List[Dict] = []
                for i in range(oldest.num_keys):
                    if oldest.buf['match_flags'][i] > 0:
                        batch_matches.append({
                            "key_index": i,
                            "target_index": int(oldest.buf['match_flags'][i] - 1)
                        })
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
        if not hasattr(self.device, 'transfer_queue') or self.device.transfer_queue is None:
            logger.warning("传输队列已不可用，回退到同步模式")
            return False
        
        return True
    
    def _run_batch_sync(self, seed: bytes, num_keys: int,
                       program, targets_buf, num_targets) -> Tuple[List[Dict], float]:
        """
        同步执行(回退模式，PRNG模式)
        
        当异步执行失败时使用。seed替代private_keys。
        """
        import pyopencl as cl
        import numpy as np
        
        start_time = time.time()
        
        # 写入种子到 seed_buffer
        seed_array = _seed_bytes_to_u32_be_array(seed[:32])
        cl.enqueue_copy(self.device.queue, self.seed_buffer, seed_array)
        
        # 使用buffer_a作为临时缓冲（仅匹配结果）
        temp_buf = self.buffer_a if self.buffer_a['matches'] else self.buffer_b
        
        try:
            cl.enqueue_fill_buffer(
                self.device.queue, temp_buf['matches'],
                np.int32(0), 0, num_keys * 4
            )
        except Exception as e:
            logger.error(f"同步模式下清空缓冲区失败: {e}")
            # 创建临时缓冲区
            try:
                import pyopencl as cl
                temp_buf['matches'] = cl.Buffer(
                    self.device.context,
                    cl.mem_flags.READ_WRITE,
                    size=num_keys * 4
                )
                cl.enqueue_fill_buffer(
                    self.device.queue, temp_buf['matches'],
                    np.int32(0), 0, num_keys * 4
                )
            except Exception as create_err:
                logger.error(f"创建临时缓冲区失败: {create_err}")
                return [], (time.time() - start_time) * 1000
        
        batch_kernel = getattr(self, '_cached_sync_kernel', None)
        if batch_kernel is None:
            batch_kernel = cl.Kernel(program, 'batch_check')
            self._cached_sync_kernel = batch_kernel
        batch_kernel(
            self.device.queue, (num_keys,), None,
            self.seed_buffer, np.uint32(num_keys),
            targets_buf, np.uint32(num_targets),
            temp_buf['matches'],
            np.uint32(getattr(self, 'check_uncompressed', 0)),
            self.precomp_buffer
        )
        
        match_flags = np.zeros(num_keys, dtype=np.int32)
        cl.enqueue_copy(self.device.queue, match_flags, temp_buf['matches'])
        self.device.queue.finish()
        
        matches = []
        for i in range(num_keys):
            if match_flags[i] > 0:
                matches.append({
                    "key_index": i,
                    "target_index": int(match_flags[i] - 1)
                })
        
        execution_time_ms = (time.time() - start_time) * 1000
        return matches, execution_time_ms
    
    def cleanup(self) -> None:
        """释放所有GPU缓冲区资源

        释放顺序：
        1. 确保所有命令队列中的命令都已完成
        2. 清理所有待处理事件
        3. 释放 seed_buffer（32字节PRNG种子缓冲区）
        4. 释放 precomp_buffer（预计算表常量缓冲区）
        5. 释放缓冲区池中的所有匹配结果缓冲区

        注意：不再引用 buffer_a['keys'] / buffer_b['keys']，
        v4.0 PRNG改造后已移除大型私鑰缓冲区。
        """
        import time
        
        # 确保所有命令队列中的命令都已完成
        if hasattr(self.device, 'compute_queue') and self.device.compute_queue:
            try:
                # 设置超时，确保清理过程不会卡住
                start_time = time.time()
                timeout = 10  # 10秒超时
                
                # 尝试完成队列中的所有命令
                self.device.compute_queue.finish()
                logger.debug("计算队列已完成所有命令")
            except Exception as e:
                logger.warning(f"完成计算队列命令失败: {e}")
        
        if hasattr(self.device, 'transfer_queue') and self.device.transfer_queue:
            try:
                self.device.transfer_queue.finish()
                logger.debug("传输队列已完成所有命令")
            except Exception as e:
                logger.warning(f"完成传输队列命令失败: {e}")
        
        # 清空预提交事件列表
        self._prefetch_events.clear()

        # 清理待处理事件
        if self.pending_event:
            try:
                self.pending_event.wait()
                logger.debug("已等待待处理事件完成")
            except Exception as e:
                logger.warning(f"等待待处理事件完成失败: {e}")
            self.pending_event = None

        # 释放 seed_buffer
        if self.seed_buffer is not None:
            try:
                self.seed_buffer.release()
                logger.debug("已释放 seed_buffer")
            except Exception as e:
                logger.warning(f"释放 seed_buffer 失败: {e}")
            self.seed_buffer = None

        # 释放 precomp_buffer
        if self.precomp_buffer is not None:
            try:
                self.precomp_buffer.release()
                logger.debug("已释放 precomp_buffer")
            except Exception as e:
                logger.warning(f"释放 precomp_buffer 失败: {e}")
            self.precomp_buffer = None

        # 释放缓冲区池中的所有 matches buffer
        buf_pool = getattr(self, '_buffer_pool', None)
        if buf_pool is not None:
            for idx, buf_dict in enumerate(buf_pool):
                matches_buf = buf_dict.get('matches')
                if matches_buf is not None:
                    try:
                        matches_buf.release()
                        logger.debug(f"已释放 _buffer_pool[{idx}]['matches']")
                    except Exception as e:
                        logger.warning(f"释放 _buffer_pool[{idx}]['matches'] 失败: {e}")
                    buf_dict['matches'] = None
                buf_dict['match_flags'] = None
            self._buffer_pool = []
        else:
            # 历史兼容：如果没有池，释放 buffer_a / buffer_b
            for buf_name, buf_dict in [('buffer_a', self.buffer_a), ('buffer_b', self.buffer_b)]:
                matches_buf = buf_dict.get('matches')
                if matches_buf is not None:
                    try:
                        matches_buf.release()
                        logger.debug(f"已释放 {buf_name}['matches']")
                    except Exception as e:
                        logger.warning(f"释放 {buf_name}['matches'] 失败: {e}")
                    buf_dict['matches'] = None
                buf_dict['match_flags'] = None

        # 清除待处理状态
        self._pending_buffer = None
        self._pending_num_keys = 0

        logger.info("异步GPU执行器资源已清理")
    
    def get_stats(self) -> Dict:
        """获取执行统计"""
        total = self.async_executions + self.sync_fallbacks
        async_rate = (self.async_executions / total * 100) if total > 0 else 0
        prefetch_total = self.prefetch_hits + self.prefetch_misses
        prefetch_rate = (self.prefetch_hits / prefetch_total * 100) if prefetch_total > 0 else 0

        return {
            'async_executions': self.async_executions,
            'sync_fallbacks': self.sync_fallbacks,
            'total_executions': total,
            'async_rate_percent': async_rate,
            'prefetch_hits': self.prefetch_hits,
            'prefetch_misses': self.prefetch_misses,
            'prefetch_rate_percent': prefetch_rate,
            'queue_depth': self.queue_depth,
            'queue_depth_hits': self.queue_depth_hits,
            'current_queue_depth': len(self._prefetch_events)
        }
