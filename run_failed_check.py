import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

tests = [
    "tests/acceptance/test_acceptance_engine.py::TestKeyCollisionEngineBlackBox::test_black_box_init_with_valid_targets",
    "tests/acceptance/test_acceptance_lifecycle.py::TestKeyCollisionEngineLifecycle::test_lifecycle_initialization",
    "tests/acceptance/test_acceptance_engine.py::TestKeyCollisionEngineMultiState::test_state_running",
]

result = subprocess.run(
    [sys.executable, "-m", "pytest"] + tests + ["-v", "--tb=short", "--no-header", "-p", "no:timeout"],
    capture_output=True,
    text=True,
    timeout=120,
)

all_output = result.stdout + result.stderr
for line in all_output.split('\n'):
    if any(kw in line for kw in ['PASSED', 'FAILED', 'ERROR', 'AssertionError', 'Error', 'assert ']):
        print(line[:200])
    elif line.startswith('E '):
        print(line[:200])
