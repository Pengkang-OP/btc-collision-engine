"""工具模块测试 — exception_handler, exceptions 基础验证"""

import unittest
from unittest.mock import Mock

from src.utils.exception_handler import ExceptionHandler
from src.utils.exceptions import (
    AddressGenerationError,
    CheckpointError,
    CollisionEngineError,
    ConfigError,
    CryptoBackendError,
    DeduplicationError,
    GPUError,
    KeyGenerationError,
    TargetResolutionError,
    ValidationError,
)


class TestExceptionBasics(unittest.TestCase):
    """异常类基础存在性验证 — 对齐 src/utils/exceptions.py 真实 API"""

    def test_collision_engine_error_is_base(self):
        err = CollisionEngineError("test")
        self.assertIsInstance(err, Exception)
        self.assertEqual(str(err), "test")

    def test_collision_error_alias(self):
        """CollisionError 是 CollisionEngineError 的别名"""
        from src.utils.exceptions import CollisionError

        err = CollisionError("test")
        self.assertIsInstance(err, CollisionEngineError)

    def test_key_generation_error_has_custom_init(self):
        """KeyGenerationError 有 error_code 和 context"""
        err = KeyGenerationError("key fail", error_code=2, context={"reason": "entropy"})
        self.assertEqual(str(err), "key fail")
        self.assertEqual(err.error_code, 2)
        self.assertEqual(err.context, {"reason": "entropy"})

    def test_key_generation_error_defaults(self):
        err = KeyGenerationError()
        self.assertEqual(err.error_code, 0)
        self.assertEqual(err.context, {})

    def test_all_subclasses_exist(self):
        """验证所有异常子类可实例化"""
        for cls in [
            AddressGenerationError,
            CheckpointError,
            ConfigError,
            CryptoBackendError,
            DeduplicationError,
            GPUError,
            TargetResolutionError,
            ValidationError,
        ]:
            err = cls("test")
            self.assertIsInstance(err, CollisionEngineError)
            self.assertEqual(str(err), "test")


class TestExceptionHandler(unittest.TestCase):
    """ExceptionHandler 统一异常处理器测试"""

    def test_handle_engine_error_runtime(self):
        stats = Mock()
        ExceptionHandler.handle_engine_error("CPU", RuntimeError("test error"), stats)
        stats.record_worker_error.assert_called_once()

    def test_handle_engine_error_value_error(self):
        stats = Mock()
        ExceptionHandler.handle_engine_error("GPU", ValueError("bad value"), stats, context="批处理")
        stats.record_worker_error.assert_called_once()

    def test_handle_engine_error_memory_error(self):
        stats = Mock()
        stats.record_error = Mock()
        ExceptionHandler.handle_engine_error("CPU", MemoryError("oom"), stats)
        stats.record_error.assert_called_once()

    def test_handle_engine_error_import_error(self):
        stats = Mock()
        ExceptionHandler.handle_engine_error("GPU", ImportError("no module"), stats)
        stats.record_worker_error.assert_called_once()

    def test_handle_engine_error_os_error(self):
        stats = Mock()
        ExceptionHandler.handle_engine_error("CPU", OSError("io error"), stats)
        stats.record_worker_error.assert_called_once()

    def test_handle_engine_error_unknown(self):
        stats = Mock()
        ExceptionHandler.handle_engine_error("CPU", TypeError("type error"), stats)
        stats.record_worker_error.assert_called_once()

    def test_handle_engine_error_keyboard_interrupt_reraises(self):
        try:
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            with self.assertRaises(KeyboardInterrupt):
                ExceptionHandler.handle_engine_error("CPU", KeyboardInterrupt())

    def test_handle_engine_error_no_stats(self):
        ExceptionHandler.handle_engine_error("CPU", RuntimeError("test"))

    def test_handle_gpu_error_runtime(self):
        result = ExceptionHandler.handle_gpu_error("随机碰撞", RuntimeError("test"))
        self.assertTrue(result)

    def test_handle_gpu_error_value_error(self):
        result = ExceptionHandler.handle_gpu_error("随机碰撞", ValueError("bad"))
        self.assertTrue(result)

    def test_handle_gpu_error_memory_error(self):
        result = ExceptionHandler.handle_gpu_error("随机碰撞", MemoryError("oom"))
        self.assertTrue(result)

    def test_handle_gpu_error_import_error(self):
        result = ExceptionHandler.handle_gpu_error("随机碰撞", ImportError("no pyopencl"))
        self.assertTrue(result)

    def test_handle_gpu_error_os_error(self):
        result = ExceptionHandler.handle_gpu_error("随机碰撞", OSError("io"))
        self.assertTrue(result)

    def test_handle_gpu_error_unknown(self):
        result = ExceptionHandler.handle_gpu_error("随机碰撞", TypeError("unknown"))
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
