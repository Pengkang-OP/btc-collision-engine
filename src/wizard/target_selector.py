"""Wizard target address selection step."""


class TargetSelector:
    """Handles target address selection in the setup wizard."""

    def select(self, targets: list[str]) -> list[str]:
        """Select addresses to target.

        Args:
            targets: Available target addresses

        Returns:
            Selected targets

        """
        return targets.copy()
