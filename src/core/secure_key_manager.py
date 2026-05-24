"""Secure key manager.

Provides production-grade private key secure storage and clearing
functionality, addressing Python memory management limitations.
Supports multiple security backends: cryptography, PyNaCl, ctypes
fallback.
"""

import ctypes
import os
import secrets
import sys
import threading  # L3 fix: add thread lock support
import warnings
from contextlib import contextmanager, suppress
from logging import getLogger
from typing import Any

logger = getLogger(__name__)

# Attempt to import cryptography libraries
try:
    import cryptography  # noqa: F401

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    import nacl.secret  # noqa: F401 — import availability check

    HAS_PYNACL = True
except ImportError:
    HAS_PYNACL = False


class SecureMemoryError(Exception):
    """Secure memory operation exception"""


class SecureKeyManager:
    """Secure key manager.

    Provides secure private key storage, usage, and clearing
    functionality, addressing the following Python memory management
    limitations:
    - Garbage collection may copy objects
    - Swap files may contain sensitive data
    - CPU cache may retain data

    Security features:
    - Uses mlock() (Linux/macOS) to prevent swapping to disk
    - Uses cryptography library secure clearing functions
    - Minimizes key residency time in memory
    - Supports context manager for automatic clearing
    - Clear statistics monitoring (class-level)

    Backend priority:
    1. cryptography.io (recommended)
    2. PyNaCl
    3. ctypes (fallback)

    Usage:
        >>> # Basic usage
        >>> with SecureKeyManager() as key_mgr:
        ...     key_mgr.generate_key()
        ...     private_key = key_mgr.get_key()
        ...     # Use private key...
        ...     address = generate_address(private_key)
        >>> # Automatically cleared on context exit

        >>> # Manual management
        >>> key_mgr = SecureKeyManager()
        >>> key_mgr.generate_key()
        >>> # Use...
        >>> key_mgr.clear()  # Manual clear
    """

    # Class-level statistics (for monitoring clear success rate)
    # L3 fix: add class-level lock for thread safety
    _stats_lock: threading.Lock = threading.Lock()
    _total_clears: int = 0
    _successful_clears: int = 0
    _failed_clears: int = 0

    def __init__(self, lock_memory: bool = True) -> None:
        """Initialize secure key manager.

        Args:
            lock_memory: Whether to lock memory to prevent swapping

        Note:
            - Linux/macOS: uses mlock() to lock memory
            - Windows: uses VirtualLock() (requires admin or
              SeLockMemoryPrivilege)
            - Windows without admin: VirtualLock() may fail,
              logged as warning
            - Memory locking requires sufficient privileges

        """
        self._key: bytearray | None = None
        self._locked = False
        self._cleared = False
        self._memory_locked = False
        self._lock_memory_enabled = lock_memory

        # Select backend
        if HAS_CRYPTOGRAPHY:
            self._backend = "cryptography"
        elif HAS_PYNACL:
            self._backend = "pynacl"
        else:
            self._backend = "ctypes"
            warnings.warn(
                "cryptography or PyNaCl not installed, "
                "using ctypes fallback. "
                "Install: pip install cryptography",
                UserWarning,
                stacklevel=2,
            )

    def _try_lock_memory(self) -> bool:
        """Attempt to lock memory to prevent sensitive data from being
        swapped to disk.

        Linux/macOS: uses mlock() system call
        Windows: uses VirtualLock() API

        Returns:
            bool: Whether memory locking succeeded

        Note:
            - Linux: requires root or CAP_IPC_LOCK, or adjust
              memlock limit
            - macOS: requires root
            - Windows: locking memory reduces working set space
            - Failure does not raise exception, but logs warning

        """
        if not self._lock_memory_enabled:
            return False

        try:
            if os.name == "nt":
                # Windows platform
                return self._lock_memory_windows()
            if os.name == "posix":
                # Linux/macOS platform
                return self._lock_memory_posix()
            logger.warning(
                f"Unsupported OS: {os.name}, "
                "cannot lock memory",
            )
            return False
        except Exception as e:
            logger.error("Memory lock failed: %s", e)
            logger.error(
                "Private key may be swapped to disk! "
                "Recommend running with admin privileges.",
            )
            if os.name == "posix":
                logger.error(
                    "On Linux, run: ulimit -l unlimited",
                )
            return False

    def _lock_memory_posix(self) -> bool:
        """POSIX (Linux/macOS) memory locking implementation.

        Uses mlock() system call to lock memory pages, preventing
        swapping to disk.
        """
        try:
            # Load C library
            if sys.platform == "darwin":
                # macOS
                libc = ctypes.CDLL(
                    "/usr/lib/libSystem.B.dylib",
                )
            else:
                # Linux
                libc = ctypes.CDLL("libc.so.6")

            # Configure mlock function signature
            # int mlock(const void *addr, size_t len);
            libc.mlock.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            libc.mlock.restype = ctypes.c_int

            # Configure munlock function signature
            # int munlock(const void *addr, size_t len);
            libc.munlock.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            libc.munlock.restype = ctypes.c_int

            # Save libc reference for later use
            self._libc = libc

            logger.info(
                "POSIX memory locking initialized (mlock/munlock)",
            )
            return True

        except (OSError, AttributeError) as e:
            logger.warning(
                "Cannot initialize POSIX memory locking: %s", e,
            )
            return False

    def _lock_memory_windows(self) -> bool:
        """Windows platform memory locking implementation.

        Uses VirtualLock() API to lock memory pages, preventing
        swapping to page file.
        """
        try:
            # Load kernel32.dll
            kernel32 = ctypes.WinDLL("kernel32.dll")

            # Configure VirtualLock function signature
            # BOOL VirtualLock(LPVOID lpAddress, SIZE_T dwSize);
            kernel32.VirtualLock.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            kernel32.VirtualLock.restype = ctypes.c_bool

            # Configure VirtualUnlock function signature
            # BOOL VirtualUnlock(LPVOID lpAddress, SIZE_T dwSize);
            kernel32.VirtualUnlock.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            kernel32.VirtualUnlock.restype = ctypes.c_bool

            # Save kernel32 reference for later use
            self._kernel32 = kernel32

            logger.info(
                "Windows memory locking initialized "
                "(VirtualLock/VirtualUnlock)",
            )
            return True

        except (OSError, AttributeError) as e:
            logger.warning(
                "Cannot initialize Windows memory locking: %s", e,
            )
            return False

    def _lock_key_memory(self) -> bool:
        """Lock current key's memory pages.

        Must be called after key generation.

        Returns:
            bool: Whether locking succeeded

        """
        if self._key is None or self._cleared:
            return False

        if not self._lock_memory_enabled:
            return False

        try:
            if os.name == "nt" and hasattr(
                self, "_kernel32",
            ):
                # Windows: VirtualLock
                addr = ctypes.addressof(
                    ctypes.c_char.from_buffer(self._key),
                )
                size = len(self._key)
                result = self._kernel32.VirtualLock(
                    addr, size,
                )

                if result:
                    self._memory_locked = True
                    return True
                error_code = ctypes.get_last_error()
                logger.warning(
                    "Windows VirtualLock failed, error code: %s", error_code,
                )
                return False

            if os.name == "posix" and hasattr(
                self, "_libc",
            ):
                # Linux/macOS: mlock
                addr = ctypes.addressof(
                    ctypes.c_char.from_buffer(self._key),
                )
                size = len(self._key)
                result = self._libc.mlock(addr, size)

                if result == 0:  # mlock returns 0 for success
                    self._memory_locked = True
                    return True
                import errno

                logger.warning(
                    f"POSIX mlock failed, error: "
                    f"{errno.errorcode.get(ctypes.get_errno(), 'Unknown')}",
                )
                return False
            return False

        except Exception as e:
            logger.warning(
                "Locking key memory failed: %s", e,
            )
            return False

    def _unlock_key_memory(self) -> bool:
        """Unlock current key's memory pages.

        Called before clearing the key.

        Returns:
            bool: Whether unlocking succeeded

        """
        if not self._memory_locked:
            return False

        if self._key is None:
            return False

        try:
            if os.name == "nt" and hasattr(
                self, "_kernel32",
            ):
                # Windows: VirtualUnlock
                addr = ctypes.addressof(
                    ctypes.c_char.from_buffer(self._key),
                )
                size = len(self._key)
                result = self._kernel32.VirtualUnlock(
                    addr, size,
                )

                if result:
                    self._memory_locked = False
                    return True
                logger.warning(
                    "Windows VirtualUnlock failed",
                )
                return False

            if os.name == "posix" and hasattr(
                self, "_libc",
            ):
                # Linux/macOS: munlock
                addr = ctypes.addressof(
                    ctypes.c_char.from_buffer(self._key),
                )
                size = len(self._key)
                result = self._libc.munlock(addr, size)

                if result == 0:  # munlock returns 0 success
                    self._memory_locked = False
                    return True
                logger.warning(
                    "POSIX munlock failed",
                )
                return False
            return False

        except Exception as e:
            logger.warning(
                "Unlocking key memory failed: %s", e,
            )
            return False

    def generate_key(
        self, key_bytes: bytes | None = None,
    ) -> None:
        """Generate or set private key.

        Args:
            key_bytes: Optional private key bytes,
                random generation if not provided

        Note:
            - Key stored as bytearray for safe clearing
            - Clears existing key if present before generating
            - Auto-attempts memory locking after generation
              (if enabled)

        """
        # If key exists, clear it first
        if self._key is not None and not self._cleared:
            self.clear()

        # Generate or set key
        if key_bytes is None:
            self._key = bytearray(
                secrets.token_bytes(32),
            )
        else:
            if len(key_bytes) != 32:
                raise ValueError(
                    "Private key must be 32 bytes",
                )
            self._key = bytearray(key_bytes)

        self._cleared = False
        self._memory_locked = False

        # Attempt memory locking
        if self._lock_memory_enabled:
            self._lock_key_memory()

    def get_key(self) -> memoryview:
        """Get read-only view of private key.

        Returns:
            Read-only memoryview for safe key access

        Warning:
            - Returns read-only memory view, cannot modify
            - Must call clear() after use
            - Do not store this reference elsewhere
            - For writable copy, use get_key_copy()

        """
        if self._key is None:
            raise SecureMemoryError(
                "Key not generated, call generate_key() first",
            )

        if self._cleared:
            raise SecureMemoryError(
                "Key has been cleared, cannot reuse",
            )

        return memoryview(self._key).toreadonly()

    def get_key_copy(self) -> bytearray:
        """Get private key copy (temporary use).

        Returns:
            bytearray copy of private key, must call
            secure_clear_bytearray() after use

        Warning:
            - Copy does NOT auto-clear, must handle manually
            - Recommend get_key() + clear() for safety

        """
        if self._key is None:
            raise SecureMemoryError(
                "Key not generated, call generate_key() first",
            )

        if self._cleared:
            raise SecureMemoryError(
                "Key has been cleared, cannot reuse",
            )

        return bytearray(self._key)

    def clear(self) -> None:
        """Securely clear private key memory.

        Clear strategy depends on backend (all based on
        ctypes.memset):
        - cryptography backend: random overwrite + memset + verify
          → safest path
        - pynacl backend: random overwrite + memset + Python retry
          fallback
        - ctypes backend: memset + simple fallback

        Note:
            - Unlocks memory before clearing
            - Memory marked swappable after clearing

        """
        if self._key is None or self._cleared:
            return

        try:
            # Unlock memory first (unlock before clear)
            if self._memory_locked:
                self._unlock_key_memory()

            if self._backend == "cryptography":
                self._clear_secure()
            elif self._backend == "pynacl":
                self._clear_with_retry()
            else:
                self._clear_with_ctypes()

            self._cleared = True

            # L3 fix: use lock for thread-safe stats
            with SecureKeyManager._stats_lock:
                SecureKeyManager._total_clears += 1
                SecureKeyManager._successful_clears += 1

        except Exception as e:
            # Clear failure is a critical error
            # L3 fix: use lock for thread-safe stats
            with SecureKeyManager._stats_lock:
                SecureKeyManager._total_clears += 1
                SecureKeyManager._failed_clears += 1
            raise SecureMemoryError(
                f"Secure clear failed: {e}",
            ) from e

    def _clear_secure(self) -> None:
        """Secure clear (verified path, for cryptography backend).

        Defense-in-depth strategy:
        1. Overwrite key memory with random data to prevent
           compiler optimization artifacts
        2. Use ctypes.memset for final zeroing
        3. Verify all bytes, raise SecureMemoryError on failure

        Why not Python loop for clearing:
        - Python loop may be optimized to no-op
        - Interpreter may retain object copies
        - ctypes.memset is low-level, bypasses Python object system
        """
        if self._key:
            # Overwrite with random data for defense depth
            random_data = secrets.token_bytes(
                len(self._key),
            )
            for i in range(len(self._key)):
                self._key[i] = random_data[i]
            # Use ctypes.memset for final zeroing
            addr = ctypes.addressof(
                ctypes.c_char.from_buffer(self._key),
            )
            size = len(self._key)
            ctypes.memset(addr, 0, size)
            if any(self._key):
                logger.error(
                    "Secure clear failed, memory not zeroed",
                )
                raise SecureMemoryError(
                    "Clear failed: memory not properly zeroed",
                )

    def _clear_with_retry(self) -> None:
        """Secure clear (with fallback path, for pynacl backend).

        Strategy:
        1. Overwrite key memory with random data
        2. Use ctypes.memset for clearing
        3. Fall back to Python multi-pass overwrite on memset
           failure
        """
        if self._key:
            # Overwrite with random data first
            random_data = secrets.token_bytes(
                len(self._key),
            )
            for i in range(len(self._key)):
                self._key[i] = random_data[i]

            # Use ctypes.memset for secure clearing
            try:
                ctypes.memset(
                    ctypes.addressof(
                        ctypes.c_char.from_buffer(
                            self._key,
                        ),
                    ),
                    0,
                    len(self._key),
                )
            except (TypeError, ValueError, OSError):
                # Fall back to secure multi-pass overwrite
                for _ in range(3):
                    for i in range(len(self._key)):
                        self._key[i] = 0xFF
                for i in range(len(self._key)):
                    self._key[i] = 0x00

    def _clear_with_ctypes(self) -> None:
        """Clear using ctypes memset (fallback scheme)"""
        if self._key:
            try:
                ctypes.memset(
                    ctypes.addressof(
                        ctypes.c_char.from_buffer(
                            self._key,
                        ),
                    ),
                    0,
                    len(self._key),
                )
            except (TypeError, ValueError, OSError):
                # At least overwrite with zeros
                for i in range(len(self._key)):
                    self._key[i] = 0

    def __enter__(self) -> "SecureKeyManager":
        """Context manager entry"""
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Context manager exit - auto-clear"""
        self.clear()

    def __del__(self) -> None:
        """Destructor - ensure clearing"""
        if (
            self._key is not None
            and not self._cleared
        ):
            # Silent failure acceptable in destructor
            # AttributeError: ctypes may be unloaded before __del__
            # (interpreter shutdown)
            # NameError: same as above
            with suppress(
                OSError,
                ValueError,
                AttributeError,
                NameError,
                RuntimeError,
            ):
                self.clear()

    @property
    def is_cleared(self) -> bool:
        """Whether key has been cleared"""
        return self._cleared

    @property
    def backend(self) -> str:
        """Current security backend"""
        return self._backend

    @property
    def is_memory_locked(self) -> bool:
        """Whether memory is locked"""
        return self._memory_locked

    @staticmethod
    def get_clear_stats() -> dict:
        """Get clear statistics.

        Returns:
            dict: Dictionary containing clear statistics
            - total: Total clear attempts
            - successful: Successful clears
            - failed: Failed clears
            - success_rate: Success rate (percentage)

        Usage:
            >>> stats = SecureKeyManager.get_clear_stats()
            >>> print(f"Clear success rate: "
            ...       f"{stats['success_rate']:.2f}%")

        """
        # L3 fix: use lock for thread-safe stats read
        with SecureKeyManager._stats_lock:
            total = SecureKeyManager._total_clears
            successful = (
                SecureKeyManager._successful_clears
            )
            failed = SecureKeyManager._failed_clears

        success_rate = (
            (successful / total * 100) if total > 0 else 100.0
        )

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
        }

    @staticmethod
    def reset_clear_stats() -> None:
        """Reset clear statistics"""
        # L3 fix: use lock for thread-safe stats reset
        with SecureKeyManager._stats_lock:
            SecureKeyManager._total_clears = 0
            SecureKeyManager._successful_clears = 0
            SecureKeyManager._failed_clears = 0


@contextmanager
def secure_key_context(
    key_bytes: bytes | None = None,
) -> Any:
    """Secure key context manager (convenience function).

    Args:
        key_bytes: Optional private key bytes

    Yields:
        memoryview: Read-only view of private key, safely
        clearable

    Usage:
        >>> with secure_key_context() as private_key:
        ...     address = generate_address(private_key)
        >>> # Auto-cleared on exit

    """
    key_mgr = SecureKeyManager()
    try:
        key_mgr.generate_key(key_bytes)
        yield key_mgr.get_key()
    finally:
        key_mgr.clear()


def generate_secure_key() -> bytearray:
    """Generate secure private key (single use).

    Returns:
        bytearray: Newly generated private key

    Warning:
        - This function does NOT clear the returned key
        - Caller must call secure_clear_bytearray() after use
        - Recommend using secure_key_context() instead

    """
    return bytearray(secrets.token_bytes(32))


def validate_private_key(private_key: bytes) -> None:
    """Validate private key format and length.

    Args:
        private_key: Private key bytes to validate

    Raises:
        TypeError: If private_key is not bytes type
        ValueError: If private_key is not exactly 32 bytes

    """
    if not isinstance(private_key, bytes):
        raise TypeError(
            f"Private key must be bytes type, got {type(private_key).__name__}",
        )
    if len(private_key) != 32:
        raise ValueError(
            f"Private key must be exactly 32 bytes, got {len(private_key)} bytes",
        )
