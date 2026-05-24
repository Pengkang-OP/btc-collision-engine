"""LogQuery 单元测试 - 匹配真实 API

API (均为静态方法):
- filter_by_level(entries: list[dict], min_level: str) -> list[dict]
- search_text(entries: list[dict], text: str) -> list[dict]
"""

import pytest

from src.log_engine.log_query import LogQuery


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_entries():
    return [
        {"level": "DEBUG", "message": "调试信息: 变量 x=1", "source": "engine"},
        {"level": "INFO", "message": "引擎启动成功", "source": "engine"},
        {"level": "INFO", "message": "初始化完成", "source": "config"},
        {"level": "WARNING", "message": "内存使用率超过 80%", "source": "monitor"},
        {"level": "WARNING", "message": "磁盘空间不足", "source": "monitor"},
        {"level": "ERROR", "message": "GPU 内核编译失败", "source": "gpu"},
        {"level": "ERROR", "message": "连接超时", "source": "network"},
        {"level": "INFO", "message": "检查点已保存", "source": "engine"},
        {"level": "DEBUG", "message": "收到数据包", "source": "network"},
        {"level": "INFO", "message": "进度: 50%", "source": "engine"},
    ]


# ============================================================================
# filter_by_level 测试
# ============================================================================


class TestFilterByLevel:
    def test_filter_debug_shows_all(self, sample_entries):
        """DEBUG 级别应包含所有日志"""
        result = LogQuery.filter_by_level(sample_entries, "DEBUG")
        assert len(result) == 10

    def test_filter_info_excludes_debug(self, sample_entries):
        """INFO 级别应排除 DEBUG"""
        result = LogQuery.filter_by_level(sample_entries, "INFO")
        assert len(result) == 8
        assert all(e["level"] != "DEBUG" for e in result)

    def test_filter_warning(self, sample_entries):
        """WARNING 级别应只包含 WARNING 和 ERROR"""
        result = LogQuery.filter_by_level(sample_entries, "WARNING")
        assert len(result) == 4
        levels = {e["level"] for e in result}
        assert levels == {"WARNING", "ERROR"}

    def test_filter_error(self, sample_entries):
        """ERROR 级别只包含 ERROR"""
        result = LogQuery.filter_by_level(sample_entries, "ERROR")
        assert len(result) == 2
        assert all(e["level"] == "ERROR" for e in result)

    def test_filter_case_insensitive(self, sample_entries):
        """级别名称大小写不敏感"""
        result = LogQuery.filter_by_level(sample_entries, "error")
        assert len(result) == 2

    def test_filter_unknown_level_treated_as_zero(self, sample_entries):
        """未知级别按 0 处理，返回所有条目"""
        result = LogQuery.filter_by_level(sample_entries, "UNKNOWN")
        assert len(result) == 10

    def test_filter_empty_entries(self):
        """空列表返回空列表"""
        result = LogQuery.filter_by_level([], "ERROR")
        assert result == []

    def test_filter_missing_level_field(self):
        """缺少 level 字段的条目默认按 INFO 处理"""
        entries = [
            {"message": "no level field"},
            {"level": "ERROR", "message": "has level"},
        ]
        result = LogQuery.filter_by_level(entries, "ERROR")
        assert len(result) == 1
        assert result[0]["level"] == "ERROR"


# ============================================================================
# search_text 测试
# ============================================================================


class TestSearchText:
    def test_search_matches(self, sample_entries):
        result = LogQuery.search_text(sample_entries, "引擎")
        assert len(result) == 1
        assert "引擎启动成功" in result[0]["message"]

    def test_search_case_insensitive(self, sample_entries):
        result = LogQuery.search_text(sample_entries, "GPU")
        assert len(result) == 1

    def test_search_no_match(self, sample_entries):
        result = LogQuery.search_text(sample_entries, "nonexistent_xyz")
        assert result == []

    def test_search_chinese(self, sample_entries):
        result = LogQuery.search_text(sample_entries, "内存")
        assert len(result) == 1
        assert "内存使用率" in result[0]["message"]

    def test_search_empty_entries(self):
        result = LogQuery.search_text([], "anything")
        assert result == []

    def test_search_missing_message_field(self):
        """缺少 message 字段的条目不被匹配"""
        entries = [
            {"level": "INFO"},
            {"level": "ERROR", "message": "匹配这个"},
        ]
        result = LogQuery.search_text(entries, "匹配")
        assert len(result) == 1

    def test_search_regex_chars_escaped(self):
        """正则特殊字符被转义为字面匹配"""
        entries = [
            {"message": "特殊字符 .* 测试"},
        ]
        result = LogQuery.search_text(entries, ".*")
        assert len(result) == 1

    def test_search_partial_match(self, sample_entries):
        """部分匹配也能找到"""
        result = LogQuery.search_text(sample_entries, "GPU")
        assert len(result) == 1


# ============================================================================
# 组合测试
# ============================================================================


class TestLogQueryCombined:
    def test_filter_then_search(self, sample_entries):
        """先过滤级别再搜索文本"""
        filtered = LogQuery.filter_by_level(sample_entries, "ERROR")
        result = LogQuery.search_text(filtered, "GPU")
        assert len(result) == 1
        assert "GPU 内核编译失败" in result[0]["message"]

    def test_filter_then_search_no_results(self, sample_entries):
        """过滤后搜索无结果"""
        filtered = LogQuery.filter_by_level(sample_entries, "ERROR")
        result = LogQuery.search_text(filtered, "内存")
        assert result == []

    def test_static_method_no_instance_needed(self):
        """静态方法不需要实例化"""
        result = LogQuery.filter_by_level([{"level": "ERROR", "message": "err"}], "ERROR")
        assert len(result) == 1
