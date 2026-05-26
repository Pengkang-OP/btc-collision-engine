"""Secure private key generator - compliant with Bitcoin Core specification."""

import pathlib
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any

from ..utils import get_configured_logger
from .secp256k1 import Secp256k1
from .secure_key_manager import SecureKeyManager

# Log system initialized uniformly by CLI/main.py entry point
logger = get_configured_logger("SecureKeyGenerator")


class SecureKeyGenerator:
    """Secure private key generator compliant with Bitcoin Core specification.

    Uses CSPRNG (Cryptographically Secure Pseudo-Random Number
    Generator) to generate private keys, ensuring they meet
    cryptocurrency industry security standards.

    Attributes:
        batch_size: Number of keys per batch
        rate_limit: Keys per second (0 = unlimited)
        key_manager: Key manager (for secure clearing)
        _lock: Thread safety lock

    Usage:
        >>> config = {'batch_size': 1000, 'rate_limit': 0}
        >>> generator = SecureKeyGenerator(config)
        >>> keys = generator.generate_batch(1000)

    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize private key generator.

        Args:
            config: Configuration dictionary
                - batch_size: Keys per batch (default 1000)
                - rate_limit: Keys per second (default 0 = unlimited)
                - key_format: Public key format (default 'both')
                - entropy_check_enabled: Enable entropy pool check
                  (default True)
                - min_entropy_bits: Minimum entropy threshold
                  (default 1000)

        """
        config = config or {}
        self.batch_size = config.get("batch_size", 1000)
        self.rate_limit = config.get("rate_limit", 0)
        self.key_format = config.get("key_format", "both")
        self.key_manager = SecureKeyManager()
        self._lock = threading.Lock()

        # P1-3 fix: entropy pool check configuration
        self.entropy_check_enabled = config.get(
            "entropy_check_enabled",
            True,
        )
        self.min_entropy_bits = config.get(
            "min_entropy_bits",
            1000,
        )

        # Statistics
        self._total_generated = 0
        self._start_time = datetime.utcnow()
        self.stats: dict[str, Any] = {
            "low_entropy_count": 0,
            "entropy_checks": 0,
            "warnings_issued": 0,
        }

        logger.info(
            "SecureKeyGenerator initialized: batch_size=%d, rate_limit=%d, entropy_check=%s",
            self.batch_size,
            self.rate_limit,
            self.entropy_check_enabled,
        )

    def _check_entropy_health(self) -> bool:
        """Check system entropy pool health.

        P1-3 fix: Add entropy pool health check to prevent weak
        key generation in low-entropy environments.

        Returns:
            bool: Whether entropy pool is healthy

        """
        if not self.entropy_check_enabled:
            return True

        try:
            # Linux: check entropy pool
            entropy_file = "/proc/sys/kernel/random/entropy_avail"
            if pathlib.Path(entropy_file).exists():
                with pathlib.Path(entropy_file).open() as f:
                    entropy = int(f.read().strip())

                self.stats["entropy_checks"] = self.stats.get("entropy_checks", 0) + 1

                if entropy < self.min_entropy_bits:
                    _entropy = entropy
                    _min_e = self.min_entropy_bits
                    logger.warning(
                        "System entropy low: %s bits (<%s), recommend installing haveged/rng-tools",
                        _entropy,
                        _min_e,
                    )
                    self.stats["low_entropy_count"] = (
                        self.stats.get(
                            "low_entropy_count",
                            0,
                        )
                        + 1
                    )

                    # Detailed suggestion on first warning
                    if self.stats["low_entropy_count"] == 1:
                        logger.warning(
                            "Low entropy may degrade key "
                            "generation quality.\n"
                            "Linux solutions:\n"
                            "  sudo apt-get install haveged\n"
                            "  sudo systemctl enable haveged\n"
                            "  sudo systemctl start haveged\n"
                            "or:\n"
                            "  sudo apt-get install "
                            "rng-tools\n"
                            "  sudo systemctl enable "
                            "rng-tools\n"
                            "  sudo systemctl start "
                            "rng-tools",
                        )
                        self.stats["warnings_issued"] = (
                            self.stats.get(
                                "warnings_issued",
                                0,
                            )
                            + 1
                        )

                    return False
                if entropy < self.min_entropy_bits * 2:
                    logger.debug(
                        "System entropy moderate: %s bits",
                        entropy,
                    )
                    return True
                logger.debug(
                    "System entropy sufficient: %s bits",
                    entropy,
                )
                return True

            # Windows/macOS cannot check, assume healthy
            # These systems use CryptGenRandom/SecureRandom,
            # not dependent on entropy pool
            if self.stats.get("entropy_checks", 0) == 0:
                # Log explanation on first check only
                import platform

                system = platform.system()
                logger.debug(
                    "%s uses system-level CSPRNG (CryptGenRandom/SecureRandom), "
                    "not dependent on /dev/random entropy pool; "
                    "security is OS-guaranteed",
                    system,
                )
                self.stats["entropy_checks"] = 1
            return True
        except Exception as e:
            logger.debug("Cannot check entropy: %s", e)
            return True  # Assume healthy if cannot check

    def generate_batch(
        self,
        count: int,
    ) -> list[bytearray]:
        """Generate private keys in batch.

        Returns mutable bytearray for secure clearing after use.

        Callers should use
        src.core.secure_key_manager.secure_clear_bytearray()
        to clear each private key after use.

        Args:
            count: Number of private keys to generate

        Returns:
            List of private keys (bytearray, mutable, supports
            clearing)

        """
        if count <= 0:
            raise ValueError(
                "Generation count must be greater than 0",
            )

        # P1-3 fix: check entropy pool health
        if not self._check_entropy_health():
            logger.warning(
                "Low entropy health, generated keys may have security risks",
            )
            # Log but don't block, to avoid performance impact

        private_keys = []
        start_time = time.time()

        for i in range(count):
            try:
                # 1. Generate 32-byte random via CSPRNG,
                #    store in mutable bytearray (supports clearing)
                private_key = bytearray(
                    secrets.token_bytes(32),
                )

                # 2. Validate private key (1 <= k < n)
                if not self._is_valid_private_key(
                    bytes(private_key),
                ):
                    logger.debug(
                        "Invalid private key generated, regenerating",
                    )
                    continue

                # 3. Add to batch list
                private_keys.append(private_key)

                # 4. Rate control (if configured)
                if self.rate_limit > 0:
                    elapsed = time.time() - start_time
                    expected_time = len(private_keys) / self.rate_limit
                    if elapsed < expected_time:
                        time.sleep(
                            expected_time - elapsed,
                        )

            except Exception as e:
                logger.error(
                    "Failed to generate key %d: %s",
                    i,
                    str(e),
                )
                continue

        # Update statistics
        with self._lock:
            self._total_generated += len(private_keys)

        elapsed = time.time() - start_time
        rate = len(private_keys) / elapsed if elapsed > 0 else 0

        logger.debug(
            "Batch generation complete: %d keys in %.2fs (%.0f keys/s)",
            len(private_keys),
            elapsed,
            rate,
        )

        # BL-2 fix: check if any valid keys were generated
        if len(private_keys) == 0 and count > 0:
            raise RuntimeError(
                f"Cannot generate any valid private keys "
                f"(requested {count}). This may indicate "
                "severe system entropy depletion or CSPRNG "
                "failure.",
            )

        return private_keys

    def generate_single(self) -> bytes:
        """Generate a single private key.

        Returns:
            32-byte private key

        """
        max_attempts = 100

        for _ in range(max_attempts):
            private_key = secrets.token_bytes(32)

            if self._is_valid_private_key(private_key):
                with self._lock:
                    self._total_generated += 1
                return private_key

        raise RuntimeError(
            "Failed to generate valid private key (exceeded max attempts)",
        )

    # 别名：兼容测试中 generate_single_key 的调用
    generate_single_key = generate_single

    def _is_valid_private_key(
        self,
        key: bytes,
    ) -> bool:
        """Validate private key against secp256k1 curve specification.

        Args:
            key: 32-byte private key

        Returns:
            Whether valid

        """
        if len(key) != 32:
            return False

        # Convert to integer
        key_int = int.from_bytes(key, "big")

        # Validate range: 1 <= k < n
        return 1 <= key_int < Secp256k1.N

    def get_statistics(self) -> dict[str, Any]:
        """Get generation statistics.

        Returns:
            Statistics dictionary

        """
        with self._lock:
            elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            rate = self._total_generated / elapsed if elapsed > 0 else 0

            stats = {
                "total_generated": self._total_generated,
                "elapsed_seconds": elapsed,
                "generation_rate": rate,
                "batch_size": self.batch_size,
                "rate_limit": self.rate_limit,
                "key_format": self.key_format,
                # P1-3 fix: add entropy stats
                "entropy_check_enabled": (self.entropy_check_enabled),
                "min_entropy_bits": self.min_entropy_bits,
                "low_entropy_warnings": self.stats.get(
                    "low_entropy_count",
                    0,
                ),
                "entropy_checks": self.stats.get(
                    "entropy_checks",
                    0,
                ),
            }

            return stats

    def reset_statistics(self) -> None:
        """Reset statistics."""
        with self._lock:
            self._total_generated = 0
            self._start_time = datetime.now(timezone.utc)
            logger.info("Statistics reset")
