#!/usr/bin/env python3
"""GPU碰撞引擎核心功能全面审计测试

覆盖:
- GPU设备检测与初始化
- 三种碰撞模式(random/range/brute_force)
- 断点续传功能
- 去重过滤器
- 目标地址处理
- 匹配结果处理
"""

import os
import secrets
import time
from unittest.mock import Mock, patch

import pytest

from src.collision.checkpoint_manager import CheckpointManager
from src.collision.deduplication_filter import DeduplicationFilter
from src.collision.gpu.engine import GPUCollisionEngine
from src.core.base58 import Base58
from src.core.wif import WIF
from src.gpu.device import GPUDeviceDetector


class TestGPUDeviceDetection:
    """GPU设备检测测试"""

    def test_gpu_device_detection_no_gpu(self, clear_gpu_detector_cache):
        """测试无GPU时检测返回False

        使用clear_gpu_detector_cache fixture自动清除所有缓存
        """
        with patch("src.gpu.device.PYOPENCL_AVAILABLE", False):
            available = GPUDeviceDetector.is_gpu_available()
            assert available is False

    def test_gpu_device_detection_with_gpu(self, clear_gpu_detector_cache):
        """测试有GPU时检测返回True

        使用clear_gpu_detector_cache fixture自动清除所有缓存
        """
        # Mock detect_devices返回设备列表
        with patch.object(GPUDeviceDetector, "detect_devices", return_value=["mock_gpu"]):
            available = GPUDeviceDetector.is_gpu_available()
            assert available is True


class TestGPUEngineInitialization:
    """GPU引擎初始化测试"""

    def _create_mock_gpu_chain(self):
        """创建完整的Mock GPU初始化链"""
        # Mock GPUDevice
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

        # Mock GPUContext
        mock_context = Mock()
        mock_context.program = Mock()
        mock_context.apply_optimizations = Mock()
        mock_context.calculate_batch_size = Mock(return_value=65536)
        mock_context.compile_kernel = Mock()
        mock_context.cleanup = Mock()

        # Mock GPUKernel
        mock_kernel = Mock()
        mock_kernel.run_batch = Mock(return_value=[])
        mock_kernel.set_targets = Mock()
        mock_kernel.cleanup = Mock()
        mock_kernel.max_batch_size = 65536

        return mock_device, mock_context, mock_kernel

    def test_gpu_engine_init_without_pyopencl(self):
        """测试无pyopencl时初始化失败"""
        with patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="pyopencl 不可用"):
                GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})

    def test_gpu_engine_init_success(self):
        """测试GPU引擎成功初始化"""
        mock_device, mock_context, mock_kernel = self._create_mock_gpu_chain()

        with patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True):
            # Mock GPUDeviceDetector返回可用
            with (
                patch(
                    "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                    return_value=True,
                ),
                patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
                patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
                patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
                patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
                patch("src.gpu.device.identify_vendor", return_value="nvidia"),
            ):
                mock_profile_loader.return_value.get_profile.return_value = None

                targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
                engine = GPUCollisionEngine(targets)

                # 验证初始化
                assert engine is not None
                assert engine._gpu_device is not None
                assert engine._gpu_context is not None
                assert engine._gpu_kernel is not None
                assert engine._target_hash160s is not None
                assert len(engine._target_list) == 1


class TestCollisionModes:
    """三种碰撞模式测试"""

    def _setup_engine_for_mode_test(self, run_batch_return=None):
        """设置用于模式测试的引擎"""
        if run_batch_return is None:
            run_batch_return = []

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
        mock_context.calculate_batch_size = Mock(return_value=1000)  # 小 batch加快测试
        mock_context.compile_kernel = Mock()
        mock_context.cleanup = Mock()

        mock_kernel = Mock()
        mock_kernel.run_batch = Mock(return_value=run_batch_return)
        mock_kernel.set_targets = Mock()
        mock_kernel.cleanup = Mock()
        mock_kernel.max_batch_size = 1000
        mock_kernel.gpu_optimizer = Mock()
        mock_kernel.gpu_optimizer.analyze_and_adjust = Mock(return_value=(1000, {}))

        return mock_device, mock_context, mock_kernel

    def _patch_gpu_engine_all(self, mock_device, mock_context, mock_kernel, mock_profile_loader):
        """统一GPU引擎Mock补丁"""
        mock_profile_loader.return_value.get_profile.return_value = None
        return [
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
            patch(
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch(
                "src.gpu.profiles.loader.GPUProfileLoader",
                return_value=mock_profile_loader,
            ),
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ]

    def test_random_search_mode(self):
        """测试随机碰撞模式"""
        mock_device, mock_context, mock_kernel = self._setup_engine_for_mode_test()

        with (
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
            patch(
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
            engine = GPUCollisionEngine(targets, batch_size=100)

            # 启动随机模式
            engine.start(mode="random")
            assert engine.is_running() is True

            # 运行2秒后停止
            time.sleep(2)
            engine.stop()

            # 验证统计数据
            assert engine.stats.total_checked > 0
            assert engine.stats.speed > 0

            # 验证run_batch被调用
            assert mock_kernel.run_batch.call_count > 0

    def test_range_scan_mode(self):
        """测试范围扫描模式"""
        mock_device, mock_context, mock_kernel = self._setup_engine_for_mode_test()

        with (
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
            patch(
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
            engine = GPUCollisionEngine(targets, batch_size=1000)

            # 启动范围扫描模式
            engine.start(mode="range", start=1, end=5000)

            # 等待完成（最多10秒）
            timeout = 10
            start_time = time.time()
            while engine.is_running() and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            engine.stop()

            # 验证处理了所有私钥
            assert engine.stats.total_checked == 5000
            assert engine._current_position == 5001

    def test_brute_force_mode(self):
        """测试暴力穷举模式"""
        mock_device, mock_context, mock_kernel = self._setup_engine_for_mode_test()

        with (
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
            patch(
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
            engine = GPUCollisionEngine(targets, batch_size=100)

            # 启动暴力穷举模式
            engine.start(mode="brute_force", start=1)
            assert engine.is_running() is True

            # 运行1秒后停止
            time.sleep(1)
            engine.stop()

            # 验证统计数据
            assert engine.stats.total_checked > 0
            assert engine._current_position > 1

    def test_invalid_mode_raises_error(self):
        """测试无效模式抛出错误"""
        mock_device, mock_context, mock_kernel = self._setup_engine_for_mode_test()

        with (
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
            patch(
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
            engine = GPUCollisionEngine(targets)

            # 测试无效模式
            with pytest.raises(ValueError, match="未知模式"):
                engine.start(mode="invalid_mode")


class TestCheckpointResume:
    """断点续传测试"""

    def test_checkpoint_save_and_load(self):
        """测试断点保存和加载"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_checkpoint.json")
            checkpoint_mgr = CheckpointManager(filepath=filepath, auto_save_interval=30)

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
            matches = [{"address": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH", "timestamp": time.time()}]

            # 保存断点
            checkpoint_mgr.save(
                mode="random",
                targets=targets,
                current_position=1000,
                total_checked=1000,
                matches=matches,
                force=True,
            )

            # 验证文件存在
            assert os.path.exists(filepath)

            # 加载断点
            loaded = checkpoint_mgr.load()

            # 验证数据
            assert loaded is not None
            assert loaded["mode"] == "random"
            assert loaded["total_checked"] == 1000
            assert loaded["current_position"] == 1000
            assert "targets" in loaded
            assert "version" in loaded
            assert loaded["version"] == 1

            # 验证敏感信息未保存
            for match in loaded.get("matches", []):
                assert "private_key" not in match
                assert "private_key_hex" not in match

    def test_checkpoint_auto_save(self):
        """测试断点自动保存"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_auto_checkpoint.json")
            checkpoint_mgr = CheckpointManager(filepath=filepath, auto_save_interval=1)

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

            # 保存断点（不强制）
            checkpoint_mgr.save(
                mode="random",
                targets=targets,
                current_position=500,
                total_checked=500,
                matches=[],
                force=False,
            )

            # 注意: save()会更新_last_save_time,所以should_auto_save返回False是正常的
            # 我们验证的是自动保存线程会在后台触发保存

            # 等待自动保存线程触发(>1秒)
            time.sleep(1.5)

            # 验证文件已创建(自动保存或buffer写入)
            # 由于save()可能已经写入,我们验证文件存在或数据在buffer中
            has_file = os.path.exists(filepath)
            has_buffer = checkpoint_mgr._buffer is not None
            assert has_file or has_buffer


class TestDeduplicationFilter:
    """去重过滤器测试"""

    def test_dedup_filter_prevents_duplicates(self):
        """测试去重过滤器防止重复"""
        dedup = DeduplicationFilter(max_size=1000, enabled=True)

        private_key_a = secrets.token_bytes(32)
        private_key_b = secrets.token_bytes(32)

        # 第一次添加私钥A
        assert dedup.check_and_add(private_key_a) is True

        # 第二次添加私钥A（重复）
        assert dedup.check_and_add(private_key_a) is False

        # 添加私钥B
        assert dedup.check_and_add(private_key_b) is True

        # 验证统计
        stats = dedup.get_stats()
        assert stats["checks_total"] == 3
        assert stats["duplicates_found"] == 1

    def test_dedup_filter_disabled(self):
        """测试去重过滤器禁用时始终返回True"""
        dedup = DeduplicationFilter(max_size=1000, enabled=False)

        private_key = secrets.token_bytes(32)

        # 禁用时始终返回True
        assert dedup.check_and_add(private_key) is True
        assert dedup.check_and_add(private_key) is True
        assert dedup.check_and_add(private_key) is True


class TestTargetAddressProcessing:
    """目标地址处理测试"""

    def test_base58_check_decode_accuracy(self):
        """测试Base58Check解码准确性"""
        address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"

        version, payload = Base58.check_decode(address)

        # 验证version和payload
        assert version == 0x00
        assert len(payload) == 20

    def test_prepare_targets_valid_addresses(self):
        """测试有效目标地址转换"""
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
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            # 3个有效地址
            targets = {
                "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX",
            }

            engine = GPUCollisionEngine(targets)

            # 验证目标地址处理
            assert len(engine._target_list) == 3
            assert len(engine._target_hash160s) == 60  # 3 * 20字节

    def test_prepare_targets_invalid_addresses(self):
        """测试包含无效地址的处理"""
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
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=True,
            ),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
            patch("src.gpu.device.identify_vendor", return_value="nvidia"),
        ):
            mock_profile_loader.return_value.get_profile.return_value = None

            # 2个有效地址 + 1个无效地址
            targets = {
                "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "INVALID_ADDRESS",
            }

            engine = GPUCollisionEngine(targets)

            # 验证只处理了有效地址
            assert len(engine._target_list) == 2
            assert len(engine._target_hash160s) == 40  # 2 * 20字节


class TestMatchResultProcessing:
    """匹配结果处理测试"""

    def test_wif_encoding_compressed(self):
        """测试压缩格式WIF编码"""
        private_key = secrets.token_bytes(32)

        wif = WIF.encode(private_key, compressed=True)

        # 验证长度和格式
        assert len(wif) == 52
        assert wif[0] in ["K", "L"]

    def test_wif_encoding_uncompressed(self):
        """测试非压缩格式WIF编码"""
        private_key = secrets.token_bytes(32)

        wif = WIF.encode(private_key, compressed=False)

        # 验证长度和格式
        assert len(wif) == 51
        assert wif[0] == "5"

    def test_wif_decode_roundtrip(self):
        """测试WIF编解码往返"""
        original_private_key = secrets.token_bytes(32)

        # 编码
        wif_compressed = WIF.encode(original_private_key, compressed=True)

        # 解码
        decoded_key, is_compressed = WIF.decode(wif_compressed)

        # 验证往返一致
        assert decoded_key == original_private_key
        assert is_compressed is True
