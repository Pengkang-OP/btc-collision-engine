#!/usr/bin/env python3
"""GPU碰撞引擎 Shim 模块测试

验证 src.collision.gpu_collision_engine (Shim) 的所有导出和常量。

该模块是向后兼容的重导出模块，不包含业务逻辑。
测试通过 sys.modules 预注入 Mock 对象，绕过真实 GPU/OpenCL 导入链，
避免 numpy C 扩展与 coverage 工具的冲突，从而实现对 shim 全部 78 行的覆盖。

隔离策略:
- 每个测试通过 fixture 独立注入/清理 sys.modules mock
- 测试完成后恢复 sys.modules，不影响其他测试文件
"""

import importlib
import sys
from unittest.mock import MagicMock

import pytest

# ═══════════════════════════════════════════════════════════════
# Mock 模块定义
# ═══════════════════════════════════════════════════════════════

def _make_mock_class(name):
    """创建带名称的 MagicMock 类。"""
    return MagicMock(name=name)


def _build_module(name, **attrs):
    """构建一个 mock 模块，将 None 值替换为 MagicMock。"""
    mod = MagicMock()
    for k, v in attrs.items():
        setattr(mod, k, v if v is not None else _make_mock_class(k))
    return mod


_MOCK_SPECS = [
    # (模块名, 属性字典) — None 值自动替换为 MagicMock(name=key)
    ("src.collision.gpu", {"__version__": "4.4.0"}),
    ("src.collision.gpu.engine", {
        "GPUCollisionEngine": None,
        "UINT32_MAX": 0xFFFFFFFF,
        "GPU_MAX_BATCH_SIZE": 1_048_576,
        "INITIAL_BATCH_SIZE": 65536,
        "PYOPENCL_AVAILABLE": True,
        "ASYNC_LOG_AVAILABLE": True,
        "GPU_CONFIG_MANAGER_AVAILABLE": True,
    }),
    ("src.gpu", {"__version__": "4.4.0"}),
    ("src.gpu.profiles", {}),
    ("src.gpu.device", {"GPUDevice": None, "GPUDeviceDetector": None, "identify_vendor": None}),
    ("src.gpu.context", {"GPUContext": None}),
    ("src.gpu.profiles.loader", {"GPUProfileLoader": None}),
    ("src.gpu.kernel_impl", {"GPUKernel": None}),
    ("src.gpu.async_executor", {"AsyncGPUExecutor": None}),
    ("src.gpu.device_manager", {"GPUDeviceManager": None}),
    ("src.gpu.config_manager", {"GPUConfigManager": None}),
    ("src.gpu.search_mode_coordinator", {"SearchModeCoordinator": None}),
    ("src.gpu.search_modes", {
        "RandomSearchMode": None,
        "BruteForceSearchMode": None,
        "RangeScanSearchMode": None,
    }),
    ("src.gpu.engine_monitor", {"GPUEngineMonitor": None}),
]

_SELF_MODULE = "src.collision.gpu_collision_engine"
_ALL_MOCK_NAMES = [name for name, _ in _MOCK_SPECS]


# ═══════════════════════════════════════════════════════════════
# Fixture
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def shim():
    """为每个测试提供基于 Mock 的干净 shim 模块。

    1. 保存 sys.modules 中即将被替换的原始条目
    2. 注入 mock 模块
    3. 强制导入/重载 shim
    4. yield shim 模块给测试
    5. 恢复 sys.modules 原始状态
    """
    # ── 保存原始状态 ──
    saved = {}
    for name in _ALL_MOCK_NAMES + [_SELF_MODULE]:
        if name in sys.modules:
            saved[name] = sys.modules[name]
        else:
            saved[name] = None  # 标记"不存在"

    try:
        # ── 注入 mock ──
        for name, attrs in _MOCK_SPECS:
            sys.modules.pop(name, None)
            sys.modules[name] = _build_module(name, **attrs)
        sys.modules.pop(_SELF_MODULE, None)

        # ── 强制重新导入 shim ──
        mod = importlib.import_module(_SELF_MODULE)

        yield mod

    finally:
        # ── 恢复原始状态 ──
        for name in _ALL_MOCK_NAMES + [_SELF_MODULE]:
            sys.modules.pop(name, None)
            if saved.get(name) is not None:
                sys.modules[name] = saved[name]


# ═══════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════


class TestGPUCollisionEngineShim:
    """测试 gpu_collision_engine Shim 模块的完整性。"""

    # ── 3.1 模块元信息 ──────────────────────────────────────

    def test_module_docstring(self, shim):
        """验证模块文档字符串存在且包含关键信息。"""
        assert shim.__doc__ is not None
        assert "GPU碰撞引擎" in shim.__doc__
        assert "向后兼容" in shim.__doc__ or "Shim" in shim.__doc__

    # ── 3.2 核心类重导出 ────────────────────────────────────

    def test_gpu_collision_engine_exported(self, shim):
        """验证 GPUCollisionEngine 可从 shim 导入。"""
        assert hasattr(shim, "GPUCollisionEngine")
        assert shim.GPUCollisionEngine is not None

    # ── 3.3 常量重导出 ──────────────────────────────────────

    def test_uint32_max_exported(self, shim):
        """验证 UINT32_MAX 常量存在且为正确类型。"""
        assert hasattr(shim, "UINT32_MAX")
        assert isinstance(shim.UINT32_MAX, int)
        assert shim.UINT32_MAX > 0

    def test_gpu_max_batch_size_exported(self, shim):
        """验证 GPU_MAX_BATCH_SIZE 常量存在且为正整数。"""
        assert hasattr(shim, "GPU_MAX_BATCH_SIZE")
        assert isinstance(shim.GPU_MAX_BATCH_SIZE, int)
        assert shim.GPU_MAX_BATCH_SIZE > 0

    def test_initial_batch_size_exported(self, shim):
        """验证 INITIAL_BATCH_SIZE 常量存在且为正整数。"""
        assert hasattr(shim, "INITIAL_BATCH_SIZE")
        assert isinstance(shim.INITIAL_BATCH_SIZE, int)
        assert shim.INITIAL_BATCH_SIZE > 0

    def test_pyopencl_available_exported(self, shim):
        """验证 PYOPENCL_AVAILABLE 常量存在。"""
        assert hasattr(shim, "PYOPENCL_AVAILABLE")

    def test_async_log_available_exported(self, shim):
        """验证 ASYNC_LOG_AVAILABLE 常量存在。"""
        assert hasattr(shim, "ASYNC_LOG_AVAILABLE")

    def test_gpu_config_manager_available_exported(self, shim):
        """验证 GPU_CONFIG_MANAGER_AVAILABLE 常量存在。"""
        assert hasattr(shim, "GPU_CONFIG_MANAGER_AVAILABLE")

    # ── 3.4 向后兼容导入验证 ────────────────────────────────

    def test_gpu_device_exported(self, shim):
        assert hasattr(shim, "GPUDevice")

    def test_gpu_device_detector_exported(self, shim):
        assert hasattr(shim, "GPUDeviceDetector")

    def test_gpu_context_exported(self, shim):
        assert hasattr(shim, "GPUContext")

    def test_gpu_kernel_exported(self, shim):
        assert hasattr(shim, "GPUKernel")

    def test_gpu_profile_loader_exported(self, shim):
        assert hasattr(shim, "GPUProfileLoader")

    def test_async_gpu_executor_exported(self, shim):
        assert hasattr(shim, "AsyncGPUExecutor")

    def test_gpu_device_manager_exported(self, shim):
        assert hasattr(shim, "GPUDeviceManager")

    def test_gpu_config_manager_exported(self, shim):
        assert hasattr(shim, "GPUConfigManager")

    def test_search_mode_coordinator_exported(self, shim):
        assert hasattr(shim, "SearchModeCoordinator")

    def test_random_search_mode_exported(self, shim):
        assert hasattr(shim, "RandomSearchMode")

    def test_brute_force_search_mode_exported(self, shim):
        assert hasattr(shim, "BruteForceSearchMode")

    def test_range_scan_search_mode_exported(self, shim):
        assert hasattr(shim, "RangeScanSearchMode")

    def test_gpu_engine_monitor_exported(self, shim):
        assert hasattr(shim, "GPUEngineMonitor")

    # ── 3.5 模块级变量 ──────────────────────────────────────

    def test_new_gpu_module_available(self, shim):
        """验证 NEW_GPU_MODULE_AVAILABLE 为 True。"""
        assert hasattr(shim, "NEW_GPU_MODULE_AVAILABLE")
        assert shim.NEW_GPU_MODULE_AVAILABLE is True

    def test_logger_configured(self, shim):
        """验证 logger 已正确配置。"""
        import logging
        assert hasattr(shim, "logger")
        assert isinstance(shim.logger, logging.Logger)
        assert "gpu_collision_engine" in shim.logger.name

    # ── 3.6 __all__ 导出列表完整性 ──────────────────────────

    _EXPECTED_ALL = {
        "GPUCollisionEngine", "GPU_MAX_BATCH_SIZE", "UINT32_MAX",
        "INITIAL_BATCH_SIZE", "GPUDevice", "GPUContext", "GPUKernel",
        "GPUDeviceDetector", "GPUDeviceManager", "GPUConfigManager",
        "GPUEngineMonitor", "GPUProfileLoader", "SearchModeCoordinator",
        "RandomSearchMode", "BruteForceSearchMode", "RangeScanSearchMode",
        "AsyncGPUExecutor", "PYOPENCL_AVAILABLE", "ASYNC_LOG_AVAILABLE",
        "GPU_CONFIG_MANAGER_AVAILABLE",
    }

    def test_all_exports_complete(self, shim):
        """验证 __all__ 包含所有预期的导出符号。"""
        assert hasattr(shim, "__all__")
        assert set(shim.__all__) == self._EXPECTED_ALL

    def test_all_exports_are_accessible(self, shim):
        """验证 __all__ 中的每个符号都可通过 getattr 访问。"""
        for name in shim.__all__:
            assert hasattr(shim, name), f"__all__ 中的 '{name}' 不可访问"

    def test_no_extra_exports_outside_all(self, shim):
        """验证不存在 __all__ 之外的意外公共符号。"""
        public_names = {n for n in dir(shim) if not n.startswith("_")}
        standard_attrs = {
            "logger", "NEW_GPU_MODULE_AVAILABLE", "get_configured_logger"
        }
        extra = public_names - set(shim.__all__) - standard_attrs
        extra = {
            n for n in extra
            if not n.startswith("assert_") and not n.startswith("attach_mock")
        }
        assert extra == set(), (
            f"存在未在 __all__ 中声明的公共符号: {extra}"
        )

    # ── 3.7 通配符导入 ──────────────────────────────────────

    def test_wildcard_import_coverage(self, shim):
        """验证 `from src.collision.gpu_collision_engine import *` 可用。"""
        ns = {}
        exec("from src.collision.gpu_collision_engine import *", ns)
        for name in shim.__all__:
            assert name in ns, f"通配符导入应包含 '{name}'"
