import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=line", "--no-header"],
    capture_output=True,
    text=True,
    cwd=r"f:\Qoder\btc-collision-engine",
)

lines = result.stdout.split('\n')
# Print summary
for line in lines:
    if 'failed' in line.lower() and ('passed' in line.lower() or 'skipped' in line.lower()):
        print(line[:200])
    elif line.strip().startswith('FAILED'):
        print(line[:200])

# Also print short summary
for line in lines:
    if 'short test summary' in line:
        idx = lines.index(line)
        for l in lines[idx:]:
            print(l[:200])
