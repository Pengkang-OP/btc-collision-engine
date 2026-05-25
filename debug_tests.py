#!/usr/bin/env python3
"""Quick test runner to debug CI failures."""

import subprocess
import sys

tests = [
    "tests/test_data_conversion.py",
    "tests/test_enhanced_monitoring.py::TestEnhancedMonitoringSystemInit",
    "tests/test_data_logger.py::TestDataLoggerErrorRecording",
    "tests/test_data_storage.py::TestSaveCurrentData",
    "tests/test_checkpoint_manager.py::TestCheckpointSaveVariants",
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
    # Print last 20 lines of stdout
    lines = result.stdout.strip().split("\n")
    for line in lines[-20:]:
        print(line)  # noqa: T201
    if result.returncode != 0:
        print(f"FAILED with return code {result.returncode}")  # noqa: T201
        print("STDERR:", result.stderr[-500:] if result.stderr else "")  # noqa: T201
