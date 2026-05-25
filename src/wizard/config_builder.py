"""Wizard configuration builder."""

from typing import Any


class ConfigBuilder:
    """Builds engine configuration from wizard selections."""

    def build(self, selections: dict[str, Any]) -> list[str]:
        """Build command-line arguments from wizard selections.

        Args:
            selections: User selections from wizard steps

        Returns:
            Command-line argument list for the collision engine

        """
        cmd = ["python", "key_collision_cli.py"]
        mode = selections.get("mode", "")
        if mode:
            cmd.extend(["-m", str(mode)])
        targets = selections.get("targets", [])
        if targets:
            cmd.extend(["-t", ",".join(targets)])
        if selections.get("checkpoint"):
            cmd.append("--checkpoint")
        if selections.get("dedup"):
            cmd.append("--dedup")
        return cmd
