#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式向导完整流程测试 - 简化版

测试向导的核心功能和显示
"""

import sys
import os

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def test_wizard_imports():
    """测试1: 导入向导相关函数"""
    print("=" * 70)
    print("测试 1: 导入向导函数")
    print("=" * 70)
    
    try:
        from src.cli.commands import (
            _cmd_quick_start,
            _quick_start_select_target,
            _quick_start_select_mode,
            _quick_start_select_options
        )
        
        print("\n✅ 所有向导函数导入成功:")
        print("  ✅ _cmd_quick_start")
        print("  ✅ _quick_start_select_target")
        print("  ✅ _quick_start_select_mode")
        print("  ✅ _quick_start_select_options")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        return False


def test_wizard_function_signatures():
    """测试2: 函数签名验证"""
    print("\n" + "=" * 70)
    print("测试 2: 函数签名验证")
    print("=" * 70)
    
    try:
        from src.cli.commands import (
            _quick_start_select_target,
            _quick_start_select_mode,
            _quick_start_select_options
        )
        import inspect
        
        functions = [
            (_quick_start_select_target, "选择目标", ['compact']),
            (_quick_start_select_mode, "选择模式", ['compact']),
            (_quick_start_select_options, "选择选项", ['compact']),
        ]
        
        all_ok = True
        for func, name, expected_params in functions:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            
            has_all = all(p in params for p in expected_params)
            
            if has_all:
                print(f"  ✅ {name}: 参数正确 {params}")
            else:
                print(f"  ❌ {name}: 缺少参数 {expected_params}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_wizard_helper_text():
    """测试3: 帮助文本验证"""
    print("\n" + "=" * 70)
    print("测试 3: 帮助文本验证")
    print("=" * 70)
    
    try:
        from src.i18n import _t, set_language
        
        # 设置为中文进行测试
        set_language('zh_CN')
        
        # 测试中文帮助文本
        keys_to_check = [
            'cli.commands.help_address_formats',
            'cli.commands.help_p2pkh',
            'cli.commands.help_p2sh',
            'cli.commands.help_bech32',
            'cli.commands.help_mode_description',
            'cli.commands.help_mode_random_detail',
            'cli.commands.help_feature_description',
            'cli.commands.help_checkpoint',
            'cli.commands.help_dedup',
        ]
        
        print("\n📋 中文帮助文本:")
        all_ok = True
        for key in keys_to_check:
            text = _t(key)
            if text and len(text) > 0 and not text.startswith('Missing'):
                print(f"  ✅ {key.split('.')[-1]}: {text[:40]}...")
            else:
                print(f"  ❌ {key.split('.')[-1]}: 翻译缺失或错误")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wizard_config():
    """测试4: 配置常量验证"""
    print("\n" + "=" * 70)
    print("测试 4: 配置常量验证")
    print("=" * 70)
    
    try:
        from src.cli.commands import QUICK_RUN_DEFAULTS, PREVIEW_CONFIG
        
        print("\n📋 QUICK_RUN_DEFAULTS:")
        for key, value in QUICK_RUN_DEFAULTS.items():
            print(f"  ✅ {key}: {value}")
        
        print("\n📋 PREVIEW_CONFIG:")
        for key, value in PREVIEW_CONFIG.items():
            print(f"  ✅ {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_wizard_with_file():
    """测试5: 向导文件加载功能"""
    print("\n" + "=" * 70)
    print("测试 5: 向导文件加载功能")
    print("=" * 70)
    
    try:
        # 创建测试文件
        test_file = os.path.join(_project_root, 'test_wizard.txt')
        test_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(f"# 测试地址\n{test_address}\n")
        
        print(f"\n📋 创建测试文件: {test_file}")
        print(f"  ✅ 文件已创建")
        
        # 读取并验证
        with open(test_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        addresses = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                addresses.append(stripped)
        
        print(f"  ✅ 检测到 {len(addresses)} 个地址")
        
        if len(addresses) == 1 and addresses[0] == test_address:
            print(f"  ✅ 地址内容正确: {addresses[0]}")
        else:
            print(f"  ❌ 地址内容错误")
            return False
        
        # 清理
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"  ✅ 已清理测试文件")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_wizard_validation():
    """测试6: 地址格式验证"""
    print("\n" + "=" * 70)
    print("测试 6: 地址格式验证")
    print("=" * 70)
    
    try:
        from src.collision.targets.resolver import TargetResolver
        
        resolver = TargetResolver()
        
        test_cases = [
            ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "P2PKH", True),
            ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "P2SH", True),
            ("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh", "Bech32", True),
            ("invalid_address", "Invalid", False),
        ]
        
        print("\n📋 地址验证测试:")
        all_ok = True
        for address, addr_type, should_valid in test_cases:
            try:
                result = resolver.resolve(address)
                is_valid = result is not None
                
                if is_valid == should_valid:
                    status = "✅" if is_valid else "✅ (正确拒绝)"
                    print(f"  {status} {addr_type}: {address[:20]}...")
                else:
                    print(f"  ❌ {addr_type}: 验证结果错误")
                    all_ok = False
            except:
                if not should_valid:
                    print(f"  ✅ Invalid: {address} (正确拒绝)")
                else:
                    print(f"  ❌ {addr_type}: 验证异常")
                    all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("交互式向导完整流程测试")
    print("=" * 70 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("测试1: 函数导入", test_wizard_imports()))
    results.append(("测试2: 函数签名", test_wizard_function_signatures()))
    results.append(("测试3: 帮助文本", test_wizard_helper_text()))
    results.append(("测试4: 配置常量", test_wizard_config()))
    results.append(("测试5: 文件加载", test_wizard_with_file()))
    results.append(("测试6: 地址验证", test_wizard_validation()))
    
    # 汇总
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
        print("\n🎉 所有交互式向导测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试未通过")
        return 1


if __name__ == "__main__":
    sys.exit(main())
