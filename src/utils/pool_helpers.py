"""Thread pool cleanup helpers for memory pool management."""

import logging
import threading
import time

logger = logging.getLogger(__name__)


class _CleanupThreadState:
    """Shared state for cleanup thread management."""

    def __init__(self):
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None


def run_cleanup_loop_safely(
    state: _CleanupThreadState,
    interval: float,
    name: str,
    cleanup_fn,
    on_memory_error: str = "continue",
) -> None:
    """Run a cleanup loop with safe error handling.

    Args:
        state: Cleanup thread state
        interval: Sleep interval between cleanup runs
        name: Thread name for logging
        cleanup_fn: Callback to execute each cycle
        on_memory_error: Action on memory errors ('continue' or 'raise')

    """
    while not state.stop_event.is_set():
        try:
            cleanup_fn()
        except MemoryError:
            if on_memory_error == "raise":
                raise
            logger.warning(
                "%s: memory error during cleanup, continuing", name,
            )
        except Exception as e:
            logger.error(
                "%s: cleanup error: %s", name, e,
            )
        time.sleep(interval)


def start_cleanup_thread(
    state: _CleanupThreadState,
    loop_fn,
    interval: float,
    name: str,
) -> None:
    """Start a background cleanup thread.

    Args:
        state: Cleanup thread state
        loop_fn: Loop function to run
        interval: Sleep interval
        name: Thread name

    """
    if state.thread and state.thread.is_alive():
        return
    state.stop_event.clear()
    thread = threading.Thread(
        target=loop_fn,
        args=(interval,),
        name=name,
        daemon=True,
    )
    thread.start()
    state.thread = thread
    logger.debug("Cleanup thread '%s' started", name)


def stop_cleanup_thread(
    state: _CleanupThreadState,
    name: str,
    timeout: float = 5.0,
) -> None:
    """Stop a background cleanup thread.

    Args:
        state: Cleanup thread state
        name: Thread name
        timeout: Max seconds to wait for thread

    """
    state.stop_event.set()
    if state.thread and state.thread.is_alive():
        state.thread.join(timeout=timeout)
    state.thread = None
    logger.debug("Cleanup thread '%s' stopped", name)
