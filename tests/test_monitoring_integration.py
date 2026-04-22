#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监控系统集成单元测试

测试监控系统与碰撞引擎的集成功能。

测试覆盖:
- KeyCollisionEngine与EnhancedMonitoringSystem集成
- 数据流验证
- 性能监控集成
- 告警集成
- 报告集成
- 生命周期管理
"""

import pytest
import os
import sys
import time
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.key_collision_engine import KeyCollisionEngine
from src.monitoring.monitor_config import MonitorConfig


class TestEngineMonitoringIntegration:
    """测试引擎与监控系统集成"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
    def teardown_method(self):
        """每个测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_engine_creates_enhanced_monitoring(self):
        """测试引擎创建增强监控系统"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=True
        )
        
        assert engine.enhanced_monitoring is not None
        assert engine.data_logger is not None
    
    def test_engine_without_monitoring(self):
        """测试引擎不启用监控"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=False,
            use_enhanced_monitoring=False
        )
        
        assert engine.enhanced_monitoring is None
        assert engine.data_logger is None
    
    def test_engine_monitoring_starts_with_engine(self):
        """测试监控系统随引擎启动"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=True
        )
        
        # 启动引擎
        engine.start(mode="random")
        
        # 验证监控系统已启动
        assert engine.enhanced_monitoring.is_running() is True
        
        # 停止引擎
        engine.stop()
        
        # 验证监控系统已停止
        assert engine.enhanced_monitoring.is_running() is False
    
    def test_engine_monitoring_stops_with_engine(self):
        """测试监控系统随引擎停止"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=True
        )
        
        engine.start(mode="random")
        time.sleep(0.5)
        
        engine.stop()
        
        # 监控系统应该已停止
        assert engine.enhanced_monitoring.is_running() is False


class TestDataFlowIntegration:
    """测试数据流集成"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
    def teardown_method(self):
        """每个测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_performance_data_recorded(self):
        """测试性能数据被记录"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            data_logging_interval=1,
            use_enhanced_monitoring=True
        )
        
        engine.start(mode="random")
        time.sleep(2)  # 等待数据记录
        engine.stop()
        
        # 验证数据已记录
        stats = engine.data_logger.get_statistics()
        assert stats is not None
    
    def test_engine_data_recorded(self):
        """测试引擎数据被记录"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            data_logging_interval=1,
            use_enhanced_monitoring=True
        )
        
        engine.start(mode="random")
        time.sleep(2)
        engine.stop()
        
        # 验证引擎数据
        current_data = engine.data_logger.get_current_data()
        assert current_data is not None


class TestMonitoringLifecycle:
    """测试监控生命周期"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
    def test_monitoring_initialization_error(self):
        """测试监控初始化错误处理"""
        # 模拟监控初始化失败
        with patch('src.monitoring.enhanced_monitoring.EnhancedMonitoringSystem',
                   side_effect=RuntimeError("Init failed")):
            engine = KeyCollisionEngine(
                targets=self.targets,
                data_logging_enabled=True,
                use_enhanced_monitoring=True
            )
            
            # 引擎应该降级处理
            assert engine.data_logging_enabled is False or engine.enhanced_monitoring is None
    
    def test_engine_restart_with_monitoring(self):
        """测试引擎重启时监控系统正常工作"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=True
        )
        
        # 第一次启动
        engine.start(mode="random")
        time.sleep(0.5)
        engine.stop()
        
        # 第二次启动
        engine.start(mode="random")
        time.sleep(0.5)
        engine.stop()
        
        # 应该正常工作
        assert True


class TestMonitoringWithDifferentModes:
    """测试不同碰撞模式下的监控"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
    def test_monitoring_in_random_mode(self):
        """测试随机模式下的监控"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            data_logging_interval=1,
            use_enhanced_monitoring=True
        )
        
        engine.start(mode="random")
        time.sleep(1)
        engine.stop()
        
        # 验证数据记录
        stats = engine.data_logger.get_statistics()
        assert stats['total_checks'] > 0
    
    def test_monitoring_in_brute_force_mode(self):
        """测试暴力穷举模式下的监控"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            data_logging_interval=1,
            use_enhanced_monitoring=True
        )
        
        engine.start(mode="brute_force", start=1)
        time.sleep(1)
        engine.stop()
        
        # 验证数据记录
        stats = engine.data_logger.get_statistics()
        assert stats['total_checks'] > 0


class TestMonitoringErrorScenarios:
    """测试监控错误场景"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
    def test_monitoring_continues_on_data_error(self):
        """测试数据记录错误时监控继续运行"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=True
        )
        
        # 模拟数据记录器错误
        original_record = engine.data_logger.record_performance_data
        engine.data_logger.record_performance_data = Mock(
            side_effect=RuntimeError("Record failed")
        )
        
        engine.start(mode="random")
        time.sleep(1)
        
        # 引擎应该仍在运行
        assert engine.is_running() is True
        
        engine.stop()
    
    def test_engine_continues_on_monitoring_error(self):
        """测试监控错误时引擎继续运行"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=True
        )
        
        # 模拟监控系统错误
        engine.enhanced_monitoring._monitoring_loop = Mock(
            side_effect=RuntimeError("Monitoring failed")
        )
        
        engine.start(mode="random")
        time.sleep(0.5)
        
        # 引擎应该仍在运行
        assert engine.is_running() is True
        
        engine.stop()


class TestMonitoringConfiguration:
    """测试监控配置"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
    def test_custom_logging_interval(self):
        """测试自定义日志间隔"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            data_logging_interval=2,
            use_enhanced_monitoring=True
        )
        
        # 验证配置已应用
        assert engine.data_logging_interval == 2
    
    def test_enhanced_monitoring_enabled(self):
        """测试增强监控启用"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=True
        )
        
        assert engine.enhanced_monitoring is not None
        assert engine.data_logger is not None
    
    def test_traditional_mode_enabled(self):
        """测试传统模式启用"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            use_enhanced_monitoring=False
        )
        
        # 应该使用传统DataLogger
        assert engine.enhanced_monitoring is None
        assert engine.data_logger is not None


class TestMonitoringDataIntegrity:
    """测试监控数据完整性"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
    def teardown_method(self):
        """每个测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_data_consistency(self):
        """测试数据一致性"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            data_logging_interval=1,
            use_enhanced_monitoring=True
        )
        
        engine.start(mode="random")
        time.sleep(2)
        engine.stop()
        
        # 获取统计数据
        stats = engine.data_logger.get_statistics()
        
        # 验证数据一致性
        assert stats['total_checks'] >= 0
        assert stats['speed'] >= 0
        assert stats['total_matches'] >= 0
    
    def test_no_data_loss_on_stop(self):
        """测试停止时无数据丢失"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            data_logging_enabled=True,
            data_logging_interval=1,
            use_enhanced_monitoring=True
        )
        
        engine.start(mode="random")
        time.sleep(2)
        
        # 获取停止前的统计
        stats_before = engine.data_logger.get_statistics()
        
        engine.stop()
        
        # 获取停止后的统计
        stats_after = engine.data_logger.get_statistics()
        
        # 数据应该保持一致
        assert stats_before['total_checks'] == stats_after['total_checks']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
