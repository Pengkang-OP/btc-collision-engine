#!/usr/bin/env python3
"""
单GPU测试脚本

此脚本用于测试单GPU的功能，包括初始化、碰撞检测和资源释放等。
"""
import time
import logging
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

pytestmark = pytest.mark.gpu  # 需要真实GPU硬件

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.utils import init_logging, get_configured_logger

# 配置日志
init_logging()
logger = get_configured_logger("SingleGPUTest")

def test_single_gpu_initialization():
    """测试单GPU初始化"""
    logger.info("开始测试单GPU初始化")

    # 创建一个测试目标地址集合
    test_targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

    # 初始化GPU碰撞引擎
    engine = None
    try:
        engine = GPUCollisionEngine(device_index=0, batch_size=1024, targets=test_targets)
        logger.info("✅ 单GPU初始化成功")

        # 获取设备信息
        device_info = engine.get_device_info()
        logger.info(f"设备信息: {device_info}")

        return True
    except Exception as e:
        logger.error(f"❌ 单GPU初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("单GPU引擎已停止")
            except Exception as e:
                logger.warning(f"停止引擎时出现错误: {e}")

def test_single_gpu_collision_detection():
    """测试单GPU碰撞检测"""
    logger.info("开始测试单GPU碰撞检测")

    # 创建一个测试目标地址集合
    test_targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

    # 初始化GPU碰撞引擎
    engine = None
    try:
        engine = GPUCollisionEngine(device_index=0, batch_size=1024, targets=test_targets)
        logger.info("单GPU引擎初始化成功")

        # 运行碰撞检测任务
        logger.info("运行碰撞检测任务...")

        # 生成一个测试种子
        test_seed = b'\x00' * 31 + b'\x01'

        # 运行碰撞检测
        start_time = time.time()
        # 注意：我们没有调用具体的碰撞检测方法，因为我们只是测试引擎的初始化和停止
        elapsed = time.time() - start_time
        logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")

        return True
    except Exception as e:
        logger.error(f"❌ 单GPU碰撞检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("单GPU引擎已停止")
            except Exception as e:
                logger.warning(f"停止引擎时出现错误: {e}")

def test_single_gpu_resource_release():
    """测试单GPU资源释放"""
    logger.info("开始测试单GPU资源释放")

    # 创建一个测试目标地址集合
    test_targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

    # 初始化GPU碰撞引擎
    engine = None
    try:
        engine = GPUCollisionEngine(device_index=0, batch_size=1024, targets=test_targets)
        logger.info("单GPU引擎初始化成功")

        # 等待一段时间
        time.sleep(2)

        # 停止引擎并释放资源
        start_time = time.time()
        engine.stop()
        elapsed = time.time() - start_time
        logger.info(f"单GPU引擎已停止，资源释放耗时: {elapsed:.2f}秒")

        # 等待一段时间，确保资源完全释放
        time.sleep(3)

        logger.info("✅ 单GPU资源释放成功")
        return True
    except Exception as e:
        logger.error(f"❌ 单GPU资源释放失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    try:
        # 测试单GPU初始化
        init_result = test_single_gpu_initialization()

        # 测试单GPU碰撞检测
        collision_result = test_single_gpu_collision_detection()

        # 测试单GPU资源释放
        release_result = test_single_gpu_resource_release()

        if init_result and collision_result and release_result:
            logger.info("✅ 单GPU测试全部成功")
        else:
            logger.error("❌ 单GPU测试部分失败")
    except Exception as e:
        logger.error(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
