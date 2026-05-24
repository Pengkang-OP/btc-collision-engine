"""Wizard mode selection step."""


class ModeSelector:
    """Handles mode selection in the setup wizard."""

    def select(self, options: list[str]) -> str:
        """Select a mode from options.

        Args:
            options: Available mode options

        Returns:
            Selected mode

        """
        return options[0] if options else ""
