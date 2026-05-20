"""通知渠道体系单元测试 (P2-7)

覆盖:
- NotificationChannel ABC 抽象性
- ConsoleNotification 各级别着色输出
- LogFileNotification 文件追加写入
- CompositeNotification 组合转发与异常隔离
- AlertSystem 集成: add/remove_notification_channel
- _trigger_alert 多渠道发送
"""

import io
import os
import sys
import tempfile
import unittest
from datetime import datetime

from src.monitoring.alert_system import (
    AlertLevel,
    AlertRecord,
    AlertSystem,
    AlertType,
)
from src.monitoring.notification_channels import (
    CompositeNotification,
    ConsoleNotification,
    LogFileNotification,
    NotificationChannel,
)


class TestNotificationChannelABC(unittest.TestCase):
    """NotificationChannel 抽象基类测试"""

    def test_01_cannot_instantiate_abc(self):
        """抽象基类不可直接实例化"""
        with self.assertRaises(TypeError):
            NotificationChannel()  # type: ignore[abstract]

    def test_02_concrete_subclass_instantiable(self):
        """实现 name/send 的子类可实例化"""

        class TestChannel(NotificationChannel):
            def __init__(self):
                self.sent: list = []

            @property
            def name(self) -> str:
                return "Test"

            def send(self, alert):
                self.sent.append(alert)

        ch = TestChannel()
        self.assertIsInstance(ch, NotificationChannel)

    def test_03_duck_typing_notification(self):
        """鸭子类型: 有 send(alert) 方法即可作为通知渠道"""
        sent = []

        class DuckChannel:
            @property
            def name(self):
                return "Duck"

            def send(self, alert):
                sent.append(alert.message)

        alert = AlertRecord(
            timestamp=datetime.now().isoformat(),
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="测试鸭子类型通知",
            metrics={},
        )

        duck = DuckChannel()
        duck.send(alert)
        self.assertIn("测试鸭子类型通知", sent)


class TestConsoleNotification(unittest.TestCase):
    """ConsoleNotification 控制台通知测试"""

    def setUp(self):
        self.channel = ConsoleNotification()

    def _capture_stderr(self, alert):
        """捕获 stderr 输出"""
        buf = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            self.channel.send(alert)
            return buf.getvalue()
        finally:
            sys.stderr = old_stderr

    def test_01_console_name(self):
        self.assertEqual(self.channel.name, "Console")

    def test_02_warning_output(self):
        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.MEMORY_OVERFLOW,
            level=AlertLevel.WARNING,
            message="内存使用过高",
            metrics={},
        )
        output = self._capture_stderr(alert)
        self.assertIn("WARNING", output)
        self.assertIn("内存使用过高", output)

    def test_03_critical_output(self):
        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.GPU_OVERHEAT,
            level=AlertLevel.CRITICAL,
            message="GPU温度过高",
            metrics={},
        )
        output = self._capture_stderr(alert)
        self.assertIn("CRITICAL", output)
        self.assertIn("GPU温度过高", output)

    def test_04_info_output(self):
        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.SYSTEM_STABLE,
            level=AlertLevel.INFO,
            message="系统恢复稳定",
            metrics={},
        )
        output = self._capture_stderr(alert)
        self.assertIn("INFO", output)

    def test_05_emergency_output(self):
        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.ERROR_RATE_HIGH,
            level=AlertLevel.EMERGENCY,
            message="紧急告警",
            metrics={},
        )
        output = self._capture_stderr(alert)
        self.assertIn("EMERGENCY", output)

    def test_06_invalid_timestamp_fallback(self):
        """无效时间戳不应崩溃"""
        alert = AlertRecord(
            timestamp="not-a-timestamp",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="测试时间戳回退",
            metrics={},
        )
        output = self._capture_stderr(alert)
        self.assertIn("测试时间戳回退", output)


class TestLogFileNotification(unittest.TestCase):
    """LogFileNotification 文件通知测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "alerts.log")

    def tearDown(self):
        try:
            os.remove(self.log_path)
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def test_01_logfile_name(self):
        ch = LogFileNotification(self.log_path)
        self.assertIn("LogFile", ch.name)
        self.assertIn(self.log_path, ch.name)

    def test_02_logfile_write(self):
        ch = LogFileNotification(self.log_path)
        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.THROUGHPUT_DROP,
            level=AlertLevel.CRITICAL,
            message="吞吐量严重下降",
            metrics={},
        )
        ch.send(alert)

        with open(self.log_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("CRITICAL", content)
        self.assertIn("吞吐量严重下降", content)

    def test_03_logfile_append(self):
        """多次写入应追加而非覆盖"""
        ch = LogFileNotification(self.log_path)
        a1 = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.MEMORY_OVERFLOW,
            level=AlertLevel.WARNING,
            message="告警A",
            metrics={},
        )
        a2 = AlertRecord(
            timestamp="2026-01-01T12:01:00",
            alert_type=AlertType.GPU_OVERHEAT,
            level=AlertLevel.CRITICAL,
            message="告警B",
            metrics={},
        )
        ch.send(a1)
        ch.send(a2)

        with open(self.log_path, encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("告警A", lines[0])
        self.assertIn("告警B", lines[1])

    def test_04_parent_dir_auto_create(self):
        """父目录自动创建"""
        subdir = os.path.join(self.tmpdir, "sub", "nested")
        log_path = os.path.join(subdir, "alerts.log")
        ch = LogFileNotification(log_path)
        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="测试目录创建",
            metrics={},
        )
        ch.send(alert)
        self.assertTrue(os.path.exists(log_path))

        # 清理
        os.remove(log_path)
        os.rmdir(subdir)
        os.rmdir(os.path.join(self.tmpdir, "sub"))


class TestCompositeNotification(unittest.TestCase):
    """CompositeNotification 组合通知测试"""

    def setUp(self):
        self.channel_a_sent: list = []
        self.channel_b_sent: list = []

        class MockChannel(NotificationChannel):
            def __init__(self, name, store):
                self._name = name
                self._store = store

            @property
            def name(self) -> str:
                return self._name

            def send(self, alert):
                self._store.append(alert.message)

        self.ch_a = MockChannel("A", self.channel_a_sent)
        self.ch_b = MockChannel("B", self.channel_b_sent)
        self.composite = CompositeNotification([self.ch_a])

    def test_01_composite_name(self):
        self.assertIn("A", self.composite.name)

    def test_02_add_channel(self):
        self.composite.add(self.ch_b)
        self.assertIn("B", self.composite.name)

    def test_03_forward_to_all(self):
        self.composite.add(self.ch_b)
        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="组合通知测试",
            metrics={},
        )
        self.composite.send(alert)
        self.assertIn("组合通知测试", self.channel_a_sent)
        self.assertIn("组合通知测试", self.channel_b_sent)

    def test_04_exception_isolation(self):
        """一个渠道失败不应阻止其他渠道"""

        class FailingChannel(NotificationChannel):
            @property
            def name(self) -> str:
                return "Failing"

            def send(self, alert):
                raise RuntimeError("Simulated channel failure")

        self.composite.add(FailingChannel())
        self.composite.add(self.ch_b)

        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="异常隔离测试",
            metrics={},
        )
        # 不应崩溃
        self.composite.send(alert)
        # B 渠道仍应收到
        self.assertIn("异常隔离测试", self.channel_b_sent)


class TestAlertSystemIntegration(unittest.TestCase):
    """AlertSystem 多渠道集成测试"""

    def setUp(self):
        self.system = AlertSystem(alert_log_file=":memory:")  # 不写文件
        self.system.alert_log_file = None

    def test_01_add_notification_channel(self):
        """add_notification_channel 添加渠道"""
        ch = ConsoleNotification()
        self.system.add_notification_channel(ch)
        self.assertEqual(len(self.system.notification_channels), 1)
        self.assertIs(self.system.notification_channels[0], ch)

    def test_02_remove_notification_channel(self):
        """remove_notification_channel 移除渠道"""
        ch = ConsoleNotification()
        self.system.add_notification_channel(ch)
        result = self.system.remove_notification_channel(ch)
        self.assertTrue(result)
        self.assertEqual(len(self.system.notification_channels), 0)

    def test_03_remove_nonexistent(self):
        """移除不存在的渠道返回 False"""
        ch = ConsoleNotification()
        result = self.system.remove_notification_channel(ch)
        self.assertFalse(result)

    def test_04_trigger_alert_sends_to_channel(self):
        """_trigger_alert 发送到注册的渠道"""
        sent: list = []

        class CollectChannel:
            @property
            def name(self):
                return "Collect"

            def send(self, alert):
                sent.append(alert)

        ch = CollectChannel()
        self.system.add_notification_channel(ch)

        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="集成测试告警",
            metrics={},
        )
        self.system._trigger_alert(alert)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].message, "集成测试告警")

    def test_05_channel_exception_does_not_block_system(self):
        """渠道异常不阻塞告警系统"""

        class FailingChannel:
            @property
            def name(self):
                return "Fail"

            def send(self, alert):
                raise RuntimeError("Channel failure")

        self.system.add_notification_channel(FailingChannel())
        self.system.add_notification_channel(ConsoleNotification())

        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="异常不应阻塞",
            metrics={},
        )
        # 不应崩溃
        self.system._trigger_alert(alert)

    def test_06_backward_compat_callbacks_still_work(self):
        """旧版 alert_callbacks 仍正常工作"""
        sent: list = []

        def my_callback(alert):
            sent.append(alert.message)

        self.system.add_alert_callback(my_callback)

        alert = AlertRecord(
            timestamp="2026-01-01T12:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="回调兼容测试",
            metrics={},
        )
        self.system._trigger_alert(alert)
        self.assertIn("回调兼容测试", sent)


if __name__ == "__main__":
    unittest.main()
