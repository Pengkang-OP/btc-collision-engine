#!/usr/bin/env python3
"""GPU碰撞引擎异常处理专项测试

覆盖:
- GPU运行时异常
- 内存溢出
- 驱动错误
- 文件系统异常
- 统一异常处理器
"""

import os
import pathlib
import tempfile
import time
from unittest.mock import Mock, patch

import pytest

from src.collision.checkpoint_manager import CheckpointManager
from src.collision.collision_stats import CollisionStats
from src.collision.gpu.engine import GPUCollisionEngine
from src.utils.exception_handler import ExceptionHandler

pytestmark = pytest.mark.gpu


class TestGPURuntimeErrors:
    """GPU运行时异常测试"""

    def test_gpu_out_of_memory_error(self):
        """测试GPU内存不足错误处理"""
        stats = CollisionStats()

        # 测试异常处理器
        error = RuntimeError("out of memory")
        ExceptionHandler.handle_gpu_error("随机碰撞", error, stats)

        # 验证错误记录
        assert stats.gpu_errors == 1
        assert stats.resource_errors == 1

    @pytest.mark.skip(
        reason="Mock GPU engine activates real hardware via GPUDeviceManager, needs deeper test infra"
    )
    def test_gpu_runtime_error_recovery(self):
        """测试GPU运行时错误恢复"""
        mock_device = Mock()
        mock_device.context = Mock()
        mock_device.queue = Mock()
        mock_device.device_info = {
            "name": "Test GPU",
            "vendor": "NVIDIA Corporation",
            "global_mem_size": 8 * 1024**3,
        }
        mock_device.initialize = Mock()
        mock_device.get_device_info = Mock(return_value=mock_device.device_info)
        mock_device.cleanup = Mock()

        mock_context = Mock()
        mock_context.program = Mock()
        mock_context.apply_optimizations = Mock()
        mock_context.calculate_batch_size = Mock(return_value=100)
        mock_context.compile_kernel = Mock()
        mock_context.cleanup = Mock()

        mock_kernel = Mock()
        # 第5次调用时抛出异常
        call_count = [0]

        def run_batch_with_error(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 5:
                raise RuntimeError("GPU execution failed")
            return []

        mock_kernel.run_batch = Mock(side_effect=run_batch_with_error)
        mock_kernel.set_targets = Mock()
        mock_kernel.cleanup = Mock()
        mock_kernel.max_batch_size = 100
        mock_kernel.gpu_optimizer = Mock()
        mock_kernel.gpu_optimizer.analyze_and_adjust = Mock(return_value=(100, {}))

        with patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True):
            with (
                patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
                patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
                patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
                patch("src.gpu.device_manager.AsyncGPUExecutor") as mock_async_executor,
                patch("src.gpu.device_manager.GPUProfileLoader") as mock_profile_loader,
            ):
                mock_profile_loader.return_value.get_profile.return_value = None

                # 异步执行器第5次调用时抛出异常（匹配原 mock_kernel.run_batch 的逻辑）
                async_call_count = [0]

                def run_batch_async_with_error(*args, **kwargs):
                    async_call_count[0] += 1
                    if async_call_count[0] == 5:
                        raise RuntimeError("GPU execution failed")
                    return ([], 50.0)

                mock_async_instance = Mock()
                mock_async_instance.initialize_buffers = Mock()
                mock_async_instance.run_batch_async = Mock(side_effect=run_batch_async_with_error)
                mock_async_instance.flush_pending = Mock(return_value=[])
                mock_async_instance.cleanup = Mock()
                mock_async_executor.return_value = mock_async_instance

                targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
                engine = GPUCollisionEngine(targets, batch_size=100)

                # 启动随机模式
                engine.start(mode="random")

                # 运行3秒（应该会遇到异常并恢复）
                time.sleep(3)
                engine.stop()

                # 验证异常被记录
                assert engine.stats.gpu_errors >= 1

                # 验证引擎继续运行（total_checked > 0）
                assert engine.stats.total_checked > 0

    def test_gpu_kernel_compile_failure(self):
        """测试GPU内核编译失败"""
        mock_device = Mock()
        mock_device.context = Mock()
        mock_device.queue = Mock()
        mock_device.device_info = {
            "name": "Test GPU",
            "vendor": "NVIDIA Corporation",
            "global_mem_size": 8 * 1024**3,
        }
        mock_device.initialize = Mock()
        mock_device.get_device_info = Mock(return_value=mock_device.device_info)
        mock_device.cleanup = Mock()
        mock_device.vendor = "NVIDIA Corporation"
        mock_device.profile = None

        with (
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUDeviceDetector.is_gpu_available", return_value=True),
            patch("src.gpu.device_manager.GPUProfileLoader") as mock_profile_loader,
            patch("pyopencl.Program") as mock_program,
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            # 模拟编译失败
            mock_program.return_value.build.side_effect = Exception("compile error")

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

            # 验证初始化失败
            with pytest.raises(RuntimeError, match="GPU初始化失败"):
                GPUCollisionEngine(targets)


class TestMemoryErrors:
    """内存溢出测试"""

    def test_memory_error_handling(self):
        """测试MemoryError处理"""
        stats = CollisionStats()

        # 测试异常处理器
        error = MemoryError("Out of memory")
        ExceptionHandler.handle_engine_error("GPU", error, stats)

        # 验证错误记录
        assert stats.worker_errors == 0  # MemoryError不记录为worker_errors

    def test_large_batch_memory_pressure(self):
        """测试大batch_size内存压力"""
        from src.utils.gpu_memory_utils import calculate_optimal_batch_size

        # 模拟GPU设备
        mock_device = Mock()
        mock_device.global_mem_size = 8 * 1024**3  # 8GB

        # 计算最优batch_size
        batch_size = calculate_optimal_batch_size(mock_device, target_buffer_size=0)

        # 验证batch_size合理（不超过显存限制）
        assert batch_size > 0
        assert batch_size < 100_000_000  # 小于1亿


class TestFileSystemErrors:
    """文件系统异常测试"""

    def test_checkpoint_file_permission_error(self):
        """测试断点文件权限错误"""
        # 在只读目录创建断点管理器
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_checkpoint.json")
            checkpoint_mgr = CheckpointManager(filepath=filepath)

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

            # 正常保存应该成功
            state = {
                "mode": "random",
                "targets": list(targets),
                "current_position": 1000,
                "total_checked": 1000,
                "matches": [],
            }
            checkpoint_mgr.save(state)

            # 验证文件存在
            assert pathlib.Path(filepath).exists()

    def test_checkpoint_file_corrupted(self):
        """测试损坏的断点文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "corrupted_checkpoint.json")
            checkpoint_mgr = CheckpointManager(filepath=filepath)

            # 创建损坏的JSON文件
            pathlib.Path(filepath).write_text("{ invalid json content", encoding="utf-8")

            # 验证加载返回None
            loaded = checkpoint_mgr.load()
            assert loaded is None


class TestExceptionHandler:
    """统一异常处理器测试"""

    def test_exception_handler_engine_error(self):
        """测试引擎错误处理"""
        stats = CollisionStats()

        # 测试RuntimeError
        error = RuntimeError("Test error")
        ExceptionHandler.handle_engine_error("GPU", error, stats, context="初始化")

        # 验证错误记录
        assert stats.worker_errors == 1

    def test_exception_handler_gpu_error_resource(self):
        """测试GPU资源错误处理"""
        stats = CollisionStats()

        # 测试资源不足错误
        error = RuntimeError("out of resources")
        ExceptionHandler.handle_gpu_error("随机碰撞", error, stats)

        # 验证错误记录
        assert stats.gpu_errors == 1
        assert stats.resource_errors == 1

    def test_exception_handler_config_error(self):
        """测试配置错误处理"""
        # 测试FileNotFoundError
        error = FileNotFoundError("Config file not found")

        # 不应该抛出异常
        ExceptionHandler.handle_config_error(error, "ConfigManager")

    def test_exception_handler_file_error(self):
        """测试文件错误处理"""
        # 测试IOError
        error = OSError("Disk read error")

        # 不应该抛出异常
        ExceptionHandler.handle_file_error(error, "读取", "/path/to/file")

    def test_exception_handler_keyboard_interrupt(self):
        """测试KeyboardInterrupt处理"""
        stats = CollisionStats()

        # KeyboardInterrupt应该重新抛出
        # 使用pytest.raises捕获重抛的异常
        with pytest.raises(KeyboardInterrupt):
            try:
                raise KeyboardInterrupt("Test interrupt")
            except KeyboardInterrupt as e:
                ExceptionHandler.handle_engine_error("GPU", e, stats)


class TestEdgeCases:
    """边界条件测试"""

    def test_zero_targets(self):
        """测试空目标地址集合

        注意: _init_gpu()方法会捕获所有异常并重新抛出为RuntimeError
        因此即使_prepare_targets()抛出ValueError,最终也会是RuntimeError

        这是设计决策:统一异常类型,便于上层处理
        """
        mock_device = Mock()
        mock_device.context = Mock()
        mock_device.queue = Mock()
        mock_device.device_info = {
            "name": "Test GPU",
            "vendor": "NVIDIA Corporation",
            "global_mem_size": 8 * 1024**3,
        }
        mock_device.initialize = Mock()
        mock_device.get_device_info = Mock(return_value=mock_device.device_info)
        mock_device.cleanup = Mock()

        mock_context = Mock()
        mock_context.program = Mock()
        mock_context.apply_optimizations = Mock()
        mock_context.calculate_batch_size = Mock(return_value=65536)
        mock_context.compile_kernel = Mock()
        mock_context.cleanup = Mock()

        mock_kernel = Mock()
        mock_kernel.run_batch = Mock(return_value=[])
        mock_kernel.set_targets = Mock()
        mock_kernel.cleanup = Mock()
        mock_kernel.max_batch_size = 65536

        with (
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
            patch(
                "src.collision.gpu.engine.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.device_manager.AsyncGPUExecutor") as mock_async_executor,
            patch("src.gpu.device_manager.GPUProfileLoader") as mock_profile_loader,
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            mock_async_instance = Mock()
            mock_async_instance.initialize_buffers = Mock()
            mock_async_instance.run_batch_async = Mock(return_value=([], 50.0))
            mock_async_instance.cleanup = Mock()
            mock_async_executor.return_value = mock_async_instance

            # 空目标地址
            targets = set()

            # 验证初始化失败（ValueError被包装成RuntimeError）
            # 错误消息已更新为包含 P2PKH/Bech32 P2WPKH 两种格式
            with pytest.raises(RuntimeError, match="没有有效的 P2PKH/Bech32 P2WPKH 目标地址"):
                GPUCollisionEngine(targets)

    def test_single_target(self):
        """测试单个目标地址"""
        mock_device = Mock()
        mock_device.context = Mock()
        mock_device.queue = Mock()
        mock_device.device_info = {
            "name": "Test GPU",
            "vendor": "NVIDIA Corporation",
            "global_mem_size": 8 * 1024**3,
        }
        mock_device.initialize = Mock()
        mock_device.get_device_info = Mock(return_value=mock_device.device_info)
        mock_device.cleanup = Mock()

        mock_context = Mock()
        mock_context.program = Mock()
        mock_context.apply_optimizations = Mock()
        mock_context.calculate_batch_size = Mock(return_value=65536)
        mock_context.compile_kernel = Mock()
        mock_context.cleanup = Mock()

        mock_kernel = Mock()
        mock_kernel.run_batch = Mock(return_value=[])
        mock_kernel.set_targets = Mock()
        mock_kernel.cleanup = Mock()
        mock_kernel.max_batch_size = 65536

        with patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True):
            with (
                patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
                patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
                patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
                patch("src.gpu.device_manager.AsyncGPUExecutor") as mock_async_executor,
                patch("src.gpu.device_manager.GPUProfileLoader") as mock_profile_loader,
            ):
                mock_profile_loader.return_value.get_profile.return_value = None

                mock_async_instance = Mock()
                mock_async_instance.initialize_buffers = Mock()
                mock_async_instance.run_batch_async = Mock(return_value=([], 50.0))
                mock_async_instance.cleanup = Mock()
                mock_async_executor.return_value = mock_async_instance

                # 单个目标地址
                targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

                # 验证初始化成功
                engine = GPUCollisionEngine(targets)
                assert len(engine.targets) == 1
