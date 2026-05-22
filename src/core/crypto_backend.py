#!/usr/bin/env python3
"""
Cryptographic backend abstraction layer.

Provides unified elliptic curve operation interface with support for
multiple backend implementations:
- Pure Python implementation (default)
- OpenSSL (via cryptography library)
- coincurve (libsecp256k1 binding)
- ecdsa library

Uses strategy pattern to allow runtime backend switching.

Thread Safety:
- CryptoBackendManager uses RLock to protect global state
- Backend switching operations are thread-safe
- Cryptographic operations are executed outside the lock to avoid
  performance bottlenecks
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, cast

# Import logging configuration
from ..utils import get_configured_logger

# Note: do not call init_logging() at module level, initialized
# uniformly by CLI entry point
# init_logging()  # removed to avoid duplicate initialization

# Get module logger
logger = get_configured_logger("CryptoBackend")


class BackendType(Enum):
    """Cryptographic backend types"""

    PURE_PYTHON = auto()  # Pure Python implementation
    OPENSSL = auto()  # OpenSSL (cryptography)
    COINCURVE = auto()  # coincurve (libsecp256k1)
    ECDSA = auto()  # ecdsa library


class CryptoBackend(ABC):
    """
    Abstract base class for cryptographic backends.

    Defines unified interface for elliptic curve operations.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name"""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available"""

    @abstractmethod
    def generate_public_key(
        self, private_key: bytes, compressed: bool = True
    ) -> bytes:
        """
        Generate public key from private key.

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format

        Returns:
            Public key bytes
        """

    @abstractmethod
    def scalar_multiply(
        self, k: int, point_x: int, point_y: int
    ) -> tuple[int, int]:
        """
        Elliptic curve scalar multiplication.

        Args:
            k: Scalar multiplier
            point_x: X coordinate of point
            point_y: Y coordinate of point

        Returns:
            (rx, ry) Result point coordinates
        """

    @abstractmethod
    def is_constant_time(self) -> bool:
        """
        Check if this backend uses constant-time algorithms.

        Returns:
            True if constant-time algorithms are used
        """


class PurePythonBackend(CryptoBackend):
    """Pure Python backend - uses existing secp256k1.py implementation"""

    def __init__(self, use_const_time: bool = False) -> None:
        from .secp256k1 import ECPoint, EllipticCurve, Secp256k1

        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self._use_const_time = use_const_time

    @property
    def name(self) -> str:
        return "Pure Python" + (" (Constant Time)" if self._use_const_time else "")

    @property
    def is_available(self) -> bool:
        return True

    def generate_public_key(
        self, private_key: bytes, compressed: bool = True
    ) -> bytes:
        # v4.2.2 R4: generate_public_key already uses
        # scalar_multiply_const_time internally,
        # both branches are equivalent, simplified to single path
        return self.ec.generate_public_key(private_key, compressed)

    def scalar_multiply(
        self, k: int, point_x: int, point_y: int
    ) -> tuple[int, int]:
        from .secp256k1 import ECPoint

        point = ECPoint(point_x, point_y)

        # v4.2.2 C1-regression fix: always use constant-time
        # implementation
        result = self.ec.scalar_multiply_const_time(k, point)

        return cast(tuple[int, int], (result.x, result.y))

    def is_constant_time(self) -> bool:
        # v4.2.2 R5: all scalar multiplications now use
        # constant-time implementation
        return True


class OpenSSLBackend(CryptoBackend):
    """OpenSSL backend - uses cryptography library"""

    def __init__(self) -> None:
        self._available = self._check_availability()
        if self._available:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.asymmetric import ec

            self._backend = default_backend()
            self._SECP256K1 = ec.SECP256K1()

    def _check_availability(self) -> bool:
        try:
            from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "OpenSSL (cryptography)"

    @property
    def is_available(self) -> bool:
        return self._available

    def generate_public_key(
        self, private_key: bytes, compressed: bool = True
    ) -> bytes:
        if not self._available:
            raise RuntimeError("OpenSSL backend not available")

        from cryptography.hazmat.primitives.asymmetric import ec

        # Create elliptic curve private key object from private key
        # bytes
        private_value = int.from_bytes(private_key, "big")
        private_key_obj = ec.derive_private_key(
            private_value, self._SECP256K1, self._backend
        )

        # Get public key
        public_key = private_key_obj.public_key()
        public_numbers = public_key.public_numbers()

        # Convert to byte format
        x = public_numbers.x
        y = public_numbers.y

        x_bytes = x.to_bytes(32, "big")

        if compressed:
            # Compressed format: 0x02 (y even) or 0x03 (y odd)
            # + x coordinate
            prefix = b"\x02" if (y % 2 == 0) else b"\x03"
            return prefix + x_bytes
        else:
            # Uncompressed format: 0x04 + x coordinate + y coordinate
            y_bytes = y.to_bytes(32, "big")
            return b"\x04" + x_bytes + y_bytes

    def scalar_multiply(
        self, k: int, point_x: int, point_y: int
    ) -> tuple[int, int]:
        """
        Note: cryptography library does not directly expose point
        multiplication, we implement it by creating temporary
        private keys.

        C-2 fix: refuse to fall back to non-constant-time
        implementation when OpenSSL is unavailable.
        Raise exception instead of falling back to insecure
        implementation.

        Side-channel security notes:
        1. Non-constant-time algorithms may leak private key
           information
        2. Attackers can infer private key bits by analyzing
           execution time
        3. Constant-time implementation ensures execution time
           is independent of input
        4. For security-sensitive scenarios, constant-time
           implementation is mandatory

        Recommended backend selection:
        - CoincurveBackend: libsecp256k1, fully constant-time
          (recommended)
        - OpenSSLBackend: generate_public_key is constant-time,
          but scalar_multiply is not
        - PurePythonBackend: optional constant-time mode, but
          lower performance
        """
        if not self._available:
            msg = "OpenSSL backend not available"
            logger.critical(f"{msg}, cannot perform scalar multiplication")
            raise RuntimeError(f"{msg}, cannot perform scalar multiplication")

        # OpenSSL backend does not support scalar multiplication,
        # fall back to pure Python constant-time implementation
        logger.warning(
            "OpenSSL backend does not support scalar multiplication"
            ", falling back to pure Python constant-time implementation"
        )
        from .secp256k1 import ECPoint, EllipticCurve

        ec_impl = EllipticCurve()
        # v4.2.2 C1-regression fix: use constant-time
        # implementation
        point = ECPoint(point_x, point_y)
        result = ec_impl.scalar_multiply_const_time(k, point)

        return cast(tuple[int, int], (result.x, result.y))

    def is_constant_time(self) -> bool:
        # v4.2.2 R9: all code paths use constant-time
        # implementation
        #
        # Important notes:
        # - generate_public_key() IS constant-time (uses OpenSSL
        #   ec.derive_private_key)
        # - scalar_multiply() now calls
        #   scalar_multiply_const_time (Montgomery Ladder),
        #   which is algorithmically constant-time, but Python
        #   interpreter level branch prediction and cache effects
        #   may cause minor variations in actual execution time
        #
        # Since is_constant_time() should reflect the capability
        # of the entire backend, conservatively return False.
        #
        # For the main use case of this project (collision
        # detection via generate_public_key), the actual execution
        # path is constant-time. This flag conservatively returns
        # False because it is difficult to guarantee absolute
        # constant-time at the Python interpreter level.
        #
        # Recommendations:
        # 1. For security-sensitive scenarios, use
        #    CoincurveBackend (libsecp256k1, fully constant-time)
        # 2. For performance-prioritized scenarios, OpenSSLBackend
        #    can be used (generate_public_key is constant-time)
        return False


class CoincurveBackend(CryptoBackend):
    """coincurve backend - uses libsecp256k1"""

    def __init__(self) -> None:
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            import coincurve  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "coincurve (libsecp256k1)"

    @property
    def is_available(self) -> bool:
        return self._available

    def generate_public_key(
        self, private_key: bytes, compressed: bool = True
    ) -> bytes:
        if not self._available:
            raise RuntimeError("coincurve backend not available")

        import coincurve

        # Generate public key using coincurve
        private_key_obj = coincurve.PrivateKey(private_key)
        return private_key_obj.public_key.format(compressed=compressed)

    def scalar_multiply(
        self, k: int, point_x: int, point_y: int
    ) -> tuple[int, int]:
        """
        coincurve scalar multiplication.

        coincurve provides efficient scalar multiplication
        implementation.
        """
        if not self._available:
            raise RuntimeError("coincurve backend not available")

        import coincurve

        # Create public key object
        # Note: coincurve's API may need adjustment
        # Using public key multiplication concept here
        pubkey_bytes = (
            b"\x04"
            + point_x.to_bytes(32, "big")
            + point_y.to_bytes(32, "big")
        )

        try:
            pubkey = coincurve.PublicKey(pubkey_bytes)
            # coincurve.PublicKey.multiply returns PublicKey object
            result = pubkey.multiply(k.to_bytes(32, "big"))

            # Format result as uncompressed public key bytes
            # (0x04 + x + y)
            result_bytes = (
                result.format(compressed=False)
                if hasattr(result, "format")
                else bytes(result)
            )
            if result_bytes[0] == 0x04 and len(result_bytes) >= 65:
                rx = int.from_bytes(result_bytes[1:33], "big")
                ry = int.from_bytes(result_bytes[33:65], "big")
                return rx, ry
            else:
                # coincurve returned unexpected format, fall back to
                # pure Python implementation
                logger.warning(
                    f"coincurve returned unexpected format: "
                    f"prefix=0x{result_bytes[0]:02x}, "
                    f"len={len(result_bytes)},"
                    f" falling back to pure Python constant-time "
                    f"implementation"
                )
        except (AttributeError, TypeError, AssertionError) as e:
            # If multiply is not available or return type doesn't
            # match, use pure Python fallback
            logger.warning(
                f"coincurve scalar multiplication failed "
                f"({type(e).__name__}), falling back to pure "
                f"Python constant-time implementation"
            )

        # Fall back to pure Python constant-time implementation
        from .secp256k1 import ECPoint, EllipticCurve

        ec_impl = EllipticCurve()
        # v4.2.2 C1-regression fix: use constant-time
        # implementation
        point = ECPoint(point_x, point_y)
        ec_result = ec_impl.scalar_multiply_const_time(k, point)
        return cast(tuple[int, int], (ec_result.x, ec_result.y))

    def is_constant_time(self) -> bool:
        # libsecp256k1 uses constant-time algorithm
        return True


class ECDSABackend(CryptoBackend):
    """ecdsa library backend"""

    def __init__(self) -> None:
        self._available = self._check_availability()
        if self._available:
            from ecdsa import SECP256k1, SigningKey, VerifyingKey  # type: ignore[import-untyped]

            self._SigningKey = SigningKey
            self._SECP256k1 = SECP256k1
            self._VerifyingKey = VerifyingKey

    def _check_availability(self) -> bool:
        try:
            import ecdsa  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "ecdsa"

    @property
    def is_available(self) -> bool:
        return self._available

    def generate_public_key(
        self, private_key: bytes, compressed: bool = True
    ) -> bytes:
        if not self._available:
            raise RuntimeError("ecdsa backend not available")

        # Generate public key using ecdsa
        signing_key = self._SigningKey.from_string(
            private_key, curve=self._SECP256k1
        )
        verifying_key = signing_key.get_verifying_key()

        if compressed:
            return cast(bytes, verifying_key.to_string("compressed"))
        else:
            return cast(bytes, b"\x04" + verifying_key.to_string())

    def scalar_multiply(
        self, k: int, point_x: int, point_y: int
    ) -> tuple[int, int]:
        """
        ecdsa scalar multiplication.

        ecdsa library does not directly expose point
        multiplication, uses pure Python fallback.
        """
        from .secp256k1 import ECPoint, EllipticCurve

        ec_impl = EllipticCurve()
        # v4.2.2 C1-regression fix: use constant-time
        # implementation
        point = ECPoint(point_x, point_y)
        result = ec_impl.scalar_multiply_const_time(k, point)
        return cast(tuple[int, int], (result.x, result.y))

    def is_constant_time(self) -> bool:
        # ecdsa library may not use constant-time algorithm
        return False


class CryptoBackendManager:
    """
    Cryptographic backend manager.

    Manages all available cryptographic backends and provides
    unified access interface.
    Supports runtime backend switching.

    Thread Safety:
    - Uses RLock to protect all state changes
    - Singleton pattern initialized at module import, naturally
      thread-safe
    - Cryptographic operations are executed outside the lock
      to avoid performance bottlenecks
    """

    _instance = None
    _lock = threading.RLock()  # Class-level lock, protects
    # singleton creation
    _backends: dict[Any, Any] = {}
    _current_backend = None
    _default_backend_type = BackendType.PURE_PYTHON

    def __new__(cls) -> "CryptoBackendManager":
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_backends()
        return cls._instance

    def _init_backends(self) -> None:
        """Initialize all backends"""
        # Instance-level lock, protects runtime state
        self._instance_lock = threading.RLock()

        logger.debug("Initializing cryptographic backends...")

        # Initialize in priority order
        self._backends[BackendType.PURE_PYTHON] = PurePythonBackend()
        self._backends[BackendType.OPENSSL] = OpenSSLBackend()
        self._backends[BackendType.COINCURVE] = CoincurveBackend()
        self._backends[BackendType.ECDSA] = ECDSABackend()

        # Set default backend
        self._select_best_backend()

        available = [
            bt.name for bt, backend in self._backends.items()
            if backend.is_available
        ]
        assert self._current_backend is not None
        logger.info(
            f"Crypto backend initialization complete: "
            f"available={available}, "
            f"current={self._current_backend.name}"
        )

    def _select_best_backend(self) -> None:
        """Select best available backend (internal method, caller must
        hold lock)"""
        # Priority: coincurve > OpenSSL > ecdsa > Pure Python
        priority_order = [
            BackendType.COINCURVE,
            BackendType.OPENSSL,
            BackendType.ECDSA,
            BackendType.PURE_PYTHON,
        ]

        with self._instance_lock:
            for backend_type in priority_order:
                backend = self._backends.get(backend_type)
                if backend and backend.is_available:
                    self._current_backend = backend
                    self._default_backend_type = backend_type
                    break

    def reset_to_best_backend(self) -> None:
        """
        Reset to best available backend (thread-safe).

        Public thread-safe method, replaces direct call to
        _select_best_backend.
        """
        self._select_best_backend()

    @property
    def current_backend(self) -> CryptoBackend:
        """
        Get current backend (thread-safe).

        Gets backend reference inside lock to ensure consistent
        instance.
        """
        with self._instance_lock:
            backend = self._current_backend
        if backend is None:
            raise RuntimeError("No crypto backend available")
        return cast(CryptoBackend, backend)

    def set_backend(
        self, backend_type: BackendType, **kwargs
    ) -> bool:
        """
        Set current backend (thread-safe).

        All state updates are atomically completed inside the
        lock to avoid race conditions.

        Args:
            backend_type: Backend type
            **kwargs: Backend-specific parameters

        Returns:
            True if setting succeeded
        """
        logger.debug(
            f"Switching crypto backend: {backend_type.name}, "
            f"params={kwargs}"
        )

        with self._instance_lock:
            if backend_type == BackendType.PURE_PYTHON:
                use_const_time = kwargs.get("use_const_time", False)
                existing = self._backends.get(backend_type)
                if existing is not None and isinstance(
                    existing, PurePythonBackend
                ):
                    existing._use_const_time = use_const_time
                else:
                    self._backends[backend_type] = (
                        PurePythonBackend(use_const_time)
                    )

            backend = self._backends.get(backend_type)
            if backend is None:
                logger.error(f"Unknown backend type: {backend_type}")
                raise ValueError(f"Unknown backend type: {backend_type}")

            if not backend.is_available:
                logger.error(f"Backend not available: {backend.name}")
                raise RuntimeError(
                    f"Backend {backend.name} is not available"
                )

            old_backend = (
                self._current_backend.name
                if self._current_backend
                else "None"
            )
            self._current_backend = backend
            self._default_backend_type = backend_type

        logger.info(
            f"Crypto backend switched: {old_backend} -> "
            f"{backend.name}"
        )
        return True

    def get_available_backends(self) -> list[tuple[BackendType, str]]:
        """Get list of all available backends (thread-safe)"""
        with self._instance_lock:
            backends_copy = dict(self._backends)
        return [
            (bt, b.name)
            for bt, b in backends_copy.items()
            if b.is_available
        ]

    def generate_public_key(
        self, private_key: bytes, compressed: bool = True
    ) -> bytes:
        """
        Generate public key using current backend.

        Note: cryptographic operations are executed outside the
        lock to avoid performance bottlenecks.

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format

        Returns:
            Public key bytes
        """
        backend = self.current_backend  # Get reference inside lock

        # Performance monitoring (only at DEBUG level)
        if logger.isEnabledFor(logging.DEBUG):
            start_time = time.perf_counter()
            result = backend.generate_public_key(private_key, compressed)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"Public key generation: {backend.name}, "
                f"elapsed={elapsed_ms:.3f}ms"
            )
            return result

        return backend.generate_public_key(private_key, compressed)

    def is_constant_time(self) -> bool:
        """Check if current backend uses constant-time algorithm"""
        backend = self.current_backend  # Get reference inside lock
        return backend.is_constant_time()


# Global backend manager instance
crypto_manager = CryptoBackendManager()


def get_crypto_backend() -> CryptoBackendManager:
    """
    Get crypto backend manager instance.

    Returns:
        CryptoBackendManager instance
    """
    return crypto_manager


# Convenience functions
def generate_public_key(
    private_key: bytes, compressed: bool = True
) -> bytes:
    """
    Generate public key using current backend.

    Args:
        private_key: 32-byte private key
        compressed: Whether to use compressed format

    Returns:
        Public key bytes
    """
    return crypto_manager.generate_public_key(private_key, compressed)


def set_crypto_backend(
    backend_type: BackendType, **kwargs
) -> bool:
    """
    Set crypto backend.

    Args:
        backend_type: Backend type
        **kwargs: Backend-specific parameters

    Returns:
        True if setting succeeded
    """
    return crypto_manager.set_backend(backend_type, **kwargs)


def get_available_backends() -> list[tuple[BackendType, str]]:
    """Get all available backends"""
    return crypto_manager.get_available_backends()


def is_secure_backend_available() -> bool:
    """
    Check if secure crypto backend is available (required for
    production).

    Secure backend definition:
    - CoincurveBackend (recommended): libsecp256k1, fully
      constant-time
    - OpenSSLBackend: generate_public_key is constant-time

    Insecure backends:
    - PurePythonBackend: optional constant-time mode, but lower
      performance
    - ECDSABackend: may not use constant-time algorithm

    Returns:
        True if secure backend is available
    """
    backend = crypto_manager.current_backend
    if backend is None:
        return False

    backend_name = backend.name.lower()

    # Coincurve is most secure
    if "coincurve" in backend_name or "libsecp256k1" in backend_name:
        return True

    # OpenSSL's generate_public_key is constant-time
    if "openssl" in backend_name:
        return True

    # PurePython needs to check if constant-time mode is enabled
    if "pure python" in backend_name or "purepython" in backend_name:
        return backend.is_constant_time()

    # Other backends conservatively return False
    return False


def get_backend_security_info() -> dict:
    """
    Get current backend security information.

    Returns:
        Dictionary containing backend security information
    """
    backend = crypto_manager.current_backend
    if backend is None:
        return {
            "available": False,
            "backend": None,
            "security_level": "unknown",
        }

    backend_name = backend.name.lower()
    is_constant_time = backend.is_constant_time()

    # Determine security level
    if "coincurve" in backend_name or "libsecp256k1" in backend_name:
        security_level = "secure"  # Fully secure
    elif "openssl" in backend_name:
        security_level = "secure" if is_constant_time else "partial"
    elif is_constant_time:
        security_level = "partial"  # Partially secure
    else:
        security_level = "insecure"  # Insecure

    return {
        "available": True,
        "backend": backend.name,
        "security_level": security_level,
        "is_constant_time": is_constant_time,
        "recommendation": _get_security_recommendation(
            security_level
        ),
    }


def _get_security_recommendation(security_level: str) -> str:
    """Get security recommendation"""
    recommendations = {
        "secure": (
            "Current backend is secure, suitable for "
            "production use"
        ),
        "partial": (
            "Current backend is partially secure, "
            "recommend installing coincurve library for "
            "better security"
        ),
        "insecure": (
            "Current backend is insecure, not "
            "recommended for production use"
        ),
    }
    return recommendations.get(security_level, "Unknown security level")


def verify_production_ready() -> tuple[bool, str]:
    """
    Verify system meets production environment security
    requirements.

    Returns:
        (is_ready, message) tuple
        is_ready: True if production requirements are met
        message: Status message
    """
    if is_secure_backend_available():
        return True, "Production environment security check passed"

    backend_info = get_backend_security_info()
    return False, (
        f"Production environment security check failed\n"
        f"  Current backend: {backend_info.get('backend', 'unknown')}\n"
        f"  Security level: {backend_info.get('security_level', 'unknown')}\n"
        f"  {backend_info.get('recommendation', '')}\n\n"
        f"Suggestions:\n"
        f"  pip install coincurve  # Recommended, most secure\n"
        f"  pip install cryptography  # Alternative, generate_public_key is constant-time\n"
    )
