# -*- coding: utf-8 -*-
"""GPUConfigManager单元测试

测试GPU配置管理器的所有功能：
1. 配置读取（优先级链）
2. 配置合并
3. 配置验证
4. 配置摘要生成
"""

import pytest
import json
import logging
from unittest.mock import patch
from src.collision.gpu_config_manager import GPUConfigManager

pytestmark = pytest.mark.gpu


class TestGPUConfigManagerInit:
    """测试GPUConfigManager初始化"""

    def test_init_creates_empty_cache(self):
        """测试初始化创建空缓存"""
        manager = GPUConfigManager()
        assert manager._config_cache == {}

    def test_init_logs_debug_message(self, caplog):
        """测试初始化输出调试日志"""
        with caplog.at_level(logging.DEBUG):
            GPUConfigManager()
            assert "GPUConfigManager已初始化" in caplog.text


class TestReadAsyncConfig:
    """测试异步配置读取（优先级链）"""

    def setup_method(self):
        """每个测试方法前创建管理器"""
        self.manager = GPUConfigManager()

    def test_priority1_constructor_config_true(self):
        """测试优先级1：构造参数启用异步"""
        constructor_config = {"gpu": {"async_execution": True}}

        enable_async, source = self.manager.read_async_config(constructor_config=constructor_config)

        assert enable_async is True
        assert source == "构造参数"

    def test_priority1_constructor_config_false(self):
        """测试优先级1：构造参数禁用异步"""
        constructor_config = {"gpu": {"async_execution": False}}

        enable_async, source = self.manager.read_async_config(constructor_config=constructor_config)

        assert enable_async is False
        assert source == "构造参数"

    def test_priority1_no_async_key(self):
        """测试优先级1：构造参数无async_execution键"""
        constructor_config = {"gpu": {"batch_size": 1024}}

        enable_async, source = self.manager.read_async_config(
            constructor_config=constructor_config, config_files=[]  # 跳过文件读取
        )

        assert enable_async is False
        assert source == "默认"

    def test_priority1_no_gpu_key(self):
        """测试优先级1：构造参数无gpu键"""
        constructor_config = {"batch_size": 1024}

        enable_async, source = self.manager.read_async_config(
            constructor_config=constructor_config, config_files=[]
        )

        assert enable_async is False
        assert source == "默认"

    def test_priority2_config_file_exists(self, tmp_path):
        """测试优先级2：配置文件存在且启用异步"""
        # 创建临时配置文件
        config_file = tmp_path / "config.json"
        config_data = {"gpu": {"async_execution": True, "batch_size": 2048}}
        config_file.write_text(json.dumps(config_data))

        enable_async, source = self.manager.read_async_config(
            constructor_config=None, config_files=[config_file]
        )

        assert enable_async is True
        assert "配置文件" in source

    def test_priority2_config_file_async_false(self, tmp_path):
        """测试优先级2：配置文件存在但禁用异步"""
        config_file = tmp_path / "config.json"
        config_data = {"gpu": {"async_execution": False}}
        config_file.write_text(json.dumps(config_data))

        enable_async, source = self.manager.read_async_config(
            constructor_config=None, config_files=[config_file]
        )

        assert enable_async is False
        assert source == "默认"

    def test_priority2_multiple_files_first_wins(self, tmp_path):
        """测试优先级2：多个配置文件，第一个匹配的生效"""
        file1 = tmp_path / "config1.json"
        file1.write_text(json.dumps({"gpu": {"async_execution": True}}))

        file2 = tmp_path / "config2.json"
        file2.write_text(json.dumps({"gpu": {"async_execution": True}}))

        enable_async, source = self.manager.read_async_config(config_files=[file1, file2])

        assert enable_async is True
        assert "config1.json" in source

    def test_priority2_invalid_json(self, tmp_path, caplog):
        """测试优先级2：JSON格式错误"""
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json}")

        with caplog.at_level(logging.WARNING):
            enable_async, source = self.manager.read_async_config(config_files=[config_file])

        assert enable_async is False
        assert "JSON格式错误" in caplog.text

    def test_priority2_permission_error(self, tmp_path, caplog):
        """测试优先级2：权限不足"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"gpu": {"async_execution": True}}))

        # Mock open函数抛出PermissionError
        with patch("builtins.open", side_effect=PermissionError("权限不足")):
            with caplog.at_level(logging.WARNING):
                enable_async, source = self.manager.read_async_config(config_files=[config_file])

        assert enable_async is False
        assert "权限不足" in caplog.text

    def test_priority3_default_value(self):
        """测试优先级3：使用默认值"""
        enable_async, source = self.manager.read_async_config(
            constructor_config=None, config_files=[]  # 无配置文件
        )

        assert enable_async is False
        assert source == "默认"

    def test_config_files_none_uses_default_paths(self):
        """测试config_files为None时使用默认路径"""
        enable_async, source = self.manager.read_async_config(config_files=None)

        # 应该不会抛出异常，使用默认路径
        assert isinstance(enable_async, bool)
        assert isinstance(source, str)


class TestMergeGPUConfigs:
    """测试配置合并功能"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    def test_merge_without_profile(self):
        """测试无Profile配置时的合并"""
        auto_config = {"batch_size": 1024, "work_group_size": 256, "memory_usage_ratio": 0.5}

        merged = self.manager.merge_gpu_configs(auto_config)

        assert merged == auto_config

    def test_merge_with_profile_override(self):
        """测试Profile配置覆盖AutoConfig"""
        auto_config = {
            "batch_size": 1024,
            "work_group_size": 256,
            "memory_usage_ratio": 0.5,
            "enable_async": False,
        }

        profile_config = {"batch_size": 2048, "enable_async": True}

        merged = self.manager.merge_gpu_configs(auto_config, profile_config)

        assert merged["batch_size"] == 2048  # 被覆盖
        assert merged["work_group_size"] == 256  # 保持原值
        assert merged["enable_async"] is True  # 被覆盖

    def test_merge_profile_invalid_value(self, caplog):
        """测试Profile配置值无效时保持默认值"""
        auto_config = {"batch_size": 1024, "work_group_size": 256}

        profile_config = {"batch_size": 512, "work_group_size": 256}  # 无效：过小

        with caplog.at_level(logging.WARNING):
            merged = self.manager.merge_gpu_configs(auto_config, profile_config)

        # batch_size应该保持原值（1024），因为512无效
        assert merged["batch_size"] == 1024
        assert "配置值无效" in caplog.text

    def test_merge_profile_extra_keys_ignored(self):
        """测试Profile配置中的额外键被忽略"""
        auto_config = {"batch_size": 1024}

        profile_config = {"unknown_key": "value", "batch_size": 2048}

        merged = self.manager.merge_gpu_configs(auto_config, profile_config)

        assert "unknown_key" not in merged
        assert merged["batch_size"] == 2048

    def test_merge_logs_completion(self, caplog):
        """测试合并完成后输出日志"""
        auto_config = {"batch_size": 1024, "work_group_size": 256, "memory_usage_ratio": 0.5}

        with caplog.at_level(logging.INFO):
            self.manager.merge_gpu_configs(auto_config)

        assert "GPU配置合并完成" in caplog.text
        assert "batch_size=1024" in caplog.text


class TestValidateConfigValue:
    """测试配置值验证"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    # batch_size验证
    def test_batch_size_valid_min(self):
        """测试batch_size最小有效值"""
        assert self.manager._validate_config_value("batch_size", 1024) is True

    def test_batch_size_valid_max(self):
        """测试batch_size最大有效值 (P1-2: < UINT32_MAX)"""
        UINT32_MAX = 0xFFFFFFFF
        assert self.manager._validate_config_value("batch_size", UINT32_MAX - 1) is True

    def test_batch_size_too_small(self):
        """测试batch_size过小"""
        assert self.manager._validate_config_value("batch_size", 512) is False

    def test_batch_size_too_large(self):
        """测试batch_size过大 (P1-2: >= UINT32_MAX 应拒绝)"""
        UINT32_MAX = 0xFFFFFFFF
        # UINT32_MAX should be rejected (gid overflow prevention)
        assert self.manager._validate_config_value("batch_size", UINT32_MAX) is False
        assert self.manager._validate_config_value("batch_size", UINT32_MAX + 1) is False

    def test_batch_size_wrong_type(self):
        """测试batch_size类型错误"""
        assert self.manager._validate_config_value("batch_size", "1024") is False

    # work_group_size验证
    def test_work_group_size_valid(self):
        """测试work_group_size有效值"""
        assert self.manager._validate_config_value("work_group_size", 256) is True

    def test_work_group_size_too_small(self):
        """测试work_group_size过小"""
        assert self.manager._validate_config_value("work_group_size", 32) is False

    def test_work_group_size_too_large(self):
        """测试work_group_size过大"""
        assert self.manager._validate_config_value("work_group_size", 4096) is False

    # memory_usage_ratio验证
    def test_memory_ratio_valid(self):
        """测试memory_usage_ratio有效值"""
        assert self.manager._validate_config_value("memory_usage_ratio", 0.5) is True

    def test_memory_ratio_zero(self):
        """测试memory_usage_ratio为0"""
        assert self.manager._validate_config_value("memory_usage_ratio", 0.0) is False

    def test_memory_ratio_over_one(self):
        """测试memory_usage_ratio超过1.0"""
        assert self.manager._validate_config_value("memory_usage_ratio", 1.5) is False

    # boolean验证
    def test_enable_async_valid_true(self):
        """测试enable_async为True"""
        assert self.manager._validate_config_value("enable_async", True) is True

    def test_enable_async_valid_false(self):
        """测试enable_async为False"""
        assert self.manager._validate_config_value("enable_async", False) is True

    def test_enable_async_invalid_string(self):
        """测试enable_async为字符串"""
        assert self.manager._validate_config_value("enable_async", "true") is False

    # unknown key
    def test_unknown_key_always_valid(self):
        """测试未知键始终返回True"""
        assert self.manager._validate_config_value("unknown_key", "any_value") is True


class TestValidateMergedConfig:
    """测试合并配置验证"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    def test_batch_size_too_small_warning(self, caplog):
        """测试batch_size过小输出警告"""
        config = {"batch_size": 512}

        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config(config)

        assert "batch_size过小" in caplog.text

    def test_batch_size_too_large_warning(self, caplog):
        """测试batch_size过大输出警告 (P1-2: >= 33M 触发显存警告)"""
        config = {"batch_size": 33554432}

        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config(config)

        assert "batch_size过大" in caplog.text

    def test_memory_ratio_too_high_warning(self, caplog):
        """测试显存使用率过高输出警告"""
        config = {"memory_usage_ratio": 0.9}

        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config(config)

        assert "显存使用率过高" in caplog.text

    def test_memory_ratio_too_low_warning(self, caplog):
        """测试显存使用率过低输出警告"""
        config = {"memory_usage_ratio": 0.2}

        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config(config)

        assert "显存使用率过低" in caplog.text

    def test_valid_config_no_warning(self, caplog):
        """测试有效配置无警告"""
        config = {"batch_size": 1024, "memory_usage_ratio": 0.5}

        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config(config)

        assert caplog.text == "" or "batch_size" not in caplog.text


class TestGetConfigSummary:
    """测试配置摘要生成"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    def test_summary_format(self):
        """测试摘要格式"""
        config = {
            "batch_size": 2048,
            "work_group_size": 512,
            "memory_usage_ratio": 0.6,
            "enable_async": True,
            "use_uint32_workaround": True,
            "use_fast_math": False,
        }

        summary = self.manager.get_config_summary(config)

        assert "GPU配置摘要:" in summary
        assert "batch_size: 2048" in summary
        assert "work_group_size: 512" in summary
        assert "memory_usage_ratio: 0.6" in summary
        assert "enable_async: True" in summary
        assert "use_uint32_workaround: True" in summary
        assert "use_fast_math: False" in summary

    def test_summary_missing_keys(self):
        """测试缺少某些键时的摘要"""
        config = {"batch_size": 1024}

        summary = self.manager.get_config_summary(config)

        assert "batch_size: 1024" in summary
        assert "work_group_size: N/A" in summary
        assert "memory_usage_ratio: N/A" in summary

    def test_summary_empty_config(self):
        """测试空配置的摘要"""
        summary = self.manager.get_config_summary({})

        assert "batch_size: N/A" in summary
        assert "work_group_size: N/A" in summary


class TestGPUConfigManagerIntegration:
    """GPUConfigManager集成测试"""

    def test_full_workflow(self, tmp_path):
        """测试完整工作流程"""
        manager = GPUConfigManager()

        # 1. 创建配置文件
        config_file = tmp_path / "config.json"
        config_data = {"gpu": {"async_execution": True, "batch_size": 4096}}
        config_file.write_text(json.dumps(config_data))

        # 2. 读取异步配置
        enable_async, source = manager.read_async_config(config_files=[config_file])
        assert enable_async is True

        # 3. 合并配置
        auto_config = {
            "batch_size": 1024,
            "work_group_size": 256,
            "memory_usage_ratio": 0.5,
            "enable_async": False,
        }

        profile_config = {"batch_size": 4096, "work_group_size": 512}

        merged = manager.merge_gpu_configs(auto_config, profile_config)

        # 4. 验证合并结果
        assert merged["batch_size"] == 4096
        assert merged["work_group_size"] == 512
        assert merged["memory_usage_ratio"] == 0.5

        # 5. 生成摘要
        summary = manager.get_config_summary(merged)
        assert "batch_size: 4096" in summary

    def test_error_handling_robustness(self):
        """测试错误处理的健壮性"""
        manager = GPUConfigManager()

        # 测试各种异常情况
        assert manager.read_async_config(config_files=[]) == (False, "默认")

        merged = manager.merge_gpu_configs({})
        assert isinstance(merged, dict)

        summary = manager.get_config_summary({})
        assert isinstance(summary, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
