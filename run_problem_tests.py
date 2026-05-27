"""Run known problematic test files and report failures."""
import subprocess
import sys
import glob

test_files = [
    'tests/unit/crypto/test_crypto_backend.py',
    'tests/unit/crypto/test_crypto_backend_edge.py',
    'tests/unit/crypto/test_bitcoin_key_validator.py',
    'tests/unit/crypto/test_key_generator.py',
    'tests/test_driver_manager.py',
    'tests/test_multi_gpu.py',
    'tests/test_p1_5_live_range_count_fix.py',
]

# Verify all files exist
for tf in test_files:
    matches = glob.glob(tf)
    if not matches:
        print(f"MISSING: {tf}")

print(f"Running {len(test_files)} files...")

result = subprocess.run(
    [sys.executable, '-m', 'pytest'] + test_files + ['--timeout=60', '-q', '--tb=line'],
    capture_output=True, text=True, timeout=300
)

# Extract summary from stdout
out_lines = result.stdout.split('\n')
summary_started = False
for line in out_lines:
    if ('FAILED' in line or 'ERROR' in line or 'passed' in line
            or 'failed' in line or 'error' in line or '==' in line):
        if 'test_' in line or '==' in line:
            print(line)

print(f"\nExit code: {result.returncode}")

# Save full output
with open('ci_problem_full.txt', 'w', encoding='utf-8') as f:
    f.write(result.stdout)
