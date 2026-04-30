# -*- coding: utf-8 -*-
"""告警通知渠道体系

P2-7 实现：将告警系统从单一日志通知扩展为多渠道通知架构。

提供通知渠道抽象基类和具体实现:
- NotificationChannel (ABC): 通知渠道抽象基类
- ConsoleNotification: 控制台彩色输出
- LogFileNotification: 追加写入告警日志文件
- CompositeNotification: 组合多个渠道同步发送

架构依赖：
    任何实现 send(alert: AlertRecord) 的对象都可作为通知渠道，
    无需继承 NotificationChannel（鸭子类型兼容）。
"""

import logging
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .alert_system import AlertRecord, AlertLevel

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# ANSI 颜色代码 (ConsoleNotification 使用)
# ──────────────────────────────────────────────
_COLORS = {
    AlertLevel.INFO:       '\033[94m',  # 蓝色
    AlertLevel.WARNING:    '\033[93m',  # 黄色
    AlertLevel.CRITICAL:   '\033[91m',  # 红色
    AlertLevel.EMERGENCY:  '\033[95m',  # 紫色
}
_RESET = '\033[0m'
_BOLD = '\033[1m'


class NotificationChannel(ABC):
    """通知渠道抽象基类

    使用示例:
        class EmailNotification(NotificationChannel):
            @property
            def name(self) -> str:
                return "Email"

            def send(self, alert: AlertRecord) -> None:
                # 发送邮件实现
                pass
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道名称 (用于日志标识)"""
        ...

    @abstractmethod
    def send(self, alert: AlertRecord) -> None:
        """发送通知

        Args:
            alert: 告警记录
        """
        ...


class ConsoleNotification(NotificationChannel):
    """控制台彩色输出通知渠道

    根据告警级别使用不同颜色打印到 stderr：
    - INFO → 蓝色
    - WARNING → 黄色
    - CRITICAL → 红色
    - EMERGENCY → 紫色加粗

    使用示例:
        channel = ConsoleNotification()
        alert_system.add_notification_channel(channel)
    """

    @property
    def name(self) -> str:
        return "Console"

    def send(self, alert: AlertRecord) -> None:
        color = _COLORS.get(alert.level, '\033[0m')
        prefix = _BOLD if alert.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY) else ''

        try:
            timestamp = datetime.fromisoformat(alert.timestamp).strftime('%H:%M:%S')
        except (ValueError, AttributeError):
            timestamp = alert.timestamp or '--:--:--'

        line = (
            f"{prefix}{color}[{alert.level.value.upper():>8}] "
            f"{timestamp}  {alert.message}{_RESET}"
        )
        print(line, file=sys.stderr, flush=True)


class LogFileNotification(NotificationChannel):
    """告警日志文件通知渠道

    将告警记录追加写入指定文本文件，格式为：
    [LEVEL] 2026-01-01 12:00:00 | PERFORMANCE_DEGRADATION | 告警消息

    使用示例:
        channel = LogFileNotification("logs/alerts.log")
        alert_system.add_notification_channel(channel)
    """

    def __init__(self, file_path: str = "logs/alert_notifications.log") -> None:
        """
        Args:
            file_path: 告警通知日志文件路径
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return f"LogFile({self.file_path})"

    def send(self, alert: AlertRecord) -> None:
        try:
            timestamp = self._format_timestamp(alert.timestamp)
        except Exception:
            timestamp = alert.timestamp or '????-??-?? ??:??:??'

        line = (
            f"[{alert.level.value.upper():>8}] "
            f"{timestamp} | "
            f"{alert.alert_type.value:>25} | "
            f"{alert.message}\n"
        )

        try:
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(line)
        except OSError as e:
            logger.error(f"写入告警通知文件失败 ({self.file_path}): {e}")

    @staticmethod
    def _format_timestamp(ts_str: str) -> str:
        """将 ISO 时间戳转换为可读格式"""
        return datetime.fromisoformat(ts_str).strftime('%Y-%m-%d %H:%M:%S')


class CompositeNotification(NotificationChannel):
    """组合通知渠道 — 将告警同步发送到多个渠道

    使用示例:
        composite = CompositeNotification([
            ConsoleNotification(),
            LogFileNotification("logs/alerts.log"),
        ])
        alert_system.add_notification_channel(composite)
    """

    def __init__(self, channels: Optional[List[NotificationChannel]] = None) -> None:
        """
        Args:
            channels: 初始渠道列表
        """
        self.channels: List[NotificationChannel] = list(channels) if channels else []

    @property
    def name(self) -> str:
        return f"Composite({', '.join(c.name for c in self.channels)})"

    def send(self, alert: AlertRecord) -> None:
        for channel in self.channels:
            try:
                channel.send(alert)
            except Exception as e:
                logger.error(
                    f"通知渠道 {channel.name} 发送失败: {e}",
                    exc_info=False,
                )

    def add(self, channel: NotificationChannel) -> None:
        """动态添加渠道"""
        self.channels.append(channel)
