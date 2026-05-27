"""GPU 引擎 Mock 测试（依赖 mock_gpu_chain fixture）.

这些测试需要 mock_gpu_chain 模拟 GPU 环境，
CI 中通过 -m "not (gpu or gpu_kernel)" 自动跳过。

非 GPU 依赖的测试移至 test_gpu_core.py。

运行：
    pytest tests/test_gpu_engine_mock.py -v --tb=short
"""

import pytest

pytestmark = [
    pytest.mark.gpu,
    pytest.mark.gpu_unit,
    pytest.mark.timeout(90),
]


# ============================================================================
# 测试：GPU 引擎初始化（使用 Mock 链）
# ============================================================================


@pytest.mark.usefixtures("mock_gpu_chain")
class TestGPUEngineInit:
    """GPU 引擎初始化测试."""

    def test_engine_instantiation(self, mock_gpu_chain):
        """测试：GPU 引擎可实例化."""
        from src.collision.gpu.engine import GPUCollisionEngine

        engine = GPUCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            batch_size=100,
        )
        assert hasattr(engine, "start")
        assert hasattr(engine, "stop")
        assert hasattr(engine, "is_running")
        assert hasattr(engine, "get_device_info")

    def test_engine_with_multiple_targets(self, mock_gpu_chain):
        """测试：多目标地址初始化."""
        from src.collision.gpu.engine import GPUCollisionEngine

        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1CounterpartyXXXXXXXXXXXXXXXUWLpVr",
            "1BitcoinXXXXXXXXXXXXXXXXXXXXXXeHvFi",
        }
        engine = GPUCollisionEngine(targets=targets, batch_size=100)
        assert engine is not None

    def test_engine_get_device_info(self, mock_gpu_chain):
        """测试：获取 GPU 设备信息."""
        from src.collision.gpu.engine import GPUCollisionEngine

        engine = GPUCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            batch_size=100,
        )
        info = engine.get_device_info()
        assert isinstance(info, dict)
        assert len(info) > 0


# ============================================================================
# 测试：GPU 引擎生命周期
# ============================================================================


@pytest.mark.usefixtures("mock_gpu_chain")
class TestGPUEngineLifecycle:
    """GPU 引擎生命周期测试."""

    def test_engine_initial_state(self, mock_gpu_chain):
        """测试：初始状态为未运行."""
        from src.collision.gpu.engine import GPUCollisionEngine

        engine = GPUCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            batch_size=100,
        )
        assert not engine.is_running()

    def test_engine_start_and_stop(self, mock_gpu_chain):
        """测试：启动和停止."""
        from src.collision.gpu.engine import GPUCollisionEngine

        engine = GPUCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
            batch_size=100,
        )
        engine.start(mode="random")
        assert engine.is_running()
        engine.stop()
        assert not engine.is_running()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
