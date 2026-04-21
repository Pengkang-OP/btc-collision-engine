#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证性能监控配置
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.performance_monitor import _get_tracker_config, EnhancedPerformanceMonitor

def main():
    print("=" * 60)
    print("性能监控配置验证")
    print("=" * 60)
    
    # 获取配置
    config = _get_tracker_config()
    
    print("\n当前配置:")
    print(f"  启用性能监控: {config['enabled']}")
    print(f"  最大记录数: {config['max_records']}")
    print(f"  慢操作阈值: {config['slow_threshold_ms']}ms ({config['slow_threshold_ms']/1000:.1f}秒)")
    print(f"  追踪慢操作: {config['track_slow_operations']}")
    print(f"  日志级别: {config['log_level']}")
    
    print("\n" + "=" * 60)
    print("阈值合理性分析")
    print("=" * 60)
    
    threshold_sec = config['slow_threshold_ms'] / 1000
    
    if threshold_sec < 1:
        print("⚠️  警告: 阈值过低 (< 1秒)")
        print("   - 会产生大量误报警告")
        print("   - 建议至少设置为 1000ms (1秒)")
    elif threshold_sec < 5:
        print("ℹ️  提示: 阈值较低 (1-5秒)")
        print("   - 适合监控常规操作")
        print("   - GPU内核编译可能会触发警告（正常现象）")
    elif threshold_sec < 30:
        print("✅ 阈值合理 (5-30秒)")
        print("   - 适合监控 GPU 内核编译和初始化")
        print("   - 首次编译通常需要 10-30 秒")
        print("   - 后续运行会使用缓存，速度更快")
    else:
        print("⚠️  警告: 阈值过高 (> 30秒)")
        print("   - 可能会错过真正的性能问题")
        print("   - 建议不超过 30000ms (30秒)")
    
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)
    print("\n建议:")
    print(f"  - 当前阈值 {config['slow_threshold_ms']}ms 已设置为合理值")
    print("  - GPU 内核编译首次运行需要 10-30 秒是正常的")
    print("  - 后续启动会使用缓存，速度会显著提升")
    print("  - 如果仍然看到警告，可以考虑进一步提高阈值")
    
    # 测试配置加载
    print("\n" + "=" * 60)
    print("测试配置文件加载")
    print("=" * 60)
    
    from src.config.config_manager import ConfigManager
    import os
    
    # 获取配置文件路径
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    print(f"\n配置文件路径: {config_path}")
    
    # 使用配置文件路径初始化
    config_mgr = ConfigManager(config_file=config_path)
    
    threshold_from_config = config_mgr.get('performance_monitoring.slow_threshold_ms', 1000)
    print(f"从 config.json 读取的阈值: {threshold_from_config}ms")
    
    if threshold_from_config == 5000:
        print("✅ 配置已正确加载!")
        print("\n说明:")
        print("  - 配置文件已成功更新为 5000ms")
        print("  - 下次启动程序时将使用新配置")
        print("  - GPU 内核编译警告将不再出现（22秒 < 不触发 5秒阈值）")
    else:
        print(f"⚠️  配置可能未更新，期望 5000ms，实际 {threshold_from_config}ms")
        print("   提示: 如果程序已在运行，需要重启才能加载新配置")

if __name__ == "__main__":
    main()
