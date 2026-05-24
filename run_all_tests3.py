import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=line", "--no-header", "--timeout=30"],
    capture_output=True,
    text=True,
)

all_output = result.stdout + "\n===STDERR===\n" + result.stderr
print(all_output[:8000])
print(f"\nEXIT CODE: {result.returncode}")
