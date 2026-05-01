#!/usr/bin/env python3
"""匹配数据存储 (MatchDataStorage) 单元测试

覆盖：
- 初始化与目录创建
- 保存匹配数据（原子写入）
- 数据完整性验证
- 备份机制
- 列表/加载/统计
"""

import os
import json
import tempfile
import pytest
from pathlib import Path

from src.collision.match_storage import MatchDataStorage

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def storage():
    """创建临时目录中的 MatchDataStorage"""
    with tempfile.TemporaryDirectory() as tmpdir:
        s = MatchDataStorage(storage_path=tmpdir)
        yield s


@pytest.fixture
def match_data():
    """创建标准的匹配数据字典"""
    return {
        "found_at": "2026-05-01T08:00:00",
        "hash160": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "generated": {
            "private_key": bytes.fromhex(
                "0c28fca386c7a227600b2fe50b7cae11ec86d3bf1fbe471be89827e19d72aa1d"
            ),
            "wif_compressed": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU72sVhvfoj",
            "wif_uncompressed": "5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAvUcVfH",
            "public_key_compressed": bytes.fromhex(
                "02b4632d08485ff1df2db55b9dafd23347d1c47a457072a1e87be26896549a8737"
            ),
            "public_key_uncompressed": bytes.fromhex(
                "04b4632d08485ff1df2db55b9dafd23347d1c47a457072a1e87be26896549a8737"
                "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            ),
            "address_compressed": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "address_uncompressed": "1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm",
            "hash160_compressed": bytes.fromhex("a1b2c3d4e5f6a1b2c3d4e5"),
            "hash160_uncompressed": bytes.fromhex("f6a1b2c3d4e5f6a1b2c3d4e5"),
        },
        "target": {
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "source": "targets.txt",
        },
    }


# ============================================================================
# 初始化测试
# ============================================================================


@pytest.mark.unit
class TestMatchStorageInit:
    """初始化测试"""

    def test_storage_dir_created(self, storage):
        assert storage.storage_path.exists()
        assert storage.storage_path.is_dir()

    def test_storage_path_is_pathlib(self, storage):
        assert isinstance(storage.storage_path, Path)


# ============================================================================
# 保存匹配测试
# ============================================================================


@pytest.mark.unit
class TestMatchStorageSave:
    """保存匹配测试"""

    def test_save_match_creates_file(self, storage, match_data):
        filepath = storage.save_match(match_data)
        assert os.path.exists(filepath)
        assert filepath.endswith(".json")

    def test_save_match_filename_format(self, storage, match_data):
        filepath = storage.save_match(match_data)
        filename = os.path.basename(filepath)
        assert filename.startswith("match_")
        assert filename.endswith(".json")
        # 应包含时间戳和 hash160 前8位

    def test_save_match_data_integrity(self, storage, match_data):
        filepath = storage.save_match(match_data)

        with open(filepath, "r", encoding="utf-8") as f:
            saved = json.load(f)

        assert "match_info" in saved
        assert "private_key" in saved
        assert "public_key" in saved
        assert "address" in saved
        assert "target_info" in saved
        assert "verification" in saved
        assert saved["verification"]["private_key_valid"] is True
        assert saved["verification"]["address_match"] is True

    def test_save_match_hex_conversion(self, storage, match_data):
        """字节串应转为十六进制字符串"""
        filepath = storage.save_match(match_data)

        with open(filepath, "r", encoding="utf-8") as f:
            saved = json.load(f)

        # 私钥 hex
        pk_hex = saved["private_key"]["hex"]
        assert isinstance(pk_hex, str)
        assert len(pk_hex) == 64  # 32 bytes = 64 hex chars

        # 公钥 hex
        pub_compressed = saved["public_key"]["compressed"]
        assert isinstance(pub_compressed, str)
        assert len(pub_compressed) == 66  # 33 bytes = 66 hex chars

    def test_save_match_creates_backup(self, storage, match_data):
        filepath = storage.save_match(match_data)
        backup_dir = storage.storage_path / "backup"
        assert backup_dir.exists()

        backup_file = backup_dir / os.path.basename(filepath)
        assert backup_file.exists()

    def test_save_match_atomic_write(self, storage, match_data):
        """验证临时文件在保存后被清理"""
        filepath = storage.save_match(match_data)
        temp_file = Path(filepath).with_suffix(".tmp")
        assert not temp_file.exists()  # 临时文件应被清理


# ============================================================================
# 列表与加载测试
# ============================================================================


@pytest.mark.unit
class TestMatchStorageList:
    """列表与加载测试"""

    def test_list_matches_empty(self, storage):
        matches = storage.list_matches()
        assert matches == []

    def test_list_matches(self, storage, match_data):
        storage.save_match(match_data)
        matches = storage.list_matches()
        assert len(matches) == 1
        assert matches[0].endswith(".json")

    def test_list_matches_sorted(self, storage, match_data):
        storage.save_match(match_data)
        # 保存第二个匹配
        match_data2 = dict(match_data)
        match_data2["hash160"] = "b" * 40
        storage.save_match(match_data2)

        matches = storage.list_matches()
        assert len(matches) == 2
        assert matches == sorted(matches)

    def test_load_match(self, storage, match_data):
        filepath = storage.save_match(match_data)
        loaded = storage.load_match(filepath)
        assert loaded is not None
        assert loaded["match_info"]["hash160"] == match_data["hash160"]

    def test_load_nonexistent_file(self, storage):
        loaded = storage.load_match("/nonexistent/path.json")
        assert loaded is None


@pytest.mark.unit
class TestMatchStorageStatistics:
    """统计测试"""

    def test_get_statistics_empty(self, storage):
        stats = storage.get_statistics()
        assert stats["total_matches"] == 0
        assert stats["storage_path"] == str(storage.storage_path)
        assert stats["backup_enabled"] is True

    def test_get_statistics_with_matches(self, storage, match_data):
        storage.save_match(match_data)
        stats = storage.get_statistics()
        assert stats["total_matches"] == 1
        assert stats["total_size_mb"] >= 0
