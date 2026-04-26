#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控系统启动脚本

该脚本用于启动监控系统，实时监控碰撞引擎的运行状态和性能指标。
"""

import sys
import time
import argparse
from datetime import datetime

from src.monitoring.monitoring_system import MonitoringSystem
from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.utils import get_configured_logger

logger = get_configured_logger("MonitoringScript")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="监控系统启动脚本")
    parser.add_argument(
        "--mode", 
        choices=["cpu", "gpu"], 
        default="cpu",
        help="选择碰撞引擎模式 (默认: cpu)"
    )
    parser.add_argument(
        "--targets", 
        nargs="*",
        default=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
        help="目标地址列表"
    )
    parser.add_argument(
        "--target-file",
        type=str,
        help="从文件加载目标地址"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="数据采集间隔 (秒)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        help="运行时长 (秒)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="生成报告"
    )
    return parser.parse_args()

def load_targets_from_file(file_path):
    """从文件加载目标地址"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            targets = [line.strip() for line in f if line.strip()]
        logger.info(f"从文件 {file_path} 加载了 {len(targets)} 个目标地址")
        return targets
    except Exception as e:
        logger.error(f"加载目标文件失败: {e}")
        return []

def main():
    """主函数"""
    args = parse_args()
    
    # 加载目标地址
    targets = args.targets
    if args.target_file:
        file_targets = load_targets_from_file(args.target_file)
        if file_targets:
            targets = file_targets
    
    logger.info(f"监控目标地址: {targets}")
    
    # 初始化碰撞引擎
    if args.mode == "gpu":
        try:
            engine = GPUCollisionEngine(targets=targets)
            logger.info("使用GPU碰撞引擎")
        except Exception as e:
            logger.warning(f"GPU引擎初始化失败，降级到CPU模式: {e}")
            engine = KeyCollisionEngine(targets=targets)
    else:
        engine = KeyCollisionEngine(targets=targets)
        logger.info("使用CPU碰撞引擎")
    
    # 初始化监控系统
    monitoring_system = MonitoringSystem(engine=engine, collection_interval=args.interval)
    
    try:
        # 启动监控系统
        monitoring_system.start()
        logger.info(f"监控系统已启动，采集间隔: {args.interval}秒")
        
        # 启动碰撞引擎
        engine.start()
        logger.info("碰撞引擎已启动")
        
        # 运行指定时长
        if args.duration:
            logger.info(f"监控系统将运行 {args.duration} 秒")
            time.sleep(args.duration)
        else:
            logger.info("监控系统已启动，按 Ctrl+C 停止")
            while True:
                time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("用户中断，正在停止系统...")
    except Exception as e:
        logger.error(f"运行出错: {e}")
    finally:
        # 停止碰撞引擎
        if engine.is_running():
            engine.stop()
            logger.info("碰撞引擎已停止")
        
        # 停止监控系统
        monitoring_system.stop()
        logger.info("监控系统已停止")
        
        # 生成报告
        if args.report:
            logger.info("生成监控报告...")
            report = monitoring_system.generate_report()
            if "error" not in report:
                logger.info(f"报告生成成功: {report.get('date', 'unknown')}")
                logger.info(f"总检测数: {report.get('summary', {}).get('total_checked', 0)}")
                logger.info(f"找到的匹配数: {report.get('summary', {}).get('matches_found', 0)}")
                logger.info(f"平均速度: {report.get('summary', {}).get('average_speed', 0):.2f} keys/s")
            else:
                logger.error(f"报告生成失败: {report.get('error')}")

if __name__ == "__main__":
    main()
