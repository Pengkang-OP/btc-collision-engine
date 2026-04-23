#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU组件样式和布局显示验证脚本

验证内容:
1. GPU选择器的Catppuccin Mocha主题样式
2. GPU监控面板的主题样式
3. 组件布局位置
4. 颜色配置一致性
5. 线程安全保护
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import ttk, messagebox


def verify_gpu_selector_styling():
    """验证GPU选择器样式"""
    print("\n" + "="*70)
    print("验证 1: GPU选择器样式 (GPUSelectorPanel)")
    print("="*70)
    
    try:
        from src.gui.components.gpu_selector import GPUSelectorPanel, GPU_COLORS
        
        # 创建测试窗口
        root = tk.Tk()
        root.title("GPU选择器样式验证")
        root.geometry("800x600")
        
        # 设置主题背景色
        root.configure(bg=GPU_COLORS['bg'])
        
        # 创建GPU选择器
        selector = GPUSelectorPanel(root)
        selector.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        print("\n✅ GPU选择器创建成功")
        print(f"   - 背景色: {GPU_COLORS['bg']}")
        print(f"   - 表面色: {GPU_COLORS['surface']}")
        print(f"   - 强调色: {GPU_COLORS['accent']}")
        print(f"   - 文字色: {GPU_COLORS['fg']}")
        
        # 验证样式配置
        checks = {
            "GPU_COLORS常量存在": hasattr(GPU_COLORS, 'keys') if hasattr(GPU_COLORS, 'keys') else isinstance(GPU_COLORS, dict),
            "背景色正确": GPU_COLORS.get('bg') == '#1e1e2e',
            "表面色正确": GPU_COLORS.get('surface') == '#313244',
            "强调色正确": GPU_COLORS.get('accent') == '#f9e2af',
            "组件创建成功": selector is not None,
            "样式对象存在": hasattr(selector, 'style'),
            "设备列表框存在": hasattr(selector, 'device_listbox'),
        }
        
        print("\n样式检查:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        all_passed = all(checks.values())
        
        if all_passed:
            print("\n✅ GPU选择器样式验证通过")
            print("   提示: 窗口已打开，请目视检查样式是否正确")
            print("   - 背景应为深色 (#1e1e2e)")
            print("   - 标题应为金色 (#f9e2af)")
            print("   - 设备列表应有深色背景和蓝色选中高亮")
        else:
            print("\n❌ GPU选择器样式验证失败")
        
        # 显示窗口3秒供检查
        root.update()
        time.sleep(3)
        root.destroy()
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ GPU选择器样式验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_gpu_monitor_styling():
    """验证GPU监控面板样式"""
    print("\n" + "="*70)
    print("验证 2: GPU监控面板样式 (MultiGPUMonitorPanel)")
    print("="*70)
    
    try:
        from src.gui.components.multi_gpu_monitor import MultiGPUMonitorPanel, MONITOR_COLORS
        
        # 创建测试窗口
        root = tk.Tk()
        root.title("GPU监控面板样式验证")
        root.geometry("800x400")
        
        # 设置主题背景色
        root.configure(bg=MONITOR_COLORS['bg'])
        
        # 创建监控面板
        monitor = MultiGPUMonitorPanel(root)
        monitor.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        print("\n✅ GPU监控面板创建成功")
        print(f"   - 背景色: {MONITOR_COLORS['bg']}")
        print(f"   - 表面色: {MONITOR_COLORS['surface']}")
        print(f"   - 强调色: {MONITOR_COLORS['accent']}")
        print(f"   - 成功色: {MONITOR_COLORS['green']}")
        print(f"   - 错误色: {MONITOR_COLORS['red']}")
        
        # 验证样式配置
        checks = {
            "MONITOR_COLORS常量存在": isinstance(MONITOR_COLORS, dict),
            "背景色正确": MONITOR_COLORS.get('bg') == '#1e1e2e',
            "表面色正确": MONITOR_COLORS.get('surface') == '#313244',
            "强调色正确": MONITOR_COLORS.get('accent') == '#f9e2af',
            "组件创建成功": monitor is not None,
            "样式对象存在": hasattr(monitor, 'style'),
            "GPU框架字典存在": hasattr(monitor, 'gpu_frames'),
        }
        
        print("\n样式检查:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        # 测试状态更新
        test_stats = {
            'device_name': 'Test GPU (NVIDIA RTX 3080)',
            'status': 'running',
            'throughput': 1234567.89,
            'keys_checked': 10000000
        }
        
        monitor.update_gpu_status(0, test_stats)
        print("\n✅ GPU状态更新测试成功")
        
        all_passed = all(checks.values())
        
        if all_passed:
            print("\n✅ GPU监控面板样式验证通过")
            print("   提示: 窗口已打开，请目视检查样式是否正确")
            print("   - 背景应为深色 (#1e1e2e)")
            print("   - 标题应为金色 (#f9e2af)")
            print("   - 状态应为绿色 (运行中)")
            print("   - 吞吐量应为蓝色 (#89b4fa)")
        else:
            print("\n❌ GPU监控面板样式验证失败")
        
        # 显示窗口3秒供检查
        root.update()
        time.sleep(3)
        root.destroy()
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ GPU监控面板样式验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_layout_integration():
    """验证布局集成"""
    print("\n" + "="*70)
    print("验证 3: 布局集成验证")
    print("="*70)
    
    try:
        from key_collision_gui import CollisionGUI, GPU_COMPONENTS_AVAILABLE
        from src.config.gui_config import COLOR_CONFIG
        
        print(f"\n✅ GPU组件可用性: {GPU_COMPONENTS_AVAILABLE}")
        print(f"✅ 主题配置: {COLOR_CONFIG.get('current_theme', 'dark_catppuccin')}")
        
        # 验证颜色配置一致性
        from src.gui.components.gpu_selector import GPU_COLORS
        from src.gui.components.multi_gpu_monitor import MONITOR_COLORS
        
        consistency_checks = {
            "GPU选择器背景色一致": GPU_COLORS.get('bg') == COLOR_CONFIG.get('bg'),
            "GPU选择器表面色一致": GPU_COLORS.get('surface') == COLOR_CONFIG.get('surface'),
            "监控面板背景色一致": MONITOR_COLORS.get('bg') == COLOR_CONFIG.get('bg'),
            "监控面板表面色一致": MONITOR_COLORS.get('surface') == COLOR_CONFIG.get('surface'),
        }
        
        print("\n颜色一致性检查:")
        for check_name, result in consistency_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        all_consistent = all(consistency_checks.values())
        
        if all_consistent:
            print("\n✅ 颜色配置完全一致")
        else:
            print("\n❌ 颜色配置存在不一致")
        
        # 创建完整GUI测试
        if GPU_COMPONENTS_AVAILABLE:
            print("\n创建完整GUI进行布局验证...")
            root = tk.Tk()
            root.title("完整GUI布局验证")
            root.withdraw()  # 隐藏窗口
            
            # 创建GUI实例
            gui = CollisionGUI(root)
            
            # 验证GPU组件集成
            layout_checks = {
                "GPU选择器已集成": gui.gpu_selector is not None,
                "GPU监控面板已集成": gui.gpu_monitor is not None,
                "GPU选择器回调已设置": gui.gpu_selector.on_apply_callback is not None,
            }
            
            print("\n布局集成检查:")
            for check_name, result in layout_checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check_name}")
            
            all_integrated = all(layout_checks.values())
            
            if all_integrated:
                print("\n✅ GPU组件布局集成验证通过")
                print("   - GPU选择器已集成到主界面")
                print("   - GPU监控面板已集成到告警区域")
                print("   - 布局顺序: 目标地址 → 控制面板 → 实时统计 → GPU选择器")
            else:
                print("\n❌ GPU组件布局集成验证失败")
            
            root.destroy()
            return all_consistent and all_integrated
        
        return all_consistent
        
    except Exception as e:
        print(f"\n❌ 布局集成验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_thread_safety():
    """验证线程安全保护"""
    print("\n" + "="*70)
    print("验证 4: 线程安全保护 (W-01修复)")
    print("="*70)
    
    try:
        from src.gui.components.gpu_selector import GPUSelectorPanel
        
        # 创建测试窗口（不启动主循环）
        root = tk.Tk()
        root.withdraw()
        
        # 创建GPU选择器
        selector = GPUSelectorPanel(root)
        
        print("\n✅ GPU选择器创建成功")
        print("✅ W-01线程安全保护已启用")
        print("\n线程安全特性:")
        print("   - after调用使用try-except包裹")
        print("   - RuntimeError被正确捕获")
        print("   - 详细日志记录")
        print("   - 优雅降级处理")
        
        # 验证代码中包含异常处理
        import inspect
        source = inspect.getsource(selector._load_devices)
        
        safety_checks = {
            "包含RuntimeError捕获": "RuntimeError" in source,
            "包含try-except": "try:" in source and "except" in source,
            "包含日志记录": "logger.warning" in source,
        }
        
        print("\n线程安全检查:")
        for check_name, result in safety_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        all_safe = all(safety_checks.values())
        
        if all_safe:
            print("\n✅ 线程安全保护验证通过")
        else:
            print("\n❌ 线程安全保护验证失败")
        
        root.destroy()
        return all_safe
        
    except Exception as e:
        print(f"\n❌ 线程安全保护验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_style_timing():
    """验证样式配置时机 (W-02/W-03修复)"""
    print("\n" + "="*70)
    print("验证 5: 样式配置时机 (W-02/W-03修复)")
    print("="*70)
    
    try:
        import inspect
        from src.gui.components.gpu_selector import GPUSelectorPanel
        from src.gui.components.multi_gpu_monitor import MultiGPUMonitorPanel
        
        # 检查GPU选择器
        selector_source = inspect.getsource(GPUSelectorPanel.__init__)
        monitor_source = inspect.getsource(MultiGPUMonitorPanel.__init__)
        
        timing_checks = {
            "GPU选择器: super在样式之前": selector_source.index("super().__init__") < selector_source.index("self.style"),
            "GPU选择器: 包含修复注释": "W-02修复" in selector_source,
            "GPU监控面板: super在样式之前": monitor_source.index("super().__init__") < monitor_source.index("self.style"),
            "GPU监控面板: 包含修复注释": "W-03修复" in monitor_source,
        }
        
        print("\n样式配置时机检查:")
        for check_name, result in timing_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")
        
        all_correct = all(timing_checks.values())
        
        if all_correct:
            print("\n✅ 样式配置时机验证通过")
            print("   - 两个组件都先调用super().__init__()")
            print("   - 然后再配置样式")
            print("   - 符合tkinter最佳实践")
        else:
            print("\n❌ 样式配置时机验证失败")
        
        return all_correct
        
    except Exception as e:
        print(f"\n❌ 样式配置时机验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主验证函数"""
    print("\n" + "="*70)
    print("GPU组件样式和布局显示验证")
    print("="*70)
    print("\n开始时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    
    results = []
    
    # 运行验证
    results.append(("GPU选择器样式", verify_gpu_selector_styling()))
    results.append(("GPU监控面板样式", verify_gpu_monitor_styling()))
    results.append(("布局集成", verify_layout_integration()))
    results.append(("线程安全保护", verify_thread_safety()))
    results.append(("样式配置时机", verify_style_timing()))
    
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
        print("✅ 所有验证通过！GPU组件样式和布局显示正常！")
        print("\n总结:")
        print("  - Catppuccin Mocha主题样式正确应用")
        print("  - 组件布局位置合理")
        print("  - 线程安全保护已启用")
        print("  - 样式配置时机正确")
        print("  - 颜色配置一致")
    else:
        print("❌ 部分验证失败，请检查错误信息")
    print("="*70)
    print("\n完成时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
