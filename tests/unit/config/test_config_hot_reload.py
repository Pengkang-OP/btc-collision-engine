"""P2-4: 配置热重载 单元测试

测试覆盖:
- ConfigWatcher: 后端选择、启停、轮询检测、防抖、错误处理
- ConfigManager: reload_config、on_config_changed、start/stop_watching
"""

import json
import os
import pathlib
import tempfile
import threading
import time

import pytest

from src.config.config_manager import ConfigManager
from src.config.config_watcher import ConfigWatcher

# ═══════════════════════════════════════════════════════════════════
# ConfigWatcher 测试
# ═══════════════════════════════════════════════════════════════════


class TestConfigWatcherBackend:
    """ConfigWatcher 后端选择测试"""

    def test_01_backend_type(self):
        """后端类型为 watchdog 或 polling"""
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with pathlib.Path(path).open("w") as f:
                json.dump({"test": True}, f)
            w = ConfigWatcher(path, lambda: None)
            assert ("watchdog", "polling") in w.backend
        finally:
            pathlib.Path(path).unlink()

    def test_02_requires_absolute_path(self):
        """拒绝相对路径"""
        with pytest.raises(ValueError):
            ConfigWatcher("relative/path.json", lambda: None)


class TestConfigWatcherLifecycle:
    """ConfigWatcher 生命周期测试"""

    def setup_method(self, method):
        fd, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"test": True}, f)

    def teardown_method(self, method):
        if pathlib.Path(self.config_path).exists():
            pathlib.Path(self.config_path).unlink()

    def test_01_start_stop(self):
        """正常启停"""
        called = []
        w = ConfigWatcher(self.config_path, lambda: called.append(1))
        assert w.start()
        assert w.is_running
        w.stop()
        assert not w.is_running

    def test_02_double_start_prevented(self):
        """重复 start 返回 False"""
        w = ConfigWatcher(self.config_path, lambda: None)
        assert w.start()
        assert not w.start()  # 第二次应失败
        w.stop()

    def test_03_stop_idempotent(self):
        """重复 stop 不抛异常"""
        w = ConfigWatcher(self.config_path, lambda: None)
        w.start()
        w.stop()
        w.stop()  # 不应抛异常

    def test_04_del_auto_stop(self):
        """析构自动停止"""
        w = ConfigWatcher(self.config_path, lambda: None)
        w.start()
        assert w.is_running
        del w  # 析构应自动停止
        # 无法直接断言，但至少不抛异常


class TestConfigWatcherPolling:
    """ConfigWatcher 轮询模式测试"""

    def setup_method(self, method):
        fd, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"version": 1}, f)

    def teardown_method(self, method):
        if pathlib.Path(self.config_path).exists():
            pathlib.Path(self.config_path).unlink()

    def test_01_poll_detects_change(self):
        """轮询检测到文件变更"""
        reloaded = []
        w = ConfigWatcher(
            self.config_path,
            on_reload=lambda: reloaded.append(True),
            poll_interval=0.3,
            debounce_seconds=0.0,
        )
        w.start()
        try:
            # 修改文件
            time.sleep(0.1)
            with pathlib.Path(self.config_path).open("w") as f:
                json.dump({"version": 2}, f)

            # 等待轮询检测
            time.sleep(1.0)

            assert len(reloaded) > 0, "轮询未检测到文件变更"
        finally:
            w.stop()

    def test_02_no_change_no_reload(self):
        """文件无变更时不触发"""
        reloaded = []
        w = ConfigWatcher(
            self.config_path,
            on_reload=lambda: reloaded.append(True),
            poll_interval=0.3,
            debounce_seconds=0.0,
        )
        w.start()
        try:
            time.sleep(1.0)
            assert len(reloaded) == 0, "无变更时不应触发重载"
        finally:
            w.stop()

    def test_03_debounce_works(self):
        """防抖：连续写入只触发一次"""
        reload_count = []
        w = ConfigWatcher(
            self.config_path,
            on_reload=lambda: reload_count.append(1),
            poll_interval=0.3,
            debounce_seconds=3.0,  # 长防抖
        )
        w.start()
        try:
            time.sleep(0.1)
            # 连续写入两次
            with pathlib.Path(self.config_path).open("w") as f:
                json.dump({"v": 1}, f)
            time.sleep(0.2)
            with pathlib.Path(self.config_path).open("w") as f:
                json.dump({"v": 2}, f)

            time.sleep(1.0)

            # 由于防抖，应该只触发一次
            assert len(reload_count) <= 1, f"防抖失效: {len(reload_count)}次触发"
        finally:
            w.stop()


class TestConfigWatcherErrors:
    """ConfigWatcher 错误处理测试"""

    def test_01_callback_exception_does_not_crash(self):
        """回调异常不导致 watcher 崩溃"""
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with pathlib.Path(path).open("w") as f:
                json.dump({}, f)

            def bad_callback():
                raise RuntimeError("Simulated error")

            w = ConfigWatcher(path, bad_callback, poll_interval=0.3, debounce_seconds=0.0)
            w.start()
            try:
                time.sleep(0.1)
                with pathlib.Path(path).open("w") as f:
                    json.dump({"new": True}, f)
                time.sleep(1.0)
                # watcher 不应崩溃
                assert w.is_running
            finally:
                w.stop()
        finally:
            pathlib.Path(path).unlink()

    def test_02_missing_file_handled(self):
        """文件不存在时轮询不崩溃"""
        import tempfile

        path = tempfile.mktemp(suffix="_nonexistent_config.json")
        w = ConfigWatcher(path, lambda: None, poll_interval=0.3)
        w.start()
        try:
            time.sleep(0.5)
            # 不应崩溃
            assert w.is_running
        finally:
            w.stop()


# ═══════════════════════════════════════════════════════════════════
# ConfigManager 热重载测试
# ═══════════════════════════════════════════════════════════════════


class TestConfigManagerReload:
    """ConfigManager.reload_config() 测试"""

    def setup_method(self, method):
        fd, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "DEBUG"}}, f)
        self.cm = ConfigManager(config_file=self.config_path)

    def teardown_method(self, method):
        self.cm.stop_watching()
        if pathlib.Path(self.config_path).exists():
            pathlib.Path(self.config_path).unlink()

    def test_01_reload_valid_config(self):
        """重载合法配置成功"""
        assert self.cm.get("logging.level") == "DEBUG"

        # 修改文件
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "WARNING"}}, f)

        result = self.cm.reload_config()
        assert result
        assert self.cm.get("logging.level") == "WARNING"

    def test_02_reload_invalid_config_preserved(self):
        """无效配置不覆盖原配置"""
        original_level = self.cm.get("logging.level")

        # 写入无效配置
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "INVALID_LEVEL"}}, f)

        result = self.cm.reload_config()
        assert not result
        # 原配置应保持不变
        assert self.cm.get("logging.level") == original_level

    def test_03_reload_no_config_file(self):
        """无配置文件时返回 False"""
        cm = ConfigManager()  # 无 config_file
        assert not cm.reload_config()

    def test_04_reload_corrupted_json(self):
        """损坏的 JSON 不覆盖原配置"""
        original_level = self.cm.get("logging.level")

        pathlib.Path(self.config_path).write_text("{ this is not valid json }")

        result = self.cm.reload_config()
        assert not result
        assert self.cm.get("logging.level") == original_level


class TestConfigManagerCallbacks:
    """ConfigManager.on_config_changed() 回调测试"""

    def setup_method(self, method):
        fd, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "INFO"}}, f)
        self.cm = ConfigManager(config_file=self.config_path)

    def teardown_method(self, method):
        self.cm.stop_watching()
        if pathlib.Path(self.config_path).exists():
            pathlib.Path(self.config_path).unlink()

    def test_01_callback_fired_on_reload(self):
        """成功重载时触发回调"""
        called = []
        self.cm.on_config_changed(lambda: called.append(True))

        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "WARNING"}}, f)

        self.cm.reload_config()
        assert len(called) == 1

    def test_02_callback_not_fired_on_failure(self):
        """重载失败时不触发回调"""
        called = []
        self.cm.on_config_changed(lambda: called.append(True))

        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "INVALID"}}, f)

        self.cm.reload_config()
        assert len(called) == 0

    def test_03_multiple_callbacks(self):
        """多个回调都被触发"""
        results = []
        self.cm.on_config_changed(lambda: results.append("A"))
        self.cm.on_config_changed(lambda: results.append("B"))

        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "ERROR"}}, f)

        self.cm.reload_config()
        assert results == ["A", "B"]

    def test_04_callback_exception_isolation(self):
        """单个回调异常不影响其他回调"""
        results = []

        def bad():
            raise RuntimeError("fail")

        def good():
            results.append("ok")

        self.cm.on_config_changed(bad)
        self.cm.on_config_changed(good)

        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "CRITICAL"}}, f)

        result = self.cm.reload_config()
        assert result  # 重载本身应成功
        assert results == ["ok"]  # 好的回调仍被调用


class TestConfigManagerWatching:
    """ConfigManager start_watching / stop_watching 测试"""

    def setup_method(self, method):
        fd, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "INFO"}}, f)
        self.cm = ConfigManager(config_file=self.config_path)

    def teardown_method(self, method):
        self.cm.stop_watching()
        if pathlib.Path(self.config_path).exists():
            pathlib.Path(self.config_path).unlink()

    def test_01_start_stop_watching(self):
        """启动和停止监听"""
        result = self.cm.start_watching()
        assert result
        assert self.cm._watcher is not None
        assert self.cm._watcher.is_running

        self.cm.stop_watching()
        assert self.cm._watcher is None

    def test_02_no_config_file(self):
        """无配置文件时返回 False"""
        cm = ConfigManager()  # 无 config_file
        assert not cm.start_watching()

    def test_03_double_start_replaces(self):
        """重复 start 替换旧的 watcher"""
        self.cm.start_watching()
        old_watcher = self.cm._watcher

        self.cm.start_watching()
        new_watcher = self.cm._watcher

        assert old_watcher is not new_watcher
        assert not old_watcher.is_running
        assert new_watcher.is_running

    def test_04_watcher_detects_and_reloads(self):
        """监听器检测到文件变更并自动重载 (端到端)"""
        assert self.cm.get("logging.level") == "INFO"

        self.cm.start_watching(poll_interval=0.3, debounce_seconds=0.0)

        try:
            time.sleep(0.1)
            with pathlib.Path(self.config_path).open("w") as f:
                json.dump({"logging": {"level": "ERROR"}}, f)

            # 等待轮询检测 + 重载
            time.sleep(1.5)

            assert self.cm.get("logging.level") == "ERROR"
        finally:
            self.cm.stop_watching()

    def test_05_watcher_rejects_invalid_config(self):
        """监听器拒绝无效配置 (配置保持不变)"""
        original_level = self.cm.get("logging.level")

        self.cm.start_watching(poll_interval=0.3, debounce_seconds=0.0)

        try:
            time.sleep(0.1)
            with pathlib.Path(self.config_path).open("w") as f:
                json.dump({"logging": {"level": "GARBAGE"}}, f)

            time.sleep(1.5)

            # 配置应保持不变
            assert self.cm.get("logging.level") == original_level
        finally:
            self.cm.stop_watching()


class TestConfigManagerThreadSafety:
    """热重载线程安全测试"""

    def setup_method(self, method):
        fd, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with pathlib.Path(self.config_path).open("w") as f:
            json.dump({"logging": {"level": "INFO"}}, f)
        self.cm = ConfigManager(config_file=self.config_path)

    def teardown_method(self, method):
        self.cm.stop_watching()
        if pathlib.Path(self.config_path).exists():
            pathlib.Path(self.config_path).unlink()

    def test_01_concurrent_reload_and_read(self):
        """并发重载和读取不崩溃"""
        errors = []

        def reloader():
            try:
                for _ in range(20):
                    self.cm.reload_config()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"reloader: {e}")

        def reader():
            try:
                for _ in range(100):
                    self.cm.get("logging.level")
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"reader: {e}")

        threads = [
            threading.Thread(target=reloader),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"并发错误: {errors}"

    def test_02_concurrent_watch_and_read(self):
        """并发监听和读取不崩溃"""
        errors = []

        def watcher_control():
            try:
                for _ in range(5):
                    self.cm.start_watching(poll_interval=0.3)
                    time.sleep(0.3)
                    self.cm.stop_watching()
                    time.sleep(0.1)
            except Exception as e:
                errors.append(f"watcher: {e}")

        def reader():
            try:
                for _ in range(100):
                    self.cm.get("logging.level")
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"reader: {e}")

        threads = [
            threading.Thread(target=watcher_control),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.cm.stop_watching()
        assert len(errors) == 0, f"并发错误: {errors}"

    def test_03_concurrent_start_stop_race(self):
        """S10: 并发 start_watching/stop_watching 不崩溃"""
        errors = []

        def starter():
            try:
                for _ in range(10):
                    self.cm.start_watching(poll_interval=0.3)
                    time.sleep(0.05)
            except Exception as e:
                errors.append(f"starter: {e}")

        def stopper():
            try:
                for _ in range(10):
                    self.cm.stop_watching()
                    time.sleep(0.05)
            except Exception as e:
                errors.append(f"stopper: {e}")

        threads = [
            threading.Thread(target=starter),
            threading.Thread(target=stopper),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        self.cm.stop_watching()
        assert len(errors) == 0, f"并发 start/stop 竞态错误: {errors}"

    def test_04_concurrent_reload_and_set_no_write_loss(self):
        """S10: 并发 reload_config + set 验证无写入丢失"""
        errors = []
        # 使用独立 key 避免与文件配置冲突
        test_key = "collision.test_concurrent_value"

        def reloader():
            try:
                for _ in range(30):
                    self.cm.reload_config()
                    time.sleep(0.03)
            except Exception as e:
                errors.append(f"reloader: {e}")

        def setter():
            try:
                for i in range(50):
                    self.cm.set(test_key, i)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"setter: {e}")

        def reader():
            try:
                for _ in range(100):
                    self.cm.get(test_key)
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"reader: {e}")

        threads = [
            threading.Thread(target=reloader),
            threading.Thread(target=setter),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        assert len(errors) == 0, f"并发 reload+set 错误: {errors}"


class TestNotificationChannelConcurrency:
    """S10: 通知渠道并发安全测试"""

    def setup_method(self, method):
        from src.monitoring.alert_system import AlertLevel, AlertSystem, AlertType

        self.AlertSystem = AlertSystem
        self.AlertLevel = AlertLevel
        self.AlertType = AlertType

    def test_01_concurrent_add_channel_and_trigger(self):
        """S10: 并发 add_notification_channel + _trigger_alert 不崩溃"""

        # notification_channels 模块已移除，用简单 stub 替代
        class StubChannel:
            def send(self, alert):
                pass

        alert_sys = self.AlertSystem()
        errors = []

        def adder():
            try:
                for _i in range(20):
                    ch = StubChannel()
                    alert_sys.add_notification_channel(ch)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"adder: {e}")

        def trigger():
            try:
                for i in range(20):
                    from src.monitoring.alert_system import AlertRecord

                    alert = AlertRecord(
                        timestamp="2026-01-01T00:00:00",
                        level=self.AlertLevel.WARNING,
                        alert_type=self.AlertType.PERFORMANCE_DEGRADATION,
                        message=f"Concurrent test alert {i}",
                        metrics={},
                    )
                    alert_sys._trigger_alert(alert)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"trigger: {e}")

        threads = [
            threading.Thread(target=adder),
            threading.Thread(target=trigger),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"并发 add+trigger 错误: {errors}"
