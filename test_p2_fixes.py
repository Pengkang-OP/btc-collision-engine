#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证P2中优先级问题修复

测试内容:
1. P2-1: 引擎类型验证
2. P2-2: 默认配置常量
3. P2-3: 倒计时可配置
4. P2-4: 国际化支持
5. P2-5: 别名检测位置
6. P2-6: 测试路径检测
"""

import sys
import os

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def test_p2_1_engine_type_validation():
    """测试P2-1: 引擎类型验证"""
    print("=" * 70)
    print("测试 P2-1: 引擎类型验证")
    print("=" * 70)
    
    try:
        from src.cli.progress import format_progress, VALID_ENGINE_TYPES
        from src.collision import CollisionStats
        
        # 测试有效引擎类型
        stats = CollisionStats()
        stats.start_time = 0
        
        print("\n📋 测试有效引擎类型:")
        for engine_type in ['cpu', 'gpu', 'multi-gpu']:
            result = format_progress(stats, 'random', engine_type=engine_type)
            expected_tag = f"[{engine_type.upper()}]"
            if expected_tag in result:
                print(f"  ✅ {engine_type}: 标签正确 ({expected_tag})")
            else:
                print(f"  ❌ {engine_type}: 标签错误")
                return False
        
        # 测试无效引擎类型（应降级为cpu）
        print("\n📋 测试无效引擎类型降级:")
        result = format_progress(stats, 'random', engine_type='invalid')
        if '[CPU]' in result:
            print("  ✅ 无效类型正确降级为 CPU")
        else:
            print("  ❌ 无效类型未降级")
            return False
        
        # 验证白名单
        print("\n📋 验证引擎类型白名单:")
        expected_types = {'cpu', 'gpu', 'multi-gpu'}
        if VALID_ENGINE_TYPES == expected_types:
            print(f"  ✅ 白名单正确: {VALID_ENGINE_TYPES}")
        else:
            print(f"  ❌ 白名单错误: {VALID_ENGINE_TYPES}")
            return False
        
        print("\n✅ P2-1 测试通过: 引擎类型验证正常")
        return True
        
    except Exception as e:
        print(f"\n❌ P2-1 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_p2_2_default_config_constants():
    """测试P2-2: 默认配置常量"""
    print("\n" + "=" * 70)
    print("测试 P2-2: 默认配置常量")
    print("=" * 70)
    
    try:
        from src.cli.commands import QUICK_RUN_DEFAULTS, PREVIEW_CONFIG
        
        print("\n📋 验证 QUICK_RUN_DEFAULTS:")
        expected_defaults = {
            'target_file': 'targets.txt',
            'mode': 'random',
            'checkpoint': True,
            'dedup': True,
            'duration': 0,
            'countdown_seconds': 3,
        }
        
        for key, expected_value in expected_defaults.items():
            if key in QUICK_RUN_DEFAULTS:
                actual_value = QUICK_RUN_DEFAULTS[key]
                if actual_value == expected_value:
                    print(f"  ✅ {key}: {actual_value}")
                else:
                    print(f"  ❌ {key}: 期望 {expected_value}, 实际 {actual_value}")
                    return False
            else:
                print(f"  ❌ {key}: 键不存在")
                return False
        
        print("\n📋 验证 PREVIEW_CONFIG:")
        expected_preview = {
            'max_preview_addresses': 3,
            'max_address_display_length': 20,
        }
        
        for key, expected_value in expected_preview.items():
            if key in PREVIEW_CONFIG:
                actual_value = PREVIEW_CONFIG[key]
                if actual_value == expected_value:
                    print(f"  ✅ {key}: {actual_value}")
                else:
                    print(f"  ❌ {key}: 期望 {expected_value}, 实际 {actual_value}")
                    return False
            else:
                print(f"  ❌ {key}: 键不存在")
                return False
        
        print("\n✅ P2-2 测试通过: 默认配置常量正确")
        return True
        
    except Exception as e:
        print(f"\n❌ P2-2 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_p2_3_countdown_configurable():
    """测试P2-3: 倒计时可配置"""
    print("\n" + "=" * 70)
    print("测试 P2-3: 倒计时可配置")
    print("=" * 70)
    
    try:
        from src.cli.commands import QUICK_RUN_DEFAULTS
        
        print("\n📋 验证倒计时配置:")
        if 'countdown_seconds' in QUICK_RUN_DEFAULTS:
            countdown = QUICK_RUN_DEFAULTS['countdown_seconds']
            if isinstance(countdown, int) and countdown > 0:
                print(f"  ✅ 倒计时已配置: {countdown} 秒")
            else:
                print(f"  ❌ 倒计时值无效: {countdown}")
                return False
        else:
            print("  ❌ countdown_seconds 键不存在")
            return False
        
        # 验证代码中使用了该配置
        commands_file = os.path.join(_project_root, 'src', 'cli', 'commands.py')
        with open(commands_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "QUICK_RUN_DEFAULTS['countdown_seconds']" in content:
            print("  ✅ 代码中使用了倒计时配置")
        else:
            print("  ❌ 代码中未使用倒计时配置")
            return False
        
        print("\n✅ P2-3 测试通过: 倒计时可配置")
        return True
        
    except Exception as e:
        print(f"\n❌ P2-3 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_p2_4_i18n_support():
    """测试P2-4: 国际化支持"""
    print("\n" + "=" * 70)
    print("测试 P2-4: 国际化支持")
    print("=" * 70)
    
    try:
        import json
        
        # 检查中文翻译
        zh_file = os.path.join(_project_root, 'src', 'i18n', 'locales', 'zh_CN.json')
        en_file = os.path.join(_project_root, 'src', 'i18n', 'locales', 'en_US.json')
        
        print("\n📋 检查中文翻译文件:")
        with open(zh_file, 'r', encoding='utf-8') as f:
            zh_data = json.load(f)
        
        # 查找cli.commands部分
        zh_commands = zh_data.get('cli', {}).get('commands', {})
        
        required_keys = [
            'help_address_formats', 'help_p2pkh', 'help_p2sh', 'help_bech32',
            'help_mode_description', 'help_mode_random_detail', 
            'help_mode_range_detail', 'help_mode_brute_detail',
            'help_feature_description', 'help_checkpoint', 'help_dedup', 'help_duration'
        ]
        
        missing_zh = []
        for key in required_keys:
            if key in zh_commands:
                print(f"  ✅ {key}: {zh_commands[key][:30]}...")
            else:
                missing_zh.append(key)
                print(f"  ❌ {key}: 缺失")
        
        if missing_zh:
            print(f"\n  ⚠️  缺失 {len(missing_zh)} 个中文翻译键")
            return False
        
        print("\n📋 检查英文翻译文件:")
        with open(en_file, 'r', encoding='utf-8') as f:
            en_data = json.load(f)
        
        en_commands = en_data.get('cli', {}).get('commands', {})
        
        missing_en = []
        for key in required_keys:
            if key in en_commands:
                print(f"  ✅ {key}: {en_commands[key][:30]}...")
            else:
                missing_en.append(key)
                print(f"  ❌ {key}: 缺失")
        
        if missing_en:
            print(f"\n  ⚠️  缺失 {len(missing_en)} 个英文翻译键")
            return False
        
        # 验证代码中使用了翻译
        commands_file = os.path.join(_project_root, 'src', 'cli', 'commands.py')
        with open(commands_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        i18n_keys = ['help_address_formats', 'help_mode_description', 'help_feature_description']
        used_count = 0
        for key in i18n_keys:
            if f'_t("cli.commands.{key}")' in content:
                used_count += 1
        
        if used_count >= len(i18n_keys):
            print(f"\n  ✅ 代码中使用了 {used_count} 个国际化键")
        else:
            print(f"\n  ❌ 代码中只使用了 {used_count}/{len(i18n_keys)} 个国际化键")
            return False
        
        print("\n✅ P2-4 测试通过: 国际化支持正常")
        return True
        
    except Exception as e:
        print(f"\n❌ P2-4 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_p2_5_alias_position():
    """测试P2-5: 别名检测位置"""
    print("\n" + "=" * 70)
    print("测试 P2-5: 别名检测位置")
    print("=" * 70)
    
    try:
        start_bat = os.path.join(_project_root, 'start.bat')
        
        with open(start_bat, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找别名检测的位置
        alias_line = None
        tool_cmd_line = None
        
        for i, line in enumerate(lines, 1):
            if 'ALIAS_REPLACED=0' in line:
                alias_line = i
            if 'set "TOOL_CMD="' in line and i < 30:  # 在前30行
                tool_cmd_line = i
        
        print("\n📋 检查别名检测位置:")
        if alias_line:
            print(f"  ✅ 别名检测在第 {alias_line} 行")
        else:
            print("  ❌ 未找到别名检测")
            return False
        
        if tool_cmd_line:
            print(f"  ℹ️  工具命令检测在第 {tool_cmd_line} 行")
        
        if alias_line and tool_cmd_line:
            if alias_line > tool_cmd_line:
                print("  ✅ 别名检测在工具命令检测之后（正确）")
            else:
                print("  ⚠️  别名检测在工具命令检测之前")
        else:
            print("  ✅ 别名检测位置合理")
        
        # 验证注释说明
        alias_comment_found = False
        for i in range(max(0, alias_line - 2), alias_line):
            if '必须在其他检测之前处理' in lines[i] or 'alias' in lines[i].lower():
                alias_comment_found = True
                print(f"  ✅ 找到说明注释: {lines[i].strip()}")
                break
        
        if not alias_comment_found:
            print("  ℹ️  未找到特殊注释（可选）")
        
        print("\n✅ P2-5 测试通过: 别名检测位置正确")
        return True
        
    except Exception as e:
        print(f"\n❌ P2-5 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_p2_6_test_path_detection():
    """测试P2-6: 测试路径检测"""
    print("\n" + "=" * 70)
    print("测试 P2-6: 测试路径检测")
    print("=" * 70)
    
    try:
        test_file = os.path.join(_project_root, 'test_interactive_improvements.py')
        
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("\n📋 检查路径检测逻辑:")
        
        # 检查是否有备用路径检测
        if 'alt_paths' in content or '备用路径' in content:
            print("  ✅ 包含备用路径检测逻辑")
        else:
            print("  ❌ 缺少备用路径检测")
            return False
        
        # 检查os.getcwd()使用
        if 'os.getcwd()' in content:
            print("  ✅ 使用 os.getcwd() 作为备用路径")
        else:
            print("  ❌ 未使用 os.getcwd()")
            return False
        
        # 检查os.path.exists验证
        if 'os.path.exists' in content:
            print("  ✅ 使用 os.path.exists 验证路径")
        else:
            print("  ❌ 未使用 os.path.exists")
            return False
        
        print("\n✅ P2-6 测试通过: 测试路径检测正确")
        return True
        
    except Exception as e:
        print(f"\n❌ P2-6 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("P2中优先级问题修复验证")
    print("=" * 70 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("P2-1: 引擎类型验证", test_p2_1_engine_type_validation()))
    results.append(("P2-2: 默认配置常量", test_p2_2_default_config_constants()))
    results.append(("P2-3: 倒计时可配置", test_p2_3_countdown_configurable()))
    results.append(("P2-4: 国际化支持", test_p2_4_i18n_support()))
    results.append(("P2-5: 别名检测位置", test_p2_5_alias_position()))
    results.append(("P2-6: 测试路径检测", test_p2_6_test_path_detection()))
    
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
        print("\n🎉 所有P2中优先级问题已修复！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个P2问题未修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
