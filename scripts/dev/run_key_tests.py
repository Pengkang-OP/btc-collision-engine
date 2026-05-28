#!/usr/bin/env python3
"""运行关键测试验证无回归 - 使用pytest API."""

import os
import sys

import pytest

# 禁用pytest的capture插件以避免Python 3.14问题
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = ""


def main():
    """运行关键测试."""
    print("=" * 80)
    print("GPU修复后无回归验证测试")
    print("=" * 80)

    # 关键测试文件
    test_files = [
        "tests/test_gpu_collision_engine.py",
        "tests/test_gpu_integration_validation.py",
        "tests/test_key_collision_engine.py",
        "tests/test_core_crypto.py",
        "tests/test_gpu_memory_pool.py",
    ]

    # 过滤存在的文件
    existing_tests = [f for f in test_files if os.path.exists(f)]

    print(f"\n将运行 {len(existing_tests)} 个测试文件:")
    for f in existing_tests:
        print(f"  - {f}")

    print(f"\n{'=' * 80}\n")

    # 使用pytest API运行
    args = [
        *existing_tests,
        "-v",
        "--tb=short",
        "--color=no",
        "-p",
        "no:cacheprovider",
    ]

    try:
        exit_code = pytest.main(args)
        return exit_code
    except Exception as e:
        print(f"\nERR pytest运行失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
