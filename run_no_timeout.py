import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

# Run tests with -p no:timeout to disable timeout plugin
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=no", "--no-header", "-p", "no:timeout"],
    capture_output=True,
    text=True,
    timeout=600,
)

all_output = result.stdout
lines = all_output.split('\n')

# Find summary line
for line in lines:
    if 'failed' in line and 'passed' in line and ('=' in line or ':' in line) and line.strip():
        print(f"SUMMARY: {line.strip()}")

# Print last 5 non-empty
non_empty = [l for l in lines if l.strip() and not l.strip().startswith('File ') and not l.strip().startswith('C:')]
for line in non_empty[-10:]:
    print(line[:200])
