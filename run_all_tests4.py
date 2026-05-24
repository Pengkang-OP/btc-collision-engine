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

# Find failed tests
failed = []
passed = 0
skipped = 0
final = ""
for line in all_output.split('\n'):
    if 'FAILED ' in line and ('::' in line or '/' in line):
        failed.append(line.strip()[:150])
    elif 'passed' in line and 'failed' in line and '=' in line:
        final = line.strip()
    elif 'PASSED' in line:
        passed += 1
    elif 'SKIPPED' in line:
        skipped += 1

print(f"Final: {final}")
print(f"PASSED count from output: {passed}, SKIPPED: {skipped}")
print(f"\nFAILED ({len(failed)}):")
for f in failed:
    print(f"  {f}")
