#!/usr/bin/env python3
"""BTC 碰撞引擎 - 统一测试运行器

用法:
    python run_all_tests.py                    # 运行全部测试
    python run_all_tests.py --smoke            # 仅运行冒烟测试
    python run_all_tests.py --unit             # 仅运行单元测试
    python run_all_tests.py --integration      # 仅运行集成测试
    python run_all_tests.py --quick            # 快速模式 (跳过 GPU 和压力测试)
    python run_all_tests.py --ci               # CI 模式 (带覆盖率)
    python run_all_tests.py --list             # 列出所有测试文件
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"

# 测试套件分类
TEST_SUITES = {
    "smoke": [
        "tests/test_smoke.py",
    ],
    "unit_core": [
        "tests/test_core_crypto.py",
        "tests/test_base58_edge.py",
        "tests/test_wif_bech32.py",
        "tests/test_secp256k1_extended.py",
        "tests/test_bitcoin_key_validation.py",
        "tests/test_boundary_values.py",
        "tests/test_entropy_check.py",
    ],
    "unit_logging": [
        "tests/test_log_collector.py",
        "tests/test_log_processor.py",
        "tests/test_log_query.py",
        "tests/test_log_storage.py",
    ],
    "unit_collision": [
        "tests/test_collision_core.py",
        "tests/test_collision_stats.py",
        "tests/test_event_bus.py",
        "tests/test_observers.py",
        "tests/test_match_storage.py",
    ],
    "unit_config": [
        "tests/test_config_manager.py",
        "tests/test_config_coordinator.py",
        "tests/test_config_validation_consistency.py",
    ],
    "unit_cli": [
        "tests/test_cli.py",
    ],
    "unit_health": [
        "tests/test_health_check.py",
    ],
    "unit_utils": [
        "tests/test_utils.py",
        "tests/test_exceptions.py",
        "tests/test_platform_utils.py",
        "tests/test_platform_check.py",
        "tests/test_fast_json.py",
    ],
    "integration": [
        "tests/test_integration_workflow.py",
        "tests/test_end_to_end.py",
        "tests/test_cli_integration.py",
        "tests/test_cli_advanced_features.py",
    ],
    "gpu": [
        "tests/test_gpu_core.py",
        "tests/test_gpu_kernel_correctness.py",
        "tests/test_gpu_kernel_integration.py",
        "tests/test_gpu_device_helper.py",
        "tests/test_gpu_engine_refactored.py",
    ],
    "concurrency": [
        "tests/test_concurrency_stress.py",
    ],
    "regression": [
        "tests/test_regression_suite.py",
    ],
}


def run_pytest(test_files, extra_args=None, verbose=True):
    """运行 pytest 测试"""
    args = [sys.executable, "-m", "pytest"]
    if verbose:
        args.append("-v")
    args.extend(test_files)
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(args, cwd=str(PROJECT_ROOT))


def print_header(title):
    """打印带格式的标题"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def print_summary(results):
    """打印测试摘要"""
    print()
    print("=" * 70)
    print("  测试结果摘要")
    print("=" * 70)

    total_passed = 0
    total_failed = 0

    for name, (returncode, elapsed) in results.items():
        status = "[通过]" if returncode == 0 else "[失败]"
        print(f"  {status} {name}  ({elapsed:.1f}s)")
        if returncode == 0:
            total_passed += 1
        else:
            total_failed += 1

    print()
    print(f"  总计: {total_passed} 通过, {total_failed} 失败")
    print("=" * 70)

    return total_failed == 0


def _select_test_files(args) -> list:
    """根据命令行参数选择要运行的测试文件列表。"""
    if args.smoke:
        return TEST_SUITES["smoke"]
    if args.unit:
        return (
            TEST_SUITES["smoke"]
            + TEST_SUITES["unit_core"]
            + TEST_SUITES["unit_logging"]
            + TEST_SUITES["unit_collision"]
            + TEST_SUITES["unit_config"]
            + TEST_SUITES["unit_cli"]
            + TEST_SUITES["unit_health"]
            + TEST_SUITES["unit_utils"]
            + TEST_SUITES["regression"]
        )
    if args.integration:
        return TEST_SUITES["integration"]
    if args.quick:
        return (
            TEST_SUITES["smoke"]
            + TEST_SUITES["unit_core"]
            + TEST_SUITES["unit_logging"]
            + TEST_SUITES["unit_collision"]
            + TEST_SUITES["unit_config"]
            + TEST_SUITES["unit_cli"]
            + TEST_SUITES["unit_health"]
            + TEST_SUITES["regression"]
            + TEST_SUITES["integration"]
        )
    # 全部测试
    test_files = []
    for suite_files in TEST_SUITES.values():
        test_files.extend(suite_files)
    if not args.gpu:
        test_files = [f for f in test_files if f not in TEST_SUITES["gpu"]]
    return test_files


def _build_pytest_args(args) -> list:
    """构建 pytest 额外参数列表。"""
    extra_args = []
    if args.ci:
        extra_args.extend(["--cov=src", "--cov-report=term-missing", "--cov-report=xml"])
    if args.keyword:
        extra_args.extend(["-k", args.keyword])
    if args.exitfirst:
        extra_args.append("-x")
    if args.quiet:
        extra_args.append("-q")
    return extra_args


def main():
    parser = argparse.ArgumentParser(
        description="BTC 碰撞引擎 - 统一测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_all_tests.py                    # 运行全部测试
  python run_all_tests.py --smoke            # 仅运行冒烟测试
  python run_all_tests.py --unit             # 仅运行单元测试
  python run_all_tests.py --quick            # 快速模式
  python run_all_tests.py --ci               # CI 模式 (带覆盖率)
  python run_all_tests.py --list             # 列出所有测试文件
        """,
    )
    parser.add_argument("--smoke", action="store_true", help="仅冒烟测试")
    parser.add_argument("--unit", action="store_true", help="仅单元测试")
    parser.add_argument("--integration", action="store_true", help="仅集成测试")
    parser.add_argument("--gpu", action="store_true", help="包含 GPU 测试")
    parser.add_argument("--quick", action="store_true", help="快速模式 (跳过慢速测试)")
    parser.add_argument("--ci", action="store_true", help="CI 模式 (带覆盖率)")
    parser.add_argument("--list", action="store_true", help="列出所有测试文件")
    parser.add_argument("--quiet", action="store_true", help="安静模式")
    parser.add_argument("-k", "--keyword", type=str, help="仅运行匹配关键词的测试")
    parser.add_argument("-x", "--exitfirst", action="store_true", help="首次失败后停止")
    args = parser.parse_args()

    # 列出测试文件
    if args.list:
        print_header("测试文件列表")
        for suite, files in TEST_SUITES.items():
            print(f"\n[{suite}]")
            for f in files:
                exists = (PROJECT_ROOT / f).exists()
                status = "[OK]" if exists else "[--]"
                print(f"  {status} {f}")
        return 0

    test_files = _select_test_files(args)

    # 仅保留存在的文件
    existing_files = [f for f in test_files if (PROJECT_ROOT / f).exists()]
    missing_files = [f for f in test_files if f not in existing_files]

    if missing_files and not args.quiet:
        print(f"[WARNING] 以下测试文件不存在 (将跳过): {missing_files}")

    if not existing_files:
        print("[ERROR] 没有可运行的测试文件")
        return 1

    extra_args = _build_pytest_args(args)

    # 运行测试
    print_header("BTC 碰撞引擎 - 测试运行")
    print(f"  测试文件数量: {len(existing_files)}")
    if extra_args:
        print(f"  额外参数: {' '.join(extra_args)}")
    print()

    start_time = time.time()
    result = run_pytest(existing_files, extra_args, verbose=not args.quiet)
    elapsed = time.time() - start_time

    if result.returncode == 0:
        print(f"\n[OK] 全部测试通过!  ({elapsed:.1f}s)")
    else:
        print(f"\n[FAIL] 部分测试失败  ({elapsed:.1f}s)")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
