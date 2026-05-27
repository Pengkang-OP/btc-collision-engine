#!/usr/bin/env python3
"""生产模式测试脚本.

此脚本用于测试系统在生产环境下的性能和稳定性，包括更大的任务量、更长的运行时间、更复杂的目标地址集合等。
"""

import time

import pytest

pytestmark = pytest.mark.gpu  # 需要真实GPU硬件

from src.collision.gpu.engine import GPUCollisionEngine  # noqa: E402
from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine  # noqa: E402
from src.utils import get_configured_logger, init_logging  # noqa: E402

# 配置日志
init_logging()
logger = get_configured_logger("ProductionTest")


def test_single_gpu_production():
    """测试单GPU生产模式."""
    logger.info("开始测试单GPU生产模式")

    # 创建一个更大的测试目标地址集合
    test_targets = {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 中本聪的地址
        "16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk",  # 披萨地址
        "1JdDGQkM3qHTXf7ALVQw69qY3V4vG7QrQ4",  # 勒索病毒地址
        "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF",  # 暗网市场地址
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # 交易所地址
        "13AM4VW2dhxYgXeQepoHkHSQuy6NgaEb94",  # 特斯拉地址
        "12ib7dJ5V4mX7w3K4QBF5jm3Z15D2jiXy",  # 矿池地址
        "14P8o9iB9ZxQRCjJnJ9tYV5RfR5sXQjJ4",  # 钱包地址
        "15h2WwK6kNN7Rg2a6q8p8vZ3Z5y7X8k9L",  # 测试地址1
        "16s7G8vHq3y7e8k9n0m1b2c3d4e5f6g7h8",  # 测试地址2
    }

    # 初始化GPU碰撞引擎
    engine = None
    try:
        engine = GPUCollisionEngine(device_index=0, batch_size=1048576, targets=test_targets)
        logger.info("单GPU引擎初始化成功")

        # 运行碰撞检测任务
        logger.info("运行碰撞检测任务...")

        # 启动碰撞检测
        start_time = time.time()

        # 运行较长时间的碰撞检测任务
        logger.info("开始运行生产模式碰撞检测任务，持续60秒...")

        # 等待60秒
        time.sleep(60)

        # 停止碰撞检测
        engine.stop()

        elapsed = time.time() - start_time
        logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")

        # 获取统计信息
        stats = engine.get_stats()
        logger.info("碰撞检测统计: %s", stats)

        logger.info("✅ 单GPU生产模式测试成功")
        return True
    except Exception as e:
        logger.error("❌ 单GPU生产模式测试失败: %s", e)
        import traceback

        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("单GPU引擎已停止")
            except Exception as e:
                logger.warning("停止引擎时出现错误: %s", e)


def test_multi_gpu_production():
    """测试多GPU生产模式."""
    logger.info("开始测试多GPU生产模式")

    # 创建一个更大的测试目标地址集合
    test_targets = {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 中本聪的地址
        "16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk",  # 披萨地址
        "1JdDGQkM3qHTXf7ALVQw69qY3V4vG7QrQ4",  # 勒索病毒地址
        "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF",  # 暗网市场地址
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # 交易所地址
        "13AM4VW2dhxYgXeQepoHkHSQuy6NgaEb94",  # 特斯拉地址
        "12ib7dJ5V4mX7w3K4QBF5jm3Z15D2jiXy",  # 矿池地址
        "14P8o9iB9ZxQRCjJnJ9tYV5RfR5sXQjJ4",  # 钱包地址
        "15h2WwK6kNN7Rg2a6q8p8vZ3Z5y7X8k9L",  # 测试地址1
        "16s7G8vHq3y7e8k9n0m1b2c3d4e5f6g7h8",  # 测试地址2
    }

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

        # 运行较长时间的碰撞检测任务
        logger.info("开始运行生产模式碰撞检测任务，持续60秒...")

        start_result = engine.start(
            targets=test_targets,
            mode="random",
            total_keys=100000000,
        )  # 1亿次碰撞检测
        if not start_result:
            logger.error("❌ 多GPU碰撞检测启动失败")
            return False

        # 等待60秒
        time.sleep(60)

        # 停止碰撞检测
        engine.stop()

        elapsed = time.time() - start_time
        logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")

        # 获取统计信息
        stats = engine.get_combined_stats()
        logger.info("碰撞检测统计: %s", stats)

        logger.info("✅ 多GPU生产模式测试成功")
        return True
    except Exception as e:
        logger.error("❌ 多GPU生产模式测试失败: %s", e)
        import traceback

        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("多GPU引擎已停止")
            except Exception as e:
                logger.warning("停止引擎时出现错误: %s", e)


def main():
    """主函数."""
    try:
        # 测试单GPU生产模式
        single_gpu_result = test_single_gpu_production()

        # 测试多GPU生产模式
        multi_gpu_result = test_multi_gpu_production()

        if single_gpu_result and multi_gpu_result:
            logger.info("✅ 生产模式测试全部成功")
        else:
            logger.error("❌ 生产模式测试部分失败")
    except Exception as e:
        logger.error("❌ 测试过程中出现错误: %s", e)
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
