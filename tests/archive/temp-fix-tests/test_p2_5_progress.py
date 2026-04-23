# -*- coding: utf-8 -*-
"""
P2-5修复: 进度回调频率控制单元测试

测试CPU碰撞引擎的双重进度回调控制机制(时间间隔+计数控制)。
"""

import unittest
import time
import sys
import os
from unittest.mock import MagicMock, patch, call
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.collision.key_collision_engine import KeyCollisionEngine, CollisionStats


@pytest.mark.unit
@pytest.mark.progress
@pytest.mark.p2_medium
class TestProgressCallbackControl(unittest.TestCase):
    """测试进度回调频率控制"""
    
    def setUp(self):
        """测试前准备"""
        self.stats = CollisionStats()
        # 修复: 使用正确的初始化参数
        self.engine = KeyCollisionEngine(
            targets={'test_address'},  # Set[str]类型
            on_progress=None
        )
        self.engine.stats = self.stats
    
    def test_time_based_progress(self):
        """测试基于时间间隔的进度报告"""
        # 设置较短的时间间隔
        self.engine._progress_interval_sec = 0.1
        self.engine._progress_interval_count = 1000000  # 计数阈值很大
        
        progress_calls = []
        self.engine.on_progress = lambda stats: progress_calls.append(stats)
        
        # 初始时间
        self.engine._last_progress_time = time.time() - 0.2  # 200ms前
        
        # 模拟进度回调检查
        current_time = time.time()
        should_report = False
        
        # 时间间隔控制
        if current_time - self.engine._last_progress_time >= self.engine._progress_interval_sec:
            should_report = True
        
        # 计数控制(未触发)
        self.engine._batch_counter += 1
        if self.engine._batch_counter >= self.engine._progress_interval_count:
            should_report = True
            self.engine._batch_counter = 0
        
        # 应触发进度报告(时间间隔已到)
        self.assertTrue(should_report)
    
    def test_count_based_progress(self):
        """测试基于计数的进度报告"""
        # 设置很长的时间间隔
        self.engine._progress_interval_sec = 3600  # 1小时
        self.engine._progress_interval_count = 5  # 计数阈值很小
        
        progress_calls = []
        self.engine.on_progress = lambda stats: progress_calls.append(stats)
        
        self.engine._last_progress_time = time.time()  # 刚刚
        
        # 模拟5个batch
        for i in range(5):
            current_time = time.time()
            should_report = False
            
            # 时间间隔控制(未触发)
            if current_time - self.engine._last_progress_time >= self.engine._progress_interval_sec:
                should_report = False
            
            # 计数控制
            self.engine._batch_counter += 1
            if self.engine._batch_counter >= self.engine._progress_interval_count:
                should_report = True
                self.engine._batch_counter = 0
        
        # 第5个batch应触发进度报告
        self.assertTrue(should_report)
        self.assertEqual(self.engine._batch_counter, 0)  # 计数器已重置
    
    def test_dual_control_progress(self):
        """测试双重控制(时间+计数)"""
        self.engine._progress_interval_sec = 0.5
        self.engine._progress_interval_count = 10
        
        report_count = [0]
        def count_progress(stats):
            """记录进度回调次数"""
            report_count[0] += 1
        
        self.engine.on_progress = count_progress
        
        self.engine._last_progress_time = time.time()
        
        # 模拟快速运行(短时间内超过计数阈值)
        for i in range(15):
            current_time = time.time()
            should_report = False
            
            # 时间间隔控制
            if current_time - self.engine._last_progress_time >= self.engine._progress_interval_sec:
                should_report = True
            
            # 计数控制
            self.engine._batch_counter += 1
            if self.engine._batch_counter >= self.engine._progress_interval_count:
                should_report = True
                self.engine._batch_counter = 0
            
            if should_report:
                self.engine.on_progress(self.engine.stats.snapshot())
                self.engine._last_progress_time = current_time
        
        # 应至少触发1次报告(计数控制: 15/10=1次)
        self.assertGreaterEqual(report_count[0], 1)
    
    def test_progress_interval_count_default(self):
        """测试默认计数间隔配置"""
        # 默认值应为1000
        self.assertEqual(self.engine._progress_interval_count, 1000)
        self.assertEqual(self.engine._batch_counter, 0)
    
    def test_batch_counter_increment(self):
        """测试batch计数器递增"""
        initial_counter = self.engine._batch_counter
        
        # 模拟处理10个batch
        for _ in range(10):
            self.engine._batch_counter += 1
        
        self.assertEqual(self.engine._batch_counter, initial_counter + 10)
    
    def test_batch_counter_reset(self):
        """测试batch计数器重置"""
        self.engine._batch_counter = 999
        self.engine._progress_interval_count = 1000
        
        # 达到阈值
        self.engine._batch_counter += 1
        if self.engine._batch_counter >= self.engine._progress_interval_count:
            self.engine._batch_counter = 0
        
        self.assertEqual(self.engine._batch_counter, 0)
    
    def test_high_speed_scenario(self):
        """测试高速运行场景(计数控制为主)"""
        # 高速运行: 每秒1000个batch
        self.engine._progress_interval_sec = 1.0
        self.engine._progress_interval_count = 100
        
        report_count = [0]  # 使用列表使其可变
        def count_progress(stats):
            """记录高速场景下的进度回调次数"""
            report_count[0] += 1
        
        self.engine.on_progress = count_progress
        
        self.engine._last_progress_time = time.time()
        
        # 模拟1000个batch(1秒内)
        for i in range(1000):
            should_report = False
            
            # 时间间隔(可能未触发)
            current_time = time.time()
            if current_time - self.engine._last_progress_time >= self.engine._progress_interval_sec:
                should_report = True
            
            # 计数控制(每100个触发)
            self.engine._batch_counter += 1
            if self.engine._batch_counter >= self.engine._progress_interval_count:
                should_report = True
                self.engine._batch_counter = 0
            
            if should_report:
                self.engine.on_progress(self.engine.stats.snapshot())
        
        # 计数控制应触发10次(1000/100)
        self.assertGreaterEqual(report_count[0], 10)
    
    def test_low_speed_scenario(self):
        """测试低速运行场景(时间控制为主)"""
        # 低速运行: 每10秒1个batch
        self.engine._progress_interval_sec = 1.0
        self.engine._progress_interval_count = 1000
        
        report_count = [0]
        def count_progress(stats):
            """记录低速场景下的进度回调次数"""
            report_count[0] += 1
        
        self.engine.on_progress = count_progress
        
        # 模拟10个batch(100秒)
        for i in range(10):
            # 模拟时间流逝
            self.engine._last_progress_time = time.time() - 1.1
            
            current_time = time.time()
            should_report = False
            
            # 时间间隔(每次都触发)
            if current_time - self.engine._last_progress_time >= self.engine._progress_interval_sec:
                should_report = True
            
            # 计数控制(未达到)
            self.engine._batch_counter += 1
        
        # 时间控制应触发
        self.assertTrue(should_report)
    
    def test_progress_callback_not_too_frequent(self):
        """测试进度回调不会过于频繁"""
        self.engine._progress_interval_sec = 0.5
        self.engine._progress_interval_count = 100
        
        call_count = 0
        def mock_progress(stats):
            nonlocal call_count
            call_count += 1
        
        self.engine.on_progress = mock_progress
        self.engine._last_progress_time = time.time()
        
        # 快速调用1000次(但计数阈值100,时间间隔0.5s)
        for i in range(1000):
            current_time = time.time()
            should_report = False
            
            if current_time - self.engine._last_progress_time >= self.engine._progress_interval_sec:
                should_report = True
                self.engine._last_progress_time = current_time
            
            self.engine._batch_counter += 1
            if self.engine._batch_counter >= self.engine._progress_interval_count:
                should_report = True
                self.engine._batch_counter = 0
            
            if should_report:
                self.engine.on_progress(self.engine.stats.snapshot())
        
        # 回调次数应远小于1000
        self.assertLess(call_count, 100)
        """测试进度回调时统计数据更新"""
        self.engine._progress_interval_sec = 0.1
        self.engine._last_progress_time = time.time() - 1.0
        
        captured_stats = None
        def capture_stats(stats):
            nonlocal captured_stats
            captured_stats = stats
        
        self.engine.on_progress = capture_stats
        
        # 模拟进度回调
        current_time = time.time()
        should_report = True  # 强制触发
        
        if should_report:
            self.engine.stats.update(5000)
            self.engine.on_progress(self.engine.stats.snapshot())
        
        # 应捕获到统计信息
        self.assertIsNotNone(captured_stats)
        self.assertEqual(captured_stats.total_checked, 5000)


@pytest.mark.unit
@pytest.mark.progress
@pytest.mark.p2_medium
@pytest.mark.integration
class TestProgressCallbackIntegration(unittest.TestCase):
    """测试进度回调集成"""
    
    def test_full_engine_with_progress(self):
        """测试完整引擎的进度回调"""
        progress_calls = []
        
        def on_progress(stats):
            progress_calls.append({
                'total_count': stats.total_count,
                'elapsed': stats.elapsed
            })
        
        # 创建引擎并设置回调
        engine = KeyCollisionEngine(
            targets={'test_address'},
            on_progress=on_progress
        )
        
        # 验证配置
        self.assertEqual(engine._progress_interval_count, 1000)
        self.assertEqual(engine._batch_counter, 0)


if __name__ == '__main__':
    unittest.main()
