"""Check current CI test failures by running pytest in a subprocess."""
import subprocess
import sys

# Run pytest collection to find errors
result = subprocess.run(
    [sys.executable, "-m", "pytest", "--collect-only", "-q", "--timeout=60"],
    capture_output=True, text=True, timeout=120
)

# Write full output to file
with open("ci_collect_output.txt", "w", encoding="utf-8") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n\n=== Exit code: {result.returncode} ===\n")

print(f"Output written to ci_collect_output.txt ({len(result.stdout)} + {len(result.stderr)} chars)")
