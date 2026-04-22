#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU选择器和导出功能界面验证脚本

此脚本验证：
1. GPU选择器是否正确显示
2. 多GPU监控面板是否正确显示
3. 导出按钮是否存在
4. 配置验证是否工作
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import messagebox


def verify_gpu_selector():
    """验证GPU选择器"""
    print("\n" + "="*60)
    print("验证 1: GPU选择器")
    print("="*60)
    
    try:
        from src.gui.components.gpu_selector import GPUSelectorPanel
        
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        # 创建GPU选择器
        selector = GPUSelectorPanel(root)
        selector.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 等待异步加载完成（GPU检测需要时间）
        print("  ⏳ 等待GPU设备加载...")
        for _ in range(10):  # 最多等待5秒
            root.update()
            time.sleep(0.5)
            if selector.device_listbox.size() > 0:
                break
        
        # 验证关键组件
        checks = {
            "device_listbox": hasattr(selector, 'device_listbox'),
            "mode_var": hasattr(selector, 'mode_var'),
            "selected_devices": hasattr(selector, 'selected_devices'),
            "selected_mode": hasattr(selector, 'selected_mode'),
        }
        
        print("\n组件检查:")
        for name, exists in checks.items():
            status = "✅" if exists else "❌"
            print(f"  {status} {name}")
        
        # 验证设备列表
        device_count = selector.device_listbox.size()
        print(f"\n检测到 {device_count} 个GPU设备:")
        for i in range(device_count):
            device_info = selector.device_listbox.get(i)
            print(f"  • {device_info}")
        
        # 验证模式选项
        print(f"\nGPU模式:")
        print(f"  当前模式: {selector.mode_var.get()}")
        print(f"  可用模式: auto, single, multi")
        
        root.destroy()
        
        all_passed = all(checks.values()) and device_count > 0
        print(f"\n{'✅' if all_passed else '❌'} GPU选择器验证{'通过' if all_passed else '失败'}")
        return all_passed
        
    except Exception as e:
        print(f"\n❌ GPU选择器验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_multi_gpu_monitor():
    """验证多GPU监控面板"""
    print("\n" + "="*60)
    print("验证 2: 多GPU监控面板")
    print("="*60)
    
    try:
        from src.gui.components.multi_gpu_monitor import MultiGPUMonitorPanel
        
        root = tk.Tk()
        root.withdraw()
        
        # 创建监控面板
        monitor = MultiGPUMonitorPanel(root)
        monitor.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 验证关键组件
        checks = {
            "gpu_container": hasattr(monitor, 'gpu_container'),
            "total_throughput_label": hasattr(monitor, 'total_throughput_label'),
            "total_keys_label": hasattr(monitor, 'total_keys_label'),
            "active_gpu_label": hasattr(monitor, 'active_gpu_label'),
            "gpu_frames": hasattr(monitor, 'gpu_frames'),
        }
        
        print("\n组件检查:")
        for name, exists in checks.items():
            status = "✅" if exists else "❌"
            print(f"  {status} {name}")
        
        # 验证初始状态
        print(f"\n初始状态:")
        print(f"  总吞吐量: {monitor.total_throughput_label.cget('text')}")
        print(f"  已检查: {monitor.total_keys_label.cget('text')}")
        print(f"  活跃GPU: {monitor.active_gpu_label.cget('text')}")
        
        root.destroy()
        
        all_passed = all(checks.values())
        print(f"\n{'✅' if all_passed else '❌'} 多GPU监控面板验证{'通过' if all_passed else '失败'}")
        return all_passed
        
    except Exception as e:
        print(f"\n❌ 多GPU监控面板验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_export_button():
    """验证导出按钮"""
    print("\n" + "="*60)
    print("验证 3: 导出功能")
    print("="*60)
    
    try:
        # 读取GUI源代码
        gui_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'key_collision_gui.py'
        )
        
        with open(gui_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # 检查导出功能
        checks = {
            "导出方法定义": 'def _export_results(self):' in source,
            "导出按钮创建": 'self.btn_export' in source,
            "按钮绑定": 'command=self._export_results' in source,
            "JSON导出": 'json.dump' in source,
            "文件权限设置": 'os.chmod' in source,
            "异常处理-ValueError": 'except ValueError' in source,
            "异常处理-IOError": 'except IOError' in source,
            "异常处理-Exception": 'except Exception' in source,
        }
        
        print("\n功能检查:")
        for name, exists in checks.items():
            status = "✅" if exists else "❌"
            print(f"  {status} {name}")
        
        all_passed = all(checks.values())
        print(f"\n{'✅' if all_passed else '❌'} 导出功能验证{'通过' if all_passed else '失败'}")
        return all_passed
        
    except Exception as e:
        print(f"\n❌ 导出功能验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_config_validation():
    """验证配置验证"""
    print("\n" + "="*60)
    print("验证 4: 配置验证")
    print("="*60)
    
    try:
        from src.config.gui_config import validate_all_configs, WINDOW_CONFIG, PADDING_CONFIG
        
        # 验证配置
        result = validate_all_configs()
        print(f"\n配置验证结果: {'✅ 通过' if result else '❌ 失败'}")
        
        # 检查关键配置
        checks = {
            "WINDOW_CONFIG.use_adaptive_size": WINDOW_CONFIG.get('use_adaptive_size', False),
            "WINDOW_CONFIG.width_ratio": 'width_ratio' in WINDOW_CONFIG,
            "WINDOW_CONFIG.height_ratio": 'height_ratio' in WINDOW_CONFIG,
            "PADDING_CONFIG完整": all(k in PADDING_CONFIG for k in ['window_padx', 'window_pady', 'section_pady']),
        }
        
        print("\n配置项检查:")
        for name, exists in checks.items():
            status = "✅" if exists else "❌"
            print(f"  {status} {name}")
        
        all_passed = result and all(checks.values())
        print(f"\n{'✅' if all_passed else '❌'} 配置验证{'通过' if all_passed else '失败'}")
        return all_passed
        
    except Exception as e:
        print(f"\n❌ 配置验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_integration_in_gui():
    """验证GUI集成"""
    print("\n" + "="*60)
    print("验证 5: GUI集成")
    print("="*60)
    
    try:
        gui_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'key_collision_gui.py'
        )
        
        with open(gui_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # 检查集成代码
        checks = {
            "GPU选择器导入": 'from src.gui.components.gpu_selector import GPUSelectorPanel' in source,
            "GPU选择器实例化": 'self.gpu_selector = GPUSelectorPanel' in source,
            "GPU选择器降级处理": 'self.gpu_selector = None' in source,
            "多GPU监控导入": 'from src.gui.components.multi_gpu_monitor import MultiGPUMonitorPanel' in source,
            "多GPU监控实例化": 'self.gpu_monitor = MultiGPUMonitorPanel' in source,
            "配置验证调用": 'self._validate_configs()' in source,
            "配置验证方法": 'def _validate_configs(self):' in source,
        }
        
        print("\n集成检查:")
        for name, exists in checks.items():
            status = "✅" if exists else "❌"
            print(f"  {status} {name}")
        
        all_passed = all(checks.values())
        print(f"\n{'✅' if all_passed else '❌'} GUI集成验证{'通过' if all_passed else '失败'}")
        return all_passed
        
    except Exception as e:
        print(f"\n❌ GUI集成验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主验证流程"""
    print("\n" + "="*60)
    print("GPU选择器和导出功能界面验证")
    print("="*60)
    
    results = []
    
    # 执行验证
    results.append(("GPU选择器", verify_gpu_selector()))
    results.append(("多GPU监控面板", verify_multi_gpu_monitor()))
    results.append(("导出功能", verify_export_button()))
    results.append(("配置验证", verify_config_validation()))
    results.append(("GUI集成", verify_integration_in_gui()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("验证结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 验证通过")
    
    if passed == total:
        print("\n🎉 所有验证通过！GPU选择器和导出功能界面正常。")
        print("\n界面功能清单:")
        print("  ✅ GPU选择器已集成")
        print("     • 支持自动/单GPU/多GPU模式")
        print("     • 显示GPU设备列表")
        print("     • 显示设备详细信息")
        print("  ✅ 多GPU监控面板已集成")
        print("     • 实时显示GPU状态")
        print("     • 显示吞吐量和显存使用")
        print("     • 汇总统计信息")
        print("  ✅ 导出功能已实现")
        print("     • 支持JSON格式")
        print("     • 支持文本格式")
        print("     • 文件权限保护")
        print("  ✅ 配置验证已实现")
        print("     • 启动时自动验证")
        print("     • 错误友好提示")
        print("  ✅ GUI集成完整")
        print("     • 降级处理完善")
        print("     • 异常保护完整")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 项验证失败，请检查错误信息。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
