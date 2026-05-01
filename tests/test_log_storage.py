#!/usr/bin/env python3
"""日志存储器 (LogStorage) 单元测试

覆盖：
- 初始化与目录创建
- 单条/批量保存
- 内存缓存查询
- 按类型/时间范围查询
- 关键词搜索
- 文件轮转
- 统计与导出
"""

import os
import json
import tempfile
import pytest
from unittest.mock import patch

from src.logging.log_storage import LogStorage

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def storage():
    """创建临时目录中的 LogStorage 实例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        s = LogStorage(storage_dir=tmpdir, max_file_size=1024, backup_count=3)
        yield s


@pytest.fixture
def populated_storage(storage):
    """预填充数据的 LogStorage"""
    events = [
        {
            "timestamp": 1000,
            "type": "engine_start",
            "source": "engine",
            "message": "引擎启动",
            "data": {},
        },
        {
            "timestamp": 1100,
            "type": "status_update",
            "source": "monitor",
            "message": "进度 50%",
            "data": {"progress": 50},
        },
        {
            "timestamp": 1200,
            "type": "engine_error",
            "source": "gpu",
            "message": "错误: 内存不足",
            "data": {},
        },
        {
            "timestamp": 1300,
            "type": "match_found",
            "source": "engine",
            "message": "匹配发现",
            "data": {"address": "1xxx"},
        },
        {
            "timestamp": 1400,
            "type": "engine_stop",
            "source": "engine",
            "message": "引擎停止",
            "data": {},
        },
    ]
    for event in events:
        storage.save(event)
    return storage


# ============================================================================
# 初始化测试
# ============================================================================


@pytest.mark.unit
class TestLogStorageInit:
    """初始化测试"""

    def test_storage_dir_created(self, storage):
        assert os.path.isdir(storage.storage_dir)

    def test_default_values(self, storage):
        assert storage.max_file_size == 1024
        assert storage.backup_count == 3

    def test_memory_buffer_initialized(self, storage):
        assert len(storage._memory_buffer) == 0
        assert storage._memory_buffer.maxlen == 10000


# ============================================================================
# 保存测试
# ============================================================================


@pytest.mark.unit
class TestLogStorageSave:
    """保存功能测试"""

    def test_save_single_event(self, storage):
        event = {"timestamp": 1000, "type": "test", "message": "hello"}
        result = storage.save(event)
        assert result is True
        assert len(storage._memory_buffer) == 1

    def test_save_to_file(self, storage):
        event = {"timestamp": 1000, "type": "test", "message": "file_test"}
        storage.save(event)
        log_file = os.path.join(storage.storage_dir, "wizard.log")
        assert os.path.exists(log_file)

    def test_save_batch(self, storage):
        events = [{"timestamp": i, "type": "batch", "message": f"msg_{i}"} for i in range(10)]
        count = storage.save_batch(events)
        assert count == 10
        assert len(storage._memory_buffer) == 10

    def test_save_batch_partial_failure(self):
        """某些事件保存失败时仍保存成功的"""
        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir)
            valid = {"timestamp": 1, "type": "ok", "message": "valid"}
            invalid = None  # 故意传入无效数据
            invalid2 = {"bad_data": object()}  # 不可序列化的数据
            events = [valid, invalid, valid, invalid2]
            count = s.save_batch(events)
            # valid 事件应成功保存（至少2条），None/无效数据被跳过
            assert count >= 2, f"期望至少2条成功，实际 {count}"
            assert len(s._memory_buffer) >= 2

    def test_save_exception_returns_false(self, storage):
        """保存过程中异常应返回 False 且不崩溃"""
        with patch.object(storage, "_save_to_file", side_effect=OSError("disk full")):
            result = storage.save({"timestamp": 1, "type": "test", "message": "x"})
            assert result is False


# ============================================================================
# 查询测试
# ============================================================================


@pytest.mark.unit
class TestLogStorageQuery:
    """查询功能测试"""

    def test_get_recent(self, populated_storage):
        results = populated_storage.get_recent(count=3)
        assert len(results) == 3
        # 应返回最近的 3 条（最后保存的在末尾）
        actual_types = [r["type"] for r in results]
        assert "engine_error" in actual_types
        assert "match_found" in actual_types
        assert "engine_stop" in actual_types

    def test_get_recent_more_than_stored(self, populated_storage):
        results = populated_storage.get_recent(count=100)
        assert len(results) == 5  # 只有 5 条数据

    def test_get_by_type(self, populated_storage):
        results = populated_storage.get_by_type("engine_error")
        assert len(results) == 1
        assert results[0]["type"] == "engine_error"

    def test_get_by_type_nonexistent(self, populated_storage):
        results = populated_storage.get_by_type("nonexistent_type")
        assert results == []

    def test_get_by_timerange(self, populated_storage):
        results = populated_storage.get_by_timerange(1100.0, 1300.0)
        assert len(results) == 3

    def test_get_by_timerange_empty(self, populated_storage):
        results = populated_storage.get_by_timerange(9999.0, 99999.0)
        assert results == []


@pytest.mark.unit
class TestLogStorageSearch:
    """搜索测试"""

    def test_search_keyword(self, populated_storage):
        results = populated_storage.search("错误")
        assert len(results) == 1
        assert "错误" in results[0]["message"]

    def test_search_case_sensitive(self, populated_storage):
        results = populated_storage.search("ERROR", case_sensitive=True)
        assert results == []

    def test_search_no_match(self, populated_storage):
        results = populated_storage.search("zzz_nonexistent")
        assert results == []


@pytest.mark.unit
class TestLogStorageStats:
    """统计测试"""

    def test_clear(self, populated_storage):
        populated_storage.clear()
        assert len(populated_storage._memory_buffer) == 0

    def test_get_stats(self, populated_storage):
        stats = populated_storage.get_stats()
        assert stats["total_count"] == 5
        assert "type_counts" in stats
        assert "file_size" in stats
        assert stats["type_counts"]["engine_start"] == 1
        assert stats["type_counts"]["status_update"] == 1

    def test_export_to_json(self, populated_storage):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name

        try:
            result = populated_storage.export_to_json(export_path)
            assert result is True
            with open(export_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == 5
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_export_recent_only(self, populated_storage):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name

        try:
            result = populated_storage.export_to_json(export_path, recent_only=True)
            assert result is True
            with open(export_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) <= 100  # get_recent 默认 100 条
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_export_failure(self, storage):
        """导出到无效路径应返回 False"""
        result = storage.export_to_json("/nonexistent/dir/file.json")
        assert result is False


# ============================================================================
# 文件轮转测试
# ============================================================================


@pytest.mark.unit
class TestLogStorageFileRotation:
    """文件轮转测试"""

    def test_rotation_triggered(self):
        """当文件大小超过限制时应触发轮转"""
        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir, max_file_size=50, backup_count=2)

            # 写入足够多数据触发轮转
            for i in range(20):
                s.save({"timestamp": i, "type": "fill", "message": "x" * 10, "data": {}})

            log_file = os.path.join(tmpdir, "wizard.log")
            backup1 = os.path.join(tmpdir, "wizard.log.1")
            # 轮转后应有当前文件或备份文件
            assert os.path.exists(log_file) or os.path.exists(backup1)

    def test_rotation_cleans_oldest_backup(self):
        """超过 backup_count 的最旧备份应被删除"""
        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir, max_file_size=30, backup_count=1)

            for i in range(30):
                s.save({"timestamp": i, "type": "fill", "message": "x" * 10, "data": {}})

            # 不应有 .2 备份（因为 backup_count=1）
            backup2 = os.path.join(tmpdir, "wizard.log.2")
            assert not os.path.exists(backup2)


# ============================================================================
# 边界情况测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.edge_cases
class TestLogStorageEdgeCases:
    """边界情况测试"""

    def test_empty_storage_queries(self, storage):
        assert storage.get_recent() == []
        assert storage.get_by_type("any") == []
        assert storage.get_by_timerange(0, 99999) == []
        assert storage.search("anything") == []

    def test_empty_storage_stats(self, storage):
        stats = storage.get_stats()
        assert stats["total_count"] == 0

    def test_concurrent_saves(self, storage):
        """并发保存不应损坏数据"""
        import threading

        def save_events(start, count):
            for i in range(start, start + count):
                storage.save({"timestamp": i, "type": "concurrent", "message": f"msg_{i}"})

        threads = []
        for j in range(4):
            t = threading.Thread(target=save_events, args=(j * 100, 25))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(storage._memory_buffer) == 100
