import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=line", "--no-header", "--timeout=30"],
    capture_output=True,
    text=True,
)

output = result.stdout + result.stderr

# Find the final summary line
for line in output.split('\n'):
    if 'failed' in line and 'passed' in line:
        print("FINAL:", line.strip())

# Also count failures
fail_count = 0
pass_count = 0
skip_count = 0
for line in output.split('\n'):
    if ' test ' in line:
        if 'PASSED' in line:
            pass_count += 1
        elif 'FAILED' in line:
            fail_count += 1
            print("FAIL:", line.split(' - ')[0].strip()[:120])
        elif 'SKIPPED' in line:
            skip_count += 1

print(f"\n=== {pass_count} passed, {fail_count} failed, {skip_count} skipped ===")
print(f"Exit: {result.returncode}")
