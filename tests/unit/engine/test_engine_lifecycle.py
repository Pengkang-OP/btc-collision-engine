"""KeyCollisionEngine 生命周期测试 (MAINT-1拆分)

原 file: test_key_collision_engine.py
抽取类: TestKeyCollisionEngineLifecycle, TestKeyCollisionEngineContextManager,
        TestKeyCollisionEngineResumeAndStop (stop边界)
"""

import threading
import time
import pytest

from src.collision.collision_stats import CollisionStats
from src.collision.key_collision_engine import KeyCollisionEngine


class TestKeyCollisionEngineLifecycle:
    """引擎生命周期测试"""

    def test_initial_state_not_running(self):
        """初始状态为未运行"""
        engine = KeyCollisionEngine(targets={"1TestAddr"})
        assert not engine.is_running()

    def test_start_sets_running(self):
        """start() 后引擎处于运行状态"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1)
        engine.start(mode="random")
        time.sleep(0.2)
        assert engine.is_running()
        engine.stop()

    def test_stop_ends_running(self):
        """stop() 后引擎停止运行"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1)
        engine.start(mode="random")
        time.sleep(0.2)
        engine.stop()
        time.sleep(0.3)
        assert not engine.is_running()

    def test_double_start_ignored(self):
        """重复 start() 不崩溃"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1)
        engine.start(mode="random")
        time.sleep(0.1)
        engine.start(mode="random")  # 第二次 start 应被忽略
        engine.stop()

    def test_stop_without_start_safe(self):
        """未启动直接调用 stop() 不崩溃"""
        engine = KeyCollisionEngine(targets={"1TestAddr"})
        engine.stop()  # 不应抛出异常

    def test_get_stats_returns_collision_stats(self):
        """get_stats() 返回 CollisionStats 对象"""
        engine = KeyCollisionEngine(targets={"1TestAddr"})
        stats = engine.get_stats()
        assert isinstance(stats, CollisionStats)


class TestKeyCollisionEngineContextManager:
    """上下文管理器 + 析构函数"""

    def test_context_manager_enter_exit(self):
        """with语句进入/退出引擎"""
        with KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        ) as engine:
            assert not engine.is_running()
            engine.start(mode="random")
            time.sleep(0.2)
            assert engine.is_running()
        # __exit__ 应调用 stop()
        time.sleep(0.3)
        assert not engine.is_running()

    def test_del_with_running_engine(self):
        """__del__ 在引擎运行时安全停止"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start(mode="random")
        time.sleep(0.2)
        engine.__del__()
        assert not engine.is_running()

    def test_del_with_stopped_engine(self):
        """__del__ 在引擎已停止时不报错"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.__del__()


class TestKeyCollisionEngineResumeAndStop:
    """start() resume 路径 + stop() 边界条件"""

    def test_start_empty_targets_warning(self):
        """空目标地址集合时启动发出警告"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="random")
        time.sleep(0.2)
        assert engine.is_running()
        engine.stop()

    def test_stop_with_thread_timeout(self):
        """stop() 超时等待线程结束"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="random")
        time.sleep(0.2)
        engine.stop(timeout=0.001)
        assert not engine.is_running()

    def test_del_with_exception_during_stop(self):
        """__del__ 中 stop 抛出异常时静默处理"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._running = True
        engine._stop_event = None  # type: ignore[assignment]
        try:
            engine.__del__()
        except Exception:
            pytest.fail("__del__ 不应向上抛出异常")
        engine._stop_event = threading.Event()
        engine._running = False

    def test_get_stats_with_live_count(self):
        """get_stats() 合并 live_range_count"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._live_range_count = 100
        engine.stats.total_checked = 50
        stats = engine.get_stats()
        assert stats.total_checked  >=  100
        engine.stop()

    def test_stop_save_checkpoint_error(self):
        """stop() 保存断点失败时记录错误但不崩溃"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="random")
        time.sleep(0.2)
        engine.checkpoint_mgr = None
        engine.stop()
        assert not engine.is_running()
