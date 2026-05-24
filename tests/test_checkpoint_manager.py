"""CheckpointManager 单元测试 - 保存/加载/删除、敏感信息清理、原子写入"""

import json
import os
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch

from src.collision.checkpoint_manager import CheckpointManager


class TestCheckpointManagerBasic(unittest.TestCase):
    """基础保存/加载/删除测试"""

    def setUp(self):
        # 使用临时文件，但不预先创建
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    def test_save_and_load(self):
        """保存后能正确加载"""
        self.mgr.save(
            mode="random",
            targets={"1A1z", "1B2y"},
            current_position=12345,
            total_checked=50000,
            matches=[],
        )
        data = self.mgr.load()
        self.assertIsNotNone(data)
        self.assertEqual(data["mode"], "random")
        self.assertEqual(data["current_position"], 12345)
        self.assertEqual(data["total_checked"], 50000)

    def test_exists_after_save(self):
        """保存后 exists() 返回 True"""
        self.assertFalse(self.mgr.exists())
        self.mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=[])
        self.assertTrue(self.mgr.exists())

    def test_delete(self):
        """删除后 exists() 返回 False"""
        self.mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=[])
        self.assertTrue(self.mgr.exists())
        self.mgr.delete()
        self.assertFalse(self.mgr.exists())

    def test_load_nonexistent_returns_none(self):
        """不存在时 load() 返回 None"""
        mgr = CheckpointManager(filepath="nonexistent_12345.json")
        self.assertIsNone(mgr.load())


class TestCheckpointSensitiveInfoCleaning(unittest.TestCase):
    """敏感信息清理测试"""

    def setUp(self):
        import uuid

        self.tmp_path = os.path.join(
            tempfile.gettempdir(), f"test_ckpt_sens_{uuid.uuid4().hex[:8]}.json",
        )
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    def test_private_key_not_saved(self):
        """私钥明文不保存到断点文件"""
        matches_with_key = [
            {
                "address": "1TestAddress",
                "private_key_hex": "deadbeef" * 8,
                "private_key_wif": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU65NZy3yH",
                "timestamp": time.time(),
            },
        ]
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=100,
            matches=matches_with_key,
        )

        # 直接读取 JSON 文件内容
        raw = pathlib.Path(self.tmp_path).read_text(encoding="utf-8")

        self.assertNotIn("deadbeef", raw)
        self.assertNotIn("KwDiBf89", raw)
        self.assertNotIn("private_key_hex", raw)
        self.assertNotIn("private_key_wif", raw)

    def test_address_preserved_in_match(self):
        """断点保存保留地址信息"""
        matches = [{"address": "1TestPreserved", "timestamp": time.time()}]
        self.mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=matches)
        data = self.mgr.load()
        self.assertEqual(data["matches"][0]["address"], "1TestPreserved")

    def test_security_note_in_file(self):
        """断点文件包含安全说明"""
        self.mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=[])
        raw = pathlib.Path(self.tmp_path).read_text(encoding="utf-8")
        self.assertIn("security_note", raw)


class TestCheckpointAtomicWrite(unittest.TestCase):
    """原子写入测试"""

    def test_file_valid_after_save(self):
        """保存后文件是有效 JSON"""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            mgr = CheckpointManager(filepath=tmp.name)
            mgr.save(
                mode="range",
                targets={"1A"},
                current_position=999,
                total_checked=5000,
                matches=[],
                range_start=1,
                range_end=10000,
            )
            with pathlib.Path(tmp.name).open(encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("mode", data)
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()

    def test_targets_saved_as_list(self):
        """目标地址保存为列表（可 JSON 序列化）"""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            mgr = CheckpointManager(filepath=tmp.name)
            mgr.save(
                mode="random",
                targets={"addr1", "addr2"},
                current_position=0,
                total_checked=0,
                matches=[],
            )
            data = mgr.load()
            self.assertIsInstance(data["targets"], list)
            self.assertIn("addr1", data["targets"])
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()


class TestCheckpointAutoSave(unittest.TestCase):
    """自动保存间隔测试"""

    def test_should_auto_save_initially(self):
        """首次调用 should_auto_save() 应返回 True（超过间隔）"""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            mgr = CheckpointManager(filepath=tmp.name, auto_save_interval=0)
            # 间隔为0，应立即触发
            self.assertTrue(mgr.should_auto_save())
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()

    def test_should_not_auto_save_too_soon(self):
        """刚保存后 should_auto_save() 应返回 False"""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            mgr = CheckpointManager(filepath=tmp.name, auto_save_interval=9999)
            mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=[])
            # 紧接着保存，间隔未到
            self.assertFalse(mgr.should_auto_save())
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()


class TestCheckpointDefaultPath(unittest.TestCase):
    """默认路径测试"""

    def test_default_filepath_uses_data_logs(self):
        """无filepath参数时使用data_logs目录"""
        mgr = CheckpointManager()
        self.assertIn("data_logs", mgr.filepath)
        self.assertIn("collision_checkpoint.json", mgr.filepath)
        # 清理
        mgr.delete()


class TestCheckpointSaveVariants(unittest.TestCase):
    """save() 多种场景测试"""

    def setUp(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_var_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path, auto_save_interval=9999)

    def tearDown(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    def test_save_force_writes_immediately(self):
        """force=True 强制写入"""
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        self.assertTrue(self.mgr.exists())

    def test_save_with_auto_save_disabled(self):
        """间隔未到时 save 仅缓冲不写入"""
        self.mgr._last_save_time = time.time()  # 刚保存过
        self.mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=[])
        # 间隔9999秒未到，不应写入文件
        self.assertFalse(pathlib.Path(self.tmp_path).exists())
        # 但 buffer 应该有数据
        self.assertIsNotNone(self.mgr._buffer)
        self.assertTrue(self.mgr._dirty)

    def test_flush_buffer_not_dirty(self):
        """_flush_buffer 在 _dirty=False 时直接返回"""
        self.mgr._dirty = False
        self.mgr._buffer = {"test": 1}
        self.mgr._flush_buffer()

    def test_flush_buffer_none(self):
        """_flush_buffer 在 _buffer=None 时直接返回"""
        self.mgr._dirty = True
        self.mgr._buffer = None
        self.mgr._flush_buffer()

    def test_save_match_with_private_key_hash(self):
        """Match 含 private_key_hash 时被保存"""
        matches = [{"address": "1Addr", "timestamp": 1.0, "private_key_hash": "abc123"}]
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=matches,
            force=True,
        )
        data = self.mgr.load()
        self.assertEqual(data["matches"][0].get("private_key_hash"), "abc123")


class TestCheckpointFlushErrors(unittest.TestCase):
    """_flush_buffer 异常处理测试"""

    def setUp(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_err_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    @patch("builtins.open")
    def test_flush_permission_error(self, mock_file):
        """PermissionError 被捕获"""
        mock_file.side_effect = PermissionError("permission denied")
        self.mgr._dirty = True
        self.mgr._buffer = {"key": "val"}
        self.mgr._flush_buffer()

    @patch("builtins.open")
    def test_flush_os_error(self, mock_file):
        """OSError 被捕获"""
        mock_file.side_effect = OSError("disk full")
        self.mgr._dirty = True
        self.mgr._buffer = {"key": "val"}
        self.mgr._flush_buffer()

    @patch("builtins.open")
    def test_flush_generic_exception(self, mock_file):
        """通用异常被捕获"""
        mock_file.side_effect = RuntimeError("unexpected")
        self.mgr._dirty = True
        self.mgr._buffer = {"key": "val"}
        self.mgr._flush_buffer()

    def test_cleanup_temp_file_exists(self):
        """_cleanup_temp_file 删除存在的临时文件"""
        temp_file = self.tmp_path + ".tmp"
        pathlib.Path(temp_file).write_text("test")
        self.assertTrue(pathlib.Path(temp_file).exists())
        self.mgr._cleanup_temp_file(temp_file)
        self.assertFalse(pathlib.Path(temp_file).exists())

    def test_cleanup_temp_file_not_exists(self):
        """_cleanup_temp_file 不存在的文件无异常"""
        self.mgr._cleanup_temp_file("/nonexistent/path.tmp")


class TestCheckpointLoadEdgeCases(unittest.TestCase):
    """load() 边界情况测试"""

    def setUp(self):
        import uuid

        self.tmp_path = os.path.join(
            tempfile.gettempdir(), f"test_ckpt_load_{uuid.uuid4().hex[:8]}.json",
        )
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        for p in [self.tmp_path, self.tmp_path + ".tmp"]:
            if pathlib.Path(p).exists():
                pathlib.Path(p).unlink()

    def test_load_version_mismatch(self):
        """版本不兼容时返回 None"""
        with pathlib.Path(self.tmp_path).open("w") as f:
            json.dump({"version": 2, "mode": "random"}, f)
        result = self.mgr.load()
        self.assertIsNone(result)

    def test_load_corrupt_json(self):
        """损坏的 JSON 返回 None"""
        pathlib.Path(self.tmp_path).write_text("not a json file {{{")
        result = self.mgr.load()
        self.assertIsNone(result)

    def test_load_temp_file_recovery(self):
        """.tmp 文件恢复为主文件"""
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "recovered"}, f)
        self.assertTrue(pathlib.Path(temp_file).exists())
        self.assertFalse(pathlib.Path(self.tmp_path).exists())

        result = self.mgr.load()
        self.assertIsNotNone(result)
        self.assertEqual(result["mode"], "recovered")

    def test_load_temp_recovery_with_main_exists(self):
        """.tmp 恢复时主文件已存在则不覆盖"""
        with pathlib.Path(self.tmp_path).open("w") as f:
            json.dump({"version": 1, "mode": "main"}, f)
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "temp"}, f)

        result = self.mgr.load()
        self.assertEqual(result["mode"], "main")


class TestCheckpointDelete(unittest.TestCase):
    """delete() 测试"""

    def setUp(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_del_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        for p in [self.tmp_path, self.tmp_path + ".tmp"]:
            if pathlib.Path(p).exists():
                pathlib.Path(p).unlink()

    def test_delete_with_temp_file(self):
        """Delete 同时清理 .tmp 文件"""
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        temp_file = self.tmp_path + ".tmp"
        pathlib.Path(temp_file).write_text("temp")
        self.assertTrue(pathlib.Path(temp_file).exists())

        self.mgr.delete()
        self.assertFalse(pathlib.Path(temp_file).exists())
        self.assertFalse(pathlib.Path(self.tmp_path).exists())

    def test_delete_clears_buffer(self):
        """Delete 清空 buffer 和 dirty"""
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        self.mgr.delete()
        self.assertIsNone(self.mgr._buffer)
        self.assertFalse(self.mgr._dirty)


class TestCheckpointPywin32Check(unittest.TestCase):
    """_check_win32_security 测试"""

    def test_check_win32_security_cached(self):
        """结果被缓存"""
        result1 = CheckpointManager._check_win32_security()
        result2 = CheckpointManager._check_win32_security()
        self.assertEqual(result1, result2)

    def test_check_win32_security_import_error(self):
        """pywin32 不可用时返回 False"""
        old_value = CheckpointManager._has_win32_security
        CheckpointManager._has_win32_security = None
        try:
            with patch("builtins.__import__", side_effect=ImportError("no pywin32")):
                result = CheckpointManager._check_win32_security()
        finally:
            CheckpointManager._has_win32_security = old_value
        self.assertFalse(result)

    def test_check_win32_security_import_success(self):
        """pywin32 可用时返回 True"""
        old_value = CheckpointManager._has_win32_security
        CheckpointManager._has_win32_security = None
        try:
            result = CheckpointManager._check_win32_security()
            # 如果 pywin32 已安装则为 True，否则为 False
            self.assertIsInstance(result, bool)
        finally:
            CheckpointManager._has_win32_security = old_value


class TestCheckpointExists(unittest.TestCase):
    """exists() 测试"""

    def test_exists_no_file(self):
        """文件不存在时返回 False"""
        mgr = CheckpointManager(filepath="/nonexistent/checkpoint.json")
        self.assertFalse(mgr.exists())


class TestCheckpointFlushDirCreation(unittest.TestCase):
    """_flush_buffer 目录创建测试"""

    def test_flush_creates_parent_dir(self):
        """父目录不存在时自动创建"""
        import shutil
        import uuid

        subdir = os.path.join(tempfile.gettempdir(), f"ckpt_test_{uuid.uuid4().hex[:8]}")
        ckpt_path = os.path.join(subdir, "checkpoint.json")
        mgr = CheckpointManager(filepath=ckpt_path)
        try:
            mgr._dirty = True
            mgr._buffer = {"version": 1, "test": True}
            mgr._flush_buffer()
            self.assertTrue(pathlib.Path(ckpt_path).exists())
        finally:
            mgr.delete()
            if pathlib.Path(subdir).exists():
                shutil.rmtree(subdir, ignore_errors=True)


class TestCheckpointCleanupErrors(unittest.TestCase):
    """_cleanup_temp_file 异常处理测试"""

    @patch("os.remove", side_effect=OSError("cannot delete"))
    @patch("os.path.exists", return_value=True)
    def test_cleanup_os_error_silenced(self, mock_exists, mock_remove):
        """删除失败时不抛出异常"""
        mgr = CheckpointManager(filepath="/tmp/test.json")
        mgr._cleanup_temp_file("/tmp/test.json.tmp")


class TestCheckpointLoadTempRecoveryErrors(unittest.TestCase):
    """load() 临时文件恢复失败测试"""

    def setUp(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_rec_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        for p in [self.tmp_path, self.tmp_path + ".tmp"]:
            if pathlib.Path(p).exists():
                pathlib.Path(p).unlink()

    @patch("os.replace", side_effect=OSError("rename failed"))
    def test_temp_recovery_rename_os_error(self, mock_rename):
        """Replace 失败时记录日志并清理"""
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "test"}, f)
        # replace 会失败，但不应崩溃
        result = self.mgr.load()
        self.assertIsNone(result)

    @patch("os.replace", side_effect=Exception("unexpected"))
    def test_temp_recovery_rename_unexpected_error(self, mock_rename):
        """Replace 未知异常被记录"""
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "test"}, f)
        result = self.mgr.load()
        self.assertIsNone(result)


class TestCheckpointDeleteErrors(unittest.TestCase):
    """delete() 异常处理测试"""

    @patch("os.path.exists", return_value=True)
    @patch("os.remove", side_effect=Exception("delete failed"))
    def test_delete_exception_caught(self, mock_remove, mock_exists):
        """Delete 异常被捕获"""
        mgr = CheckpointManager(filepath="/tmp/test.json")
        mgr.delete()


if __name__ == "__main__":
    unittest.main(verbosity=2)
