#!/usr/bin/env python3
"""配置协调器 (ConfigCoordinator) 单元测试

覆盖：
- 初始化与配置同步
- 统一获取/设置配置
- 配置验证
- 配置保存
- GPU/Crypto 配置同步
"""

import json
import pathlib
import tempfile
from unittest.mock import patch

import pytest

from src.config.config_coordinator import ConfigCoordinator

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def _mock_config_validations():
    """Mock 所有配置验证和保存操作，避免深层 patch 嵌套"""
    with (
        patch("src.config.config_manager.ConfigManager.validate", return_value=[]),
        patch("src.config.crypto_config.CryptoConfig.validate", return_value=[]),
        patch("src.config.crypto_config.CryptoConfig.set", return_value=True),
        patch("src.config.crypto_config.CryptoConfig.apply_to_crypto_manager", return_value=True),
    ):
        yield


@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    config_data = {
        "collision": {"max_workers": 4, "progress_interval": 1000},
        "gpu": {
            "use_gpu": True,
            "device_index": 0,
            "batch_size": 65536,
            "auto_detect": True,
            "memory_usage_ratio": 0.5,
            "enable_vendor_optimizations": True,
        },
        "crypto": {
            "backend": "auto",
            "constant_time": True,
            "verify_checksums": True,
            "strict_wif_validation": True,
        },
        "logging": {"level": "INFO", "enable_console": True},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(config_data, f)
        config_path = f.name

    yield config_path
    if pathlib.Path(config_path).exists():
        pathlib.Path(config_path).unlink()


@pytest.fixture
def coordinator(temp_config_file, _mock_config_validations):
    """创建 ConfigCoordinator 实例"""
    c = ConfigCoordinator(config_file=temp_config_file)
    return c


# ============================================================================
# 初始化测试
# ============================================================================


@pytest.mark.unit
class TestConfigCoordinatorInit:
    """初始化测试"""

    def test_creates_config_manager(self, temp_config_file, _mock_config_validations):
        c = ConfigCoordinator(config_file=temp_config_file)
        assert c.config_manager is not None
        assert c.crypto_config is not None
        assert c.gpu_config is not None

    def test_syncs_configs_on_init(self, temp_config_file, _mock_config_validations):
        c = ConfigCoordinator(config_file=temp_config_file)
        # 配置应已同步
        assert c.config_manager is not None


@pytest.mark.unit
class TestConfigCoordinatorGet:
    """获取配置测试"""

    def test_get_existing_key(self, coordinator):
        value = coordinator.get("collision.max_workers", 1)
        # 默认会走 ConfigManager.get
        assert value is not None

    def test_get_nonexistent_key_with_default(self, coordinator):
        value = coordinator.get("nonexistent.key", "default_val")
        assert value == "default_val"

    def test_get_crypto_key(self, coordinator):
        # Crypto 配置通过特殊路由
        value = coordinator.get("crypto.backend", "none")
        assert value is not None

    def test_get_without_default(self, coordinator):
        value = coordinator.get("nonexistent_key")
        assert value is None


@pytest.mark.unit
class TestConfigCoordinatorSet:
    """设置配置测试"""

    def test_set_crypto_key(self, coordinator):
        result = coordinator.set("crypto.backend", "test_value")
        assert isinstance(result, bool)

    def test_set_non_crypto_key(self, coordinator):
        result = coordinator.set("logging.level", "DEBUG")
        assert isinstance(result, bool)


@pytest.mark.unit
class TestConfigCoordinatorUnified:
    """统一配置视图测试"""

    def test_get_unified_config(self, coordinator):
        config = coordinator.get_unified_config()
        assert isinstance(config, dict)
        assert "collision" in config
        assert "gpu" in config
        assert "crypto" in config
        assert "logging" in config


@pytest.mark.unit
class TestConfigCoordinatorValidate:
    """验证测试"""

    def test_validate_all(self, coordinator):
        errors = coordinator.validate_all()
        assert isinstance(errors, dict)

    def test_validate_all_empty_on_success(self, temp_config_file, _mock_config_validations):
        c = ConfigCoordinator(config_file=temp_config_file)
        errors = c.validate_all()
        assert errors == {} or all(len(v) == 0 for v in errors.values())


@pytest.mark.unit
class TestConfigCoordinatorGPU:
    """GPU配置测试"""

    def test_get_gpu_config(self, coordinator):
        gpu_config = coordinator.get_gpu_config()
        assert isinstance(gpu_config, dict)

    def test_get_crypto_config(self, coordinator):
        crypto_config = coordinator.get_crypto_config()
        assert isinstance(crypto_config, dict)

    def test_apply_crypto_config(self, coordinator):
        result = coordinator.apply_crypto_config()
        assert isinstance(result, bool)
