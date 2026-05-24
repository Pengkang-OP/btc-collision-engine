import subprocess
import sys
import os
import re

os.chdir(r"f:\Qoder\btc-collision-engine")

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=no", "--no-header", "--timeout=30"],
    capture_output=True,
    text=True,
)

all_output = result.stdout

# Find the final summary line with pattern like "= X failed, Y passed, Z skipped ="
pattern = r'(\d+)\s+failed.*?(\d+)\s+passed.*?(\d+)\s+skipped'
match = re.search(pattern, all_output)
if match:
    print(f"FINAL: {match.group(1)} failed, {match.group(2)} passed, {match.group(3)} skipped")
else:
    # Try alternative pattern
    for line in all_output.split('\n'):
        if 'failed' in line and 'passed' in line and ('=' in line or ':' in line):
            print(f"SUMMARY: {line.strip()}")

# Also print the last few lines
lines = all_output.split('\n')
for line in lines[-5:]:
    if line.strip():
        print(f"LAST: {line.strip()[:200]}")
