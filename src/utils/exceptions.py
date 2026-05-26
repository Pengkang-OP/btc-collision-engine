"""Custom exception classes for the collision engine.

Provides unified exception base class and error code system with context support.
"""

from __future__ import annotations

from typing import Any


class CollisionError(Exception):
    """Base exception for collision engine errors.

    Provides error codes and context information support.

    Attributes:
        message: Error description
        error_code: Integer error code
        context: Error context dictionary
        original_error: Original exception (if any)

    """

    # Error code definitions
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
        """Initialize exception.

        Args:
            message: Error description
            error_code: Error code, defaults to UNKNOWN_ERROR
            context: Error context dictionary
            original_error: Original exception that caused this error

        """
        self.message = message
        self.error_code = error_code if error_code is not None else self.UNKNOWN_ERROR
        self.context = context or {}
        self.original_error = original_error

        # Build complete error message
        full_message = f"[{self.error_code}] {message}"
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            full_message += f" (context: {context_str})"

        super().__init__(full_message)

    def __str__(self) -> str:
        """Return formatted error message."""
        return self.args[0] if self.args else f"[{self.error_code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary format for serialization.

        Returns:
            Dictionary containing exception information

        """
        result: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "error_type": self.__class__.__name__,
        }
        if self.original_error:
            result["original_error"] = str(self.original_error)
        return result


# Backward compatibility alias
CollisionEngineError = CollisionError


class ConfigError(CollisionError):
    """Configuration error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.CONFIG_ERROR, context, original_error)


class ValidationError(CollisionError):
    """Validation error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.VALIDATION_ERROR, context, original_error)


class KeyGenerationError(CollisionError):
    """Key generation error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.KEY_GENERATION_ERROR, context, original_error)


class AddressGenerationError(CollisionError):
    """Address generation error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.ADDRESS_GENERATION_ERROR, context, original_error)


class CheckpointError(CollisionError):
    """Checkpoint management error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.CHECKPOINT_ERROR, context, original_error)


class DeduplicationError(CollisionError):
    """Deduplication filter error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.DEDUPLICATION_ERROR, context, original_error)


class TargetResolutionError(CollisionError):
    """Target resolution error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.TARGET_RESOLUTION_ERROR, context, original_error)


class CryptoBackendError(CollisionError):
    """Crypto backend error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.CRYPTO_BACKEND_ERROR, context, original_error)


class GPUError(CollisionError):
    """GPU operation error."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, error_code or self.UNKNOWN_ERROR, context, original_error)
