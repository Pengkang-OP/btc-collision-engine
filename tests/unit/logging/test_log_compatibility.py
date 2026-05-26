#!/usr/bin/env python3
"""日志系统兼容性测试

验证日志系统在不同版本的平台环境和浏览器中的表现，确保日志功能在各种场景下均能正常工作。
"""

import logging
import os
import pathlib
import tempfile
from src.utils.log_collection_rules import init_log_collection_rules
from src.utils.log_dependency_manager import check_dependencies, init_log_dependencies
from src.utils.log_performance_optimizer import get_performance_optimizer
from src.utils.log_platform_adapter import get_platform_adapter, get_platform_info
from src.utils.logger import get_logger, get_sampled_logger, setup_logger
from src.utils.logging_config import get_configured_logger, init_logging


class TestLogCompatibility:
    """日志系统兼容性测试"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录用于测试日志文件
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test.log")

        # 初始化日志依赖
        init_log_dependencies()

        # 初始化日志系统
        init_logging(
            {
                "level": "DEBUG",
                "file": self.log_file,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        )

        # 初始化日志收集规则
        self.rule_config = os.path.join(self.temp_dir, "log_rules.json")
        init_log_collection_rules(self.rule_config)

        # 确保日志目录存在
        pathlib.Path(os.path.dirname(self.log_file)).mkdir(exist_ok=True, parents=True)

    def tearDown(self):
        """清理测试环境"""
        # 关闭所有日志处理器
        import logging

        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            try:
                handler.close()
            except (OSError, RuntimeError):
                pass  # handler关闭失败不影响测试

        # 清理临时文件
        import time

        time.sleep(0.1)  # 等待文件操作完成

        try:
            if pathlib.Path(self.log_file).exists():
                pathlib.Path(self.log_file).unlink()
            if pathlib.Path(self.log_file + ".async").exists():
                pathlib.Path(self.log_file + ".async").unlink()
            if pathlib.Path(self.log_file + ".format").exists():
                pathlib.Path(self.log_file + ".format").unlink()
            if pathlib.Path(self.rule_config).exists():
                pathlib.Path(self.rule_config).unlink()
            if pathlib.Path(self.temp_dir).exists():
                import shutil

                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"清理测试环境时出错: {e}")

    def test_platform_compatibility(self):
        """测试平台兼容性"""
        platform_info = get_platform_info()
        assert isinstance(platform_info, dict)
        assert "name" in platform_info
        assert "version" in platform_info
        assert "architecture" in platform_info

        # 测试平台适配器
        adapter = get_platform_adapter()
        assert adapter is not None

        # 测试平台特定的日志目录
        log_dir = adapter.get_log_directory()
        assert isinstance(log_dir, str)
        assert pathlib.Path(log_dir.is_absolute())

        # 测试目录创建
        assert adapter.ensure_directory(self.temp_dir)

    def test_logger_initialization(self):
        """测试日志记录器初始化"""
        # 测试基本日志记录器
        logger = get_logger("test.logger")
        assert isinstance(logger, logging.Logger)

        # 测试配置好的日志记录器
        configured_logger = get_configured_logger("test.configured")
        assert isinstance(configured_logger, logging.Logger)

        # 测试采样日志记录器
        sampled_logger = get_sampled_logger("test.sampled", sample_rate=10)
        assert sampled_logger is not None

    def test_log_levels(self):
        """测试日志级别"""
        # 直接使用setup_logger创建带有文件处理器的日志记录器
        logger = setup_logger("test.levels", level="DEBUG", log_file=self.log_file)

        # 测试不同级别的日志
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # 关闭处理器
        for handler in logger.handlers:
            handler.close()

        # 验证日志文件存在
        assert pathlib.Path(self.log_file.exists())

    def test_log_collection_rules(self):
        """测试日志收集规则"""
        # 直接创建一个新的规则管理器实例，确保使用正确的配置文件路径
        from src.utils.log_collection_rules import LogCollectionRule, LogCollectionRuleManager

        rule_manager = LogCollectionRuleManager(self.rule_config)
        assert rule_manager is not None

        # 测试规则匹配
        rules = rule_manager.get_matching_rules("core.module", "INFO", "Test message")
        assert isinstance(rules, list)

        # 测试添加规则
        new_rule = LogCollectionRule(name="Test Rule", module_pattern="test.*", level="DEBUG")
        rule_manager.add_rule(new_rule)

        # 测试保存和加载规则
        rule_manager.save_rules()
        # 确保规则文件存在
        assert pathlib.Path(self.rule_config.exists())

    def test_log_dependencies(self):
        """测试日志依赖"""
        dependencies = check_dependencies()
        assert isinstance(dependencies, dict)

        # 验证核心依赖存在
        assert dependencies.get("logging", True)
        assert dependencies.get("json", True)

    def test_log_performance_optimizer(self):
        """测试日志性能优化器"""
        optimizer = get_performance_optimizer()
        assert optimizer is not None

        # 测试优化日志记录器
        logger = get_logger("test.optimizer")
        optimized_logger = optimizer.optimize_logger(logger)
        assert isinstance(optimized_logger, logging.Logger)

        # 测试统计信息
        stats = optimizer.get_stats()
        assert isinstance(stats, dict)

    def test_log_file_operations(self):
        """测试日志文件操作"""
        # 直接使用setup_logger创建带有文件处理器的日志记录器
        logger = setup_logger("test.file", level="INFO", log_file=self.log_file)
        test_message = "Test log message"
        logger.info(test_message)

        # 关闭处理器
        for handler in logger.handlers:
            handler.close()

        # 验证日志文件内容
        assert pathlib.Path(self.log_file.exists())
        with pathlib.Path(self.log_file).open(encoding="utf-8") as f:
            content = f.read()
            assert test_message in content

    def test_async_logging(self):
        """测试异步日志"""
        from src.utils.logger import AsyncFileHandler

        # 创建异步文件处理器
        async_handler = AsyncFileHandler(self.log_file + ".async")
        logger = get_logger("test.async")
        logger.addHandler(async_handler)

        # 测试异步日志写入
        for i in range(100):
            logger.info("Async log message %s", i)

        # 关闭异步处理器
        async_handler.close()

        # 验证异步日志文件存在
        assert pathlib.Path(self.log_file + ".async".exists())

    def test_sampled_logging(self):
        """测试采样日志"""
        # 先创建基础日志记录器
        base_logger = setup_logger("test.sampled", level="INFO", log_file=self.log_file)
        # 创建采样日志记录器
        sampled_logger = get_sampled_logger("test.sampled", sample_rate=10)

        # 测试采样日志写入
        for i in range(100):
            sampled_logger.info("Sampled log message %s", i)

        # 关闭处理器
        for handler in base_logger.handlers:
            handler.close()

        # 验证日志文件存在
        assert pathlib.Path(self.log_file.exists())

    def test_platform_specific_handlers(self):
        """测试平台特定的处理器"""
        from src.utils.log_platform_adapter import get_platform_specific_handlers

        handlers = get_platform_specific_handlers()
        assert isinstance(handlers, dict)
        assert "file_handler" in handlers
        assert "console_handler" in handlers

    def test_error_handling(self):
        """测试错误处理"""
        # 直接使用setup_logger创建带有文件处理器的日志记录器
        logger = setup_logger("test.error", level="ERROR", log_file=self.log_file)

        # 测试异常日志
        try:
            raise ValueError("Test error")
        except ValueError:
            logger.exception("Exception occurred")

        # 关闭处理器
        for handler in logger.handlers:
            handler.close()

        # 验证日志文件存在
        assert pathlib.Path(self.log_file.exists())

    def test_log_formatting(self):
        """测试日志格式化"""
        # 测试自定义格式
        custom_logger = setup_logger(
            "test.format",
            level="INFO",
            log_file=self.log_file + ".format",
            format="%(levelname)s: %(message)s",
        )

        test_message = "Custom format test"
        custom_logger.info(test_message)

        # 关闭处理器
        for handler in custom_logger.handlers:
            handler.close()

        # 验证日志文件内容
        assert pathlib.Path(self.log_file + ".format".exists())
        with pathlib.Path(self.log_file + ".format").open(encoding="utf-8") as f:
            content = f.read()
            assert "INFO: " + test_message in content

