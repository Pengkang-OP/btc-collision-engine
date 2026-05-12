#!/usr/bin/env python3
"""
引导事件定义

定义引导界面模块的事件类型。
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WizardEventType(Enum):
    """引导事件类型"""

    WIZARD_START = "wizard_start"
    TARGET_SELECTED = "target_selected"
    MODE_SELECTED = "mode_selected"
    OPTIONS_SELECTED = "options_selected"
    GPU_SELECTED = "gpu_selected"
    CONFIG_BUILT = "config_built"
    WIZARD_COMPLETE = "wizard_complete"
    WIZARD_CANCELLED = "wizard_cancelled"
    WIZARD_ERROR = "wizard_error"
    USER_INPUT = "user_input"
    VALIDATION_FAILED = "validation_failed"


@dataclass
class WizardEvent:
    """引导事件数据结构"""

    event_type: WizardEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "wizard"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        }


class EventDispatcher:
    """事件分发器"""

    def __init__(self):
        self._listeners: dict[WizardEventType, list] = {}

    def register(self, event_type: WizardEventType, callback):
        """注册事件监听器"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unregister(self, event_type: WizardEventType, callback):
        """取消注册事件监听器"""
        if event_type in self._listeners:
            self._listeners[event_type].remove(callback)

    def dispatch(self, event: WizardEvent):
        """分发事件"""
        if event.event_type in self._listeners:
            for callback in self._listeners[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(
                        f"Event callback failed for {event.event_type.value}: {e}", exc_info=True
                    )

    def clear(self):
        """清空所有监听器"""
        self._listeners.clear()
