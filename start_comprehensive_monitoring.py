#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动全面监控脚本

启用所有监控功能：
- 数据日志记录
- 实时监控数据采集
- GPU监控
- 告警系统
- 报告生成
- 性能优化监控
"""

import sys
import os
import time
import logging
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.monitoring.monitor_config import MonitorConfig
from src.monitoring.enhanced_monitoring import EnhancedMonitoringSystem
from src.monitoring.gpu_monitor import GPUMonitor
from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ComprehensiveMonitor")


def create_comprehensive_config() -> MonitorConfig:
    """创建全面监控配置
    
    Returns:
        全面监控配置对象
    """
    config = MonitorConfig(
        # 数据日志配置 - 启用
        data_logging_enabled=True,
        data_logging_interval=1.0,  # 每秒记录一次
        data_log_save_frequency=5,  # 每5次保存一次
        
        # 监控配置 - 启用
        enable_monitoring_data=True,  # 启用监控数据采集
        collection_interval=1.0,  # 每秒采集一次
        
        # GPU监控 - 启用
        enable_gpu_monitoring=True,
        gpu_monitoring_interval=2.0,  # 每2秒采集一次GPU数据
        
        # 告警配置 - 启用
        alert_enabled=True,
        alert_threshold=0.8,  # 80%阈值触发告警
        alert_cooldown=60.0,  # 60秒冷却时间
        max_alerts_per_hour=120,  # 每小时最多120条告警
        
        # 报告配置 - 启用
        report_enabled=True,
        report_interval=300.0,  # 每5分钟生成一次报告
        report_save_path="data_logs",
        
        # 性能优化配置 - 启用
        enable_performance_optimization=True,
        auto_adjust_batch_size=True,
        performance_log_interval=5.0,  # 每5秒记录一次性能
        
        # 调试模式 - 启用（用于全面监控）
        enable_debug_mode=True,
        max_log_entries=50000,  # 最大50000条日志
        cleanup_interval=43200.0,  # 12小时清理一次
    )
    
    return config


def start_comprehensive_monitoring():
    """启动全面监控系统"""
    logger.info("=" * 60)
    logger.info("启动全面监控系统")
    logger.info("=" * 60)
    
    # 1. 创建全面监控配置
    config = create_comprehensive_config()
    logger.info(f"监控配置: {config}")
    
    # 2. 初始化增强监控系统
    monitoring_system = EnhancedMonitoringSystem(
        engine=None,  # 引擎将在运行时绑定
        config=config
    )
    
    # 3. 初始化GPU监控
    gpu_monitor = None
    gpu_performance_monitor = None
    
    try:
        gpu_monitor = GPUMonitor()
        gpu_info = gpu_monitor.get_gpu_info()
        if gpu_info:
            logger.info(f"GPU设备: {gpu_info.get('name', 'Unknown')}")
            logger.info(f"GPU厂商: {gpu_info.get('vendor', 'Unknown')}")
            logger.info(f"显存总量: {gpu_info.get('memory_total', 0) / (1024**3):.2f} GB")
        else:
            logger.warning("未检测到GPU设备，GPU监控将不可用")
    except Exception as e:
        logger.warning(f"GPU监控初始化失败: {e}")
    
    try:
        gpu_performance_monitor = GPUPerformanceMonitor()
        logger.info("GPU性能监控器已初始化")
    except Exception as e:
        logger.warning(f"GPU性能监控器初始化失败: {e}")
    
    # 4. 启动监控系统
    monitoring_system.start()
    logger.info("增强监控系统已启动")
    
    if gpu_performance_monitor:
        try:
            gpu_performance_monitor.start()
            logger.info("GPU性能监控器已启动")
        except Exception as e:
            logger.warning(f"启动GPU性能监控器失败: {e}")
    
    logger.info("=" * 60)
    logger.info("全面监控系统启动完成")
    logger.info("=" * 60)
    
    # 5. 显示监控状态
    print_monitoring_status(monitoring_system, gpu_monitor, gpu_performance_monitor)
    
    return monitoring_system, gpu_monitor, gpu_performance_monitor


def print_monitoring_status(monitoring_system, gpu_monitor, gpu_performance_monitor):
    """打印监控状态"""
    print("\n" + "=" * 60)
    print("🔍 全面监控状态")
    print("=" * 60)
    
    # 增强监控系统状态
    print(f"\n📊 增强监控系统:")
    print(f"  运行状态: {'✅ 运行中' if monitoring_system.is_running() else '❌ 未运行'}")
    print(f"  数据日志: {'✅ 启用' if monitoring_system.data_logger else '❌ 禁用'}")
    print(f"  监控数据: {'✅ 启用' if monitoring_system.storage else '❌ 禁用'}")
    print(f"  告警系统: {'✅ 启用' if monitoring_system.alert_system else '❌ 禁用'}")
    print(f"  报告生成: {'✅ 启用' if monitoring_system.report_generator else '❌ 禁用'}")
    
    # GPU监控状态
    if gpu_monitor:
        print(f"\n🎮 GPU监控:")
        try:
            gpu_metrics = gpu_monitor.get_gpu_metrics()
            print(f"  GPU名称: {gpu_metrics.get('name', 'Unknown')}")
            print(f"  显存使用: {gpu_metrics.get('memory_used', 0) / (1024**2):.0f} MB / {gpu_metrics.get('memory_total', 0) / (1024**2):.0f} MB")
            print(f"  使用率: {gpu_metrics.get('memory_usage_percent', 0):.1f}%")
        except Exception as e:
            print(f"  获取GPU信息失败: {e}")
    
    # GPU性能监控状态
    if gpu_performance_monitor:
        print(f"\n📈 GPU性能监控:")
        print(f"  运行状态: {'✅ 运行中' if hasattr(gpu_performance_monitor, '_running') and gpu_performance_monitor._running else '❌ 未运行'}")
    
    print("\n" + "=" * 60)


def monitor_loop(monitoring_system, gpu_monitor, gpu_performance_monitor):
    """监控循环 - 实时显示监控数据"""
    logger.info("开始实时监控循环...")
    logger.info("按 Ctrl+C 停止监控")
    
    try:
        while True:
            time.sleep(5)  # 每5秒刷新一次
            
            # 获取当前状态
            try:
                status = monitoring_system.get_current_status()
                
                # 打印关键指标
                if 'data_stats' in status:
                    stats = status['data_stats']
                    print(f"\r📊 性能: {stats.get('speed', 0):.2f} keys/s | "
                          f"已检测: {stats.get('total_checks', 0):,} | "
                          f"匹配: {stats.get('total_matches', 0)} | "
                          f"CPU: {stats.get('cpu_usage', 0):.1f}% | "
                          f"内存: {stats.get('memory_usage', 0):.0f}MB",
                          end='', flush=True)
            except Exception as e:
                logger.debug(f"获取状态失败: {e}")
                
    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在停止监控...")
        
        # 停止所有监控
        monitoring_system.stop()
        if gpu_performance_monitor:
            gpu_performance_monitor.stop()
        
        logger.info("所有监控系统已停止")
        print("\n监控系统已停止")


if __name__ == "__main__":
    # 启动全面监控
    monitoring_system, gpu_monitor, gpu_performance_monitor = start_comprehensive_monitoring()
    
    # 进入监控循环
    monitor_loop(monitoring_system, gpu_monitor, gpu_performance_monitor)
