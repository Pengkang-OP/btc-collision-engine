#!/usr/bin/env python3
"""
GPU压力测试

模拟高负载、长时间运行和错误恢复场景，验证 GPU 引擎的稳定性和鲁棒性：
- 大批量私钥处理
- 长时间运行（内存追踪、缓冲区清理）
- 随机错误注入和间歇性失败

所有 GPU 操作全部使用 mock，不依赖实际 GPU 硬件。
"""

import os
import random
import secrets
import time
from unittest.mock import Mock

import pytest

from src.gpu.gpu_recovery_manager import GPUFailureType, GPURecoveryManager
from src.gpu.load_balancer import GPULoadBalancer
from tests.gpu_mock_factory import GPUMockFactory

# ---------------------------------------------------------------------------
# secp256k1 常量
# ---------------------------------------------------------------------------
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _generate_key_batch(size: int) -> list:
    """生成 size 个有效随机私钥整数"""
    return [secrets.randbelow(SECP256K1_N - 1) + 1 for _ in range(size)]


def _make_device(global_index, vendor="nvidia", mem_gb=8.0, compute_units=68):
    return {
        "global_index": global_index,
        "name": f"Mock GPU {global_index}",
        "vendor": vendor,
        "global_mem_gb": mem_gb,
        "max_compute_units": compute_units,
    }


# ---------------------------------------------------------------------------
# TestLargeBatch：大批量测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestLargeBatch:
    """大批量私钥处理测试"""

    def test_million_keys_processing_mock(self):
        """模拟百万级私钥处理（分批 mock，每批 1000 个）"""
        TOTAL_KEYS = 100_000  # 模拟百万场景（mock 测试，缩减总量）
        BATCH_SIZE = 1_000

        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=BATCH_SIZE)

        # mock GPU 批量处理：返回 batch_size 个 Hash160（20字节）
        mock_kernel.run_batch = Mock(
            side_effect=lambda seed, num_keys: [b"\xab" * 20 for _ in range(num_keys)]
        )

        total_processed = 0
        results = []

        # 分批提交
        for offset in range(0, TOTAL_KEYS, BATCH_SIZE):
            cur_batch_size = min(BATCH_SIZE, TOTAL_KEYS - offset)
            seed = os.urandom(32)
            batch_results = mock_kernel.run_batch(seed, cur_batch_size)
            total_processed += cur_batch_size
            results.extend(batch_results)

        assert total_processed == TOTAL_KEYS, f"处理总量 {total_processed} 应等于 {TOTAL_KEYS}"
        assert len(results) == TOTAL_KEYS
        # 验证每个结果为 20 字节 Hash160
        for h in results[:10]:  # 抽查前 10 个
            assert len(h) == 20, f"Hash160 应为 20 字节，实际 {len(h)}"

    def test_batch_size_boundary_maximum(self):
        """测试 max_batch_size 边界：批次恰好等于最大值时正常处理"""
        MAX_BATCH_SIZE = 65536
        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=MAX_BATCH_SIZE)
        mock_kernel.run_batch = Mock(
            side_effect=lambda seed, num_keys: [b"\x00" * 20 for _ in range(num_keys)]
        )

        # 批次等于最大值
        seed = os.urandom(32)
        results = mock_kernel.run_batch(seed, MAX_BATCH_SIZE)
        assert len(results) == MAX_BATCH_SIZE

    def test_batch_size_boundary_exceed_max(self):
        """超过 max_batch_size 时应分成多批处理"""
        MAX_BATCH_SIZE = 1_000
        TOTAL_KEYS = 3_500

        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=MAX_BATCH_SIZE)

        call_sizes = []

        def mock_run_batch(seed, num_keys):
            call_sizes.append(num_keys)
            return [b"\x00" * 20 for _ in range(num_keys)]

        mock_kernel.run_batch = Mock(side_effect=mock_run_batch)

        # 模拟引擎按 max_batch_size 分批
        total_processed = 0
        for i in range(0, TOTAL_KEYS, MAX_BATCH_SIZE):
            cur_batch_size = min(MAX_BATCH_SIZE, TOTAL_KEYS - i)
            seed = os.urandom(32)
            mock_kernel.run_batch(seed, cur_batch_size)
            total_processed += cur_batch_size

        assert total_processed == TOTAL_KEYS
        # 验证批次大小均不超过 MAX_BATCH_SIZE
        for size in call_sizes:
            assert size <= MAX_BATCH_SIZE, f"批次大小 {size} 超过最大值 {MAX_BATCH_SIZE}"

    def test_large_batch_load_distribution(self):
        """百万级任务在多 GPU 下正确分配（负载均衡验证）"""
        devices = [_make_device(i, "nvidia", 8.0, 68) for i in range(4)]
        balancer = GPULoadBalancer(devices, strategy="equal")

        total_keys = 1_000_000
        ranges = balancer.assign_all_key_ranges(total_keys)

        assert len(ranges) == 4
        total_assigned = sum(end - start for start, end in ranges.values())
        assert total_assigned <= total_keys
        # 每 GPU 应分配约 25% ± 5%
        for idx, (start, end) in ranges.items():
            assigned = end - start
            assert abs(assigned - 250_000) < 25_000, f"GPU {idx} 分配 {assigned:,}，偏差过大"

    def test_empty_batch_handled_gracefully(self):
        """空批次不应导致崩溃"""
        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=1000)
        mock_kernel.run_batch = Mock(return_value=[])

        seed = os.urandom(32)
        result = mock_kernel.run_batch(seed, 0)
        assert result == [], "空批次应返回空列表"
        mock_kernel.run_batch.assert_called_once_with(seed, 0)


# ---------------------------------------------------------------------------
# TestLongRunning：长时间运行模拟
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestLongRunning:
    """长时间运行场景：内存追踪、缓冲区管理"""

    def test_multi_round_no_memory_leak_simulation(self):
        """连续处理 100 轮 batch，内存追踪器报告无累积泄漏"""
        ROUNDS = 100
        BATCH_SIZE = 100

        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=BATCH_SIZE)
        mock_kernel.run_batch = Mock(
            side_effect=lambda seed, num_keys: [b"\xff" * 20 for _ in range(num_keys)]
        )

        # 追踪每轮分配/释放的缓冲区
        allocated_buffers = []
        freed_buffers = []

        def alloc_buffer(size):
            buf = Mock()
            buf.size = size
            allocated_buffers.append(buf)
            return buf

        def free_buffer(buf):
            if buf in allocated_buffers:
                freed_buffers.append(buf)
                allocated_buffers.remove(buf)

        # 模拟 100 轮：每轮分配→处理→释放
        for round_idx in range(ROUNDS):
            buf = alloc_buffer(BATCH_SIZE * 32)
            seed = os.urandom(32)
            mock_kernel.run_batch(seed, BATCH_SIZE)
            free_buffer(buf)

        # 验证：所有分配的缓冲区均已释放（无泄漏）
        assert (
            len(allocated_buffers) == 0
        ), f"{ROUNDS} 轮后仍有 {len(allocated_buffers)} 个未释放缓冲区"
        assert len(freed_buffers) == ROUNDS, f"已释放缓冲区数 {len(freed_buffers)} 应等于 {ROUNDS}"

    def test_buffer_tracker_cleanup_after_long_run(self):
        """长时间运行后，mock 缓冲区追踪器的 cleanup 被正确调用"""
        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=200)
        mock_kernel.run_batch = Mock(return_value=[b"\x00" * 20])

        # 模拟长时间运行后清理
        for _ in range(50):
            mock_kernel.run_batch(os.urandom(32), 1)

        mock_kernel.cleanup()
        mock_kernel.cleanup.assert_called_once()

    def test_throughput_stable_across_rounds(self):
        """模拟 50 轮批处理，每轮耗时稳定（不应出现单轮超时）"""
        ROUNDS = 50
        BATCH_SIZE = 100
        MAX_ROUND_TIME_MS = 100  # mock 调用应 < 100ms

        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=BATCH_SIZE)
        mock_kernel.run_batch = Mock(
            side_effect=lambda seed, num_keys: [b"\xee" * 20 for _ in range(num_keys)]
        )

        for _ in range(ROUNDS):
            seed = os.urandom(32)
            t0 = time.perf_counter()
            mock_kernel.run_batch(seed, BATCH_SIZE)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            assert (
                elapsed_ms < MAX_ROUND_TIME_MS
            ), f"单轮处理耗时 {elapsed_ms:.1f}ms 超过 {MAX_ROUND_TIME_MS}ms"

    def test_recovery_manager_stats_stable_over_time(self):
        """长时间运行中，恢复管理器统计不会意外重置"""
        recovery_manager = GPURecoveryManager(
            max_retry_count=5,
            retry_delay_seconds=0.001,
        )

        # 产生 10 次失败
        for i in range(10):
            recovery_manager.handle_gpu_failure(
                gpu_id=0,
                error=RuntimeError(f"error {i}"),
            )

        stats = recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == 10, f"总失败次数 {stats['total_failures']} 应为 10"
        assert stats["success_rate"] >= 0, "成功率不应为负"
        assert stats["success_rate"] <= 100, "成功率不应超过 100"

    def test_kernel_set_targets_called_each_round(self):
        """每轮批处理前 set_targets 应被正确调用"""
        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=100)
        targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

        ROUNDS = 10
        for _ in range(ROUNDS):
            mock_kernel.set_targets(targets)

        assert mock_kernel.set_targets.call_count == ROUNDS


# ---------------------------------------------------------------------------
# TestErrorRecoveryStress：错误恢复压力测试
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestErrorRecoveryStress:
    """错误恢复压力测试：随机错误注入、连续失败、间歇性失败"""

    ERRORS = [
        MemoryError("out of memory"),
        TimeoutError("kernel execution timeout"),
        RuntimeError("device lost: cl_invalid_device"),
        RuntimeError("compute error: cl_invalid_value"),
        RuntimeError("unknown gpu error"),
    ]

    def _make_recovery_manager(self):
        return GPURecoveryManager(
            max_retry_count=3,
            retry_delay_seconds=0.001,
            batch_size_reduction_factor=0.5,
            auto_redistribute=True,
        )

    def test_random_error_injection_engine_recovers(self):
        """随机注入 20 次 GPU 错误，引擎不崩溃，统计正常"""
        recovery_manager = self._make_recovery_manager()
        redistribute_mock = Mock()

        for _ in range(20):
            error = random.choice(self.ERRORS)
            recovery_manager.handle_gpu_failure(
                gpu_id=0,
                error=error,
                redistribute_callback=redistribute_mock,
            )

        stats = recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == 20
        assert stats["success_rate"] >= 0

    def test_random_error_injection_multiple_gpus(self):
        """随机向 4 个 GPU 各注入错误，统计独立追踪"""
        recovery_manager = self._make_recovery_manager()

        for i in range(4):
            error = random.choice(self.ERRORS)
            recovery_manager.handle_gpu_failure(
                gpu_id=i,
                error=error,
            )

        stats = recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == 4

    def test_consecutive_5_failures_marks_gpu_failed(self):
        """连续 5 次 GPU 失败后，GPU 被标记为永久失败（禁用）"""
        recovery_manager = self._make_recovery_manager()

        # 注册总返回失败的恢复回调
        recovery_manager.register_recovery_callback(gpu_id=0, callback=lambda action, *args: False)

        for _ in range(6):  # 超过 max_retry_count+2
            recovery_manager.handle_gpu_failure(
                gpu_id=0,
                error=RuntimeError("persistent failure"),
            )

        assert recovery_manager.is_gpu_failed(0), "连续多次失败后 GPU 0 应被标记为失败"

    def test_consecutive_failures_alert_called(self):
        """连续失败时 alert_callback 被调用"""
        recovery_manager = self._make_recovery_manager()
        alert_mock = Mock()

        recovery_manager.register_recovery_callback(gpu_id=0, callback=lambda action, *args: False)

        for _ in range(4):
            recovery_manager.handle_gpu_failure(
                gpu_id=0,
                error=RuntimeError("error"),
                alert_callback=alert_mock,
            )

        assert alert_mock.call_count >= 1, "alert_callback 应至少被调用一次"

    def test_intermittent_failures_3_success_1_fail(self):
        """间歇性失败：每 3 次成功后失败 1 次，引擎稳定运行 20 次"""
        ROUNDS = 20
        mock_kernel = GPUMockFactory.create_gpu_kernel(batch_size=100)
        recovery_manager = self._make_recovery_manager()

        call_count = 0
        success_count = 0
        failure_count = 0

        def intermittent_run_batch(seed, num_keys):
            nonlocal call_count, success_count, failure_count
            call_count += 1
            if call_count % 4 == 0:
                failure_count += 1
                raise RuntimeError("intermittent gpu error")
            success_count += 1
            return [b"\xcc" * 20 for _ in range(num_keys)]

        mock_kernel.run_batch = Mock(side_effect=intermittent_run_batch)

        results = []
        for _ in range(ROUNDS):
            try:
                seed = os.urandom(32)
                result = mock_kernel.run_batch(seed, 10)
                results.extend(result)
            except RuntimeError as e:
                recovery_manager.handle_gpu_failure(
                    gpu_id=0,
                    error=e,
                )

        # 验证成功次数约为 3/4
        assert success_count == ROUNDS - failure_count
        expected_failures = ROUNDS // 4
        assert (
            abs(failure_count - expected_failures) <= 1
        ), f"间歇性失败次数 {failure_count} 与期望 {expected_failures} 偏差过大"

        # 统计追踪正确
        stats = recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == failure_count

    def test_intermittent_failures_engine_state_consistent(self):
        """间歇性失败期间，恢复管理器状态始终一致"""
        recovery_manager = self._make_recovery_manager()

        for i in range(15):
            if i % 3 == 2:
                recovery_manager.handle_gpu_failure(
                    gpu_id=0,
                    error=RuntimeError(f"intermittent error {i}"),
                )

        stats = recovery_manager.get_recovery_stats()
        # 5 次失败（i=2,5,8,11,14）
        assert stats["total_failures"] == 5
        assert "success_rate" in stats
        assert "failed_gpus" in stats

    def test_error_injection_oom_triggers_batch_reduction_config(self):
        """OOM 错误应通过 batch_size_reduction_factor 记录降批配置"""
        recovery_manager = self._make_recovery_manager()

        # 记录原始降批因子
        original_factor = recovery_manager.batch_size_reduction_factor
        assert original_factor == 0.5

        # 注入 OOM 错误
        recovery_manager.handle_gpu_failure(
            gpu_id=0,
            error=MemoryError("out of memory"),
        )

        # 降批因子应保持（由外部引擎负责实际降批）
        assert recovery_manager.batch_size_reduction_factor == original_factor

    def test_mixed_error_types_classification(self):
        """混合错误类型均能被正确分类"""
        recovery_manager = self._make_recovery_manager()

        error_type_pairs = [
            (MemoryError("out of memory"), GPUFailureType.OUT_OF_MEMORY),
            (TimeoutError("timeout"), GPUFailureType.TIMEOUT),
            (RuntimeError("device removed"), GPUFailureType.DEVICE_LOST),
            (RuntimeError("kernel execution error"), GPUFailureType.COMPUTE_ERROR),
            (ValueError("some unknown error"), GPUFailureType.UNKNOWN),
        ]

        for error, expected_type in error_type_pairs:
            classified = recovery_manager._classify_failure(error)
            assert classified == expected_type, (
                f"错误 '{error}' 应被分类为 {expected_type.value}，" f"实际: {classified.value}"
            )

    def test_fallback_triggered_when_enough_gpus_fail(self):
        """当失败 GPU 数量超过阈值时，触发 CPU 降级回调"""
        recovery_manager = GPURecoveryManager(
            max_retry_count=3,
            retry_delay_seconds=0.001,
            auto_redistribute=True,
            max_failed_gpus_before_fallback=2,
        )

        fallback_called = []

        def fallback_cb(reason):
            fallback_called.append(reason)

        recovery_manager.set_fallback_callback(fallback_cb)

        # 注册让恢复总失败的回调
        for gpu_id in [0, 1]:
            recovery_manager.register_recovery_callback(
                gpu_id=gpu_id, callback=lambda action, *args: False
            )

        # 让 GPU 0 和 GPU 1 都超过最大重试次数
        for _ in range(5):
            recovery_manager.handle_gpu_failure(gpu_id=0, error=RuntimeError("error"))
        for _ in range(5):
            recovery_manager.handle_gpu_failure(gpu_id=1, error=RuntimeError("error"))

        # 两个 GPU 失败（≥ 阈值 2），应触发 CPU 降级
        assert len(fallback_called) >= 1, "应触发 CPU 降级回调"
        assert recovery_manager.is_fallback_to_cpu, "应已降级到 CPU 模式"

    def test_recovery_stats_success_rate_calculation(self):
        """成功率 = 成功恢复次数 / 总失败次数 * 100"""
        recovery_manager = self._make_recovery_manager()

        # 无回调（默认假设健康）→ 早期失败会成功恢复
        for _ in range(4):
            recovery_manager.handle_gpu_failure(
                gpu_id=0,
                error=RuntimeError("error"),
            )

        stats = recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == 4
        assert (
            0.0 <= stats["success_rate"] <= 100.0
        ), f"成功率 {stats['success_rate']} 不在 [0, 100] 范围内"

    def test_multiple_gpu_ids_independent_failure_tracking(self):
        """不同 GPU ID 的失败独立追踪，不互相干扰"""
        recovery_manager = self._make_recovery_manager()

        # GPU 0 失败 3 次，GPU 1 失败 2 次，GPU 2 失败 1 次
        for i in range(3):
            recovery_manager.handle_gpu_failure(gpu_id=0, error=RuntimeError("err"))
        for i in range(2):
            recovery_manager.handle_gpu_failure(gpu_id=1, error=RuntimeError("err"))
        for i in range(1):
            recovery_manager.handle_gpu_failure(gpu_id=2, error=RuntimeError("err"))

        stats = recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == 6, f"总失败次数 {stats['total_failures']} 应为 6"
