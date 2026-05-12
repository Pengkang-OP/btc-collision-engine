#!/usr/bin/env python3
"""
GPU性能监控示例

演示如何使用GPU性能监控系统：
1. 安装依赖
2. 创建监控器
3. 启动监控
4. 获取性能数据
"""

import sys
import time
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """检查依赖是否安装"""
    print("=" * 60)
    print("检查GPU监控依赖...")
    print("=" * 60)
    
    try:
        import pynvml
        print("✓ pynvml (NVIDIA监控) 已安装")
    except ImportError:
        print("✗ pynvml 未安装 - NVIDIA GPU监控将不可用")
        print("  安装命令: pip install pynvml")
    
    try:
        import pyamdgpuinfo
        print("✓ pyamdgpuinfo (AMD监控) 已安装")
    except ImportError:
        print("✗ pyamdgpuinfo 未安装 - AMD GPU监控将不可用")
        print("  安装命令: pip install pyamdgpuinfo")
    
    print()


def standalone_gpu_monitor():
    """独立的GPU监控器（不依赖完整引擎）"""
    print("=" * 60)
    print("独立GPU硬件监控演示")
    print("=" * 60)
    
    from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor
    
    # 创建监控器（不传入engine）
    monitor = GPUPerformanceMonitor(check_interval=1.0)
    
    # 手动初始化设备信息
    monitor._device_name = "Standalone Monitor"
    monitor._vendor = "Unknown"
    
    # 启动监控
    monitor.start()
    print("\n监控已启动，按Ctrl+C停止...\n")
    
    try:
        # 监控10秒
        for i in range(10):
            # 获取统计
            stats = monitor.get_stats()
            
            print(f"\n[第 {i+1} 秒] 实时GPU状态:")
            print(f"  GPU利用率: {stats.get('avg_gpu_utilization', 0) * 100:.1f}%")
            print(f"  显存使用: {stats.get('avg_memory_used_mb', 0):.0f} MB")
            print(f"  温度: {stats.get('avg_temperature', 0):.1f} °C")
            print(f"  功耗: {stats.get('avg_power_usage_w', 0):.1f} W")
            print(f"  硬件监控: {'活跃' if stats.get('hardware_monitoring_active', False) else '不可用'}")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n监控已停止")
    finally:
        monitor.stop()


def main():
    """主函数"""
    print("\nBTC Collision Engine - GPU性能监控系统\n")
    
    # 检查依赖
    check_dependencies()
    
    # 运行独立监控
    standalone_gpu_monitor()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
