#!/usr/bin/env python3
"""日志查询器 (LogQuery) 单元测试

覆盖：
- 查询过滤 (event_type/source/time/keyword)
- 时间范围查询
- 类型统计
- 自定义过滤
- 空文件/不存在文件处理
"""

import os
import json
import tempfile
import pytest
from datetime import datetime, timezone

from src.logging.log_query import LogQuery

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_log_file():
    """创建包含测试日志数据的临时文件"""
    events = [
        {
            "timestamp": 1000.0,
            "type": "engine_start",
            "source": "engine",
            "message": "引擎启动",
            "data": {},
        },
        {
            "timestamp": 1100.0,
            "type": "status_update",
            "source": "monitor",
            "message": "进度更新",
            "data": {"progress": 50},
        },
        {
            "timestamp": 1200.0,
            "type": "engine_error",
            "source": "gpu",
            "message": "GPU内存不足",
            "data": {},
        },
        {
            "timestamp": 1300.0,
            "type": "match_found",
            "source": "engine",
            "message": "发现匹配",
            "data": {"address": "1A1z..."},
        },
        {
            "timestamp": 1400.0,
            "type": "engine_stop",
            "source": "engine",
            "message": "引擎停止",
            "data": {},
        },
        {
            "timestamp": 1500.0,
            "type": "status_update",
            "source": "monitor",
            "message": "状态报告",
            "data": {"progress": 100},
        },
        {
            "timestamp": 1600.0,
            "type": "gpu_detected",
            "source": "gpu",
            "message": "检测到NVIDIA RTX 4090",
            "data": {},
        },
        {
            "timestamp": 1700.0,
            "type": "engine_error",
            "source": "gpu",
            "message": "内核编译失败",
            "data": {},
        },
        {
            "timestamp": 1800.0,
            "type": "status_update",
            "source": "monitor",
            "message": "最终状态",
            "data": {"final": True},
        },
        {
            "timestamp": 1900.0,
            "type": "config_loaded",
            "source": "config",
            "message": "配置加载完成",
            "data": {},
        },
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
        temp_path = f.name

    yield temp_path
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def log_query(temp_log_file):
    """创建 LogQuery 实例，使用临时日志目录"""
    log_dir = os.path.dirname(temp_log_file)
    # 重命名临时文件为 wizard.log
    wizard_path = os.path.join(log_dir, "wizard.log")
    if os.path.exists(wizard_path):
        os.remove(wizard_path)
    os.rename(temp_log_file, wizard_path)

    query = LogQuery(storage_dir=log_dir)
    yield query

    if os.path.exists(wizard_path):
        os.remove(wizard_path)


# ============================================================================
# 基础查询测试
# ============================================================================


@pytest.mark.unit
class TestLogQueryBasic:
    """基础查询测试"""

    def test_query_all(self, log_query):
        results = log_query.query()
        assert len(results) == 10

    def test_query_with_limit(self, log_query):
        results = log_query.query(limit=3)
        assert len(results) <= 3

    def test_get_recent(self, log_query):
        results = log_query.get_recent(count=5)
        assert len(results) <= 5


@pytest.mark.unit
class TestLogQueryFilterByType:
    """按类型过滤测试"""

    def test_filter_by_event_type(self, log_query):
        results = log_query.query(event_type="engine_error")
        assert len(results) == 2
        assert all(r["type"] == "engine_error" for r in results)

    def test_filter_by_source(self, log_query):
        results = log_query.query(source="gpu")
        assert len(results) == 3
        assert all(r["source"] == "gpu" for r in results)

    def test_filter_by_type_and_source(self, log_query):
        results = log_query.query(event_type="status_update", source="monitor")
        assert len(results) == 3
        assert all(r["type"] == "status_update" for r in results)
        assert all(r["source"] == "monitor" for r in results)

    def test_get_by_type(self, log_query):
        results = log_query.get_by_type("engine_error")
        assert len(results) == 2


@pytest.mark.unit
class TestLogQueryFilterByTime:
    """按时间过滤测试"""

    def test_filter_by_start_time(self, log_query):
        results = log_query.query(start_time=1500.0)
        assert len(results) > 0
        assert all(r["timestamp"] >= 1500.0 for r in results)

    def test_filter_by_end_time(self, log_query):
        results = log_query.query(end_time=1200.0)
        assert len(results) > 0
        assert all(r["timestamp"] <= 1200.0 for r in results)

    def test_filter_by_time_range(self, log_query):
        results = log_query.query(start_time=1200.0, end_time=1600.0)
        assert len(results) > 0
        assert all(1200.0 <= r["timestamp"] <= 1600.0 for r in results)

    def test_get_by_timerange(self, log_query):
        start = datetime.fromtimestamp(1000, tz=timezone.utc)
        end = datetime.fromtimestamp(2000, tz=timezone.utc)
        results = log_query.get_by_timerange(start, end)
        assert len(results) == 10

    def test_get_last_hour(self, log_query):
        results = log_query.get_last_hour()
        assert isinstance(results, list)

    def test_get_last_day(self, log_query):
        results = log_query.get_last_day()
        assert isinstance(results, list)


@pytest.mark.unit
class TestLogQueryKeyword:
    """关键词搜索测试"""

    def test_search_keyword(self, log_query):
        results = log_query.search("GPU")
        assert len(results) > 0

    def test_search_keyword_case_insensitive(self, log_query):
        results = log_query.search("gpu")
        assert len(results) > 0

    def test_query_with_keyword(self, log_query):
        results = log_query.query(keyword="内核")
        assert len(results) == 1
        assert "内核编译失败" in results[0]["message"]


@pytest.mark.unit
class TestLogQueryStatistics:
    """统计功能测试"""

    def test_count_by_type(self, log_query):
        counts = log_query.count_by_type()
        assert counts["engine_start"] == 1
        assert counts["status_update"] == 3
        assert counts["engine_error"] == 2
        assert counts["match_found"] == 1
        assert counts["engine_stop"] == 1

    def test_get_statistics(self, log_query):
        stats = log_query.get_statistics()
        assert stats["total_count"] == 10
        assert "type_counts" in stats
        assert "log_file_exists" in stats
        assert stats["log_file_exists"] is True

    def test_tail(self, log_query):
        results = log_query.tail(count=3)
        assert len(results) == 3


@pytest.mark.unit
class TestLogQueryCustomFilter:
    """自定义过滤测试"""

    def test_filter_with_predicate(self, log_query):
        # 过滤所有错误日志
        results = log_query.filter(lambda e: "error" in e.get("type", ""))
        assert len(results) == 2
        assert all("error" in r["type"] for r in results)

    def test_filter_with_complex_predicate(self, log_query):
        # 过滤 GPU 源且包含 "失败" 的日志
        results = log_query.filter(
            lambda e: e.get("source") == "gpu" and "失败" in e.get("message", "")
        )
        assert len(results) == 1


@pytest.mark.unit
@pytest.mark.edge_cases
class TestLogQueryEdgeCases:
    """边界情况测试"""

    def test_nonexistent_log_file(self):
        query = LogQuery(storage_dir="/nonexistent/path")
        results = query.query()
        assert results == []

    def test_empty_search(self, log_query):
        results = log_query.search("nonexistent_keyword_xyz")
        assert results == []

    def test_invalid_json_lines(self):
        """文件中包含无效 JSON 行应被跳过"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "wizard.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write('{"timestamp": 1000, "type": "ok", "message": "valid"}\n')
                f.write("this is not json\n")
                f.write('{"timestamp": 2000, "type": "also_ok", "message": "valid2"}\n')

            query = LogQuery(storage_dir=tmpdir)
            results = query.query()
            assert len(results) == 2
            assert results[0]["type"] == "ok"
            assert results[1]["type"] == "also_ok"
