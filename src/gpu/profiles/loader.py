"""GPU profile loader for configuration presets."""
import json
from pathlib import Path

from ...utils import get_configured_logger

logger = get_configured_logger("GPUProfileLoader")


class GPUProfileLoader:
    """Loads GPU configuration profiles from JSON files."""

    def __init__(
        self,
        profile_dir: str | Path | None = None,
    ):
        self._profile_dir = Path(
            profile_dir
            or Path(__file__).parent / "profiles"
        )

    def load(self, name: str) -> dict:
        """Load a GPU profile by name.

        Args:
            name: Profile name

        Returns:
            Profile configuration dictionary
        """
        filepath = self._profile_dir / f"{name}.json"
        if not filepath.exists():
            logger.warning(
                f"Profile not found: {name}"
            )
            return {}
        with open(filepath) as f:
            return json.load(f)

    def list_profiles(self) -> list[str]:
        """List available GPU profiles.

        Returns:
            List of profile names
        """
        return [
            p.stem
            for p in self._profile_dir.glob("*.json")
        ]
