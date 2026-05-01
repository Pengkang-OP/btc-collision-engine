#!/usr/bin/env python3
"""
多GPU测试脚本

此脚本用于测试多GPU的功能，包括初始化、碰撞检测和资源释放等。
"""

import time
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402

pytestmark = pytest.mark.gpu  # 需要真实GPU硬件

from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine  # noqa: E402
from src.utils import init_logging, get_configured_logger  # noqa: E402

# 配置日志
init_logging()
logger = get_configured_logger("MultiGPUTest")


def test_multi_gpu_initialization():
    """测试多GPU初始化"""
    logger.info("开始测试多GPU初始化")

    # 初始化多GPU碰撞引擎
    engine = None
    try:
        engine = MultiGPUCollisionEngine()
        logger.info("多GPU引擎创建成功")

        # 初始化设备
        init_result = engine.initialize(device_count=2)
        if not init_result:
            logger.error("❌ 多GPU设备初始化失败")
            return False

        logger.info("✅ 多GPU初始化成功")

        # 获取设备信息
        devices = engine.get_devices()
        logger.info(f"设备信息: {devices}")

        # 获取设备数量
        device_count = len(devices)
        logger.info(f"设备数量: {device_count}")

        return True
    except Exception as e:
        logger.error(f"❌ 多GPU初始化失败: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("多GPU引擎已停止")
            except Exception as e:
                logger.warning(f"停止引擎时出现错误: {e}")


def test_multi_gpu_collision_detection():
    """测试多GPU碰撞检测"""
    logger.info("开始测试多GPU碰撞检测")

    # 创建一个测试目标地址集合
    test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    # 初始化多GPU碰撞引擎
    engine = None
    try:
        engine = MultiGPUCollisionEngine()
        logger.info("多GPU引擎创建成功")

        # 初始化设备
        init_result = engine.initialize(device_count=2)
        if not init_result:
            logger.error("❌ 多GPU设备初始化失败")
            return False

        logger.info("多GPU引擎初始化成功")

        # 运行碰撞检测任务
        logger.info("运行碰撞检测任务...")

        # 启动碰撞检测
        start_time = time.time()
        start_result = engine.start(targets=test_targets, mode="random", total_keys=100000)
        if not start_result:
            logger.error("❌ 多GPU碰撞检测启动失败")
            return False

        # 运行一段时间
        time.sleep(5)

        # 停止碰撞检测
        engine.stop()

        elapsed = time.time() - start_time
        logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")

        # 获取统计信息
        stats = engine.get_combined_stats()
        logger.info(f"碰撞检测统计: {stats}")

        return True
    except Exception as e:
        logger.error(f"❌ 多GPU碰撞检测失败: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("多GPU引擎已停止")
            except Exception as e:
                logger.warning(f"停止引擎时出现错误: {e}")


def test_multi_gpu_resource_release():
    """测试多GPU资源释放"""
    logger.info("开始测试多GPU资源释放")

    # 创建一个测试目标地址集合
    test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    # 初始化多GPU碰撞引擎
    engine = None
    try:
        engine = MultiGPUCollisionEngine()
        logger.info("多GPU引擎创建成功")

        # 初始化设备
        init_result = engine.initialize(device_count=2)
        if not init_result:
            logger.error("❌ 多GPU设备初始化失败")
            return False

        logger.info("多GPU引擎初始化成功")

        # 启动碰撞检测
        start_result = engine.start(targets=test_targets, mode="random", total_keys=100000)
        if not start_result:
            logger.error("❌ 多GPU碰撞检测启动失败")
            return False

        # 运行一段时间
        time.sleep(2)

        # 停止引擎并释放资源
        start_time = time.time()
        engine.stop()
        elapsed = time.time() - start_time
        logger.info(f"多GPU引擎已停止，资源释放耗时: {elapsed:.2f}秒")

        # 等待一段时间，确保资源完全释放
        time.sleep(3)

        # 清理资源
        engine.cleanup()
        logger.info("多GPU引擎资源已清理")

        logger.info("✅ 多GPU资源释放成功")
        return True
    except Exception as e:
        logger.error(f"❌ 多GPU资源释放失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        # 测试多GPU初始化
        init_result = test_multi_gpu_initialization()

        # 测试多GPU碰撞检测
        collision_result = test_multi_gpu_collision_detection()

        # 测试多GPU资源释放
        release_result = test_multi_gpu_resource_release()

        if init_result and collision_result and release_result:
            logger.info("✅ 多GPU测试全部成功")
        else:
            logger.error("❌ 多GPU测试部分失败")
    except Exception as e:
        logger.error(f"❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
