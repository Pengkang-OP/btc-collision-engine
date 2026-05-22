#!/usr/bin/env python3
"""完整测试套件验证脚本"""

import subprocess
import sys
import time


def run_test_module(module_name):
    """运行单个测试模块"""
    print(f"\n{'=' * 80}")
    print(f"运行测试: {module_name}")
    print("=" * 80)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            f"tests/{module_name}.py",
            "-q",
            "--tb=no",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    output = result.stdout + result.stderr

    # 提取结果
    if "passed" in output:
        # 提取通过数量
        for line in output.split("\n"):
            if "passed" in line:
                print(f"✅ {module_name}: {line.strip()}")
                return True, line.strip()
    elif "failed" in output:
        for line in output.split("\n"):
            if "failed" in line:
                print(f"❌ {module_name}: {line.strip()}")
                return False, line.strip()

    print(f"⚠️  {module_name}: 结果解析失败")
    return None, output[:200]


def main():
    """主函数"""
    print("=" * 80)
    print("BTC碰撞引擎 - 完整测试套件验证")
    print("=" * 80)
    print(f"Python版本: {sys.version}")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 关键测试模块
    test_modules = [
        "test_multiprocess_security",
        "test_gpu_memory_pool",
        "test_gpu_recovery",
        "test_alert_system",
        "test_address_import",
        "test_gpu_device_helper",
    ]

    results = []
    start_time = time.time()

    for module in test_modules:
        try:
            success, detail = run_test_module(module)
            results.append({"module": module, "success": success, "detail": detail})
        except subprocess.TimeoutExpired:
            print(f"⏱️  {module}: 超时")
            results.append({"module": module, "success": False, "detail": "超时"})
        except Exception as e:
            print(f"❌ {module}: 异常 - {e}")
            results.append({"module": module, "success": False, "detail": str(e)})

    # 汇总结果
    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)

    passed = sum(1 for r in results if r["success"] is True)
    failed = sum(1 for r in results if r["success"] is False)
    total = len(results)

    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r['module']}: {r['detail']}")

    print("\n" + "=" * 80)
    print(f"总计: {passed}/{total} 模块通过")
    print(f"耗时: {elapsed:.2f}秒")
    print("=" * 80)

    if passed == total:
        print("\n🎉 所有关键测试模块通过！")
        return 0
    else:
        print(f"\n⚠️  {failed}个模块测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
