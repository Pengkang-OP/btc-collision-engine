#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志处理器

处理和格式化日志数据。
"""

import re
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from .events import LogEvent, LogEventType


class LogProcessor:
    """日志处理器

    负责日志的格式化和处理。
    """

    def __init__(self):
        self._filters = []
        self._redactors = []  # 脱敏器：修改事件数据，不丢弃事件
        self._formatters = {}

    def process(self, event: LogEvent) -> Optional[Dict[str, Any]]:
        """处理日志事件

        Args:
            event: 日志事件

        Returns:
            处理后的事件字典，如果被过滤则返回None
        """
        # 1. 先应用脱敏器（修改 data 内容，不丢弃事件）
        for redact_func in self._redactors:
            event.data = redact_func(event.data)

        # 2. 再应用丢弃过滤器
        for filter_func in self._filters:
            if not filter_func(event):
                return None

        # 格式化
        formatted = self.format(event)

        # 调用格式化器
        formatter = self._formatters.get(event.event_type.value)
        if formatter:
            formatted = formatter(formatted)

        return formatted

    def format(self, event: LogEvent) -> Dict[str, Any]:
        """格式化事件

        Args:
            event: 日志事件

        Returns:
            格式化后的事件字典
        """
        return {
            "timestamp": event.timestamp,
            "formatted_time": event.formatted_time,
            "type": event.event_type.value,
            "source": event.source,
            "data": event.data,
            "message": self._build_message(event),
        }

    def _build_message(self, event: LogEvent) -> str:
        """构建日志消息"""
        msg_parts = [f"[{event.event_type.value}]"]

        if event.source != "logging":
            msg_parts.append(f"({event.source})")

        data = event.data
        if isinstance(data, dict):
            if "message" in data:
                msg_parts.append(data["message"])
            elif "error" in data:
                msg_parts.append(f"Error: {data['error']}")
            elif "status" in data:
                msg_parts.append(data["status"])
            else:
                msg_parts.append(str(data))
        else:
            msg_parts.append(str(data))

        return " ".join(msg_parts)

    def add_redactor(self, redact_func):
        """添加脱敏器

        脱敏器修改事件内容（如替换敏感信息），不丢弃事件。

        Args:
            redact_func: 脱敏函数，接收 event.data，返回修改后的 data
        """
        self._redactors.append(redact_func)

    def add_filter(self, filter_func):
        """添加过滤器

        Args:
            filter_func: 过滤函数，接收LogEvent，返回bool
        """
        self._filters.append(filter_func)

    def remove_filter(self, filter_func):
        """移除过滤器"""
        if filter_func in self._filters:
            self._filters.remove(filter_func)

    def add_formatter(self, event_type: str, formatter_func):
        """添加格式化器

        Args:
            event_type: 事件类型
            formatter_func: 格式化函数
        """
        self._formatters[event_type] = formatter_func

    def remove_formatter(self, event_type: str):
        """移除格式化器"""
        self._formatters.pop(event_type, None)

    def format_to_json(self, event: LogEvent) -> str:
        """格式化为JSON字符串"""
        formatted = self.format(event)
        return json.dumps(formatted, ensure_ascii=False)

    def format_to_text(self, event: LogEvent) -> str:
        """格式化为文本"""
        formatted = self.format(event)
        return f"{formatted['formatted_time']} {formatted['message']}"

    def process_batch(self, events: List[LogEvent]) -> List[Dict[str, Any]]:
        """批量处理事件

        Args:
            events: 事件列表

        Returns:
            处理后的事件字典列表
        """
        results = []
        for event in events:
            result = self.process(event)
            if result:
                results.append(result)
        return results


class SensitiveDataFilter:
    """敏感数据过滤器

    过滤可能包含私钥等敏感信息的数据。
    """

    SENSITIVE_PATTERNS = [
        (r"[0-9a-fA-F]{64}", "***REDACTED***"),  # 私钥 (hex)
        (r'PrivateKey["\']?\s*[:=]\s*["\']?[0-9a-fA-F]{64}', "***REDACTED***"),
        # P0-1: 比特币地址模式
        (r"\b1[1-9A-HJ-NP-Za-km-z]{24,33}\b", "[P2PKH_ADDRESS]"),  # P2PKH
        (r"\b3[1-9A-HJ-NP-Za-km-z]{24,33}\b", "[P2SH_ADDRESS]"),  # P2SH
        (r"\bbc1[ac-hj-np-z02-9]{38,58}\b", "[BECH32_ADDRESS]"),  # Bech32
        (r"\bbc1p[ac-hj-np-z02-9]{58}\b", "[BECH32M_ADDRESS]"),  # Bech32m
        # P1-1: WIF 格式私钥
        (r"\b5[HJK][1-9A-HJ-NP-Za-km-z]{48,49}\b", "[WIF_UNCOMPRESSED_KEY]"),
        (r"\b[KL][1-9A-HJ-NP-Za-km-z]{50,51}\b", "[WIF_COMPRESSED_KEY]"),
        # BIP32 扩展密钥
        (r"\b[xXtT]prv[1-9A-HJ-NP-Za-km-z]{107,108}\b", "[BIP32_EXTENDED_KEY]"),
        (r"\b[xXtT]pub[1-9A-HJ-NP-Za-km-z]{107,108}\b", "[BIP32_EXTENDED_PUBKEY]"),
    ]

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def filter(self, event: LogEvent) -> bool:
        """过滤敏感数据"""
        if not self.enabled:
            return True

        data_str = str(event.data)

        for pattern, replacement in self.SENSITIVE_PATTERNS:
            if re.search(pattern, data_str, re.IGNORECASE):
                return False

        return True

    @classmethod
    def redact_data(cls, data: Any) -> Any:
        """脱敏数据（支持 str/dict/list）

        对事件数据进行脱敏处理，修改内容而非丢弃事件。
        """
        if isinstance(data, str):
            return cls.redact(data)
        elif isinstance(data, dict):
            return {k: cls.redact_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.redact_data(item) for item in data]
        return data

    @classmethod
    def redact(cls, text: str) -> str:
        """脱敏文本"""
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
