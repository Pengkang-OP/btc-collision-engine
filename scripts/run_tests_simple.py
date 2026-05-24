#!/usr/bin/env python3
"""简化的测试运行器 - 绕过Python 3.14 pytest兼容性问题"""

import os
import sys
import time
import traceback


def run_test_file(test_file):
    """运行单个测试文件"""
    print(f"\n{'=' * 80}")
    print(f"运行测试: {test_file}")
    print(f"{'=' * 80}")

    # 导入测试模块
    module_name = os.path.splitext(os.path.basename(test_file))[0]
    try:
        # 动态导入
        import importlib.util

        spec = importlib.util.spec_from_file_location(module_name, test_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 查找所有测试函数
        test_functions = [attr for attr in dir(module) if attr.startswith("test_")]

        passed = 0
        failed = 0
        errors = []

        for test_func_name in test_functions:
            test_func = getattr(module, test_func_name)
            if not callable(test_func):
                continue

            try:
                print(f"  运行 {test_func_name}...", end=" ")
                start_time = time.time()
                test_func()
                elapsed = time.time() - start_time
                print(f"✅ 通过 ({elapsed:.2f}s)")
                passed += 1
            except Exception as e:
                print("❌ 失败")
                errors.append((test_func_name, str(e), traceback.format_exc()))
                failed += 1

        print(f"\n  结果: {passed} 通过, {failed} 失败")
        return passed, failed, errors

    except Exception as e:
        print(f"  ❌ 导入失败: {e}")
        return 0, 1, [("import", str(e), traceback.format_exc())]


def main():
    """运行关键测试"""
    print("=" * 80)
    print("GPU修复后无回归验证测试")
    print("=" * 80)

    # 关键测试文件列表
    test_files = [
        "tests/test_gpu_collision_engine.py",
        "tests/test_gpu_integration_validation.py",
        "tests/test_gpu_device_helper.py",
        "tests/test_key_collision_engine.py",
        "tests/test_core_crypto.py",
        "tests/test_gpu_memory_pool.py",
        "tests/test_gpu_performance.py",
    ]

    total_passed = 0
    total_failed = 0
    all_errors = []

    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"\n⚠️  跳过不存在的文件: {test_file}")
            continue

        passed, failed, errors = run_test_file(test_file)
        total_passed += passed
        total_failed += failed
        all_errors.extend(errors)

    # 打印总结
    print(f"\n{'=' * 80}")
    print("测试总结")
    print(f"{'=' * 80}")
    print(f"总测试数: {total_passed + total_failed}")
    print(f"✅ 通过: {total_passed}")
    print(f"❌ 失败: {total_failed}")

    if total_passed + total_failed > 0:
        pass_rate = (total_passed / (total_passed + total_failed)) * 100
        print(f"通过率: {pass_rate:.1f}%")

    if all_errors:
        print(f"\n{'=' * 80}")
        print("失败详情:")
        print(f"{'=' * 80}")
        for test_name, error_msg, tb in all_errors[:5]:  # 只显示前5个
            print(f"\n测试: {test_name}")
            print(f"错误: {error_msg}")
            print(tb)

    print(f"\n{'=' * 80}")
    if total_failed == 0:
        print("🎉 所有测试通过! 无回归!")
    else:
        print(f"⚠️  有 {total_failed} 个测试失败")
    print(f"{'=' * 80}")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
