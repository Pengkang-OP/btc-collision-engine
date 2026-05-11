"""Run pytest with coverage and capture output to file."""
import subprocess
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTEST_NO_FORCE_EXIT"] = "1"

outfile = "test_results/cov_fresh.txt"
cmd = [
    sys.executable, "-m", "pytest", "tests/",
    "--tb=no", "-q",
    "-m", "not (gpu or gpu_kernel)",
    "--cov=src", "--cov-report=term",
    "-p", "no:cacheprovider",
]

print(f"Running: {' '.join(cmd)}")
print(f"Output: {outfile}")

with open(outfile, "w", encoding="utf-8") as f:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    for line in proc.stdout:
        f.write(line)
    proc.wait()

print(f"Exit code: {proc.returncode}")
print("Done. Check test_results/cov_fresh.txt")
