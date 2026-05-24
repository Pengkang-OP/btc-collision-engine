import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=line", "--no-header"],
    capture_output=True,
    text=True,
    cwd=r"f:\Qoder\btc-collision-engine",
)

# Extract just the FAILURES section
lines = result.stdout.split('\n')
in_failures = False
for line in lines:
    if 'FAILURES' in line and '=' in line:
        in_failures = True
        continue
    if in_failures:
        if 'short test summary' in line:
            break
        print(line[:200])
