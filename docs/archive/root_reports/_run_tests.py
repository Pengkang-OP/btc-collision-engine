import subprocess
import sys

r = subprocess.run(
    [sys.executable, '-m', 'pytest', 'tests/', 
     '--tb=line', '-q', '--no-header',
     '--ignore=tests/test_m3_optimization_benchmark.py',
     '--ignore=tests/archive'],
    capture_output=True, text=True, timeout=300,
    cwd=r'f:\Qoder\btc-collision-engine'
)

with open(r'f:\Qoder\btc-collision-engine\_test_result.txt', 'w', encoding='utf-8') as f:
    lines = r.stdout.strip().split('\n')
    # Write last 40 lines of stdout
    f.write("=== STDOUT (last 40 lines) ===\n")
    for line in lines[-40:]:
        f.write(line + '\n')
    f.write(f"\n=== RETURN CODE: {r.returncode} ===\n")
