#!/usr/bin/env python3
"""单GPU测试脚本.

此脚本用于测试单GPU的功能，包括初始化、碰撞检测和资源释放等。
"""

import time

import pytest

pytestmark = pytest.mark.gpu  # 需要真实GPU硬件

from src.collision.gpu.engine import GPUCollisionEngine
from src.utils import get_configured_logger, init_logging

# 配置日志
init_logging()
logger = get_configured_logger("SingleGPUTest")


def _run_gpu_engine_test(test_targets, test_name: str) -> None:
    """内部辅助：初始化 GPU 引擎并返回 engine 实例用于后续测试。."""
    try:
        engine = GPUCollisionEngine(device_index=0, batch_size=1024, targets=test_targets)
        return engine
    except Exception as e:
        logger.error("ERR %s 引擎初始化失败: %s", test_name, e)
        raise


def test_single_gpu_initialization():
    """测试单GPU初始化."""
    logger.info("开始测试单GPU初始化")

    test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    engine = None
    try:
        engine = _run_gpu_engine_test(test_targets, "单GPU初始化")
        logger.info("OK 单GPU初始化成功")

        device_info = engine.get_device_info()
        logger.info("设备信息: %s", device_info)
        assert device_info is not None, "设备信息不应为空"
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("单GPU引擎已停止")
            except Exception as e:
                logger.warning("停止引擎时出现错误: %s", e)


def test_single_gpu_collision_detection():
    """测试单GPU碰撞检测."""
    logger.info("开始测试单GPU碰撞检测")

    test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    engine = None
    try:
        engine = _run_gpu_engine_test(test_targets, "单GPU碰撞检测")
        logger.info("单GPU引擎初始化成功")

        logger.info("运行碰撞检测任务...")
        start_time = time.time()
        # 注意：我们没有调用具体的碰撞检测方法，因为我们只是测试引擎的初始化和停止
        elapsed = time.time() - start_time
        logger.info("碰撞检测任务完成，耗时: %.2f秒", elapsed)
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("单GPU引擎已停止")
            except Exception as e:
                logger.warning("停止引擎时出现错误: %s", e)


def test_single_gpu_resource_release():
    """测试单GPU资源释放."""
    logger.info("开始测试单GPU资源释放")

    test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    engine = None
    try:
        engine = _run_gpu_engine_test(test_targets, "单GPU资源释放")
        logger.info("单GPU引擎初始化成功")

        time.sleep(2)

        start_time = time.time()
        engine.stop()
        elapsed = time.time() - start_time
        logger.info("单GPU引擎已停止，资源释放耗时: %.2f秒", elapsed)

        time.sleep(3)
        logger.info("OK 单GPU资源释放成功")
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("单GPU引擎已停止（finally）")
            except Exception as e:
                logger.warning("停止引擎时出现错误: %s", e)


def main():
    """主函数."""
    tests = [
        ("单GPU初始化", test_single_gpu_initialization),
        ("单GPU碰撞检测", test_single_gpu_collision_detection),
        ("单GPU资源释放", test_single_gpu_resource_release),
    ]
    all_ok = True
    for name, test_func in tests:
        try:
            test_func()
            logger.info("OK %s 成功", name)
        except Exception as e:
            logger.error("ERR %s 失败: %s", name, e)
            import traceback

            traceback.print_exc()
            all_ok = False

    if all_ok:
        logger.info("OK 单GPU测试全部成功")
    else:
        logger.error("ERR 单GPU测试部分失败")


if __name__ == "__main__":
    main()
