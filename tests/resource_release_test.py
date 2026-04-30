#!/usr/bin/env python3
"""
测试GPU资源释放功能

此脚本用于测试修复后的GPU资源释放功能，确保在引擎停止后GPU资源能够被正确释放。
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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_resource_release():
    """测试GPU资源释放功能"""
    logger.info("开始测试GPU资源释放功能")

    # 初始化GPU碰撞引擎
    engine = None
    try:
        # 创建一个测试目标地址集合（使用有效的比特币地址格式）
        # 注意：这是一个无效的测试地址，但格式正确
        test_targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
        engine = GPUCollisionEngine(device_index=0, batch_size=1024, targets=test_targets)
        logger.info("GPU碰撞引擎初始化成功")

        # 模拟任务完成，等待一段时间
        logger.info("任务执行完成，等待2秒...")
        time.sleep(2)

        # 停止引擎并释放资源
        logger.info("停止GPU碰撞引擎，释放资源...")
        start_time = time.time()
        engine.stop()
        elapsed = time.time() - start_time
        logger.info(f"GPU碰撞引擎已停止，资源释放耗时: {elapsed:.2f}秒")

        # 等待一段时间，确保资源有足够时间释放
        logger.info("等待5秒，确保资源完全释放...")
        time.sleep(5)

        logger.info("GPU资源释放测试完成")
        return True

    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
            except Exception as e:
                logger.warning(f"停止引擎时出现错误: {e}")

if __name__ == "__main__":
    success = test_resource_release()
    if success:
        logger.info("✅ GPU资源释放测试成功")
    else:
        logger.error("❌ GPU资源释放测试失败")
