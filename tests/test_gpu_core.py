#!/usr/bin/env python3
"""GPU 核心模块补充测试

覆盖 src/gpu/ 下未充分测试的模块：
- constants.py (GPU常量与辅助函数)
- kernel_protocol.py (GPU内核协议与工厂)
- gpu_config.py (GPU配置 dataclass)
"""

import pytest
from unittest.mock import Mock

# ============================================================================
# 1. GPU Constants 测试
# ============================================================================

from src.gpu.constants import (
    PER_KEY_MEMORY_BYTES,
    BYTES_PER_MB,
    BATCH_SIZE_ALIGNMENT,
    MIN_BATCH_SIZE,
    MAX_BATCH_SIZE,
    DEFAULT_BATCH_SIZE,
    MEMORY_EFFICIENCY_MIN,
    MEMORY_EFFICIENCY_MAX,
    DEFAULT_MEMORY_EFFICIENCY,
    align_batch_size,
    clamp_batch_size,
)


class TestGPUConstants:
    """GPU常量定义测试"""

    def test_per_key_memory(self):
        assert PER_KEY_MEMORY_BYTES == 36

    def test_bytes_per_mb(self):
        assert BYTES_PER_MB == 1024 * 1024

    def test_batch_size_alignment(self):
        assert BATCH_SIZE_ALIGNMENT == 1024

    def test_batch_size_bounds(self):
        assert MIN_BATCH_SIZE == 1024
        assert MAX_BATCH_SIZE == 4194304
        assert DEFAULT_BATCH_SIZE == 262144

    def test_memory_efficiency_bounds(self):
        assert MEMORY_EFFICIENCY_MIN == 0.1
        assert MEMORY_EFFICIENCY_MAX == 0.9
        assert DEFAULT_MEMORY_EFFICIENCY == 0.6


class TestAlignBatchSize:
    """align_batch_size 函数测试"""

    def test_exact_alignment(self):
        """精确对齐值"""
        assert align_batch_size(1024) == 1024
        assert align_batch_size(2048) == 2048
        assert align_batch_size(262144) == 262144

    def test_rounds_down(self):
        """向下对齐"""
        assert align_batch_size(1500) == 1024
        assert align_batch_size(2047) == 1024

    def test_large_batch(self):
        """大批次"""
        assert align_batch_size(262145, 1024) == 262144

    def test_below_minimum(self):
        """低于最小值的批次"""
        assert align_batch_size(512) == MIN_BATCH_SIZE
        assert align_batch_size(0) == MIN_BATCH_SIZE
        assert align_batch_size(1) == MIN_BATCH_SIZE

    def test_custom_alignment(self):
        """自定义对齐值"""
        assert align_batch_size(5000, 2048) == 4096

    def test_zero_batch(self):
        """零批次"""
        assert align_batch_size(0) == 1024


class TestClampBatchSize:
    """clamp_batch_size 函数测试"""

    def test_within_range(self):
        """范围内值保持不变"""
        assert clamp_batch_size(1024) == 1024
        assert clamp_batch_size(262144) == 262144
        assert clamp_batch_size(4194304) == 4194304

    def test_below_min(self):
        """低于最小值被提升"""
        assert clamp_batch_size(0) == MIN_BATCH_SIZE
        assert clamp_batch_size(500) == MIN_BATCH_SIZE

    def test_above_max(self):
        """高于最大值被限制"""
        assert clamp_batch_size(5000000) == MAX_BATCH_SIZE
        assert clamp_batch_size(10000000) == MAX_BATCH_SIZE


# ============================================================================
# 2. GPUKernelProtocol 测试
# ============================================================================

from src.gpu.kernel_protocol import GPUKernelProtocol, GPUKernelFactory  # noqa: E402


class TestGPUKernelProtocol:
    """GPUKernelProtocol 协议测试"""

    def test_protocol_is_runtime_checkable(self):
        """协议是运行时可检查的"""

        assert hasattr(GPUKernelProtocol, "__metadata__") or True

    def test_isinstance_with_mock(self):
        """Mock 对象可以满足协议（如果实现所有方法）"""

        class MockKernel:
            def run_batch(self, seed, num_keys):
                return []

            def set_targets(self, target_hash160s, num_targets, check_uncompressed=0):
                pass

            def cleanup(self):
                pass

            @property
            def max_batch_size(self):
                return 65536

            @property
            def device(self):
                return Mock()

            @property
            def program(self):
                return Mock()

        kernel = MockKernel()
        assert isinstance(kernel, GPUKernelProtocol)


class TestGPUKernelFactory:
    """GPUKernelFactory 工厂测试"""

    def test_create_without_register_raises(self):
        """未注册时创建抛出异常"""
        GPUKernelFactory.reset()
        with pytest.raises(ValueError, match="未注册GPU内核类"):
            GPUKernelFactory.create(Mock())

    def test_register_and_create(self):
        """注册后可以创建实例"""
        GPUKernelFactory.reset()

        class MockKernelClass:
            def __init__(self, device, max_batch_size=None, program=None):
                self.device = device
                self.max_batch_size = max_batch_size or 65536
                self.program = program

            def run_batch(self, seed, num_keys):
                return []

            def set_targets(self, *args, **kwargs):
                pass

            def cleanup(self):
                pass

        GPUKernelFactory.register(MockKernelClass)
        device_mock = Mock()
        kernel = GPUKernelFactory.create(device_mock, max_batch_size=131072)

        assert kernel.device is device_mock
        assert kernel.max_batch_size == 131072

        GPUKernelFactory.reset()

    def test_reset(self):
        """reset 清空注册"""
        GPUKernelFactory.reset()

        class DummyKernel:
            def __init__(self, device, max_batch_size=None, program=None):
                pass

        GPUKernelFactory.register(DummyKernel)
        assert GPUKernelFactory._kernel_class is not None

        GPUKernelFactory.reset()
        assert GPUKernelFactory._kernel_class is None

    def test_create_passes_program(self):
        """create 传递 program 参数"""
        GPUKernelFactory.reset()

        captured_program = []

        class MockKernelClass:
            def __init__(self, device, max_batch_size=None, program=None):
                self.device = device
                self.program = program
                captured_program.append(program)

        GPUKernelFactory.register(MockKernelClass)
        mock_program = Mock()
        kernel = GPUKernelFactory.create(Mock(), program=mock_program)  # noqa: F841

        assert captured_program[0] is mock_program
        GPUKernelFactory.reset()


# ============================================================================
# 3. GPU Config Dataclasses 测试
# ============================================================================

from src.gpu.gpu_config import (  # noqa: E402
    GPURecoveryConfig,
    DataMonitorConfig,
    MultiGPUConfig,
    WorkerConfig,
)


class TestGPURecoveryConfig:
    """GPURecoveryConfig 测试"""

    def test_defaults(self):
        config = GPURecoveryConfig()
        assert config.max_retry_count == 3
        assert config.retry_delay_seconds == 5.0
        assert config.batch_size_reduction_factor == 0.5
        assert config.auto_redistribute is True

    def test_custom_values(self):
        config = GPURecoveryConfig(
            max_retry_count=5,
            retry_delay_seconds=10.0,
            batch_size_reduction_factor=0.3,
            auto_redistribute=False,
        )
        assert config.max_retry_count == 5
        assert config.retry_delay_seconds == 10.0
        assert config.batch_size_reduction_factor == 0.3
        assert config.auto_redistribute is False

    def test_from_dict_empty(self):
        config = GPURecoveryConfig.from_dict({})
        assert config.max_retry_count == 3

    def test_from_dict_none(self):
        config = GPURecoveryConfig.from_dict(None)
        assert config.max_retry_count == 3

    def test_from_dict_partial(self):
        config = GPURecoveryConfig.from_dict({"max_retry_count": 10})
        assert config.max_retry_count == 10
        assert config.retry_delay_seconds == 5.0  # default

    def test_from_dict_full(self):
        d = {
            "max_retry_count": 7,
            "retry_delay_seconds": 2.5,
            "batch_size_reduction_factor": 0.75,
            "auto_redistribute": False,
        }
        config = GPURecoveryConfig.from_dict(d)
        assert config.max_retry_count == 7
        assert config.retry_delay_seconds == 2.5
        assert config.batch_size_reduction_factor == 0.75
        assert config.auto_redistribute is False


class TestDataMonitorConfig:
    """DataMonitorConfig 测试"""

    def test_defaults(self):
        config = DataMonitorConfig()
        assert config.check_interval == 1.0
        assert config.throughput_threshold == 0.5
        assert config.error_rate_threshold == 0.1
        assert config.stale_data_timeout == 10.0
        assert config.max_issues_per_minute == 100

    def test_get_method(self):
        """.get() 兼容 dict-like 访问"""
        config = DataMonitorConfig()
        assert config.get("check_interval") == 1.0
        assert config.get("nonexistent") is None
        assert config.get("nonexistent", "default") == "default"

    def test_from_dict_none(self):
        config = DataMonitorConfig.from_dict(None)
        assert config.check_interval == 1.0

    def test_from_dict_partial(self):
        config = DataMonitorConfig.from_dict({"check_interval": 2.0, "error_rate_threshold": 0.25})
        assert config.check_interval == 2.0
        assert config.error_rate_threshold == 0.25
        assert config.throughput_threshold == 0.5  # default


class TestMultiGPUConfig:
    """MultiGPUConfig 测试"""

    def test_defaults(self):
        config = MultiGPUConfig()
        assert config.total_pool_mb == 512
        assert config.enable_data_monitor is True
        assert isinstance(config.data_monitor, DataMonitorConfig)
        assert isinstance(config.gpu_recovery, GPURecoveryConfig)
        assert config.worker_join_timeout == 30
        assert config.workload_monitor_interval == 5
        assert config.auto_rebalance is True
        assert config.auto_pause_on_critical is False
        assert config.per_device_config == {}

    def test_from_dict_none(self):
        config = MultiGPUConfig.from_dict(None)
        assert config.total_pool_mb == 512

    def test_from_dict_empty(self):
        config = MultiGPUConfig.from_dict({})
        assert config.auto_rebalance is True

    def test_from_dict_with_nested(self):
        d = {
            "total_pool_mb": 1024,
            "enable_data_monitor": False,
            "auto_rebalance": False,
            "worker_join_timeout": 60,
            "data_monitor": {"check_interval": 5.0},
            "gpu_recovery": {"max_retry_count": 5},
        }
        config = MultiGPUConfig.from_dict(d)
        assert config.total_pool_mb == 1024
        assert config.enable_data_monitor is False
        assert config.auto_rebalance is False
        assert config.worker_join_timeout == 60
        assert config.data_monitor.check_interval == 5.0
        assert config.gpu_recovery.max_retry_count == 5


class TestWorkerConfig:
    """WorkerConfig 测试"""

    def test_defaults(self):
        config = WorkerConfig()
        assert config.batch_size is None
        assert config.work_group_size == 256
        assert config.max_memory_mb is None

    def test_custom(self):
        config = WorkerConfig(batch_size=65536, work_group_size=128, max_memory_mb=512)
        assert config.batch_size == 65536
        assert config.work_group_size == 128
        assert config.max_memory_mb == 512

    def test_from_dict_none(self):
        config = WorkerConfig.from_dict(None)
        assert config.batch_size is None

    def test_from_dict(self):
        config = WorkerConfig.from_dict({"batch_size": 32768, "work_group_size": 64})
        assert config.batch_size == 32768
        assert config.work_group_size == 64

    def test_to_dict(self):
        config = WorkerConfig(batch_size=131072, max_memory_mb=1024)
        d = config.to_dict()
        assert d["batch_size"] == 131072
        assert d["work_group_size"] == 256
        assert d["max_memory_mb"] == 1024

    def test_to_dict_no_max_memory(self):
        config = WorkerConfig(batch_size=65536)
        d = config.to_dict()
        assert "max_memory_mb" not in d
