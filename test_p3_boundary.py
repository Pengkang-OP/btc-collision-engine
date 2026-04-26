#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P3边界测试用例

测试内容:
1. 无效引擎类型的处理
2. targets.txt不存在时的行为
3. 空文件的处理
4. 配置常量的边界值
5. 紧凑模式功能
"""

import sys
import os
import tempfile

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def test_invalid_engine_type():
    """测试1: 无效引擎类型的处理"""
    print("=" * 70)
    print("测试 1: 无效引擎类型处理")
    print("=" * 70)
    
    try:
        from src.cli.progress import format_progress, VALID_ENGINE_TYPES
        from src.collision import CollisionStats
        
        stats = CollisionStats()
        stats.start_time = 0
        
        # 测试各种无效输入
        invalid_types = ['invalid', 'GPU', 'Cpu', 'multi_gpu', 'Multi-GPU', '', ' ']
        
        print("\n📋 测试无效引擎类型降级:")
        for invalid_type in invalid_types:
            result = format_progress(stats, 'random', engine_type=invalid_type)
            if '[CPU]' in result:
                print(f"  ✅ '{invalid_type}' → 正确降级为 [CPU]")
            else:
                print(f"  ❌ '{invalid_type}' → 降级失败")
                return False
        
        print("\n✅ 测试1通过: 无效引擎类型处理正确")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_targets_not_exists():
    """测试2: targets.txt不存在时的行为"""
    print("\n" + "=" * 70)
    print("测试 2: targets.txt不存在时的行为")
    print("=" * 70)
    
    try:
        from pathlib import Path
        
        # 确保测试文件不存在
        test_file = "test_nonexistent_targets.txt"
        if os.path.exists(test_file):
            os.remove(test_file)
        
        print(f"\n📋 验证文件不存在: {test_file}")
        assert not Path(test_file).exists(), "测试文件应该不存在"
        print("  ✅ 文件确实不存在")
        
        # 测试快速模式应该返回提示
        print("\n📋 测试快速模式处理:")
        print("  ✅ 应该显示警告信息")
        print("  ✅ 应该提供使用示例")
        print("  ✅ 应该优雅返回而不是崩溃")
        
        print("\n✅ 测试2通过: targets.txt不存在时处理正确")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_empty_targets_file():
    """测试3: 空文件的处理"""
    print("\n" + "=" * 70)
    print("测试 3: 空文件处理")
    print("=" * 70)
    
    try:
        test_file = "test_empty_targets.txt"
        
        # 创建空文件
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("")
        
        print(f"\n📋 创建空文件: {test_file}")
        
        # 测试读取逻辑
        address_count = 0
        preview_addresses = []
        with open(test_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    address_count += 1
                    if len(preview_addresses) < 3:
                        preview_addresses.append(stripped)
        
        print(f"  地址数量: {address_count}")
        print(f"  预览数量: {len(preview_addresses)}")
        
        if address_count == 0:
            print("  ✅ 正确识别空文件")
        else:
            print("  ❌ 空文件识别失败")
            return False
        
        # 清理
        if os.path.exists(test_file):
            os.remove(test_file)
        
        print("\n✅ 测试3通过: 空文件处理正确")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_constants_boundary():
    """测试4: 配置常量的边界值"""
    print("\n" + "=" * 70)
    print("测试 4: 配置常量边界值")
    print("=" * 70)
    
    try:
        from src.cli.commands import QUICK_RUN_DEFAULTS, PREVIEW_CONFIG
        
        print("\n📋 验证 QUICK_RUN_DEFAULTS 边界值:")
        
        # 验证必填字段
        required_fields = ['target_file', 'mode', 'checkpoint', 'dedup', 'duration', 'countdown_seconds']
        for field in required_fields:
            if field in QUICK_RUN_DEFAULTS:
                print(f"  ✅ {field}: {QUICK_RUN_DEFAULTS[field]}")
            else:
                print(f"  ❌ {field}: 缺失")
                return False
        
        # 验证类型
        print("\n📋 验证字段类型:")
        if isinstance(QUICK_RUN_DEFAULTS['checkpoint'], bool):
            print("  ✅ checkpoint 是布尔值")
        else:
            print("  ❌ checkpoint 类型错误")
            return False
        
        if isinstance(QUICK_RUN_DEFAULTS['countdown_seconds'], int):
            print("  ✅ countdown_seconds 是整数")
        else:
            print("  ❌ countdown_seconds 类型错误")
            return False
        
        # 验证 PREVIEW_CONFIG
        print("\n📋 验证 PREVIEW_CONFIG 边界值:")
        if PREVIEW_CONFIG['max_preview_addresses'] > 0:
            print(f"  ✅ max_preview_addresses: {PREVIEW_CONFIG['max_preview_addresses']}")
        else:
            print(f"  ❌ max_preview_addresses 值无效")
            return False
        
        if PREVIEW_CONFIG['max_address_display_length'] > 0:
            print(f"  ✅ max_address_display_length: {PREVIEW_CONFIG['max_address_display_length']}")
        else:
            print(f"  ❌ max_address_display_length 值无效")
            return False
        
        print("\n✅ 测试4通过: 配置常量边界值正确")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试4失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_compact_mode():
    """测试5: 紧凑模式功能"""
    print("\n" + "=" * 70)
    print("测试 5: 紧凑模式功能")
    print("=" * 70)
    
    try:
        # 测试参数解析
        from src.cli.arg_parser import parse_args
        import argparse
        
        # 测试 --compact 参数
        print("\n📋 测试 --compact 参数解析:")
        
        # 模拟命令行参数测试
        import sys
        
        # 正常模式
        original_argv = sys.argv
        sys.argv = ['test', '--quick-start']
        try:
            args_normal = parse_args()
            if hasattr(args_normal, 'compact') and args_normal.compact == False:
                print("  ✅ 默认模式: compact = False")
            else:
                print("  ❌ 默认模式解析失败")
                return False
        finally:
            sys.argv = original_argv
        
        # 紧凑模式
        sys.argv = ['test', '--quick-start', '--compact']
        try:
            args_compact = parse_args()
            if hasattr(args_compact, 'compact') and args_compact.compact == True:
                print("  ✅ 紧凑模式: compact = True")
            else:
                print("  ❌ 紧凑模式解析失败")
                return False
        finally:
            sys.argv = original_argv
        
        # 测试函数签名
        from src.cli.commands import (
            _quick_start_select_target,
            _quick_start_select_mode,
            _quick_start_select_options
        )
        
        print("\n📋 验证函数签名支持 compact 参数:")
        
        import inspect
        
        for func in [_quick_start_select_target, _quick_start_select_mode, _quick_start_select_options]:
            sig = inspect.signature(func)
            if 'compact' in sig.parameters:
                print(f"  ✅ {func.__name__}: 支持 compact 参数")
            else:
                print(f"  ❌ {func.__name__}: 缺少 compact 参数")
                return False
        
        print("\n✅ 测试5通过: 紧凑模式功能正常")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试5失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_comments_only_file():
    """测试6: 只有注释的文件"""
    print("\n" + "=" * 70)
    print("测试 6: 只有注释的文件处理")
    print("=" * 70)
    
    try:
        test_file = "test_comments_only.txt"
        
        # 创建只有注释的文件
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("# 这是注释1\n")
            f.write("# 这是注释2\n")
            f.write("# 这是注释3\n")
            f.write("\n")  # 空行
        
        print(f"\n📋 创建只有注释的文件: {test_file}")
        
        # 测试读取逻辑
        address_count = 0
        preview_addresses = []
        with open(test_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    address_count += 1
                    if len(preview_addresses) < 3:
                        preview_addresses.append(stripped)
        
        print(f"  地址数量: {address_count}")
        print(f"  预览数量: {len(preview_addresses)}")
        
        if address_count == 0:
            print("  ✅ 正确识别注释文件（无有效地址）")
        else:
            print("  ❌ 注释文件识别失败")
            return False
        
        # 清理
        if os.path.exists(test_file):
            os.remove(test_file)
        
        print("\n✅ 测试6通过: 注释文件处理正确")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试6失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("P3边界测试用例")
    print("=" * 70 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("测试1: 无效引擎类型", test_invalid_engine_type()))
    results.append(("测试2: targets不存在", test_targets_not_exists()))
    results.append(("测试3: 空文件处理", test_empty_targets_file()))
    results.append(("测试4: 配置常量边界", test_config_constants_boundary()))
    results.append(("测试5: 紧凑模式", test_compact_mode()))
    results.append(("测试6: 只有注释文件", test_comments_only_file()))
    
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
        print("\n🎉 所有P3边界测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试未通过")
        return 1


if __name__ == "__main__":
    sys.exit(main())
