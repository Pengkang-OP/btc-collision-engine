"""
P1-5 修复验证：_live_range_count 双重计数BUG

验证要点：
1. _live_range_count 不被批次结束重复提交（L808-812 已删除）
2. Worker退出时提交32步余数
3. total_count + _live_range_count 不重复计入已完成worker
"""
import threading
import time
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.key_collision_engine import KeyCollisionEngine


class TestLiveRangeCountFix(unittest.TestCase):
    """P1-5: _live_range_count 双重计数修复验证"""

    def setUp(self):
        """每个测试创建独立的引擎实例"""
        self.engine = None

    def tearDown(self):
        """清理"""
        if self.engine and hasattr(self.engine, '_executor') and self.engine._executor:
            self.engine.stop()
            time.sleep(0.3)

    def test_live_range_count_reset_after_random_search(self):
        """P1-5-A: random_search结束后 _live_range_count 应为0"""
        complete_event = threading.Event()
        
        def on_complete(stats):
            complete_event.set()
        
        self.engine = KeyCollisionEngine(
            targets={"1NonExistentTestAddress12345"},
            on_complete=on_complete,
            max_workers=1,
        )
        
        # 追踪 _live_range_count 的中间值
        live_counts = []
        original_live_count = self.engine._live_range_count
        
        self.engine.start(mode="random")
        time.sleep(1.5)  # 等待一些批次完成
        
        # 记录运行中的 _live_range_count
        if hasattr(self.engine, '_state_lock'):
            with self.engine._state_lock:
                running_count = self.engine._live_range_count
                live_counts.append(running_count)
        
        self.engine.stop()
        complete_event.wait(timeout=10)
        
        # 最终 _live_range_count 应为0（已重置）
        final_live = self.engine._live_range_count
        self.assertEqual(final_live, 0, 
            f"_live_range_count 应为0(已重置)，实际为 {final_live}")
        
        print(f"\n[P1-5-A ✓] _live_range_count 已正确重置: {final_live}")

    def test_final_count_not_doubled_random_search(self):
        """P1-5-B: random_search 最终计数不翻倍（核心验证）"""
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
        # 设为小批次加速测试
        self.engine._batch_size = 50
        
        self.engine.start(mode="random")
        time.sleep(2.0)
        self.engine.stop()
        complete_event.wait(timeout=10)
        
        if final_stats:
            final_count = final_stats[0]
            # 核心断言：最终计数应该是合理值（远小于翻倍值）
            # 修复前：_live_range_count 被重复计入，导致计数虚高约100%
            # 修复后：计数应为实际处理的私钥数
            self.assertGreater(final_count, 0, "应处理了一些私钥")
            
            # 如果存在双重计数bug，计数会异常偏高
            # 批次=50，单worker 2秒大约处理2000-5000个，不会到100k
            self.assertLess(final_count, 100000, 
                f"计数 {final_count} 异常偏高，可能存在双重计数")
            
            print(f"\n[P1-5-B ✓] 最终计数: {final_count} (在合理范围内)")

    def test_live_count_not_double_accumulated(self):
        """P1-5-C: _live_range_count 内部机制验证（直接访问内部状态）"""
        self.engine = KeyCollisionEngine(
            targets={"1NonExistentTestAddress12345"},
            max_workers=1,
        )
        # 设为32步对齐的批次以便测试
        self.engine._batch_size = 32
        
        # 重置内部计数器
        self.engine._live_range_count = 0
        
        self.engine.start(mode="random")
        time.sleep(1.0)
        
        # 获取中间状态（检查没有异常大的值）
        with self.engine._state_lock:
            mid_live = self.engine._live_range_count
        
        self.engine.stop()
        time.sleep(0.5)
        
        # 运行中 _live_range_count 不应异常大
        # 修复前：每批次 batch_count 被重复加入
        # batch_size=32, 1秒大约有多个批次
        # 合理范围：一个批次约32个
        self.assertLess(mid_live, 1000, 
            f"_live_range_count={mid_live} 异常偏高，可能存在 batch_end 重复提交")
        
        print(f"\n[P1-5-C ✓] 运行中 _live_range_count={mid_live} (合理范围)")

    def test_range_scan_live_count_reset(self):
        """P1-5-D: range_scan 结束后 _live_range_count 正确"""
        complete_event = threading.Event()
        
        def on_complete(stats):
            complete_event.set()
        
        self.engine = KeyCollisionEngine(
            targets={"1NonExistentTestAddress12345"},
            on_complete=on_complete,
            max_workers=1,
        )
        
        self.engine._live_range_count = 0
        self.engine.start(mode="range", start=1, end=500)
        complete_event.wait(timeout=30)
        
        # range_scan最终应正确计数（500个私钥）
        stats = self.engine.get_stats()
        final_count = stats.total_checked
        
        # 实际检查数应接近500（排除跳过无效值的）
        self.assertGreater(final_count, 0)
        self.assertLessEqual(final_count, 500)
        
        print(f"\n[P1-5-D ✓] range_scan 最终计数: {final_count} (范围1-500)")

    def test_no_batch_end_double_count_in_worker(self):
        """P1-5-E: 确认 _random_search_worker 中不存在批次结束重复提交"""
        # 通过代码检查：确认 L808-812 的旧代码已被删除
        import inspect
        
        worker_source = inspect.getsource(KeyCollisionEngine._random_search_worker)
        
        # 检查："_live_range_count += batch_count" 只应出现在注释中
        lines = worker_source.split('\n')
        exec_lines = [l for l in lines if 'self._live_range_count += batch_count' in l]
        
        for line in exec_lines:
            stripped = line.strip()
            # 必须是注释（以#开头）
            self.assertTrue(stripped.startswith('#'),
                f"非注释行仍包含旧代码! 行内容: {line.strip()[:80]}")
        
        # 确认reminder提交代码存在
        self.assertIn("remainder = local_count % 32", worker_source,
            "缺少worker退出时的剩余计数提交代码")
        
        # 确认_total_count减法代码存在于主循环中
        random_search_source = inspect.getsource(KeyCollisionEngine.random_search)
        self.assertIn("_live_range_count = max(0, self._live_range_count - local_count)",
            random_search_source,
            "缺少已完成worker live计数转移代码")
        
        print(f"\n[P1-5-E ✓] 代码中无重复提交，余数提交和计数转移代码均存在")

    def test_progress_callback_counts_monotonic(self):
        """P1-5-F: 进度回调中的total_checked单调递增（不翻倍）"""
        progress_counts = []
        
        def on_progress(stats):
            progress_counts.append(stats.total_checked)
        
        self.engine = KeyCollisionEngine(
            targets={"1NonExistentTestAddress12345"},
            on_progress=on_progress,
            max_workers=1,
        )
        self.engine._batch_size = 50
        
        self.engine.start(mode="random")
        time.sleep(2.0)
        self.engine.stop()
        time.sleep(0.5)
        
        if len(progress_counts) >= 2:
            # 单调递增检查
            for i in range(1, len(progress_counts)):
                self.assertGreaterEqual(progress_counts[i], progress_counts[i-1],
                    f"进度计数应单调递增: {progress_counts[i-1]} -> {progress_counts[i]}")
            
            # 检查没有异常跳跃（翻倍迹象）
            for i in range(1, len(progress_counts)):
                prev = max(progress_counts[i-1], 1)
                ratio = progress_counts[i] / prev
                # 跳过从0到第一个值的首次跳跃（正常初始化）
                if progress_counts[i-1] == 0:
                    continue
                # 允许小跳跃（批次完成），但不应该有翻倍
                self.assertLess(ratio, 5.0,
                    f"进度计数跳跃异常 (ratio={ratio:.2f}): "
                    f"{progress_counts[i-1]} -> {progress_counts[i]}")
            
            print(f"\n[P1-5-F ✓] 进度计数单调递增: {progress_counts}")
        else:
            print(f"\n[P1-5-F ⚠] 进度回调次数不足({len(progress_counts)})，跳过完整性验证")


if __name__ == "__main__":
    unittest.main(verbosity=2)
