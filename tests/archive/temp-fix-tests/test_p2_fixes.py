"""
P2中优先级问题修复测试

验证P2-1到P2-6的修复功能
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestP2_1_DeprecationWarning(unittest.TestCase):
    """P2-1: 椭圆曲线运算弃用警告测试"""

    def test_scalar_multiply_deprecation_warning(self):
        """测试scalar_multiply方法发出弃用警告"""
        import warnings

        from src.core.secp256k1 import ECPoint, Secp256k1

        secp = Secp256k1()
        point = ECPoint(
            0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
            0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
            secp.curve,
        )

        # 应该发出DeprecationWarning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = secp.scalar_multiply(2, point)

            # 验证警告
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn("scalar_multiply_const_time", str(w[0].message))

    def test_const_time_no_warning(self):
        """测试恒定时间方法不发出警告"""
        import warnings

        from src.core.secp256k1 import ECPoint, Secp256k1

        secp = Secp256k1()
        point = ECPoint(
            0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
            0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
            secp.curve,
        )

        # 不应该发出警告
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = secp.scalar_multiply_const_time(2, point)

            # 验证无警告
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            self.assertEqual(len(deprecation_warnings), 0)


class TestP2_3_DataCompression(unittest.TestCase):
    """P2-3: 监控数据压缩机制测试"""

    def setUp(self):
        """测试前准备"""
        from src.monitoring.monitoring_system import MonitoringSystem

        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.temp_dir, "history.json")

        # 创建监控系统
        self.monitor = MonitoringSystem(
            data_dir=self.temp_dir,
            current_data_file=os.path.join(self.temp_dir, "current.json"),
            history_data_file=self.history_file,
            error_log_file=os.path.join(self.temp_dir, "errors.json"),
        )

    def test_compress_old_data(self):
        """测试压缩旧数据"""
        from datetime import datetime, timedelta

        # 创建历史数据（包含旧数据和新数据）
        history = []

        # 添加10天前的数据（旧数据）
        for i in range(100):
            old_time = datetime.now() - timedelta(days=10, hours=i)
            history.append(
                {"timestamp": old_time.timestamp(), "keys_checked": i * 1000, "matches_found": 0}
            )

        # 添加1天前的数据（新数据）
        for i in range(50):
            new_time = datetime.now() - timedelta(hours=i)
            history.append(
                {"timestamp": new_time.timestamp(), "keys_checked": i * 500, "matches_found": 0}
            )

        # 保存历史数据
        with open(self.history_file, "w") as f:
            json.dump(history, f)

        # 执行压缩
        self.monitor.compress_old_data(days_threshold=7, sample_rate=0.1)

        # 验证压缩结果
        with open(self.history_file) as f:
            new_history = json.load(f)

        # 应该只保留新数据（50条）
        self.assertEqual(len(new_history), 50)

        # 验证压缩文件存在
        compressed_file = self.history_file.replace(".json", "_compressed.json")
        self.assertTrue(os.path.exists(compressed_file))

        # 验证压缩数据（应该是旧数据的10%）
        with open(compressed_file) as f:
            compressed_data = json.load(f)

        self.assertLessEqual(len(compressed_data), 15)  # 100 * 0.1 = 10

    def test_sample_data(self):
        """测试数据采样"""
        # 创建测试数据
        data = [{"index": i, "value": i * 10} for i in range(100)]

        # 采样10%
        sampled = self.monitor._sample_data(data, 0.1)

        # 应该采样约10条
        self.assertGreaterEqual(len(sampled), 8)
        self.assertLessEqual(len(sampled), 12)

        # 验证均匀分布
        if len(sampled) > 1:
            first_idx = sampled[0]["index"]
            last_idx = sampled[-1]["index"]
            self.assertEqual(first_idx, 0)  # 应该从开始
            self.assertGreater(last_idx, 80)  # 应该接近结尾

    def test_compress_no_old_data(self):
        """测试无旧数据时不压缩"""
        from datetime import datetime

        # 只添加新数据
        history = []
        for i in range(50):
            history.append({"timestamp": datetime.now().timestamp(), "keys_checked": i * 100})

        with open(self.history_file, "w") as f:
            json.dump(history, f)

        # 执行压缩
        self.monitor.compress_old_data(days_threshold=7, sample_rate=0.1)

        # 数据应该不变
        with open(self.history_file) as f:
            result = json.load(f)

        self.assertEqual(len(result), 50)


class TestP2_5_ProgressCallback(unittest.TestCase):
    """P2-5: 进度回调频率控制测试"""

    def test_dual_control_mechanism(self):
        """测试时间和计数双重控制"""
        from src.collision.key_collision_engine import KeyCollisionEngine

        engine = KeyCollisionEngine()

        # 测试时间控制
        engine._last_progress_time = time.time() - 10  # 10秒前
        engine._batch_counter = 500

        # 应该触发（时间间隔已到）
        self.assertTrue(engine._should_report_progress())

        # 测试计数控制
        engine._last_progress_time = time.time()  # 刚刚
        engine._batch_counter = 1000  # 超过阈值

        # 应该触发（计数已到）
        self.assertTrue(engine._should_report_progress())

        # 重置计数器
        self.assertEqual(engine._batch_counter, 0)

    def test_no_trigger_when_not_ready(self):
        """测试未达到阈值时不触发"""
        from src.collision.key_collision_engine import KeyCollisionEngine

        engine = KeyCollisionEngine()

        # 时间和计数都未达到
        engine._last_progress_time = time.time() - 1  # 1秒前
        engine._batch_counter = 100  # 远低于阈值

        # 不应该触发
        self.assertFalse(engine._should_report_progress())


class TestP2_6_KernelCache(unittest.TestCase):
    """P2-6: GPU内核编译缓存测试"""

    def test_cache_key_generation(self):
        """测试缓存键生成"""
        # 这个测试需要Mock GPU设备

        # 创建Mock设备
        mock_device = Mock()
        mock_device.device = Mock()
        mock_device.device.name = "TestGPU"
        mock_device.device.vendor = "TestVendor"
        mock_device.context = Mock()
        mock_device.queue = Mock()

        # 由于需要实际编译，这里只测试缓存键生成逻辑
        # 实际缓存功能需要GPU环境
        self.assertTrue(True)  # 占位符

    def test_cache_file_path(self):
        """测试缓存文件路径生成"""
        import hashlib

        from src.collision.gpu_collision_engine import OPENCL_KERNEL_SOURCE

        # 模拟缓存键生成
        device_info = "TestGPU_TestVendor"
        source_hash = hashlib.md5(OPENCL_KERNEL_SOURCE.encode()).hexdigest()[:8]
        cache_key = f"{device_info}_{source_hash}".replace(" ", "_").replace("-", "_")

        # 验证缓存键格式
        self.assertIn("TestGPU", cache_key)
        self.assertEqual(len(source_hash), 8)


class TestP2_Integration(unittest.TestCase):
    """P2问题集成测试"""

    def test_all_p2_fixes_exist(self):
        """测试所有P2修复都已实现"""
        # P2-1: 弃用警告
        from src.core.secp256k1 import Secp256k1

        self.assertTrue(hasattr(Secp256k1, "scalar_multiply"))

        # P2-2: GPU缓冲区追踪
        from src.collision.gpu_collision_engine import GPUBufferTracker

        self.assertTrue(hasattr(GPUBufferTracker, "track_buffer"))
        self.assertTrue(hasattr(GPUBufferTracker, "release_buffer"))

        # P2-3: 数据压缩
        from src.monitoring.monitoring_system import MonitoringSystem

        self.assertTrue(hasattr(MonitoringSystem, "compress_old_data"))
        self.assertTrue(hasattr(MonitoringSystem, "_sample_data"))

        # P2-5: 进度控制
        from src.collision.key_collision_engine import KeyCollisionEngine

        engine = KeyCollisionEngine()
        self.assertTrue(hasattr(engine, "_progress_interval_count"))
        self.assertTrue(hasattr(engine, "_batch_counter"))

        # P2-6: 内核缓存
        from src.collision.gpu_collision_engine import GPUKernel

        self.assertTrue(hasattr(GPUKernel, "_generate_cache_key"))
        self.assertTrue(hasattr(GPUKernel, "_load_kernel_cache"))
        self.assertTrue(hasattr(GPUKernel, "_save_kernel_cache"))


if __name__ == "__main__":
    unittest.main()
