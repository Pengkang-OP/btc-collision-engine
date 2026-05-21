#!/usr/bin/env python3
"""匹配数据存储 (MatchDataStorage) 单元测试

覆盖：
- 初始化与目录创建
- 保存匹配数据（原子写入）
- 数据完整性验证
- 备份机制
- 列表/加载/统计
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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
            # 使用占位数据 — 私钥为全零占位符，WIF为明显假值
            "private_key": b"\x00" * 32,
            "wif_compressed": "5" + "H" + "0" * 49,
            "wif_uncompressed": "5" + "J" + "0" * 49,
            "public_key_compressed": bytes.fromhex("02" + "00" * 32),
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

    @patch("os.chmod", side_effect=OSError("chmod failed"))
    def test_init_chmod_failure_warning(self, mock_chmod):
        """os.chmod 失败时记录警告但不崩溃"""
        with tempfile.TemporaryDirectory() as tmpdir:
            s = MatchDataStorage(storage_path=tmpdir)
            assert s.storage_path.exists()


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

        with open(filepath, encoding="utf-8") as f:
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

        with open(filepath, encoding="utf-8") as f:
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
class TestMatchStorageEdgeCases:
    """边缘情况测试"""

    @patch.object(MatchDataStorage, "_create_backup", side_effect=Exception("backup fail"))
    def test_save_match_exception_cleans_temp(self, mock_backup, storage, match_data):
        """save_match 异常时清理临时文件并重新抛出"""
        with pytest.raises(Exception):  # noqa: B017
            storage.save_match(match_data)
        # 临时文件应被清理
        temp_files = list(storage.storage_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_build_complete_data_non_bytes_to_hex(self, storage, match_data):
        """to_hex 处理非 bytes 类型"""
        # hash160_compressed 传字符串而非 bytes
        match_data["generated"]["hash160_compressed"] = "already_hex_string"
        filepath = storage.save_match(match_data)
        with open(filepath) as f:
            saved = json.load(f)
        # 字符串原样返回
        assert saved["address"]["hash160_compressed"] == "already_hex_string"

    @patch("builtins.open", side_effect=Exception("disk error"))
    def test_create_backup_exception_caught(self, mock_open, storage, match_data):
        """_create_backup 异常被捕获不传播"""
        storage._create_backup(Path("/tmp/test.json"), {"key": "val"})

    @patch.object(Path, "unlink", side_effect=OSError("unlink failed"))
    def test_temp_cleanup_unlink_error(self, mock_unlink, storage, match_data):
        """临时文件清理失败不传播异常"""
        # 让 os.chmod 在 temp_file 仍存在时失败，触发 cleanup 代码路径
        with patch("os.chmod", side_effect=OSError("chmod fail")), pytest.raises(OSError):
            storage.save_match(match_data)

    def test_list_matches_skips_non_file(self, storage):
        """list_matches 跳过非文件条目"""
        # 创建一个匹配模式但不是文件的目录
        fake_dir = storage.storage_path / "match_20260501_dir_test.json"
        fake_dir.mkdir()
        try:
            matches = storage.list_matches()
            assert fake_dir.name not in [os.path.basename(m) for m in matches]
        finally:
            fake_dir.rmdir()


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
