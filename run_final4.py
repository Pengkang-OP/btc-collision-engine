import subprocess
import sys
import os
import re

os.chdir(r"f:\Qoder\btc-collision-engine")

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=no", "--no-header"],
    capture_output=True,
    text=True,
    timeout=120,
)

all_output = result.stdout + result.stderr

match = re.search(r'(\d+)\s+failed.*?(\d+)\s+passed.*?(\d+)\s+skipped', all_output)
if match:
    f, p, s = match.group(1), match.group(2), match.group(3)
    print(f"RESULT: {f} failed, {p} passed, {s} skipped")

# Check for any FAILED
for line in all_output.split('\n'):
    if 'FAILED ' in line and '::' in line:
        print(f"FAIL: {line.strip()[:150]}")
    if 'ERRORS' in line:
        print(f"ERROR: {line.strip()[:150]}")
    if 'passed' in line and 'failed' in line and '=' in line:
        print(f"SUMMARY: {line.strip()}")
