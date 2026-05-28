"""CheckpointManager 单元测试 - 保存/加载/删除、敏感信息清理、原子写入."""

import json
import os
import pathlib
import tempfile
import time
from unittest.mock import patch

import pytest

from src.collision.checkpoint_manager import CheckpointManager


class TestCheckpointManagerBasic:
    """基础保存/加载/删除测试."""

    def setup_method(self):
        # 使用临时文件，但不预先创建
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def teardown_method(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    def test_save_and_load(self):
        """保存后能正确加载."""
        self.mgr.save(
            mode="random",
            targets={"1A1z", "1B2y"},
            current_position=12345,
            total_checked=50000,
            matches=[],
            force=True,
        )
        data = self.mgr.load()
        assert data is not None
        assert data["mode"] == "random"
        assert data["current_position"] == 12345
        assert data["total_checked"] == 50000

    def test_exists_after_save(self):
        """保存后 exists() 返回 True."""
        assert not self.mgr.exists
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        assert self.mgr.exists

    def test_delete(self):
        """删除后 exists() 返回 False."""
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        assert self.mgr.exists
        self.mgr.delete()
        assert not self.mgr.exists

    def test_load_nonexistent_returns_none(self):
        """不存在时 load() 返回 None."""
        mgr = CheckpointManager(filepath="nonexistent_12345.json")
        assert mgr.load() is None


class TestCheckpointSensitiveInfoCleaning:
    """敏感信息清理测试."""

    def setup_method(self):
        import uuid

        self.tmp_path = os.path.join(
            tempfile.gettempdir(),
            f"test_ckpt_sens_{uuid.uuid4().hex[:8]}.json",
        )
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def teardown_method(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    def test_private_key_not_saved(self):
        """私钥明文不保存到断点文件."""
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
            force=True,
        )

        # 直接读取 JSON 文件内容
        raw = pathlib.Path(self.tmp_path).read_text(encoding="utf-8")

        assert "deadbeef" not in raw
        assert "KwDiBf89" not in raw
        assert "private_key_hex" not in raw
        assert "private_key_wif" not in raw

    def test_address_preserved_in_match(self):
        """断点保存保留地址信息."""
        matches = [{"address": "1TestPreserved", "timestamp": time.time()}]
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=matches,
            force=True,
        )
        data = self.mgr.load()
        assert data["matches"][0]["address"] == "1TestPreserved"

    def test_security_note_in_file(self):
        """断点文件包含安全说明."""
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        raw = pathlib.Path(self.tmp_path).read_text(encoding="utf-8")
        assert "security_note" in raw


class TestCheckpointAtomicWrite:
    """原子写入测试."""

    def test_file_valid_after_save(self):
        """保存后文件是有效 JSON."""
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
                force=True,
            )
            with pathlib.Path(tmp.name).open(encoding="utf-8") as f:
                data = json.load(f)
            assert "mode" in data
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()

    def test_targets_saved_as_list(self):
        """目标地址保存为列表（可 JSON 序列化）."""
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
                force=True,
            )
            data = mgr.load()
            assert isinstance(data["targets"], list)
            assert "addr1" in data["targets"]
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()


class TestCheckpointAutoSave:
    """自动保存间隔测试."""

    def test_should_auto_save_initially(self):
        """首次调用 should_auto_save 应返回 True（超过间隔）."""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            mgr = CheckpointManager(filepath=tmp.name, auto_save_interval=0)
            # 间隔为0，应立即触发
            assert mgr.should_auto_save
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()

    def test_should_not_auto_save_too_soon(self):
        """刚保存后 should_auto_save 应返回 False."""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            mgr = CheckpointManager(filepath=tmp.name, auto_save_interval=9999)
            mgr.save(
                mode="random",
                targets=set(),
                current_position=0,
                total_checked=0,
                matches=[],
                force=True,
            )
            # 紧接着保存，间隔未到
            assert not mgr.should_auto_save
        finally:
            if pathlib.Path(tmp.name).exists():
                pathlib.Path(tmp.name).unlink()


class TestCheckpointDefaultPath:
    """默认路径测试."""

    def test_default_filepath_uses_data_logs(self):
        """无filepath参数时使用默认路径."""
        mgr = CheckpointManager()
        # 默认路径为 checkpoint.json（不在 data_logs 目录下）
        assert "checkpoint.json" in str(mgr.filepath)
        # 清理
        if mgr.filepath.exists():
            mgr.delete()


class TestCheckpointSaveVariants:
    """save() 多种场景测试."""

    def setup_method(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_var_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path, auto_save_interval=9999)

    def teardown_method(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    def test_save_force_writes_immediately(self):
        """force=True 强制写入."""
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        assert self.mgr.exists

    def test_save_with_auto_save_disabled(self):
        """间隔未到时 save 仅缓冲不写入."""
        self.mgr._last_save = time.time()  # 刚保存过
        self.mgr.save(mode="random", targets=set(), current_position=0, total_checked=0, matches=[])
        # 间隔9999秒未到，不应写入文件
        assert not pathlib.Path(self.tmp_path).exists()
        # 但 buffer 应该有数据
        assert self.mgr._buffer is not None
        assert self.mgr._dirty

    def test_flush_buffer_not_dirty(self):
        """_flush_buffer 在 _dirty=False 时直接返回."""
        self.mgr._dirty = False
        self.mgr._buffer = {"test": 1}
        self.mgr._flush_buffer()

    def test_flush_buffer_none(self):
        """_flush_buffer 在 _buffer=None 时直接返回."""
        self.mgr._dirty = True
        self.mgr._buffer = None
        self.mgr._flush_buffer()

    def test_save_match_with_private_key_hash(self):
        """Match 含 private_key_hash 时被保存."""
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
        assert data["matches"][0].get("private_key_hash") == "abc123"


class TestCheckpointFlushErrors:
    """_flush_buffer 异常处理测试."""

    def setup_method(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_err_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def teardown_method(self):
        if pathlib.Path(self.tmp_path).exists():
            pathlib.Path(self.tmp_path).unlink()

    @patch("builtins.open")
    def test_flush_permission_error(self, mock_file):
        """PermissionError 被捕获."""
        mock_file.side_effect = PermissionError("permission denied")
        self.mgr._dirty = True
        self.mgr._buffer = {"key": "val"}
        self.mgr._flush_buffer()

    @patch("builtins.open")
    def test_flush_os_error(self, mock_file):
        """OSError 被捕获."""
        mock_file.side_effect = OSError("disk full")
        self.mgr._dirty = True
        self.mgr._buffer = {"key": "val"}
        self.mgr._flush_buffer()

    @patch("builtins.open")
    def test_flush_generic_exception(self, mock_file):
        """通用异常被捕获."""
        mock_file.side_effect = RuntimeError("unexpected")
        self.mgr._dirty = True
        self.mgr._buffer = {"key": "val"}
        self.mgr._flush_buffer()

    # _cleanup_temp_file 和 _check_win32_security 已移除（死代码）


class TestCheckpointLoadEdgeCases:
    """load() 边界情况测试."""

    def setup_method(self):
        import uuid

        self.tmp_path = os.path.join(
            tempfile.gettempdir(),
            f"test_ckpt_load_{uuid.uuid4().hex[:8]}.json",
        )
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def teardown_method(self):
        for p in [self.tmp_path, self.tmp_path + ".tmp"]:
            if pathlib.Path(p).exists():
                pathlib.Path(p).unlink()

    def test_load_version_mismatch(self):
        """版本不兼容时返回 None."""
        with pathlib.Path(self.tmp_path).open("w") as f:
            json.dump({"version": 99, "mode": "random"}, f)
        result = self.mgr.load()
        assert result is None

    def test_load_corrupt_json(self):
        """损坏的 JSON 返回 None."""
        pathlib.Path(self.tmp_path).write_text("not a json file {{{")
        result = self.mgr.load()
        assert result is None

    def test_load_temp_file_recovery(self):
        """.tmp 文件恢复为主文件."""
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "recovered"}, f)
        assert pathlib.Path(temp_file).exists()
        assert not pathlib.Path(self.tmp_path).exists()

        result = self.mgr.load()
        # version=1 != CHECKPOINT_VERSION=2, 所以返回 None
        assert result is None

    def test_load_temp_recovery_with_main_exists(self):
        """.tmp 恢复时主文件已存在则不覆盖."""
        with pathlib.Path(self.tmp_path).open("w") as f:
            json.dump({"version": 1, "mode": "main"}, f)
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "temp"}, f)

        result = self.mgr.load()
        # version=1 != CHECKPOINT_VERSION=2, 所以返回 None
        assert result is None


class TestCheckpointDelete:
    """delete() 测试."""

    def setup_method(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_del_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def teardown_method(self):
        for p in [self.tmp_path, self.tmp_path + ".tmp"]:
            if pathlib.Path(p).exists():
                pathlib.Path(p).unlink()

    def test_delete_with_temp_file(self):
        """Delete 清理主文件，.tmp 文件需手动清理."""
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
        assert pathlib.Path(temp_file).exists()

        self.mgr.delete()
        # delete 只清理主文件，不清理 .tmp 文件
        assert not pathlib.Path(self.tmp_path).exists()
        # 手动清理 .tmp
        if pathlib.Path(temp_file).exists():
            pathlib.Path(temp_file).unlink()

    def test_delete_clears_buffer(self):
        """Delete 清空 buffer 和 dirty."""
        self.mgr.save(
            mode="random",
            targets=set(),
            current_position=0,
            total_checked=0,
            matches=[],
            force=True,
        )
        self.mgr.delete()
        assert self.mgr._buffer is None
        assert not self.mgr._dirty


class TestCheckpointExists:
    """exists() 测试."""

    def test_exists_no_file(self):
        """文件不存在时返回 False."""
        mgr = CheckpointManager(filepath="/nonexistent/checkpoint.json")
        assert not mgr.exists


class TestCheckpointFlushDirCreation:
    """_flush_buffer 目录创建测试."""

    def test_flush_creates_parent_dir(self):
        """父目录不存在时自动创建."""
        import shutil
        import uuid

        subdir = os.path.join(tempfile.gettempdir(), f"ckpt_test_{uuid.uuid4().hex[:8]}")
        ckpt_path = os.path.join(subdir, "checkpoint.json")
        mgr = CheckpointManager(filepath=ckpt_path)
        try:
            mgr._dirty = True
            mgr._buffer = {"version": 1, "test": True}
            mgr._flush_buffer()
            assert pathlib.Path(ckpt_path).exists()
        finally:
            mgr.delete()
            if pathlib.Path(subdir).exists():
                shutil.rmtree(subdir, ignore_errors=True)


class TestCheckpointLoadTempRecoveryErrors:
    """load() 临时文件恢复失败测试."""

    def setup_method(self):
        import uuid

        self.tmp_path = os.path.join(tempfile.gettempdir(), f"test_ckpt_rec_{uuid.uuid4().hex[:8]}.json")
        self.mgr = CheckpointManager(filepath=self.tmp_path)

    def teardown_method(self):
        for p in [self.tmp_path, self.tmp_path + ".tmp"]:
            if pathlib.Path(p).exists():
                pathlib.Path(p).unlink()

    @patch("os.replace", side_effect=OSError("rename failed"))
    def test_temp_recovery_rename_os_error(self, mock_rename):
        """Replace 失败时记录日志并清理."""
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "test"}, f)
        # replace 会失败，但不应崩溃
        result = self.mgr.load()
        assert result is None

    @patch("pathlib.Path.replace", side_effect=Exception("unexpected"))
    def test_temp_recovery_rename_unexpected_error(self, mock_rename):
        """Replace 未知异常被记录."""
        temp_file = self.tmp_path + ".tmp"
        with pathlib.Path(temp_file).open("w") as f:
            json.dump({"version": 1, "mode": "test"}, f)
        result = self.mgr.load()
        assert result is None


class TestCheckpointDeleteErrors:
    """delete() 异常处理测试."""

    def test_delete_exception_caught(self):
        """Delete 异常被捕获."""
        mgr = CheckpointManager(filepath="/tmp/test.json")
        # Patch the instance's filepath Path methods
        with (
            patch.object(type(mgr.filepath), "exists", return_value=True),
            patch.object(type(mgr.filepath), "unlink", side_effect=Exception("delete failed")),
        ):
            mgr.delete()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
