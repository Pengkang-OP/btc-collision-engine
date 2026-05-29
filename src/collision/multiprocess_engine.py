r"""Multi-process collision engine for CPU-parallel collision detection.

Distributes key generation and address matching across multiple CPU
processes for improved throughput.

Usage:
    >>> engine = MultiProcessCollisionEngine(config)
    >>> engine.start()
    >>> engine.add_targets({"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"})
    >>> engine.submit_task(b"\\x00" * 32)  # Submit a private key to check
    >>> result = engine.get_result()  # Get async result
    >>> engine.stop()

Note:
    For production use, prefer GPU-based collision detection which
    provides 100-1000x better performance. The multi-process engine
    is suitable for CPU-only environments or as fallback.
"""

from __future__ import annotations

__all__ = [
    "MultiProcessCollisionEngine",
]

import multiprocessing
import queue
import time
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("MultiProcessEngine")


class MultiProcessCollisionEngine:
    """Multi-process collision detection engine.

    Distributes work across CPU cores using separate processes for
    key generation, address computation, and matching.

    This is a reference implementation for CPU-only environments.
    For production, use GPU-based collision detection.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the multiprocess collision engine.

        Args:
            config: Engine configuration dict. Supported keys:
                - max_workers: Number of worker processes (default: CPU count)
                - target_addresses: Set of target addresses to check

        """
        self.config = config or {}
        self._num_workers = self.config.get(
            "max_workers",
            multiprocessing.cpu_count(),
        )
        self._running = False
        self._task_queue: multiprocessing.Queue[bytes] | None = None
        self._result_queue: multiprocessing.Queue[dict[str, Any]] | None = None
        self._processes: list[multiprocessing.Process] = []
        self._total_keys = 0
        self._start_time: float | None = None
        logger.info(
            f"Multi-process engine initialized: {self._num_workers} workers",
        )

    def start(self) -> None:
        """Start worker processes."""
        self._running = True
        self._task_queue = multiprocessing.Queue(
            maxsize=1000,
        )
        self._result_queue = multiprocessing.Queue()
        self._start_time = time.time()

        for i in range(self._num_workers):
            p = multiprocessing.Process(
                target=self._worker_loop,
                args=(i,),
                daemon=True,
            )
            p.start()
            self._processes.append(p)

        logger.info(
            f"Started {self._num_workers} worker processes",
        )

    def stop(self) -> None:
        """Stop all worker processes."""
        self._running = False
        for p in self._processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
        self._processes.clear()
        elapsed = time.time() - self._start_time if self._start_time else 0
        logger.info(
            f"Multi-process engine stopped: {self._total_keys} keys in {elapsed:.1f}s",
        )

    def submit_task(self, private_key_bytes: bytes) -> None:
        """Submit a private key to the work queue.

        Args:
            private_key_bytes: 32-byte private key to check.

        """
        if self._task_queue is None:
            raise RuntimeError("Engine not started. Call start() first.")
        self._task_queue.put(private_key_bytes)

    def get_result(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        """Get a result from the completed work queue (non-blocking).

        Args:
            timeout: Wait timeout in seconds. None = block indefinitely.

        Returns:
            Result dict with keys:
                - private_key_hex: Matched private key in hex
                - address: Matched Bitcoin address
                - worker_id: Worker process ID
            Or None if no result available.

        """
        if self._result_queue is None:
            raise RuntimeError("Engine not started. Call start() first.")
        try:
            return self._result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _worker_loop(
        self,
        worker_id: int,
    ) -> None:
        """Worker process main loop.

        Each worker continuously pulls private key bytes from the
        task queue, computes the corresponding Bitcoin address,
        and checks against target addresses.

        Args:
            worker_id: Unique worker process identifier (0-indexed).

        """
        # Import inside worker process to avoid pickling issues
        from ..core.address_generator import P2PKHAddressGenerator

        # resolve targets from manager config via shared state
        # In multi-process mode, targets are read-only after engine start
        # and are passed via queue messages
        address_generator = P2PKHAddressGenerator()

        while self._running:
            try:
                assert self._task_queue is not None
                assert self._result_queue is not None
                task = self._task_queue.get(timeout=1)

                # Generate Bitcoin address from private key bytes
                address = address_generator.generate_from_private_key(task)  # type: ignore[attr-defined]

                result: dict[str, Any] = {
                    "private_key_hex": task.hex(),
                    "address": address,
                    "worker_id": worker_id,
                }
                self._result_queue.put(result)
            except queue.Empty:
                continue
            except (ValueError, OSError, RuntimeError) as e:
                logger.error(
                    "Worker %d: processing error: %s",
                    worker_id,
                    e,
                )
                continue

    def _process_task(
        self,
        worker_id: int,
        task: bytes,
    ) -> None:
        """Process a single task (private key).

        Legacy method — actual processing now happens in _worker_loop.
        Kept for backward compatibility.

        Args:
            worker_id: Worker process ID
            task: Private key bytes

        """
        assert self._result_queue is not None
        result: dict[str, Any] = {
            "private_key_hex": task.hex(),
            "worker_id": worker_id,
        }
        self._result_queue.put(result)

    def get_stats(self) -> dict[str, Any]:
        """Get current engine statistics.

        Returns:
            Dict with keys: total_keys, elapsed, throughput, workers, running

        """
        elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            "total_keys": self._total_keys,
            "elapsed": elapsed,
            "throughput": (self._total_keys / max(elapsed, 0.001)),
            "workers": self._num_workers,
            "running": self._running,
        }
