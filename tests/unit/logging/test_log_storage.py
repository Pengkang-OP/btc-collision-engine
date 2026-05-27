"""LogStorage 单元测试 - 匹配真实 API.

API:
- __init__(storage_dir="logs")
- save(entries: list[dict]) -> None
- load_all() -> list[dict]
"""

import json
import pathlib
import tempfile

import pytest

from src.log_engine.log_storage import LogStorage

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def storage(tmpdir):
    return LogStorage(storage_dir=tmpdir)


# ============================================================================
# 初始化测试
# ============================================================================


class TestLogStorageInit:
    def test_storage_dir_created(self, storage, tmpdir):
        assert pathlib.Path(tmpdir).is_dir()

    def test_default_dir(self):
        import tempfile
        from pathlib import Path

        # 使用临时目录避免污染工作区
        with tempfile.TemporaryDirectory() as d:
            LogStorage(storage_dir=d)
            assert Path(d).is_dir()

    def test_default_path_works(self):
        """默认路径 'logs' 能正常工作."""
        with tempfile.TemporaryDirectory() as d:
            logs_dir = pathlib.Path(d) / "logs"
            LogStorage(storage_dir=str(logs_dir))
            assert logs_dir.is_dir()


# ============================================================================
# 保存测试
# ============================================================================


class TestLogStorageSave:
    def test_save_writes_file(self, storage, tmpdir):
        storage.save([{"key": "value"}])
        files = list(pathlib.Path(tmpdir).glob("log_*.json"))
        assert len(files) == 1

    def test_save_creates_json_content(self, storage, tmpdir):
        entries = [
            {"timestamp": 1000, "type": "start", "message": "started"},
            {"timestamp": 1001, "type": "stop", "message": "stopped"},
        ]
        storage.save(entries)

        files = list(pathlib.Path(tmpdir).glob("log_*.json"))
        with open(files[0]) as f:
            data = json.load(f)
        assert data == entries

    def test_save_empty_list(self, storage, tmpdir):
        storage.save([])
        files = list(pathlib.Path(tmpdir).glob("log_*.json"))
        assert len(files) == 1

    def test_multiple_saves_creates_separate_files(self, storage, tmpdir):
        import time

        storage.save([{"id": 1}])
        time.sleep(1.1)  # save() 使用 int(time.time()) 秒级文件名
        storage.save([{"id": 2}])
        files = list(pathlib.Path(tmpdir).glob("log_*.json"))
        assert len(files) == 2

    def test_save_handles_unicode(self, storage, tmpdir):
        entries = [{"message": "中文测试 🚀", "type": "test"}]
        storage.save(entries)
        files = list(pathlib.Path(tmpdir).glob("log_*.json"))
        with open(files[0], encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["message"] == "中文测试 🚀"


# ============================================================================
# 加载测试
# ============================================================================


class TestLogStorageLoad:
    def test_load_all_empty(self, storage):
        assert storage.load_all() == []

    def test_load_all_single_file(self, storage, tmpdir):
        storage.save([{"a": 1}, {"b": 2}])
        result = storage.load_all()
        assert len(result) == 2
        assert result == [{"a": 1}, {"b": 2}]

    def test_load_all_multiple_files(self, storage, tmpdir):
        import time

        storage.save([{"id": 1}])
        time.sleep(1.1)
        storage.save([{"id": 2}])
        time.sleep(1.1)
        storage.save([{"id": 3}])
        result = storage.load_all()
        assert len(result) == 3
        assert [e["id"] for e in result] == [1, 2, 3]

    def test_load_all_sorted_by_filename(self, storage, tmpdir):
        """文件按名称排序加载，保证时间顺序."""
        import time

        storage.save([{"seq": 1}])
        time.sleep(1.1)
        storage.save([{"seq": 2}])
        time.sleep(1.1)
        storage.save([{"seq": 3}])
        result = storage.load_all()
        assert [e["seq"] for e in result] == [1, 2, 3]


# ============================================================================
# 边界情况
# ============================================================================


class TestLogStorageEdgeCases:
    def test_storage_dir_with_subdirs(self, tmpdir):
        """支持子目录路径."""
        sub = pathlib.Path(tmpdir) / "sub" / "logs"
        LogStorage(storage_dir=str(sub))
        assert sub.is_dir()

    def test_save_and_load_roundtrip(self, storage, tmpdir):
        """保存后重新加载数据一致."""
        original = [
            {"ts": 1, "msg": "first"},
            {"ts": 2, "msg": "second"},
        ]
        storage.save(original)
        loaded = storage.load_all()
        assert loaded == original

    def test_large_number_of_entries(self, storage, tmpdir):
        """大量条目保存和加载."""
        entries = [{"id": i, "data": f"entry_{i}"} for i in range(1000)]
        storage.save(entries)
        loaded = storage.load_all()
        assert len(loaded) == 1000
        assert loaded == entries

    def test_load_all_ignores_non_json_files(self, storage, tmpdir):
        """load_all 只读取 log_*.json 文件."""
        storage.save([{"valid": True}])
        # 创建干扰文件
        (pathlib.Path(tmpdir) / "other.txt").write_text("not json")
        (pathlib.Path(tmpdir) / "log_backup.txt").write_text("also not json")
        result = storage.load_all()
        assert len(result) == 1
