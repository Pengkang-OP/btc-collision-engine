"""异步GPU执行器的类型、常量和配置定义.

从 async_executor.py 拆分，提高模块可维护性.

v5.2.4: _PendingBatch.__init__ 初始化 batch_num 属性，消除外部赋值的 type: ignore[attr-defined]。
"""

import types
from typing import Any

__all__ = [
    "ASYNC_RECOVER_AFTER_SYNC_COUNT",
    "DEFAULT_QUEUE_DEPTH",
    "GPU_SPECIFIC_CONFIG",
    "MAX_CONSECUTIVE_SYNC_FALLBACKS",
]


# 队列深度管理常量
DEFAULT_QUEUE_DEPTH = 4  # GPU 队列中保持的预提交批次数量

# GPU型号特定配置（不可变）
GPU_SPECIFIC_CONFIG = types.MappingProxyType(
    {
        # NVIDIA GTX 1660 系列优化配置 — v5.1.1: 大幅提升消除锯齿波
        "1660": {
            "queue_depth": 20,
            "initial_batch_size": 1048576,
            "max_batch_size": 2097152,
            "memory_factor": 0.80,
        },
        # NVIDIA RTX 30系列
        "rtx30": {
            "queue_depth": 20,
            "initial_batch_size": 1048576,
            "max_batch_size": 4194304,
            "memory_factor": 0.88,
        },
        # NVIDIA RTX 40系列
        "rtx40": {
            "queue_depth": 24,
            "initial_batch_size": 2097152,
            "max_batch_size": 8388608,
            "memory_factor": 0.92,
        },
        # NVIDIA GTX 10系列
        "10": {
            "queue_depth": 16,
            "initial_batch_size": 1048576,
            "max_batch_size": 2097152,
            "memory_factor": 0.72,
        },
        # NVIDIA GTX 9系列
        "9": {
            "queue_depth": 12,
            "initial_batch_size": 524288,
            "max_batch_size": 1048576,
            "memory_factor": 0.62,
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
            "queue_depth": 32,
            "initial_batch_size": 4194304,
            "max_batch_size": 16777216,
            "memory_factor": 0.90,
        },
        # 默认配置
        "default": {
            "queue_depth": 4,
            "initial_batch_size": 65536,
            "max_batch_size": 262144,
            "memory_factor": 0.6,
        },
    },
)  # MappingProxyType


class _PendingBatch:
    """队列深度管理中，单个已提交到 GPU 但尚未取回结果的批次描述符.

    Attributes:
        read_event: OpenCL 事件，结果回读完成后触发
        buf: 对应的缓冲区字典，包含 'matches' 和 'match_flags'
        num_keys: 当前批次的密钥数量
        seed: 当前批次对应的 32 字节种子，用于 seed+gid 还原私钥

    """

    __slots__ = ("batch_num", "buf", "num_keys", "read_event", "seed")

    def __init__(self, read_event: Any, buf: Any, num_keys: int, seed: bytes) -> None:
        self.read_event = read_event
        self.buf = buf
        self.num_keys = num_keys
        self.seed = seed
        self.batch_num = 0  # 在 __slots__ 中声明，后续由调用方赋值


class _SyncFallbackError(Exception):
    """异步执行回退信号：已通过同步路径完成执行，携带结果.

    用于在 _allocate_buffer / _transfer_seed / _clear_matches_buffer 中
    当异步预处理失败时，已完成同步执行并把结果带回外层，避免二次执行和结果丢失。
    """

    __slots__ = ("execution_time_ms", "matches")

    def __init__(
        self, matches: "list[tuple[bytes, list[dict[str, Any]]]]", execution_time_ms: float
    ) -> None:
        super().__init__(
            f"Async fallback complete: {len(matches)} matches, {execution_time_ms:.1f}ms",
        )
        self.matches = [dict(m) for m in matches]  # type: ignore[var-annotated, arg-type]
        self.execution_time_ms = execution_time_ms


# 异步模式恢复常量
ASYNC_RECOVER_AFTER_SYNC_COUNT = 10
MAX_CONSECUTIVE_SYNC_FALLBACKS = 50
