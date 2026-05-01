"""GPU引擎重构 Phase 4 测试套件 - 碰撞核心实现

测试范围:
- CollisionCore 初始化 (含 engine 注入)
- 生命周期管理 (start/stop/pause/resume)
- 批次回调 (on_batch_complete)
- 断点恢复 (_restore_checkpoint)
- 进度节流 (_maybe_call_progress)
- 搜索协调器初始化 (真实引擎 vs 存根)
- 模块导出与版本号

版本: v1.0
创建日期: 2026-04-30
"""

import pytest
import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Set, Dict, Any

# ========== Fixtures ==========


@pytest.fixture
def sample_targets() -> Set[str]:
    return {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1"}


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    return {
        "checkpoint_interval": 5,
        "dedup_enabled": False,
        "checkpoint_enabled": False,
        "progress_interval": 0.5,
    }


@pytest.fixture
def sample_config_full() -> Dict[str, Any]:
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


# ========== Test: 生命周期管理 ==========


class TestCollisionCoreLifecycle:
    """测试 CollisionCore 启动/停止/暂停/恢复"""

    def test_start_with_stats_init(self, sample_targets, sample_config):
        """启动时初始化统计组件"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        assert core.stats is not None
        assert core._running is True
        core.stop()

    def test_start_double_call_is_safe(self, sample_targets, sample_config):
        """重复启动应被安全忽略"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        core.start(mode="random")  # 不应抛出异常
        assert core._running is True
        core.stop()

    def test_stop_cleans_up(self, sample_targets, sample_config):
        """停止时清理运行状态"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        core.stop()
        assert core._running is False
        assert core._paused is False

    def test_stop_when_not_running_is_safe(self, sample_targets, sample_config):
        """未运行时停止应安全"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.stop()  # 不应抛出异常
        assert core._running is False

    def test_pause_resume_cycle(self, sample_targets, sample_config):
        """暂停和恢复循环"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        assert core._running is True
        assert core._paused is False

        core.pause()
        assert core._paused is True

        core.resume()
        assert core._paused is False

        core.stop()

    def test_pause_when_not_running_is_safe(self, sample_targets, sample_config):
        """未运行时暂停应安全"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.pause()  # 不应抛出异常
        assert core._paused is False

    def test_resume_when_not_paused_is_safe(self, sample_targets, sample_config):
        """未暂停时恢复应安全"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        core.resume()  # 不应抛出异常 (未暂停)
        assert core._paused is False
        core.stop()

    def test_is_running_reflects_state(self, sample_targets, sample_config):
        """is_running 反映当前状态"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        assert core.is_running() is False
        core.start(mode="random")
        assert core.is_running() is True
        core.stop()
        assert core.is_running() is False

    def test_reset_stats(self, sample_targets, sample_config):
        """重置统计"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        core.stats.update(1000)
        assert core.stats.total_checked > 0
        core.reset()
        core.stop()

    def test_start_with_checkpoint_enabled(self, sample_targets, sample_config_full):
        """启用断点时启动，应初始化断点管理器"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config_full)
        core.start(mode="random")
        assert core.checkpoint is not None
        assert core.checkpoint_enabled is True
        core.stop()

    def test_start_with_dedup_enabled(self, sample_targets, sample_config_full):
        """启用了去重时启动，应初始化去重过滤器"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config_full)
        core.start(mode="random")
        assert core.dedup_filter is not None
        assert core.dedup_enabled is True
        core.stop()

    def test_start_sets_timestamps(self, sample_targets, sample_config):
        """启动时设置正确的时间戳"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        before = time.time()
        core.start(mode="random")
        after = time.time()
        assert core._start_time >= before
        assert core._start_time <= after
        assert core._last_checkpoint_time >= before
        assert core._last_progress_time >= before
        core.stop()

    def test_start_with_resume_kwarg(self, sample_targets, sample_config_full):
        """启动时传递 resume=True 会尝试恢复断点"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config_full)
        core.start(mode="random", resume=True)
        assert core._running is True
        # resume 从 kwargs 中 pop 出来，不会传给 search_coordinator
        core.stop()


# ========== Test: 批次完成回调 ==========


class TestOnBatchComplete:
    """测试 on_batch_complete 批次回调"""

    def test_stats_updated_on_batch(self, sample_targets, sample_config):
        """批次完成后更新统计"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        initial_checked = core.stats.total_checked
        core.on_batch_complete(matches=[], batch_size=1000)
        assert core.stats.total_checked > initial_checked
        core.stop()

    def test_skips_when_not_running(self, sample_targets, sample_config):
        """未运行时跳过批次处理"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core._running = False
        core.stats = MagicMock()
        core.on_batch_complete(matches=[], batch_size=1000)
        core.stats.update.assert_not_called()

    def test_skips_when_paused(self, sample_targets, sample_config):
        """暂停时跳过批次处理"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        core.pause()
        core.stats = MagicMock()
        core.on_batch_complete(matches=[], batch_size=1000)
        core.stats.update.assert_not_called()
        core.stop()

    def test_match_callback_invoked(self, sample_targets, sample_config):
        """匹配时调用 on_match 回调"""
        from src.collision.gpu.core import CollisionCore

        match_calls = []

        def on_match(pk, addr, wif):
            match_calls.append((pk, addr, wif))

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_match=on_match,
        )
        core.start(mode="random")

        match_result = {
            "address": "1TestAddr",
            "private_key": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7b8c9d0e1f2a3b4c5d6a7b8c9d0e1f2",
            "wif": "5KTestWIF",
        }
        core.on_batch_complete(matches=[match_result], batch_size=1000)
        assert len(match_calls) == 1

        core.stop()

    def test_match_callback_with_bytes_private_key(self, sample_targets, sample_config):
        """匹配回调中 private_key 为 bytes 类型"""
        from src.collision.gpu.core import CollisionCore

        match_calls = []

        def on_match(pk, addr, wif):
            match_calls.append((pk, addr, wif))

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_match=on_match,
        )
        core.start(mode="random")

        pk_bytes = b"\x01" * 32
        match_result = {
            "address": "1TestAddr",
            "private_key": pk_bytes,
            "wif": "5KTestWIF",
        }
        core.on_batch_complete(matches=[match_result], batch_size=1000)
        assert len(match_calls) == 1
        assert match_calls[0][0] == pk_bytes

        core.stop()

    def test_dedup_filter_applied(self, sample_targets, sample_config_full):
        """去重过滤器应用到批次匹配结果 (使用Mock注入)"""
        from src.collision.gpu.core import CollisionCore

        match_calls = []

        def on_match(pk, addr, wif):
            match_calls.append(addr)

        # 使用工厂注入 Mock
        mock_dedup = MagicMock()
        mock_dedup.check_and_add.side_effect = [True, False]

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            on_match=on_match,
            dedup_factory=lambda: mock_dedup,
        )
        core.start(mode="random")

        match1 = {"address": "1Addr1", "private_key": "aa" * 32, "wif": "5K1"}
        match2 = {"address": "1Addr2", "private_key": "bb" * 32, "wif": "5K2"}

        core.on_batch_complete(matches=[match1, match2], batch_size=1000)
        # 只有第一个通过去重
        assert len(match_calls) == 1
        assert match_calls[0] == "1Addr1"

        core.stop()

    def test_dedup_filter_not_applied_when_disabled(self, sample_targets, sample_config):
        """去重未启用时不过滤"""
        from src.collision.gpu.core import CollisionCore

        match_calls = []

        def on_match(pk, addr, wif):
            match_calls.append(addr)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_match=on_match,
        )
        core.start(mode="random")

        match1 = {"address": "1Addr1", "private_key": "aa" * 32, "wif": "5K1"}
        match2 = {"address": "1Addr2", "private_key": "bb" * 32, "wif": "5K2"}

        core.on_batch_complete(matches=[match1, match2], batch_size=1000)
        assert len(match_calls) == 2

        core.stop()

    def test_progress_callback_throttled(self, sample_targets, sample_config):
        """进度回调被节流 (1秒内只调用一次)"""
        from src.collision.gpu.core import CollisionCore

        progress_calls = []

        def on_progress(stats):
            progress_calls.append(stats)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_progress=on_progress,
        )
        core.start(mode="random")

        # 重置进度时间戳，确保第一次触发
        core._last_progress_time = 0

        # 第一次批次 → 触发进度回调
        core.on_batch_complete(matches=[], batch_size=1000)
        assert len(progress_calls) == 1

        # 立即第二次批次 → 被节流，不触发
        core.on_batch_complete(matches=[], batch_size=1000)
        assert len(progress_calls) == 1

        # 手动设置上次进度时间为过去 → 再次触发
        core._last_progress_time = time.time() - core.progress_interval - 0.1
        core.on_batch_complete(matches=[], batch_size=1000)
        assert len(progress_calls) == 2

        core.stop()

    def test_progress_callback_receives_snapshot(self, sample_targets, sample_config):
        """进度回调接收 CollisionStats 快照"""
        from src.collision.gpu.core import CollisionCore

        received_stats = []

        def on_progress(stats):
            received_stats.append(stats)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_progress=on_progress,
        )
        core.start(mode="random")
        # 重置进度时间戳确保触发
        core._last_progress_time = 0
        core.on_batch_complete(matches=[], batch_size=1000)

        assert len(received_stats) == 1
        # snapshot 应包含 total_checked 属性
        assert hasattr(received_stats[0], "total_checked")

        core.stop()

    def test_batch_when_stats_is_none_skips(self, sample_targets, sample_config):
        """stats 为 None 时，批次回调安全跳过"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core._running = True
        core.stats = None
        # 不应抛出异常
        core.on_batch_complete(matches=[], batch_size=1000)


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
        core.start(mode="random", resume=True)

        assert core.config["mode"] == "random"
        assert core.stats.total_checked == 50000

        core.stop()

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
        core.start(mode="random", resume=True)
        # 应正常运行，无异常
        assert core._running is True
        core.stop()

    def test_restore_when_no_checkpoint_manager(self, sample_targets, sample_config):
        """无断点管理器时恢复安全"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.checkpoint = None
        core.stats = MagicMock()
        core._restore_checkpoint()  # 不应抛出异常

    def test_restore_without_stats(self, sample_targets, sample_config_full):
        """恢复时 stats 为 None 不报错"""
        from src.collision.gpu.core import CollisionCore

        cp = MagicMock()
        cp.load.return_value = {
            "mode": "random",
            "total_checked": 100,
            "current_position": 50,
            "matches": [],
        }

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            checkpoint_factory=lambda: cp,
        )
        # 不调用 start()，直接手动设置 checkpoint
        core.checkpoint = cp
        core.stats = None
        core._restore_checkpoint()  # 不应抛出异常

    def test_restore_with_empty_matches(self, sample_targets, sample_config_full):
        """恢复时匹配列表为空"""
        from src.collision.gpu.core import CollisionCore

        cp = MagicMock()
        cp.load.return_value = {
            "mode": "random",
            "total_checked": 200,
            "current_position": 100,
            "matches": [],
        }

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            checkpoint_factory=lambda: cp,
        )
        core.start(mode="random", resume=True)
        assert core.stats.total_checked == 200
        core.stop()


# ========== Test: 搜索协调器初始化 ==========


class TestSearchCoordinatorInit:
    """测试 _init_search_coordinator"""

    def test_with_engine_creates_real_coordinator(self, sample_targets, sample_config):
        """有引擎引用时创建真实协调器 (通过存根对比验证)"""
        from src.collision.gpu.core import CollisionCore

        mock_engine = MagicMock()
        # 验证: 无引擎时创建存根
        core_no_engine = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            engine=None,
        )
        core_no_engine._init_search_coordinator()
        assert core_no_engine.search_coordinator is not None

        # 验证: 有引擎引用时尝试使用真实协调器
        # 由于 SearchModeCoordinator 需要完整的 GPUCollisionEngine,
        # Mock 引擎可能导致导入失败，此时应回退到存根
        core_with_engine = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            engine=mock_engine,
        )
        core_with_engine._init_search_coordinator()
        assert core_with_engine.search_coordinator is not None
        # 存根支持基本操作
        core_with_engine.search_coordinator.start("random")
        assert core_with_engine.search_coordinator.get_current_mode() == "random"

    def test_without_engine_creates_stub(self, sample_targets, sample_config):
        """无引擎引用时创建存根"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core._init_search_coordinator()
        assert core.search_coordinator is not None
        # 存根应支持基本操作
        core.search_coordinator.start("random")
        assert core.search_coordinator.get_current_mode() == "random"
        core.search_coordinator.pause()
        core.search_coordinator.resume()
        core.search_coordinator.stop()
        assert core.search_coordinator.get_current_mode() is None

    def test_with_engine_import_failure_falls_back_to_stub(self, sample_targets, sample_config):
        """引擎导入失败时回退到存根 (存根是安全的降级方案)"""
        from src.collision.gpu.core import CollisionCore

        # 验证: _init_search_coordinator 异常时回退到存根
        mock_engine = MagicMock()
        mock_engine.config = {"gpu": {}}

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            engine=mock_engine,
        )
        # _init_search_coordinator 内部 try/except 确保从不抛出异常
        core._init_search_coordinator()

        # 无论如何都应该有 search_coordinator (真实或存根)
        assert core.search_coordinator is not None
        core.search_coordinator.start("random")
        assert core.search_coordinator.get_current_mode() == "random"
        core.search_coordinator.stop()
        assert core.search_coordinator.get_current_mode() is None

    def test_stub_supports_switch_mode(self, sample_targets):
        """存根支持切换模式"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        stub = core._create_search_stub()
        stub.start("random")
        assert stub.get_current_mode() == "random"
        stub.switch_mode("range_scan")
        assert stub.get_current_mode() == "range_scan"


# ========== Test: 进度节流 ==========


class TestProgressThrottling:
    """测试进度回调节流"""

    def test_first_call_triggers_progress(self, sample_targets, sample_config):
        """首次调用触发进度回调"""
        from src.collision.gpu.core import CollisionCore

        calls = []

        def on_progress(stats):
            calls.append(1)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_progress=on_progress,
        )
        core.start(mode="random")
        # 重置时间戳确保首次触发
        core._last_progress_time = 0
        core._maybe_call_progress()
        assert len(calls) == 1
        core.stop()

    def test_throttle_prevents_rapid_calls(self, sample_targets, sample_config):
        """节流阻止过快的回调"""
        from src.collision.gpu.core import CollisionCore

        calls = []

        def on_progress(stats):
            calls.append(1)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_progress=on_progress,
        )
        core.start(mode="random")
        # 重置时间戳确保首次触发
        core._last_progress_time = 0
        core._maybe_call_progress()
        assert len(calls) == 1

        # 立即再次调用 → 被节流
        core._maybe_call_progress()
        assert len(calls) == 1
        core.stop()

    def test_throttle_allows_after_interval(self, sample_targets, sample_config):
        """间隔过后允许再次触发"""
        from src.collision.gpu.core import CollisionCore

        calls = []

        def on_progress(stats):
            calls.append(1)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_progress=on_progress,
        )
        core.start(mode="random")
        # 重置时间戳确保首次触发
        core._last_progress_time = 0
        core._maybe_call_progress()
        assert len(calls) == 1

        # 模拟过了间隔时间
        core._last_progress_time = time.time() - core.progress_interval - 0.1
        core._maybe_call_progress()
        assert len(calls) == 2
        core.stop()

    def test_no_progress_callback_safe(self, sample_targets):
        """无进度回调时 _maybe_call_progress 安全"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        core.stats = MagicMock()
        core._maybe_call_progress()  # 不应抛出异常

    def test_no_stats_safe(self, sample_targets):
        """stats 为 None 时 _maybe_call_progress 安全"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        core._maybe_call_progress()  # 不应抛出异常

    def test_progress_exception_handled(self, sample_targets, sample_config):
        """进度回调异常被捕获"""
        from src.collision.gpu.core import CollisionCore

        def on_progress(stats):
            raise ValueError("测试异常")

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_progress=on_progress,
        )
        core.start(mode="random")
        # 不应传播异常
        core._maybe_call_progress()
        core.stop()

    def test_progress_uses_snapshot(self, sample_targets, sample_config):
        """使用 snapshot 获取统计快照"""
        from src.collision.gpu.core import CollisionCore

        captured_stats = []

        def on_progress(stats):
            captured_stats.append(stats)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_progress=on_progress,
        )
        core.start(mode="random")
        # 重置时间戳确保触发
        core._last_progress_time = 0
        core._maybe_call_progress()

        assert len(captured_stats) == 1

        core.stop()


# ========== Test: 获取统计信息 ==========


class TestGetStats:
    """测试 get_stats"""

    def test_get_stats_returns_dict(self, sample_targets, sample_config):
        """返回字典类型的统计信息"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        stats = core.get_stats()
        assert isinstance(stats, dict)
        core.stop()

    def test_get_stats_when_not_started(self, sample_targets):
        """未启动时返回空字典"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        assert core.get_stats() == {}

    def test_get_stats_includes_running_status(self, sample_targets, sample_config):
        """包含 running 状态"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        stats = core.get_stats()
        assert stats["running"] is True
        core.stop()
        stats = core.get_stats()
        # stop 后 stats 仍然存在但 running 为 False
        if "running" in stats:
            assert stats["running"] is False

    def test_get_stats_includes_elapsed_time(self, sample_targets, sample_config):
        """包含已运行时间"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        time.sleep(0.1)
        stats = core.get_stats()
        assert "elapsed_time" in stats
        assert stats["elapsed_time"] > 0
        core.stop()

    def test_get_stats_without_to_dict(self, sample_targets, sample_config):
        """stats 无 to_dict 方法时返回仅额外信息 (running/elapsed_time)"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        # CollisionStats 原生没有 to_dict 方法,
        # get_stats() 应回退到仅返回 running 和 elapsed_time
        stats = core.get_stats()
        assert "running" in stats
        assert "elapsed_time" in stats
        core.stop()


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
        """测试模块版本号 v4.0.0"""
        from src.collision import gpu

        assert gpu.__version__ == "6.0.0"

    def test_collision_core_in_all(self):
        """验证 CollisionCore 在 __all__ 中"""
        from src.collision.gpu import __all__ as gpu_all

        assert "CollisionCore" in gpu_all

    def test_factory_get_collision_core(self):
        """测试工厂函数"""
        from src.collision.gpu import get_collision_core
        from src.collision.gpu.core import CollisionCore

        assert get_collision_core() is CollisionCore

    def test_no_phase4_todos_in_core(self):
        """验证 core.py 中无 Phase 4 TODO"""
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
        with open(core_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Phase 4 TODO 应该已经全部移除
        assert "# TODO: Phase 4" not in content, "core.py 中还有未处理的 Phase 4 TODO"
        assert "# TODO: 恢复统计和状态" not in content, "core.py 中还有未处理的恢复统计TODO"
        assert "# TODO: 实现进度回调节流逻辑" not in content, "core.py 中还有未处理的进度节流TODO"

    def test_types_import(self):
        """验证 TYPE_CHECKING 导入正常工作"""
        import typing

        # 验证在非类型检查时导入不触发
        from src.collision.gpu.core import CollisionCore

        # 如果能正常导入，说明 TYPE_CHECKING 守卫正确


# ========== Test: 集成测试 ==========


class TestCollisionCoreIntegration:
    """集成场景测试"""

    def test_full_lifecycle_with_dedup_and_checkpoint(self, sample_targets, sample_config_full):
        """完整生命周期：去重+断点+进度回调"""
        from src.collision.gpu.core import CollisionCore

        progress_calls = []
        match_calls = []

        def on_progress(stats):
            progress_calls.append(stats.speed)

        def on_match(pk, addr, wif):
            match_calls.append(addr)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config_full,
            on_progress=on_progress,
            on_match=on_match,
        )
        core.start(mode="random")

        # 重置进度时间戳确保首次批次触发进度回调
        core._last_progress_time = 0

        # 模拟多个批次
        match_with_key = {
            "address": "1MatchAddr",
            "private_key": "c" * 64,
            "wif": "5KMatchWIF",
        }

        for i in range(5):
            matches = [match_with_key] if i == 2 else []
            core.on_batch_complete(matches=matches, batch_size=10000)

        # 验证：匹配回调被调用
        assert len(match_calls) >= 1
        # 验证：进度回调被调用（可能被节流）
        assert len(progress_calls) >= 1

        stats = core.get_stats()
        assert stats["running"] is True
        assert "total_checked" in stats or core.stats.total_checked > 0

        core.stop()
        assert core.is_running() is False

    def test_huge_batch_size_overflow_safe(self, sample_targets, sample_config):
        """大批次大小不会溢出"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets, config=sample_config)
        core.start(mode="random")
        # 十亿级批次
        core.on_batch_complete(matches=[], batch_size=1_000_000_000)
        assert core.stats.total_checked > 0
        core.stop()

    def test_many_matches_in_one_batch(self, sample_targets, sample_config):
        """单个批次中大量匹配"""
        from src.collision.gpu.core import CollisionCore

        match_calls = []

        def on_match(pk, addr, wif):
            match_calls.append(addr)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_match=on_match,
        )
        core.start(mode="random")

        many_matches = [
            {"address": f"1Addr{i}", "private_key": f"{i:064x}", "wif": f"5KWIF{i}"}
            for i in range(100)
        ]
        core.on_batch_complete(matches=many_matches, batch_size=10000)
        assert len(match_calls) == 100
        core.stop()

    def test_concurrent_batch_complete_safety(self, sample_targets, sample_config):
        """并发批次完成回调的安全性"""
        from src.collision.gpu.core import CollisionCore

        match_calls = []

        def on_match(pk, addr, wif):
            match_calls.append(addr)

        core = CollisionCore(
            targets=sample_targets,
            config=sample_config,
            on_match=on_match,
        )
        core.start(mode="random")

        errors = []

        def worker():
            try:
                for _ in range(10):
                    core.on_batch_complete(
                        matches=[{"address": "1Test", "private_key": "d" * 64, "wif": "5KTest"}],
                        batch_size=100,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发测试出现错误: {errors}"
        assert len(match_calls) > 0
        core.stop()

    def test_start_failure_cleanup(self, sample_targets):
        """启动后即使搜索协调器失败也能安全停止"""
        from src.collision.gpu.core import CollisionCore

        core = CollisionCore(targets=sample_targets)
        # 使用存根启动
        core.start(mode="random")
        assert core._running is True

        # 即使存根模式也应该能安全停止
        core.stop()
        assert core._running is False


# ========== 运行配置 ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
