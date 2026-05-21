"""统计系统性能监控 (src/cli/stats_performance_monitor.py) 单元测试。

覆盖: PerformanceSample, StatsPerformanceMonitor, StatsUpdateProfiler,
       get_global_monitor, profile_stats_update
目标: 25% → 85%+
"""

import threading
import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

from src.cli.stats_performance_monitor import (
    PerformanceSample,
    StatsPerformanceMonitor,
    StatsUpdateProfiler,
    get_global_monitor,
    profile_stats_update,
)

# ── PerformanceSample ──────────────────────────────────────────


class TestPerformanceSample(unittest.TestCase):
    """PerformanceSample dataclass 测试。"""

    def test_create_sample(self):
        """创建 PerformanceSample 并验证字段值。"""
        sample = PerformanceSample(
            timestamp=1234567890.0,
            latency_ms=5.5,
            lock_contention=10.0,
            throughput=1000.0,
            memory_usage_mb=256.0,
            cpu_usage=45.0,
        )
        self.assertEqual(sample.timestamp, 1234567890.0)
        self.assertEqual(sample.latency_ms, 5.5)
        self.assertEqual(sample.lock_contention, 10.0)
        self.assertEqual(sample.throughput, 1000.0)
        self.assertEqual(sample.memory_usage_mb, 256.0)
        self.assertEqual(sample.cpu_usage, 45.0)

    def test_sample_equality(self):
        """相同字段的 PerformanceSample 相等。"""
        a = PerformanceSample(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        b = PerformanceSample(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        self.assertEqual(a, b)

    def test_sample_inequality(self):
        """不同字段的 PerformanceSample 不相等。"""
        a = PerformanceSample(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        b = PerformanceSample(2.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        self.assertNotEqual(a, b)


# ── StatsPerformanceMonitor ────────────────────────────────────


class TestStatsPerformanceMonitor(unittest.TestCase):
    """StatsPerformanceMonitor 测试。

    使用 mock 避免实际创建线程和访问 psutil。
    """

    def setUp(self):
        self._thread_patcher = patch("threading.Thread")
        self._mock_thread_cls = self._thread_patcher.start()
        self._mock_thread = MagicMock()
        self._mock_thread_cls.return_value = self._mock_thread

        self._psutil_patcher = patch("psutil.Process")
        self._mock_process_cls = self._psutil_patcher.start()
        self._mock_process = MagicMock()
        self._mock_process.memory_info.return_value.rss = 128 * 1024 * 1024
        self._mock_process.cpu_percent.return_value = 25.0
        self._mock_process_cls.return_value = self._mock_process

    def tearDown(self):
        self._thread_patcher.stop()
        self._psutil_patcher.stop()

    def _make_monitor(self, thresholds=None):
        """创建监控器，mock 掉 _monitor_loop 避免后台线程干扰。"""
        with patch.object(StatsPerformanceMonitor, "_monitor_loop"):
            return StatsPerformanceMonitor(alert_thresholds=thresholds)

    # ── __init__ ───────────────────────────────────────────────

    def test_init_default_thresholds(self):
        """默认告警阈值。"""
        with patch.object(StatsPerformanceMonitor, "_monitor_loop"):
            monitor = StatsPerformanceMonitor()
            self.assertEqual(monitor._thresholds["latency_ms"], 100.0)
            self.assertEqual(monitor._thresholds["lock_contention"], 0.5)
            self.assertEqual(monitor._thresholds["memory_mb"], 512.0)
            self.assertEqual(monitor._thresholds["cpu_usage"], 80.0)

    def test_init_custom_thresholds(self):
        """自定义告警阈值完全替换默认值（非合并）。"""
        custom = {"latency_ms": 50.0, "memory_mb": 256.0}
        with patch.object(StatsPerformanceMonitor, "_monitor_loop"):
            monitor = StatsPerformanceMonitor(alert_thresholds=custom)
            self.assertEqual(monitor._thresholds["latency_ms"], 50.0)
            self.assertEqual(monitor._thresholds["memory_mb"], 256.0)
            # 自定义阈值完全替换，未指定的键不存在
            self.assertNotIn("lock_contention", monitor._thresholds)

    def test_init_creates_stop_event(self):
        """__init__ 创建 _stop_event。"""
        monitor = self._make_monitor()
        self.assertIsInstance(monitor._stop_event, threading.Event)

    def test_init_creates_samples_deque(self):
        """__init__ 创建 _samples deque（最大长度 100）。"""
        monitor = self._make_monitor()
        self.assertIsInstance(monitor._samples, deque)
        self.assertEqual(monitor._samples.maxlen, 100)

    def test_init_initializes_counters(self):
        """__init__ 初始化计数器为零。"""
        monitor = self._make_monitor()
        self.assertEqual(monitor._update_count, 0)
        self.assertEqual(monitor._total_latency_ms, 0.0)
        self.assertEqual(monitor._lock_wait_time_ms, 0.0)

    def test_init_starts_monitor_thread(self):
        """__init__ 启动监控线程。"""
        self._make_monitor()
        self._mock_thread_cls.assert_called_once()
        # 验证 target 是 _monitor_loop, daemon=True
        _, kwargs = self._mock_thread_cls.call_args
        self.assertTrue(kwargs.get("daemon"))

    def test_init_alert_callback_none(self):
        """__init__ 后 _alert_callback 为 None。"""
        monitor = self._make_monitor()
        self.assertIsNone(monitor._alert_callback)

    def test_init_creates_psutil_process(self):
        """__init__ 创建 psutil.Process()。"""
        self._make_monitor()
        self._mock_process_cls.assert_called_once()

    # ── set_alert_callback ─────────────────────────────────────

    def test_set_alert_callback(self):
        """设置告警回调。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        self.assertIs(monitor._alert_callback, cb)

    def test_set_alert_callback_none(self):
        """清除告警回调。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        monitor.set_alert_callback(None)
        self.assertIsNone(monitor._alert_callback)

    # ── record_update ──────────────────────────────────────────

    def test_record_update_increments_counters(self):
        """record_update 累加计数器。"""
        monitor = self._make_monitor()
        monitor.record_update(5.0, 1.0)
        self.assertEqual(monitor._update_count, 1)
        self.assertEqual(monitor._total_latency_ms, 5.0)
        self.assertEqual(monitor._lock_wait_time_ms, 1.0)

    def test_record_update_multiple_calls(self):
        """多次 record_update 累加。"""
        monitor = self._make_monitor()
        monitor.record_update(2.0, 0.5)
        monitor.record_update(3.0, 0.5)
        self.assertEqual(monitor._update_count, 2)
        self.assertEqual(monitor._total_latency_ms, 5.0)
        self.assertEqual(monitor._lock_wait_time_ms, 1.0)

    # ── _take_sample ───────────────────────────────────────────

    def test_take_sample_elapsed_zero_returns_early(self):
        """elapsed <= 0 → 提前返回，不更新 _last_check_time。"""
        monitor = self._make_monitor()
        monitor._last_check_time = time.time() + 999  # 未来时间
        prev_last_check = monitor._last_check_time
        monitor._take_sample()
        # _last_check_time 未更新（因为提前返回）
        self.assertEqual(monitor._last_check_time, prev_last_check)

    def test_take_sample_collects_metrics(self):
        """正常采样收集各指标。"""
        monitor = self._make_monitor()
        monitor._last_check_time = time.time() - 2.0
        monitor.record_update(10.0, 2.0)
        monitor.record_update(20.0, 4.0)
        monitor._take_sample()
        # 计数器被重置
        self.assertEqual(monitor._update_count, 0)
        # samples 队列应有新采样
        self.assertEqual(len(monitor._samples), 1)
        sample = monitor._samples[0]
        # avg latency = (10+20)/2 = 15
        self.assertAlmostEqual(sample.latency_ms, 15.0)
        # avg lock_wait = (2+4)/2 = 3
        # lock_contention = 3 / (15 + 0.001) * 100 ≈ 19.9987
        expected_lock = 3.0 / (15.0 + 0.001) * 100
        self.assertAlmostEqual(sample.lock_contention, expected_lock, places=1)
        # throughput = 2 / elapsed
        self.assertAlmostEqual(sample.throughput, 2.0 / 2.0, places=1)

    def test_take_sample_psutil_exception_handled(self):
        """psutil 异常 → memory/cpu 设为 0.0。"""
        monitor = self._make_monitor()
        monitor._last_check_time = time.time() - 1.0
        monitor.record_update(1.0, 0.0)
        # 让 psutil 抛异常
        monitor._process.memory_info.side_effect = OSError("access denied")
        monitor._take_sample()
        sample = monitor._samples[0]
        self.assertEqual(sample.memory_usage_mb, 0.0)
        self.assertEqual(sample.cpu_usage, 0.0)

    def test_take_sample_zero_updates(self):
        """update_count=0 时不会除零。"""
        monitor = self._make_monitor()
        monitor._last_check_time = time.time() - 1.0
        # 不调用 record_update，update_count=0
        monitor._take_sample()
        sample = monitor._samples[0]
        self.assertEqual(sample.latency_ms, 0.0)
        self.assertEqual(sample.lock_contention, 0.0)
        self.assertEqual(sample.throughput, 0.0)

    # ── _monitor_loop ──────────────────────────────────────────

    def test_monitor_loop_iterates_and_stops(self):
        """_monitor_loop 在 stop_event 设置后退出 (L92-94)。"""
        monitor = self._make_monitor()
        call_count = [0]

        def _counting_sleep(_):
            call_count[0] += 1
            if call_count[0] >= 3:
                monitor._stop_event.set()

        with patch.object(monitor, "_take_sample"):
            with patch("time.sleep", side_effect=_counting_sleep):
                monitor._monitor_loop()
        self.assertEqual(call_count[0], 3)

    # ── _check_alerts ──────────────────────────────────────────

    def test_check_alerts_no_callback_returns_early(self):
        """无回调 → _check_alerts 直接返回。"""
        monitor = self._make_monitor()
        sample = PerformanceSample(0, 200.0, 90.0, 0, 1024.0, 99.0)
        # 不应抛异常
        monitor._check_alerts(sample)

    def test_check_alerts_latency_triggers(self):
        """延迟超过阈值 → 触发延迟告警。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        sample = PerformanceSample(0, 200.0, 0, 0, 0, 0)
        monitor._check_alerts(sample)
        # latency_ms=200 > threshold=100
        cb.assert_called_once_with("latency_ms", 200.0, 100.0)

    def test_check_alerts_lock_contention_triggers(self):
        """锁竞争超过阈值 → 触发锁竞争告警。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        # lock_contention > threshold * 100 = 50
        sample = PerformanceSample(0, 0, 60.0, 0, 0, 0)
        monitor._check_alerts(sample)
        cb.assert_called_once_with("lock_contention", 60.0, 50.0)

    def test_check_alerts_memory_triggers(self):
        """内存使用超过阈值 → 触发内存告警。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        sample = PerformanceSample(0, 0, 0, 0, 1024.0, 0)
        monitor._check_alerts(sample)
        cb.assert_called_once_with("memory_mb", 1024.0, 512.0)

    def test_check_alerts_cpu_triggers(self):
        """CPU 使用超过阈值 → 触发 CPU 告警。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        sample = PerformanceSample(0, 0, 0, 0, 0, 90.0)
        monitor._check_alerts(sample)
        cb.assert_called_once_with("cpu_usage", 90.0, 80.0)

    def test_check_alerts_multiple_triggers(self):
        """多个指标同时超过阈值 → 多次回调。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        sample = PerformanceSample(0, 200.0, 60.0, 0, 1024.0, 90.0)
        monitor._check_alerts(sample)
        self.assertEqual(cb.call_count, 4)

    def test_check_alerts_no_triggers(self):
        """所有指标正常 → 无回调。"""
        monitor = self._make_monitor()
        cb = MagicMock()
        monitor.set_alert_callback(cb)
        sample = PerformanceSample(0, 50.0, 10.0, 0, 256.0, 30.0)
        monitor._check_alerts(sample)
        cb.assert_not_called()

    def test_check_alerts_callback_exception_handled(self):
        """回调抛异常 → 静默处理，不影响其他告警。"""
        monitor = self._make_monitor()
        cb = MagicMock(side_effect=[RuntimeError("boom"), None, None, None])
        monitor.set_alert_callback(cb)
        sample = PerformanceSample(0, 200.0, 60.0, 0, 1024.0, 90.0)
        # 不应抛异常
        monitor._check_alerts(sample)
        # 4 个告警都应触发（即使第一个抛异常）
        self.assertEqual(cb.call_count, 4)

    # ── get_recent_performance ─────────────────────────────────

    def test_get_recent_performance_empty_returns_defaults(self):
        """无采样 → 返回默认值。"""
        monitor = self._make_monitor()
        result = monitor.get_recent_performance()
        self.assertEqual(result["average_latency_ms"], 0.0)
        self.assertEqual(result["average_lock_contention"], 0.0)
        self.assertEqual(result["average_throughput"], 0.0)
        self.assertEqual(result["average_memory_mb"], 0.0)
        self.assertEqual(result["average_cpu_usage"], 0.0)
        self.assertEqual(result["sample_count"], 0)

    def test_get_recent_performance_with_samples(self):
        """有采样 → 返回平均值。"""
        monitor = self._make_monitor()
        now = time.time()
        monitor._samples.append(PerformanceSample(now - 1, 10.0, 5.0, 100.0, 200.0, 30.0))
        monitor._samples.append(PerformanceSample(now - 2, 20.0, 15.0, 200.0, 300.0, 50.0))
        result = monitor.get_recent_performance(window_seconds=5.0)
        self.assertEqual(result["sample_count"], 2)
        self.assertAlmostEqual(result["average_latency_ms"], 15.0)
        self.assertAlmostEqual(result["average_lock_contention"], 10.0)
        self.assertAlmostEqual(result["average_throughput"], 150.0)
        self.assertAlmostEqual(result["average_memory_mb"], 250.0)
        self.assertAlmostEqual(result["average_cpu_usage"], 40.0)

    def test_get_recent_performance_filters_by_window(self):
        """过期采样被窗口过滤。"""
        monitor = self._make_monitor()
        now = time.time()
        # 新采样（窗口内）
        monitor._samples.append(PerformanceSample(now - 1, 10.0, 5.0, 100.0, 200.0, 30.0))
        # 旧采样（窗口外）
        monitor._samples.append(PerformanceSample(now - 100, 20.0, 15.0, 200.0, 300.0, 50.0))
        result = monitor.get_recent_performance(window_seconds=5.0)
        self.assertEqual(result["sample_count"], 1)

    # ── get_performance_report ─────────────────────────────────

    def test_get_performance_report(self):
        """获取完整性能报告包含所有字段。"""
        monitor = self._make_monitor()
        report = monitor.get_performance_report()
        self.assertIn("timestamp", report)
        self.assertIn("recent_performance", report)
        self.assertIn("thresholds", report)
        self.assertIn("status", report)
        self.assertEqual(report["thresholds"], monitor._thresholds)

    # ── _get_health_status ─────────────────────────────────────

    def test_health_status_healthy(self):
        """所有指标正常 → healthy。"""
        monitor = self._make_monitor()
        recent = {
            "average_latency_ms": 50.0,
            "average_lock_contention": 10.0,
            "average_memory_mb": 256.0,
            "average_cpu_usage": 30.0,
            "average_throughput": 0,
            "sample_count": 1,
        }
        self.assertEqual(monitor._get_health_status(recent), "healthy")

    def test_health_status_warning_latency(self):
        """延迟超标 → warning。"""
        monitor = self._make_monitor()
        recent = {
            "average_latency_ms": 200.0,
            "average_lock_contention": 10.0,
            "average_memory_mb": 256.0,
            "average_cpu_usage": 30.0,
            "average_throughput": 0,
            "sample_count": 1,
        }
        self.assertEqual(monitor._get_health_status(recent), "warning")

    def test_health_status_warning_lock(self):
        """锁竞争超标 → warning。"""
        monitor = self._make_monitor()
        recent = {
            "average_latency_ms": 50.0,
            "average_lock_contention": 60.0,
            "average_memory_mb": 256.0,
            "average_cpu_usage": 30.0,
            "average_throughput": 0,
            "sample_count": 1,
        }
        self.assertEqual(monitor._get_health_status(recent), "warning")

    def test_health_status_critical_memory(self):
        """内存超标 → critical。"""
        monitor = self._make_monitor()
        recent = {
            "average_latency_ms": 50.0,
            "average_lock_contention": 10.0,
            "average_memory_mb": 1024.0,
            "average_cpu_usage": 30.0,
            "average_throughput": 0,
            "sample_count": 1,
        }
        self.assertEqual(monitor._get_health_status(recent), "critical")

    def test_health_status_warning_cpu(self):
        """CPU 超标 → warning。"""
        monitor = self._make_monitor()
        recent = {
            "average_latency_ms": 50.0,
            "average_lock_contention": 10.0,
            "average_memory_mb": 256.0,
            "average_cpu_usage": 90.0,
            "average_throughput": 0,
            "sample_count": 1,
        }
        self.assertEqual(monitor._get_health_status(recent), "warning")

    # ── stop ───────────────────────────────────────────────────

    def test_stop_sets_event_and_joins(self):
        """stop 设置停止事件并 join 线程。"""
        monitor = self._make_monitor()
        monitor.stop()
        self.assertTrue(monitor._stop_event.is_set())
        self._mock_thread.join.assert_called_once_with(timeout=1.0)


# ── StatsUpdateProfiler ────────────────────────────────────────


class TestStatsUpdateProfiler(unittest.TestCase):
    """StatsUpdateProfiler 测试。"""

    def setUp(self):
        self._mock_monitor = MagicMock(spec=StatsPerformanceMonitor)
        self._profiler = StatsUpdateProfiler(self._mock_monitor)

    def test_init_stores_monitor(self):
        """__init__ 保存 monitor 引用。"""
        profiler = StatsUpdateProfiler(self._mock_monitor)
        self.assertIs(profiler._monitor, self._mock_monitor)

    def test_profile_update_calls_record_update(self):
        """profile_update 调用 monitor.record_update。"""

        def dummy_func(x):
            return x * 2

        result = self._profiler.profile_update(dummy_func, 5)
        self.assertEqual(result, 10)
        # 验证 record_update 被调用
        self._mock_monitor.record_update.assert_called_once()

    def test_profile_update_monitor_none_does_not_crash(self):
        """monitor=None → 不调用 record_update，不抛异常。"""
        profiler = StatsUpdateProfiler(None)
        result = profiler.profile_update(lambda x: x + 1, 1)
        self.assertEqual(result, 2)

    def test_profile_update_passes_args_and_kwargs(self):
        """profile_update 透传 args/kwargs 给被包装函数。"""

        def dummy_func(a, b=0):
            return a + b

        result = self._profiler.profile_update(dummy_func, 3, b=4)
        self.assertEqual(result, 7)
        self._mock_monitor.record_update.assert_called_once()


# ── 全局函数 ───────────────────────────────────────────────────


class TestGlobalFunctions(unittest.TestCase):
    """get_global_monitor / profile_stats_update 测试。"""

    def setUp(self):
        # 保存并清除全局状态
        import src.cli.stats_performance_monitor as spm

        self._orig_global = spm._global_monitor
        spm._global_monitor = None
        self._thread_patcher = patch("threading.Thread")
        self._thread_patcher.start()
        self._psutil_patcher = patch("psutil.Process")
        self._psutil_patcher.start()

    def tearDown(self):
        import src.cli.stats_performance_monitor as spm

        spm._global_monitor = self._orig_global
        self._thread_patcher.stop()
        self._psutil_patcher.stop()

    def test_get_global_monitor_creates_instance(self):
        """首次调用创建实例。"""
        with patch.object(StatsPerformanceMonitor, "_monitor_loop"):
            monitor = get_global_monitor()
            self.assertIsInstance(monitor, StatsPerformanceMonitor)

    def test_get_global_monitor_returns_singleton(self):
        """重复调用返回同一实例。"""
        with patch.object(StatsPerformanceMonitor, "_monitor_loop"):
            m1 = get_global_monitor()
            m2 = get_global_monitor()
            self.assertIs(m1, m2)

    def test_profile_stats_update_decorator(self):
        """profile_stats_update 装饰器包装函数。"""
        with patch.object(StatsPerformanceMonitor, "_monitor_loop"):

            @profile_stats_update
            def add_one(x):
                return x + 1

            result = add_one(41)
            self.assertEqual(result, 42)


if __name__ == "__main__":
    unittest.main()
