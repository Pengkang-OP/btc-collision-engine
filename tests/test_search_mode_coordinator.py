#!/usr/bin/env python3
"""搜索模式协调器 (SearchModeCoordinator) 单元测试.

覆盖：
- 初始化与搜索模式创建
- get_available_modes / get_current_mode 状态查询
- start 模式启动与分发（random / brute_force / range_scan）
- switch_mode 模式切换
- stop 停止当前模式
- get_mode_instance / get_mode_status / get_all_modes_status
- 错误处理：未知模式、resume 检查点
- 边界值：重复切换、空检查点、无 checkpoint_mgr
"""

from unittest.mock import MagicMock

import pytest

from src.gpu.search_mode_coordinator import SearchModeCoordinator

# ============================================================================
# 辅助函数
# ============================================================================


def _make_engine_stub(**kwargs):
    """创建 GPUCollisionEngine stub."""
    engine = MagicMock()
    engine.config = kwargs.get("config", {})
    engine.checkpoint_mgr = kwargs.get("checkpoint_mgr")
    engine._current_position = kwargs.get("_current_position", 0)
    engine.stats = MagicMock()
    engine.stats.total_keys = kwargs.get("total_keys", 0)
    engine.is_running = MagicMock(return_value=kwargs.get("is_running", True))
    return engine


# ============================================================================
# 初始化测试
# ============================================================================


@pytest.mark.unit
class TestSearchModeCoordinatorInit:
    """SearchModeCoordinator 初始化测试."""

    def test_init_creates_all_modes(self):
        """测试初始化创建所有三种搜索模式 - 通过 patch 类构造."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)

        # 验证模式被创建并存储
        modes = coordinator.get_available_modes()
        assert "random" in modes
        assert "brute_force" in modes
        assert "range_scan" in modes
        assert len(modes) == 3

    def test_init_modes_in_dict(self):
        """测试模式存储在 _modes 字典中且为对象."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)

        assert coordinator.MODE_RANDOM in coordinator._modes
        assert coordinator.MODE_BRUTE_FORCE in coordinator._modes
        assert coordinator.MODE_RANGE_SCAN in coordinator._modes
        # 模式值是真实对象（非 None）
        assert coordinator._modes[coordinator.MODE_RANDOM] is not None
        assert coordinator._modes[coordinator.MODE_BRUTE_FORCE] is not None
        assert coordinator._modes[coordinator.MODE_RANGE_SCAN] is not None

    def test_init_current_mode_none(self):
        """测试初始化后 current_mode 为 None."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        assert coordinator._current_mode is None

    def test_init_custom_logger(self):
        """测试使用自定义 logger."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        custom_logger = MagicMock()
        coordinator = SearchModeCoordinator(engine, logger=custom_logger)
        assert coordinator.logger is custom_logger

    def test_init_reads_seed_prefetch_from_config(self):
        """测试从 engine.config 读取 seed_prefetch_size."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 20}})
        coordinator = SearchModeCoordinator(engine)
        # 验证模式可用
        assert coordinator.get_mode_instance("random") is not None

    def test_init_default_seed_prefetch(self):
        """测试无配置时使用默认 seed_prefetch_size=5."""
        engine = _make_engine_stub(config={})
        coordinator = SearchModeCoordinator(engine)
        assert coordinator.get_mode_instance("random") is not None

    def test_engine_no_config_attr(self):
        """测试 engine 无 config 属性时的回退."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        del engine.config
        coordinator = SearchModeCoordinator(engine)
        assert coordinator.get_current_mode() is None


# ============================================================================
# get_available_modes / get_current_mode 测试
# ============================================================================


@pytest.mark.unit
class TestQueryModes:
    """模式查询测试."""

    def test_get_available_modes(self):
        """测试获取可用模式列表."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        modes = coordinator.get_available_modes()
        assert "random" in modes
        assert "brute_force" in modes
        assert "range_scan" in modes

    def test_get_current_mode_initial(self):
        """测试初始状态 current_mode 为 None."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        assert coordinator.get_current_mode() is None

    def test_get_current_mode_after_start(self):
        """测试启动后 current_mode 更新."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)

        # Mock search mode execute
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", start=0)
        assert coordinator.get_current_mode() == "brute_force"


# ============================================================================
# start 测试
# ============================================================================


@pytest.mark.unit
class TestStart:
    """启动模式测试."""

    def test_start_unknown_mode_raises(self):
        """测试启动未知模式抛出 ValueError."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        with pytest.raises(ValueError, match="未知的搜索模式"):
            coordinator.start("invalid_mode")

    def test_start_brute_force(self):
        """测试启动暴力穷举模式."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", start=100)
        bf_mode.execute.assert_called_once_with(100)

    def test_start_brute_force_default_start(self):
        """测试暴力穷举默认 start=0."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force")
        bf_mode.execute.assert_called_once_with(0)

    def test_start_range_scan(self):
        """测试启动范围扫描模式."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        rs_mode = coordinator._modes["range_scan"]
        rs_mode.execute = MagicMock()

        coordinator.start("range_scan", start=10, end=100)
        rs_mode.execute.assert_called_once_with(10, 100)

    def test_start_range_scan_default_end(self):
        """测试范围扫描默认 end=2**256-1."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        rs_mode = coordinator._modes["range_scan"]
        rs_mode.execute = MagicMock()

        coordinator.start("range_scan", start=0)
        rs_mode.execute.assert_called_once_with(0, 2**256 - 1)

    def test_start_random(self):
        """测试启动随机搜索模式."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        r_mode = coordinator._modes["random"]
        r_mode.execute = MagicMock()

        coordinator.start("random")
        r_mode.execute.assert_called_once()


# ============================================================================
# resume 检查点恢复测试
# ============================================================================


@pytest.mark.unit
class TestResume:
    """检查点恢复测试."""

    def test_resume_with_checkpoint(self):
        """测试从检查点恢复."""
        mock_checkpoint_mgr = MagicMock()
        mock_checkpoint_mgr.load.return_value = {
            "position": 5000,
            "stats": MagicMock(),
        }
        engine = _make_engine_stub(
            checkpoint_mgr=mock_checkpoint_mgr,
            config={"gpu": {"seed_prefetch_size": 5}},
        )
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", resume=True, start=0)

        assert engine._current_position == 5000
        bf_mode.execute.assert_called_once_with(0)

    def test_resume_no_checkpoint(self):
        """测试无检查点时从头开始."""
        mock_checkpoint_mgr = MagicMock()
        mock_checkpoint_mgr.load.return_value = None
        engine = _make_engine_stub(
            checkpoint_mgr=mock_checkpoint_mgr,
            config={"gpu": {"seed_prefetch_size": 5}},
        )
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", resume=True, start=0)
        assert engine._current_position == 0
        bf_mode.execute.assert_called_once_with(0)

    def test_resume_no_checkpoint_mgr(self):
        """测试无 checkpoint_mgr 时正常运行."""
        engine = _make_engine_stub(
            checkpoint_mgr=None,
            config={"gpu": {"seed_prefetch_size": 5}},
        )
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", resume=True, start=0)
        bf_mode.execute.assert_called_once_with(0)


# ============================================================================
# switch_mode 测试
# ============================================================================


@pytest.mark.unit
class TestSwitchMode:
    """模式切换测试."""

    def test_switch_to_different_mode(self):
        """测试切换到不同模式."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)

        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()
        rs_mode = coordinator._modes["range_scan"]
        rs_mode.execute = MagicMock()

        coordinator.start("brute_force", start=0)
        coordinator.switch_mode("range_scan", start=10, end=100)

        assert coordinator.get_current_mode() == "range_scan"
        rs_mode.execute.assert_called_once_with(10, 100)

    def test_switch_to_same_mode_noop(self):
        """测试切换到相同模式无操作."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)

        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", start=0)
        bf_mode.execute.reset_mock()
        coordinator.switch_mode("brute_force", start=0)

        bf_mode.execute.assert_not_called()

    def test_switch_saves_checkpoint(self):
        """测试切换时保存检查点."""
        mock_checkpoint_mgr = MagicMock()
        engine = _make_engine_stub(
            checkpoint_mgr=mock_checkpoint_mgr,
            total_keys=10000,
            config={"gpu": {"seed_prefetch_size": 5}},
        )
        coordinator = SearchModeCoordinator(engine)

        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()
        rs_mode = coordinator._modes["range_scan"]
        rs_mode.execute = MagicMock()

        coordinator.start("brute_force", start=0)
        coordinator.switch_mode("range_scan", start=10, end=100)

        # _save_current_state 调用 engine._save_checkpoint
        engine._save_checkpoint.assert_called()


# ============================================================================
# stop 测试
# ============================================================================


@pytest.mark.unit
class TestStop:
    """停止模式测试."""

    def test_stop_clears_current_mode(self):
        """测试停止后清除 current_mode."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", start=0)
        coordinator.stop()
        assert coordinator.get_current_mode() is None

    def test_stop_no_current_mode(self):
        """测试无当前模式时 stop 无异常."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        coordinator.stop()  # 不应抛出异常

    def test_stop_calls_mode_stop(self):
        """测试停止时调用搜索模式的 stop 方法."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        r_mode = coordinator._modes["random"]
        r_mode.execute = MagicMock()
        r_mode.stop = MagicMock()

        coordinator.start("random")
        coordinator.stop()
        r_mode.stop.assert_called_once()

    def test_stop_mode_without_stop_method(self):
        """测试搜索模式无 stop 方法时不报错."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()
        # BruteForceSearchMode 本身无 stop 方法，直接验证 coordinator.stop() 不抛异常

        coordinator.start("brute_force", start=0)
        coordinator.stop()  # 不应抛出异常


# ============================================================================
# get_mode_instance / get_mode_status 测试
# ============================================================================


@pytest.mark.unit
class TestGetMode:
    """获取模式实例和状态测试."""

    def test_get_mode_instance_exists(self):
        """测试获取存在的模式实例."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        instance = coordinator.get_mode_instance("random")
        assert instance is not None

    def test_get_mode_instance_not_exists(self):
        """测试获取不存在的模式返回 None."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        assert coordinator.get_mode_instance("invalid") is None

    def test_get_mode_status_not_found(self):
        """测试获取不存在模式的状态."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        status = coordinator.get_mode_status("invalid")
        assert status == {"error": "搜索模式不存在"}

    def test_get_mode_status_has_get_status(self):
        """测试模式有 get_status 方法时."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        r_mode = coordinator._modes["random"]
        r_mode.get_status = MagicMock(
            return_value={
                "mode": "random",
                "seed_generated": 100,
            },
        )
        status = coordinator.get_mode_status("random")
        assert status["mode"] == "random"
        assert status["seed_generated"] == 100

    def test_get_mode_status_no_get_status(self):
        """测试模式无 get_status 方法时的回退."""
        engine = _make_engine_stub(
            is_running=True,
            config={"gpu": {"seed_prefetch_size": 5}},
        )
        coordinator = SearchModeCoordinator(engine)
        # BruteForceSearchMode 没有 get_status 方法
        status = coordinator.get_mode_status("brute_force")
        assert status["mode"] == "brute_force"
        assert status["status"] == "available"
        assert status["engine_running"] is True

    def test_get_mode_status_exception(self):
        """测试获取状态时异常处理."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        r_mode = coordinator._modes["random"]
        r_mode.get_status = MagicMock(side_effect=RuntimeError("内部错误"))

        status = coordinator.get_mode_status("random")
        assert status == {"error": "内部错误"}

    def test_get_all_modes_status(self):
        """测试获取所有模式状态."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        all_status = coordinator.get_all_modes_status()
        assert "random" in all_status
        assert "brute_force" in all_status
        assert "range_scan" in all_status
        assert len(all_status) == 3


# ============================================================================
# 边界值测试
# ============================================================================


@pytest.mark.unit
class TestBoundaryConditions:
    """边界条件测试."""

    def test_start_range_scan_large_range(self):
        """测试范围扫描大范围."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        rs_mode = coordinator._modes["range_scan"]
        rs_mode.execute = MagicMock()

        coordinator.start("range_scan", start=2**128, end=2**129)
        rs_mode.execute.assert_called_once_with(2**128, 2**129)

    def test_start_brute_force_zero(self):
        """测试暴力穷举 start=0."""
        engine = _make_engine_stub(config={"gpu": {"seed_prefetch_size": 5}})
        coordinator = SearchModeCoordinator(engine)
        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()

        coordinator.start("brute_force", start=0)
        bf_mode.execute.assert_called_once_with(0)

    def test_resume_save_checkpoint_error(self):
        """测试保存检查点时异常不传播."""
        mock_checkpoint_mgr = MagicMock()
        mock_checkpoint_mgr.save.side_effect = OSError("磁盘满")
        engine = _make_engine_stub(
            checkpoint_mgr=mock_checkpoint_mgr,
            total_keys=5000,
            config={"gpu": {"seed_prefetch_size": 5}},
        )
        coordinator = SearchModeCoordinator(engine)

        bf_mode = coordinator._modes["brute_force"]
        bf_mode.execute = MagicMock()
        rs_mode = coordinator._modes["range_scan"]
        rs_mode.execute = MagicMock()

        coordinator.start("brute_force", start=0)
        coordinator.switch_mode("range_scan", start=10, end=100)
        assert coordinator.get_current_mode() == "range_scan"
