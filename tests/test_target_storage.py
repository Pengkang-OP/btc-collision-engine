#!/usr/bin/env python3
"""地址持久化存储 (storage) 单元测试

覆盖：
- validate_bitcoin_address 地址验证函数
- ADDRESS_PATTERNS 正则表达式
- AddressStorage 初始化与存储操作
- JSON/SQLite/CSV 后端
- get_storage_info / export_csv
"""

import os
import pathlib
import tempfile

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_addresses():
    return {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "1HLoD9x9dDqvtJ3BMLBiqtitRzhfxkAW8H",
        "12higDjoCCNXSA95xZMWUdPvXNmkAduhWv",
    }


# ============================================================================
# validate_bitcoin_address 测试
# ============================================================================


@pytest.mark.unit
class TestValidateBitcoinAddress:
    """地址格式验证测试"""

    def test_valid_p2pkh(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True

    def test_valid_p2sh(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") is True

    def test_valid_bech32(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq") is True

    def test_invalid_too_short(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("1short") is False

    def test_invalid_too_long(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("1" + "A" * 62) is False

    def test_empty_string(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("") is False

    def test_none(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address(None) is False

    def test_sql_injection_chars(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("1A1z'; DROP TABLE targets;--") is False

    def test_unknown_format(self):
        from src.collision.targets.storage import validate_bitcoin_address

        assert validate_bitcoin_address("xyz123notvalid") is False


# ============================================================================
# ADDRESS_PATTERNS 测试
# ============================================================================


@pytest.mark.unit
class TestAddressPatterns:
    """地址正则模式测试"""

    def test_patterns_exist(self):
        from src.collision.targets.storage import ADDRESS_PATTERNS

        assert "P2PKH" in ADDRESS_PATTERNS
        assert "P2SH" in ADDRESS_PATTERNS
        assert "BECH32" in ADDRESS_PATTERNS

    def test_p2pkh_pattern(self):
        from src.collision.targets.storage import ADDRESS_PATTERNS

        assert ADDRESS_PATTERNS["P2PKH"].match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert ADDRESS_PATTERNS["P2PKH"].match("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")

    def test_bech32_pattern(self):
        from src.collision.targets.storage import ADDRESS_PATTERNS

        assert ADDRESS_PATTERNS["BECH32"].match("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        assert ADDRESS_PATTERNS["BECH32"].match("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt")


# ============================================================================
# AddressStorage 测试
# ============================================================================


@pytest.mark.unit
class TestAddressStorageJson:
    """JSON 存储测试"""

    def test_init_creates_directory(self, temp_dir):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "targets.json")
        storage = AddressStorage(storage_type="json", path=storage_path)  # noqa: F841
        # 应创建目录
        assert pathlib.Path(os.path.dirname(storage_path) or ".").exists()

    def test_save_and_load_json(self, temp_dir, sample_addresses):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "targets.json")
        storage = AddressStorage(storage_type="json", path=storage_path)
        success = storage.save_targets(sample_addresses)
        assert success is True
        assert pathlib.Path(storage_path).exists()

        targets, metadata = storage.load_targets()
        assert targets == sample_addresses
        assert metadata is not None

    def test_save_with_metadata(self, temp_dir, sample_addresses):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "targets_meta.json")
        storage = AddressStorage(storage_type="json", path=storage_path)
        meta = {"name": "test", "version": 1}
        storage.save_targets(sample_addresses, metadata=meta)
        targets, loaded_meta = storage.load_targets()
        assert loaded_meta == meta

    def test_load_nonexistent_json(self, temp_dir):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "nonexistent.json")
        storage = AddressStorage(storage_type="json", path=storage_path)
        targets, metadata = storage.load_targets()
        assert targets == set()
        assert metadata is None


@pytest.mark.unit
class TestAddressStorageSqlite:
    """SQLite 存储测试"""

    def test_init_creates_directory(self, temp_dir):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "targets.db")
        storage = AddressStorage(storage_type="sqlite", path=storage_path)  # noqa: F841
        assert pathlib.Path(os.path.dirname(storage_path) or ".").exists()

    def test_save_and_load_sqlite(self, temp_dir, sample_addresses):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "targets.db")
        storage = AddressStorage(storage_type="sqlite", path=storage_path)
        success = storage.save_targets(sample_addresses)
        assert success is True

        targets, metadata = storage.load_targets()
        assert targets == sample_addresses

    def test_save_filters_invalid(self, temp_dir):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "filtered.db")
        storage = AddressStorage(storage_type="sqlite", path=storage_path)
        mixed = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "not_a_valid_address_xyz"}
        success = storage.save_targets(mixed)
        assert success is True
        targets, _ = storage.load_targets()
        assert "not_a_valid_address_xyz" not in targets


@pytest.mark.unit
class TestAddressStorageCsv:
    """CSV 存储测试"""

    def test_save_and_load_csv(self, temp_dir, sample_addresses):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "targets.csv")
        storage = AddressStorage(storage_type="csv", path=storage_path)
        success = storage.save_targets(sample_addresses)
        assert success is True

        targets, _ = storage.load_targets()
        assert targets == sample_addresses

    def test_export_csv(self, temp_dir, sample_addresses):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "storage.json")
        export_path = os.path.join(temp_dir, "export.csv")
        storage = AddressStorage(storage_type="json", path=storage_path)
        success = storage.export_csv(sample_addresses, export_path)
        assert success is True
        assert pathlib.Path(export_path).exists()


@pytest.mark.unit
class TestGetStorageInfo:
    """存储信息测试"""

    def test_info_for_existing(self, temp_dir, sample_addresses):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "info.json")
        storage = AddressStorage(storage_type="json", path=storage_path)
        storage.save_targets(sample_addresses)
        info = storage.get_storage_info()
        assert info["exists"] is True
        assert info["storage_type"] == "json"
        assert info["size_bytes"] > 0

    def test_info_for_nonexistent(self, temp_dir):
        from src.collision.targets.storage import AddressStorage

        storage_path = os.path.join(temp_dir, "noexist.json")
        storage = AddressStorage(storage_type="json", path=storage_path)
        info = storage.get_storage_info()
        assert info["exists"] is False
