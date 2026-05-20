"""
Intel GPU 专有优化器单元测试

测试 IntelGPUOptimizer 类，覆盖：
- apply_optimizations() 正常路径与 workaround 验证失败路径
- init_monitoring_and_tuning() 组件防御性初始化逻辑
- get_optimization_flags() 标志读取
- _verify_uint32_workaround() 内部验证逻辑
- 组件属性访问器 (timeout_manager / memory_monitor / ...)

所有 GPU 依赖通过 Mock 隔离，不依赖真实 GPU 或 OpenCL。
"""

import logging
import os
import sys
import unittest
from unittest.mock import Mock, patch

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.gpu.intel_optimizer import IntelGPUOptimizer  # noqa: E402

# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

# 包含正确 uint32 workaround 特征字符串的内核源码片段
# 注意: v4.2.1 PRNG改造后，内核使用 __constant const uint *seed 替代 __global const uint *private_keys
_VALID_KERNEL_SOURCE = """
__kernel void btc_collision(
    __constant const uint *seed,
    __global uint *match_flags,
    __global const uchar *target_hashes,
    const uint num_keys,
    const uint num_targets
) {
    // kernel body
}
"""

# 缺少 uint32 workaround 特征字符串的内核源码（用于验证失败场景）
_INVALID_KERNEL_SOURCE = """
__kernel void btc_collision(
    __global const ulong *private_keys,
    __global uint *match_flags
) {
    // kernel body without uint workaround
}
"""


def _make_intel_device(
    name: str = "Intel(R) Arc(TM) A770 Graphics",
    vendor: str = "Intel Corporation",
    global_mem_size: int = 16 * 1024**3,
    timeout_seconds: float = 30.0,
    enable_async_execution: bool = True,
    memory_efficiency: float = 0.70,
    driver_version: str = "31.0.101.4255",
) -> Mock:
    """创建 Mock Intel GPU 设备对象"""
    device = Mock()
    device.name = name
    device.vendor = vendor
    device.device_info = {
        "name": name,
        "vendor": vendor,
        "global_mem_size": global_mem_size,
    }
    device.timeout_seconds = timeout_seconds
    device.enable_async_execution = enable_async_execution
    device.memory_efficiency = memory_efficiency
    device.driver_version = driver_version
    return device


def _make_optimizer_with_no_imports(device=None, config=None):
    """创建 IntelGPUOptimizer，并 patch 所有延迟导入为 ImportError"""
    if device is None:
        device = _make_intel_device()
    if config is None:
        config = {}
    return IntelGPUOptimizer(device=device, config=config)


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.gpu
class TestIntelGPUOptimizerInit(unittest.TestCase):
    """测试 IntelGPUOptimizer 初始化"""

    def test_default_init_components_none(self):
        """默认初始化时所有内部组件应为 None"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        self.assertIsNone(optimizer._timeout_manager)
        self.assertIsNone(optimizer._memory_monitor)
        self.assertIsNone(optimizer._benchmark_suite)
        self.assertIsNone(optimizer._auto_tuner)
        self.assertIsNone(optimizer._performance_reporter)

    def test_device_stored_correctly(self):
        """设备对象应被正确存储"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        self.assertIs(optimizer._device, device)

    def test_config_stored_correctly(self):
        """配置字典应被正确存储"""
        config = {"some_key": "some_value"}
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config=config)
        self.assertIs(optimizer._config, config)

    def test_custom_logger_used(self):
        """传入 engine_logger 时应使用该 logger"""
        device = _make_intel_device()
        custom_logger = logging.getLogger("test_intel_optimizer")
        optimizer = IntelGPUOptimizer(device=device, config={}, engine_logger=custom_logger)
        self.assertIs(optimizer._logger, custom_logger)

    def test_default_logger_not_none(self):
        """不传 engine_logger 时 _logger 应不为 None"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        self.assertIsNotNone(optimizer._logger)


@pytest.mark.unit
@pytest.mark.gpu
class TestVerifyUint32Workaround(unittest.TestCase):
    """测试 _verify_uint32_workaround() 方法"""

    def setUp(self):
        self.device = _make_intel_device()
        self.optimizer = IntelGPUOptimizer(device=self.device, config={})

    def test_valid_kernel_source_returns_true(self):
        """包含正确 workaround 特征字符串的内核源码应返回 True"""
        result = self.optimizer._verify_uint32_workaround(_VALID_KERNEL_SOURCE)
        self.assertTrue(result)

    def test_invalid_kernel_source_returns_false(self):
        """缺少 workaround 特征字符串的内核源码应返回 False"""
        result = self.optimizer._verify_uint32_workaround(_INVALID_KERNEL_SOURCE)
        self.assertFalse(result)

    def test_empty_kernel_source_returns_false(self):
        """空字符串内核源码应返回 False"""
        result = self.optimizer._verify_uint32_workaround("")
        self.assertFalse(result)

    def test_contains_partial_match_returns_false(self):
        """仅包含部分特征字符串时应返回 False"""
        partial_source = "__constant const uint seed"  # 缺少 *
        result = self.optimizer._verify_uint32_workaround(partial_source)
        self.assertFalse(result)

    def test_exact_signature_in_longer_source(self):
        """在较长的内核源码中包含精确特征字符串应返回 True"""
        long_source = "// header\n" + _VALID_KERNEL_SOURCE + "\n// footer"
        result = self.optimizer._verify_uint32_workaround(long_source)
        self.assertTrue(result)


@pytest.mark.unit
@pytest.mark.gpu
class TestApplyOptimizationsSuccess(unittest.TestCase):
    """测试 apply_optimizations() 成功路径"""

    def setUp(self):
        self.device = _make_intel_device()
        self.optimizer = IntelGPUOptimizer(device=self.device, config={})

    def _make_engine_context(self, kernel_source=None):
        """构建测试用的 engine_context"""
        return {
            "kernel_source": kernel_source or _VALID_KERNEL_SOURCE,
            "engine": Mock(),
        }

    def test_returns_dict(self):
        """成功时应返回字典"""
        context = self._make_engine_context()
        result = self.optimizer.apply_optimizations(context)
        self.assertIsInstance(result, dict)

    def test_uint32_workaround_verified_in_result(self):
        """成功时 result 应包含 uint32_workaround_verified=True"""
        context = self._make_engine_context()
        result = self.optimizer.apply_optimizations(context)
        self.assertTrue(result.get("uint32_workaround_verified"))

    def test_timeout_seconds_in_result(self):
        """成功时 result 应包含 timeout_seconds"""
        context = self._make_engine_context()
        result = self.optimizer.apply_optimizations(context)
        self.assertIn("timeout_seconds", result)
        self.assertEqual(result["timeout_seconds"], 30.0)

    def test_async_enabled_in_result(self):
        """成功时 result 应包含 async_enabled"""
        context = self._make_engine_context()
        result = self.optimizer.apply_optimizations(context)
        self.assertIn("async_enabled", result)
        self.assertTrue(result["async_enabled"])

    def test_memory_efficiency_in_result(self):
        """成功时 result 应包含 memory_efficiency"""
        context = self._make_engine_context()
        result = self.optimizer.apply_optimizations(context)
        self.assertIn("memory_efficiency", result)
        self.assertAlmostEqual(result["memory_efficiency"], 0.70)

    def test_driver_version_in_result(self):
        """成功时 result 应包含 driver_version"""
        context = self._make_engine_context()
        result = self.optimizer.apply_optimizations(context)
        self.assertIn("driver_version", result)
        self.assertEqual(result["driver_version"], "31.0.101.4255")

    def test_monitoring_components_in_result(self):
        """成功时 result 应包含 monitoring_components 字典"""
        context = self._make_engine_context()
        result = self.optimizer.apply_optimizations(context)
        self.assertIn("monitoring_components", result)
        self.assertIsInstance(result["monitoring_components"], dict)

    def test_device_without_driver_version(self):
        """设备没有 driver_version 时 result['driver_version'] 应为 None"""
        device = _make_intel_device()
        del device.driver_version  # 移除属性
        optimizer = IntelGPUOptimizer(device=device, config={})
        context = {"kernel_source": _VALID_KERNEL_SOURCE, "engine": Mock()}
        result = optimizer.apply_optimizations(context)
        self.assertIsNone(result["driver_version"])

    def test_async_disabled_device(self):
        """异步执行未启用的设备应正确反映在结果中"""
        device = _make_intel_device(enable_async_execution=False)
        optimizer = IntelGPUOptimizer(device=device, config={})
        context = {"kernel_source": _VALID_KERNEL_SOURCE, "engine": Mock()}
        result = optimizer.apply_optimizations(context)
        self.assertFalse(result["async_enabled"])


@pytest.mark.unit
@pytest.mark.gpu
class TestApplyOptimizationsFailure(unittest.TestCase):
    """测试 apply_optimizations() 失败路径"""

    def test_invalid_kernel_raises_runtime_error(self):
        """uint32 workaround 验证失败时应抛出 RuntimeError"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        context = {
            "kernel_source": _INVALID_KERNEL_SOURCE,
            "engine": Mock(),
        }
        with self.assertRaises(RuntimeError) as cm:
            optimizer.apply_optimizations(context)
        self.assertIn("workaround", str(cm.exception).lower())

    def test_empty_kernel_raises_runtime_error(self):
        """空内核源码应导致 RuntimeError"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        context = {"kernel_source": "", "engine": Mock()}
        with self.assertRaises(RuntimeError):
            optimizer.apply_optimizations(context)

    def test_missing_kernel_source_raises_runtime_error(self):
        """engine_context 不含 kernel_source 时（默认空字符串）应抛出 RuntimeError"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        context = {"engine": Mock()}  # 无 kernel_source
        with self.assertRaises(RuntimeError):
            optimizer.apply_optimizations(context)


@pytest.mark.unit
@pytest.mark.gpu
class TestInitMonitoringAndTuning(unittest.TestCase):
    """测试 init_monitoring_and_tuning() 方法"""

    def setUp(self):
        self.device = _make_intel_device()
        self.optimizer = IntelGPUOptimizer(device=self.device, config={})

    def _make_context(self):
        return {"engine": Mock()}

    def test_returns_dict_with_required_keys(self):
        """应返回包含 5 个组件键的字典"""
        context = self._make_context()
        result = self.optimizer.init_monitoring_and_tuning(context)
        required_keys = {
            "timeout_manager",
            "memory_monitor",
            "benchmark_suite",
            "auto_tuner",
            "performance_reporter",
        }
        self.assertEqual(set(result.keys()), required_keys)

    def test_all_components_none_when_imports_unavailable(self):
        """所有子模块均不可导入时，所有组件应为 None"""
        context = self._make_context()

        import_patches = {
            "src.gpu.intel_timeout_manager": None,
            "src.gpu.intel_memory_monitor": None,
            "src.gpu.benchmark_suite": None,
            "src.gpu.auto_tuner": None,
            "src.gpu.performance_reporter": None,
        }
        with patch.dict("sys.modules", import_patches):
            result = self.optimizer.init_monitoring_and_tuning(context)

        self.assertIsNone(result["timeout_manager"])
        self.assertIsNone(result["memory_monitor"])
        self.assertIsNone(result["benchmark_suite"])
        self.assertIsNone(result["auto_tuner"])
        self.assertIsNone(result["performance_reporter"])

    def test_no_engine_in_context_skips_p2_components(self):
        """engine_context 中无 engine 时，P2 组件（benchmark/tuner/reporter）应为 None"""
        context = {}  # 无 engine

        import_patches = {
            "src.gpu.intel_timeout_manager": None,
            "src.gpu.intel_memory_monitor": None,
        }
        with patch.dict("sys.modules", import_patches):
            result = self.optimizer.init_monitoring_and_tuning(context)

        self.assertIsNone(result["benchmark_suite"])
        self.assertIsNone(result["auto_tuner"])
        self.assertIsNone(result["performance_reporter"])

    def test_properties_updated_after_init(self):
        """init 后内部属性应与返回字典的值一致"""
        context = self._make_context()
        import_patches = {
            "src.gpu.intel_timeout_manager": None,
            "src.gpu.intel_memory_monitor": None,
            "src.gpu.benchmark_suite": None,
            "src.gpu.auto_tuner": None,
            "src.gpu.performance_reporter": None,
        }
        with patch.dict("sys.modules", import_patches):
            result = self.optimizer.init_monitoring_and_tuning(context)

        self.assertIs(self.optimizer._timeout_manager, result["timeout_manager"])
        self.assertIs(self.optimizer._memory_monitor, result["memory_monitor"])
        self.assertIs(self.optimizer._benchmark_suite, result["benchmark_suite"])
        self.assertIs(self.optimizer._auto_tuner, result["auto_tuner"])
        self.assertIs(self.optimizer._performance_reporter, result["performance_reporter"])

    def test_device_info_not_dict_skips_memory_monitor(self):
        """device.device_info 不是字典时应跳过显存监控器初始化"""
        device = _make_intel_device()
        device.device_info = "not_a_dict"  # 非字典类型
        optimizer = IntelGPUOptimizer(device=device, config={})

        # Mock IntelMemoryMonitor 可导入
        Mock()
        mock_timeout_cls = Mock()
        mock_timeout_cls.return_value = Mock()

        with patch.dict(
            "sys.modules",
            {
                "src.gpu.benchmark_suite": None,
                "src.gpu.auto_tuner": None,
                "src.gpu.performance_reporter": None,
            },
        ), patch("src.gpu.intel_optimizer.open", side_effect=ImportError, create=True):
            context = {"engine": Mock()}
            result = optimizer.init_monitoring_and_tuning(context)

        self.assertIsNone(result["memory_monitor"])

    def test_zero_global_mem_size_skips_memory_monitor(self):
        """device_info['global_mem_size'] == 0 时应跳过显存监控器"""
        device = _make_intel_device()
        device.device_info = {
            "name": "Test",
            "vendor": "Intel",
            "global_mem_size": 0,  # 零大小
        }
        optimizer = IntelGPUOptimizer(device=device, config={})

        import_patches = {
            "src.gpu.intel_timeout_manager": None,
            "src.gpu.benchmark_suite": None,
            "src.gpu.auto_tuner": None,
            "src.gpu.performance_reporter": None,
        }
        with patch.dict("sys.modules", import_patches):
            context = {"engine": Mock()}
            result = optimizer.init_monitoring_and_tuning(context)

        self.assertIsNone(result["memory_monitor"])


@pytest.mark.unit
@pytest.mark.gpu
class TestGetOptimizationFlags(unittest.TestCase):
    """测试 get_optimization_flags() 方法"""

    def test_returns_dict(self):
        """应返回字典类型"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        self.assertIsInstance(result, dict)

    def test_contains_required_keys(self):
        """应包含所有必需的标志键"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        required_keys = {
            "async_execution",
            "timeout_seconds",
            "memory_efficiency",
            "driver_version",
            "timeout_manager_active",
            "memory_monitor_active",
            "benchmark_suite_active",
            "auto_tuner_active",
            "performance_reporter_active",
        }
        self.assertTrue(required_keys.issubset(set(result.keys())))

    def test_initial_all_components_inactive(self):
        """初始状态下所有组件应为 inactive (False)"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        self.assertFalse(result["timeout_manager_active"])
        self.assertFalse(result["memory_monitor_active"])
        self.assertFalse(result["benchmark_suite_active"])
        self.assertFalse(result["auto_tuner_active"])
        self.assertFalse(result["performance_reporter_active"])

    def test_async_execution_reads_device_attribute(self):
        """async_execution 应读取 device.enable_async_execution"""
        device = _make_intel_device(enable_async_execution=True)
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        self.assertTrue(result["async_execution"])

    def test_async_execution_false_when_disabled(self):
        """async_execution 应在 device 禁用时返回 False"""
        device = _make_intel_device(enable_async_execution=False)
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        self.assertFalse(result["async_execution"])

    def test_timeout_seconds_reads_device_attribute(self):
        """timeout_seconds 应读取 device.timeout_seconds"""
        device = _make_intel_device(timeout_seconds=60.0)
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        self.assertEqual(result["timeout_seconds"], 60.0)

    def test_memory_efficiency_reads_device_attribute(self):
        """memory_efficiency 应读取 device.memory_efficiency"""
        device = _make_intel_device(memory_efficiency=0.85)
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        self.assertAlmostEqual(result["memory_efficiency"], 0.85)

    def test_driver_version_reads_device_attribute(self):
        """driver_version 应读取 device.driver_version"""
        device = _make_intel_device(driver_version="31.0.101.4255")
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        self.assertEqual(result["driver_version"], "31.0.101.4255")

    def test_component_active_after_manual_set(self):
        """手动设置内部组件后，对应 _active 标志应变为 True"""
        device = _make_intel_device()
        optimizer = IntelGPUOptimizer(device=device, config={})

        optimizer._timeout_manager = Mock()
        optimizer._memory_monitor = Mock()

        result = optimizer.get_optimization_flags()
        self.assertTrue(result["timeout_manager_active"])
        self.assertTrue(result["memory_monitor_active"])
        self.assertFalse(result["benchmark_suite_active"])

    def test_default_values_when_device_missing_attrs(self):
        """设备缺少属性时应使用默认值"""
        device = Mock(spec=[])  # 没有任何属性的 Mock
        optimizer = IntelGPUOptimizer(device=device, config={})
        result = optimizer.get_optimization_flags()
        # 应有默认值而非抛出异常
        self.assertFalse(result["async_execution"])
        self.assertEqual(result["timeout_seconds"], 30)
        self.assertAlmostEqual(result["memory_efficiency"], 0.70)
        self.assertIsNone(result["driver_version"])


@pytest.mark.unit
@pytest.mark.gpu
class TestComponentProperties(unittest.TestCase):
    """测试组件属性访问器（property）"""

    def setUp(self):
        self.device = _make_intel_device()
        self.optimizer = IntelGPUOptimizer(device=self.device, config={})

    def test_timeout_manager_property_returns_none_by_default(self):
        """初始状态 timeout_manager 属性应为 None"""
        self.assertIsNone(self.optimizer.timeout_manager)

    def test_memory_monitor_property_returns_none_by_default(self):
        """初始状态 memory_monitor 属性应为 None"""
        self.assertIsNone(self.optimizer.memory_monitor)

    def test_benchmark_suite_property_returns_none_by_default(self):
        """初始状态 benchmark_suite 属性应为 None"""
        self.assertIsNone(self.optimizer.benchmark_suite)

    def test_auto_tuner_property_returns_none_by_default(self):
        """初始状态 auto_tuner 属性应为 None"""
        self.assertIsNone(self.optimizer.auto_tuner)

    def test_performance_reporter_property_returns_none_by_default(self):
        """初始状态 performance_reporter 属性应为 None"""
        self.assertIsNone(self.optimizer.performance_reporter)

    def test_timeout_manager_property_after_set(self):
        """手动设置内部属性后 property 应返回对应对象"""
        mock_tm = Mock()
        self.optimizer._timeout_manager = mock_tm
        self.assertIs(self.optimizer.timeout_manager, mock_tm)

    def test_memory_monitor_property_after_set(self):
        """手动设置 _memory_monitor 后 property 应返回对应对象"""
        mock_mm = Mock()
        self.optimizer._memory_monitor = mock_mm
        self.assertIs(self.optimizer.memory_monitor, mock_mm)

    def test_benchmark_suite_property_after_set(self):
        """手动设置 _benchmark_suite 后 property 应返回对应对象"""
        mock_bs = Mock()
        self.optimizer._benchmark_suite = mock_bs
        self.assertIs(self.optimizer.benchmark_suite, mock_bs)

    def test_auto_tuner_property_after_set(self):
        """手动设置 _auto_tuner 后 property 应返回对应对象"""
        mock_at = Mock()
        self.optimizer._auto_tuner = mock_at
        self.assertIs(self.optimizer.auto_tuner, mock_at)

    def test_performance_reporter_property_after_set(self):
        """手动设置 _performance_reporter 后 property 应返回对应对象"""
        mock_pr = Mock()
        self.optimizer._performance_reporter = mock_pr
        self.assertIs(self.optimizer.performance_reporter, mock_pr)


if __name__ == "__main__":
    unittest.main()
