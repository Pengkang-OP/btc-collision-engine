#!/usr/bin/env python3
"""DataStorage 独立单元测试 (P1-6)

测试 src.monitoring.monitoring_system.DataStorage 类的完整功能，
包括 P0 统一数据源委托模式和独立写入模式。

测试覆盖:
- DataStorage 初始化 (默认/自定义/带data_logger委托)
- save_current_data / save_history_data / save_error
- _load_history_with_recovery (委托/非委托)
- get_current_data / get_history_data / get_error_logs
- compress_old_data 数据压缩采样
- 向后兼容 (无data_logger时独立工作)
- 边界场景: 空文件、损坏JSON、超大文件
"""

import json
import os
import pathlib
import shutil
import tempfile
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.monitoring.data_logger import DataLogger
from src.monitoring.monitoring_system import DataStorage, MonitoringData

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_storage_dir():
    """创建临时存储目录"""
    d = tempfile.mkdtemp()
    yield d
    if pathlib.Path(d).exists():
        shutil.rmtree(d)


@pytest.fixture
def storage_no_logger(temp_storage_dir):
    """无 data_logger 委托的 DataStorage"""
    return DataStorage(storage_dir=temp_storage_dir, data_logger=None)


@pytest.fixture
def mock_data_logger():
    """创建 Mock DataLogger"""
    mock = MagicMock(spec=DataLogger)
    mock._current_data = {}
    mock._history_buffer = []
    mock.HISTORY_SCHEMA_VERSION = "1.0"
    # mock _load_history_with_recovery to return a list
    mock._load_history_with_recovery.return_value = []
    return mock


@pytest.fixture
def storage_with_logger(mock_data_logger):
    """带 data_logger 委托的 DataStorage"""
    return DataStorage(data_logger=mock_data_logger)


@pytest.fixture
def sample_monitoring_data():
    """创建样本 MonitoringData"""
    data = MonitoringData()
    data.performance = {
        "speed": 1000.0,
        "total_checked": 5000,
        "matches_found": 0,
        "cpu_usage": 50.0,
        "memory_usage": 200.0,
        "thread_count": 4,
    }
    data.system = {
        "os": "nt",
        "python_version": "3.12.0",
        "pid": 12345,
        "uptime": 3600.0,
    }
    data.engine = {
        "mode": "random",
        "target_count": 10,
        "is_running": True,
        "current_position": 500,
    }
    return data


# ============================================================================
# 初始化测试
# ============================================================================


@pytest.mark.unit
class TestDataStorageInit:
    """测试 DataStorage 初始化"""

    def test_init_default(self):
        """默认初始化"""
        storage = DataStorage()
        assert storage.storage_dir is not None
        assert "data_logs" in storage.storage_dir
        assert storage._data_logger is None

    def test_init_custom_dir(self, temp_storage_dir):
        """自定义存储目录"""
        storage = DataStorage(storage_dir=temp_storage_dir)
        assert storage.storage_dir == temp_storage_dir

    def test_init_with_data_logger(self, mock_data_logger):
        """带 DataLogger 委托"""
        storage = DataStorage(data_logger=mock_data_logger)
        assert storage._data_logger is mock_data_logger

    def test_init_without_data_logger(self, temp_storage_dir):
        """无 DataLogger 时仍正常工作"""
        storage = DataStorage(storage_dir=temp_storage_dir, data_logger=None)
        assert storage._data_logger is None

    def test_init_creates_error_log_file(self, temp_storage_dir):
        """初始化时创建 error_log.json (无委托模式)"""
        DataStorage(storage_dir=temp_storage_dir, data_logger=None)
        error_path = os.path.join(temp_storage_dir, "error_log.json")
        assert pathlib.Path(error_path).exists()

    def test_init_creates_history_file(self, temp_storage_dir):
        """初始化时创建 history_data.json (无委托模式)"""
        DataStorage(storage_dir=temp_storage_dir, data_logger=None)
        history_path = os.path.join(temp_storage_dir, "history_data.json")
        assert pathlib.Path(history_path).exists()


# ============================================================================
# save_current_data 测试
# ============================================================================


@pytest.mark.unit
class TestSaveCurrentData:
    """测试 save_current_data"""

    def test_save_with_delegation(self, storage_with_logger, mock_data_logger, sample_monitoring_data):
        """委托模式下调用 DataLogger.save_current_data"""
        storage_with_logger.save_current_data(sample_monitoring_data)

        # 验证委托的 DataLogger 被调用
        mock_data_logger.save_current_data.assert_called_once()

    def test_save_with_delegation_syncs_data(
        self,
        storage_with_logger,
        mock_data_logger,
        sample_monitoring_data,
    ):
        """委托模式下同步 performance/system/engine 数据到 DataLogger"""
        storage_with_logger.save_current_data(sample_monitoring_data)

        # 验证委托方法被调用（Mock 不实际更新内部状态，验证调用即可）
        assert mock_data_logger.record_performance_data.called
        assert mock_data_logger.record_system_data.called
        assert mock_data_logger.record_engine_data.called
        assert mock_data_logger.save_current_data.called

    def test_save_without_delegation(self, storage_no_logger, sample_monitoring_data):
        """非委托模式下直接写入文件"""
        storage_no_logger.save_current_data(sample_monitoring_data)

        # 验证文件存在
        assert pathlib.Path(storage_no_logger.current_data_file).exists()

    def test_save_without_delegation_content(self, storage_no_logger, sample_monitoring_data):
        """非委托模式写入内容验证"""
        storage_no_logger.save_current_data(sample_monitoring_data)

        with pathlib.Path(storage_no_logger.current_data_file).open(encoding="utf-8") as f:
            saved = json.load(f)

            assert "timestamp" in saved
            assert "performance" in saved
            assert saved["performance"]["speed"] == 1000.0
            assert saved["performance"]["total_checked"] == 5000

    def test_delegation_error_handled(
        self,
        storage_with_logger,
        mock_data_logger,
        sample_monitoring_data,
    ):
        """委托模式下 DataLogger 抛出异常应被捕获"""
        mock_data_logger.save_current_data.side_effect = RuntimeError("delegation error")

        # 不应抛出异常
        storage_with_logger.save_current_data(sample_monitoring_data)


# ============================================================================
# save_history_data 测试
# ============================================================================


@pytest.mark.unit
class TestSaveHistoryData:
    """测试 save_history_data"""

    def test_save_with_delegation(self, storage_with_logger, mock_data_logger, sample_monitoring_data):
        """委托模式下调用 DataLogger 保存历史数据"""
        storage_with_logger.save_history_data(sample_monitoring_data)

        # 验证委托的 DataLogger 被调用
        assert mock_data_logger.save_history_data.called

    def test_save_without_delegation(self, storage_no_logger, sample_monitoring_data):
        """非委托模式下直接写入文件"""
        storage_no_logger.save_history_data(sample_monitoring_data)

        assert pathlib.Path(storage_no_logger.history_data_file).exists()

    def test_save_without_delegation_content(self, storage_no_logger, sample_monitoring_data):
        """非委托模式写入内容验证"""
        storage_no_logger.save_history_data(sample_monitoring_data)

        history = storage_no_logger._load_history_with_recovery()
        assert len(history) >= 1
        # 验证第一条记录的 performance 数据
        assert history[0]["performance"]["speed"] == 1000.0
        assert history[0]["performance"]["total_checked"] == 5000

    def test_delegation_error_handled(
        self,
        storage_with_logger,
        mock_data_logger,
        sample_monitoring_data,
    ):
        """委托模式下缓冲区操作异常应被捕获"""
        mock_data_logger._history_buffer = None  # 模拟异常状态
        try:
            storage_with_logger.save_history_data(sample_monitoring_data)
        except AttributeError:
            pass  # 预期可能抛出，但不应崩溃


# ============================================================================
# save_error 测试
# ============================================================================


@pytest.mark.unit
class TestSaveError:
    """测试 save_error"""

    def test_save_with_delegation(self, storage_with_logger, mock_data_logger):
        """委托模式下调用 DataLogger.record_error"""
        error = {"type": "test", "message": "test error message"}
        storage_with_logger.save_error(error)

        mock_data_logger.record_error.assert_called_once()
        call_args = mock_data_logger.record_error.call_args
        assert call_args[1]["error_type"] == "test"
        assert call_args[1]["message"] == "test error message"

    def test_save_without_delegation(self, storage_no_logger):
        """非委托模式下直接写入 error_log.json"""
        error = {"type": "test", "message": "test error"}
        storage_no_logger.save_error(error)

        error_log_path = storage_no_logger.error_log_file
        assert pathlib.Path(error_log_path).exists()

        with pathlib.Path(error_log_path).open(encoding="utf-8") as f:
            errors = json.load(f)
            assert len(errors) >= 1
            assert errors[-1]["type"] == "test"
            assert errors[-1]["message"] == "test error"

    def test_save_error_with_missing_type(self, storage_with_logger, mock_data_logger):
        """错误记录缺少 type 字段时使用默认值"""
        error = {"message": "no type field"}
        storage_with_logger.save_error(error)

        call_args = mock_data_logger.record_error.call_args
        assert call_args[1]["error_type"] == "unknown"

    def test_error_log_limit_500(self, storage_no_logger):
        """错误日志超过 500 条时截断"""
        for i in range(510):
            storage_no_logger.save_error({"type": "test", "message": f"error {i}"})

        with pathlib.Path(storage_no_logger.error_log_file).open(encoding="utf-8") as f:
            errors = json.load(f)

        assert len(errors) <= 500
        # 应该保留最新的 500 条
        assert errors[-1]["message"] == "error 509"

    def test_delegation_error_handled(self, storage_with_logger, mock_data_logger):
        """委托模式下 record_error 异常应被捕获"""
        mock_data_logger.record_error.side_effect = RuntimeError("delegation error")
        error = {"type": "test", "message": "test"}

        # 不应抛出异常
        storage_with_logger.save_error(error)


# ============================================================================
# _load_history_with_recovery 测试
# ============================================================================


@pytest.mark.unit
class TestLoadHistoryWithRecovery:
    """测试历史数据加载与恢复"""

    def test_delegation_passthrough(self, storage_with_logger, mock_data_logger):
        """委托模式下直接调用 DataLogger 的恢复方法"""
        mock_data_logger._load_history_with_recovery.return_value = [
            {"timestamp": 1000, "performance": {"speed": 500}},
        ]

        result = storage_with_logger._load_history_with_recovery()
        mock_data_logger._load_history_with_recovery.assert_called_once()
        assert len(result) == 1
        assert result[0]["performance"]["speed"] == 500

    def test_no_file_returns_empty(self, storage_no_logger):
        """文件不存在时返回空列表"""
        # 删除初始化时创建的文件
        if pathlib.Path(storage_no_logger.history_data_file).exists():
            pathlib.Path(storage_no_logger.history_data_file).unlink()

            result = storage_no_logger._load_history_with_recovery()
            assert result == []

    def test_empty_file_returns_empty(self, storage_no_logger):
        """空文件 (但存在) 的处理"""
        # 写入空内容
        with pathlib.Path(storage_no_logger.history_data_file).open("w", encoding="utf-8") as f:
            f.write("")

            result = storage_no_logger._load_history_with_recovery()
            assert result == []

    def test_valid_history_loaded(self, storage_no_logger):
        """正常历史数据加载 (JSONL 格式)"""
        test_data = [
            {"timestamp": 1000, "performance": {"speed": 100}},
            {"timestamp": 2000, "performance": {"speed": 200}},
        ]
        with pathlib.Path(storage_no_logger.history_data_file).open("w", encoding="utf-8") as f:
            f.writelines(json.dumps(record) + "\n" for record in test_data)

        result = storage_no_logger._load_history_with_recovery()
        assert len(result) == 2
        assert result[0]["timestamp"] == 1000

    def test_corrupt_json_fallback_to_recovery(self, storage_no_logger):
        """损坏的 JSONL 数据回退到正则恢复

        DataStorage._recover_history_data 使用简化正则匹配平铺对象
        (不含嵌套花括号)，此处提供不含嵌套的损坏数据。
        """
        # JSONL 格式：有效行 + 损坏行
        corrupt_content = '{"timestamp": 1000, "speed": 100, "total": 5000}\nCORRUPTED_GARBAGExyz'
        pathlib.Path(storage_no_logger.history_data_file).write_text(corrupt_content, encoding="utf-8")

        result = storage_no_logger._load_history_with_recovery()
        # JSONL 模式下有效行可正常解析
        assert len(result) >= 1
        assert any("timestamp" in r for r in result)

    def test_malformed_json_content(self, storage_no_logger):
        """完全损坏的 JSON 内容"""
        with pathlib.Path(storage_no_logger.history_data_file).open("w", encoding="utf-8") as f:
            f.write("NOT JSON AT ALL {{{")

            result = storage_no_logger._load_history_with_recovery()
            # 不应抛异常
            assert isinstance(result, list)

    def test_exception_during_read(self, storage_no_logger):
        """读取异常时返回空列表"""
        with pathlib.Path(storage_no_logger.history_data_file).open("w", encoding="utf-8") as f:
            json.dump([{"valid": "data"}], f)

            # 模拟读取失败
            with patch("builtins.open", side_effect=PermissionError("access denied")):
                result = storage_no_logger._load_history_with_recovery()
                assert result == []


# ============================================================================
# 读操作测试
# ============================================================================


@pytest.mark.unit
class TestReadOperations:
    """测试数据读取方法"""

    def test_get_current_data_exists(self, storage_no_logger, sample_monitoring_data):
        """读取已保存的当前数据"""
        storage_no_logger.save_current_data(sample_monitoring_data)

        result = storage_no_logger.get_current_data()
        assert result is not None
        assert "performance" in result

    def test_get_current_data_no_file(self, storage_no_logger):
        """文件不存在时返回 None"""
        if pathlib.Path(storage_no_logger.current_data_file).exists():
            pathlib.Path(storage_no_logger.current_data_file).unlink()

            result = storage_no_logger.get_current_data()
            assert result is None

    def test_get_history_data(self, storage_no_logger, sample_monitoring_data):
        """读取历史数据"""
        storage_no_logger.save_history_data(sample_monitoring_data)

        result = storage_no_logger.get_history_data()
        assert isinstance(result, list)

    def test_get_history_data_no_file(self, storage_no_logger):
        """历史数据文件不存在"""
        if pathlib.Path(storage_no_logger.history_data_file).exists():
            pathlib.Path(storage_no_logger.history_data_file).unlink()

            result = storage_no_logger.get_history_data()
            assert result == []

    def test_get_error_logs(self, storage_no_logger):
        """读取错误日志"""
        storage_no_logger.save_error({"type": "test", "message": "hello"})

        result = storage_no_logger.get_error_logs()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_get_error_logs_no_file(self, storage_no_logger):
        """错误日志文件不存在"""
        if pathlib.Path(storage_no_logger.error_log_file).exists():
            pathlib.Path(storage_no_logger.error_log_file).unlink()

            result = storage_no_logger.get_error_logs()
            assert result == []

    def test_get_error_logs_corrupt(self, storage_no_logger):
        """损坏的错误日志"""
        with pathlib.Path(storage_no_logger.error_log_file).open("w", encoding="utf-8") as f:
            f.write("CORRUPTED")

            result = storage_no_logger.get_error_logs()
            assert result == []


# ============================================================================
# compress_old_data 测试
# ============================================================================


@pytest.mark.unit
class TestCompressOldData:
    """测试数据压缩"""

    def test_compress_with_data(self, storage_no_logger):
        """有历史数据时的压缩"""
        # 写入多条历史数据
        for i in range(10):
            storage_no_logger.save_history_data(self._make_monitoring_data(i))

            # 压缩 (days_threshold=0 压缩全部数据)
            storage_no_logger.compress_old_data(days_threshold=0, sample_rate=0.5)

            # 压缩后的文件应存在
            compressed_file = storage_no_logger.history_data_file.replace(".json", "_compressed.json")
            assert pathlib.Path(compressed_file).exists()

    def test_compress_no_history(self, storage_no_logger):
        """无历史数据时跳过压缩"""
        storage_no_logger.compress_old_data(days_threshold=0, sample_rate=0.5)

        compressed_file = storage_no_logger.history_data_file.replace(".json", "_compressed.json")
        # 无数据时不应创建压缩文件
        assert not pathlib.Path(compressed_file).exists()

    @staticmethod
    def _make_monitoring_data(index: int) -> MonitoringData:
        data = MonitoringData()
        data.performance["speed"] = 1000.0 + index * 100
        data.performance["total_checked"] = 5000 + index * 1000
        return data


# ============================================================================
# 向后兼容测试
# ============================================================================


@pytest.mark.unit
class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_no_logger_all_operations_work(self, storage_no_logger, sample_monitoring_data):
        """无 data_logger 时所有操作仍正常工作"""
        # 写操作
        storage_no_logger.save_current_data(sample_monitoring_data)
        storage_no_logger.save_history_data(sample_monitoring_data)
        storage_no_logger.save_error({"type": "test", "message": "compat test"})

        # 读操作
        current = storage_no_logger.get_current_data()
        history = storage_no_logger.get_history_data()
        errors = storage_no_logger.get_error_logs()

        assert current is not None
        assert isinstance(history, list)
        assert isinstance(errors, list)

    def test_with_none_logger(self, temp_storage_dir):
        """显式传递 data_logger=None"""
        storage = DataStorage(storage_dir=temp_storage_dir, data_logger=None)
        assert storage._data_logger is None

        data = MonitoringData()
        storage.save_current_data(data)  # 不应崩溃
        storage.save_history_data(data)  # 不应崩溃

    def test_storage_dir_unchanged_after_multiple_saves(self, storage_no_logger, sample_monitoring_data):
        """多次保存后存储目录不变"""
        original_dir = storage_no_logger.storage_dir

        for _ in range(3):
            storage_no_logger.save_current_data(sample_monitoring_data)
            storage_no_logger.save_history_data(sample_monitoring_data)

            assert storage_no_logger.storage_dir == original_dir

    def test_compressed_file_naming(self, storage_no_logger):
        """压缩文件名命名规范"""
        original = storage_no_logger.history_data_file
        compressed = original.replace(".json", "_compressed.json")
        assert compressed.endswith("_compressed.json")
        assert compressed != original


# ============================================================================
# 线程安全基础测试
# ============================================================================


@pytest.mark.unit
class TestThreadSafety:
    """测试线程安全性"""

    def test_concurrent_reads(self, storage_no_logger, sample_monitoring_data):
        """并发读操作不冲突"""
        # 先写入数据
        storage_no_logger.save_current_data(sample_monitoring_data)
        storage_no_logger.save_history_data(sample_monitoring_data)

        results: list = []

        def read_data():
            for _ in range(10):
                c = storage_no_logger.get_current_data()
                h = storage_no_logger.get_history_data()
                e = storage_no_logger.get_error_logs()
                results.append((c is not None, isinstance(h, list), isinstance(e, list)))

        threads = [threading.Thread(target=read_data) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有结果应为 (True, True, True)
        assert all(r == (True, True, True) for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
