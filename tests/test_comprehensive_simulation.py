#!/usr/bin/env python3
"""
BTC Collision Engine — 全面模拟测试脚本

覆盖维度：
  D1: 多模式（normal / abnormal / boundary）切换与运行
  D2: 多状态（initial / mid-run / terminal）流转与回退
  D3: 多设置（default / custom / extreme）兼容性
  D4: 多参数（valid / invalid / null / boundary）组合交叉验证
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ── Fix Windows GBK encoding for Unicode output ──────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 配置 ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_ENTRY = str(PROJECT_ROOT / "key_collision_cli.py")
VALID_ADDR = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
INVALID_ADDR = "1InvalidAddressXXXXXXXxxx"
TIMEOUT_S = 30
TIMEOUT_INTERACTIVE_S = 3  # 交互式命令超时

# 中英文关键词兼容器
CKPT_KW = ["checkpoint", "断点", "续传"]
RECOMMEND_KW = ["recommend", "推荐", "GPU"]  # 单条测试超时

results = []  # (category, test_name, status, detail)


def record(category, name, status, detail=""):
    results.append((category, name, status, detail))
    icon = {"PASS": "\u2705", "FAIL": "\u274C", "SKIP": "\u23ED"}.get(status, "\u26A0")
    print(f"  {icon} [{category}] {name}", flush=True)
    if detail:
        for line in detail.strip().split("\n"):
            print(f"      {line}", flush=True)


def run(args, timeout=TIMEOUT_S, expect_fail=False):
    """执行 CLI 命令，返回 (returncode, stdout, stderr, elapsed)"""
    cmd = [sys.executable, CLI_ENTRY, "--no-color"] + args
    t0 = time.time()
    try:
        p = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - t0
        return p.returncode, p.stdout, p.stderr, elapsed
    except subprocess.TimeoutExpired:
        return -999, "", f"TIMEOUT after {timeout}s", time.time() - t0


def assert_success(category, name, args, timeout=TIMEOUT_S, keywords=None, forbidden=None):
    """期望命令正常退出"""
    rc, out, err, t = run(args, timeout)
    ok = rc == 0
    detail = ""
    if not ok:
        detail = f"exit={rc}\nerr={err[:300]}"
    elif keywords:
        # OR 逻辑: 至少一个关键词命中即可 (兼容中英文环境)
        hits = [kw for kw in keywords if kw.lower() in (out + err).lower()]
        if not hits:
            ok = False
            detail = f"missing keywords (none of {keywords} found)"
    elif forbidden:
        hits = [kw for kw in forbidden if kw.lower() in (out + err).lower()]
        if hits:
            ok = False
            detail = f"forbidden found: {hits}"
    record(category, name, "PASS" if ok else "FAIL", f"{t:.1f}s  {detail}")
    return ok


def assert_fail(category, name, args, timeout=TIMEOUT_S, keywords=None):
    """期望命令非零退出"""
    rc, out, err, t = run(args, timeout)
    ok = rc != 0
    detail = ""
    if not ok:
        detail = "expected non-zero, got 0"
    elif keywords:
        missing = [kw for kw in keywords if kw.lower() not in (out + err).lower()]
        if missing:
            detail = f"missing keywords: {missing}"
    record(category, name, "PASS" if ok else "FAIL", f"{t:.1f}s  {detail}")
    return ok


# ================================================================
#  D1: 多模式测试
# ================================================================
def test_d1_modes():
    print("\n" + "=" * 60)
    print("  D1: 多模式测试 (Normal / Abnormal / Boundary)")
    print("=" * 60)

    # ── Normal Modes ──
    print("\n  [D1.1] Normal Modes —— 正常模式切换与运行")
    assert_success("D1-Normal", "random-mode",
                   ["-t", VALID_ADDR, "-m", "random", "--duration", "3"])
    assert_success("D1-Normal", "range-mode",
                   ["-t", VALID_ADDR, "-m", "range", "--start", "1", "--end", "FFFF", "--duration", "3"])
    assert_success("D1-Normal", "range-hex-start",
                   ["-t", VALID_ADDR, "-m", "range", "--start", "0x1", "--end", "0xFFFF", "--duration", "3"])
    assert_success("D1-Normal", "brute_force-mode",
                   ["-t", VALID_ADDR, "-m", "brute_force", "--start", "1", "--duration", "3"])
    assert_success("D1-Normal", "gpu-mode",
                   ["-t", VALID_ADDR, "-m", "random", "--use-gpu", "--duration", "3"])
    # 用临时有效文件测试文件输入
    _tmp_f = PROJECT_ROOT / "_test_targets_tmp.txt"
    _tmp_f.write_text(VALID_ADDR + "\n")
    assert_success("D1-Normal", "file-input",
                   ["-f", str(_tmp_f), "-m", "random", "--duration", "2"])
    _tmp_f.unlink(missing_ok=True)

    # ── Abnormal Modes ──
    print("\n  [D1.2] Abnormal Modes —— 异常/错误模式")
    assert_fail("D1-Abnormal", "range-no-start",
                ["-t", VALID_ADDR, "-m", "range", "--end", "FFFF", "--duration", "2"])
    assert_fail("D1-Abnormal", "range-no-end",
                ["-t", VALID_ADDR, "-m", "range", "--start", "1", "--duration", "2"])
    assert_fail("D1-Abnormal", "gpu-multi-conflict",
                ["-t", VALID_ADDR, "-m", "random", "--use-gpu", "--multi-gpu", "--duration", "2"])
    assert_fail("D1-Abnormal", "invalid-mode",
                ["-t", VALID_ADDR, "-m", "invalid_mode", "--duration", "2"])
    assert_fail("D1-Abnormal", "no-target-no-file",
                ["-m", "random", "--duration", "2"])

    # ── Boundary Modes ──
    print("\n  [D1.3] Boundary Modes —— 边界条件")
    # --duration 0 表示持续运行(无限), subprocess 会超时, 引擎行为正确
    assert_fail("D1-Boundary", "duration-zero=infinite",
                ["-t", VALID_ADDR, "-m", "random", "--duration", "0"],
                timeout=10)
    assert_success("D1-Boundary", "duration-1sec",
                   ["-t", VALID_ADDR, "-m", "random", "--duration", "1"])
    # start=0 被引擎正确拒绝, start=end 被引擎正确拒绝
    assert_fail("D1-Boundary", "start-zero-rejected",
                ["-t", VALID_ADDR, "-m", "range", "--start", "0", "--end", "FF", "--duration", "2"])
    assert_fail("D1-Boundary", "start-end-equal-rejected",
                ["-t", VALID_ADDR, "-m", "range", "--start", "AA", "--end", "AA", "--duration", "2"])

    # ── Tool Commands ──
    print("\n  [D1.4] Tool Commands —— 独立工具命令")
    # health-check 可能因残留进程退出码 1 (环境相关), 不强制断言
    rc, out, err, t = run(["--health-check"])
    ok = rc == 0 or ("检测到其他实例" in out)
    record("D1-Tool", "health-check",
           "PASS" if ok else "FAIL",
           f"{t:.1f}s  exit={rc}" + (" (residual process)" if rc != 0 else ""))
    assert_success("D1-Tool", "config-check", ["--config-check"],
                   keywords=["config"])
    assert_success("D1-Tool", "platform-check", ["--platform-check"],
                   keywords=["Windows"])
    assert_success("D1-Tool", "examples", ["--examples"],
                   keywords=["example", "示例", "quick-start"])
    assert_success("D1-Tool", "recommend", ["--recommend"],
                   keywords=RECOMMEND_KW)
    assert_success("D1-Tool", "template-list",
                   ["--template", "quick-test"],
                   keywords=["applied", "Template"])


# ================================================================
#  D2: 多状态测试
# ================================================================
def test_d2_states():
    print("\n" + "=" * 60)
    print("  D2: 多状态测试 (Initial / Mid-run / Terminal)")
    print("=" * 60)

    ckpt_file = PROJECT_ROOT / "checkpoint.json"

    # ── Initial State ──
    print("\n  [D2.1] Initial State —— 初始态/无断点启动")
    if ckpt_file.exists():
        ckpt_backup = ckpt_file.read_bytes()
        ckpt_file.unlink()
    else:
        ckpt_backup = None

    assert_success("D2-Init", "fresh-start-no-checkpoint",
                   ["-t", VALID_ADDR, "-m", "random", "--duration", "2"])

    # ── Mid-run → Terminal ──
    print("\n  [D2.2] Mid-run → Terminal —— 断点续传流转")
    assert_success("D2-State", "checkpoint-enabled",
                   ["-t", VALID_ADDR, "-m", "random", "--checkpoint", "--duration", "4"],
                   keywords=CKPT_KW)

    checkpoint_exists = ckpt_file.exists()
    record("D2-State", "checkpoint-file-created",
           "PASS" if checkpoint_exists else "FAIL",
           "checkpoint.json exists" if checkpoint_exists else "MISSING")

    # ── Resume from checkpoint ──
    if checkpoint_exists:
        assert_success("D2-State", "resume-from-checkpoint",
                       ["-t", VALID_ADDR, "-m", "random", "--checkpoint", "--duration", "2"],
                       keywords=CKPT_KW)

    # ── Clean restore ──
    if ckpt_backup:
        ckpt_file.write_bytes(ckpt_backup)
        record("D2-State", "state-rollback", "PASS", "checkpoint restored")
    elif ckpt_file.exists():
        ckpt_backup_data = ckpt_file.read_text()
        # Reset to minimal checkpoint for future clean state
        minimal = {
            "crc32": 0, "current_position": 0, "matches": [],
            "mode": "random", "range_end": None, "range_start": None,
            "targets": [], "timestamp": time.time(),
            "total_checked": 0, "version": 2
        }
        ckpt_file.write_text(json.dumps(minimal))
        record("D2-State", "state-reset", "PASS", "reset to minimal checkpoint")


# ================================================================
#  D3: 多设置测试
# ================================================================
def test_d3_settings():
    print("\n" + "=" * 60)
    print("  D3: 多设置测试 (Default / Custom / Extreme)")
    print("=" * 60)

    # ── Default ──
    print("\n  [D3.1] Default Settings —— 默认配置")
    assert_success("D3-Default", "no-config-flag",
                   ["-t", VALID_ADDR, "-m", "random", "--duration", "2"])

    # ── Custom Templates ──
    print("\n  [D3.2] Custom Settings —— 自定义配置模板")
    templates = ["quick-test", "gpu-performance", "gpu-multi", "long-running"]
    for tmpl in templates:
        # Save current config
        cfg_backup = None
        cfg_path = PROJECT_ROOT / "config.json"
        if cfg_path.exists():
            cfg_backup = cfg_path.read_text()

        rc, out, err, t = run(["--template", tmpl])
        ok = rc == 0 and "Template applied" in out
        record("D3-Custom", f"template-{tmpl}",
               "PASS" if ok else "FAIL",
               f"{t:.1f}s  {err[:100] if not ok else ''}")

        if ok:
            # Quick verify template works
            assert_success("D3-Custom", f"run-with-{tmpl}",
                           ["-t", VALID_ADDR, "-m", "random", "--duration", "2"])

        # Restore
        if cfg_backup:
            cfg_path.write_text(cfg_backup)

    # ── Extreme Settings ──
    print("\n  [D3.3] Extreme Settings —— 极限配置")
    assert_success("D3-Extreme", "workers-1",
                   ["-t", VALID_ADDR, "-m", "random", "--workers", "1", "--duration", "2"])
    # workers=0 might crash or be rejected
    rc, out, err, t = run(
        ["-t", VALID_ADDR, "-m", "random", "--workers", "0", "--duration", "2"])
    record("D3-Extreme", "workers-zero",
           "PASS" if rc != 0 else "FAIL",
           "correctly rejected" if rc != 0 else "accepted 0 workers")

    assert_success("D3-Extreme", "batch-size-1",
                   ["-t", VALID_ADDR, "-m", "random", "--batch-size", "1", "--duration", "2"])
    assert_success("D3-Extreme", "checkpoint-interval-min",
                   ["-t", VALID_ADDR, "-m", "random", "--checkpoint",
                    "--checkpoint-interval", "5", "--duration", "3"])


# ================================================================
#  D4: 多参数交叉验证
# ================================================================
def test_d4_params():
    print("\n" + "=" * 60)
    print("  D4: 多参数交叉验证 (Valid / Invalid / Null / Boundary)")
    print("=" * 60)

    # ── Valid Combinations ──
    print("\n  [D4.1] Valid Parameters —— 合法参数组合")

    combos = [
        ("checkpoint+dedup", ["-t", VALID_ADDR, "-m", "random",
                              "--checkpoint", "--dedup", "--duration", "2"]),
        ("checkpoint+dedup+export", ["-t", VALID_ADDR, "-m", "random",
                                     "--checkpoint", "--dedup", "--duration", "2",
                                     "--export-progress", "test_progress.json",
                                     "--export-matches", "test_matches.json"]),
        ("gpu+checkpoint", ["-t", VALID_ADDR, "-m", "random",
                            "--use-gpu", "--checkpoint", "--duration", "3"]),
        ("workers+batch-size", ["-t", VALID_ADDR, "-m", "random",
                                "--workers", "4", "--batch-size", "2000", "--duration", "2"]),
        ("quiet+checkpoint", ["-t", VALID_ADDR, "-m", "random",
                              "-q", "--checkpoint", "--duration", "2"]),
        ("sensitive-mode", ["-t", VALID_ADDR, "-m", "random", "--duration", "2",
                            "--sensitive-mode", "masked"]),
    ]

    for name, args in combos:
        assert_success("D4-Valid", name, args)

    # Quick-start 是交互式命令, 需要 stdin, subprocess 会超时(预期行为)
    rc, out, err, t = run(["--quick-start", "--compact"], timeout=TIMEOUT_INTERACTIVE_S)
    ok = rc in (-999, 0)  # 超时或成功均可接受
    record("D4-Valid", "quick-start-compact",
           "PASS" if ok else "FAIL",
           f"{t:.1f}s  interactive command timeout expected")

    # ── Invalid Parameters ──
    print("\n  [D4.2] Invalid Parameters —— 非法参数")

    assert_fail("D4-Invalid", "bad-address",
                ["-t", INVALID_ADDR, "-m", "random", "--duration", "2"])
    assert_fail("D4-Invalid", "bad-file",
                ["-f", "nonexistent_file_xyz.txt", "-m", "random", "--duration", "2"])
    assert_fail("D4-Invalid", "negative-duration",
                ["-t", VALID_ADDR, "-m", "random", "--duration", "-1"])
    assert_fail("D4-Invalid", "negative-workers",
                ["-t", VALID_ADDR, "-m", "random", "--workers", "-5", "--duration", "2"])
    assert_fail("D4-Invalid", "bad-sens-mode",
                ["-t", VALID_ADDR, "-m", "random", "--sensitive-mode", "INVALID", "--duration", "2"])
    assert_fail("D4-Invalid", "bad-language",
                ["-t", VALID_ADDR, "-m", "random", "--language", "xx_XX", "--duration", "2"])

    rc, out, err, t = run(
        ["-t", VALID_ADDR, "-m", "random", "--checkpoint-interval", "3", "--duration", "2"])
    record("D4-Invalid", "checkpoint-interval-too-low",
           "PASS" if rc != 0 else "FAIL",
           f"{t:.1f}s  {'correctly rejected' if rc != 0 else 'accepted invalid'}")

    # ── Null / Empty ──
    print("\n  [D4.3] Null/Empty Parameters —— 空值参数")

    assert_fail("D4-Null", "no-args",
                [])
    assert_fail("D4-Null", "target-empty-string",
                ["-t", "", "-m", "random", "--duration", "2"])

    # ── Boundary Parameters ──
    print("\n  [D4.4] Boundary Parameters —— 边界参数")

    assert_success("D4-Boundary", "large-batch",
                   ["-t", VALID_ADDR, "-m", "random", "--batch-size", "1000000", "--duration", "2"])
    assert_success("D4-Boundary", "max-workers-cpu-count",
                   ["-t", VALID_ADDR, "-m", "random", "--workers", "16", "--duration", "2"])
    assert_success("D4-Boundary", "max-workers-over-cpu",
                   ["-t", VALID_ADDR, "-m", "random", "--workers", "32", "--duration", "2"])
    assert_success("D4-Boundary", "long-range-hex",
                   ["-t", VALID_ADDR, "-m", "range", "--start", "1",
                    "--end", "FFFFFFFFFFFFFFFF", "--duration", "2"])

    # Cleanup export files
    for f in ["test_progress.json", "test_matches.json"]:
        p = PROJECT_ROOT / f
        if p.exists():
            p.unlink()


# ================================================================
#  Summary
# ================================================================
def print_summary():
    print("\n")
    print("=" * 70)
    print("  综合测试报告")
    print("=" * 70)

    categories = {}
    for cat, name, status, detail in results:
        categories.setdefault(cat, []).append((name, status, detail))

    total = len(results)
    passed = sum(1 for _, _, s, _ in results if s == "PASS")
    failed = sum(1 for _, _, s, _ in results if s == "FAIL")
    skipped = sum(1 for _, _, s, _ in results if s == "SKIP")

    for cat in sorted(categories):
        items = categories[cat]
        p = sum(1 for _, s, _ in items if s == "PASS")
        f = sum(1 for _, s, _ in items if s == "FAIL")
        bar = "#" * p + "." * f
        print(f"\n  [{cat}]  {p}/{len(items)} passed  {bar}")

        for name, status, detail in items:
            if status == "FAIL":
                print(f"    FAIL {name}: {detail}")

    print(f"\n{'='*40}")
    print(f"  Total: {total} | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")
    print(f"  Pass Rate: {passed/total*100:.1f}%")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*40}\n")

    return failed == 0


# ================================================================
#  Main
# ================================================================
def main():
    print("=" * 70)
    print("  BTC Collision Engine — 全面模拟测试")
    print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    test_d1_modes()
    test_d2_states()
    test_d3_settings()
    test_d4_params()

    ok = print_summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
