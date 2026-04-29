#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志系统兼容性测试

验证日志系统在不同版本的平台环境和浏览器中的表现，确保日志功能在各种场景下均能正常工作。
"""
import os
import sys
import unittest
import logging
import platform
import tempfile
import json
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.logger import setup_logger, get_logger, get_sampled_logger
from src.utils.logging_config import init_logging, get_configured_logger
from src.utils.log_collection_rules import init_log_collection_rules, get_rule_manager
from src.utils.log_dependency_manager import init_log_dependencies, check_dependencies
from src.utils.log_performance_optimizer import get_performance_optimizer, optimize_logger
from src.utils.log_platform_adapter import get_platform_adapter, get_platform_info


class TestLogCompatibility(unittest.TestCase):
    """日志系统兼容性测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建临时目录用于测试日志文件
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test.log')
        
        # 初始化日志依赖
        init_log_dependencies()
        
        # 初始化日志系统
        init_logging({
            "level": "DEBUG",
            "file": self.log_file,
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        })
        
        # 初始化日志收集规则
        self.rule_config = os.path.join(self.temp_dir, 'log_rules.json')
        init_log_collection_rules(self.rule_config)
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def tearDown(self):
        """清理测试环境"""
        # 关闭所有日志处理器
        import logging
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            try:
                handler.close()
            except Exception:
                pass
        
        # 清理临时文件
        import time
        time.sleep(0.1)  # 等待文件操作完成
        
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
            if os.path.exists(self.log_file + '.async'):
                os.remove(self.log_file + '.async')
            if os.path.exists(self.log_file + '.format'):
                os.remove(self.log_file + '.format')
            if os.path.exists(self.rule_config):
                os.remove(self.rule_config)
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"清理测试环境时出错: {e}")
    
    def test_platform_compatibility(self):
        """测试平台兼容性"""
        platform_info = get_platform_info()
        self.assertIsInstance(platform_info, dict)
        self.assertIn('name', platform_info)
        self.assertIn('version', platform_info)
        self.assertIn('architecture', platform_info)
        
        # 测试平台适配器
        adapter = get_platform_adapter()
        self.assertIsNotNone(adapter)
        
        # 测试平台特定的日志目录
        log_dir = adapter.get_log_directory()
        self.assertIsInstance(log_dir, str)
        self.assertTrue(os.path.isabs(log_dir))
        
        # 测试目录创建
        self.assertTrue(adapter.ensure_directory(self.temp_dir))
    
    def test_logger_initialization(self):
        """测试日志记录器初始化"""
        # 测试基本日志记录器
        logger = get_logger('test.logger')
        self.assertIsInstance(logger, logging.Logger)
        
        # 测试配置好的日志记录器
        configured_logger = get_configured_logger('test.configured')
        self.assertIsInstance(configured_logger, logging.Logger)
        
        # 测试采样日志记录器
        sampled_logger = get_sampled_logger('test.sampled', sample_rate=10)
        self.assertIsNotNone(sampled_logger)
    
    def test_log_levels(self):
        """测试日志级别"""
        # 直接使用setup_logger创建带有文件处理器的日志记录器
        logger = setup_logger('test.levels', level='DEBUG', log_file=self.log_file)
        
        # 测试不同级别的日志
        logger.debug('Debug message')
        logger.info('Info message')
        logger.warning('Warning message')
        logger.error('Error message')
        logger.critical('Critical message')
        
        # 关闭处理器
        for handler in logger.handlers:
            handler.close()
        
        # 验证日志文件存在
        self.assertTrue(os.path.exists(self.log_file))
    
    def test_log_collection_rules(self):
        """测试日志收集规则"""
        # 直接创建一个新的规则管理器实例，确保使用正确的配置文件路径
        from src.utils.log_collection_rules import LogCollectionRuleManager, LogCollectionRule
        rule_manager = LogCollectionRuleManager(self.rule_config)
        self.assertIsNotNone(rule_manager)
        
        # 测试规则匹配
        rules = rule_manager.get_matching_rules('core.module', 'INFO', 'Test message')
        self.assertIsInstance(rules, list)
        
        # 测试添加规则
        new_rule = LogCollectionRule(
            name="Test Rule",
            module_pattern="test.*",
            level="DEBUG"
        )
        rule_manager.add_rule(new_rule)
        
        # 测试保存和加载规则
        rule_manager.save_rules()
        # 确保规则文件存在
        self.assertTrue(os.path.exists(self.rule_config))
    
    def test_log_dependencies(self):
        """测试日志依赖"""
        dependencies = check_dependencies()
        self.assertIsInstance(dependencies, dict)
        
        # 验证核心依赖存在
        self.assertTrue(dependencies.get('logging', True))
        self.assertTrue(dependencies.get('json', True))
    
    def test_log_performance_optimizer(self):
        """测试日志性能优化器"""
        optimizer = get_performance_optimizer()
        self.assertIsNotNone(optimizer)
        
        # 测试优化日志记录器
        logger = get_logger('test.optimizer')
        optimized_logger = optimizer.optimize_logger(logger)
        self.assertIsInstance(optimized_logger, logging.Logger)
        
        # 测试统计信息
        stats = optimizer.get_stats()
        self.assertIsInstance(stats, dict)
    
    def test_log_file_operations(self):
        """测试日志文件操作"""
        # 直接使用setup_logger创建带有文件处理器的日志记录器
        logger = setup_logger('test.file', level='INFO', log_file=self.log_file)
        test_message = 'Test log message'
        logger.info(test_message)
        
        # 关闭处理器
        for handler in logger.handlers:
            handler.close()
        
        # 验证日志文件内容
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn(test_message, content)
    
    def test_async_logging(self):
        """测试异步日志"""
        from src.utils.logger import AsyncFileHandler
        
        # 创建异步文件处理器
        async_handler = AsyncFileHandler(self.log_file + '.async')
        logger = get_logger('test.async')
        logger.addHandler(async_handler)
        
        # 测试异步日志写入
        for i in range(100):
            logger.info(f'Async log message {i}')
        
        # 关闭异步处理器
        async_handler.close()
        
        # 验证异步日志文件存在
        self.assertTrue(os.path.exists(self.log_file + '.async'))
    
    def test_sampled_logging(self):
        """测试采样日志"""
        # 先创建基础日志记录器
        base_logger = setup_logger('test.sampled', level='INFO', log_file=self.log_file)
        # 创建采样日志记录器
        sampled_logger = get_sampled_logger('test.sampled', sample_rate=10)
        
        # 测试采样日志写入
        for i in range(100):
            sampled_logger.info(f'Sampled log message {i}')
        
        # 关闭处理器
        for handler in base_logger.handlers:
            handler.close()
        
        # 验证日志文件存在
        self.assertTrue(os.path.exists(self.log_file))
    
    def test_platform_specific_handlers(self):
        """测试平台特定的处理器"""
        from src.utils.log_platform_adapter import get_platform_specific_handlers
        
        handlers = get_platform_specific_handlers()
        self.assertIsInstance(handlers, dict)
        self.assertIn('file_handler', handlers)
        self.assertIn('console_handler', handlers)
    
    def test_error_handling(self):
        """测试错误处理"""
        # 直接使用setup_logger创建带有文件处理器的日志记录器
        logger = setup_logger('test.error', level='ERROR', log_file=self.log_file)
        
        # 测试异常日志
        try:
            raise ValueError('Test error')
        except ValueError:
            logger.exception('Exception occurred')
        
        # 关闭处理器
        for handler in logger.handlers:
            handler.close()
        
        # 验证日志文件存在
        self.assertTrue(os.path.exists(self.log_file))
    
    def test_log_formatting(self):
        """测试日志格式化"""
        # 测试自定义格式
        custom_logger = setup_logger(
            'test.format',
            level='INFO',
            log_file=self.log_file + '.format',
            format='%(levelname)s: %(message)s'
        )
        
        test_message = 'Custom format test'
        custom_logger.info(test_message)
        
        # 关闭处理器
        for handler in custom_logger.handlers:
            handler.close()
        
        # 验证日志文件内容
        self.assertTrue(os.path.exists(self.log_file + '.format'))
        with open(self.log_file + '.format', 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('INFO: ' + test_message, content)


if __name__ == '__main__':
    unittest.main()
