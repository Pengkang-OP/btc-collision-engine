#!/usr/bin/env python3
"""GPU 配置数据类 (gpu_config.py) 单元测试.

覆盖：
- MultiGPUConfig: 默认值、from_dict、嵌套配置
- WorkerConfig: 默认值、from_dict、to_dict
- GPURecoveryConfig: 默认值、from_dict
- DataMonitorConfig: 默认值、from_dict、dict-like get()
- 边界值处理：None dict、空 dict、部分覆盖、类型转换、大值
"""

import pytest

from src.gpu.gpu_config import (
    DataMonitorConfig,
    GPURecoveryConfig,
    MultiGPUConfig,
    WorkerConfig,
)

# ============================================================================
# MultiGPUConfig 测试
# ============================================================================


@pytest.mark.unit
class TestMultiGPUConfig:
    """MultiGPUConfig 数据类测试."""

    # ── 默认值 ──

    def test_default_values(self):
        """测试默认值."""
        cfg = MultiGPUConfig()
        assert cfg.total_pool_mb == 512
        assert cfg.enable_data_monitor is True
        assert isinstance(cfg.data_monitor, DataMonitorConfig)
        assert isinstance(cfg.gpu_recovery, GPURecoveryConfig)
        assert cfg.worker_join_timeout == 30
        assert cfg.workload_monitor_interval == 5
        assert cfg.auto_rebalance is True
        assert cfg.auto_pause_on_critical is False
        assert cfg.per_device_config == {}

    # ── from_dict ──

    def test_from_dict_none(self):
        """测试 from_dict(None) 使用默认值."""
        cfg = MultiGPUConfig.from_dict(None)
        assert cfg.total_pool_mb == 512

    def test_from_dict_empty(self):
        """测试 from_dict({}) 使用默认值."""
        cfg = MultiGPUConfig.from_dict({})
        assert cfg.total_pool_mb == 512
        assert cfg.enable_data_monitor is True

    def test_from_dict_partial(self):
        """测试 from_dict 部分覆盖."""
        cfg = MultiGPUConfig.from_dict(
            {
                "total_pool_mb": 1024,
                "worker_join_timeout": 60,
            },
        )
        assert cfg.total_pool_mb == 1024
        assert cfg.worker_join_timeout == 60
        # 未指定的保持默认
        assert cfg.enable_data_monitor is True
        assert cfg.workload_monitor_interval == 5

    def test_from_dict_full(self):
        """测试 from_dict 完整覆盖."""
        cfg = MultiGPUConfig.from_dict(
            {
                "total_pool_mb": 2048,
                "enable_data_monitor": False,
                "data_monitor": {"check_interval": 2.0},
                "gpu_recovery": {"max_retry_count": 5},
                "worker_join_timeout": 120,
                "workload_monitor_interval": 10,
                "auto_rebalance": False,
                "auto_pause_on_critical": True,
                "per_device_config": {"gpu0": {"batch_size": 1024}},
            },
        )
        assert cfg.total_pool_mb == 2048
        assert cfg.enable_data_monitor is False
        assert cfg.data_monitor.check_interval == 2.0
        assert cfg.gpu_recovery.max_retry_count == 5
        assert cfg.worker_join_timeout == 120
        assert cfg.workload_monitor_interval == 10
        assert cfg.auto_rebalance is False
        assert cfg.auto_pause_on_critical is True
        assert cfg.per_device_config == {"gpu0": {"batch_size": 1024}}

    # ── 嵌套配置 ──

    def test_nested_data_monitor_no_dict(self):
        """测试未指定 data_monitor 时使用默认."""
        cfg = MultiGPUConfig.from_dict({})
        assert isinstance(cfg.data_monitor, DataMonitorConfig)
        assert cfg.data_monitor.check_interval == 1.0

    def test_nested_gpu_recovery_no_dict(self):
        """测试未指定 gpu_recovery 时使用默认."""
        cfg = MultiGPUConfig.from_dict({})
        assert isinstance(cfg.gpu_recovery, GPURecoveryConfig)
        assert cfg.gpu_recovery.max_retry_count == 3

    # ── 边界值 ──

    def test_boundary_zero_pool(self):
        """测试 total_pool_mb=0（边界值）."""
        cfg = MultiGPUConfig.from_dict({"total_pool_mb": 0})
        assert cfg.total_pool_mb == 0

    def test_boundary_large_values(self):
        """测试大值."""
        cfg = MultiGPUConfig.from_dict(
            {
                "total_pool_mb": 10**6,
                "worker_join_timeout": 3600,
                "workload_monitor_interval": 86400,
            },
        )
        assert cfg.total_pool_mb == 10**6
        assert cfg.worker_join_timeout == 3600

    def test_unknown_keys_ignored(self):
        """测试未知键被忽略."""
        cfg = MultiGPUConfig.from_dict({"unknown_key": 999, "total_pool_mb": 100})
        assert cfg.total_pool_mb == 100
        # 不应有 unknown_key 属性
        assert not hasattr(cfg, "unknown_key")


# ============================================================================
# WorkerConfig 测试
# ============================================================================


@pytest.mark.unit
class TestWorkerConfig:
    """WorkerConfig 数据类测试."""

    # ── 默认值 ──

    def test_default_values(self):
        """测试默认值."""
        cfg = WorkerConfig()
        assert cfg.batch_size is None
        assert cfg.work_group_size == 256
        assert cfg.max_memory_mb is None

    # ── from_dict ──

    def test_from_dict_none(self):
        """测试 from_dict(None)."""
        cfg = WorkerConfig.from_dict(None)
        assert cfg.batch_size is None

    def test_from_dict_empty(self):
        """测试 from_dict({})."""
        cfg = WorkerConfig.from_dict({})
        assert cfg.batch_size is None
        assert cfg.work_group_size == 256

    def test_from_dict_full(self):
        """测试 from_dict 完整填充."""
        cfg = WorkerConfig.from_dict(
            {
                "batch_size": 65536,
                "work_group_size": 512,
                "max_memory_mb": 4096,
            },
        )
        assert cfg.batch_size == 65536
        assert cfg.work_group_size == 512
        assert cfg.max_memory_mb == 4096

    # ── to_dict ──

    def test_to_dict_full(self):
        """测试 to_dict 完整输出."""
        cfg = WorkerConfig(batch_size=1024, work_group_size=256, max_memory_mb=2048)
        result = cfg.to_dict()
        assert result == {
            "batch_size": 1024,
            "work_group_size": 256,
            "max_memory_mb": 2048,
        }

    def test_to_dict_none_max_memory(self):
        """测试 to_dict 时 max_memory_mb 为 None 被省略."""
        cfg = WorkerConfig(batch_size=1024, work_group_size=256)
        result = cfg.to_dict()
        assert result == {
            "batch_size": 1024,
            "work_group_size": 256,
        }
        assert "max_memory_mb" not in result

    def test_to_dict_default(self):
        """测试默认 WorkerConfig 的 to_dict."""
        cfg = WorkerConfig()
        result = cfg.to_dict()
        assert result == {
            "batch_size": None,
            "work_group_size": 256,
        }

    # ── 边界值 ──

    def test_boundary_zero_batch(self):
        """测试 batch_size=0（边界值）."""
        cfg = WorkerConfig.from_dict({"batch_size": 0})
        assert cfg.batch_size == 0

    def test_boundary_negative(self):
        """测试负数值保留（不在此层校验）."""
        cfg = WorkerConfig.from_dict({"work_group_size": -1})
        assert cfg.work_group_size == -1

    # ── 类型安全 ──

    def test_batch_size_is_int_or_none(self):
        """测试 batch_size 类型."""
        cfg = WorkerConfig(batch_size=10000)
        assert isinstance(cfg.batch_size, int)
        cfg2 = WorkerConfig()
        assert cfg2.batch_size is None


# ============================================================================
# GPURecoveryConfig 测试
# ============================================================================


@pytest.mark.unit
class TestGPURecoveryConfig:
    """GPURecoveryConfig 数据类测试."""

    def test_default_values(self):
        """测试默认值."""
        cfg = GPURecoveryConfig()
        assert cfg.max_retry_count == 3
        assert cfg.retry_delay_seconds == 5.0
        assert cfg.batch_size_reduction_factor == 0.5
        assert cfg.auto_redistribute is True

    def test_from_dict_none(self):
        """测试 from_dict(None)."""
        cfg = GPURecoveryConfig.from_dict(None)
        assert cfg.max_retry_count == 3

    def test_from_dict_empty(self):
        """测试 from_dict({})."""
        cfg = GPURecoveryConfig.from_dict({})
        assert cfg.max_retry_count == 3

    def test_from_dict_partial(self):
        """测试 from_dict 部分覆盖."""
        cfg = GPURecoveryConfig.from_dict(
            {
                "max_retry_count": 10,
                "batch_size_reduction_factor": 0.25,
            },
        )
        assert cfg.max_retry_count == 10
        assert cfg.batch_size_reduction_factor == 0.25
        assert cfg.retry_delay_seconds == 5.0  # 保持默认
        assert cfg.auto_redistribute is True

    def test_from_dict_full(self):
        """测试 from_dict 完整覆盖."""
        cfg = GPURecoveryConfig.from_dict(
            {
                "max_retry_count": 1,
                "retry_delay_seconds": 1.0,
                "batch_size_reduction_factor": 0.1,
                "auto_redistribute": False,
            },
        )
        assert cfg.max_retry_count == 1
        assert cfg.retry_delay_seconds == 1.0
        assert cfg.batch_size_reduction_factor == 0.1
        assert cfg.auto_redistribute is False

    # ── 边界值 ──

    def test_boundary_zero_retry(self):
        """测试 max_retry_count=0."""
        cfg = GPURecoveryConfig.from_dict({"max_retry_count": 0})
        assert cfg.max_retry_count == 0

    def test_boundary_zero_delay(self):
        """测试 retry_delay_seconds=0."""
        cfg = GPURecoveryConfig.from_dict({"retry_delay_seconds": 0.0})
        assert cfg.retry_delay_seconds == 0.0

    def test_boundary_full_reduction(self):
        """测试 batch_size_reduction_factor=1.0（不缩减）."""
        cfg = GPURecoveryConfig.from_dict({"batch_size_reduction_factor": 1.0})
        assert cfg.batch_size_reduction_factor == 1.0

    def test_boundary_large_retry(self):
        """测试大重试次数."""
        cfg = GPURecoveryConfig.from_dict({"max_retry_count": 9999})
        assert cfg.max_retry_count == 9999


# ============================================================================
# DataMonitorConfig 测试
# ============================================================================


@pytest.mark.unit
class TestDataMonitorConfig:
    """DataMonitorConfig 数据类测试."""

    # ── 默认值 ──

    def test_default_values(self):
        """测试默认值."""
        cfg = DataMonitorConfig()
        assert cfg.check_interval == 1.0
        assert cfg.throughput_threshold == 0.5
        assert cfg.error_rate_threshold == 0.1
        assert cfg.stale_data_timeout == 10.0
        assert cfg.max_issues_per_minute == 100
        assert cfg.max_seen_keys == 100000
        assert cfg.max_seen_addresses == 10000
        assert cfg.max_retry_count == 3
        assert cfg.anomaly_threshold == 0.1

    # ── from_dict ──

    def test_from_dict_none(self):
        """测试 from_dict(None)."""
        cfg = DataMonitorConfig.from_dict(None)
        assert cfg.check_interval == 1.0

    def test_from_dict_empty(self):
        """测试 from_dict({})."""
        cfg = DataMonitorConfig.from_dict({})
        assert cfg.check_interval == 1.0
        assert cfg.max_seen_keys == 100000

    def test_from_dict_partial(self):
        """测试 from_dict 部分覆盖."""
        cfg = DataMonitorConfig.from_dict(
            {
                "check_interval": 5.0,
                "max_seen_keys": 50000,
            },
        )
        assert cfg.check_interval == 5.0
        assert cfg.max_seen_keys == 50000
        assert cfg.throughput_threshold == 0.5  # 保持默认

    def test_from_dict_full(self):
        """测试 from_dict 完整覆盖."""
        cfg = DataMonitorConfig.from_dict(
            {
                "check_interval": 2.0,
                "throughput_threshold": 0.8,
                "error_rate_threshold": 0.05,
                "stale_data_timeout": 30.0,
                "max_issues_per_minute": 200,
                "max_seen_keys": 500000,
                "max_seen_addresses": 50000,
                "max_retry_count": 10,
                "anomaly_threshold": 0.2,
            },
        )
        assert cfg.check_interval == 2.0
        assert cfg.throughput_threshold == 0.8
        assert cfg.error_rate_threshold == 0.05
        assert cfg.stale_data_timeout == 30.0
        assert cfg.max_issues_per_minute == 200
        assert cfg.max_seen_keys == 500000
        assert cfg.max_seen_addresses == 50000
        assert cfg.max_retry_count == 10
        assert cfg.anomaly_threshold == 0.2

    # ── dict-like get() ──

    def test_get_existing_key(self):
        """测试 get() 获取存在的键."""
        cfg = DataMonitorConfig()
        assert cfg.get("check_interval") == 1.0
        assert cfg.get("max_seen_keys") == 100000

    def test_get_missing_key_with_default(self):
        """测试 get() 获取不存在的键返回默认值."""
        cfg = DataMonitorConfig()
        assert cfg.get("non_existent", 42) == 42

    def test_get_missing_key_no_default(self):
        """测试 get() 获取不存在的键无默认值时返回 None."""
        cfg = DataMonitorConfig()
        assert cfg.get("non_existent") is None

    def test_get_custom_value(self):
        """测试 get() 自定义构造后的值."""
        cfg = DataMonitorConfig.from_dict({"check_interval": 3.0})
        assert cfg.get("check_interval") == 3.0

    # ── 边界值 ──

    def test_boundary_zero_interval(self):
        """测试 check_interval=0."""
        cfg = DataMonitorConfig.from_dict({"check_interval": 0.0})
        assert cfg.check_interval == 0.0

    def test_boundary_zero_threshold(self):
        """测试 anomaly_threshold=0."""
        cfg = DataMonitorConfig.from_dict({"anomaly_threshold": 0.0})
        assert cfg.anomaly_threshold == 0.0

    def test_boundary_large_seen(self):
        """测试大的 seen 值."""
        cfg = DataMonitorConfig.from_dict(
            {
                "max_seen_keys": 10**9,
                "max_seen_addresses": 10**8,
            },
        )
        assert cfg.max_seen_keys == 10**9
        assert cfg.max_seen_addresses == 10**8


# ============================================================================
# 集成测试: 数据类之间的组合
# ============================================================================


@pytest.mark.unit
class TestConfigComposition:
    """测试多个配置数据类组合使用."""

    def test_multi_gpu_contains_nested(self):
        """测试 MultiGPUConfig 的嵌套配置类型正确."""
        cfg = MultiGPUConfig()
        assert isinstance(cfg.data_monitor, DataMonitorConfig)
        assert isinstance(cfg.gpu_recovery, GPURecoveryConfig)

    def test_from_dict_nested_inheritance(self):
        """测试嵌套配置从 dict 继承."""
        cfg = MultiGPUConfig.from_dict(
            {
                "data_monitor": {"check_interval": 7.0},
                "gpu_recovery": {"max_retry_count": 7},
            },
        )
        assert cfg.data_monitor.check_interval == 7.0
        # 未指定的嵌套字段保持默认
        assert cfg.data_monitor.throughput_threshold == 0.5
        assert cfg.gpu_recovery.max_retry_count == 7
        assert cfg.gpu_recovery.retry_delay_seconds == 5.0

    def test_from_dict_none_nested(self):
        """测试 from_dict 未指定嵌套时为默认对象."""
        cfg = MultiGPUConfig.from_dict({"total_pool_mb": 100})
        assert isinstance(cfg.data_monitor, DataMonitorConfig)
        assert cfg.data_monitor.check_interval == 1.0

    def test_round_trip_worker_config(self):
        """测试 WorkerConfig from_dict -> to_dict 往返."""
        original = {"batch_size": 65536, "work_group_size": 512, "max_memory_mb": 8192}
        cfg = WorkerConfig.from_dict(original)
        result = cfg.to_dict()
        assert result == original
