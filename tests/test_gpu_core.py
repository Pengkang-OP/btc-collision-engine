"""
GPU 核心测试（无 GPU 依赖）- 与 test_gpu_engine_mock.py 分开

这些测试不依赖 mock_gpu_chain，不需要 GPU 环境，
在 CI 中不会被 -m "not gpu" 过滤掉。

运行：
    pytest tests/test_gpu_core.py -v --tb=short
"""

import sys

import pytest

sys.path.insert(0, ".")


# ============================================================================
# 测试：GPU 可用性检测
# ============================================================================

@pytest.mark.unit
class TestGPUAvailability:
    """GPU 可用性检测（不依赖 GPU 环境）"""

    def test_gpu_engine_conditional_import(self):
        """测试：GPU 引擎条件导入"""
        try:
            from src.collision.gpu.engine import GPUCollisionEngine
            assert GPUCollisionEngine is not None
        except ImportError:
            pass  # 无 GPU 依赖时允许导入失败

    def test_gpu_engine_has_core_methods(self):
        """测试：GPU 引擎核心方法签名"""
        from src.collision.gpu.engine import GPUCollisionEngine

        method_names = {m for m in dir(GPUCollisionEngine) if not m.startswith("_")}
        core_methods = {"start", "stop", "is_running", "get_stats", "get_device_info"}
        missing = core_methods - method_names
        assert not missing, f"缺失方法: {missing}"


# ============================================================================
# 测试：GPU 事件脱敏（无 GPU 依赖）
# ============================================================================

@pytest.mark.unit
class TestGPUMasking:
    """GPU 事件脱敏测试（不涉及 GPU 硬件）"""

    def test_match_event_masks_wif(self):
        """测试：匹配事件 WIF 脱敏"""
        from src.collision.events import EngineMatchEvent

        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="KwDiBf89QgGbjEhKnhxAbTtPCGZxx3GZvV3gxCSQHhTtRzmxy1fy",
            target_address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        )
        assert event.wif != "KwDiBf89QgGbjEhKnhxAbTtPCGZxx3GZvV3gxCSQHhTtRzmxy1fy"
        assert "..." in str(event.wif)

    def test_event_metadata_excludes_secrets(self):
        """测试：事件元数据不包含密钥"""
        from src.collision.events import EngineMatchEvent

        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1Address",
            wif="KwDiBf89QgGbjEhKnhxAbTtPCGZxx3GZvV3gxCSQHhTtRzmxy1fy",
        )
        metadata_str = str(event.metadata)
        assert "private_key" not in metadata_str
        assert "x01" not in metadata_str


# ============================================================================
# 测试：GPU 常量（无 GPU 依赖）
# ============================================================================

@pytest.mark.unit
class TestGPUConstants:
    """GPU 常量和配置测试"""

    def test_constants_exist(self):
        """测试：GPU 常量定义齐全"""
        from src.collision.gpu import engine as gpu_engine

        expected = {
            "PYOPENCL_AVAILABLE", "UINT32_MAX", "GPU_MAX_BATCH_SIZE",
            "INITIAL_BATCH_SIZE", "THREAD_JOIN_TIMEOUT",
        }
        for const in expected:
            assert hasattr(gpu_engine, const), f"缺失常量: {const}"

    def test_batch_size_constants_are_positive(self):
        """测试：批次大小常量为正数"""
        from src.collision.gpu.engine import (
            GPU_MAX_BATCH_SIZE, INITIAL_BATCH_SIZE, UINT32_MAX,
        )
        assert GPU_MAX_BATCH_SIZE > 0
        assert INITIAL_BATCH_SIZE > 0
        assert UINT32_MAX > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
