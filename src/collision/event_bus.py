"""事件总线 - 发布/订阅模式实现

用于解耦碰撞引擎与监控/日志系统的通信。

使用示例:
    >>> from src.collision.event_bus import EventBus
    >>> from src.collision.events import EngineProgressEvent, EventType
    >>>
    >>> # 创建事件总线
    >>> bus = EventBus()
    >>>
    >>> # 订阅事件
    >>> def handle_progress(event):
    ...     print(f"进度: {event.total_checked}")
    >>>
    >>> bus.subscribe(EventType.ENGINE_PROGRESS, handle_progress)
    >>>
    >>> # 发布事件
    >>> event = EngineProgressEvent(total_checked=1000000, speed=537000.0)
    >>> bus.publish(event)
    >>>
    >>> # 取消订阅
    >>> bus.unsubscribe(EventType.ENGINE_PROGRESS, handle_progress)
"""

import threading
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
import logging

from .events import CollisionEvent, EventType

logger = logging.getLogger(__name__)


class EventBus:
    """
    事件总线 - 解耦组件通信

    实现发布/订阅模式，允许组件通过事件进行通信，
    而无需直接依赖彼此。

    Attributes:
        async_mode: 是否异步处理事件
        max_queue_size: 事件队列最大大小 (异步模式)

    Example:
        >>> bus = EventBus()
        >>>
        >>> # 订阅多个事件
        >>> bus.subscribe(EventType.ENGINE_PROGRESS, progress_handler)
        >>> bus.subscribe(EventType.ENGINE_MATCH, match_handler)
        >>> bus.subscribe(EventType.ENGINE_ERROR, error_handler)
        >>>
        >>> # 发布事件
        >>> bus.publish(EngineProgressEvent(total_checked=1000, speed=500000))
        >>>
        >>> # 获取统计信息
        >>> print(f"订阅者数量: {bus.subscriber_count}")
        >>> print(f"发布事件数: {bus.published_count}")
    """

    def __init__(self, async_mode: bool = False, max_queue_size: int = 1000) -> None:
        """
        初始化事件总线

        Args:
            async_mode: 是否异步处理事件 (默认False)
            max_queue_size: 事件队列最大大小 (异步模式)
        """
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._error_handler: Optional[Callable] = None
        self._async_mode = async_mode
        self._max_queue_size = max_queue_size

        # 统计信息
        self._published_count = 0
        self._error_count = 0

        # 异步队列（同步模式下为 None）
        self._event_queue: Optional[Any] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._running: bool = False

        if async_mode:
            import queue

            self._event_queue = queue.Queue(maxsize=max_queue_size)
            self._running = True
            self._worker_thread = threading.Thread(target=self._process_events, daemon=True)
            self._worker_thread.start()
            logger.info("事件总线已启动 (异步模式)")
        else:
            logger.debug("事件总线已初始化 (同步模式)")

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数，签名为 handler(event: CollisionEvent) -> None

        Example:
            >>> def handle_progress(event: EngineProgressEvent):
            ...     print(f"速度: {event.speed}")
            >>>
            >>> bus.subscribe(EventType.ENGINE_PROGRESS, handle_progress)
        """
        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(f"订阅事件: {event_type.value}, 处理器: {handler.__name__}")

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        取消订阅

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        with self._lock:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"取消订阅: {event_type.value}, 处理器: {handler.__name__}")

    def subscribe_to_all(self, handler: Callable) -> None:
        """
        订阅所有事件类型

        Args:
            handler: 事件处理函数，签名为 handler(event_type: EventType, event: CollisionEvent) -> None

        Example:
            >>> def handle_all(event_type, event):
            ...     print(f"收到事件: {event_type.value}")
            >>>
            >>> bus.subscribe_to_all(handle_all)
        """

        def wrapper(event: CollisionEvent) -> None:
            handler(event.event_type, event)

        # 订阅所有事件类型
        for event_type in EventType:
            self.subscribe(event_type, wrapper)

    def publish(self, event: CollisionEvent) -> None:
        """
        发布事件

        Args:
            event: 事件对象

        Example:
            >>> event = EngineProgressEvent(total_checked=1000, speed=500000)
            >>> bus.publish(event)
        """
        if event is None:
            logger.warning("publish() 收到 None 事件，已忽略")
            return
        if event.event_type is None:
            logger.warning("publish() 收到 event_type 为 None 的事件，已忽略")
            return

        self._published_count += 1

        if self._async_mode:
            # 异步模式: 加入队列
            assert self._event_queue is not None
            try:
                self._event_queue.put_nowait(event)
            except Exception as e:  # noqa: F841
                logger.warning(f"事件队列已满，丢弃事件: {event.event_type.value}")
        else:
            # 同步模式: 直接处理
            self._dispatch_event(event)

    def _dispatch_event(self, event: CollisionEvent) -> None:
        """
        分发事件到所有订阅者

        Args:
            event: 事件对象
        """
        with self._lock:
            handlers = list(self._subscribers.get(event.event_type, [])) if event.event_type else []

        if not handlers:
            logger.debug(f"事件无订阅者: {event.event_type.value if event.event_type else 'N/A'}")
            return

        # 在锁外执行处理器，避免死锁
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self._error_count += 1
                logger.error(f"事件处理器异常 [{handler.__name__}]: {e}")

                if self._error_handler:
                    try:
                        self._error_handler(event, e)
                    except Exception as handler_err:
                        logger.error(f"错误处理器异常: {handler_err}")

    def _process_events(self) -> None:
        """异步处理事件队列 (后台线程)"""
        import queue

        logger.info("事件处理线程已启动")

        while self._running:
            assert self._event_queue is not None
            try:
                event = self._event_queue.get(timeout=0.1)
                self._dispatch_event(event)
                self._event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"事件处理异常: {e}")

        logger.info("事件处理线程已停止")

    def set_error_handler(self, handler: Callable) -> None:
        """
        设置全局错误处理器

        Args:
            handler: 错误处理函数，签名为 handler(event, exception) -> None
        """
        self._error_handler = handler
        logger.debug("全局错误处理器已设置")

    def stop(self) -> None:
        """
        停止事件总线 (异步模式)

        清空事件队列并停止工作线程。
        """
        if self._async_mode:
            self._running = False

            # 清空队列
            assert self._event_queue is not None
            try:
                while not self._event_queue.empty():
                    self._event_queue.get_nowait()
            except Exception:
                pass

            # 等待工作线程结束
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=2.0)

            logger.info("事件总线已停止")

    def clear(self) -> None:
        """清空所有订阅"""
        with self._lock:
            subscriber_count = self.subscriber_count
            self._subscribers.clear()
            logger.info(f"清空所有订阅 (共 {subscriber_count} 个订阅者)")

    def shutdown(self) -> None:
        """关闭事件总线 (异步模式)"""
        if self._async_mode:
            self._running = False
            if self._worker_thread:
                self._worker_thread.join(timeout=5)
            logger.info("事件总线已关闭")

    @property
    def subscriber_count(self) -> int:
        """获取订阅者总数"""
        with self._lock:
            return sum(len(handlers) for handlers in self._subscribers.values())

    @property
    def published_count(self) -> int:
        """获取已发布事件总数"""
        return self._published_count

    @property
    def error_count(self) -> int:
        """获取错误总数"""
        return self._error_count

    def get_stats(self) -> Dict[str, int]:
        """
        获取事件总线统计信息

        Returns:
            统计信息字典
        """
        return {
            "subscriber_count": self.subscriber_count,
            "published_count": self._published_count,
            "error_count": self._error_count,
            "async_mode": self._async_mode,
            "queue_size": self._event_queue.qsize() if self._event_queue else 0,
        }

    def __enter__(self) -> "EventBus":
        """上下文管理器入口"""
        return self

    def __exit__(
        self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]
    ) -> None:
        """上下文管理器出口"""
        self.shutdown()


# 全局事件总线实例 (单例模式)
_global_event_bus: Optional[EventBus] = None
_global_event_bus_lock = threading.Lock()


def get_event_bus(async_mode: bool = False) -> EventBus:
    """
    获取全局事件总线 (单例)

    Args:
        async_mode: 是否异步模式 (仅在首次调用时有效)

    Returns:
        全局事件总线实例

    Example:
        >>> bus = get_event_bus()
        >>> bus.subscribe(EventType.ENGINE_PROGRESS, handler)
    """
    global _global_event_bus

    if _global_event_bus is None:
        with _global_event_bus_lock:
            if _global_event_bus is None:
                _global_event_bus = EventBus(async_mode=async_mode)

    return _global_event_bus


def reset_event_bus() -> None:
    """
    重置全局事件总线 (主要用于测试)

    Warning:
        仅用于测试环境，生产环境不应调用此函数
    """
    global _global_event_bus

    with _global_event_bus_lock:
        if _global_event_bus:
            _global_event_bus.shutdown()
            _global_event_bus = None
            logger.info("全局事件总线已重置")
