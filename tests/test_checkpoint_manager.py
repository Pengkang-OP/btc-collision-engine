"""CheckpointManager 单元测试 - 保存/加载/删除、敏感信息清理、原子写入"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.checkpoint_manager import CheckpointManager


class TestCheckpointManagerBasic(unittest.TestCase):
    """基础保存/加载/删除测试"""

    def setUp(self):
        # 使用临时文件，但不预先创建
        import uuid

        self.tmp_path = os.path.join(
            tempfile.gettempdir(), f"test_ckpt_{uuid.uuid4().hex[:8]}.json"
        )
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)

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
            tempfile.gettempdir(), f"test_ckpt_sens_{uuid.uuid4().hex[:8]}.json"
        )
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)

    def test_private_key_not_saved(self):
        """私钥明文不保存到断点文件"""
        matches_with_key = [
            {
                "address": "1TestAddress",
                "private_key_hex": "deadbeef" * 8,
                "private_key_wif": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU65NZy3yH",
                "timestamp": time.time(),
            }
        ]
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=100,
            matches=matches_with_key,
        )

        # 直接读取 JSON 文件内容
        with open(self.tmp_path, encoding="utf-8") as f:
            raw = f.read()

        self.assertNotIn("deadbeef", raw)
        self.assertNotIn("KwDiBf89", raw)
        self.assertNotIn("private_key_hex", raw)
        self.assertNotIn("private_key_wif", raw)

    def test_address_preserved_in_match(self):
        """断点保存保留地址信息"""
        matches = [{"address": "1TestPreserved", "timestamp": time.time()}]
        self.mgr.save(
            mode="random", targets=set(), current_position=0, total_checked=0, matches=matches
        )
        data = self.mgr.load()
        self.assertEqual(data["matches"][0]["address"], "1TestPreserved")

    def test_security_note_in_file(self):
        """断点文件包含安全说明"""
        self.mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=[])
        with open(self.tmp_path, encoding="utf-8") as f:
            raw = f.read()
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
            with open(tmp.name, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("mode", data)
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

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
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


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
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

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
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
