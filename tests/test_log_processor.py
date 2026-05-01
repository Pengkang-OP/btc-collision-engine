#!/usr/bin/env python3
"""日志处理器 (LogProcessor) 和敏感数据过滤器 (SensitiveDataFilter) 单元测试

覆盖：
- LogProcessor 格式化/处理
- 过滤器链
- 格式化器注册
- 批量处理
- JSON/文本输出
- SensitiveDataFilter 私钥/地址脱敏
"""

import pytest
import json
from unittest.mock import Mock

from src.logging.log_processor import LogProcessor, SensitiveDataFilter
from src.logging.events import LogEvent, LogEventType

# ============================================================================
# LogProcessor 测试
# ============================================================================


@pytest.mark.unit
class TestLogProcessorFormat:
    """LogProcessor 格式化测试"""

    def test_process_basic_event(self):
        processor = LogProcessor()
        event = LogEvent(
            event_type=LogEventType.STATUS_UPDATE, data={"message": "引擎启动"}, source="test"
        )
        result = processor.process(event)
        assert result is not None
        assert result["type"] == "status_update"
        assert result["source"] == "test"
        assert "message" in result

    def test_process_with_filter_excluded(self):
        processor = LogProcessor()
        # 添加一个始终返回 False 的过滤器
        processor.add_filter(lambda e: False)

        event = LogEvent(event_type=LogEventType.STATUS_UPDATE, data={"message": "test"})
        result = processor.process(event)
        assert result is None  # 被过滤

    def test_process_with_filter_passed(self):
        processor = LogProcessor()
        processor.add_filter(lambda e: True)

        event = LogEvent(event_type=LogEventType.ENGINE_START, data={"mode": "random"})
        result = processor.process(event)
        assert result is not None
        assert result["type"] == "engine_start"

    def test_format_output_structure(self):
        processor = LogProcessor()
        event = LogEvent(
            event_type=LogEventType.ENGINE_ERROR, data={"error": "GPU OOM"}, source="gpu"
        )
        result = processor.format(event)
        assert "timestamp" in result
        assert "formatted_time" in result
        assert "type" in result
        assert "source" in result
        assert "data" in result
        assert "message" in result
        assert result["type"] == "engine_error"

    def test_build_message_with_message_key(self):
        processor = LogProcessor()
        event = LogEvent(event_type=LogEventType.STATUS_UPDATE, data={"message": "hello world"})
        result = processor.format(event)
        assert "hello world" in result["message"]

    def test_build_message_with_error_key(self):
        processor = LogProcessor()
        event = LogEvent(event_type=LogEventType.ENGINE_ERROR, data={"error": "connection refused"})
        result = processor.format(event)
        assert "connection refused" in result["message"]

    def test_build_message_with_status_key(self):
        processor = LogProcessor()
        event = LogEvent(event_type=LogEventType.STATUS_UPDATE, data={"status": "running"})
        result = processor.format(event)
        assert "running" in result["message"]

    def test_build_message_non_dict_data(self):
        processor = LogProcessor()
        event = LogEvent(event_type=LogEventType.STATUS_UPDATE, data="plain string data")
        result = processor.format(event)
        assert "plain string data" in result["message"]

    def test_format_to_json(self):
        processor = LogProcessor()
        event = LogEvent(event_type=LogEventType.ENGINE_START, data={"mode": "random"})
        json_str = processor.format_to_json(event)
        parsed = json.loads(json_str)
        assert parsed["type"] == "engine_start"
        assert parsed["data"]["mode"] == "random"

    def test_format_to_text(self):
        processor = LogProcessor()
        event = LogEvent(event_type=LogEventType.STATUS_UPDATE, data={"message": "test text"})
        text = processor.format_to_text(event)
        assert "test text" in text


@pytest.mark.unit
class TestLogProcessorBatch:
    """LogProcessor 批量处理测试"""

    def test_process_batch(self):
        processor = LogProcessor()
        events = [
            LogEvent(LogEventType.STATUS_UPDATE, {"message": "msg1"}),
            LogEvent(LogEventType.ENGINE_START, {"mode": "random"}),
            LogEvent(LogEventType.ENGINE_ERROR, {"error": "err"}),
        ]
        results = processor.process_batch(events)
        assert len(results) == 3
        assert results[0]["data"]["message"] == "msg1"
        assert results[1]["data"]["mode"] == "random"
        assert results[2]["data"]["error"] == "err"

    def test_process_batch_with_filtered(self):
        processor = LogProcessor()
        processor.add_filter(lambda e: e.event_type != LogEventType.ENGINE_ERROR)
        events = [
            LogEvent(LogEventType.STATUS_UPDATE, {"message": "ok"}),
            LogEvent(LogEventType.ENGINE_ERROR, {"error": "filtered out"}),
        ]
        results = processor.process_batch(events)
        assert len(results) == 1
        assert results[0]["data"]["message"] == "ok"


@pytest.mark.unit
class TestLogProcessorFilterManagement:
    """过滤器管理测试"""

    def test_add_remove_filter(self):
        processor = LogProcessor()
        f1 = lambda e: True
        processor.add_filter(f1)
        assert len(processor._filters) == 1
        processor.remove_filter(f1)
        assert len(processor._filters) == 0

    def test_remove_nonexistent_filter(self):
        processor = LogProcessor()
        processor.remove_filter(lambda e: True)  # 不应抛异常


@pytest.mark.unit
class TestLogProcessorFormatterManagement:
    """格式化器管理测试"""

    def test_add_remove_formatter(self):
        processor = LogProcessor()
        fmt = Mock()
        processor.add_formatter("engine_start", fmt)
        assert "engine_start" in processor._formatters
        processor.remove_formatter("engine_start")
        assert "engine_start" not in processor._formatters

    def test_formatter_applied_during_process(self):
        processor = LogProcessor()
        fmt = Mock(return_value={"custom": "formatted"})
        processor.add_formatter("status_update", fmt)

        event = LogEvent(LogEventType.STATUS_UPDATE, {"message": "test"})
        result = processor.process(event)
        fmt.assert_called_once()
        assert result == {"custom": "formatted"}


# ============================================================================
# SensitiveDataFilter 测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestSensitiveDataFilterInit:
    """SensitiveDataFilter 初始化测试"""

    def test_default_enabled(self):
        sf = SensitiveDataFilter()
        assert sf.enabled is True

    def test_disabled(self):
        sf = SensitiveDataFilter(enabled=False)
        assert sf.enabled is False


@pytest.mark.unit
@pytest.mark.security
class TestSensitiveDataFilterPrivacy:
    """SensitiveDataFilter 过滤测试"""

    def test_filter_hex_64_chars(self):
        """64字符十六进制串(私钥)应被过滤"""
        sf = SensitiveDataFilter()
        event = LogEvent(
            LogEventType.STATUS_UPDATE,
            data={"key": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"},
        )
        assert sf.filter(event) is False

    def test_filter_p2pkh_address(self):
        """P2PKH 地址应被过滤"""
        sf = SensitiveDataFilter()
        event = LogEvent(
            LogEventType.MATCH_FOUND, data={"address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        )
        assert sf.filter(event) is False

    def test_filter_p2sh_address(self):
        """P2SH 地址应被过滤"""
        sf = SensitiveDataFilter()
        event = LogEvent(
            LogEventType.MATCH_FOUND, data={"address": "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"}
        )
        assert sf.filter(event) is False

    def test_filter_bech32_address(self):
        """Bech32 地址应被过滤"""
        sf = SensitiveDataFilter()
        event = LogEvent(
            LogEventType.MATCH_FOUND, data={"address": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"}
        )
        assert sf.filter(event) is False

    def test_filter_bech32m_address(self):
        """Bech32m (Taproot) 地址应被过滤"""
        sf = SensitiveDataFilter()
        event = LogEvent(
            LogEventType.MATCH_FOUND,
            data={"address": "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2ys4tqmpyuf4v"},
        )
        assert sf.filter(event) is False

    def test_safe_data_passes(self):
        """安全数据(不含敏感信息)应通过"""
        sf = SensitiveDataFilter()
        event = LogEvent(
            LogEventType.STATUS_UPDATE, data={"message": "引擎运行正常", "speed": 500000}
        )
        assert sf.filter(event) is True

    def test_disabled_filter_allows_all(self):
        """禁用时所有数据应通过"""
        sf = SensitiveDataFilter(enabled=False)
        event = LogEvent(
            LogEventType.MATCH_FOUND, data={"address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        )
        assert sf.filter(event) is True


@pytest.mark.unit
@pytest.mark.security
class TestSensitiveDataFilterRedact:
    """SensitiveDataFilter.redact() 脱敏测试"""

    def test_redact_private_key(self):
        """脱敏 64 字符十六进制串"""
        text = "私钥: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        redacted = SensitiveDataFilter.redact(text)
        assert "***REDACTED***" in redacted
        assert "a1b2c3" not in redacted

    def test_redact_p2pkh_address(self):
        """脱敏 P2PKH 地址"""
        text = "地址: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        redacted = SensitiveDataFilter.redact(text)
        assert "[P2PKH_ADDRESS]" in redacted
        assert "1A1zP1eP5Q" not in redacted

    def test_redact_p2sh_address(self):
        """脱敏 P2SH 地址"""
        text = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        redacted = SensitiveDataFilter.redact(text)
        assert "[P2SH_ADDRESS]" in redacted

    def test_redact_bech32_address(self):
        """脱敏 Bech32 地址"""
        text = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        redacted = SensitiveDataFilter.redact(text)
        assert "[BECH32_ADDRESS]" in redacted

    def test_redact_bech32m_address(self):
        """脱敏 Bech32m 地址"""
        text = "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2ys4tqmpyuf4v"
        redacted = SensitiveDataFilter.redact(text)
        assert "[BECH32M_ADDRESS]" in redacted

    def test_redact_multiple_sensitive_items(self):
        """脱敏包含多个敏感项/地址的文本"""
        text = (
            "Found match: addr1=1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa, "
            "addr2=3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        )
        redacted = SensitiveDataFilter.redact(text)
        assert "[P2PKH_ADDRESS]" in redacted
        assert "[P2SH_ADDRESS]" in redacted

    def test_redact_no_sensitive_data(self):
        """无敏感数据的文本保持不变"""
        text = "引擎运行正常，速度 500000 keys/s"
        redacted = SensitiveDataFilter.redact(text)
        assert redacted == text
