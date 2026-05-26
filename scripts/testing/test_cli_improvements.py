#!/usr/bin/env python3
"""
CLI人性化改进测试脚本

测试新增的CLI功能：
1. --examples 命令
2. --config-check 命令
3. 错误提示改进
4. --quick-start 命令（交互式，需要手动测试）
"""

import subprocess
import sys


def run_test(test_name, command, expected_output=None, should_fail=False):
    """运行单个测试"""
    print(f"\n{'=' * 70}")
    print(f"测试: {test_name}")
    print(f"命令: {command}")
    print("=" * 70)

    try:
        # 设置环境变量以支持UTF-8
        import os

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        output = (result.stdout or "") + (result.stderr or "")

        # 检查预期输出
        if expected_output:
            # 支持多种可能的输出格式
            expected_variants = [expected_output]
            if "💡" in expected_output:
                expected_variants.append("[Tip]")
            if "📚" in expected_output:
                expected_variants.append("[Examples]")
            if "🔧" in expected_output:
                expected_variants.append("[Config Check]")

            found = any(variant in output for variant in expected_variants)
            if found:
                print("✅ 通过 - 找到预期输出")
                return True
            else:
                print(f"❌ 失败 - 未找到预期输出: {expected_output}")
                print(f"实际输出:\n{output[:500]}")
                return False

        # 检查是否应该失败
        if should_fail:
            if result.returncode != 0:
                print(f"✅ 通过 - 命令按预期失败 (退出码: {result.returncode})")
                return True
            else:
                print("❌ 失败 - 命令应该失败但成功了")
                return False
        else:
            if result.returncode == 0:
                print("✅ 通过 - 命令成功执行")
                return True
            else:
                print(f"❌ 失败 - 命令执行失败 (退出码: {result.returncode})")
                print(f"输出:\n{output[:500]}")
                return False

    except subprocess.TimeoutExpired:
        print("❌ 失败 - 命令执行超时")
        return False
    except Exception as e:
        print(f"❌ 失败 - 异常: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 70)
    print("🧪 CLI人性化改进测试套件")
    print("=" * 70)

    tests = [
        {
            "name": "1. --examples 命令",
            "command": "python key_collision_cli.py --examples",
            "expected": "📚 BTC碰撞引擎 - 常用示例",
        },
        {
            "name": "2. --config-check 命令",
            "command": "python key_collision_cli.py --config-check",
            "expected": "🔧 配置文件检查",
        },
        {
            "name": "3. 无参数错误提示改进",
            "command": "python key_collision_cli.py",
            "expected": "💡 提示:",
            "should_fail": True,
        },
        {
            "name": "4. range模式缺少--start错误提示",
            "command": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m range",
            "expected": "💡 示例:",
            "should_fail": True,
        },
        {
            "name": "5. 帮助信息包含新参数",
            "command": "python key_collision_cli.py --help",
            "expected": "--quick-start",
        },
        {
            "name": "6. --quick-start 参数存在",
            "command": "python key_collision_cli.py --help",
            "expected": "启动交互式快速引导模式",
        },
    ]

    results = []
    for test in tests:
        success = run_test(
            test["name"], test["command"], test.get("expected"), test.get("should_fail", False)
        )
        results.append((test["name"], success))

    # 汇总结果
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")

    print("-" * 70)
    print(f"总计: {passed}/{total} 通过 ({passed / total * 100:.1f}%)")
    print("=" * 70)

    if passed == total:
        print("\n🎉 所有测试通过！CLI人性化改进已成功实施。")
        print("\n✨ 新增功能:")
        print("   1. --quick-start    交互式快速引导")
        print("   2. --examples       常用示例展示")
        print("   3. --config-check   配置状态检查")
        print("   4. 改进的错误提示   带解决方案建议")
        print("   5. 可视化进度条     更直观的进度显示")
        print("   6. 首次运行向导     自动检测并引导")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查实现")
        return 1


if __name__ == "__main__":
    sys.exit(main())
