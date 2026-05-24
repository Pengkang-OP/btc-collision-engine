import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

with open("test_output.txt", "w") as outfile:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=no", "--no-header"],
        stdout=outfile,
        stderr=subprocess.STDOUT,
        timeout=120,
    )

# Read back
with open("test_output.txt", "r") as f:
    content = f.read()

# Print last lines
lines = content.strip().split('\n')
for line in lines[-15:]:
    print(line[:200])

# Find summary
import re
for line in lines:
    match = re.search(r'(\d+)\s+failed.*?(\d+)\s+passed.*?(\d+)\s+skipped', line)
    if match:
        print(f"\n=== FINAL: {match.group(1)} failed, {match.group(2)} passed, {match.group(3)} skipped ===")
