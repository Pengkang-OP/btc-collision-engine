"""Wizard option selection step."""

from typing import Any


class OptionSelector:
    """Handles option selection in the setup wizard."""

    def select(
        self,
        options: list[dict[str, Any]],
        key: str,
    ) -> str | None:
        """Select an option by key.

        Args:
            options: List of option dicts with 'key' field
            key: Selection key

        Returns:
            Selected option value or None

        """
        for opt in options:
            if opt.get("key") == key:
                return opt.get("value")
        return None
