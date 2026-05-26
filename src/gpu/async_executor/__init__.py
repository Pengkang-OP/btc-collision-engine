"""GPU 异步执行器包

从 src/gpu/async_executor.py（1707行）拆分为 6 个模块：

  _executor.py    — AsyncGPUExecutor 核心类（继承三个 Mixin）
  _gpu_info.py     — _GPUInfoMixin（型号检测、配置适配）
  _collector.py    — _ResultCollectorMixin（后台结果收集器）
  _sync.py         — _SyncFallbackMixin（同步回退、资源清理）
  _error_utils.py  — with_sync_fallback 装饰器 + 工具函数
  __init__.py      — 公共 API 导出 + 向后兼容别名

v5.2.3: 代码质量优化。外部代码无感知。
"""

from ._executor import AsyncGPUExecutor

# ============================================================
# 向后兼容：保留旧模块级导出，原 `from async_executor import X` 继续可用
# ============================================================
from ..executor_types import (
    DEFAULT_QUEUE_DEPTH,
    GPU_SPECIFIC_CONFIG,
    _PendingBatch,
    _SyncFallbackError,
)
from ..seed_utils import _seed_bytes_to_u32_be_array

__all__ = [
    "AsyncGPUExecutor",
    "GPU_SPECIFIC_CONFIG",
    "DEFAULT_QUEUE_DEPTH",
    "_PendingBatch",
    "_SyncFallbackError",
    "_seed_bytes_to_u32_be_array",
]
