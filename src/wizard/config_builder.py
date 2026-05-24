"""Wizard configuration builder."""


class ConfigBuilder:
    """Builds engine configuration from wizard selections."""

    def build(self, selections: dict) -> dict:
        """Build configuration dictionary.

        Args:
            selections: User selections from wizard steps

        Returns:
            Engine configuration dictionary

        """
        return dict(selections)
