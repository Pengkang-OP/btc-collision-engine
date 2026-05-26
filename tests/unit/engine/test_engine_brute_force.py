"""KeyCollisionEngine 暴力穷举测试 (MAINT-1拆分)

原 file: test_key_collision_engine.py
抽取类: TestKeyCollisionEngineBruteForce, TestKeyCollisionEngineBruteForceWorker
"""

import threading
import time

from src.collision.key_collision_engine import KeyCollisionEngine
from tests.conftest_engine import get_known_target


class TestKeyCollisionEngineBruteForce:
    """暴力穷举模式测试"""

    def test_brute_force_start_stop(self):
        """暴力穷举能正常启动和停止"""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            max_workers=1,
        )
        engine.start(mode="brute_force", start=1)
        time.sleep(1)
        engine.stop()

    def test_brute_force_increments_from_start(self):
        """暴力穷举从指定起始值递增"""
        _, known_addr = get_known_target()
        match_event = threading.Event()

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: match_event.set(),
            max_workers=1,
        )
        engine.start(mode="brute_force", start=1)
        match_event.wait(timeout=10)
        engine.stop()
        assert match_event.is_set()

    def test_brute_force_with_progress_callback(self):
        """暴力穷举：进度回调被调用"""
        progress_called = []

        def on_progress(snapshot):
            progress_called.append(snapshot.total_checked)

        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            on_progress=on_progress,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.progress_interval = 1
        engine.start(mode="brute_force", start=1, max_keys=10)
        time.sleep(1.0)
        engine.stop()
        assert len(progress_called)  >  0

    def test_brute_force_with_complete_callback(self):
        """暴力穷举：完成回调被调用"""
        complete_called = threading.Event()
        final_stats = []

        def on_complete(stats):
            final_stats.append(stats.total_checked)
            complete_called.set()

        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            on_complete=on_complete,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="brute_force", start=1, max_keys=10)
        complete_called.wait(timeout=10)
        engine.stop()
        assert len(final_stats)  >  0


class TestKeyCollisionEngineBruteForceWorker:
    """_brute_force_worker 内部路径：max_keys、匹配、错误处理"""

    def test_brute_force_worker_max_keys_limit(self):
        """暴力穷举：max_keys 限制生效"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 1
        count = engine._brute_force_worker(0, batch_size=2, max_keys=5)
        assert count  >=  5
        engine.stop()

    def test_brute_force_worker_known_key_match(self):
        """暴力穷举：已知私钥匹配"""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 1
        engine._stop_event.clear()
        count = engine._brute_force_worker(0, batch_size=3, max_keys=10)
        assert count  >=  1
        assert len(engine.stats.matches)  ==  1
        engine.stop()

    def test_brute_force_worker_no_callback_stops(self):
        """暴力穷举：无 on_match 回调时匹配后停止"""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=None,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 1
        engine._stop_event.clear()
        count = engine._brute_force_worker(0, batch_size=3, max_keys=10)
        assert count  >=  1
        assert engine._stop_event.is_set()
        engine.stop()

    def test_brute_force_worker_out_of_range_key(self):
        """暴力穷举：从 k=0 开始跳过无效私钥不崩溃"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 0
        engine._stop_event.clear()
        count = engine._brute_force_worker(0, batch_size=2, max_keys=5)
        assert count  >  0, "k=0应被跳过，不应崩溃"
        engine.stop()

    def test_brute_force_with_max_keys(self):
        """brute_force 设置 max_keys 限制扫描数量"""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="brute_force", start=1, max_keys=10)
        time.sleep(0.5)
        engine.stop()
        stats = engine.get_stats()
        assert stats.total_checked  >  0
        engine.stop()
