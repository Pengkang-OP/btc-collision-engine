"""Custom exception classes for the collision engine."""


class CollisionEngineError(Exception):
    """Base exception for collision engine errors."""


class KeyGenerationError(CollisionEngineError):
    """Raised when private key generation fails."""

    def __init__(
        self,
        message: str = "",
        error_code: int = 0,
        context: dict | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}


class ConfigError(CollisionEngineError):
    """Raised when configuration is invalid."""


class GPUError(CollisionEngineError):
    """Raised when GPU operations fail."""


class CheckpointError(CollisionEngineError):
    """Raised when checkpoint operations fail."""
