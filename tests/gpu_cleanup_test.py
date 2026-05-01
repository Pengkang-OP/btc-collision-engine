#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU资源清理测试脚本

专门测试GPU碰撞引擎的资源清理功能，确保stop()方法正确释放所有资源。
"""

import sys
import os
import time
import logging
from typing import Set

# 添加项目根目录到Python模块路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import pytest

pytestmark = pytest.mark.gpu  # 需要真实GPU硬件

from src.collision.gpu_collision_engine import GPUCollisionEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
        "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM",
    ]

    targets = set()
    for i in range(count):
        address = sample_addresses[i % len(sample_addresses)]
        targets.add(address)

    return targets


def test_gpu_cleanup():
    """测试GPU资源清理"""
    logger.info("开始测试GPU资源清理...")

    targets = generate_test_targets()

    try:
        # 创建GPU碰撞引擎
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=0,  # 使用第一个GPU
            batch_size=8192,
            data_logging_enabled=False,
        )

        logger.info("GPU碰撞引擎创建成功")

        # 启动引擎
        engine.start(mode="random")
        logger.info("GPU碰撞引擎启动成功")

        # 运行一小段时间
        time.sleep(5)

        # 停止引擎
        logger.info("停止GPU碰撞引擎...")
        engine.stop()
        logger.info("GPU碰撞引擎停止成功")

        # 验证资源清理
        logger.info("验证资源清理...")

        # 检查关键属性是否已清理
        assert not engine._running, "引擎状态应该为停止"
        assert engine._stop_event.is_set(), "停止事件应该已设置"

        logger.info("GPU资源清理测试通过！")
        return True

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_multiple_start_stop():
    """测试多次启动和停止"""
    logger.info("开始测试多次启动和停止...")

    targets = generate_test_targets()

    try:
        # 创建GPU碰撞引擎
        engine = GPUCollisionEngine(
            targets=targets, device_index=0, batch_size=8192, data_logging_enabled=False
        )

        logger.info("GPU碰撞引擎创建成功")

        # 多次启动和停止
        for i in range(3):
            logger.info(f"第{i+1}次启动引擎...")
            engine.start(mode="random")
            time.sleep(2)
            logger.info(f"第{i+1}次停止引擎...")
            engine.stop()
            time.sleep(1)

        logger.info("多次启动和停止测试通过！")
        return True

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("开始GPU资源清理测试...")

    # 运行测试
    tests = [
        ("GPU资源清理测试", test_gpu_cleanup),
        ("多次启动和停止测试", test_multiple_start_stop),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n运行测试: {test_name}")
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name} 通过")
        else:
            logger.info(f"❌ {test_name} 失败")

    # 生成测试报告
    logger.info(f"\n测试完成！")
    logger.info(f"总测试数: {total}")
    logger.info(f"通过测试数: {passed}")
    logger.info(f"测试通过率: {passed / total * 100:.1f}%")


if __name__ == "__main__":
    main()
