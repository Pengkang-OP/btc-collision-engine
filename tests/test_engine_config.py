#!/usr/bin/env python3
"""GPUEngineConfig 单元测试

覆盖 src/collision/gpu/engine.py 中的 GPUEngineConfig 数据类：
- 默认值验证
- 边界值（极小 batch_size=1, 极大 batch_size=1M）
- to_dict / from_dict 往返
- 非法值处理
"""

import pytest

from src.collision.gpu.engine import GPUEngineConfig
from src.collision.gpu.key_generator import KeyGenerationStrategy

# ============================================================================
# 辅助函数
# ============================================================================


def _reconstruct_from_dict(d: dict) -> GPUEngineConfig:
    """从 to_dict() 输出重建 GPUEngineConfig 实例（模拟 from_dict 往返）

    to_dict() 将 key_generation_strategy 序列化为 .value（字符串），
    而构造函数期望 KeyGenerationStrategy 枚举，因此需要显式转换。
    """
    converted = dict(d)
    if "key_generation_strategy" in converted:
        raw = converted["key_generation_strategy"]
        if isinstance(raw, str):
            converted["key_generation_strategy"] = KeyGenerationStrategy(raw)
    return GPUEngineConfig(**converted)


# ============================================================================
# 默认值验证
# ============================================================================


@pytest.mark.unit
class TestGPUEngineConfigDefaults:
    """GPUEngineConfig 默认值验证"""

    def test_default_device_index(self):
        """默认 device_index 应为 1"""
        cfg = GPUEngineConfig()
        assert cfg.device_index == 1

    def test_default_batch_size(self):
        """默认 batch_size 应为 None（自动计算）"""
        cfg = GPUEngineConfig()
        assert cfg.batch_size is None

    def test_default_checkpoint_disabled(self):
        """默认 checkpoint_enabled 应为 False"""
        cfg = GPUEngineConfig()
        assert cfg.checkpoint_enabled is False

    def test_default_dedup_disabled(self):
        """默认 dedup_enabled 应为 False"""
        cfg = GPUEngineConfig()
        assert cfg.dedup_enabled is False

    def test_default_dedup_max_size(self):
        """默认 dedup_max_size 应为 1_000_000"""
        cfg = GPUEngineConfig()
        assert cfg.dedup_max_size == 1_000_000

    def test_default_checkpoint_interval(self):
        """默认 checkpoint_interval 应为 30"""
        cfg = GPUEngineConfig()
        assert cfg.checkpoint_interval == 30

    def test_default_data_logging_enabled(self):
        """默认 data_logging_enabled 应为 True"""
        cfg = GPUEngineConfig()
        assert cfg.data_logging_enabled is True

    def test_default_data_logging_interval(self):
        """默认 data_logging_interval 应为 5"""
        cfg = GPUEngineConfig()
        assert cfg.data_logging_interval == 5

    def test_default_use_enhanced_monitoring(self):
        """默认 use_enhanced_monitoring 应为 True"""
        cfg = GPUEngineConfig()
        assert cfg.use_enhanced_monitoring is True

    def test_default_use_gpu_memory_pool(self):
        """默认 use_gpu_memory_pool 应为 True"""
        cfg = GPUEngineConfig()
        assert cfg.use_gpu_memory_pool is True

    def test_default_gpu_pool_max_buffers(self):
        """默认 gpu_pool_max_buffers 应为 100"""
        cfg = GPUEngineConfig()
        assert cfg.gpu_pool_max_buffers == 100

    def test_default_gpu_pool_max_memory_mb(self):
        """默认 gpu_pool_max_memory_mb 应为 512"""
        cfg = GPUEngineConfig()
        assert cfg.gpu_pool_max_memory_mb == 512

    def test_default_use_async_logging(self):
        """默认 use_async_logging 应为 False"""
        cfg = GPUEngineConfig()
        assert cfg.use_async_logging is False

    def test_default_async_log_file(self):
        """默认 async_log_file 应为 'logs/gpu_async.log'"""
        cfg = GPUEngineConfig()
        assert cfg.async_log_file == "logs/gpu_async.log"

    def test_default_async_log_max_bytes(self):
        """默认 async_log_max_bytes 应为 10MB"""
        cfg = GPUEngineConfig()
        assert cfg.async_log_max_bytes == 10 * 1024 * 1024

    def test_default_async_log_backup_count(self):
        """默认 async_log_backup_count 应为 5"""
        cfg = GPUEngineConfig()
        assert cfg.async_log_backup_count == 5

    def test_default_check_uncompressed(self):
        """默认 check_uncompressed 应为 None（自动检测）"""
        cfg = GPUEngineConfig()
        assert cfg.check_uncompressed is None

    def test_default_key_generation_strategy(self):
        """默认 key_generation_strategy 应为 PRNG_SEED"""
        cfg = GPUEngineConfig()
        assert cfg.key_generation_strategy == KeyGenerationStrategy.PRNG_SEED

    def test_all_defaults_roundtrip_identity(self):
        """全默认值实例经 to_dict 后重建应保持等价"""
        cfg = GPUEngineConfig()
        d = cfg.to_dict()
        cfg2 = _reconstruct_from_dict(d)
        assert cfg2.device_index == cfg.device_index
        assert cfg2.batch_size == cfg.batch_size
        assert cfg2.dedup_max_size == cfg.dedup_max_size
        assert cfg2.key_generation_strategy == cfg.key_generation_strategy


# ============================================================================
# 边界值
# ============================================================================


@pytest.mark.unit
class TestGPUEngineConfigBoundary:
    """GPUEngineConfig 边界值测试"""

    # ── batch_size 边界 ──

    def test_batch_size_min_one(self):
        """batch_size=1（极小批量）"""
        cfg = GPUEngineConfig(batch_size=1)
        assert cfg.batch_size == 1

    def test_batch_size_one_million(self):
        """batch_size=1_000_000（大批量）"""
        cfg = GPUEngineConfig(batch_size=1_000_000)
        assert cfg.batch_size == 1_000_000

    def test_batch_size_zero(self):
        """batch_size=0（边界值）"""
        cfg = GPUEngineConfig(batch_size=0)
        assert cfg.batch_size == 0

    def test_batch_size_large(self):
        """batch_size=2**31-1（极大值）"""
        cfg = GPUEngineConfig(batch_size=2**31 - 1)
        assert cfg.batch_size == 2**31 - 1

    # ── device_index 边界 ──

    def test_device_index_zero(self):
        """device_index=0（第一块 GPU）"""
        cfg = GPUEngineConfig(device_index=0)
        assert cfg.device_index == 0

    def test_device_index_large(self):
        """device_index=99（多 GPU 场景）"""
        cfg = GPUEngineConfig(device_index=99)
        assert cfg.device_index == 99

    # ── dedup_max_size 边界 ──

    def test_dedup_max_size_one(self):
        """dedup_max_size=1（最小去重容量）"""
        cfg = GPUEngineConfig(dedup_max_size=1)
        assert cfg.dedup_max_size == 1

    def test_dedup_max_size_large(self):
        """dedup_max_size=100_000_000（大去重容量）"""
        cfg = GPUEngineConfig(dedup_max_size=100_000_000)
        assert cfg.dedup_max_size == 100_000_000

    # ── checkpoint_interval 边界 ──

    def test_checkpoint_interval_zero(self):
        """checkpoint_interval=0（立即保存）"""
        cfg = GPUEngineConfig(checkpoint_interval=0)
        assert cfg.checkpoint_interval == 0

    def test_checkpoint_interval_large(self):
        """checkpoint_interval=3600（1小时）"""
        cfg = GPUEngineConfig(checkpoint_interval=3600)
        assert cfg.checkpoint_interval == 3600

    # ── gpu_pool_max_buffers 边界 ──

    def test_gpu_pool_max_buffers_zero(self):
        """gpu_pool_max_buffers=0（无缓冲池）"""
        cfg = GPUEngineConfig(gpu_pool_max_buffers=0)
        assert cfg.gpu_pool_max_buffers == 0

    def test_gpu_pool_max_buffers_large(self):
        """gpu_pool_max_buffers=10000（大缓冲池）"""
        cfg = GPUEngineConfig(gpu_pool_max_buffers=10000)
        assert cfg.gpu_pool_max_buffers == 10000

    # ── gpu_pool_max_memory_mb 边界 ──

    def test_gpu_pool_max_memory_mb_zero(self):
        """gpu_pool_max_memory_mb=0（无内存池）"""
        cfg = GPUEngineConfig(gpu_pool_max_memory_mb=0)
        assert cfg.gpu_pool_max_memory_mb == 0

    def test_gpu_pool_max_memory_mb_large(self):
        """gpu_pool_max_memory_mb=32768（32GB）"""
        cfg = GPUEngineConfig(gpu_pool_max_memory_mb=32768)
        assert cfg.gpu_pool_max_memory_mb == 32768

    # ── async_log_max_bytes 边界 ──

    def test_async_log_max_bytes_min(self):
        """async_log_max_bytes=1024（1KB）"""
        cfg = GPUEngineConfig(async_log_max_bytes=1024)
        assert cfg.async_log_max_bytes == 1024

    def test_async_log_max_bytes_large(self):
        """async_log_max_bytes=10**9（1GB）"""
        cfg = GPUEngineConfig(async_log_max_bytes=10**9)
        assert cfg.async_log_max_bytes == 10**9

    # ── async_log_backup_count 边界 ──

    def test_async_log_backup_count_zero(self):
        """async_log_backup_count=0（不保留备份）"""
        cfg = GPUEngineConfig(async_log_backup_count=0)
        assert cfg.async_log_backup_count == 0

    # ── data_logging_interval 边界 ──

    def test_data_logging_interval_min(self):
        """data_logging_interval=1（每秒记录）"""
        cfg = GPUEngineConfig(data_logging_interval=1)
        assert cfg.data_logging_interval == 1

    # ── check_uncompressed 边界 ──

    def test_check_uncompressed_true(self):
        """check_uncompressed=True（强制双格式检查）"""
        cfg = GPUEngineConfig(check_uncompressed=True)
        assert cfg.check_uncompressed is True

    def test_check_uncompressed_false(self):
        """check_uncompressed=False（仅压缩格式）"""
        cfg = GPUEngineConfig(check_uncompressed=False)
        assert cfg.check_uncompressed is False

    # ── 字符串边界 ──

    def test_async_log_file_empty(self):
        """async_log_file=''（空路径）"""
        cfg = GPUEngineConfig(async_log_file="")
        assert cfg.async_log_file == ""

    def test_async_log_file_special_chars(self):
        """async_log_file 含特殊字符"""
        special_path = "logs/gpu_async_test-v2.0_2026.log"
        cfg = GPUEngineConfig(async_log_file=special_path)
        assert cfg.async_log_file == special_path


# ============================================================================
# to_dict / from_dict 往返
# ============================================================================


@pytest.mark.unit
class TestGPUEngineConfigRoundtrip:
    """GPUEngineConfig to_dict / from_dict 往返测试"""

    # ── to_dict 输出结构 ──

    def test_to_dict_contains_all_keys(self):
        """to_dict() 应包含所有配置字段"""
        cfg = GPUEngineConfig()
        d = cfg.to_dict()
        expected_keys = {
            "device_index",
            "batch_size",
            "checkpoint_enabled",
            "dedup_enabled",
            "dedup_max_size",
            "checkpoint_interval",
            "data_logging_enabled",
            "data_logging_interval",
            "use_enhanced_monitoring",
            "use_gpu_memory_pool",
            "gpu_pool_max_buffers",
            "gpu_pool_max_memory_mb",
            "use_async_logging",
            "async_log_file",
            "async_log_max_bytes",
            "async_log_backup_count",
            "check_uncompressed",
            "key_generation_strategy",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_strategy_is_string(self):
        """to_dict() 中 key_generation_strategy 应为字符串值"""
        cfg = GPUEngineConfig(key_generation_strategy=KeyGenerationStrategy.AES_CTR)
        d = cfg.to_dict()
        assert d["key_generation_strategy"] == "aes_ctr"
        assert isinstance(d["key_generation_strategy"], str)

    def test_to_dict_none_fields(self):
        """to_dict() 中 None 值字段应正确序列化"""
        cfg = GPUEngineConfig(batch_size=None, check_uncompressed=None)
        d = cfg.to_dict()
        assert d["batch_size"] is None
        assert d["check_uncompressed"] is None

    # ── 往返重建 ──

    def test_roundtrip_full_custom(self):
        """自定义全量配置 to_dict -> 重建 -> 等价性"""
        cfg = GPUEngineConfig(
            device_index=0,
            batch_size=131072,
            checkpoint_enabled=True,
            dedup_enabled=True,
            dedup_max_size=5_000_000,
            checkpoint_interval=60,
            data_logging_enabled=False,
            data_logging_interval=10,
            use_enhanced_monitoring=False,
            use_gpu_memory_pool=False,
            gpu_pool_max_buffers=200,
            gpu_pool_max_memory_mb=1024,
            use_async_logging=True,
            async_log_file="logs/test_custom.log",
            async_log_max_bytes=50 * 1024 * 1024,
            async_log_backup_count=10,
            check_uncompressed=True,
            key_generation_strategy=KeyGenerationStrategy.CHACHA20,
        )
        d = cfg.to_dict()
        cfg2 = _reconstruct_from_dict(d)
        assert cfg2.device_index == cfg.device_index
        assert cfg2.batch_size == cfg.batch_size
        assert cfg2.checkpoint_enabled == cfg.checkpoint_enabled
        assert cfg2.dedup_enabled == cfg.dedup_enabled
        assert cfg2.dedup_max_size == cfg.dedup_max_size
        assert cfg2.checkpoint_interval == cfg.checkpoint_interval
        assert cfg2.data_logging_enabled == cfg.data_logging_enabled
        assert cfg2.data_logging_interval == cfg.data_logging_interval
        assert cfg2.use_enhanced_monitoring == cfg.use_enhanced_monitoring
        assert cfg2.use_gpu_memory_pool == cfg.use_gpu_memory_pool
        assert cfg2.gpu_pool_max_buffers == cfg.gpu_pool_max_buffers
        assert cfg2.gpu_pool_max_memory_mb == cfg.gpu_pool_max_memory_mb
        assert cfg2.use_async_logging == cfg.use_async_logging
        assert cfg2.async_log_file == cfg.async_log_file
        assert cfg2.async_log_max_bytes == cfg.async_log_max_bytes
        assert cfg2.async_log_backup_count == cfg.async_log_backup_count
        assert cfg2.check_uncompressed == cfg.check_uncompressed
        assert cfg2.key_generation_strategy == cfg.key_generation_strategy

    def test_roundtrip_minimal(self):
        """最小配置（仅覆盖 batch_size）往返"""
        cfg = GPUEngineConfig(batch_size=65536)
        d = cfg.to_dict()
        cfg2 = _reconstruct_from_dict(d)
        assert cfg2.batch_size == 65536
        # 未覆盖字段应为默认值
        assert cfg2.device_index == 1
        assert cfg2.dedup_max_size == 1_000_000

    def test_roundtrip_all_strategies(self):
        """所有 KeyGenerationStrategy 枚举值往返"""
        for strategy in KeyGenerationStrategy:
            cfg = GPUEngineConfig(key_generation_strategy=strategy)
            d = cfg.to_dict()
            cfg2 = _reconstruct_from_dict(d)
            assert cfg2.key_generation_strategy == strategy, f"策略 {strategy} 往返失败"

    def test_roundtrip_batch_size_none(self):
        """batch_size=None 往返应保持 None"""
        cfg = GPUEngineConfig(batch_size=None)
        d = cfg.to_dict()
        assert d["batch_size"] is None
        cfg2 = _reconstruct_from_dict(d)
        assert cfg2.batch_size is None

    def test_roundtrip_check_uncompressed_false(self):
        """check_uncompressed=False 往返应保持 False"""
        cfg = GPUEngineConfig(check_uncompressed=False)
        d = cfg.to_dict()
        cfg2 = _reconstruct_from_dict(d)
        assert cfg2.check_uncompressed is False

    # ── to_dict 不可变性 ──

    def test_to_dict_modify_does_not_affect_config(self):
        """修改 to_dict() 返回的字典不应影响原始配置"""
        cfg = GPUEngineConfig(batch_size=65536)
        d = cfg.to_dict()
        d["batch_size"] = 999
        d["device_index"] = 999
        assert cfg.batch_size == 65536
        assert cfg.device_index == 1

    def test_multiple_to_dict_consistent(self):
        """多次调用 to_dict() 应返回一致结果"""
        cfg = GPUEngineConfig(batch_size=65536)
        d1 = cfg.to_dict()
        d2 = cfg.to_dict()
        assert d1 == d2


# ============================================================================
# 非法值处理
# ============================================================================


@pytest.mark.unit
class TestGPUEngineConfigInvalid:
    """GPUEngineConfig 非法值及错误处理测试"""

    # ── 负数值 ──

    def test_negative_batch_size(self):
        """batch_size 为负值：数据类不自动校验，允许构造"""
        cfg = GPUEngineConfig(batch_size=-1)
        assert cfg.batch_size == -1

    def test_negative_device_index(self):
        """device_index 为负值"""
        cfg = GPUEngineConfig(device_index=-1)
        assert cfg.device_index == -1

    def test_negative_dedup_max_size(self):
        """dedup_max_size 为负值"""
        cfg = GPUEngineConfig(dedup_max_size=-100)
        assert cfg.dedup_max_size == -100

    def test_negative_checkpoint_interval(self):
        """checkpoint_interval 为负值"""
        cfg = GPUEngineConfig(checkpoint_interval=-10)
        assert cfg.checkpoint_interval == -10

    def test_negative_gpu_pool_max_buffers(self):
        """gpu_pool_max_buffers 为负值"""
        cfg = GPUEngineConfig(gpu_pool_max_buffers=-1)
        assert cfg.gpu_pool_max_buffers == -1

    def test_negative_gpu_pool_max_memory_mb(self):
        """gpu_pool_max_memory_mb 为负值"""
        cfg = GPUEngineConfig(gpu_pool_max_memory_mb=-512)
        assert cfg.gpu_pool_max_memory_mb == -512

    def test_negative_async_log_max_bytes(self):
        """async_log_max_bytes 为负值"""
        cfg = GPUEngineConfig(async_log_max_bytes=-1)
        assert cfg.async_log_max_bytes == -1

    def test_negative_async_log_backup_count(self):
        """async_log_backup_count 为负值"""
        cfg = GPUEngineConfig(async_log_backup_count=-5)
        assert cfg.async_log_backup_count == -5

    # ── 非法 key_generation_strategy 值 ──

    def test_invalid_strategy_string_in_reconstruct(self):
        """reconstruct 时传入无效策略字符串应抛出 ValueError"""
        d = GPUEngineConfig().to_dict()
        d["key_generation_strategy"] = "invalid_strategy"
        with pytest.raises(ValueError):
            _reconstruct_from_dict(d)

    # ── 缺少必需字段 ──

    def test_all_fields_have_defaults(self):
        """所有字段都有默认值，无参构造不应抛出异常"""
        # GPUEngineConfig 是 dataclass，所有字段都有默认值
        cfg = GPUEngineConfig()
        assert cfg.device_index == 1

    def test_empty_dict_reconstruct(self):
        """空 dict 重建后应使用全部默认值"""
        GPUEngineConfig()
        d = {}
        # 空 dict 传给构造函数等同于全默认值
        cfg_default = GPUEngineConfig(**d)
        assert cfg_default.device_index == 1
        assert cfg_default.batch_size is None

    # ── 数据类型边界 ──

    def test_bool_as_device_index(self):
        """device_index 传入 bool（Python 中 bool 是 int 子类）"""
        cfg = GPUEngineConfig(device_index=True)  # type: ignore
        # Python 中 True == 1
        assert cfg.device_index == 1

    def test_bool_as_batch_size(self):
        """batch_size 传入 bool"""
        cfg = GPUEngineConfig(batch_size=False)  # type: ignore
        assert cfg.batch_size == 0

    def test_float_as_batch_size_int(self):
        """batch_size 传入浮点数（可转为 int 的值）"""
        cfg = GPUEngineConfig(batch_size=65536.0)  # type: ignore
        assert cfg.batch_size == 65536

    def test_large_string_as_log_file(self):
        """async_log_file 传入超长字符串"""
        long_path = "x" * 4096
        cfg = GPUEngineConfig(async_log_file=long_path)
        assert cfg.async_log_file == long_path


# ============================================================================
# 配置组合场景
# ============================================================================


@pytest.mark.unit
class TestGPUEngineConfigScenarios:
    """GPUEngineConfig 典型使用场景测试"""

    def test_high_throughput_config(self):
        """高吞吐量场景：大批次 + 大内存池 + 无日志"""
        cfg = GPUEngineConfig(
            batch_size=524288,
            gpu_pool_max_memory_mb=4096,
            gpu_pool_max_buffers=500,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
            use_async_logging=False,
        )
        assert cfg.batch_size == 524288
        assert cfg.gpu_pool_max_memory_mb == 4096
        assert cfg.data_logging_enabled is False

    def test_debug_config(self):
        """调试场景：小批次 + 详细日志 + 异步日志开启"""
        cfg = GPUEngineConfig(
            batch_size=256,
            data_logging_enabled=True,
            data_logging_interval=1,
            use_enhanced_monitoring=True,
            use_async_logging=True,
            async_log_file="logs/debug.log",
            async_log_max_bytes=1024 * 1024,
            async_log_backup_count=3,
        )
        assert cfg.batch_size == 256
        assert cfg.data_logging_interval == 1
        assert cfg.use_async_logging is True
        assert cfg.async_log_file == "logs/debug.log"

    def test_checkpoint_heavy_config(self):
        """频繁检查点场景：启用 checkpoint + 短间隔 + 去重"""
        cfg = GPUEngineConfig(
            checkpoint_enabled=True,
            checkpoint_interval=5,
            dedup_enabled=True,
            dedup_max_size=10_000_000,
        )
        assert cfg.checkpoint_enabled is True
        assert cfg.checkpoint_interval == 5
        assert cfg.dedup_enabled is True
        assert cfg.dedup_max_size == 10_000_000

    def test_minimal_gpu_config(self):
        """最小 GPU 配置：device_index=0 + 自动 batch_size"""
        cfg = GPUEngineConfig(
            device_index=0,
            batch_size=None,
        )
        assert cfg.device_index == 0
        assert cfg.batch_size is None


# ============================================================================
# 不可变性 / 冻结测试（如适用）
# ============================================================================


@pytest.mark.unit
class TestGPUEngineConfigImmutability:
    """GPUEngineConfig 字段可变性测试"""

    def test_fields_are_mutable(self):
        """GPUEngineConfig 不是 frozen dataclass，字段应可修改"""
        cfg = GPUEngineConfig(batch_size=65536)
        cfg.batch_size = 131072  # 应可修改
        assert cfg.batch_size == 131072

    def test_to_dict_returns_new_dict_each_call(self):
        """每次 to_dict() 应返回新的 dict 对象"""
        cfg = GPUEngineConfig()
        d1 = cfg.to_dict()
        d2 = cfg.to_dict()
        assert d1 is not d2  # 不同对象
        assert d1 == d2  # 但内容相同


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
