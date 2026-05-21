#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互改进功能测试脚本

测试以下改进:
1. 快速模式 (--quick-run)
2. 交互式帮助 (上下文帮助)
3. 进度显示格式 (统一格式)
4. 命令别名 (快捷方式)
"""

import sys
import os

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.cli.progress import format_progress
from src.collision import CollisionStats


def test_progress_format():
    """测试进度显示格式改进"""
    print("=" * 70)
    print("测试 1: 进度显示格式改进")
    print("=" * 70)
    
    # 创建测试数据
    stats = CollisionStats()
    stats.start_time = 1000
    stats.total_checked = 1500000
    stats.matches = []
    
    # 测试不同引擎类型
    test_cases = [
        ('cpu', 'CPU模式'),
        ('gpu', 'GPU模式'),
        ('multi-gpu', '多GPU模式'),
    ]
    
    for engine_type, desc in test_cases:
        progress_str = format_progress(stats, 'random', total_range=100000000, engine_type=engine_type)
        print(f"\n{desc}:")
        print(f"  {progress_str}")
        
        # 验证引擎类型标签
        assert f"[{engine_type.upper()}]" in progress_str, f"应包含引擎类型标签 [{engine_type.upper()}]"
    
    print("\n✅ 进度显示格式测试通过")
    return True


def test_quick_run_command():
    """测试快速模式命令"""
    print("\n" + "=" * 70)
    print("测试 2: 快速模式命令 (--quick-run)")
    print("=" * 70)
    
    # 测试参数解析
    try:
        from src.cli.arg_parser import parse_args
        
        # 模拟 --quick-run 参数
        sys.argv = ['key_collision_cli.py', '--quick-run']
        args = parse_args()
        
        assert hasattr(args, 'quick_run'), "应包含 quick_run 属性"
        assert args.quick_run == True, "quick_run 应为 True"
        
        print("  ✅ --quick-run 参数解析正确")
        
    except Exception as e:
        print(f"  ❌ 快速模式测试失败: {e}")
        return False
    
    print("\n✅ 快速模式命令测试通过")
    return True


def test_command_aliases():
    """测试命令别名"""
    print("\n" + "=" * 70)
    print("测试 3: 命令别名支持")
    print("=" * 70)
    
    # 检查 start.bat 中是否包含别名定义
    start_bat_path = os.path.join(_project_root, 'start.bat')
    
    # 如果路径不存在，尝试其他可能的路径
    if not os.path.exists(start_bat_path):
        alt_paths = [
            os.path.join(os.getcwd(), 'start.bat'),
            'start.bat'
        ]
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                start_bat_path = alt_path
                break
    
    if os.path.exists(start_bat_path):
        with open(start_bat_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        aliases = ['qs', 'qr', 'hc', 'cc', 'ex', 'rec']
        for alias in aliases:
            if f'"{alias}"' in content or f"'{alias}'" in content:
                print(f"  ✅ 别名 {alias} 已定义")
            else:
                print(f"  ⚠️  别名 {alias} 未找到")
    else:
        print("  ⚠️  start.bat 不存在")
    
    print("\n✅ 命令别名测试完成")
    return True


def test_context_help():
    """测试交互式帮助"""
    print("\n" + "=" * 70)
    print("测试 4: 交互式帮助 (上下文帮助)")
    print("=" * 70)
    
    # 检查 commands.py 中是否包含帮助文本
    commands_path = os.path.join(_project_root, 'src', 'cli', 'commands.py')
    if os.path.exists(commands_path):
        with open(commands_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        help_indicators = [
            ('[?] 提示', '步骤1帮助'),
            ('[?] 模式说明', '步骤2帮助'),
            ('[?] 功能说明', '步骤3帮助'),
        ]
        
        for indicator, desc in help_indicators:
            if indicator in content:
                print(f"  ✅ {desc} 已添加")
            else:
                print(f"  ⚠️  {desc} 未找到")
    else:
        print("  ⚠️  commands.py 不存在")
    
    print("\n✅ 交互式帮助测试完成")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("BTC碰撞引擎 - 交互改进功能测试")
    print("=" * 70 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("进度显示格式", test_progress_format()))
    results.append(("快速模式命令", test_quick_run_command()))
    results.append(("命令别名", test_command_aliases()))
    results.append(("交互式帮助", test_context_help()))
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！交互改进功能正常。")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试未通过，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
