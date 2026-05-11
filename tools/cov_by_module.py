"""按模块分批运行 pytest --cov 并汇总覆盖率，从低到高排序。"""
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).parent.parent
TESTS = PROJECT / "tests"

# 模块 → 测试文件映射 (非GPU)
MODULES = {
    "web": ["test_web*.py"],
    "wizard": ["test_wizard*.py", "test_first_run_wizard.py"],
    "utils": [
        "test_data_cleanup.py", "test_exceptions.py", "test_fast_json.py",
        "test_health_check.py", "test_logger.py", "test_logging_config.py",
        "test_helpers.py", "test_exception_handling.py",
        "test_data_conversion.py", "test_document_quality.py",
        "test_log_throttling.py", "test_security_log_filter.py",
        "test_utils.py", "test_utils_core.py",
        "test_platform_utils.py", "test_performance_monitor.py",
        "test_platform_check.py", "test_file_utils.py",
    ],
    "monitoring": [
        "test_alert_notifications.py", "test_alert_system.py",
        "test_alert_system_integration.py", "test_data_logger.py",
        "test_data_logging_integration.py", "test_data_monitor.py",
        "test_enhanced_monitoring.py", "test_engine_monitoring.py",
        "test_monitor_config.py", "test_monitoring_integration.py",
        "test_notification_channels.py", "test_optimization_monitor.py",
        "test_event_bus.py", "test_event_system.py",
    ],
    "logging": [
        "test_log_collector.py", "test_log_processor.py",
        "test_log_query.py", "test_log_storage.py", "test_log_window.py",
        "test_logging_module.py", "test_log_compatibility.py",
    ],
    "config": [
        "test_config_manager.py", "test_config_hot_reload.py",
        "test_config_coordinator.py", "test_config_migration.py",
        "test_config_validation_consistency.py",
    ],
    "i18n": ["test_i18n.py"],
    "collision": [
        "test_collision_core.py", "test_collision_stats.py",
        "test_key_collision_engine.py", "test_match_storage.py",
        "test_address_matching_flow.py", "test_checkpoint_manager.py",
        "test_memory_pool.py", "test_memory_pool_fix.py",
        "test_memory_locking.py", "test_dependency_injection.py",
        "test_deduplication_filter.py", "test_boundary_values.py",
    ],
    "core": [
        "test_core_crypto.py", "test_core_fixes_verification.py",
        "test_bigint_optimizer.py", "test_crypto_backend.py",
        "test_bitcoin_key_validation.py", "test_address_generator_base.py",
        "test_key_generator_entropy.py", "test_entropy_check.py",
        "test_known_keypair_verification.py",
    ],
    "cli": [
        "test_cli.py", "test_cli_integration.py",
        "test_cli_advanced_features.py", "test_commands.py",
    ],
}


def parse_coverage_table(output: str) -> dict:
    """解析 coverage 表，返回 {filepath: (stmts, miss, cover%)} """
    result = {}
    in_table = False
    for line in output.split("\n"):
        if line.startswith("---") or line.startswith("==="):
            continue
        if line.startswith("Name") and "Stmts" in line:
            in_table = True
            continue
        if line.startswith("TOTAL"):
            in_table = False
            continue
        if in_table:
            parts = line.strip().split()
            if len(parts) >= 4:
                fpath = parts[0]
                try:
                    stmts = int(parts[1])
                    miss = int(parts[2])
                    cover_str = parts[3].rstrip("%")
                    cover = int(cover_str) if cover_str else 0
                    result[fpath] = (stmts, miss, cover)
                except (ValueError, IndexError):
                    pass
    return result


def module_coverage(module_files: list[str], mod_name: str = "") -> dict:
    """运行指定模块测试并返回覆盖率。"""
    test_paths = []
    for pattern in module_files:
        matches = list(TESTS.glob(pattern))
        test_paths.extend(matches)

    if not test_paths:
        return {}

    test_args = [str(t.relative_to(PROJECT)) for t in test_paths]
    cmd = [
        sys.executable, "-m", "pytest",
        *test_args,
        "--tb=no", "--cov=src", f"--cov={mod_name}", "--cov-report=term",
        "-m", "not (gpu or gpu_kernel)",
        "-p", "no:cacheprovider", "-q",
    ]

    try:
        result = subprocess.run(
            cmd, cwd=str(PROJECT),
            capture_output=True, text=True, timeout=300,
        )
        combined = result.stdout + "\n" + result.stderr
        return parse_coverage_table(combined)
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ 超时")
        return {}
    except Exception as e:
        print(f"  ⚠️ 错误: {e}")
        return {}


def main():
    results = {}

    order = ["web", "wizard", "utils", "logging", "config", "i18n", "collision", "core", "cli"]

    for mod_name in order:
        patterns = MODULES.get(mod_name, [])
        if not patterns:
            continue
        print(f"\n{'='*60}")
        print(f"📦 模块: {mod_name} ({len(patterns)} 测试文件)")
        print(f"{'='*60}")
        cov_data = module_coverage(patterns, mod_name)

        mod_total_stmts = 0
        mod_total_miss = 0
        for fpath, (stmts, miss, cover) in cov_data.items():
            if f"src/{mod_name}/" in fpath or f"src\\{mod_name}\\" in fpath:
                mod_total_stmts += stmts
                mod_total_miss += miss

        if mod_total_stmts > 0:
            mod_cover = round((mod_total_stmts - mod_total_miss) / mod_total_stmts * 100, 1)
        else:
            mod_cover = 0.0

        results[mod_name] = {
            "stmts": mod_total_stmts,
            "miss": mod_total_miss,
            "cover": mod_cover,
            "files_tested": len([f for f in cov_data if f"src/{mod_name}/" in f or f"src\\{mod_name}\\" in f]),
        }

        print(f"  → {mod_name}: {mod_cover:.1f}% ({mod_total_stmts - mod_total_miss}/{mod_total_stmts} stmts)")

    print(f"\n\n{'='*60}")
    print("📊 汇总：按覆盖率从低到高")
    print(f"{'='*60}")
    print(f"{'模块':<15} {'覆盖%':>8} {'覆盖行':>10} {'总行数':>8} {'文件数':>8}")
    print("-" * 55)
    for mod_name in sorted(results, key=lambda m: results[m]["cover"]):
        r = results[mod_name]
        covered = r["stmts"] - r["miss"]
        print(f"{mod_name:<15} {r['cover']:>7.1f}% {covered:>10} {r['stmts']:>8} {r['files_tested']:>8}")


if __name__ == "__main__":
    main()
