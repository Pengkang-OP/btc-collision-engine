#!/usr/bin/env python3
"""观察者模式 (Observer) 单元测试

覆盖：
- CollisionObserver 接口
- BaseCollisionObserver 默认实现
- MonitoringObserver 监控观察者
- LoggingObserver 日志观察者
- ObserverManager 管理器
"""

import pytest
from unittest.mock import Mock

from src.collision.observers import (
    CollisionObserver,
    BaseCollisionObserver,
    MonitoringObserver,
    LoggingObserver,
    ObserverManager,
)
from src.collision.collision_stats import CollisionStats

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def stats():
    """创建测试用的 CollisionStats"""
    s = CollisionStats()
    s.start_time = 1000.0
    s.total_checked = 50000
    s.speed = 10000.0
    s.elapsed = 5.0
    return s


@pytest.fixture
def mock_monitoring_system():
    """Mock 监控系统"""
    ms = Mock()
    ms.data_logger = Mock()
    ms.data_logger.record_error = Mock()
    return ms


@pytest.fixture
def mock_logger():
    """Mock logger"""
    return Mock()


# ============================================================================
# CollisionObserver 接口测试
# ============================================================================


@pytest.mark.unit
class TestCollisionObserverInterface:
    """观察者接口测试"""

    def test_base_observer_is_abstract(self):
        """直接实例化 CollisionObserver 应抛 TypeError"""
        with pytest.raises(TypeError):
            CollisionObserver()  # type: ignore[abstract]

    def test_base_observer_concrete(self):
        """BaseCollisionObserver 可实例化（有默认实现）"""
        observer = BaseCollisionObserver()
        assert isinstance(observer, CollisionObserver)


@pytest.mark.unit
class TestBaseCollisionObserver:
    """BaseCollisionObserver 测试"""

    def test_default_on_progress(self, stats):
        observer = BaseCollisionObserver()
        observer.on_progress(stats)  # 不应抛异常

    def test_default_on_match(self):
        observer = BaseCollisionObserver()
        observer.on_match(b"\x01" * 32, "1Address", "WIF_string")  # 不应抛异常

    def test_default_on_complete(self, stats):
        observer = BaseCollisionObserver()
        observer.on_complete(stats)  # 不应抛异常

    def test_default_on_error(self):
        observer = BaseCollisionObserver()
        observer.on_error(RuntimeError("test"), {"context": "data"})  # 不应抛异常

    def test_can_override_methods(self):
        """子类可选择性覆盖方法"""

        class PartialObserver(BaseCollisionObserver):
            def on_progress(self, stats):
                self.last_progress = stats

        observer = PartialObserver()
        observer.on_progress(CollisionStats())
        assert hasattr(observer, "last_progress")
        # 其他方法不应抛异常
        observer.on_match(b"key", "addr", "wif")
        observer.on_complete(CollisionStats())
        observer.on_error(Exception("test"))


# ============================================================================
# MonitoringObserver 测试
# ============================================================================


@pytest.mark.unit
class TestMonitoringObserver:
    """MonitoringObserver 测试"""

    def test_on_progress(self, stats, mock_monitoring_system):
        observer = MonitoringObserver(mock_monitoring_system)
        observer.on_progress(stats)  # 不应抛异常

    def test_on_match(self, mock_monitoring_system):
        observer = MonitoringObserver(mock_monitoring_system)
        observer.on_match(
            b"\x01" * 32,
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU72sVhvfoj",
        )
        mock_monitoring_system.data_logger.record_error.assert_called_once()
        call_kwargs = mock_monitoring_system.data_logger.record_error.call_args[1]
        assert call_kwargs["error_type"] == "MatchFound"
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in call_kwargs["error_message"]

    def test_on_error(self, mock_monitoring_system):
        observer = MonitoringObserver(mock_monitoring_system)
        error = ValueError("invalid key")
        observer.on_error(error, {"key_id": 42})

        mock_monitoring_system.data_logger.record_error.assert_called_once()
        call_kwargs = mock_monitoring_system.data_logger.record_error.call_args[1]
        assert call_kwargs["error_type"] == "ValueError"
        assert call_kwargs["error_message"] == "invalid key"
        assert call_kwargs["context"] == {"key_id": 42}

    def test_no_data_logger_does_not_crash(self, stats):
        """没有 data_logger 时不崩溃"""
        ms = Mock(spec=[])  # 没有 data_logger
        observer = MonitoringObserver(ms)
        observer.on_progress(stats)
        observer.on_match(b"key", "addr", "wif")
        observer.on_error(Exception("test"))


# ============================================================================
# LoggingObserver 测试
# ============================================================================


@pytest.mark.unit
class TestLoggingObserver:
    """LoggingObserver 测试"""

    def test_on_progress_sample_rate(self, mock_logger, stats):
        """进度日志应采样记录（每10000次）"""
        observer = LoggingObserver(mock_logger)

        # 第 9999 次不记录
        stats.total_checked = 9999
        observer.on_progress(stats)
        mock_logger.info.assert_not_called()

        # 第 10000 次记录
        stats.total_checked = 10000
        observer.on_progress(stats)
        mock_logger.info.assert_called_once()

    def test_on_match(self, mock_logger):
        observer = LoggingObserver(mock_logger)
        observer.on_match(b"\x01" * 32, "1Target", "WIF12345...")
        mock_logger.warning.assert_called_once()
        call_msg = mock_logger.warning.call_args[0][0]
        assert "1Target" in call_msg

    def test_on_complete(self, mock_logger, stats):
        observer = LoggingObserver(mock_logger)
        stats.total_checked = 1000000
        observer.on_complete(stats)
        mock_logger.info.assert_called_once()


# ============================================================================
# ObserverManager 测试
# ============================================================================


@pytest.mark.unit
class TestObserverManager:
    """ObserverManager 测试"""

    def test_add_observer(self):
        manager = ObserverManager()
        observer = BaseCollisionObserver()
        manager.add_observer(observer)
        assert manager.observer_count == 1

    def test_add_invalid_observer(self):
        manager = ObserverManager()
        with pytest.raises(TypeError, match="CollisionObserver"):
            manager.add_observer("not an observer")  # type: ignore[arg-type]

    def test_remove_observer(self):
        manager = ObserverManager()
        observer = BaseCollisionObserver()
        manager.add_observer(observer)
        assert manager.remove_observer(observer) is True
        assert manager.observer_count == 0

    def test_remove_nonexistent_observer(self):
        manager = ObserverManager()
        observer = BaseCollisionObserver()
        assert manager.remove_observer(observer) is False

    def test_notify_progress(self, stats):
        manager = ObserverManager()
        o1 = Mock(spec=BaseCollisionObserver)
        o2 = Mock(spec=BaseCollisionObserver)
        manager.add_observer(o1)
        manager.add_observer(o2)

        manager.notify_progress(stats)
        o1.on_progress.assert_called_once_with(stats)
        o2.on_progress.assert_called_once_with(stats)

    def test_notify_match(self):
        manager = ObserverManager()
        o1 = Mock(spec=BaseCollisionObserver)
        manager.add_observer(o1)

        manager.notify_match(b"key", "addr", "wif")
        o1.on_match.assert_called_once_with(b"key", "addr", "wif")

    def test_notify_complete(self, stats):
        manager = ObserverManager()
        o1 = Mock(spec=BaseCollisionObserver)
        manager.add_observer(o1)

        manager.notify_complete(stats)
        o1.on_complete.assert_called_once_with(stats)

    def test_notify_error(self):
        manager = ObserverManager()
        o1 = Mock(spec=BaseCollisionObserver)
        manager.add_observer(o1)

        error = RuntimeError("test")
        manager.notify_error(error, {"detail": "ctx"})
        o1.on_error.assert_called_once_with(error, {"detail": "ctx"})

    def test_observer_exception_does_not_block_others(self, stats):
        """一个观察者异常不影响其他观察者"""
        manager = ObserverManager()
        bad = Mock(spec=BaseCollisionObserver)
        bad.on_progress = Mock(side_effect=RuntimeError("observer crash"))
        good = Mock(spec=BaseCollisionObserver)
        manager.add_observer(bad)
        manager.add_observer(good)

        manager.notify_progress(stats)
        # good 应仍然被调用
        good.on_progress.assert_called_once_with(stats)

    def test_clear(self):
        manager = ObserverManager()
        manager.add_observer(BaseCollisionObserver())
        manager.add_observer(BaseCollisionObserver())
        assert manager.observer_count == 2
        manager.clear()
        assert manager.observer_count == 0
