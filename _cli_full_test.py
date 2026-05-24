# -*- coding: utf-8 -*-
"""CLI Full-Feature Multi-Mode Multi-State Test (v5.1).

Runs comprehensive CLI tests covering ALL modes, GPU configs, parameters,
and edge cases. Uses real GPU hardware (NVIDIA GTX 1660 Ti + Intel Arc A770).

Design:
  Phase 1: Utility/tool commands (instant, no GPU)
  Phase 2: random mode variants (GPU, multi-GPU, checkpoint, dedup)
  Phase 3: range mode variants
  Phase 4: brute_force mode variants
  Phase 5: parameter combinations (verbosity, export, etc.)
  Phase 6: edge cases

Each test runs CLI via subprocess, with short --duration (3-5s) for speed tests.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
CLI_ENTRY = str(PROJECT_DIR / "key_collision_cli.py")
TEST_ADDR = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
RANGE_START = "0x1"
RANGE_END = "0x10000"
TIMEOUT = 60  # max seconds per test

results = []
passed = 0
failed = 0
errors = 0

def green(s): return f"\033[32m{s}\033[0m"
def red(s): return f"\033[31m{s}\033[0m"
def yellow(s): return f"\033[33m{s}\033[0m"
def bold(s): return f"\033[1m{s}\033[0m"

def run_cli(name, args, expect_in=None, expect_not=None,
            duration=None, timeout=TIMEOUT, use_config=True, check_rc=True):
    """Run CLI command and verify output."""
    global passed, failed, errors

    cmd = [sys.executable, CLI_ENTRY]
    if use_config:
        cmd.extend(["--config", str(PROJECT_DIR / "config.json")])
    if duration is not None:
        args = args + ["--duration", str(duration)]
    cmd.extend(args)

    start = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            cwd=str(PROJECT_DIR),
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
        )
        elapsed = time.time() - start
        output = proc.stdout.decode('utf-8', errors='replace') + proc.stderr.decode('utf-8', errors='replace')
        rc = proc.returncode

        checks_ok = True
        details = []

        # Check exit code
        if check_rc and rc != 0:
            details.append(f"Exit code: {rc}")
            checks_ok = False

        if expect_in:
            exp_list = expect_in if isinstance(expect_in, list) else [expect_in]
            for exp in exp_list:
                if exp not in output:
                    details.append(f"Missing: '{exp}'")
                    checks_ok = False

        if expect_not:
            exp_list = expect_not if isinstance(expect_not, list) else [expect_not]
            for exp in exp_list:
                if exp in output:
                    details.append(f"Unexpected: '{exp}'")
                    checks_ok = False

        status = "PASS" if checks_ok else "FAIL"
        if checks_ok:
            passed += 1
            icon = green("OK")
        else:
            failed += 1
            icon = red("FAIL")

        # Extract speed if present
        speed_match = re.search(r'([\d,]+)\s*keys?/s', output)
        speed_str = f" @ {speed_match.group(1)} keys/s" if speed_match else ""

        print(f"  [{icon}] {name} ({elapsed:.1f}s{speed_str})")
        for d in details[:3]:
            print(f"       {red(d)}")

        results.append({
            "name": name, "status": status, "elapsed": elapsed,
            "rc": rc, "details": details, "cmd": " ".join(cmd[-8:]),
        })

    except subprocess.TimeoutExpired:
        errors += 1
        print(f"  [{red('TIMEOUT')}] {name}")
        results.append({"name": name, "status": "TIMEOUT", "elapsed": timeout})
    except Exception as e:
        errors += 1
        print(f"  [{red('ERROR')}] {name}: {e}")
        results.append({"name": name, "status": "ERROR", "elapsed": 0})


# ═══════════════════════════════════════════════════════════════
print()
print(bold("=" * 60))
print(bold(" CLI Full-Feature Multi-Mode Test (v5.1)"))
print(bold("=" * 60))
print(f"  GPUs: NVIDIA GTX 1660 Ti (device 0) + Intel Arc A770 (device 1)")
print(f"  Config: config.json (batch_size=1M, queue_depth=auto, async=true)")
print()

# ═══════════════════════════════════════════════════════════════
# Phase 1: Utility/Tool Commands
# ═══════════════════════════════════════════════════════════════
print(bold("--- Phase 1: Utility/Tool Commands ---"))

run_cli("--version", ["--version"], expect_in=["key_collision_cli", "5.0"], use_config=False, check_rc=False)
run_cli("--examples", ["--examples"], expect_in="示例", use_config=False)
run_cli("--config-check", ["--config-check"], expect_in="OK", use_config=False)
run_cli("--recommend", ["--recommend"], expect_in="推荐", use_config=False)
run_cli("--platform-check", ["--platform-check"], use_config=False)

# --health-check may fail if not all deps present, just check it runs
run_cli("--health-check", ["--health-check"], use_config=False, check_rc=False)
run_cli("--validate-addresses",
        ["--validate-addresses", str(PROJECT_DIR / "test_data" / "test_targets.json")],
        use_config=False)


# ═══════════════════════════════════════════════════════════════
# Phase 2: Random Mode Variants
# ═══════════════════════════════════════════════════════════════
print()
print(bold("--- Phase 2: Random Mode ---"))

# 2a: Basic random with auto GPU (--use-gpu, device_index=-1)
run_cli("random + auto GPU", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
], expect_in=["keys/s", "M"], duration=4, timeout=30)

# 2b: NVIDIA GPU explicitly (device 0)
run_cli("random + NVIDIA GPU (dev 0)", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--gpu-device", "0",
], expect_in="keys/s", duration=4, timeout=30)

# 2c: Intel GPU explicitly (device 1)
run_cli("random + Intel GPU (dev 1)", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--gpu-device", "1",
], expect_in="keys/s", duration=4, timeout=30)

# 2d: Multi-GPU mode
run_cli("random + Multi-GPU", [
    "-t", TEST_ADDR, "-m", "random", "--multi-gpu",
], expect_in="keys/s", duration=4, timeout=30)

# 2e: Multi-GPU with specific indices
run_cli("random + Multi-GPU (indices 0 1)", [
    "-t", TEST_ADDR, "-m", "random", "--multi-gpu", "--gpu-indices", "0", "1",
], expect_in="keys/s", duration=4, timeout=30)

# 2f: Multi-GPU with count limit
run_cli("random + Multi-GPU (count=1)", [
    "-t", TEST_ADDR, "-m", "random", "--multi-gpu", "--gpu-count", "1",
], expect_in="keys/s", duration=4, timeout=30)

# 2g: GPU with custom batch size
run_cli("random + GPU batch_size=500000", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--gpu-batch-size", "500000",
], expect_in="keys/s", duration=4, timeout=30)

# 2h: GPU with checkpoint
run_cli("random + GPU + checkpoint", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--checkpoint",
    "--checkpoint-interval", "5",
], expect_in="keys/s", duration=6, timeout=30)

# 2i: GPU with dedup
run_cli("random + GPU + dedup", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--dedup",
], expect_in="keys/s", duration=4, timeout=30)

# 2j: GPU with dedup + checkpoint
run_cli("random + GPU + dedup + checkpoint", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--dedup", "--checkpoint", "--checkpoint-interval", "5",
], expect_in="keys/s", duration=6, timeout=30)


# ═══════════════════════════════════════════════════════════════
# Phase 3: Range Mode Variants
# ═══════════════════════════════════════════════════════════════
print()
print(bold("--- Phase 3: Range Mode ---"))

# 3a: Basic range with GPU
run_cli("range + GPU (NVIDIA)", [
    "-t", TEST_ADDR, "-m", "range",
    "--start", RANGE_START, "--end", RANGE_END,
    "--use-gpu", "--gpu-device", "0",
], expect_in="keys/s", duration=4, timeout=30)

# 3b: Range with Intel GPU
run_cli("range + GPU (Intel)", [
    "-t", TEST_ADDR, "-m", "range",
    "--start", RANGE_START, "--end", RANGE_END,
    "--use-gpu", "--gpu-device", "1",
], expect_in="keys/s", duration=4, timeout=30)

# 3c: Range with multi-GPU
run_cli("range + Multi-GPU", [
    "-t", TEST_ADDR, "-m", "range",
    "--start", RANGE_START, "--end", RANGE_END,
    "--multi-gpu",
], expect_in="keys/s", duration=4, timeout=30)


# ═══════════════════════════════════════════════════════════════
# Phase 4: Brute Force Mode Variants
# ═══════════════════════════════════════════════════════════════
print()
print(bold("--- Phase 4: Brute Force Mode ---"))

# 4a: Basic brute_force with GPU
run_cli("brute_force + GPU (NVIDIA)", [
    "-t", TEST_ADDR, "-m", "brute_force",
    "--start", RANGE_START,
    "--use-gpu", "--gpu-device", "0",
], expect_in="keys/s", duration=4, timeout=30)

# 4b: Brute force with Intel GPU
run_cli("brute_force + GPU (Intel)", [
    "-t", TEST_ADDR, "-m", "brute_force",
    "--start", RANGE_START,
    "--use-gpu", "--gpu-device", "1",
], expect_in="keys/s", duration=4, timeout=30)

# ═══════════════════════════════════════════════════════════════
# Phase 5: Parameter Combinations
# ═══════════════════════════════════════════════════════════════
print()
print(bold("--- Phase 5: Parameter Combinations ---"))

# 5a: Verbose mode
run_cli("random + GPU + verbose (-v)", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "-v",
], expect_in="keys/s", duration=3, timeout=30)

# 5b: Very verbose (-vv)
run_cli("random + GPU + verbose (-vv)", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "-vv",
], expect_in="keys/s", duration=3, timeout=30)

# 5c: Sensitive mode hash_only
run_cli("random + GPU + sensitive=hash_only", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--sensitive-mode", "hash_only",
], expect_in="keys/s", duration=3, timeout=30)

# 5d: Export progress
run_cli("random + GPU + export-progress", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--export-progress", str(PROJECT_DIR / "_test_progress.json"),
], expect_in="keys/s", duration=3, timeout=30)

# 5e: No color
run_cli("random + GPU + no-color", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--no-color",
], expect_in="keys/s", duration=3, timeout=30)

# 5f: English language
run_cli("random + GPU + en_US", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--language", "en_US",
], expect_in="keys", duration=3, timeout=30)


# ═══════════════════════════════════════════════════════════════
# Phase 6: Edge Cases
# ═══════════════════════════════════════════════════════════════
print()
print(bold("--- Phase 6: Edge Cases ---"))

# 6a: NVIDIA GPU with extra workers
run_cli("random + NVIDIA + workers=2", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--gpu-device", "0", "--workers", "2",
], expect_in="keys/s", duration=3, timeout=30)

# 6b: Intel GPU with auto-tune
run_cli("random + Intel + auto-tune", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--gpu-device", "1", "--auto-tune",
], expect_in="keys/s", duration=4, timeout=30)

# 6c: NVIDIA with progress-interval
run_cli("random + NVIDIA + progress-interval=2", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--gpu-device", "0", "--progress-interval", "2",
], expect_in="keys/s", duration=4, timeout=30)

# 6d: Skip security check
run_cli("random + GPU + skip-security-check", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu", "--skip-security-check",
], expect_in="keys/s", duration=3, timeout=30)

# 6e: Fast quick-run (different starting config)
run_cli("quick-run with GPU", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--gpu-device", "0", "--quick-run",
], duration=3, timeout=30)

# 6f: Template + run
run_cli("template quick-test + run", [
    "-t", TEST_ADDR, "-m", "random", "--use-gpu",
    "--template", "quick-test",
], duration=3, timeout=30)


# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print()
print(bold("=" * 60))
print(bold(" Test Summary"))
print(bold("=" * 60))
print(f"  {green('PASSED')}: {passed}")
print(f"  {red('FAILED')}: {failed}")
print(f"  {yellow('ERRORS')}: {errors}")
total = passed + failed + errors
print(f"  Total: {total}")

# Show failures
if failed > 0:
    print()
    print(red("Failures:"))
    for r in results:
        if r["status"] == "FAIL":
            print(f"  - {r['name']}: {r['details']}")

if errors > 0:
    print()
    print(yellow("Errors:"))
    for r in results:
        if r["status"] in ("ERROR", "TIMEOUT"):
            print(f"  - {r['name']}: {r['status']}")

# Save results
with open(PROJECT_DIR / "_cli_full_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print()
print(f"Results saved to _cli_full_test_results.json")

# Cleanup test artifacts
for fname in ["_test_progress.json"]:
    fp = PROJECT_DIR / fname
    if fp.exists():
        fp.unlink()

# Exit code
sys.exit(0 if failed == 0 and errors == 0 else 1)
