"""ConfigManager配置验证一致性测试 - 确保JSON Schema和手动验证逻辑一致"""

import pytest

import unittest

from src.config.config_manager import HAS_JSONSCHEMA, ConfigManager


class TestConfigValidationConsistency:
    """验证JSON Schema和手动验证的一致性"""

    def setUp(self):
        self.mgr = ConfigManager()

    def test_valid_config_passes_both_validators(self):
        """有效的配置应该同时通过JSON Schema和手动验证"""
        valid_config = {
            "collision": {
                "max_workers": 8,
                "progress_interval": 1000,
                "checkpoint_interval": 30,
                "dedup_max_size": 1000000,
            },
            "logging": {
                "level": "DEBUG",
                "format": "%(asctime)s - %(message)s",
                "file": "test.log",
                "max_bytes": 10485760,
                "backup_count": 5,
                "enable_console": True,
                "enable_file": True,
                "rotation_type": "size",
                "rotation_when": "midnight",
                "rotation_interval": 1,
                "compress_backups": False,
            },
            "gpu": {
                "use_gpu": True,
                "device_index": 0,
                "batch_size": 65536,
                "auto_detect": True,
                "memory_usage_ratio": 0.5,
                "enable_vendor_optimizations": True,
            },
            "performance_monitoring": {
                "enabled": True,
                "track_slow_operations": True,
                "slow_threshold_ms": 30000,
                "max_records": 10000,
                "log_level": "INFO",
            },
            "crypto": {
                "backend": "auto",
                "constant_time": False,
                "verify_checksums": True,
                "strict_wif_validation": True,
            },
        }

        errors = self.mgr.validate(valid_config)
        assert len(errors) == 0, f"有效配置不应有错误: {errors}"

    def test_invalid_max_workers_fails_validation(self):
        """无效的max_workers应该被检测到"""
        invalid_config = {"collision": {"max_workers": -1}}

        errors = self.mgr.validate(invalid_config)
        assert errors in "collision.max_workers"

    def test_invalid_log_level_fails_validation(self):
        """无效的日志级别应该被检测到"""
        invalid_config = {"logging": {"level": "INVALID_LEVEL"}}

        errors = self.mgr.validate(invalid_config)
        assert errors in "logging.level"

    def test_invalid_gpu_batch_size_fails_validation(self):
        """无效的GPU批处理大小应该被检测到"""
        invalid_config = {"gpu": {"batch_size": 0}}

        errors = self.mgr.validate(invalid_config)
        assert errors in "gpu.batch_size"

    def test_boolean_validation_strict(self):
        """严格的布尔值检查 - 整数不应被接受为布尔值"""
        # 测试布尔值字段接收整数的情况
        invalid_config = {
            "gpu": {"use_gpu": 1},  # 应该是布尔值，不是整数
            "logging": {"enable_console": 0},  # 应该是布尔值，不是整数
        }

        errors = self.mgr.validate(invalid_config)
        # 确保整数不会被误判为布尔值
        assert errors in "gpu.use_gpu"
        assert errors in "logging.enable_console"

    def test_config_dependencies_validation(self):
        """配置依赖关系验证 - 日志轮转模式依赖（仅手动验证）"""
        # 配置依赖关系验证仅在手动验证模式下生效
        # 当jsonschema可用时，validate()优先使用Schema验证
        from src.config.config_manager import HAS_JSONSCHEMA

        if not HAS_JSONSCHEMA:
            # 仅在没有jsonschema时测试依赖关系验证
            # size轮转模式需要max_bytes
            size_without_max_bytes = {"logging": {"rotation_type": "size"}}

            errors = self.mgr.validate(size_without_max_bytes)
            assert errors in "logging.max_bytes"

            # time轮转模式需要rotation_when
            time_without_when = {"logging": {"rotation_type": "time"}}

            errors = self.mgr.validate(time_without_when)
            assert errors in "logging.rotation_when"
        else:
            # jsonschema模式下跳过此测试（依赖检查仅在手动验证中）
            pytest.skip("jsonschema可用，依赖关系验证由Schema处理")

    def test_additional_properties_rejected(self):
        """额外属性应该被拒绝（Schema验证）"""
        config_with_extra = {
            "collision": {"max_workers": 8, "invalid_extra_field": "value"},  # 不应该被允许
            "logging": {"level": "INFO"},
            "unknown_top_level_key": "value",  # 不应该被允许
        }

        if HAS_JSONSCHEMA:
            errors = self.mgr.validate(config_with_extra)
            # JSON Schema应该拒绝额外属性
            assert len(errors) > 0

    def test_default_config_validation(self):
        """默认配置应该完全通过验证"""
        mgr = ConfigManager()
        errors = mgr.validate()
        assert len(errors) == 0, f"默认配置不应有错误: {errors}"

    def test_merge_config_validation(self):
        """合并后的配置应该通过验证"""
        mgr = ConfigManager()
        mgr.set("collision.max_workers", 16)
        mgr.set("logging.level", "DEBUG")
        mgr.set("gpu.batch_size", 131072)

        errors = mgr.validate()
        assert len(errors) == 0, f"合并配置不应有错误: {errors}"

    def test_empty_config_validation(self):
        """空配置应该通过验证（使用默认值）"""
        empty_config = {}
        errors = self.mgr.validate(empty_config)
        # 空配置应该是有效的（所有字段可选）
        assert len(errors) == 0, f"空配置不应有错误: {errors}"

    def test_none_values_validation(self):
        """None值应该被正确处理"""
        config_with_none = {
            "collision": {"max_workers": None},  # None是有效的
            "logging": {"level": "INFO"},
        }

        errors = self.mgr.validate(config_with_none)
        assert len(errors) == 0, f"None值配置不应有错误: {errors}"


class TestConfigValidationEdgeCases:
    """验证边界条件测试"""

    def test_max_workers_boundary(self):
        """max_workers边界值测试"""
        mgr = ConfigManager()

        # 最小值边界
        mgr.set("collision.max_workers", 1)
        errors = mgr.validate()
        assert len(errors) == 0

        # 最大值边界
        mgr.set("collision.max_workers", 1024)
        errors = mgr.validate()
        assert len(errors) == 0

        # 超过最大值
        mgr.set("collision.max_workers", 1025)
        errors = mgr.validate()
        assert errors in "collision.max_workers"

    def test_gpu_batch_size_boundary(self):
        """GPU批处理大小边界值测试"""
        mgr = ConfigManager()

        # 最小值边界
        mgr.set("gpu.batch_size", 1)
        errors = mgr.validate()
        assert len(errors) == 0

        # 最大值边界
        mgr.set("gpu.batch_size", 16777216)
        errors = mgr.validate()
        assert len(errors) == 0

        # 超过最大值
        mgr.set("gpu.batch_size", 16777217)
        errors = mgr.validate()
        assert errors in "gpu.batch_size"

    def test_memory_ratio_boundary(self):
        """内存比率边界值测试"""
        mgr = ConfigManager()

        # 边界值
        mgr.set("gpu.memory_usage_ratio", 1.0)
        errors = mgr.validate()
        assert len(errors) == 0

        # 无效值（小于等于0）
        mgr.set("gpu.memory_usage_ratio", 0)
        errors = mgr.validate()
        assert errors in "gpu.memory_usage_ratio"

        # 无效值（大于1）
        mgr.set("gpu.memory_usage_ratio", 1.5)
        errors = mgr.validate()
        assert errors in "gpu.memory_usage_ratio"


if __name__ == "__main__":
    unittest.main(verbosity=2)
