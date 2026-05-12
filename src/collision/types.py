"""碰撞引擎类型定义

定义回调函数类型别名，统一CPU和GPU引擎的接口签名。

使用示例:
    >>> from src.collision.types import ProgressCallback, MatchCallback
    >>> from src.collision.collision_stats import CollisionStats
    >>>
    >>> def my_progress_handler(stats: CollisionStats) -> None:
    ...     print(f"速度: {stats.speed}")
    >>>
    >>> # 类型提示会自动检查参数
    >>> callback: ProgressCallback = my_progress_handler
"""

from collections.abc import Callable
from typing import Any

from .collision_stats import CollisionStats

# ============================================================================
# 回调函数类型别名
# ============================================================================

ProgressCallback = Callable[[CollisionStats], None]
"""
进度回调函数类型

签名: (stats: CollisionStats) -> None

参数:
    stats: 碰撞统计信息对象，包含速度、检测数、匹配数等

示例:
    >>> def handle_progress(stats: CollisionStats) -> None:
    ...     print(f"速度: {stats.speed} keys/s")
    ...     print(f"已检测: {stats.total_checked}")
    ...     print(f"匹配数: {stats.matches_found}")
    >>>
    >>> engine = KeyCollisionEngine(
    ...     targets=targets,
    ...     on_progress=handle_progress
    ... )
"""

MatchCallback = Callable[[bytes, str, str], None]
"""
匹配回调函数类型

签名: (private_key: bytes, address: str, wif: str) -> None

参数:
    private_key: 匹配的私钥 (bytes格式)
    address: 生成的比特币地址
    wif: WIF格式私钥

⚠️ 安全注意:
    private_key 是敏感信息，使用后应立即清零。
    不要将私钥记录到日志或传递给不可信的函数。

示例:
    >>> def handle_match(private_key: bytes, address: str, wif: str) -> None:
    ...     # 保存匹配结果
    ...     save_match(address, wif)
    ...
    ...     # 安全清零私钥
    ...     secure_clear_bytearray(private_key)
    >>>
    >>> engine = KeyCollisionEngine(
    ...     targets=targets,
    ...     on_match=handle_match
    ... )
"""

CompleteCallback = Callable[[CollisionStats], None]
"""
完成回调函数类型

签名: (stats: CollisionStats) -> None

参数:
    stats: 最终碰撞统计信息对象

示例:
    >>> def handle_complete(stats: CollisionStats) -> None:
    ...     print("碰撞完成!")
    ...     print(f"总检测: {stats.total_checked}")
    ...     print(f"总匹配: {stats.matches_found}")
    ...     print(f"平均速度: {stats.avg_speed} keys/s")
    >>>
    >>> engine = KeyCollisionEngine(
    ...     targets=targets,
    ...     on_complete=handle_complete
    ... )
"""

ErrorCallback = Callable[[str, str, Exception | None], None]
"""
错误回调函数类型

签名: (error_type: str, message: str, exception: Optional[Exception]) -> None

参数:
    error_type: 错误类型 (如 "invalid_key", "address_generation_failed")
    message: 错误消息
    exception: 异常对象 (如果有的话)

示例:
    >>> def handle_error(error_type: str, message: str, exception: Optional[Exception]) -> None:
    ...     print(f"错误 [{error_type}]: {message}")
    ...     if exception:
    ...         print(f"异常详情: {exception}")
    >>>
    >>> engine = KeyCollisionEngine(
    ...     targets=targets
    ... )
    >>> engine.on_error = handle_error
"""


# ============================================================================
# 事件处理器类型
# ============================================================================

from .events import CollisionEvent  # noqa: E402

EventHandler = Callable[[CollisionEvent], None]
"""
事件处理器函数类型

签名: (event: CollisionEvent) -> None

参数:
    event: 事件对象 (如 EngineProgressEvent, EngineMatchEvent等)

示例:
    >>> from src.collision.events import EngineProgressEvent
    >>>
    >>> def handle_event(event: CollisionEvent) -> None:
    ...     if isinstance(event, EngineProgressEvent):
    ...         print(f"进度: {event.total_checked}")
    >>>
    >>> event_bus.subscribe(EventType.ENGINE_PROGRESS, handle_event)
"""

ErrorHandler = Callable[[CollisionEvent, Exception], None]
"""
错误处理器函数类型

签名: (event: CollisionEvent, exception: Exception) -> None

参数:
    event: 触发错误的事件对象
    exception: 异常对象

示例:
    >>> def handle_error(event: CollisionEvent, exception: Exception) -> None:
    ...     print(f"事件处理失败: {exception}")
    ...     logger.error(f"事件: {event.event_type}, 错误: {exception}")
    >>>
    >>> event_bus.set_error_handler(handle_error)
"""


# ============================================================================
# 引擎配置类型
# ============================================================================

TargetAddresses = set[str]
"""目标地址集合类型"""

EngineConfig = dict[str, Any]
"""引擎配置字典类型"""

MatchResult = dict[str, str]
"""匹配结果字典类型"""
