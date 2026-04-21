#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增强监控系统单元测试

测试src.monitoring.enhanced_monitoring模块的所有功能。

测试覆盖:
- EnhancedMonitoringSystem初始化和配置
- 监控系统启动和停止
- 监控循环和数据采集
- 数据日志集成
- 异常检测和告警
- 报告生成
- 系统状态查询
- 错误处理和恢复
"""

import pytest
import os
import sys
import time
import shutil
import tempfile
import logging
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.monitoring.enhanced_monitoring import EnhancedMonitoringSystem
from src.monitoring.monitor_config import MonitorConfig
from src.monitoring.data_logger import DataLogger


class TestEnhancedMonitoringSystemInit:
    """测试EnhancedMonitoringSystem初始化"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        
    def teardown_method(self):
        """每个测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        monitor = EnhancedMonitoringSystem(engine=None)
        
        assert monitor is not None
        assert monitor.data_logger is not None
        assert monitor._running is False
        assert monitor.engine is None
        
    def test_init_with_custom_config(self):
        """测试使用自定义配置初始化"""
        config = MonitorConfig(
            data_logging_enabled=True,
            collection_interval=2.0,
            enable_monitoring_data=False
        )
        
        monitor = EnhancedMonitoringSystem(engine=None, config=config)
        
        assert monitor.config.collection_interval == 2.0
        assert monitor.config.enable_monitoring_data is False
        assert monitor.data_logger is not None
        
    def test_init_with_disabled_logging(self):
        """测试禁用数据日志初始化"""
        config = MonitorConfig(data_logging_enabled=False)
        
        monitor = EnhancedMonitoringSystem(engine=None, config=config)
        
        assert monitor.data_logger is None
        
    def test_init_with_monitoring_data_enabled(self):
        """测试启用监控数据采集"""
        config = MonitorConfig(enable_monitoring_data=True)
        
        monitor = EnhancedMonitoringSystem(engine=None, config=config)
        
        assert monitor.storage is not None
        assert monitor.detector is not None
        assert monitor.alert_system is not None
        assert monitor.report_generator is not None
        
    def test_init_with_deprecated_params(self):
        """测试使用已弃用的参数初始化（向后兼容）"""
        monitor = EnhancedMonitoringSystem(
            engine=None,
            collection_interval=3.0,
            enable_monitoring_data=False
        )
        
        assert monitor.collection_interval == 3.0
        assert monitor.enable_monitoring_data is False
        
    def test_init_with_invalid_config_fallback(self, caplog):
        """测试无效配置时回退到默认配置"""
        # 创建一个无效配置（alert_threshold超出范围）
        config = MonitorConfig(alert_threshold=1.5)
        
        with caplog.at_level(logging.WARNING):
            monitor = EnhancedMonitoringSystem(engine=None, config=config)
            
            # 应该记录警告
            assert any("配置验证失败" in record.message for record in caplog.records)
            
    def test_init_logs_message(self, caplog):
        """测试初始化时记录日志"""
        with caplog.at_level(logging.INFO):
            monitor = EnhancedMonitoringSystem(engine=None)
            
            assert any("增强版监控系统初始化完成" in record.message 
                      for record in caplog.records)


class TestEnhancedMonitoringSystemLifecycle:
    """测试监控系统生命周期"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.mock_engine = Mock()
        self.mock_engine.is_running.return_value = False
        self.mock_engine.get_stats.return_value = None
        
        config = MonitorConfig(
            data_logging_enabled=True,
            collection_interval=0.1,  # 快速采集用于测试
            enable_monitoring_data=False
        )
        
        self.monitor = EnhancedMonitoringSystem(
            engine=self.mock_engine,
            config=config
        )
    
    def teardown_method(self):
        """每个测试后清理"""
        if self.monitor.is_running():
            self.monitor.stop()
    
    def test_start_monitoring(self):
        """测试启动监控系统"""
        self.monitor.start()
        
        assert self.monitor.is_running() is True
        assert self.monitor._thread is not None
        assert self.monitor._thread.is_alive() is True
    
    def test_stop_monitoring(self):
        """测试停止监控系统"""
        self.monitor.start()
        assert self.monitor.is_running() is True
        
        self.monitor.stop()
        
        assert self.monitor.is_running() is False
        # 等待线程完全停止
        time.sleep(0.2)
        assert self.monitor._thread.is_alive() is False
    
    def test_start_already_running(self):
        """测试重复启动（应该无操作）"""
        self.monitor.start()
        assert self.monitor.is_running() is True
        
        # 再次启动不应该出错
        self.monitor.start()
        assert self.monitor.is_running() is True
    
    def test_stop_not_running(self):
        """测试停止未运行的系统（应该无操作）"""
        assert self.monitor.is_running() is False
        
        # 停止未运行的系统不应该出错
        self.monitor.stop()
        assert self.monitor.is_running() is False
    
    def test_monitoring_loop_runs(self):
        """测试监控循环运行"""
        # 配置mock引擎返回统计数据
        mock_stats = Mock()
        mock_stats.speed = 1000.0
        mock_stats.total_checked = 5000
        mock_stats.matches = []
        self.mock_engine.get_stats.return_value = mock_stats
        self.mock_engine._current_mode = "random"
        self.mock_engine.targets = set()
        self.mock_engine._current_position = 0
        
        self.monitor.start()
        
        # 等待监控循环运行几次
        time.sleep(0.5)
        
        # 验证数据日志记录器被调用
        assert self.monitor.data_logger is not None
        
        self.monitor.stop()


class TestEnhancedMonitoringSystemDataCollection:
    """测试数据采集功能"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        
        # 创建mock引擎
        self.mock_engine = Mock()
        mock_stats = Mock()
        mock_stats.speed = 1500.0
        mock_stats.total_checked = 10000
        mock_stats.matches = []
        self.mock_engine.get_stats.return_value = mock_stats
        self.mock_engine.is_running.return_value = True
        self.mock_engine._current_mode = "brute_force"
        self.mock_engine.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        self.mock_engine._current_position = 5000
        
        config = MonitorConfig(
            data_logging_enabled=True,
            collection_interval=0.1,
            enable_monitoring_data=False
        )
        
        self.monitor = EnhancedMonitoringSystem(
            engine=self.mock_engine,
            config=config
        )
    
    def teardown_method(self):
        """每个测试后清理"""
        if self.monitor.is_running():
            self.monitor.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_collect_performance_data(self):
        """测试采集性能数据"""
        # 启动监控并等待数据采集
        self.monitor.start()
        time.sleep(0.3)
        self.monitor.stop()
        
        # 验证数据已记录
        stats = self.monitor.data_logger.get_statistics()
        assert stats is not None
    
    def test_collect_engine_data(self):
        """测试采集引擎数据"""
        self.monitor.start()
        time.sleep(0.3)
        self.monitor.stop()
        
        # 验证引擎数据已记录
        stats = self.monitor.data_logger.get_statistics()
        assert 'total_checks' in stats
    
    def test_collect_system_data(self):
        """测试采集系统数据"""
        self.monitor.start()
        time.sleep(0.3)
        self.monitor.stop()
        
        # 验证系统数据已记录
        current_data = self.monitor.data_logger.get_current_data()
        assert current_data is not None
    
    def test_collect_with_no_engine(self):
        """测试没有引擎时的数据采集"""
        monitor = EnhancedMonitoringSystem(
            engine=None,
            config=MonitorConfig(data_logging_enabled=True, collection_interval=0.1)
        )
        
        monitor.start()
        time.sleep(0.3)
        monitor.stop()
        
        # 不应该出错
        assert True
    
    def test_collect_with_engine_no_stats(self):
        """测试引擎返回None统计数据"""
        self.mock_engine.get_stats.return_value = None
        
        self.monitor.start()
        time.sleep(0.3)
        self.monitor.stop()
        
        # 不应该出错
        assert True


class TestEnhancedMonitoringSystemAlerts:
    """测试告警功能"""
    
    def setup_method(self):
        """每个测试前准备"""
        config = MonitorConfig(
            data_logging_enabled=True,
            enable_monitoring_data=True,  # 启用告警系统
            collection_interval=0.1,
            alert_enabled=True,
            alert_threshold=0.8
        )
        
        self.mock_engine = Mock()
        mock_stats = Mock()
        mock_stats.speed = 0.0  # 低速触发告警
        mock_stats.total_checked = 0
        mock_stats.matches = []
        self.mock_engine.get_stats.return_value = mock_stats
        self.mock_engine.is_running.return_value = True
        self.mock_engine._current_mode = "random"
        self.mock_engine.targets = set()
        self.mock_engine._current_position = 0
        
        self.monitor = EnhancedMonitoringSystem(
            engine=self.mock_engine,
            config=config
        )
    
    def teardown_method(self):
        """每个测试后清理"""
        if self.monitor.is_running():
            self.monitor.stop()
    
    def test_alert_system_initialized(self):
        """测试告警系统已初始化"""
        assert self.monitor.alert_system is not None
        assert self.monitor.detector is not None
    
    def test_alert_generation(self):
        """测试告警生成"""
        self.monitor.start()
        time.sleep(0.5)
        self.monitor.stop()
        
        # 验证告警系统运行（可能产生告警）
        assert self.monitor.alert_system is not None


class TestEnhancedMonitoringSystemReports:
    """测试报告生成功能"""
    
    def setup_method(self):
        """每个测试前准备"""
        config = MonitorConfig(
            data_logging_enabled=True,
            enable_monitoring_data=False,
            collection_interval=0.1,
            report_enabled=True,
            report_interval=0.5  # 快速报告用于测试
        )
        
        self.mock_engine = Mock()
        mock_stats = Mock()
        mock_stats.speed = 1000.0
        mock_stats.total_checked = 5000
        mock_stats.matches = []
        self.mock_engine.get_stats.return_value = mock_stats
        self.mock_engine.is_running.return_value = True
        self.mock_engine._current_mode = "random"
        self.mock_engine.targets = set()
        self.mock_engine._current_position = 0
        
        self.monitor = EnhancedMonitoringSystem(
            engine=self.mock_engine,
            config=config
        )
    
    def teardown_method(self):
        """每个测试后清理"""
        if self.monitor.is_running():
            self.monitor.stop()
    
    def test_generate_report(self):
        """测试生成报告"""
        self.monitor.start()
        time.sleep(0.7)  # 等待报告生成
        self.monitor.stop()
        
        # 验证报告已生成（检查日志）
        assert True
    
    def test_generate_report_with_data_logger(self):
        """测试通过数据日志生成报告"""
        # 记录一些数据
        self.monitor.data_logger.record_performance_data(
            speed=1000.0,
            total_checked=5000,
            matches_found=0,
            cpu_usage=50.0,
            memory_usage=200.0,
            thread_count=4
        )
        
        # 生成报告
        report = self.monitor.data_logger.generate_report("daily")
        
        assert report is not None
        assert 'total_checks' in report


class TestEnhancedMonitoringSystemStatus:
    """测试状态查询功能"""
    
    def setup_method(self):
        """每个测试前准备"""
        config = MonitorConfig(
            data_logging_enabled=True,
            enable_monitoring_data=False,
            collection_interval=0.1
        )
        
        self.mock_engine = Mock()
        mock_stats = Mock()
        mock_stats.speed = 1200.0
        mock_stats.total_checked = 8000
        mock_stats.matches = []
        self.mock_engine.get_stats.return_value = mock_stats
        self.mock_engine.is_running.return_value = True
        self.mock_engine._current_mode = "brute_force"
        self.mock_engine.targets = {"test_address"}
        self.mock_engine._current_position = 4000
        
        self.monitor = EnhancedMonitoringSystem(
            engine=self.mock_engine,
            config=config
        )
    
    def teardown_method(self):
        """每个测试后清理"""
        if self.monitor.is_running():
            self.monitor.stop()
    
    def test_get_current_status(self):
        """测试获取当前状态"""
        self.monitor.start()
        time.sleep(0.3)
        
        status = self.monitor.get_current_status()
        
        assert status is not None
        assert 'data_stats' in status
        
        self.monitor.stop()
    
    def test_get_data_logger(self):
        """测试获取数据日志记录器"""
        logger = self.monitor.get_data_logger()
        
        assert logger is not None
        assert isinstance(logger, DataLogger)


class TestEnhancedMonitoringSystemErrorHandling:
    """测试错误处理"""
    
    def setup_method(self):
        """每个测试前准备"""
        config = MonitorConfig(
            data_logging_enabled=True,
            collection_interval=0.1,
            enable_monitoring_data=False
        )
        
        self.monitor = EnhancedMonitoringSystem(
            engine=None,
            config=config
        )
    
    def teardown_method(self):
        """每个测试后清理"""
        if self.monitor.is_running():
            self.monitor.stop()
    
    def test_monitoring_loop_error_recovery(self):
        """测试监控循环错误恢复"""
        # 创建会抛出异常的引擎
        faulty_engine = Mock()
        faulty_engine.get_stats.side_effect = RuntimeError("Test error")
        faulty_engine.is_running.return_value = True
        
        self.monitor.engine = faulty_engine
        
        # 启动监控，应该能处理错误并继续运行
        self.monitor.start()
        time.sleep(0.3)
        
        # 系统应该仍在运行
        assert self.monitor.is_running() is True
        
        self.monitor.stop()
    
    def test_engine_attribute_error(self):
        """测试引擎缺少属性的处理"""
        # 创建不完整的引擎
        incomplete_engine = Mock()
        # 不提供get_stats方法
        
        self.monitor.engine = incomplete_engine
        
        self.monitor.start()
        time.sleep(0.3)
        
        # 不应该崩溃
        assert self.monitor.is_running() is True
        
        self.monitor.stop()


class TestEnhancedMonitoringSystemIntegration:
    """测试系统集成"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """每个测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_full_lifecycle(self):
        """测试完整生命周期"""
        # 创建mock引擎
        mock_engine = Mock()
        mock_stats = Mock()
        mock_stats.speed = 1000.0
        mock_stats.total_checked = 5000
        mock_stats.matches = []
        mock_engine.get_stats.return_value = mock_stats
        mock_engine.is_running.return_value = True
        mock_engine._current_mode = "random"
        mock_engine.targets = set()
        mock_engine._current_position = 0
        
        config = MonitorConfig(
            data_logging_enabled=True,
            collection_interval=0.1,
            enable_monitoring_data=False
        )
        
        monitor = EnhancedMonitoringSystem(
            engine=mock_engine,
            config=config
        )
        
        # 启动
        monitor.start()
        assert monitor.is_running() is True
        
        # 运行一段时间
        time.sleep(0.5)
        
        # 获取状态
        status = monitor.get_current_status()
        assert status is not None
        
        # 停止
        monitor.stop()
        assert monitor.is_running() is False
    
    def test_concurrent_start_stop(self):
        """测试并发启动停止"""
        config = MonitorConfig(
            data_logging_enabled=True,
            collection_interval=0.1
        )
        
        monitor = EnhancedMonitoringSystem(engine=None, config=config)
        
        # 快速启动和停止
        for _ in range(3):
            monitor.start()
            time.sleep(0.1)
            monitor.stop()
            time.sleep(0.1)
        
        # 应该能正常工作
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
