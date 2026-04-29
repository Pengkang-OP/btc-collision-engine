#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引导模块消息队列

用于引导模块与日志模块之间的异步消息传递。
"""

import queue
import threading
import time
from typing import Optional, Dict, Any
from .events import WizardEvent, WizardEventType


class WizardMessageQueue:
    """引导模块到日志模块的消息队列"""

    def __init__(self, maxsize: int = 1000):
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._enabled = True
        self._subscribers: list = []

    def send(self, event_type: WizardEventType, data: Dict[str, Any], priority: int = 5) -> bool:
        """发送事件到队列

        Args:
            event_type: 事件类型
            data: 事件数据
            priority: 优先级（1-10，1最高）

        Returns:
            bool: 是否发送成功
        """
        if not self._enabled:
            return False

        try:
            event = WizardEvent(event_type=event_type, data=data)
            self._queue.put_nowait((priority, event))
            self._notify_subscribers(event)
            return True
        except queue.Full:
            return False

    def send_wizard_start(self, config: Dict[str, Any]) -> bool:
        """发送向导开始事件"""
        return self.send(WizardEventType.WIZARD_START, {'config': config})

    def send_target_selected(self, targets: list, target_file: Optional[str] = None) -> bool:
        """发送目标选择事件"""
        return self.send(WizardEventType.TARGET_SELECTED, {
            'targets': targets,
            'target_file': target_file
        })

    def send_mode_selected(self, mode: str, start_key: Optional[str] = None,
                          end_key: Optional[str] = None) -> bool:
        """发送模式选择事件"""
        return self.send(WizardEventType.MODE_SELECTED, {
            'mode': mode,
            'start_key': start_key,
            'end_key': end_key
        })

    def send_options_selected(self, checkpoint: bool, dedup: bool, duration: int) -> bool:
        """发送选项选择事件"""
        return self.send(WizardEventType.OPTIONS_SELECTED, {
            'checkpoint': checkpoint,
            'dedup': dedup,
            'duration': duration
        })

    def send_gpu_selected(self, gpu_indices: list, use_multi_gpu: bool) -> bool:
        """发送GPU选择事件"""
        return self.send(WizardEventType.GPU_SELECTED, {
            'gpu_indices': gpu_indices,
            'use_multi_gpu': use_multi_gpu
        })

    def send_wizard_complete(self, result: Dict[str, Any]) -> bool:
        """发送向导完成事件"""
        return self.send(WizardEventType.WIZARD_COMPLETE, {'result': result})

    def send_wizard_cancelled(self) -> bool:
        """发送向导取消事件"""
        return self.send(WizardEventType.WIZARD_CANCELLED, {})

    def send_wizard_error(self, error_message: str) -> bool:
        """发送向导错误事件"""
        return self.send(WizardEventType.WIZARD_ERROR, {'error': error_message}, priority=1)

    def receive(self, timeout: Optional[float] = None) -> Optional[WizardEvent]:
        """从队列接收事件

        Args:
            timeout: 超时时间（秒）

        Returns:
            Optional[WizardEvent]: 事件对象或None
        """
        try:
            priority, event = self._queue.get(timeout=timeout)
            return event
        except queue.Empty:
            return None

    def receive_all(self, timeout: float = 0.1) -> list:
        """接收所有可用事件

        Args:
            timeout: 每次接收的超时时间

        Returns:
            list: 事件列表
        """
        events = []
        while True:
            event = self.receive(timeout)
            if event is None:
                break
            events.append(event)
        return events

    def subscribe(self, callback):
        """订阅所有事件"""
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """取消订阅"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify_subscribers(self, event: WizardEvent):
        """通知订阅者"""
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                pass

    def enable(self):
        """启用队列"""
        self._enabled = True

    def disable(self):
        """禁用队列"""
        self._enabled = False

    def clear(self):
        """清空队列"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def size(self) -> int:
        """获取队列大小"""
        return self._queue.qsize()

    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return self._queue.empty()

    def is_full(self) -> bool:
        """检查队列是否已满"""
        return self._queue.full()


# 全局消息队列实例
_global_message_queue: Optional[WizardMessageQueue] = None


def get_message_queue() -> WizardMessageQueue:
    """获取全局消息队列实例"""
    global _global_message_queue
    if _global_message_queue is None:
        _global_message_queue = WizardMessageQueue()
    return _global_message_queue


def reset_message_queue():
    """重置全局消息队列"""
    global _global_message_queue
    if _global_message_queue is not None:
        _global_message_queue.clear()
    _global_message_queue = None
