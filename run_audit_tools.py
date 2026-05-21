#!/usr/bin/env python3
"""运行代码审计、安全扫描和类型检查"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent

def main():
    # === 1. BANDIT Security Scan ===
    print("=" * 70)
    print("BANDIT 安全扫描结果 (src/)")
    print("=" * 70)
    bandit_file = BASE / "bandit_report.json"
    if bandit_file.exists():
        with open(bandit_file, "r") as f:
            data = json.load(f)
        results = data.get("results", [])
        metrics = data.get("metrics", {})
        # Summarize by severity
        sev_count = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        conf_count = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for r in results:
            sev_count[r["issue_severity"]] = sev_count.get(r["issue_severity"], 0) + 1
            conf_count[r["issue_confidence"]] = conf_count.get(r["issue_confidence"], 0) + 1
        
        print(f"\nTotal issues found: {len(results)}")
        print(f"  By Severity: HIGH={sev_count.get('HIGH',0)}, MEDIUM={sev_count.get('MEDIUM',0)}, LOW={sev_count.get('LOW',0)}")
        print(f"  By Confidence: HIGH={conf_count.get('HIGH',0)}, MEDIUM={conf_count.get('MEDIUM',0)}, LOW={conf_count.get('LOW',0)}")
        
        # Print LOC metrics
        loc = metrics.get("loc", {})
        if loc:
            print(f"\n  Files scanned: {loc.get('total', 0)}")
            print(f"  Lines of code: {loc.get('total', 0)}")
        
        if results:
            print("\n  Issue Details:")
            for i, r in enumerate(results, 1):
                fname = r["filename"].replace("\\", "/")
                print(f"  [{i}] [{r['issue_severity']}] {r['test_id']}")
                print(f"      File: {fname}:{r['line_number']}")
                print(f"      Message: {r['issue_text'][:120]}")
                print(f"      Confidence: {r['issue_confidence']}")
                print()
        else:
            print("\n  No security issues found.")
    else:
        print("  bandit_report.json not found")

    # === 2. FLAKE8 Code Style ===
    print()
    print("=" * 70)
    print("FLAKE8 代码风格检查结果 (src/)")
    print("=" * 70)
    r = subprocess.run(
        [sys.executable, "-m", "flake8", "src/", "--max-line-length=120", "--statistics", "--count"],
        capture_output=True, text=True, timeout=120
    )
    stdout_lines = [l for l in r.stdout.split("\n") if l.strip()]
    stderr_lines = [l for l in r.stderr.split("\n") if l.strip()]
    
    if stdout_lines:
        print(f"\n  Flake8 output ({len(stdout_lines)} lines):")
        for line in stdout_lines:
            print(f"    {line}")
    if r.returncode != 0:
        print(f"\n  Exit code: {r.returncode} (issues found)")
    else:
        print("\n  Zero issues found.")
    
    # Count specific error types
    error_types = {}
    for line in stdout_lines:
        if ":" in line and line.strip():
            parts = line.split()
            if len(parts) > 1:
                error_types.setdefault(parts[-1], 0)
                error_types[parts[-1]] += 1
    
    if error_types:
        print("\n  Error type breakdown:")
        for etype, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"    {etype}: {count}")

    # === 3. MYPY Type Checking ===
    print()
    print("=" * 70)
    print("MYPY 类型检查结果 (src/core/)")
    print("=" * 70)
    r2 = subprocess.run(
        [sys.executable, "-m", "mypy", "src/core/"],
        capture_output=True, text=True, timeout=120
    )
    mypy_lines = [l for l in r2.stdout.split("\n") if l.strip() and not l.startswith("#")]
    
    if mypy_lines:
        print(f"\n  Mypy output ({len(mypy_lines)} lines):")
        for line in mypy_lines:
            print(f"    {line}")
    else:
        print("\n  No mypy output (may need configuration)")
    
    # Count errors vs notes
    errors = sum(1 for l in mypy_lines if "error:" in l)
    notes = sum(1 for l in mypy_lines if "note:" in l)
    print(f"\n  Errors: {errors}, Notes: {notes}")
    print(f"  Exit code: {r2.returncode}")
    
    # === 4. Summary ===
    print()
    print("=" * 70)
    print("审核结果汇总")
    print("=" * 70)
    print(f"\n  Bandit 安全问题: {len(results)}")
    print(f"  Flake8 代码问题: {'Yes (exit=' + str(r.returncode) + ')' if r.returncode else 'None'}")
    print(f"  Mypy 类型错误: {errors}")
    print()

if __name__ == "__main__":
    main()
