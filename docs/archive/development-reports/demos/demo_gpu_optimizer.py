#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU自适应性能优化系统演示
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gpu.performance_optimizer import (
    get_gpu_optimizer, 
    PerformanceMetrics, 
    GPUVendor
)
import time


def print_separator(title):
    """打印分隔线"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_vendor_detection():
    """演示厂商检测"""
    print_separator("1. GPU厂商检测")
    
    optimizer = get_gpu_optimizer()
    
    test_cases = [
        ("NVIDIA GeForce RTX 3080", "NVIDIA Corporation"),
        ("AMD Radeon RX 6800 XT", "Advanced Micro Devices"),
        ("Intel Arc A770", "Intel Corporation"),
        ("RTX 4090", ""),
        ("Unknown GPU", "Unknown"),
    ]
    
    for device_name, vendor_str in test_cases:
        vendor = optimizer.detect_vendor(device_name, vendor_str)
        print(f"  {device_name:30s} -> {vendor.value}")


def demo_profile_creation():
    """演示配置创建"""
    print_separator("2. GPU配置优化")
    
    optimizer = get_gpu_optimizer()
    optimizer.reset()
    
    # NVIDIA配置
    print("\n[NVIDIA GeForce RTX 3080 - 10GB显存]")
    nvidia_profile = optimizer.create_optimized_profile(
        device_name="NVIDIA GeForce RTX 3080",
        vendor_str="NVIDIA Corporation",
        global_mem_size=10 * 1024**3,
        compile_time_ms=15000
    )
    print(f"  Batch Size:      {nvidia_profile.max_batch_size:,}")
    print(f"  Work Group Size: {nvidia_profile.work_group_size}")
    print(f"  内存使用率:      {nvidia_profile.memory_usage_ratio:.0%}")
    print(f"  异步执行:        {nvidia_profile.enable_async_execution}")
    print(f"  uint32 Workaround: {nvidia_profile.use_uint32_workaround}")
    
    # Intel配置
    print("\n[Intel Arc A770 - 16GB显存]")
    optimizer.reset()
    intel_profile = optimizer.create_optimized_profile(
        device_name="Intel Arc A770",
        vendor_str="Intel Corporation",
        global_mem_size=16 * 1024**3,
        compile_time_ms=22000
    )
    print(f"  Batch Size:      {intel_profile.max_batch_size:,}")
    print(f"  Work Group Size: {intel_profile.work_group_size}")
    print(f"  内存使用率:      {intel_profile.memory_usage_ratio:.0%}")
    print(f"  异步执行:        {intel_profile.enable_async_execution}")
    print(f"  uint32 Workaround: {intel_profile.use_uint32_workaround}")
    print(f"  推荐模式:        {intel_profile.preferred_mode}")


def demo_adaptive_adjustment():
    """演示自适应调整"""
    print_separator("3. 自适应性能调整")
    
    optimizer = get_gpu_optimizer()
    optimizer.reset()
    
    # 创建配置
    optimizer.create_optimized_profile(
        device_name="NVIDIA RTX 3080",
        vendor_str="NVIDIA",
        global_mem_size=10 * 1024**3
    )
    
    # 场景1: 性能良好
    print("\n[场景1: 性能良好 - 应增大batch_size]")
    for i in range(10):
        optimizer.record_performance(PerformanceMetrics(
            batch_execution_time_ms=50,  # 很快
            keys_per_second=200000,
            error_count=0
        ))
    
    batch_size = 100000
    new_batch_size, adjustments = optimizer.analyze_and_adjust(
        current_batch_size=batch_size,
        error_rate=0.0
    )
    print(f"  调整前: {batch_size:,}")
    print(f"  调整后: {new_batch_size:,}")
    print(f"  原因:   {list(adjustments.keys())[0] if adjustments else '无调整'}")
    
    # 场景2: 错误率高
    print("\n[场景2: 错误率高 - 应减小batch_size]")
    optimizer.reset()
    optimizer.create_optimized_profile(
        device_name="NVIDIA RTX 3080",
        vendor_str="NVIDIA",
        global_mem_size=10 * 1024**3
    )
    
    for i in range(10):
        optimizer.record_performance(PerformanceMetrics(
            batch_execution_time_ms=100,
            keys_per_second=100000,
            error_count=5
        ))
    
    batch_size = 100000
    new_batch_size, adjustments = optimizer.analyze_and_adjust(
        current_batch_size=batch_size,
        error_rate=0.05  # 5%错误率
    )
    print(f"  调整前: {batch_size:,}")
    print(f"  调整后: {new_batch_size:,}")
    print(f"  原因:   {list(adjustments.keys())[0] if adjustments else '无调整'}")
    
    # 场景3: 执行慢
    print("\n[场景3: 执行时间长 - 应减小batch_size]")
    optimizer.reset()
    optimizer.create_optimized_profile(
        device_name="NVIDIA RTX 3080",
        vendor_str="NVIDIA",
        global_mem_size=10 * 1024**3
    )
    
    for i in range(10):
        optimizer.record_performance(PerformanceMetrics(
            batch_execution_time_ms=2000,  # 2秒，很慢
            keys_per_second=5000,
            error_count=0
        ))
    
    batch_size = 100000
    new_batch_size, adjustments = optimizer.analyze_and_adjust(
        current_batch_size=batch_size,
        error_rate=0.0
    )
    print(f"  调整前: {batch_size:,}")
    print(f"  调整后: {new_batch_size:,}")
    print(f"  原因:   {list(adjustments.keys())[0] if adjustments else '无调整'}")


def demo_optimization_report():
    """演示优化报告"""
    print_separator("4. 优化报告生成")
    
    optimizer = get_gpu_optimizer()
    optimizer.reset()
    
    # 创建配置并模拟运行
    optimizer.create_optimized_profile(
        device_name="NVIDIA GeForce RTX 3080",
        vendor_str="NVIDIA Corporation",
        global_mem_size=10 * 1024**3,
        compile_time_ms=15000
    )
    
    # 模拟性能数据
    for i in range(20):
        optimizer.record_performance(PerformanceMetrics(
            kernel_compile_time_ms=15000 if i == 0 else 0,
            batch_execution_time_ms=50 + i,
            keys_per_second=200000 - i * 1000,
            memory_usage_mb=7000,
            error_count=1 if i > 15 else 0
        ))
    
    # 生成报告
    report = optimizer.get_optimization_report()
    
    print("\n[GPU配置文件]")
    profile = report.get("profile", {})
    for key, value in profile.items():
        print(f"  {key:20s}: {value}")
    
    print("\n[性能统计]")
    perf = report.get("performance", {})
    for key, value in perf.items():
        print(f"  {key:25s}: {value}")
    
    print("\n[优化建议]")
    recommendations = report.get("recommendations", [])
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
    else:
        print("  暂无建议")


def demo_memory_scaling():
    """演示显存 scaling"""
    print_separator("5. 显存自适应调整")
    
    optimizer = get_gpu_optimizer()
    
    mem_sizes = [
        (1, "1GB (低端GPU)"),
        (2, "2GB (入门级)"),
        (4, "4GB (中端)"),
        (8, "8GB (高端)"),
        (16, "16GB (旗舰)"),
    ]
    
    print(f"\n{'显存':15s} {'Batch Size':>12s} {'内存使用率':>12s}")
    print("-" * 45)
    
    for mem_gb, label in mem_sizes:
        optimizer.reset()
        profile = optimizer.create_optimized_profile(
            device_name="Test GPU",
            vendor_str="Test",
            global_mem_size=mem_gb * 1024**3
        )
        print(f"{label:15s} {profile.max_batch_size:>12,} {profile.memory_usage_ratio:>11.0%}")


def main():
    """主演示函数"""
    print("=" * 70)
    print("  GPU自适应性能优化系统演示")
    print("=" * 70)
    
    demo_vendor_detection()
    demo_profile_creation()
    demo_adaptive_adjustment()
    demo_optimization_report()
    demo_memory_scaling()
    
    print_separator("演示完成")
    print("\n系统已准备就绪，可以自动优化GPU碰撞引擎性能！")
    print("查看 GPU_PERFORMANCE_OPTIMIZATION.md 了解更多详情。\n")


if __name__ == "__main__":
    main()
