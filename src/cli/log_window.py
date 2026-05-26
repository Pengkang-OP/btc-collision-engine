"""CLI log display window."""

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)


class LogWindow:
    """Displays logs in a scrollable terminal window."""

    def __init__(self, max_lines: int = 100):
        self._lines: list[str] = []
        self._max_lines = max_lines

    def add_line(self, line: str) -> None:
        """Add a log line.

        Args:
            line: Log text

        """
        self._lines.append(line)
        if len(self._lines) > self._max_lines:
            self._lines.pop(0)

    def render(self) -> str:
        """Render window contents.

        Returns:
            Formatted window string

        """
        return "\n".join(self._lines[-20:])
