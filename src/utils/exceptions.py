"""Custom exception classes for the collision engine."""


class CollisionEngineError(Exception):
    """Base exception."""


CollisionError = CollisionEngineError


class KeyGenerationError(CollisionEngineError):
    def __init__(self, message="", error_code=0, context=None):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}


class AddressGenerationError(CollisionEngineError):
    pass


class ConfigError(CollisionEngineError):
    pass


class GPUError(CollisionEngineError):
    pass


class CheckpointError(CollisionEngineError):
    pass


class CryptoBackendError(CollisionEngineError):
    pass


class DeduplicationError(CollisionEngineError):
    pass


class TargetResolutionError(CollisionEngineError):
    pass


class ValidationError(CollisionEngineError):
    pass
