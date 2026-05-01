#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""性能基准测试脚本

用于测试多GPU优化后的性能效果，包括：
- 双缓冲异步执行模式
- 智能批次大小调整
- 动态负载均衡
- 内存管理优化

测试场景：
1. 单GPU性能测试
2. 多GPU性能测试
3. 不同批次大小测试
4. 内存使用测试
5. 负载均衡测试
"""

import sys
import os
import time
import random
import logging
from typing import Set, List, Dict

# 添加项目根目录到Python模块路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import pytest

pytestmark = pytest.mark.gpu  # 需要真实GPU硬件

from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_test_targets(count: int = 1000) -> Set[str]:
    """生成测试目标地址

    Args:
        count: 目标地址数量

    Returns:
        目标地址集合
    """
    # 生成一些格式正确的比特币地址作为测试目标
    # 注意：这些地址不是真实的私钥生成的，仅用于测试
    targets = set()

    # 使用几个格式正确的比特币地址作为测试目标
    # 这些是真实的比特币地址格式，但不是真实的私钥生成的
    sample_addresses = [
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        "1N5czHm9q7wSjzM7X4GCe4yi7z14L9tK8",
        "1M8s2S5bgAzSSzVTeL7zruvMPLvzSkEAuv",
        "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM",
    ]

    # 循环生成多个目标地址
    for i in range(count):
        # 循环使用示例地址
        address = sample_addresses[i % len(sample_addresses)]
        targets.add(address)

    return targets


def test_single_gpu_performance():
    """测试单GPU性能"""
    logger.info("开始单GPU性能测试...")

    # 生成测试目标
    targets = generate_test_targets(1000)

    # 创建多GPU引擎，只使用一个GPU
    engine = MultiGPUCollisionEngine(
        {"enable_async_execution": True, "workload_monitor_interval": 2}
    )

    # 初始化引擎，只使用一个GPU
    if not engine.initialize(device_count=1):
        logger.error("无法初始化单GPU引擎")
        return

    # 测试参数
    total_keys = 10000000  # 1000万私钥
    test_duration = 30  # 测试持续时间(秒)

    # 启动碰撞
    start_time = time.time()
    if not engine.start(targets=targets, mode="random", total_keys=total_keys):
        logger.error("无法启动单GPU测试")
        engine.cleanup()
        return

    # 运行测试
    time.sleep(test_duration)

    # 停止引擎
    engine.stop()

    # 获取统计信息
    stats = engine.get_combined_stats()
    elapsed_time = stats.get("elapsed_time", test_duration)
    total_keys_checked = stats.get("total_keys_checked", 0)
    throughput = stats.get("combined_throughput", 0)

    logger.info(f"单GPU测试结果:")
    logger.info(f"  总检查私钥数: {total_keys_checked:,}")
    logger.info(f"  运行时间: {elapsed_time:.2f}秒")
    logger.info(f"  吞吐量: {throughput:.0f} keys/s")

    # 清理资源
    engine.cleanup()

    return stats


def test_multi_gpu_performance():
    """测试多GPU性能"""
    logger.info("开始多GPU性能测试...")

    # 生成测试目标
    targets = generate_test_targets(1000)

    # 创建多GPU引擎
    engine = MultiGPUCollisionEngine(
        {"enable_async_execution": True, "workload_monitor_interval": 2, "auto_rebalance": True}
    )

    # 初始化引擎，使用所有可用GPU
    if not engine.initialize(device_count=-1):
        logger.error("无法初始化多GPU引擎")
        return

    # 测试参数
    total_keys = 50000000  # 5000万私钥
    test_duration = 60  # 测试持续时间(秒)

    # 启动碰撞
    start_time = time.time()
    if not engine.start(targets=targets, mode="random", total_keys=total_keys):
        logger.error("无法启动多GPU测试")
        engine.cleanup()
        return

    # 运行测试
    time.sleep(test_duration)

    # 停止引擎
    engine.stop()

    # 获取统计信息
    stats = engine.get_combined_stats()
    elapsed_time = stats.get("elapsed_time", test_duration)
    total_keys_checked = stats.get("total_keys_checked", 0)
    throughput = stats.get("combined_throughput", 0)
    device_count = stats.get("device_count", 0)

    logger.info(f"多GPU测试结果:")
    logger.info(f"  GPU数量: {device_count}")
    logger.info(f"  总检查私钥数: {total_keys_checked:,}")
    logger.info(f"  运行时间: {elapsed_time:.2f}秒")
    logger.info(f"  总吞吐量: {throughput:.0f} keys/s")
    if device_count > 0:
        logger.info(f"  每GPU平均吞吐量: {throughput / device_count:.0f} keys/s")

    # 打印每个GPU的详细统计
    per_device = stats.get("per_device", {})
    for device_idx, device_stats in per_device.items():
        logger.info(f"  GPU {device_idx}:")
        logger.info(f"    检查私钥数: {device_stats.get('keys_checked', 0):,}")
        logger.info(f"    吞吐量: {device_stats.get('throughput', 0):.0f} keys/s")
        logger.info(f"    错误率: {device_stats.get('error_rate', 0):.2f}%")

    # 清理资源
    engine.cleanup()

    return stats


def test_batch_size_performance():
    """测试不同批次大小的性能"""
    logger.info("开始批次大小性能测试...")

    # 生成测试目标
    targets = generate_test_targets(1000)

    # 测试不同批次大小
    batch_sizes = [65536, 131072, 262144, 524288, 1048576]
    results = []

    for batch_size in batch_sizes:
        logger.info(f"测试批次大小: {batch_size}")

        # 创建多GPU引擎
        engine = MultiGPUCollisionEngine(
            {"enable_async_execution": True, "per_device_config": {"0": {"batch_size": batch_size}}}
        )

        # 初始化引擎，只使用一个GPU
        if not engine.initialize(device_count=1):
            logger.error("无法初始化引擎")
            continue

        # 测试参数
        total_keys = 5000000  # 500万私钥
        test_duration = 20  # 测试持续时间(秒)

        # 启动碰撞
        if not engine.start(targets=targets, mode="random", total_keys=total_keys):
            logger.error("无法启动测试")
            engine.cleanup()
            continue

        # 运行测试
        time.sleep(test_duration)

        # 停止引擎
        engine.stop()

        # 获取统计信息
        stats = engine.get_combined_stats()
        elapsed_time = stats.get("elapsed_time", test_duration)
        total_keys_checked = stats.get("total_keys_checked", 0)
        throughput = stats.get("combined_throughput", 0)

        result = {
            "batch_size": batch_size,
            "keys_checked": total_keys_checked,
            "elapsed_time": elapsed_time,
            "throughput": throughput,
        }
        results.append(result)

        logger.info(f"  结果: {throughput:.0f} keys/s")

        # 清理资源
        engine.cleanup()

    # 打印批次大小测试结果
    logger.info("批次大小测试结果汇总:")
    for result in results:
        logger.info(f"  批次大小 {result['batch_size']}: {result['throughput']:.0f} keys/s")

    return results


def test_memory_usage():
    """测试内存使用情况"""
    logger.info("开始内存使用测试...")

    # 生成测试目标
    targets = generate_test_targets(1000)

    # 创建多GPU引擎
    engine = MultiGPUCollisionEngine(
        {"enable_async_execution": True, "workload_monitor_interval": 2}
    )

    # 初始化引擎，只使用一个GPU
    if not engine.initialize(device_count=1):
        logger.error("无法初始化引擎")
        return

    # 测试参数
    total_keys = 20000000  # 2000万私钥
    test_duration = 40  # 测试持续时间(秒)

    # 启动碰撞
    if not engine.start(targets=targets, mode="random", total_keys=total_keys):
        logger.error("无法启动测试")
        engine.cleanup()
        return

    # 运行测试，期间监控内存使用
    start_time = time.time()
    while time.time() - start_time < test_duration:
        time.sleep(5)
        # 获取工作负载统计
        workload_stats = engine.get_workload_stats()
        logger.info(f"内存使用监控: {workload_stats}")

    # 停止引擎
    engine.stop()

    # 获取统计信息
    stats = engine.get_combined_stats()

    # 清理资源
    engine.cleanup()

    return stats


def test_load_balancing():
    """测试负载均衡效果"""
    logger.info("开始负载均衡测试...")

    # 生成测试目标
    targets = generate_test_targets(1000)

    # 创建多GPU引擎
    engine = MultiGPUCollisionEngine(
        {"enable_async_execution": True, "workload_monitor_interval": 2, "auto_rebalance": True}
    )

    # 初始化引擎，使用所有可用GPU
    if not engine.initialize(device_count=-1):
        logger.error("无法初始化引擎")
        return

    # 测试参数
    total_keys = 100000000  # 1亿私钥
    test_duration = 120  # 测试持续时间(秒)

    # 启动碰撞
    if not engine.start(targets=targets, mode="random", total_keys=total_keys):
        logger.error("无法启动测试")
        engine.cleanup()
        return

    # 运行测试，期间监控负载均衡
    start_time = time.time()
    while time.time() - start_time < test_duration:
        time.sleep(10)
        # 获取工作负载统计
        workload_stats = engine.get_workload_stats()
        logger.info(f"负载均衡监控: {workload_stats}")

        # 获取性能历史
        performance_history = engine.get_performance_history()
        if performance_history:
            latest = performance_history[-1]
            logger.info(f"最新性能: {latest['combined_throughput']:.0f} keys/s")

    # 停止引擎
    engine.stop()

    # 获取统计信息
    stats = engine.get_combined_stats()

    # 清理资源
    engine.cleanup()

    return stats


def main():
    """主测试函数"""
    logger.info("开始性能基准测试...")

    # 运行各个测试
    test_results = {
        "single_gpu": test_single_gpu_performance(),
        "multi_gpu": test_multi_gpu_performance(),
        "batch_size": test_batch_size_performance(),
        "memory_usage": test_memory_usage(),
        "load_balancing": test_load_balancing(),
    }

    # 打印最终结果
    logger.info("性能基准测试完成！")
    logger.info("测试结果汇总:")

    # 单GPU测试结果
    if test_results["single_gpu"]:
        single_gpu_stats = test_results["single_gpu"]
        logger.info(f"单GPU测试: {single_gpu_stats.get('combined_throughput', 0):.0f} keys/s")

    # 多GPU测试结果
    if test_results["multi_gpu"]:
        multi_gpu_stats = test_results["multi_gpu"]
        device_count = multi_gpu_stats.get("device_count", 0)
        total_throughput = multi_gpu_stats.get("combined_throughput", 0)
        logger.info(f"多GPU测试: {device_count}个GPU, 总吞吐量 {total_throughput:.0f} keys/s")
        if device_count > 0:
            logger.info(f"每GPU平均: {total_throughput / device_count:.0f} keys/s")

    # 批次大小测试结果
    if test_results["batch_size"]:
        best_batch = max(test_results["batch_size"], key=lambda x: x["throughput"])
        logger.info(
            f"最佳批次大小: {best_batch['batch_size']} (吞吐量: {best_batch['throughput']:.0f} keys/s)"
        )

    logger.info("所有测试已完成！")


if __name__ == "__main__":
    main()
