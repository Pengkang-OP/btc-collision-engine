"""批量测试之前有问题的文件"""
import sys
import subprocess

files = [
    "tests/test_dependency_injection.py",
    "tests/test_enhanced_monitoring.py",
    "tests/test_utf8_helper.py",
    "tests/test_first_run_wizard.py",
    "tests/test_p1_3_k_range_validation.py",
    "tests/unit/collision/test_deduplication_filter.py",
    "tests/test_multi_format_conversion.py",
    "tests/test_windows_permission_retry.py",
    "tests/test_memory_pool.py",
    "tests/test_secure_key_manager.py",
    "tests/test_event_system.py",
    "tests/test_simd_optimizer_edge.py",
]

for f in files:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", f, "--timeout=60", "--tb=line", "-q"],
        capture_output=True, text=True, cwd="f:/Qoder/btc-collision-engine",
        timeout=120,
    )
    # Extract the last line of output
    lines = result.stdout.strip().split("\n")
    summary = lines[-1] if lines else "NO OUTPUT"
    print(f"{f:60s} => {summary}")
