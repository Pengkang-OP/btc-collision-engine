import subprocess
import sys
import os
import io

os.chdir(r"f:\Qoder\btc-collision-engine")

# Use a file to capture output to avoid encoding issues
output_file = "final_test_output.txt"

with open(output_file, "w", encoding="utf-8", errors="replace") as f:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=no", "--no-header", "-p", "no:cacheprovider"],
        stdout=f,
        stderr=subprocess.STDOUT,
        timeout=180,
    )

# Read back with error handling
with open(output_file, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

import re

# Extract summary
for line in content.split('\n'):
    # Look for the short test summary info
    if 'failed' in line and 'passed' in line and ('=' in line or ':' in line):
        print(f"SUMMARY: {line.strip()}")

# Find the summary at the bottom
lines = content.split('\n')
for line in lines[-20:]:
    if line.strip():
        print(line.strip()[:200])
