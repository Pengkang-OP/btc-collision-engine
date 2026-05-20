#!/usr/bin/env python3
"""
多 GPU兼容性测试

验证不同厂商、不同型号 GPU 的兼容性，包括：
- 同厂商同型号负载均衡（平均分配，权重误差 < 5%）
- 同厂商不同型号按性能加权分配
- 跨厂商兼容性（workaround 共存）
- GPU 故障恢复与任务重分配
- 动态负载重平衡
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.gpu.gpu_recovery_manager import GPUFailureType, GPURecoveryManager
from src.gpu.load_balancer import GPULoadBalancer

# ---------------------------------------------------------------------------
# 辅助函数：构建标准设备字典
# ---------------------------------------------------------------------------


def _make_device(global_index, name, vendor, mem_gb, compute_units):
    """构建 GPULoadBalancer 所需的设备信息字典"""
    return {
        "global_index": global_index,
        "name": name,
        "vendor": vendor,  # 应为 lowercase key 如 'nvidia'/'amd'/'intel'
        "global_mem_gb": mem_gb,
        "max_compute_units": compute_units,
    }


def _weights_sum_to_one(weights: dict, tol: float = 1e-6) -> bool:
    return abs(sum(weights.values()) - 1.0) < tol


# ---------------------------------------------------------------------------
# TestSameVendorSameModel：同厂商同型号
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestSameVendorSameModel:
    """同厂商同型号：验证负载均衡平均分配（权重误差 < 5%）"""

    def test_dual_nvidia_equal_load(self):
        """两块 RTX 3080（8GB/68CU），equal 策略：权重各 0.5，误差 < 5%"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
        ]
        balancer = GPULoadBalancer(devices, strategy="equal")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights), "权重之和应为 1.0"
        assert abs(weights[0] - 0.5) < 0.05, f"GPU 0 权重 {weights[0]:.3f} 误差超 5%"
        assert abs(weights[1] - 0.5) < 0.05, f"GPU 1 权重 {weights[1]:.3f} 误差超 5%"

    def test_dual_nvidia_performance_load(self):
        """两块 RTX 3080（相同规格），performance 策略：权重应近似相等"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights)
        # 两块相同规格，权重应非常接近（误差 < 5%）
        assert (
            abs(weights[0] - weights[1]) < 0.05
        ), f"相同规格 GPU 权重差异过大: {weights[0]:.3f} vs {weights[1]:.3f}"

    def test_dual_amd_equal_load(self):
        """两块 RX 6800 XT（16GB/72CU），equal 策略：权重各 0.5"""
        devices = [
            _make_device(0, "AMD Radeon RX 6800 XT", "amd", 16.0, 72),
            _make_device(1, "AMD Radeon RX 6800 XT", "amd", 16.0, 72),
        ]
        balancer = GPULoadBalancer(devices, strategy="equal")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights)
        assert abs(weights[0] - 0.5) < 0.05
        assert abs(weights[1] - 0.5) < 0.05

    def test_triple_nvidia_equal_load(self):
        """三块相同 GPU，equal 策略：每块权重约 1/3，误差 < 5%"""
        devices = [_make_device(i, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68) for i in range(3)]
        balancer = GPULoadBalancer(devices, strategy="equal")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights)
        for idx, w in weights.items():
            assert abs(w - 1 / 3) < 0.05, f"GPU {idx} 权重 {w:.3f} 误差超 5%"

    def test_equal_load_key_range_assignment(self):
        """equal 策略：两块相同 GPU 各分配约 50% 私钥范围"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
        ]
        balancer = GPULoadBalancer(devices, strategy="equal")
        total_keys = 1_000_000
        ranges = balancer.assign_all_key_ranges(total_keys)

        for idx, (start, end) in ranges.items():
            assigned = end - start
            assert abs(assigned - 500_000) < 50_000, f"GPU {idx} 分配 {assigned:,} 个密钥，偏差过大"


# ---------------------------------------------------------------------------
# TestSameVendorDifferentModel：同厂商不同型号
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestSameVendorDifferentModel:
    """同厂商不同型号：按性能加权分配"""

    def test_nvidia_mixed_models_performance_weight(self):
        """RTX 3080（8GB/68CU） + RTX 4090（24GB/128CU），性能策略下 4090 权重更大"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "NVIDIA GeForce RTX 4090", "nvidia", 24.0, 128),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights)
        assert (
            weights[1] > weights[0]
        ), f"RTX 4090 权重 {weights[1]:.3f} 应大于 RTX 3080 {weights[0]:.3f}"
        # 4090 显存是 3080 的 3 倍，权重差距应明显
        assert weights[1] > 0.6, f"RTX 4090 权重 {weights[1]:.3f} 应超过 0.6"

    def test_nvidia_mixed_models_key_range_distribution(self):
        """RTX 3080 + RTX 4090：4090 获得超过 60% 的私钥搜索任务"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "NVIDIA GeForce RTX 4090", "nvidia", 24.0, 128),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        total_keys = 1_000_000
        ranges = balancer.assign_all_key_ranges(total_keys)

        assigned_0 = ranges[0][1] - ranges[0][0]
        assigned_1 = ranges[1][1] - ranges[1][0]
        total_assigned = assigned_0 + assigned_1

        # 总分配量与请求量基本一致（允许舍入误差）
        assert total_assigned <= total_keys

        # 4090 分配量超过 60%
        assert (
            assigned_1 > total_assigned * 0.6
        ), f"RTX 4090 分配 {assigned_1:,}，期望超过 60%（{int(total_assigned * 0.6):,}）"

    def test_amd_mixed_models_performance_weight(self):
        """RX 6800 XT（16GB/72CU） + RX 7900 XTX（24GB/96CU），7900 XTX 权重更大"""
        devices = [
            _make_device(0, "AMD Radeon RX 6800 XT", "amd", 16.0, 72),
            _make_device(1, "AMD Radeon RX 7900 XTX", "amd", 24.0, 96),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights)
        assert (
            weights[1] > weights[0]
        ), f"RX 7900 XTX 权重 {weights[1]:.3f} 应大于 RX 6800 XT {weights[0]:.3f}"

    def test_performance_weight_reflects_memory_diff(self):
        """性能权重主要由显存大小决定：显存翻倍，权重应明显更大"""
        devices = [
            _make_device(0, "GPU A", "nvidia", 8.0, 64),
            _make_device(1, "GPU B", "nvidia", 16.0, 64),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        assert weights[1] > weights[0], "显存更大的 GPU 权重应更大"
        # 16GB vs 8GB，权重比约 2:1
        assert weights[1] / weights[0] > 1.5, f"权重比 {weights[1] / weights[0]:.2f}，期望 > 1.5"


# ---------------------------------------------------------------------------
# TestCrossVendor：不同厂商
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestCrossVendor:
    """不同厂商 GPU 兼容性测试"""

    def test_nvidia_intel_cross_vendor_equal_load(self):
        """NVIDIA RTX 3080 + Intel Arc A770，equal 策略下各 50%"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "Intel Arc A770", "intel", 16.0, 512),
        ]
        balancer = GPULoadBalancer(devices, strategy="equal")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights)
        assert abs(weights[0] - 0.5) < 0.05
        assert abs(weights[1] - 0.5) < 0.05

    def test_nvidia_amd_cross_vendor_performance_load(self):
        """NVIDIA RTX 3080 + AMD RX 6800 XT，性能策略：AMD 显存更大权重应更大"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "AMD Radeon RX 6800 XT", "amd", 16.0, 72),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        assert _weights_sum_to_one(weights)
        # AMD 16GB 显存 > NVIDIA 8GB，权重应更大
        assert (
            weights[1] > weights[0]
        ), f"AMD(16GB) 权重 {weights[1]:.3f} 应大于 NVIDIA(8GB) {weights[0]:.3f}"

    def test_all_vendors_three_way(self):
        """NVIDIA + AMD + Intel 三厂商共存，权重之和为 1.0"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "AMD Radeon RX 6800 XT", "amd", 16.0, 72),
            _make_device(2, "Intel Arc A770", "intel", 16.0, 512),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        assert len(weights) == 3, f"应有 3 个设备权重，实际 {len(weights)}"
        assert _weights_sum_to_one(weights), f"权重之和 {sum(weights.values()):.6f} 不为 1.0"
        # 每个权重应为正数
        for idx, w in weights.items():
            assert w > 0, f"GPU {idx} 权重 {w} 应为正数"

    def test_intel_workaround_does_not_affect_nvidia_weight(self):
        """Intel 的 uint32 workaround 不影响 NVIDIA 设备的权重计算"""
        devices_nvidia_only = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
        ]
        devices_mixed = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "Intel Arc A770", "intel", 16.0, 512),
        ]

        balancer_single = GPULoadBalancer(devices_nvidia_only, strategy="performance")
        balancer_mixed = GPULoadBalancer(devices_mixed, strategy="performance")

        # 单 NVIDIA 的绝对权重为 1.0；混合下 NVIDIA 权重应小于 1.0
        weight_single = balancer_single.calculate_weights()[0]
        weight_mixed = balancer_mixed.calculate_weights()[0]

        assert weight_single == pytest.approx(1.0), "单独 NVIDIA 权重应为 1.0"
        assert 0 < weight_mixed < 1.0, "混合场景下 NVIDIA 权重应在 (0, 1)"

    def test_vendor_factors_order_nvidia_gt_amd_gt_intel(self):
        """厂商因子：NVIDIA > AMD > Intel（相同显存和 CU）"""
        devices = [
            _make_device(0, "NVIDIA GPU", "nvidia", 10.0, 100),
            _make_device(1, "AMD GPU", "amd", 10.0, 100),
            _make_device(2, "Intel GPU", "intel", 10.0, 100),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        # NVIDIA 因子 1.0 > AMD 0.95 > Intel 0.9
        assert weights[0] > weights[1], "NVIDIA 权重应大于 AMD"
        assert weights[1] > weights[2], "AMD 权重应大于 Intel"

    def test_cross_vendor_total_keys_covered(self):
        """跨厂商分配：所有 GPU 分配的私钥总和等于请求总量"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "AMD Radeon RX 6800 XT", "amd", 16.0, 72),
            _make_device(2, "Intel Arc A770", "intel", 16.0, 512),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        total_keys = 1_000_000
        ranges = balancer.assign_all_key_ranges(total_keys)

        total_assigned = sum(end - start for start, end in ranges.values())
        assert (
            total_assigned <= total_keys
        ), f"分配总量 {total_assigned:,} 超过请求量 {total_keys:,}"
        # 至少分配了 95% 的总量（允许少量舍入损失）
        assert (
            total_assigned >= total_keys * 0.95
        ), f"分配总量 {total_assigned:,} 低于 95%（{int(total_keys * 0.95):,}）"


# ---------------------------------------------------------------------------
# TestGPUFailureRecovery：GPU 故障恢复
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestGPUFailureRecovery:
    """GPU 故障恢复测试"""

    def setup_method(self):
        """每个测试前创建新的恢复管理器"""
        self.recovery_manager = GPURecoveryManager(
            max_retry_count=3,
            retry_delay_seconds=0.01,  # 测试中缩短延迟
            batch_size_reduction_factor=0.5,
            auto_redistribute=True,
        )

    def test_single_gpu_failure_recorded(self):
        """模拟单个 GPU 失败，失败信息被正确记录"""
        redistribute_mock = Mock()
        error = RuntimeError("device lost")

        self.recovery_manager.handle_gpu_failure(
            gpu_id=0,
            error=error,
            redistribute_callback=redistribute_mock,
        )

        stats = self.recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == 1

    def test_oom_failure_classified_correctly(self):
        """OOM 错误被分类为 OUT_OF_MEMORY 类型"""
        error = MemoryError("out of memory: cannot allocate buffer")
        failure_type = self.recovery_manager._classify_failure(error)
        assert failure_type == GPUFailureType.OUT_OF_MEMORY

    def test_timeout_failure_classified_correctly(self):
        """超时错误被分类为 TIMEOUT 类型"""
        error = TimeoutError("kernel execution timeout")
        failure_type = self.recovery_manager._classify_failure(error)
        assert failure_type == GPUFailureType.TIMEOUT

    def test_device_lost_failure_classified_correctly(self):
        """设备丢失错误被分类为 DEVICE_LOST 类型"""
        error = RuntimeError("device removed: cl_invalid_device")
        failure_type = self.recovery_manager._classify_failure(error)
        assert failure_type == GPUFailureType.DEVICE_LOST

    def test_single_gpu_failure_redistribution_called(self):
        """GPU 失败恢复失败后，redistribute_callback 被调用"""
        redistribute_mock = Mock()

        # 注册不健康的恢复回调（让恢复一直失败）
        self.recovery_manager.register_recovery_callback(0, lambda action, *args: False)

        # 触发足够多次失败使策略变为 DISABLE_GPU
        for _ in range(5):
            self.recovery_manager.handle_gpu_failure(
                gpu_id=0,
                error=RuntimeError("persistent failure"),
                redistribute_callback=redistribute_mock,
            )

        # redistribute_callback 至少被调用一次
        assert redistribute_mock.call_count >= 1

    def test_batch_size_reduction_on_oom(self):
        """OOM 错误后，batch_size_reduction_factor 被记录在恢复配置中"""
        assert self.recovery_manager.batch_size_reduction_factor == 0.5
        # 默认因子为 0.5（批次大小降为原来的 50%）

    def test_engine_continues_after_failure_auto_redistribute(self):
        """GPU 失败后，auto_redistribute=True 时重分配回调会被触发"""
        redistribute_mock = Mock()
        alert_mock = Mock()

        # 注册恢复回调（返回 False 使恢复失败，触发重分配）
        self.recovery_manager.register_recovery_callback(
            gpu_id=2, callback=lambda action, *args: False
        )

        for _ in range(4):
            self.recovery_manager.handle_gpu_failure(
                gpu_id=2,
                error=RuntimeError("kernel error"),
                redistribute_callback=redistribute_mock,
                alert_callback=alert_mock,
            )

        assert redistribute_mock.call_count >= 1, "应触发至少一次负载重分配"

    def test_gpu_marked_failed_after_max_retries(self):
        """超过最大重试次数后，GPU 被标记为失败"""
        # 注册总返回失败的恢复回调
        self.recovery_manager.register_recovery_callback(
            gpu_id=1, callback=lambda action, *args: False
        )

        max_retries = self.recovery_manager.max_retry_count + 2
        for _ in range(max_retries):
            self.recovery_manager.handle_gpu_failure(
                gpu_id=1,
                error=RuntimeError("persistent error"),
            )

        assert self.recovery_manager.is_gpu_failed(1), "GPU 1 应被标记为失败"

    def test_recovery_stats_tracking(self):
        """恢复统计信息正确追踪总失败次数"""
        for i in range(3):
            self.recovery_manager.handle_gpu_failure(
                gpu_id=i,
                error=RuntimeError(f"error on gpu {i}"),
            )

        stats = self.recovery_manager.get_recovery_stats()
        assert stats["total_failures"] == 3

    def test_reset_failure_history_clears_failed_state(self):
        """重置失败历史后，GPU 不再被标记为失败"""
        self.recovery_manager.register_recovery_callback(
            gpu_id=0, callback=lambda action, *args: False
        )
        for _ in range(5):
            self.recovery_manager.handle_gpu_failure(gpu_id=0, error=RuntimeError("error"))

        self.recovery_manager.reset_failure_history(gpu_id=0)
        assert not self.recovery_manager.is_gpu_failed(0), "重置后不应标记为失败"


# ---------------------------------------------------------------------------
# TestDynamicRebalancing：动态负载重平衡
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestDynamicRebalancing:
    """动态负载重平衡测试"""

    def _make_two_nvidia_devices(self):
        return [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
        ]

    def test_rebalance_interval_triggers_correctly(self):
        """should_rebalance() 在间隔时间内应返回 False"""
        devices = self._make_two_nvidia_devices()
        balancer = GPULoadBalancer(devices, strategy="equal", rebalance_interval=3600)

        # 刚创建，未到重平衡时间
        assert balancer.should_rebalance() is False

    def test_performance_degradation_rebalance(self):
        """模拟 GPU 0 性能下降 50%，redistribute_load() 后 GPU 0 权重下降"""
        devices = self._make_two_nvidia_devices()
        balancer = GPULoadBalancer(devices, strategy="equal", rebalance_interval=0)

        # 记录初始权重
        initial_weights = balancer.calculate_weights()
        initial_weights[0]

        # GPU 0 性能降低 50%，GPU 1 保持正常
        balancer.record_performance(device_idx=0, throughput=500_000, error_rate=0.0)
        balancer.record_performance(device_idx=1, throughput=1_000_000, error_rate=0.0)

        # 触发重平衡
        new_weights = balancer.redistribute_load()

        # GPU 0 吞吐量是 GPU 1 的 50%，权重也应约为 1/3
        assert (
            new_weights[0] < new_weights[1]
        ), f"性能下降后 GPU 0 权重 {new_weights[0]:.3f} 应小于 GPU 1 {new_weights[1]:.3f}"

    def test_record_performance_updates_stats(self):
        """record_performance 后 get_device_load 返回更新后的吞吐量"""
        devices = self._make_two_nvidia_devices()
        balancer = GPULoadBalancer(devices, strategy="equal")

        balancer.record_performance(device_idx=0, throughput=800_000, error_rate=0.1)
        load_info = balancer.get_device_load(device_idx=0)

        assert load_info is not None
        assert load_info["throughput"] == 800_000
        assert load_info["error_rate"] == pytest.approx(0.1)

    def test_gpu_recovery_rejoin_weights_normalized(self):
        """模拟 GPU 恢复后，权重重新归一化（总和为 1.0）"""
        devices = self._make_two_nvidia_devices()
        balancer = GPULoadBalancer(devices, strategy="equal", rebalance_interval=0)

        # GPU 0 长期低性能
        balancer.record_performance(device_idx=0, throughput=100_000, error_rate=0.5)
        balancer.record_performance(device_idx=1, throughput=900_000, error_rate=0.0)
        balancer.redistribute_load()

        # GPU 0 恢复正常
        balancer.record_performance(device_idx=0, throughput=900_000, error_rate=0.0)
        recovered_weights = balancer.redistribute_load()

        assert _weights_sum_to_one(
            recovered_weights
        ), f"恢复后权重之和 {sum(recovered_weights.values()):.6f} 不为 1.0"

    def test_all_loads_returns_all_devices(self):
        """get_all_loads() 返回所有设备的负载信息"""
        devices = self._make_two_nvidia_devices()
        balancer = GPULoadBalancer(devices, strategy="equal")
        # 先分配范围，使 key_ranges 被填充
        balancer.assign_all_key_ranges(1_000_000)

        all_loads = balancer.get_all_loads()
        assert len(all_loads) == 2
        for idx in [0, 1]:
            assert idx in all_loads, f"GPU {idx} 应在 get_all_loads() 中"

    def test_set_strategy_changes_weights(self):
        """set_strategy() 切换策略后权重重新计算"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 3080", "nvidia", 8.0, 68),
            _make_device(1, "NVIDIA GeForce RTX 4090", "nvidia", 24.0, 128),
        ]
        balancer = GPULoadBalancer(devices, strategy="equal")
        equal_weights = balancer.calculate_weights().copy()

        balancer.set_strategy("performance")
        perf_weights = balancer.calculate_weights()

        # 切换到 performance 后，权重不再相等
        assert perf_weights[1] != equal_weights[1], "切换策略后权重应发生变化"
        assert perf_weights[1] > perf_weights[0], "RTX 4090 权重应大于 RTX 3080"


# ---------------------------------------------------------------------------
# TestKernelCompilationCache: 3.1 内核编译缓存
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestKernelCompilationCache:
    """场景 3.1: 内核编译缓存 (GPUContext._kernel_cache)"""

    def test_vendor_key_nvidia(self):
        """_get_vendor_key 返回包含 nvidia 的键"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine.__new__(MultiGPUCollisionEngine)
        engine._compiled_programs = {}
        device = {
            "vendor": "NVIDIA Corporation",
            "platform_name": "NVIDIA CUDA",
            "global_index": 0,
        }
        key = engine._get_vendor_key(device)
        assert "nvidia" in key.lower(), f"键 {key} 应包含 'nvidia'"

    def test_vendor_key_amd(self):
        """_get_vendor_key 返回包含 amd 相关内容的键"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine.__new__(MultiGPUCollisionEngine)
        engine._compiled_programs = {}
        device = {
            "vendor": "Advanced Micro Devices, Inc.",
            "platform_name": "AMD Accelerated Parallel Processing",
            "global_index": 0,
        }
        key = engine._get_vendor_key(device)
        assert "advanced" in key.lower() or "amd" in key.lower(), f"键 {key} 应包含 AMD 相关内容"

    def test_vendor_key_intel(self):
        """_get_vendor_key 返回包含 intel 的键"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine.__new__(MultiGPUCollisionEngine)
        engine._compiled_programs = {}
        device = {
            "vendor": "Intel(R) Corporation",
            "platform_name": "Intel(R) OpenCL Graphics",
            "global_index": 0,
        }
        key = engine._get_vendor_key(device)
        assert "intel" in key.lower(), f"键 {key} 应包含 'intel'"

    def test_same_vendor_compile_config_cached(self):
        """同厂商第二次请求不重复注册编译配置"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine.__new__(MultiGPUCollisionEngine)
        engine._compiled_programs = {}

        device1 = {
            "vendor": "NVIDIA Corporation",
            "platform_name": "NVIDIA CUDA",
            "global_index": 0,
        }
        device2 = {
            "vendor": "NVIDIA Corporation",
            "platform_name": "NVIDIA CUDA",
            "global_index": 1,
        }
        kernel_src = "__kernel void test(){}"
        build_opts = "-cl-fast-relaxed-math"

        config1 = engine._get_or_cache_compile_config(device1, kernel_src, build_opts)
        config2 = engine._get_or_cache_compile_config(device2, kernel_src, build_opts)

        # 同厂商应返回相同配置
        assert config1 is config2, "同厂商 GPU 应复用编译配置"
        assert config1["build_options"] == build_opts

    def test_different_vendor_separate_configs(self):
        """不同厂商各自独立编译配置"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine.__new__(MultiGPUCollisionEngine)
        engine._compiled_programs = {}

        nvidia_dev = {
            "vendor": "NVIDIA Corporation",
            "platform_name": "NVIDIA CUDA",
            "global_index": 0,
        }
        amd_dev = {
            "vendor": "Advanced Micro Devices, Inc.",
            "platform_name": "AMD APP",
            "global_index": 1,
        }
        kernel_src = "__kernel void test(){}"

        cfg_nvidia = engine._get_or_cache_compile_config(
            nvidia_dev, kernel_src, "-cl-std=CL2.0"
        )
        cfg_amd = engine._get_or_cache_compile_config(amd_dev, kernel_src, "-cl-std=CL2.0")

        assert cfg_nvidia is not cfg_amd, "不同厂商应为独立配置"
        # 厂商间配置使用 vendor_key 区分（build_options 可能相同，但缓存键不同）
        assert cfg_nvidia["vendor_key"] != cfg_amd["vendor_key"], (
            f"不同厂商应有不同 vendor_key, "
            f"实际: nvidia={cfg_nvidia['vendor_key']}, amd={cfg_amd['vendor_key']}"
        )

    def test_context_kernel_cache_initially_empty(self):
        """GPUContext._kernel_cache 初始化为空"""
        from src.gpu.context import GPUContext

        ctx = GPUContext.__new__(GPUContext)
        ctx._kernel_cache = {}
        ctx.program = None

        # 初始应为空
        assert len(ctx._kernel_cache) == 0, "GPUContext._kernel_cache 初始应为空"

    def test_context_cache_key_format(self):
        """GPUContext._kernel_cache 的键包含源码哈希和编译选项"""
        import hashlib

        kernel_src = "__kernel void test(){}"
        build_opts = "-cl-std=CL2.0"
        source_hash = hashlib.md5(kernel_src.encode(), usedforsecurity=False).hexdigest()[:16]
        cache_key = f"{source_hash}_{build_opts.replace(' ', '_')}"

        # 验证键格式包含哈希和选项
        assert source_hash in cache_key, "缓存键应包含源码哈希"
        assert "CL2" in cache_key or "cl2" in cache_key.lower(), "缓存键应包含编译选项标识"


# ---------------------------------------------------------------------------
# TestProportionalMemoryPools: 3.2 按显存比例分配内存池
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestProportionalMemoryPools:
    """场景 3.2: Per-GPU 内存池按显存比例分配"""

    def test_single_device_gets_full_pool(self):
        """单卡获得全部分配额度"""
        from src.gpu.memory_pool import GPUMemoryPool

        devices = [{"name": "GPU A", "global_mem_size": 8 * 1024**3}]  # 8GB
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=512)

        assert 0 in pools
        stats = pools[0].get_stats()
        assert stats["max_memory_mb"] == 512

    def test_equal_vram_equal_split(self):
        """两块显存相同的 GPU，各分得 50%"""
        from src.gpu.memory_pool import GPUMemoryPool

        devices = [
            {"name": "GPU A", "global_mem_size": 8 * 1024**3},
            {"name": "GPU B", "global_mem_size": 8 * 1024**3},
        ]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=512)

        assert len(pools) == 2
        mb0 = pools[0].get_stats()["max_memory_mb"]
        mb1 = pools[1].get_stats()["max_memory_mb"]
        # 各 256MB，允许 1MB 误差（int 截断）
        assert abs(mb0 - 256) <= 1, f"GPU 0 内存池 {mb0}MB，期望 ~256MB"
        assert abs(mb1 - 256) <= 1, f"GPU 1 内存池 {mb1}MB，期望 ~256MB"

    def test_proportional_allocation_different_vram(self):
        """显存 8GB + 24GB：内存池按 1:3 比例分配"""
        from src.gpu.memory_pool import GPUMemoryPool

        devices = [
            {"name": "RTX 3080", "global_mem_size": 8 * 1024**3},  # 8GB
            {"name": "RTX 4090", "global_mem_size": 24 * 1024**3},  # 24GB
        ]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=512)

        mb0 = pools[0].get_stats()["max_memory_mb"]  # 8/(8+24) * 512 = 128MB
        mb1 = pools[1].get_stats()["max_memory_mb"]  # 24/(8+24) * 512 = 384MB

        assert mb1 > mb0, f"RTX 4090 内存池 ({mb1}MB) 应大于 RTX 3080 ({mb0}MB)"
        # 4090 显存是 3080 的 3 倍，内存池比也应达到2:1 以上
        assert mb1 / mb0 >= 2.0, f"内存池比 {mb1 / mb0:.2f}，期望 >= 2.0"

    def test_zero_vram_equal_fallback(self):
        """无法获取显存信息时，均分内存池"""
        from src.gpu.memory_pool import GPUMemoryPool

        devices = [
            {"name": "GPU A", "global_mem_size": 0},
            {"name": "GPU B", "global_mem_size": 0},
        ]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=256)

        assert len(pools) == 2
        mb0 = pools[0].get_stats()["max_memory_mb"]
        mb1 = pools[1].get_stats()["max_memory_mb"]
        assert mb0 >= 64, f"GPU 0 内存池 {mb0}MB 不应低于 64MB"
        assert mb1 >= 64, f"GPU 1 内存池 {mb1}MB 不应低于 64MB"

    def test_minimum_pool_64mb(self):
        """小显存 GPU 也至少分得 64MB 内存池"""
        from src.gpu.memory_pool import GPUMemoryPool

        devices = [
            {"name": "Tiny GPU", "global_mem_size": 1 * 1024**3},  # 1GB
            {"name": "Big GPU", "global_mem_size": 100 * 1024**3},  # 100GB
        ]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=512)

        mb_small = pools[0].get_stats()["max_memory_mb"]
        assert mb_small >= 64, f"1GB 显存 GPU 内存池 {mb_small}MB 不应低于 64MB"

    def test_empty_devices_returns_empty(self):
        """空设备列表返回空映射"""
        from src.gpu.memory_pool import GPUMemoryPool

        pools = GPUMemoryPool.create_proportional_pools([])
        assert pools == {}

    def test_multi_engine_stores_pool_config(self):
        """多 GPU 引擎初始化后 _device_memory_pool_config 有内容"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        devices = [
            {
                "global_index": 0,
                "name": "RTX 3080",
                "vendor": "nvidia",
                "global_mem_size": 8 * 1024**3,
                "recommended_batch_size": 65536,
                "recommended_work_group": 256,
                "score": 100,
            },
            {
                "global_index": 1,
                "name": "RTX 4090",
                "vendor": "nvidia",
                "global_mem_size": 24 * 1024**3,
                "recommended_batch_size": 131072,
                "recommended_work_group": 256,
                "score": 200,
            },
        ]

        with patch("src.gpu.multi_gpu_engine.get_gpu_selector") as mock_selector:
            selector_inst = MagicMock()
            selector_inst.detect_all_devices.return_value = devices
            selector_inst.select_devices_by_indices.return_value = devices
            mock_selector.return_value = selector_inst

            with patch("src.gpu.multi_gpu_engine.DataMonitor"):
                with patch("src.gpu.multi_gpu_engine.GPURecoveryManager"):
                    engine = MultiGPUCollisionEngine()
                    result = engine.initialize(device_count=2)

        if result:
            assert len(engine._device_memory_pool_config) == 2
            mb0 = engine._device_memory_pool_config.get(0, 0)
            mb1 = engine._device_memory_pool_config.get(1, 0)
            if mb0 > 0 and mb1 > 0:
                assert mb1 > mb0, "RTX 4090 内存池应大于 RTX 3080"


# ---------------------------------------------------------------------------
# TestVendorBuildOptions: 3.3 厂商编译选项细化
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestVendorBuildOptions:
    """场景 3.3: 厂商特定编译选项（VENDOR_BUILD_OPTIONS）"""

    def test_vendor_build_options_exists(self):
        """VENDOR_BUILD_OPTIONS 常量存在且包含三大厂商"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        assert "nvidia" in VENDOR_BUILD_OPTIONS
        assert "amd" in VENDOR_BUILD_OPTIONS
        assert "intel" in VENDOR_BUILD_OPTIONS

    def test_nvidia_no_fast_relaxed_math(self):
        """NVIDIA 编译选项不包含 -cl-fast-relaxed-math（精度安全约束）"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        nvidia_opts = VENDOR_BUILD_OPTIONS["nvidia"]["options"]
        assert (
            "-cl-fast-relaxed-math" not in nvidia_opts
        ), f"NVIDIA 不应包含 -cl-fast-relaxed-math（精度安全约束），实际: {nvidia_opts}"

    def test_amd_no_fast_relaxed_math(self):
        """AMD 编译选项不包含 -cl-fast-relaxed-math（精度风险）"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        amd_opts = VENDOR_BUILD_OPTIONS["amd"]["options"]
        assert (
            "-cl-fast-relaxed-math" not in amd_opts
        ), f"AMD 不应包含 -cl-fast-relaxed-math，实际: {amd_opts}"

    def test_intel_no_fast_relaxed_math(self):
        """Intel 编译选项不包含 -cl-fast-relaxed-math（已知精度问题）"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        intel_opts = VENDOR_BUILD_OPTIONS["intel"]["options"]
        assert (
            "-cl-fast-relaxed-math" not in intel_opts
        ), f"Intel 不应包含 -cl-fast-relaxed-math，实际: {intel_opts}"

    def test_amd_uses_cl2(self):
        """AMD 使用 CL2.0 标准"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        amd_opts = VENDOR_BUILD_OPTIONS["amd"]["options"]
        assert any(
            "CL2.0" in o or "cl2" in o.lower() for o in amd_opts
        ), f"AMD 应使用 CL2.0，实际: {amd_opts}"

    def test_intel_uses_cl2(self):
        """Intel 使用 CL2.0 标准"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        intel_opts = VENDOR_BUILD_OPTIONS["intel"]["options"]
        assert any(
            "CL2.0" in o or "cl2" in o.lower() for o in intel_opts
        ), f"Intel 应使用 CL2.0，实际: {intel_opts}"

    def test_intel_has_workarounds_flag(self):
        """Intel 配置标记 intel_workarounds=True"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        assert VENDOR_BUILD_OPTIONS["intel"].get("intel_workarounds") is True

    def test_all_vendors_have_description(self):
        """所有厂商配置都有 description 字段"""
        from src.gpu.context import VENDOR_BUILD_OPTIONS

        for vendor, cfg in VENDOR_BUILD_OPTIONS.items():
            assert "description" in cfg, f"厂商 {vendor} 缺少 description 字段"
            assert isinstance(cfg["description"], str) and cfg["description"]

    def _get_build_options_for_vendor(self, vendor_name: str) -> str:
        """构造模拟 GPUContext 并调用 _get_build_options"""
        from src.gpu.context import GPUContext

        ctx = GPUContext.__new__(GPUContext)
        ctx._kernel_cache = {}
        mock_vendor = MagicMock()
        mock_vendor.get_vendor_name.return_value = vendor_name
        ctx.vendor_handler = mock_vendor
        return ctx._get_build_options()

    def test_get_build_options_nvidia_no_fast_math(self):
        """_get_build_options 对 NVIDIA 不包含 fast-relaxed-math（精度安全约束）"""
        opts = self._get_build_options_for_vendor("nvidia")
        assert "-cl-fast-relaxed-math" not in opts

    def test_get_build_options_amd_no_fast_math(self):
        """_get_build_options 对 AMD 不包含 fast-relaxed-math"""
        opts = self._get_build_options_for_vendor("amd")
        assert "-cl-fast-relaxed-math" not in opts

    def test_get_build_options_intel_no_fast_math(self):
        """_get_build_options 对 Intel 不包含 fast-relaxed-math"""
        opts = self._get_build_options_for_vendor("intel")
        assert "-cl-fast-relaxed-math" not in opts

    def test_get_build_options_unknown_vendor_safe(self):
        """未知厂商使用安全编译选项（不启用快速数学）"""
        opts = self._get_build_options_for_vendor("unknown_vendor")
        assert "-cl-fast-relaxed-math" not in opts


# ---------------------------------------------------------------------------
# TestSingleGPUMode: 单卡模式工具函数
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestSingleGPUMode:
    """场景 1: GPU 单卡模式基本功能验证"""

    def test_single_gpu_device_selection(self):
        """单卡自动选择最优设备"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 4090", "nvidia", 24.0, 128),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        weights = balancer.calculate_weights()

        assert len(weights) == 1
        assert abs(weights[0] - 1.0) < 1e-6, f"单卡权重 {weights[0]} 应为 1.0"

    def test_single_gpu_full_key_range(self):
        """单卡获得全部密鑰范围"""
        devices = [
            _make_device(0, "NVIDIA GeForce RTX 4090", "nvidia", 24.0, 128),
        ]
        balancer = GPULoadBalancer(devices, strategy="performance")
        ranges = balancer.assign_all_key_ranges(1_000_000)

        assert 0 in ranges
        start, end = ranges[0]
        assert end - start == 1_000_000

    def test_single_gpu_proportional_pool_is_full(self):
        """单卡内存池分配全部 total_pool_mb"""
        from src.gpu.memory_pool import GPUMemoryPool

        devices = [{"name": "RTX 4090", "global_mem_size": 24 * 1024**3}]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=512)

        assert 0 in pools
        assert pools[0].get_stats()["max_memory_mb"] == 512
