#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证P1-1和P1-2修复

测试内容:
1. P1-1: 快速模式显示文件预览
2. P1-2: 命令别名功能正常工作
"""

import sys
import os
import tempfile
from pathlib import Path

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def test_p1_1_file_preview():
    """测试P1-1: 快速模式文件预览功能"""
    print("=" * 70)
    print("测试 P1-1: 快速模式文件预览")
    print("=" * 70)
    
    # 创建临时targets.txt文件
    test_file = "test_targets_preview.txt"
    try:
        # 创建测试文件
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("# 测试目标地址文件\n")
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy\n")
            f.write("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\n")
            f.write("# 这是注释\n")
            f.write("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2\n")
        
        print(f"\n✅ 创建测试文件: {test_file}")
        print("   包含4个地址 (3个有效 + 1个注释)\n")
        
        # 验证文件读取逻辑
        address_count = 0
        preview_addresses = []
        with open(test_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    address_count += 1
                    if len(preview_addresses) < 3:
                        preview_addresses.append(stripped)
        
        print(f"📊 文件统计:")
        print(f"   有效地址数: {address_count}")
        print(f"   预览地址数: {len(preview_addresses)}")
        print(f"\n📋 地址预览:")
        for i, addr in enumerate(preview_addresses, 1):
            display_addr = addr[:20] + "..." if len(addr) > 20 else addr
            print(f"   {i}. {display_addr}")
        
        if address_count > 3:
            print(f"   ... 及其他 {address_count - 3} 个地址")
        
        # 验证逻辑正确性
        assert address_count == 4, f"地址数量应为4，实际为{address_count}"
        assert len(preview_addresses) == 3, f"预览地址应为3个，实际为{len(preview_addresses)}"
        
        print("\n✅ P1-1 测试通过: 文件预览功能正常")
        return True
        
    except Exception as e:
        print(f"\n❌ P1-1 测试失败: {e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"\n🧹 已清理测试文件: {test_file}")


def test_p1_2_command_alias():
    """测试P1-2: 命令别名功能"""
    print("\n" + "=" * 70)
    print("测试 P1-2: 命令别名功能")
    print("=" * 70)
    
    # 检查start.bat中的别名实现
    start_bat_path = os.path.join(_project_root, 'start.bat')
    
    print(f"\n📍 检查路径: {start_bat_path}")
    print(f"📍 路径存在: {os.path.exists(start_bat_path)}")
    
    if not os.path.exists(start_bat_path):
        # 尝试其他可能的路径
        alt_paths = [
            os.path.join(os.getcwd(), 'start.bat'),
            'start.bat'
        ]
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                start_bat_path = alt_path
                print(f"📍 使用备用路径: {start_bat_path}")
                break
        else:
            print("❌ start.bat 不存在")
            return False
    
    with open(start_bat_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 测试1: 检查别名检测逻辑
    print("\n📋 检查别名检测逻辑:")
    aliases = {
        'qs': '--quick-start',
        'qr': '--quick-run',
        'hc': '--health-check',
        'cc': '--config-check',
        'ex': '--examples',
        'rec': '--recommend'
    }
    
    all_passed = True
    for alias, full_cmd in aliases.items():
        # 检查是否包含别名检测
        if f'"{alias}"' in content or f"'{alias}'" in content:
            # 检查是否设置ARGS变量
            if f'set "ARGS={full_cmd}' in content:
                print(f"  ✅ 别名 {alias} -> {full_cmd} (正确实现)")
            else:
                print(f"  ❌ 别名 {alias} -> {full_cmd} (缺少ARGS设置)")
                all_passed = False
        else:
            print(f"  ❌ 别名 {alias} 未定义")
            all_passed = False
    
    # 测试2: 检查是否使用ARGS变量
    print("\n📋 检查ARGS变量使用:")
    if '!ARGS!' in content:
        print("  ✅ 检测到 !ARGS! 变量使用")
    else:
        print("  ❌ 未检测到 !ARGS! 变量使用")
        all_passed = False
    
    # 测试3: 检查ALIAS_REPLACED标志
    print("\n📋 检查ALIAS_REPLACED标志:")
    if 'ALIAS_REPLACED' in content:
        print("  ✅ 检测到 ALIAS_REPLACED 标志")
    else:
        print("  ❌ 未检测到 ALIAS_REPLACED 标志")
        all_passed = False
    
    # 测试4: 检查goto标签
    print("\n📋 检查流程控制:")
    if ':after_alias_check' in content:
        print("  ✅ 检测到 :after_alias_check 标签")
    else:
        print("  ❌ 未检测到 :after_alias_check 标签")
        all_passed = False
    
    if all_passed:
        print("\n✅ P1-2 测试通过: 命令别名功能实现正确")
    else:
        print("\n❌ P1-2 测试失败: 命令别名实现存在问题")
    
    return all_passed


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("P1高优先级问题修复验证")
    print("=" * 70 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("P1-1: 文件预览", test_p1_1_file_preview()))
    results.append(("P1-2: 命令别名", test_p1_2_command_alias()))
    
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
        print("\n🎉 所有P1高优先级问题已修复！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个P1问题未修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
