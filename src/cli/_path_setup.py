"""Path setup for project imports and module discovery."""
import sys
from pathlib import Path

# Ensure src directory is in path
_src_dir = Path(__file__).resolve().parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
