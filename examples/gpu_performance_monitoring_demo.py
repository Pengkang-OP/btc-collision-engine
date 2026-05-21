"""
GPU性能监控使用示例

演示如何使用GPUPerformanceMonitor监控GPU碰撞引擎
"""

import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collision.gpu.engine import GPUCollisionEngine


def example_1_basic_gpu_monitoring():
    """示例1: 基本GPU监控"""
    print("="*80)
    print("示例1: 基本GPU监控")
    print("="*80)

    if not GPUCollisionEngine.is_gpu_available():
        print("❌ GPU不可用,跳过示例")
        return

    # 创建GPU引擎
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    engine = GPUCollisionEngine(
        targets=targets,
        batch_size=100000
    )

    # 获取GPU监控器(已自动启动)
    monitor = engine.gpu_performance_monitor

    if not monitor:
        print("❌ GPU监控器未初始化")
        return

    print(f"✅ GPU设备: {monitor._device_name}")
    print(f"✅ 厂商: {monitor._vendor}")
    print(f"✅ 显存: {monitor._total_memory_mb:.0f}MB")
    print()

    # 启动引擎(短时间运行)
    print("🚀 启动GPU引擎(运行5秒)...")
    engine.start(mode='random')

    # 等待5秒收集数据
    time.sleep(5)

    # 停止引擎
    engine.stop()

    # 获取性能报告
    report = monitor.get_performance_report()

    print("\n📊 GPU性能报告:")
    print(f"  设备: {report.device_name}")
    print(f"  厂商: {report.vendor}")
    print(f"  监控时长: {report.monitoring_duration_sec:.1f}秒")
    print(f"  总批次数: {report.total_batches}")
    print(f"  总处理密钥: {report.total_keys_processed:,}")
    print(f"  平均吞吐量: {report.avg_throughput_keys_per_sec:,.0f} keys/s")
    print(f"  峰值吞吐量: {report.peak_throughput_keys_per_sec:,.0f} keys/s")
    print(f"  平均执行时间: {report.avg_execution_time_ms:.1f}ms")
    print(f"  显存使用峰值: {report.memory_usage_peak_mb:.1f}MB")
    print(f"  错误率: {report.error_rate_percent:.2f}%")
    print(f"  性能稳定性: {report.performance_stability_percent:.1f}%")
    print()


def example_2_real_time_monitoring():
    """示例2: 实时监控GPU指标"""
    print("="*80)
    print("示例2: 实时监控GPU指标")
    print("="*80)

    if not GPUCollisionEngine.is_gpu_available():
        print("❌ GPU不可用,跳过示例")
        return

    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    engine = GPUCollisionEngine(
        targets=targets,
        batch_size=50000
    )

    monitor = engine.gpu_performance_monitor

    if not monitor:
        print("❌ GPU监控器未初始化")
        return

    # 注册性能退化回调
    def on_degradation(metrics, ratio):
        print(f"\n⚠️ 性能退化告警: 当前={metrics.keys_per_second:,.0f} keys/s, "
              f"退化率={ratio:.2%}")

    monitor.on_degradation(on_degradation)

    # 启动引擎
    print("🚀 启动GPU引擎(运行10秒,每2秒显示指标)...")
    engine.start(mode='random')

    # 实时监控
    for i in range(5):
        time.sleep(2)

        # 获取当前指标
        throughput = monitor.get_current_throughput()
        memory = monitor.get_memory_usage()

        print(f"\n[{i*2+2}s] GPU指标:")
        print(f"  当前吞吐量: {throughput:,.0f} keys/s")
        print(f"  显存使用: {memory['used_mb']:.1f}MB / {memory['total_mb']:.0f}MB "
              f"({memory['usage_percent']:.1f}%)")
        print(f"  内存池命中率: {memory['pool_hit_rate']:.1f}%")

    # 停止引擎
    engine.stop()

    # 导出指标数据
    print("\n📤 导出GPU指标数据(JSON格式,前1000字符):")
    json_data = monitor.export_metrics(format='json')
    print(json_data[:1000])
    print("...")
    print()


def example_3_memory_tracking():
    """示例3: 显存使用跟踪"""
    print("="*80)
    print("示例3: 显存使用跟踪")
    print("="*80)

    if not GPUCollisionEngine.is_gpu_available():
        print("❌ GPU不可用,跳过示例")
        return

    from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor

    # 创建独立监控器
    monitor = GPUPerformanceMonitor()
    monitor.start()

    # 模拟显存分配
    print("📊 模拟显存分配和释放...")

    # 分配128MB
    monitor.record_memory_metrics(
        used_memory_mb=128.0,
        total_memory_mb=8192.0,
        allocation=True,
        pool_hit=False
    )
    print(f"  分配128MB后: {monitor.get_memory_usage()}")

    # 再分配256MB
    monitor.record_memory_metrics(
        used_memory_mb=384.0,
        total_memory_mb=8192.0,
        allocation=True,
        pool_hit=True  # 命中内存池
    )
    print(f"  分配256MB后: {monitor.get_memory_usage()}")

    # 释放128MB
    monitor.record_memory_metrics(
        used_memory_mb=256.0,
        total_memory_mb=8192.0,
        allocation=False,
        pool_hit=False
    )
    print(f"  释放128MB后: {monitor.get_memory_usage()}")

    # 获取显存报告
    memory = monitor.get_memory_usage()
    print("\n📈 显存统计:")
    print(f"  当前使用: {memory['used_mb']:.1f}MB")
    print(f"  使用率: {memory['usage_percent']:.2f}%")
    print(f"  峰值使用: {memory['peak_mb']:.1f}MB")
    print(f"  内存池命中率: {memory['pool_hit_rate']:.1f}%")

    monitor.stop()
    print()


def example_4_comparison_cpu_vs_gpu():
    """示例4: CPU vs GPU性能对比"""
    print("="*80)
    print("示例4: CPU vs GPU性能对比")
    print("="*80)

    if not GPUCollisionEngine.is_gpu_available():
        print("❌ GPU不可用,跳过示例")
        return

    from src.collision.key_collision_engine import KeyCollisionEngine
    from src.monitoring.optimization_monitor import get_performance_monitor

    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

    # 测试CPU性能
    print("\n🔵 测试CPU引擎(5秒)...")
    cpu_monitor = get_performance_monitor()
    cpu_monitor.start()

    cpu_engine = KeyCollisionEngine(
        targets=targets,
        use_performance_optimization=True
    )

    # 手动生成一些地址
    import secrets
    start_time = time.time()
    count = 0
    while time.time() - start_time < 5:
        pk = secrets.token_bytes(32)
        cpu_engine.generator.generate_from_private_key(pk)
        count += 1

    cpu_monitor.record_metrics(
        addresses_generated=count,
        elapsed_time=5.0,
        optimization_enabled=True
    )

    cpu_speed = cpu_monitor.get_average_speed(window_seconds=5.0)
    print(f"  CPU速度: {cpu_speed:,.0f} addresses/s")

    # 测试GPU性能
    print("\n🟢 测试GPU引擎(5秒)...")
    gpu_engine = GPUCollisionEngine(
        targets=targets,
        batch_size=100000
    )

    gpu_monitor = gpu_engine.gpu_performance_monitor

    gpu_engine.start(mode='random')
    time.sleep(5)
    gpu_engine.stop()

    gpu_report = gpu_monitor.get_performance_report()
    gpu_speed = gpu_report.avg_throughput_keys_per_sec

    print(f"  GPU速度: {gpu_speed:,.0f} keys/s")

    # 对比
    if cpu_speed > 0:
        speedup = gpu_speed / cpu_speed
        print("\n📊 性能对比:")
        print(f"  GPU加速比: {speedup:.2f}x")
        print(f"  GPU比CPU快: {(speedup-1)*100:.0f}%")

    print()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("GPU性能监控使用示例")
    print("="*80)
    print()

    try:
        example_1_basic_gpu_monitoring()
    except Exception as e:
        print(f"示例1失败: {e}")

    try:
        example_2_real_time_monitoring()
    except Exception as e:
        print(f"示例2失败: {e}")

    try:
        example_3_memory_tracking()
    except Exception as e:
        print(f"示例3失败: {e}")

    try:
        example_4_comparison_cpu_vs_gpu()
    except Exception as e:
        print(f"示例4失败: {e}")

    print("="*80)
    print("所有示例完成!")
