"""异常处理类单元测试 - CollisionError及其子类"""


import pytest

from src.utils.exceptions import (
    AddressGenerationError,
    CheckpointError,
    CollisionError,
    ConfigError,
    CryptoBackendError,
    DeduplicationError,
    KeyGenerationError,
    TargetResolutionError,
    ValidationError,
)


class TestCollisionErrorBase:
    """CollisionError 基类测试"""

    def test_basic_exception(self):
        """基础异常创建"""
        error = CollisionError("Test error")
        assert error.message == "Test error"
        assert error.error_code == 1000
        assert error.context == {}
        assert error.original_error is None

    def test_exception_with_error_code(self):
        """带错误码的异常"""
        error = CollisionError("Custom error", error_code=2001)
        assert error.error_code == 2001

    def test_exception_with_context(self):
        """带上下文信息的异常"""
        context = {"file": "test.txt", "line": 42}
        error = CollisionError("Context error", context=context)
        assert error.context == context
        assert error.context["file"] == "test.txt"
        assert error.context["line"] == 42

    def test_exception_with_original_error(self):
        """带原始异常的异常"""
        original = ValueError("Original error")
        error = CollisionError("Wrapped error", original_error=original)
        assert error.original_error == original
        assert isinstance(error.original_error, ValueError)

    def test_exception_str_representation(self):
        """异常字符串表示"""
        error = CollisionError("Test message")
        str_repr = str(error)
        assert "[1000]" in str_repr
        assert "Test message" in str_repr

    def test_exception_with_context_str(self):
        """带上下文的字符串表示"""
        context = {"key": "value"}
        error = CollisionError("Context test", context=context)
        str_repr = str(error)
        assert "key=value" in str_repr

    def test_exception_to_dict(self):
        """异常转换为字典"""
        error = CollisionError("Dict test", error_code=1234)
        error_dict = error.to_dict()

        assert error_dict["error_code"] == 1234
        assert error_dict["message"] == "Dict test"
        assert error_dict["error_type"] == "CollisionError"
        assert error_dict["context"] == {}

    def test_exception_to_dict_with_context(self):
        """带上下文的字典转换"""
        context = {"info": "details"}
        error = CollisionError("Dict context", context=context)
        error_dict = error.to_dict()

        assert error_dict["context"] == context
        assert error_dict["context"]["info"] == "details"

    def test_exception_to_dict_with_original(self):
        """带原始异常的字典转换"""
        original = RuntimeError("Original")
        error = CollisionError("Wrapped", original_error=original)
        error_dict = error.to_dict()

        assert "original_error" in error_dict
        assert error_dict["original_error"] == "Original"

    def test_exception_inheritance(self):
        """异常继承自Exception"""
        error = CollisionError("Test")
        assert isinstance(error, Exception)

    def test_exception_can_be_raised(self):
        """异常可以被抛出和捕获"""
        with pytest.raises(CollisionError) as exc_info:
            raise CollisionError("Raised error")

        assert exc_info.value.message == "Raised error"
        assert exc_info.value.error_code == 1000


class TestConfigError:
    """ConfigError 测试"""

    def test_config_error_default_code(self):
        """ConfigError 默认错误码"""
        error = ConfigError("Config failed")
        assert error.error_code == 1003

    def test_config_error_custom_code(self):
        """ConfigError 自定义错误码"""
        error = ConfigError("Custom config error", error_code=3001)
        assert error.error_code == 3001

    def test_config_error_context(self):
        """ConfigError 上下文信息"""
        context = {"key": "invalid_key", "value": "invalid_value"}
        error = ConfigError("Invalid config", context=context)
        assert error.context["key"] == "invalid_key"

    def test_config_error_inheritance(self):
        """ConfigError 继承自 CollisionError"""
        error = ConfigError("Test")
        assert isinstance(error, CollisionError)
        assert isinstance(error, Exception)


class TestValidationError:
    """ValidationError 测试"""

    def test_validation_error_default_code(self):
        """ValidationError 默认错误码"""
        error = ValidationError("Validation failed")
        assert error.error_code == 1004

    def test_validation_error_context(self):
        """ValidationError 上下文信息"""
        context = {"field": "email", "reason": "invalid format"}
        error = ValidationError("Validation error", context=context)
        assert error.context["field"] == "email"

    def test_validation_error_inheritance(self):
        """ValidationError 继承自 CollisionError"""
        error = ValidationError("Test")
        assert isinstance(error, CollisionError)


class TestKeyGenerationError:
    """KeyGenerationError 测试"""

    def test_key_generation_error_default_code(self):
        """KeyGenerationError 默认错误码"""
        error = KeyGenerationError("Key generation failed")
        assert error.error_code == 1001

    def test_key_generation_error_context(self):
        """KeyGenerationError 上下文信息"""
        context = {"key_length": 16}
        error = KeyGenerationError("Invalid key length", context=context)
        assert error.context["key_length"] == 16

    def test_key_generation_error_inheritance(self):
        """KeyGenerationError 继承自 CollisionError"""
        error = KeyGenerationError("Test")
        assert isinstance(error, CollisionError)


class TestAddressGenerationError:
    """AddressGenerationError 测试"""

    def test_address_generation_error_default_code(self):
        """AddressGenerationError 默认错误码"""
        error = AddressGenerationError("Address generation failed")
        assert error.error_code == 1002

    def test_address_generation_error_context(self):
        """AddressGenerationError 上下文信息"""
        context = {"public_key": "invalid_key"}
        error = AddressGenerationError("Invalid public key", context=context)
        assert error.context["public_key"] == "invalid_key"

    def test_address_generation_error_inheritance(self):
        """AddressGenerationError 继承自 CollisionError"""
        error = AddressGenerationError("Test")
        assert isinstance(error, CollisionError)


class TestCheckpointError:
    """CheckpointError 测试"""

    def test_checkpoint_error_default_code(self):
        """CheckpointError 默认错误码"""
        error = CheckpointError("Checkpoint failed")
        assert error.error_code == 1005

    def test_checkpoint_error_context(self):
        """CheckpointError 上下文信息"""
        context = {"checkpoint_file": "checkpoint.json"}
        error = CheckpointError("Load failed", context=context)
        assert error.context["checkpoint_file"] == "checkpoint.json"

    def test_checkpoint_error_inheritance(self):
        """CheckpointError 继承自 CollisionError"""
        error = CheckpointError("Test")
        assert isinstance(error, CollisionError)


class TestDeduplicationError:
    """DeduplicationError 测试"""

    def test_deduplication_error_default_code(self):
        """DeduplicationError 默认错误码"""
        error = DeduplicationError("Deduplication failed")
        assert error.error_code == 1006

    def test_deduplication_error_context(self):
        """DeduplicationError 上下文信息"""
        context = {"filter_size": 1000000}
        error = DeduplicationError("Filter full", context=context)
        assert error.context["filter_size"] == 1000000

    def test_deduplication_error_inheritance(self):
        """DeduplicationError 继承自 CollisionError"""
        error = DeduplicationError("Test")
        assert isinstance(error, CollisionError)


class TestTargetResolutionError:
    """TargetResolutionError 测试"""

    def test_target_resolution_error_default_code(self):
        """TargetResolutionError 默认错误码"""
        error = TargetResolutionError("Target resolution failed")
        assert error.error_code == 1007

    def test_target_resolution_error_context(self):
        """TargetResolutionError 上下文信息"""
        context = {"target": "invalid_address"}
        error = TargetResolutionError("Invalid target", context=context)
        assert error.context["target"] == "invalid_address"

    def test_target_resolution_error_inheritance(self):
        """TargetResolutionError 继承自 CollisionError"""
        error = TargetResolutionError("Test")
        assert isinstance(error, CollisionError)


class TestCryptoBackendError:
    """CryptoBackendError 测试"""

    def test_crypto_backend_error_default_code(self):
        """CryptoBackendError 默认错误码"""
        error = CryptoBackendError("Crypto backend failed")
        assert error.error_code == 1008

    def test_crypto_backend_error_context(self):
        """CryptoBackendError 上下文信息"""
        context = {"backend": "coincurve"}
        error = CryptoBackendError("Backend error", context=context)
        assert error.context["backend"] == "coincurve"

    def test_crypto_backend_error_with_original(self):
        """CryptoBackendError 带原始异常"""
        original = ImportError("No module named coincurve")
        error = CryptoBackendError("Backend import failed", original_error=original)
        assert error.original_error == original

    def test_crypto_backend_error_inheritance(self):
        """CryptoBackendError 继承自 CollisionError"""
        error = CryptoBackendError("Test")
        assert isinstance(error, CollisionError)


class TestExceptionErrorCodes:
    """错误码唯一性测试"""

    def test_error_codes_are_unique(self):
        """所有错误码应该唯一"""
        error_codes = [
            CollisionError.UNKNOWN_ERROR,
            CollisionError.KEY_GENERATION_ERROR,
            CollisionError.ADDRESS_GENERATION_ERROR,
            CollisionError.CONFIG_ERROR,
            CollisionError.VALIDATION_ERROR,
            CollisionError.CHECKPOINT_ERROR,
            CollisionError.DEDUPLICATION_ERROR,
            CollisionError.TARGET_RESOLUTION_ERROR,
            CollisionError.CRYPTO_BACKEND_ERROR,
        ]
        # 检查是否有重复
        assert len(error_codes) == len(set(error_codes))

    def test_error_codes_are_in_range(self):
        """错误码应该在合理范围内"""
        error_codes = [
            CollisionError.UNKNOWN_ERROR,
            CollisionError.KEY_GENERATION_ERROR,
            CollisionError.ADDRESS_GENERATION_ERROR,
            CollisionError.CONFIG_ERROR,
            CollisionError.VALIDATION_ERROR,
            CollisionError.CHECKPOINT_ERROR,
            CollisionError.DEDUPLICATION_ERROR,
            CollisionError.TARGET_RESOLUTION_ERROR,
            CollisionError.CRYPTO_BACKEND_ERROR,
        ]
        for code in error_codes:
            assert code >= 1000
            assert code < 2000


class TestExceptionIntegration:
    """异常集成测试"""

    def test_exception_chaining(self):
        """异常链式传递"""
        try:
            try:
                raise ValueError("Root cause")
            except ValueError as e:
                raise ConfigError(
                    "Configuration failed",
                    original_error=e,
                    context={"config_key": "test"},
                ) from e
        except ConfigError as e:
            assert e.error_code == 1003
            assert isinstance(e.original_error, ValueError)
            assert e.original_error.args[0] == "Root cause"
            assert e.context["config_key"] == "test"

    def test_multiple_exceptions_handling(self):
        """多种异常处理"""
        exceptions = [
            ConfigError("Config error"),
            ValidationError("Validation error"),
            KeyGenerationError("Key error"),
            AddressGenerationError("Address error"),
            CheckpointError("Checkpoint error"),
            DeduplicationError("Dedup error"),
            TargetResolutionError("Target error"),
            CryptoBackendError("Crypto error"),
        ]

        error_codes = set()
        for exc in exceptions:
            assert isinstance(exc, CollisionError)
            error_codes.add(exc.error_code)

        # 验证所有异常都有不同的错误码
        assert len(error_codes) == len(exceptions)

    def test_exception_serialization_roundtrip(self):
        """异常序列化往返测试"""
        original_exc = RuntimeError("Original error")
        error = CryptoBackendError(
            "Crypto operation failed",
            error_code=1008,
            context={"operation": "sign", "backend": "coincurve"},
            original_error=original_exc,
        )

        # 转换为字典
        error_dict = error.to_dict()

        # 验证字典包含所有必要信息
        assert error_dict["error_code"] == 1008
        assert error_dict["message"] == "Crypto operation failed"
        assert error_dict["error_type"] == "CryptoBackendError"
        assert error_dict["context"]["operation"] == "sign"
        assert error_dict["context"]["backend"] == "coincurve"
        assert error_dict["original_error"] == "Original error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
