"""工具模块测试 — exceptions, exception_handler, encoding_utils"""

import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.exceptions import (  # noqa: E402
    CollisionError,
    ConfigError,
    ValidationError,
    KeyGenerationError,
    AddressGenerationError,
    CheckpointError,
    DeduplicationError,
    TargetResolutionError,
    CryptoBackendError,
)
from src.utils.exception_handler import ExceptionHandler  # noqa: E402


class TestCollisionError(unittest.TestCase):
    """CollisionError 基类测试"""

    def test_basic_error(self):
        err = CollisionError("test message")
        self.assertEqual(err.message, "test message")
        self.assertEqual(err.error_code, CollisionError.UNKNOWN_ERROR)
        self.assertIn("1000", str(err))
        self.assertIn("test message", str(err))

    def test_custom_error_code(self):
        err = CollisionError("test", error_code=9999)
        self.assertEqual(err.error_code, 9999)
        self.assertIn("9999", str(err))

    def test_with_context(self):
        err = CollisionError("test", context={"key": "value", "id": 42})
        self.assertEqual(err.context, {"key": "value", "id": 42})
        self.assertIn("key=value", str(err))

    def test_with_original_error(self):
        original = ValueError("original")
        err = CollisionError("wrapped", original_error=original)
        self.assertIs(err.original_error, original)
        d = err.to_dict()
        self.assertIn("original_error", d)
        self.assertEqual(d["original_error"], "original")

    def test_to_dict(self):
        err = CollisionError("test", error_code=1004, context={"a": 1})
        d = err.to_dict()
        self.assertEqual(d["error_code"], 1004)
        self.assertEqual(d["message"], "test")
        self.assertEqual(d["context"], {"a": 1})
        self.assertEqual(d["error_type"], "CollisionError")

    def test_to_dict_without_original(self):
        err = CollisionError("test")
        d = err.to_dict()
        self.assertNotIn("original_error", d)

    def test_error_code_constants(self):
        self.assertEqual(CollisionError.UNKNOWN_ERROR, 1000)
        self.assertEqual(CollisionError.KEY_GENERATION_ERROR, 1001)
        self.assertEqual(CollisionError.ADDRESS_GENERATION_ERROR, 1002)
        self.assertEqual(CollisionError.CONFIG_ERROR, 1003)
        self.assertEqual(CollisionError.VALIDATION_ERROR, 1004)
        self.assertEqual(CollisionError.CHECKPOINT_ERROR, 1005)
        self.assertEqual(CollisionError.DEDUPLICATION_ERROR, 1006)
        self.assertEqual(CollisionError.TARGET_RESOLUTION_ERROR, 1007)
        self.assertEqual(CollisionError.CRYPTO_BACKEND_ERROR, 1008)


class TestExceptionSubclasses(unittest.TestCase):
    """所有异常子类测试"""

    def test_config_error(self):
        err = ConfigError("config error")
        self.assertEqual(err.error_code, CollisionError.CONFIG_ERROR)
        self.assertIsInstance(err, CollisionError)

    def test_validation_error(self):
        err = ValidationError("validation error")
        self.assertEqual(err.error_code, CollisionError.VALIDATION_ERROR)

    def test_key_generation_error(self):
        err = KeyGenerationError("key error")
        self.assertEqual(err.error_code, CollisionError.KEY_GENERATION_ERROR)

    def test_address_generation_error(self):
        err = AddressGenerationError("addr error")
        self.assertEqual(err.error_code, CollisionError.ADDRESS_GENERATION_ERROR)

    def test_checkpoint_error(self):
        err = CheckpointError("checkpoint error")
        self.assertEqual(err.error_code, CollisionError.CHECKPOINT_ERROR)

    def test_deduplication_error(self):
        err = DeduplicationError("dedup error")
        self.assertEqual(err.error_code, CollisionError.DEDUPLICATION_ERROR)

    def test_target_resolution_error(self):
        err = TargetResolutionError("target error")
        self.assertEqual(err.error_code, CollisionError.TARGET_RESOLUTION_ERROR)

    def test_crypto_backend_error(self):
        err = CryptoBackendError("crypto error")
        self.assertEqual(err.error_code, CollisionError.CRYPTO_BACKEND_ERROR)

    def test_subclass_with_custom_code(self):
        err = ConfigError("custom", error_code=999)
        self.assertEqual(err.error_code, 999)
        self.assertIsInstance(err, CollisionError)

    def test_subclass_with_context(self):
        err = ValidationError("v", context={"field": "name"})
        self.assertIn("field", str(err))

    def test_subclass_to_dict(self):
        err = KeyGenerationError("key gen failed", context={"reason": "low entropy"})
        d = err.to_dict()
        self.assertEqual(d["error_type"], "KeyGenerationError")


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
            raise KeyboardInterrupt()
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
