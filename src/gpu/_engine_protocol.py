"""GPU碰撞引擎协议接口.

消除 src/gpu/ → src/collision/gpu/engine 的反向依赖（ROADMAP #13）.
所有需要 GPUCollisionEngine 类型引用的 src/gpu/ 模块改为引用此协议。

用法:
    from src.gpu._engine_protocol import GPUEngineProtocol

协议中的每个成员都是在 src/gpu/ 各模块中被实际访问的属性或方法。
运行时由 src.collision.gpu.engine.GPUCollisionEngine 通过 duck typing 实现。
"""

from __future__ import annotations

from typing import Any, Protocol


class GPUEngineProtocol(Protocol):
    """GPU碰撞引擎协议接口.

    ROADMAP #13: 替代 TYPE_CHECKING 导入 ``from ..collision.gpu.engine import
    GPUCollisionEngine``，消除 src/gpu/ → src/collision/gpu/ 的反向依赖.

    此协议覆盖 src/gpu/ 各模块（worker、monitor、coordinator、search_modes）
    在类型检查时实际访问的所有属性和方法。运行时由 GPUCollisionEngine 的
    duck typing 自动满足。
    """

    # ── 公共属性 ──
    targets: set[Any]
    batch_size: int
    stats: Any
    config: dict[str, Any]
    event_bus: Any
    checkpoint_mgr: Any
    device_index: int

    # ── 回调 ──
    on_match: Any | None
    on_progress: Any | None
    on_complete: Any | None

    # ── 私有属性（被各搜索模式模块大量访问） ──
    _running: bool
    _stop_event: Any
    _gpu_kernel: Any
    _device_manager: Any
    _async_executor: Any
    _batch_size_lock: Any
    _recovery_manager: Any
    _gpu_device: Any
    _consecutive_gpu_errors: int
    _max_gpu_error_retries: int
    _last_progress_time: float
    _progress_interval_sec: float
    _current_position: int

    # ── 公共方法 ──
    def start(self, mode: str = "random", **kwargs: Any) -> None: ...

    def stop(self) -> None: ...

    def is_running(self) -> bool: ...

    def get_stats(self) -> Any: ...

    def get_device_info(self) -> dict[str, Any]: ...

    # ── 内部方法（被搜索模式模块调用） ──
    def _save_checkpoint(self, count: int) -> None: ...

    def _execute_gpu_batch(self, batch_start: int, batch_size: int, batch_seed: bytes) -> Any: ...

    def _process_gpu_matches_prng(self, batch_seed: bytes, batch_matches: int) -> None: ...

    def _update_performance_metrics(self, batch_time: float, num_keys: int) -> None: ...

    def _check_and_report_progress(self) -> None: ...
