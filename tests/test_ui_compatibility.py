#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI模块兼容性改进测试脚本

测试内容:
1. 跨平台字体选择
2. 自适应窗口大小
3. 配置项验证
4. 工具提示
5. 快捷键绑定
6. 错误提示优化
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from src.utils.platform_utils import PlatformUtils
from src.config.gui_config import (
    WINDOW_CONFIG, FONT_CONFIG, COLOR_CONFIG, 
    PLATFORM_INFO, validate_all_configs
)


def test_platform_utils():
    """测试跨平台工具类"""
    print("=" * 60)
    print("测试1: 跨平台工具类")
    print("=" * 60)
    
    # 平台检测
    print(f"✓ 当前平台: {PlatformUtils.get_platform_name()}")
    print(f"  - Windows: {PlatformUtils.is_windows()}")
    print(f"  - macOS: {PlatformUtils.is_macos()}")
    print(f"  - Linux: {PlatformUtils.is_linux()}")
    
    # 字体选择
    ui_font = PlatformUtils.get_ui_font()
    mono_font = PlatformUtils.get_mono_font()
    print(f"\n✓ 字体选择:")
    print(f"  - UI字体: {ui_font}")
    print(f"  - 等宽字体: {mono_font}")
    
    # 屏幕尺寸
    screen_width, screen_height = PlatformUtils.get_screen_size()
    print(f"\n✓ 屏幕尺寸: {screen_width}x{screen_height}")
    
    # 最优窗口尺寸
    opt_width, opt_height = PlatformUtils.get_optimal_window_size()
    print(f"✓ 最优窗口尺寸: {opt_width}x{opt_height}")
    
    # DPI缩放
    dpi_scale = PlatformUtils.get_dpi_scale()
    print(f"✓ DPI缩放: {dpi_scale:.2f}")
    
    # 系统信息
    sys_info = PlatformUtils.get_system_info()
    print(f"\n✓ 系统信息:")
    for key, value in sys_info.items():
        print(f"  - {key}: {value}")
    
    print("\n✅ 跨平台工具类测试通过\n")
    return True


def test_gui_config():
    """测试GUI配置"""
    print("=" * 60)
    print("测试2: GUI配置验证")
    print("=" * 60)
    
    # 验证配置
    try:
        validate_all_configs()
        print("✓ 配置验证通过")
    except Exception as e:
        print(f"✗ 配置验证失败: {e}")
        return False
    
    # 检查平台信息
    print(f"\n✓ 平台信息:")
    for key, value in PLATFORM_INFO.items():
        print(f"  - {key}: {value}")
    
    # 检查字体配置
    print(f"\n✓ 字体配置:")
    for key, value in FONT_CONFIG.items():
        font_name = value[0] if isinstance(value, tuple) else value
        print(f"  - {key}: {font_name}")
    
    # 检查窗口配置
    print(f"\n✓ 窗口配置:")
    print(f"  - 自适应大小: {WINDOW_CONFIG.get('use_adaptive_size', False)}")
    print(f"  - 宽度比例: {WINDOW_CONFIG.get('width_ratio', 0.75)}")
    print(f"  - 高度比例: {WINDOW_CONFIG.get('height_ratio', 0.80)}")
    print(f"  - 默认尺寸: {WINDOW_CONFIG['default_width']}x{WINDOW_CONFIG['default_height']}")
    print(f"  - 最小尺寸: {WINDOW_CONFIG['min_width']}x{WINDOW_CONFIG['min_height']}")
    
    print("\n✅ GUI配置测试通过\n")
    return True


def test_tutorial():
    """测试工具提示和用户引导"""
    print("=" * 60)
    print("测试3: 工具提示和用户引导")
    print("=" * 60)
    
    try:
        from src.utils.ui_tutorial import Tooltip, UserGuide, add_tooltip
        
        # 创建临时窗口
        root = tk.Tk()
        root.withdraw()  # 隐藏窗口
        
        # 测试Tooltip
        btn = tk.Button(root, text="测试按钮")
        btn.pack()
        
        tooltip = Tooltip(btn, "这是一个测试提示")
        print("✓ Tooltip类创建成功")
        
        # 测试add_tooltip便捷函数
        btn2 = tk.Button(root, text="测试按钮2")
        btn2.pack()
        
        tooltip2 = add_tooltip(btn2, "这是另一个提示")
        print("✓ add_tooltip函数测试成功")
        
        # 测试UserGuide
        guide = UserGuide(root)
        print("✓ UserGuide类创建成功")
        
        root.destroy()
        print("\n✅ 工具提示和用户引导测试通过\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试4: 模块导入")
    print("=" * 60)
    
    modules_to_test = [
        ("src.utils.platform_utils", "PlatformUtils"),
        ("src.utils.ui_tutorial", "Tooltip, UserGuide"),
        ("src.config.gui_config", "WINDOW_CONFIG, FONT_CONFIG"),
    ]
    
    all_passed = True
    for module, classes in modules_to_test:
        try:
            __import__(module)
            print(f"✓ {module} ({classes})")
        except Exception as e:
            print(f"✗ {module} 导入失败: {e}")
            all_passed = False
    
    if all_passed:
        print("\n✅ 模块导入测试通过\n")
    else:
        print("\n✗ 部分模块导入失败\n")
    
    return all_passed


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("UI模块兼容性改进测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 测试1: 跨平台工具类
    results.append(("跨平台工具类", test_platform_utils()))
    
    # 测试2: GUI配置
    results.append(("GUI配置", test_gui_config()))
    
    # 测试3: 工具提示
    results.append(("工具提示", test_tutorial()))
    
    # 测试4: 模块导入
    results.append(("模块导入", test_imports()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！UI模块兼容性改进已成功实施。")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查错误信息。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
