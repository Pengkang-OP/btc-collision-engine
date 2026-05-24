#!/usr/bin/env python3
"""GPU资源清理测试脚本

专门测试GPU碰撞引擎的资源清理功能，确保stop()方法正确释放所有资源。
"""


import pytest

pytestmark = [
    pytest.mark.gpu,
    pytest.mark.gpu_unit,
    pytest.mark.timeout(90),
]


@pytest.mark.usefixtures("mock_gpu_chain")
class TestGPUCleanup:
    """GPU资源清理测试"""

    def test_gpu_cleanup(self, mock_gpu_chain):
        """测试GPU资源清理"""
        from src.collision.gpu.engine import GPUCollisionEngine

        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        }
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=0,
            batch_size=8192,
            data_logging_enabled=False,
        )
        engine.start(mode="random")
        assert engine.is_running()
        engine.stop()
        assert not engine.is_running()

    def test_multiple_start_stop(self, mock_gpu_chain):
        """测试多次启动和停止"""
        from src.collision.gpu.engine import GPUCollisionEngine

        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        }
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=0,
            batch_size=8192,
            data_logging_enabled=False,
        )

        for _ in range(3):
            engine.start(mode="random")
            assert engine.is_running()
            engine.stop()
            assert not engine.is_running()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
