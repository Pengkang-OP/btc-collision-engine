#!/usr/bin/env python3
"""
内存泄漏检测脚本

此脚本用于检测系统中的内存泄漏问题，包括GPU资源泄漏、内存池泄漏等。
"""

import os
import time

import psutil

from src.collision.gpu.engine import GPUCollisionEngine
from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine
from src.utils import get_configured_logger, init_logging

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


def _log_memory_usage(label, memory):
    """统一日志输出内存使用情况"""
    logger.info(
        f"{label}内存使用: RSS={memory['rss']:.2f}MB, "
        f"VMS={memory['vms']:.2f}MB, "
        f"使用率={memory['percent']:.2f}%"
    )


def _log_memory_change(current_mem, initial_mem, loop_idx=None):
    """输出内存变化"""
    rss_diff = current_mem["rss"] - initial_mem["rss"]
    vms_diff = current_mem["vms"] - initial_mem["vms"]
    prefix = f"循环 {loop_idx + 1} " if loop_idx is not None else "总"
    _log_memory_usage(prefix, current_mem)
    logger.info(f"  内存变化: RSS={rss_diff:.2f}MB, VMS={vms_diff:.2f}MB")


def test_gpu_collision_engine_memory_leak():
    """
    测试GPU碰撞引擎的内存泄漏
    """
    logger.info("开始测试GPU碰撞引擎的内存泄漏...")

    test_targets = {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk",
    }

    initial_memory = get_memory_usage()
    _log_memory_usage("初始", initial_memory)

    for i in range(5):
        logger.info(f"测试循环 {i + 1}/5")

        engine = None
        try:
            engine = GPUCollisionEngine(
                device_index=0, batch_size=65536, targets=test_targets
            )
            logger.info("GPU碰撞引擎初始化成功")

            engine.start(mode="random")
            start_time = time.time()
            time.sleep(5)
            elapsed = time.time() - start_time
            logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")

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

        current_memory = get_memory_usage()
        _log_memory_change(current_memory, initial_memory, loop_idx=i)

        time.sleep(2)

    final_memory = get_memory_usage()
    _log_memory_usage("最终", final_memory)

    total_rss_diff = final_memory["rss"] - initial_memory["rss"]
    total_vms_diff = final_memory["vms"] - initial_memory["vms"]
    logger.info(f"总内存变化: RSS={total_rss_diff:.2f}MB, VMS={total_vms_diff:.2f}MB")

    if total_rss_diff > 100:
        logger.error("检测到内存泄漏: RSS增加超过100MB")
        return False
    else:
        logger.info("未检测到明显的内存泄漏")
        return True


def test_multi_gpu_engine_memory_leak():
    """
    测试多GPU引擎的内存泄漏
    """
    logger.info("开始测试多GPU引擎的内存泄漏...")

    test_targets = {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk",
    }

    initial_memory = get_memory_usage()
    _log_memory_usage("初始", initial_memory)

    for i in range(3):
        logger.info(f"测试循环 {i + 1}/3")

        engine = None
        try:
            engine = MultiGPUCollisionEngine()
            logger.info("多GPU引擎创建成功")

            init_result = engine.initialize(device_count=2)
            if not init_result:
                logger.error("多GPU设备初始化失败")
                continue

            logger.info("多GPU引擎初始化成功")

            start_time = time.time()

            start_result = engine.start(
                targets=test_targets, mode="random", total_keys=10000000
            )
            if not start_result:
                logger.error("多GPU碰撞检测启动失败")
                continue

            time.sleep(5)
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

        current_memory = get_memory_usage()
        _log_memory_change(current_memory, initial_memory, loop_idx=i)

        time.sleep(2)

    final_memory = get_memory_usage()
    _log_memory_usage("最终", final_memory)

    total_rss_diff = final_memory["rss"] - initial_memory["rss"]
    total_vms_diff = final_memory["vms"] - initial_memory["vms"]
    logger.info(f"总内存变化: RSS={total_rss_diff:.2f}MB, VMS={total_vms_diff:.2f}MB")

    if total_rss_diff > 150:
        logger.error("检测到内存泄漏: RSS增加超过150MB")
        return False
    else:
        logger.info("未检测到明显的内存泄漏")
        return True


def main():
    """主函数"""
    try:
        logger.info("开始内存泄漏检测...")

        gpu_result = test_gpu_collision_engine_memory_leak()
        multi_gpu_result = test_multi_gpu_engine_memory_leak()

        if gpu_result and multi_gpu_result:
            logger.info("内存泄漏检测全部通过")
        else:
            logger.error("内存泄漏检测部分失败")
    except Exception as e:
        logger.error(f"检测过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
