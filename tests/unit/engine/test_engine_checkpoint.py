"""KeyCollisionEngine 断点测试 (MAINT-1拆分)

原 file: test_key_collision_engine.py
抽取类: TestKeyCollisionEngineP3Checkpoint
"""

import json
import os
import pathlib
import shutil
import tempfile
import time

from src.collision.key_collision_engine import KeyCollisionEngine


class TestKeyCollisionEngineP3Checkpoint:
    """P3: Checkpoint 持久化：resume_from / start_from / start resume"""

    def setUp(self):
        self._ckpt_dir = tempfile.mkdtemp(prefix="test_ckpt_")
        self._ckpt_path = os.path.join(self._ckpt_dir, "checkpoint.json")

    def tearDown(self):
        shutil.rmtree(self._ckpt_dir, ignore_errors=True)

    def _create_checkpoint(self, mode="range", current_position=100, total_checked=500, range_end=1000):
        data = {
            "version": 2,
            "timestamp": "2026-05-03T00:00:00",
            "mode": mode,
            "targets": ["1TestAddr"],
            "current_position": current_position,
            "total_checked": total_checked,
            "matches": [],
            "range_start": 1,
            "range_end": range_end,
        }
        pathlib.Path(os.path.dirname(self._ckpt_path)).mkdir(exist_ok=True, parents=True)
        with pathlib.Path(self._ckpt_path).open("w") as f:
            json.dump(data, f)

    def test_resume_from_checkpoint_no_file(self):
        """无断点文件时返回 None"""
        from src.collision.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.checkpoint_mgr = mgr
        result = engine.resume_from_checkpoint()
        assert result is None
        engine.stop()

    def test_resume_from_checkpoint_range(self):
        """从 range 模式断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="range", current_position=100, total_checked=500, range_end=1000)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.checkpoint_mgr = mgr
        result = engine.resume_from_checkpoint()
        assert result is not None
        assert result["mode"] == "range"
        assert engine.stats.total_checked == 500
        engine.stop()

    def test_resume_from_checkpoint_brute_force(self):
        """从 brute_force 模式断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(
            mode="brute_force",
            current_position=200,
            total_checked=300,
            range_end=None,
        )
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.checkpoint_mgr = mgr
        result = engine.resume_from_checkpoint()
        assert result is not None
        assert result["mode"] == "brute_force"
        engine.stop()

    def test_start_from_checkpoint_range(self):
        """start_from_checkpoint range 模式"""
        data = {"mode": "range", "current_position": 50, "range_end": 500000}
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start_from_checkpoint(data)
        time.sleep(0.3)
        assert engine.is_running()
        engine.stop()

    def test_start_from_checkpoint_brute_force(self):
        """start_from_checkpoint brute_force 模式"""
        data = {"mode": "brute_force", "current_position": 50}
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start_from_checkpoint(data)
        time.sleep(0.3)
        assert engine.is_running()
        engine.stop()

    def test_start_from_checkpoint_random(self):
        """start_from_checkpoint random 模式"""
        data = {"mode": "random"}
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start_from_checkpoint(data)
        time.sleep(0.2)
        assert engine.is_running()
        engine.stop()

    def test_start_resume_from_range_checkpoint(self):
        """start(resume=True) 从 range 断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="range", current_position=1, total_checked=0, range_end=500000)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="range", resume=True, start=1, end=1000)
        time.sleep(0.3)
        assert engine.is_running()
        engine.stop()

    def test_start_resume_from_brute_force_checkpoint(self):
        """start(resume=True) 从 brute_force 断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="brute_force", current_position=1, total_checked=0, range_end=None)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="brute_force", resume=True, start=1, max_keys=5)
        time.sleep(0.5)
        assert engine.is_running()
        engine.stop()

    def test_start_resume_from_random_checkpoint(self):
        """start(resume=True) 从 random 断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="random", current_position=0, total_checked=100, range_end=None)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="random", resume=True)
        time.sleep(0.2)
        assert engine.is_running()
        engine.stop()

    def test_start_resume_checkpoint_load_failure(self):
        """start(resume=True) 断点加载失败时回退到正常启动"""
        from src.collision.checkpoint_manager import CheckpointManager

        class FailingCheckpointManager(CheckpointManager):
            def load(self):
                raise RuntimeError("模拟加载失败")

        mgr = FailingCheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="random", resume=True)
        time.sleep(0.2)
        assert engine.is_running(), "断点加载失败应回退到正常启动"
        engine.stop()
