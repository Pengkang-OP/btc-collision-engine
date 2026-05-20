"""边界值单元测试

针对关键模块的边界条件进行测试，确保：
1. 最小值/最大值处理正确
2. 空值/None处理正确
3. 类型转换处理正确
4. 异常情况处理正确
"""

import pytest

from src.collision.gpu_config_manager import GPUConfigManager


class TestBatchSizeBoundaries:
    """batch_size边界值测试"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    # 最小值边界
    def test_batch_size_minimum_valid(self):
        """测试batch_size最小有效值1024"""
        assert self.manager._validate_config_value("batch_size", 1024) is True

    def test_batch_size_below_minimum(self):
        """测试batch_size低于最小值1023"""
        assert self.manager._validate_config_value("batch_size", 1023) is False

    def test_batch_size_one(self):
        """测试batch_size=1（远低于最小值）"""
        assert self.manager._validate_config_value("batch_size", 1) is False

    # 最大值边界
    def test_batch_size_maximum_valid(self):
        """测试batch_size最大有效值 (P1-2: < UINT32_MAX)"""
        UINT32_MAX = 0xFFFFFFFF
        assert self.manager._validate_config_value("batch_size", UINT32_MAX - 1) is True

    def test_batch_size_above_maximum(self):
        """测试batch_size超过最大值 (P1-2: >= UINT32_MAX 应拒绝)"""
        UINT32_MAX = 0xFFFFFFFF
        assert self.manager._validate_config_value("batch_size", UINT32_MAX) is False

    def test_batch_size_very_large(self):
        """测试batch_size非常大 (P1-2: >= UINT32_MAX 应拒绝)"""
        UINT32_MAX = 0xFFFFFFFF
        assert self.manager._validate_config_value("batch_size", UINT32_MAX + 1000) is False

    # 类型边界
    def test_batch_size_float(self):
        """测试batch_size为浮点数"""
        assert self.manager._validate_config_value("batch_size", 1024.5) is False

    def test_batch_size_string(self):
        """测试batch_size为字符串"""
        assert self.manager._validate_config_value("batch_size", "1024") is False

    def test_batch_size_none(self):
        """测试batch_size为None"""
        assert self.manager._validate_config_value("batch_size", None) is False

    def test_batch_size_negative(self):
        """测试batch_size为负数"""
        assert self.manager._validate_config_value("batch_size", -1024) is False

    def test_batch_size_zero(self):
        """测试batch_size为0"""
        assert self.manager._validate_config_value("batch_size", 0) is False


class TestWorkGroupSizeBoundaries:
    """work_group_size边界值测试"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    # 最小值边界
    def test_work_group_size_minimum_valid(self):
        """测试work_group_size最小有效值64"""
        assert self.manager._validate_config_value("work_group_size", 64) is True

    def test_work_group_size_below_minimum(self):
        """测试work_group_size低于最小值63"""
        assert self.manager._validate_config_value("work_group_size", 63) is False

    # 最大值边界
    def test_work_group_size_maximum_valid(self):
        """测试work_group_size最大有效值2048"""
        assert self.manager._validate_config_value("work_group_size", 2048) is True

    def test_work_group_size_above_maximum(self):
        """测试work_group_size超过最大值2049"""
        assert self.manager._validate_config_value("work_group_size", 2049) is False

    # 常用值测试
    @pytest.mark.parametrize("size", [64, 128, 256, 512, 1024])
    def test_work_group_size_common_values(self, size):
        """测试常用的work_group_size值"""
        assert self.manager._validate_config_value("work_group_size", size) is True

    # 类型边界
    def test_work_group_size_float(self):
        """测试work_group_size为浮点数"""
        assert self.manager._validate_config_value("work_group_size", 256.0) is False

    def test_work_group_size_string(self):
        """测试work_group_size为字符串"""
        assert self.manager._validate_config_value("work_group_size", "256") is False


class TestMemoryUsageRatioBoundaries:
    """memory_usage_ratio边界值测试"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    # 最小值边界
    def test_memory_ratio_near_zero(self):
        """测试memory_usage_ratio接近0"""
        assert self.manager._validate_config_value("memory_usage_ratio", 0.01) is True

    def test_memory_ratio_zero(self):
        """测试memory_usage_ratio=0（无效）"""
        assert self.manager._validate_config_value("memory_usage_ratio", 0.0) is False

    def test_memory_ratio_negative(self):
        """测试memory_usage_ratio为负数"""
        assert self.manager._validate_config_value("memory_usage_ratio", -0.1) is False

    # 最大值边界
    def test_memory_ratio_maximum_valid(self):
        """测试memory_usage_ratio最大有效值1.0"""
        assert self.manager._validate_config_value("memory_usage_ratio", 1.0) is True

    def test_memory_ratio_above_maximum(self):
        """测试memory_usage_ratio超过1.0"""
        assert self.manager._validate_config_value("memory_usage_ratio", 1.01) is False

    # 常用值测试
    @pytest.mark.parametrize("ratio", [0.3, 0.45, 0.5, 0.7, 0.85])
    def test_memory_ratio_common_values(self, ratio):
        """测试常用的显存使用率"""
        assert self.manager._validate_config_value("memory_usage_ratio", ratio) is True

    # 类型边界
    def test_memory_ratio_integer(self):
        """测试memory_usage_ratio为整数（应该允许）"""
        assert self.manager._validate_config_value("memory_usage_ratio", 1) is True

    def test_memory_ratio_string(self):
        """测试memory_usage_ratio为字符串"""
        assert self.manager._validate_config_value("memory_usage_ratio", "0.5") is False

    def test_memory_ratio_none(self):
        """测试memory_usage_ratio为None"""
        assert self.manager._validate_config_value("memory_usage_ratio", None) is False


class TestBooleanConfigBoundaries:
    """布尔型配置边界测试"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    @pytest.mark.parametrize("key", ["enable_async", "use_uint32_workaround", "use_fast_math"])
    def test_true_valid(self, key):
        """测试True有效"""
        assert self.manager._validate_config_value(key, True) is True

    @pytest.mark.parametrize("key", ["enable_async", "use_uint32_workaround", "use_fast_math"])
    def test_false_valid(self, key):
        """测试False有效"""
        assert self.manager._validate_config_value(key, False) is True

    @pytest.mark.parametrize("key", ["enable_async", "use_uint32_workaround", "use_fast_math"])
    def test_string_true_invalid(self, key):
        """测试字符串'true'无效"""
        assert self.manager._validate_config_value(key, "true") is False

    @pytest.mark.parametrize("key", ["enable_async", "use_uint32_workaround", "use_fast_math"])
    def test_string_false_invalid(self, key):
        """测试字符串'false'无效"""
        assert self.manager._validate_config_value(key, "false") is False

    @pytest.mark.parametrize("key", ["enable_async", "use_uint32_workaround", "use_fast_math"])
    def test_integer_invalid(self, key):
        """测试整数无效"""
        assert self.manager._validate_config_value(key, 1) is False
        assert self.manager._validate_config_value(key, 0) is False

    @pytest.mark.parametrize("key", ["enable_async", "use_uint32_workaround", "use_fast_math"])
    def test_none_invalid(self, key):
        """测试None无效"""
        assert self.manager._validate_config_value(key, None) is False


class TestMergedConfigValidation:
    """合并配置验证边界测试"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    def test_empty_config(self):
        """测试空配置"""
        # 应该不抛出异常
        self.manager._validate_merged_config({})

    def test_config_with_none_values(self):
        """测试包含None值的配置"""
        config = {"batch_size": None, "memory_usage_ratio": None}
        # 应该不抛出异常（验证会跳过None）
        self.manager._validate_merged_config(config)

    def test_batch_size_boundary_warnings(self, caplog):
        """测试batch_size边界警告"""
        import logging

        # 过小
        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config({"batch_size": 512})
        assert "batch_size过小" in caplog.text

        caplog.clear()

        # 过大
        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config({"batch_size": 33554432})
        assert "batch_size过大" in caplog.text

    def test_memory_ratio_boundary_warnings(self, caplog):
        """测试显存使用率边界警告"""
        import logging

        # 过高
        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config({"memory_usage_ratio": 0.9})
        assert "显存使用率过高" in caplog.text

        caplog.clear()

        # 过低
        with caplog.at_level(logging.WARNING):
            self.manager._validate_merged_config({"memory_usage_ratio": 0.2})
        assert "显存使用率过低" in caplog.text


class TestConfigSummaryBoundaries:
    """配置摘要边界测试"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    def test_empty_config_summary(self):
        """测试空配置的摘要"""
        summary = self.manager.get_config_summary({})

        # 所有值应该显示为N/A或默认值
        assert "batch_size: N/A" in summary
        assert "work_group_size: N/A" in summary
        assert "enable_async: False" in summary

    def test_partial_config_summary(self):
        """测试部分配置的摘要"""
        config = {"batch_size": 1024}
        summary = self.manager.get_config_summary(config)

        assert "batch_size: 1024" in summary
        assert "work_group_size: N/A" in summary

    def test_full_config_summary(self):
        """测试完整配置的摘要"""
        config = {
            "batch_size": 2048,
            "work_group_size": 512,
            "memory_usage_ratio": 0.6,
            "enable_async": True,
            "use_uint32_workaround": True,
            "use_fast_math": False,
        }
        summary = self.manager.get_config_summary(config)

        assert "batch_size: 2048" in summary
        assert "work_group_size: 512" in summary
        assert "memory_usage_ratio: 0.6" in summary
        assert "enable_async: True" in summary


class TestReadAsyncConfigBoundaries:
    """异步配置读取边界测试"""

    def setup_method(self):
        self.manager = GPUConfigManager()

    def test_none_constructor_config(self):
        """测试构造函数配置为None"""
        enable_async, source = self.manager.read_async_config(
            constructor_config=None, config_files=[]
        )
        assert enable_async is False
        assert source == "默认"

    def test_empty_constructor_config(self):
        """测试构造函数配置为空字典"""
        enable_async, source = self.manager.read_async_config(
            constructor_config={}, config_files=[]
        )
        assert enable_async is False
        assert source == "默认"

    def test_constructor_config_without_gpu(self):
        """测试构造函数配置无gpu键"""
        enable_async, source = self.manager.read_async_config(
            constructor_config={"batch_size": 1024}, config_files=[]
        )
        assert enable_async is False
        assert source == "默认"

    def test_constructor_config_without_async(self):
        """测试构造函数配置无async_execution键"""
        enable_async, source = self.manager.read_async_config(
            constructor_config={"gpu": {"batch_size": 1024}}, config_files=[]
        )
        assert enable_async is False
        assert source == "默认"

    def test_empty_config_files_list(self):
        """测试配置文件列表为空"""
        enable_async, source = self.manager.read_async_config(
            constructor_config=None, config_files=[]
        )
        assert enable_async is False
        assert source == "默认"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
