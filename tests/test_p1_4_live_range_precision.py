"""P1-4 定向验证测试: range_scan 停止时 _live_range_count 精度丢失修复

修复内容: range_scan 最终计数合并 _live_range_count + data_logging 同步
修复文件: src/collision/key_collision_engine.py

验证项:
  A - range_scan final_count 使用 total_count + _live_range_count
  B - range_scan 最终 _live_range_count 已重置为0
  C - random_search 对比: pattern 一致性
  D - _range_scan_worker 有 500步余数提交
"""

import inspect
import threading
import time

from src.collision.key_collision_engine import KeyCollisionEngine


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
        """验证 range_scan 最终通过 _range_scan_finalize 合并计数"""
        source = inspect.getsource(KeyCollisionEngine.range_scan)
        finalize_source = inspect.getsource(KeyCollisionEngine._range_scan_finalize)

        # range_scan 应调用 _range_scan_finalize 进行最终计数合并
        assert "_range_scan_finalize(total_count" in source, (
            "range_scan 应调用 _range_scan_finalize 合并计数"
        )
        # _range_scan_finalize 内应合并 _live_range_count
        assert "total_count + self._live_range_count" in finalize_source, (
            "_range_scan_finalize 应合并 _live_range_count"
        )
        assert "self._live_range_count = 0" in finalize_source, (
            "_range_scan_finalize 应重置 _live_range_count"
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
        """验证 random_search 通过 _random_search_finalize 正确处理 final_count"""
        source = inspect.getsource(KeyCollisionEngine.random_search)
        finalize_source = inspect.getsource(KeyCollisionEngine._random_search_finalize)

        # random_search 应调用 _random_search_finalize
        assert "_random_search_finalize(total_count)" in source, (
            "random_search 应调用 _random_search_finalize"
        )
        # _random_search_finalize 内应使用 final_count 并重置
        assert "final_count" in finalize_source, (
            "_random_search_finalize 应使用 final_count"
        )
        assert "self._live_range_count = 0" in finalize_source, (
            "_random_search_finalize 应重置 _live_range_count"
        )

    # ================================================================
    # 验证 D: _range_scan_worker 有余数提交
    # ================================================================
    def test_d_range_scan_worker_has_remainder(self):
        """验证 _range_scan_worker 有 500步余数提交"""
        source = inspect.getsource(KeyCollisionEngine._range_scan_worker)

        assert "local_count % 32" in source, "_range_scan_worker 应有余数提交（local_count % 32）"
        assert "self._live_range_count +=" in source, "_range_scan_worker 应提交余数到 _live_range_count"
        assert "remainder" in source, "_range_scan_worker 应有 remainder 变量"

    # ================================================================
    # 验证 E: range_scan data_logging 使用 final_count
    # ================================================================
    def test_e_data_logging_uses_final_count(self):
        """验证 range_scan 的数据日志通过 _range_scan_finalize 使用 final_count"""
        source = inspect.getsource(KeyCollisionEngine._range_scan_finalize)

        # _range_scan_finalize 使用 final_count 更新 stats
        assert "final_count" in source, (
            "_range_scan_finalize 应使用 final_count 进行统计更新"
        )
        assert "self.stats.update(final_count" in source, (
            "_range_scan_finalize 应使用 final_count 更新 stats"
        )
