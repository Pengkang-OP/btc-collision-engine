#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据日志系统测试

测试数据日志系统的各项功能，包括性能记录、错误记录、报告生成等。
"""

import os
import sys
import time
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.monitoring.data_logger import DataLogger
from src.utils import init_logging


class TestDataLogger(unittest.TestCase):
    """测试数据日志记录器"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        self.data_logger = DataLogger(storage_dir=self.test_dir)
        
        # 初始化日志系统
        try:
            init_logging()
        except:
            pass  # 可能已经初始化过
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.data_logger)
        self.assertTrue(os.path.exists(self.data_logger.storage_dir))
        self.assertTrue(os.path.exists(self.data_logger.current_data_file))
        self.assertTrue(os.path.exists(self.data_logger.history_data_file))
        self.assertTrue(os.path.exists(self.data_logger.error_log_file))
        self.assertTrue(os.path.exists(self.data_logger.performance_log_file))
    
    def test_record_performance_data(self):
        """测试性能数据记录"""
        self.data_logger.record_performance_data(
            speed=1500.5,
            total_checked=50000,
            matches_found=2,
            cpu_usage=65.2,
            memory_usage=345.6,
            thread_count=4
        )
        
        # 检查当前数据
        current_data = self.data_logger.get_current_data()
        self.assertIn("performance", current_data)
        perf_data = current_data["performance"]
        self.assertEqual(perf_data["speed"], 1500.5)
        self.assertEqual(perf_data["total_checked"], 50000)
        self.assertEqual(perf_data["matches_found"], 2)
        self.assertEqual(perf_data["cpu_usage"], 65.2)
        self.assertEqual(perf_data["memory_usage"], 345.6)
        self.assertEqual(perf_data["thread_count"], 4)
    
    def test_record_system_data(self):
        """测试系统数据记录"""
        self.data_logger.record_system_data(
            os_name="test_os",
            python_version="3.9.0",
            pid=12345,
            uptime=3600.0
        )
        
        current_data = self.data_logger.get_current_data()
        self.assertIn("system", current_data)
        sys_data = current_data["system"]
        self.assertEqual(sys_data["os"], "test_os")
        self.assertEqual(sys_data["python_version"], "3.9.0")
        self.assertEqual(sys_data["pid"], 12345)
        self.assertEqual(sys_data["uptime"], 3600.0)
    
    def test_record_engine_data(self):
        """测试引擎数据记录"""
        self.data_logger.record_engine_data(
            mode="test_mode",
            target_count=100,
            is_running=True,
            current_position=5000,
            additional_info={"test_key": "test_value"}
        )
        
        current_data = self.data_logger.get_current_data()
        self.assertIn("engine", current_data)
        eng_data = current_data["engine"]
        self.assertEqual(eng_data["mode"], "test_mode")
        self.assertEqual(eng_data["target_count"], 100)
        self.assertTrue(eng_data["is_running"])
        self.assertEqual(eng_data["current_position"], 5000)
        self.assertEqual(eng_data["test_key"], "test_value")
    
    def test_record_error(self):
        """测试错误记录"""
        try:
            raise ValueError("Test error")
        except Exception as e:
            self.data_logger.record_error(
                error_type="test_error",
                message="This is a test error",
                exception=e,
                context={"test": True}
            )
        
        # 检查错误日志文件
        with open(self.data_logger.error_log_file, 'r', encoding='utf-8') as f:
            errors = json.load(f)
        
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(error["type"], "test_error")
        self.assertEqual(error["message"], "This is a test error")
        self.assertEqual(error["exception_type"], "ValueError")
        self.assertEqual(error["context"]["test"], True)
    
    def test_save_and_load_current_data(self):
        """测试当前数据的保存和加载"""
        # 记录一些数据
        self.data_logger.record_performance_data(1000.0, 10000, 1, 50.0, 200.0, 2)
        self.data_logger.record_system_data("test", "3.9.0", 1234, 100.0)
        self.data_logger.record_engine_data("test", 50, True, 5000)
        
        # 保存数据
        self.data_logger.save_current_data()
        
        # 检查文件是否存在
        self.assertTrue(os.path.exists(self.data_logger.current_data_file))
        
        # 读取并验证数据
        with open(self.data_logger.current_data_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        self.assertIn("performance", saved_data)
        self.assertIn("system", saved_data)
        self.assertIn("engine", saved_data)
    
    def test_get_statistics(self):
        """测试统计信息获取"""
        # 记录多个性能数据点
        for i in range(5):
            self.data_logger.record_performance_data(
                speed=1000.0 + i * 100,
                total_checked=10000 + i * 1000,
                matches_found=i,
                cpu_usage=50.0 + i * 5,
                memory_usage=200.0 + i * 20,
                thread_count=2
            )
        
        stats = self.data_logger.get_statistics()
        
        self.assertEqual(stats["total_checks"], 14000)  # 最后一个值
        self.assertEqual(stats["matches_found"], 4)     # 最后一个值
        self.assertEqual(stats["avg_speed"], 1200.0)    # (1000+1100+1200+1300+1400)/5
        self.assertEqual(stats["max_speed"], 1400.0)
        self.assertEqual(stats["min_speed"], 1000.0)
    
    def test_generate_report(self):
        """测试报告生成"""
        # 记录一些数据
        for i in range(10):
            self.data_logger.record_performance_data(
                speed=1000.0 + i * 50,
                total_checked=10000 + i * 1000,
                matches_found=i % 3,
                cpu_usage=50.0 + i * 2,
                memory_usage=200.0 + i * 10,
                thread_count=2
            )
        
        # 保存历史数据
        self.data_logger.save_history_data()
        
        # 生成报告
        report = self.data_logger.generate_report("daily")
        
        self.assertIn("summary", report)
        self.assertIn("trends", report)
        self.assertIn("recommendations", report)
        self.assertEqual(report["data_points"], 10)
    
    def test_data_limits(self):
        """测试数据限制功能"""
        # 记录超过限制的数据点
        for i in range(1100):  # 超过1000的限制
            self.data_logger.record_performance_data(
                speed=float(i),
                total_checked=i,
                matches_found=0,
                cpu_usage=50.0,
                memory_usage=200.0,
                thread_count=2
            )
        
        # 保存历史数据
        self.data_logger.save_history_data()
        
        # 检查历史数据文件
        with open(self.data_logger.history_data_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 应该限制在1000条
        self.assertLessEqual(len(history), 1000)
    
    def test_cleanup_old_data(self):
        """测试旧数据清理"""
        # 记录一些数据
        self.data_logger.record_performance_data(1000.0, 10000, 0, 50.0, 200.0, 2)
        self.data_logger.save_history_data()
        
        # 清理数据（设置很短的保留时间）
        self.data_logger.cleanup_old_data(max_age_days=0)  # 清理所有数据
        
        # 检查历史数据
        with open(self.data_logger.history_data_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 数据应该被清理
        self.assertEqual(len(history), 0)


class TestEnhancedMonitoringSystem(unittest.TestCase):
    """测试增强版监控系统"""
    
    def setUp(self):
        """测试前准备"""
        from src.monitoring.enhanced_monitoring import EnhancedMonitoringSystem
        self.test_dir = tempfile.mkdtemp()
        
        # 创建模拟引擎
        self.mock_engine = MagicMock()
        self.mock_engine.is_running.return_value = False
        self.mock_engine.get_stats.return_value = None
        
        # 创建增强监控系统（但不启动）
        self.monitor = EnhancedMonitoringSystem(engine=self.mock_engine, collection_interval=1)
    
    def tearDown(self):
        """测试后清理"""
        if hasattr(self.monitor, 'data_logger') and self.monitor.data_logger:
            test_dir = self.monitor.data_logger.storage_dir
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)
        
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.monitor)
        self.assertIsNotNone(self.monitor.data_logger)
        self.assertFalse(self.monitor.is_running())
    
    def test_data_logger_integration(self):
        """测试数据日志集成"""
        # 获取数据日志记录器
        data_logger = self.monitor.get_data_logger()
        self.assertIsNotNone(data_logger)
        
        # 验证可以正常使用
        data_logger.record_performance_data(1000.0, 10000, 0, 50.0, 200.0, 2)
        stats = data_logger.get_statistics()
        self.assertEqual(stats["total_checks"], 10000)


if __name__ == "__main__":
    unittest.main()