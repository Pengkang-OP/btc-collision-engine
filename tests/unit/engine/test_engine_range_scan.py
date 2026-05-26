"""KeyCollisionEngine 范围扫描测试 (MAINT-1拆分)

原 file: test_key_collision_engine.py
抽取类: TestKeyCollisionEngineRangeScan, TestKeyCollisionEngineRangeScanWorker,
        TestKeyCollisionEngineRangeScanOrchestration
"""

import threading
import time

import pytest

from src.collision.key_collision_engine import KeyCollisionEngine
from tests.conftest_engine import get_known_target


class TestKeyCollisionEngineRangeScan:
    """范围扫描模式测试"""

    def test_range_scan_basic(self):
        """范围扫描能正常启动和停止"""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            max_workers=1,
        )
        engine.start(mode="range", start=1, end=100)
        time.sleep(1)
        engine.stop()

    def test_range_scan_counts_checked(self):
        """范围扫描后检查数正确"""
        complete_event = threading.Event()

        def on_complete(stats):
            complete_event.set()

        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            on_complete=on_complete,
            max_workers=1,
        )
        engine.start(mode="range", start=1, end=1000)
        time.sleep(0.5)
        if not engine.is_running():
            pytest.fail("引擎未启动")
        if not complete_event.wait(timeout=60):
            engine.stop()
            pytest.fail("范围扫描未在60秒内完成")
        stats = engine.get_stats()
        assert stats.total_checked  >  900, f"total_checked={stats.total_checked}"


class TestKeyCollisionEngineRangeScanWorker:
    """_range_scan_worker 内部路径：匹配、压缩/非压缩、错误处理"""

    def test_range_scan_worker_known_key_match(self):
        """范围扫描工作线程：已知私钥匹配"""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 5, 0)
        assert count  ==  5
        assert len(engine.stats.matches)  ==  1
        engine.stop()

    def test_range_scan_worker_compressed_only(self):
        """范围扫描：仅压缩格式（check_uncompressed=False）"""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            check_uncompressed=False,
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 5, 0)
        assert count  ==  5
        assert len(engine.stats.matches)  ==  1
        engine.stop()

    def test_range_scan_worker_with_uncompressed_check(self):
        """范围扫描：启用双格式检查（check_uncompressed=True）"""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            check_uncompressed=True,
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 5, 0)
        assert count  ==  5
        assert len(engine.stats.matches)  ==  1
        engine.stop()

    def test_range_scan_worker_no_callback_stops(self):
        """范围扫描：无 on_match 回调时匹配后停止"""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=None,
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 5, 0)
        assert count  <  5, "匹配后应提前停止"
        assert engine._stop_event.is_set()
        engine.stop()

    def test_range_scan_worker_no_match(self):
        """范围扫描：无匹配目标"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddressXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 10, 0)
        assert count  ==  10
        assert len(engine.stats.matches)  ==  0
        engine.stop()

    def test_range_scan_worker_out_of_range_key(self):
        """范围扫描：私钥超出secp256k1范围时跳过"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(0, 5, 0)
        assert count  ==  5, "k=0应跳过，仅5个有效"
        engine.stop()


class TestKeyCollisionEngineRangeScanOrchestration:
    """range_scan + brute_force 编排层：进度回调、数据日志"""

    def test_range_scan_with_progress_callback(self):
        """范围扫描：进度回调被调用"""
        progress_called = []

        def on_progress(snapshot):
            progress_called.append(snapshot.total_checked)

        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            on_progress=on_progress,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="range", start=1, end=20)
        time.sleep(0.5)
        engine.stop()
        assert len(progress_called)  >  0, "进度回调应至少被调用一次"

    def test_range_scan_with_complete_callback(self):
        """范围扫描：完成回调被调用"""
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
        engine.start(mode="range", start=1, end=10)
        complete_called.wait(timeout=10)
        engine.stop()
        assert len(final_stats)  >  0
