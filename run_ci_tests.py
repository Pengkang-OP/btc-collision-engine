"""Quick test runner for CI failures."""
import subprocess
import sys

tests = [
    "tests/test_data_conversion.py",
    "tests/test_checkpoint_manager.py::TestCheckpointSaveVariants",
    "tests/test_enhanced_monitoring.py::TestEnhancedMonitoringSystemInit",
]

for test in tests:
    print(f"\n{'='*60}")
    print(f"Running: {test}")
    print('='*60)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test, "-v", "--tb=short", "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=r"f:\Qoder\btc-collision-engine"
    )
    # Print last 30 lines of stdout
    lines = result.stdout.strip().split('\n')
    for line in lines[-30:]:
        print(line)
    if result.returncode != 0:
        print(f"FAILED with return code {result.returncode}")
