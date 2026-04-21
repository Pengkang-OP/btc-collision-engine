#!/usr/bin/env python3
"""直接启动GPU碰撞引擎(异步优化版)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.collision.gpu_collision_engine import GPUCollisionEngine
import time
import threading


def main():
    print("="*80)
    print("  GPU碰撞引擎 - 异步优化版本")
    print("="*80)
    print()
    
    # 创建引擎
    print("创建GPU碰撞引擎...")
    engine = GPUCollisionEngine(
        targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
        batch_size=1000000,  # 100万
        use_gpu_memory_pool=True,
        device_index=1  # Intel Arc A770
    )
    
    # 启用异步执行
    if hasattr(engine, '_gpu_device'):
        print("配置GPU异步执行...")
        engine._gpu_device.enable_async_execution = True
        
        # 重新初始化GPUDevice(启用异步)
        print("重新初始化GPU设备(启用双队列)...")
        engine._gpu_device.cleanup()
        engine._gpu_device.initialize(device_index=1, enable_async=True)
    
    # 检查异步状态
    if hasattr(engine, '_gpu_device'):
        if engine._gpu_device.enable_async_execution:
            print("✅ GPU异步执行已启用")
            print(f"  - 计算队列: {engine._gpu_device.compute_queue is not None}")
            print(f"  - 传输队列: {engine._gpu_device.transfer_queue is not None}")
            
            # 手动初始化异步执行器
            if not hasattr(engine, '_async_executor') or engine._async_executor is None:
                print("初始化异步执行器...")
                from src.gpu.async_executor import AsyncGPUExecutor
                engine._async_executor = AsyncGPUExecutor(
                    engine._gpu_device,
                    max_batch_size=engine.batch_size
                )
                engine._async_executor.initialize_buffers(
                    engine._gpu_device.context,
                    num_keys=engine.batch_size
                )
                print("✅ 异步执行器已初始化")
            
            print(f"  - 异步执行器: {engine._async_executor is not None}")
        else:
            print("❌ GPU异步执行未启用")
    
    print()
    print("启动引擎...")
    print()
    
    # 启动引擎
    def run_engine():
        engine.start()
    
    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()
    
    # 监控30秒
    print("监控运行状态(30秒)...")
    print("-" * 80)
    
    try:
        for i in range(6):
            time.sleep(5)
            monitor = engine.gpu_performance_monitor
            report = monitor.get_performance_report()
            
            print(f'  [{(i+1)*5}s] 吞吐量: {report.avg_throughput_keys_per_sec:>10,.0f} keys/s | '
                  f'错误率: {report.error_rate_percent:>6.2f}% | '
                  f'批次: {report.total_batches}')
    
    except KeyboardInterrupt:
        pass
    
    # 停止引擎
    print()
    print("停止引擎...")
    engine.stop()
    thread.join(timeout=5)
    
    print()
    print("="*80)
    print("  测试完成")
    print("="*80)


if __name__ == "__main__":
    main()
