import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

# Run just the lifecycle running test
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/test_acceptance_lifecycle.py::TestKeyCollisionEngineLifecycle::test_lifecycle_running", "-v", "--tb=short", "--no-header", "-p", "no:timeout"],
    capture_output=True,
    text=True,
    timeout=30,
)

output = result.stdout + result.stderr
for line in output.split('\n'):
    if any(kw in line for kw in ['PASSED', 'FAILED', 'ERROR', 'AssertionError', 'RuntimeError', 'assert ']):
        print(line[:200])
    elif line.startswith('E '):
        print(line[:200])

print(f"\nRC: {result.returncode}")
