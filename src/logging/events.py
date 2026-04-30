#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志事件定义

定义日志处理模块的事件类型。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any
import time


class LogEventType(Enum):
    """日志事件类型"""

    ENGINE_START = "engine_start"
    ENGINE_STOP = "engine_stop"
    ENGINE_ERROR = "engine_error"
    ENGINE_PAUSE = "engine_pause"
    ENGINE_RESUME = "engine_resume"
    GPU_DETECTED = "gpu_detected"
    GPU_USAGE_UPDATE = "gpu_usage_update"
    PERFORMANCE_UPDATE = "performance_update"
    MATCH_FOUND = "match_found"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CONFIG_LOADED = "config_loaded"
    STATUS_UPDATE = "status_update"


@dataclass
class LogEvent:
    """日志事件数据结构"""

    event_type: LogEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "logging"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        }

    @property
    def formatted_time(self) -> str:
        """获取格式化的时间字符串"""
        from datetime import datetime

        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
