"""地址导入和自动保存功能测试"""

import json
import os
import tempfile

import pytest

from src.collision.targets.storage import AddressStorage


class TestAddressImport:
    """地址导入功能测试"""

    def test_import_from_text_file(self):
        """测试从文本文件导入地址"""
        # 创建临时文本文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# 测试地址文件\n")
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2\n")
            f.write("invalid_address\n")  # 无效地址
            f.write("12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX\n")
            temp_txt_path = f.name

        try:
            # 创建存储实例
            storage = AddressStorage()

            # 执行导入
            result = storage.import_addresses(
                source_path=temp_txt_path,
                storage_dir=tempfile.mkdtemp(),
                validate=True,
                storage_type="json",
            )

            # 验证结果
            assert result["success"] is True
            assert result["imported_count"] >= 2  # 至少2个有效地址
            assert result["invalid_count"] >= 1  # 至少1个无效地址
            assert result["total_count"] == 4
            assert os.path.exists(result["storage_path"])

            # 验证保存的文件内容
            with open(result["storage_path"], encoding="utf-8") as f:
                data = json.load(f)
                assert "targets" in data
                assert len(data["targets"]) == result["imported_count"]
                assert "metadata" in data
                assert data["metadata"]["imported_count"] == result["imported_count"]

        finally:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)

    def test_import_from_json_file(self):
        """测试从JSON文件导入地址"""
        # 创建临时JSON文件
        test_data = {
            "addresses": [
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
                "invalid_address",
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(test_data, f)
            temp_json_path = f.name

        try:
            storage = AddressStorage()

            result = storage.import_addresses(
                source_path=temp_json_path,
                storage_dir=tempfile.mkdtemp(),
                validate=True,
                storage_type="json",
            )

            assert result["success"] is True
            assert result["imported_count"] == 2
            assert result["invalid_count"] == 1

        finally:
            if os.path.exists(temp_json_path):
                os.unlink(temp_json_path)

    def test_import_from_csv_file(self):
        """测试从CSV文件导入地址"""
        # 创建临时CSV文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("address,name\n")
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa,test1\n")
            f.write("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2,test2\n")
            f.write("invalid_address,test3\n")
            temp_csv_path = f.name

        try:
            storage = AddressStorage()

            result = storage.import_addresses(
                source_path=temp_csv_path,
                storage_dir=tempfile.mkdtemp(),
                validate=True,
                storage_type="csv",
            )

            assert result["success"] is True
            assert result["imported_count"] == 2
            assert result["invalid_count"] == 1

        finally:
            if os.path.exists(temp_csv_path):
                os.unlink(temp_csv_path)

    def test_import_without_validation(self):
        """测试不验证直接导入"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("invalid_address\n")
            temp_txt_path = f.name

        try:
            storage = AddressStorage()

            result = storage.import_addresses(
                source_path=temp_txt_path,
                storage_dir=tempfile.mkdtemp(),
                validate=False,  # 不验证
                storage_type="json",
            )

            assert result["success"] is True
            assert result["imported_count"] == 2  # 包括无效地址
            assert result["invalid_count"] == 0  # 没有验证，所以没有无效地址

        finally:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)

    def test_import_nonexistent_file(self):
        """测试导入不存在的文件"""
        storage = AddressStorage()

        result = storage.import_addresses(
            source_path="/nonexistent/file.txt", storage_dir=tempfile.mkdtemp()
        )

        assert result["success"] is False
        assert result["error"] is not None
        # 安全检查看起来先于文件存在性检查，所以可能报路径错误或文件不存在
        assert "不存在" in result["error"] or "路径超出允许范围" in result["error"]

    def test_import_with_progress_callback(self):
        """测试带进度回调的导入"""
        progress_calls = []

        def progress_callback(imported, total, address):
            progress_calls.append((imported, total, address))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2\n")
            temp_txt_path = f.name

        try:
            storage = AddressStorage()

            result = storage.import_addresses(
                source_path=temp_txt_path,
                storage_dir=tempfile.mkdtemp(),
                validate=True,
                storage_type="json",
                progress_callback=progress_callback,
            )

            assert result["success"] is True
            assert len(progress_calls) == 2  # 应该有2次进度回调

        finally:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)

    def test_import_sqlite_format(self):
        """测试SQLite格式导入"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2\n")
            temp_txt_path = f.name

        try:
            storage = AddressStorage()

            result = storage.import_addresses(
                source_path=temp_txt_path,
                storage_dir=tempfile.mkdtemp(),
                validate=True,
                storage_type="sqlite",
            )

            assert result["success"] is True
            assert result["imported_count"] == 2
            assert result["storage_path"].endswith(".db")

            # 验证可以通过存储加载
            loaded_storage = AddressStorage(storage_type="sqlite", path=result["storage_path"])
            loaded_targets, metadata = loaded_storage.load_targets()
            assert len(loaded_targets) == 2

        finally:
            if os.path.exists(temp_txt_path):
                os.unlink(temp_txt_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
