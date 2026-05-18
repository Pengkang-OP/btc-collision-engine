#!/usr/bin/env python3
"""CLI安全检查功能测试"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(project_root))


def test_security_check_integration():
    """测试安全检查集成到CLI"""
    print("=" * 70)
    print("CLI安全检查集成测试")
    print("=" * 70)

    # 测试1: 导入验证
    print("\n[测试1] 导入验证:")
    print("-" * 70)
    try:
        from src.cli.main import _run_main
        from src.core.crypto_backend import verify_production_ready
        print("  ✅ 导入成功")
    except ImportError as e:
        print(f"  ❌ 导入失败: {e}")
        return False

    # 测试2: 验证生产模式安全检查
    print("\n[测试2] 生产模式安全检查:")
    print("-" * 70)
    is_ready, message = verify_production_ready()
    print(f"  状态: {'✅ 通过' if is_ready else '❌ 未通过'}")
    print(f"  消息:\n{message}")

    # 测试3: 参数解析器检查
    print("\n[测试3] 参数解析器检查:")
    print("-" * 70)
    from src.cli.arg_parser import parse_args

    # 创建一个模拟的参数列表
    test_args = ["--production", "-t", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]

    # 临时替换 sys.argv
    original_argv = sys.argv
    try:
        sys.argv = ["test"] + test_args
        args = parse_args()
        print(f"  ✅ --production 参数: {args.production}")
        print(f"  ✅ --secure 参数: {args.secure}")
        print(f"  ✅ --skip-security-check 参数: {args.skip_security_check}")
    finally:
        sys.argv = original_argv

    # 测试4: 验证帮助信息
    print("\n[测试4] 帮助信息验证:")
    print("-" * 70)
    original_argv = sys.argv
    try:
        sys.argv = ["test", "--help"]
        try:
            parse_args()
        except SystemExit:
            pass  # --help 会触发 SystemExit，正常行为
        print("  ✅ 帮助信息可正常显示")
    finally:
        sys.argv = original_argv

    # 测试5: 验证安全选项在帮助中的显示
    print("\n[测试5] 安全选项帮助信息:")
    print("-" * 70)
    import io

    original_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        sys.argv = ["test", "--help"]
        try:
            parse_args()
        except SystemExit:
            pass
        help_text = sys.stdout.getvalue()
        if "--production" in help_text:
            print("  ✅ --production 选项已添加")
        if "--secure" in help_text:
            print("  ✅ --secure 选项已添加")
        if "--skip-security-check" in help_text:
            print("  ✅ --skip-security-check 选项已添加")
        if "安全选项" in help_text:
            print("  ✅ 安全选项分组已添加")
    finally:
        sys.stdout = original_stdout
        sys.argv = original_argv

    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)

    return is_ready


if __name__ == "__main__":
    try:
        success = test_security_check_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
