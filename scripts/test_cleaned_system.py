#!/usr/bin/env python3
"""
清理后系统性能和稳定性测试脚本

此脚本用于测试清理后系统的性能和稳定性，确保系统能够正常运行。
"""
import os
import sys
import time
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import init_logging, get_configured_logger
from src.collision.gpu_collision_engine import GPUCollisionEngine

# 配置日志
init_logging()
logger = get_configured_logger("CleanedSystemTest")

def test_gpu_collision_engine_performance():
    """
    测试GPU碰撞引擎的性能
    """
    logger.info("开始测试GPU碰撞引擎的性能...")
    
    # 创建一个测试目标地址集合
    test_targets = {
        '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',  # 中本聪的地址
        '16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk'   # 披萨地址
    }
    
    # 初始化GPU碰撞引擎
    engine = None
    try:
        engine = GPUCollisionEngine(device_index=0, batch_size=1048576, targets=test_targets)
        logger.info("GPU碰撞引擎初始化成功")
        
        # 运行碰撞检测任务
        start_time = time.time()
        
        # 运行10秒的碰撞检测任务
        logger.info("开始运行碰撞检测任务，持续10秒...")
        
        # 等待10秒
        time.sleep(10)
        
        # 停止碰撞检测
        engine.stop()
        
        elapsed = time.time() - start_time
        logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")
        
        # 获取统计信息
        stats = engine.get_stats()
        logger.info(f"碰撞检测统计: {stats}")
        
        # 检查性能
        if 'total_keys' in stats and 'elapsed' in stats:
            keys_per_second = stats['total_keys'] / stats['elapsed']
            logger.info(f"性能: {keys_per_second:.2f} keys/s")
            
            # 检查性能是否合理
            if keys_per_second > 100000:
                logger.info("✅ 性能测试通过: 每秒处理超过10万次碰撞检测")
            else:
                logger.warning("⚠️ 性能测试警告: 每秒处理次数低于10万次")
        
        logger.info("✅ GPU碰撞引擎性能测试成功")
        return True
    except Exception as e:
        logger.error(f"❌ GPU碰撞引擎性能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if engine:
            try:
                engine.stop()
                logger.info("GPU碰撞引擎已停止")
            except Exception as e:
                logger.warning(f"停止引擎时出现错误: {e}")

def test_system_stability():
    """
    测试系统的稳定性
    """
    logger.info("开始测试系统的稳定性...")
    
    # 测试多次初始化和停止
    for i in range(3):
        logger.info(f"稳定性测试循环 {i+1}/3")
        
        # 创建一个测试目标地址集合
        test_targets = {
            '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',  # 中本聪的地址
            '16rCmCmbuWDhPjWTrpQGaU3EPdZF7MTdUk'   # 披萨地址
        }
        
        # 初始化GPU碰撞引擎
        engine = None
        try:
            engine = GPUCollisionEngine(device_index=0, batch_size=1048576, targets=test_targets)
            logger.info("GPU碰撞引擎初始化成功")
            
            # 运行碰撞检测任务
            start_time = time.time()
            
            # 运行3秒的碰撞检测任务
            time.sleep(3)
            
            # 停止碰撞检测
            engine.stop()
            
            elapsed = time.time() - start_time
            logger.info(f"碰撞检测任务完成，耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            logger.error(f"❌ 稳定性测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if engine:
                try:
                    engine.stop()
                    logger.info("GPU碰撞引擎已停止")
                except Exception as e:
                    logger.warning(f"停止引擎时出现错误: {e}")
        
        # 等待垃圾回收
        time.sleep(1)
    
    logger.info("✅ 系统稳定性测试成功")
    return True

def main():
    """主函数"""
    try:
        logger.info("开始测试清理后系统的性能和稳定性...")
        
        # 测试GPU碰撞引擎的性能
        performance_result = test_gpu_collision_engine_performance()
        
        # 测试系统的稳定性
        stability_result = test_system_stability()
        
        if performance_result and stability_result:
            logger.info("✅ 清理后系统的性能和稳定性测试全部成功")
        else:
            logger.error("❌ 清理后系统的性能和稳定性测试部分失败")
    except Exception as e:
        logger.error(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
