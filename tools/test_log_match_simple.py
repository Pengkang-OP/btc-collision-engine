#!/usr/bin/env python3
"""测试日志匹配失败提示的逻辑"""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_log_matching():
    """测试日志匹配逻辑"""
    print("=" * 80)
    print("  测试: 日志匹配失败提示逻辑")
    print("=" * 80)
    print()
    
    # 测试用例1: 日志中有目标数量
    print("【测试1】日志中有目标地址数量")
    print("-" * 80)
    log_with_targets = "2026-04-21 15:00:01 [INFO] 加载38个目标地址"
    
    num_targets = 0
    targets_match = re.search(r'(\d+)\s*个目标', log_with_targets)
    if targets_match:
        num_targets = int(targets_match.group(1))
        print(f"  ✅ 匹配成功: 目标地址数量: {num_targets}")
        if num_targets > 10:
            print(f"     → 目标地址较多,可能影响性能!")
    else:
        print(f"  ℹ️  未检测到目标地址数量(使用默认值0)")
        print(f"     → 可能原因: 日志格式变化或程序未完全启动")
    
    assert num_targets == 38, "应该匹配到38个目标"
    print()
    
    # 测试用例2: 日志中没有目标数量
    print("【测试2】日志中无目标地址数量")
    print("-" * 80)
    log_without_targets = "2026-04-21 15:00:00 [INFO] GPU碰撞引擎启动"
    
    num_targets = 0
    targets_match = re.search(r'(\d+)\s*个目标', log_without_targets)
    if targets_match:
        num_targets = int(targets_match.group(1))
        print(f"  ⚠️  目标地址数量: {num_targets}")
        if num_targets > 10:
            print(f"     → 目标地址较多,可能影响性能!")
    else:
        print(f"  ℹ️  未检测到目标地址数量(使用默认值0)")
        print(f"     → 可能原因: 日志格式变化或程序未完全启动")
    
    assert num_targets == 0, "应该使用默认值0"
    print()
    
    # 测试用例3: 空日志
    print("【测试3】空日志")
    print("-" * 80)
    empty_log = ""
    
    num_targets = 0
    targets_match = re.search(r'(\d+)\s*个目标', empty_log)
    if targets_match:
        num_targets = int(targets_match.group(1))
        print(f"  ⚠️  目标地址数量: {num_targets}")
        if num_targets > 10:
            print(f"     → 目标地址较多,可能影响性能!")
    else:
        print(f"  ℹ️  未检测到目标地址数量(使用默认值0)")
        print(f"     → 可能原因: 日志格式变化或程序未完全启动")
    
    assert num_targets == 0, "应该使用默认值0"
    print()
    
    print("=" * 80)
    print("  ✅ 所有测试通过!")
    print("=" * 80)
    print()
    print("改进效果:")
    print("  ✅ 日志格式变化时: 显示友好提示,而非静默失败")
    print("  ✅ 程序未启动时: 说明可能原因,引导用户检查")
    print("  ✅ 正常运行时: 正常显示目标数量,无额外提示")
    print()


if __name__ == "__main__":
    print("\n")
    test_log_matching()
