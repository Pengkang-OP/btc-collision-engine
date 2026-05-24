"""Cross-vendor GPU test - NVIDIA + Intel, single & multi."""
import subprocess, sys, os, time

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'
env['PYTHONUTF8'] = '1'
target = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'

tests = [
    # === Single GPU per vendor ===
    ('-m random --use-gpu --duration 3', 'auto_best_gpu'),
    ('-m random --use-gpu --gpu-device 0 --duration 3', 'nvidia_1660ti'),
    ('-m random --use-gpu --gpu-device 1 --duration 3', 'intel_arc_a770'),

    # === Multi-GPU same vendor (single card per vendor, tests multi-GPU path) ===
    ('-m random --multi-gpu --duration 3 --gpu-indices 0', 'multi_nvidia_only'),
    ('-m random --multi-gpu --duration 3 --gpu-indices 1', 'multi_intel_only'),

    # === Cross-vendor Multi-GPU ===
    ('-m random --multi-gpu --duration 3', 'multi_auto_all'),
    ('-m random --multi-gpu --duration 3 --gpu-indices 0 1', 'multi_nv_intel_both'),

    # === Single GPU per vendor - other modes ===
    ('-m range --use-gpu --gpu-device 0 --start 1 --duration 2', 'nv_range'),
    ('-m brute_force --use-gpu --gpu-device 0 --duration 2', 'nv_bruteforce'),
    ('-m range --use-gpu --gpu-device 1 --start 1 --duration 2', 'intel_range'),
    ('-m brute_force --use-gpu --gpu-device 1 --duration 2', 'intel_bruteforce'),
]

outfile = 'f:/Qoder/btc-collision-engine/_xvendor_result.txt'
results = []

for args_str, name in tests:
    start = time.time()
    try:
        r = subprocess.run(
            [sys.executable, '-X', 'utf8', '-m', 'src', '-t', target] + args_str.split(),
            capture_output=True, timeout=40, env=env
        )
        elapsed = time.time() - start
        stdout = r.stdout.decode('utf-8', errors='replace')
        stderr = r.stderr.decode('utf-8', errors='replace')
        combined = stdout + stderr

        has_error = 'ERROR' in combined.upper() or 'Exception' in combined or 'Traceback' in combined

        # Extract speed
        speed = None
        for line in stdout.split('\n'):
            if 'keys/s' in line:
                try:
                    val = line.split('keys/s')[0].strip().split()[-1].replace(',', '')
                    speed = float(val)
                    break
                except:
                    pass

        # Extract device info
        device_info = []
        for line in combined.split('\n'):
            if 'GPU设备' in line and ('GeForce' in line or 'Arc' in line or 'Intel' in line or 'NVIDIA' in line):
                device_info.append(line.strip()[:120])
            if '异步' in line and '执行' in line:
                device_info.append(line.strip()[:120])

        status = 'PASS' if r.returncode == 0 and not has_error else 'FAIL'
        if speed and speed < 5000:
            status = 'FAIL(slow)'

        speed_str = f'{speed:,.0f}' if speed else '-'
        line = f'[{status:12s}] {name:25s} RC={r.returncode} speed={speed_str} time={elapsed:.1f}s'
        print(line)
        results.append((name, status, speed, elapsed, line))
    except subprocess.TimeoutExpired:
        line = f'[TIMEOUT     ] {name}'
        print(line)
        results.append((name, 'TIMEOUT', None, 0, line))

# Summary
pass_count = sum(1 for _, s, *_ in results if 'PASS' in s)
fail_count = sum(1 for _, s, *_ in results if s == 'FAIL')
timeout_count = sum(1 for _, s, *_ in results if s == 'TIMEOUT')

summary = f'\n{"="*70}\n'
summary += f'Results: {pass_count} PASS / {fail_count} FAIL / {timeout_count} TIMEOUT / {len(results)} total\n\n'
summary += 'GPU Speed Comparison:\n'
for name, status, speed, elapsed, _ in results:
    if speed and speed > 0:
        summary += f'  {name:30s} {speed:>12,.0f} keys/s  ({elapsed:.1f}s) [{status}]\n'
    else:
        summary += f'  {name:30s} {"N/A":>12s}              ({elapsed:.1f}s) [{status}]\n'
summary += '='*70

print(summary)

with open(outfile, 'w', encoding='utf-8') as f:
    for _, _, _, _, line in results:
        f.write(line + '\n')
    f.write(summary)
