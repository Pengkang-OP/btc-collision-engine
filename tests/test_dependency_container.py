#!/usr/bin/env python3
"""依赖注入容器 (DependencyContainer) 单元测试

覆盖:
- 属性延迟创建 (stats/event_bus/data_logger)
- 实例复用
- setter 注入与链式调用
- reset 重置
- __repr__ 字符串表示
"""

from unittest.mock import MagicMock, patch

from src.collision.dependency_container import DependencyContainer


# ============================================================================
# 初始化和属性延迟创建
# ============================================================================


class TestDependencyContainerInit:
    """测试初始化和属性延迟创建"""

    def test_initial_state(self):
        """初始化后 _stats/_event_bus/_data_logger 均为 None"""
        container = DependencyContainer()
        assert container._stats is None
        assert container._event_bus is None
        assert container._data_logger is None

    def test_stats_lazy_creation(self):
        """首次访问 stats 触发 CollisionStats 延迟创建

        注意: patch 路径为 src.collision.collision_stats.CollisionStats，
        因为属性 getter 内部通过 from .collision_stats import CollisionStats
        惰性导入。若未来重构为模块级导入，需改为
        src.collision.dependency_container.CollisionStats。
        """
        with patch(
            "src.collision.collision_stats.CollisionStats"
        ) as mock_cs:
            mock_instance = MagicMock()
            mock_cs.return_value = mock_instance
            container = DependencyContainer()
            result = container.stats
            assert result is mock_instance
            mock_cs.assert_called_once()

    def test_event_bus_lazy_creation(self):
        """首次访问 event_bus 触发 EventBus 延迟创建

        注意: patch 路径依赖于属性 getter 内部的惰性导入
        (from .event_bus import EventBus)。
        """
        with patch("src.collision.event_bus.EventBus") as mock_eb:
            mock_instance = MagicMock()
            mock_eb.return_value = mock_instance
            container = DependencyContainer()
            result = container.event_bus
            assert result is mock_instance
            mock_eb.assert_called_once()

    def test_data_logger_lazy_creation(self):
        """首次访问 data_logger 触发 DataLogger 延迟创建

        注意: patch 路径依赖于属性 getter 内部的惰性导入
        (from ..monitoring.data_logger import DataLogger)。
        """
        with patch(
            "src.monitoring.data_logger.DataLogger"
        ) as mock_dl:
            mock_instance = MagicMock()
            mock_dl.return_value = mock_instance
            container = DependencyContainer()
            result = container.data_logger
            assert result is mock_instance
            mock_dl.assert_called_once()

    def test_stats_reuses_instance(self):
        """多次访问 stats 返回同一实例"""
        with patch(
            "src.collision.collision_stats.CollisionStats"
        ) as mock_cs:
            mock_instance = MagicMock()
            mock_cs.return_value = mock_instance
            container = DependencyContainer()
            first = container.stats
            second = container.stats
            assert first is second
            mock_cs.assert_called_once()

    def test_event_bus_reuses_instance(self):
        """多次访问 event_bus 返回同一实例"""
        with patch("src.collision.event_bus.EventBus") as mock_eb:
            mock_instance = MagicMock()
            mock_eb.return_value = mock_instance
            container = DependencyContainer()
            first = container.event_bus
            second = container.event_bus
            assert first is second
            mock_eb.assert_called_once()

    def test_data_logger_reuses_instance(self):
        """多次访问 data_logger 返回同一实例"""
        with patch(
            "src.monitoring.data_logger.DataLogger"
        ) as mock_dl:
            mock_instance = MagicMock()
            mock_dl.return_value = mock_instance
            container = DependencyContainer()
            first = container.data_logger
            second = container.data_logger
            assert first is second
            mock_dl.assert_called_once()


# ============================================================================
# 注入方法
# ============================================================================


class TestDependencyContainerInjection:
    """测试依赖注入方法"""

    def test_set_stats_replaces_lazy(self):
        """set_stats 注入后 stats 属性返回注入值而非延迟创建"""
        container = DependencyContainer()
        mock_stats = MagicMock()
        container.set_stats(mock_stats)
        # 注入后访问 stats 不应触发 CollisionStats 惰性创建
        with patch(
            "src.collision.collision_stats.CollisionStats"
        ) as mock_cs:
            assert container.stats is mock_stats
            assert container._stats is mock_stats
            mock_cs.assert_not_called()

    def test_set_event_bus_replaces_lazy(self):
        """set_event_bus 注入后 event_bus 属性返回注入值"""
        container = DependencyContainer()
        mock_eb = MagicMock()
        container.set_event_bus(mock_eb)
        # 注入后访问 event_bus 不应触发 EventBus 惰性创建
        with patch("src.collision.event_bus.EventBus") as mock_eb_cls:
            assert container.event_bus is mock_eb
            assert container._event_bus is mock_eb
            mock_eb_cls.assert_not_called()

    def test_set_data_logger_replaces_lazy(self):
        """set_data_logger 注入后 data_logger 属性返回注入值"""
        container = DependencyContainer()
        mock_dl = MagicMock()
        container.set_data_logger(mock_dl)
        # 注入后访问 data_logger 不应触发 DataLogger 惰性创建
        with patch(
            "src.monitoring.data_logger.DataLogger"
        ) as mock_dl_cls:
            assert container.data_logger is mock_dl
            assert container._data_logger is mock_dl
            mock_dl_cls.assert_not_called()

    def test_chainable_setters(self):
        """setter 方法支持链式调用"""
        container = DependencyContainer()
        mock_stats = MagicMock()
        mock_eb = MagicMock()
        mock_dl = MagicMock()
        result = container.set_stats(mock_stats).set_event_bus(
            mock_eb
        ).set_data_logger(mock_dl)
        assert result is container
        assert container.stats is mock_stats
        assert container.event_bus is mock_eb
        assert container.data_logger is mock_dl

    def test_reset_clears_all(self):
        """reset() 将所有依赖恢复为 None，之后属性重新延迟创建"""
        container = DependencyContainer()
        mock_stats = MagicMock()
        mock_eb = MagicMock()
        mock_dl = MagicMock()
        container.set_stats(mock_stats)
        container.set_event_bus(mock_eb)
        container.set_data_logger(mock_dl)

        container.reset()

        assert container._stats is None
        assert container._event_bus is None
        assert container._data_logger is None

        # reset 后访问属性应重新触发延迟创建
        with patch(
            "src.collision.collision_stats.CollisionStats"
        ) as mock_cs:
            new_stats = MagicMock()
            mock_cs.return_value = new_stats
            result = container.stats
            assert result is new_stats
            assert result is not mock_stats

        with patch("src.collision.event_bus.EventBus") as mock_eb_cls:
            new_eb = MagicMock()
            mock_eb_cls.return_value = new_eb
            result = container.event_bus
            assert result is new_eb
            assert result is not mock_eb

        with patch(
            "src.monitoring.data_logger.DataLogger"
        ) as mock_dl_cls:
            new_dl = MagicMock()
            mock_dl_cls.return_value = new_dl
            result = container.data_logger
            assert result is new_dl
            assert result is not mock_dl


# ============================================================================
# __repr__ 字符串表示
# ============================================================================


class TestDependencyContainerRepr:
    """测试 __repr__ 字符串表示"""

    def test_repr_all_lazy(self):
        """全部未注入时 repr 显示 'lazy'"""
        container = DependencyContainer()
        r = repr(container)
        assert "lazy" in r
        assert "set" not in r

    def test_repr_partial_set(self):
        """部分注入时 repr 正确显示 set/lazy 混合"""
        container = DependencyContainer()
        container.set_stats(MagicMock())
        r = repr(container)
        assert "stats=set" in r
        assert "event_bus=lazy" in r
        assert "data_logger=lazy" in r

    def test_repr_all_set(self):
        """全部注入时 repr 全部显示 'set'"""
        container = DependencyContainer()
        container.set_stats(MagicMock())
        container.set_event_bus(MagicMock())
        container.set_data_logger(MagicMock())
        r = repr(container)
        assert "stats=set" in r
        assert "event_bus=set" in r
        assert "data_logger=set" in r
        assert "lazy" not in r
