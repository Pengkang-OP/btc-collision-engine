"""Wizard GPU device selection step."""


class GPUSelector:
    """Handles GPU device selection in the setup wizard."""

    def select(self, devices: list[dict]) -> list[int]:
        """Select GPU devices to use.

        Args:
            devices: Available GPU devices

        Returns:
            Selected device indices
        """
        return [d.get("index", i) for i, d in enumerate(devices)]
