"""Tests for monitoring system EventBus integration."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.collision.event_bus import EventBus
from src.collision.events import (
    EngineCompleteEvent,
    EngineMatchEvent,
    EngineProgressEvent,
    EngineStartEvent,
    EngineStopEvent,
)
from src.monitoring.event_adapters import DataLoggerAdapter, EnhancedMonitoringAdapter


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_enhanced_monitoring():
    monitoring = MagicMock()
    monitoring.data_logger = MagicMock()
    return monitoring


class TestEnhancedMonitoringAdapter:
    def test_init(self, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        assert adapter._monitoring is mock_enhanced_monitoring

    def test_subscribe_to(self, event_bus, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        adapter.subscribe_to(event_bus)

    def test_on_engine_start(self, event_bus, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        adapter.subscribe_to(event_bus)
        event = EngineStartEvent(mode="random", target_count=1, batch_size=1000000)
        event_bus.publish(event)

    def test_on_engine_progress(self, event_bus, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        adapter.subscribe_to(event_bus)
        event = EngineProgressEvent(
            total_checked=1000,
            speed=50000.0,
            matches_found=0,
            elapsed_time=0.02,
        )
        event_bus.publish(event)

    def test_on_engine_match(self, event_bus, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        adapter.subscribe_to(event_bus)
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1ABC",
            wif="L5EZftfw...",
            target_address="1ABC",
        )
        event_bus.publish(event)

    def test_on_engine_stop(self, event_bus, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        adapter.subscribe_to(event_bus)
        event = EngineStopEvent(reason="user_request", stats={}, total_checked=1000)
        event_bus.publish(event)

    def test_on_engine_complete(self, event_bus, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        adapter.subscribe_to(event_bus)
        event = EngineCompleteEvent(
            total_checked=1000,
            matches_found=0,
            elapsed_time=0.02,
            avg_speed=50000.0,
        )
        event_bus.publish(event)

    def test_multiple_events(self, event_bus, mock_enhanced_monitoring):
        adapter = EnhancedMonitoringAdapter(mock_enhanced_monitoring)
        adapter.subscribe_to(event_bus)
        event_bus.publish(EngineStartEvent())
        event_bus.publish(EngineProgressEvent(total_checked=500))
        event_bus.publish(EngineProgressEvent(total_checked=1000))
        event_bus.publish(EngineMatchEvent(private_key=b"\x01" * 32, address="1ABC", wif="test"))
        event_bus.publish(EngineStopEvent())
        assert mock_enhanced_monitoring.record_metric.call_count >= 2


class TestDataLoggerAdapter:
    def test_init(self):
        mock_logger = MagicMock()
        adapter = DataLoggerAdapter(mock_logger)
        assert adapter.data_logger is mock_logger

    def test_subscribe_to(self, event_bus):
        from src.monitoring.event_adapters import setup_data_logging

        mock_logger = MagicMock()
        adapter = setup_data_logging(event_bus, mock_logger)
        assert adapter.data_logger is mock_logger

    def test_on_engine_progress(self, event_bus):
        from src.monitoring.event_adapters import setup_data_logging

        mock_logger = MagicMock()
        setup_data_logging(event_bus, mock_logger)
        event = EngineProgressEvent(
            total_checked=1000,
            speed=50000.0,
            matches_found=0,
            elapsed_time=0.02,
        )
        event_bus.publish(event)
        assert mock_logger.log_progress.called

    def test_on_engine_match(self, event_bus):
        from src.monitoring.event_adapters import setup_data_logging

        mock_logger = MagicMock()
        setup_data_logging(event_bus, mock_logger)
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1ABC",
            wif="L5EZftfw...",
            target_address="1ABC",
        )
        event_bus.publish(event)
        assert mock_logger.log_match.called

    def test_on_engine_error(self, event_bus):
        from src.monitoring.event_adapters import setup_data_logging

        mock_logger = MagicMock()
        setup_data_logging(event_bus, mock_logger)
        from src.collision.events import EngineErrorEvent

        event = EngineErrorEvent(
            error_type="test_error",
            error_message="test error message",
        )
        event_bus.publish(event)
        assert mock_logger.log_error.called
