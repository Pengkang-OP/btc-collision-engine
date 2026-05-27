"""Tests for GPUResultProcessor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.collision.gpu._result_processor import GPUResultProcessor


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine._device_manager.target_list = ["1ABC", "1XYZ"]
    engine._device_manager.target_hash160s = b"\x00" * 40
    engine.dedup_filter = None
    engine.stats = MagicMock()
    engine.event_bus = MagicMock()
    engine.on_match = None
    engine._match_callback_timeout = 5.0
    return engine


class TestGPUResultProcessor:
    def test_init(self, mock_engine):
        processor = GPUResultProcessor(mock_engine)
        assert processor._engine is mock_engine

    def test_safe_invoke_match_callback_no_callback(self, mock_engine):
        mock_engine.on_match = None
        processor = GPUResultProcessor(mock_engine)
        result = processor.safe_invoke_match_callback(b"\x01" * 32, "1ABC", "L5EZftfw...")
        assert result is True

    def test_safe_invoke_match_callback_with_callback(self, mock_engine):
        callback = MagicMock(return_value=True)
        mock_engine.on_match = callback
        processor = GPUResultProcessor(mock_engine)
        result = processor.safe_invoke_match_callback(b"\x01" * 32, "1ABC", "L5EZftfw...")
        assert result is True

    def test_process_matches_empty(self, mock_engine):
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches(b"\x01" * 32, [])

    def test_process_matches_single(self, mock_engine):
        private_key = b"\x01" * 32
        private_keys = private_key * 1
        matches = [{"key_index": 0, "target_index": 0}]
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches(private_keys, matches)
        assert mock_engine.event_bus.publish.called

    def test_process_matches_dedup_filter(self, mock_engine):
        mock_engine.dedup_filter = MagicMock()
        mock_engine.dedup_filter.check_and_add.return_value = False
        private_key = b"\x01" * 32
        private_keys = private_key * 1
        matches = [{"key_index": 0, "target_index": 0}]
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches(private_keys, matches)
        assert not mock_engine.event_bus.publish.called

    def test_process_matches_out_of_bounds_key(self, mock_engine):
        private_keys = b"\x01" * 32
        matches = [{"key_index": 5, "target_index": 0}]
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches(private_keys, matches)
        assert not mock_engine.event_bus.publish.called

    def test_process_matches_out_of_bounds_target(self, mock_engine):
        private_key = b"\x01" * 32
        private_keys = private_key * 1
        matches = [{"key_index": 0, "target_index": 999}]
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches(private_keys, matches)
        assert not mock_engine.event_bus.publish.called

    def test_process_matches_prng_empty(self, mock_engine):
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches_prng(b"\x05" * 32, [])

    def test_process_matches_prng_single(self, mock_engine):
        matches = [{"key_index": 0, "target_index": 0}]
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches_prng(b"\x05" * 32, matches)
        assert mock_engine.event_bus.publish.called

    def test_process_matches_prng_invalid_key(self, mock_engine):
        matches = [{"key_index": 0, "target_index": 0}]
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches_prng(b"\x00" * 32, matches)
        assert not mock_engine.event_bus.publish.called

    def test_process_matches_prng_out_of_bounds_target(self, mock_engine):
        matches = [{"key_index": 0, "target_index": 999}]
        processor = GPUResultProcessor(mock_engine)
        processor.process_matches_prng(b"\x05" * 32, matches)
        assert not mock_engine.event_bus.publish.called
