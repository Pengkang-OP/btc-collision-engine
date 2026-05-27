#!/usr/bin/env python3
"""测试异步配置自动读取逻辑"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.collision.gpu_collision_engine import GPUCollisionEngine


def test_config_priority():
    """测试配置优先级"""
    
    print("=" * 80)
    print("  测试异步配置自动读取逻辑")
    print("=" * 80)
    print()
    
    # 测试1: 无配置(默认)
    print("【测试1】无配置(默认)")
    print("-" * 80)
    try:
        engine1 = GPUCollisionEngine(
            targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
            batch_size=100000,
            device_index=1
        )
        if hasattr(engine1, '_gpu_device'):
            print(f"  异步执行: {'✅ 已启用' if engine1._gpu_device.enable_async_execution else '❌ 未启用'}")
            print(f"  计算队列: {'✅' if hasattr(engine1._gpu_device, 'compute_queue') and engine1._gpu_device.compute_queue else '❌'}")
        engine1.stop()
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    
    print()
    
    # 测试2: 传入配置(启用异步)
    print("【测试2】传入config参数(async_execution=true)")
    print("-" * 80)
    try:
        engine2 = GPUCollisionEngine(
            targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
            batch_size=100000,
            device_index=1
        )
        # 手动设置config模拟GUI行为
        engine2.config = {
            'gpu': {
                'async_execution': True
            }
        }
        # 重新初始化
        if hasattr(engine2, '_gpu_device'):
            engine2._gpu_device.cleanup()
            engine2._gpu_device.initialize(1, enable_async=True)
        
        print(f"  异步执行: {'✅ 已启用' if engine2._gpu_device.enable_async_execution else '❌ 未启用'}")
        print(f"  计算队列: {'✅' if hasattr(engine2._gpu_device, 'compute_queue') and engine2._gpu_device.compute_queue else '❌'}")
        print(f"  传输队列: {'✅' if hasattr(engine2._gpu_device, 'transfer_queue') and engine2._gpu_device.transfer_queue else '❌'}")
        engine2.stop()
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    
    print()
    
    # 测试3: 传入配置(禁用异步)
    print("【测试3】传入config参数(async_execution=false)")
    print("-" * 80)
    try:
        engine3 = GPUCollisionEngine(
            targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
            batch_size=100000,
            device_index=1
        )
        engine3.config = {
            'gpu': {
                'async_execution': False  # 明确禁用
            }
        }
        if hasattr(engine3, '_gpu_device'):
            print(f"  异步执行: {'✅ 已启用' if engine3._gpu_device.enable_async_execution else '❌ 未启用'}")
            print(f"  应使用同步模式")
        engine3.stop()
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    
    print()
    print("=" * 80)
    print("  测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_config_priority()
