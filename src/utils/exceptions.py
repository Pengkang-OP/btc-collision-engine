"""异常处理类

提供统一的异常基类和错误码体系，支持错误上下文信息。
"""

from typing import Any


class CollisionError(Exception):
    """
    碰撞引擎异常基类

    所有自定义异常的基类，提供错误码和上下文信息支持。

    属性:
        message: 错误描述信息
        error_code: 错误码（整数）
        context: 错误上下文信息字典
        original_error: 原始异常（如果有）
    """

    # 错误码定义
    UNKNOWN_ERROR = 1000
    KEY_GENERATION_ERROR = 1001
    ADDRESS_GENERATION_ERROR = 1002
    CONFIG_ERROR = 1003
    VALIDATION_ERROR = 1004
    CHECKPOINT_ERROR = 1005
    DEDUPLICATION_ERROR = 1006
    TARGET_RESOLUTION_ERROR = 1007
    CRYPTO_BACKEND_ERROR = 1008

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """
        初始化异常

        参数:
            message: 错误描述信息
            error_code: 错误码，默认使用类定义的 UNKNOWN_ERROR
            context: 错误上下文信息字典
            original_error: 导致此异常的原始异常
        """
        self.message = message
        self.error_code = error_code or self.UNKNOWN_ERROR
        self.context = context or {}
        self.original_error = original_error

        # 构建完整的错误消息
        full_message = f"[{self.error_code}] {message}"
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            full_message += f" (上下文: {context_str})"

        super().__init__(full_message)

    def __str__(self) -> str:
        """返回格式化的错误消息"""
        return self.args[0] if self.args else f"[{self.error_code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """
        将异常转换为字典格式，便于序列化

        返回:
            包含异常信息的字典
        """
        result = {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "error_type": self.__class__.__name__,
        }
        if self.original_error:
            result["original_error"] = str(self.original_error)
        return result


class ConfigError(CollisionError):
    """配置错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.CONFIG_ERROR, context, original_error)


class ValidationError(CollisionError):
    """验证错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.VALIDATION_ERROR, context, original_error)


class KeyGenerationError(CollisionError):
    """密钥生成错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.KEY_GENERATION_ERROR, context, original_error)


class AddressGenerationError(CollisionError):
    """地址生成错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(
            message, error_code or self.ADDRESS_GENERATION_ERROR, context, original_error
        )


class CheckpointError(CollisionError):
    """断点管理错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.CHECKPOINT_ERROR, context, original_error)


class DeduplicationError(CollisionError):
    """去重过滤错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.DEDUPLICATION_ERROR, context, original_error)


class TargetResolutionError(CollisionError):
    """目标解析错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(
            message, error_code or self.TARGET_RESOLUTION_ERROR, context, original_error
        )


class CryptoBackendError(CollisionError):
    """加密后端错误异常"""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.CRYPTO_BACKEND_ERROR, context, original_error)
