"""碰撞引擎模块包"""
from typing import Set, Optional, Dict, Any
from .targets.resolver import TargetResolver
from .collision_stats import CollisionStats
from .checkpoint_manager import CheckpointManager
from .deduplication_filter import DeduplicationFilter
from .bloom_deduplication_filter import BloomDeduplicationFilter
from .base_engine import BaseCollisionEngine
from .key_collision_engine import KeyCollisionEngine
from .observers import CollisionObserver, BaseCollisionObserver, ObserverManager
from .multiprocess_engine import MultiprocessCollisionEngine, HybridCollisionEngine
from .continuous_matcher import ContinuousMatcher
from .match_storage import MatchDataStorage
from .collision_helpers import (
    encode_private_key_to_wif,
    format_match_result,
    safe_wif_encode
)
from . import constants

# 事件系统 (v3.2.0新增)
from .events import (
    EventType,
    CollisionEvent,
    EngineProgressEvent,
    EngineMatchEvent,
    EngineErrorEvent,
    EngineCompleteEvent,
    EngineStartEvent,
    EngineStopEvent,
    GPUKernelExecEvent,
    GPUErrorEvent,
    MonitoringAlertEvent,
    MonitoringAnomalyEvent
)
from .event_bus import EventBus, get_event_bus, reset_event_bus
from .types import (
    ProgressCallback,
    MatchCallback,
    CompleteCallback,
    ErrorCallback,
    EventHandler,
    ErrorHandler
)

# 条件导出 GPUCollisionEngine（pyopencl 可能不可用）
try:
    from .gpu_collision_engine import GPUCollisionEngine
    _GPU_AVAILABLE = True
except ImportError as _gpu_import_err:
    GPUCollisionEngine = None  # type: ignore[misc,assignment]
    _GPU_AVAILABLE = False
    import logging as _logging
    _logging.getLogger(__name__).info(
        "[GPU提示] pyopencl 未安装，GPU加速功能不可用，将使用 CPU 模式运行。\n"
        "  如需启用 GPU 加速，请安装 OpenCL 运行时，然后：\n"
        "    pip install pyopencl"
    )

__all__ = [
    'BaseCollisionEngine',
    'TargetResolver',
    'CollisionStats',
    'CheckpointManager',
    'DeduplicationFilter',
    'BloomDeduplicationFilter',
    'KeyCollisionEngine',
    'GPUCollisionEngine',
    'CollisionObserver',
    'BaseCollisionObserver',
    'ObserverManager',
    'MultiprocessCollisionEngine',
    'HybridCollisionEngine',
    'create_collision_engine',
    # 业务逻辑模块
    'ContinuousMatcher',
    'MatchDataStorage',
    # 辅助工具函数
    'encode_private_key_to_wif',
    'format_match_result',
    'safe_wif_encode',
    # 事件系统 (v3.2.0新增)
    'EventType',
    'CollisionEvent',
    'EngineProgressEvent',
    'EngineMatchEvent',
    'EngineErrorEvent',
    'EngineCompleteEvent',
    'EngineStartEvent',
    'EngineStopEvent',
    'GPUKernelExecEvent',
    'GPUErrorEvent',
    'MonitoringAlertEvent',
    'MonitoringAnomalyEvent',
    'EventBus',
    'get_event_bus',
    'reset_event_bus',
    # 类型定义 (v3.2.0新增)
    'ProgressCallback',
    'MatchCallback',
    'CompleteCallback',
    'ErrorCallback',
    'EventHandler',
    'ErrorHandler'
]


def create_collision_engine(targets: Set[str], mode: str = 'auto', 
                           config: Optional[Dict[str, Any]] = None,
                           **kwargs) -> BaseCollisionEngine:
    """
    创建碰撞引擎实例

    参数:
        targets: 目标地址集合
        mode: 'auto'|'gpu'|'cpu'
            auto: 检测GPU可用性自动选择
            gpu: 强制使用GPU（不可用时抛异常）
            cpu: 强制使用CPU
        config: 配置字典（可选）
            如果提供，将从中读取引擎配置
            优先级: kwargs > config > 默认值
        **kwargs: 传递给引擎构造函数的参数
            - 对于GPU引擎: batch_size, device_index, dedup_filter, checkpoint_mgr
            - 对于CPU引擎: on_progress, on_match, on_complete, checkpoint_enabled,
                         dedup_enabled, dedup_max_size, checkpoint_interval, max_workers

    返回:
        碰撞引擎实例 (GPUCollisionEngine 或 KeyCollisionEngine)

    异常:
        RuntimeError: 当mode='gpu'但GPU不可用时
        ValueError: 当mode参数无效时

    示例:
        >>> # 基本用法
        >>> engine = create_collision_engine(targets={'1A...'}, mode='auto')
        
        >>> # 使用配置字典
        >>> config = {
        ...     'gpu': {'batch_size': 131072, 'device_index': 0},
        ...     'collision': {'max_workers': 4}
        ... }
        >>> engine = create_collision_engine(targets, mode='auto', config=config)
        
        >>> # 强制GPU
        >>> engine = create_collision_engine(targets, mode='gpu', batch_size=65536)
        
        >>> # 强制CPU
        >>> engine = create_collision_engine(targets, mode='cpu', max_workers=4)
    """
    # 参数验证
    if mode not in ('auto', 'gpu', 'cpu'):
        raise ValueError(f"无效的mode参数: {mode}，必须是 'auto', 'gpu' 或 'cpu'")
    
    # 如果没有targets，发出警告
    if not targets:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("目标地址集合为空，碰撞将无意义")

    # 合并配置: kwargs优先级最高，config次之
    if config:
        merged_kwargs = _merge_config_with_kwargs(config, kwargs)
    else:
        merged_kwargs = kwargs.copy()

    # auto模式: 检查GPU可用性自动选择
    if mode == 'auto':
        if _GPU_AVAILABLE and GPUCollisionEngine.is_gpu_available():
            return GPUCollisionEngine(targets=targets, **merged_kwargs)
        else:
            if not _GPU_AVAILABLE:
                import logging as _log
                _log.getLogger(__name__).info(
                    "[GPU提示] pyopencl 未安装，已自动切换到 CPU 模式。\n"
                    "  如需 GPU 加速： pip install pyopencl"
                )
            elif not GPUCollisionEngine.is_gpu_available():
                import logging as _log
                _log.getLogger(__name__).info(
                    "[GPU提示] 未检测到可用的 OpenCL 设备，已自动切换到 CPU 模式。\n"
                    "  请确认已安装对应厂商的 GPU 驱动及 OpenCL 运行时。"
                )
            return KeyCollisionEngine(targets=targets, **merged_kwargs)

    # gpu模式: 强制使用GPU
    if mode == 'gpu':
        if not _GPU_AVAILABLE:
            raise RuntimeError(
                "GPU不可用: pyopencl 未安装。\n"
                "  请安装 OpenCL 运行时并执行: pip install pyopencl\n"
                "  安装指南请参阅 docs/FAQ.md#GPU"
            )
        if not GPUCollisionEngine.is_gpu_available():
            raise RuntimeError(
                "GPU不可用: 未检测到可用的 OpenCL 设备。\n"
                "  请确认：\n"
                "    1. GPU 驱动已正确安装（Intel: https://www.intel.com/opencl, NVIDIA: CUDA驱动包）\n"
                "    2. OpenCL 运行时已安装\n"
                "    3. 运行 `python scripts/diagnose.py` 获取详细说明"
            )
        return GPUCollisionEngine(targets=targets, **merged_kwargs)

    # cpu模式: 强制使用CPU
    return KeyCollisionEngine(targets=targets, **merged_kwargs)


def _merge_config_with_kwargs(config: Dict[str, Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并配置字典和kwargs
    
    参数:
        config: 配置字典（包含gpu, collision等配置段）
        kwargs: 直接传递的参数
    
    返回:
        合并后的参数字典
    
    优先级: kwargs > config > 默认值
    """
    merged = {}
    
    # 从config中提取GPU配置
    if 'gpu' in config:
        gpu_config = config['gpu']
        if 'batch_size' in gpu_config:
            merged['batch_size'] = gpu_config['batch_size']
        if 'device_index' in gpu_config:
            merged['device_index'] = gpu_config['device_index']
    
    # 从config中提取碰撞引擎配置
    if 'collision' in config:
        collision_config = config['collision']
        if 'max_workers' in collision_config:
            merged['max_workers'] = collision_config['max_workers']
        if 'checkpoint_interval' in collision_config:
            merged['checkpoint_interval'] = collision_config['checkpoint_interval']
        if 'dedup_max_size' in collision_config:
            merged['dedup_max_size'] = collision_config['dedup_max_size']
    
    # kwargs覆盖config（kwargs优先级更高）
    merged.update(kwargs)
    
    return merged
