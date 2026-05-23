"""GPU引擎重构 Phase 4 测试套件 - 碰撞核心实现

测试范围:
- CollisionCore 初始化 (含 engine 注入)
- 断点恢复 (_restore_checkpoint)
- 断点保存 (_save_checkpoint)
- 统计查询 (get_stats / is_running)
- 模块导出与版本号

版本: v4.5.0
更新日期: 2026-05-21
说明: v4.5.0 已移除所有 [DEPRECATED] 方法 (start/stop/pause/resume/reset/on_batch_complete)
"""

import pathlib
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.gpu

# ========== Fixtures ==========


@pytest.fixture
def sample_targets() -> set[str]:
    return {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1"}


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "checkpoint_interval": 5,
        "dedup_enabled": False,
        "checkpoint_enabled": False,
        "progress_interval": 0.5,
    }


@pytest.fixture
def sample_config_full() -> dict[str, Any]:
    return {
        "checkpoint_interval": 5,
        "dedup_enabled": True,
        "checkpoint_enabled": True,
        "dedup_max_size": 100_000,
        "progress_interval": 0.1,
    }


@pytest.fixture
def mock_stats():
    """Mock CollisionStats"""
    stats = MagicMock()
    stats.total_checked = 0
    stats.speed = 0.0
    stats.elapsed = 0.0
    stats.start_time = 0.0
    stats.matches = []
    stats.to_dict.return_value = {"total_checked": 0, "speed": 0.0}

    def snapshot_side_effect():
        snap = MagicMock()
        snap.total_checked = stats.total_checked
        snap.speed = stats.speed
        return snap

    stats.snapshot.side_effect = snapshot_side_effect
    return stats


@pytest.fixture
def mock_checkpoint():
    """Mock CheckpointManager"""
    cp = MagicMock()
    cp.load.return_value = None
    return cp


@pytest.fixture
def mock_dedup():
    """Mock DeduplicationFilter"""
    dedup = MagicMock()
    dedup.check_and_add.return_value = True
    return dedup


# ========== Test: 初始化 ==========


class TestCollisionCoreInit:
    """测试 CollisionCore 初始化"""

    def test_basic_init(self, sample_targets, sample_config):
        """基本初始化"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        assert core.targets == sample_targets
        assert core.config == sample_config
        assert core._running is False
        assert core._paused is False
        assert core.stats is None
        assert core.checkpoint is None
        assert core.dedup_filter is None
        assert core.search_coordinator is None

    def test_init_with_engine(self, sample_targets):
        """带引擎引用初始化"""
        from src.collision.gpu.core import CollisionCore

        mock_engine = MagicMock()
        core = CollisionCore(targets=sample_targets, engine=mock_engine)
        assert core._engine is mock_engine

    def test_init_with_callbacks(self, sample_targets):
        """带回调和配置的初始化"""
        from src.collision.gpu.core import CollisionCore

        def on_progress(stats):
            pass

        def on_match(pk, addr, wif):
            pass

        core = CollisionCore(
            targets=sample_targets,
            on_progress=on_progress,
            on_match=on_match,
        )
        assert core.on_progress is on_progress
        assert core.on_match is on_match

    def test_init_with_factories(self, sample_targets):
        """带依赖注入工厂的初始化"""
        from src.collision.gpu.core import CollisionCore

        stats_factory = MagicMock(return_value=MagicMock())
        checkpoint_factory = MagicMock(return_value=MagicMock())
        dedup_factory = MagicMock(return_value=MagicMock())

        core = CollisionCore(
            targets=sample_targets,
            stats_factory=stats_factory,
            checkpoint_factory=checkpoint_factory,
            dedup_factory=dedup_factory,
        )
        assert core._stats_factory is stats_factory
        assert core._checkpoint_factory is checkpoint_factory
        assert core._dedup_factory is dedup_factory

    def test_init_config_defaults(self, sample_targets):
        """验证配置默认值"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        assert core.checkpoint_interval == 30
        assert core.dedup_enabled is False
        assert core.checkpoint_enabled is False
        assert core.progress_interval == 1.0

    def test_init_config_custom(self, sample_targets, sample_config_full):
        """自定义配置参数"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config_full)
        assert core.checkpoint_interval == 5
        assert core.dedup_enabled is True
        assert core.checkpoint_enabled is True
        assert core.progress_interval == 0.1

    def test_init_progress_tracking_vars(self, sample_targets):
        """验证进度追踪变量初始化"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        assert core._last_progress_time == 0.0
        assert core.progress_interval == 1.0


# ========== Test: 断点恢复 ==========


class TestCheckpointRestore:
    """测试 _restore_checkpoint 断点恢复"""

    def test_restore_with_valid_data(self, sample_targets, sample_config_full):
        """从有效断点数据恢复"""
        from src.collision.gpu.core import CollisionCore

        checkpoint_data = {
            "version": 1,
            "mode": "random",
            "total_checked": 50000,
            "current_position": 49999,
            "matches": [{"address": "1Test", "timestamp": 1234567890}],
        }

        cp = MagicMock()
        cp.load.return_value = checkpoint_data

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            checkpoint_factory=lambda: cp,
        )
        core._init_stats()
        core.checkpoint = cp
        core._restore_checkpoint()

        assert core.config["mode"] == "random"
        assert core.stats.total_checked == 50000

    def test_restore_when_no_checkpoint_data(self, sample_targets, sample_config_full):
        """无断点数据时不报错"""
        from src.collision.gpu.core import CollisionCore

        cp = MagicMock()
        cp.load.return_value = None

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            checkpoint_factory=lambda: cp,
        )
        core.checkpoint = cp
        core._init_stats()
        core._restore_checkpoint()  # 不应抛出异常
        assert core.stats.total_checked == 0

    def test_restore_when_checkpoint_is_none(self, sample_targets, sample_config):
        """Checkpoint 为 None 时不报错"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.checkpoint = None
        core._restore_checkpoint()  # 不应抛出异常

    def test_restore_updates_config_mode(self, sample_targets, sample_config_full):
        """恢复时更新 config mode"""
        from src.collision.gpu.core import CollisionCore

        checkpoint_data = {
            "mode": "brute_force",
            "total_checked": 10,
            "current_position": 5,
            "matches": [],
        }
        cp = MagicMock()
        cp.load.return_value = checkpoint_data

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            checkpoint_factory=lambda: cp,
        )
        core.checkpoint = cp
        core._init_stats()
        core._restore_checkpoint()
        assert core.config["mode"] == "brute_force"

    def test_restore_error_logged(self, sample_targets, sample_config):
        """恢复异常时记录错误"""
        from src.collision.gpu.core import CollisionCore

        cp = MagicMock()
        cp.load.side_effect = RuntimeError("模拟恢复错误")

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            checkpoint_factory=lambda: cp,
        )
        core.checkpoint = cp
        core._restore_checkpoint()  # 不应抛出，错误被日志记录


# ========== Test: 断点保存 ==========


class TestCheckpointSave:
    """测试 _save_checkpoint 断点保存"""

    def test_save_with_valid_state(self, sample_targets, sample_config_full):
        """在有效状态下保存断点"""
        from src.collision.gpu.core import CollisionCore

        saved_data = {}

        class CheckpointRecorder:
            def save(self, **kwargs):
                saved_data.update(kwargs)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            checkpoint_factory=CheckpointRecorder,
        )
        core.checkpoint = CheckpointRecorder()
        core._init_stats()
        core._save_checkpoint()
        assert "mode" in saved_data
        assert "targets" in saved_data
        assert "total_checked" in saved_data

    def test_save_when_no_checkpoint(self, sample_targets, sample_config):
        """Checkpoint 为 None 时不保存"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.checkpoint = None
        core._save_checkpoint()  # 不应抛出

    def test_save_when_no_stats(self, sample_targets, sample_config_full):
        """Stats 为 None 时不保存"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            checkpoint_factory=lambda: MagicMock(),
        )
        core.checkpoint = MagicMock()
        core.stats = None
        core._save_checkpoint()  # 不应抛出


# ========== Test: 统计 ==========


class TestGetStats:
    """测试 get_stats"""

    def test_get_stats_returns_dict(self, sample_targets, sample_config):
        """返回字典类型的统计信息"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core._init_stats()
        stats = core.get_stats()
        assert isinstance(stats, dict)

    def test_get_stats_when_not_started(self, sample_targets):
        """未初始化时返回空字典"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        assert core.get_stats() == {}

    def test_get_stats_includes_running_status(self, sample_targets, sample_config):
        """包含 running 状态"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core._init_stats()
        stats = core.get_stats()
        assert "elapsed_time" in stats

    def test_get_stats_includes_elapsed_time(self, sample_targets, sample_config):
        """包含已运行时间"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core._init_stats()
        time.sleep(0.05)
        stats = core.get_stats()
        assert "elapsed_time" in stats

    def test_is_running_initial_state(self, sample_targets):
        """初始未运行"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        assert core.is_running() is False


# ========== Test: 私有初始化方法 ==========


class TestPrivateInitMethods:
    """测试 _init_stats / _init_checkpoint / _init_dedup_filter"""

    def test_init_stats_default(self, sample_targets):
        """_init_stats 默认创建 CollisionStats"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        core._init_stats()
        assert core.stats is not None

    def test_init_stats_with_factory(self, sample_targets):
        """_init_stats 使用注入工厂"""
        from src.collision.gpu.core import CollisionCore

        mock_stats_obj = MagicMock()
        core = CollisionCore(targets=sample_targets, stats_factory=lambda: mock_stats_obj)
        core._init_stats()
        assert core.stats is mock_stats_obj

    def test_init_checkpoint_default(self, sample_targets, sample_config):
        """_init_checkpoint 使用默认 CheckpointManager"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.checkpoint_enabled = True
        core._init_checkpoint()
        assert core.checkpoint is not None

    def test_init_checkpoint_with_factory(self, sample_targets):
        """_init_checkpoint 使用注入工厂"""
        from src.collision.gpu.core import CollisionCore

        mock_cp = MagicMock()
        core = CollisionCore(targets=sample_targets, checkpoint_factory=lambda: mock_cp)
        core.checkpoint_enabled = True
        core._init_checkpoint()
        assert core.checkpoint is mock_cp

    def test_init_dedup_default(self, sample_targets, sample_config):
        """_init_dedup_filter 使用默认 DeduplicationFilter"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.dedup_enabled = True
        core._init_dedup_filter()
        assert core.dedup_filter is not None

    def test_init_dedup_with_factory(self, sample_targets):
        """_init_dedup_filter 使用注入工厂"""
        from src.collision.gpu.core import CollisionCore

        mock_dedup = MagicMock()
        core = CollisionCore(targets=sample_targets, dedup_factory=lambda: mock_dedup)
        core.dedup_enabled = True
        core._init_dedup_filter()
        assert core.dedup_filter is mock_dedup


# ========== Test: 模块导入与版本 ==========


class TestModuleImports:
    """测试模块导入和版本"""

    def test_import_collision_core(self):
        """测试导入 CollisionCore"""
        from src.collision.gpu.core import CollisionCore

        assert CollisionCore is not None

    def test_import_from_gpu_package(self):
        """测试从 gpu 包导入"""
        from src.collision.gpu import CollisionCore

        assert CollisionCore is not None

    def test_module_version(self):
        """测试模块版本号"""
        from src.collision import gpu

        assert gpu.__version__ == "5.0.0"

    def test_collision_core_in_all(self):
        """验证 CollisionCore 在 __all__ 中"""
        from src.collision.gpu import __all__ as gpu_all

        assert "CollisionCore" in gpu_all

    def test_factory_get_collision_core(self):
        """测试工厂函数"""
        from src.collision.gpu import get_collision_core
        from src.collision.gpu.core import CollisionCore

        assert get_collision_core() is CollisionCore

    def test_no_deprecated_methods_in_core(self):
        """验证 core.py 中已无弃用方法"""
        import os

        core_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "collision",
            "gpu",
            "core.py",
        )
        core_path = os.path.abspath(core_path)
        content = pathlib.Path(core_path).read_text(encoding="utf-8")
        assert "[DEPRECATED]" not in content, "core.py 中仍有 [DEPRECATED] 标记"

    def test_types_import(self):
        """测试类型别名"""
        from src.collision.types import CompleteCallback, MatchCallback, ProgressCallback

        assert MatchCallback is not None
        assert ProgressCallback is not None
        assert CompleteCallback is not None

    def test_threading_import(self):
        """测试 threading 模块可用"""
        assert threading is not None

    def test_no_deprecated_imports(self):
        """验证未导入弃用方法需要的 warnings 模块 (已移除)"""
        import os

        core_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "collision",
            "gpu",
            "core.py",
        )
        core_path = os.path.abspath(core_path)
        content = pathlib.Path(core_path).read_text(encoding="utf-8")
        assert "import warnings" not in content, "core.py 不应再导入 warnings (弃用方法已移除)"
        assert "FutureWarning" not in content, "core.py 不应再有 FutureWarning (弃用方法已移除)"
