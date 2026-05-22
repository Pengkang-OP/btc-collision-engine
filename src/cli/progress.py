"""Progress display utilities for CLI."""
import sys
import time
from typing import Any


class ProgressBar:
    """Simple progress bar for CLI display."""

    def __init__(self, total: int, width: int = 40):
        self.total = total
        self.width = width
        self._start = time.time()

    def update(self, current: int) -> None:
        """Update progress bar display.

        Args:
            current: Current progress value
        """
        if self.total <= 0:
            return
        ratio = min(current / self.total, 1.0)
        filled = int(self.width * ratio)
        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = time.time() - self._start
        rate = current / max(elapsed, 0.001)
        sys.stdout.write(
            f"\r|{bar}| {ratio:.0%} "
            f"[{rate:.0f} keys/s]"
        )
        sys.stdout.flush()

    def finish(self) -> None:
        """Clear progress display."""
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
