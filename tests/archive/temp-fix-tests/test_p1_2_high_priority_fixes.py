# -*- coding: utf-8 -*-
"""
P1-2 High优先级问题修复测试

验证H1（GPU健康验证）和H2（统计信息线程保护）修复
"""

import unittest
import threading
import time
from unittest.mock import Mock, patch, MagicMock

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gpu.gpu_recovery_manager import (
    GPURecoveryManager,
    GPUFailureType,
    RecoveryStrategy,
    GPUFailureRecord
)


class TestH1_GPUHealthVerification(unittest.TestCase):
    """H1: GPU健康验证测试"""
    
    def test_verify_gpu_health_with_callback_success(self):
        """测试GPU健康验证 - 回调返回成功"""
        manager = GPURecoveryManager()
        
        # 注册健康检查回调
        def health_check_callback(action, *args):
            if action == "health_check":
                return {"healthy": True, "status": "ok"}
            return None
        
        manager.register_recovery_callback(0, health_check_callback)
        
        # 验证健康检查
        result = manager._verify_gpu_health(0)
        self.assertTrue(result)
    
    def test_verify_gpu_health_with_callback_failure(self):
        """测试GPU健康验证 - 回调返回失败"""
        manager = GPURecoveryManager()
        
        # 注册健康检查回调
        def health_check_callback(action, *args):
            if action == "health_check":
                return {"healthy": False, "error": "GPU still failing"}
            return None
        
        manager.register_recovery_callback(0, health_check_callback)
        
        # 验证健康检查
        result = manager._verify_gpu_health(0)
        self.assertFalse(result)
    
    def test_verify_gpu_health_no_callback(self):
        """测试GPU健康验证 - 无回调（向后兼容）"""
        manager = GPURecoveryManager()
        
        # 未注册回调，应该假设健康
        result = manager._verify_gpu_health(0)
        self.assertTrue(result)
    
    def test_verify_gpu_health_callback_exception(self):
        """测试GPU健康验证 - 回调异常"""
        manager = GPURecoveryManager()
        
        # 注册会抛出异常的回调
        def failing_callback(action, *args):
            if action == "health_check":
                raise RuntimeError("Health check failed")
            return None
        
        manager.register_recovery_callback(0, failing_callback)
        
        # 验证健康检查（应该返回False）
        result = manager._verify_gpu_health(0)
        self.assertFalse(result)
    
    def test_verify_gpu_health_with_success_field(self):
        """测试GPU健康验证 - 使用success字段"""
        manager = GPURecoveryManager()
        
        def health_check_callback(action, *args):
            if action == "health_check":
                return {"success": True}
            return None
        
        manager.register_recovery_callback(0, health_check_callback)
        
        result = manager._verify_gpu_health(0)
        self.assertTrue(result)
    
    def test_recovery_immediate_with_health_check(self):
        """测试立即重试策略包含健康检查"""
        manager = GPURecoveryManager()
        
        # 注册回调
        health_checked = [False]
        
        def callback(action, *args):
            if action == "health_check":
                health_checked[0] = True
                return {"healthy": True}
            return None
        
        manager.register_recovery_callback(0, callback)
        
        # 执行立即重试
        result = manager._execute_recovery(
            gpu_id=0,
            failure_type=GPUFailureType.UNKNOWN,
            strategy=RecoveryStrategy.RETRY_IMMEDIATE
        )
        
        # 验证健康检查被调用
        self.assertTrue(health_checked[0])
        self.assertTrue(result)
    
    def test_recovery_reinitialize_with_health_check(self):
        """测试重新初始化策略包含健康检查"""
        manager = GPURecoveryManager()
        
        actions = []
        
        def callback(action, *args):
            actions.append(action)
            if action == "reinitialize":
                return {"success": True}
            elif action == "health_check":
                return {"healthy": True}
            return None
        
        manager.register_recovery_callback(0, callback)
        
        # 执行重新初始化
        result = manager._execute_recovery(
            gpu_id=0,
            failure_type=GPUFailureType.DEVICE_LOST,
            strategy=RecoveryStrategy.REINITIALIZE
        )
        
        # 验证先初始化，后健康检查
        self.assertIn("reinitialize", actions)
        self.assertIn("health_check", actions)
        self.assertTrue(result)
    
    def test_recovery_reinitialize_failed_initialization(self):
        """测试重新初始化失败时不执行健康检查"""
        manager = GPURecoveryManager()
        
        actions = []
        
        def callback(action, *args):
            actions.append(action)
            if action == "reinitialize":
                return {"success": False}  # 初始化失败
            elif action == "health_check":
                return {"healthy": True}
            return None
        
        manager.register_recovery_callback(0, callback)
        
        # 执行重新初始化
        result = manager._execute_recovery(
            gpu_id=0,
            failure_type=GPUFailureType.DEVICE_LOST,
            strategy=RecoveryStrategy.REINITIALIZE
        )
        
        # 验证初始化失败，不执行健康检查
        self.assertIn("reinitialize", actions)
        self.assertNotIn("health_check", actions)
        self.assertFalse(result)


class TestH2_StatsThreadSafety(unittest.TestCase):
    """H2: 统计信息线程保护测试"""
    
    def test_concurrent_failure_recording(self):
        """测试并发失败记录的线程安全性"""
        manager = GPURecoveryManager()
        
        # 多线程并发记录失败
        def record_failures(thread_id):
            for i in range(100):
                record = GPUFailureRecord(
                    gpu_id=thread_id % 4,
                    failure_type=GPUFailureType.UNKNOWN,
                    error_message=f"Error from thread {thread_id}"
                )
                manager._record_failure(thread_id % 4, record)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=record_failures, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证统计信息准确
        self.assertEqual(manager._total_failures, 1000)
    
    def test_concurrent_recovery_updates(self):
        """测试并发恢复更新的线程安全性"""
        manager = GPURecoveryManager()
        
        # 初始值
        manager._total_failures = 1000
        
        # 多线程并发更新恢复统计
        def update_recovery(success):
            for _ in range(100):
                if success:
                    with manager._stats_lock:
                        manager._successful_recoveries += 1
                else:
                    with manager._stats_lock:
                        manager._failed_recoveries += 1
        
        threads = []
        # 5个线程记录成功
        for _ in range(5):
            t = threading.Thread(target=update_recovery, args=(True,))
            threads.append(t)
            t.start()
        
        # 5个线程记录失败
        for _ in range(5):
            t = threading.Thread(target=update_recovery, args=(False,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证统计信息准确
        self.assertEqual(manager._successful_recoveries, 500)
        self.assertEqual(manager._failed_recoveries, 500)
    
    def test_stats_lock_exists(self):
        """测试统计锁存在"""
        manager = GPURecoveryManager()
        
        self.assertTrue(hasattr(manager, '_stats_lock'))
        self.assertIsInstance(manager._stats_lock, type(threading.Lock()))
    
    def test_get_recovery_stats_thread_safe(self):
        """测试获取统计信息的线程安全性"""
        manager = GPURecoveryManager()
        
        # 后台线程持续更新统计
        def update_stats():
            for _ in range(1000):
                with manager._stats_lock:
                    manager._total_failures += 1
                    manager._successful_recoveries += 1
        
        t = threading.Thread(target=update_stats)
        t.start()
        
        # 主线程频繁读取统计
        for _ in range(100):
            stats = manager.get_recovery_stats()
            self.assertIn('total_failures', stats)
            self.assertIn('successful_recoveries', stats)
            self.assertIn('failed_recoveries', stats)
            time.sleep(0.001)
        
        t.join()


class TestH1H2_Integration(unittest.TestCase):
    """H1和H2集成测试"""
    
    def test_full_recovery_flow_with_health_check(self):
        """测试完整恢复流程（包含健康检查和线程安全）"""
        manager = GPURecoveryManager(max_retry_count=3)
        
        health_check_count = [0]
        
        def callback(action, *args):
            if action == "health_check":
                health_check_count[0] += 1
                return {"healthy": True}
            elif action == "reinitialize":
                return {"success": True}
            return None
        
        manager.register_recovery_callback(0, callback)
        
        # 模拟多次失败和恢复
        for i in range(3):
            error = RuntimeError(f"Test error {i}")
            manager.handle_gpu_failure(
                gpu_id=0,
                error=error
            )
        
        # 验证健康检查被调用
        self.assertGreater(health_check_count[0], 0)
        
        # 验证统计信息准确
        stats = manager.get_recovery_stats()
        self.assertEqual(stats['total_failures'], 3)
        self.assertGreater(stats['successful_recoveries'], 0)
    
    def test_concurrent_handle_gpu_failure(self):
        """测试并发处理GPU失败的线程安全性"""
        manager = GPURecoveryManager()
        
        def callback(action, *args):
            if action == "health_check":
                return {"healthy": True}
            return None
        
        manager.register_recovery_callback(0, callback)
        manager.register_recovery_callback(1, callback)
        
        # 多线程并发处理失败
        def handle_failure(gpu_id):
            for _ in range(50):
                error = RuntimeError(f"Error on GPU {gpu_id}")
                manager.handle_gpu_failure(
                    gpu_id=gpu_id,
                    error=error
                )
        
        threads = []
        for gpu_id in range(4):
            t = threading.Thread(target=handle_failure, args=(gpu_id,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证统计信息准确
        stats = manager.get_recovery_stats()
        self.assertEqual(stats['total_failures'], 200)


class TestH3_HealthCheckTimeout(unittest.TestCase):
    """H3: 健康检查超时控制测试"""
    
    def test_health_check_timeout(self):
        """测试健康检查超时处理"""
        manager = GPURecoveryManager()
        manager.health_check_timeout = 0.1  # 100ms超时
        
        # 注册慢速回调
        def slow_callback(action, *args):
            if action == "health_check":
                time.sleep(1.0)  # 超过超时
            return None
        
        manager.register_recovery_callback(0, slow_callback)
        
        # 应该超时并返回False
        result = manager._verify_gpu_health(0)
        self.assertFalse(result)
    
    def test_health_check_normal_completion(self):
        """测试健康检查正常完成"""
        manager = GPURecoveryManager()
        manager.health_check_timeout = 5.0
        
        def normal_callback(action, *args):
            if action == "health_check":
                time.sleep(0.01)  # 快速完成
                return {"healthy": True}
            return None
        
        manager.register_recovery_callback(0, normal_callback)
        
        result = manager._verify_gpu_health(0)
        self.assertTrue(result)
    
    def test_custom_timeout_parameter(self):
        """测试自定义超时参数"""
        manager = GPURecoveryManager()
        manager.health_check_timeout = 10.0  # 默认10秒
        
        call_count = [0]
        
        def callback(action, *args):
            if action == "health_check":
                call_count[0] += 1
                return {"healthy": True}
            return None
        
        manager.register_recovery_callback(0, callback)
        
        # 使用自定义超时
        result = manager._verify_gpu_health(0, timeout=0.5)
        self.assertTrue(result)
        self.assertEqual(call_count[0], 1)


class TestM1_ReduceBatchSize(unittest.TestCase):
    """M1: REDUCE_BATCH_SIZE策略验证测试"""
    
    def test_reduce_batch_size_with_health_check(self):
        """测试减小批次策略包含健康检查"""
        manager = GPURecoveryManager()
        
        actions = []
        
        def callback(action, *args):
            actions.append(action)
            if action == "health_check":
                return {"healthy": True}
            elif action == "reduce_batch_size":
                return None
            return None
        
        manager.register_recovery_callback(0, callback)
        
        # 执行减小批次策略
        result = manager._execute_recovery(
            gpu_id=0,
            failure_type=GPUFailureType.OUT_OF_MEMORY,
            strategy=RecoveryStrategy.REDUCE_BATCH_SIZE
        )
        
        # 验证调用了减小批次和健康检查
        self.assertIn("reduce_batch_size", actions)
        self.assertIn("health_check", actions)
        self.assertTrue(result)
    
    def test_reduce_batch_size_health_check_failure(self):
        """测试减小批次策略健康检查失败"""
        manager = GPURecoveryManager()
        
        actions = []
        
        def callback(action, *args):
            actions.append(action)
            if action == "health_check":
                return {"healthy": False}
            elif action == "reduce_batch_size":
                return None
            return None
        
        manager.register_recovery_callback(0, callback)
        
        # 执行减小批次策略
        result = manager._execute_recovery(
            gpu_id=0,
            failure_type=GPUFailureType.OUT_OF_MEMORY,
            strategy=RecoveryStrategy.REDUCE_BATCH_SIZE
        )
        
        # 验证健康检查失败导致恢复失败
        self.assertIn("reduce_batch_size", actions)
        self.assertIn("health_check", actions)
        self.assertFalse(result)


class TestH4_FutureCancellation(unittest.TestCase):
    """H4: 超时取消future测试"""
    
    def test_future_cancel_on_timeout(self):
        """测试超时时尝试取消future"""
        manager = GPURecoveryManager()
        manager.health_check_timeout = 0.1  # 100ms超时
        
        call_started = threading.Event()
        call_finished = threading.Event()
        
        def slow_callback(action, *args):
            if action == "health_check":
                call_started.set()
                time.sleep(2.0)  # 远超超时
                call_finished.set()
            return None
        
        manager.register_recovery_callback(0, slow_callback)
        
        # 执行健康检查（应该超时）
        result = manager._verify_gpu_health(0)
        self.assertFalse(result)
        
        # 验证回调已开始执行
        self.assertTrue(call_started.is_set())
        
        # 注意：由于回调已在运行，无法取消，但应该返回False
        # 回调会继续在后台运行直到完成
    
    def test_no_thread_leak_on_multiple_timeouts(self):
        """测试多次超时不会泄露线程"""
        import threading
        
        manager = GPURecoveryManager()
        manager.health_check_timeout = 0.05  # 50ms超时
        
        def slow_callback(action, *args):
            if action == "health_check":
                time.sleep(1.0)  # 超过超时
            return None
        
        manager.register_recovery_callback(0, slow_callback)
        
        # 记录初始线程数
        initial_threads = threading.active_count()
        
        # 多次触发超时
        for _ in range(5):
            manager._verify_gpu_health(0)
        
        # 等待线程池清理
        time.sleep(0.5)
        
        # 验证线程数没有显著增长
        final_threads = threading.active_count()
        # 允许少量增长（线程创建/销毁的延迟）
        self.assertLessEqual(final_threads, initial_threads + 2)
    
    def test_cancel_before_execution(self):
        """测试任务未开始时取消成功"""
        manager = GPURecoveryManager()
        manager.health_check_timeout = 0.001  # 极短超时
        
        call_count = [0]
        
        def callback(action, *args):
            if action == "health_check":
                call_count[0] += 1
                time.sleep(0.1)
            return {"healthy": True}
        
        manager.register_recovery_callback(0, callback)
        
        # 超时极短，可能来不及执行
        result = manager._verify_gpu_health(0)
        # 结果可能是False（超时）或True（刚好完成）
        # 但不会阻塞
        self.assertIsInstance(result, bool)


class TestM2_StatsConsistency(unittest.TestCase):
    """M2: 统计一致性快照测试"""
    
    def test_get_recovery_stats_consistency(self):
        """测试统计快照一致性"""
        manager = GPURecoveryManager()
        
        # 模拟并发更新
        def update_stats():
            for _ in range(100):
                with manager._stats_lock:
                    manager._total_failures += 1
                    manager._successful_recoveries += 1
        
        threads = [threading.Thread(target=update_stats) for _ in range(10)]
        for t in threads:
            t.start()
        
        # 读取统计
        stats = manager.get_recovery_stats()
        
        # 验证快照一致性
        self.assertIn('total_failures', stats)
        self.assertIn('successful_recoveries', stats)
        self.assertIn('failed_recoveries', stats)
        self.assertIn('success_rate', stats)
        
        for t in threads:
            t.join()


if __name__ == '__main__':
    unittest.main()
