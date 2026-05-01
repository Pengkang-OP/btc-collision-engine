#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行完整测试套件验证无回归"""

import subprocess
import sys


def run_tests():
    """运行pytest并返回结果"""
    print("=" * 80)
    print("运行完整测试套件验证无回归")
    print("=" * 80)
    print()

    # 运行pytest（禁用capture插件以避免Python 3.14兼容性问题）
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--no-header",
            "-p",
            "no:capture",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # 输出结果
    print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    # 提取关键统计信息
    lines = result.stdout.split("\n")
    for line in lines:
        if "passed" in line or "failed" in line or "error" in line:
            print("\n" + "=" * 80)
            print(f"测试结果: {line}")
            print("=" * 80)

    return result.returncode


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
