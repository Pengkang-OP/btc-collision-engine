#!/usr/bin/env python3
"""
内存泄漏检测脚本

此脚本用于检测系统中的内存泄漏问题，包括GPU资源泄漏、内存池泄漏等。
"""

import os
import sys
import time

import psutil

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.collision.gpu.engine import GPUCollisionEngine  # noqa: E402
from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine  # noqa: E402
from src.utils import get_configured_logger, init_logging  # noqa: E402

# 配置日志
init_logging()
logger = get_configured_logger("MemoryLeakDetection")


def get_memory_usage():
    """
    获取当前内存使用情况

    Returns:
        内存使用情况字典
    """
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return {
        "rss": memory_info.rss / 1024 / 1024,  # MB
        "vms": memory_info.vms / 1024 / 1024,  # MB
        "percent": process.memory_percent(),
    }


def test_gpu_collision_engine_memory_leak():
    """
    测试GPU碰撞引擎的内存泄漏
    """
    logger.info("开始测试GPU碰撞引擎的内存泄漏...")

    # 创建一个测试目标地址集合
    test_targets = {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 中本聪的地址
        "16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk",  # 披萨地址
    }

    # 初始内存使用情况
    initial_memory = get_memory_usage()
    logger.info(
        f"初始内存使用: RSS={initial_memory['rss']:.2f}MB, VMS={initial_memory['vms']:.2f}MB, 使用率={
            initial_memory['percent']:.2f}%"
    )

    # 测试循环
    for i in range(5):
        logger.info(f"测试循环 {i + 1}/5")

        # 初始化GPU碰撞引擎
        engine = None
        try:
            engine = GPUCollisionEngine(device_index=0, batch_size=65536, targets=test_targets)
            logger.info("GPU碰撞引擎初始化成功")

            # 运行碰撞检测任务
            engine.start(mode="random")
            start_time = time.time()
            time.sleep(5)  # 运行5秒
            elapsed = time.time() - start_time
            logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")

            # 停止碰撞检测
            engine.stop()
            logger.info("GPU碰撞引擎停止成功")

        except Exception as e:
            logger.error(f"测试过程中出现错误: {e}")
            import traceback

            traceback.print_exc()
        finally:
            if engine:
                try:
                    engine.stop()
                    logger.info("GPU碰撞引擎已停止")
                except Exception as e:
                    logger.warning(f"停止引擎时出现错误: {e}")

        # 检查内存使用情况
        current_memory = get_memory_usage()
        logger.info(
            f"循环 {i + 1} 内存使用: RSS={current_memory['rss']:.2f}MB, VMS={
                current_memory['vms']:.2f}MB, 使用率={current_memory['percent']:.2f}%"
        )

        # 计算内存变化
        rss_diff = current_memory["rss"] - initial_memory["rss"]
        vms_diff = current_memory["vms"] - initial_memory["vms"]
        logger.info(f"内存变化: RSS={rss_diff:.2f}MB, VMS={vms_diff:.2f}MB")

        # 等待垃圾回收
        time.sleep(2)

    # 最终内存使用情况
    final_memory = get_memory_usage()
    logger.info(
        f"最终内存使用: RSS={final_memory['rss']:.2f}MB, VMS={final_memory['vms']:.2f}MB, 使用率={
            final_memory['percent']:.2f}%"
    )

    # 计算总内存变化
    total_rss_diff = final_memory["rss"] - initial_memory["rss"]
    total_vms_diff = final_memory["vms"] - initial_memory["vms"]
    logger.info(f"总内存变化: RSS={total_rss_diff:.2f}MB, VMS={total_vms_diff:.2f}MB")

    # 判断是否存在内存泄漏
    if total_rss_diff > 100:  # 如果RSS增加超过100MB，认为存在内存泄漏
        logger.error("❌ 检测到内存泄漏: RSS增加超过100MB")
        return False
    else:
        logger.info("✅ 未检测到明显的内存泄漏")
        return True


def test_multi_gpu_engine_memory_leak():
    """
    测试多GPU引擎的内存泄漏
    """
    logger.info("开始测试多GPU引擎的内存泄漏...")

    # 创建一个测试目标地址集合
    test_targets = {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 中本聪的地址
        "16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk",  # 披萨地址
    }

    # 初始内存使用情况
    initial_memory = get_memory_usage()
    logger.info(
        f"初始内存使用: RSS={initial_memory['rss']:.2f}MB, VMS={initial_memory['vms']:.2f}MB, 使用率={
            initial_memory['percent']:.2f}%"
    )

    # 测试循环
    for i in range(3):
        logger.info(f"测试循环 {i + 1}/3")

        # 初始化多GPU碰撞引擎
        engine = None
        try:
            engine = MultiGPUCollisionEngine()
            logger.info("多GPU引擎创建成功")

            # 初始化设备
            init_result = engine.initialize(device_count=2)
            if not init_result:
                logger.error("多GPU设备初始化失败")
                continue

            logger.info("多GPU引擎初始化成功")

            # 运行碰撞检测任务
            start_time = time.time()

            start_result = engine.start(
                targets=test_targets, mode="random", total_keys=10000000
            )  # 1000万次碰撞检测
            if not start_result:
                logger.error("多GPU碰撞检测启动失败")
                continue

            time.sleep(5)  # 运行5秒

            # 停止碰撞检测
            engine.stop()

            elapsed = time.time() - start_time
            logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")

        except Exception as e:
            logger.error(f"测试过程中出现错误: {e}")
            import traceback

            traceback.print_exc()
        finally:
            if engine:
                try:
                    engine.stop()
                    logger.info("多GPU引擎已停止")
                except Exception as e:
                    logger.warning(f"停止引擎时出现错误: {e}")

        # 检查内存使用情况
        current_memory = get_memory_usage()
        logger.info(
            f"循环 {i + 1} 内存使用: RSS={current_memory['rss']:.2f}MB, VMS={
                current_memory['vms']:.2f}MB, 使用率={current_memory['percent']:.2f}%"
        )

        # 计算内存变化
        rss_diff = current_memory["rss"] - initial_memory["rss"]
        vms_diff = current_memory["vms"] - initial_memory["vms"]
        logger.info(f"内存变化: RSS={rss_diff:.2f}MB, VMS={vms_diff:.2f}MB")

        # 等待垃圾回收
        time.sleep(2)

    # 最终内存使用情况
    final_memory = get_memory_usage()
    logger.info(
        f"最终内存使用: RSS={final_memory['rss']:.2f}MB, VMS={final_memory['vms']:.2f}MB, 使用率={
            final_memory['percent']:.2f}%"
    )

    # 计算总内存变化
    total_rss_diff = final_memory["rss"] - initial_memory["rss"]
    total_vms_diff = final_memory["vms"] - initial_memory["vms"]
    logger.info(f"总内存变化: RSS={total_rss_diff:.2f}MB, VMS={total_vms_diff:.2f}MB")

    # 判断是否存在内存泄漏
    if total_rss_diff > 150:  # 如果RSS增加超过150MB，认为存在内存泄漏
        logger.error("❌ 检测到内存泄漏: RSS增加超过150MB")
        return False
    else:
        logger.info("✅ 未检测到明显的内存泄漏")
        return True


def main():
    """主函数"""
    try:
        logger.info("开始内存泄漏检测...")

        # 测试GPU碰撞引擎的内存泄漏
        gpu_result = test_gpu_collision_engine_memory_leak()

        # 测试多GPU引擎的内存泄漏
        multi_gpu_result = test_multi_gpu_engine_memory_leak()

        if gpu_result and multi_gpu_result:
            logger.info("✅ 内存泄漏检测全部通过")
        else:
            logger.error("❌ 内存泄漏检测部分失败")
    except Exception as e:
        logger.error(f"❌ 检测过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
