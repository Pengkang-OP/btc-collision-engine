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

# Find summary with regex
match = re.search(r'(\d+)\s+failed.*?(\d+)\s+passed.*?(\d+)\s+skipped', all_output)
if match:
    f, p, s = match.group(1), match.group(2), match.group(3)
    print(f"FINAL RESULT: {f} failed, {p} passed, {s} skipped")
    total = int(f) + int(p) + int(s)
    print(f"Total: {total}/322 (difference: {322 - total})")

# Also find FAILED lines
for line in all_output.split('\n'):
    if 'FAILED ' in line and ('::' in line or '/' in line):
        print(f"FAIL: {line.strip()[:150]}")
