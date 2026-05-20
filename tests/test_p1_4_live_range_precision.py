"""P1-4 定向验证测试: range_scan 停止时 _live_range_count 精度丢失修复

修复内容: range_scan 最终计数合并 _live_range_count + data_logging 同步
修复文件: src/collision/key_collision_engine.py

验证项:
  A - range_scan final_count 使用 total_count + _live_range_count
  B - range_scan 最终 _live_range_count 已重置为0
  C - random_search 对比: pattern 一致性
  D - _range_scan_worker 有 500步余数提交
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import inspect  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

from src.collision.key_collision_engine import KeyCollisionEngine  # noqa: E402


class TestP1_4RangeScanPrecisionFix:
    """P1-4 range_scan 停止精度修复验证"""

    def setup_method(self):
        """每个测试创建独立引擎实例"""
        self.engine = None

    def teardown_method(self):
        """清理"""
        if self.engine and self.engine._thread and self.engine._thread.is_alive():
            self.engine.stop()
            time.sleep(0.3)

    # ================================================================
    # 验证 A: range_scan final_count 使用 _live_range_count
    # ================================================================
    def test_a_range_scan_final_uses_live_count(self):
        """验证 range_scan 最终计数包含 _live_range_count"""
        source = inspect.getsource(KeyCollisionEngine.range_scan)

        # 必须在 Executor 退出后包含 final_count = total_count + _live_range_count
        assert "final_count" in source, "range_scan 应使用 final_count 变量"
        assert (
            "total_count + self._live_range_count" in source
        ), "range_scan final_count 应合并 _live_range_count"
        # 确保不再用空 total_count 更新 stats
        lines = source.split("\n")
        # 在 self._executor = None 之后不应有 self.stats.update(total_count, ...
        executor_none_idx = None
        for i, l in enumerate(lines):
            if "self._executor = None" in l:
                executor_none_idx = i
                break
        assert executor_none_idx is not None

        after_exec = lines[executor_none_idx:]
        bad_pattern = any(
            "self.stats.update(total_count" in l and "total_range" in l
            for l in after_exec  # noqa: E741, E501
        )
        assert not bad_pattern, (
            "range_scan 不应再用 total_count 直接更新 stats，" "应使用 final_count"
        )

    # ================================================================
    # 验证 B: range_scan 停止后 _live_range_count 重置
    # ================================================================
    def test_b_range_scan_stop_resets_live_count(self):
        """验证 range_scan 停止后 _live_range_count 重置为0"""
        complete_event = threading.Event()
        final_stats = []

        def on_complete(stats):
            final_stats.append(stats.total_checked)
            complete_event.set()

        self.engine = KeyCollisionEngine(
            targets={"1NonExistentTestAddress12345"},
            on_complete=on_complete,
            max_workers=1,
        )

        # 启动 range_scan 模式（用较大范围确保有 pending workers）
        self.engine.start(mode="range", start=1, end=50000)
        time.sleep(1.0)  # 等待一些进度
        self.engine.stop()

        complete_event.wait(timeout=10)

        # _live_range_count 应为0
        live = self.engine._live_range_count
        assert live == 0, f"range_scan 停止后 _live_range_count 应为0，实际为 {live}"

    # ================================================================
    # 验证 C: random_search pattern 一致性
    # ================================================================
    def test_c_random_search_still_correct(self):
        """验证 random_search 的 final_count 逻辑未被破坏"""
        source = inspect.getsource(KeyCollisionEngine.random_search)

        assert (
            "final_count = total_count + self._live_range_count" in source
        ), "random_search 应保持 final_count = total_count + _live_range_count"
        assert "self._live_range_count = 0" in source, "random_search 应重置 _live_range_count"

    # ================================================================
    # 验证 D: _range_scan_worker 有余数提交
    # ================================================================
    def test_d_range_scan_worker_has_remainder(self):
        """验证 _range_scan_worker 有 500步余数提交"""
        source = inspect.getsource(KeyCollisionEngine._range_scan_worker)

        assert "local_count % 500" in source, "_range_scan_worker 应有余数提交（local_count % 500）"
        assert (
            "self._live_range_count +=" in source
        ), "_range_scan_worker 应提交余数到 _live_range_count"
        assert "remainder" in source, "_range_scan_worker 应有 remainder 变量"

    # ================================================================
    # 验证 E: range_scan data_logging 使用 final_count
    # ================================================================
    def test_e_data_logging_uses_final_count(self):
        """验证 range_scan data_logging 使用 final_count"""
        source = inspect.getsource(KeyCollisionEngine.range_scan)

        # 确认 data_logging current_position 使用 final_count
        assert (
            "current_position=final_count" in source
        ), "data_logging 的 current_position 应使用 final_count"
