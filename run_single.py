import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

# Run just the simple init test
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/test_acceptance_engine.py::TestKeyCollisionEngineBlackBox::test_black_box_init_with_valid_targets", "-v", "--tb=long", "--no-header", "-p", "no:timeout"],
    capture_output=True,
    text=True,
    timeout=60,
)

print(result.stdout[-2000:])
print(f"\nRC: {result.returncode}")
