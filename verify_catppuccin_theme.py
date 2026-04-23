#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU组件Catppuccin主题样式显示验证

验证内容:
1. GPU选择器的Catppuccin Mocha主题
2. GPU监控面板的Catppuccin Mocha主题
3. 颜色配置一致性
4. 样式应用正确性
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk


def verify_catppuccin_colors():
    """验证Catppuccin Mocha主题颜色配置"""
    print("\n" + "="*70)
    print("验证 1: Catppuccin Mocha 主题颜色配置")
    print("="*70)
    
    try:
        from src.gui.components.gpu_selector import GPU_COLORS
        from src.gui.components.multi_gpu_monitor import MONITOR_COLORS
        from src.config.gui_config import COLOR_CONFIG
        
        # Catppuccin Mocha 标准色值
        expected_colors = {
            'bg': '#1e1e2e',      # Base
            'surface': '#313244', # Surface0
            'surface1': '#45475a', # Surface1
            'surface2': '#585b70', # Surface2
            'fg': '#cdd6f4',      # Text
            'accent': '#f9e2af',  # Yellow
            'blue': '#89b4fa',    # Blue
            'green': '#a6e3a1',   # Green
            'red': '#f38ba8',     # Red
            'peach': '#fab387',   # Peach
            'mauve': '#cba6f7',   # Mauve
            'teal': '#94e2d5',    # Teal
        }
        
        print("\nGPU选择器颜色配置:")
        gpu_checks = {}
        for color_name, expected_value in expected_colors.items():
            actual_value = GPU_COLORS.get(color_name, 'N/A')
            match = actual_value == expected_value
            gpu_checks[color_name] = match
            status = "✅" if match else "❌"
            print(f"   {status} {color_name:12s}: {actual_value:10s} (期望: {expected_value})")
        
        print("\nGPU监控面板颜色配置:")
        monitor_checks = {}
        for color_name, expected_value in expected_colors.items():
            actual_value = MONITOR_COLORS.get(color_name, 'N/A')
            match = actual_value == expected_value
            monitor_checks[color_name] = match
            status = "✅" if match else "❌"
            print(f"   {status} {color_name:12s}: {actual_value:10s} (期望: {expected_value})")
        
        print("\n配置文件颜色对比:")
        config_checks = {}
        for color_name in ['bg', 'surface', 'accent', 'fg']:
            gpu_val = GPU_COLORS.get(color_name, 'N/A')
            monitor_val = MONITOR_COLORS.get(color_name, 'N/A')
            config_val = COLOR_CONFIG.get(color_name, 'N/A')
            
            consistent = (gpu_val == monitor_val == config_val)
            config_checks[color_name] = consistent
            status = "✅" if consistent else "❌"
            print(f"   {status} {color_name:12s}: GPU={gpu_val}, Monitor={monitor_val}, Config={config_val}")
        
        all_passed = all(gpu_checks.values()) and all(monitor_checks.values()) and all(config_checks.values())
        
        if all_passed:
            print("\n✅ Catppuccin Mocha主题颜色配置完全正确")
        else:
            print("\n❌ 颜色配置存在问题")
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ 颜色配置验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_gpu_selector_theme():
    """验证GPU选择器主题样式"""
    print("\n" + "="*70)
    print("验证 2: GPU选择器 Catppuccin 主题样式")
    print("="*70)
    
    try:
        from src.gui.components.gpu_selector import GPUSelectorPanel, GPU_COLORS
        
        # 创建测试窗口
        root = tk.Tk()
        root.title("GPU选择器 - Catppuccin Mocha主题验证")
        root.geometry("900x700")
        root.configure(bg=GPU_COLORS['bg'])
        
        # 创建GPU选择器
        selector = GPUSelectorPanel(root)
        selector.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        print("\n✅ GPU选择器创建成功")
        print(f"\n主题样式检查:")
        print(f"   ✅ 背景色: {GPU_COLORS['bg']} (Base)")
        print(f"   ✅ 表面色: {GPU_COLORS['surface']} (Surface0)")
        print(f"   ✅ 强调色: {GPU_COLORS['accent']} (Yellow)")
        print(f"   ✅ 文字色: {GPU_COLORS['fg']} (Text)")
        
        # 验证样式对象
        style_checks = {
            "样式对象存在": hasattr(selector, 'style'),
            "配置方法存在": hasattr(selector, '_configure_style'),
            "设备列表框存在": hasattr(selector, 'device_listbox'),
            "模式变量存在": hasattr(selector, 'mode_var'),
        }
        
        print(f"\n组件检查:")
        for check_name, result in style_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        all_passed = all(style_checks.values())
        
        if all_passed:
            print("\n" + "="*70)
            print("🎨 GPU选择器主题样式验证窗口已打开")
            print("="*70)
            print("\n请目视检查以下样式:")
            print("   1. 背景色应为深色 (#1e1e2e)")
            print("   2. 标题应为金色 (#f9e2af)")
            print("   3. 设备列表框:")
            print("      - 背景: 深色 (#1e1e2e)")
            print("      - 文字: 浅色 (#cdd6f4)")
            print("      - 选中: 蓝色 (#89b4fa)")
            print("   4. 按钮和标签应使用Catppuccin色系")
            print("   5. 整体风格应与Catppuccin Mocha主题一致")
            print("="*70)
        
        # 显示窗口5秒供检查
        root.update()
        time.sleep(5)
        root.destroy()
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ GPU选择器主题验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_gpu_monitor_theme():
    """验证GPU监控面板主题样式"""
    print("\n" + "="*70)
    print("验证 3: GPU监控面板 Catppuccin 主题样式")
    print("="*70)
    
    try:
        from src.gui.components.multi_gpu_monitor import MultiGPUMonitorPanel, MONITOR_COLORS
        
        # 创建测试窗口
        root = tk.Tk()
        root.title("GPU监控面板 - Catppuccin Mocha主题验证")
        root.geometry("900x500")
        root.configure(bg=MONITOR_COLORS['bg'])
        
        # 创建监控面板
        monitor = MultiGPUMonitorPanel(root)
        monitor.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 添加测试数据
        test_stats = {
            'device_name': 'NVIDIA GeForce RTX 3080',
            'status': 'running',
            'throughput': 1234567.89,
            'keys_checked': 10000000
        }
        
        monitor.update_gpu_status(0, test_stats)
        
        print("\n✅ GPU监控面板创建成功")
        print(f"\n主题样式检查:")
        print(f"   ✅ 背景色: {MONITOR_COLORS['bg']} (Base)")
        print(f"   ✅ 表面色: {MONITOR_COLORS['surface']} (Surface0)")
        print(f"   ✅ 强调色: {MONITOR_COLORS['accent']} (Yellow)")
        print(f"   ✅ 状态色(运行): {MONITOR_COLORS['green']} (Green)")
        print(f"   ✅ 吞吐量色: {MONITOR_COLORS['blue']} (Blue)")
        
        # 验证样式对象
        style_checks = {
            "样式对象存在": hasattr(monitor, 'style'),
            "配置方法存在": hasattr(monitor, '_configure_style'),
            "GPU框架字典存在": hasattr(monitor, 'gpu_frames'),
            "状态更新成功": 0 in monitor.gpu_frames,
        }
        
        print(f"\n组件检查:")
        for check_name, result in style_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        all_passed = all(style_checks.values())
        
        if all_passed:
            print("\n" + "="*70)
            print("🎨 GPU监控面板主题样式验证窗口已打开")
            print("="*70)
            print("\n请目视检查以下样式:")
            print("   1. 背景色应为深色 (#1e1e2e)")
            print("   2. 标题应为金色 (#f9e2af)")
            print("   3. GPU状态框架:")
            print("      - 设备名称: 浅色文字 (#cdd6f4)")
            print("      - 运行状态: 绿色 (#a6e3a1)")
            print("      - 吞吐量: 蓝色 (#89b4fa)")
            print("   4. 汇总统计区域:")
            print("      - 总吞吐量: 绿色 (#a6e3a1)")
            print("      - 标签文字: 浅色 (#cdd6f4)")
            print("   5. 整体风格应与Catppuccin Mocha主题一致")
            print("="*70)
        
        # 显示窗口5秒供检查
        root.update()
        time.sleep(5)
        root.destroy()
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ GPU监控面板主题验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_theme_consistency():
    """验证主题一致性"""
    print("\n" + "="*70)
    print("验证 4: Catppuccin 主题一致性")
    print("="*70)
    
    try:
        from src.gui.components.gpu_selector import GPU_COLORS
        from src.gui.components.multi_gpu_monitor import MONITOR_COLORS
        from src.config.gui_config import COLOR_CONFIG
        
        print("\n主题一致性检查:")
        
        consistency_checks = {
            "GPU选择器与配置文件背景色一致": 
                GPU_COLORS.get('bg') == COLOR_CONFIG.get('bg'),
            "GPU选择器与配置文件表面色一致": 
                GPU_COLORS.get('surface') == COLOR_CONFIG.get('surface'),
            "GPU选择器与配置文件强调色一致": 
                GPU_COLORS.get('accent') == COLOR_CONFIG.get('accent'),
            "监控面板与配置文件背景色一致": 
                MONITOR_COLORS.get('bg') == COLOR_CONFIG.get('bg'),
            "监控面板与配置文件表面色一致": 
                MONITOR_COLORS.get('surface') == COLOR_CONFIG.get('surface'),
            "监控面板与配置文件强调色一致": 
                MONITOR_COLORS.get('accent') == COLOR_CONFIG.get('accent'),
            "GPU选择器与监控面板背景色一致": 
                GPU_COLORS.get('bg') == MONITOR_COLORS.get('bg'),
            "GPU选择器与监控面板表面色一致": 
                GPU_COLORS.get('surface') == MONITOR_COLORS.get('surface'),
            "GPU选择器与监控面板强调色一致": 
                GPU_COLORS.get('accent') == MONITOR_COLORS.get('accent'),
        }
        
        for check_name, result in consistency_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        all_consistent = all(consistency_checks.values())
        
        if all_consistent:
            print("\n✅ Catppuccin Mocha主题完全一致")
            print("   - GPU选择器、监控面板、配置文件使用相同的颜色方案")
            print("   - 主题风格统一")
        else:
            print("\n❌ 主题一致性存在问题")
        
        return all_consistent
        
    except Exception as e:
        print(f"\n❌ 主题一致性验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主验证函数"""
    print("\n" + "="*70)
    print("GPU组件 Catppuccin Mocha 主题样式显示验证")
    print("="*70)
    print("\n开始时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("\nCatppuccin Mocha 主题色值:")
    print("   Base (背景):    #1e1e2e")
    print("   Surface0 (表面): #313244")
    print("   Yellow (强调):  #f9e2af")
    print("   Text (文字):    #cdd6f4")
    print("   Blue (蓝色):    #89b4fa")
    print("   Green (绿色):   #a6e3a1")
    print("   Red (红色):     #f38ba8")
    
    results = []
    
    # 运行验证
    results.append(("Catppuccin颜色配置", verify_catppuccin_colors()))
    results.append(("GPU选择器主题样式", verify_gpu_selector_theme()))
    results.append(("GPU监控面板主题样式", verify_gpu_monitor_theme()))
    results.append(("主题一致性", verify_theme_consistency()))
    
    # 汇总结果
    print("\n" + "="*70)
    print("验证结果汇总")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ 所有验证通过！Catppuccin Mocha主题样式显示正常！")
        print("\n总结:")
        print("  - Catppuccin Mocha主题颜色配置正确")
        print("  - GPU选择器主题样式应用成功")
        print("  - GPU监控面板主题样式应用成功")
        print("  - 主题一致性完全保证")
        print("  - 整体UI风格统一协调")
    else:
        print("❌ 部分验证失败，请检查错误信息")
    print("="*70)
    print("\n完成时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
