#!/usr/bin/env python3
"""Quick test runner for CI failures."""

import subprocess
import sys

tests = [
    "tests/test_data_conversion.py",
    "tests/test_checkpoint_manager.py::TestCheckpointSaveVariants",
    "tests/test_enhanced_monitoring.py::TestEnhancedMonitoringSystemInit",
]

for test in tests:
    print(f"\n{'=' * 60}")  # noqa: T201
    print(f"Running: {test}")  # noqa: T201
    print("=" * 60)  # noqa: T201
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test, "-v", "--tb=line", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd="f:\\Qoder\\btc-collision-engine",
    )
    # Print last 30 lines of stdout
    lines = result.stdout.strip().split("\n")
    for line in lines[-30:]:
        print(line)  # noqa: T201
    if result.returncode != 0:
        print(f"FAILED with return code {result.returncode}")  # noqa: T201
        # Print last 10 lines of stderr
        err_lines = result.stderr.strip().split("\n")
        for line in err_lines[-10:]:
            print(line)  # noqa: T201
