# -*- coding: utf-8 -*-
"""file_utils 模块单元测试

测试原子写入、安全读取、备份恢复、安全删除等功能。
"""

import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from src.utils.file_utils import (
    atomic_json_write,
    atomic_json_read,
    _recover_from_backup,
    safe_file_delete,
    get_file_size_safe,
    ensure_directory,
)


class TestAtomicJsonWrite:
    """atomic_json_write 原子写入测试"""

    def setup_method(self):
        """创建临时目录"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test.json")

    def teardown_method(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_basic_write(self):
        """基本 JSON 写入"""
        data = {"key": "value", "num": 42}
        result = atomic_json_write(self.test_file, data)
        assert result is True
        assert os.path.exists(self.test_file)
        with open(self.test_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_write_creates_directory(self):
        """自动创建父目录"""
        nested_file = os.path.join(self.test_dir, "sub", "deep", "config.json")
        data = {"a": 1}
        result = atomic_json_write(nested_file, data)
        assert result is True
        assert os.path.exists(nested_file)

    def test_write_with_indent(self):
        """带缩进写入"""
        data = {"a": 1, "b": 2}
        result = atomic_json_write(self.test_file, data, indent=4)
        assert result is True
        content = Path(self.test_file).read_text(encoding="utf-8")
        assert "    " in content

    def test_write_without_fsync(self):
        """fsync=False"""
        data = {"a": 1}
        result = atomic_json_write(self.test_file, data, fsync=False)
        assert result is True
        assert os.path.exists(self.test_file)

    def test_write_overwrite_existing(self):
        """覆盖已存在文件"""
        data1 = {"version": 1}
        data2 = {"version": 2}
        atomic_json_write(self.test_file, data1)
        result = atomic_json_write(self.test_file, data2)
        assert result is True
        with open(self.test_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data2

    def test_write_ensure_ascii(self):
        """ensure_ascii=True"""
        data = {"key": "value"}
        result = atomic_json_write(self.test_file, data, ensure_ascii=True)
        assert result is True

    def test_write_type_error_returns_false(self):
        """不可序列化数据返回 False"""
        result = atomic_json_write(self.test_file, object())
        assert result is False


class TestAtomicJsonRead:
    """atomic_json_read 安全读取测试"""

    def setup_method(self):
        """创建临时目录"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "data.json")

    def teardown_method(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_read_existing_file(self):
        """读取存在的 JSON 文件"""
        data = {"key": "value", "list": [1, 2, 3]}
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = atomic_json_read(self.test_file)
        assert result == data

    def test_read_nonexistent_file_returns_default(self):
        """文件不存在返回 default"""
        result = atomic_json_read(self.test_file, default={"fallback": True})
        assert result == {"fallback": True}

    def test_read_nonexistent_file_returns_none(self):
        """文件不存在返回 None (默认)"""
        result = atomic_json_read(self.test_file)
        assert result is None

    def test_read_with_validation_pass(self):
        """验证函数通过"""
        data = {"key": "value"}
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = atomic_json_read(
            self.test_file, validate_func=lambda d: "key" in d
        )
        assert result == data

    def test_read_with_validation_fail(self):
        """验证函数失败返回 default"""
        data = {"wrong": "value"}
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = atomic_json_read(
            self.test_file, default={"backup": True},
            validate_func=lambda d: "key" in d
        )
        assert result == {"backup": True}

    def test_read_corrupted_json_triggers_recovery(self):
        """JSON 损坏触发备份恢复"""
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        result = atomic_json_read(self.test_file, default={"recovered": True})
        assert result == {"recovered": True}


class TestRecoverFromBackup:
    """_recover_from_backup 备份恢复测试"""

    def setup_method(self):
        """创建临时目录"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "config.json")

    def teardown_method(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_recover_from_tmp(self):
        """从 .tmp 文件恢复"""
        tmp_file = self.test_file + ".tmp"
        data = {"from": "tmp"}
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = _recover_from_backup(self.test_file, None)
        assert result == data
        assert os.path.exists(self.test_file)
        assert not os.path.exists(tmp_file)

    def test_recover_from_bak(self):
        """从 .bak 文件恢复"""
        bak_file = self.test_file + ".bak"
        data = {"from": "bak"}
        with open(bak_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = _recover_from_backup(self.test_file, None)
        assert result == data

    def test_recover_tmp_priority_over_bak(self):
        """tmp 优先于 bak"""
        tmp_file = self.test_file + ".tmp"
        bak_file = self.test_file + ".bak"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"from": "tmp"}, f)
        with open(bak_file, "w", encoding="utf-8") as f:
            json.dump({"from": "bak"}, f)

        result = _recover_from_backup(self.test_file, None)
        assert result == {"from": "tmp"}
        # tmp 被 rename 到原文件，bak 仍存在
        assert os.path.exists(bak_file)

    def test_recover_no_backup_returns_default(self):
        """无备份返回 default"""
        result = _recover_from_backup(self.test_file, {"custom": "default"})
        assert result == {"custom": "default"}

    def test_recover_tmp_corrupted_falls_back(self):
        """tmp 损坏后清理并尝试 bak"""
        tmp_file = self.test_file + ".tmp"
        bak_file = self.test_file + ".bak"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write("{invalid")
        with open(bak_file, "w", encoding="utf-8") as f:
            json.dump({"from": "bak"}, f)

        result = _recover_from_backup(self.test_file, None)
        assert result == {"from": "bak"}
        assert not os.path.exists(tmp_file)


class TestSafeFileDelete:
    """safe_file_delete 安全删除测试"""

    def setup_method(self):
        """创建临时目录"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "to_delete.txt")

    def teardown_method(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_delete_existing_with_backup(self):
        """删除并创建 .bak"""
        with open(self.test_file, "w") as f:
            f.write("test data")
        result = safe_file_delete(self.test_file, backup=True)
        assert result is True
        assert not os.path.exists(self.test_file)
        assert os.path.exists(self.test_file + ".bak")

    def test_delete_existing_without_backup(self):
        """不备份直接删除"""
        with open(self.test_file, "w") as f:
            f.write("test data")
        result = safe_file_delete(self.test_file, backup=False)
        assert result is True
        assert not os.path.exists(self.test_file)
        assert not os.path.exists(self.test_file + ".bak")

    def test_delete_nonexistent_returns_true(self):
        """文件不存在返回 True"""
        result = safe_file_delete(self.test_file)
        assert result is True

    def test_delete_backup_failure_still_deletes(self):
        """备份失败仍尝试删除"""
        with open(self.test_file, "w") as f:
            f.write("test data")

        with patch("shutil.copy2", side_effect=OSError("permission denied")):
            result = safe_file_delete(self.test_file, backup=True)
        assert result is True
        assert not os.path.exists(self.test_file)


class TestGetFileSizeSafe:
    """get_file_size_safe 文件大小测试"""

    def setup_method(self):
        """创建临时目录"""
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_existing_file_size(self):
        """获取存在的文件大小"""
        test_file = os.path.join(self.test_dir, "data.bin")
        with open(test_file, "wb") as f:
            f.write(b"x" * 1024)
        size = get_file_size_safe(test_file)
        assert size == 1024

    def test_nonexistent_file_returns_zero(self):
        """不存在返回 0"""
        size = get_file_size_safe(os.path.join(self.test_dir, "nonexistent"))
        assert size == 0

    def test_getsize_error_returns_zero(self):
        """os.path.getsize 异常时返回 0"""
        test_file = os.path.join(self.test_dir, "data.bin")
        with open(test_file, "wb") as f:
            f.write(b"x" * 100)
        with patch("os.path.getsize", side_effect=OSError("disk error")):
            size = get_file_size_safe(test_file)
        assert size == 0


class TestEnsureDirectory:
    """ensure_directory 目录创建测试"""

    def setup_method(self):
        """创建临时目录"""
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_create_new_directory(self):
        """创建新目录"""
        new_dir = os.path.join(self.test_dir, "new_dir")
        result = ensure_directory(new_dir)
        assert result is True
        assert os.path.isdir(new_dir)

    def test_existing_directory(self):
        """已存在目录"""
        existing = os.path.join(self.test_dir, "existing")
        os.makedirs(existing)
        result = ensure_directory(existing)
        assert result is True

    def test_creation_failure_returns_false(self):
        """权限错误返回 False（模拟）"""
        with patch("os.path.exists", return_value=False), \
             patch("os.makedirs", side_effect=OSError("permission denied")):
            result = ensure_directory("/invalid/path")
        assert result is False
