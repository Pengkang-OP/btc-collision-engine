#!/usr/bin/env python3
"""GPU异步执行器 (AsyncGPUExecutor) 单元测试.

覆盖：
- _seed_bytes_to_u32_be_array 种子转换
- GPU_SPECIFIC_CONFIG 配置完整性
- _PendingBatch 数据类
- AsyncGPUExecutor 初始化与GPU型号检测
- _detect_gpu_model / _get_gpu_config
- _is_buffer_valid 缓冲区有效性检查
- prefetch_next_batch 预取
- flush_pending 结果回收
- get_stats 统计信息
- cleanup 资源释放
"""

from unittest.mock import MagicMock, Mock

import numpy as np
import pytest

# ============================================================================
# _seed_bytes_to_u32_be_array 测试
# ============================================================================


@pytest.mark.unit
class TestSeedBytesToU32:
    """种子字节转换测试."""

    def test_valid_32_byte_seed(self):
        from src.gpu.async_executor import _seed_bytes_to_u32_be_array

        seed = bytes(range(32))
        result = _seed_bytes_to_u32_be_array(seed)
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.uint32
        assert len(result) == 8

    def test_invalid_length_raises(self):
        import pytest as pt

        from src.gpu.async_executor import _seed_bytes_to_u32_be_array

        with pt.raises(ValueError, match="32 bytes"):
            _seed_bytes_to_u32_be_array(b"short")

    def test_empty_seed_raises(self):
        import pytest as pt

        from src.gpu.async_executor import _seed_bytes_to_u32_be_array

        with pt.raises(ValueError, match="32 bytes"):
            _seed_bytes_to_u32_be_array(b"")

    def test_33_byte_seed_raises(self):
        import pytest as pt

        from src.gpu.async_executor import _seed_bytes_to_u32_be_array

        with pt.raises(ValueError, match="32 bytes"):
            _seed_bytes_to_u32_be_array(b"x" * 33)

    def test_all_zeros_seed(self):
        from src.gpu.async_executor import _seed_bytes_to_u32_be_array

        seed = b"\x00" * 32
        result = _seed_bytes_to_u32_be_array(seed)
        assert np.all(result == 0)

    def test_endianness_conversion(self):
        from src.gpu.async_executor import _seed_bytes_to_u32_be_array

        # 0xDEADBEEF in big-endian
        seed = b"\x00" * 28 + b"\xde\xad\xbe\xef"
        result = _seed_bytes_to_u32_be_array(seed)
        # On little-endian x86, last element should be 0xDEADBEEF as native uint32
        assert result[7] == 0xDEADBEEF


# ============================================================================
# GPU_SPECIFIC_CONFIG 测试
# ============================================================================


@pytest.mark.unit
class TestGpuSpecificConfig:
    """GPU配置完整性测试."""

    REQUIRED_KEYS = ["queue_depth", "initial_batch_size", "max_batch_size", "memory_factor"]

    def test_default_config_exists(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG

        assert "default" in GPU_SPECIFIC_CONFIG

    def test_all_gpu_configs_have_required_keys(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG

        for gpu_model, config in GPU_SPECIFIC_CONFIG.items():
            for key in self.REQUIRED_KEYS:
                assert key in config, f"{gpu_model} missing key: {key}"

    def test_known_gpu_models_exist(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG

        expected_models = [
            "1660",
            "rtx30",
            "rtx40",
            "10",
            "9",
            "amd6000",
            "amd7000",
            "intel",
            "default",
        ]
        for model in expected_models:
            assert model in GPU_SPECIFIC_CONFIG, f"Missing GPU config: {model}"

    def test_all_queue_depths_positive(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG

        for model, config in GPU_SPECIFIC_CONFIG.items():
            assert config["queue_depth"] >= 1, f"{model} queue_depth <= 0"

    def test_all_batch_sizes_positive(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG

        for model, config in GPU_SPECIFIC_CONFIG.items():
            assert config["initial_batch_size"] > 0, f"{model} initial_batch_size <= 0"
            assert config["max_batch_size"] >= config["initial_batch_size"], f"{model} max < initial"

    def test_memory_factors_valid(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG

        for model, config in GPU_SPECIFIC_CONFIG.items():
            assert 0 < config["memory_factor"] <= 1.0, f"{model} invalid memory_factor"

    def test_default_queue_depth_constant(self):
        from src.gpu.async_executor import DEFAULT_QUEUE_DEPTH

        assert DEFAULT_QUEUE_DEPTH == 4


# ============================================================================
# _PendingBatch 测试
# ============================================================================


@pytest.mark.unit
class TestPendingBatch:
    """待处理批次数据类测试."""

    def test_create_pending_batch(self):
        from src.gpu.async_executor import _PendingBatch

        read_event = Mock()
        buf = {"matches": Mock(), "match_flags": np.zeros(10, dtype=np.int32)}
        pb = _PendingBatch(read_event=read_event, buf=buf, num_keys=1000, seed=b"x" * 32)
        assert pb.read_event is read_event
        assert pb.buf is buf
        assert pb.num_keys == 1000
        assert pb.seed == b"x" * 32

    def test_has_slots(self):
        from src.gpu.async_executor import _PendingBatch

        pb = _PendingBatch(Mock(), {}, 0, b"")
        assert hasattr(pb, "read_event")
        assert hasattr(pb, "buf")
        assert hasattr(pb, "num_keys")
        assert hasattr(pb, "seed")


# ============================================================================
# AsyncGPUExecutor 初始化测试
# ============================================================================


@pytest.mark.unit
class TestAsyncExecutorInit:
    """异步执行器初始化测试."""

    def test_init_defaults(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        # No device_info → default model
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        assert executor.queue_depth == 4
        assert executor.sync_fallbacks == 0
        assert executor.async_executions == 0

    def test_init_custom_queue_depth(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144, queue_depth=6)
        assert executor.queue_depth == 6

    def test_init_queue_depth_min_one(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144, queue_depth=0)
        assert executor.queue_depth == 1  # clamped to min 1

    def test_init_uses_gpu_specific_max_batch(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = {"name": "NVIDIA GeForce GTX 1660 SUPER"}
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=10000)
        # Should use GPU specific config max_batch_size (2097152, v5.1.1 4x upgrade) over constructor param
        assert executor.max_batch_size == 2097152

    def test_init_initial_state(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        assert executor.buffer_a == {"matches": None, "match_flags": None}
        assert executor.buffer_b == {"matches": None, "match_flags": None}
        assert executor.precomp_buffer is None
        assert executor.seed_buffer is None
        assert executor.current_buffer == "A"
        assert executor.pending_event is None
        assert executor.is_async_ready is False
        assert executor._prefetch_events == []


# ============================================================================
# _detect_gpu_model 测试
# ============================================================================


@pytest.mark.unit
class TestDetectGpuModel:
    """GPU型号检测测试."""

    def _make_executor_with_name(self, name):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = {"name": name}
        return AsyncGPUExecutor(gpu_device, max_batch_size=262144)

    def test_detect_1660(self):
        executor = self._make_executor_with_name("NVIDIA GeForce GTX 1660")
        assert executor._detect_gpu_model() == "1660"

    def test_detect_rtx40(self):
        executor = self._make_executor_with_name("NVIDIA GeForce RTX 4090")
        assert executor._detect_gpu_model() == "rtx40"

    def test_detect_rtx30(self):
        executor = self._make_executor_with_name("NVIDIA GeForce RTX 3080")
        assert executor._detect_gpu_model() == "rtx30"

    def test_detect_rtx_generic(self):
        executor = self._make_executor_with_name("NVIDIA GeForce RTX 2080")
        assert executor._detect_gpu_model() == "rtx30"  # default RTX → rtx30

    def test_detect_gtx10(self):
        executor = self._make_executor_with_name("NVIDIA GeForce GTX 1080")
        assert executor._detect_gpu_model() == "10"

    def test_detect_gtx9(self):
        executor = self._make_executor_with_name("NVIDIA GeForce GTX 980")
        assert executor._detect_gpu_model() == "9"

    def test_detect_amd_radeon(self):
        executor = self._make_executor_with_name("AMD Radeon RX 6800")
        assert executor._detect_gpu_model() == "amd6000"

    def test_detect_amd_generic(self):
        executor = self._make_executor_with_name("AMD Radeon Pro W5700")
        assert executor._detect_gpu_model() == "amd6000"

    def test_detect_intel_arc(self):
        executor = self._make_executor_with_name("Intel Arc A770")
        assert executor._detect_gpu_model() == "intel"

    def test_detect_intel_iris(self):
        executor = self._make_executor_with_name("Intel Iris Xe Graphics")
        assert executor._detect_gpu_model() == "intel"

    def test_detect_unknown_default(self):
        executor = self._make_executor_with_name("Some Unknown GPU")
        assert executor._detect_gpu_model() == "default"

    def test_detect_no_device_info(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        assert executor._detect_gpu_model() == "default"


# ============================================================================
# _get_gpu_config 测试
# ============================================================================


@pytest.mark.unit
class TestGetGpuConfig:
    """GPU配置获取测试."""

    def test_get_known_model_config(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG, AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        config = executor._get_gpu_config("1660")
        assert config == GPU_SPECIFIC_CONFIG["1660"]

    def test_get_unknown_model_returns_default(self):
        from src.gpu.async_executor import GPU_SPECIFIC_CONFIG, AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        config = executor._get_gpu_config("nonexistent_model")
        assert config == GPU_SPECIFIC_CONFIG["default"]


# ============================================================================
# _is_buffer_valid 测试
# ============================================================================


@pytest.mark.unit
class TestIsBufferValid:
    """缓冲区有效性检查测试."""

    def test_valid_buffers(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor.seed_buffer = MagicMock()
        assert executor._is_buffer_valid() is True

    def test_null_seed_buffer(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor.seed_buffer = None
        assert executor._is_buffer_valid() is False

    def test_null_transfer_queue(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.transfer_queue = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor.seed_buffer = MagicMock()
        assert executor._is_buffer_valid() is False

    def test_no_transfer_queue_attr(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        del gpu_device.transfer_queue  # remove attribute
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor.seed_buffer = MagicMock()
        assert executor._is_buffer_valid() is False


# ============================================================================
# prefetch_next_batch 测试
# ============================================================================


@pytest.mark.unit
class TestPrefetchNextBatch:
    """预取下一批次测试."""

    def test_prefetch_disabled(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor._prefetch_enabled = False
        executor._next_batch_ready = MagicMock()

        executor.prefetch_next_batch(seed=b"x" * 32, num_keys=1000)

        executor._next_batch_ready.set.assert_not_called()

    def test_prefetch_with_valid_seed(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor._next_batch_ready = MagicMock()

        executor.prefetch_next_batch(seed=b"y" * 32, num_keys=5000)

        assert executor._next_batch_data == b"y" * 32
        assert executor._next_batch_size == 5000
        executor._next_batch_ready.set.assert_called_once()

    def test_prefetch_exception_clears_event(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor._next_batch_ready = MagicMock()
        # Make .set() raise to trigger exception path
        executor._next_batch_ready.set.side_effect = RuntimeError("mock error")

        executor.prefetch_next_batch(seed=b"x" * 32, num_keys=5000)

        # Event should be cleared on error
        executor._next_batch_ready.clear.assert_called()


# ============================================================================
# flush_pending 测试
# ============================================================================


@pytest.mark.unit
class TestFlushPending:
    """结果回收测试."""

    def test_flush_empty_queue(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        results = executor.flush_pending()
        assert results == []
        assert executor.pending_event is None
        assert executor._pending_buffer is None

    def test_flush_with_pending_event(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        # Create mock pending batch
        mock_event = MagicMock()
        mock_buf = {
            "match_flags": np.array([0, 0, 1, 0, 2], dtype=np.int32),
        }
        seed = b"s" * 32
        from src.gpu.async_executor import _PendingBatch

        pb = _PendingBatch(read_event=mock_event, buf=mock_buf, num_keys=5, seed=seed)
        executor._prefetch_events.append(pb)
        executor.pending_event = mock_event

        results = executor.flush_pending()

        assert len(results) == 1
        returned_seed, matches = results[0]
        assert returned_seed == seed
        assert len(matches) == 2  # indices 2 and 4
        assert matches[0]["key_index"] == 2
        assert matches[0]["target_index"] == 0  # int(1 - 1)
        assert matches[1]["key_index"] == 4
        assert matches[1]["target_index"] == 1  # int(2 - 1)


# ============================================================================
# get_stats 测试
# ============================================================================


@pytest.mark.unit
class TestGetStats:
    """统计信息测试."""

    def test_get_stats_initial(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        stats = executor.get_stats()
        assert stats["async_executions"] == 0
        assert stats["sync_fallbacks"] == 0
        assert stats["total_executions"] == 0
        assert stats["async_rate_percent"] == 0
        assert stats["queue_depth"] == 4

    def test_get_stats_after_executions(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        executor.async_executions = 80
        executor.sync_fallbacks = 20
        executor.queue_depth_hits = 50

        stats = executor.get_stats()
        assert stats["async_executions"] == 80
        assert stats["sync_fallbacks"] == 20
        assert stats["total_executions"] == 100
        assert stats["async_rate_percent"] == 80.0
        assert stats["queue_depth_hits"] == 50

    def test_get_stats_all_keys_present(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        stats = executor.get_stats()
        expected_keys = [
            "async_executions",
            "sync_fallbacks",
            "total_executions",
            "async_rate_percent",
            "prefetch_hits",
            "prefetch_misses",
            "prefetch_rate_percent",
            "queue_depth",
            "queue_depth_hits",
            "current_queue_depth",
        ]
        for key in expected_keys:
            assert key in stats, f"Missing key: {key}"

    def test_get_stats_current_queue_depth(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)
        # _prefetch_events empty → current_queue_depth == 0
        assert executor.get_stats()["current_queue_depth"] == 0


# ============================================================================
# cleanup 测试
# ============================================================================


@pytest.mark.unit
class TestCleanup:
    """资源清理测试."""

    def test_cleanup_no_buffers(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.compute_queue = MagicMock()
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        executor.cleanup()  # Should not crash

        assert executor.seed_buffer is None
        assert executor.precomp_buffer is None
        assert executor.pending_event is None

    def test_cleanup_with_seed_buffer(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.compute_queue = MagicMock()
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        mock_seed_buf = MagicMock()
        # v5.1.1: cleanup() iterates _seed_buffer_pool, not self.seed_buffer directly
        executor._seed_buffer_pool = [mock_seed_buf]

        executor.cleanup()

        mock_seed_buf.release.assert_called_once()
        assert executor.seed_buffer is None
        assert len(executor._seed_buffer_pool) == 0

    def test_cleanup_with_precomp_buffer(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.compute_queue = MagicMock()
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        mock_precomp = MagicMock()
        executor.precomp_buffer = mock_precomp

        executor.cleanup()

        mock_precomp.release.assert_called_once()
        assert executor.precomp_buffer is None

    def test_cleanup_with_pool_buffers(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.compute_queue = MagicMock()
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        mock_buf1 = MagicMock()
        mock_buf2 = MagicMock()
        executor._buffer_pool = [
            {"matches": mock_buf1, "match_flags": np.zeros(10)},
            {"matches": mock_buf2, "match_flags": np.zeros(10)},
        ]

        executor.cleanup()

        mock_buf1.release.assert_called_once()
        mock_buf2.release.assert_called_once()
        assert executor._buffer_pool == []

    def test_cleanup_release_exception_handled(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.compute_queue = MagicMock()
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        mock_buf = MagicMock()
        mock_buf.release.side_effect = RuntimeError("already released")
        executor._buffer_pool = [{"matches": mock_buf, "match_flags": None}]

        executor.cleanup()  # Should not crash

    def test_cleanup_with_pending_event(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        gpu_device = MagicMock()
        gpu_device.device_info = None
        gpu_device.compute_queue = MagicMock()
        gpu_device.transfer_queue = MagicMock()
        executor = AsyncGPUExecutor(gpu_device, max_batch_size=262144)

        mock_event = MagicMock()
        executor.pending_event = mock_event

        executor.cleanup()

        mock_event.wait.assert_called_once()
        assert executor.pending_event is None
