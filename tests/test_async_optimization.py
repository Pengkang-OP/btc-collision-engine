#!/usr/bin/env python3
"""测试GPU异步优化效果"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.gpu.device import GPUDeviceDetector


def main():
    print('='*80)
    print('  GPU异步优化效果测试')
    print('='*80)
    print()

    # 1. 检测GPU
    print('步骤1: 检测GPU设备')
    print('-'*80)
    devices = GPUDeviceDetector.detect_devices()
    print(f'检测到 {len(devices)} 个GPU设备:')
    for i, dev in enumerate(devices):
        name = dev.get('name', 'Unknown')
        mem_gb = dev.get('global_mem_size', 0) / (1024**3)
        print(f'  GPU {i}: {name} ({mem_gb:.1f}GB)')
    print()

    # 2. 创建引擎(启用异步)
    print('步骤2: 创建GPU碰撞引擎(异步模式)')
    print('-'*80)
    
    engine = GPUCollisionEngine(
        targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
        batch_size=1000000,  # 100万
        use_gpu_memory_pool=True,
        device_index=1  # Intel Arc A770
    )
    
    # 检查是否启用异步
    if hasattr(engine, '_gpu_device') and engine._gpu_device.enable_async_execution:
        print('[PASS] GPU异步执行已启用')
        print(f'  - 计算队列: {engine._gpu_device.compute_queue is not None}')
        print(f'  - 传输队列: {engine._gpu_device.transfer_queue is not None}')
        print(f'  - 异步执行器: {engine._async_executor is not None}')
    else:
        print('[WARN] GPU异步执行未启用')
    
    device_info = engine.get_device_info()
    if device_info.get('name') == 'Unknown' and hasattr(engine, '_gpu_device'):
        device_info = engine._gpu_device.device_info
    
    gpu_name = device_info.get('name', 'Unknown')
    print(f'使用GPU: {gpu_name}')
    print()

    # 3. 运行测试
    print('步骤3: 运行测试(20秒)')
    print('-'*80)

    def run_engine():
        engine.start()

    thread = threading.Thread(target=run_engine, daemon=True)
    thread.start()

    # 监控性能
    throughputs = []
    for i in range(4):
        time.sleep(5)
        monitor = engine.gpu_performance_monitor
        report = monitor.get_performance_report()
        
        throughput = report.avg_throughput_keys_per_sec
        throughputs.append(throughput)
        
        print(f'  [{(i+1)*5}s] 吞吐量: {throughput:>10,.0f} keys/s | '
              f'错误率: {report.error_rate_percent:>6.2f}% | '
              f'批次: {report.total_batches}')

    # 停止引擎
    print()
    print('步骤4: 停止引擎')
    print('-'*80)
    engine.stop()
    thread.join(timeout=5)

    if thread.is_alive():
        print('[WARN] 引擎线程未正常停止')
    else:
        print('[PASS] 引擎正常停止')

    print()
    print('='*80)
    print('  测试结果')
    print('='*80)
    print()

    avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0
    print(f'平均吞吐量: {avg_throughput:,.0f} keys/s')
    print(f'各次测量: {[f"{t:,.0f}" for t in throughputs]}')
    print()

    # 对比
    print('性能对比:')
    print(f'  优化前(同步): ~44,000 keys/s')
    print(f'  优化后(异步): {avg_throughput:,.0f} keys/s')
    
    if avg_throughput > 44000:
        improvement = ((avg_throughput - 44000) / 44000) * 100
        print(f'  性能提升: +{improvement:.1f}%')
        print()
        print('[PASS] 异步优化成功! 性能显著提升!')
    else:
        print(f'  性能提升: 未达预期')
        print()
        print('[WARN] 异步优化效果不明显')
    
    # 异步执行统计
    if hasattr(engine, '_async_executor') and engine._async_executor:
        stats = engine._async_executor.get_stats()
        print()
        print('异步执行统计:')
        print(f'  异步执行次数: {stats["async_executions"]}')
        print(f'  同步回退次数: {stats["sync_fallbacks"]}')
        print(f'  异步执行率: {stats["async_rate_percent"]:.1f}%')

    print()


if __name__ == "__main__":
    main()
