import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/acceptance/", "-q", "--tb=short", "--no-header"],
    capture_output=True,
    text=True,
    cwd=r"f:\Qoder\btc-collision-engine",
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500])
print(f"\nExit code: {result.returncode}")
