# -*- coding: utf-8 -*-
"""
压力测试 - 验证优化模块在高负载下的表现

测试场景:
1. 大量地址生成(10万)
2. 长时间运行(10分钟)
3. 高并发(8线程)
4. 内存稳定性
"""

import sys
import time
import secrets
import threading
import tracemalloc
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator  # noqa: E402
from src.monitoring.optimization_monitor import OptimizationPerformanceMonitor  # noqa: E402


def stress_test_1_large_volume():
    """压力测试1: 大量地址生成(10万)"""
    print("=" * 80)
    print("压力测试1: 大量地址生成(100,000)")
    print("=" * 80)

    generator = OptimizedP2PKHAddressGenerator()
    monitor = OptimizationPerformanceMonitor()
    monitor.start()

    total_addresses = 100000
    batch_size = 1000
    num_batches = total_addresses // batch_size

    start_time = time.perf_counter()
    total_generated = 0

    try:
        for batch in range(num_batches):
            batch_start = time.perf_counter()
            generation_times = []

            for _ in range(batch_size):
                pk = secrets.token_bytes(32)

                pk_start = time.perf_counter()
                generator.generate_from_private_key(pk)
                pk_time = (time.perf_counter() - pk_start) * 1000

                generation_times.append(pk_time)

            batch_elapsed = time.perf_counter() - batch_start
            total_generated += batch_size

            # 记录指标
            monitor.record_metrics(
                addresses_generated=batch_size,
                elapsed_time=batch_elapsed,
                optimization_enabled=True,
                generation_times=generation_times,
            )

            # 每10批显示进度
            if (batch + 1) % 10 == 0:
                elapsed = time.perf_counter() - start_time
                speed = total_generated / elapsed
                print(
                    f"  进度: {total_generated:,}/{total_addresses:,} "
                    f"({total_generated / total_addresses * 100:.1f}%) - "
                    f"{speed:.0f} addr/s"
                )

        total_elapsed = time.perf_counter() - start_time
        avg_speed = total_generated / total_elapsed

        print("\n  ✅ 完成!")
        print(f"  总地址数: {total_generated:,}")
        print(f"  总耗时: {total_elapsed:.2f}s")
        print(f"  平均速度: {avg_speed:.0f} addr/s")

        # 获取报告
        report = monitor.get_performance_report()
        print(f"  峰值速度: {report['summary']['peak_speed']:.0f} addr/s")
        print(f"  稳定性: {report['summary']['stability']:.1f}%")

    finally:
        monitor.stop()


def stress_test_2_long_running():
    """压力测试2: 长时间运行(5分钟)"""
    print("\n" + "=" * 80)
    print("压力测试2: 长时间运行(5分钟)")
    print("=" * 80)

    generator = OptimizedP2PKHAddressGenerator()
    monitor = OptimizationPerformanceMonitor()
    monitor.start()

    duration = 300  # 5分钟
    start_time = time.perf_counter()
    total_generated = 0

    try:
        while (time.perf_counter() - start_time) < duration:
            batch_start = time.perf_counter()
            batch_count = 1000

            for _ in range(batch_count):
                pk = secrets.token_bytes(32)
                generator.generate_from_private_key(pk)

            batch_elapsed = time.perf_counter() - batch_start
            total_generated += batch_count

            # 记录指标
            monitor.record_metrics(
                addresses_generated=batch_count,
                elapsed_time=batch_elapsed,
                optimization_enabled=True,
            )

            # 每30秒显示进度
            elapsed = time.perf_counter() - start_time
            if int(elapsed) % 30 == 0:
                speed = total_generated / elapsed
                duration - elapsed
                print(
                    f"  已运行: {elapsed:.0f}s/{duration}s "
                    f"({elapsed / duration * 100:.1f}%) - "
                    f"已生成: {total_generated:,} - "
                    f"速度: {speed:.0f} addr/s"
                )
                time.sleep(1)  # 避免重复打印

        total_elapsed = time.perf_counter() - start_time
        avg_speed = total_generated / total_elapsed

        print("\n  ✅ 完成!")
        print(f"  运行时间: {total_elapsed:.0f}s")
        print(f"  总地址数: {total_generated:,}")
        print(f"  平均速度: {avg_speed:.0f} addr/s")

    finally:
        monitor.stop()


def stress_test_3_high_concurrency():
    """压力测试3: 高并发(8线程,50,000地址)"""
    print("\n" + "=" * 80)
    print("压力测试3: 高并发(8线程, 50,000地址)")
    print("=" * 80)

    generator = OptimizedP2PKHAddressGenerator()
    monitor = OptimizationPerformanceMonitor()
    monitor.start()

    total_addresses = 50000
    num_threads = 8
    addresses_per_thread = total_addresses // num_threads

    errors = []
    results = []
    lock = threading.Lock()

    def worker(thread_id):
        try:
            thread_generated = 0
            generation_times = []

            for _ in range(addresses_per_thread):
                pk = secrets.token_bytes(32)

                pk_start = time.perf_counter()
                generator.generate_from_private_key(pk)
                pk_time = (time.perf_counter() - pk_start) * 1000

                generation_times.append(pk_time)
                thread_generated += 1

            with lock:
                results.append(thread_generated)
                monitor.record_metrics(
                    addresses_generated=thread_generated,
                    elapsed_time=sum(generation_times) / 1000,
                    optimization_enabled=True,
                    generation_times=generation_times[:100],  # 只记录前100个
                )
        except Exception as e:
            with lock:
                errors.append((thread_id, e))

    start_time = time.perf_counter()

    # 启动线程
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()

    # 等待完成
    for i, t in enumerate(threads):
        t.join()
        print(f"  线程 {i + 1}/{num_threads} 完成")

    total_elapsed = time.perf_counter() - start_time
    total_generated = sum(results)

    print("\n  ✅ 完成!")
    print(f"  线程数: {num_threads}")
    print(f"  总地址数: {total_generated:,}")
    print(f"  总耗时: {total_elapsed:.2f}s")
    print(f"  平均速度: {total_generated / total_elapsed:.0f} addr/s")
    print(f"  错误数: {len(errors)}")

    monitor.stop()

    if errors:
        print("\n  ❌ 发现错误:")
        for thread_id, error in errors:
            print(f"    线程 {thread_id}: {error}")


def stress_test_4_memory_stability():
    """压力测试4: 内存稳定性(监控内存泄漏)"""
    print("\n" + "=" * 80)
    print("压力测试4: 内存稳定性(50,000地址)")
    print("=" * 80)

    # 启动内存跟踪
    tracemalloc.start()

    generator = OptimizedP2PKHAddressGenerator()

    # 初始内存
    initial_snapshot = tracemalloc.take_snapshot()

    total_addresses = 50000
    batch_size = 10000

    print(f"\n  开始生成 {total_addresses:,} 个地址...")

    for batch in range(total_addresses // batch_size):
        for _ in range(batch_size):
            pk = secrets.token_bytes(32)
            generator.generate_from_private_key(pk)

        # 检查内存
        current, peak = tracemalloc.get_traced_memory()
        print(f"  批次 {
            batch
            + 1}: 当前={
            current
            / 1024
            / 1024:.2f}MB, " f"峰值={
                peak
                / 1024
            / 1024:.2f}MB")

    # 最终内存
    final_snapshot = tracemalloc.take_snapshot()
    current, peak = tracemalloc.get_traced_memory()

    # 分析内存差异
    top_stats = final_snapshot.compare_to(initial_snapshot, "lineno")

    print("\n  ✅ 完成!")
    print(f"  当前内存: {current / 1024 / 1024:.2f}MB")
    print(f"  峰值内存: {peak / 1024 / 1024:.2f}MB")

    # 显示前5个内存增长最多的位置
    print("\n  内存增长TOP 5:")
    for stat in top_stats[:5]:
        print(f"    {stat}")

    tracemalloc.stop()


def main():
    """运行所有压力测试"""
    print("\n" + "=" * 80)
    print("优化模块压力测试套件")
    print("=" * 80)

    try:
        # 测试1: 大量地址生成
        stress_test_1_large_volume()

        # 测试2: 长时间运行(可选,取消注释启用)
        # stress_test_2_long_running()

        # 测试3: 高并发
        stress_test_3_high_concurrency()

        # 测试4: 内存稳定性
        stress_test_4_memory_stability()

    except KeyboardInterrupt:
        print("\n\n  ⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n\n  ❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("压力测试完成!")
    print("=" * 80)


if __name__ == "__main__":
    main()
