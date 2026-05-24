"""CLI constants and defaults."""

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_INVALID_CONFIG = 2
EXIT_GPU_ERROR = 3

# Output formatting
PROGRESS_BAR_WIDTH = 40
DEFAULT_PAGE_SIZE = 20

# Config file paths
CONFIG_FILE_NAME = "config.json"
CONFIG_EXAMPLE_FILE = "config.example.json"
WIZARD_MARKER_PATH = ".wizard_completed"

# Required config sections
REQUIRED_CONFIG_SECTIONS = [
    "collision",
    "engine",
    "logging",
    "monitoring",
    "gpu",
    "crypto",
    "security",
]

# Separator lines for CLI output
SEPARATOR_EQUAL = "=" * 64
SEPARATOR_DASHED = "-" * 64
SEPARATOR_DASHED_SHORT = "-" * 40
