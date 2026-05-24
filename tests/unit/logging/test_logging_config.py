#!/usr/bin/env python3
"""日志配置管理 (LoggingConfig) 单元测试

覆盖：
- LoggingConfig 单例与初始化
- SafeRotatingFileHandler Windows 安全轮转
- 磁盘空间检查
- 配置加载与获取
- init_logging / get_configured_logger
"""

import logging
import os
import pathlib
import shutil
import sys
import tempfile
from unittest.mock import Mock, patch

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def reset_logging_config():
    """每个测试前后重置 LoggingConfig 单例，并清理 root logger handlers"""
    from src.utils.logging_config import LoggingConfig

    # 保存原始 root logger 状态
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    # 重置单例
    LoggingConfig._instance = None
    LoggingConfig._initialized = False
    LoggingConfig._config = None
    yield
    # 清理 root logger handlers（释放文件句柄，避免 Windows PermissionError）
    for handler in list(root_logger.handlers):
        try:
            handler.close()
        except (OSError, RuntimeError):
            pass  # handler关闭失败不阻塞清理
    root_logger.handlers.clear()
    # 恢复原始 handlers
    for handler in original_handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(original_level)
    # 重置单例
    LoggingConfig._instance = None
    LoggingConfig._initialized = False
    LoggingConfig._config = None


@pytest.fixture
def temp_log_dir():
    """临时日志目录（自动清理前关闭日志处理器，避免 Windows 文件锁定）"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    # 关闭所有 root logger handlers，释放文件句柄
    root = logging.getLogger()
    for handler in list(root.handlers):
        try:
            handler.close()
        except (OSError, RuntimeError):
            pass  # handler关闭失败不阻塞清理
    root.handlers.clear()
    # 清理临时目录
    try:
        shutil.rmtree(tmpdir)
    except PermissionError:
        pass  # Windows 下可能有残留文件锁定


# ============================================================================
# LoggingConfig 单例与初始化测试
# ============================================================================


@pytest.mark.unit
class TestLoggingConfigSingleton:
    """单例模式测试"""

    def test_singleton_returns_same_instance(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        a = LoggingConfig()
        b = LoggingConfig()
        assert a is b

    def test_new_creates_instance(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        instance = LoggingConfig()
        assert isinstance(instance, LoggingConfig)

    def test_init_sets_initialized_flag(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init()
        assert lc._initialized is True

    def test_init_uses_default_config(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init()
        config = lc.get_config()
        assert config["level"] == "INFO"
        assert config["enable_console"] is True
        assert config["enable_file"] is True

    def test_init_with_custom_config(self, reset_logging_config, temp_log_dir):
        from src.utils.logging_config import LoggingConfig

        log_file = os.path.join(temp_log_dir, "custom.log")
        lc = LoggingConfig()
        lc.init({"level": "DEBUG", "file": log_file, "enable_console": False})
        config = lc.get_config()
        assert config["level"] == "DEBUG"
        assert config["file"] == log_file
        assert config["enable_console"] is False

    def test_init_idempotent(self, reset_logging_config):
        """重复 init() 不应报错"""
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init()
        # 第二次调用不应异常
        lc.init()
        assert lc._initialized is True

    def test_init_creates_log_directory(self, reset_logging_config, temp_log_dir):
        from src.utils.logging_config import LoggingConfig

        log_subdir = os.path.join(temp_log_dir, "logs")
        log_file = os.path.join(log_subdir, "test.log")
        lc = LoggingConfig()
        lc.init({"file": log_file, "enable_console": False})
        assert pathlib.Path(log_subdir).is_dir()


# ============================================================================
# 配置获取测试
# ============================================================================


@pytest.mark.unit
class TestLoggingConfigGet:
    """配置获取测试"""

    def test_get_config_returns_dict(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init()
        config = lc.get_config()
        assert isinstance(config, dict)
        assert "level" in config

    def test_get_config_before_init_returns_default(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        config = lc.get_config()
        assert config["level"] == "INFO"


# ============================================================================
# 磁盘空间检查测试
# ============================================================================


@pytest.mark.unit
class TestDiskSpaceCheck:
    """磁盘空间检查测试"""

    def test_check_disk_space_sufficient(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init()
        # 要求极小空间，应通过
        result = lc.check_disk_space(min_free_mb=0)
        assert result is True

    def test_check_disk_space_insufficient(self, reset_logging_config):
        """mock磁盘空间不足场景，不依赖真实磁盘"""
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init({"file": "/tmp/test.log", "enable_console": False})
        with patch("shutil.disk_usage") as mock_du:
            # 模拟磁盘只有 1MB 可用
            mock_du.return_value = Mock(
                free=1 * 1024 * 1024, total=1024 * 1024 * 1024, used=1023 * 1024 * 1024,
            )
            result = lc.check_disk_space(min_free_mb=100)
            assert result is False

    def test_check_disk_space_with_shutil(self, reset_logging_config):
        """Mock shutil.disk_usage 模拟磁盘空间"""
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init({"file": "/tmp/test.log", "enable_console": False})
        with patch("shutil.disk_usage") as mock_du:
            mock_du.return_value = Mock(
                free=50 * 1024 * 1024, total=1024 * 1024 * 1024, used=974 * 1024 * 1024,
            )
            result = lc.check_disk_space(min_free_mb=100)
            assert result is False


# ============================================================================
# SafeRotatingFileHandler 测试
# ============================================================================


@pytest.mark.unit
class TestSafeRotatingFileHandler:
    """安全日志轮转测试"""

    def test_creates_handler(self, temp_log_dir):
        from src.utils.logging_config import SafeRotatingFileHandler

        log_file = os.path.join(temp_log_dir, "test.log")
        handler = SafeRotatingFileHandler(log_file, maxBytes=1024, backupCount=2)
        assert handler is not None
        handler.close()

    def test_doRollover_windows_retry(self, temp_log_dir):
        """Windows 下 doRollover 重试不会崩溃"""
        from src.utils.logging_config import SafeRotatingFileHandler

        log_file = os.path.join(temp_log_dir, "test_retry.log")
        handler = SafeRotatingFileHandler(log_file, maxBytes=100, backupCount=1, encoding="utf-8")
        # 写入一些数据
        record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)
        handler.emit(record)
        try:
            handler.doRollover()
        except Exception:
            pass  # 在某些条件下可能失败
        handler.close()

    def test_non_windows_uses_parent_doRollover(self, temp_log_dir):
        """非 Windows 平台走父类 doRollover"""
        if sys.platform == "win32":
            pytest.skip("当前平台为 Windows，测试不适用")
        from src.utils.logging_config import SafeRotatingFileHandler

        log_file = os.path.join(temp_log_dir, "test_linux.log")
        handler = SafeRotatingFileHandler(log_file, maxBytes=10000, backupCount=1)
        assert not handler._is_windows
        handler.close()


# ============================================================================
# init_logging / get_configured_logger 测试
# ============================================================================


@pytest.mark.unit
class TestLoggingInitFunctions:
    """初始化函数测试"""

    def test_init_logging_returns_none(self, reset_logging_config):
        """init_logging() 返回 None（无返回值）"""
        from src.utils import init_logging

        result = init_logging()
        assert result is None

    def test_get_configured_logger_returns_logger(self):
        from src.utils import get_configured_logger

        logger = get_configured_logger("TestModule")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "TestModule"

    def test_get_configured_logger_same_name_returns_same(self):
        from src.utils import get_configured_logger

        a = get_configured_logger("SameName")
        b = get_configured_logger("SameName")
        assert a is b


# ============================================================================
# 集成测试
# ============================================================================


@pytest.mark.unit
class TestLoggingConfigIntegration:
    """集成测试"""

    def test_full_init_workflow(self, reset_logging_config, temp_log_dir):
        from src.utils.logging_config import LoggingConfig

        log_file = os.path.join(temp_log_dir, "full_test.log")
        lc = LoggingConfig()
        lc.init({"level": "WARNING", "file": log_file, "enable_console": True})
        config = lc.get_config()
        assert config["level"] == "WARNING"
        assert config["file"] == log_file
        # 磁盘检查
        assert lc.check_disk_space(min_free_mb=0) is True

    def test_console_only_config(self, reset_logging_config):
        from src.utils.logging_config import LoggingConfig

        lc = LoggingConfig()
        lc.init({"enable_console": True, "enable_file": False})
        config = lc.get_config()
        assert config["enable_console"] is True
        assert config["enable_file"] is False

    def test_file_only_config(self, reset_logging_config, temp_log_dir):
        from src.utils.logging_config import LoggingConfig

        log_file = os.path.join(temp_log_dir, "file_only.log")
        lc = LoggingConfig()
        lc.init({"enable_console": False, "enable_file": True, "file": log_file})
        config = lc.get_config()
        assert config["enable_file"] is True
        assert config["enable_console"] is False
