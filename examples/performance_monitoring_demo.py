"""
性能监控使用示例
演示如何使用OptimizationPerformanceMonitor监控优化效果
"""
import secrets
import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.address_generator import P2PKHAddressGenerator
from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator
from src.monitoring.optimization_monitor import OptimizationPerformanceMonitor, get_performance_monitor


def example_1_basic_monitoring():
    """示例1: 基本性能监控"""
    print("="*80)
    print("示例1: 基本性能监控")
    print("="*80)

    # 创建监控器
    monitor = OptimizationPerformanceMonitor(check_interval=2.0)
    monitor.start()

    try:
        # 模拟碰撞引擎工作
        generator = OptimizedP2PKHAddressGenerator()

        total_addresses = 0
        batch_size = 50
        num_batches = 5

        for batch in range(num_batches):
            start = time.perf_counter()
            generation_times = []

            for _ in range(batch_size):
                pk = secrets.token_bytes(32)

                pk_start = time.perf_counter()
                generator.generate_from_private_key(pk)
                pk_time = (time.perf_counter() - pk_start) * 1000  # 转毫秒

                generation_times.append(pk_time)

            elapsed = time.perf_counter() - start
            total_addresses += batch_size

            # 记录指标
            monitor.record_metrics(
                addresses_generated=batch_size,
                elapsed_time=elapsed,
                optimization_enabled=True,
                precomputed_table=True,
                simd_hash=True,
                memory_pool=True,
                generation_times=generation_times
            )

            print(f"批次 {batch+1}/{num_batches}: "
                  f"{batch_size} 地址, {elapsed:.2f}s, "
                  f"{batch_size/elapsed:.0f} addr/s")

            time.sleep(0.5)  # 模拟实际工作间隔

        # 获取性能报告
        report = monitor.get_performance_report()

        print("\n" + "="*80)
        print("性能报告")
        print("="*80)
        print(f"  总地址数: {report['summary']['total_addresses']}")
        print(f"  峰值速度: {report['summary']['peak_speed']:.0f} addr/s")
        print(f"  平均速度: {report['summary']['avg_speed']:.0f} addr/s")
        print(f"  稳定性: {report['summary']['stability']:.1f}%")
        print(f"  优化启用率: {report['optimization']['enabled_percentage']:.1f}%")
        print(f"  平均延迟: {report['latency']['avg_ms']:.2f}ms")

    finally:
        monitor.stop()


def example_2_degradation_detection():
    """示例2: 性能退化检测"""
    print("\n" + "="*80)
    print("示例2: 性能退化检测")
    print("="*80)

    monitor = OptimizationPerformanceMonitor(
        check_interval=1.0,
        degradation_threshold=0.8  # 下降20%触发告警
    )

    # 注册退化回调
    def on_degradation(metrics, ratio):
        print("\n  ⚠️ 性能退化告警!")
        print(f"     当前速度: {metrics.speed:.0f} addr/s")
        print(f"     峰值速度: {monitor._peak_speed:.0f} addr/s")
        print(f"     退化率: {ratio:.2%}")

    monitor.on_degradation(on_degradation)
    monitor.start()

    try:
        generator = OptimizedP2PKHAddressGenerator()

        # 正常性能阶段
        print("\n  [阶段1] 正常性能")
        for i in range(3):
            start = time.perf_counter()
            for _ in range(20):
                pk = secrets.token_bytes(32)
                generator.generate_from_private_key(pk)
            elapsed = time.perf_counter() - start

            monitor.record_metrics(
                addresses_generated=20,
                elapsed_time=elapsed,
                optimization_enabled=True
            )

            print(f"    批次 {i+1}: {20/elapsed:.0f} addr/s")
            time.sleep(0.3)

        # 模拟性能退化(添加延迟)
        print("\n  [阶段2] 模拟性能退化")
        for i in range(3):
            start = time.perf_counter()
            for _ in range(20):
                pk = secrets.token_bytes(32)
                generator.generate_from_private_key(pk)
                time.sleep(0.05)  # 人为添加延迟
            elapsed = time.perf_counter() - start

            monitor.record_metrics(
                addresses_generated=20,
                elapsed_time=elapsed,
                optimization_enabled=True
            )

            print(f"    批次 {i+1}: {20/elapsed:.0f} addr/s")
            time.sleep(0.3)

    finally:
        monitor.stop()


def example_3_metrics_export():
    """示例3: 指标导出"""
    print("\n" + "="*80)
    print("示例3: 指标导出")
    print("="*80)

    monitor = OptimizationPerformanceMonitor()
    monitor.start()

    try:
        # 记录一些指标
        generator = OptimizedP2PKHAddressGenerator()

        for _ in range(3):
            start = time.perf_counter()
            for _ in range(10):
                pk = secrets.token_bytes(32)
                generator.generate_from_private_key(pk)
            elapsed = time.perf_counter() - start

            monitor.record_metrics(
                addresses_generated=10,
                elapsed_time=elapsed,
                optimization_enabled=True
            )

        # 导出JSON
        json_data = monitor.export_metrics(format='json')
        print("\n  JSON格式(前200字符):")
        print(f"  {json_data[:200]}...")

        # 导出CSV
        csv_data = monitor.export_metrics(format='csv')
        print("\n  CSV格式:")
        for line in csv_data.split('\n')[:5]:
            print(f"  {line}")

    finally:
        monitor.stop()


def example_4_global_monitor():
    """示例4: 全局监控器"""
    print("\n" + "="*80)
    print("示例4: 全局性能监控器")
    print("="*80)

    # 获取全局监控器
    monitor = get_performance_monitor()
    monitor.start()

    try:
        # 模拟工作负载
        generator = OptimizedP2PKHAddressGenerator()

        start = time.perf_counter()
        for _ in range(50):
            pk = secrets.token_bytes(32)
            generator.generate_from_private_key(pk)
        elapsed = time.perf_counter() - start

        # 记录指标
        monitor.record_metrics(
            addresses_generated=50,
            elapsed_time=elapsed,
            optimization_enabled=True,
            precomputed_table=True,
            simd_hash=True,
            memory_pool=True
        )

        # 获取当前指标
        current = monitor.get_current_metrics()
        if current:
            print("\n  当前性能:")
            print(f"    速度: {current.speed:.0f} addr/s")
            print(f"    延迟: {current.avg_generation_time_ms:.2f}ms")
            print(f"    优化: {current.optimization_enabled}")

        # 获取平均速度
        avg_speed = monitor.get_average_speed(window_seconds=60.0)
        print(f"    平均速度(60s窗口): {avg_speed:.0f} addr/s")

    finally:
        monitor.stop()


def example_5_comparison_monitoring():
    """示例5: 优化版vs标准版对比监控"""
    print("\n" + "="*80)
    print("示例5: 优化版vs标准版对比监控")
    print("="*80)

    num_keys = 100
    test_keys = [secrets.token_bytes(32) for _ in range(num_keys)]

    # 监控优化版
    monitor_opt = OptimizationPerformanceMonitor()
    monitor_opt.start()

    generator_opt = OptimizedP2PKHAddressGenerator()

    start = time.perf_counter()
    for pk in test_keys:
        generator_opt.generate_from_private_key(pk)
    elapsed_opt = time.perf_counter() - start

    monitor_opt.record_metrics(
        addresses_generated=num_keys,
        elapsed_time=elapsed_opt,
        optimization_enabled=True
    )

    monitor_opt.stop()

    # 监控标准版
    monitor_std = OptimizationPerformanceMonitor()
    monitor_std.start()

    generator_std = P2PKHAddressGenerator()

    start = time.perf_counter()
    for pk in test_keys:
        generator_std.generate_address(pk)
    elapsed_std = time.perf_counter() - start

    monitor_std.record_metrics(
        addresses_generated=num_keys,
        elapsed_time=elapsed_std,
        optimization_enabled=False
    )

    monitor_std.stop()

    # 对比结果
    report_opt = monitor_opt.get_performance_report()
    report_std = monitor_std.get_performance_report()

    print("\n  优化版:")
    print(f"    速度: {report_opt['summary']['avg_speed']:.0f} addr/s")
    print(f"    耗时: {elapsed_opt:.2f}s")
    print("    优化: 已启用")

    print("\n  标准版:")
    print(f"    速度: {report_std['summary']['avg_speed']:.0f} addr/s")
    print(f"    耗时: {elapsed_std:.2f}s")
    print("    优化: 未启用")

    speedup = elapsed_std / elapsed_opt if elapsed_opt > 0 else 0
    print("\n  性能对比:")
    print(f"    加速比: {speedup:.2f}x")

    if speedup > 1:
        print("    ✅ 优化版更快")
    else:
        print("    ⚠️ 标准版更快(可能使用coincurve)")


def main():
    """运行所有示例"""
    print("\n" + "="*80)
    print("性能监控系统使用示例")
    print("="*80)

    try:
        example_1_basic_monitoring()
        example_2_degradation_detection()
        example_3_metrics_export()
        example_4_global_monitor()
        example_5_comparison_monitoring()
    except Exception as e:
        print(f"\n示例执行失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("所有示例完成!")
    print("="*80)


if __name__ == '__main__':
    main()
