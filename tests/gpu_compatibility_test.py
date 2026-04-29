#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU兼容性测试脚本

测试系统在不同厂商和型号的GPU上的兼容性和性能。
"""

import sys
import os
import time
import logging
from typing import Set, List, Dict

# 添加项目根目录到Python模块路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.gpu.device import GPUDeviceDetector, identify_vendor, identify_gpu_model

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_test_targets(count: int = 5) -> Set[str]:
    """生成测试目标地址
    
    Args:
        count: 目标地址数量
        
    Returns:
        目标地址集合
    """
    # 使用格式正确的比特币地址作为测试目标
    sample_addresses = [
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        "1N5czHm9q7wSjzM7X4GCe4yi7z14L9tK8",
        "1M8s2S5bgAzSSzVTeL7zruvMPLvzSkEAuv",
        "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM"
    ]
    
    targets = set()
    for i in range(count):
        address = sample_addresses[i % len(sample_addresses)]
        targets.add(address)
    
    return targets


def test_gpu_device_detection():
    """测试GPU设备检测功能"""
    logger.info("开始测试GPU设备检测...")
    
    try:
        devices = GPUDeviceDetector.detect_devices()
        logger.info(f"检测到 {len(devices)} 个GPU设备")
        
        for i, device in enumerate(devices):
            device_name = device.get('name', 'Unknown')
            vendor = device.get('vendor', 'Unknown')
            vendor_identifier = identify_vendor(device_name, vendor)
            gpu_model = identify_gpu_model(device_name, vendor_identifier)
            
            logger.info(f"  [{i}] {device_name}")
            logger.info(f"    - 厂商: {vendor}")
            logger.info(f"    - 厂商标识: {vendor_identifier}")
            logger.info(f"    - 型号标识: {gpu_model}")
            logger.info(f"    - 显存: {device.get('global_mem_size', 0)/(1024**3):.1f} GB")
            logger.info(f"    - 计算单元: {device.get('max_compute_units', 'N/A')}")
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gpu_initialization(device_index: int):
    """测试GPU设备初始化
    
    Args:
        device_index: 设备索引
        
    Returns:
        (成功标志, 错误信息)
    """
    logger.info(f"开始测试GPU设备 [{device_index}] 初始化...")
    
    targets = generate_test_targets()
    
    try:
        # 创建GPU碰撞引擎
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=device_index,
            batch_size=8192,
            data_logging_enabled=False
        )
        
        logger.info(f"GPU设备 [{device_index}] 初始化成功")
        
        # 启动引擎
        engine.start(mode="random")
        logger.info(f"GPU设备 [{device_index}] 启动成功")
        
        # 运行一小段时间
        time.sleep(3)
        
        # 停止引擎
        engine.stop()
        logger.info(f"GPU设备 [{device_index}] 停止成功")
        
        return True, None
        
    except Exception as e:
        error_msg = f"GPU设备 [{device_index}] 测试失败: {e}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return False, error_msg


def test_gpu_batch_sizes(device_index: int):
    """测试不同批次大小的兼容性
    
    Args:
        device_index: 设备索引
        
    Returns:
        (成功标志, 错误信息)
    """
    logger.info(f"开始测试GPU设备 [{device_index}] 不同批次大小...")
    
    targets = generate_test_targets()
    
    # 测试不同的批次大小
    batch_sizes = [4096, 8192, 16384, 32768]
    
    for batch_size in batch_sizes:
        try:
            logger.info(f"  测试批次大小: {batch_size}")
            
            # 创建GPU碰撞引擎
            engine = GPUCollisionEngine(
                targets=targets,
                device_index=device_index,
                batch_size=batch_size,
                data_logging_enabled=False
            )
            
            # 启动引擎
            engine.start(mode="random")
            
            # 运行一小段时间
            time.sleep(2)
            
            # 停止引擎
            engine.stop()
            
            logger.info(f"  批次大小 {batch_size} 测试成功")
            
        except Exception as e:
            error_msg = f"GPU设备 [{device_index}] 批次大小 {batch_size} 测试失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    return True, None


def test_all_gpus():
    """测试所有可用的GPU设备"""
    logger.info("开始测试所有GPU设备...")
    
    # 检测所有可用的GPU设备
    devices = GPUDeviceDetector.detect_devices()
    
    if not devices:
        logger.warning("没有检测到GPU设备")
        return []
    
    test_results = []
    
    for i, device in enumerate(devices):
        device_name = device.get('name', 'Unknown')
        logger.info(f"\n=== 测试 GPU 设备 [{i}]: {device_name} ===")
        
        # 测试设备初始化
        init_success, init_error = test_gpu_initialization(i)
        
        # 测试不同批次大小
        batch_success, batch_error = test_gpu_batch_sizes(i) if init_success else (False, "初始化失败")
        
        # 记录测试结果
        test_results.append({
            'device_index': i,
            'device_name': device_name,
            'init_success': init_success,
            'init_error': init_error,
            'batch_success': batch_success,
            'batch_error': batch_error
        })
    
    return test_results


def generate_compatibility_report(test_results: List[Dict]):
    """生成兼容性测试报告
    
    Args:
        test_results: 测试结果列表
        
    Returns:
        兼容性测试报告
    """
    logger.info("\n=== GPU 兼容性测试报告 ===")
    
    if not test_results:
        logger.info("没有测试结果")
        return
    
    total_devices = len(test_results)
    init_success_count = sum(1 for result in test_results if result['init_success'])
    batch_success_count = sum(1 for result in test_results if result['batch_success'])
    
    logger.info(f"测试设备数量: {total_devices}")
    logger.info(f"初始化成功: {init_success_count}/{total_devices} ({init_success_count/total_devices*100:.1f}%)")
    logger.info(f"批次大小测试成功: {batch_success_count}/{total_devices} ({batch_success_count/total_devices*100:.1f}%)")
    
    for result in test_results:
        device_index = result['device_index']
        device_name = result['device_name']
        init_status = "✅ 成功" if result['init_success'] else "❌ 失败"
        batch_status = "✅ 成功" if result['batch_success'] else "❌ 失败"
        
        logger.info(f"\n设备 [{device_index}]: {device_name}")
        logger.info(f"  初始化: {init_status}")
        if not result['init_success'] and result['init_error']:
            logger.info(f"    错误: {result['init_error']}")
        logger.info(f"  批次大小测试: {batch_status}")
        if not result['batch_success'] and result['batch_error']:
            logger.info(f"    错误: {result['batch_error']}")


def main():
    """主测试函数"""
    logger.info("开始GPU兼容性测试...")
    
    # 测试GPU设备检测
    detection_success = test_gpu_device_detection()
    
    if not detection_success:
        logger.error("GPU设备检测失败，测试终止")
        return
    
    # 测试所有GPU设备
    test_results = test_all_gpus()
    
    # 生成兼容性测试报告
    generate_compatibility_report(test_results)
    
    logger.info("\nGPU兼容性测试完成！")


if __name__ == "__main__":
    main()
