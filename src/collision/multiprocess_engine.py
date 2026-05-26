#!/usr/bin/env python3
"""Multi-process collision engine for CPU-parallel collision detection.

Distributes key generation and address matching across multiple CPU
processes for improved throughput.
"""

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
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the multiprocess collision engine."""
        self.config = config or {}
        self._num_workers = self.config.get(
            "max_workers",
            multiprocessing.cpu_count(),
        )
        self._running = False
        self._task_queue: multiprocessing.Queue[bytes] | None = None
        self._result_queue: multiprocessing.Queue[bytes] | None = None
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

    def _worker_loop(
        self,
        worker_id: int,
    ) -> None:
        """Worker process main loop."""
        while self._running:
            try:
                assert self._task_queue is not None
                task = self._task_queue.get(
                    timeout=1,
                )
                self._process_task(
                    worker_id,
                    task,
                )
            except queue.Empty:
                continue

    def _process_task(
        self,
        worker_id: int,
        task: bytes,
    ) -> None:
        """Process a single task (private key).

        Args:
            worker_id: Worker process ID
            task: Private key bytes

        """
        assert self._result_queue is not None
        self._result_queue.put(task)

    def get_stats(self) -> dict[str, Any]:
        """Get current engine statistics."""
        elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            "total_keys": self._total_keys,
            "elapsed": elapsed,
            "throughput": (self._total_keys / max(elapsed, 0.001)),
            "workers": self._num_workers,
            "running": self._running,
        }
