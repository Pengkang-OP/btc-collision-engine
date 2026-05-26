"""Wizard interface definitions."""

from ..utils import get_configured_logger
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = get_configured_logger(__name__)


class WizardMode(Enum):
    """Wizard operation mode."""

    INTERACTIVE = "interactive"
    COMPACT = "compact"
    AUTO = "auto"


@dataclass
class WizardConfig:
    """Wizard configuration."""

    mode: WizardMode = WizardMode.INTERACTIVE
    show_intro: bool = True
    show_summary: bool = True
    validate_input: bool = True
    auto_continue: bool = False
    countdown_seconds: int = 5


@dataclass
class WizardResult:
    """Wizard execution result."""

    success: bool = False
    targets: list[str] = field(default_factory=list)
    target_file: str = ""
    mode: str = ""
    checkpoint: bool = False
    dedup: bool = False
    duration: float = 0.0
    gpu_indices: list[int] = field(default_factory=list)
    use_multi_gpu: bool = False
    error_message: str = ""
    start_key: str = ""
    end_key: str = ""
    command: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "targets": self.targets,
            "target_file": self.target_file,
            "mode": self.mode,
            "checkpoint": self.checkpoint,
            "dedup": self.dedup,
            "duration": self.duration,
            "gpu_indices": self.gpu_indices,
            "use_multi_gpu": self.use_multi_gpu,
            "error_message": self.error_message,
            "start_key": self.start_key,
            "end_key": self.end_key,
        }

    def build_command(self) -> str:
        """Build command line string."""
        cmd = []
        if self.mode:
            cmd.append(f"--mode {self.mode}")
        if self.targets:
            cmd.append(f"--targets {','.join(self.targets)}")
        if self.checkpoint:
            cmd.append("--checkpoint")
        if self.dedup:
            cmd.append("--dedup")
        return " ".join(cmd)

    def save_to_file(self, filepath: str) -> None:
        """Save result to file."""
        import json

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> "WizardResult | None":
        """Load result from file."""
        import json

        try:
            with open(filepath) as f:
                data = json.load(f)
            result = cls()
            for key, value in data.items():
                setattr(result, key, value)
            return result
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.debug("Failed to load wizard result from file '%s': %s", filepath, e)
            return None


class WizardStep(ABC):
    """Abstract wizard step."""

    @abstractmethod
    def render(self) -> str:
        """Render step UI."""

    @abstractmethod
    def handle_input(self, data: Any) -> bool:
        """Handle user input.

        Returns:
            True if step should advance

        """


class WizardPage(ABC):  # noqa: B024
    """Abstract wizard page."""
