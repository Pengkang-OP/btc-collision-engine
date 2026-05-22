"""Big integer optimization module for elliptic curve operations.

Provides optimized big integer operations using gmpy2 when available,
with pure Python fallback.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import gmpy2

    HAS_GMPY2 = True
except ImportError:
    HAS_GMPY2 = False


class BigIntOptimizer:
    """Big integer arithmetic optimizer.

    Uses gmpy2 for accelerated big integer operations when available,
    with automatic pure Python fallback.

    Performance:
    - Modular exponentiation: 2-5x faster with gmpy2
    - Modular inverse: 3-8x faster with gmpy2
    - Large integer multiplication: 2-4x faster with gmpy2
    """

    def __init__(self):
        """Initialize optimizer with best available backend."""
        self._use_gmpy2 = HAS_GMPY2
        if self._use_gmpy2:
            logger.debug("gmpy2 available, using optimized backend")
        else:
            logger.debug("gmpy2 not available, using pure Python backend")

    def mod_pow(self, base: int, exp: int, mod: int) -> int:
        """Compute modular exponentiation: base^exp mod mod.

        Args:
            base: Base integer
            exp: Exponent
            mod: Modulus

        Returns:
            Modular exponentiation result
        """
        if self._use_gmpy2:
            return int(gmpy2.powmod(base, exp, mod))
        return pow(base, exp, mod)

    def mod_inverse(self, a: int, m: int) -> int:
        """Compute modular multiplicative inverse.

        Args:
            a: Integer to find inverse of
            m: Modulus (must be prime)

        Returns:
            Modular inverse of a modulo m

        Raises:
            ValueError: When inverse does not exist
        """
        if self._use_gmpy2:
            result = gmpy2.invert(a, m)
            if result == 0:
                raise ValueError(f"Modular inverse does not exist for {a} mod {m}")
            return int(result)
        # Pure Python fallback using extended Euclidean algorithm
        g, x, _ = self._extended_gcd(a, m)
        if g != 1:
            raise ValueError(f"Modular inverse does not exist for {a} mod {m}")
        return x % m

    @staticmethod
    def _extended_gcd(a: int, b: int) -> tuple[int, int, int]:
        """Extended Euclidean algorithm.

        Returns (g, x, y) such that a*x + b*y = g = gcd(a, b).

        Args:
            a: First integer
            b: Second integer

        Returns:
            (gcd, x, y) tuple
        """
        if a == 0:
            return b, 0, 1
        g, x1, y1 = BigIntOptimizer._extended_gcd(b % a, a)
        return g, y1 - (b // a) * x1, x1

    @property
    def backend_name(self) -> str:
        """Get current backend name."""
        return "gmpy2" if self._use_gmpy2 else "pure_python"
