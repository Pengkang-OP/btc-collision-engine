"""GPU内存优化工具函数单元测试

测试src/utils/gpu_memory_utils.py中的所有功能和边界情况。
"""

import pytest
from src.utils.gpu_memory_utils import (
    calculate_optimal_batch_size,
    MIN_GPU_MEMORY,
    DEFAULT_BATCH_SIZE,
    BatchSizeConfig,
)

pytestmark = pytest.mark.gpu


class MockDeviceObj:
    """模拟GPU设备对象"""

    def __init__(self, global_mem_size):
        self.global_mem_size = global_mem_size


class MockGPUDevice:
    """模拟GPU设备"""

    def __init__(self, global_mem_size, has_device_info=True):
        self.device = MockDeviceObj(global_mem_size)
        if has_device_info:
            self.device_info = {"global_mem_size": global_mem_size, "name": "Mock GPU"}
        else:
            self.device_info = {}


# ============================================================================
# 正常路径测试
# ============================================================================


class TestNormalPath:
    """正常路径测试"""

    def test_6gb_gpu_no_targets(self):
        """测试6GB显存，无目标地址"""
        device = MockGPUDevice(6 * 1024**3)
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 8388608  # 应该达到最大值8M

    def test_16gb_gpu_no_targets(self):
        """测试16GB显存，无目标地址"""
        device = MockGPUDevice(16 * 1024**3)
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 8388608  # 应该达到最大值8M

    def test_128mb_gpu_no_targets(self):
        """测试128MB显存，无目标地址"""
        device = MockGPUDevice(128 * 1024**2)
        batch_size = calculate_optimal_batch_size(device)

        # 128MB * 0.5 / 36 = ~1.86M，应该小于8M
        assert batch_size < 8388608
        assert batch_size >= 1024
        assert batch_size % 1024 == 0  # 应该对齐到1024

    def test_with_target_buffer(self):
        """测试带目标地址缓冲区"""
        device = MockGPUDevice(6 * 1024**3)
        target_buffer_size = 10000 * 20  # 10000个目标地址，200KB

        batch_size = calculate_optimal_batch_size(device, target_buffer_size)

        # 应该仍然接近8M（影响很小）
        assert batch_size <= 8388608
        assert batch_size >= 1024

    def test_custom_memory_usage_ratio(self):
        """测试自定义显存使用比例"""
        device = MockGPUDevice(6 * 1024**3)

        # 使用70%显存
        config = BatchSizeConfig(memory_usage_ratio=0.7)
        batch_size = calculate_optimal_batch_size(device, config=config)

        assert batch_size <= 8388608
        assert batch_size >= 1024

    def test_custom_batch_size_range(self):
        """测试自定义batch_size范围"""
        device = MockGPUDevice(6 * 1024**3)

        config = BatchSizeConfig(min_batch_size=2048, max_batch_size=4194304)  # 4M
        batch_size = calculate_optimal_batch_size(device, config=config)

        assert batch_size <= 4194304
        assert batch_size >= 2048

    def test_memory_alignment(self):
        """测试内存对齐"""
        device = MockGPUDevice(128 * 1024**2)

        config = BatchSizeConfig(memory_alignment=2048)
        batch_size = calculate_optimal_batch_size(device, config=config)

        assert batch_size % 2048 == 0


# ============================================================================
# 边界条件测试
# ============================================================================


class TestBoundaryConditions:
    """边界条件测试"""

    def test_zero_memory(self):
        """测试显存为0"""
        device = MockGPUDevice(0)
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 1024  # 应该返回最小值

    def test_negative_memory(self):
        """测试显存为负数"""
        device = MockGPUDevice(-1)
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 1024  # 应该返回最小值

    def test_very_small_memory_1_byte(self):
        """测试极小显存（1字节）"""
        device = MockGPUDevice(1)
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 1024  # 应该返回最小值

    def test_very_small_memory_1kb(self):
        """测试极小显存（1KB）"""
        device = MockGPUDevice(1024)
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 1024  # 应该返回最小值

    def test_min_memory_threshold(self):
        """测试最小显存阈值（1MB）"""
        device = MockGPUDevice(MIN_GPU_MEMORY - 1)  # 略小于1MB
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 1024  # 应该返回最小值

    def test_just_above_min_memory(self):
        """测试略大于最小显存阈值"""
        device = MockGPUDevice(MIN_GPU_MEMORY + 1)  # 略大于1MB
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size >= 1024

    def test_very_large_memory_100gb(self):
        """测试超大显存（100GB）"""
        device = MockGPUDevice(100 * 1024**3)
        batch_size = calculate_optimal_batch_size(device)

        assert batch_size == 8388608  # 应该达到最大值8M

    def test_zero_target_buffer(self):
        """测试目标缓冲区为0"""
        device = MockGPUDevice(6 * 1024**3)
        batch_size = calculate_optimal_batch_size(device, target_buffer_size=0)

        assert batch_size == 8388608

    def test_large_target_buffer(self):
        """测试大目标缓冲区（100万个目标地址）"""
        device = MockGPUDevice(6 * 1024**3)
        target_buffer_size = 1_000_000 * 20  # 100万个目标地址，~19MB

        batch_size = calculate_optimal_batch_size(device, target_buffer_size)

        # 对6GB显存影响很小
        assert batch_size >= 8000000  # 仍然接近8M

    def test_target_buffer_exceeds_available(self):
        """测试目标缓冲区超过可用内存"""
        device = MockGPUDevice(128 * 1024**2)  # 128MB
        target_buffer_size = 100 * 1024**2  # 100MB（超过50%可用内存）

        batch_size = calculate_optimal_batch_size(device, target_buffer_size)

        # 应该返回最小batch_size
        assert batch_size == 1024


# ============================================================================
# 异常路径测试
# ============================================================================


class TestExceptionPaths:
    """异常路径测试"""

    def test_negative_target_buffer_size(self):
        """测试负数目标缓冲区大小"""
        device = MockGPUDevice(6 * 1024**3)

        with pytest.raises(ValueError) as exc_info:
            calculate_optimal_batch_size(device, target_buffer_size=-1)

        assert "target_buffer_size不能为负数" in str(exc_info.value)

    def test_zero_memory_usage_ratio(self):
        """测试显存使用比例为0"""
        device = MockGPUDevice(6 * 1024**3)

        with pytest.raises(ValueError) as exc_info:
            config = BatchSizeConfig(memory_usage_ratio=0)
            calculate_optimal_batch_size(device, config=config)

        assert "memory_usage_ratio必须在(0, 1]范围内" in str(exc_info.value)

    def test_negative_memory_usage_ratio(self):
        """测试显存使用比例为负数"""
        device = MockGPUDevice(6 * 1024**3)

        with pytest.raises(ValueError) as exc_info:
            config = BatchSizeConfig(memory_usage_ratio=-0.5)
            calculate_optimal_batch_size(device, config=config)

        assert "memory_usage_ratio必须在(0, 1]范围内" in str(exc_info.value)

    def test_memory_usage_ratio_greater_than_one(self):
        """测试显存使用比例大于1"""
        device = MockGPUDevice(6 * 1024**3)

        with pytest.raises(ValueError) as exc_info:
            config = BatchSizeConfig(memory_usage_ratio=1.5)
            calculate_optimal_batch_size(device, config=config)

        assert "memory_usage_ratio必须在(0, 1]范围内" in str(exc_info.value)

    def test_zero_min_batch_size(self):
        """测试最小batch_size为0"""
        device = MockGPUDevice(6 * 1024**3)

        with pytest.raises(ValueError) as exc_info:
            config = BatchSizeConfig(min_batch_size=0)
            calculate_optimal_batch_size(device, config=config)

        assert "min_batch_size必须为正数" in str(exc_info.value)

    def test_negative_min_batch_size(self):
        """测试最小batch_size为负数"""
        device = MockGPUDevice(6 * 1024**3)

        with pytest.raises(ValueError) as exc_info:
            config = BatchSizeConfig(min_batch_size=-100)
            calculate_optimal_batch_size(device, config=config)

        assert "min_batch_size必须为正数" in str(exc_info.value)

    def test_max_batch_size_less_than_min(self):
        """测试最大batch_size小于最小batch_size"""
        device = MockGPUDevice(6 * 1024**3)

        with pytest.raises(ValueError) as exc_info:
            config = BatchSizeConfig(min_batch_size=10000, max_batch_size=1000)
            calculate_optimal_batch_size(device, config=config)

        assert "max_batch_size" in str(exc_info.value)
        assert "min_batch_size" in str(exc_info.value)

    def test_device_without_device_attribute(self):
        """测试设备对象缺少device属性"""

        class BadDevice:
            pass

        device = BadDevice()
        batch_size = calculate_optimal_batch_size(device)

        # 应该捕获异常并返回默认值
        assert batch_size == DEFAULT_BATCH_SIZE

    def test_device_without_global_mem_size(self):
        """测试设备对象缺少global_mem_size属性"""

        class BadDevice:
            def __init__(self):
                self.device = object()  # 没有global_mem_size

        device = BadDevice()
        batch_size = calculate_optimal_batch_size(device)

        # 应该捕获异常并返回默认值
        assert batch_size == DEFAULT_BATCH_SIZE


# ============================================================================
# 常量测试
# ============================================================================


class TestConstants:
    """常量测试"""

    def test_min_gpu_memory_value(self):
        """测试最小显存常量值"""
        assert MIN_GPU_MEMORY == 1 * 1024 * 1024  # 1MB
        assert MIN_GPU_MEMORY == 1048576

    def test_default_batch_size_value(self):
        """测试默认batch_size常量值"""
        assert DEFAULT_BATCH_SIZE == 65536
        assert DEFAULT_BATCH_SIZE == 64 * 1024


# ============================================================================
# 参数化测试
# ============================================================================


class TestParameterized:
    """参数化测试"""

    @pytest.mark.parametrize(
        "mem_size,expected_range",
        [
            (128 * 1024**2, (1024, 2000000)),  # 128MB
            (256 * 1024**2, (1024, 4000000)),  # 256MB
            (512 * 1024**2, (1024, 8000000)),  # 512MB
            (1024**3, (1024, 8388608)),  # 1GB
            (2 * 1024**3, (1024, 8388608)),  # 2GB
            (4 * 1024**3, (1024, 8388608)),  # 4GB
            (6 * 1024**3, (8388608, 8388608)),  # 6GB
            (8 * 1024**3, (8388608, 8388608)),  # 8GB
            (16 * 1024**3, (8388608, 8388608)),  # 16GB
            (24 * 1024**3, (8388608, 8388608)),  # 24GB
        ],
    )
    def test_various_gpu_memory_sizes(self, mem_size, expected_range):
        """测试各种GPU显存大小"""
        device = MockGPUDevice(mem_size)
        batch_size = calculate_optimal_batch_size(device)

        min_expected, max_expected = expected_range
        assert min_expected <= batch_size <= max_expected
        assert batch_size % 1024 == 0  # 应该对齐到1024

    @pytest.mark.parametrize("target_count", [0, 100, 1000, 10000, 100000])
    def test_various_target_counts(self, target_count):
        """测试不同数量的目标地址"""
        device = MockGPUDevice(6 * 1024**3)
        target_buffer_size = target_count * 20  # 每个Hash160是20字节

        batch_size = calculate_optimal_batch_size(device, target_buffer_size)

        assert batch_size >= 1024
        assert batch_size <= 8388608


# ============================================================================
# 性能测试
# ============================================================================


class TestPerformance:
    """性能测试（简单验证，非基准测试）"""

    def test_calculation_speed(self):
        """测试计算速度（应该在1ms内完成）"""
        import time

        device = MockGPUDevice(6 * 1024**3)

        start = time.perf_counter()
        for _ in range(1000):
            calculate_optimal_batch_size(device)
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000
        avg_ms = elapsed_ms / 1000

        # 平均每次调用应该小于1ms
        assert avg_ms < 1.0, f"平均耗时{avg_ms:.3f}ms，超过1ms"


# ============================================================================
# BatchSizeConfig独立测试
# ============================================================================


class TestBatchSizeConfig:
    """BatchSizeConfig配置对象独立测试"""

    def test_default_values(self):
        """测试默认配置值"""
        config = BatchSizeConfig()

        assert config.memory_usage_ratio == 0.5
        assert config.min_batch_size == 1024
        assert config.max_batch_size == 8388608
        assert config.memory_alignment == 1024
        assert config.per_key_memory == 36

    def test_custom_values(self):
        """测试自定义配置值"""
        config = BatchSizeConfig(
            memory_usage_ratio=0.7,
            min_batch_size=2048,
            max_batch_size=4194304,
            memory_alignment=2048,
            per_key_memory=40,
        )

        assert config.memory_usage_ratio == 0.7
        assert config.min_batch_size == 2048
        assert config.max_batch_size == 4194304
        assert config.memory_alignment == 2048
        assert config.per_key_memory == 40

    def test_partial_custom_values(self):
        """测试部分自定义配置值"""
        config = BatchSizeConfig(memory_usage_ratio=0.8, min_batch_size=4096)

        # 自定义值
        assert config.memory_usage_ratio == 0.8
        assert config.min_batch_size == 4096

        # 默认值
        assert config.max_batch_size == 8388608
        assert config.memory_alignment == 1024
        assert config.per_key_memory == 36

    def test_config_equality(self):
        """测试配置对象相等性"""
        config1 = BatchSizeConfig()
        config2 = BatchSizeConfig()

        # dataclass自动生成__eq__
        assert config1 == config2

        config3 = BatchSizeConfig(memory_usage_ratio=0.7)
        assert config1 != config3

    def test_config_repr(self):
        """测试配置对象字符串表示"""
        config = BatchSizeConfig()
        repr_str = repr(config)

        # dataclass自动生成__repr__
        assert "BatchSizeConfig" in repr_str
        assert "memory_usage_ratio=0.5" in repr_str
        assert "min_batch_size=1024" in repr_str

    def test_config_immutability_option(self):
        """测试配置对象可变性（当前为可变）"""
        config = BatchSizeConfig()

        # 当前实现是可变的
        config.memory_usage_ratio = 0.7
        assert config.memory_usage_ratio == 0.7

    def test_config_validation_method(self):
        """测试配置验证方法"""
        # 有效配置
        config1 = BatchSizeConfig()
        config1.validate()  # 不应抛出异常

        config2 = BatchSizeConfig(
            memory_usage_ratio=0.7, min_batch_size=2048, max_batch_size=4194304
        )
        config2.validate()  # 不应抛出异常

        # 无效配置 - memory_usage_ratio为0
        with pytest.raises(ValueError) as exc_info:
            BatchSizeConfig(memory_usage_ratio=0)
        assert "memory_usage_ratio必须在(0, 1]范围内" in str(exc_info.value)

        # 无效配置 - memory_usage_ratio为负数
        with pytest.raises(ValueError):
            BatchSizeConfig(memory_usage_ratio=-0.5)

        # 无效配置 - memory_usage_ratio大于1
        with pytest.raises(ValueError):
            BatchSizeConfig(memory_usage_ratio=1.5)

        # 无效配置 - min_batch_size为0
        with pytest.raises(ValueError) as exc_info:
            BatchSizeConfig(min_batch_size=0)
        assert "min_batch_size必须为正数" in str(exc_info.value)

        # 无效配置 - min_batch_size为负数
        with pytest.raises(ValueError):
            BatchSizeConfig(min_batch_size=-100)

        # 无效配置 - max_batch_size < min_batch_size
        with pytest.raises(ValueError) as exc_info:
            BatchSizeConfig(min_batch_size=10000, max_batch_size=1000)
        assert "max_batch_size" in str(exc_info.value)
        assert "min_batch_size" in str(exc_info.value)

        # 无效配置 - memory_alignment为0
        with pytest.raises(ValueError) as exc_info:
            BatchSizeConfig(memory_alignment=0)
        assert "memory_alignment必须为正数" in str(exc_info.value)

        # 无效配置 - memory_alignment为负数
        with pytest.raises(ValueError):
            BatchSizeConfig(memory_alignment=-1024)

        # 无效配置 - per_key_memory为0
        with pytest.raises(ValueError) as exc_info:
            BatchSizeConfig(per_key_memory=0)
        assert "per_key_memory必须为正数" in str(exc_info.value)

        # 无效配置 - per_key_memory为负数
        with pytest.raises(ValueError):
            BatchSizeConfig(per_key_memory=-36)

    def test_post_init_auto_validation(self):
        """测试__post_init__自动验证"""
        # 有效配置 - 自动验证通过
        BatchSizeConfig()
        # 如果验证失败，会在创建时抛出异常

        config2 = BatchSizeConfig(memory_usage_ratio=0.7, min_batch_size=2048)  # noqa: F841
        # 自动验证通过

        # 无效配置 - 自动验证失败
        with pytest.raises(ValueError) as exc_info:
            BatchSizeConfig(memory_usage_ratio=0)
        assert "memory_usage_ratio必须在(0, 1]范围内" in str(exc_info.value)

        with pytest.raises(ValueError):
            BatchSizeConfig(min_batch_size=0)

        with pytest.raises(ValueError):
            BatchSizeConfig(memory_alignment=0)

        with pytest.raises(ValueError):
            BatchSizeConfig(per_key_memory=0)

    def test_config_serialization(self):
        """测试配置对象序列化"""
        from dataclasses import asdict
        import json

        config = BatchSizeConfig(memory_usage_ratio=0.7, min_batch_size=2048)

        # 序列化为字典
        config_dict = asdict(config)
        assert isinstance(config_dict, dict)
        assert config_dict["memory_usage_ratio"] == 0.7
        assert config_dict["min_batch_size"] == 2048

        # 序列化为JSON
        json_str = json.dumps(config_dict)
        assert isinstance(json_str, str)

        # 反序列化
        restored_dict = json.loads(json_str)
        restored_config = BatchSizeConfig(**restored_dict)
        assert restored_config == config

    def test_config_reuse(self):
        """测试配置对象复用"""
        config = BatchSizeConfig(memory_usage_ratio=0.7)

        device1 = MockGPUDevice(6 * 1024**3)
        device2 = MockGPUDevice(8 * 1024**3)
        device3 = MockGPUDevice(12 * 1024**3)

        # 同一配置用于多个设备
        batch_size1 = calculate_optimal_batch_size(device1, config=config)
        batch_size2 = calculate_optimal_batch_size(device2, config=config)
        batch_size3 = calculate_optimal_batch_size(device3, config=config)

        # 都应该成功计算
        assert batch_size1 >= 1024
        assert batch_size2 >= 1024
        assert batch_size3 >= 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
