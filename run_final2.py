import subprocess
import sys
import os

os.chdir(r"f:\Qoder\btc-collision-engine")

# Run tests without timeout limit for better results
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=no", "--no-header"],
    capture_output=True,
    text=True,
    timeout=300,  # 5min max
)

all_output = result.stdout
lines = all_output.split('\n')

# Print last 10 non-empty lines
non_empty = [l for l in lines if l.strip()]
for line in non_empty[-20:]:
    print(line[:200])
